from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, asdict
from typing import Any

BUILD = "403.0"
POLICY_ID = "phase18.negative-path-abuse-framework.v403"


@dataclass(frozen=True)
class NegativePathScenario:
    key: str
    category: str
    component: str
    expected: str
    severity: str
    automated: bool = True


SCENARIOS = (
    NegativePathScenario("missing.soak_session", "missing_record", "target_soak399.verify_session", "structured_missing_session", "P1"),
    NegativePathScenario("missing.acceptance_run", "missing_record", "final_acceptance400.verify", "structured_missing_run", "P1"),
    NegativePathScenario("auth.read_only_global_acceptance", "authorization", "final_acceptance400.run_acceptance", "permission_denied", "P1"),
    NegativePathScenario("auth.read_only_case_mutation", "authorization", "governance359.authorize", "permission_denied", "P1"),
    NegativePathScenario("confirmation.acceptance_run", "confirmation", "final_acceptance400.run_acceptance", "exact_confirmation_required", "P1"),
    NegativePathScenario("confirmation.acceptance_review", "confirmation", "final_acceptance400.review", "exact_confirmation_required", "P1"),
    NegativePathScenario("review.invalid_disposition", "invalid_state", "final_acceptance400.review", "unsupported_disposition", "P1"),
    NegativePathScenario("review.duplicate_acceptance", "duplicate_mutation", "phase17_acceptance_review_400", "unique_review_per_run", "P1"),
    NegativePathScenario("qualification.governance_bypass", "abuse", "model_holdout398.qualification_status", "governance_hard_veto", "P1"),
    NegativePathScenario("qualification.bad_second_reviewer", "abuse", "model_holdout398.qualification_status", "quality_reviewer_diversity", "P1"),
    NegativePathScenario("qualification.harmful_overreach", "abuse", "model_holdout398.qualification_status", "harmful_overreach_veto", "P1"),
    NegativePathScenario("readiness.needs_remediation", "invalid_state", "build400.phase17_status", "phase18_not_ready", "P1"),
    NegativePathScenario("scope.empty_case_id", "scope_manipulation", "final_acceptance400._auth", "global_scope_authorized", "P1"),
    NegativePathScenario("integrity.acceptance_tamper", "integrity", "final_acceptance400.verify", "hash_chain_failure", "P1"),
    NegativePathScenario("integrity.soak_tamper", "integrity", "target_soak399.verify_session", "hash_chain_failure", "P1"),
)


class NegativePathFramework403:
    """Read-only catalogue and source/runtime contract audit for fail-closed behavior.

    The framework does not grant authority and does not execute external research. Runtime
    probes are limited to read-only validation calls against impossible identifiers.
    """

    def __init__(self, *, build401: Any, build402: Any, soak399: Any, acceptance400: Any):
        self.build401 = build401
        self.build402 = build402
        self.soak399 = soak399
        self.acceptance400 = acceptance400

    def catalog(self) -> dict[str, Any]:
        rows = [asdict(s) for s in SCENARIOS]
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "default_fail_closed": True,
            "scenarios": rows,
            "scenario_count": len(rows),
            "categories": sorted({s.category for s in SCENARIOS}),
            "p1_scenarios": sum(1 for s in SCENARIOS if s.severity == "P1"),
            "production_release_ready": False,
        }

    @staticmethod
    def _source(module_name: str, class_name: str, method_name: str) -> str:
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        return inspect.getsource(getattr(cls, method_name))

    def contract_audit(self) -> dict[str, Any]:
        holdout = self._source("eagleeye_pro.phase17.model_holdout398", "ModelHoldoutEvaluation398", "qualification_status")
        soak = self._source("eagleeye_pro.phase17.target_soak399", "TargetEnvironmentSoak399", "verify_session")
        acceptance_auth = self._source("eagleeye_pro.phase17.final_acceptance400", "Phase17FinalAcceptance400", "_auth")
        acceptance_run = self._source("eagleeye_pro.phase17.final_acceptance400", "Phase17FinalAcceptance400", "run_acceptance")
        acceptance_review = self._source("eagleeye_pro.phase17.final_acceptance400", "Phase17FinalAcceptance400", "review")
        acceptance_verify = self._source("eagleeye_pro.phase17.final_acceptance400", "Phase17FinalAcceptance400", "verify")
        status400 = self._source("eagleeye.application.build400.service", "Build400Phase17FinalAcceptanceService", "phase17_status")
        checks = {
            "soak_missing_record_structured": "missing_session" in soak and "if not row" in soak,
            "acceptance_missing_record_structured": "missing_run" in acceptance_verify and "if not run" in acceptance_verify,
            "global_acceptance_governed": "governance.authorize" in acceptance_auth and "dossier.review" in acceptance_auth,
            "run_exact_confirmation": "confirmation!=CONFIRM_RUN" in acceptance_run.replace(" ", ""),
            "review_exact_confirmation": "confirmation!=CONFIRM_REVIEW" in acceptance_review.replace(" ", ""),
            "review_disposition_allowlist": "accept_internal_phase17" in acceptance_review and "needs_remediation" in acceptance_review,
            "holdout_governance_hard_veto": "governance_compliance=1" in holdout.replace(" ", ""),
            "holdout_quality_reviewer_diversity": "qualifying_external_reviewers" in holdout,
            "holdout_harmful_overreach_veto": "harmful_external_reviews==0" in holdout.replace(" ", ""),
            "needs_remediation_blocks_phase18": "accept_internal_phase17" in status400,
            "authorization_matrix_pass": bool(self.build402.authorization_audit().get("authorization_audit_pass")),
            "security_gate401_pass": bool(self.build401.security_gate().get("security_gate_pass")),
        }
        return {
            "build": BUILD,
            "checks": checks,
            "contract_audit_pass": all(checks.values()),
            "fail_closed": True,
            "production_release_ready": False,
        }

    def safe_runtime_probes(self) -> dict[str, Any]:
        soak = self.soak399.verify_session("missing-build403-probe")
        acceptance = self.acceptance400.verify("missing-build403-probe")
        checks = {
            "missing_soak_is_structured": soak == {"valid": False, "violations": ["missing_session"]},
            "missing_acceptance_is_structured": acceptance == {"valid": False, "violations": ["missing_run"]},
        }
        return {"build": BUILD, "checks": checks, "runtime_probe_pass": all(checks.values()), "mutation_free": True}

    def evaluate(self) -> dict[str, Any]:
        catalog = self.catalog()
        contracts = self.contract_audit()
        probes = self.safe_runtime_probes()
        return {
            "build": BUILD,
            "scenario_count": catalog["scenario_count"],
            "categories": catalog["categories"],
            "contract_audit_pass": contracts["contract_audit_pass"],
            "runtime_probe_pass": probes["runtime_probe_pass"],
            "negative_path_framework_ready": contracts["contract_audit_pass"] and probes["runtime_probe_pass"],
            "five_build_feedback_cycle": True,
            "next_public_feedback_build": "405.0",
            "production_release_ready": False,
        }
