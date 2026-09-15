# Release Notes – Build 392.0

## Added
- deterministic case reasoning workspaces bound to Build-391 synthesis and Build-382/384/388 research-gap state;
- provenance-preserving argument graph from Evidence Candidates → Claims → Hypotheses;
- explicit reasoning issues for counterevidence, source-independence gaps, insufficient independent support, open hypothesis tests, integrity holds and source/coverage gaps;
- deterministic next-investigation plan proposals with priority ordering and explicit `requires_go` markers;
- exact-confirmation human review gate for reasoning plans;
- reviewed-plan bridge to Investigation Kernel notebook without using the legacy numerical hypothesis-confidence path;
- workspace/plan hash verification and stale-workspace detection.

## Governance
Build 392 has no execution authority. It does not issue GO, confirm LIVE, enqueue jobs, perform network requests, promote Evidence Candidates, merge identities, or decide truth/probability.
