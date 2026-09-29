# EagleEye Build 448.0 — Investigator Workspace + UI Audit

Build 448 replaces the primary workspace with a case-first operator surface and adds repeatable UI functionality audits.

## Why this build was necessary

The previous primary navigation was visually reduced, but the visible shell still identified itself as a Phase-13 workspace and delegated most sections through historical Build-340/343 rendering chains. The current Build-439/446/447 investigation flow existed technically but was not presented as one coherent operator workflow.

Build 448 makes the current flow the default UI.

## Primary workspace

The main navigation now contains eight case-scoped views:

1. Übersicht
2. Recherche
3. AI-Ermittlung
4. Evidence
5. Claims & Hypothesen
6. Graph & Timeline
7. Dossier
8. OPSEC & Team

The historical workspace remains available at `/legacy` for expert/specialized functions.

## Functional actions surfaced in the UI

The workspace can invoke the already-governed APIs for:

- Build-439 investigation-loop creation, authorization and bounded advance;
- Build-446 source dispatch preparation and individually confirmed acquisition;
- Build-447 Evidence synchronization and review;
- Build-447 Claim proposal and human review;
- Build-447 Living-Dossier creation, review and export.

The UI does not bypass any confirmation phrase or capability check.

## UI audit

Build 448 records repeatable audits in `ui_audit_448`.

Checks include:

- document and language metadata;
- viewport and responsive layout;
- semantic main/navigation landmarks;
- visible status feedback region;
- keyboard focus styling;
- absence of the stale Phase-13 primary branding;
- presence of all eight primary views;
- availability of the legacy workspace;
- visibility of the Evidence/Claim/Dossier truth boundary;
- registration of all required Build-439/446/447 read and mutation routes.

Warnings also flag excessive initial markup, table density, disclosure density and inline click handlers.

UI audit results are hash-bound and retained per case.

## GitHub CI

Build 448 adds a scheduled GitHub UI audit workflow in addition to the normal PR CI. The scheduled job exercises structural UI and route-contract tests even when no feature PR is active.

GitHub Copilot code review should also be requested on UI-related PRs when available in the repository.

## Deliberate boundaries

Build 448 does not:

- add new network authority;
- bypass per-path Build-446 confirmation;
- auto-review Evidence or Claims;
- determine truth;
- auto-publish Dossiers;
- remove the Legacy/Expert workspace.

Production readiness remains false.

Next: Build 449 — Human Review / Team Workflow.
