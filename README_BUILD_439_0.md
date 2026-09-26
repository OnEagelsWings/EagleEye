# EagleEye Build 439.0 — AI Investigation Loop

Build 439 is the final functional Phase-19 build before the Build-440 hard checkpoint. It connects the existing planning, bounded research-wave, multi-agent, Phase-19 acquisition, entity-resolution, temporal/relationship-fusion, hypothesis/counterevidence, gap-analysis and synthesis layers into one human-authorized investigation loop.

## Investigation loop

A Build-439 loop binds one case objective to:

1. an immutable Build-413 investigation plan;
2. a bounded Build-414 research-wave envelope;
3. a Build-415/416 multi-agent analysis session with continuity checks;
4. Phase-19 registered source selection;
5. bounded Build-425 crawl-task creation and Build-426 prioritisation;
6. observation of Build-422/423 acquisition and evidence intake;
7. Build-437 cross-source entity resolution;
8. Build-438 temporal / relationship fusion;
9. Build-417/418 working hypotheses, counterevidence and gap analysis;
10. Build-419 reviewable synthesis.

The loop does not start autonomous cycles until an authorized case user enters the exact confirmation phrase:

\`AUTHORIZE INVESTIGATION LOOP\`

The authorization activates only the bounded analytical orchestration envelope. It does **not** grant Build 439 direct network authority.

## Retrieval boundary

Build 439 may create and prioritize bounded Phase-19 crawl tasks after human GO. Build-425 currently has no network executor, so a separately governed external retrieval adapter must perform ordinary public-web retrieval and submit the result through the existing intake path.

Tor/onion sources are never converted into ordinary Build-425 tasks. They remain routed to the isolated Tor worker and keep its separate approval boundary.

## Hypothesis discipline

Subquestions seed explicitly labelled working-hypothesis candidates. They are not findings. The loop preserves support, counterevidence, uncertainty and open questions through Builds 417/418. Missing evidence and missing counterevidence are surfaced as research gaps. Build 439 does not automatically accept a hypothesis, promote evidence, resolve identity, infer hidden relationships, infer causality or determine truth.

## Scope and safeguards

- case-scoped authorization;
- exact human GO required;
- immutable plan and research-wave binding;
- registered Phase-19 source allowlist;
- bounded cycles and bounded collection tasks;
- no autonomous source/scope expansion;
- no direct Build-439 network execution;
- no access-control bypass;
- provenance preserved through acquisition, resolution and fusion;
- reviewed same-entity links remain non-destructive;
- unresolved temporal/relationship conflicts stay review-visible;
- production readiness remains false.

## Test

Run:

\`\`\`bash
pytest -q tests/test_build439_integrated.py
\`\`\`

For the authenticated case workflow, follow \`BUILD_439_CASE_TEST.md\`.

Build 440 is the next hard checkpoint and should qualify the complete Phase-19 investigation path rather than introduce another major feature.
