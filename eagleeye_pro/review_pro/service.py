from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security_kernel.policy import classify_sensitivity

REVIEW_STAGES = {
    "raw_hit",
    "candidate",
    "relevant_candidate",
    "evidence_item",
    "counter_evidence",
    "discarded",
    "needs_second_source",
}

REQUIRED_CHECKS = [
    "name_fit",
    "place_fit",
    "time_fit",
    "source_independence",
    "source_reliability",
    "name_doppler_risk",
    "counter_evidence_checked",
    "sensitivity_checked",
    "reportability_checked",
]


class ReviewInboxProService:
    """Build 50.0 review center.

    The service enforces that hits are staged, checklist-reviewed and only then promoted
    into evidence-oriented workflow states.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS review_inbox_pro_46 (
          review_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          source_object_type TEXT NOT NULL,
          source_object_id TEXT NOT NULL,
          title TEXT NOT NULL,
          source_url TEXT DEFAULT '',
          summary TEXT DEFAULT '',
          source_category TEXT DEFAULT '',
          stage TEXT DEFAULT 'raw_hit',
          priority INTEGER DEFAULT 50,
          checklist_json TEXT NOT NULL,
          sensitivity_json TEXT NOT NULL,
          reportability TEXT DEFAULT 'not_reportable',
          reviewer TEXT DEFAULT 'local-analyst',
          decision_reason TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_review_pro_46_case ON review_inbox_pro_46(case_id, stage, priority DESC);
        ''')
        self.db.conn.commit()

    def stage_hit(self, case_id: str, source_object_type: str, source_object_id: str, *, title: str, source_url: str = "", summary: str = "", source_category: str = "", priority: int = 50) -> Dict[str, Any]:
        sensitivity = classify_sensitivity(" ".join([title, source_url, summary]))
        checklist = {k: "unchecked" for k in REQUIRED_CHECKS}
        review_id = new_id("review46")
        self.db.execute('''INSERT INTO review_inbox_pro_46(review_id,case_id,source_object_type,source_object_id,title,source_url,summary,source_category,stage,priority,checklist_json,sensitivity_json,reportability,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [review_id, case_id, source_object_type, source_object_id, title, source_url, summary, source_category, "raw_hit", int(priority), dumps(checklist), dumps(sensitivity), "not_reportable", now_ts(), now_ts()])
        self.audit.log("stage", "review_inbox_pro_46", review_id, case_id, {"source_object_type": source_object_type, "sensitivity": sensitivity})
        return self.get(review_id)

    def update_checklist(self, review_id: str, updates: Dict[str, str], reviewer: str = "local-analyst", note: str = "") -> Dict[str, Any]:
        item = self.get(review_id)
        checklist = dict(item["checklist"])
        for key, value in updates.items():
            if key not in REQUIRED_CHECKS:
                raise ValueError(f"Unknown review check: {key}")
            if value not in {"unchecked", "pass", "fail", "unknown", "not_applicable"}:
                raise ValueError(f"Invalid check value for {key}: {value}")
            checklist[key] = value
        self.db.execute("UPDATE review_inbox_pro_46 SET checklist_json=?, reviewer=?, decision_reason=?, updated_at=? WHERE review_id=?", [dumps(checklist), reviewer, note or item.get("decision_reason", ""), now_ts(), review_id])
        self.audit.log("update", "review_checklist_46", review_id, item["case_id"], {"updates": updates, "reviewer": reviewer})
        return self.get(review_id)

    def set_stage(self, review_id: str, stage: str, reason: str, reportability: str | None = None, reviewer: str = "local-analyst") -> Dict[str, Any]:
        if stage not in REVIEW_STAGES:
            raise ValueError(f"Invalid review stage: {stage}")
        item = self.get(review_id)
        checklist = item["checklist"]
        if stage in {"evidence_item", "counter_evidence"}:
            blockers = [k for k, v in checklist.items() if v not in {"pass", "not_applicable"} and k in {"name_fit", "source_reliability", "sensitivity_checked", "reportability_checked"}]
            if blockers:
                raise ValueError("Review checklist incomplete for evidence promotion: " + ", ".join(blockers))
        if reportability is None:
            reportability = item.get("reportability") or "not_reportable"
        self.db.execute("UPDATE review_inbox_pro_46 SET stage=?, reportability=?, reviewer=?, decision_reason=?, updated_at=? WHERE review_id=?", [stage, reportability, reviewer, reason, now_ts(), review_id])
        self.audit.log("stage_change", "review_inbox_pro_46", review_id, item["case_id"], {"stage": stage, "reason": reason, "reportability": reportability})
        return self.get(review_id)

    def list_items(self, case_id: str, stage: str | None = None, limit: int = 200) -> List[Dict[str, Any]]:
        if stage:
            rows = self.db.all("SELECT * FROM review_inbox_pro_46 WHERE case_id=? AND stage=? ORDER BY priority DESC, updated_at DESC LIMIT ?", [case_id, stage, limit])
        else:
            rows = self.db.all("SELECT * FROM review_inbox_pro_46 WHERE case_id=? ORDER BY priority DESC, updated_at DESC LIMIT ?", [case_id, limit])
        return [self._decode(r) for r in rows]

    def get(self, review_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM review_inbox_pro_46 WHERE review_id=?", [review_id])
        if not row:
            raise KeyError(review_id)
        return self._decode(row)

    def _decode(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row = dict(row)
        row["checklist"] = loads(row.pop("checklist_json", "{}"), {})
        row["sensitivity"] = loads(row.pop("sensitivity_json", "{}"), {})
        return row
