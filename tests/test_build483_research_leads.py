"""Build 483 – authenticated, case-isolated search-lead acceptance."""
import pytest
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app483 import create_workspace_app483
from eagleeye.interfaces.web.research483 import listed
from test_build471_local_ai import workspace
from test_build478_findings import csrf_session

pytestmark=pytest.mark.parametrize("workspace",[create_workspace_app483],indirect=True)

def data(workspace,**patch):
    app,client,user,cid,*_=workspace
    values={
        "case_id":cid,"csrf":csrf_session(workspace),
        "url":"https://example.org/public/notice",
        "title":"Public source for investigation",
        "note":"I found the public article through the manually approved Dork search.",
    }
    values.update(patch)
    return values

def test_real_case_ui_manual_lead_and_no_automatic_evidence(workspace):
    app,client,user,cid,*_=workspace
    assert app.version=="483.0"
    assert client.get("/health").json()["build"]=="483.0"
    page=client.get("/workbench",params={"case_id":cid})
    assert page.status_code==200 and "Recherchefunde sichern" in page.text
    assert "/workbench/leads483?case_id="+cid in page.text
    view=client.get("/workbench/leads483",params={"case_id":cid})
    assert view.status_code==200 and "keinen Originalbeleg" in view.text
    created=client.post("/workbench/leads483",data=data(workspace),follow_redirects=False)
    assert created.status_code==303
    listed_rows=listed(app.state.context,cid)
    assert len(listed_rows)==1 and listed_rows[0]["review_state"]=="unverified_lead"
    assert listed_rows[0]["created_by"]==user["username"]
    assert app.state.context.evidence_claims_dossier_447.case_evidence(cid)==[]
    duplicate=client.post("/workbench/leads483",data=data(workspace),follow_redirects=False)
    assert duplicate.status_code==303
    assert len(listed(app.state.context,cid))==1
    after=client.get("/workbench/leads483",params={"case_id":cid})
    assert after.status_code==200 and "Ungeprüfter Suchhinweis" in after.text
    assert 'rel="noopener noreferrer"' in after.text

def test_lead_requires_csrf_and_public_url(workspace):
    app,client,user,cid,*_=workspace
    assert client.post("/workbench/leads483",data=data(workspace,csrf="invalid")).status_code==403
    for target in ["http://example.org/notice","https://localhost/",
                   "https://127.0.0.1/private","https://foo.internal/x",
                   "https://user:pass@example.org/x","javascript:alert(1)",
                   "https://example.org:8443/private","https://127.1/private","https://0177.0.0.1/private","https://0x7f.0.0.1/private",
                   "https://ｅxample.local/private",
                   "https://ｅxample.internal/private",
                   "https://１２７.０.０.１/private",
                   "https://foo.ｉｎｔｅｒｎａｌ/private",
                   "https://foo.internal．/private",
                   "https://１２７.０.０.１．/private",
                   "https://foo．internal．/private",
                   "https://foo.internal。/private"]:
        response=client.post("/workbench/leads483",
            data=data(workspace,url=target),follow_redirects=False)
        assert response.status_code==422,(target,response.status_code)
    assert listed(app.state.context,cid)==[]

def test_case_separation_and_html_escaping(workspace):
    app,client,user,cid,docid,other,*_=workspace
    assert client.post("/workbench/leads483",
        data=data(workspace,title='<img src=x onerror=alert(1)>'),
        follow_redirects=False).status_code==303
    page=client.get("/workbench/leads483",params={"case_id":cid})
    assert '<img src=x onerror' not in page.text
    assert '&lt;img src=x onerror' in page.text
    foreign=client.get("/workbench/leads483",params={"case_id":other})
    assert foreign.status_code==200 and "Noch keine Treffer" in foreign.text
    assert "onerror=alert" not in foreign.text
    assert client.get("/workbench/leads483",params={"case_id":"wrong"}).status_code==403
    with TestClient(app) as unknown:
        assert unknown.get("/workbench/leads483",params={"case_id":cid}).status_code==401

def test_tampered_lead_is_not_displayed_as_valid(workspace):
    app,client,user,cid,*_=workspace
    assert client.post("/workbench/leads483",data=data(workspace)).status_code==200
    ctx=app.state.context
    ctx.db.execute("UPDATE research_leads_483 SET title=? WHERE case_id=?",
                   ("Changed without audit",cid))
    assert client.get("/workbench/leads483",params={"case_id":cid}).status_code==409
