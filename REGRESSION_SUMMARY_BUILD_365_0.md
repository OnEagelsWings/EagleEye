# Regression Summary – Build 365.0

Build-365 suite: **22/22 PASS**.

Build-364 regression suite: **24/26 PASS**.

The two Build-364 failures are expected historical version assertions:
1. Build-364 version test requires runtime/schema/package `364.0/364.0.0`; Build 365 correctly reports `365.0/365.0.0`.
2. Build-364 web-health test requires health build `364.0`; Build 365 correctly reports `365.0`.

All other Build-364 remote-team, TLS policy, RBAC, session anomaly, AI, OPSEC, crawler and truthfulness tests pass.
