# EagleEye Build 446.0 — Live AI Investigation Loop

Build 446 closes the main integration gap identified by the Build-445 acquisition checkpoint.

A human-authorized Build-439 investigation loop can now prepare per-source acquisition dispatches to the correct specialized adapter:

- ordinary public Surface -> Build 442 hardened Surface retrieval;
- public News feeds -> Build 443;
- controlled Public Social -> Build 444.

## No generic AI network authority

Build 446 does not give the AI investigator unrestricted network access.

A Build-439 loop must already be active, and every dispatched source must already be inside the loop's explicit `allowed_source_ids`.

Each live dispatch keeps the underlying path-specific confirmation:

- Surface: `SURFACE442_LIVE`
- News: `NEWS443_LIVE`
- Social: `SOCIAL444_LIVE`

No batch auto-execution exists.

## Dispatch model

Build 446 creates a persistent dispatch ticket containing:

- loop;
- case;
- current loop cycle;
- source;
- selected route;
- specialized task;
- required confirmation;
- state and reason.

Repeated preparation in the same loop/cycle reuses the existing source ticket rather than silently creating parallel work.

Unsupported or separately governed sources become `review_required`.

Tor remains outside Build 446 and continues to require the isolated Tor worker and its separate approval boundary.

## Routing

The default routing rules are intentionally conservative:

- `social` -> Social adapter only when `coverage.social_adapter` is declared;
- `rss` / `news` -> News;
- `api` -> News only when explicit news-feed capabilities are declared, otherwise Surface;
- other public HTTP(S) sources -> Surface;
- non-public access modes -> human review;
- Tor -> separate review.

## Closed-loop analytical refresh

After successful acquisition, Build 446 refreshes:

- Build-437 entity resolution;
- Build-438 temporal/relationship fusion;
- Build-418 hypothesis/counterevidence matrix;
- Build-419 synthesis.

This is analytical recomputation only.

It does not:

- automatically accept hypotheses;
- promote evidence;
- determine truth;
- expand source scope;
- launch another network wave.

## Build-445 relationship

Build 445 remains a historical hard checkpoint and may still be on `HOLD` until real non-fixture external validation exists for Surface, News and Social.

Build 446 closes the specific 445 integration gap:

`build439_specialized_news_social_adapter_dispatch_not_implemented`

but does not retroactively rewrite the Build-445 report.

## Current limits

- process/container retrieval isolation is still not implemented;
- broad external endpoint coverage is not established;
- authenticated/private collection remains unsupported;
- production readiness remains false.

Next: Build 447 — Evidence -> Claims -> Dossier Closure.
