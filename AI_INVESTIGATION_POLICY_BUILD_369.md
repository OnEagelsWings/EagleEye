# AI Investigation Policy – Build 369

- Explicit human `GO` remains mandatory before autonomous investigation.
- Before starting another bounded research wave, the AI investigator performs a read-only Crawler Production preflight.
- Queue backpressure, stale crawler leases or open source-health circuits can place the investigation in `crawler_operations_hold`.
- Crawler-production health and soak context are disclosed in the evidence-first dossier.
- The AI investigator may not enable/disable recurring schedules, claim/renew/recover worker leases or change source health directly.
- Provider connector `LIVE` gates, source reviews, RBAC and case isolation remain authoritative.
- No automatic fact promotion, identity merge, evidence release or export is introduced.
- No direct network, shell, firewall, OS, Tor, credential, account or ACL authority is granted.
