# AI Investigation Policy — Build 381

- AI may consume the case-scoped Control Plane snapshot and produce a source-selection plan.
- AI receives no direct network, crawler-enqueue, connector-execution, identity-merge, workflow-mutation or scope-expansion authority in Build 381.
- Every generated plan has `requires_go=true`, `execution_authority=false`, `scope_expansion_authority=false`.
- Source candidates remain subject to human source review, case membership/RBAC, workflow budgets, provider-specific LIVE gates, OPSEC preflight and provenance requirements.
- Coverage and source ranking are planning signals, never truth probabilities.
