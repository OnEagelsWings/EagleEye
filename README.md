# EagleEye — Build 458

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 458 is the **Document Intelligence 2.0** focused development build. It retains Build-457 workspace reliability while adding page/block-based PDF/text source anchors, manual extraction review and hash-bound Claim citations. See `README_BUILD_458_0.md`.

The governed chain is:

Acquisition → AI Dispatch → Evidence → Independent Review → Claims → Independent Review → Graph/Timeline/Synthesis → Living Dossier → Independent Dossier Review → Separate Export Approval → Authorized Export → Recovery/Restart Verification.

Build 455 remains the retained operational baseline. Build 456 adds:

- review-only Hebrew/Arabic/Cyrillic/Latin entity and alias candidates;
- conservative cross-script similarity with no automatic identity confirmation;
- human-reviewed source-family and independence-group overrides;
- Claim-level raw-mention vs independent-origin reporting;
- exact-payload deduplication so republications do not inflate corroboration;
- retention of the Build-455 governed live-research/recovery baseline.

## Install / verify

```bash
python INSTALL_EAGLEEYE_458.py
python INSTALL_EAGLEEYE_458.py --check
```

## Focused Build-456 qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build457_workspace_reliability.py
```

Build 458 intentionally does not rerun the complete repository or live operational gate. The full five-build regression remains scheduled for Build 460.

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
