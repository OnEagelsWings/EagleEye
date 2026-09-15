from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
class QualityControl65Service:
    """Build 65.0 analyst quality, bias control and confidence calibration."""
    def __init__(self, db: Database, audit: AuditService):
        self.db = db; self.audit = audit; self.ensure_schema()
    def ensure_schema(self) -> None:
        self.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS quality_reviews_65 (
          review_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, entity_id TEXT DEFAULT '', score INTEGER DEFAULT 0,
          label TEXT NOT NULL, checklist_json TEXT NOT NULL, bias_warnings_json TEXT NOT NULL,
          calibration_json TEXT NOT NULL, required_actions_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_quality65_case ON quality_reviews_65(case_id, entity_id, created_at);
        """)
        self.db.conn.commit()
    def evaluate_workspace(self, case_id: str, entity_id: str = "", workspace: Dict[str, Any] | None = None, *, persist: bool = True) -> Dict[str, Any]:
        workspace = workspace or {}; top_findings = workspace.get("top_findings") or []; warnings = workspace.get("warnings") or []
        identity = workspace.get("doppler_and_identity") or {}; claim_summary = workspace.get("claim_summary") or {}
        checklist = [
            self._item("identity_anchor_present", bool(workspace.get("entity", {}).get("display_name")), "Identitätsanker vorhanden"),
            self._item("source_chain_present", bool(top_findings), "Mindestens ein Fund mit Quellenbezug vorhanden"),
            self._item("countercheck_documented", claim_summary.get("count", 0) > 0 or identity.get("assessment_count", 0) > 0, "Claim-/Identitätsprüfung dokumentiert"),
            self._item("doppler_checked", identity.get("assessment_count", 0) > 0, "Doppler-/Namensgleichheitsprüfung vorhanden"),
            self._item("warnings_visible", True, "Warnungen bleiben sichtbar und werden nicht geglättet"),
        ]
        bias: List[Dict[str, Any]] = []
        if top_findings and len({(i.get("finding", {}) or {}).get("domain", "") for i in top_findings}) <= 1:
            bias.append({"type": "single_source_domain_bias", "severity": "medium", "text": "Mehrere unabhängige Domains/Quellentypen prüfen."})
        if identity.get("max_doppler_risk", 0) >= 55:
            bias.append({"type": "doppler_risk", "severity": "high", "text": "Namensgleichheit/Doppelgänger-Risiko vor Claim-Verdichtung klären."})
        if claim_summary.get("reportable", 0) and not identity.get("assessment_count", 0):
            bias.append({"type": "claim_without_identity_gate", "severity": "high", "text": "Berichtsfähige Claims brauchen Identitätsgate."})
        if warnings:
            bias.append({"type": "open_warnings", "severity": "medium", "text": "Offene Warnungen vor externer Weitergabe prüfen."})
        calibration = self._calibrate(workspace, bias); passed = sum(1 for c in checklist if c["status"] == "pass")
        score = max(0, min(100, int((passed / len(checklist)) * 70 + calibration["confidence_score"] * 0.3 - len([b for b in bias if b["severity"] == "high"]) * 12)))
        label = "review_ready" if score >= 80 else "usable_with_bias_review" if score >= 60 else "not_ready"
        actions = sorted({a for b in bias for a in self._action_for_bias(b["type"])})
        rid = new_id("q65"); result = {"review_id": rid, "case_id": case_id, "entity_id": entity_id, "score": score, "label": label, "checklist": checklist, "bias_warnings": bias, "calibration": calibration, "required_actions": actions, "created_at": now_ts()}
        if persist:
            self.db.execute("""INSERT INTO quality_reviews_65(review_id,case_id,entity_id,score,label,checklist_json,bias_warnings_json,calibration_json,required_actions_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", [rid, case_id, entity_id, score, label, dumps(checklist), dumps(bias), dumps(calibration), dumps(actions), result["created_at"]])
            self.audit.log("evaluate", "quality_control_65", rid, case_id, {"score": score, "label": label, "bias_count": len(bias)})
        return result
    def latest(self, case_id: str, entity_id: str = "") -> Dict[str, Any] | None:
        row = self.db.one("SELECT * FROM quality_reviews_65 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id]) if not entity_id else self.db.one("SELECT * FROM quality_reviews_65 WHERE case_id=? AND entity_id=? ORDER BY created_at DESC LIMIT 1", [case_id, entity_id])
        if not row: return None
        row["checklist"] = loads(row.pop("checklist_json", "[]"), []); row["bias_warnings"] = loads(row.pop("bias_warnings_json", "[]"), []); row["calibration"] = loads(row.pop("calibration_json", "{}"), {}); row["required_actions"] = loads(row.pop("required_actions_json", "[]"), []); return row
    def _item(self, key: str, ok: bool, text: str) -> Dict[str, Any]: return {"key": key, "status": "pass" if ok else "review_required", "text": text}
    def _calibrate(self, workspace: Dict[str, Any], bias: List[Dict[str, Any]]) -> Dict[str, Any]:
        base = int(workspace.get("readiness_score", 0) or 0); high = len([b for b in bias if b.get("severity") == "high"]); medium = len([b for b in bias if b.get("severity") == "medium"])
        confidence = max(0, min(100, base - high * 18 - medium * 7)); label = "well_calibrated" if confidence >= 80 else "usable_with_caveats" if confidence >= 60 else "overclaiming_risk"
        return {"confidence_score": confidence, "label": label, "readiness_input": base, "bias_penalty": high * 18 + medium * 7}
    def _action_for_bias(self, bias_type: str) -> List[str]:
        return {"single_source_domain_bias": ["add_independent_source"], "doppler_risk": ["complete_identity_doppler_review"], "claim_without_identity_gate": ["run_identity_gate_before_claim"], "open_warnings": ["review_open_warnings"]}.get(bias_type, ["manual_review"])
