from __future__ import annotations

import re
from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class SmartQueryOptimizerService:
    """Build 55.8: query precision/recall optimizer."""

    def __init__(self, db: Database, audit: AuditService, search_quality=None):
        self.db = db
        self.audit = audit
        self.search_quality = search_quality
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS query_optimizer_reviews_55_8 (
          review_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          quality_query_id TEXT DEFAULT '',
          original_query TEXT NOT NULL,
          quality_label TEXT NOT NULL,
          precision_score INTEGER DEFAULT 0,
          recall_score INTEGER DEFAULT 0,
          issues_json TEXT NOT NULL,
          suggestions_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_query_optimizer_558_entity ON query_optimizer_reviews_55_8(case_id, entity_id, created_at DESC);
        ''')
        self.db.conn.commit()

    def review_quality_query(self, quality_query_id: str) -> Dict[str, Any]:
        q = self.db.one("SELECT * FROM search_quality_queries_55_5 WHERE quality_query_id=?", [quality_query_id])
        if not q:
            raise KeyError(quality_query_id)
        try:
            fp = self.search_quality.get_fingerprint(q["case_id"], q["entity_id"])["fingerprint"] if self.search_quality else {}
        except Exception:
            fp = {}
        return self.review_raw_query(q["case_id"], q["entity_id"], q["query"], quality_query_id=quality_query_id, fingerprint=fp)

    def review_raw_query(self, case_id: str, entity_id: str, query: str, *, quality_query_id: str = "", fingerprint: Dict[str, Any] | None = None) -> Dict[str, Any]:
        fp = fingerprint or {}
        q = " ".join(str(query).split())
        issues: List[str] = []
        suggestions: List[Dict[str, Any]] = []
        quote_count = q.count('"') // 2
        has_site = "site:" in q.lower()
        has_filetype = "filetype:" in q.lower()
        has_or = " OR " in q or "(" in q
        strong_anchors = fp.get("strong_anchors", []) or []
        name = fp.get("display_name", "")
        precision = 45 + min(quote_count * 12, 30) + (12 if has_site else 0) + (8 if has_filetype else 0) - (8 if has_or else 0)
        recall = 45 + (15 if has_or else 0) - min(quote_count * 5, 20) - (8 if has_site else 0)
        if name and name not in q:
            issues.append("missing_exact_name_anchor")
            suggestions.append({"type": "precision", "query": f'"{name}" {q}', "reason": "exakten Namensanker ergänzen"})
        if len(q.split()) <= 2 and not strong_anchors:
            issues.append("too_broad_no_context_anchor")
        if len(q) > 160:
            issues.append("possibly_too_narrow")
            suggestions.append({"type": "recall", "query": self._shorten(q), "reason": "zu enge Query stufenweise öffnen"})
        if strong_anchors and not any(str(a).lower() in q.lower() for a in strong_anchors[:8]):
            issues.append("missing_known_context_anchor")
            for a in strong_anchors[:3]:
                suggestions.append({"type": "precision", "query": f'"{name}" "{a}"' if name else f'"{a}" {q}', "reason": "bekannten Kontextanker nutzen"})
        if not has_filetype and any(w in q.lower() for w in ["gericht", "urteil", "register", "satzung", "jahresabschluss", "bericht"]):
            suggestions.append({"type": "source_dork", "query": q + " filetype:pdf", "reason": "öffentliche Dokument-/PDF-Spur prüfen"})
        if fp.get("places"):
            negatives = " ".join(f'-"{p}"' for p in fp.get("places", [])[:2])
            suggestions.append({"type": "countercheck", "query": f'"{name}" {negatives}'.strip(), "reason": "Namensdoppler ohne bekannte Orte prüfen"})
        precision = max(0, min(100, precision)); recall = max(0, min(100, recall))
        if precision >= 75 and recall >= 35:
            label = "balanced_high_precision"
        elif precision < 55 and recall >= 50:
            label = "too_broad"
        elif precision >= 75 and recall < 30:
            label = "too_narrow"
        else:
            label = "review_required"
        rid = new_id("qopt558")
        self.db.execute('''INSERT INTO query_optimizer_reviews_55_8(review_id,case_id,entity_id,quality_query_id,original_query,quality_label,precision_score,recall_score,issues_json,suggestions_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [rid, case_id, entity_id, quality_query_id, q, label, precision, recall, dumps(issues), dumps(suggestions[:8]), now_ts()])
        self.audit.log("review", "query_optimizer_55_8", rid, case_id, {"label": label, "issues": issues})
        return self.get_review(rid)

    def optimize_entity_queries(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        rows = self.db.all("SELECT quality_query_id FROM search_quality_queries_55_5 WHERE case_id=? AND entity_id=? ORDER BY precision_bias DESC", [case_id, entity_id])
        reviews = [self.review_quality_query(r["quality_query_id"]) for r in rows]
        return {"case_id": case_id, "entity_id": entity_id, "review_count": len(reviews), "reviews": reviews}

    def get_review(self, review_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM query_optimizer_reviews_55_8 WHERE review_id=?", [review_id])
        if not row:
            raise KeyError(review_id)
        row["issues"] = loads(row.pop("issues_json", "[]"), [])
        row["suggestions"] = loads(row.pop("suggestions_json", "[]"), [])
        return row

    def latest_reviews(self, case_id: str, entity_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM query_optimizer_reviews_55_8 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for r in rows:
            r["issues"] = loads(r.pop("issues_json", "[]"), [])
            r["suggestions"] = loads(r.pop("suggestions_json", "[]"), [])
        return rows

    def _shorten(self, q: str) -> str:
        parts = re.findall(r'"[^"]+"|\S+', q)
        return " ".join(parts[:8])
