"""Current Build 500 source and application contract, without older build suites."""
from pathlib import Path
import ast
import json
import tomllib
import pytest
from eagleeye.interfaces.web.app500 import create_workspace_app500
from test_build471_local_ai import workspace

ROOT=Path(__file__).resolve().parents[1]
ws=pytest.mark.parametrize("workspace",[create_workspace_app500],indirect=True)

def test_release_package_contract():
    meta=tomllib.loads((ROOT/"pyproject.toml").read_text(encoding="utf-8"))
    assert meta["project"]["version"]=="500.0.0"
    version=ast.parse((ROOT/"eagleeye_pro/version.py").read_text(encoding="utf-8"))
    build=next(node.value.value for node in version.body
               if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="BUILD" for t in node.targets))
    assert build=="500.0"
    installer=(ROOT/"INSTALL_EAGLEEYE_500.py").read_text(encoding="utf-8")
    assert 'PACKAGE_VERSION = "500.0.0"' in installer
    assert 'RUNTIME_DIR = ".eagleeye-runtime-500"' in installer
    assert 'RECEIPT = "install-receipt-500.json"' in installer
    assert "no-index" in installer and "wheelhouse" in installer
    for suffix in ("bat","sh"):
        start=(ROOT/f"START_EAGLEEYE_PRO.{suffix}").read_text(encoding="utf-8")
        assert "INSTALL_EAGLEEYE_500.py" in start
        assert ".eagleeye-runtime-500" in start
        assert "EAGLEEYE_DATA_DIR=" not in start

@ws
def test_app500_has_integrated_routes_and_release_hold(workspace):
    app,client,user,cid,*_=workspace
    assert str(app.version)=="500.0"
    paths={route.path for route in app.routes}
    for route in ("/workbench/plan496","/workbench/run497","/workbench/ai498",
                  "/workbench/transfer499","/workbench/release500","/workbench/intel/web"):
        assert route in paths
    r=client.get("/workbench/release500",params={"case_id":cid})
    assert r.status_code==200
    assert "Release Candidate" in r.text and "OFFEN" in r.text
    assert client.get("/workbench/release500",params={"case_id":"unknown"}).status_code==403


