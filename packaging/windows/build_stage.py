"""Assemble the folder the Windows installer ships (``build/stage``).

Steps (run by .github/workflows/windows-installer.yml on a Windows runner):

  runtime   official embeddable Python + tkinter from the same Python version, isolated via ._pth
  assemble  bundled tools and documentation, nothing from the repository that is not needed
  manifest  SHA-256 of every shipped file plus versions, written last

The stage never contains data, settings or credentials. Cases and settings live in the user's
folders (``%LOCALAPPDATA%\\EagleEye-500``, ``%LOCALAPPDATA%\\EagleEye-Vault``).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Tool scripts started from the Start menu (see src/eagleeye/bootstrap/windows_start.py).
RESEARCH_BRIDGE_SKIP = re.compile(r"^(test_.*|live_private_acceptance|release_gate|build_windows_release)\.py$")
ANALYSIS_FILES = ("bridge.py", "engine.py", "security_tools.py", "local.html", "README.txt")
DOCS = {
    "LIESMICH.md": "LIESMICH_KOMPLETTPAKET.md",
    "BETRIEBSHANDBUCH_BUERO.md": "BETRIEBSHANDBUCH_BUERO.md",
    "GESAMTVERSION_500.md": "GESAMTVERSION_500.md",
    "VAULT.md": "PersonOSINT/docs/VAULT.md",
    "PERSONOSINT.md": "PersonOSINT/README.md",
    "INSTALLATION_WINDOWS.md": "packaging/windows/README.md",
}


def pth_text(version: tuple[int, int]) -> str:
    """Import path of the bundled runtime. A ._pth file also makes Python ignore PYTHONPATH,
    PYTHONHOME and registry entries, so nothing outside the program folder is imported."""
    tag = f"{version[0]}{version[1]}"
    return "\n".join([f"python{tag}.zip", ".", "Lib", r"Lib\site-packages", "import site", ""])


def prepare_runtime(runtime: Path, tk_source: Path) -> None:
    """Turn the extracted embeddable package into the EagleEye runtime."""
    version = sys.version_info[:2]
    tag = f"{version[0]}{version[1]}"
    dll = runtime / f"python{tag}.dll"
    if not dll.is_file():
        raise SystemExit(f"Eingebettetes Python {version[0]}.{version[1]} erwartet, {dll.name} fehlt")
    for old in runtime.glob("python*._pth"):
        old.unlink()
    (runtime / f"python{tag}._pth").write_text(pth_text(version), encoding="ascii")
    (runtime / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)
    # tkinter (folder picker, Forschungs-Brücke) is not part of the embeddable package.
    # Take it from the official installation of exactly the same version
    # (an installed Python or the unpacked tcltk.msi of python.org).
    if not (tk_source / "DLLs" / "_tkinter.pyd").is_file():
        # An unpacked MSI may nest the installation layout one level deeper.
        found = next(iter(sorted(tk_source.rglob("DLLs/_tkinter.pyd"))), None)
        if found is not None:
            tk_source = found.parent.parent
    shutil.copytree(tk_source / "Lib" / "tkinter", runtime / "Lib" / "tkinter",
                    ignore=shutil.ignore_patterns("__pycache__", "test*"), dirs_exist_ok=True)
    copied = []
    tkinter_pyd = tk_source / "DLLs" / "_tkinter.pyd"
    if not tkinter_pyd.is_file():
        raise SystemExit("tkinter-Bestandteile nicht gefunden in " + str(tk_source))
    shutil.copy2(tkinter_pyd, runtime / tkinter_pyd.name)
    copied.append(tkinter_pyd.name)
    # The Tcl/Tk libraries (names differ between Tcl 8.6 and 9): every DLL of the full
    # installation that the embeddable package lacks.
    for item in sorted((tk_source / "DLLs").glob("*.dll")):
        if not (runtime / item.name).exists():
            shutil.copy2(item, runtime / item.name)
            copied.append(item.name)
    # Tcl's Windows-only "dde" and "registry" packages are not used by tkinter; leave them out.
    shutil.copytree(tk_source / "tcl", runtime / "tcl", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("dde[0-9]*", "reg[0-9]*", "*dde[0-9]*.dll", "*registry[0-9]*.dll"))
    (runtime / "tkinter-files.txt").write_text("\n".join(copied) + "\n", encoding="ascii")
    print("Laufzeit vorbereitet:", runtime, "| tkinter:", ", ".join(copied))


def assemble(stage: Path, repo: Path = REPO) -> None:
    tools = stage / "tools"
    bridge = tools / "research_exchange"
    bridge.mkdir(parents=True, exist_ok=True)
    for item in sorted((repo / "tools" / "research_exchange").glob("*.py")):
        if not RESEARCH_BRIDGE_SKIP.match(item.name):
            shutil.copy2(item, bridge / item.name)
    for name in ("README.md",):
        shutil.copy2(repo / "tools" / "research_exchange" / name, bridge / name)
    analysis = tools / "analysis"
    analysis.mkdir(parents=True, exist_ok=True)
    for name in ANALYSIS_FILES:
        shutil.copy2(repo / "tools" / "analysis" / name, analysis / name)
    shutil.copy2(repo / "tools" / "quellen_pruefen_fallakte.py", tools / "quellen_pruefen_fallakte.py")
    docs = stage / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    for target, source in DOCS.items():
        shutil.copy2(repo / source, docs / target)
    # Database migrations: an installed wheel looks for them below sys.prefix (= runtime folder);
    # pip --target does not copy wheel data files, so they are placed here explicitly.
    shutil.copytree(repo / "alembic_104_1", stage / "runtime" / "alembic_104_1",
                    ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    # pip --target leaves console-script wrappers that point at the build machine's Python.
    for scripts in ("bin", "Scripts"):
        shutil.rmtree(stage / "runtime" / "Lib" / "site-packages" / scripts, ignore_errors=True)
    print("Werkzeuge und Anleitungen übernommen:", stage)


def lock_versions(lock: Path) -> dict[str, str]:
    versions = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.\-\[\]]+)==([^\s\\;]+)", line)
        if match:
            versions[match.group(1).split("[")[0].lower()] = match.group(2)
    return versions


def write_manifest(stage: Path, *, version: str, commit: str, embed_sha256: str, python: str) -> Path:
    files = {}
    for item in sorted(stage.rglob("*")):
        if item.is_file() and item.name not in ("MANIFEST-SHA256.json",):
            files[item.relative_to(stage).as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    manifest = {
        "product": "EagleEye", "version": version, "source_commit": commit,
        "python": python, "python_embed_sha256": embed_sha256,
        "packages": lock_versions(REPO / "packaging" / "windows" / "requirements-windows.lock"),
        "files": files,
    }
    path = stage / "MANIFEST-SHA256.json"
    path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Manifest: {len(files)} Dateien")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="step", required=True)
    run = sub.add_parser("runtime")
    run.add_argument("--runtime", type=Path, required=True)
    run.add_argument("--tk-from", type=Path, default=Path(sys.base_prefix))
    asm = sub.add_parser("assemble")
    asm.add_argument("--stage", type=Path, required=True)
    man = sub.add_parser("manifest")
    man.add_argument("--stage", type=Path, required=True)
    man.add_argument("--version", required=True)
    man.add_argument("--commit", required=True)
    man.add_argument("--embed-sha256", required=True)
    man.add_argument("--python", required=True)
    args = parser.parse_args(argv)
    if args.step == "runtime":
        prepare_runtime(args.runtime, args.tk_from)
    elif args.step == "assemble":
        assemble(args.stage)
    else:
        write_manifest(args.stage, version=args.version, commit=args.commit,
                       embed_sha256=args.embed_sha256, python=args.python)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
