# AI remediation scope for Build 400

This branch exists to remediate four defects identified by the automated Codex review of PR #1. The intended code changes must preserve EagleEye's human-governed, local-first security model and add regression tests.

Required fixes:

1. **Build 398 external holdout qualification** (`eagleeye_pro/phase17/model_holdout398.py`): qualification must not depend only on coverage/reviewer counts. Require a minimum external-model structural score, minimum blinded human-review quality scores, and block qualification when any external review flags harmful overreach.
2. **Build 400 Phase 18 readiness** (`src/eagleeye/application/build400/service.py`): `phase18_entry_ready` must only be true when the latest review disposition is exactly `accept_internal_phase17`; a `needs_remediation` review must keep it false.
3. **Build 400 final acceptance authorization** (`eagleeye_pro/phase17/final_acceptance400.py`): final acceptance and review must require an approval/reviewer capability even for a global run with an empty `case_id`; read-only users must not be able to advance the global Phase 18 state.
4. **Build 399 soak verification** (`eagleeye_pro/phase17/target_soak399.py`): an unknown `session_id` must return a structured `missing_session` result instead of throwing `TypeError` from `dict(None)`.

Regression expectations:

- low-quality or harmful holdout reviews cannot qualify Build 398;
- a remediation review cannot mark Phase 18 ready;
- a global read-only identity cannot run final acceptance;
- a missing soak session returns `{valid: false, violations: ["missing_session"]}`;
- existing Build 400 integration tests remain green.

Maintainer-side reference implementation has already been exercised locally with 17 targeted tests passing. Review this branch independently; do not assume that reference is correct.