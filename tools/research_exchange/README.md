# EagleEye Research Exchange (development preview)

This module exchanges **public scientific, historical, technical and institutional topic records only**. Never send personal investigation data, profiles, private case files, credentials, monitoring data or confidential material. The `classification: public-topic` declaration is **not** a personal-data detector; the human operator must inspect each record. Synthetic records must not become evidence.

## Architecture and scope

- **EagleEye source code** belongs in `OnEagelsWings/EagleEye`, Draft PR #97 (`feature/research-exchange-bridge`). Never commit exchange records, local keys or audit databases to the public code repository.
- **Exchange records** belong exclusively in the private `OnEagelsWings/MichaIntel` branch `research-exchange`.
- **Inbound**: explicit fetch without checkout or execution; strict schema validation; local SQLite staging and duplicate/conflict audit. No automatic vault or case import.
- **Outbound**: explicit preview, typed exact confirmation `APPROVE PUBLIC RESEARCH`, v2 HMAC receipt bound to the exact original bytes, separate manual confirmation, private Git push with conflict protection and retry. No periodic/background sync.
- **Audit**: UI outbound path writes HMAC-chained SQLite events (attempt **before** network; result after). Invalid chains refuse further publication. Interior edits and deletions are detected; tail truncation requires an independent trusted checkpoint, which is not part of this preview.

## Windows setup / launching the local GUI

Prerequisites: Windows, Python 3.11+ (with Tkinter), Git and authenticated Git Credential Manager with access to the private MichaIntel research branch; no extra paid service.

A **test-only** workspace is installed at `%LOCALAPPDATA%\EagleEyeResearchBridge`:

- `source`: Research Bridge code from PR #97.
- `workspace\git`: separate empty local Git repository for explicit fetches.
- `workspace\inbox`, `workspace\outbox`: local staging areas.
- `workspace\staging.sqlite`: inbound validated record storage (created on first fetch).
- `workspace\audit\ledger.sqlite`: outgoing signed audit (created on first publication).
- `secrets\approval.dpapi`: encrypted, current-user DPAPI key outside Git.

Windows secrets provisioning (run only once and never check in the output):

```powershell
python "$env:LOCALAPPDATA\EagleEyeResearchBridge\source\tools\research_exchange\init_windows_key.py"
```

Launch by double-clicking `%LOCALAPPDATA%\EagleEyeResearchBridge\START_RESEARCH_BRIDGE.cmd`, or run `tools\research_exchange\START_RESEARCH_BRIDGE_WINDOWS.cmd` from the checkout.

The **Eingang** tab fetches only on user request, stages validated records, shows source commit/status, and allows inspection. For a selected entry the operator may explicitly record a local **approved** or **deferred** decision, with an exact confirmation phrase and HMAC audit entry; no transfer or evidence import happens. The **Ausgang** tab prepares a schema-compliant JSON draft and previews it; a typed confirmation produces an in-memory signature, followed by a second affirmative confirmation to publish. The **Audit** tab verifies the local HMAC chain before displaying it. Inputs are always displayed as plain text (never executed or rendered as HTML). A reboot does not cause any automatic upload.

## Verification

```powershell
python -m unittest discover -s tools/research_exchange -p "test_*.py" -v
```

Opt-in interactive GUI smoke (creates only synthetic temporary local data and never publishes):

```powershell
$env:EAGLEEYE_RUN_GUI_SMOKE="1"
python -m unittest discover -s tools/research_exchange -p "test_desktop_ui.py" -v
Remove-Item Env:\EAGLEEYE_RUN_GUI_SMOKE
```

GitHub Actions separately runs the full test suite on Linux and Windows. Portable and Windows-only tests skip when platform requirements do not apply.

## Limitations before version 1.0

No independent off-host audit checkpoint, no end-to-end authenticated plugin adapter, no packaged/signed Windows installer, no formal user acceptance of GUI or public-branch transfer. Do not merge, release, or treat imported records as verified evidence until the remaining release criteria are met.
