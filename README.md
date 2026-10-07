# EagleEye — Build 453

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 453 adds **Historical Web Intelligence 2.0** and a **verified Recovery Basis**. See `README_BUILD_453_0.md`.

The current governed chain remains:

Acquisition → AI Dispatch → Evidence → Independent Review → Claims → Independent Review → Graph/Timeline/Synthesis → Living Dossier → Independent Dossier Review → Separate Export Approval → Authorized Export.

New in 453:

- Internet Archive CDX and Common Crawl historical index planning/import with acquisition provenance;
- ranked historical capture candidates and disappearance/change signals;
- linkage of retrieved archive pages into Build 428;
- verified SQLite recovery points and safe staged restore preparation;
- focused CI between five-build hard checkpoints.

## Install / verify

```bash
python INSTALL_EAGLEEYE_453.py
python INSTALL_EAGLEEYE_453.py --check
```

## Focused development qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build453_historical_recovery.py
```

The full research workflow is intentionally reserved for 455/460/465/... rather than repeated on every development build.

Current roadmap:

- 450 Investigation Workflow Hard Checkpoint
- 451 Retrieval isolation and scanner gate
- 452 Deterministic deployment
- 453 Historical Web Intelligence 2.0 + Recovery Basis
- 454 Cross-Reference Engine + Domain Infrastructure Intelligence
- 455 Full Operations / real-source research gate

Historical compatibility assets remain present, including `EAGLEEYE_PRO_450_0.py` and the retained checkpoint regression `test_build450_integrated.py`. The default launchers start Build 453.
