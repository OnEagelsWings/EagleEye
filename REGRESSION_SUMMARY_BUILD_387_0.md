# Regression Summary Build 387.0

## Current delta
- Build 387 integrated tests: **14/14 PASS**.
- Phase 17 suite (381–387): **139/143 PASS**.
- Four failures are expected historical release-boundary assertions from Builds 385/386 (old version and launcher expectations).
- Functional regressions in the Phase 17 delta: **0**.

## Historical predecessor receipt
Build 386 already qualified the Build 360–380 historical line at **792/822 PASS**, with **30 expected version/health/launcher boundary failures and 0 functional regressions**. Build 387 does not modify legacy Phase-16 implementation code; it adds the controlled executor, Build-387 service/UI registration, and the current version/launcher. The Build-386 release manifest is therefore retained as the historical predecessor regression receipt.

## Build 387 safety boundaries
- Exact `LIVE` confirmation required after a valid Build-386 GO grant.
- Grant is reserved, post-reservation-revalidated, enqueued and consumed inside one immediate transaction.
- Replay is denied.
- Executor performs no network fetch and claims no worker lease.
- Workflow budget and active-crawl limits are rechecked at dispatch time.
- Automatic scope expansion and host-security mutation remain disabled.
