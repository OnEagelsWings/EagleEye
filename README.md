# EagleEye — Build 439

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance. Build 439 is published for **public testing and evaluation**, not as a general production-ready release.

## Build 439 focus

Build 439 adds the **AI Investigation Loop**, the final major functional step before the Phase-19 hard checkpoint at Build 440.

After explicit human authorization, the loop coordinates the existing EagleEye stack:

- investigation planning and bounded research waves;
- Phase-19 registered-source selection;
- bounded crawl-task planning and prioritisation;
- observation of evidence intake;
- cross-source entity resolution;
- temporal and relationship fusion;
- multi-agent analysis;
- working hypotheses, counterevidence and gap analysis;
- reviewable investigation synthesis.

The exact activation phrase is:

\`AUTHORIZE INVESTIGATION LOOP\`

Human GO activates only the bounded analytical orchestration envelope. Build 439 does not grant itself direct network authority. Ordinary web retrieval still requires the separately governed retrieval path; Tor/onion material stays behind the isolated Tor worker and its separate approval boundary.

## External testers wanted

We are actively looking for independent testers on Windows, Linux and macOS. Please test only with synthetic, demo, or clearly public data. Do **not** use confidential investigations, credentials, secrets, or sensitive personal information.

**Repository:** https://github.com/OnEagelsWings/EagleEye  
**Testing guide:** [TESTING.md](TESTING.md)  
**Public beta feedback:** https://github.com/OnEagelsWings/EagleEye/issues/2

## Fastest Windows test

Requirements: **Python 3.12 or newer**.

\`\`\`powershell
git clone https://github.com/OnEagelsWings/EagleEye.git
cd EagleEye
START_EAGLEEYE_PRO.bat
\`\`\`

Manual Windows start:

\`\`\`powershell
py -3 -m pip install -e .
py -3 EAGLEEYE_PRO_439_0.py
\`\`\`

## Linux / macOS

Debian/Ubuntu users may need the OS venv package before first start. If \`python3 -m ensurepip --version\` reports that ensurepip is unavailable, install \`python3-venv\` or the matching versioned package.

\`\`\`bash
git clone https://github.com/OnEagelsWings/EagleEye.git
cd EagleEye
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
\`\`\`

The default local address is \`http://127.0.0.1:8765\`. If that port is occupied, EagleEye selects another free loopback port automatically.

## Five-minute smoke test

1. Start EagleEye on a clean machine or Python environment.
2. Confirm that the browser workspace opens.
3. Open \`/health\` and verify \`ok: true\` and build \`439.0\`.
4. Create a synthetic/demo case.
5. Run the Build-439 case self-test described in [BUILD_439_CASE_TEST.md](BUILD_439_CASE_TEST.md).
6. Confirm that the test reports human-GO enforcement, bounded task planning and no direct network execution.
7. Close EagleEye completely and start it again.

## Diagnostics and tests

\`\`\`bash
eagleeye --diagnose
python -m pip install -e '.[test]'
pytest -q tests/test_build439_integrated.py
\`\`\`

The canonical Build-439 suite verifies the full plan-to-synthesis loop, explicit GO, Phase-19 source scoping, public crawl-task planning, Tor separation, hypothesis discipline, integrity and case isolation.

For regression work on the immediately preceding fusion layer, the retained artifacts are \`EAGLEEYE_PRO_438_0.py\` and \`tests/test_build438_integrated.py\`.

## Security and release scope

- Default server binding remains loopback-only.
- No Build-439 network execution starts automatically or on boot.
- Build 439 cannot autonomously enlarge the approved source scope.
- Crawl tasks are planning/intake contracts, not proof that retrieval occurred.
- Working hypotheses are not findings and remain human-reviewable.
- Counterevidence and unresolved gaps stay first-class.
- Build 437 reviewed identity links remain non-destructive.
- Build 438 temporal/relationship assertions retain provenance.
- Production readiness remains **false**.

Build 440 is the next hard checkpoint. It should qualify the complete Phase-19 investigation path rather than introduce another large capability.

See \`README_BUILD_439_0.md\` and \`RELEASE_MANIFEST_BUILD_439_0.json\` for the engineering scope.
