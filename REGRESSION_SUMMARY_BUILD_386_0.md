# Regression Summary – Build 386.0

## Current Build
- Build-386 integrated tests: **16/16 PASS**
- Acceptance: **17/17 PASS**
- GO-grant benchmark: **200/200 PASS**, 0 violations

## Phase 17 regression (381–386)
- **134/138 PASS**
- 4 expected historical release-boundary assertions from Build 384/385 (version, health/server, generic launcher)
- **0 functional regressions**

## Historical regression (360–380)
- **792/822 PASS**
- 30 expected historical release-boundary assertions (version, health/server, generic launcher)
- **0 functional regressions**

## Security boundary
- No Build-386 network execution path added.
- No crawler job is created by preflight or GO grant issuance.
- GO tokens are persisted only as SHA-256 hashes.
- Grants bind packet hash, source state, workflow generation/request budgets, Operations preflight, and OPSEC preflight.
- Existing explicit `LIVE` execution confirmation remains mandatory downstream.
