"""Build-500 offline installer must emit a persistent pip log and avoid redundant work."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess


def test_build500_offline_pip_emits_log_and_uses_low_overhead_flags(tmp_path, monkeypatch):
    installer_path = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
    spec = spec_from_file_location("build500_installer_under_test", installer_path)
    assert spec and spec.loader
    installer = module_from_spec(spec)
    spec.loader.exec_module(installer)
    monkeypatch.setattr(installer, "_verify_wheelhouse", lambda _root: None)
    observed = {}

    def run(command, *, cwd, check):
        observed.update(command=command, cwd=cwd, check=check)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(installer.subprocess, "run", run)
    python = installer._runtime_python(tmp_path)
    installer._install(tmp_path, python, offline=True)
    args = observed["command"]
    assert args[:3] == [str(python), "-m", "pip"]
    assert "--log" in args
    assert Path(args[args.index("--log") + 1]) == tmp_path / ".eagleeye-runtime-500" / "install-pip-500.log"
    assert "--no-cache-dir" in args
    assert "--no-compile" in args
    assert "--no-index" in args
    assert observed["cwd"] == str(tmp_path)
    assert observed["check"] is True
    assert (tmp_path / ".eagleeye-runtime-500").is_dir()


def test_build500_installer_rejects_linked_log(tmp_path, monkeypatch):
    installer_path = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
    spec = spec_from_file_location("build500_installer_link_guard", installer_path)
    assert spec and spec.loader
    installer = module_from_spec(spec)
    spec.loader.exec_module(installer)
    monkeypatch.setattr(installer, "_verify_wheelhouse", lambda _root: None)
    runtime = tmp_path / ".eagleeye-runtime-500"
    runtime.mkdir()
    external = tmp_path / "external.log"
    external.write_text("do not overwrite", encoding="utf-8")
    try:
        (runtime / "install-pip-500.log").symlink_to(external)
    except (OSError, NotImplementedError):
        import pytest
        pytest.skip("symlink not permitted in current environment")
    import pytest
    with pytest.raises(RuntimeError, match=r"Linked installer (?:log|file path)"):
        installer._install(tmp_path, installer._runtime_python(tmp_path), offline=True)
    assert external.read_text(encoding="utf-8") == "do not overwrite"


def test_build500_installer_rejects_linked_runtime_before_pip(tmp_path, monkeypatch):
    import pytest
    installer_path = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
    spec = spec_from_file_location("build500_installer_runtime_guard", installer_path)
    assert spec and spec.loader
    installer = module_from_spec(spec)
    spec.loader.exec_module(installer)
    external = tmp_path / "old-install"
    external.mkdir()
    runtime = tmp_path / installer.RUNTIME_DIR
    try:
        runtime.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink not permitted")
    called = []
    monkeypatch.setattr(installer.subprocess, "run", lambda *a, **kw: called.append(a))
    with pytest.raises(RuntimeError, match="runtime path"):
        installer._install(tmp_path, installer._runtime_python(tmp_path), quiet=True)
    assert not called
    assert list(external.iterdir()) == []



def test_build500_installer_rejects_linked_installation_root(tmp_path, monkeypatch):
    import pytest
    installer_path = Path(__file__).resolve().parents[1] / "INSTALL_EAGLEEYE_500.py"
    spec = spec_from_file_location("build500_installer_root_guard", installer_path)
    assert spec and spec.loader
    installer = module_from_spec(spec)
    spec.loader.exec_module(installer)
    real_root = tmp_path / "real-build500"
    real_root.mkdir()
    linked_root = tmp_path / "linked-build500"
    try:
        linked_root.symlink_to(real_root, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink not permitted")
    calls = []
    monkeypatch.setattr(installer.subprocess, "run", lambda *a, **kw: calls.append(a))
    with pytest.raises(RuntimeError, match="Linked or unexpected installer runtime"):
        installer._install(linked_root, installer._runtime_python(linked_root), quiet=True)
    assert not calls
    assert list(real_root.iterdir()) == []
