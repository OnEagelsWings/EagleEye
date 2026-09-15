# Release Notes — EagleEye Build 365.0

## Operations foundation
Build 365 introduces a consolidated, case-scoped observability layer without creating another set of per-build operational tables. Metrics are derived from the canonical job, crawler, security, evidence/search and audit ledgers.

## Analyst workflow
A dedicated Operations Console provides queue state, worker leases, crawler activity, incident state and local readiness for the current case. JSON endpoints expose the same case-scoped data for controlled integrations.

## AI investigation improvement
The AI investigator performs a read-only operational preflight. If the case has a serious unresolved operations/security incident, the investigation cycle stops in `operations_hold` before a new research wave starts. The review dossier records the operational context.

## OPSEC improvement
The defensive supervisor can activate a case-local circuit breaker and cancel active work for the affected case. Other cases remain untouched. System, firewall, Tor, credentials and ACLs remain outside autonomous authority.

## Crawler improvement
Crawler operations now expose queue/lease health, case trace context and incident awareness. Failed/dead-letter and stale-lease recovery stays human-controlled.

## Validation
- 22/22 Build-365 tests pass.
- 2400/2400 deterministic operations benchmark cases pass with 0 violations.
- Local SQLite/job/audit live validation passes.
- External team operations/load validation remains not run.
- Production release readiness remains false.
