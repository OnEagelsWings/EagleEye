# Release Notes — Build 366.0

Build 366 is Phase 16 build 6/20 and focuses on Corporate Live Data.

## Added
- Governed GLEIF LEI and SEC EDGAR submissions execution paths.
- Per-identifier corporate source registration over the consolidated schema.
- Explicit `LIVE` gate and read-only source-review requirement.
- Canonical corporate provenance receipt derived from crawl/object/parse ledgers.
- SEC declared-contact User-Agent enforcement.
- AI corporate-safe context and dossier integration.
- Corporate job OPSEC validation/cancellation.
- Corporate web dashboard/API surfaces.
- Explicit operator live-validation harness.

## Qualification
- 26/26 Build-366 tests pass.
- 2,600/2,600 benchmark cases pass with 0 violations.
- Build-365 functional regression is green except for the expected version-boundary assertion.
- Schema remains 141 tables / 128 indexes / 8 triggers.

## Validation boundary
Neither GLEIF nor SEC was contacted by the build acceptance or benchmark environment. Both external validation states remain `not_run`; production release remains false.
