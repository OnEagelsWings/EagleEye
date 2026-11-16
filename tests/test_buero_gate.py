"""Live provider runs (497/501) respect the mandate state; a refusal does not consume the plan step."""
import pytest

from eagleeye.application import execution497, plan496
from eagleeye.application.buero import service as buero
from eagleeye.interfaces.web.app497 import create_workspace_app497
from test_build471_local_ai import workspace  # noqa: F401  (fixture)

ws = pytest.mark.parametrize("workspace", [create_workspace_app497], indirect=True)
CLEAN = {"q_beziehung": "nein", "q_schutz": "nein", "q_schutzanordnung": "nein", "q_anschrift": "nein",
         "q_identitaet": "ja", "decision": "annehmen"}


def _approved_step(ctx, user, cid):
    plan = plan496.create_plan(ctx, user, cid, "Research public corporate registry facts",
                               "Public synthetic test data only; no private records or tracking.")
    step = plan496.add_step(ctx, user, cid, plan["plan_id"], "provider_proposal",
                            "Look for public technical account metadata.", "github_public_profile_120")
    plan = plan496.review_plan(ctx, user, cid, plan["plan_id"], "approved",
                               "Scope and proposed public provider need independent review.", plan["record_hash"])
    return plan, step


@ws
def test_live_run_waits_for_the_mandate_screening(workspace):
    app, client, user, cid, *_ = workspace
    ctx = app.state.context
    buero.attach_mandate(ctx, user, cid, {"kind": "online", "legal_basis_key": "einwilligung", "client_id": "neu",
                                          "client_kind": "privat", "client_name": "Kunde"})
    plan, step = _approved_step(ctx, user, cid)
    args = dict(query="sampletest", purpose="Public metadata validation only", mode="live",
                confirmation=execution497.APPROVAL_PHRASE, search_intent_id="intent_x", search_query_id="query_x")
    with pytest.raises(execution497.ExecutionError, match="Auftragsprüfung ist noch nicht abgeschlossen"):
        execution497.run_step(ctx, user, cid, plan["plan_id"], step["step_id"], **args)
    assert not execution497.get_execution(ctx, cid, step["step_id"]), "the refused step stays available"
    with pytest.raises(PermissionError, match="Auftragsprüfung"):
        ctx.provider_collection_120.execute(case_id=cid, provider_key="github_public_profile_120", query="sampletest",
                                            purpose="Public metadata validation only", approved_by=user["username"],
                                            confirmation=execution497.APPROVAL_PHRASE, mode="live")
    buero.screen(ctx, user, cid, CLEAN)
    with pytest.raises(Exception) as later:
        execution497.run_step(ctx, user, cid, plan["plan_id"], step["step_id"], **args)
    assert "Auftrag" not in str(later.value), "after acceptance only the usual search approval applies"


@ws
def test_cases_without_office_data_are_not_blocked(workspace):
    app, client, user, cid, *_ = workspace
    ctx = app.state.context
    assert ctx.research_gate(cid) == ""
