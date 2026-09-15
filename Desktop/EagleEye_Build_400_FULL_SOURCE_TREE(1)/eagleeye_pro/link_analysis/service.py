from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class LinkAnalysisService:
    """Build 50 timeline and link-analysis service with sourced edges only."""

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS timeline_events_50 (
          event_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          event_time TEXT NOT NULL,
          title TEXT NOT NULL,
          description TEXT DEFAULT '',
          place TEXT DEFAULT '',
          source_object_type TEXT DEFAULT '',
          source_object_id TEXT DEFAULT '',
          confidence_label TEXT DEFAULT 'candidate',
          uncertainty_note TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS link_edges_50 (
          link_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          source_label TEXT NOT NULL,
          target_label TEXT NOT NULL,
          relationship_type TEXT NOT NULL,
          source_object_type TEXT NOT NULL,
          source_object_id TEXT NOT NULL,
          confidence_label TEXT DEFAULT 'candidate',
          counter_evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_tl50_case ON timeline_events_50(case_id, event_time);
        CREATE INDEX IF NOT EXISTS idx_link50_case ON link_edges_50(case_id, relationship_type);
        ''')
        self.db.conn.commit()

    def add_timeline_event(self, case_id: str, event_time: str, title: str, *, description: str = "", place: str = "", source_object_type: str = "", source_object_id: str = "", confidence_label: str = "candidate", uncertainty_note: str = "") -> Dict[str, Any]:
        if not source_object_id:
            raise ValueError("Timeline event requires a source_object_id.")
        event_id = new_id("tl50")
        self.db.execute('''INSERT INTO timeline_events_50(event_id,case_id,event_time,title,description,place,source_object_type,source_object_id,confidence_label,uncertainty_note,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [event_id, case_id, event_time, title, description, place, source_object_type, source_object_id, confidence_label, uncertainty_note, now_ts()])
        self.audit.log("create", "timeline_event_50", event_id, case_id, {"title": title, "source_object_id": source_object_id})
        return self.get_timeline_event(event_id)

    def add_link(self, case_id: str, source_label: str, target_label: str, relationship_type: str, *, source_object_type: str, source_object_id: str, confidence_label: str = "candidate", counter_evidence: List[str] | None = None) -> Dict[str, Any]:
        if not source_object_id:
            raise ValueError("Links require source evidence or document id.")
        link_id = new_id("link50")
        self.db.execute('''INSERT INTO link_edges_50(link_id,case_id,source_label,target_label,relationship_type,source_object_type,source_object_id,confidence_label,counter_evidence_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [link_id, case_id, source_label, target_label, relationship_type, source_object_type, source_object_id, confidence_label, dumps(counter_evidence or []), now_ts()])
        self.audit.log("create", "link_edge_50", link_id, case_id, {"relationship_type": relationship_type})
        return self.get_link(link_id)

    def get_timeline_event(self, event_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM timeline_events_50 WHERE event_id=?", [event_id])
        if not row:
            raise KeyError(event_id)
        return row

    def get_link(self, link_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM link_edges_50 WHERE link_id=?", [link_id])
        if not row:
            raise KeyError(link_id)
        row["counter_evidence"] = loads(row.pop("counter_evidence_json", "[]"), [])
        return row

    def build_case_map(self, case_id: str) -> Dict[str, Any]:
        timeline = self.db.all("SELECT * FROM timeline_events_50 WHERE case_id=? ORDER BY event_time, created_at", [case_id])
        links = self.db.all("SELECT * FROM link_edges_50 WHERE case_id=? ORDER BY relationship_type, created_at", [case_id])
        for link in links:
            link["counter_evidence"] = loads(link.pop("counter_evidence_json", "[]"), [])
        return {"case_id": case_id, "timeline_events": timeline, "links": links, "metrics": {"timeline_events": len(timeline), "links": len(links)}}
