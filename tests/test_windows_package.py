"""Windows package: lock file, stage assembly and Start-menu launcher (what can be checked without Windows)."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

from eagleeye.bootstrap import windows_start

ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging" / "windows"


def _load_build_stage():
    spec = importlib.util.spec_from_file_location("build_stage", PACKAGING / "build_stage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _names(lines):
    return {re.split(r"[<>=!~\[; ]", line.strip(), maxsplit=1)[0].lower().replace("_", "-")
            for line in lines if line.strip() and not line.strip().startswith(("#", "-"))}


def test_lock_covers_every_runtime_dependency_with_hashes():
    import tomllib

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    wanted = (PACKAGING / "requirements-windows.in").read_text(encoding="utf-8").splitlines()
    fallakte = [line for line in wanted[wanted.index("# Fallakte (aus pyproject.toml)") + 1:]
                if line and not line.startswith("#")][:len(project)]
    assert sorted(fallakte) == sorted(project), "requirements-windows.in must list exactly the pyproject dependencies"
    personosint = (ROOT / "PersonOSINT" / "requirements.txt").read_text(encoding="utf-8").splitlines()
    runtime_names = _names(project) | (_names(personosint) - {"pytest", "httpx"})
    lock = (PACKAGING / "requirements-windows.lock").read_text(encoding="utf-8")
    pinned = {m.group(1).lower().replace("_", "-") for m in re.finditer(r"^([A-Za-z0-9_.\-]+)==", lock, re.M)}
    assert runtime_names <= pinned, sorted(runtime_names - pinned)
    blocks = re.split(r"\n(?=[A-Za-z0-9])", lock.strip())
    assert all("--hash=sha256:" in block for block in blocks), "every pinned package needs a SHA-256 hash"
    assert "pytest" not in pinned and "httpx" not in pinned, "test tools are not shipped"


def test_runtime_import_path_stays_inside_the_program_folder():
    stage = _load_build_stage()
    text = stage.pth_text((3, 14))
    assert text.splitlines() == ["python314.zip", ".", "Lib", r"Lib\site-packages", "import site"]
    assert not any(":" in line or line.startswith(("\\", "/", "..")) for line in text.splitlines())


def test_stage_contains_tools_docs_and_migrations_but_no_tests(tmp_path):
    stage = _load_build_stage()
    (tmp_path / "runtime" / "Lib" / "site-packages" / "bin").mkdir(parents=True)
    stage.assemble(tmp_path, ROOT)
    bridge = tmp_path / "tools" / "research_exchange"
    shipped = {p.name for p in bridge.iterdir()}
    assert not any(name.startswith("test_") for name in shipped)
    # every module the desktop UI and the local setup import must be shipped
    import ast

    local = {p.stem for p in (ROOT / "tools" / "research_exchange").glob("*.py")}
    needed, todo = set(), ["desktop_ui", "install_local"]
    while todo:
        name = todo.pop()
        if name in needed:
            continue
        needed.add(name)
        for node in ast.walk(ast.parse((ROOT / "tools" / "research_exchange" / f"{name}.py").read_text(encoding="utf-8"))):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            todo += [m.split(".")[0] for m in mods if m.split(".")[0] in local]
    assert {f"{n}.py" for n in needed} <= shipped
    for name in ("bridge.py", "engine.py", "security_tools.py", "local.html"):
        assert (tmp_path / "tools" / "analysis" / name).is_file()
    assert (tmp_path / "tools" / "quellen_pruefen_fallakte.py").is_file()
    assert (tmp_path / "runtime" / "alembic_104_1" / "env.py").is_file()
    assert (tmp_path / "runtime" / "alembic_104_1" / "versions").is_dir()
    assert not (tmp_path / "runtime" / "Lib" / "site-packages" / "bin").exists()
    for doc in ("LIESMICH.md", "BETRIEBSHANDBUCH_BUERO.md", "VAULT.md", "INSTALLATION_WINDOWS.md"):
        assert (tmp_path / "docs" / doc).is_file()
    manifest = stage.write_manifest(tmp_path, version="500.0.1", commit="abc", embed_sha256="0" * 64, python="3.14.10")
    import json

    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["files"]["docs/LIESMICH.md"] and data["packages"]["fastapi"]
    assert "MANIFEST-SHA256.json" not in data["files"]


def test_every_entry_has_a_start_menu_shortcut_and_the_workflow_checks_them():
    iss = (PACKAGING / "EagleEye.iss").read_text(encoding="utf-8")
    in_menu = set(re.findall(r'Parameters: "\{#Start\} ([a-z\-]+)"', iss))
    assert in_menu == set(windows_start.ENTRIES)
    workflow = (ROOT / ".github" / "workflows" / "windows-installer.yml").read_text(encoding="utf-8")
    checked = set(re.findall(r"= '([a-z\-]+)'", workflow.split("$expected = @{", 1)[1].split("}", 1)[0]))
    assert checked == set(windows_start.ENTRIES)
    assert "runasoriginaluser" in iss, "the app must not start with the installer's admin rights"
    assert '#define Start "-I -m eagleeye.bootstrap.windows_start"' in iss


def test_program_folder_is_derived_from_the_bundled_runtime(tmp_path):
    exe = tmp_path / "EagleEye" / "runtime" / "python.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    assert windows_start.app_dir(str(exe)) == tmp_path / "EagleEye"
    with pytest.raises(SystemExit, match="installierten EagleEye-Paket"):
        windows_start.app_dir(str(tmp_path / "python.exe"))


def test_tool_scripts_run_with_their_own_folder_on_the_import_path(tmp_path, capsys):
    tool = tmp_path / "tool"
    tool.mkdir()
    (tool / "helper_ee_test.py").write_text("VALUE = 'nachbar'\n", encoding="utf-8")
    (tool / "main_ee_test.py").write_text(
        "import sys\nfrom helper_ee_test import VALUE\nprint(VALUE, sys.argv[1:])\nraise SystemExit(3 if '--fail' in sys.argv else 0)\n",
        encoding="utf-8")
    before = sys.path[:]
    assert windows_start.run_script(tool / "main_ee_test.py", ["--init"]) == 0
    assert windows_start.run_script(tool / "main_ee_test.py", ["--fail"]) == 3
    assert sys.path == before
    out = capsys.readouterr().out
    assert "nachbar ['--init']" in out and "nachbar ['--fail']" in out
    assert windows_start.run_script(tool / "fehlt.py", []) == 1
    sys.modules.pop("helper_ee_test", None)


def test_fallakte_entry_passes_the_program_folder(tmp_path, monkeypatch):
    from eagleeye.bootstrap import desktop476

    exe = tmp_path / "EagleEye" / "runtime" / "python.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "executable", str(exe))
    calls = []
    monkeypatch.setattr(desktop476, "main", lambda argv: calls.append(argv) or 0)
    assert windows_start.main(["fallakte", "--no-browser"]) == 0
    assert windows_start.main(["datenordner"]) == 0
    assert calls == [["--install-root", str(tmp_path / "EagleEye"), "--no-browser"],
                     ["--install-root", str(tmp_path / "EagleEye"), "--choose-workspace"]]
    monkeypatch.setattr(desktop476, "main", lambda argv: (_ for _ in ()).throw(RuntimeError("kaputt")))
    assert windows_start.main(["fallakte"]) == 1, "a crash is reported, not a vanishing window"


def test_runtime_gets_tkinter_from_the_full_installation_without_dde_and_registry(tmp_path):
    stage = _load_build_stage()
    tag = f"{sys.version_info[0]}{sys.version_info[1]}"
    runtime, full = tmp_path / "runtime", tmp_path / "full"
    runtime.mkdir()
    for name in (f"python{tag}.dll", "libcrypto-3.dll", f"python{tag}._pth"):
        (runtime / name).write_bytes(b"embed")
    for rel in ("DLLs/_tkinter.pyd", "DLLs/tcl90.dll", "DLLs/tcl9tk90.dll", "DLLs/libcrypto-3.dll",
                "Lib/tkinter/__init__.py", "Lib/tkinter/filedialog.py", "tcl/tcl9.0/init.tcl",
                "tcl/tcl9.0/dde1.4/tcl9dde14.dll", "tcl/tcl9.0/reg1.3/tcl9registry13.dll", "tcl/tk9.0/tk.tcl"):
        (full / rel).parent.mkdir(parents=True, exist_ok=True)
        (full / rel).write_bytes(b"full")
    stage.prepare_runtime(runtime, full)
    assert (runtime / "libcrypto-3.dll").read_bytes() == b"embed", "the embeddable package's own files stay"
    assert sorted((runtime / "tkinter-files.txt").read_text().split()) == ["_tkinter.pyd", "tcl90.dll", "tcl9tk90.dll"]
    assert (runtime / "Lib" / "tkinter" / "filedialog.py").is_file()
    assert (runtime / "tcl" / "tcl9.0" / "init.tcl").is_file() and (runtime / "tcl" / "tk9.0" / "tk.tcl").is_file()
    assert not (runtime / "tcl" / "tcl9.0" / "dde1.4").exists() and not (runtime / "tcl" / "tcl9.0" / "reg1.3").exists()
    assert (runtime / f"python{tag}._pth").read_text().splitlines()[-1] == "import site"


def test_tkinter_source_may_be_an_unpacked_msi_with_a_nested_layout(tmp_path):
    stage = _load_build_stage()
    tag = f"{sys.version_info[0]}{sys.version_info[1]}"
    runtime, msi = tmp_path / "runtime", tmp_path / "tcltk"
    runtime.mkdir()
    (runtime / f"python{tag}.dll").write_bytes(b"embed")
    for rel in ("Python/DLLs/_tkinter.pyd", "Python/DLLs/tcl90.dll", "Python/Lib/tkinter/__init__.py", "Python/tcl/tcl9.0/init.tcl"):
        (msi / rel).parent.mkdir(parents=True, exist_ok=True)
        (msi / rel).write_bytes(b"msi")
    stage.prepare_runtime(runtime, msi)
    assert (runtime / "_tkinter.pyd").is_file() and (runtime / "tcl90.dll").is_file()
    assert (runtime / "tcl" / "tcl9.0" / "init.tcl").is_file() and (runtime / "Lib" / "tkinter" / "__init__.py").is_file()
