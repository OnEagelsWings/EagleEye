"""Build 489 focused smoke: authenticated, case-scoped and tamper-checked checkpoint."""
import pytest
from fastapi.testclient import TestClient
from eagleeye.interfaces.web.app489 import create_workspace_app489
from test_build471_local_ai import workspace
from test_build488_integration import entities, form
from test_build487_sources import lead
from test_build481_evidence_bridge import document_approved

pytestmark = pytest.mark.parametrize("workspace", [create_workspace_app489], indirect=True)


def test_checkpoint_integrates_real_human_review_and_original(workspace, tmp_path):
    app, client, user, cid, *_ = workspace
    left, right = entities(workspace, tmp_path)
    assert client.post("/workbench/entities488", data=form(workspace, left, right),
                       follow_redirects=False).status_code == 303
    lead_id = lead(workspace)
    document_approved(workspace)
    from test_build487_sources import form as source_form
    assert client.post("/workbench/sources487",
                       data=source_form(workspace, lead_id),
                       follow_redirects=False).status_code == 303
    response = client.get("/workbench/checkpoint489", params={"case_id": cid})
    assert response.status_code == 200
    assert "Auditierte Entitätsentscheidungen (1)" in response.text
    assert "Integritätsgeprüfte Quellenzuordnungen (1)" in response.text
    assert user["username"] in response.text
    assert "belegt keine Entitätsidentität" in response.text
    assert app.state.context.evidence_claims_dossier_447.case_claims(cid) == []


def test_checkpoint_denies_anonymous_and_foreign_case(workspace):
    app, client, user, cid, doc, foreign, *_ = workspace
    response = client.get("/workbench/checkpoint489", params={"case_id": foreign})
    assert response.status_code in (403, 404)
    with TestClient(app) as anon:
        assert anon.get("/workbench/checkpoint489",
                        params={"case_id": cid}).status_code == 401


def test_checkpoint_fails_closed_on_tampered_review(workspace, tmp_path):
    app, client, user, cid, *_ = workspace
    left, right = entities(workspace, tmp_path)
    assert client.post("/workbench/entities488", data=form(workspace, left, right),
                       follow_redirects=False).status_code == 303
    app.state.context.db.execute(
        "UPDATE entity_candidate_reviews_488 SET rationale='forged' WHERE case_id=?",
        (cid,))
    assert client.get("/workbench/checkpoint489",
                      params={"case_id": cid}).status_code == 409
