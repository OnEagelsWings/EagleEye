"""Build 483: real case-governed research leads are not Evidence."""
import pytest
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app483 import create_workspace_app483
from eagleeye.interfaces.web.research483 import listed,validate_public_lead_url
from test_build471_local_ai import workspace
from test_build478_findings import csrf_session
from test_build475_ai_checkpoint import member

pytestmark=pytest.mark.parametrize("workspace",[create_workspace_app483],indirect=True)

def payload(workspace):
    app,client,user,cid,*_=workspace
    return {
      "case_id":cid,"csrf":csrf_session(workspace),
      "url":"https://www.example.org/public/company-report.pdf",
      "title":"Public example research report",
      "note":"The analyst opened this public listing and documented the page context."
    }

def test_search_lead_real_case_first_run_graph_dork_image_and_report(workspace):
    app,client,user,cid,*_=workspace
    assert app.version=="483.0"
    assert client.get("/health").json()["build"]=="483.0"
    guided=client.get("/workbench",params={"case_id":cid})
    assert guided.status_code==200 and "Recherchefunde sichern" in guided.text
    expert=client.get("/workbench/expert",params={"case_id":cid})
    assert expert.status_code==200 and "Recherchefunde und Suchhinweise" in expert.text
    for route in ("/workbench/dorks482","/workbench/images482","/graph464",
                  "/documents458","/workbench/closure","/workbench/report",
                  "/workbench/leads483"):
        assert client.get(route,params={"case_id":cid}).status_code==200,route
    assert "Fallhinweis speichern" in client.get("/workbench/dorks482",
        params={"case_id":cid,"topic":"Example Research"}).text

def test_manual_search_lead_persists_without_promoting_it_to_fact(workspace):
    app,client,user,cid,*_=workspace
    ctx=app.state.context
    form=payload(workspace)
    before=ctx.db.one("SELECT count(*) n FROM acquisition_event_422")["n"]
    r=client.post("/workbench/leads483",data=form,follow_redirects=False)
    assert r.status_code==303,r.text[:320]
    leads=listed(ctx,cid)
    assert len(leads)==1 and leads[0]["review_state"]=="unverified_lead"
    assert leads[0]["created_by"]==user["username"]
    assert ctx.evidence_claims_dossier_447.case_claims(cid)==[]
    assert ctx.evidence_claims_dossier_447.case_evidence(cid)==[]
    assert ctx.db.one("SELECT count(*) n FROM acquisition_event_422")["n"]==before
    assert client.post("/workbench/leads483",data=form,follow_redirects=False).status_code==303
    assert len(listed(ctx,cid))==1
    response=client.get("/workbench/leads483",params={"case_id":cid})
    assert "Public example research report" in response.text
    assert "Ungeprüfter Suchhinweis" in response.text
    assert response.headers["cache-control"]=="no-store"

def test_cross_case_csrf_and_unsafe_urls_are_blocked(workspace):
    app,client,user,cid,doc_id,foreign,*_=workspace
    form=payload(workspace)
    assert client.post("/workbench/leads483",data={**form,"csrf":"forged"}).status_code==403
    for url in ("http://example.org", "https://127.0.0.1/", "https://localhost/",
                "https://private.local/", "file:///etc/passwd",
                "https://user:password@example.org/x", "https://example.org:8443/",
                "https://[::1]/", "https://example.org\nmalicious"):
        assert client.post("/workbench/leads483",data={**form,"url":url}).status_code==422,url
    assert app.state.context.db.one("SELECT count(*) n FROM research_leads_483")["n"]==0
    assert client.get("/workbench/leads483",params={"case_id":"missing_case"}).status_code==403
    with TestClient(app) as anonymous:
        assert anonymous.get("/workbench/leads483",params={"case_id":cid}).status_code==401
    # A case-scoped non-admin user cannot read the other case.
    member(workspace,"read_only")
    assert client.get("/workbench/leads483",params={"case_id":foreign}).status_code==403

def test_integrity_tamper_fails_closed(workspace):
    app,client,user,cid,*_=workspace
    assert client.post("/workbench/leads483",data=payload(workspace)).status_code==200
    ctx=app.state.context
    row=listed(ctx,cid)[0]
    ctx.db.execute("UPDATE research_leads_483 SET title=? WHERE lead_id=?",("changed",row["lead_id"]))
    assert client.get("/workbench/leads483",params={"case_id":cid}).status_code==409
