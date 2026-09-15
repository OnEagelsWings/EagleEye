# EagleEye – kontinuierlicher Crawler-Ausbau Build 370–380

Der Crawler bleibt von Build 370 bis einschließlich Build 380 ein verbindlicher Entwicklungsstrang. Jeder Build muss einen messbaren, testbaren Crawler-Increment liefern; neue Fachfeatures dürfen diese Weiterentwicklung nicht verdrängen.

| Build | Crawler-Increment | Status |
|---:|---|---|
| 370 | Tor-specific queue, SOCKS-auth capsule isolation, Tor backpressure, Tor lease/recovery | completed |
| 371 | entity-linked crawl provenance and source-to-entity lead queue; every lead preserves source/crawl/fetch/object hashes; no auto-merge | completed |
| 372 | crawler/entity-resolution evaluation corpus, false-link and source-quality calibration | completed |
| 373 | graph-aware analyst projection plus human-confirmed navigation to already-evidenced approved sources; source-health/backpressure/request budgets; no autonomous scope expansion | completed |
| 374 | case workflow orchestration, source budgets, pause/resume and analyst handoff | completed |
| 375 | AI crawl-planning evaluation, coverage metrics and scope-expansion denial tests | completed |
| 376 | dossier source-coverage, bounded absence-observation semantics, stale-source and research-gap metrics | completed |
| 377 | image/media crawling provenance, deduplication and object-store pressure controls | completed |
| 378 | voice-to-crawl intent preview, explicit source selection, budget preview, edit→reconfirmation and case-workflow delegation with no direct voice network authority | completed |
| 379 | external qualification framework plus local soak/load/failure prequalification, recovery SLO measurement, queue/lease stability, case-isolation and object-store pressure gates; signed external receipt required | completed |
| 380 | professional-pilot telemetry, final crawler SLO gate and scope-aware production decision | completed |

## Build 371 rules

- A crawl may create only a **review lead**, never an identity fact.
- Lead provenance binds `case_id`, `source_id`, `crawl_run_id`, optional `fetch_id`, source record hash and the canonical fetch/object hash chain.
- Entity lead analysis has zero request budget and no direct network client.
- Crawler workers and entity-lead workers use different job types and cannot silently consume each other's work.
- Strong identifier conflicts veto same-entity inference; common names are collision-risk signals.
- Independent human review remains required before a non-destructive same-entity link can be approved.

## Build 372 rules

- Evaluation uses synthetic or explicitly analyst-labeled holdout comparisons; no automatic threshold tuning.
- False-link safety is measured separately from identity probability; scores remain review weights.
- Source quality annotates crawler→entity leads but cannot confirm identity or bypass independent review.
- Strong-identifier-conflict escape and common-name false-link rates are explicit gates.
- Build 372 adds no direct network authority and no per-build data tables.

## Build 374 rules

- A configured case workflow is a case-local execution boundary; source and case request budgets are explicit and auditable.
- Workflow state is stored in the canonical job/event ledger; Build 374 adds no per-build workflow tables.
- Queued workflow crawls can be paused and resumed; running workers are drained/flagged rather than force-killed.
- Analyst handoff is two-step: proposal plus acceptance by an active analyst/investigator/case-lead member.
- Graph navigation and manual crawl enqueue paths are workflow-budget-aware once the workflow is configured.
- OPSEC detects untagged crawler jobs created after workflow activation and contains them case-locally.
- No automatic scope expansion, no direct workflow network authority and no review bypass are introduced.


## Build 375 actual crawler increment
- Structured AI crawl-plan evaluation is active.
- Coverage/source-selection, workflow-state, request-budget, backpressure and Scope-Expansion-Denial tests are mandatory.
- Valid plans are recommendations for human confirmation only; automatic AI crawler execution remains disabled.
- Special provider and Tor gates remain separate.
- External real-case AI planning evaluation remains not_run.


## Build 376 rules

- Source Coverage measures research completeness, never truth probability.
- `not_attempted`, `attempted_failed`, `covered_stale` and `covered_recent` remain distinct states.
- A bounded absence observation requires a succeeded case/source crawl plus at least one successful fetch and explicit analyst `RECORD` confirmation.
- A bounded absence observation is not non-existence and is not counterevidence by default.
- Staleness is source-class aware and creates a review/refresh gap, not an automatic truth update.
- Research gaps never auto-enqueue crawler work; Build 376 has no direct network authority.
- OPSEC blocks crawler jobs tagged for automatic gap closure and audits tampered absence observations.

## Build 377 actual status — completed
Crawler increment 377 adds image/media crawl provenance, exact SHA-256 deduplication before a new media object is written, logical object-store pressure gates, and a review-first handoff into the existing local Image Intelligence Agent. Image analysis does not gain network authority. Reverse-image providers remain separately reviewed gateways and no image result may auto-confirm identity or scene location.


## Build 378 actual status — completed
- Voice-to-crawler uses a visible preview bound to transcript, explicit source IDs, workflow generation and a SHA-256 preview hash.
- Voice never auto-selects sources; at most 2 already workflow-budgeted clearnet sources and 30 estimated requests may be proposed.
- Any transcript/source edit creates a new intent and invalidates the prior confirmation. Exact confirmation `VOICE CRAWL` is required.
- A fresh workflow/source/backpressure preflight runs again at confirmation time; stale previews cannot override current controls.
- Provider-linked connectors and Tor/onion sources remain on their separate manual LIVE/TOR gates.
- Confirmed work is delegated to Build-374's governed case-workflow enqueue path; the voice layer performs no network request itself.
- Crawler jobs retain the voice intent ID and preview hash for OPSEC/provenance checks.


## Build 379 actual status — completed
- Local deterministic prequalification exercises real SQLite/job/crawler checkpoint, lease-recovery, backpressure and OPSEC paths with replay transports.
- Recovery SLOs are measured locally, but local timings are not promoted to external production SLO evidence.
- Production runtime exposes no fault-injection API; qualification fault markers appearing in an operational case are contained by OPSEC.
- External qualification requires a Build-379 fingerprint-bound receipt, at least one hour of independent execution, minimum crawler/failure volumes, zero cross-case/evidence-loss/network-escalation violations and an Ed25519 signature verified against a locally configured independent-review trust anchor.
- Object-store pressure qualification must block at the hard limit without automatic evidence deletion or eviction.
- `externally_validated` remains false unless the signed external receipt is actually present and verifies; Build 380 retains final production-decision authority.


## Build 380 actual status — completed
- Professional-pilot telemetry aggregates the existing operations, crawler, workflow, evidence and OPSEC state without starting network work.
- The final crawler SLO gate explicitly separates accelerated local prequalification from independently measured production SLO evidence.
- Local pilot SLO gate: pass when Build-379 local evidence is current; production SLO gate requires the signed Build-379 external receipt.
- Final decision taxonomy is `not_ready`, `professional_pilot_only`, or `production_candidate`; there is no automatic promotion.
- Current packaged decision without an independent receipt: **professional_pilot_only**.
- Unvalidated specialty paths remain separately gated even if the core later becomes a production candidate.
- Phase 16 progress: **20/20**.
