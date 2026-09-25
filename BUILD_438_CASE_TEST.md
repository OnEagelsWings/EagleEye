# Build 438 case-specific test

Build 438 includes an authenticated, case-scoped self-test. It creates only synthetic Build-437 fixture observations and performs no network retrieval.

## API

With EagleEye running and an authenticated session, create or choose a disposable test case, then call:

```text
POST /api/build438/cases/{case_id}/fusion/selftest
```

The request must be same-origin and the user must have `research.run` capability for the case.

## PASS contract

A PASS verifies that:

- the underlying Build-437 provenance/entity-resolution fixture passes;
- explicit source timestamps become provenance-bound timeline events;
- unreviewed identity candidates remain separate fusion groups;
- no identity is confirmed automatically;
- no destructive merge occurs;
- relationship semantics remain explicit-source-only;
- no relationship inference is performed from co-occurrence;
- machine-extracted events remain candidate-only;
- temporal order is not treated as causality;
- Build 438 performs no network execution;
- the Build-438 persisted fusion-run integrity hash verifies.

The self-test does not prove production readiness. It is a deterministic engineering acceptance check for the Build-438 fusion contract.
