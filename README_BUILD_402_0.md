# EagleEye Build 402.0 — Authorization Matrix Audit

Build 402 turns the Build-400/401 authorization lessons into a machine-readable and regression-tested security contract.

## What changed

- Catalogues the security-relevant Phase-17 mutation surfaces from execution grants through final acceptance.
- Maps each mutation to its required capability and scope.
- Audits source code read-only to verify that each catalogued mutation traverses the expected governance path.
- Fails the Build-402 gate if a mutation is protected only by `case.read`.
- Includes global final-acceptance mutations in the same authorization model as case-scoped actions.
- Exposes a role/capability matrix and explicitly verifies that `read_only` has no catalogued mutation capability.
- Keeps all authorization decisions hash-chained through the existing TeamIdentity access ledger.
- Keeps `production_release_ready=false`.

## Feedback-cycle rule

Builds 401–405 remain one internal hardening cycle. The cumulative result is published after Build 405 for GitHub AI and external tester review. P0/P1 findings block the next cycle; P2/P3 findings are fed back into the Phase-18–20 roadmap according to risk and user impact.
