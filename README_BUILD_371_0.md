# EagleEye PersonOSINT Pro Build 371.0

Build 371 introduces Entity Resolution v2 and the required Build-371 crawler increment: entity-linked crawl provenance and a source-to-entity lead queue.

The system never treats similarity as identity proof. Strong identifier conflicts veto same-entity inference; independent sources affect review priority only. Every crawler-originated entity lead retains case/source/crawl/fetch/object provenance and has zero network request budget. Independent human review remains mandatory before any non-destructive same-entity link.

Production release remains false; calibrated external/holdout Entity Resolution evaluation is scheduled for Build 372.
