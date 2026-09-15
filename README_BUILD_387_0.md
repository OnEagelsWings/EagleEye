# EagleEye Build 387.0 — Controlled Executor

Build 387 introduces the controlled Phase-17 execution boundary. A short-lived Build-386 GO grant can be consumed once, after an exact human `LIVE` confirmation, to enqueue existing reviewed read-only connector jobs.

The grant is revalidated after reservation and before enqueue. Source state, workflow generation, budget, Operations and OPSEC state are all bound. Dispatch is transactional and replay-safe. The executor itself never fetches the network and never claims a worker lease.

Current status: professional-pilot line preserved; production release readiness remains false.
