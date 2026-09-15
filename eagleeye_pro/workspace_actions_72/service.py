from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class WorkspaceActions72Service:
    """Build 72.0 interactive analyst workspace actions.

    The service turns Workspace 71 from a passive dashboard into an auditable
    review surface. Every state change is written as an action event and, where
    appropriate, reflected in graph/capture/export tables. It does not collect
    external data and remains review-first by design.
    """
    EDGE_STATUSES = {"candidate", "accepted", "rejected", "needs_more_evidence", "reviewed"}
    CAPTURE_STATUSES = {"captured_to_review", "verified", "tamper_warning", "rejected", "needs_recapture"}
    CLAIM_STATUSES = {"unverified_hint", "weakly_supported", "partially_supported", "strongly_supported", "contradicted", "rejected", "needs_manual_review"}

    def __init__(self, db: Database, audit: AuditService, *, graph=None, capture_vault=None, quality_control=None):
        self.db = db
        self.audit = audit
        self.graph = graph
        self.capture_vault = capture_vault
        self.quality_control = quality_control
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS workspace_action_events_72 (
          action_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, entity_id TEXT DEFAULT '', action_type TEXT NOT NULL,
          object_type TEXT NOT NULL, object_id TEXT NOT NULL, from_status TEXT DEFAULT '', to_status TEXT DEFAULT '',
          actor TEXT NOT NULL, reason TEXT DEFAULT '', details_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_workspace72_case ON workspace_action_events_72(case_id, created_at);
        CREATE TABLE IF NOT EXISTS export_gate_reviews_72 (
          review_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, entity_id TEXT DEFAULT '', export_mode TEXT NOT NULL,
          decision TEXT NOT NULL, reasons_json TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_exportgate72_case ON export_gate_reviews_72(case_id, created_at);
        CREATE TABLE IF NOT EXISTS claim_reviews_72 (
          claim_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, entity_id TEXT DEFAULT '', statement TEXT NOT NULL,
          status TEXT NOT NULL, support_refs_json TEXT NOT NULL, contra_refs_json TEXT NOT NULL,
          actor TEXT NOT NULL, reason TEXT DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_claimreviews72_case ON claim_reviews_72(case_id, status);
        """)
        self.db.conn.commit()

    def review_graph_edge(self, case_id: str, edge_id: str, status: str, reason: str = "", actor: str = "local-analyst") -> Dict[str, Any]:
        if status not in self.EDGE_STATUSES:
            raise ValueError(f"unsupported edge review status: {status}")
        edge = self.db.one("SELECT * FROM investigation_graph_edges_68 WHERE edge_id=? AND case_id=?", [edge_id, case_id])
        if not edge:
            raise KeyError(edge_id)
        old = edge.get("review_status", "candidate")
        self.db.execute("UPDATE investigation_graph_edges_68 SET review_status=?, metadata_json=? WHERE edge_id=?", [status, self._merge_json(edge.get("metadata_json"), {"review_reason": reason, "reviewed_by": actor, "reviewed_at": now_ts()}), edge_id])
        event = self._event(case_id, "review_graph_edge", "graph_edge_68", edge_id, old, status, actor, reason, {"edge_type": edge.get("edge_type")})
        return {"ok": True, "edge_id": edge_id, "from_status": old, "to_status": status, "event": event}

    def verify_capture(self, case_id: str, artifact_id: str, actor: str = "local-analyst", reason: str = "") -> Dict[str, Any]:
        if not self.capture_vault:
            raise RuntimeError("capture_vault service not attached")
        artifact = self.capture_vault.get_artifact(artifact_id)
        if artifact.get("case_id") != case_id:
            raise KeyError(artifact_id)
        verification = self.capture_vault.verify_artifact(artifact_id)
        old = artifact.get("custody_status", "captured_to_review")
        new = "verified" if verification.get("valid") else "tamper_warning"
        self.db.execute("UPDATE capture_artifacts_69 SET custody_status=?, metadata_json=? WHERE artifact_id=?", [new, dumps({**artifact.get("metadata", {}), "verification": verification, "verified_by": actor, "verified_at": now_ts(), "verification_reason": reason}), artifact_id])
        event = self._event(case_id, "verify_capture", "capture_artifact_69", artifact_id, old, new, actor, reason, verification)
        return {"ok": verification.get("valid"), "artifact_id": artifact_id, "from_status": old, "to_status": new, "verification": verification, "event": event}

    def create_or_update_claim_review(self, case_id: str, statement: str, status: str = "unverified_hint", entity_id: str = "", support_refs: List[str] | None = None, contra_refs: List[str] | None = None, actor: str = "local-analyst", reason: str = "", claim_id: str = "") -> Dict[str, Any]:
        if status not in self.CLAIM_STATUSES:
            raise ValueError(f"unsupported claim status: {status}")
        ts = now_ts()
        if claim_id:
            existing = self.db.one("SELECT * FROM claim_reviews_72 WHERE claim_id=? AND case_id=?", [claim_id, case_id])
            if not existing:
                raise KeyError(claim_id)
            old = existing.get("status", "")
            self.db.execute("UPDATE claim_reviews_72 SET statement=?,status=?,support_refs_json=?,contra_refs_json=?,actor=?,reason=?,updated_at=? WHERE claim_id=?", [statement, status, dumps(support_refs or []), dumps(contra_refs or []), actor, reason, ts, claim_id])
        else:
            claim_id = new_id("claim72")
            old = ""
            self.db.execute("INSERT INTO claim_reviews_72(claim_id,case_id,entity_id,statement,status,support_refs_json,contra_refs_json,actor,reason,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", [claim_id, case_id, entity_id, statement, status, dumps(support_refs or []), dumps(contra_refs or []), actor, reason, ts, ts])
        event = self._event(case_id, "review_claim", "claim_review_72", claim_id, old, status, actor, reason, {"support_refs": support_refs or [], "contra_refs": contra_refs or []})
        return self.get_claim(claim_id) | {"event": event}

    def set_export_gate(self, case_id: str, export_mode: str = "internal_redacted", decision: str = "review_required", reasons: List[str] | None = None, entity_id: str = "", actor: str = "local-analyst") -> Dict[str, Any]:
        rid = new_id("expg72")
        self.db.execute("INSERT INTO export_gate_reviews_72(review_id,case_id,entity_id,export_mode,decision,reasons_json,actor,created_at) VALUES(?,?,?,?,?,?,?,?)", [rid, case_id, entity_id, export_mode, decision, dumps(reasons or []), actor, now_ts()])
        event = self._event(case_id, "set_export_gate", "export_gate_review_72", rid, "", decision, actor, "; ".join(reasons or []), {"export_mode": export_mode})
        return self.get_export_gate_review(rid) | {"event": event}

    def list_actions(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM workspace_action_events_72 WHERE case_id=? ORDER BY created_at DESC", [case_id])
        for r in rows:
            r["details"] = loads(r.pop("details_json", "{}"), {})
        return rows

    def get_claim(self, claim_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM claim_reviews_72 WHERE claim_id=?", [claim_id])
        if not row:
            raise KeyError(claim_id)
        row["support_refs"] = loads(row.pop("support_refs_json", "[]"), [])
        row["contra_refs"] = loads(row.pop("contra_refs_json", "[]"), [])
        return row

    def latest_export_gate(self, case_id: str) -> Dict[str, Any] | None:
        row = self.db.one("SELECT * FROM export_gate_reviews_72 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if not row:
            return None
        row["reasons"] = loads(row.pop("reasons_json", "[]"), [])
        return row

    def get_export_gate_review(self, review_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM export_gate_reviews_72 WHERE review_id=?", [review_id])
        if not row:
            raise KeyError(review_id)
        row["reasons"] = loads(row.pop("reasons_json", "[]"), [])
        return row

    def _event(self, case_id: str, action_type: str, object_type: str, object_id: str, from_status: str, to_status: str, actor: str, reason: str, details: Dict[str, Any]) -> Dict[str, Any]:
        aid = new_id("act72")
        self.db.execute("INSERT INTO workspace_action_events_72(action_id,case_id,action_type,object_type,object_id,from_status,to_status,actor,reason,details_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", [aid, case_id, action_type, object_type, object_id, from_status or "", to_status or "", actor, reason, dumps(details), now_ts()])
        self.audit.log(action_type, object_type, object_id, case_id, {"from": from_status, "to": to_status, "reason": reason})
        return self.list_actions(case_id)[0]

    def _merge_json(self, raw: str | None, patch: Dict[str, Any]) -> str:
        data = loads(raw, {}) or {}
        data.update(patch)
        return dumps(data)
