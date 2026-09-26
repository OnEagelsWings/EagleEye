# EagleEye — Build 441

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance. Build 441 starts **Phase 20** by adding controlled execution for ordinary public Surface-Web crawl tasks.

## Build 441 focus

Build 440 established that the Phase-19 engineering chain was internally coherent but still lacked ordinary live Surface-Web execution. Build 441 closes that specific gap.

Existing Build-425 crawl tasks can now be executed through a tightly bounded Surface-Web adapter:

- public HTTP(S) GET only;
- exact registered source host only;
- exact task host allowlist;
- globally routable DNS addresses only;
- DNS-to-IP pinning for the actual connection;
- HTTPS SNI and certificate validation;
- fail-closed robots.txt enforcement;
- same-host redirects only, maximum three;
- hard timeout and response-size limits;
- safe content-type allowlist;
- no credentials, cookies, forms, uploads, writes or JavaScript;
- no environment proxy inheritance;
- no private/local-network or onion targets;
- no autonomous source or scope expansion.

Results are ingested through the existing Build-425 -> Build-422/423 provenance path.

## Human authorization

A permitted case user can explicitly run a planned task with:

\`SURFACE441_LIVE\`

Tasks created by an already active, explicitly human-authorized Build-439 investigation loop can also use that existing loop authorization. Build 441 still revalidates case binding, source allowlist, target host, DNS and robots policy before any public request.

## Phase-20 readiness

Build 441 changes one major readiness item:

- controlled ordinary Surface-Web retrieval: **implemented**

Still incomplete:

- dedicated News retrieval adapter;
- dedicated Public-Social retrieval adapter;
- broader external end-to-end validation;
- production hardening.

Therefore EagleEye still reports:

- \`general_live_collection_complete: false\`
- \`real_world_general_research_ready: false\`
- \`production_release_ready: false\`

## External testers wanted

Use only synthetic, demo, or clearly public data. Do not use confidential investigations, credentials, secrets, or sensitive personal information during beta testing.

**Repository:** https://github.com/OnEagelsWings/EagleEye  
**Testing guide:** [TESTING.md](TESTING.md)  
**Public beta feedback:** https://github.com/OnEagelsWings/EagleEye/issues/2

## Windows

Requirements: **Python 3.12 or newer**.

\`\`\`powershell
git clone https://github.com/OnEagelsWings/EagleEye.git
cd EagleEye
START_EAGLEEYE_PRO.bat
\`\`\`

Manual start:

\`\`\`powershell
py -3 -m pip install -e .
py -3 EAGLEEYE_PRO_441_0.py
\`\`\`

## Linux / macOS

Debian/Ubuntu users may need \`python3-venv\` before the first start.

\`\`\`bash
git clone https://github.com/OnEagelsWings/EagleEye.git
cd EagleEye
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
\`\`\`

The default workspace address is \`http://127.0.0.1:8765\`.

## Qualification

For the deterministic no-network case test:

\`\`\`
POST /api/build441/cases/{case_id}/retrieval/selftest
\`\`\`

Or run:

\`\`\`bash
python -m pip install -e '.[test]'
pytest -q tests/test_build441_integrated.py
\`\`\`

The Build-441 suite covers successful provenance-bound retrieval replay, robots blocking, private-IP/SSRF rejection, cross-host redirect blocking, unsafe media blocking, fixture live-execution denial, Build-439 loop authorization and current launcher/version contracts.

The Build-440 hard checkpoint remains retained as the Phase-19 baseline.

See \`README_BUILD_441_0.md\`, \`BUILD_441_CASE_TEST.md\` and \`RELEASE_MANIFEST_BUILD_441_0.json\`.
