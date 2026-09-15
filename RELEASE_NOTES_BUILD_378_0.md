# Release Notes — Build 378.0

- Added Voice Live Validation + Voice-to-Crawler Intent Preview.
- Added explicit source selection (max 2) and bounded voice request estimate (max 30).
- Added exact `VOICE CRAWL` confirmation and edit-triggered reconfirmation.
- Added fresh confirmation-time workflow/source-health/backpressure preflight.
- Added voice intent/preview-hash provenance tags on governed crawler jobs.
- Added Build-378 OPSEC checks for tampering, direct-network claims, scope expansion and Tor bypass.
- Reused local optional STT; no audio persistence and no external STT requirement.
- No new Build-378 data tables.
- External voice/STT/multi-analyst/network validation remains not_run; production release remains false.
