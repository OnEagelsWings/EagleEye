# EagleEye PersonOSINT Pro — Build 363.0

Build 363 advances Phase 16 with Object Store + Team Search live-readiness.

Portable defaults remain local CAS + SQLite FTS5. External S3/MinIO and PostgreSQL team-search backends are opt-in and never auto-connected. Their live harnesses only set `externally_validated=true` after an explicit real external run.

Current build-environment status: external S3/MinIO **not_run**, external Team Search **not_run**.
