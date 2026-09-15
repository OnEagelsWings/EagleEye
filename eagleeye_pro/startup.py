from __future__ import annotations
import argparse
import importlib
import json
import os
import platform
import sys
import traceback
from datetime import datetime
from pathlib import Path

from eagleeye_pro.version import BUILD, BUILD_NAME
LEGACY_DIAGNOSTIC_BUILD = BUILD


def _root_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _log_dir(base_dir: str | Path | None = None) -> Path:
    base = Path(base_dir) if base_dir else _root_dir()
    p = base / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_startup_log(message: str, base_dir: str | Path | None = None, filename: str = "startup_latest.log") -> Path:
    log_dir = _log_dir(base_dir)
    latest = log_dir / filename
    timestamped = log_dir / f"startup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    payload = f"{BUILD_NAME}\n{datetime.now().isoformat()}\n\n{message}\n"
    latest.write_text(payload, encoding="utf-8")
    timestamped.write_text(payload, encoding="utf-8")
    return latest


def diagnose(base_dir: str | Path | None = None) -> dict:
    base = Path(base_dir) if base_dir else _root_dir()
    checks: list[dict] = []

    def check(name: str, fn):
        try:
            value = fn()
            checks.append({"name": name, "status": "pass", "value": value})
        except Exception as exc:
            checks.append({"name": name, "status": "fail", "error": repr(exc), "traceback": traceback.format_exc()})

    check("python_version", lambda: sys.version)
    check("platform", lambda: platform.platform())
    check("working_directory", lambda: str(Path.cwd()))
    check("root_dir", lambda: str(_root_dir()))
    check("base_dir", lambda: str(base))
    check("tkinter_import", lambda: importlib.import_module("tkinter").TkVersion)
    check("app_context_import", lambda: importlib.import_module("eagleeye_pro.core.app_context").AppContext.__name__)
    check("desktop_import", lambda: importlib.import_module("eagleeye_pro.ui.desktop").EagleEyeDesktop.__name__)
    check("canonical_cli_import", lambda: importlib.import_module("eagleeye.interfaces.cli.main").main.__name__)

    def db_open():
        from eagleeye_pro.core.app_context import AppContext
        ctx = AppContext(base_dir=base)
        try:
            schema = ctx.db.one("SELECT value FROM meta WHERE key='schema_version'")
            integrity = ctx.db.one("PRAGMA integrity_check")
            return {"db_path": str(ctx.db.path), "schema_version": schema, "integrity": integrity}
        finally:
            ctx.close()
    check("database_open", db_open)

    status = "pass" if all(c["status"] == "pass" for c in checks) else "fail"
    result = {"build": LEGACY_DIAGNOSTIC_BUILD, "current_build": BUILD, "status": status, "checks": checks}
    out = _log_dir(base) / "startup_diagnostics_build_185_1.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_startup_log(json.dumps(result, ensure_ascii=False, indent=2), base)
    return result


def run_gui(base_dir: str | Path | None = None, safe_mode: bool = False) -> int:
    base = Path(base_dir) if base_dir else _root_dir()
    try:
        if safe_mode:
            from eagleeye_pro.ui.pilot_desktop import run_pilot_desktop
            run_pilot_desktop(base_dir=base, startup_error="Safe Mode wurde ausdrücklich gestartet.")
        else:
            from eagleeye_pro.ui.desktop import run_desktop
            run_desktop(base_dir=base)
        return 0
    except Exception:
        tb = traceback.format_exc()
        write_startup_log("GUI START FAILED - NO AUTOMATIC LEGACY FALLBACK\n\n" + tb, base)
        print("EagleEye konnte nicht starten. Diagnose: logs/startup_latest.log", file=sys.stderr)
        print(tb, file=sys.stderr)
        return 2

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=BUILD_NAME)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--safe-mode", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--base-dir", default=None)
    args = parser.parse_args(argv)
    if args.diagnose:
        print(json.dumps(diagnose(args.base_dir), ensure_ascii=False, indent=2))
        return 0
    if args.gui or args.safe_mode:
        return run_gui(args.base_dir, safe_mode=args.safe_mode)
    print(json.dumps(diagnose(args.base_dir), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
