# Build 493 – Unified PersonOSINT Intake (development slice)

Status: **committed to integration branch, not production approved**.

Branch: `integration/build493-unified-personosint`
Base: `claude/spiderfoot-reverse-engineering-dn8lpd` (Build 492 development layer).
PersonOSINT source: `claude/osint-platform-person-search-r875rx` (independent PersonOSINT 1.4 application).

## Implemented

- Selected Build 493 application factory from the normal EagleEye server, retaining
  the Build 492 web-capture, OCR, source-family and network-analysis views.
- Added an authenticated, CSRF-protected, case-scoped intake for an existing
  PersonOSINT 1.4 case export in **Dossier & Export → Falldaten (JSON)** format:
  `GET/POST /workbench/personosint493?case_id=...`.
- Import only bounded, public HTTPS `findings[]` as research483
  `unverified_lead` records. Inherit **no** external review status, evidence,
  entity identity, relationship, case permissions, foreign case ID, audit record
  or source trust. No remote PersonOSINT instance or database is connected.
- Keep the original JSON only in transient request memory. Save URL, title,
  clearly labelled origin note and hashed foreign case reference in audit.
- Existing canonical research483 validation, case authorization, URL deduplication,
  250-lead case limit, hash integrity and user audit remain in force.
- Fixed normal Windows/Unix launch scripts so the default workspace is not
  created inside the upgradeable installation directory. Updated the auxiliary
  Windows tools to use `.eagleeye-runtime-490`.
- Ignore version-specific local runtimes and case directories in Git.
- Focused Build-493 tests exercise the real web application and import boundary.

## Non-goals / unfinished

- This is a **one-way import slice**, not a merged PersonOSINT server.
- No automatic transfer of entities, documents or private source data.
- A source URL is not an archived original or evidence; use EagleEye's
  normal governed capture/review flow before asserting it as a claim.
- No automatic live-source lookup, cross-case merging, or autonomous action.
- No migration of Build 398/legacy case data.
- Installed package version intentionally remains 490.0 until the full
  installer, dependency and runtime release contract is updated together.
- The present focus is on the **current** integration branch only. No
  retesting or edits of accepted historical build branches.

## Acceptance

Run on Windows and Linux against **this branch**:

```
python -m pip install -e '.[test]'
python -m pytest -q tests/test_build493_personosint.py tests/test_build490_package_contract.py tests/test_build490_server_selection.py tests/test_build490_real_server_start.py
```

Before any internal release, also execute a real `START_EAGLEEYE_PRO.bat`
start on Windows, a restart against the same external workspace, a backup +
restore check and an end-to-end test with a synthetic PersonOSINT JSON export.
GitHub's TestClient and launcher text checks are not a substitute for this.

## Integration roadmap

1. **493**: safe PersonOSINT case-lead intake, launcher repair, shared contract.
2. **494**: design a canonical PersonOSINT entity/identifier review adapter and
   integrate the case workflow without duplicate identity or audit stores.
3. **495**: create and verify a **current-branch** Windows internal ZIP, full
   runtime/installer checkpoint, recovery and no legacy-data regression.
4. 496–500: converge case-level source permissions, research engine, WARC,
   lineage, dossiers, AI tools, OPSEC and team governance on one kernel.

Neither Claude branch is merged wholesale: the original PersonOSINT work is
preserved on its source branch and remains independently accessible.
