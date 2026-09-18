# EagleEye Build 403.0 — Negative Path & Abuse Framework

Build 403 turns the Build-400 GitHub/Codex findings into a permanent fail-closed testing discipline.

## Added
- machine-readable negative-path catalogue with 15 P1 scenarios
- missing-record contracts for soak and final acceptance
- read-only/global-scope authorization bypass checks
- exact-confirmation checks
- invalid-review-state checks
- duplicate-mutation contract
- governance hard-veto, qualifying-reviewer diversity, and harmful-overreach checks
- integrity/tamper scenarios
- read-only runtime probes that do not grant capability or execute external research

## Validation
- Build 403 integrated: 8/8 PASS
- adjacent Build 398–403 regression selection: 52/52 PASS
- 7 historical version/launcher assertions deselected because they intentionally target prior build identities
- real local server start: PASS
- /health build=403.0, negative_path_framework=true, negative_path_scenarios=15

Build 403 remains an engineering/testing baseline. production_release_ready=false.
Public feedback checkpoint remains Build 405.
