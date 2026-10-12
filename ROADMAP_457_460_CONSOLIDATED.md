# EagleEye — Consolidated Roadmap 457–460

This roadmap reconciles the two development lines previously tracked separately:
the Build-452 deployment/reliability line and the recurring EagleEye UI Audit line.
It is the governing plan after Build 456 and supersedes the earlier assumption that
Build 457 should immediately start Document Intelligence 2.0.

## Baseline carried forward

The following foundations remain mandatory and must not regress:

- Build 452: deterministic isolated deployment, absolute retrieval deadlines,
  hardened qualification boundaries, immutable export behavior and reproducible
  installed runtime.
- Build 453: recovery/rollback and restart verification.
- Build 454: operational/public infrastructure integration and provenance-bound
  XRef candidate logic; correlation remains candidate evidence, never truth.
- Build 455: full operational research checkpoint with bounded real public sources,
  governed Evidence -> Claims/counterevidence -> Dossier -> independent review ->
  export -> restart/recovery/reference verification.
- Build 456: multilingual Entity/Alias review candidates plus reviewed source lineage
  and raw-mention vs reviewed-independent-origin accounting. No automatic identity
  merge and no automatic truth promotion.

The five-build cadence remains authoritative:
456–459 are focused development builds; 460 is the next complete hard checkpoint.

## Reconciled priority decision

The UI Audit identified unresolved workspace correctness issues that affect the
operator's next action and can therefore distort real investigations. These issues
take precedence over adding another analysis subsystem.

Therefore:

- Build 457 = Workspace Reliability + UI Functional Closure
- Build 458 = Document Intelligence 2.0
- Build 459 = Integration Burn-in + Field Workflow Readiness
- Build 460 = Full Real-Research / UI / Recovery Hard Checkpoint

## Build 457 — Workspace Reliability + UI Functional Closure

Goal: make the Investigator Workspace reliable enough that the operator sees the
correct active investigation cycle, correct remaining dispatch budget, and correct
next action.

Required corrections:

1. Active-loop selection
   - determine the newest active loop independently of the newest historical loop;
   - never let a completed/newer historical loop hide an older still-active loop.

2. Loop-scoped decision logic
   - readiness, blockers and next-action checks must be scoped to the selected loop;
   - records from previous cycles must not satisfy or block the current cycle.

3. Dispatch recommendation scope
   - recommendations may use only the current active cycle;
   - prior-cycle dispatches must not leak into the current next-action calculation.

4. Dispatch budget accounting
   - subtract already consumed/reserved dispatch work from the current loop budget;
   - fail closed when the remaining budget is exhausted or ambiguous.

5. UI audit depth
   - keep the current import/health/status smoke;
   - add focused browser-level tests for the current Investigator Workspace:
     navigation, case switching, forms, keyboard operation, error states and mobile/
     narrow viewport behavior;
   - do not invoke the complete historical repository regression on 457.

6. UI structure
   - preserve the consolidated Investigator Workspace rather than reintroducing
     parallel legacy navigation;
   - Legacy remains available separately for expert/historical access;
   - Evidence, Claims/Hypotheses, Graph/Timeline and Dossier must remain visibly
     connected by case context and next-action flow.

Acceptance for 457:
- targeted loop/dispatch regressions green;
- browser UI matrix green;
- no cross-case/cross-cycle state leakage;
- no automatic research action created solely from UI recommendation logic.

## Build 458 — Document Intelligence 2.0

Goal: make long reports, PDFs and structured documents first-class Evidence sources.

Scope:
- page-level and paragraph-level anchors;
- table, figure-caption and footnote anchors where extractable;
- stable document/source hash plus anchor hash;
- claim links bind to the exact document Evidence version and anchor;
- distinguish extracted text from OCR-derived text;
- preserve document provenance through Evidence, Claim and Dossier export;
- bounded OCR fallback only when parsed text is unavailable/insufficient;
- review UI for precise source-location inspection.

Do not add autonomous truth scoring.

## Build 459 — Integration Burn-in + Field Workflow Readiness

Goal: converge 452–458 into a robust pre-checkpoint operating build.

Focused scenarios:
- long-running research sessions;
- restart/resume in the middle of a case;
- network/source/scanner degradation;
- source disappearance after capture;
- malformed HTML/documents;
- large-document and multi-document cases;
- bounded parallel acquisition;
- idempotent retries and duplicate suppression;
- Entity/Source-Lineage/Document-Anchor consistency after restart;
- workspace state recovery without losing operator position or review state.

No complete repository checkpoint suite unless a failure specifically requires a
broader regression.

## Build 460 — Complete hard checkpoint

Build 460 must be usable for a complete real research task and must execute the full
five-build validation.

Required end-to-end chain:

Research Question
-> governed public Source acquisition
-> retrieval isolation/content-risk gate
-> multilingual Entity/Alias candidates
-> source-lineage review
-> Document Intelligence anchors
-> Evidence review
-> Claims + counterevidence + uncertainty
-> Graph/Timeline
-> Living Dossier
-> independent/four-eyes review
-> export approval
-> JSON/DOCX/PDF/ZIP package
-> restart/recovery
-> reference/hash/integrity revalidation
-> UI/browser workflow verification

Build-460 metrics:
- source fetch success/failure reasons;
- unique publication payloads vs raw mentions;
- reviewed independent origins;
- provenance completeness;
- stale/duplicate Evidence exclusions;
- unsupported Claim rate;
- Entity false-merge prevention;
- document-anchor resolvability;
- restart/resume integrity;
- export/reference integrity;
- operator workflow failures and UI dead ends.

## Non-negotiable authority boundaries through 460

- no automatic identity confirmation or destructive merge;
- no automatic Claim truth acceptance;
- no access-control bypass or scope expansion;
- source independence is not a truth probability;
- infrastructure/XRef correlation is candidate evidence only;
- stale/rejected/unlinked Evidence cannot contribute to corroboration;
- reviewed decisions remain bound to the exact version/hash the reviewer saw;
- audit mutations are attributed to the authenticated operator;
- production readiness remains separate from engineering/checkpoint success.

## Test cadence

- 457: focused workspace/loop/browser tests.
- 458: focused document/provenance/anchor tests.
- 459: focused long-run/restart/integration burn-in.
- 460: complete repository regression + phase chain + UI/browser matrix + bounded
  real public-source end-to-end research gate + recovery/reference verification.
