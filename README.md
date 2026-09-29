# EagleEye — Build 447

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 447 implements **Evidence → Claims → Dossier Closure**.

## What changed

The current Phase-20 flow is now closed from acquisition into a reviewable Living Dossier:

```
Acquisition
  -> Evidence
  -> Claims
  -> Hypotheses / Counterevidence
  -> Evidence Matrix
  -> Synthesis
  -> Living Dossier
```

Build 447 does not convert observations into facts automatically.

## Evidence Viewer and source snapshots

Build 447 synchronizes case-scoped Build-423 observations and binds them to their Build-421/422/423 provenance. Where available, Build-429 News and Build-432 Social metadata are attached.

Each Evidence item records:

- source ID and source snapshot;
- acquisition event;
- content ID and SHA-256;
- canonical target;
- media type;
- duplicate state;
- descriptive News/Social context;
- underlying record hashes.

Raw payloads are not duplicated into the Build-447 ledger.

Evidence begins `unreviewed` and requires explicit human review.

## Claim ↔ Evidence model

Claims are explicit propositions, not AI findings.

A Claim requires at least one human-accepted supporting Evidence item.

Links are explicitly classified as:

- support;
- contradict;
- context.

Counterevidence is retained. A Claim with contradictory Evidence cannot be created without an uncertainty note.

Claim review is a separate human action. Only `accepted_for_dossier` Claims can enter a Living Dossier revision.

No automatic probability or truth score is assigned.

## Living Dossier revisions

Each dossier build creates a numbered revision containing:

- case context;
- accepted Claims;
- Claim↔Evidence matrix;
- Counterevidence;
- uncertainty register;
- Build-418 hypothesis/counterevidence matrix when a Build-439 loop is bound;
- latest Build-419 synthesis;
- Build-446 acquisition execution references;
- source snapshots and content hashes.

Every revision begins as:

`draft_for_review`

Human review is required before export.

## Export

Approved revisions can be exported as:

- JSON
- DOCX
- PDF
- manifest with hashes
- ZIP Case Package

The package carries references, provenance and integrity hashes. Raw source payloads are not automatically copied into it.

Formal four-eyes review/export workflow is intentionally left for Build 449.

## Explicit confirmations

- Evidence review: `REVIEW EVIDENCE 447`
- Claim review: `REVIEW CLAIM 447`
- Dossier approval: `APPROVE DOSSIER 447`
- Dossier export: `EXPORT DOSSIER 447`

The confirmations are intentionally separate.

## Integrity

Build 447 checks both its own records and the provenance chain underneath them.

If a referenced Build-421/422/423 record changes after Evidence sync, integrity becomes invalid.

If an Evidence item changes after it has been linked to a Claim, the Claim link is no longer considered intact.

Dossier approval/export fail closed on integrity errors.

## Still not claimed

- automatic truth determination
- automatic Claim acceptance
- automatic Dossier publication
- unrestricted AI network authority
- formal four-eyes workflow for Build-447 export
- production readiness

Therefore:

- `real_world_general_research_ready = false`
- `production_release_ready = false`

## Qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build447_integrated.py
```

Case-specific deterministic qualification:

```
POST /api/build447/cases/{case_id}/selftest
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
py -3 EAGLEEYE_PRO_447_0.py
```

Linux/macOS:

```bash
chmod +x START_EAGLEEYE_PRO.sh
./START_EAGLEEYE_PRO.sh
```

See `README_BUILD_447_0.md`, `BUILD_447_CASE_TEST.md` and `RELEASE_MANIFEST_BUILD_447_0.json`.

Current roadmap:

- 447 Evidence → Claims → Dossier Closure
- 448 Investigator Workspace
- 449 Human Review / Team Workflow
- 450 Investigation Workflow Hard Checkpoint
