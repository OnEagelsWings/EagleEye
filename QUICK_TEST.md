# EagleEye — 15-Minute External Test

Thank you for testing EagleEye. This test is deliberately small: the goal is to learn whether a person who has never used EagleEye can get from the repository to a first investigation workflow in 15 minutes.

> Use only the bundled synthetic demo material. Do not enter credentials, private case data, sensitive personal information, or confidential investigation material.

## 1. Start the test

### Windows

Double-click:

`RUN_EXTERNAL_TEST.bat`

### Linux / macOS

```bash
chmod +x RUN_EXTERNAL_TEST.sh
./RUN_EXTERNAL_TEST.sh
```

The helper performs a local preflight and writes `external_test_report.txt`. It sends no telemetry.

Then start EagleEye with the normal repository launcher if it is not already running.

## 2. Five tasks

Start a timer when you begin.

1. **Launch** — Get EagleEye running and open its local browser workspace.
2. **Case** — Create a case named `EE-15MIN-DEMO`.
3. **Evidence** — Use `demo/external_test_case.json` and record at least one supplied evidence item in the case. Do not research the synthetic names on the public internet.
4. **Analysis** — Record which of the two supplied claims is better supported and explicitly mark uncertainty or contradiction. If the AI Investigator is available, ask it to distinguish fact, hypothesis and unresolved conflict.
5. **Persistence** — Close EagleEye completely, start it again, and verify that the demo case/evidence remains accessible.

Target: complete the workflow in **15 minutes or less**. Do not spend time repairing EagleEye for us. If installation or startup blocks you, that is a useful test result.

## 3. Copy/paste feedback

Open `external_test_report.txt` and add:

```text
First launch: PASS / FAIL
Demo case created: PASS / FAIL
Evidence recorded: PASS / FAIL
Fact/hypothesis/uncertainty workflow: PASS / FAIL / NOT AVAILABLE
Restart persistence: PASS / FAIL
Time to first investigation:
Biggest blocker or confusing step:
Expected behavior:
Actual behavior:
Would you voluntarily try EagleEye again? YES / NO / MAYBE
```

Post that report in the public beta issue or open a separate GitHub issue for a reproducible defect.

## Success criterion

This test is successful for the project even when EagleEye fails. We need reproducible evidence about installation friction, startup failures, confusing UI, persistence problems and unclear investigation workflows—not polite feedback.
