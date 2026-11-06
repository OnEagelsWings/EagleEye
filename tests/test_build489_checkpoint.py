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
    assert "/documents458?case_id=" in response.text
    assert "document_id=" in response.text
    assert "<th>Begründung</th>" in response.text
    assert "These matching names require independent source verification." in response.text
    assert app.state.context.evidence_claims_dossier_447.case_claims(cid) == []


def test_checkpoint_denies_anonymous_and_foreign_case(workspace):
    app, client, admin, cid, doc, foreign, *_ = workspace
    # The fixture's initial admin created BOTH cases and legitimately has
    # access to both. Test cross-case denial with a genuinely restricted user.
    ctx = app.state.context
    restricted = ctx.team_governance_359.create_user(
        identity=admin, username="restricted489",
        display_name="Restricted checkpoint reviewer",
        global_role="reviewer", password="Independent!Review_2026",
    )
    ctx.team_governance_359.assign_case_role(
        identity=admin, case_id=cid, username=restricted["username"],
        case_role="reviewer", notes="Only the primary synthetic case",
    )
    import hashlib
    from eagleeye.interfaces.web.app448 import COOKIE
    fingerprint = hashlib.sha256(b"testclient||testclient").hexdigest()
    session = ctx.team_identity_359.authenticate(
        username=restricted["username"],
        password="Independent!Review_2026",
        client_fingerprint=fingerprint,
    )
    with TestClient(app) as limited:
        limited.cookies.set(COOKIE, session.token)
        assert limited.get("/workbench/checkpoint489",
                           params={"case_id": cid}).status_code == 200
        response = limited.get("/workbench/checkpoint489",
                               params={"case_id": foreign})
        assert response.status_code in (403, 404)
    # Reuse the active lifespan: nested TestClient shutdown closes shared case services.
    original_token = client.cookies.get(COOKIE)
    client.cookies.delete(COOKIE)
    try:
        assert client.get("/workbench/checkpoint489",
                          params={"case_id": cid}).status_code == 401
    finally:
        if original_token is not None:
            client.cookies.set(COOKIE, original_token)


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
