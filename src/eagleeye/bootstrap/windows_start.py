"""Start-menu entries of the installed Windows package.

The installer puts an official Python runtime into ``<Programmordner>\\runtime`` and creates one
shortcut per entry, e.g. ``runtime\\python.exe -I -m eagleeye.bootstrap.windows_start fallakte``.
Nothing here needs a Python installation on the computer, and nothing is written into the program
folder: cases, settings and reports stay in the user's own folders.
"""
from __future__ import annotations

import argparse
import os
import runpy
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ENTRIES = {
    "fallakte": "EagleEye Fallakte – Fenster offen lassen, Schließen beendet EagleEye",
    "datenordner": "EagleEye – Arbeitsordner wählen",
    "diagnose": "EagleEye – Startdiagnose",
    "vault": "EagleEye Vault – Fenster offen lassen, Schließen sperrt den Vault",
    "personosint": "PersonOSINT",
    "personosint-server": "PersonOSINT als Server im eigenen Netz",
    "quellen": "EagleEye – Quellen prüfen",
    "analyse": "EagleEye Analyse-Arbeitsplatz",
    "forschung": "EagleEye Forschungs-Brücke",
}


def app_dir(executable: str | None = None) -> Path:
    """The program folder: the runtime's python.exe lives in ``<app>\\runtime``."""
    exe = Path(executable or sys.executable).resolve()
    if exe.parent.name.lower() != "runtime":
        raise SystemExit("Dieser Starter gehört zum installierten EagleEye-Paket (Ordner „runtime“).")
    return exe.parent.parent


def documents_dir() -> Path:
    """The user's Documents folder (also when redirected, e.g. to OneDrive)."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            import uuid

            folder = uuid.UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")  # FOLDERID_Documents
            guid = (ctypes.c_byte * 16).from_buffer_copy(folder.bytes_le)
            path = ctypes.c_wchar_p()
            shell32 = ctypes.windll.shell32
            shell32.SHGetKnownFolderPath.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]
            if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path)) == 0:
                try:
                    return Path(path.value)
                finally:
                    ctypes.windll.ole32.CoTaskMemFree(path)
        except (AttributeError, OSError, ValueError):
            pass
    return Path.home() / "Documents"


def _title(text: str) -> None:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleTitleW(text)
        except (AttributeError, OSError):
            pass


def _exit_code(code) -> int:
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    print(code, flush=True)
    return 1


def _call(function, *args) -> int:
    try:
        return _exit_code(function(*args))
    except SystemExit as stop:
        return _exit_code(stop.code)


def run_script(script: Path, args: list[str]) -> int:
    """Run one of the bundled tool scripts like ``python script.py``: its folder is on the import path."""
    if not script.is_file():
        print("Programmteil fehlt: " + str(script), flush=True)
        return 1
    saved_argv, saved_path = sys.argv[:], sys.path[:]
    sys.argv = [str(script), *args]
    sys.path.insert(0, str(script.parent))

    def run() -> int:
        runpy.run_path(str(script), run_name="__main__")  # returns the script's globals, not an exit code
        return 0

    try:
        return _call(run)
    finally:
        sys.argv, sys.path[:] = saved_argv, saved_path


def _fallakte(app: Path, extra: list[str]) -> int:
    from eagleeye.bootstrap import desktop476

    return _call(desktop476.main, ["--install-root", str(app), *extra])


def _personosint(args: list[str]) -> int:
    from personosint.__main__ import main

    return _call(main, args)


def _quellen(app: Path) -> int:
    folder = documents_dir() / "EagleEye" / "Quellenprüfung"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    print("\n  EagleEye – Quellen prüfen (Internetverbindung nötig)")
    print("  Jede Quelle wird einmal mit einer unkritischen Testabfrage aufgerufen. Es wird nichts gespeichert.\n")
    print("  --- Quellen der EagleEye-Fallakte ---", flush=True)
    first = run_script(app / "tools" / "quellen_pruefen_fallakte.py", ["--out", str(folder / f"Fallakte_{stamp}.md")])
    print("\n  --- Quellen von PersonOSINT ---", flush=True)
    second = _personosint(["check-sources", "--out", str(folder / f"PersonOSINT_{stamp}.md")])
    print("\n  Die Berichte liegen in: " + str(folder), flush=True)
    if os.name == "nt":
        os.startfile(folder)  # noqa: S606 - opens the user's own report folder in Explorer
    return first or second


def _analyse(app: Path, extra: list[str]) -> int:
    tool = app / "tools" / "analysis"
    if Path("D:/EagleEye").is_dir() and "EAGLEEYE_ANALYSIS_HOME" not in os.environ:
        os.environ["EAGLEEYE_ANALYSIS_HOME"] = str(Path("D:/EagleEye/Analyseergebnisse"))
    native = tool / "native"
    extra_path = [native / "Library" / "bin", native / "Scripts", native]
    extra_path += [found / "bin" for found in sorted((tool / "tsk").glob("sleuthkit-*")) if (found / "bin" / "fls.exe").is_file()]
    present = [str(p) for p in extra_path if p.is_dir()]
    if present:
        os.environ["PATH"] = os.pathsep.join(present + [os.environ.get("PATH", "")])
    if (native / "share" / "tessdata" / "eng.traineddata").is_file():
        os.environ["TESSDATA_PREFIX"] = str(native / "share" / "tessdata")
    return run_script(tool / "bridge.py", extra)


def _forschung(app: Path) -> int:
    tool = app / "tools" / "research_exchange"
    init = subprocess.run([sys.executable, "-I", "-m", "eagleeye.bootstrap.windows_start", "skript",
                           str(tool / "install_local.py"), "--init"], check=False)
    if init.returncode:
        print("Fehler bei der lokalen Einrichtung. Keine Übertragung gestartet.", flush=True)
        return 2
    return run_script(tool / "desktop_ui.py", [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EagleEye-Start (installiertes Windows-Paket)")
    parser.add_argument("entry", choices=[*ENTRIES, "skript"])
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.entry == "skript":  # internal: run a bundled tool script in a fresh process
        return run_script(Path(args.rest[0]), args.rest[1:]) if args.rest else 2
    _title(ENTRIES[args.entry])
    app = app_dir()
    try:
        code = {
            "fallakte": lambda: _fallakte(app, args.rest),
            "datenordner": lambda: _fallakte(app, ["--choose-workspace", *args.rest]),
            "diagnose": lambda: _fallakte(app, ["--diagnose", *args.rest]),
            "vault": lambda: _personosint(["vault", *args.rest]),
            "personosint": lambda: _personosint(args.rest),
            "personosint-server": lambda: _personosint(["--server", "--no-browser", *args.rest]),
            "quellen": lambda: _quellen(app),
            "analyse": lambda: _analyse(app, args.rest),
            "forschung": lambda: _forschung(app),
        }[args.entry]()
    except Exception as exc:  # noqa: BLE001 - show a readable message instead of a vanishing window
        print(f"\n{ENTRIES[args.entry].split(' – ')[0]} konnte nicht starten ({type(exc).__name__}: {exc}).", flush=True)
        code = 1
    if (code or args.entry in ("diagnose", "quellen", "personosint-server")) and sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\nZum Schließen die Eingabetaste drücken … ")
        except (EOFError, KeyboardInterrupt):
            pass
    return code


if __name__ == "__main__":
    raise SystemExit(main())
