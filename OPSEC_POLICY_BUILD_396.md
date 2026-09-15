# OPSEC Policy — Build 396

Build 396 is a local reconciliation/analysis layer. It performs no direct network fetch and creates no crawler job, worker lease, GO grant or LIVE authorization.

Unmatched new evidence is surfaced as review material and is not force-mapped to an active Claim. Re-analysis proposals are generation-bound to the active Build-395 state and fail closed if that state changes before branch creation.
