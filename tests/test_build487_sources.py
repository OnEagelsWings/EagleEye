"""Build 487: real original, attribution, idempotency, ACL, CSRF and tamper tests."""
import pytest
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app487 import create_workspace_app487
from eagleeye.interfaces.web.sources487 import source_links
from test_build471_local_ai import workspace
from test_build478_findings import csrf_session
from test_build481_evidence_bridge import document_approved
from test_build483_research_leads import data as lead_data

pytestmark = pytest.mark.parametrize("workspace", [create_workspace_app487], indirect=True)

def form(workspace, lead_id, **patch):
    app, client, user, cid, doc_id, *_ = workspace
    data = {"case_id": cid, "csrf": csrf_session(workspace), "lead_id": lead_id,
            "document_id": doc_id, "rationale":
            "I checked the original and manually associated it with this public search lead.",
            "confirm": "yes"}
    data.update(patch)
    return data

def lead(workspace):
    app, client, user, cid, *_ = workspace
    assert client.post("/workbench/leads483", data=lead_data(workspace),
                       follow_redirects=False).status_code == 303
    from eagleeye.interfaces.web.research483 import listed
    return listed(app.state.context, cid)[0]["lead_id"]

def test_real_manual_source_action_without_evidence(workspace):
    app, client, user, cid, doc_id, *_ = workspace
    assert app.version == "487.0"
    assert client.get("/health").json()["build"] == "487.0"
    assert "/workbench/sources487?" in client.get("/workbench", params={"case_id": cid}).text
    lead_id = lead(workspace)
    assert client.post("/workbench/sources487", data=form(workspace, lead_id),
                       follow_redirects=False).status_code == 409
    document_approved(workspace)
    for _ in range(2):
        assert client.post("/workbench/sources487", data=form(workspace, lead_id),
                           follow_redirects=False).status_code == 303
    links = source_links(app.state.context, user, cid)
    assert len(links) == 1 and links[0]["document_id"] == doc_id
    assert links[0]["created_by"] == user["username"]
    assert len(links[0]["original_sha256"]) == 64
    assert app.state.context.evidence_claims_dossier_447.case_evidence(cid) == []
    assert app.state.context.evidence_claims_dossier_447.case_claims(cid) == []
    page = client.get("/workbench/sources487", params={"case_id": cid})
    assert page.status_code == 200 and "nicht bewiesen" in page.text

def test_csrf_origin_foreign_document_and_anonymous_denied(workspace):
    app, client, user, cid, doc_id, foreign, foreign_doc = workspace
    lead_id = lead(workspace)
    document_approved(workspace)
    for patch, headers, expected in [
        ({"csrf": "wrong"}, {}, 403),
        ({"confirm": ""}, {}, 422),
        ({}, {"Origin": "https://attacker.example"}, 403),
        ({"document_id": foreign_doc}, {}, 403),
        ({"lead_id": "not-a-case-lead"}, {}, 404),
    ]:
        response = client.post("/workbench/sources487", data=form(workspace, lead_id, **patch),
                               headers=headers, follow_redirects=False)
        assert response.status_code == expected, (patch, response.status_code)
    assert source_links(app.state.context, user, cid) == []
    with TestClient(app) as anonymous:
        assert anonymous.get("/workbench/sources487", params={"case_id": cid}).status_code == 401

def test_original_and_association_tampering_block_display(workspace):
    app, client, user, cid, doc_id, *_ = workspace
    lead_id = lead(workspace)
    document_approved(workspace)
    assert client.post("/workbench/sources487", data=form(workspace, lead_id),
                       follow_redirects=False).status_code == 303
    ctx = app.state.context
    doc = ctx.document_intelligence_458._document(doc_id)
    path = ctx.document_intelligence_458.root / doc["stored_relpath"]
    original = path.read_bytes()
    path.write_bytes(b"tampered")
    assert client.get("/workbench/sources487", params={"case_id": cid}).status_code == 409
    path.write_bytes(original)
    ctx.db.execute("UPDATE lead_original_links_487 SET rationale=? WHERE case_id=?",
                   ("forged", cid))
    assert client.get("/workbench/sources487", params={"case_id": cid}).status_code == 409
