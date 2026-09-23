# EagleEye Build 422.0 — Acquisition Event & Provenance Contract

Build 422 introduces the immutable acquisition-event ledger that sits between source selection and later retrieval workers. Every acquisition observation can be tied to a case, Build-421 source, target, method, timestamp, content hash, media type, byte count, provenance metadata and usage/terms metadata.

This build records acquisition facts but performs no network retrieval, evidence promotion or truth determination. The contract is intentionally usable by later Surface Web, API, archive, social and public-Tor workers without giving the ledger execution authority.

Acceptance: source-to-event provenance, case scoping, SHA-256 validation, tamper detection, runtime/launcher integration, and regression compatibility. Production release readiness remains false.
