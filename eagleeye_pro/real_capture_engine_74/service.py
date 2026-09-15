from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.url_policy import URLPolicy

class RealCaptureEngine74Service:
    """Build 74.0 lawful real capture engine foundation.

    Captures user-supplied public HTML/text snapshots into a local evidence path,
    normalizes the URL, extracts basic metadata, hashes every artifact and links
    it into CaptureVault69. Live network fetching is intentionally not automatic.
    """
    def __init__(self, db: Database, audit: AuditService, capture_dir: str | Path, *, capture_vault=None):
        self.db = db
        self.audit = audit
        self.capture_dir = Path(capture_dir)
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.capture_vault = capture_vault
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS real_captures_74 (
          capture_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, url TEXT NOT NULL, normalized_url TEXT NOT NULL,
          title TEXT NOT NULL, text_path TEXT DEFAULT '', html_path TEXT DEFAULT '', text_hash TEXT DEFAULT '', html_hash TEXT DEFAULT '',
          http_status INTEGER DEFAULT 0, content_type TEXT DEFAULT '', capture_vault_artifact_id TEXT DEFAULT '',
          metadata_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_realcapture74_case ON real_captures_74(case_id, created_at);
        """)
        self.db.conn.commit()

    def capture_snapshot(self, case_id: str, url: str, html: str = "", text: str = "", title: str = "", http_status: int = 0, content_type: str = "text/html", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        policy = URLPolicy.evaluate_capture_url(url)
        if not policy.get("ok"):
            raise ValueError("URL blocked by URLPolicy: " + str(policy.get("blocked_reason")))
        if not text and html:
            text = self.extract_text(html)
        if not title:
            title = self.extract_title(html) or "public web snapshot"
        cid = new_id("cap74")
        cdir = self.capture_dir / cid
        cdir.mkdir(parents=True, exist_ok=True)
        html_path = text_path = ""
        html_hash = text_hash = ""
        if html:
            html_path = str(cdir / "snapshot.html")
            Path(html_path).write_text(html, encoding="utf-8")
            html_hash = self._sha_text(html)
        if text:
            text_path = str(cdir / "snapshot.txt")
            Path(text_path).write_text(text, encoding="utf-8")
            text_hash = self._sha_text(text)
        vault_id = ""
        if self.capture_vault:
            artifact = self.capture_vault.record_text_capture(case_id, policy.get("normalized_url") or url, title, text or "", html=html or "", metadata={"real_capture_74": cid, **(metadata or {})})
            vault_id = artifact["artifact_id"]
        created = now_ts()
        self.db.execute("""INSERT INTO real_captures_74(capture_id,case_id,url,normalized_url,title,text_path,html_path,text_hash,html_hash,http_status,content_type,capture_vault_artifact_id,metadata_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [cid, case_id, url, policy.get("normalized_url") or url, title, text_path, html_path, text_hash, html_hash, int(http_status or 0), content_type, vault_id, dumps(metadata or {}), created])
        self.audit.log("capture", "real_capture_74", cid, case_id, {"normalized_url": policy.get("normalized_url") or url, "vault_artifact_id": vault_id})
        return self.get_capture(cid)

    def get_capture(self, capture_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM real_captures_74 WHERE capture_id=?", [capture_id])
        if not row:
            raise KeyError(capture_id)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row

    def verify_capture(self, capture_id: str) -> Dict[str, Any]:
        cap = self.get_capture(capture_id)
        problems = []
        if cap.get("text_path"):
            p = Path(cap["text_path"])
            if not p.exists() or self._sha_text(p.read_text(encoding="utf-8", errors="ignore")) != cap.get("text_hash"):
                problems.append("text_snapshot_hash_mismatch")
        if cap.get("html_path"):
            p = Path(cap["html_path"])
            if not p.exists() or self._sha_text(p.read_text(encoding="utf-8", errors="ignore")) != cap.get("html_hash"):
                problems.append("html_snapshot_hash_mismatch")
        return {"capture_id": capture_id, "valid": not problems, "problems": problems, "capture_vault_artifact_id": cap.get("capture_vault_artifact_id", "")}

    def list_case_captures(self, case_id: str):
        return [self.get_capture(r["capture_id"]) for r in self.db.all("SELECT capture_id FROM real_captures_74 WHERE case_id=? ORDER BY created_at DESC", [case_id])]

    def extract_title(self, html: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
        return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

    def extract_text(self, html: str) -> str:
        no_script = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html or "", flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", no_script)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _sha_text(self, value: str) -> str:
        return hashlib.sha256((value or "").encode("utf-8")).hexdigest()
