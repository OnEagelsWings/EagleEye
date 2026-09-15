# EagleEye Build 392.0 – Regression Summary

## Current Build 392 suite
- `tests/test_build392_integrated.py`: **22/22 PASS**.
- Acceptance qualification: **18/18 PASS**.
- Reasoning benchmark: **1000/1000 PASS**, 0 violations.

## Integrated Phase-17 regression
Build-specific integrated suites for Builds 384–392 contain 133 tests. On the current Build-392 tree:
- **117/133 PASS unchanged**.
- **16 expected release-boundary assertions**: each historical suite for Builds 384–391 contains one version/package/schema assertion and one current-launcher/server assertion that intentionally targets its historical build number.
- **0 functional regressions** in the retained Build-384–391 functionality.

## Historical predecessor qualification
Build 392 consumes the qualified Build-391 predecessor receipt. That receipt preserves the previously qualified Phase-16 / Build-380 professional-pilot line and records 0 functional regressions in the inherited historical baseline. Build 392 does not reinterpret old historical version assertions as functional failures.

## Safety / authority regression
Build 392 creates no crawler jobs, GO grants, evidence promotions, legacy probability hypotheses, identity merges, or direct network requests during its reasoning, plan proposal, plan review, or kernel-notebook bridge paths.
