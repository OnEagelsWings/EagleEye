"""Real server-entry smoke: factory, routes, startup, and health, no mocked app."""
from fastapi.testclient import TestClient
from eagleeye.interfaces.web import server


def test_real_server_entry_initializes_integrated_workspace(tmp_path):
    app = server.create_workspace_app(base_dir=tmp_path)
    assert str(app.version) == str(server.BUILD)
    paths = {route.path for route in app.routes}
    assert "/workbench/checkpoint489" in paths
    assert "/graph464" in paths
    assert "/assistant471/generate" in paths
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["ok"] is True
        assert str(health.json()["build"]) == str(server.BUILD)
