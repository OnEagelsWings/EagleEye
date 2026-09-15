# EagleEye Build 383.0 – Phase 17 Overlay

Build 383 adds the governed **Source Planner v1** on top of Builds 381–382.

The planner translates missions into transparent source-class proposals, selects acquisition templates, ranks catalogued sources and surfaces data-acquisition gaps. Mission inference is advisory until exact analyst confirmation. All work remains network-silent and non-executing.

Run:

```bash
python -m unittest discover -s tests -v
python EAGLEEYE_ACCEPTANCE_BUILD_383_0.py
python tools/benchmark_build383.py
```
