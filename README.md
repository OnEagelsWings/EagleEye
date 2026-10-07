# EagleEye — Build 454

EagleEye is a local-first, evidence- and provenance-oriented OSINT/investigation workspace with human-governed AI assistance.

Build 454 adds the **Cross-Reference Engine** and **Public Domain Infrastructure Intelligence**. See `README_BUILD_454_0.md`.

The governed chain remains:

Acquisition → AI Dispatch → Evidence → Independent Review → Claims → Independent Review → Graph/Timeline/Synthesis → Living Dossier → Independent Dossier Review → Separate Export Approval → Authorized Export.

New in 454:

- RDAP, public DNS, Certificate Transparency, IP-RDAP and RIPEstat lookup planning;
- payload imports bound to existing acquisition/content provenance and exact SHA-256;
- Entity ↔ Domain cross references;
- shared-anchor and shared-public-infrastructure candidates;
- historical-web ↔ Entity/Domain correlation;
- explainable candidate paths and next-pivot recommendations;
- explicit guardrails against interpreting shared hosting/DNS/CDN infrastructure as common ownership.

## Install / verify

```bash
python INSTALL_EAGLEEYE_454.py
python INSTALL_EAGLEEYE_454.py --check
```

## Focused development qualification

```bash
python -m pip install -e '.[test]'
pytest -q tests/test_build454_xref_infrastructure.py
```

The complete research workflow remains on the five-build cadence: 455/460/465/....

Current roadmap:

- 450 Investigation Workflow Hard Checkpoint
- 451 Retrieval isolation and scanner gate
- 452 Deterministic deployment
- 453 Historical Web Intelligence 2.0 + Recovery Basis
- 454 Cross-Reference Engine + Domain Infrastructure Intelligence
- 455 Full Operations / real-source research gate

Historical compatibility assets remain present, including `EAGLEEYE_PRO_450_0.py` and the retained checkpoint regression `test_build450_integrated.py`. The default launchers start Build 454.
