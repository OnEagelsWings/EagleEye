# EagleEye Build 382.0 – Phase 17 Persistent Source Intelligence

## Implemented
- SQLite-backed persistent Global Source Registry reference repository.
- Append-only source revisions with deterministic source and registry fingerprints.
- Case-scoped source candidate/approved/excluded state.
- Exact human `APPROVE SOURCE` confirmation for approval; approval does not grant execution authority.
- Persistent research-plan ledger bound to registry fingerprint and Build-381 plan hash.
- Evidence-linked source coverage ledger.
- Coverage-gap taxonomy: registry gap, selection gap, coverage gap, stale source, failed/blocked source.
- Explicit invariant that a no-result observation never proves non-existence.
- Build-382 persistent Investigation Control Plane facade.
- Cached schema/registry hot paths after scale benchmark exposed avoidable repeated integrity/catalog reconstruction work.

## Deliberately not claimed
- No live connector execution.
- No crawler/network execution.
- No full Build-380 database/app integration because the full Build-380 source ZIP is not available in the working directory.
- No external validation and no production qualification.

## Phase-17 direction
Build 382 turns the Build-381 in-memory catalog into a durable Data Acquisition planning layer. Build 383 can now add richer source taxonomy/query templates and a formal Source Planner while preserving the same GO/OPSEC boundaries.
