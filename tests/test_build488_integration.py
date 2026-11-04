"""Build 488: real authenticated entity review end-to-end smoke."""
import pytest
from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app488 import create_workspace_app488
from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye.application.build488.reviews import reviews_for_case
from test_build471_local_ai import workspace
from test_build478_findings import csrf_session

pytestmark = pytest.mark.parametrize("workspace", [create_workspace_app488], indirect=True)


def entities(workspace, tmp_path):
    app, client, user, cid, _doc, foreign, *_ = workspace
    with EntityRegistry461(tmp_path / "entity_registry_462.sqlite3") as store:
        first = store.create_entity(case_id=cid, kind="person", label="Müller")
        second = store.create_entity(case_id=cid, kind="person", label="Müller")
        store.create_entity(case_id=foreign, kind="person", label="Müller")
    return first["id"], second["id"]


def form(workspace, left, right, **changes):
    _app, _client, _user, cid, *_ = workspace
    data = {"case_id": cid, "csrf": csrf_session(workspace),
            "left_entity_id": left, "right_entity_id": right,
            "decision": "needs_evidence",
            "rationale": "These matching names require independent source verification.",
            "confirm": "yes"}
    data.update(changes)
    return data


def test_review_persists_and_is_visible_without_merge(workspace, tmp_path):
    app, client, user, cid, *_ = workspace
    left, right = entities(workspace, tmp_path)
    response = client.get("/workbench/entities488", params={"case_id": cid})
    assert response.status_code == 200
    assert "Müller" in response.text
    data = form(workspace, left, right)
    for _ in range(2):
        assert client.post("/workbench/entities488", data=data, follow_redirects=False).status_code == 303
    rows = reviews_for_case(app.state.context, user, cid)
    assert len(rows) == 1 and rows[0]["decision"] == "needs_evidence"
    assert rows[0]["reviewed_by"] == user["username"]
    assert "needs_evidence" in client.get("/workbench/entities488", params={"case_id": cid}).text
    with EntityRegistry461(tmp_path / "entity_registry_462.sqlite3") as store:
        assert len(store.graph(cid)["entities"]) == 2
        assert store.graph(cid)["relations"] == []


@pytest.mark.parametrize("change,headers,expected", [
    ({"csrf": "wrong"}, {}, 403),
    ({}, {"Origin": "https://attacker.example"}, 403),
    ({"confirm": ""}, {}, 422),
    ({"decision": "identity_confirmed"}, {}, 422),
    ({"left_entity_id": "forged"}, {}, 409),
])
def test_rejected_posts_do_not_create_reviews(workspace, tmp_path, change, headers, expected):
    app, client, user, cid, *_ = workspace
    left, right = entities(workspace, tmp_path)
    response = client.post("/workbench/entities488",
                           data=form(workspace, left, right, **change),
                           headers=headers, follow_redirects=False)
    assert response.status_code == expected, response.text
    assert reviews_for_case(app.state.context, user, cid) == []


def test_anonymous_and_foreign_case_denied(workspace, tmp_path):
    app, client, user, cid, _doc, foreign, *_ = workspace
    left, right = entities(workspace, tmp_path)
    # Generate the authenticated CSRF form before opening a second TestClient:
    # its lifespan shutdown closes the shared application context.
    foreign_form = form(workspace, left, right, case_id=foreign)
    assert client.post("/workbench/entities488",
                       data=foreign_form,
                       follow_redirects=False).status_code in (403, 409)
    with TestClient(app) as anon:
        assert anon.get("/workbench/entities488", params={"case_id": cid}).status_code == 401


def test_tampered_review_fails_closed(workspace, tmp_path):
    app, client, user, cid, *_ = workspace
    left, right = entities(workspace, tmp_path)
    assert client.post("/workbench/entities488", data=form(workspace, left, right),
                       follow_redirects=False).status_code == 303
    app.state.context.db.execute(
        "UPDATE entity_candidate_reviews_488 SET rationale='forged' WHERE case_id=?", (cid,))
    assert client.get("/workbench/entities488", params={"case_id": cid}).status_code == 409


def test_historical_review_remains_visible_after_candidate_disappears(workspace, tmp_path, monkeypatch):
    """An old analyst decision must remain visible even if matching rules change."""
    app, client, user, cid, *_ = workspace
    left, right = entities(workspace, tmp_path)
    assert client.post("/workbench/entities488", data=form(workspace, left, right),
                       follow_redirects=False).status_code == 303
    import eagleeye.interfaces.web.entities488 as view
    monkeypatch.setattr(view, "current_candidates", lambda ctx, base_dir, case_id: [])
    page = client.get("/workbench/entities488", params={"case_id": cid})
    assert page.status_code == 200
    assert "Historische Prüfentscheidung" in page.text
    assert "needs_evidence" in page.text
    assert left in page.text and right in page.text
    assert "erneut prüfen" in page.text
    # Stale candidates must not be writable merely because an earlier review exists.
    stale = client.post("/workbench/entities488", data=form(workspace, left, right),
                        follow_redirects=False)
    assert stale.status_code == 409
    assert len(reviews_for_case(app.state.context, user, cid)) == 1


def test_review_cannot_be_silently_rewritten_or_injected(workspace, tmp_path):
    """Immutable analyst decision; HTML in a rationale is displayed as text."""
    app, client, user, cid, *_ = workspace
    left, right = entities(workspace, tmp_path)
    rationale = "Independent source needed: <script>alert('x')</script>"
    first = client.post("/workbench/entities488",
                        data=form(workspace, left, right, rationale=rationale),
                        follow_redirects=False)
    assert first.status_code == 303, first.text
    displayed = client.get("/workbench/entities488", params={"case_id": cid})
    assert displayed.status_code == 200
    assert "<script>alert('x')</script>" not in displayed.text
    assert "&lt;script&gt;" in displayed.text
    # A forged change cannot replace a prior audited review, even if the
    # candidate matcher still returns the pair.
    changed = client.post("/workbench/entities488",
                          data=form(workspace, left, right,
                                    decision="not_same",
                                    rationale="This is a new and conflicting analyst conclusion."),
                          follow_redirects=False)
    assert changed.status_code == 409
    rows = reviews_for_case(app.state.context, user, cid)
    assert len(rows) == 1
    assert rows[0]["decision"] == "needs_evidence"
    assert rows[0]["rationale"] == rationale
