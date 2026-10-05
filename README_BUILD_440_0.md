# EagleEye Build 440.0 — Phase 19 Hard Checkpoint

Build 440 is a **hard engineering checkpoint** for the Phase-19 chain. It does not add another broad capability layer. Instead it qualifies the integrated path built in Builds 421–439 and records the remaining real-world limitations explicitly.

## What Build 440 qualifies

The checkpoint requires integrity across all 19 Phase-19 components:

- source registry, acquisition events and content store;
- source health, crawl-task planning and prioritisation;
- change detection and archive-history intake;
- news ingest/extraction/provenance;
- public-social normalization;
- organization and registry intelligence;
- isolated, separately approved Tor research;
- surface/onion correlation;
- cross-source entity resolution;
- temporal/relationship fusion;
- the human-authorized AI Investigation Loop.

A dedicated qualification case then runs the Build-439 synthetic end-to-end path. This exercises planning, explicit GO, bounded research waves, multi-agent coordination, hypothesis/counterevidence handling, Phase-19 entity resolution/fusion, bounded collection-task planning and synthesis.

## Two separate readiness statements

A successful Build-440 qualification means:

**Phase-19 engineering checkpoint: PASS**

It does **not** mean:

**general live-research or production readiness: PASS**

The checkpoint currently records these limitations:

- ordinary Surface-Web crawl execution is not implemented inside Build 425;
- News retrieval execution is not implemented inside Build 429;
- Public-Social retrieval execution is not implemented inside Build 432;
- Build-439 collection tasks still require a separately governed retrieval adapter;
- controlled Tor retrieval is a separate gated path with explicit approval and confirmation;
- external end-to-end validation and production hardening remain incomplete.

These limitations are expected to make \`live_collection_complete\`, \`real_world_general_research_ready\` and \`production_release_ready\` remain \`false\` even when the engineering checkpoint passes.

## Fail-closed contract

Build 440 holds the checkpoint if:

- any required component fails integrity;
- the Build-439 case qualification fails;
- a forbidden autonomous authority appears;
- the declared live-retrieval boundary is no longer represented accurately.

No checkpoint result grants new operational authority.

## Test

Run:

\`\`\`bash
pytest -q tests/test_build440_integrated.py
\`\`\`

For the authenticated case-specific qualification, follow \`BUILD_440_CASE_TEST.md\`.

The next development priority after a passing Build 440 is not another analytical layer. It is a controlled ordinary-surface retrieval adapter plus external end-to-end validation.
