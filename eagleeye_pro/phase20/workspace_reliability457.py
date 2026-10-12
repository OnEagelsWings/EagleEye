from __future__ import annotations

import json

BUILD = "457.0"
POLICY_ID = "phase20.workspace-reliability-current-loop.v457"


class WorkspaceReliability457:
    """Corrects operator workspace selection and cycle-scoped recommendations.

    Historical loops remain visible, but operational state is derived from the
    newest active loop first, then the newest awaiting-authorization loop, then
    the newest historical loop. Prior-cycle/other-loop work never satisfies the
    current cycle's dispatch recommendation or budget.
    """

    def __init__(self, db, audit, *, workspace448, matrix418, synthesis419, actor="local-analyst"):
        self.db = db
        self.audit = audit
        self.workspace448 = workspace448
        self.matrix418 = matrix418
        self.synthesis419 = synthesis419
        self.actor = actor

    @staticmethod
    def _newest(rows, state):
        for row in reversed(rows):
            if str(row.get("state") or "") == state:
                return row
        return None

    def _analysis_for_loop(self, loop, identity):
        if not loop:
            return None, None
        matrix = None
        synthesis = None
        try:
            matrix = self.matrix418.matrix(session_id=loop["session_id"], identity=identity)
        except (KeyError, PermissionError, RuntimeError, ValueError):
            matrix = None
        row = self.db.one(
            "SELECT * FROM investigation_synthesis_419 WHERE session_id=? "
            "ORDER BY rowid DESC LIMIT 1",
            (str(loop["session_id"]),),
        )
        if row:
            synthesis = dict(row)
            try:
                synthesis["summary"] = json.loads(synthesis.get("summary_json") or "{}")
            except Exception:
                synthesis["summary"] = {}
        return matrix, synthesis

    def snapshot(self, *, identity, case_id):
        base = self.workspace448.snapshot(identity=identity, case_id=case_id)
        loops = list(base.get("loops") or [])
        latest_historical = loops[-1] if loops else None
        active_loop = self._newest(loops, "active")
        awaiting_loop = self._newest(loops, "awaiting_human_authorization")
        current_loop = active_loop or awaiting_loop or latest_historical

        dispatches = list(base.get("dispatches") or [])
        current_cycle = int((current_loop or {}).get("current_cycle") or 0)
        current_cycle_dispatches = [
            x for x in dispatches
            if current_loop
            and str(x.get("loop_id") or "") == str(current_loop.get("loop_id") or "")
            and int(x.get("cycle_number") or 0) == current_cycle
            and str(x.get("state") or "") != "failed"
        ]
        consumed_sources = {
            str(x.get("source_id") or "")
            for x in current_cycle_dispatches
            if str(x.get("source_id") or "")
        }
        max_tasks = int((current_loop or {}).get("scope", {}).get("max_collection_tasks_per_cycle") or 0)
        remaining = max(0, max_tasks - len(consumed_sources)) if current_loop else 0
        allowed = sorted({
            str(x)
            for x in (current_loop or {}).get("scope", {}).get("allowed_source_ids", [])
            if str(x)
        })
        recommended = []
        if current_loop and current_loop.get("state") == "active" and remaining:
            recommended = [x for x in allowed if x not in consumed_sources][:remaining]

        matrix, synthesis = self._analysis_for_loop(current_loop, identity)
        metrics = dict(base.get("metrics") or {})
        metrics["gaps"] = len((matrix or {}).get("gaps") or [])
        metrics["conflicts"] = len((matrix or {}).get("conflicts") or [])

        actions = []
        if not loops:
            actions.append({"view": "ai", "priority": "high", "label": "AI-Ermittlung anlegen"})
        elif active_loop:
            executable = [
                x for x in current_cycle_dispatches
                if x.get("state") in {"awaiting_path_confirmation", "replay_ready"}
            ]
            if executable:
                actions.append({"view": "research", "priority": "high", "label": "Vorbereitete Dispatches ausführen"})
            elif recommended:
                actions.append({"view": "research", "priority": "high", "label": "Quellen-Dispatch vorbereiten"})
            elif remaining == 0 and max_tasks:
                actions.append({"view": "research", "priority": "normal", "label": "Zyklusbudget ausgeschöpft – Ergebnisse prüfen"})
        elif awaiting_loop:
            actions.append({"view": "ai", "priority": "high", "label": "AI-Ermittlung freigeben"})
        elif latest_historical and latest_historical.get("state") == "review_required":
            actions.append({"view": "ai", "priority": "high", "label": "AI-Ermittlung prüfen"})

        if metrics.get("evidence_unreviewed"):
            actions.append({"view": "evidence", "priority": "high", "label": f"{metrics['evidence_unreviewed']} Evidence-Items prüfen"})
        if metrics.get("claims_review_required"):
            actions.append({"view": "claims", "priority": "high", "label": f"{metrics['claims_review_required']} Claims prüfen"})
        if metrics.get("gaps") or metrics.get("conflicts"):
            actions.append({"view": "claims", "priority": "medium", "label": f"{metrics['gaps']} Gaps / {metrics['conflicts']} Konflikte prüfen"})
        if metrics.get("claims_accepted") and not base.get("dossiers"):
            actions.append({"view": "dossier", "priority": "medium", "label": "Living Dossier erzeugen"})
        if metrics.get("dossiers_review_required"):
            actions.append({"view": "dossier", "priority": "high", "label": f"{metrics['dossiers_review_required']} Dossier-Revision(en) prüfen"})
        if not actions:
            actions.append({"view": "overview", "priority": "normal", "label": "Keine zwingende nächste Aktion"})

        base.update({
            "workspace_build": BUILD,
            "latest_historical_loop": latest_historical,
            "active_loop": active_loop,
            "awaiting_authorization_loop": awaiting_loop,
            "latest_loop": current_loop,
            "selected_loop": current_loop,
            "selected_loop_reason": (
                "newest_active"
                if active_loop
                else "newest_awaiting_authorization"
                if awaiting_loop
                else "latest_historical"
                if latest_historical
                else "none"
            ),
            "current_cycle_dispatches": current_cycle_dispatches,
            "recommended_dispatch_source_ids": recommended,
            "dispatch_budget": {
                "max_per_cycle": max_tasks,
                "reserved_or_consumed": len(consumed_sources),
                "remaining": remaining,
                "cycle_number": current_cycle,
                "loop_id": str((current_loop or {}).get("loop_id") or ""),
            },
            "matrix": matrix,
            "latest_synthesis": synthesis,
            "metrics": metrics,
            "next_actions": actions,
            "truth_determined": False,
        })
        return base

    def status(self):
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "active_loop_selected_independently": True,
            "loop_scoped_recommendations": True,
            "remaining_dispatch_budget_enforced": True,
            "prior_cycle_dispatch_leakage": False,
            "automatic_research_action": False,
            "automatic_truth_determination": False,
            "full_research_gate_this_build": False,
            "next_build": "458.0",
            "next_checkpoint": "460.0",
            "production_release_ready": False,
        }
