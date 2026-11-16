# EagleEye Build 496 – human-gated investigation plans (development)

Date: 2026-11-10. Branch: `integration/build493-unified-personosint`.
Installed package identity still Build 490 until installer version is migrated.
Do not claim a standalone installer or autonomous AI system.

## Implemented

- One `app496` application factory layered on existing `app495`, with all 492–495
  WARC, document review, public source discovery and PersonOSINT intake preserved.
- `src/eagleeye/application/plan496.py`: persistent case-scoped
  `case_plans_496` and `case_plan_steps_496` in the **canonical** case DB.
  It enforces per-case RBAC, content bounds, hashing, audit records, strict tool
  proposal type allowlist and optimistic concurrency on reviews.
- Separate `research.run` for drafting/marking manual outcomes and
  `source.review` for approving or rejecting the plan. A plan can never be
  edited after review. Reviewed states are immutable in this interface.
- Existing canonical provider keys may be mentioned in `provider_proposal`
  steps. Disabled/unregistered providers are refused.
- Explicitly **NO live network execution**, no crawler or AI execution,
  no automatic Evidence or graph updates. A plan approval is *not* a
  substitute for a separately approved case search intent in
  `ProviderCollection120Service.execute(..., mode="live")`.
- `/workbench/plan496` review workbench plus link in the
  guided workflow, PersonOSINT workbench and evidence/analysis hub.
- Focused Windows/Linux integration tests for full lifecycle, case boundaries,
  CSRF, stale review, hash tamper detection, provider allowlisting and no
  provider runs.

## Next controlled development

497: Implement a read-only preview of existing provider search intents,
  per-step authorizations, public endpoint policy and result queues.
  Then a tightly gated execution adapter to the **existing** ProviderCollection120,
  with explicit operator confirmation, replay-only baseline, and
  live-mode tests on synthetic mocked transports before any live provider test.

498: Add typed, schema-validated AI plan proposals with prompt-injection isolation,
  quota/approval gates, case-scoped retrieval, provenance and human acceptance.
  The LLM never calls the network directly; it requests deterministic services.

499: Join person/source candidate review and graph/evidence via recoverable,
  idempotent operations; verify backup/restore across original files, WARC,
  canonical case DB and entity registry. Do not infer person identity.

500: Formal current-branch release gates: version/installer alignment,
  actual Windows launcher, repeated restart, backup+restore, two-person audit,
  OPSEC policy enforcement, and user acceptance before internal Release 1.0.

## Verification

```sh
python -m pip install -e '.[test]'
python -m pytest -q tests/test_build496_plan.py tests/test_build495_person_workbench.py tests/test_build490_server_selection.py tests/test_build490_real_server_start.py
```

Tests are synthetic/local and cannot prove a live internet search or
real-world investigative quality.
