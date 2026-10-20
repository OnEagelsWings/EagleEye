from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app462 import create_workspace_app462
from eagleeye_pro.version import BUILD


def test_build462_live_case_workbench_persists_entities_and_relationships(tmp_path):
    app = create_workspace_app462(base_dir=tmp_path)
    ctx = app.state.context
    try:
        with TestClient(app) as client:
            response = client.get("/entities462", params={"case_id": "forged"}, follow_redirects=False)
            assert response.status_code == 303
            ctx.team_identity_359.create_initial_admin(
                username="admin462", display_name="QA Admin",
                password="Build462!Password_88"
            )
            fingerprint = hashlib.sha256(b"testclient||testclient").hexdigest()
            session = ctx.team_identity_359.authenticate(
                username="admin462", password="Build462!Password_88",
                client_fingerprint=fingerprint
            )
            identity = ctx.team_identity_359.validate_session(
                session.token, client_fingerprint=fingerprint, touch=False
            )
            case = ctx.team_governance_359.create_case(
                identity=identity, title="Test <Case>", client="QA",
                purpose="Local persistent entity editing", legal_basis="public_data"
            )
            case_id = case["case_id"]
            client.cookies.set(COOKIE, session.token)
            home = client.get("/", params={"case_id": case_id})
            assert home.status_code == 200
            assert "/entities462?" in home.text
            page = client.get("/entities462", params={"case_id": case_id})
            assert page.status_code == 200
            assert "Test &lt;Case&gt;" in page.text
            assert "Test <Case>" not in page.text
            assert client.post("/entities462/create", data={
                "case_id": case_id, "kind": "person", "label": "Alice"
            }, follow_redirects=False).status_code == 303
            assert client.post("/entities462/create", data={
                "case_id": case_id, "kind": "organization", "label": "Example Org"
            }, follow_redirects=False).status_code == 303
            from eagleeye.application.entity_registry461 import EntityRegistry461
            with EntityRegistry461(tmp_path / "entity_registry_462.sqlite3") as store:
                items = store.graph(case_id)["entities"]
            assert len(items) == 2
            saved = client.post("/entities462/link", data={
                "case_id": case_id, "source_id": items[0]["id"],
                "target_id": items[1]["id"], "predicate": "mentioned_with",
                "source_ref": "local:document-123"
            }, follow_redirects=False)
            assert saved.status_code == 303
            page = client.get("/entities462", params={"case_id": case_id})
            assert "mentioned_with" in page.text
            assert "local:document-123" in page.text
            assert "nicht unabhängig verifiziert" in page.text
            assert client.get("/entities462", params={"case_id": "other-case"},
                              follow_redirects=False).status_code == 303
            rejected = client.post("/entities462/create", data={
                "case_id": "other-case", "kind": "person", "label": "Leak"
            }, follow_redirects=False)
            assert rejected.status_code == 303
            blocked = client.post("/entities462/create",
                headers={"Origin": "https://evil.example"}, data={
                "case_id": case_id, "kind": "person", "label": "Attack"
            })
            assert blocked.status_code == 403
        # Persisted records exist after request lifecycle ends.
        with EntityRegistry461(tmp_path / "entity_registry_462.sqlite3") as store:
            graph = store.graph(case_id)
        assert len(graph["entities"]) == 2
        assert len(graph["relations"]) == 1
    finally:
        ctx.close()
