from __future__ import annotations

from typing import Any, Dict

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, new_id, now_ts, dumps, loads


class OperationalResearchStableService:
    """Build 61.0: integrated operational research stable workflow."""

    def __init__(self, db: Database, audit: AuditService, *, capture_pro, fund_intel, entity_resolution, dashboard, calibration, osint_core=None):
        self.db = db
        self.audit = audit
        self.capture_pro = capture_pro
        self.fund_intel = fund_intel
        self.entity_resolution = entity_resolution
        self.dashboard_service = dashboard
        self.calibration = calibration
        self.osint_core = osint_core
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS operational_research_cycles_61_0 (
          cycle_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          session_id TEXT DEFAULT '',
          batch_id TEXT DEFAULT '',
          imported_count INTEGER DEFAULT 0,
          intelligence_count INTEGER DEFAULT 0,
          assessed_count INTEGER DEFAULT 0,
          calibration_run_id TEXT DEFAULT '',
          status TEXT DEFAULT 'completed',
          summary_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def run_cycle(self, case_id: str, entity_id: str, *, raw_serp_text: str = "", url: str = "", title: str = "", snippet: str = "", category_key: str = "", query: str = "", engine: str = "manual", session_id: str = "") -> Dict[str, Any]:
        if raw_serp_text.strip():
            cap = self.capture_pro.import_serp_block(case_id, entity_id, raw_serp_text, category_key=category_key, query=query, engine=engine)
            captures = cap.get("results", [])
            batch_id = cap.get("batch_id", "")
        elif url.strip():
            cap = self.capture_pro.import_url(case_id, entity_id, url, title=title, snippet=snippet, category_key=category_key, query=query, engine=engine)
            captures = cap.get("results", [])
            batch_id = cap.get("batch_id", "")
        else:
            captures = []
            batch_id = ""
        intelligence = []
        assessments = []
        for c in captures:
            intel = self.fund_intel.import_capture_to_person_file(c["capture_result_id"])
            intelligence.append(intel)
            try:
                assessments.append(self.entity_resolution.assess_capture_result(c))
                if intel.get("person_finding_id"):
                    # also assess the created person finding if available
                    finding = self.fund_intel.person_detail.get_finding(intel["person_finding_id"])
                    assessments.append(self.entity_resolution.assess_person_finding(finding))
            except Exception:
                pass
        dash = self.dashboard_service.dashboard(case_id, entity_id)
        cal = self.calibration.evaluate_entity(case_id, entity_id, session_id=session_id)
        cycle_id = new_id("ors61")
        summary = {"dashboard_metrics": dash.get("metrics", {}), "calibration": cal.get("metrics", {}), "next_actions": dash.get("next_actions", [])[:8]}
        self.db.execute('''INSERT INTO operational_research_cycles_61_0(cycle_id,case_id,entity_id,session_id,batch_id,imported_count,intelligence_count,assessed_count,calibration_run_id,summary_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [cycle_id, case_id, entity_id, session_id, batch_id, len(captures), len(intelligence), len(assessments), cal.get("run_id", ""), dumps(summary), now_ts()])
        self.audit.log("run", "operational_research_cycle_61_0", cycle_id, case_id, {"entity_id": entity_id, "imported": len(captures)})
        return {"cycle_id": cycle_id, "case_id": case_id, "entity_id": entity_id, "batch_id": batch_id, "captures": captures, "intelligence": intelligence, "assessments": assessments, "dashboard": dash, "calibration": cal}

    def latest(self, case_id: str, entity_id: str = "", limit: int = 10):
        rows = self.db.all("SELECT * FROM operational_research_cycles_61_0 WHERE case_id=? AND (?='' OR entity_id=?) ORDER BY created_at DESC LIMIT ?", [case_id, entity_id, entity_id, int(limit)])
        for r in rows:
            r["summary"] = loads(r.pop("summary_json", "{}"), {})
        return rows
