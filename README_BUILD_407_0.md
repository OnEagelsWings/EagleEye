# EagleEye Build 407.0 — Connector/Data Fabric v1

Build 407 introduces a governed connector/data-fabric control plane over Source Registry v2. It classifies registered sources into normalized adapter kinds, creates review-first acquisition plans, and imports caller-supplied results into immutable provenance-bound intake envelopes.

## Safety and governance invariants

- Build 407 performs no network request by itself.
- Every fabric plan has `requires_go=true`, `network_execution=false`, and `execution_authority=false`.
- Imported payloads are `unreviewed_intake`, never evidence by import alone.
- Source Registry v2 integrity and Build 406 security invariants are prerequisites for the Build 407 gate.
- Disabled sources fail closed.
- Intake requires provenance (`retrieved_at`, `origin_ref`, `collector`) and is size-limited to 10 MB.
- Production release readiness remains false.

## Adapter kinds

`rest_api`, `registry`, `bulk_dataset`, `local_mirror`, `crawler`, `archive`, `internal_evidence`.

## Validation

- Build 407 suite: 8/8 PASS.
- Predecessor functional regression sample: 39 PASS; seven historical version/launcher assertions intentionally remain build-boundary-specific.
- Real Uvicorn startup and `/health`: PASS, reporting Build 407.0 and `data_fabric_gate_pass=true`.
