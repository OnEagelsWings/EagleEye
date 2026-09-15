from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import base64
import hashlib
import json
import os
import zipfile

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, new_id, now_ts


class SecureCaseStorageService:
    """Build 51/54 secure storage package service.

    Creates sealed case packages with manifest hashes. Optional passphrase encryption
    uses cryptography.Fernet when available; otherwise the package remains integrity-
    sealed and explicitly marked as not encrypted.
    """

    def __init__(self, db: Database, audit: AuditService, storage_root: str | Path):
        self.db = db
        self.audit = audit
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS secure_case_packages_54 (
          package_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          package_type TEXT NOT NULL,
          package_path TEXT NOT NULL,
          manifest_path TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          encrypted INTEGER DEFAULT 0,
          encryption_method TEXT DEFAULT '',
          file_count INTEGER DEFAULT 0,
          created_at TEXT NOT NULL,
          notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_securepkg54_case ON secure_case_packages_54(case_id, created_at);
        ''')
        self.db.conn.commit()

    def create_package(self, case_id: str, *, package_type: str = "sealed_case_package", passphrase: str = "", include_reports: bool = True, include_evidence: bool = True, notes: str = "") -> Dict[str, Any]:
        package_id = new_id("pkg54")
        outdir = self.storage_root / case_id
        outdir.mkdir(parents=True, exist_ok=True)
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id]) or {}
        sources: List[Dict[str, Any]] = []
        if include_evidence and self._table_exists("evidence_vault_artifacts_50"):
            for row in self.db.all("SELECT artifact_id,title,stored_path,sha256,review_status,source_url FROM evidence_vault_artifacts_50 WHERE case_id=?", [case_id]):
                p = Path(row["stored_path"])
                if p.exists() and p.is_file():
                    sources.append({"kind": "evidence", "id": row["artifact_id"], "title": row["title"], "path": p, "sha256": row["sha256"], "source_url": row.get("source_url", "")})
        if include_reports and self._table_exists("handover_reports_50"):
            for row in self.db.all("SELECT report_id,report_path,content_hash FROM handover_reports_50 WHERE case_id=?", [case_id]):
                p = Path(row["report_path"])
                if p.exists() and p.is_file():
                    sources.append({"kind": "report", "id": row["report_id"], "title": p.name, "path": p, "sha256": row.get("content_hash", "")})
        manifest = {"build": "54.0", "package_id": package_id, "case_id": case_id, "case_title": case.get("title", ""), "package_type": package_type, "created_at": now_ts(), "files": []}
        zip_path = outdir / f"{package_id}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("CASE_SUMMARY.json", json.dumps({"case": case, "package_id": package_id, "created_at": manifest["created_at"]}, ensure_ascii=False, indent=2))
            for item in sources:
                arc = f"{item['kind']}/{item['id']}_{Path(item['path']).name}"
                zf.write(item["path"], arc)
                manifest["files"].append({"path": arc, "kind": item["kind"], "id": item["id"], "title": item["title"], "sha256": item.get("sha256") or self._sha256_file(item["path"]), "source_url": item.get("source_url", "")})
            zf.writestr("MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        final_path = zip_path
        encrypted = False
        encryption_method = "integrity_sealed_zip"
        if passphrase:
            encrypted_path = outdir / f"{package_id}.sealed"
            enc = self._encrypt_file_if_possible(zip_path, encrypted_path, passphrase)
            if enc["encrypted"]:
                final_path = encrypted_path
                encrypted = True
                encryption_method = enc["method"]
                zip_path.unlink(missing_ok=True)
            else:
                encryption_method = "integrity_sealed_zip_no_crypto_dependency"
        package_sha = self._sha256_file(final_path)
        manifest_path = outdir / f"{package_id}_manifest.json"
        manifest["package_sha256"] = package_sha
        manifest["encrypted"] = encrypted
        manifest["encryption_method"] = encryption_method
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.db.execute('''INSERT INTO secure_case_packages_54(package_id,case_id,package_type,package_path,manifest_path,sha256,encrypted,encryption_method,file_count,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [package_id, case_id, package_type, str(final_path), str(manifest_path), package_sha, int(encrypted), encryption_method, len(manifest["files"]), now_ts(), notes])
        self.audit.log("create", "secure_case_package_54", package_id, case_id, {"encrypted": encrypted, "file_count": len(manifest["files"]), "sha256": package_sha})
        return self.get_package(package_id)

    def get_package(self, package_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM secure_case_packages_54 WHERE package_id=?", [package_id])
        if not row:
            raise KeyError(package_id)
        return row

    def verify_package(self, package_id: str) -> Dict[str, Any]:
        pkg = self.get_package(package_id)
        p = Path(pkg["package_path"])
        ok = p.exists() and self._sha256_file(p) == pkg["sha256"]
        return {"package_id": package_id, "valid": bool(ok), "stored_sha256": pkg["sha256"], "current_sha256": self._sha256_file(p) if p.exists() else "", "encrypted": bool(pkg.get("encrypted"))}

    def _encrypt_file_if_possible(self, src: Path, dst: Path, passphrase: str) -> Dict[str, Any]:
        try:
            from cryptography.fernet import Fernet  # type: ignore
        except Exception:
            return {"encrypted": False, "method": "cryptography_not_available"}
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 390000, dklen=32)
        token = Fernet(base64.urlsafe_b64encode(key)).encrypt(src.read_bytes())
        dst.write_bytes(b"EAGLEEYE54-FERNET\n" + base64.b64encode(salt) + b"\n" + token)
        return {"encrypted": True, "method": "fernet_pbkdf2_sha256_390k"}

    def _sha256_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))
