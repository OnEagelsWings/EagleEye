# EagleEye — Build 443

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance. Build 443 is the third build of **Phase 20 — Real-World Acquisition, Operationalization & Serious Beta**.

## Build 443 focus

Build 441 introduced controlled public Surface-Web retrieval. Build 442 hardened that path. Build 443 now adds a dedicated **live public News acquisition layer** on top of the same hardened retrieval boundary.

Supported feed formats:

- RSS
- Atom
- JSON Feed

Registered sources must use source type \`rss\`, \`news\` or \`api\` and access mode \`public\`.

## News acquisition chain

\`\`\`
421 Source Registry
  -> 425 feed task
  -> 442 hardened public retrieval
  -> 422 parent feed acquisition event
  -> 423 feed fingerprint/dedup
  -> normalized feed entries
  -> derived 422/423 item observations
  -> 429 normalized news items
  -> 431 provenance/syndication analysis
\`\`\`

The feed body is used only in memory during parsing. Build 443 does not introduce a second persistent raw-payload store.

## Data-quality boundary

A feed item is persisted only when it has:

- a title;
- a public HTTP(S) canonical URL;
- a parseable publication timestamp;
- an article host inside the reviewed source allowlist.

The registered source host is automatically allowed. Additional publisher/article hosts must be declared explicitly through \`coverage.allowed_article_hosts\`.

Missing publication times are not silently replaced by collection time. Cross-host article links outside the reviewed allowlist are skipped rather than followed.

Duplicate \`source_id + external_id\` items are not re-ingested.

## Parser security

XML feeds with DTD or ENTITY declarations are rejected. Feed parsing is bounded by the Build-443 byte and item limits and still inherits Build-442 DNS, retry, rate-limit, TLS and robots protections.

## Semantic discipline

Build 443 does **not** infer entities, events or claims merely from feed titles and summaries.

Build 430 remains available downstream for an explicit semantic-extraction stage, but Build 443 itself records source observations rather than presenting feed metadata as verified fact.

## Live execution

A reviewed feed task requires the exact confirmation:

\`NEWS443_LIVE\`

No authenticated feeds, cookie sessions, login automation, paywall bypass, JavaScript rendering or article-body spidering are introduced.

## Current readiness

Implemented:

- controlled public Surface-Web retrieval;
- Build-442 retrieval hardening;
- live RSS/Atom/JSON Feed acquisition;
- normalized 429 news-item ingestion;
- 431 provenance/syndication analysis;
- deterministic no-network qualification.

Still incomplete:

- controlled Public-Social acquisition;
- automatic semantic extraction from news content;
- broad article-body acquisition;
- broad external end-to-end validation;
- process/container retrieval isolation;
- production hardening.

Therefore EagleEye still reports:

- \`general_live_collection_complete: false\`
- \`real_world_general_research_ready: false\`
- \`production_release_ready: false\`

The next build is **444 — Controlled Public-Social Acquisition**. The next hard checkpoint is **445 — Data Acquisition Hard Checkpoint**.

## External testing

Use only synthetic, demo, or clearly public data. Do not use confidential investigations, credentials, private/internal services, paywalled login flows or sensitive personal information during beta qualification.

**Repository:** https://github.com/OnEagelsWings/EagleEye  
**Testing guide:** [TESTING.md](TESTING.md)  
**Public beta feedback:** https://github.com/OnEagelsWings/EagleEye/issues/2

## Start

Python **3.12+** is required.

Windows:

\`\`\`powershell
START_EAGLEEYE_PRO.bat
\`\`\`

Manual start:

\`\`\`powershell
py -3 -m pip install -e .
py -3 EAGLEEYE_PRO_443_0.py
\`\`\`

Linux/macOS:

\`\`\`bash
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
\`\`\`

## Qualification

Deterministic no-network qualification:

\`\`\`
POST /api/build443/cases/{case_id}/news/selftest
\`\`\`

or:

\`\`\`bash
python -m pip install -e '.[test]'
pytest -q tests/test_build443_integrated.py
\`\`\`

See \`README_BUILD_443_0.md\`, \`BUILD_443_CASE_TEST.md\` and \`RELEASE_MANIFEST_BUILD_443_0.json\`.
