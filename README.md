# EagleEye — Build 446

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 446 implements the **Live AI Investigation Loop** integration identified as the main open gap by Build 445.

## What changed

A human-authorized Build-439 investigation loop can now prepare reviewed per-source dispatch tickets and route each approved source to the correct acquisition path:

- Surface -> Build 442 hardened retrieval
- News -> Build 443 public News acquisition
- Public Social -> Build 444 controlled Social acquisition

The AI loop still does not receive generic network authority.

## Human control remains explicit

A Build-439 loop must already be active.

Every source must already be present in the loop's `allowed_source_ids`.

Every live dispatch retains its own path-specific confirmation:

- Surface: `SURFACE442_LIVE`
- News: `NEWS443_LIVE`
- Social: `SOCIAL444_LIVE`

There is no global "run all" confirmation and no automatic live batch execution.

## Conservative routing

- `social` sources require an explicit reviewed Social adapter.
- `rss` and `news` sources route to News.
- `api` routes to News only when explicit News-feed capabilities are declared; otherwise it routes to Surface.
- other reviewed public HTTP(S) sources route to Surface.
- non-public access modes require human review.
- Tor remains outside Build 446 and retains its separate isolated-worker approval boundary.

## Closed analytical loop

After successful acquisition, EagleEye refreshes:

```
Acquisition
  -> Entity Resolution 437
  -> Temporal / Relationship Fusion 438
  -> Hypothesis / Counterevidence Matrix 418
  -> Synthesis 419
```

This does not promote hypotheses to fact, determine truth or automatically launch another acquisition wave.

## Build 445 relationship

Build 445 remains a historical hard checkpoint.

Build 446 closes the specific integration gap:

`build439_specialized_news_social_adapter_dispatch_not_implemented`

It does not retroactively rewrite an earlier Build-445 report and does not convert missing external validation into a PASS.

## Current limitations

Still not claimed:

- OS process/container retrieval isolation
- authenticated/private collection
- broad external platform coverage
- automatic social-graph expansion
- production readiness

Therefore:

- `real_world_general_research_ready = false`
- `production_release_ready = false`

## Qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build446_integrated.py
```

Case-specific deterministic qualification:

```
POST /api/build446/cases/{case_id}/selftest
```

Prepare reviewed dispatch tickets:

```
POST /api/build446/loops/{loop_id}/dispatches/prepare
```

Execute exactly one ticket with the confirmation specified on that ticket:

```
POST /api/build446/dispatches/{dispatch_id}/execute
```

## Start

Python **3.12+** is required.

Windows:

```powershell
START_EAGLEEYE_PRO.bat
```

Manual start:

```powershell
py -3 -m pip install -e .
py -3 EAGLEEYE_PRO_446_0.py
```

Linux/macOS:

```bash
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
```

See `README_BUILD_446_0.md`, `BUILD_446_CASE_TEST.md` and `RELEASE_MANIFEST_BUILD_446_0.json`.

Current roadmap:

- 446 Live AI Investigation Loop
- 447 Evidence -> Claims -> Dossier Closure
- 448 Investigator Workspace
- 449 Human Review / Team Workflow
- 450 Investigation Workflow Hard Checkpoint
