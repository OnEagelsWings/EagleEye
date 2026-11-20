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


## Controlled inbound index / targeted import

The local GUI retrieves only Git **path metadata** when the operator clicks "Remote-IDs laden". The operator selects a specific UUID and explicitly confirms fetching **only that record**. The importer filters by UUID **before** reading any private Git blobs. Pre-existing records on the private branch are neither inspected nor automatically staged. The GUI never opens case files or imports research records as evidence.

First-run launch from an EagleEye checkout executes the idempotent Windows workspace preparation script `install_local.py --init` and opens the GUI. Existing protected DPAPI key material, SQLite records and Git branches are preserved. No paid services or background services are installed.

## Actual synthetic live private-branch acceptance (2026-11-20)

With explicit synthetic-test authorization, `live_private_acceptance.py` was executed against the private MichaIntel `research-exchange` branch, returning exit code 0. It created exactly one synthetic public-topic outbound request (`81955ef7-e0d0-4043-a75d-0e58223d175f`) and one synthetic public-topic inbound response (`1a360777-cf62-46d7-ba5f-6aa295a2b55c`). The test confirmed byte-for-byte remote roundtrip, exact-record inbound staging, explicit inbound approval, idempotent outgoing retry (`duplicate`), blocked same-ID conflicting outgoing content, and a five-event HMAC audit trail. The remote commits were `d7377f0c691f3437ea4cbbc08261b9a03560e119` and `32c374a9e642bd1605fbf2ce723701b5199d0585`.

The script is guarded by two explicit CLI flags and does not make network writes by default. **Do not rerun the live test routinely:** each successful run creates a new pair of synthetic fixtures on the private branch. It does not read pre-existing private records. It is not a general-purpose research crawler.

Real user-facing private-branch publication still requires the operator's on-screen approval and review of record contents. The schema's classification claim does not ensure absence of personal data.

## Integration guidance

EagleEye's integrated root `START_HIER.bat` may offer an additional **Forschungs-Brücke** menu action, calling `tools\research_exchange\START_RESEARCH_BRIDGE_WINDOWS.cmd` in the current checked-out source. It must not import anything into the case/evidence vault, touch `main`, or bypass the two explicit operator confirmations. Keep the integration on a separate review branch based on PR #94 until its concurrent developer has accepted it.


## Windows 1.0 Release Candidate (2026-11-20)

The **unsigned** RC2 is packaged with free PyInstaller 6.19 on Windows x64. Once installed it runs without a Python interpreter, but private Git exchange still requires Git Credential Manager access to the private research branch. The package does not contain tokens, private records or signing keys.

On DoMi313 the package lives on drive D: at `D:\EagleEyeResearchBuild\rc2\EagleEyeResearchBridge-1.0.0-rc2-Windows-x64.zip`. Verify its SHA256:

`e8974769d0ed9814dd448eddaa7a4f9856f8ad7eecc0edd2d174478253d5de82`

Extract the ZIP, inspect the package, and run **Install.cmd**. The user-scoped installer validates every payload SHA256 from the manifest and installs under `%LOCALAPPDATA%\Programs\EagleEyeResearchBridge\versions\1.0.0-rc2`. It creates the desktop link **EagleEye Forschungs-Bruecke (Vorschau)** without requiring administrator privileges. The existing key, audit log, Git staging workspace and research records are **never** overwritten. An explicit **Uninstall.cmd** removes only the program; user data is retained.

The installer keeps older version directories and supports explicit SHA256-verified rollback via `Switch-ResearchBridge-Version.ps1 -Version 1.0.0-rc1`. Only the user requests an update/rollback; there is no silent updater.

Reproducible build command on an authorized Windows developer machine with Python 3.12 + PyInstaller:

```powershell
python tools/research_exchange/packaging/build_windows_release.py D:\EagleEyeResearchBuild\clean-output
```

The resulting ZIP is an **internal Release Candidate, NOT a signed or approved 1.0 release**. See `RELEASE_CANDIDATE_RC2.md`, `acceptance_rc2.json` and run the fail-closed `release_gate.py`. Manual GUI acceptance, off-host audit anchor, explicit unsigned internal-use risk acceptance or code signing, integration owner approval and final release owner approval remain outstanding. These steps cannot be automated away.
