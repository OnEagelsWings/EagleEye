# EagleEye Phase 16 Progress – Build 371

**Phase:** 16 – Live Operations, Entity Intelligence & External Validation  
**Progress:** 11/20 builds

## Build 371 – Entity Resolution v2 + Entity-linked Crawler Provenance

### Delivered
- Evidence-weighted Entity Resolution v2 layered over the canonical review-gated entity ledger.
- Strong identifier conflict veto for email, phone and external IDs.
- Birth-year conflict penalty, common-name collision penalty and independent-source weighting.
- Scores are prioritisation weights, never calibrated identity probabilities.
- No automatic identity confirmation, destructive merge or automatic same-entity link.
- Existing independent human review workflow remains authoritative for non-destructive links.
- Crawler increment: source/crawl/fetch/object provenance can be bound to a dedicated source-to-entity lead job.
- Entity lead queue uses the canonical persistent job ledger with zero network-request budget.
- Generic crawler workers and entity-link workers are separated by job type.
- OPSEC validates case scope and provenance hash and can cancel tampered leads only within the affected case.
- AI dossier gains unresolved Entity Resolution and crawler-lead context but no merge approval authority.
- No new per-build data tables.

## Qualification boundary
- Build 371 performs deterministic internal qualification only.
- Calibrated holdout / external Entity Resolution evaluation is intentionally Build 372 work.
- Production release ready: **false**.

## Final internal qualification
- Build-371 tests: **48/48 PASS**.
- Build-370 regression: **44/45 PASS**; expected historical version assertion only.
- Local crawler→entity provenance/lead workflow: **PASS**.
- Benchmark: **3,800/3,800 PASS**, **0 violations**.
- Acceptance: **21/21 PASS**.
- Activated canonical entity schema: **165 tables / 133 indexes / 8 triggers**; Build-371-specific tables added: **0**.
- External calibrated entity-resolution evaluation: **not_run / scheduled for Build 372**.
- `build_acceptance_ready=true`; `production_release_ready=false`.
