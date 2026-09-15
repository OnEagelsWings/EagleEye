from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)


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


def _canonical(url: str) -> str:
    try:
        p = urlparse((url or "").strip())
        scheme = (p.scheme or "https").lower()
        host = p.netloc.lower().replace("www.", "")
        path = p.path.rstrip("/") or "/"
        return f"{scheme}://{host}{path}"
    except Exception:
        return (url or "").strip()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


class BrowserCaptureSERPImportProService:
    """Build 60.1: SERP/capture import layer.

    User-initiated import only: the service parses pasted public result blocks
    or single public URLs. It does not crawl, scrape hidden content or bypass
    access controls. It creates normalized capture candidates that downstream
    services can classify, score and link into the person file.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS capture_import_batches_60_1 (
          batch_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          category_key TEXT DEFAULT '',
          query TEXT DEFAULT '',
          engine TEXT DEFAULT '',
          import_mode TEXT NOT NULL,
          raw_hash TEXT NOT NULL,
          result_count INTEGER DEFAULT 0,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS capture_results_60_1 (
          capture_result_id TEXT PRIMARY KEY,
          batch_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          title TEXT NOT NULL,
          url TEXT NOT NULL,
          canonical_url TEXT NOT NULL,
          domain TEXT DEFAULT '',
          snippet TEXT DEFAULT '',
          position INTEGER DEFAULT 0,
          category_key TEXT DEFAULT '',
          query TEXT DEFAULT '',
          engine TEXT DEFAULT '',
          source_guess TEXT DEFAULT 'public_web',
          duplicate_key TEXT NOT NULL,
          status TEXT DEFAULT 'captured',
          created_at TEXT NOT NULL,
          UNIQUE(case_id, entity_id, duplicate_key)
        );
        CREATE INDEX IF NOT EXISTS idx_capture601_entity ON capture_results_60_1(case_id, entity_id, created_at DESC);
        ''')
        self.db.conn.commit()

    def import_serp_block(self, case_id: str, entity_id: str, raw_text: str, *, category_key: str = "", query: str = "", engine: str = "manual_serp") -> Dict[str, Any]:
        if not case_id or not entity_id:
            raise ValueError("case_id and entity_id are required")
        if not _clean(raw_text):
            raise ValueError("raw SERP text is required")
        parsed = self.parse_serp_text(raw_text)
        batch_id = new_id("cap601")
        now = now_ts()
        created: List[Dict[str, Any]] = []
        for idx, item in enumerate(parsed, start=1):
            row = self._upsert_result(batch_id, case_id, entity_id, item, idx, category_key=category_key, query=query, engine=engine, now=now)
            created.append(row)
        self.db.execute('''INSERT INTO capture_import_batches_60_1(batch_id,case_id,entity_id,category_key,query,engine,import_mode,raw_hash,result_count,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [batch_id, case_id, entity_id, category_key, query, engine, "serp_paste", _sha(raw_text)[:32], len(created), now])
        self.audit.log("import", "capture_serp_batch_60_1", batch_id, case_id, {"entity_id": entity_id, "count": len(created), "engine": engine})
        return {"batch_id": batch_id, "count": len(created), "results": created}

    def import_url(self, case_id: str, entity_id: str, url: str, *, title: str = "", snippet: str = "", category_key: str = "", query: str = "", engine: str = "manual_url") -> Dict[str, Any]:
        if not url or not url.strip().lower().startswith(("http://", "https://")):
            raise ValueError("A public http(s) URL is required")
        raw = "\n".join([title or url, url, snippet])
        batch_id = new_id("cap601")
        now = now_ts()
        item = {"title": title or url, "url": url, "snippet": snippet}
        row = self._upsert_result(batch_id, case_id, entity_id, item, 1, category_key=category_key, query=query, engine=engine, now=now)
        self.db.execute('''INSERT INTO capture_import_batches_60_1(batch_id,case_id,entity_id,category_key,query,engine,import_mode,raw_hash,result_count,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [batch_id, case_id, entity_id, category_key, query, engine, "single_url", _sha(raw)[:32], 1, now])
        return {"batch_id": batch_id, "count": 1, "result": row, "results": [row]}

    def parse_serp_text(self, raw_text: str) -> List[Dict[str, str]]:
        lines = [_clean(x) for x in raw_text.splitlines() if _clean(x)]
        results: List[Dict[str, str]] = []
        seen = set()
        for i, line in enumerate(lines):
            urls = URL_RE.findall(line)
            for url in urls:
                can = _canonical(url)
                if can in seen:
                    continue
                seen.add(can)
                title = ""
                snippet_parts: List[str] = []
                # nearby previous non-url line is usually the title
                for j in range(i - 1, max(-1, i - 4), -1):
                    if j >= 0 and not URL_RE.search(lines[j]) and len(lines[j]) > 2:
                        title = lines[j]
                        break
                if not title:
                    title = _domain(url) or url
                for j in range(i + 1, min(len(lines), i + 4)):
                    if not URL_RE.search(lines[j]):
                        snippet_parts.append(lines[j])
                results.append({"title": title[:240], "url": url.rstrip(".,;"), "snippet": " ".join(snippet_parts)[:900]})
        return results

    def list_results(self, case_id: str, entity_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM capture_results_60_1 WHERE case_id=? AND entity_id=? ORDER BY created_at DESC LIMIT ?", [case_id, entity_id, int(limit)])

    def get_result(self, capture_result_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM capture_results_60_1 WHERE capture_result_id=?", [capture_result_id])
        if not row:
            raise KeyError(capture_result_id)
        return row

    def _upsert_result(self, batch_id: str, case_id: str, entity_id: str, item: Dict[str, str], position: int, *, category_key: str, query: str, engine: str, now: str) -> Dict[str, Any]:
        url = str(item.get("url", "")).strip()
        canonical = _canonical(url)
        duplicate_key = _sha(canonical)[:32]
        source_guess = self._source_guess(url, item.get("title", ""), item.get("snippet", ""))
        existing = self.db.one("SELECT * FROM capture_results_60_1 WHERE case_id=? AND entity_id=? AND duplicate_key=?", [case_id, entity_id, duplicate_key])
        if existing:
            return existing
        capture_result_id = new_id("cr601")
        self.db.execute('''INSERT INTO capture_results_60_1(capture_result_id,batch_id,case_id,entity_id,title,url,canonical_url,domain,snippet,position,category_key,query,engine,source_guess,duplicate_key,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [capture_result_id, batch_id, case_id, entity_id, _clean(item.get("title", ""))[:240] or _domain(url) or url, url, canonical, _domain(url), _clean(item.get("snippet", ""))[:900], int(position), category_key, query, engine, source_guess, duplicate_key, "captured", now])
        return self.get_result(capture_result_id)

    def _source_guess(self, url: str, title: str, snippet: str) -> str:
        hay = " ".join([url, title, snippet]).lower()
        if any(x in hay for x in ["gericht", "justiz", "urteil", "aktenzeichen"]):
            return "court_or_justice"
        if any(x in hay for x in ["handelsregister", "unternehmensregister", "bundesanzeiger", "vereinsregister", "registerportal"]):
            return "registry"
        if ".pdf" in hay or "filetype:pdf" in hay:
            return "public_pdf"
        if any(x in hay for x in ["zeitung", "presse", "news"]):
            return "newspaper_press"
        if any(x in hay for x in ["foto", "bild", "image"]):
            return "image_media"
        if any(x in hay for x in ["archive", "archiv", "kirchenbuch", "taufe"]):
            return "archival_source"
        return "public_web"
