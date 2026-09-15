from __future__ import annotations
import hashlib
import shutil
from pathlib import Path
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class LocalEvidenceVault75Service:
    """Build 75.0 local evidence vault.

    Stores imported public/user-provided artifacts under a case-specific vault,
    records SHA-256 hashes, supports verification and links artifacts to captures,
    claims or graph elements without weakening public-only boundaries.
    """
    def __init__(self, db: Database, audit: AuditService, vault_dir: str | Path):
        self.db = db
        self.audit = audit
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS local_evidence_items_75 (
          evidence_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, title TEXT NOT NULL, original_path TEXT DEFAULT '', stored_path TEXT NOT NULL,
          artifact_type TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, source_ref TEXT DEFAULT '', linked_object_type TEXT DEFAULT '', linked_object_id TEXT DEFAULT '',
          custody_status TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at TEXT NOT NULL, verified_at TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_localevidence75_case ON local_evidence_items_75(case_id, created_at);
        """)
        self.db.conn.commit()

    def ingest_file(self, case_id: str, path: str | Path, title: str = "public evidence file", artifact_type: str = "file", source_ref: str = "", linked_object_type: str = "", linked_object_id: str = "", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        src = Path(path)
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(str(src))
        eid = new_id("ev75")
        case_dir = self.vault_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        suffix = src.suffix[:20]
        dest = case_dir / f"{eid}{suffix}"
        shutil.copy2(src, dest)
        digest = self._sha_file(dest)
        size = dest.stat().st_size
        self.db.execute("""INSERT INTO local_evidence_items_75(evidence_id,case_id,title,original_path,stored_path,artifact_type,sha256,size_bytes,source_ref,linked_object_type,linked_object_id,custody_status,metadata_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [eid, case_id, title, str(src), str(dest), artifact_type, digest, size, source_ref, linked_object_type, linked_object_id, "stored_to_review", dumps(metadata or {}), now_ts()])
        self.audit.log("ingest", "local_evidence_item_75", eid, case_id, {"sha256": digest, "artifact_type": artifact_type})
        return self.get_item(eid)

    def ingest_text(self, case_id: str, title: str, text: str, artifact_type: str = "text_note", source_ref: str = "", linked_object_type: str = "", linked_object_id: str = "", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        tmp_dir = self.vault_dir / "_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp = tmp_dir / f"{new_id('tmp')}.txt"
        tmp.write_text(text or "", encoding="utf-8")
        try:
            return self.ingest_file(case_id, tmp, title=title, artifact_type=artifact_type, source_ref=source_ref, linked_object_type=linked_object_type, linked_object_id=linked_object_id, metadata=metadata)
        finally:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass

    def verify_item(self, evidence_id: str) -> Dict[str, Any]:
        item = self.get_item(evidence_id)
        problems: List[str] = []
        p = Path(item["stored_path"])
        if not p.exists():
            problems.append("stored_file_missing")
        elif self._sha_file(p) != item.get("sha256"):
            problems.append("sha256_mismatch")
        status = "verified" if not problems else "tamper_warning"
        self.db.execute("UPDATE local_evidence_items_75 SET custody_status=?, verified_at=? WHERE evidence_id=?", [status, now_ts(), evidence_id])
        self.audit.log("verify", "local_evidence_item_75", evidence_id, item["case_id"], {"status": status, "problems": problems})
        return {"evidence_id": evidence_id, "valid": not problems, "problems": problems, "custody_status": status}

    def get_item(self, evidence_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM local_evidence_items_75 WHERE evidence_id=?", [evidence_id])
        if not row:
            raise KeyError(evidence_id)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row

    def list_case_items(self, case_id: str) -> List[Dict[str, Any]]:
        return [self.get_item(r["evidence_id"]) for r in self.db.all("SELECT evidence_id FROM local_evidence_items_75 WHERE case_id=? ORDER BY created_at DESC", [case_id])]

    def _sha_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
