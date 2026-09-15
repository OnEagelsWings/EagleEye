# Regression Summary – Build 364.0

Build-363 regression suite: **18/20 PASS**.

The two failures are expected historical version assertions:
1. Build-363 version test requires runtime/schema/package `363.0/363.0.0`; Build 364 correctly reports `364.0/364.0.0`.
2. Build-363 web-health test requires health build `363.0`; Build 364 correctly reports `364.0`.

All other Build-363 Object Store, Team Search, AI, OPSEC, crawler and truthfulness tests pass.
