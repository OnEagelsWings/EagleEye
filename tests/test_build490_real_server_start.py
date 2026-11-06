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


def test_independent_workspace_runtime_paths_do_not_touch_legacy_install(tmp_path):
    """New-install runtime metadata must be rooted in its own workspace."""
    import json

    fresh = tmp_path / "eagleeye-internal-1"
    legacy = tmp_path / "eagleeye-build-398"
    legacy_runtime = server._runtime_path(legacy)
    legacy_runtime.parent.mkdir(parents=True)
    legacy_runtime.write_text('{"legacy": true}', encoding="utf-8")

    fresh_runtime = server._write_runtime(
        fresh, host="127.0.0.1", port=8765, instance_id="synthetic-test-instance"
    )
    assert fresh_runtime == server._runtime_path(fresh)
    assert fresh_runtime != legacy_runtime
    assert json.loads(fresh_runtime.read_text(encoding="utf-8"))["instance_id"] == "synthetic-test-instance"
    assert legacy_runtime.read_text(encoding="utf-8") == '{"legacy": true}'
