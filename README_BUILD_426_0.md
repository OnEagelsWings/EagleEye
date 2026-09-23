# EagleEye Build 426.0 — Crawl Prioritization & Budgets

Build 426 adds bounded prioritization to Phase 19 collection tasks. It combines investigator/AI relevance, urgency, operational source health and a small cost factor into an auditable priority score. Per-task budgets cover pages, bytes, depth and execution time.

The result is advisory orchestration only. Build 426 does not execute network requests, expand scope, bypass access controls or decide evidential truth. Rate-limited sources are deferred and unavailable sources blocked from the queue recommendation.

This build follows the Build-425 acquisition-chain checkpoint and prepares incremental crawling/change detection in Build 427.
