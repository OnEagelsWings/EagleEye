# EagleEye Build 400 — Testing Guide

This guide is for external testers evaluating EagleEye Build 400 on fresh systems.

> Build 400 is a testing/evaluation baseline, not a production release. Use only synthetic, demo, or clearly public test data. Do not use confidential investigations, credentials, secrets, or sensitive personal information.

## 1. Environment

Please record:

- operating system and version
- CPU
- RAM
- Python version
- install method: Git clone or downloaded ZIP

Python 3.11 or newer is required.

## 2. First-start test

### Windows

1. Clone or download the repository.
2. Open the repository root.
3. Double-click `START_EAGLEEYE_PRO.bat`.
4. Allow the first-run setup to create `.venv` and install Python dependencies.
5. Confirm that the EagleEye browser workspace opens.

### Linux / macOS

```bash
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
```

The default local address is `http://127.0.0.1:8765`. EagleEye may select another loopback port when 8765 is unavailable.

## 3. Health test

Open `/health` on the displayed local EagleEye address. Expected minimum values:

```json
{
  "ok": true,
  "build": "400.0",
  "network_execution_on_boot": false,
  "production_release_ready": false
}
```

Do not treat additional capability flags as production-readiness claims.

## 4. Functional smoke test

Using only synthetic/demo data:

1. Open the workspace home screen.
2. Create a test case.
3. Re-open or navigate back to that case.
4. Inspect the case/evidence workspace.
5. Exercise the AI/investigation dialogue without granting unnecessary external actions.
6. If available, test one bounded research/crawler workflow using harmless public test targets.
7. Inspect the dossier/report workspace.
8. Close EagleEye completely.
9. Start it again and verify that the application still opens and the test case remains accessible as expected.

## 5. Developer test

For testers comfortable with Python:

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build400_integrated.py
```

Expected maintainer baseline: `11 passed`.

## 6. Report template

Please report results in GitHub issue #2 or open a separate issue for a reproducible defect.

```text
OS / version:
CPU:
RAM:
Python version:
Install method: clone / ZIP
First-start installation: PASS / FAIL
App opened in browser: PASS / FAIL
Health endpoint: PASS / FAIL
Case creation: PASS / FAIL
Restart: PASS / FAIL
AI/investigation workspace: PASS / FAIL / NOT TESTED
Crawler/research workflow: PASS / FAIL / NOT TESTED
Dossier/report workflow: PASS / FAIL / NOT TESTED
Observed error message:
Steps to reproduce:
Expected behavior:
Actual behavior:
Anything confusing in the UI/install process:
```

Before posting logs or screenshots, remove credentials, API tokens, cookies, identifying local paths, private case material, or any other sensitive information.

## 7. Highest-priority validation targets

We especially need independent confirmation of:

- fresh Windows 10/11 first-start setup
- Python 3.11 / 3.12 / 3.13 compatibility
- launch behavior when Firefox is unavailable
- behavior when port 8765 is already occupied
- clean restart after first-run initialization
- usability of the first case-creation workflow
- clarity of the AI/investigator interaction model
- errors or confusing states in the crawler/research UI
- resource use on ordinary 8–16 GB RAM systems

Thank you for helping test EagleEye.