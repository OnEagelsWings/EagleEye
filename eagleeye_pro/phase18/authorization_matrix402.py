from __future__ import annotations

import importlib
import inspect
from dataclasses import dataclass, asdict
from typing import Any

from eagleeye.team.governance359 import ROLE_CAPABILITIES

BUILD = "402.0"
POLICY_ID = "phase18.authorization-matrix-audit.v402"


@dataclass(frozen=True)
class AuthorizationSurface:
    key: str
    module: str
    class_name: str
    method: str
    capability: str
    scope: str
    mutation: bool = True
    authorization_method: str = ""


SURFACES = (
    AuthorizationSurface("execution.preflight", "eagleeye_pro.phase17.execution_authority386", "ExecutionAuthority386", "preflight", "crawler.run", "case"),
    AuthorizationSurface("execution.revoke", "eagleeye_pro.phase17.execution_authority386", "ExecutionAuthority386", "revoke_grant", "crawler.run", "case"),
    AuthorizationSurface("execution.execute", "eagleeye_pro.phase17.controlled_executor387", "ControlledExecutor387", "execute_grant", "crawler.run", "case"),
    AuthorizationSurface("waves.start", "eagleeye_pro.phase17.research_wave_execution388", "GovernedResearchWave388", "start_session", "crawler.run", "case", authorization_method="_authorize"),
    AuthorizationSurface("waves.dispatch", "eagleeye_pro.phase17.research_wave_execution388", "GovernedResearchWave388", "attach_dispatch", "crawler.run", "case", authorization_method="_authorize"),
    AuthorizationSurface("waves.advance", "eagleeye_pro.phase17.research_wave_execution388", "GovernedResearchWave388", "advance", "crawler.run", "case", authorization_method="_authorize"),
    AuthorizationSurface("evidence.promote", "eagleeye_pro.phase17.result_intake389", "ResultIntake389", "promote_candidate", "source.review", "case", authorization_method="_authorize"),
    AuthorizationSurface("evidence.review.create", "eagleeye_pro.phase17.evidence_review390", "EvidenceReviewCorroboration390", "create_review", "source.review", "case", authorization_method="_authorize"),
    AuthorizationSurface("evidence.review.assess", "eagleeye_pro.phase17.evidence_review390", "EvidenceReviewCorroboration390", "assess_review", "source.review", "case", authorization_method="_authorize"),
    AuthorizationSurface("evidence.review.finalize", "eagleeye_pro.phase17.evidence_review390", "EvidenceReviewCorroboration390", "finalize_review", "source.review", "case", authorization_method="_authorize"),
    AuthorizationSurface("synthesis.claim.review", "eagleeye_pro.phase17.investigation_synthesis391", "InvestigationSynthesis391", "review_claim", "source.review", "case", authorization_method="_authorize"),
    AuthorizationSurface("synthesis.hypothesis.propose", "eagleeye_pro.phase17.investigation_synthesis391", "InvestigationSynthesis391", "propose_hypothesis", "dossier.write", "case", authorization_method="_authorize"),
    AuthorizationSurface("synthesis.hypothesis.review", "eagleeye_pro.phase17.investigation_synthesis391", "InvestigationSynthesis391", "review_hypothesis", "dossier.write", "case", authorization_method="_authorize"),
    AuthorizationSurface("reasoning.workspace.create", "eagleeye_pro.phase17.case_reasoning392", "CaseReasoningWorkspace392", "create_workspace", "dossier.write", "case", authorization_method="_authorize"),
    AuthorizationSurface("reasoning.plan.propose", "eagleeye_pro.phase17.case_reasoning392", "CaseReasoningWorkspace392", "propose_plan", "dossier.write", "case", authorization_method="_authorize"),
    AuthorizationSurface("reasoning.plan.review", "eagleeye_pro.phase17.case_reasoning392", "CaseReasoningWorkspace392", "review_plan", "dossier.write", "case", authorization_method="_authorize"),
    AuthorizationSurface("dialogue.challenge", "eagleeye_pro.phase17.investigator_dialogue393", "InvestigatorDialogueChallenge393", "challenge", "dossier.write", "case", authorization_method="_authorize"),
    AuthorizationSurface("dialogue.proposal.review", "eagleeye_pro.phase17.investigator_dialogue393", "InvestigatorDialogueChallenge393", "review_proposal", "dossier.write", "case", authorization_method="_authorize"),
    AuthorizationSurface("discussion.revision.propose", "eagleeye_pro.phase17.discussion_revision394", "InvestigatorDiscussionRevision394", "create_revision_proposal", "dossier.write", "case", authorization_method="_authorize"),
    AuthorizationSurface("discussion.revision.review", "eagleeye_pro.phase17.discussion_revision394", "InvestigatorDiscussionRevision394", "review_revision", "dossier.write", "case", authorization_method="_authorize"),
    AuthorizationSurface("discussion.revision.apply", "eagleeye_pro.phase17.discussion_revision394", "InvestigatorDiscussionRevision394", "apply_revision", "dossier.write", "case", authorization_method="_authorize"),
    AuthorizationSurface("state.branch.create", "eagleeye_pro.phase17.case_state_graph395", "CaseStateVersionGraph395", "create_branch", "dossier.write", "case", authorization_method="_auth"),
    AuthorizationSurface("state.adoption.review", "eagleeye_pro.phase17.case_state_graph395", "CaseStateVersionGraph395", "review_adoption", "dossier.write", "case", authorization_method="_auth"),
    AuthorizationSurface("state.adoption.apply", "eagleeye_pro.phase17.case_state_graph395", "CaseStateVersionGraph395", "apply_adoption", "dossier.write", "case", authorization_method="_auth"),
    AuthorizationSurface("reconciliation.baseline.create", "eagleeye_pro.phase17.case_reconciliation396", "CaseStateReconciliation396", "create_baseline", "dossier.write", "case", authorization_method="_auth"),
    AuthorizationSurface("reconciliation.reanalysis.propose", "eagleeye_pro.phase17.case_reconciliation396", "CaseStateReconciliation396", "propose_reanalysis", "dossier.write", "case", authorization_method="_auth"),
    AuthorizationSurface("reconciliation.reanalysis.review", "eagleeye_pro.phase17.case_reconciliation396", "CaseStateReconciliation396", "review_reanalysis", "dossier.write", "case", authorization_method="_auth"),
    AuthorizationSurface("reconciliation.baseline.advance", "eagleeye_pro.phase17.case_reconciliation396", "CaseStateReconciliation396", "advance_baseline", "dossier.write", "case", authorization_method="_auth"),
    AuthorizationSurface("analyst.recommendation.propose", "eagleeye_pro.phase17.argumentative_analyst397", "ArgumentativeAIAnalyst397", "propose_recommendation", "dossier.write", "case", authorization_method="_auth"),
    AuthorizationSurface("analyst.recommendation.review", "eagleeye_pro.phase17.argumentative_analyst397", "ArgumentativeAIAnalyst397", "review_recommendation", "dossier.write", "case", authorization_method="_auth"),
    AuthorizationSurface("acceptance.run.global", "eagleeye_pro.phase17.final_acceptance400", "Phase17FinalAcceptance400", "run_acceptance", "dossier.review", "global_or_case", authorization_method="_auth"),
    AuthorizationSurface("acceptance.review.global", "eagleeye_pro.phase17.final_acceptance400", "Phase17FinalAcceptance400", "review", "dossier.review", "global_or_case", authorization_method="_auth"),
)


