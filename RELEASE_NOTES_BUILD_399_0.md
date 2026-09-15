# Release Notes — Build 399.0

- Added frozen 72-hour Windows/Firefox soak plan.
- Requires 289 samples at 15-minute nominal cadence with start/end coverage and bounded sample gaps.
- Requires healthy application, SQLite integrity, crawler/worker health, native Firefox E2E probe and protected profile evidence.
- Requires successful `application_restart` and `firefox_restart` recovery evidence.
- Added hash-bound external evidence-bundle import and session integrity verification.
- Added explicit human final qualification review.
- Internal simulations cannot qualify the external gate.
- No browser launch, network fetch, crawler execution, GO/LIVE issuance, or evidence promotion authority is added to the qualification core.
- Real 72-hour live qualification remains pending external execution.
