# Release Notes – Build 369.0

Build 369 is the Phase-16 Crawler Production build. It adds an explicit scheduler, backpressure, source-health/circuit-breaker logic, lease heartbeat/recovery, operational soak snapshots and AI/OPSEC preflight integration to the existing evidence-first crawler.

The scheduler is deliberately operator-orchestrated. It may schedule only already approved unauthenticated clearnet sources. Provider-specific connector `LIVE` gates and the controlled darknet/Tor path are not bypassable through recurring scheduling.

A production-health correction treats absent `robots.txt` responses (HTTP 404/410) as normal rather than degrading an otherwise healthy source. Rate limits, authentication changes, 5xx responses, parser/fetch failures and explicit quarantine remain health signals.

No external long-running soak/load validation is claimed in this build environment. Production release remains blocked.
