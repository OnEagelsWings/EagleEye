# EagleEye — Build 452

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 452 adds **Deterministic Local Deployment** on top of the Build-451 retrieval-isolation work and consolidates the outstanding Build-450 hardening changes. See `README_BUILD_452_0.md` for the installer/runtime contract, deadline fixes and qualification limits.

The current governed chain remains:

Acquisition → AI Dispatch → Evidence → Independent Review → Claims → Independent Review → Graph/Timeline/Synthesis → Living Dossier → Independent Dossier Review → Separate Export Approval → Authorized Export.

Engineering qualification, real-source research usability, independent external validation and production readiness remain separate decisions.

## Install / verify

```bash
python INSTALL_EAGLEEYE_452.py
python INSTALL_EAGLEEYE_452.py --check
```

The default launchers install into `.eagleeye-runtime` when required and then run the installed package with Python isolated mode.

## Development qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build452_deployment.py
```

Current roadmap:

- 450 Investigation Workflow Hard Checkpoint
- 451 Retrieval isolation and scanner gate
- 452 Deterministic deployment
- 453 Recovery and rollback
- 454 Reliability / operational integration
- 455 Full Operations / real-source research gate

The retained historical launchers remain available for compatibility, including `EAGLEEYE_PRO_450_0.py`. The default launchers start Build 452.
