# EagleEye Build 397.0 — Argumentative AI Analyst & Crawler Readiness Hardening

Build 397 integrates the 14 September 2026 weekly readiness findings into the product line.

## Core changes
- Fixes robots.txt wildcard/end-anchor matching (`*`, `$`).
- Correctly handles groups with multiple `User-agent` lines.
- Uses longest matching Allow/Disallow rule with Allow winning equal-specificity ties.
- Fails closed for ambiguous robots retrieval failures; only explicit 404/410 is treated as robots absence.
- Adds a provenance-bound argumentative analyst with precise evidence citations, support/counterevidence separation, source-independence awareness, discriminating questions, explicit stop/continue decisions, and review-only revision recommendations.

## Governance
No truth-probability, automatic evidence promotion, GO issuance, LIVE confirmation, active-state mutation, direct network fetch, or execution authority is added by Build 397.

## Qualification
- Build 397 integration tests: 13/13 PASS
- Acceptance: 17/17 PASS
- Analyst benchmark: 1000/1000 PASS, 0 violations
- Builds 360–380 regression: 792/822 PASS, 30 expected historical release boundaries, 0 functional regressions
- Phase 17 regression: 280/303 PASS, 23 expected historical release boundaries, 0 functional regressions
- Crawler Builds 369–370: 83/85 PASS, 2 expected release boundaries, 0 functional regressions

Status remains `professional_pilot_only`; `production_release_ready=false`. External browser/Windows/Tor/connector/model/soak qualification remains open.