def test_offline_wheelhouse_rejects_unverified_archive(tmp_path):
    import hashlib
    import importlib.util

    spec = importlib.util.spec_from_file_location("build500_installer", ROOT / "INSTALL_EAGLEEYE_500.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel_name = "eagleeye_personosint_pro-500.0.0-py3-none-any.whl"
    payload = b"sealed-wheel-fixture"
    (wheelhouse / wheel_name).write_bytes(payload)
    (wheelhouse / "MANIFEST-SHA256.json").write_text(
        json.dumps({wheel_name: hashlib.sha256(payload).hexdigest()}), encoding="utf-8"
    )
    installer._verify_wheelhouse(tmp_path)
    (wheelhouse / "unverified-500.0.tar.gz").write_bytes(b"unsealed source archive")
    with pytest.raises(RuntimeError, match="unverified"):
        installer._verify_wheelhouse(tmp_path)


def test_linux_wheelhouse_uses_verified_offline_install(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("build500_installer", ROOT / "INSTALL_EAGLEEYE_500.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    (tmp_path / "wheelhouse").mkdir()
    verified = []
    commands = []
    monkeypatch.setattr(installer, "_verify_wheelhouse", lambda root: verified.append(root))
    monkeypatch.setattr(installer.subprocess, "run", lambda command, **kwargs: commands.append(command))
    installer._install(tmp_path, tmp_path / "python", quiet=True)
    assert verified == [tmp_path]
    assert len(commands) == 1
    assert "--force-reinstall" in commands[0]
    assert "--no-index" in commands[0]
    assert "--find-links" in commands[0]
    assert "eagleeye-personosint-pro==500.0.0" in commands[0]


def test_build500_default_workspace_isolated_from_previous_release(tmp_path, monkeypatch):
    from eagleeye.bootstrap import desktop476, paths
    monkeypatch.delenv("EAGLEEYE_SETTINGS_DIR", raising=False)
    monkeypatch.delenv("EAGLEEYE_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "profile"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "profile"))
    previous = tmp_path / "profile" / "EagleEye-490"
    previous.mkdir(parents=True)
    saved = previous / "workspace.json"
    saved.write_text(json.dumps({"workspace_directory": str(previous / "workspace")}), encoding="utf-8")
    before = saved.read_bytes()
    install = tmp_path / "program"
    install.mkdir()
    expected = tmp_path / "profile" / "EagleEye-500" / "workspace"
    assert desktop476.resolve_workspace(install) == expected
    assert paths.default_runtime_root() == expected
    assert desktop476.resolve_workspace(install) == expected
    assert saved.read_bytes() == before
    assert not (previous / "workspace").exists()


def test_build500_offline_restore_preserves_data_and_revokes_login(tmp_path):
    """Exercise the current app, real SQLite backup and fresh restore directory."""
    import hashlib
    import sqlite3
    from contextlib import closing
    from fastapi.testclient import TestClient
    from eagleeye.bootstrap.recovery479 import create_backup, restore_backup

    source = tmp_path / "Arbeitsbereich-Übung"
    source.mkdir()
    app = create_workspace_app500(base_dir=source)
    password = "a-Long-Test-Password2026!"
    try:
        with TestClient(app) as client:
            launch = (source / "data/security_364/local_session_token").read_text().strip()
            assert client.get("/security/start", params={"token": launch}).status_code == 200
            assert client.post("/security/bootstrap", data={
                "username": "pilotadmin", "display_name": "Pilot Admin",
                "password": password}).status_code == 200
            assert client.post("/security/login", data={
                "username": "pilotadmin", "password": password},
                follow_redirects=False).status_code == 303
            token = client.cookies.get("ee_auth_session")
            assert token
    finally:
        app.state.context.close()

    db = source / "data/eagleeye.db"
    with closing(sqlite3.connect(db)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM phase15_team_sessions WHERE revoked=0").fetchone()[0] > 0
        connection.execute("CREATE TABLE build500_restore_marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO build500_restore_marker VALUES (?)", ("Übung",))
        connection.commit()
    original = source / "data" / "restore-test-original.txt"
    original.write_bytes(b"Build 500 original evidence fixture")
    digest = hashlib.sha256(original.read_bytes()).hexdigest()
    archive = tmp_path / "backup.zip"
    backup = create_backup(source, archive)
    assert backup["build"] == "500.0"
    assert backup["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    target = tmp_path / "Wiederherstellung"
    receipt = restore_backup(archive, target)
    assert receipt["sessions_revoked"] > 0
    assert receipt["existing_workspace_overwritten"] is False
    assert not (target / "data/security_364/local_session_token").exists()
    assert hashlib.sha256((target / "data/restore-test-original.txt").read_bytes()).hexdigest() == digest
    with closing(sqlite3.connect(target / "data/eagleeye.db")) as connection:
        assert connection.execute("SELECT value FROM build500_restore_marker").fetchone() == ("Übung",)
        assert connection.execute("SELECT COUNT(*) FROM phase15_team_sessions WHERE revoked=0").fetchone() == (0,)
    with closing(sqlite3.connect(db)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM phase15_team_sessions WHERE revoked=0").fetchone()[0] > 0
    restored = create_workspace_app500(base_dir=target)
    try:
        with TestClient(restored) as client:
            client.cookies.set("ee_auth_session", token)
            assert client.get("/", follow_redirects=False).status_code in (302, 303, 401, 403)
            client.cookies.clear()
            launch = (target / "data/security_364/local_session_token").read_text().strip()
            assert client.get("/security/start", params={"token": launch}).status_code == 200
            assert client.post("/security/login", data={
                "username": "pilotadmin", "password": password},
                follow_redirects=False).status_code == 303
    finally:
        restored.state.context.close()


@pytest.mark.parametrize("staged", [False, True])
def test_release_pack_rejects_dirty_tracked_source(tmp_path, staged):
    import importlib.util
    import subprocess

    spec = importlib.util.spec_from_file_location("pack500", ROOT / "tools/pack500.py")
    pack = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pack)
    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True,
                       capture_output=True)
    git("init")
    git("config", "user.name", "Synthetic Test")
    git("config", "user.email", "test@example.invalid")
    tracked = tmp_path / "source.py"
    tracked.write_text("original", encoding="utf-8")
    git("add", "source.py")
    git("commit", "-m", "fixture")
    tracked.write_text("changed", encoding="utf-8")
    if staged:
        git("add", "source.py")
    out = tmp_path / "candidate.zip"
    with pytest.raises(ValueError, match="clean tracked source"):
        pack.build(tmp_path, out)
    assert not out.exists()


def test_build500_receipt_fingerprint_changes_with_wheel_manifest(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("build500_installer", ROOT / "INSTALL_EAGLEEYE_500.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    folder = tmp_path / "wheelhouse"
    folder.mkdir()
    manifest = folder / "MANIFEST-SHA256.json"
    manifest.write_text('{"fixture.whl":"' + "a" * 64 + '"}', encoding="utf-8")
    before = installer._source_fingerprint(tmp_path)
    manifest.write_text('{"fixture.whl":"' + "b" * 64 + '"}', encoding="utf-8")
    assert installer._source_fingerprint(tmp_path) != before


def test_release_pack_refuses_tracked_symlink_and_missing_source(tmp_path):
    """No silent omission of tracked source, including a link outside the release tree."""
    import importlib.util
    import os
    import subprocess

    spec = importlib.util.spec_from_file_location("pack500", ROOT / "tools/pack500.py")
    pack = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pack)

    def git(*args):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    git("init")
    git("config", "user.name", "Synthetic Test")
    git("config", "user.email", "test@example.invalid")
    tracked = tmp_path / "source.py"
    tracked.write_text("original", encoding="utf-8")
    git("add", "source.py")
    git("commit", "-m", "fixture")
    tracked.unlink()
    with pytest.raises(ValueError, match="missing tracked source"):
        pack.build(tmp_path, tmp_path / "missing.zip")

    outside = tmp_path.parent / (tmp_path.name + "-outside.txt")
    outside.write_text("not part of release", encoding="utf-8")
    try:
        os.symlink(outside, tracked)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable on this host")
    with pytest.raises(ValueError, match="tracked source symlink"):
        pack.build(tmp_path, tmp_path / "linked.zip")
    assert not (tmp_path / "linked.zip").exists()


def test_build500_runtime_probe_rejects_linked_installation_root(tmp_path):
    """A symlinked release root must not reuse another installation runtime."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("build500_installer", ROOT / "INSTALL_EAGLEEYE_500.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    actual = tmp_path / "release-original"
    actual.mkdir()
    alias = tmp_path / "release-alias"
    try:
        alias.symlink_to(actual, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable on this host")
    assert installer._runtime_path_linked(alias)
    assert installer._probe(alias)["reason"] == "runtime_link_forbidden"
    with pytest.raises(RuntimeError, match="Linked runtime paths"):
        installer._ensure_runtime(alias, quiet=True)
    assert not (actual / installer.RUNTIME_DIR).exists()
