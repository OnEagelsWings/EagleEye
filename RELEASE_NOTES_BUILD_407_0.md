# Release Notes — Build 407.0

Phase 18 continues with Connector/Data Fabric v1. The build unifies source access planning and result intake semantics without adding network authority. Source Registry v2 metadata drives adapter classification. Result imports are hash-bound, provenance-required intake artifacts and cannot automatically become evidence.

Build 407 also removes historical Build-406 version coupling from the current acceptance gate: Build 406 security invariants are consumed, while Build 407 validates its own runtime/package version independently.

`production_release_ready=false` remains unchanged.
