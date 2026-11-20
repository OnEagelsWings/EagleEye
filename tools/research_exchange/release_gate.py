"""Fail-closed, read-only 1.0 RC acceptance gate: never merges or releases.

Evidence is a user-reviewable, strictly shaped JSON document. Even if all
requirements pass, the script only reports readiness, never changes GitHub.
"""
import argparse
import json
from pathlib import Path
import sys

REQUIRED = {
    "synthetic_private_roundtrip": "Live synthetic two-way private GitHub exchange",
    "chatgpt_to_eagleeye": "Connected GitHub synthetic request staged locally",
    "windows_regression": "Windows research bridge regression suite",
    "linux_regression": "Linux research bridge regression suite",
    "windows_frozen_gui_smoke": "Portable EXE and Tk startup",
    "package_sha256": "Externally published RC archive SHA256",
    "install_update_rollback_uninstall": "Real portable ZIP install/update/rollback/uninstall",
    "eagleeye_ci": "Current integration PR full EagleEye CI",
    "gui_user_acceptance": "Owner visually inspected and used Windows GUI",
    "audit_independent_anchor": "Independent trusted checkpoint against audit tail loss",
    "code_signing_or_risk_approval": "Trusted executable signature or explicitly accepted unsigned internal distribution",
    "integration_owner_approval": "Current EagleEye branch owner accepts PR integration",
    "release_owner_approval": "Explicit human approval to release version 1.0",
}

VALID = {"passed", "pending", "failed", "skipped"}


def evaluate(record):
    if not isinstance(record, dict) or record.get("app_id") != "eagleeye-public-research-bridge" \
            or record.get("version") not in ("1.0.0-rc1", "1.0.0-rc2", "1.0.0-rc3"):
        raise ValueError("release record identity invalid")
    checks = record.get("checks")
    if not isinstance(checks, dict) or set(checks) != set(REQUIRED):
        raise ValueError("release record check names must match the complete gate")
    if any(value not in VALID for value in checks.values()):
        raise ValueError("invalid release gate status")
    blocked = [key for key, value in checks.items() if value != "passed"]
    return {
        "status": "HOLD" if blocked else "READY_FOR_MANUAL_RELEASE",
        "blocked": blocked,
        "passed": len(checks) - len(blocked),
        "total": len(checks),
        "no_automatic_merge_or_release": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_file", type=Path)
    args = parser.parse_args()
    record = json.loads(args.evidence_file.read_text(encoding="utf-8"))
    verdict = evaluate(record)
    print(json.dumps(verdict, sort_keys=True, indent=2))
    # A pending release is a non-zero exit, even when all automated tests pass.
    return 0 if verdict["status"] == "READY_FOR_MANUAL_RELEASE" else 2


if __name__ == "__main__":
    sys.exit(main())
