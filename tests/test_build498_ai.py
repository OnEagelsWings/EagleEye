"""Build 498: Ollama is optional; model text never becomes execution authority."""
import json
import pytest
from eagleeye.application import ai498,plan496
from eagleeye.interfaces.web.app498 import create_workspace_app498
from test_build471_local_ai import workspace

ws=pytest.mark.parametrize("workspace",[create_workspace_app498],indirect=True)
class StubModel:
    def __init__(self,data):self.data=data;self.calls=[]
    def request(self,method,path,payload=None,*,timeout=5):
        self.calls.append((method,path,payload))
        if path=="/api/tags":return {"models":[{"name":"local-test:1"}]}
        return {"message":{"content":json.dumps(self.data,ensure_ascii=False)}}

@ws
def test_local_ai_is_just_reviewable_plan_proposal(workspace):
    app,client,user,cid,*_=workspace;ctx=app.state.context
    plan=plan496.create_plan(ctx,user,cid,"Review public entity registry statements",
                             "Official or publicly licensed documents only, no private tracking.")
    model=StubModel({"steps":[{"kind":"document_review","instruction":"Compare public record with original PDF."},
                                {"kind":"hypothesis_check","instruction":"Identify contradictory official information."}]})
    proposal=ai498.generate(ctx,user,cid,plan["plan_id"],"local-test:1",client=model)
    assert proposal["state"]=="pending_review"
    assert model.calls[0][:2]==("GET","/api/tags")
    assert model.calls[1][:2]==("POST","/api/chat")
    assert plan496.list_steps(ctx,cid,plan["plan_id"])==[]
    ai498.decide(ctx,user,cid,plan["plan_id"],proposal["proposal_id"],"accepted",
                "The proposed steps are bounded and compatible with the case scope.")
    assert len(plan496.list_steps(ctx,cid,plan["plan_id"]))==2
    assert len(ai498.proposals(ctx,cid,plan["plan_id"]))==1
    with pytest.raises(ai498.ProposalError,match="Already reviewed"):
        ai498.decide(ctx,user,cid,plan["plan_id"],proposal["proposal_id"],"accepted",
                    "Duplicate model approval is explicitly forbidden.")

@ws
def test_rejects_tool_injection_and_unknown_providers(workspace):
    app,client,user,cid,*_=workspace;ctx=app.state.context
    plan=plan496.create_plan(ctx,user,cid,"Assess synthetic public company sources",
                             "Public test registers and controlled model proposals only.")
    for obj in [
        {"steps":[{"kind":"run_shell","instruction":"Run arbitrary command now."}]},
        {"steps":[{"kind":"provider_proposal","instruction":"Find public profiles in official catalog.",
                    "provider_key":"private_leak_db"}]},
        {"steps":[{"kind":"document_review","instruction":"Review official documents.", "shell":"rm -rf /"}]},
    ]:
        with pytest.raises((ai498.ProposalError,plan496.PlanError)):
            ai498.generate(ctx,user,cid,plan["plan_id"],"local-test:1",client=StubModel(obj))
    assert not ai498.proposals(ctx,cid,plan["plan_id"])
    assert not plan496.list_steps(ctx,cid,plan["plan_id"])

@ws
def test_ai_ui_does_not_make_local_model_call_on_get(workspace,monkeypatch):
    app,client,user,cid,*_=workspace
    monkeypatch.setattr(ai498.LocalOllama471,"request",lambda *args,**kw:(_ for _ in ()).throw(AssertionError("NO")))
    r=client.get("/workbench/ai498",params={"case_id":cid})
    assert r.status_code==200 and "127.0.0.1" in r.text
    assert client.get("/workbench/ai498",params={"case_id":"forbidden"}).status_code==403
