# Build 453 — Historical Web Intelligence 2.0 + Recovery Basis

Build 453 is a development build between the 450 and 455 hard checkpoints. In accordance with the five-build cadence, it adds investigation capability and focused regression coverage without rerunning the complete case-to-export qualification matrix.

## Historical Web Intelligence 2.0

The new `HistoricalWebIntelligence453` service turns historical-web lookup into a provenance-aware investigation workflow rather than a loose archive URL helper.

It can:

- create bounded historical queries for Internet Archive CDX and a selected Common Crawl `CC-MAIN` index;
- preserve the exact provider query that should be executed through the existing governed acquisition path;
- import Internet Archive JSON and Common Crawl CDXJ only when the index response is already bound to a Build-422 acquisition event and Build-423 content observation;
- deduplicate candidates, preserve provider digests and timestamps, and rank first/last observations and digest changes for analyst attention;
- mark Common Crawl WARC range retrieval separately instead of pretending that an index hit is already retrieved page content;
- link a successfully acquired archived page into the existing Build-428 Archive History chain;
- compare two supplied historical text extractions and report added/removed lines as change signals, never as automatic truth claims.

The service has no independent network authority. Live provider queries remain subject to the existing Build-441/442/451 retrieval controls and human-governed dispatch.

## Recovery Basis

Build 453 also introduces a conservative recovery foundation:

- SQLite online backup into a managed `recovery_453` directory;
- SHA-256 manifest and SQLite `quick_check`;
- immutable catalog metadata for each recovery point;
- independent verification before restore preparation;
- restore **staging** into a separate verified database file.

Build 453 deliberately does not overwrite the active database while EagleEye is running. Final replacement requires an explicit restart/maintenance step. This avoids turning a recovery feature into an unsafe live-database mutation.

## Test cadence

Normal development builds now use focused tests. The complete historical regression and full real-source research chain are reserved for build numbers divisible by five: 455, 460, 465, and so on.

Build 453 therefore requires:

- Build-453 historical/recovery tests;
- current import/compile smoke;
- lightweight UI/current-server check;
- no automatic full-repository regression.

Build 455 remains the next complete real-source case → acquisition → Evidence → Claims → independent review → Dossier → approved export → restart/reference verification gate.

## Boundaries

Historical archive observations are not automatically facts. Candidate ranking is investigative prioritization, not a reliability or truth score. Common Crawl index hits that require WARC range retrieval remain explicitly marked as not yet retrieval-ready. Recovery staging never replaces the active database automatically.

Production readiness and operating-host qualification remain **HOLD**.
