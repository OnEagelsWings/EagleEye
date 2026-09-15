# Regression Summary — Build 360.0

- Current Build-360 suite: **21/21 PASS**.
- Build-359 regression suite: **25/27 PASS**.
- The two Build-359 failures are expected version-boundary assertions: Build-359 `version_status()` no longer reports coherence after the canonical runtime/package version advances to 360.0, and the historical Build-359 web test expects `/health` to return `359.0` rather than `360.0`.
- Functional Build-359 RBAC, four-eyes export, crawler quotas, lease recovery, voice boundaries, membership isolation and access-chain tests remain green.
- Pillow emits deprecation warnings for `Image.getdata()` in the inherited local visual descriptor implementation; this is not a Build-360 functional failure but should be remediated before Pillow 14.
