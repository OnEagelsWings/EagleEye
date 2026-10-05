# EagleEye Build 437.0 — Cross-source Entity Resolution

Build 437 turns Phase-19 observations into a transparent, review-gated entity-resolution workflow without creating a second competing identity system. It bridges current News, Social, Organization and Registry-backed observations into EagleEye's canonical entity-resolution ledger and reuses the evidence-weighted review logic already proven in the platform.

The design is deliberately aligned with EagleEye's niche: evidence-first, provenance-first, local-first and human-governed investigation for small professional teams. Scores are prioritisation weights, **not identity probabilities**. The system never automatically confirms identity and never destructively merges records.

Every Phase-19 binding retains source/event/content provenance. Organization identifiers, public websites/domains and social account identifiers can become explicit resolution anchors. Machine-extracted news mentions remain lower-reliability candidates. Surface↔Onion content correlation from Build 436 is exposed only as contextual material in a resolution packet and is explicitly **not treated as identity evidence**.

Candidate pairs are generated only inside the same case and are bounded for small-team workflows. Strong identifier conflicts can veto same-entity hypotheses. A proposed same-entity link requires an explicit human proposal and independent human review; approved links remain non-destructive.

A deterministic case-specific self-test is included in `BUILD_437_CASE_TEST.md`. Production readiness remains false. Build 438 will fuse accepted cross-source entities into temporal and relationship context without erasing provenance.
