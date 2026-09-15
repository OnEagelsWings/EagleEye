# EagleEye Build 398.0 — Model Holdout & Human Evaluation Framework

Build 398 adds a frozen, hash-bound 60-case structural holdout framework, deterministic internal baseline, external-model run import receipts, blinded human review records, and qualification metrics. It does not execute a model or network request itself.

## Qualification boundary

The bundled 60 cases are synthetic fixtures for framework qualification. The internal deterministic baseline is **not** a real-model benchmark. Build 398 remains `external_holdout_qualified=false`, `real_model_runs=0`, and `human_reviewed_cases=0` until externally executed model runs and blinded human reviews are imported with provenance.

Production release remains false.
