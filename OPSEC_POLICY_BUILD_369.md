# Defensive OPSEC Policy – Build 369

- Scheduled crawl jobs are continuously checked for source review, case scope, scheduler configuration and source-health integrity.
- Invalid or tampered Build-369 scheduled jobs may be cancelled only inside the affected case.
- Source-health circuit breakers can prevent additional scheduled work for rate-limited, offline, authentication-changed, contract-changed or quarantined sources.
- Generic recurring scheduling cannot bypass provider-specific `LIVE` confirmations.
- Generic recurring scheduling cannot schedule darknet/onion sources.
- Crawler-only expired-lease recovery may requeue an expired governed crawl while preserving its checkpoint; arbitrary job auto-resume is not granted.
- No autonomous firewall, OS, Tor, credential, account, ACL or system-policy mutation is permitted.
