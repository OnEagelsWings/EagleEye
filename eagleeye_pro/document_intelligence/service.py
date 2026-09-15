from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

ENTITY_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "url": re.compile(r"https?://[^\s)\]}>]+"),
    "date": re.compile(r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2})\b"),
    "aktenzeichen": re.compile(r"\b(?:Az\.?|Aktenzeichen)\s*[:]?\s*[-A-Za-z0-9/ .]+", re.IGNORECASE),
    "phone": re.compile(r"\b(?:\+49|0)[0-9][0-9 /().-]{6,}\b"),
}

class DocumentIntelligenceService:
    """Build 57.1 – OCR/Document Intelligence foundation.

    Provides safe, optional document extraction without pretending OCR output is
    fact. Native OCR is represented as a review-required mode and no external
    dependency is required for the release build.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS document_intelligence_extracts_57_1 (
          extract_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT DEFAULT '',
          source_path TEXT DEFAULT '',
          source_url TEXT DEFAULT '',
          title TEXT NOT NULL,
          document_type TEXT NOT NULL,
          extraction_mode TEXT NOT NULL,
          text_sha256 TEXT NOT NULL,
          text_preview TEXT NOT NULL,
          entities_json TEXT NOT NULL,
          ocr_required INTEGER DEFAULT 0,
          manual_review_required INTEGER DEFAULT 1,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def extract_from_text(self, case_id: str, entity_id: str, *, title: str, text: str, source_url: str = "", document_type: str = "text", extraction_mode: str = "native_text") -> Dict[str, Any]:
        if not text.strip():
            raise ValueError("document text is required")
        entities = self.extract_entities(text)
        eid = new_id("doc571")
        sha = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        preview = text.strip()[:3000]
        self.db.execute("INSERT INTO document_intelligence_extracts_57_1(extract_id,case_id,entity_id,source_path,source_url,title,document_type,extraction_mode,text_sha256,text_preview,entities_json,ocr_required,manual_review_required,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [eid, case_id, entity_id, "", source_url, title.strip() or "Dokument", document_type, extraction_mode, sha, preview, dumps(entities), 1 if extraction_mode.startswith("ocr") else 0, 1, now_ts()])
        self.audit.log("extract", "document_intelligence_57_1", eid, case_id, {"entity_id": entity_id, "document_type": document_type, "entities": {k: len(v) for k, v in entities.items()}})
        return self.get_extract(eid)

    def extract_from_file(self, case_id: str, entity_id: str, path: str | Path, *, source_url: str = "", title: str = "") -> Dict[str, Any]:
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(str(p))
        raw = p.read_bytes()
        doc_type = p.suffix.lower().lstrip(".") or "binary"
        text = ""
        mode = "native_text"
        if doc_type in {"txt", "md", "csv", "html", "htm", "json", "xml"}:
            text = raw.decode("utf-8", errors="ignore")
        elif doc_type == "pdf":
            # Lightweight release-safe extraction: pulls visible ASCII/UTF-8 strings.
            # Scanned PDFs remain OCR candidates and must be reviewed manually.
            text = self._strings_from_binary(raw)
            mode = "pdf_text_candidate" if len(text.strip()) > 80 else "ocr_required_pdf"
        else:
            text = self._strings_from_binary(raw)
            mode = "binary_text_candidate" if len(text.strip()) > 80 else "ocr_required_binary"
        result = self.extract_from_text(case_id, entity_id, title=title or p.name, text=text or "[OCR erforderlich: keine verwertbare Textschicht erkannt]", source_url=source_url, document_type=doc_type, extraction_mode=mode)
        self.db.execute("UPDATE document_intelligence_extracts_57_1 SET source_path=? WHERE extract_id=?", [str(p), result["extract_id"]])
        return self.get_extract(result["extract_id"])

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for key, pattern in ENTITY_PATTERNS.items():
            values = sorted({m.group(0).strip().rstrip('.,;') for m in pattern.finditer(text) if m.group(0).strip()})[:100]
            out[key] = values
        # simple capitalized name/organization candidates for manual review only
        candidates = re.findall(r"\b[A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){1,3}\b", text)
        out["name_or_org_candidates"] = sorted(set(candidates))[:100]
        return out

    def list_extracts(self, case_id: str, entity_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM document_intelligence_extracts_57_1 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for r in rows:
            r["entities"] = loads(r.pop("entities_json", "{}"), {})
            r["ocr_required"] = bool(r.get("ocr_required")); r["manual_review_required"] = bool(r.get("manual_review_required"))
        return rows

    def get_extract(self, extract_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM document_intelligence_extracts_57_1 WHERE extract_id=?", [extract_id])
        if not row:
            raise KeyError(extract_id)
        row["entities"] = loads(row.pop("entities_json", "{}"), {})
        row["ocr_required"] = bool(row.get("ocr_required")); row["manual_review_required"] = bool(row.get("manual_review_required"))
        return row

    def _strings_from_binary(self, raw: bytes) -> str:
        s = raw.decode("utf-8", errors="ignore")
        if len(s.strip()) < 80:
            s = raw.decode("latin-1", errors="ignore")
        chunks = re.findall(r"[\x20-\x7EÄÖÜäöüß€]{4,}", s)
        return "\n".join(chunks[:3000])
