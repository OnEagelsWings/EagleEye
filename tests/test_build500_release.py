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
    assert "--no-index" in commands[0]
    assert "--find-links" in commands[0]
    assert "eagleeye-personosint-pro==500.0.0" in commands[0]
