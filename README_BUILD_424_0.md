# EagleEye Build 424.0 — Source Health, Rate Limits & Freshness

Build 424 adds a passive health ledger for acquisition sources registered by Build 421. It records availability state, HTTP status, latency, quota state, retry-after guidance, freshness timestamps and error classes. The layer exposes bounded acquisition advice so later crawler planning can defer rate-limited sources or avoid unavailable sources without granting this component network authority.

Health observations are append-oriented, integrity protected and audited. Build 424 performs no probing by itself: observations must come from an approved collector or human/system integration. It does not expand investigation scope or determine evidential truth.

Production release readiness remains false. Build 425 is the planned first hard Phase-19 checkpoint and crawler-core integration.
