# Release Notes — Build 387.0

- Added ControlledExecutor387.
- Added exactly-once consumption of Build-386 GO grants.
- Added post-reservation TOCTOU revalidation.
- Reused existing Build-366/367/368 live connector gates instead of adding a parallel network path.
- Added Build-374 workflow tagging, request-budget and active-crawl rechecks.
- Added durable execution_dispatch_387 receipt and record-hash verification.
- Executor performs no direct network fetch and claims no worker lease.
- Automatic scope expansion and host-security mutation remain disabled.
