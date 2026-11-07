"""Build 486 – non-destructive desktop start and safe runtime identity checks."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eagleeye.bootstrap import desktop476
from eagleeye.interfaces.web import server
from eagleeye.interfaces.web.app486 import create_workspace_app486


@pytest.fixture
def isolated_settings(monkeypatch, tmp_path):
    settings = tmp_path / "settings"
    monkeypatch.setenv("EAGLEEYE_SETTINGS_DIR", str(settings))
    monkeypatch.delenv("EAGLEEYE_DATA_DIR", raising=False)
    # Historical Build-486 bootstrap contracts must run under their original
    # build identity; the active 490–500 namespace intentionally forbids
    # implicit reuse of Build-398 data (covered separately by Build-490 tests).
    monkeypatch.setattr(desktop476, "BUILD", "486.0")
    return settings


def test_new_install_without_case_uses_current_bootstrap_not_legacy(tmp_path, isolated_settings):
    workspace = desktop476.resolve_workspace(tmp_path / "fresh-install")
    app = create_workspace_app486(base_dir=workspace)
    try:
        assert app.version == "486.0"
        with TestClient(app) as client:
            assert client.get("/health").json()["build"] == "486.0"
            first = client.get("/new-case", follow_redirects=False)
            assert first.status_code == 303
            assert first.headers["location"] == "/security/bootstrap"
            assert "Legacy Workspace nicht verfügbar" not in first.text
    finally:
        app.state.context.close()


def test_existing_build398_workspace_is_reused_without_touching_data(tmp_path, isolated_settings):
    install = tmp_path / "old-build-398"
    data = install / "data"
    data.mkdir(parents=True)
    legacy = data / "eagleeye.db"
    legacy.write_bytes(b"preserved legacy fixture, no migration permitted")
    before = legacy.read_bytes()
    chosen = desktop476.resolve_workspace(install)
    assert chosen == install.resolve()
    assert legacy.read_bytes() == before
    assert json.loads((isolated_settings / "workspace.json").read_text(encoding="utf-8"))["workspace_directory"] == str(install.resolve())


def test_saved_workdir_survives_new_install_and_unicode_path(tmp_path, isolated_settings):
    existing = tmp_path / "Fälle_ÄÖÜ_日本語"
    (existing / "data").mkdir(parents=True)
    original = existing / "data" / "eagleeye.db"
    original.write_bytes(b"existing cases must not be overwritten")
    desktop476.remember_workspace(existing)
    chosen = desktop476.resolve_workspace(tmp_path / "new-build")
    assert chosen == existing.resolve()
    assert original.read_bytes() == b"existing cases must not be overwritten"


@pytest.mark.parametrize("bad_content", ["not-json", "[]", "{}", '{"workspace_directory": null}'])
def test_broken_settings_fail_closed_without_replacing_case_path(tmp_path, isolated_settings, bad_content):
    isolated_settings.mkdir()
    settings_file = isolated_settings / "workspace.json"
    settings_file.write_text(bad_content, encoding="utf-8")
    with pytest.raises(ValueError, match="Arbeitsordner-Konfiguration"):
        desktop476.resolve_workspace(tmp_path / "fresh")
    assert settings_file.read_text(encoding="utf-8") == bad_content
    assert not (isolated_settings / "workspace").exists()


def test_missing_saved_workdir_fails_closed(tmp_path, isolated_settings):
    isolated_settings.mkdir()
    settings_file = isolated_settings / "workspace.json"
    settings_file.write_text(json.dumps({"workspace_directory": str(tmp_path / "missing")}), encoding="utf-8")
    with pytest.raises(ValueError, match="gespeicherte Arbeitsordner fehlt"):
        desktop476.resolve_workspace(tmp_path / "fresh")
    assert settings_file.is_file()


def test_diagnostics_do_not_persist_or_echo_token_strings(tmp_path, isolated_settings):
    root = tmp_path / "workspace"
    secret = "TOKEN-NEVER-IN-DIAGNOSTICS-123"
    desktop476.write_start_status(root, "start-failed", browser=secret, error_type=secret, port="bad")
    status = (root / "data/runtime_126_0/start-status.json").read_text(encoding="utf-8")
    assert secret not in status
    report = desktop476.diagnostics(root)
    assert secret not in json.dumps(report, ensure_ascii=False)
    assert report["contains_credentials"] is False


class _Response:
    def __init__(self, *, build="486.0", instance=""):
        self.headers = {"X-EagleEye-Instance": instance}
        self.payload = json.dumps({"ok": True, "build": build}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size=-1):
        return self.payload[:size]


def test_running_server_requires_matching_workspace_instance(tmp_path, monkeypatch):
    # Validate the historical 486 contract against its own build identity.
    # The active server correctly rejects older builds by default.
    monkeypatch.setattr(server, "BUILD", "486.0")
    root = tmp_path / "workspace"
    nonce = "a" * 48
    server._write_runtime(root, host="127.0.0.1", port=8765, instance_id=nonce)

    class _Opener:
        def __init__(self, instance, build="486.0"):
            self.instance = instance
            self.build = build

        def open(self, url, timeout):
            assert url == "http://127.0.0.1:8765/health"
            assert timeout <= 1
            return _Response(build=self.build, instance=self.instance)

    monkeypatch.setattr(server.urllib.request, "build_opener", lambda *_: _Opener("wrong-instance"))
    assert server._read_running_workspace(root) is None
    monkeypatch.setattr(server.urllib.request, "build_opener", lambda *_: _Opener(nonce))
    assert server._read_running_workspace(root)["port"] == 8765
    monkeypatch.setattr(server.urllib.request, "build_opener", lambda *_: _Opener("", "485.0"))
    assert server._read_running_workspace(root) is None
    assert server._read_running_workspace(root, accept_other_build=True)["build"] == "485.0"


def test_browser_readiness_does_not_trust_unrelated_local_server(monkeypatch):
    monkeypatch.setattr(server, "BUILD", "486.0")
    class _Opener:
        def __init__(self, instance):
            self.instance = instance

        def open(self, url, timeout):
            assert url == "http://127.0.0.1:8765/health"
            return _Response(instance=self.instance)

    monkeypatch.setattr(server.urllib.request, "build_opener", lambda *_: _Opener("unrelated"))
    assert server._health_ready(8765, expected_instance="expected") is False
    monkeypatch.setattr(server.urllib.request, "build_opener", lambda *_: _Opener("expected"))
    assert server._health_ready(8765, expected_instance="expected") is True


def test_parallel_workspace_lock_does_not_allow_second_writer(tmp_path):
    from eagleeye.bootstrap.runtime_lock import workspace_runtime_lock
    with workspace_runtime_lock(tmp_path, timeout=0):
        with pytest.raises(RuntimeError, match="EagleEye läuft noch"):
            with workspace_runtime_lock(tmp_path, timeout=0):
                pytest.fail("second writer entered the same workspace")


def test_unresponsive_loopback_server_times_out_without_token(monkeypatch, tmp_path):
    root = tmp_path / "workspace"
    server._write_runtime(root, host="127.0.0.1", port=8765, instance_id="a" * 48)

    class _TimeoutOpener:
        def open(self, url, timeout):
            assert timeout <= 0.6
            raise TimeoutError("loopback socket timed out")

    monkeypatch.setattr(server.urllib.request, "build_opener", lambda *_: _TimeoutOpener())
    assert server._read_running_workspace(root) is None


def test_real_build485_case_remains_visible_after_build486_workspace_upgrade(tmp_path, isolated_settings):
    from eagleeye.interfaces.web.app485 import create_workspace_app485

    old_root = tmp_path / "previous-build-workspace"
    previous = create_workspace_app485(base_dir=old_root)
    try:
        old = previous.state.context
        old.team_identity_359.create_initial_admin(
            username="upgradeqa", display_name="Upgrade QA",
            password="Distinct!Upgrade-Test-486")
        issued = old.team_identity_359.authenticate(
            username="upgradeqa", password="Distinct!Upgrade-Test-486",
            client_fingerprint="upgrade-qa")
        actor = old.team_identity_359.validate_session(
            issued.token, client_fingerprint="upgrade-qa", touch=False)
        case = old.team_governance_359.create_case(
            identity=actor, title="Preserved existing investigation",
            client="QA", purpose="Synthetic upgrade preservation",
            legal_basis="public_data")
        case_id = case["case_id"]
    finally:
        previous.state.context.close()

    desktop476.remember_workspace(old_root)
    restored_root = desktop476.resolve_workspace(tmp_path / "new-build-installation")
    assert restored_root == old_root.resolve()
    upgraded = create_workspace_app486(base_dir=restored_root)
    try:
        new = upgraded.state.context
        issued = new.team_identity_359.authenticate(
            username="upgradeqa", password="Distinct!Upgrade-Test-486",
            client_fingerprint="upgrade-qa-new")
        actor = new.team_identity_359.validate_session(
            issued.token, client_fingerprint="upgrade-qa-new", touch=False)
        assert case_id in {
            str(row["case_id"])
            for row in new.team_governance_359.visible_cases(actor)
        }
    finally:
        upgraded.state.context.close()
