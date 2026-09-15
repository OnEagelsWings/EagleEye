# Release Notes — Build 394.0

## Added
- Multi-turn Investigator Discussion Workspace.
- Argument/counterargument chains with parent-turn provenance.
- Side-by-side competing-hypothesis comparison.
- Human-reviewed versioned revision proposals.
- Append-only revision lineage for Claim, Hypothesis and Reasoning Plan working copies.
- Stale-base and source-hash conflict protection.
- Notebook-only Kernel bridge for versioned working copies.

## Governance
- No automatic overwrite of Build-391/392 objects.
- No edit access to evidence-derived corroboration metrics.
- No truth/probability assignment.
- No automatic GO/LIVE, crawler dispatch, evidence promotion or identity merge.

## Qualification
- Build-394 tests: 21/21 PASS.
- Acceptance: 22/22 PASS.
- Benchmark: 500 discussion turns + 50 versioned revisions, 0 violations.
- Phase-17 regression 384–394: 158/178, with 20 expected historical release-boundary assertions and 0 functional regressions.
- Release gate: 24/24 PASS.
