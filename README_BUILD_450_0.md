# EagleEye Build 450.0 — Investigation Workflow Hard Checkpoint

Build 450 is a fail-closed engineering checkpoint for the complete current investigation workflow.

## Qualified deterministic chain

Source Registry → Controlled Acquisition → Build-446 AI Dispatch → Evidence → Independent Evidence Review → Claim → Independent Claim Review → Living Dossier → Independent Dossier Review → Separate Export Approval → Authorized Export Executor → JSON/DOCX/PDF/ZIP Case Package.

The checkpoint is deliberately **not executable from an ordinary investigation case**.

## Isolation and authentication boundary

A Build-450 qualification run now requires:

- an isolated qualification case created and marked by Build 450;
- a system administrator using a real active authenticated session;
- a different reviewer using a separate real active authenticated session;
- explicit reviewer consent for that exact qualification case (`CONSENT BUILD 450 QUALIFICATION`);
- reviewer case capabilities for Evidence, Dossier and export review;
- valid component integrity before any mutating qualification action.

The checkpoint does not fabricate reviewer identities and does not execute review actions on behalf of an unauthenticated or non-consenting user.

The operational browser workspace exposes checkpoint status only. It does not expose a mutating “run qualification” action.

## Fail-closed preflight

Before fixture acquisition, Evidence synchronization, Claim creation, Dossier creation or export, Build 450 verifies:

- the qualification-case marker;
- both authenticated identities;
- component integrity;
- the authority contract.

A failed preflight aborts before workflow mutation. The same preflight is enforced even when the internal mutating workflow method is called directly.

## Engineering vs field validation

Build 450 deliberately separates `engineering_result`, `external_validation_result`, and `release_result`.

A deterministic engineering PASS does not turn the release result into PASS. Production readiness remains false.

## Required components

The checkpoint checks Builds 441–449:

- 441 controlled surface retrieval;
- 442 surface hardening;
- 443 live news acquisition;
- 444 controlled public social acquisition;
- 445 data acquisition checkpoint;
- 446 live AI investigation dispatch;
- 447 Evidence → Claims → Dossier;
- 448 Investigator Workspace;
- 449 Human Review / Team Workflow.

## Authority contract

The checkpoint fails when current components claim prohibited automatic authority such as automatic GO, scope expansion, Evidence/Claim acceptance, truth determination, review completion, direct review bypass, private/direct social collection or access-control bypass.

Per-path acquisition confirmation and formal four-eyes export remain required.

## Required test levels

Build 450 CI runs:

- Build-450 integrated tests;
- Phase-19/20 regression 421–450;
- Phase-18/19/20 current-chain regression 413–450;
- full repository regression;
- targeted Build-420/418/417/416 regressions;
- current UI audit;
- GitHub Codex review on the tested head.

Build-450 tests explicitly cover isolated-case enforcement, authenticated reviewer sessions and consent, fail-before-mutation integrity behavior, direct internal workflow preflight, bypass-route absence, physical JSON/DOCX/PDF/manifest/ZIP hash revalidation, post-qualification component tamper, checkpoint-record tamper behavior and release-vs-engineering separation.

## Boundaries

Build 450 is not a truth certification, legal conclusion, production-security certification, proof that all external endpoints are reachable, or release authorization.

`production_release_ready = false`
