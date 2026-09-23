# EagleEye Build 436.0 — Surface ↔ Onion Correlation & OPSEC

Build 436 correlates **reviewed** Build-435 onion research with clearnet/public-surface evidence already present in the same case. It never performs new network retrieval.

Candidate links are generated from provenance-bound content signals: exact SHA-256 identity, identical normalized-text fingerprints, and high token-Jaccard overlap. The numeric score describes content similarity only; it is not a probability that the surface and onion actors, accounts or organizations are the same entity.

The OPSEC gate verifies that correlated onion material retains the Tor/public-source contract: `tor_public` acquisition, quarantined provenance, no destination authentication, no forms and no scope expansion. A failed OPSEC contract is surfaced as a blocker and prevents the run from reporting operational follow-up as allowed.

Build 436 performs no automatic entity resolution, no identity determination, no cross-surface contact, no scope expansion and no network execution. Cross-source Entity Resolution remains scheduled for Build 437.

A deterministic case-specific self-test is included in `BUILD_436_CASE_TEST.md`. Production readiness remains false.
