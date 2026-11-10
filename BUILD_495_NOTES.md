# EagleEye 495 – Unified PersonOSINT integration, source handoff

**Status:** integrated development source on branch `integration/build493-unified-personosint`.
**Not a released Windows installer**. Runtime package and version remain `490.0`
until a separate, fully checked installer release is prepared.

## What now runs as one EagleEye app

Normal `eagleeye.interfaces.web.server.create_workspace_app()` uses
`app495 -> app494 -> app493 -> app492 -> app489` with **the same case ID,
session, team_governance, document store, research lead table and audit**.

- **492:** WARC web capture + SHA-256, document/OCR extraction, source families,
  reviewed entity matching, network and FTM-oriented export.
- **493:** PersonOSINT 1.4 `export/case.json` public HTTPS findings imported
  only as canonical `research_leads_483` (always `unverified_lead`).
- **494:** PersonOSINT JSON `entities` imported as case-scoped review-only
  candidate rows, with hash integrity, deduplication and explicit reviewed
  decisions; never inferred verified identities or automatic graph edges.
- **495:** Unified `/workbench/personosint495`: deliberate public person,
  username and company research links, canonical source/graph/report
  tools and the two import workbenches.
- **495:** From a lead, open a prefilled **WARC capture** form (GET makes no
  outbound request; POST requires the normal authorization and consent).
- **Startup:** Windows/Linux launchers now respect data separation; normal
  helpers use the same version-specific venv as the installer.
- **Packaging:** GitHub Actions creates `EagleEye-495-ClaudeCode-SourceHandoff`
  source ZIP with both the integrated repo and Claude's original PersonOSINT
  1.4 files separately, plus SHA-256 manifest. It is not an executable release.

## Important limits

This is an **integration and Claude Code handoff milestone**, not complete
functional parity with the standalone PersonOSINT server:
- Full live PersonOSINT connectors still require migration to the EagleEye
  approved egress, case grants and evidence pipeline. The source catalogue
  in 495 is **manual**, not an automatic bulk crawler.
- Entity suggestions require a person to manually enter a justified graph
  record using EagleEye's existing editor; there is deliberately no cross-DB
  auto-merge or verified identity promotion.
- PersonOSINT's separate auth, 2FA, backup and team server are **not** run
  side-by-side. EagleEye's existing canonical team and audit own the case.
- Mandate screening, retention policies, monitoring and dossier templates
  need reviewed migrations instead of duplicate databases or competing UIs.
- Operational acceptance of a real Windows launcher, installed-package
  version alignment, full source integration, WARC restore and permitted
  live network flows is still needed before a production/internal release.

## Acceptance

```sh
python -m pip install -e '.[test]'
python -m pytest -q tests/test_build493_personosint.py tests/test_build494_personosint.py tests/test_build495_person_workbench.py tests/test_build490_server_selection.py tests/test_build490_package_contract.py tests/test_build490_real_server_start.py
```

Tests run for the current branch on GitHub Actions Windows and Linux.
The original Claude PersonOSINT and accepted old EagleEye branches remain unchanged.
