# EagleEye Phase 18 — Adaptive Plan Builds 406–410

This plan integrates the blocking feedback from the Builds 401–405 GitHub/Codex review into the normal Phase 18 roadmap. Feedback is not handled as a side patch: it changes build priorities.

## Build 406 — Review Remediation & Runtime Integration

Build 406 is a blocking remediation build. It must close all currently known P1 findings before the Data Fabric work proceeds.

Required work:
1. Enforce `governance_compliance == 1` in every holdout qualification predicate.
2. Count reviewer diversity only from reviews that independently satisfy all quality predicates and `harmful_overreach == 0`.
3. Make Build 401 security-gate fields authoritative and backed by implemented predicates; add a clean bootstrapped-context regression.
4. Canonically install Phase 18 services before app401–app404 access; add startup tests for all factories.
5. Wire the production launcher/server to the current Build 405/406 app and regress `/health` plus current endpoints.
6. Expand the authorization matrix to every qualification-changing Build 398/399 mutation (including external-run import/review operations), enforce governance authorization in those methods, and add read-only denial tests.
7. Replace free-form P0/P1 closure with ordered transitions, structured integrity-bound evidence, authorized independent verification, and proof that the named regression exists/passed.
8. Make Build 404 review-ledger integrity a mandatory prerequisite for Build 405/406 acceptance; tampering must fail closed.

Exit gate: zero open P0/P1 from PR #5, all associated permanent regressions green, startup/launcher green, `production_release_ready=false`.

## Build 407 — Connector/Data Fabric v1

Resume the original roadmap only after Build 406 passes. Introduce a unified connector interface over public/licensed APIs, register/bulk data, local mirrors, crawl sources, search providers and archives. Every connector must bind to Source Registry v2 metadata, provenance, rate limits, usage policy, OPSEC preflight and explicit execution scope.

## Build 408 — Federated Search v1

One investigation question can generate a governed query plan over local evidence, registered APIs, public web/search, archives and approved local mirrors. Results are normalized, deduplicated and provenance-preserving. No automatic evidence promotion and no automatic GO.

## Build 409 — Retrieval Quality & Coverage

Add source coverage, freshness, duplicate density, conflict density, citation completeness, unsupported-claim detection and missing-provenance metrics. The engine reports gaps; it does not convert quality metrics into truth probabilities.

## Build 410 — Feedback Cycle 2 Gate

Run integrated regressions, negative-path tests, authorization audit, review-ledger integrity, connector/data-fabric tests and real startup checks. Publish Builds 406–410 to GitHub for the next Codex/Copilot/external-tester cycle. P0/P1 findings block advancement; P2/P3 are prioritized into 411–415 according to safety, integrity, usability and investigation impact.

## Tester communication rule through Phase 20

Whenever the recommended baseline, branch, build or test focus changes, update both PR/feedback threads and the public tester issue. Each tester update must state:
- current recommended baseline/build/branch;
- whether it is development, beta, RC or release-ready;
- known blocking P0/P1 findings;
- exact areas that need testing now;
- obsolete test instructions that should no longer be followed;
- safe-data restriction (synthetic/demo/public data only where applicable).

At minimum, publish a tester update at each five-build boundary and immediately after any P0/P1 changes the recommended baseline or invalidates prior test results.

## Adaptive roadmap rule

The plan through Build 460 remains goal-driven, not feature-locked. External tester and AI-review findings may move, split, postpone or replace planned work. Security, authorization, evidence integrity, provenance, runtime reliability and human-governance defects take precedence over new features.