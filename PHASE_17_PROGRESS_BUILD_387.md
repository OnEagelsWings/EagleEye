# Phase 17 Progress — Build 387

Build 387 is the seventh integrated Phase-17 build (381–387). It turns a valid Build-386 capability-scoped GO grant into exactly-once canonical Phase-16 connector jobs after explicit `LIVE` confirmation.

## Implemented
- atomic grant reserve → post-reservation revalidation → enqueue → workflow tagging → dispatch receipt → grant consumption
- replay protection and hash-only token handling
- reuse of Build-366/367/368 reviewed live connector gates
- Build-374 workflow budget and active-crawl enforcement
- Phase-17 provenance on queued jobs
- durable dispatch receipt with integrity verification

## Explicit boundary
Build 387 enqueues work but does not claim a worker or perform a network fetch. External connector validation and general production readiness are not promoted.
