# EagleEye Phase 16 Progress – Build 374

**Phase:** 16 – Live Operations, Entity Intelligence & External Validation  
**Progress:** 14/20 builds

## Build 374 – Case Workflow

### Delivered
- Case-scoped workflow state on canonical Phase-15 job/event/audit ledgers; no Build-374 workflow tables.
- Explicit per-source request budgets, aggregate case request budget and active-crawl limits.
- Workflow-aware manual crawler enqueue and graph navigation.
- Explicit pause/resume with queued-job suspension and running-worker drain semantics.
- Two-step analyst handoff: `HANDOFF` proposal plus designated target `ACCEPT`.
- Workflow status includes budget usage, remaining source/case requests, paused jobs, draining jobs and handoff packet.
- AI investigation hold for paused/handoff-pending workflows.
- OPSEC detection of untagged/tampered post-activation crawler work.
- Crawler continuous-development increment 374 completed.

### Preserved boundaries
- No automatic scope expansion.
- No automatic identity merge.
- No workflow-owned direct network client.
- No force-kill of running workers.
- No firewall/OS/Tor/credential/account/ACL mutation.
- External multi-analyst workflow validation remains `not_run`.
- `production_release_ready=false`.
