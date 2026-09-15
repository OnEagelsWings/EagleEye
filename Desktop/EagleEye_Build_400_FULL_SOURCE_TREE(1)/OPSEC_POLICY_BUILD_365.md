# Defensive OPSEC Policy – Build 365

- Build 365 extends the defensive supervisor with queue-failure, stale-worker and incident-console monitoring.
- A case-scoped operational circuit breaker may defensively cancel queued/running jobs in the affected case when critical/high-attention operational incidents are present.
- The circuit breaker must not cancel jobs from unrelated cases.
- Dead-letter recovery and stale-lease recovery remain explicit human/role-gated actions; Build 365 does not auto-resume failed work.
- Existing Build-364 remote-session anomaly and cross-case denial protections remain active.
- The supervisor may block, cancel, pause, isolate or quarantine within approved case/job profiles.
- No autonomous firewall, OS, Tor, account, credential or ACL mutation is permitted.
