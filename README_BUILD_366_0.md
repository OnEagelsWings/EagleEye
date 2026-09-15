# EagleEye PersonOSINT Pro — Build 366.0

## Phase 16: Corporate Live Data

Build 366 extends the controlled pilot candidate with a governed corporate-data execution layer for official public no-auth connector paths already present in EagleEye.

### Primary surfaces
- GLEIF LEI record lookup by exact LEI.
- SEC EDGAR submissions lookup by exact CIK.
- Human source review + explicit `LIVE` confirmation.
- Bounded read-only crawler execution.
- Canonical evidence/object/parser provenance and derived corporate receipts.
- Case-scoped corporate summary for AI dossiers with data minimization.
- OPSEC cancellation of tampered corporate jobs.

### Not added
- No person-name live search.
- No authenticated corporate API execution.
- No new credential store.
- No identity auto-merge.
- No automatic external connection on startup.
- No claim of production readiness.

### Start
Windows: `START_EAGLEEYE_PRO.bat`  
Python: `python EAGLEEYE_PRO_366_0.py --gui`

### Explicit live validation
`tools/live_corporate_validate_366.py` requires an operator-selected connector/identifier and `--confirm LIVE`. SEC additionally requires a declared User-Agent containing contact information.

Build 366 ships with external GLEIF/SEC runtime validation as `not_run`; deterministic replay evidence is intentionally insufficient for `externally_validated=true`.
