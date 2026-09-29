# Build 448 UI and functionality audit

## Scope

The audit evaluates the **current primary operator surface**, not every historical compatibility screen.

### Structural checks

- eight primary case-scoped views are reachable;
- current build branding is shown;
- responsive viewport and breakpoints exist;
- keyboard focus is visible;
- main/nav landmarks exist;
- status feedback uses an aria-live region;
- Legacy/Expert workspace remains reachable.

### Functional route checks

The UI audit verifies that the application still registers the required routes for:

- Build 439 create/authorize/advance;
- Build 446 prepare/execute;
- Build 447 Evidence sync/review;
- Build 447 Claim create/review;
- Build 447 Dossier create/review/export.

The audit checks route presence. The integrated tests additionally execute representative flows.

## Recurrence

Two recurring mechanisms are intended:

1. GitHub Actions scheduled UI audit workflow.
2. Periodic independent review of UI clarity/functionality plus GitHub Codex PR review.

These reviews should treat regressions in clarity, dead controls, stale build wording, hidden core workflow actions, and broken route contracts as release blockers for subsequent UI-facing builds.
