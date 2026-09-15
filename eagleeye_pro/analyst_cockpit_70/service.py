from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class AnalystCockpit70Service:
    """Build 70.0 unified analyst cockpit backbone."""
    def __init__(self, db: Database, audit: AuditService, *, architecture=None, adapters=None, graph=None, capture_vault=None, quality_control=None):
        self.db = db
        self.audit = audit
        self.architecture = architecture
        self.adapters = adapters
        self.graph = graph
        self.capture_vault = capture_vault
        self.quality_control = quality_control
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS analyst_cockpit_snapshots_70 (
          snapshot_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, label TEXT NOT NULL, readiness_score INTEGER NOT NULL,
          panels_json TEXT NOT NULL, next_actions_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cockpit70_case ON analyst_cockpit_snapshots_70(case_id, created_at);
        """)
        self.db.conn.commit()

    def build_dashboard(self, case_id: str, entity_id: str = "", persist: bool = True) -> Dict[str, Any]:
        architecture = self.architecture.latest_blueprint(case_id) if self.architecture else None
        maturity = (architecture or {}).get("maturity") or (self.architecture.assess_maturity({}) if self.architecture else {"score": 0, "next_actions": []})
        adapter_count = len(self.adapters.list_specs()) if self.adapters else 0
        graph_metrics = self.graph.metrics(case_id) if self.graph else {"node_count": 0, "edge_count": 0, "graph_readiness": 0}
        captures = self.capture_vault.list_case_artifacts(case_id) if self.capture_vault else []
        quality = self.quality_control.latest(case_id, entity_id) if self.quality_control else None
        panels = {
            "architecture": {"maturity_score": maturity.get("score", 0), "label": maturity.get("label", "unknown"), "blockers": maturity.get("blockers", [])},
            "source_adapters": {"registered_specs": adapter_count, "status": "contract_ready" if adapter_count >= 5 else "needs_expansion"},
            "capture_vault": {"artifact_count": len(captures), "status": "active" if captures else "empty"},
            "graph_workspace": graph_metrics,
            "quality_control": quality or {"label": "not_evaluated", "score": 0},
        }
        readiness = self._score(panels)
        label = "spearhead_candidate" if readiness >= 85 else "professional_beta" if readiness >= 70 else "architecture_alpha" if readiness >= 50 else "foundation"
        next_actions = self._next_actions(panels, maturity)
        sid = new_id("cock70")
        result = {"snapshot_id": sid, "case_id": case_id, "entity_id": entity_id, "label": label, "readiness_score": readiness, "panels": panels, "next_actions": next_actions, "created_at": now_ts()}
        if persist:
            self.db.execute("""INSERT INTO analyst_cockpit_snapshots_70(snapshot_id,case_id,label,readiness_score,panels_json,next_actions_json,created_at)
            VALUES(?,?,?,?,?,?,?)""", [sid, case_id, label, readiness, dumps(panels), dumps(next_actions), result["created_at"]])
            self.audit.log("build", "analyst_cockpit_70", sid, case_id, {"label": label, "readiness_score": readiness})
        return result

    def latest(self, case_id: str) -> Dict[str, Any] | None:
        row = self.db.one("SELECT * FROM analyst_cockpit_snapshots_70 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if not row:
            return None
        row["panels"] = loads(row.pop("panels_json", "{}"), {})
        row["next_actions"] = loads(row.pop("next_actions_json", "[]"), [])
        return row

    def _score(self, panels: Dict[str, Any]) -> int:
        arch = int(panels["architecture"].get("maturity_score", 0))
        graph = int(panels["graph_workspace"].get("graph_readiness", 0))
        quality = int((panels["quality_control"] or {}).get("score", 0) or 0)
        capture = min(100, int(panels["capture_vault"].get("artifact_count", 0)) * 25)
        adapters = min(100, int(panels["source_adapters"].get("registered_specs", 0)) * 15)
        return max(0, min(100, int(arch * .25 + adapters * .15 + capture * .2 + graph * .25 + quality * .15)))

    def _next_actions(self, panels: Dict[str, Any], maturity: Dict[str, Any]) -> List[str]:
        actions = list(maturity.get("next_actions") or [])
        if panels["capture_vault"].get("artifact_count", 0) == 0:
            actions.append("record_first_public_capture_artifact")
        if panels["graph_workspace"].get("node_count", 0) < 3:
            actions.append("create_person_identifier_source_graph_seed")
        if (panels["quality_control"] or {}).get("label") in {None, "not_evaluated"}:
            actions.append("run_quality_control_65_before_export")
        return list(dict.fromkeys(actions))[:8]
