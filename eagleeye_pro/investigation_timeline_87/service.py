from __future__ import annotations
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class InvestigationTimeline87Service:
    """Build 87.0 timeline view: separates event time, capture time and review time."""
    def __init__(self, db: Database, audit: AuditService):
        self.db = db; self.audit = audit; self.ensure_schema()
    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS timeline_events_87(
          timeline_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, event_time TEXT NOT NULL,
          time_type TEXT NOT NULL, title TEXT NOT NULL, description TEXT DEFAULT '', source_ref TEXT DEFAULT '',
          confidence TEXT DEFAULT 'candidate', review_status TEXT DEFAULT 'candidate', metadata_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_timeline87_case_time ON timeline_events_87(case_id,event_time);
        """); self.db.conn.commit()
    def add_event(self, case_id: str, event_time: str, title: str, description: str = "", time_type: str = "event_time", source_ref: str = "", confidence: str = "candidate", review_status: str = "candidate", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        if time_type not in {"event_time", "capture_time", "publication_time", "review_time", "export_time"}: raise ValueError("unsupported time_type")
        tid = new_id("tl87")
        self.db.execute("INSERT INTO timeline_events_87(timeline_id,case_id,event_time,time_type,title,description,source_ref,confidence,review_status,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", [tid, case_id, event_time, time_type, title, description, source_ref, confidence, review_status, dumps(metadata or {}), now_ts()])
        self.audit.log("add", "timeline_event_87", tid, case_id, {"time_type": time_type, "title": title})
        return self.get(tid)
    def build(self, case_id: str, include_derived: bool = True) -> Dict[str, Any]:
        events = [self._row(r) for r in self.db.all("SELECT * FROM timeline_events_87 WHERE case_id=? ORDER BY event_time, created_at", [case_id])]
        derived = []
        if include_derived:
            if self._table("real_captures_74"):
                for r in self.db.all("SELECT capture_id,title,url,created_at FROM real_captures_74 WHERE case_id=? ORDER BY created_at", [case_id]):
                    derived.append({"timeline_id": "derived_" + r["capture_id"], "case_id": case_id, "event_time": r.get("created_at", ""), "time_type": "capture_time", "title": "Capture: " + (r.get("title") or r.get("url") or ""), "description": r.get("url", ""), "source_ref": r["capture_id"], "confidence": "captured", "review_status": "candidate", "metadata": {"derived_from": "real_captures_74"}})
            if self._table("claims_v3_80"):
                for r in self.db.all("SELECT claim_id,statement,grade,created_at,review_status FROM claims_v3_80 WHERE case_id=? ORDER BY created_at", [case_id]):
                    derived.append({"timeline_id": "derived_" + r["claim_id"], "case_id": case_id, "event_time": r.get("created_at", ""), "time_type": "review_time", "title": "Claim: " + (r.get("statement") or "")[:80], "description": "grade=" + r.get("grade", ""), "source_ref": r["claim_id"], "confidence": r.get("grade", "candidate"), "review_status": r.get("review_status", "candidate"), "metadata": {"derived_from": "claims_v3_80"}})
        all_events = sorted(events + derived, key=lambda x: (x.get("event_time") or "", x.get("timeline_id") or ""))
        return {"case_id": case_id, "event_count": len(all_events), "events": all_events, "conflicts": [], "warnings": ["Timeline events are analytical aids, not independent proof."]}
    def get(self, tid: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM timeline_events_87 WHERE timeline_id=?", [tid])
        if not row: raise KeyError(tid)
        return self._row(row)
    def _row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row
    def _table(self, name: str) -> bool:
        return self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]) is not None
