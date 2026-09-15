# EagleEye Phase 16 Progress – Build 370

**Phase:** 16 – Live Operations, Entity Intelligence & External Validation  
**Progress:** 10/20 builds

## Build 370 – Controlled Tor Gateway + Crawler Continuity
- Tor execution is explicit opt-in through the existing `tor_read_only_v1` network profile.
- SOCKS endpoint is loopback-only; onion hostnames are sent as SOCKS5 DOMAIN targets and are never locally DNS-resolved.
- Per-search SOCKS username/password values are isolation tokens only; no destination credentials are supported.
- No Tor ControlPort, NEWNYM, torrc mutation, Tor process spawning, firewall or OS mutation.
- Exact reviewed v3 onion source + case RBAC + explicit `TOR_LIVE` are required before a Tor crawl can be queued.
- Tor crawls use a dedicated job type and cannot be claimed by the generic Build-369 Clearnet worker.
- Tor queue has independent case/global backpressure, lease renewal and expired-lease recovery.
- Crawler production capabilities from Build 369 (provenance, source health, delta/resume, evidence storage) remain authoritative.
- AI receives Tor/crawler readiness context but has no Tor configuration, enqueue or network authority.
- Defensive OPSEC may cancel malformed Tor jobs only inside the affected case.
- Crawler expansion is now a mandatory measurable increment in every Build 370–380.

## Truthful validation status
- Local SOCKS5 contract/fixture validation: qualification target for Build 370.
- Real local Tor daemon validation: **not_run** until actually performed.
- External onion-service validation: **not_run** until actually performed.
- Production release ready: **false**.

## Final internal qualification
- Build-370 tests: **45/45 PASS**.
- Build-369 regression: **39/40 PASS**; expected historical version assertion only.
- Benchmark: **3,600/3,600 PASS**, **0 violations**.
- Acceptance: **22/22 PASS**.
- Local SOCKS5 contract + HTTP fixture: **PASS**.
- Local Tor daemon validation: **not_run**.
- External onion-service validation: **not_run**.
- `build_acceptance_ready=true`; `production_release_ready=false`.
