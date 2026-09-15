# EagleEye PersonOSINT Pro – Build 367.0

Build 367 adds a governed Procurement / Public Money layer to Phase 16. It integrates exact-record USAspending Award and TED published-notice XML retrieval into the existing review-first crawler/object/parser/audit chain. TED Search remains plan-only because the official search endpoint requires POST, while the qualified crawler remains deliberately GET/HEAD-only.

The release adds no per-build evidence tables and does not widen AI or OPSEC system authority. Public-money correlations remain human-review leads. External validation remains explicitly not-run unless a real live receipt is produced by the validation harness.
