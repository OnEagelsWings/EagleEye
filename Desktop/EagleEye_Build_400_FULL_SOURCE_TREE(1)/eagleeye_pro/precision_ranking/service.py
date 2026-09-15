from __future__ import annotations

from typing import Any, Dict, List
import re

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


def _tokens(value: Any) -> List[str]:
    if isinstance(value, str):
        vals = [value]
    elif isinstance(value, list):
        vals = [str(v) for v in value]
    else:
        vals = [str(value)] if value else []
    out: List[str] = []
    for v in vals:
        out.extend(t.lower() for t in re.findall(r"[\wÄÖÜäöüß.-]{3,}", v or ""))
    return sorted(set(out))


class PrecisionRankingService:
    """Build 50 relevance ranking for public candidates."""

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS precision_rankings_50 (
          ranking_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          object_type TEXT NOT NULL,
          object_id TEXT NOT NULL,
          score INTEGER DEFAULT 0,
          factors_json TEXT NOT NULL,
          recommendation TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_rank50_case ON precision_rankings_50(case_id, score DESC);
        ''')
        self.db.conn.commit()

    def rank_candidate(self, case_id: str, object_type: str, object_id: str, *, text: str, target: Dict[str, Any] | None = None, source_category: str = "", document_date: str = "", url: str = "") -> Dict[str, Any]:
        target = target or self._first_target(case_id)
        text_l = (text or "").lower()
        name_tokens = _tokens(target.get("name", "")) if target else []
        aliases = _tokens(target.get("aliases_json", [])) if target else []
        places = _tokens(target.get("locations_json", [])) if target else []
        orgs = _tokens(target.get("companies_json", [])) if target else []
        factors = {
            "name_fit": self._ratio(name_tokens, text_l),
            "alias_fit": self._ratio(aliases, text_l),
            "place_fit": self._ratio(places, text_l),
            "organization_fit": self._ratio(orgs, text_l),
            "source_quality": self._source_quality(source_category, url),
            "date_presence": 1.0 if document_date or re.search(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b|\b(?:19|20)\d{2}\b", text_l) else 0.0,
        }
        score = int(round(100 * (0.30*factors["name_fit"] + 0.10*factors["alias_fit"] + 0.16*factors["place_fit"] + 0.14*factors["organization_fit"] + 0.22*factors["source_quality"] + 0.08*factors["date_presence"])))
        if factors["name_fit"] < 0.5:
            recommendation = "needs_identity_anchor_review"
        elif score >= 75:
            recommendation = "high_priority_review"
        elif score >= 50:
            recommendation = "standard_review"
        else:
            recommendation = "low_priority_or_doppler_review"
        ranking_id = new_id("rank50")
        self.db.execute('''INSERT INTO precision_rankings_50(ranking_id,case_id,object_type,object_id,score,factors_json,recommendation,created_at)
        VALUES(?,?,?,?,?,?,?,?)''', [ranking_id, case_id, object_type, object_id, score, dumps(factors), recommendation, now_ts()])
        self.audit.log("rank", "precision_candidate_50", object_id, case_id, {"score": score, "recommendation": recommendation})
        return self.get(ranking_id)

    def rank_review_inbox(self, case_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM review_inbox_pro_46 WHERE case_id=? ORDER BY updated_at DESC LIMIT ?", [case_id, limit]) if self._table_exists("review_inbox_pro_46") else []
        out = []
        for r in rows:
            out.append(self.rank_candidate(case_id, "review_inbox_pro_46", r["review_id"], text=" ".join([r.get("title", ""), r.get("summary", ""), r.get("source_url", "")]), source_category=r.get("source_category", ""), url=r.get("source_url", "")))
        return out

    def get(self, ranking_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM precision_rankings_50 WHERE ranking_id=?", [ranking_id])
        if not row:
            raise KeyError(ranking_id)
        row["factors"] = loads(row.pop("factors_json", "{}"), {})
        return row

    def list_rankings(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM precision_rankings_50 WHERE case_id=? ORDER BY score DESC, created_at DESC", [case_id])
        for row in rows:
            row["factors"] = loads(row.pop("factors_json", "{}"), {})
        return rows

    def _ratio(self, tokens: List[str], text_l: str) -> float:
        if not tokens:
            return 0.0
        return min(1.0, sum(1 for t in tokens if t in text_l) / max(1, min(len(tokens), 3)))

    def _source_quality(self, category: str, url: str) -> float:
        text = (category + " " + url).lower()
        if any(x in text for x in ["court", "register", "gazette", "government", "bund", "rdap", "certificate"]):
            return 0.9
        if any(x in text for x in ["newspaper", "press", "public_pdf", "archive"]):
            return 0.72
        if any(x in text for x in ["social", "profile"]):
            return 0.48
        return 0.55

    def _first_target(self, case_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM targets WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if not row:
            return {}
        for k in ["aliases_json", "emails_json", "usernames_json", "locations_json", "companies_json", "domains_json"]:
            row[k] = loads(row.get(k), [])
        return row

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))
