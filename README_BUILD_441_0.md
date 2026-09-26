# EagleEye Build 441.0 — Controlled Surface Retrieval

Build 441 starts **Phase 20** by closing the largest real-world data-acquisition gap identified at the Build-440 hard checkpoint: execution of bounded ordinary Surface-Web crawl tasks.

## What Build 441 adds

Build 441 executes existing Build-425 single-page crawl tasks against explicitly registered public HTTP(S) sources and routes every result back through the existing Build-425 -> Build-422/423 provenance and content-intake path.

The live executor is intentionally narrow:

- GET only;
- public access mode only;
- exact registered host only;
- exact task host allowlist;
- public globally routable DNS addresses only;
- DNS-to-IP pinning for the actual connection;
- TLS certificate/SNI validation for HTTPS;
- same-host redirects only, maximum three;
- fail-closed robots.txt enforcement;
- hard timeout and response-size budgets;
- safe content-type allowlist;
- no cookies or authentication headers;
- no forms, uploads, writes or JavaScript execution;
- no environment proxy inheritance;
- no onion execution;
- no live execution of synthetic fixture sources;
- no autonomous source/scope expansion.

## Two live authorization paths

### Explicit task execution

A permitted case user with \`crawler.run\` can execute a planned public task by repeating:

\`SURFACE441_LIVE\`

### Previously authorized Build-439 loop

A Build-425 task created by an **active, explicitly human-authorized Build-439 investigation loop** can be executed through the loop-authorized path without asking for a second per-task phrase. Build 441 verifies that the task remains in the same case and that its source is still inside the loop's approved source allowlist.

This does not let the AI enlarge its scope.

## Robots and redirects

Build 441 requests \`/robots.txt\` before the target. If robots policy cannot be obtained safely, the task fails closed. Cross-host redirects are rejected even when the destination is otherwise public.

## DNS / SSRF boundary

The hostname is resolved before each request. Every resolved address must be globally routable. The live transport then connects directly to a validated IP while preserving the original HTTP Host and HTTPS SNI/certificate checks. This prevents a task from using private, loopback, link-local or other non-public addresses.

## Current readiness

Build 441 materially changes the Build-440 result for ordinary Surface-Web acquisition:

- controlled ordinary Surface-Web retrieval: implemented;
- Build-425 provenance intake: integrated;
- Build-439 authorized-loop execution path: supported.

The wider system is still not generally live-complete. Dedicated News and Public-Social retrieval adapters remain incomplete, and external validation/production hardening are still required.

Therefore:

- \`general_live_collection_complete = false\`
- \`real_world_general_research_ready = false\`
- \`production_release_ready = false\`

## Qualification

Run:

\`\`\`bash
pytest -q tests/test_build441_integrated.py
\`\`\`

The deterministic self-test opens no external sockets. See \`BUILD_441_CASE_TEST.md\`.
