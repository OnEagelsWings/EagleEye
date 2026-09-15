from __future__ import annotations
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class ReviewBoardV288Service:
    """Build 88.0 review board v2: centralizes claims, graph edges, identity and counter-evidence review."""
    def __init__(self, db: Database, audit: AuditService):
        self.db = db; self.audit = audit; self.ensure_schema()
    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS review_decisions_88(
          decision_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT NOT NULL,
          decision TEXT NOT NULL, reason TEXT DEFAULT '', actor TEXT DEFAULT 'local-analyst', metadata_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_review88_case ON review_decisions_88(case_id,object_type,object_id);
        """); self.db.conn.commit()
    def board(self, case_id: str) -> Dict[str, Any]:
        claims = self.db.all("SELECT * FROM claims_v3_80 WHERE case_id=? ORDER BY created_at DESC", [case_id]) if self._table("claims_v3_80") else []
        edges = self.db.all("SELECT * FROM investigation_graph_edges_68 WHERE case_id=? AND review_status IN ('candidate','unreviewed') ORDER BY created_at DESC", [case_id]) if self._table("investigation_graph_edges_68") else []
        identity = self.db.all("SELECT * FROM identity_assessments_78 WHERE case_id=? ORDER BY created_at DESC", [case_id]) if self._table("identity_assessments_78") else []
        counters = self.db.all("SELECT * FROM counter_evidence_79 WHERE case_id=? ORDER BY created_at DESC", [case_id]) if self._table("counter_evidence_79") else []
        decisions = self.list_decisions(case_id)
        queues = {"claims_needing_review": [c for c in claims if c.get("review_status") not in {"accepted", "rejected"}], "candidate_edges": edges, "identity_reviews": identity, "counter_evidence": counters}
        metrics = {k: len(v) for k, v in queues.items()}; metrics["decisions"] = len(decisions)
        return {"case_id": case_id, "metrics": metrics, "queues": queues, "recent_decisions": decisions[:20], "principle": "review_first_not_auto_truth"}
    def decide(self, case_id: str, object_type: str, object_id: str, decision: str, reason: str = "", actor: str = "local-analyst", metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        allowed = {"accepted", "rejected", "needs_more_evidence", "redaction_required", "export_blocked", "export_allowed"}
        if decision not in allowed: raise ValueError("unsupported decision")
        did = new_id("rv88")
        self.db.execute("INSERT INTO review_decisions_88(decision_id,case_id,object_type,object_id,decision,reason,actor,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)", [did, case_id, object_type, object_id, decision, reason, actor, dumps(metadata or {}), now_ts()])
        if object_type == "claim_v3_80" and self._table("claims_v3_80"):
            self.db.execute("UPDATE claims_v3_80 SET review_status=?,updated_at=? WHERE claim_id=?", [decision, now_ts(), object_id])
        if object_type == "graph_edge_68" and self._table("investigation_graph_edges_68"):
            self.db.execute("UPDATE investigation_graph_edges_68 SET review_status=? WHERE edge_id=?", [decision, object_id])
        self.audit.log("decide", "review_decision_88", did, case_id, {"object_type": object_type, "object_id": object_id, "decision": decision})
        return self.get_decision(did)
    def get_decision(self, did: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM review_decisions_88 WHERE decision_id=?", [did])
        if not row: raise KeyError(did)
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return row
    def list_decisions(self, case_id: str):
        rows = self.db.all("SELECT * FROM review_decisions_88 WHERE case_id=? ORDER BY created_at DESC", [case_id])
        for r in rows: r["metadata"] = loads(r.pop("metadata_json", "{}"), {})
        return rows
    def _table(self, name: str) -> bool:
        return self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]) is not None
