# EagleEye Build 438.0 — Temporal / Relationship Fusion

Build 438 follows Build 437's cross-source entity-resolution layer and turns reviewed identity links plus Phase-19 provenance into a unified temporal and relationship context.

## What changes

### Reviewed identity fusion, without record merging

Build 438 reads only active `same_entity_reviewed` links from the canonical entity-resolution ledger. Linked records are represented as a deterministic fusion group, while all original resolution entities, aliases, anchors and source bindings remain intact. Unreviewed candidates remain separate.

### Provenance-bound timeline

The case timeline uses explicit timestamps already present in source records: organization observations, source-asserted founding/dissolution dates, public social publication times, news publication times, archive captures and change-detection snapshots. Machine-extracted news events are admitted only when they contain an explicit parseable calendar/ISO time, and they remain marked as machine candidates.

Archive/snapshot capture time is explicitly distinguished from asserted event time. Conflicting lifecycle dates are surfaced as review disagreements; they are never auto-resolved.

### Explicit relationship graph

Relationship edges come from explicit `organization_relation_claim_433` assertions whose endpoints are bound into Build 437 entities. Each edge retains source, acquisition-event, content and source-span information. Person-role observations whose person endpoint is not explicitly resolved remain unresolved candidates. Public-social reply/reshare references are shown as observation relationships, not promoted to entity relationships.

Build 438 does **not** create graph edges from text co-occurrence and does not infer control, ownership, identity, causality or truth.

## Safety / integrity contract

- case-scoped only;
- Build-437 binding integrity and canonical resolution event-chain preflight;
- Phase-19 acquisition/content/news/social/organization/registry/change/archive integrity preflight;
- reviewed identity links are non-destructive;
- source records are retained;
- machine-extracted news events remain candidates;
- no automatic temporal-conflict resolution;
- no automatic entity relationship inference;
- no automatic identity confirmation;
- no truth or causality determination;
- no Build-438 network execution;
- production readiness remains false.

## Test

Run:

```bash
pytest -q tests/test_build438_integrated.py
```

For the authenticated case-specific workflow, follow `BUILD_438_CASE_TEST.md`.

Build 440 remains the next planned hard checkpoint.
