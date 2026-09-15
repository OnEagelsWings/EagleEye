# EagleEye Build 378.0 — Voice Live Validation

Build 378 adds a review-first Voice → Crawler Intent layer. A spoken or typed transcript is converted into a visible preview only after the analyst explicitly selects already approved sources. The preview shows source state, workflow budgets, estimated requests and block reasons. Editing the transcript or source list invalidates the previous confirmation. Exact `VOICE CRAWL` confirmation triggers a fresh preflight and delegates approved clearnet work to the existing Case Workflow crawler queue.

No audio is persisted by the Build-378 layer. The voice layer does not perform network requests, auto-select sources, invoke provider/Tor special paths, or expand scope automatically.
