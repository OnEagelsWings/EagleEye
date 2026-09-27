# EagleEye — Build 445

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 445 is the **Phase-20 Data Acquisition Hard Checkpoint**.

## What this checkpoint evaluates

The gate qualifies the three public acquisition paths implemented in Builds 441–444:

- controlled Surface-Web retrieval;
- live public News-feed acquisition;
- controlled Public-Social acquisition.

It separates four distinct claims:

1. implementation;
2. deterministic engineering qualification;
3. external non-fixture validation;
4. production readiness.

A deterministic CI pass is not treated as real-world validation.

## Expected fresh-install result

On CI or a fresh installation with no real external validation history:

- engineering result: `pass`
- external result: `hold`
- overall result: `hold`
- data acquisition gate pass: `false`

That is the correct fail-closed state.

## What counts as real external validation

Fixture and replay runs do not count.

The gate requires at least one successful non-fixture run for each path:

- Surface: Build-442 explicit external validation;
- News: Build-443 live public ingestion;
- Public Social: Build-444 live public ingestion.

Only after all three are present can Build 445 return an overall `pass`.

Even then, EagleEye does **not** claim production readiness.

## Known open integration items

Build 445 deliberately reports two remaining gaps:

- Build 439 does not yet route News/Social collection tasks into the specialized 443/444 live adapters;
- retrieval has logical isolation but not OS process/container isolation.

The first is the main target for **Build 446 — Live AI Investigation Loop**.

## Qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build445_integrated.py
```

Case-specific API:

```
POST /api/build445/cases/{case_id}/qualification/run
```

Status:

```
GET /api/build445/qualification/status
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
py -3 EAGLEEYE_PRO_445_0.py
```

Linux/macOS:

```bash
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
```

See `README_BUILD_445_0.md`, `BUILD_445_CASE_TEST.md` and `RELEASE_MANIFEST_BUILD_445_0.json`.

Current roadmap:

- 445 Data Acquisition Hard Checkpoint
- 446 Live AI Investigation Loop
- 447 Evidence → Claims → Dossier Closure
- 448 Investigator Workspace
- 449 Human Review / Team Workflow
- 450 Investigation Workflow Hard Checkpoint

`real_world_general_research_ready = false`

`production_release_ready = false`
