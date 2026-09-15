# EagleEye Build 396.0

## Case State Reconciliation & Incremental Re-analysis

Build 396 detects new reviewable evidence, finalized corroboration reviews and reviewed claims relative to an explicit baseline and determines which active Build-395 claims, hypotheses and reasoning plans may require re-analysis.

Core controls:
- explicit reconciliation baseline and explicit baseline advancement
- delta-only signal comparison
- conservative exact proposition matching; unrelated evidence remains unmatched review material
- dependency propagation from impacted claims to active hypotheses and reasoning plans
- review-required re-analysis proposals
- explicit re-analysis branch creation without adoption
- stale active-generation protection
- append-only scan/proposal/review history
- no automatic active-state adoption, GO/LIVE, network execution or evidence promotion

Status: Professional Pilot line. Not a production release.
