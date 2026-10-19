from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tools" / "CHECKPOINT_REGRESSION_EXCLUSIONS_461.json"
RETIRED_360_364 = [
    "tests/test_build360.py",
    "tests/test_build361.py",
    "tests/test_build362.py",
    "tests/test_build363.py",
    "tests/test_build364.py",
]


def load_manifest() -> dict:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    exclusions = data.get("exclusions") or []
    if int(data.get("excluded_count") or -1) != len(exclusions):
        raise RuntimeError("checkpoint exclusion count mismatch")
    seen = set()
    for item in exclusions:
        nodeid = str(item.get("nodeid") or "")
        reason = str(item.get("reason") or "")
        if not nodeid.startswith("tests/test_build") or "::" not in nodeid:
            raise RuntimeError("invalid checkpoint exclusion node id: " + nodeid)
        if "test_build461" in nodeid:
            raise RuntimeError("Build-461 tests may not be excluded")
        if not reason.startswith("superseded_"):
            raise RuntimeError("checkpoint exclusion requires explicit superseded reason")
        if nodeid in seen:
            raise RuntimeError("duplicate checkpoint exclusion: " + nodeid)
        seen.add(nodeid)
    return data


def phase18_20_targets() -> list[str]:
    targets = []
    for build in range(413, 462):
        # Include every available suite for the selected build, not only
        # historical naming conventions; new phase builds use new suffixes.
        candidates = sorted((ROOT / "tests").glob(f"test_build{build}_*.py"))
        exact = ROOT / "tests" / f"test_build{build}.py"
        if exact.is_file():
            candidates.insert(0, exact)
        for path in candidates:
            if path.is_file():
                rel = path.relative_to(ROOT).as_posix()
                if rel not in targets:
                    targets.append(rel)
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the Build-461 checkpoint regression while excluding only exact, documented historical current-build assertions."
    )
    parser.add_argument("--phase18-20", action="store_true", help="Run only the Phase-18/20 Build-413..455 chain.")
    parser.add_argument("--collect-only", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest()
    targets = phase18_20_targets() if args.phase18_20 else ["tests"]
    selected_files = None if targets == ["tests"] else set(targets)

    exclusions = []
    reasons: dict[str, int] = {}
    for item in manifest["exclusions"]:
        nodeid = item["nodeid"]
        file_part = nodeid.split("::", 1)[0]
        if selected_files is not None and file_part not in selected_files:
            continue
        exclusions.append(nodeid)
        reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1

    cmd = [sys.executable, "-m", "pytest", "-q", *targets]
    if not args.phase18_20:
        for path in RETIRED_360_364:
            cmd.append("--ignore=" + path)
    for nodeid in exclusions:
        cmd.extend(["--deselect", nodeid])
    if args.collect_only:
        cmd.append("--collect-only")

    print(json.dumps({
        "policy": manifest["policy"],
        "scope": "phase18-20" if args.phase18_20 else "repository",
        "targets": targets,
        "exact_deselections": len(exclusions),
        "reasons": reasons,
        "current_build_tests_excluded": False,
    }, indent=2, sort_keys=True))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
