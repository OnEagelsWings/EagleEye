from __future__ import annotations

import platform
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "external_test_report.txt"


def read_version() -> str:
    p = ROOT / "pyproject.toml"
    if not p.exists():
        return "UNKNOWN"
    text = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else "UNKNOWN"


def launcher_status() -> tuple[str, list[str]]:
    candidates = [
        "START_EAGLEEYE_PRO.bat",
        "START_EAGLEEYE_PRO.sh",
    ]
    present = [name for name in candidates if (ROOT / name).exists()]
    return ("PASS" if present else "FAIL", present)


def demo_status() -> str:
    return "PASS" if (ROOT / "demo" / "external_test_case.json").exists() else "FAIL"


def main() -> int:
    started = time.monotonic()
    launcher, launchers = launcher_status()
    demo = demo_status()
    py_ok = sys.version_info >= (3, 12)

    lines = [
        "EagleEye External Test — Local Preflight",
        "========================================",
        f"Project version: {read_version()}",
        f"OS: {platform.platform()}",
        f"Python: {platform.python_version()}",
        f"Python >= 3.12: {'PASS' if py_ok else 'FAIL'}",
        f"Repository launchers present: {launcher} ({', '.join(launchers) or 'none'})",
        f"Synthetic demo fixture: {demo}",
        f"Preflight duration: {time.monotonic() - started:.2f}s",
        "",
        "Manual 15-minute results",
        "------------------------",
        "First launch: PASS / FAIL",
        "Demo case created: PASS / FAIL",
        "Evidence recorded: PASS / FAIL",
        "Fact/hypothesis/uncertainty workflow: PASS / FAIL / NOT AVAILABLE",
        "Restart persistence: PASS / FAIL",
        "Time to first investigation:",
        "Biggest blocker or confusing step:",
        "Expected behavior:",
        "Actual behavior:",
        "Would you voluntarily try EagleEye again? YES / NO / MAYBE",
        "",
        "Privacy: this helper sends no telemetry and performs no external research.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:9]))
    print(f"\nReport written to: {REPORT}")
    return 0 if py_ok and launcher == "PASS" and demo == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
