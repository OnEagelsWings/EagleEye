from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, List
@dataclass(frozen=True)
class ExportDecision:
    decision: str; reasons: List[str]; required_actions: List[str]; export_mode: str
    def as_dict(self) -> Dict[str, Any]: return asdict(self)
class ExportPolicy:
    """Build 63.0 central export gate for casefiles and reports."""
    @staticmethod
    def evaluate(workspace: Dict[str, Any], privacy: Dict[str, Any], *, export_mode: str = "authority_redacted") -> Dict[str, Any]:
        reasons: List[str] = []; actions: List[str] = []
        score = int(workspace.get("readiness_score", 0) or 0)
        flags = set(privacy.get("flags") or [])
        detections = privacy.get("detections") or []
        detected_types = {d.get("type") for d in detections if isinstance(d, dict)}
        if flags & {"minor_data", "private_address", "redaction_block"} or detected_types & {"minor_related", "possible_address", "victim_witness_related"}:
            reasons.append("sensitive_or_address_related_data_requires_manual_review"); actions.append("manual_redaction_review"); decision = "blocked_until_redaction_review"
        elif score < 65:
            reasons.append("readiness_below_65"); actions.append("complete_evidence_matrix_and_countercheck"); decision = "draft_not_ready"
        elif workspace.get("warnings"):
            reasons.append("workspace_warnings_present"); actions.append("review_identity_doppler_and_privacy_warnings"); decision = "exportable_with_warnings"
        else:
            reasons.append("minimum_export_gate_passed"); decision = "export_ready"
        return ExportDecision(decision, sorted(set(reasons)), sorted(set(actions)), export_mode).as_dict()
