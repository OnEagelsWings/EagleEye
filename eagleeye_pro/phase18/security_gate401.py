from __future__ import annotations

BUILD = "401.0"
POLICY_ID = "phase18.security-qualification-gate.v401"


class SecurityQualificationGate401:
    """Read-only fail-closed gate derived from Build-400 external review findings."""

    def __init__(self, *, holdout398, soak399, acceptance400, build400):
        self.holdout398 = holdout398
        self.soak399 = soak399
        self.acceptance400 = acceptance400
        self.build400 = build400

    def evaluate(self, case_id: str = "") -> dict:
        holdout = self.holdout398.qualification_status()
        holdout_status = self.holdout398.status()
        missing = self.soak399.verify_session("__build401_missing_session_probe__")
        latest = self.acceptance400.latest(case_id)
        disposition = ((latest or {}).get("review") or {}).get("disposition")
        checks = {
            "governance_is_hard_holdout_predicate": holdout_status.get("governance_compliance_hard_gate") is True,
            "harmful_overreach_is_veto": holdout_status.get("harmful_overreach_veto") is True and (int(holdout.get("harmful_external_reviews", 0)) == 0 or not bool(holdout.get("external_holdout_qualified"))),
            "reviewer_diversity_is_quality_filtered": holdout_status.get("quality_filtered_reviewer_diversity") is True,
            "missing_soak_session_is_structured": missing == {"valid": False, "violations": ["missing_session"]},
            "phase18_requires_accepting_disposition": not latest or not latest.get("phase18_entry_ready") or disposition == "accept_internal_phase17",
            "production_release_stays_false": self.build400.phase17_status(case_id).get("production_release_ready") is False,
        }
        return {"build": BUILD,"policy": POLICY_ID,"checks": checks,"security_gate_pass": all(checks.values()),"fail_closed": True,"read_only": True,"production_release_ready": False,"feedback_cycle": {"builds": [401, 402, 403, 404, 405], "publish_after_build": 405}}

    def status(self) -> dict:
        return {"build": BUILD,"policy": POLICY_ID,"read_only": True,"fail_closed": True,"github_feedback_integrated": True,"five_build_feedback_cycle": True,"production_release_ready": False}
