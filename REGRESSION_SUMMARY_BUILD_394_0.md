# EagleEye Build 394.0 Regression Summary

- Scope: integrated Phase-17 tests Build 384–394
- Result: PASS with expected historical release boundaries
- Passed: 158 / 178
- Expected historical version/launcher boundaries: 20
- Functional regressions: 0
- Build 394 tests: 21 / 21 PASS
- Code fingerprint: `3244ac06d483f99561cf9b02c06e99f4eb744f1fb2e8fb88d3289e78351f2deb`
- Historical Build 360–380 qualification: inherited through the qualified Build-393 predecessor receipt; not re-executed in this delta qualification.

The 20 non-passing legacy assertions are the two intentional release-boundary assertions in each Build 384–393 suite: the old build/package/schema number and the old current launcher/web-app pointer. No functional test from those suites failed.
