# EagleEye — Build 448

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 448 introduces the **Investigator Workspace** and a recurring **UI functionality audit**.

## Primary workflow

The current operator path is now visible as one coherent chain:

```
Recherche
  -> AI Investigation
  -> Acquisition
  -> Evidence
  -> Claims / Counterevidence
  -> Graph & Timeline
  -> Synthesis
  -> Living Dossier
```

The previous historical workspace is retained at `/legacy` for specialized and compatibility functions.

## Simplified primary navigation

The primary UI has eight case-scoped views:

- Übersicht
- Recherche
- AI-Ermittlung
- Evidence
- Claims & Hypothesen
- Graph & Timeline
- Dossier
- OPSEC & Team

The stale “Phase 13 · Simplified AI Investigation Workspace” primary shell is no longer the current workspace.

## Functional UI

Build 448 exposes the already governed actions from Builds 439, 446 and 447 directly in the current workspace:

- create, authorize and advance bounded AI investigation loops;
- prepare source dispatches and execute one individually confirmed acquisition route;
- synchronize and review Evidence;
- create and review Claims with explicit support/contradict/context links;
- inspect hypothesis gaps and conflicts;
- inspect graph/timeline summary and latest synthesis;
- create, review and export Living Dossier revisions.

No UI control bypasses the underlying RBAC, case scope or exact confirmation phrase.

## UI audit

Build 448 records hash-bound case-scoped UI audits.

The audit checks:

- current build branding;
- eight primary views;
- responsive viewport and mobile breakpoints;
- keyboard focus styling;
- semantic main/navigation landmarks;
- accessible status feedback;
- availability of the Legacy workspace;
- visible Evidence/Claim/Dossier epistemic boundary;
- registration of all required Build-439/446/447 read and mutation routes.

Warnings additionally flag excessive initial markup, table/disclosure density and inline click handlers.

## Recurring GitHub review

`.github/workflows/ui-audit.yml` runs a scheduled weekly UI audit and can also be triggered manually.

UI-facing pull requests should additionally request GitHub Codex review when that reviewer is available in the repository.

## Safety and analytical boundaries

Still unchanged:

- no generic AI network authority;
- no automatic Evidence acceptance;
- no automatic Claim acceptance;
- no automatic truth determination;
- no automatic Dossier publication;
- production readiness remains false.

## Qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build448_integrated.py
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
py -3 EAGLEEYE_PRO_448_0.py
```

Linux/macOS:

```bash
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
```

See `README_BUILD_448_0.md`, `BUILD_448_UI_AUDIT.md` and `RELEASE_MANIFEST_BUILD_448_0.json`.

Current roadmap:

- 448 Investigator Workspace + UI Audit
- 449 Human Review / Team Workflow
- 450 Investigation Workflow Hard Checkpoint
