# EagleEye Build 421.0 — Acquisition Source Registry

Build 421 starts Phase 19 with a real-data control plane rather than another autonomous execution layer.

The registry describes sources by type, access mode, URL, capabilities, coverage, terms/licensing note, provenance identity and integrity hash. Supported source classes are API, RSS, website, search, dataset, archive, social, registry, NGO, government, news and public Tor onion sources.

Build 421 performs no network retrieval. It stores source contracts for later governed collectors. It grants no direct network authority, credential collection, access-control bypass or autonomous scope expansion. Onion entries must use .onion hosts and cannot be misclassified as ordinary websites.

Acceptance requires version coherence, source registration/filtering, boundary validation, tamper detection and launcher integration while Build 420 remains a regression baseline. Production release readiness remains false.
