# Build 400.0 Regression Summary

## Full current-tree rerun

- Total tests: **1175**
- Passed: **1119/1175**
- Failed assertions: **56**
- Classified historical release boundaries: **56**
- Functional regressions: **0**
- Build 400 integrated: **11/11 PASS**

## By major line

- Builds 360–380: **792/822 PASS**; 30 superseded build/schema/health/server/launcher expectations; **0 functional regressions**.
- Phase-17 suites 381–400: **327/353 PASS**; 26 superseded version/current-launcher expectations; **0 functional regressions**.

## Classification

Every failing assertion was inspected. The failures are limited to tests that intentionally pin an older build/package/schema/health value or an older `current` web-app/launcher target. In Build 400 those values correctly resolve to 400.0. No current functional behavior assertion failed.

This classification does not imply external production qualification. The real Build-398 model/human holdout and Build-399 72-hour Windows/Firefox soak remain pending.
