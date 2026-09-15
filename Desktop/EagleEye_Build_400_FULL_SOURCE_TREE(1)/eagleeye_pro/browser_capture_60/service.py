from __future__ import annotations

from typing import Any, Dict, List
import hashlib
from urllib.parse import urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(str(part or "").encode("utf-8", errors="ignore")); h.update(b"\0")
    return h.hexdigest()


def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


class BrowserCaptureLocalHelper60Service:
    """Build 60.0 browser capture/local helper foundation.

    Captures are user-initiated payloads from visible public browser results. The
    service stores a local session token and queue entries; it does not crawl,
    scrape hidden content, bypass access controls or run a network server.
    """

    def __init__(self, db: Database, audit: AuditService, *, result_capture=None, provider_sdk=None):
        self.db = db
        self.audit = audit
        self.result_capture = result_capture
        self.provider_sdk = provider_sdk
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS browser_capture_sessions_60 (
          session_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          token_hash TEXT NOT NULL,
          status TEXT DEFAULT 'active',
          created_at TEXT NOT NULL,
          expires_at TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS browser_capture_queue_60 (
          capture_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          title TEXT NOT NULL,
          url TEXT NOT NULL,
          domain TEXT DEFAULT '',
          snippet TEXT DEFAULT '',
          query TEXT DEFAULT '',
          engine TEXT DEFAULT '',
          category_key TEXT DEFAULT '',
          normalized_id TEXT DEFAULT '',
          person_finding_id TEXT DEFAULT '',
          status TEXT DEFAULT 'queued',
          payload_hash TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_browser60_queue_session ON browser_capture_queue_60(session_id, created_at DESC);
        ''')
        self.db.conn.commit()

    def create_session(self, case_id: str, entity_id: str, *, ttl_minutes: int = 240) -> Dict[str, Any]:
        if not case_id or not entity_id:
            raise ValueError("case_id and entity_id are required")
        session_id = new_id("bcap60")
        token = new_id("tok60")
        self.db.execute('''INSERT INTO browser_capture_sessions_60(session_id,case_id,entity_id,token_hash,status,created_at,expires_at)
        VALUES(?,?,?,?,?,?,?)''', [session_id, case_id, entity_id, _sha(token), "active", now_ts(), f"ttl_minutes:{int(ttl_minutes)}"])
        self.audit.log("create", "browser_capture_session_60", session_id, case_id, {"entity_id": entity_id})
        return {"session_id": session_id, "case_id": case_id, "entity_id": entity_id, "token": token, "localhost_mode": True, "instructions": "Capture visible public results only; paste or send title/url/snippet/query/engine."}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM browser_capture_sessions_60 WHERE session_id=?", [session_id])
        if not row:
            raise KeyError(session_id)
        return row

    def import_capture(self, session_id: str, payload: Dict[str, Any], *, token: str = "") -> Dict[str, Any]:
        session = self.get_session(session_id)
        if session.get("status") != "active":
            raise ValueError("capture session is not active")
        if token and _sha(token) != session.get("token_hash"):
            raise PermissionError("invalid capture token")
        title = str(payload.get("title") or "").strip()
        url = str(payload.get("url") or "").strip()
        snippet = str(payload.get("snippet") or "").strip()
        query = str(payload.get("query") or "").strip()
        engine = str(payload.get("engine") or "").strip()
        category_key = str(payload.get("category_key") or "").strip()
        if not title or not url:
            raise ValueError("title and url are required")
        payload_hash = _sha(title, url, snippet, query, engine, category_key)
        normalized_id = ""
        if self.provider_sdk:
            norm = self.provider_sdk.normalize_results("browser_result_helper", [{"title": title, "url": url, "snippet": snippet}], case_id=session["case_id"], entity_id=session["entity_id"])
            if norm.get("results"):
                normalized_id = norm["results"][0].get("normalized_id", "")
        person_finding_id = ""
        if self.result_capture:
            try:
                imported = self.result_capture.import_url_fund(session["case_id"], session["entity_id"], url, title=title, snippet=snippet, category=category_key or "browser_capture", engine=engine or "browser")
                person_finding_id = imported.get("person_finding_id", "") or imported.get("finding_id", "")
            except Exception:
                person_finding_id = ""
        capture_id = new_id("bcq60")
        try:
            self.db.execute('''INSERT INTO browser_capture_queue_60(capture_id,session_id,case_id,entity_id,title,url,domain,snippet,query,engine,category_key,normalized_id,person_finding_id,status,payload_hash,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [capture_id, session_id, session["case_id"], session["entity_id"], title, url, _domain(url), snippet, query, engine, category_key, normalized_id, person_finding_id, "imported" if person_finding_id else "queued", payload_hash, now_ts()])
        except Exception:
            existing = self.db.one("SELECT * FROM browser_capture_queue_60 WHERE session_id=? AND payload_hash=?", [session_id, payload_hash])
            if existing:
                capture_id = existing["capture_id"]
        self.audit.log("import", "browser_capture_60", capture_id, session["case_id"], {"engine": engine, "domain": _domain(url), "person_finding_id": person_finding_id})
        return {"capture_id": capture_id, "session_id": session_id, "normalized_id": normalized_id, "person_finding_id": person_finding_id, "status": "imported" if person_finding_id else "queued", "domain": _domain(url)}

    def queue(self, session_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM browser_capture_queue_60 WHERE session_id=? ORDER BY created_at DESC", [session_id])
