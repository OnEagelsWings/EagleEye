# EagleEye Build 380 — Final Phase-16 Readiness Assessment

## Executive decision

**Current decision: `professional_pilot_only`.**

Phase 16 is technically complete at **20/20 builds**. The local, deterministic and replay-based qualification chain is internally consistent, the final crawler pilot-SLO gate is satisfied, and the platform is suitable for a **controlled professional pilot** with human review, explicit source authorization, bounded crawler budgets and defensive OPSEC.

It is **not** honestly a general production candidate in the packaged state because the independent Build-379 qualification receipt is absent (`not_run`). Build 380 therefore keeps both `production_candidate=false` and `production_release_ready=false`.

## What is currently strong enough for a controlled pilot

- case-scoped RBAC and audit/provenance;
- governed crawler queues with budgets, source review, backpressure, checkpoint/lease recovery and case isolation;
- Entity Resolution v2 with strong-identifier conflict veto and mandatory independent human review;
- Analyst Graph UX and Case Workflow with pause/resume and analyst handoff;
- AI crawl-plan evaluation with no direct crawl authority;
- evidence-first Dossier vNext with source coverage, staleness and bounded absence semantics;
- local image-intelligence handoff with exact deduplication and object-store pressure controls;
- local voice-to-crawl preview with edit/reconfirmation and no direct voice network authority;
- controlled Tor gateway remains separately gated;
- defensive OPSEC supervision with no autonomous firewall, OS, Tor-config, credential or ACL mutation.

## Final crawler SLO position

The Build-379 local prequalification created 500 durable crawler jobs, injected 50 lease/worker failures, used two workers, recovered 100% of sampled expired leases, recorded zero cross-case leaks, zero evidence-loss events and zero unauthorized network escalation. Those timings are an **accelerated local simulation**, not an external one-hour wall-clock soak.

For Build 380:

- `pilot_slo_gate_pass=true` when the bound local Build-379 evidence is current;
- `production_slo_gate_pass=false` until the independent Build-379 receipt validates;
- no automatic evidence eviction;
- no automatic production promotion.

## Outstanding external validation

The current package still records `not_run` for substantial real-world validation areas, including independent operational qualification, external PostgreSQL/team backend, S3/MinIO/team search, external remote-team clients, live connector families, external long-running crawler soak/load, real Tor/onion execution, real-world entity-resolution holdout, external analyst UX/workflow, professional dossier review, external image-provider review and external voice/STT multi-analyst validation.

These are not hidden behind a synthetic readiness score. The final decision exposes them explicitly.

## Scope of the professional pilot

Default pilot scope is a local or controlled private workspace using reviewed public/licensed sources, human-confirmed crawler work, bounded requests, human-reviewed entity resolution, evidence-first dossiers, local image analysis, local voice intent preview and defensive OPSEC.

The following remain disabled or separately gated: automatic identity merge, automatic scope expansion, unreviewed live connectors, Tor live work without its dedicated validation/confirmation, external reverse-image work without review, unvalidated public remote-team deployment, automatic production promotion and system-level firewall/OS/Tor/credential/ACL mutation.

## Production decision rule

Build 380 supports exactly three decision states:

1. `not_ready` — local final gates fail;
2. `professional_pilot_only` — local final gates pass but independent external qualification is absent;
3. `production_candidate` — local final gates pass and the fingerprint-bound independent Build-379 qualification verifies.

Even `production_candidate` is a candidate state, not an automatic deployment action. Human release review remains mandatory and unvalidated specialty capabilities stay separately gated.
