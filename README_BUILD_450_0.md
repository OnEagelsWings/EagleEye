# EagleEye Build 450.0 — Investigation Workflow Hard Checkpoint

Build 450 is a fail-closed engineering checkpoint for the complete current investigation workflow.

## Qualified deterministic chain

Source Registry → Controlled Acquisition → Build-446 AI Dispatch → Evidence → Independent Evidence Review → Claim → Independent Claim Review → Living Dossier → Independent Dossier Review → Separate Export Approval → Authorized Export Executor → JSON/DOCX/PDF/ZIP Case Package.

The checkpoint requires a dedicated case, a system administrator/investigator and a separate eligible reviewer.

## Engineering vs field validation

Build 450 deliberately separates `engineering_result`, `external_validation_result`, and `release_result`.

A deterministic engineering PASS does not turn the release result into PASS. Production readiness remains false.

## Required components

The checkpoint checks 441 controlled surface retrieval, 442 surface hardening, 443 live news acquisition, 444 controlled public social acquisition, 445 data acquisition checkpoint, 446 live AI investigation dispatch, 447 Evidence→Claims→Dossier, 448 Investigator Workspace and 449 Human Review/Team Workflow.

## Authority contract

The checkpoint fails when current components claim prohibited automatic authority such as automatic GO, scope expansion, Evidence/Claim acceptance, truth determination, review completion, direct review bypass, private/direct social collection or access-control bypass.

Per-path acquisition confirmation and four-eyes export remain required.

## Required test levels

Build 450 CI runs the Build-450 integrated suite, Phase-19/20 regression 421–450, Phase-18/19/20 current-chain regression 413–450, full repository regression and targeted Build-420/418/417/416 regressions. UI regression is retained and GitHub Codex review is required for the current head.

## Boundaries

Build 450 is not a truth certification, legal conclusion, production-security certification, proof that all external endpoints are reachable, or release authorization.

`production_release_ready = false`
