# EagleEye — Build 440

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance. Build 440 is the **Phase-19 hard engineering checkpoint** and is published for testing and evaluation, not as a general production-ready release.

## Build 440 focus

Build 440 qualifies the integrated chain created in Builds 421–439 rather than adding another broad feature layer.

The checkpoint verifies:

- source registration, provenance-aware acquisition records and content storage;
- source-health tracking, crawl-task planning and prioritisation;
- change detection and archive-history intake;
- News ingest/extraction/provenance;
- public-social normalization;
- organization and registry intelligence;
- separately approved isolated Tor research;
- surface/onion correlation;
- cross-source entity resolution;
- temporal/relationship fusion;
- the human-authorized AI Investigation Loop from plan through synthesis.

A dedicated qualification case also executes the synthetic Build-439 end-to-end path.

## What a PASS means

A Build-440 \`qualification_result: pass\` means the **Phase-19 engineering checkpoint passed**.

It does not mean that EagleEye has complete live collection or production readiness.

The checkpoint deliberately reports:

- \`live_collection_complete: false\`
- \`real_world_general_research_ready: false\`
- \`production_release_ready: false\`

The main current blockers are concrete: Build 425 has no ordinary Surface-Web network executor; Build 429 has no News retrieval executor; Build 432 has no Public-Social retrieval executor; Build-439 crawl tasks therefore still need a separately governed external retrieval adapter. The Tor path is different: it is implemented only through the isolated worker with its own approval and confirmation boundary.

## External testers wanted

We are looking for independent testing on Windows, Linux and macOS. Use only synthetic, demo, or clearly public data. Do not use confidential investigations, credentials, secrets, or sensitive personal information.

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
py -3 EAGLEEYE_PRO_440_0.py
\`\`\`

## Linux / macOS

Debian/Ubuntu users may need \`python3-venv\` before the first start.

\`\`\`bash
git clone https://github.com/OnEagelsWings/EagleEye.git
cd EagleEye
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
\`\`\`

The default local address is \`http://127.0.0.1:8765\`. If the port is occupied, EagleEye selects another free loopback port automatically.

## Checkpoint test

1. Start EagleEye.
2. Open \`/health\` and verify build \`440.0\`.
3. Create a dedicated synthetic/demo qualification case.
4. Run the authenticated Build-440 qualification described in [BUILD_440_CASE_TEST.md](BUILD_440_CASE_TEST.md).
5. A technical PASS must still report live-collection and production readiness as false.
6. Restart EagleEye and verify the workspace starts cleanly again.

## Diagnostics and tests

\`\`\`bash
eagleeye --diagnose
python -m pip install -e '.[test]'
pytest -q tests/test_build440_integrated.py
\`\`\`

The canonical Build-440 suite verifies fail-closed qualification, full Phase-19 component integrity, the Build-439 end-to-end case path, truthful live-capability disclosure, authority boundaries, qualification-record integrity and case isolation.

## Next priority

After Build 440, the highest-value engineering work is a controlled ordinary-surface retrieval adapter plus external end-to-end validation. Additional analytical layers should not be treated as a substitute for closing this data-acquisition gap.

See \`README_BUILD_440_0.md\` and \`RELEASE_MANIFEST_BUILD_440_0.json\` for the checkpoint contract.
