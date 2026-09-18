# Code Audit Build 404.0

- Persistent table: `ai_review_finding_404`
- Allowed severities: P0, P1, P2, P3
- Blocking severities: P0, P1
- Finding states: open, fix_in_progress, fixed_pending_verification, verified_closed
- P0/P1 closure requires fix evidence + verification evidence + regression-test identifier
- Ledger integrity protected by content hashes and audit events
- Build 403 negative-path contracts/probes/catalog are preserved as prerequisites
- No production-release authority is introduced
