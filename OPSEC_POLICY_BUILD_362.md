# OPSEC Policy — Build 362

The autonomous defensive OPSEC supervisor continues per-search protection and additionally monitors backend configuration hygiene. Persisted raw passwords, credentials, tokens or password-bearing PostgreSQL DSNs are treated as a security finding. For an affected case the supervisor may defensively stop queued/retry/running jobs.

It may block, pause, cancel, quarantine and record security evidence inside approved policy profiles. It may not autonomously change firewall rules, OS configuration, Tor configuration, accounts, credentials or access controls.
