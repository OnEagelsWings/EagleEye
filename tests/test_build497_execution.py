"""Build 497: approved-provider execution and no unapproved live egress."""
import pytest
from eagleeye.application import plan496, execution497
from eagleeye.interfaces.web.app497 import create_workspace_app497
from test_build471_local_ai import workspace

ws=pytest.mark.parametrize("workspace",[create_workspace_app497],indirect=True)

@ws
def test_provider_run_requires_plan_and_separate_live_approval(workspace,monkeypatch):
    app,client,user,cid,*_=workspace
    ctx=app.state.context
    plan=plan496.create_plan(ctx,user,cid,"Research public corporate registry facts",
                             "Public synthetic test data only; no private records or tracking.")
    step=plan496.add_step(ctx,user,cid,plan["plan_id"],"provider_proposal",
                          "Look for public technical account metadata.",
                          "github_public_profile_120")
    calls=[]
    provider=ctx.provider_collection_120
    def pretend_execute(**kwargs):
        calls.append(kwargs)
        return {"run_id":"synthetic_run_497","status":"completed"}
    monkeypatch.setattr(provider,"execute",pretend_execute)
    with pytest.raises(execution497.ExecutionError,match="not approved"):
        execution497.run_step(ctx,user,cid,plan["plan_id"],step["step_id"],query="sampletest",
                              purpose="Public metadata validation only",mode="replay",
                              confirmation=execution497.APPROVAL_PHRASE)
    plan=plan496.review_plan(ctx,user,cid,plan["plan_id"],"approved",
                "Scope and proposed public provider need independent review.",plan["record_hash"])
    with pytest.raises(execution497.ExecutionError,match="intent"):
        execution497.run_step(ctx,user,cid,plan["plan_id"],step["step_id"],query="sampletest",
                              purpose="Public metadata validation only",mode="live",
                              confirmation=execution497.APPROVAL_PHRASE)
    assert not calls and not execution497.get_execution(ctx,cid,step["step_id"])
    item=execution497.run_step(ctx,user,cid,plan["plan_id"],step["step_id"],query="sampletest",
                              purpose="Public metadata validation only",mode="replay",
                              confirmation=execution497.APPROVAL_PHRASE)
    assert item["state"]=="completed" and item["mode"]=="replay"
    assert calls[0]["mode"]=="replay" and calls[0]["max_results"]==20
    assert len(execution497.list_executions(ctx,cid,plan["plan_id"]))==1
    with pytest.raises(execution497.ExecutionError,match="already"):
        execution497.run_step(ctx,user,cid,plan["plan_id"],step["step_id"],query="sampletest",
                              purpose="Public metadata validation only",mode="replay",
                              confirmation=execution497.APPROVAL_PHRASE)

@ws
def test_failed_execution_is_never_automatically_retried(workspace,monkeypatch):
    app,client,user,cid,*_=workspace
    ctx=app.state.context
    plan=plan496.create_plan(ctx,user,cid,"Inspect synthetic public account metadata",
                             "Only public non-sensitive test fixtures, no live source collection.")
    step=plan496.add_step(ctx,user,cid,plan["plan_id"],"provider_proposal",
                          "Replay an approved public metadata query.",
                          "github_public_profile_120")
    plan496.review_plan(ctx,user,cid,plan["plan_id"],"approved",
               "Only offline replay of existing data is permitted here.",plan["record_hash"])
    def fail(**kwargs):raise RuntimeError("provider unavailable")
    monkeypatch.setattr(ctx.provider_collection_120,"execute",fail)
    with pytest.raises(execution497.ExecutionError,match="failed"):
        execution497.run_step(ctx,user,cid,plan["plan_id"],step["step_id"],query="sampletest",
                             purpose="Synthetic metadata verification",mode="replay",
                             confirmation=execution497.APPROVAL_PHRASE)
    assert execution497.get_execution(ctx,cid,step["step_id"])["state"]=="failed"
    with pytest.raises(execution497.ExecutionError,match="already"):
        execution497.run_step(ctx,user,cid,plan["plan_id"],step["step_id"],query="sampletest",
                             purpose="Synthetic metadata verification",mode="replay",
                             confirmation=execution497.APPROVAL_PHRASE)

@ws
def test_provider_workbench_is_case_scoped_and_never_runs_on_get(workspace,monkeypatch):
    app,client,user,cid,*_=workspace
    calls=[]
    monkeypatch.setattr(app.state.context.provider_collection_120,"execute",
                        lambda **k: calls.append(k))
    x=client.get("/workbench/run497",params={"case_id":cid})
    assert x.status_code==200 and "Replay" in x.text
    assert client.get("/workbench/run497",params={"case_id":"invalid"}).status_code==403
    assert calls==[]
