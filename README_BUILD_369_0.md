# EagleEye PersonOSINT Pro – Build 369.0

## Phase 16 – Crawler Production

Build 369 hardens the existing governed read-only crawler for sustained professional operations without widening investigative authority.

### Delivered
- operator-orchestrated recurring schedules for already reviewed unauthenticated clearnet sources;
- queue backpressure with case/global high-water marks and per-tick enqueue caps;
- source-health circuit breaker with bounded exponential backoff;
- `robots.txt` 404/410 treated as normal absence, not as source outage;
- lease heartbeat and crawler-only expired-lease recovery while preserving checkpoints;
- inherited ETag/Last-Modified conditional delta fetches and durable frontier resume;
- case-scoped soak snapshots for runs, throughput, errors, resumes and stale leases;
- AI research preflight that holds new waves when crawler operations are unsafe;
- defensive OPSEC validation of scheduled jobs.

### Hard boundaries
- no background crawler worker starts at boot;
- no automatic external connection at boot;
- provider connectors with explicit `LIVE` gates cannot be placed on the generic recurring scheduler;
- darknet/onion sources cannot be placed on the generic recurring scheduler;
- no autonomous firewall, OS, Tor, credential, account or ACL mutation;
- no new per-build database tables.

### Release truthfulness
Build 369 can qualify the scheduler/worker/delta/resume/lease stack locally with deterministic replay. That is not an external long-running soak/load validation. `production_release_ready` therefore remains `false` until independent external qualification is actually performed.
