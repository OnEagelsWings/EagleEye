"""Pure universal investigation-kernel transition contract.

This module is deliberately NO-I/O: no SQLite, browser, network, credentials,
agent execution or dossier export. The GUI/service integration must implement
these transitions with a persistent case-scoped journal and authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet


class Stage(str, Enum):
    CREATED = "created"
    SCOPED = "scoped"
    PLAN_DRAFT = "plan_draft"
    PLAN_APPROVED = "plan_approved"
    AGENTS_RUNNING = "agents_running"
    RESULTS_COLLECTED = "results_collected"
    EVIDENCE_REVIEWED = "evidence_reviewed"
    DOSSIER_DRAFTED = "dossier_drafted"
    INVESTIGATOR_REVIEW = "investigator_review"
    RELEASE_APPROVED = "release_approved"
    DELIVERED = "delivered"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class Action(str, Enum):
    ACCEPT_SCOPE = "accept_scope"
    DRAFT_PLAN = "draft_plan"
    APPROVE_PLAN = "approve_plan"
    START_AGENTS = "start_agents"
    RECORD_RESULTS = "record_results"
    ACCEPT_EVIDENCE = "accept_evidence"
    DRAFT_DOSSIER = "draft_dossier"
    SUBMIT_DOSSIER = "submit_dossier"
    REJECT_FOR_REWORK = "reject_for_rework"
    APPROVE_RELEASE = "approve_release"
    DELIVER = "deliver"
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"


class KernelGateError(ValueError):
    """A required authorization, source or state transition was not met."""


@dataclass(frozen=True, slots=True)
class KernelCheckpoint:
    case_id: str
    stage: Stage = Stage.CREATED
    plan_hash: str = ""
    approved_agents: FrozenSet[str] = frozenset()
    approved_plan_hash: str = ""
    approved_by: str = ""
    dossier_author: str = ""
    reviewer: str = ""
    prior_stage: Stage | None = None
    stopped_reason: str = ""


@dataclass(frozen=True, slots=True)
class TransitionProof:
    """Assertion inputs from separately authorized, audited upstream services."""

    actor: str
    human: bool = False
    scope_documented: bool = False
    legal_basis_documented: bool = False
    plan_hash: str = ""
    approved_agents: FrozenSet[str] = frozenset()
    requested_agents: FrozenSet[str] = frozenset()
    sensitive_agent_go: bool = False
    captured_sources: int = 0
    reviewed_evidence: int = 0
    all_claims_have_original_anchors: bool = False
    unresolved_critical_issues: int = 0
    export_manifest_verified: bool = False
    reviewer_independent: bool = False
    note: str = ""


_ALLOWED = {
    (Stage.CREATED, Action.ACCEPT_SCOPE): Stage.SCOPED,
    (Stage.SCOPED, Action.DRAFT_PLAN): Stage.PLAN_DRAFT,
    (Stage.PLAN_DRAFT, Action.DRAFT_PLAN): Stage.PLAN_DRAFT,  # rework/revise before renewed GO
    (Stage.PLAN_DRAFT, Action.APPROVE_PLAN): Stage.PLAN_APPROVED,
    (Stage.PLAN_APPROVED, Action.START_AGENTS): Stage.AGENTS_RUNNING,
    (Stage.AGENTS_RUNNING, Action.RECORD_RESULTS): Stage.RESULTS_COLLECTED,
    (Stage.RESULTS_COLLECTED, Action.ACCEPT_EVIDENCE): Stage.EVIDENCE_REVIEWED,
    (Stage.EVIDENCE_REVIEWED, Action.DRAFT_DOSSIER): Stage.DOSSIER_DRAFTED,
    (Stage.DOSSIER_DRAFTED, Action.SUBMIT_DOSSIER): Stage.INVESTIGATOR_REVIEW,
    (Stage.INVESTIGATOR_REVIEW, Action.APPROVE_RELEASE): Stage.RELEASE_APPROVED,
    (Stage.RELEASE_APPROVED, Action.DELIVER): Stage.DELIVERED,
    (Stage.RESULTS_COLLECTED, Action.REJECT_FOR_REWORK): Stage.PLAN_DRAFT,
    (Stage.INVESTIGATOR_REVIEW, Action.REJECT_FOR_REWORK): Stage.PLAN_DRAFT,
}

HUMAN_ONLY = {
    Action.ACCEPT_SCOPE, Action.APPROVE_PLAN, Action.ACCEPT_EVIDENCE,
    Action.SUBMIT_DOSSIER, Action.APPROVE_RELEASE, Action.DELIVER,
    Action.PAUSE, Action.RESUME, Action.CANCEL,
}
NETWORK_SENSITIVE_AGENTS = frozenset({
    "darknet", "restricted_register", "external_ai", "licensed_person_data"
})


def advance(
    current: KernelCheckpoint, action: Action, proof: TransitionProof
) -> KernelCheckpoint:
    """Check *proof*; never authorise actions by just believing an AI output.

    The caller must attest proof with audited, ACL-checked system facts.
    """
    if not current.case_id or not proof.actor:
        raise KernelGateError("case and authenticated actor are required")
    if action in HUMAN_ONLY and not proof.human:
        raise KernelGateError("human actor approval required")

    if action == Action.PAUSE:
        if current.stage not in {Stage.AGENTS_RUNNING, Stage.PLAN_APPROVED}:
            raise KernelGateError("only queued/running investigation can pause")
        return KernelCheckpoint(
            case_id=current.case_id, stage=Stage.PAUSED,
            plan_hash=current.plan_hash, approved_agents=current.approved_agents,
            approved_plan_hash=current.approved_plan_hash,
            approved_by=current.approved_by,
            dossier_author=current.dossier_author, reviewer=current.reviewer,
            prior_stage=current.stage,
            stopped_reason=proof.note or "operator pause",
        )
    if action == Action.RESUME:
        if current.stage != Stage.PAUSED or current.prior_stage is None:
            raise KernelGateError("no resumable investigation")
        return KernelCheckpoint(
            case_id=current.case_id, stage=current.prior_stage,
            plan_hash=current.plan_hash, approved_agents=current.approved_agents,
            approved_plan_hash=current.approved_plan_hash,
            approved_by=current.approved_by,
            dossier_author=current.dossier_author, reviewer=current.reviewer,
        )
    if action == Action.CANCEL:
        if current.stage in {Stage.DELIVERED, Stage.CANCELLED}:
            raise KernelGateError("terminal case")
        return KernelCheckpoint(
            case_id=current.case_id, stage=Stage.CANCELLED,
            plan_hash=current.plan_hash, approved_agents=current.approved_agents,
            approved_plan_hash=current.approved_plan_hash,
            approved_by=current.approved_by, dossier_author=current.dossier_author,
            reviewer=current.reviewer, stopped_reason=proof.note or "operator cancel",
        )

    target = _ALLOWED.get((current.stage, action))
    if target is None:
        raise KernelGateError(f"invalid case transition: {current.stage} / {action}")
    if action == Action.ACCEPT_SCOPE and (
        not proof.scope_documented or not proof.legal_basis_documented
    ):
        raise KernelGateError("approved objective and legal basis required")
    if action == Action.DRAFT_PLAN:
        if not proof.plan_hash or len(proof.plan_hash) != 64:
            raise KernelGateError("persisted SHA-256 plan identity required")
        # A revised plan revokes every previous agent authority.
        return KernelCheckpoint(
            case_id=current.case_id, stage=target, plan_hash=proof.plan_hash
        )
    if action == Action.REJECT_FOR_REWORK:
        # Force *new* plan hash and independent GO before additional network.
        return KernelCheckpoint(case_id=current.case_id, stage=target)
    if action == Action.APPROVE_PLAN:
        if not current.plan_hash or proof.plan_hash != current.plan_hash:
            raise KernelGateError("approval must bind to exact immutable plan hash")
        if not proof.approved_agents:
            raise KernelGateError("explicit agent allowlist required")
        if NETWORK_SENSITIVE_AGENTS & proof.approved_agents and not proof.sensitive_agent_go:
            raise KernelGateError("independent special authorization required")
        return KernelCheckpoint(
            case_id=current.case_id, stage=target,
            plan_hash=current.plan_hash,
            approved_agents=proof.approved_agents,
            approved_plan_hash=current.plan_hash,
            approved_by=proof.actor,
        )
    if action == Action.START_AGENTS:
        if not current.approved_plan_hash or current.approved_plan_hash != current.plan_hash:
            raise KernelGateError("approved plan revision required")
        if not proof.requested_agents or not proof.requested_agents <= current.approved_agents:
            raise KernelGateError("dispatch exceeds approved agent scope")
    if action == Action.RECORD_RESULTS and proof.captured_sources < 0:
        raise KernelGateError("invalid capture count")
    if action == Action.ACCEPT_EVIDENCE and (
        proof.reviewed_evidence < 1 or proof.captured_sources < 1
        or not proof.all_claims_have_original_anchors
    ):
        raise KernelGateError("human-reviewed original evidence and provenance required")
    if action == Action.DRAFT_DOSSIER and not proof.all_claims_have_original_anchors:
        raise KernelGateError("claim provenance insufficient")
    if action == Action.SUBMIT_DOSSIER:
        if proof.unresolved_critical_issues:
            raise KernelGateError("critical issues require rework")
        if not proof.all_claims_have_original_anchors:
            raise KernelGateError("dossier cannot contain unsupported verified claims")
        return KernelCheckpoint(
            case_id=current.case_id, stage=target,
            plan_hash=current.plan_hash, approved_agents=current.approved_agents,
            approved_plan_hash=current.approved_plan_hash, approved_by=current.approved_by,
            dossier_author=proof.actor,
        )
    if action == Action.APPROVE_RELEASE:
        if (
            not proof.reviewer_independent or not current.dossier_author
            or proof.actor == current.dossier_author
            or proof.unresolved_critical_issues
            or not proof.all_claims_have_original_anchors
        ):
            raise KernelGateError("independent, attributable human dossier review required")
        return KernelCheckpoint(
            case_id=current.case_id, stage=target, plan_hash=current.plan_hash,
            approved_agents=current.approved_agents,
            approved_plan_hash=current.approved_plan_hash, approved_by=current.approved_by,
            dossier_author=current.dossier_author, reviewer=proof.actor,
        )
    if action == Action.DELIVER and (
        not current.reviewer or not proof.export_manifest_verified
    ):
        raise KernelGateError("approved reviewed dossier + verified export required")

    return KernelCheckpoint(
        case_id=current.case_id, stage=target, plan_hash=current.plan_hash,
        approved_agents=current.approved_agents,
        approved_plan_hash=current.approved_plan_hash,
        approved_by=current.approved_by,
        dossier_author=current.dossier_author, reviewer=current.reviewer,
    )
