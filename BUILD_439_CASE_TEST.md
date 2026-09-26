# Build 439 case-specific qualification

Build 439 includes an authenticated self-test for a selected case. Use only a synthetic/demo case.

## Endpoint

With EagleEye running and an authenticated case-researcher/admin session:

\`\`\`
POST /api/build439/cases/{case_id}/investigation/selftest
\`\`\`

The self-test:

- seeds the existing Build-438 synthetic provenance fixture;
- creates a Build-413 plan, Build-414 bounded wave and Build-415 session;
- creates question-derived working hypotheses;
- verifies that advancing before human GO is blocked;
- authorizes the loop with the exact Build-439 confirmation;
- runs one bounded cycle;
- creates/prioritizes synthetic crawl tasks without performing network I/O;
- re-runs Build-437 entity resolution and Build-438 fusion;
- runs multi-agent analysis, hypothesis-gap/counterevidence review and Build-419 synthesis;
- verifies that scope does not expand and truth is not determined.

A passing result returns \`"result": "PASS"\` with every check set to \`true\`.

The self-test does not contact external systems.
