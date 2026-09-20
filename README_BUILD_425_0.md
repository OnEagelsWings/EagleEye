# EagleEye Build 425.0 — AI Investigation Crawler Core

Build 425 establishes the case-scoped crawler orchestration boundary. Investigation objectives become bounded crawl tasks tied to Build-421 sources, Build-424 source-health advice, Build-422 acquisition events and Build-423 content fingerprints.

This build deliberately separates planning/orchestration from network execution. It does not yet ship a generic live HTTP executor. An approved retrieval adapter must return content into the ingestion boundary, where provenance and deduplication are applied. Public HTTP(S) targets only; Onion execution is reserved for the isolated Tor worker planned for Build 435. No access-control bypass or autonomous scope expansion is permitted.

Build 425 is also the first Phase-19 hard checkpoint: the 421–425 chain must be qualified before Build 426 proceeds.
