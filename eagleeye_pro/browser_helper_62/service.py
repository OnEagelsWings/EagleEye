from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)


def _domain(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


class BrowserHelperOneClickCapture62Service:
    """Build 62.0: one-click/browser-helper capture foundation.

    This service does not crawl the web and does not bypass access controls. It
    produces a local helper/bookmarklet payload format and imports user-initiated
    visible browser captures into the existing Capture Pro / Fund Intelligence
    pipeline.
    """

    def __init__(self, db: Database, audit: AuditService, *, capture_pro=None, fund_intel=None, helper_root: str | Path | None = None):
        self.db = db
        self.audit = audit
        self.capture_pro = capture_pro
        self.fund_intel = fund_intel
        self.helper_root = Path(helper_root) if helper_root else Path.cwd() / "browser_helper_62"
        self.helper_root.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS browser_helper_sessions_62 (
          helper_session_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          token TEXT NOT NULL,
          status TEXT DEFAULT 'active',
          helper_path TEXT DEFAULT '',
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS browser_helper_imports_62 (
          helper_import_id TEXT PRIMARY KEY,
          helper_session_id TEXT DEFAULT '',
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          title TEXT NOT NULL,
          url TEXT NOT NULL,
          domain TEXT DEFAULT '',
          snippet TEXT DEFAULT '',
          query TEXT DEFAULT '',
          engine TEXT DEFAULT '',
          category_key TEXT DEFAULT '',
          capture_result_id TEXT DEFAULT '',
          intelligence_id TEXT DEFAULT '',
          person_finding_id TEXT DEFAULT '',
          status TEXT DEFAULT 'imported',
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_bh62_entity ON browser_helper_imports_62(case_id, entity_id, created_at DESC);
        ''')
        self.db.conn.commit()

    def create_helper_session(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        if not case_id or not entity_id:
            raise ValueError("case_id and entity_id are required")
        sid = new_id("bh62")
        token = new_id("tok62")
        path = self.helper_root / f"EagleEye_Browser_Helper_{sid}.html"
        path.write_text(self._helper_html(sid, token), encoding="utf-8")
        self.db.execute('''INSERT INTO browser_helper_sessions_62(helper_session_id,case_id,entity_id,token,status,helper_path,created_at)
        VALUES(?,?,?,?,?,?,?)''', [sid, case_id, entity_id, token, "active", str(path), now_ts()])
        self.audit.log("create", "browser_helper_session_62", sid, case_id, {"entity_id": entity_id, "path": str(path)})
        return {"helper_session_id": sid, "case_id": case_id, "entity_id": entity_id, "token": token, "helper_path": str(path), "bookmarklet": self.bookmarklet(sid, token)}

    def bookmarklet(self, helper_session_id: str, token: str) -> str:
        js = (
            "javascript:(()=>{"
            "const p={title:document.title,url:location.href,snippet:(window.getSelection?String(window.getSelection()):''),"
            f"helper_session_id:'{helper_session_id}',token:'{token}',captured_at:new Date().toISOString()}};"
            "prompt('EagleEye Capture JSON kopieren:',JSON.stringify(p,null,2));"
            "})()"
        )
        return js

    def import_payload(self, case_id: str, entity_id: str, payload: str | Dict[str, Any], *, category_key: str = "", query: str = "", engine: str = "browser_helper") -> Dict[str, Any]:
        data = self._parse_payload(payload)
        title = _clean(data.get("title") or data.get("name") or "Öffentlicher Browser-Treffer")
        url = _clean(data.get("url") or data.get("href") or "")
        snippet = _clean(data.get("snippet") or data.get("selection") or data.get("text") or data.get("description") or "")
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("Der Capture-Payload muss eine öffentliche http(s)-URL enthalten.")
        cat = category_key or _clean(data.get("category_key", ""))
        q = query or _clean(data.get("query", ""))
        eng = engine or _clean(data.get("engine", "browser_helper"))
        session_id = _clean(data.get("helper_session_id", ""))
        cap = None
        intel = None
        if self.capture_pro:
            cap_res = self.capture_pro.import_url(case_id, entity_id, url, title=title, snippet=snippet, category_key=cat, query=q, engine=eng)
            cap = cap_res.get("result") or {}
        if self.fund_intel and cap and cap.get("capture_result_id"):
            intel = self.fund_intel.import_capture_to_person_file(cap["capture_result_id"])
        import_id = new_id("bhimp62")
        self.db.execute('''INSERT INTO browser_helper_imports_62(helper_import_id,helper_session_id,case_id,entity_id,title,url,domain,snippet,query,engine,category_key,capture_result_id,intelligence_id,person_finding_id,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [import_id, session_id, case_id, entity_id, title, url, _domain(url), snippet, q, eng, cat, (cap or {}).get("capture_result_id", ""), (intel or {}).get("intelligence_id", ""), (intel or {}).get("person_finding_id", ""), "imported", now_ts()])
        self.audit.log("import", "browser_helper_capture_62", import_id, case_id, {"entity_id": entity_id, "domain": _domain(url), "person_finding_id": (intel or {}).get("person_finding_id", "")})
        return {"helper_import_id": import_id, "capture_result": cap, "fund_intelligence": intel, "person_finding_id": (intel or {}).get("person_finding_id", ""), "domain": _domain(url), "title": title, "url": url}

    def import_serp_clipboard(self, case_id: str, entity_id: str, raw_text: str, *, category_key: str = "", query: str = "", engine: str = "browser_clipboard") -> Dict[str, Any]:
        if not _clean(raw_text):
            raise ValueError("Bitte sichtbare Suchergebnisse oder Treffertext einfügen.")
        results: List[Dict[str, Any]] = []
        if self.capture_pro:
            batch = self.capture_pro.import_serp_block(case_id, entity_id, raw_text, category_key=category_key, query=query, engine=engine)
            for cap in batch.get("results", []):
                intel = self.fund_intel.import_capture_to_person_file(cap["capture_result_id"]) if self.fund_intel else None
                results.append({"capture_result": cap, "fund_intelligence": intel})
        else:
            # fallback parser
            for url in URL_RE.findall(raw_text):
                results.append(self.import_payload(case_id, entity_id, {"url": url, "title": _domain(url), "snippet": raw_text[:500]}, category_key=category_key, query=query, engine=engine))
        return {"count": len(results), "results": results}

    def list_imports(self, case_id: str, entity_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM browser_helper_imports_62 WHERE case_id=? AND entity_id=? ORDER BY created_at DESC LIMIT ?", [case_id, entity_id, int(limit)])

    def _parse_payload(self, payload: str | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        text = str(payload or "").strip()
        if not text:
            raise ValueError("Leerer Capture-Payload.")
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        urls = URL_RE.findall(text)
        if not urls:
            raise ValueError("Kein URL im Capture-Payload gefunden.")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        title = next((l for l in lines if not URL_RE.search(l)), _domain(urls[0]))
        snippet = " ".join(l for l in lines if l != title and not l.startswith(urls[0]))[:900]
        return {"title": title, "url": urls[0], "snippet": snippet}

    def _helper_html(self, helper_session_id: str, token: str) -> str:
        bm = self.bookmarklet(helper_session_id, token).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"""<!doctype html>
<html><head><meta charset='utf-8'><title>EagleEye Browser Helper 62</title></head>
<body style='font-family:Arial,sans-serif;max-width:980px;margin:2rem auto;line-height:1.45'>
<h1>EagleEye Browser Helper – Build 62</h1>
<p>Dieser Helper erzeugt nur nutzerinitiierte Capture-Payloads aus sichtbaren öffentlichen Browserseiten. Er crawlt nicht, umgeht keine Logins, CAPTCHAs oder Paywalls und sendet nichts automatisch.</p>
<h2>Bookmarklet</h2>
<p>Lege diesen Link als Lesezeichen ab. Auf einer öffentlichen Trefferseite anklicken, JSON kopieren und in EagleEye importieren.</p>
<p><a href="{bm}">An EagleEye senden</a></p>
<h2>Session</h2>
<pre>helper_session_id: {helper_session_id}\ntoken: {token}</pre>
</body></html>"""
