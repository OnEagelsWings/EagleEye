# EagleEye Build 382.0 – Phase 17 Overlay

Build 382 continues the approved Phase-17 plan with persistent source intelligence.

The overlay is intentionally network-silent. It adds durable Source Registry revisions, case source scope, a research-plan ledger and evidence-linked coverage/gap analysis. It does not claim connector execution, full application integration, external validation, or production readiness.

Run:

```bash
python -m unittest discover -s tests -v
python EAGLEEYE_ACCEPTANCE_BUILD_382_0.py
python tools/benchmark_build382.py
```
