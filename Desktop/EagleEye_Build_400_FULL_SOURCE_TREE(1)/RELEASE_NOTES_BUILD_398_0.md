# Release Notes — Build 398.0

- Added 60-case frozen holdout suite across 12 investigation domains.
- Added hash-bound run receipts, structural metrics, blinded human-review ledger, and frozen internal baseline.
- Hardened external qualification gate: reviews of deterministic reference runs cannot satisfy external-model qualification.
- Requires every holdout case to have an external-model run and a blinded review of that external run; at least two external reviewers overall.
- No direct model execution, network authority, GO/LIVE issuance, evidence promotion, or truth-probability training.
- External live-model/human qualification remains pending.
