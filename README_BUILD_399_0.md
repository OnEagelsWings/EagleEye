# EagleEye Build 399.0 — Target Environment Soak & Recovery Qualification

Build 399 provides the qualification framework for the planned 72-hour real target-environment test. Qualification requires native Windows, native Firefox end-to-end evidence, the protected Firefox profile, 15-minute samples (minimum 289 over 72 hours), application/database/crawler/worker health, controlled application and Firefox recovery events, an external execution receipt, and human final review.

## Qualification boundary

No real 72-hour run is bundled with this release. Internal simulation and synthetic gate fixtures exercise the framework only and can never count as external qualification evidence. The release therefore remains `external_72h_soak_qualified=false` and `production_release_ready=false` until real evidence is imported later.
