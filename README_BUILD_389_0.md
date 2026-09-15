# EagleEye Build 389.0 — Result Intake & Evidence Normalization

Build 389 closes the gap between terminal research-wave outputs and analyst-reviewable evidence material. It reuses the Build-350 parser layer, preserves raw Phase-15 objects and their hashes, creates provenance-bound normalized candidates, and links exact logical duplicates without collapsing independent-source observations.

Candidates remain `needs_review`. The AI-investigator feed is explicitly candidate-only and assigns no truth probability, identity merge, or evidence acceptance. `PROMOTE EVIDENCE` is an explicit human action; promotion copies a normalized candidate into Evidence Vault with `needs_review` status and does not create a verified `evidence_items` record.

Quarantined objects are never auto-parsed or promoted. Build 389 performs no network fetch, creates no GO grant and creates no crawler job.
