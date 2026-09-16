# Phase 18 Feedback Cycle — Builds 401–405

This branch is the first mandatory five-build public feedback cycle for EagleEye Phase 18.

## Changes under review

- **401 — Security & Qualification Gate Hardening**: read-only fail-closed gate around Build-398/399/400 qualification, soak and human-review controls.
- **402 — Authorization Matrix Audit**: machine-readable inventory of 32 high-risk mutation surfaces, their required capabilities and allowed roles; global acceptance is included.
- **403 — Negative Path / Abuse Framework**: 15 P1 negative-path scenarios covering missing records, authorization, confirmations, invalid state, duplicate mutations, governance bypass, scope manipulation and integrity.
- **404 — AI Review Gate**: persistent review ledger; P0/P1 remain blocking until fix evidence + verification evidence + a named regression test exist.
- **405 — Source Registry v2**: governed source capability/auth/rate/usage/provenance/health metadata; health is observation only and never grants live/network authority.

## Build-400 remediation carried forward

The cycle also carries forward the prior GitHub AI remediation branch for: human acceptance disposition, global acceptance authorization, holdout quality thresholds, harmful-overreach veto and structured missing-session handling.

The Build-401 regression explicitly requires two additional invariants found by the second Codex review:

1. `governance_compliance == 1` must be a hard predicate independent of aggregate structural score.
2. reviewer diversity must count only reviewers whose own blinded reviews meet all qualification thresholds.

Reviewers should treat failure of either invariant as **P1/blocking**.

## Local reference validation before publication

The complete local Build-405 source tree was tested before this review branch was opened:

- Build 405 integration suite: **7/7 PASS**
- sampled functional predecessor regressions: **36 PASS**; only historical build-number/launcher assertions were excluded
- real local server startup: **PASS**
- `/health`: Build `405.0`, 6/6 source metadata rows complete, no network execution on boot, `production_release_ready=false`

The public review branch uses `phase18.bootstrap405` as a compatibility bootstrap instead of rewriting the large legacy `AppContext` in this review upload. Please review whether this bootstrap is safe and whether canonical ServiceRegistry integration should replace it before merge.

## Required review focus

Please inspect for:

- any path by which an unsafe model run can satisfy holdout qualification;
- reviewer-diversity or harmful-overreach bypasses;
- authorization surfaces missing from Build 402;
- global-vs-case scope authorization discrepancies;
- stale, missing, duplicate or malformed-state behaviors absent from Build 403;
- ways to mark a P0/P1 `verified_closed` without adequate evidence in Build 404;
- metadata-hash or health-history integrity problems in Build 405;
- source health accidentally enabling network/live collection;
- invalid auth/provenance metadata accepted by Source Registry v2;
- bootstrap/runtime wiring errors and stale Build-400 references.

Do not weaken human-governed controls, automatic-GO restrictions, provenance requirements or `production_release_ready=false` to make tests pass.

## Feedback policy through Phase 20

Every five builds are published for renewed AI/external review. P0/P1 findings must be corrected and regression-tested before the next cycle is accepted. P2/P3 findings are triaged by security, data-integrity, installation and investigation impact and may reprioritize later Phase 18–20 builds. The roadmap is intentionally adaptive to evidence from these reviews.
