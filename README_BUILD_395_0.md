# EagleEye Build 395.0

## Case State Version Graph & Controlled Adoption

Build 395 turns Build-394 working-copy revisions into an explicit case-state graph. Each claim, hypothesis and reasoning plan can have an active working node, alternate branch heads and an append-only transition history. Adoption and rollback are human-reviewed, generation-bound and fail closed when state changes between review and apply. Historical evidence and prior working versions are never overwritten.

### Safety boundaries

- no truth probability or automatic truth acceptance
- no automatic evidence promotion
- no GO/LIVE issuance
- no direct network fetch or crawler execution
- no automatic identity merge
- state adoption grants no execution authority

Status: **Professional Pilot**; `production_release_ready=false`.
