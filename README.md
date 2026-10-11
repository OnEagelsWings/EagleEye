# EagleEye — Build 455

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 455 is the **Full Operations / Real-Source Research Hard Checkpoint**. See `README_BUILD_455_0.md`.

The governed chain is:

Acquisition → AI Dispatch → Evidence → Independent Review → Claims → Independent Review → Graph/Timeline/Synthesis → Living Dossier → Independent Dossier Review → Separate Export Approval → Authorized Export → Recovery/Restart Verification.

Build 455 validates:

- the retained Build-450 governed workflow;
- Build-451 process-isolated retrieval and content-risk boundary;
- Build-452 isolated deterministic runtime;
- Build-453 recovery verification;
- Build-454 public infrastructure and explainable XRef integration;
- a bounded live public-source research case;
- physical JSON/DOCX/PDF/manifest/ZIP hash integrity;
- actual close/reopen persistence and reference integrity;
- the full five-build regression cadence.

## Install / verify

```bash
python INSTALL_EAGLEEYE_455.py
python INSTALL_EAGLEEYE_455.py --check
```

## Hard-checkpoint qualification

```bash
python -m pip install -e '.[test]'
python tools/run_checkpoint_regression455.py
python tools/run_checkpoint_regression455.py --phase18-20
python tools/build455_live_public_gate.py
```

The live qualification is intentionally bounded to stable public reference sources. It is not a general-purpose autonomous collection command.

The five-build regression runner keeps historical functional tests active while deselecting only exact legacy assertions that require an old build to remain the current runtime/server/installer, or predate the canonical case-identity boundary. Every exclusion is enumerated with a reason in `tools/CHECKPOINT_REGRESSION_EXCLUSIONS_455.json`; no Build-455 test can be excluded by that policy.

Current roadmap:

- 450 Investigation Workflow Hard Checkpoint
- 451 Retrieval isolation and content-risk gate
- 452 Deterministic deployment
- 453 Historical Web Intelligence 2.0 + Recovery Basis
- 454 Cross-Reference Engine + Domain Infrastructure Intelligence
- 455 Full Operations / Real-Source Research Gate
- 456 Multilingual Entity/Alias Resolution + canonical Source-Lineage
- 457 Document Intelligence 2.0 + precise Evidence anchors
- 458 Organization/Ownership/Registry Intelligence + connector qualification
- 459 Graph Analytics 2.0 + Red-Team/Local-AI integration
- 460 Serious Beta / repeated full operational gate
- 461–464 product/security packaging, external connector/media/team qualification
- 465 Release-Candidate / external-beta hard checkpoint

Production release remains separate from operational research usability.
