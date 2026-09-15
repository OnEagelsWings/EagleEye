from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.url_policy import URLPolicy

class CaptureVault69Service:
    """Build 69.0 capture vault foundation.

    Records metadata and hashes for lawful public captures. It intentionally does
    not bypass access controls and does not fetch private resources.
    """
    def __init__(self, db: Database, audit: AuditService, vault_dir: str | Path):
        self.db = db
        self.audit = audit
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS capture_artifacts_69 (
          artifact_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, url TEXT NOT NULL, normalized_url TEXT NOT NULL,
          title TEXT NOT NULL, capture_mode TEXT NOT NULL, text_hash TEXT NOT NULL, html_hash TEXT DEFAULT '',
          screenshot_hash TEXT DEFAULT '', file_hash TEXT DEFAULT '', storage_path TEXT DEFAULT '', metadata_json TEXT NOT NULL,
          custody_status TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_capture69_case ON capture_artifacts_69(case_id, created_at);
        """)
        self.db.conn.commit()

    def record_text_capture(self, case_id: str, url: str, title: str, text: str, html: str = "", screenshot_hash: str = "", metadata: Dict[str, Any] | None = None, persist_text: bool = True) -> Dict[str, Any]:
        policy = URLPolicy.evaluate_capture_url(url)
        if not policy.get("ok"):
            raise ValueError("URL blocked by URLPolicy: " + str(policy.get("blocked_reason")))
        aid = new_id("cap69")
        text_hash = hashlib.sha256((text or "").encode("utf-8")).hexdigest()
        html_hash = hashlib.sha256((html or "").encode("utf-8")).hexdigest() if html else ""
        storage_path = ""
        if persist_text:
            out = self.vault_dir / f"{aid}.txt"
            out.write_text(text or "", encoding="utf-8")
            storage_path = str(out)
        created = now_ts()
        self.db.execute("""INSERT INTO capture_artifacts_69(artifact_id,case_id,url,normalized_url,title,capture_mode,text_hash,html_hash,screenshot_hash,file_hash,storage_path,metadata_json,custody_status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [aid, case_id, url, policy.get("normalized_url") or url, title, "manual_public_text_capture", text_hash, html_hash, screenshot_hash, "", storage_path, dumps(metadata or {}), "captured_to_review", created])
        self.audit.log("record", "capture_artifact_69", aid, case_id, {"url": policy.get("normalized_url") or url, "text_hash": text_hash})
        return self.get_artifact(aid)

    def record_file_artifact(self, case_id: str, path: str | Path, source_url: str = "", title: str = "public file artifact", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        fp = Path(path)
        if not fp.exists() or not fp.is_file():
            raise FileNotFoundError(str(fp))
        policy = URLPolicy.evaluate_capture_url(source_url) if source_url else {"ok": True, "normalized_url": ""}
        if not policy.get("ok"):
            raise ValueError("URL blocked by URLPolicy: " + str(policy.get("blocked_reason")))
        aid = new_id("cap69")
        digest = self._sha_file(fp)
        self.db.execute("""INSERT INTO capture_artifacts_69(artifact_id,case_id,url,normalized_url,title,capture_mode,text_hash,html_hash,screenshot_hash,file_hash,storage_path,metadata_json,custody_status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [aid, case_id, source_url, policy.get("normalized_url") or source_url, title, "manual_public_file_capture", "", "", "", digest, str(fp), dumps(metadata or {}), "captured_to_review", now_ts()])
        self.audit.log("record", "capture_file_artifact_69", aid, case_id, {"file_hash": digest, "path": str(fp)})
        return self.get_artifact(aid)

    def get_artifact(self, artifact_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM capture_artifacts_69 WHERE artifact_id=?", [artifact_id])
        if not row:
            raise KeyError(artifact_id)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row

    def list_case_artifacts(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT artifact_id FROM capture_artifacts_69 WHERE case_id=? ORDER BY created_at DESC", [case_id])
        return [self.get_artifact(r["artifact_id"]) for r in rows]

    def verify_artifact(self, artifact_id: str) -> Dict[str, Any]:
        art = self.get_artifact(artifact_id)
        problems: List[str] = []
        if art.get("storage_path") and Path(art["storage_path"]).exists() and art.get("text_hash"):
            current = hashlib.sha256(Path(art["storage_path"]).read_text(encoding="utf-8", errors="ignore").encode("utf-8")).hexdigest()
            if current != art["text_hash"]:
                problems.append("text_hash_mismatch")
        if art.get("storage_path") and art.get("file_hash"):
            fp = Path(art["storage_path"])
            if not fp.exists():
                problems.append("file_missing")
            elif self._sha_file(fp) != art["file_hash"]:
                problems.append("file_hash_mismatch")
        return {"artifact_id": artifact_id, "valid": not problems, "problems": problems, "custody_status": art.get("custody_status")}

    def _sha_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
