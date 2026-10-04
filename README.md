# EagleEye — Build 450

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 450 is the **Investigation Workflow Hard Checkpoint**.

The current governed chain is:

Acquisition → AI Dispatch → Evidence → Independent Review → Claims → Independent Review → Graph/Timeline/Synthesis → Living Dossier → Independent Dossier Review → Separate Export Approval → Authorized Export.

The checkpoint distinguishes engineering qualification from external field validation and production release. A deterministic engineering PASS does not certify factual truth, external endpoint reliability or production readiness.

## Qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build450_integrated.py
```

## Start

```bash
python EAGLEEYE_PRO_450_0.py
```

Current roadmap:

- 450 Investigation Workflow Hard Checkpoint
- next phase is determined from checkpoint findings

See `README_BUILD_450_0.md`, `BUILD_450_CASE_TEST.md`, and `RELEASE_MANIFEST_BUILD_450_0.json`.
