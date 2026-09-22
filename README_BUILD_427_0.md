# EagleEye Build 427.0 — Incremental Crawling & Change Detection

Build 427 adds source snapshots and change detection to the Phase-19 acquisition chain. Repeated retrievals of the same case/source/target can be compared against the previous snapshot. Exact hashes identify unchanged content; normalized text similarity classifies minor versus material change and records bounded added/removed token summaries.

Every snapshot remains tied to its Build-422 acquisition event and Build-423 canonical content object. Snapshot and change records are integrity protected and audited. Change detection is an evidence signal, not a truth or credibility determination.

The component has no network authority. Build 428 will add historical-web/archive acquisition.
