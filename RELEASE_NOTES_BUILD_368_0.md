# Release Notes – EagleEye Build 368.0

## Added
- Federal Register exact-document connector and parser.
- Internet Archive exact-item metadata connector and parser.
- Plan-only NARA, GovInfo, OFAC SDN and UN sanctions source definitions.
- Reference receipt layer using canonical Phase-15 provenance.
- Data-minimized OFAC/UN sanctions parsers for controlled reference matching.
- Case-scoped legal/government/archive AI context.
- Defensive OPSEC controls for plan-only, signed-redirect, archive-download and fuzzy-sanctions boundaries.
- Build-368 web/API workspace for reference intelligence.

## Preserved boundaries
- GET/HEAD-only qualified crawler execution.
- Human source review and explicit `LIVE` confirmation.
- No generic URL execution or automatic external startup traffic.
- No AI direct network/system-control authority.
- No automatic sanctions match confirmation, legal conclusion or adverse decision.
- No new per-build data tables.

## Validation statement
Deterministic tests and replay benchmarks are internal qualification evidence only. They do not constitute real external source validation, an external penetration test, load test or professional pilot.
