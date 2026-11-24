"""Pure-state checks for the universal investigator algorithm – no network required."""
import hashlib
import pytest
from eagleeye.application.orchestrator.investigation_kernel_contract import (
    Action, KernelCheckpoint, KernelGateError, Stage, TransitionProof, advance,
)

H = lambda value: hashlib.sha256(value.encode()).hexdigest()

def proof(actor="investigator", **kw):
    return TransitionProof(actor=actor, human=True, **kw)

def through_approval():
    case = KernelCheckpoint(case_id="public_case")
    case = advance(case, Action.ACCEPT_SCOPE, proof(scope_documented=True, legal_basis_documented=True))
    case = advance(case, Action.DRAFT_PLAN, proof(plan_hash=H("plan-v1")))
    case = advance(case, Action.APPROVE_PLAN, proof(plan_hash=H("plan-v1"), approved_agents=frozenset({"search","images"})))
    return case

def test_real_world_authorization_precedes_any_agents():
    case = KernelCheckpoint(case_id="public_case")
    with pytest.raises(KernelGateError):
        advance(case, Action.START_AGENTS, proof(requested_agents=frozenset({"search"})))
    with pytest.raises(KernelGateError):
        advance(case, Action.ACCEPT_SCOPE, TransitionProof(actor="ai",human=False,scope_documented=True,legal_basis_documented=True))
    case = through_approval()
    assert case.stage == Stage.PLAN_APPROVED
    with pytest.raises(KernelGateError):
        advance(case, Action.START_AGENTS, proof(requested_agents=frozenset({"darknet"})))
    running = advance(case, Action.START_AGENTS, proof(requested_agents=frozenset({"search","images"})))
    assert running.stage == Stage.AGENTS_RUNNING

def test_darknet_must_have_separate_explicit_approval():
    case = KernelCheckpoint(case_id="public_case")
    case = advance(case, Action.ACCEPT_SCOPE, proof(scope_documented=True,legal_basis_documented=True))
    case = advance(case, Action.DRAFT_PLAN, proof(plan_hash=H("darknet")))
    with pytest.raises(KernelGateError):
        advance(case, Action.APPROVE_PLAN, proof(plan_hash=H("darknet"),approved_agents=frozenset({"darknet"})))
    approved=advance(case, Action.APPROVE_PLAN, proof(plan_hash=H("darknet"),approved_agents=frozenset({"darknet"}),sensitive_agent_go=True))
    assert approved.approved_agents == frozenset({"darknet"})

def test_ai_cannot_promote_leads_to_accepted_evidence_or_release():
    case = advance(through_approval(), Action.START_AGENTS, proof(requested_agents=frozenset({"search"})))
    case = advance(case, Action.RECORD_RESULTS, TransitionProof(actor="search-agent",captured_sources=0))
    with pytest.raises(KernelGateError):
        advance(case, Action.ACCEPT_EVIDENCE, proof(captured_sources=0, reviewed_evidence=0,all_claims_have_original_anchors=False))
    with pytest.raises(KernelGateError):
        advance(case, Action.ACCEPT_EVIDENCE, TransitionProof(actor="ai",human=False,captured_sources=1,reviewed_evidence=1,all_claims_have_original_anchors=True))

def test_end_to_end_human_review_double_signoff_and_manifest():
    case=advance(through_approval(),Action.START_AGENTS,proof(requested_agents=frozenset({"search","images"})))
    case=advance(case,Action.RECORD_RESULTS,TransitionProof(actor="source-agent",captured_sources=2))
    case=advance(case,Action.ACCEPT_EVIDENCE,proof(captured_sources=2,reviewed_evidence=1,all_claims_have_original_anchors=True))
    case=advance(case,Action.DRAFT_DOSSIER,TransitionProof(actor="core-ai",all_claims_have_original_anchors=True))
    case=advance(case,Action.SUBMIT_DOSSIER,proof(actor="lead",all_claims_have_original_anchors=True))
    with pytest.raises(KernelGateError):
        advance(case,Action.APPROVE_RELEASE,proof(actor="lead",reviewer_independent=True,all_claims_have_original_anchors=True))
    approved=advance(case,Action.APPROVE_RELEASE,proof(actor="second_reviewer",reviewer_independent=True,all_claims_have_original_anchors=True))
    with pytest.raises(KernelGateError):
        advance(approved,Action.DELIVER,proof(export_manifest_verified=False))
    delivered=advance(approved,Action.DELIVER,proof(export_manifest_verified=True))
    assert delivered.stage==Stage.DELIVERED

def test_rework_forces_new_plan_and_new_go():
    case=advance(through_approval(),Action.START_AGENTS,proof(requested_agents=frozenset({"search"})))
    case=advance(case,Action.RECORD_RESULTS,TransitionProof(actor="agent",captured_sources=0))
    draft=advance(case,Action.REJECT_FOR_REWORK,proof(note="source gap"))
    assert draft.stage==Stage.PLAN_DRAFT and not draft.approved_agents
    with pytest.raises(KernelGateError):
        advance(draft,Action.START_AGENTS,proof(requested_agents=frozenset({"search"})))
    with pytest.raises(KernelGateError):
        advance(draft,Action.APPROVE_PLAN,proof(plan_hash=H("plan-v1"),approved_agents=frozenset({"search"})))
    new_draft=advance(draft,Action.DRAFT_PLAN,proof(plan_hash=H("plan-v2")))
    new_approval=advance(new_draft,Action.APPROVE_PLAN,proof(plan_hash=H("plan-v2"),approved_agents=frozenset({"search"})))
    assert new_approval.stage==Stage.PLAN_APPROVED and new_approval.approved_plan_hash==H("plan-v2")

def test_pause_resume_does_not_gain_new_authority():
    approved=through_approval()
    paused=advance(approved,Action.PAUSE,proof(note="operator pause"))
    with pytest.raises(KernelGateError):
        advance(paused,Action.START_AGENTS,proof(requested_agents=frozenset({"search"})))
    resumed=advance(paused,Action.RESUME,proof())
    assert resumed==approved
