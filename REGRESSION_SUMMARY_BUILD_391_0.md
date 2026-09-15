# Regression Summary — Build 391.0

## Phase 17 integrated regression

The integrated Build 384–391 test line was executed in two reproducible blocks because the full combined run exceeds the execution window.

- Tests collected: **112**
- Passed unchanged: **98**
- Expected historical release-boundary failures: **14**
- Functional regressions: **0**

All 14 failures are historical assertions that intentionally expect an older current runtime/package version or older current web launcher (`app384` … `app390`). The active release is Build 391.0, so these tests correctly fail their old release-boundary expectations. No functional test in the Phase-17 data, execution, evidence, corroboration, or synthesis path failed.

### Boundary classification

- Build 384: version/package boundary + current-launcher boundary
- Build 385: version/package boundary + current-launcher boundary
- Build 386: version/package boundary + current-launcher boundary
- Build 387: version/package boundary + current-launcher boundary
- Build 388: version/package boundary + current-launcher boundary
- Build 389: version/package boundary + current-launcher boundary
- Build 390: version/package boundary + current-launcher boundary

## Build 391 delta qualification

- Build-391 integration tests: **18/18 PASS**
- Build-391 acceptance: **16/16 PASS**
- Build-391 synthesis benchmark: **1000/1000 PASS**
- Benchmark violations: **0**
- Legacy `hypotheses_112` rows created by Build 391: **0**
- Automatic jobs created by Build 391: **0**
- Automatic execution grants created by Build 391: **0**
- Automatic evidence promotions created by Build 391: **0**

## Historical predecessor line

Build 391 inherits the qualified Build-390 predecessor receipt. Build 390 already preserved the earlier Build-360–380 professional-pilot qualification with zero functional regressions. Build 391 does not claim that those historical release-boundary assertions become current again.

## Result

**PASS — 0 functional regressions.** Build 391 changes the current release boundary and adds an epistemic synthesis layer only. It does not alter crawler/network execution authority, evidence promotion authority, identity merge authority, or production-release status.
