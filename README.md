# EagleEye — Build 442

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance. Build 442 is the second build of **Phase 20 — Real-World Acquisition, Operationalization & Serious Beta**.

## Build 442 focus

Build 441 introduced controlled ordinary public Surface-Web retrieval. Build 442 hardens that path for real-world use without widening its authority.

The active Surface-Web execution path now adds:

- task-scoped DNS/IP pinning;
- detection of later non-public DNS answers;
- protection against DNS rebinding into private/loopback/link-local space;
- bounded retry for transient transport errors and selected HTTP failures;
- exponential backoff;
- per-source task-rate control;
- minimum spacing between tasks to the same source;
- source-scoped worker locking;
- one concurrent live Build-442 worker;
- fresh stateless transport per live run;
- persisted attempt/failure telemetry.

Build 441's safety contract remains in force:

- public HTTP(S) GET only;
- exact registered host and task scope;
- fail-closed robots.txt handling;
- same-host redirects only;
- TLS certificate/SNI validation;
- hard time and byte budgets;
- no credentials, cookies, forms, uploads, write methods or JavaScript;
- no private/local targets;
- no onion execution;
- no autonomous source/scope expansion.

## DNS hardening

The first valid public DNS answer becomes the task's pinned connection set. Later DNS answers are observed again. If a later answer becomes private or otherwise non-global, EagleEye stops before the next fetch. If a public CDN answer changes while remaining public, the change is recorded but the original validated IP set remains pinned for that task.

## Retry and rate policy

Transient retries are bounded to at most three attempts for transport failures and HTTP 408, 425, 429, 500, 502, 503 and 504.

TLS certificate verification failures are not retried.

The current EagleEye safety ceiling is:

- maximum 6 task starts per source per rolling minute;
- minimum 1 second between task starts against the same source.

A source's own terms or server guidance may require stricter behavior.

## External validation

External validation never runs automatically, on startup, or in CI.

A reviewed non-fixture public Build-425 task can be used for one explicit validation run with:

\`VALIDATE442_EXTERNAL\`

That run still passes through all Build-441/442 restrictions and provenance handling.

## Isolation boundary

Build 442 provides logical isolation through source locks, one live worker and fresh stateless transports. It does **not** claim process/container isolation. Stronger process/network isolation remains planned for the later Phase-20 OPSEC block.

## Current readiness

Implemented:

- controlled ordinary Surface-Web retrieval;
- current-scope Surface-Web hardening;
- deterministic retry/DNS/rate-limit qualification;
- explicit real external validation mechanism.

Still incomplete:

- dedicated live News acquisition;
- dedicated Public-Social acquisition;
- broad external end-to-end validation;
- process/container retrieval isolation;
- production hardening.

Therefore:

- \`general_live_collection_complete: false\`
- \`real_world_general_research_ready: false\`
- \`production_release_ready: false\`

The next build is **443 — Live News Acquisition**. The next hard checkpoint is **445 — Data Acquisition Hard Checkpoint**.

## External testers

Use only synthetic, demo, or clearly public data. Do not use confidential investigations, credentials, secrets, internal services or sensitive personal information.

**Repository:** https://github.com/OnEagelsWings/EagleEye  
**Testing guide:** [TESTING.md](TESTING.md)  
**Public beta feedback:** https://github.com/OnEagelsWings/EagleEye/issues/2

## Start

Python **3.12+** is required.

Windows:

\`\`\`powershell
START_EAGLEEYE_PRO.bat
\`\`\`

Manual Windows start:

\`\`\`powershell
py -3 -m pip install -e .
py -3 EAGLEEYE_PRO_442_0.py
\`\`\`

Linux/macOS:

\`\`\`bash
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
\`\`\`

## Qualification

Deterministic no-network qualification:

\`\`\`
POST /api/build442/cases/{case_id}/retrieval/selftest
\`\`\`

or:

\`\`\`bash
python -m pip install -e '.[test]'
pytest -q tests/test_build442_integrated.py
\`\`\`

See \`README_BUILD_442_0.md\`, \`BUILD_442_CASE_TEST.md\` and \`RELEASE_MANIFEST_BUILD_442_0.json\`.
