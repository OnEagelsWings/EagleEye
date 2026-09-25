# EagleEye — Build 438

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance. Build 438 is published for **public testing and evaluation**, not as a general production-ready release.

## Build 438 focus

Build 438 adds **Temporal / Relationship Fusion** on top of Build 437 cross-source entity resolution. It groups only identity records already connected by independently reviewed `same_entity_reviewed` links, and does so non-destructively: the original entity records and source bindings remain intact.

The fusion layer produces:
- a case-scoped timeline from explicit source timestamps and source-asserted lifecycle dates;
- a case-scoped relationship graph from explicit source relationship claims;
- provenance-preserving entity context across News, Social, Organization/Registry, archive/change-history, and existing reviewed identity links;
- review-visible temporal disagreements and unresolved relationship endpoints.

Machine-extracted news events remain candidates. Social reply/reshare links remain observation relationships unless an explicit entity relationship exists. Text co-occurrence is not converted into a relationship, temporal adjacency is not converted into causality, and Build 438 performs no automatic identity confirmation, destructive merge, truth determination, or network execution.

## External testers wanted

We are actively looking for independent testers on Windows, Linux and macOS. Please test only with synthetic, demo, or clearly public data. Do **not** use confidential investigations, credentials, secrets, or sensitive personal information.

**Repository:** https://github.com/OnEagelsWings/EagleEye  
**Testing guide:** [TESTING.md](TESTING.md)  
**Public beta feedback:** https://github.com/OnEagelsWings/EagleEye/issues/2

## Fastest Windows test

Requirements: **Python 3.12 or newer**.

```powershell
git clone https://github.com/OnEagelsWings/EagleEye.git
cd EagleEye
START_EAGLEEYE_PRO.bat
```

Alternatively, download the repository as ZIP, extract it, and double-click `START_EAGLEEYE_PRO.bat`.

Manual Windows start:

```powershell
py -3 -m pip install -e .
py -3 EAGLEEYE_PRO_438_0.py
```

## Linux / macOS

Debian/Ubuntu users may need the OS venv package before first start. If `python3 -m ensurepip --version` reports that ensurepip is unavailable, install `python3-venv` or the matching versioned package.

```bash
git clone https://github.com/OnEagelsWings/EagleEye.git
cd EagleEye
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
```

The default local address is `http://127.0.0.1:8765`. If that port is occupied, EagleEye selects another free loopback port automatically.

## Five-minute smoke test

1. Start EagleEye on a clean machine or Python environment.
2. Confirm the browser workspace opens.
3. Open `/health` and verify `ok: true` and build `438.0`.
4. Create a test/demo case and exercise the case/evidence workspace.
5. Run the Build-438 case self-test described in [BUILD_438_CASE_TEST.md](BUILD_438_CASE_TEST.md).
6. Close EagleEye completely and start it again.
7. Report PASS/FAIL and reproducible errors in the public beta issue.

## Diagnostics and tests

```bash
eagleeye --diagnose
python -m pip install -e '.[test]'
pytest -q tests/test_build438_integrated.py
```

The canonical case-specific Build-438 test uses the authenticated self-test endpoint and validates provenance-bound timeline construction, review-gated identity fusion, explicit-only relationship semantics, and the absence of automatic causality/identity/relationship inference.

## Security and release scope

- The default server binds only to loopback (`127.0.0.1`).
- No automatic external research/network execution is started on boot by Build 438.
- Reviewed same-entity links are used as a non-destructive view; source records are retained.
- Temporal conflicts remain review items; Build 438 does not decide which source is true.
- Relationship edges require explicit source assertions; text co-occurrence does not create edges.
- Build 438 is a Phase-19 engineering build; broad live-research/general production readiness is **not** claimed.

See `README_BUILD_438_0.md` and `RELEASE_MANIFEST_BUILD_438_0.json` for the engineering scope.
