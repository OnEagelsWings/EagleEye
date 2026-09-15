from __future__ import annotations
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class CaseDashboardV286Service:
    """Build 86.0 case dashboard v2: status, warnings, open reviews and next steps."""
    def __init__(self, db: Database, audit: AuditService):
        self.db = db; self.audit = audit; self.ensure_schema()
    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS case_dashboards_86(
          dashboard_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, status TEXT NOT NULL,
          metrics_json TEXT NOT NULL, warnings_json TEXT NOT NULL, next_steps_json TEXT NOT NULL,
          sections_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_dashboard86_case ON case_dashboards_86(case_id, created_at);
        """); self.db.conn.commit()
    def build(self, case_id: str, persist: bool = True) -> Dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id]) or {"case_id": case_id, "title": "unknown"}
        metrics = {
            "targets": self._count("targets", case_id),
            "graph_nodes": self._count("investigation_graph_nodes_68", case_id),
            "graph_edges": self._count("investigation_graph_edges_68", case_id),
            "captures": self._count("real_captures_74", case_id),
            "evidence_items": self._count("local_evidence_items_75", case_id),
            "claims": self._count("claims_v3_80", case_id),
            "public_documents": self._count("public_documents_85", case_id),
            "search_results": self._count("search_results_81", case_id),
        }
        open_claims = self.db.all("SELECT claim_id,grade,review_status,statement FROM claims_v3_80 WHERE case_id=? AND review_status NOT IN ('accepted','rejected') ORDER BY created_at DESC LIMIT 20", [case_id]) if self._table("claims_v3_80") else []
        unreviewed_edges = self.db.all("SELECT edge_id,edge_type,confidence,review_status FROM investigation_graph_edges_68 WHERE case_id=? AND review_status IN ('candidate','unreviewed') ORDER BY created_at DESC LIMIT 20", [case_id]) if self._table("investigation_graph_edges_68") else []
        warnings = []
        if metrics["claims"] and open_claims:
            warnings.append({"level": "medium", "code": "open_claim_reviews", "message": "Claims require analyst review before export."})
        if metrics["graph_edges"] and unreviewed_edges:
            warnings.append({"level": "medium", "code": "unreviewed_graph_edges", "message": "Candidate graph edges are not confirmed relationships."})
        if metrics["evidence_items"] == 0:
            warnings.append({"level": "high", "code": "missing_evidence_vault_items", "message": "No local evidence artifacts are stored for this case."})
        if metrics["captures"] == 0:
            warnings.append({"level": "medium", "code": "missing_real_captures", "message": "No real capture snapshots are recorded."})
        readiness = max(0, min(100, metrics["evidence_items"] * 12 + metrics["claims"] * 8 + metrics["graph_edges"] * 5 + metrics["captures"] * 10 - len([w for w in warnings if w["level"] == "high"]) * 15))
        status = "operational_review_ready" if readiness >= 75 else "working_case" if readiness >= 40 else "foundation_missing"
        next_steps = []
        if metrics["captures"] == 0: next_steps.append("Capture public source snapshots before building stronger claims.")
        if metrics["evidence_items"] == 0: next_steps.append("Store source artifacts in the Evidence Vault and verify hashes.")
        if unreviewed_edges: next_steps.append("Review candidate graph edges and reject weak associations.")
        if open_claims: next_steps.append("Review open claims and add counter-evidence where needed.")
        if not next_steps: next_steps.append("Prepare a redacted report package and run Casefile Pro verification.")
        result = {"dashboard_id": new_id("dash86"), "case_id": case_id, "case": case, "status": status, "readiness_score": readiness, "metrics": metrics, "warnings": warnings, "next_steps": next_steps, "sections": {"open_claims": open_claims, "unreviewed_edges": unreviewed_edges}}
        if persist:
            self.db.execute("INSERT INTO case_dashboards_86(dashboard_id,case_id,status,metrics_json,warnings_json,next_steps_json,sections_json,created_at) VALUES(?,?,?,?,?,?,?,?)", [result["dashboard_id"], case_id, status, dumps(metrics), dumps(warnings), dumps(next_steps), dumps(result["sections"]), now_ts()])
            self.audit.log("build", "case_dashboard_86", result["dashboard_id"], case_id, {"status": status, "readiness_score": readiness})
        return result
    def latest(self, case_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM case_dashboards_86 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if not row: return self.build(case_id)
        row["metrics"] = loads(row.pop("metrics_json", "{}"), {}); row["warnings"] = loads(row.pop("warnings_json", "[]"), []); row["next_steps"] = loads(row.pop("next_steps_json", "[]"), []); row["sections"] = loads(row.pop("sections_json", "{}"), {})
        return row
    def _table(self, name: str) -> bool:
        return self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]) is not None
    def _count(self, table: str, case_id: str) -> int:
        if not self._table(table): return 0
        return int((self.db.one(f"SELECT COUNT(*) c FROM {table} WHERE case_id=?", [case_id]) or {"c": 0})["c"])
