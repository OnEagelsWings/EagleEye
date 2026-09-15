from __future__ import annotations

import hashlib
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security_kernel.policy import classify_sensitivity


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip and data and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


class PublicDocumentExtractor:
    """Build 50.0 public document extractor.

    It performs conservative local extraction only. It does not fetch URLs or bypass access
    restrictions. PDF support is best-effort without OCR; uncertain extraction is flagged.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS public_document_extracts_46 (
          extract_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          source_url TEXT DEFAULT '',
          document_title TEXT NOT NULL,
          document_type TEXT NOT NULL,
          document_date TEXT DEFAULT '',
          retrieved_at TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          text_hash TEXT NOT NULL,
          extraction_method TEXT NOT NULL,
          extraction_confidence TEXT DEFAULT 'candidate',
          entities_json TEXT NOT NULL,
          dates_json TEXT NOT NULL,
          places_json TEXT NOT NULL,
          citations_json TEXT NOT NULL,
          sensitivity_json TEXT NOT NULL,
          review_status TEXT DEFAULT 'needs_review',
          notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_doc_extracts_46_case ON public_document_extracts_46(case_id, retrieved_at DESC);
        ''')
        self.db.conn.commit()

    def extract_from_text(self, case_id: str, text: str, *, title: str = "public document", source_url: str = "", document_type: str = "text", document_date: str = "", notes: str = "") -> Dict[str, Any]:
        text = self._normalize_text(text)
        content_hash = _sha256((source_url or "") + "\n" + text)
        text_hash = _sha256(text)
        entities = self._extract_entities(text)
        dates = self._extract_dates(text)
        places = self._extract_places(text, entities)
        citations = self._build_citations(text, source_url)
        sensitivity = classify_sensitivity(" ".join([title, source_url, text[:2000]]))
        confidence = "medium" if len(text) > 100 else "low"
        return self._store(case_id, source_url, title, document_type, document_date, content_hash, text_hash, "text", confidence, entities, dates, places, citations, sensitivity, notes)

    def extract_from_file(self, case_id: str, path: str | Path, *, source_url: str = "", document_title: str = "", document_date: str = "", notes: str = "") -> Dict[str, Any]:
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(str(p))
        data = p.read_bytes()
        content_hash = _sha256_bytes(data)
        suffix = p.suffix.lower().lstrip(".") or "binary"
        title = document_title or p.name
        if suffix in {"html", "htm"}:
            raw = data.decode("utf-8", errors="replace")
            parser = _HTMLTextExtractor(); parser.feed(raw)
            text = parser.text()
            method = "html_text"
            confidence = "medium" if text else "low"
        elif suffix == "pdf":
            text = self._best_effort_pdf_text(data)
            method = "pdf_best_effort_no_ocr"
            confidence = "low" if len(text) < 500 else "candidate"
        else:
            text = data.decode("utf-8", errors="replace")
            method = f"{suffix}_text_best_effort"
            confidence = "medium" if len(text) > 100 else "low"
        text = self._normalize_text(text)
        entities = self._extract_entities(text)
        dates = self._extract_dates(text)
        places = self._extract_places(text, entities)
        citations = self._build_citations(text, source_url or str(p))
        sensitivity = classify_sensitivity(" ".join([title, source_url, text[:2000]]))
        return self._store(case_id, source_url, title, suffix, document_date, content_hash, _sha256(text), method, confidence, entities, dates, places, citations, sensitivity, notes)

    def _store(self, case_id: str, source_url: str, title: str, document_type: str, document_date: str, content_hash: str, text_hash: str, method: str, confidence: str, entities: Dict[str, Any], dates: List[str], places: List[str], citations: List[Dict[str, Any]], sensitivity: Dict[str, Any], notes: str) -> Dict[str, Any]:
        extract_id = new_id("extract46")
        self.db.execute('''INSERT INTO public_document_extracts_46(extract_id,case_id,source_url,document_title,document_type,document_date,retrieved_at,content_hash,text_hash,extraction_method,extraction_confidence,entities_json,dates_json,places_json,citations_json,sensitivity_json,review_status,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [extract_id, case_id, source_url, title, document_type, document_date, now_ts(), content_hash, text_hash, method, confidence, dumps(entities), dumps(dates), dumps(places), dumps(citations), dumps(sensitivity), "needs_review", notes])
        result = self.get_extract(extract_id)
        self.audit.log("create", "public_document_extract_46", extract_id, case_id, {"document_type": document_type, "extraction_confidence": confidence, "sensitivity": sensitivity, "entity_counts": {k: len(v) for k, v in entities.items()}})
        return result

    def get_extract(self, extract_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM public_document_extracts_46 WHERE extract_id=?", [extract_id])
        if not row:
            raise KeyError(extract_id)
        return self._decode(row)

    def list_extracts(self, case_id: str) -> List[Dict[str, Any]]:
        return [self._decode(r) for r in self.db.all("SELECT * FROM public_document_extracts_46 WHERE case_id=? ORDER BY retrieved_at DESC", [case_id])]

    def _decode(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)
        row["entities"] = loads(row.pop("entities_json", "{}"), {})
        row["dates"] = loads(row.pop("dates_json", "[]"), [])
        row["places"] = loads(row.pop("places_json", "[]"), [])
        row["citations"] = loads(row.pop("citations_json", "[]"), [])
        row["sensitivity"] = loads(row.pop("sensitivity_json", "{}"), {})
        return row

    def _best_effort_pdf_text(self, data: bytes) -> str:
        # Conservative best-effort extraction for embedded literal strings. This is not OCR.
        chunks = re.findall(rb"\(([^\)\r\n]{3,200})\)", data[:5_000_000])
        decoded = []
        for c in chunks[:4000]:
            try:
                decoded.append(c.decode("utf-8", errors="ignore"))
            except Exception:
                decoded.append(c.decode("latin-1", errors="ignore"))
        text = " ".join(decoded)
        if len(text) < 80:
            text = data[:1_000_000].decode("latin-1", errors="ignore")
        return text

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", html.unescape(text or "")).strip()

    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        # Lightweight deterministic extraction; labels are candidates.
        emails = sorted(set(re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", text)))[:50]
        urls = sorted(set(re.findall(r"https?://[^\s\)\]\}\"']+", text)))[:50]
        register_numbers = sorted(set(re.findall(r"\b(?:HRB|HRA|VR|GnR|PR)\s?\d{1,8}\b", text, flags=re.I)))[:50]
        court_refs = sorted(set(re.findall(r"\b\d{1,3}\s?[A-Z]{1,4}\s?\d{1,6}/\d{2,4}\b", text)))[:50]
        names = sorted(set(re.findall(r"\b[A-ZÄÖÜ][a-zäöüß]{2,}(?:\s+(?:von|van|de|zu|der|den|und))?\s+[A-ZÄÖÜ][a-zäöüß]{2,}\b", text)))[:80]
        orgs = sorted(set(re.findall(r"\b[A-ZÄÖÜ][\wÄÖÜäöüß&.\- ]{2,80}\s(?:e\.V\.|GmbH|gGmbH|AG|KG|OHG|Stiftung|Gemeinde|Synagoge|Schule|Universität)\b", text)))[:80]
        return {"emails": emails, "urls": urls, "register_numbers": register_numbers, "court_refs": court_refs, "person_name_candidates": names, "organization_candidates": orgs}

    def _extract_dates(self, text: str) -> List[str]:
        patterns = [
            r"\b\d{1,2}\.\s?\d{1,2}\.\s?\d{4}\b",
            r"\b\d{4}-\d{2}-\d{2}\b",
            r"\b(?:Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+\d{4}\b",
            r"\b\d{4}\b",
        ]
        found: list[str] = []
        for pat in patterns:
            found.extend(re.findall(pat, text, flags=re.I))
        return sorted(set(found))[:80]

    def _extract_places(self, text: str, entities: Dict[str, Any]) -> List[str]:
        hints = re.findall(r"\b(?:in|aus|bei|nach|von)\s+([A-ZÄÖÜ][a-zäöüß\-]{2,}(?:\s+[A-ZÄÖÜ][a-zäöüß\-]{2,})?)", text)
        return sorted(set(hints))[:50]

    def _build_citations(self, text: str, source_url: str) -> List[Dict[str, Any]]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        selected = [s.strip() for s in sentences if len(s.strip()) > 30][:12]
        return [{"source_url": source_url, "excerpt": s[:280], "locator": f"sentence:{idx+1}"} for idx, s in enumerate(selected)]


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
