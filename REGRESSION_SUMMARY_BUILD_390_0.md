# Regression Summary — Build 390.0

## Phase 17 integrated regression

- Tests executed across Builds 381–390: **193**
- Passed unchanged: **181**
- Expected historical release-boundary failures: **12**
- Functional regressions: **0**

The 12 expected failures are old Build-384–389 assertions that require their historical runtime/package version or historical current launcher. Build 390 correctly reports 390.0 and points the current launcher/server to app390.

## Historical predecessor

Build 389 remains the qualified predecessor. Its release manifest records zero functional regressions and preserves the prior Build-360–380 professional-pilot qualification chain.

## Build 390

- Dedicated tests: 16/16 PASS
- Acceptance: 14/14 PASS
- Benchmark: 1000/1000 PASS, 0 violations
- Production release ready: false
