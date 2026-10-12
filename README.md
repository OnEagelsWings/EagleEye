# EagleEye — Build 457

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 457 is the **Workspace Reliability + UI Functional Closure** focused development build. It retains the passed Build-455 hard checkpoint and the Build-456 multilingual/entity-lineage layer while closing operator-workspace cycle and dispatch-budget correctness gaps. See `ROADMAP_457_460_CONSOLIDATED.md`.

The governed chain is:

Acquisition → AI Dispatch → Evidence → Independent Review → Claims → Independent Review → Graph/Timeline/Synthesis → Living Dossier → Independent Dossier Review → Separate Export Approval → Authorized Export → Recovery/Restart Verification.

Build 455 remains the retained operational hard-checkpoint baseline. Build 457 adds:

- review-only Hebrew/Arabic/Cyrillic/Latin entity and alias candidates inherited from Build 456;
- active-loop selection that is independent of the newest historical/terminal loop;
- current-cycle-only dispatch recommendations and operator actions;
- enforcement of the **remaining** authorized per-cycle dispatch budget;
- repeated per-feed boilerplate suppression for publication fingerprints;
- actionable client errors for bounded entity-scan validation;
- retention of the Build-455 governed live-research/recovery baseline.

## Install / verify

```bash
python INSTALL_EAGLEEYE_457.py
python INSTALL_EAGLEEYE_457.py --check
```

## Focused Build-457 qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build457_workspace_reliability.py
```

Build 457 intentionally does not rerun the complete repository or live operational gate. The full five-build regression remains scheduled for Build 460.

Current roadmap:

- 450 Investigation Workflow Hard Checkpoint
- 451 Retrieval isolation and content-risk gate
- 452 Deterministic deployment
- 453 Historical Web Intelligence 2.0 + Recovery Basis
- 454 Cross-Reference Engine + Domain Infrastructure Intelligence
- 455 Full Operations / Real-Source Research Gate
- 456 Multilingual Entity/Alias Resolution + canonical Source-Lineage
- 457 Workspace Reliability + UI Functional Closure
- 458 Document Intelligence 2.0 + precise Evidence anchors
- 459 Integration Burn-in + Field Workflow Readiness
- 460 Complete Real-Research / UI / Recovery Hard Checkpoint
- 461–464 product/security packaging, external connector/media/team qualification
- 465 Release-Candidate / external-beta hard checkpoint

Production release remains separate from operational research usability.


## Retained checkpoint regression contract

The retained Phase-20 checkpoint reference remains available for compatibility checks:

```bash
pytest -q tests/test_build450_integrated.py
```
