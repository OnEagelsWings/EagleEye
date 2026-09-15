# Defensive OPSEC Policy – Build 374

- Once a case workflow is configured, post-activation crawler jobs must carry the correct workflow ID, generation and source-budget reservation.
- Untagged or tampered queued workflow crawls are cancelled case-locally; running jobs are marked to drain rather than force-killed.
- Paused, handoff-pending and completed workflows may not leave new queued crawler work active.
- Analyst handoff requires an active case membership and explicit target acceptance.
- OPSEC does not mutate firewall, OS, Tor configuration, credentials, accounts, ACLs or external infrastructure.
- No automatic scope expansion or review bypass is permitted.
