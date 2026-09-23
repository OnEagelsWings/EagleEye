# EagleEye Build 433.0 — Organization Intelligence

Build 433 adds a case-scoped organization-intelligence layer for public-source investigations. It separates analyst-defined organization subjects from provenance-bound source observations and source-asserted relationship claims.

The build can retain organization names and aliases, organization type, jurisdiction, public website, registration/identifier claims, public officer or representative claims, source-observed attributes, and organization-to-organization relationship claims. Conflicting attribute values are surfaced instead of silently choosing a winner.

Build 433 does **not** perform automatic entity resolution, beneficial-ownership determination, control determination, or truth promotion. Those distinctions are deliberate because cross-source entity resolution is scheduled later in Phase 19. Every substantive observation remains bound to a Build-422 acquisition event and Build-423 content object.

A one-step case-specific self-test is included. See `BUILD_433_CASE_TEST.md`. Production readiness remains false; Build 435 is the next hard checkpoint.