class AuthorizationMatrixAudit402:
    """Read-only authorization inventory and source-level governance audit."""

    def __init__(self, *, governance: Any, identity: Any):
        self.governance = governance
        self.identity = identity

    @staticmethod
    def _allowed_roles(capability: str) -> list[str]:
        return sorted(role for role, caps in ROLE_CAPABILITIES.items() if capability in caps)

    def matrix(self) -> dict[str, Any]:
        rows = []
        for surface in SURFACES:
            row = asdict(surface)
            row["allowed_case_roles"] = self._allowed_roles(surface.capability)
            row["read_only_allowed"] = "read_only" in row["allowed_case_roles"]
            rows.append(row)
        return {"build": BUILD,"policy": POLICY_ID,"default_deny": True,"rows": rows,"mutation_surfaces": len(rows),"capabilities": sorted({s.capability for s in SURFACES}),"global_or_case_mutations": [s.key for s in SURFACES if s.scope == "global_or_case"],"production_release_ready": False}

    def _source_check(self, surface: AuthorizationSurface) -> dict[str, Any]:
        try:
            module = importlib.import_module(surface.module)
            cls = getattr(module, surface.class_name)
            method = getattr(cls, surface.method)
            method_source = inspect.getsource(method)
            auth_source = method_source
            if surface.authorization_method:
                helper = getattr(cls, surface.authorization_method)
                auth_source = inspect.getsource(helper)
            combined_source = method_source + "\n" + auth_source
            auth_path_present = "governance.authorize" in combined_source or "self._authorize(" in method_source or "self._auth(" in method_source
            capability_present = surface.capability in combined_source
            mutation_not_read_only = (not surface.mutation) or surface.capability != "case.read"
            return {"key": surface.key,"source_resolved": True,"authorization_path_present": auth_path_present,"expected_capability_present": capability_present,"mutation_not_case_read_only": mutation_not_read_only,"pass": auth_path_present and capability_present and mutation_not_read_only}
        except Exception as exc:
            return {"key": surface.key,"source_resolved": False,"authorization_path_present": False,"expected_capability_present": False,"mutation_not_case_read_only": surface.capability != "case.read","pass": False,"error": type(exc).__name__}

    def audit(self) -> dict[str, Any]:
        matrix = self.matrix()
        source_checks = [self._source_check(s) for s in SURFACES]
        read_only_denied = all(not row["read_only_allowed"] for row in matrix["rows"])
        global_scopes_review_only = all(s.capability == "dossier.review" for s in SURFACES if s.scope == "global_or_case")
        checks = {"all_sources_resolved": all(x["source_resolved"] for x in source_checks),"all_mutations_have_governance_path": all(x["authorization_path_present"] for x in source_checks),"all_expected_capabilities_present": all(x["expected_capability_present"] for x in source_checks),"no_mutation_uses_case_read_only": all(x["mutation_not_case_read_only"] for x in source_checks),"read_only_role_denied_all_catalogued_mutations": read_only_denied,"global_acceptance_requires_review_capability": global_scopes_review_only,"default_deny_declared": matrix["default_deny"] is True}
        return {"build": BUILD,"policy": POLICY_ID,"checks": checks,"source_checks": source_checks,"authorization_audit_pass": all(checks.values()),"fail_closed": True,"read_only_audit": True,"production_release_ready": False}

    def role_matrix(self) -> dict[str, Any]:
        caps = sorted({s.capability for s in SURFACES})
        roles = {role: {cap: cap in ROLE_CAPABILITIES[role] for cap in caps} for role in sorted(ROLE_CAPABILITIES)}
        return {"build": BUILD,"policy": POLICY_ID,"capabilities": caps,"roles": roles,"read_only_has_mutation_capability": any(roles["read_only"].values()),"production_release_ready": False}

    def status(self) -> dict[str, Any]:
        return {"build": BUILD,"policy": POLICY_ID,"authorization_matrix": True,"source_level_governance_audit": True,"global_scope_included": True,"default_deny": True,"read_only": True,"fail_closed": True,"production_release_ready": False}
