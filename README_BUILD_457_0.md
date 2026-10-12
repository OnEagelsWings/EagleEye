# Build 457 — Workspace Reliability + UI Functional Closure

Build 457 reconciles the deployment/reliability line with the EagleEye UI Audit findings before further analysis features are added.

## Correct operational loop selection

The investigator workspace now distinguishes:
- latest historical loop;
- newest active loop;
- newest loop awaiting authorization.

Operational recommendations prefer the newest **active** loop even when a newer historical loop is already completed/review-required. If no active loop exists, an awaiting-authorization loop is selected before historical-only state.

## Cycle-scoped dispatch logic

Dispatch recommendations and budget accounting are scoped to the selected loop and current cycle.

The authoritative per-cycle budget now applies in the backend dispatcher itself:
- existing non-failed tickets consume/reserve capacity;
- only genuinely new source dispatches consume remaining capacity;
- existing tickets remain idempotently addressable;
- prior-cycle and other-loop dispatches do not reduce the current cycle budget;
- requests exceeding the remaining budget fail closed.

The UI exposes maximum, reserved/consumed and remaining cycle budget.

## UI functional closure

The current workspace renders Build 457 and uses the corrected current-loop snapshot for Overview, Research and AI views. Historical dispatches remain visible as history, while they no longer alter current-cycle recommendations.

Responsive and keyboard-focus contracts remain retained. Build 457 is still a focused development build: the next complete repository/real-research checkpoint remains Build 460.

## Authority boundaries

Build 457 does not:
- auto-create or execute research actions;
- expand source scope;
- merge identities;
- accept Claims as truth;
- alter the four-eyes review boundary.

## Next

Build 458: Document Intelligence 2.0 with precise page/paragraph/table/footnote Evidence anchors.
