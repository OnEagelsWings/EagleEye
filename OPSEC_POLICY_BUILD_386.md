# OPSEC Policy – Build 386

GO issuance is denied when the case has Operations circuit-breaker conditions, invalid workflow jobs, production-gate override markers, unreviewed/disabled sources, insufficient request budget, or a non-active workflow. Grant tokens are returned once and stored only as hashes.

No offensive capability and no autonomous firewall, OS, Tor, credential, or ACL mutation is introduced. Build 386 creates no network requests and no crawler jobs.
