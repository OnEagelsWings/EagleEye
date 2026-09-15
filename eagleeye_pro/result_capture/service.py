from __future__ import annotations

import hashlib
import re
from html import unescape
from typing import Any, Dict, List
from urllib.parse import urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


def _domain(url: str) -> str:
    try:
        return urlparse(url.strip()).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p or "").encode("utf-8", errors="ignore")); h.update(b"\0")
    return h.hexdigest()


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", unescape(s or "")).strip()


def _extract_title(html_text: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html_text or "", re.I | re.S)
    return _clean(m.group(1)) if m else ""


def _extract_description(html_text: str) -> str:
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html_text or "", re.I | re.S)
    if not m:
        m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html_text or "", re.I | re.S)
    return _clean(m.group(1)) if m else ""


FINDING_TYPE_BY_HOST = [
    ("gerichte", "court_or_justice"), ("justiz", "court_or_justice"), ("bundesanzeiger", "registry"),
    ("unternehmensregister", "registry"), ("handelsregister", "registry"), ("registerportal", "registry"),
    ("deutsche-digitale-bibliothek", "archival_source"), ("zeitungsportal", "newspaper_press"),
]


class ResultCaptureImportService:
    """Build 55.6: controlled URL/fund import for the research engine.

    This is not an automated scraping/bypass layer. It turns a URL or pasted
    public result snippet into a normalized, review-first finding linked to the
    current entity, chain and Search Quality Engine.
    """

    def __init__(self, db: Database, audit: AuditService, person_detail=None, search_quality=None, search_chain=None):
        self.db = db
        self.audit = audit
        self.person_detail = person_detail
        self.search_quality = search_quality
        self.search_chain = search_chain
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS result_capture_imports_55_6 (
          import_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          url TEXT NOT NULL,
          domain TEXT DEFAULT '',
          title TEXT NOT NULL,
          snippet TEXT DEFAULT '',
          category_key TEXT DEFAULT '',
          quality_query_id TEXT DEFAULT '',
          query TEXT DEFAULT '',
          engine TEXT DEFAULT '',
          source_type TEXT DEFAULT 'public_web',
          document_date TEXT DEFAULT '',
          normalized_hash TEXT NOT NULL,
          person_finding_note_id TEXT DEFAULT '',
          quality_result_id TEXT DEFAULT '',
          chain_node_id TEXT DEFAULT '',
          review_status TEXT DEFAULT 'candidate',
          metadata_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_result_capture_556_entity ON result_capture_imports_55_6(case_id, entity_id, created_at DESC);
        ''')
        self.db.conn.commit()

    def suggest_source_type(self, url: str, title: str = "", snippet: str = "") -> str:
        host = _domain(url)
        blob = f"{host} {url} {title} {snippet}".lower()
        if url.lower().endswith(".pdf") or "filetype:pdf" in blob:
            return "public_pdf"
        for needle, stype in FINDING_TYPE_BY_HOST:
            if needle in blob:
                return stype
        if any(x in blob for x in ["zeitung", "presse", "article", "news"]):
            return "newspaper_press"
        if any(x in blob for x in ["impressum", "verein", "gmbh", "team", "vorstand"]):
            return "organization_site"
        if any(x in blob for x in ["jpg", "jpeg", "png", "webp", "foto", "bild"]):
            return "image_media"
        return "public_web"

    def import_public_result(
        self,
        case_id: str,
        entity_id: str,
        *,
        url: str,
        title: str = "",
        snippet: str = "",
        html_text: str = "",
        category_key: str = "",
        quality_query_id: str = "",
        query: str = "",
        engine: str = "",
        document_date: str = "",
        source_type: str = "",
        auto_person_finding: bool = True,
        auto_quality_score: bool = True,
        auto_chain_node: bool = True,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        if not case_id or not entity_id:
            raise ValueError("case_id and entity_id are required")
        if not url.strip() or not urlparse(url.strip()).scheme.startswith("http"):
            raise ValueError("A public http(s) URL is required")
        title = _clean(title) or _extract_title(html_text) or _domain(url) or "Öffentlicher Treffer"
        snippet = _clean(snippet) or _extract_description(html_text)
        if quality_query_id and self.search_quality and not query:
            row = self.db.one("SELECT query, category_key FROM search_quality_queries_55_5 WHERE quality_query_id=?", [quality_query_id])
            if row:
                query = row.get("query", "")
                category_key = category_key or row.get("category_key", "")
        source_type = source_type or self.suggest_source_type(url, title, snippet)
        n_hash = _sha(url.lower().split("#")[0], title, snippet, query, source_type)[:32]
        existing = self.db.one("SELECT import_id FROM result_capture_imports_55_6 WHERE case_id=? AND entity_id=? AND normalized_hash=?", [case_id, entity_id, n_hash])
        now = now_ts()
        if existing:
            iid = existing["import_id"]
            self.db.execute("UPDATE result_capture_imports_55_6 SET title=?, snippet=?, updated_at=? WHERE import_id=?", [title, snippet, now, iid])
        else:
            iid = new_id("cap556")
            self.db.execute('''INSERT INTO result_capture_imports_55_6(import_id,case_id,entity_id,url,domain,title,snippet,category_key,quality_query_id,query,engine,source_type,document_date,normalized_hash,metadata_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [iid, case_id, entity_id, url.strip(), _domain(url), title, snippet, category_key, quality_query_id, query, engine, source_type, document_date, n_hash, dumps(metadata or {}), now, now])
        row = self.get_import(iid)

        chain_node_id = row.get("chain_node_id", "")
        if auto_chain_node and self.search_chain and not chain_node_id:
            parent = self._parent_for_query(quality_query_id) or ""
            node = self.search_chain.add_node(
                case_id, "source_hit", title, snippet or url, entity_id=entity_id, parent_node_id=parent,
                relation_type="found_by_quality_query" if parent else "captured_public_result",
                source_url=url, relevance_score=55, confidence_label="candidate_public_result",
                metadata={"build": "55.6", "query": query, "engine": engine, "source_category": source_type, "document_date": document_date, "category_key": category_key, "import_id": iid},
                status="found",
            )
            chain_node_id = node["node_id"]
            self.db.execute("UPDATE result_capture_imports_55_6 SET chain_node_id=?, updated_at=? WHERE import_id=?", [chain_node_id, now_ts(), iid])
            row["chain_node_id"] = chain_node_id

        quality_result_id = row.get("quality_result_id", "")
        if auto_quality_score and self.search_quality and not quality_result_id:
            res = self.search_quality.add_or_score_result(case_id, entity_id, title=title, url=url, snippet=snippet, quality_query_id=quality_query_id, query=query, engine=engine, source_type=source_type, document_date=document_date, source_hit_node_id=chain_node_id)
            quality_result_id = res["result_id"]
            self.db.execute("UPDATE result_capture_imports_55_6 SET quality_result_id=?, updated_at=? WHERE import_id=?", [quality_result_id, now_ts(), iid])
            row["quality_result_id"] = quality_result_id
            row["quality_result"] = res

        person_finding_note_id = row.get("person_finding_note_id", "")
        if auto_person_finding and self.person_detail and not person_finding_note_id:
            finding = self.person_detail.add_finding_note(
                case_id, entity_id, title=title, summary=snippet or f"Öffentlicher Treffer: {url}", finding_type=self._finding_type_from_source(source_type),
                source_url=url, document_date=document_date, category=category_key or source_type, status="candidate", analyst_note="Build 55.6 Fundimport; manuelle Prüfung vor Verwertung.", chain_node_id=chain_node_id, evidence_level="candidate", redaction_required=self._redaction_required(source_type, category_key), metadata={"import_id": iid, "quality_result_id": quality_result_id, "query": query, "engine": engine},
            )
            person_finding_note_id = finding["finding_note_id"]
            self.db.execute("UPDATE result_capture_imports_55_6 SET person_finding_note_id=?, updated_at=? WHERE import_id=?", [person_finding_note_id, now_ts(), iid])
            row["person_finding_note_id"] = person_finding_note_id
            row["person_finding"] = finding

        self.audit.log("import", "result_capture_import_55_6", iid, case_id, {"entity_id": entity_id, "source_type": source_type, "quality_result_id": quality_result_id})
        return self.get_import(iid)

    def list_imports(self, case_id: str, entity_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM result_capture_imports_55_6 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for r in rows:
            r["metadata"] = loads(r.pop("metadata_json", "{}"), {})
        return rows

    def get_import(self, import_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM result_capture_imports_55_6 WHERE import_id=?", [import_id])
        if not row:
            raise KeyError(import_id)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row

    def _parent_for_query(self, quality_query_id: str) -> str:
        if not quality_query_id:
            return ""
        row = self.db.one("SELECT chain_parameter_node_id FROM search_quality_queries_55_5 WHERE quality_query_id=?", [quality_query_id])
        return row.get("chain_parameter_node_id", "") if row else ""

    def _finding_type_from_source(self, source_type: str) -> str:
        return {
            "court_or_justice": "court", "registry": "registry", "public_pdf": "pdf", "newspaper_press": "press", "archival_source": "archive", "image_media": "image", "organization_site": "web"
        }.get(source_type, "web")

    def _redaction_required(self, source_type: str, category_key: str) -> bool:
        return source_type in {"court_or_justice", "registry", "image_media"} or category_key in {"person_public_personal_data", "person_legal_proceedings", "person_images", "person_public_financial_data"}
