# EagleEye Build 432.0 — Social Public Data Adapters

Build 432 adds a case-scoped normalization layer for public social data. It supports Mastodon-public, Bluesky-public and generic-public adapter contracts without implementing autonomous network retrieval.

Each observation is bound to a Build-422 acquisition event and Build-423 content object. Canonical public URLs, UTC publication times, object/account identifiers, reply/reshare lineage, public metrics and sanitized metadata are normalized and integrity-hashed. Private/direct/followers-only content, credential collection and access-control bypass are outside the contract.

For manual verification, Build 432 adds a one-step case-specific self-test and a fixture-ingest route. Synthetic test records are explicitly tagged `test_fixture=true`.

See `BUILD_432_CASE_TEST.md` for case-specific test instructions. Production readiness remains false; the next hard checkpoint is Build 435.
