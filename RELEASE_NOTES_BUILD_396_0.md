# Release Notes — Build 396.0

Build 396 adds an incremental reconciliation layer above the Build-395 Case State Version Graph.

Highlights:
- explicit evidence/change baseline
- new-signal inventory for Evidence Candidates, finalized Corroboration Reviews and reviewed Claims
- active Claim/Hypothesis/Reasoning-Plan impact detection
- conservative unmatched-signal handling
- review-only Re-analysis Proposals
- controlled Build-395 re-analysis branches without adoption
- stale-generation blocking
- explicit baseline advancement

Qualification:
- Build 396 tests: 15/15 PASS
- Acceptance: 28/28 PASS
- Benchmark: 1,000/1,000 signals reconciled, 0 violations
- Phase 17 381–383: 85/85 PASS
- Phase 17 384–396: 183/205 PASS; 22 expected historical release boundaries; 0 functional regressions
- Production release ready: false
