# EagleEye — Build 449

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 449 adds the formal **Human Review & Team Workflow** on top of the Build-448 Investigator Workspace.

## Current investigation chain

```
Recherche
  -> AI Investigation
  -> Acquisition
  -> Evidence
  -> Team Review
  -> Claims / Counterevidence
  -> Team Review
  -> Graph & Timeline
  -> Synthesis
  -> Living Dossier
  -> Dossier Review
  -> Export Approval
  -> Export
```

## Primary workspace

The eight-view case-first workspace remains:

- Übersicht
- Recherche
- AI-Ermittlung
- Evidence
- Claims & Hypothesen
- Graph & Timeline
- Dossier
- OPSEC & Team

Build 449 integrates the review queue into these views rather than adding another navigation layer.

## Four-eyes review

Formal review tasks are available for:

- Evidence
- Claims
- Dossier revisions
- Dossier export approval

Rules:

- requester and reviewer must be different users;
- Claim/Dossier creator and reviewer must be different users;
- optional named reviewer assignment is case-scoped;
- reviewer explicitly claims the task;
- object changes after request make the review stale;
- rationale is mandatory;
- comments, challenges, agreement and counter-hypotheses are preserved as review discussion;
- no review action determines objective truth automatically.

## Dossier release

A current Build-449 dossier release requires:

1. accepted human-reviewed Claims;
2. independent Dossier approval;
3. a separate export-review request;
4. independent export approval;
5. an authorized executor different from the approving reviewer.

The current Build-449 app removes the direct Build-447 Evidence/Claim/Dossier review and export mutation routes. Older build apps retain them only for compatibility.

## UI and QA

Build 448's UI audit remains active. Build 449 adds team-review integration tests and is included in the current Phase-19/20 regression chain.

## Safety and analytical boundaries

Unchanged:

- no generic AI network authority;
- no automatic Evidence acceptance;
- no automatic Claim acceptance;
- no automatic truth determination;
- no automatic Dossier publication;
- production readiness remains false.

## Qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build449_integrated.py
```

## Start

Python **3.12+** is required.

Windows:

```powershell
START_EAGLEEYE_PRO.bat
```

Manual:

```powershell
py -3 -m pip install -e .
py -3 EAGLEEYE_PRO_449_0.py
```

Linux/macOS:

```bash
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
```

See `README_BUILD_449_0.md`, `BUILD_449_CASE_TEST.md`, and `RELEASE_MANIFEST_BUILD_449_0.json`.

Current roadmap:

- 449 Human Review / Team Workflow
- 450 Investigation Workflow Hard Checkpoint
