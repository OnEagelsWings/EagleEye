"""Build 485: original Dork, image, graph, evidence and report remain case-scoped."""
import pytest
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app485 import create_workspace_app485
from eagleeye.interfaces.web.pilot485 import case_pilot_snapshot
from eagleeye.interfaces.web.research483 import propose
from test_build471_local_ai import workspace

pytestmark=pytest.mark.parametrize("workspace",[create_workspace_app485],indirect=True)

def test_first_case_has_honest_go_no_go_and_all_original_routes(workspace):
    app,client,user,cid,doc_id,*_=workspace
    assert app.version=="485.0"
    assert client.get("/health").json()["build"]=="485.0"
    stats=case_pilot_snapshot(app.state.context,user,cid)
    assert stats["documents"]>=1
    assert stats["evidence"]==0
    assert stats["search_leads"]==0
    page=client.get("/workbench/pilot485",params={"case_id":cid})
    assert page.status_code==200
    assert "NO-GO" in page.text
    assert "Ungeprüfte Suchhinweise" in page.text
    assert "Originaldokumente" in page.text
    assert page.headers["cache-control"]=="no-store"
    nav=client.get("/workbench",params={"case_id":cid})
    assert "Pilot-Abnahme und belegbarer Fortschritt" in nav.text
    for route in ("/workbench/dorks482","/workbench/leads483",
                  "/workbench/images482","/workbench/media484",
                  "/graph464","/workbench/closure","/workbench/report"):
        result=client.get(route,params={"case_id":cid})
        assert result.status_code==200,(route,result.status_code)

def test_real_lead_is_visible_but_not_auto_evidence(workspace):
    app,client,user,cid,*_=workspace
    ctx=app.state.context
    propose(ctx,user,cid,"https://www.example.org/public-source",
            "Public observation","Manually opened a permitted public page, content unverified.")
    page=client.get("/workbench/pilot485",params={"case_id":cid})
    assert page.status_code==200
    assert "NO-GO" in page.text
    assert "Ungeprüfte Suchhinweise" in page.text
    assert ctx.evidence_claims_dossier_447.case_evidence(cid)==[]
    assert ctx.evidence_claims_dossier_447.case_claims(cid)==[]
    assert ctx.evidence_claims_dossier_447.case_dossiers(cid)==[]

def test_authentication_and_case_boundaries(workspace):
    app,client,user,cid,docid,foreign,*_=workspace
    assert client.get("/workbench/pilot485",params={"case_id":"missing"}).status_code==403
    with TestClient(app) as anonymous:
        result=anonymous.get("/workbench/pilot485",params={"case_id":cid})
        assert result.status_code==401
        assert "Synthetic AI case" not in result.text

def test_tampered_lead_disables_pilot_board(workspace):
    app,client,user,cid,*_=workspace
    ctx=app.state.context
    row=propose(ctx,user,cid,"https://www.example.org/public-source",
            "Public observation","This public document is a candidate for independent verification.")
    ctx.db.execute("UPDATE research_leads_483 SET title=? WHERE lead_id=?",
                   ("Unlogged alteration",row["lead_id"]))
    assert client.get("/workbench/pilot485",params={"case_id":cid}).status_code==409
