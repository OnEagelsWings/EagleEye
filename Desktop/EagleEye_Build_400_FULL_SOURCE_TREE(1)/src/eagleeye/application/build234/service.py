from __future__ import annotations

import hashlib
import html
import json
from typing import Any, Mapping

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _text(value: Any, limit: int = 20_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


class Build234QualificationRemediationService:
    """Governed remediation and full-suite requalification for Build-233 findings.

    A ticket is never considered fixed merely because an analyst changes its status.
    Build 234 requires: accepted ticket -> immutable remediation plan -> independent
    plan review -> full frozen-suite rerun under the same environment -> independent
    rerun review -> target-gate pass + collateral non-regression -> independent final
    verification review. No model/source/network action is performed automatically.
    """

    BUILD = "234.0"
    HIGHER_IS_BETTER = {
        "precision_at_k", "counter_evidence_recall", "cross_script_accuracy",
        "grounding_precision", "grounding_recall", "dialogue_correction_rate",
    }
    LOWER_IS_BETTER = {"false_merge_rate", "opsec_violation_rate", "runtime_p95_ms"}
    QUALITY_METRICS = HIGHER_IS_BETTER | {"false_merge_rate", "opsec_violation_rate"}
    ALL_GUARDRAILS = HIGHER_IS_BETTER | LOWER_IS_BETTER

    def __init__(self, db: Any, audit: Any, *, qualification: Any, campaign: Any, actor: str = "local-analyst") -> None:
        self.db, self.audit, self.qualification, self.campaign, self.actor = db, audit, qualification, campaign, actor

    def create_plan(self, *, ticket_id: str, root_cause: str, change_summary: str, verification_strategy: str, created_by: str, confirmation: str) -> dict[str, Any]:
        ticket = self._ticket(ticket_id)
        if confirmation != f"REMEDIATION PLAN 234 {ticket_id} ERSTELLEN":
            raise PermissionError("explicit approval required")
        latest = self._ticket_status(ticket_id)
        if latest not in {"accepted_for_234", "in_progress"}:
            raise PermissionError("ticket must be accepted for Build 234")
        existing = self.db.one("SELECT * FROM remediation_plans_234 WHERE ticket_id=?", (ticket_id,))
        if existing:
            return self._plan_payload(existing)
        root = _text(root_cause, 6000).strip(); change = _text(change_summary, 6000).strip(); strategy = _text(verification_strategy, 6000).strip()
        if min(len(root), len(change), len(strategy)) < 12:
            raise ValueError("substantive root cause, change summary and verification strategy required")
        impacted = _loads(ticket["impacted_cases_json"], [])
        guardrails = sorted(self.ALL_GUARDRAILS - {ticket["metric_key"]})
        plan_id, now = new_id("remplan234"), now_ts()
        payload = {
            "plan_id": plan_id, "ticket_id": ticket_id, "cycle_id": ticket["cycle_id"], "campaign_id": ticket["campaign_id"],
            "case_id": ticket["case_id"], "metric_key": ticket["metric_key"], "severity": ticket["severity"],
            "root_cause": root, "change_summary": change, "verification_strategy": strategy,
            "impacted_cases": impacted, "guardrail_metrics": guardrails, "created_by": created_by, "created_at": now,
        }
        self.db.execute("INSERT INTO remediation_plans_234 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            plan_id, ticket_id, ticket["cycle_id"], ticket["campaign_id"], ticket["case_id"], ticket["metric_key"], ticket["severity"],
            root, change, strategy, dumps(impacted), dumps(guardrails), created_by, now, _hash(payload),
        ))
        self.campaign.act_on_ticket(ticket_id=ticket_id, status="in_progress", note="Build 234 remediation plan created; independent plan review required.", actor=created_by, confirmation=f"REMEDIATION 233 {ticket_id} STATUS SPEICHERN")
        self._event(ticket["case_id"], "remediation_plan_created", "remediation_plan", plan_id, {"ticket_id": ticket_id, "metric": ticket["metric_key"], "guardrail_count": len(guardrails)}, created_by)
        return payload

    def review_plan(self, *, plan_id: str, decision: str, note: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        plan = self._plan(plan_id)
        if confirmation != f"REMEDIATION PLAN REVIEW 234 {plan_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == plan["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"approved", "rejected"}:
            raise ValueError("invalid review decision")
        if self.db.one("SELECT review_id FROM remediation_plan_reviews_234 WHERE plan_id=?", (plan_id,)):
            raise ValueError("plan already reviewed")
        note = _text(note, 6000).strip()
        if len(note) < 12:
            raise ValueError("substantive review note required")
        review_id, now = new_id("remplanreview234"), now_ts()
        payload = {"review_id": review_id, "plan_id": plan_id, "case_id": plan["case_id"], "decision": decision, "note": note, "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO remediation_plan_reviews_234 VALUES(?,?,?,?,?,?,?,?)", (review_id, plan_id, plan["case_id"], decision, note, reviewer, now, _hash(payload)))
        self._event(plan["case_id"], "remediation_plan_reviewed", "remediation_plan", plan_id, {"decision": decision}, reviewer)
        return payload

    def submit_rerun(self, *, plan_id: str, results: Mapping[str, Any], submitted_by: str, confirmation: str) -> dict[str, Any]:
        plan = self._plan(plan_id)
        if confirmation != f"REMEDIATION RERUN 234 {plan_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        review = self.db.one("SELECT * FROM remediation_plan_reviews_234 WHERE plan_id=?", (plan_id,))
        if not review or review["decision"] != "approved":
            raise PermissionError("approved independent remediation plan review required")
        cycle = self._cycle(plan["cycle_id"])
        campaign = self.db.one("SELECT * FROM qualification_campaigns_233 WHERE campaign_id=?", (plan["campaign_id"],))
        manifest = self.db.one("SELECT * FROM qualification_manifests_233 WHERE campaign_id=?", (plan["campaign_id"],))
        if not campaign or not manifest:
            raise PermissionError("frozen Build-233 campaign manifest required")
        trial = self.qualification.submit_trial(
            suite_id=campaign["suite_id"], system_label="candidate", build_label=self.BUILD,
            results=results, environment=_loads(manifest["environment_json"], {}), submitted_by=submitted_by,
            confirmation=f"PHASE8 TRIAL 232 {campaign['suite_id']} SPEICHERN",
        )
        rerun_id, now = new_id("remrerun234"), now_ts()
        payload = {
            "rerun_id": rerun_id, "plan_id": plan_id, "ticket_id": plan["ticket_id"], "case_id": plan["case_id"],
            "suite_id": campaign["suite_id"], "source_cycle_id": plan["cycle_id"], "source_candidate_scorecard_id": cycle["candidate_scorecard_id"],
            "baseline_scorecard_id": cycle["baseline_scorecard_id"], "trial_id": trial["trial_id"], "target_metric": plan["metric_key"],
            "submitted_by": submitted_by, "submitted_at": now,
        }
        self.db.execute("INSERT INTO remediation_reruns_234 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            rerun_id, plan_id, plan["ticket_id"], plan["case_id"], campaign["suite_id"], plan["cycle_id"], cycle["candidate_scorecard_id"],
            cycle["baseline_scorecard_id"], trial["trial_id"], plan["metric_key"], submitted_by, now, _hash(payload),
        ))
        self._event(plan["case_id"], "remediation_rerun_submitted", "remediation_rerun", rerun_id, {"trial_id": trial["trial_id"], "target_metric": plan["metric_key"], "full_suite_required": True}, submitted_by)
        return {**payload, "trial": trial, "automatic_resolution": False}

    def review_rerun(self, *, rerun_id: str, decision: str, note: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        rerun = self._rerun(rerun_id)
        if confirmation != f"REMEDIATION RERUN REVIEW 234 {rerun_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if self.db.one("SELECT rerun_review_id FROM remediation_rerun_reviews_234 WHERE rerun_id=?", (rerun_id,)):
            raise ValueError("rerun already reviewed")
        result = self.qualification.review_trial(
            trial_id=rerun["trial_id"], decision=decision, note=note, reviewer=reviewer,
            confirmation=f"PHASE8 TRIAL REVIEW 232 {rerun['trial_id']} SPEICHERN",
        )
        review_id, now = new_id("remrerunreview234"), now_ts()
        payload = {"rerun_review_id": review_id, "rerun_id": rerun_id, "case_id": rerun["case_id"], "decision": decision, "note": _text(note, 6000), "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO remediation_rerun_reviews_234 VALUES(?,?,?,?,?,?,?,?)", (review_id, rerun_id, rerun["case_id"], decision, payload["note"], reviewer, now, _hash(payload)))
        self._event(rerun["case_id"], "remediation_rerun_reviewed", "remediation_rerun", rerun_id, {"decision": decision}, reviewer)
        return {**payload, "trial_review": result}

    def finalize_verification(self, *, rerun_id: str, created_by: str, confirmation: str) -> dict[str, Any]:
        rerun = self._rerun(rerun_id)
        if confirmation != f"REMEDIATION VERIFY 234 {rerun_id} AUSWERTEN":
            raise PermissionError("explicit approval required")
        if self.db.one("SELECT verification_id FROM remediation_verifications_234 WHERE rerun_id=?", (rerun_id,)):
            row = self.db.one("SELECT * FROM remediation_verifications_234 WHERE rerun_id=?", (rerun_id,))
            return self._verification_payload(row)
        rr = self.db.one("SELECT * FROM remediation_rerun_reviews_234 WHERE rerun_id=?", (rerun_id,))
        if not rr or rr["decision"] != "accepted":
            raise PermissionError("accepted independent rerun review required")
        score = self.qualification.create_scorecard(
            trial_id=rerun["trial_id"], created_by=created_by,
            confirmation=f"PHASE8 SCORECARD 232 {rerun['trial_id']} ERSTELLEN",
        )
        comparison = self.qualification.compare_scorecards(
            baseline_scorecard_id=rerun["baseline_scorecard_id"], candidate_scorecard_id=score["scorecard_id"],
            created_by=created_by, confirmation=f"PHASE8 QUALIFICATION 232 {score['scorecard_id']} VERGLEICHEN",
        )
        before = self._scorecard(rerun["source_candidate_scorecard_id"])["metrics"]
        after = score["metrics"]
        target = rerun["target_metric"]
        guardrail_deltas: dict[str, Any] = {}
        failed_guardrails: list[str] = []
        for metric in sorted(self.ALL_GUARDRAILS - {target}):
            b = float(before.get(metric, 0.0)); a = float(after.get(metric, 0.0))
            delta = round(a - b, 4 if metric != "runtime_p95_ms" else 3)
            if metric in self.HIGHER_IS_BETTER:
                passed = a + 1e-9 >= b
            else:
                passed = a <= b + 1e-9
            guardrail_deltas[metric] = {"before": b, "after": a, "delta": delta, "pass": passed}
            if not passed:
                failed_guardrails.append(metric)
        target_gate = bool((comparison["gates"].get(target) or {}).get("pass"))
        quality_gates = {k: v for k, v in comparison["gates"].items() if k in self.QUALITY_METRICS}
        all_quality = bool(quality_gates) and all(bool(v.get("pass")) for v in quality_gates.values())
        collateral = not failed_guardrails
        comparable = bool(comparison["comparable_environment"])
        if not comparable:
            status = "incomplete"
        elif target_gate and all_quality and collateral and comparison["status"] == "pass_pending_review":
            status = "pass_pending_review"
        else:
            status = "needs_revision"
        target_before = float(before.get(target, 0.0)); target_after = float(after.get(target, 0.0))
        verification_id, now = new_id("remverify234"), now_ts()
        payload = {
            "verification_id": verification_id, "rerun_id": rerun_id, "plan_id": rerun["plan_id"], "ticket_id": rerun["ticket_id"],
            "case_id": rerun["case_id"], "target_metric": target, "scorecard_id": score["scorecard_id"], "comparison_id": comparison["comparison_id"],
            "target_gate_pass": target_gate, "all_quality_gates_pass": all_quality, "collateral_non_regression": collateral,
            "comparable_environment": comparable, "target_before": target_before, "target_after": target_after,
            "guardrail_deltas": guardrail_deltas, "failed_guardrails": failed_guardrails, "status": status,
            "created_by": created_by, "created_at": now, "automatic_resolution": False,
        }
        self.db.execute("INSERT INTO remediation_verifications_234 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            verification_id, rerun_id, rerun["plan_id"], rerun["ticket_id"], rerun["case_id"], target, score["scorecard_id"], comparison["comparison_id"],
            int(target_gate), int(all_quality), int(collateral), int(comparable), target_before, target_after, dumps(guardrail_deltas), dumps(failed_guardrails), status,
            created_by, now, _hash(payload),
        ))
        self._event(rerun["case_id"], "remediation_verified", "remediation_verification", verification_id, {"ticket_id": rerun["ticket_id"], "status": status, "target_gate_pass": target_gate, "failed_guardrails": failed_guardrails}, created_by)
        return {**payload, "scorecard": score, "comparison": comparison}

    def review_verification(self, *, verification_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        verification = self._verification(verification_id)
        if confirmation != f"REMEDIATION VERIFY REVIEW 234 {verification_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == verification["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"resolved", "needs_revision", "rejected"}:
            raise ValueError("invalid review decision")
        if decision == "resolved" and verification["status"] != "pass_pending_review":
            raise ValueError("remediation verification gates did not pass")
        if self.db.one("SELECT verification_review_id FROM remediation_verification_reviews_234 WHERE verification_id=?", (verification_id,)):
            raise ValueError("verification already reviewed")
        rationale = _text(rationale, 6000).strip()
        if len(rationale) < 12:
            raise ValueError("substantive rationale required")
        review_id, now = new_id("remverifyreview234"), now_ts()
        payload = {"verification_review_id": review_id, "verification_id": verification_id, "case_id": verification["case_id"], "decision": decision, "rationale": rationale, "reviewer": reviewer, "reviewed_at": now, "release_authorized": False}
        self.db.execute("INSERT INTO remediation_verification_reviews_234 VALUES(?,?,?,?,?,?,?,?)", (review_id, verification_id, verification["case_id"], decision, rationale, reviewer, now, _hash(payload)))
        if decision == "resolved":
            self.campaign.act_on_ticket(
                ticket_id=verification["ticket_id"], status="resolved",
                note=f"Build 234 verification {verification_id} passed target gate and collateral non-regression; independently reviewed by {reviewer}.",
                actor=reviewer, confirmation=f"REMEDIATION 233 {verification['ticket_id']} STATUS SPEICHERN",
            )
        self._event(verification["case_id"], "remediation_verification_reviewed", "remediation_verification", verification_id, {"decision": decision, "ticket_id": verification["ticket_id"], "release_authorized": False}, reviewer)
        return payload

    def readiness(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        tickets = self.db.all("SELECT * FROM remediation_tickets_233 WHERE case_id=? AND target_build='234.0' ORDER BY rowid", (case_id,))
        rows = []
        for ticket in tickets:
            status = self._ticket_status(ticket["ticket_id"])
            plan = self.db.one("SELECT * FROM remediation_plans_234 WHERE ticket_id=?", (ticket["ticket_id"],))
            resolved_review = None
            if plan:
                resolved_review = self.db.one("SELECT r.* FROM remediation_verification_reviews_234 r JOIN remediation_verifications_234 v ON v.verification_id=r.verification_id WHERE v.ticket_id=? AND r.decision='resolved' ORDER BY r.rowid DESC LIMIT 1", (ticket["ticket_id"],))
            rows.append({"ticket_id": ticket["ticket_id"], "metric_key": ticket["metric_key"], "severity": ticket["severity"], "status": status, "plan_id": plan["plan_id"] if plan else None, "verified_resolved": bool(resolved_review)})
        accepted = [r for r in rows if r["status"] in {"accepted_for_234", "in_progress", "resolved"}]
        unresolved = [r for r in accepted if not r["verified_resolved"]]
        if not tickets:
            status = "no_remediation_required"
        elif accepted and not unresolved and all(r["verified_resolved"] for r in accepted):
            status = "remediation_complete"
        elif unresolved:
            status = "remediation_in_progress"
        else:
            status = "tickets_awaiting_acceptance"
        return {"build": self.BUILD, "case_id": case_id, "status": status, "ticket_count": len(tickets), "accepted_count": len(accepted), "unresolved_count": len(unresolved), "tickets": rows, "release_authorized": False, "next_build": "235.0" if status in {"no_remediation_required", "remediation_complete"} else None}

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        return {
            "build": self.BUILD,
            "plans": self.db.all("SELECT * FROM remediation_plans_234 WHERE case_id=? ORDER BY rowid DESC LIMIT 40", (case_id,)),
            "reruns": self.db.all("SELECT * FROM remediation_reruns_234 WHERE case_id=? ORDER BY rowid DESC LIMIT 40", (case_id,)),
            "verifications": self.db.all("SELECT * FROM remediation_verifications_234 WHERE case_id=? ORDER BY rowid DESC LIMIT 40", (case_id,)),
            "reviews": self.db.all("SELECT * FROM remediation_verification_reviews_234 WHERE case_id=? ORDER BY rowid DESC LIMIT 40", (case_id,)),
            "readiness": self.readiness(case_id=case_id),
            "policy": {"full_suite_rerun": True, "same_environment": True, "target_gate_required": True, "collateral_non_regression": True, "independent_reviews": True, "automatic_network": False, "automatic_release": False},
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        data = self.dashboard(case_id=case_id); esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
        plans = data["plans"]
        latest_plan = plans[0]["plan_id"] if plans else ""
        readiness = data["readiness"]
        return f"""
<section class='card' id='build234_remediation'>
<h2>Build 234 – Qualification Remediation</h2>
<p>Ein Ticket gilt erst nach genehmigtem Fix-Plan, vollständigem Suite-Rerun, Target-Gate und <strong>Collateral Non-Regression</strong> als behoben.</p>
<div class='grid two'>
<div class='card'><h3>Remediation-Plan</h3><form method='post' action='/build234/plan-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='ticket_id' placeholder='Build-233 Ticket-ID' required><textarea name='root_cause' placeholder='Root cause' required></textarea><textarea name='change_summary' placeholder='Gezielte Änderung / Fix' required></textarea><textarea name='verification_strategy' placeholder='Wie wird der Fix gegen die eingefrorene Suite geprüft?' required></textarea><button>Plan erstellen</button></form></div>
<div class='card'><h3>Plan unabhängig prüfen</h3><form method='post' action='/build234/plan-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='plan_id' value='{esc(latest_plan)}' placeholder='Plan-ID' required><select name='decision'><option>approved</option><option>rejected</option></select><textarea name='note' placeholder='Unabhängige Review-Notiz' required></textarea><button>Plan prüfen</button></form></div>
<div class='card'><h3>Vollständigen Rerun speichern</h3><form method='post' action='/build234/rerun-submit'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='plan_id' value='{esc(latest_plan)}' placeholder='Plan-ID' required><textarea name='results_json' placeholder='Vollständige Ergebnis-JSON aller 14 eingefrorenen Fälle' required></textarea><button>Rerun reviewpflichtig speichern</button></form></div>
<div class='card'><h3>Rerun prüfen</h3><form method='post' action='/build234/rerun-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='rerun_id' placeholder='Rerun-ID' required><select name='decision'><option>accepted</option><option>rejected</option></select><textarea name='note' placeholder='Unabhängige Prüfung des Messlaufs' required></textarea><button>Rerun prüfen</button></form></div>
<div class='card'><h3>Verification auswerten</h3><form method='post' action='/build234/verify'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='rerun_id' placeholder='Rerun-ID' required><button>Target + Guardrails prüfen</button></form></div>
<div class='card'><h3>Verification unabhängig freigeben</h3><form method='post' action='/build234/verify-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='verification_id' placeholder='Verification-ID' required><select name='decision'><option>resolved</option><option>needs_revision</option><option>rejected</option></select><textarea name='rationale' placeholder='Begründete Entscheidung' required></textarea><button>Review speichern</button></form></div>
</div>
<p><strong>Status:</strong> {esc(readiness['status'])} · Tickets: {readiness['ticket_count']} · angenommen: {readiness['accepted_count']} · offen in 234: {readiness['unresolved_count']}</p>
<p><strong>Guardrail:</strong> Ein repariertes Zielmetric reicht nicht; jede nicht betroffene Qualitätsmetrik muss mindestens auf dem Stand des ursprünglichen Candidate-Runs bleiben.</p>
</section>"""

    def _ticket(self, ticket_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM remediation_tickets_233 WHERE ticket_id=?", (ticket_id,))
        if not row: raise KeyError("remediation ticket not found")
        return dict(row)

    def _ticket_status(self, ticket_id: str) -> str:
        row = self.db.one("SELECT status FROM remediation_ticket_actions_233 WHERE ticket_id=? ORDER BY rowid DESC LIMIT 1", (ticket_id,))
        return str((row or {"status": "open"})["status"])

    def _plan(self, plan_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM remediation_plans_234 WHERE plan_id=?", (plan_id,))
        if not row: raise KeyError("remediation plan not found")
        return dict(row)

    def _plan_payload(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "impacted_cases": _loads(row["impacted_cases_json"], []), "guardrail_metrics": _loads(row["guardrail_metrics_json"], [])}

    def _cycle(self, cycle_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM qualification_cycles_233 WHERE cycle_id=?", (cycle_id,))
        if not row: raise KeyError("qualification cycle not found")
        return dict(row)

    def _rerun(self, rerun_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM remediation_reruns_234 WHERE rerun_id=?", (rerun_id,))
        if not row: raise KeyError("remediation rerun not found")
        return dict(row)

    def _scorecard(self, scorecard_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM qualification_scorecards_232 WHERE scorecard_id=?", (scorecard_id,))
        if not row: raise KeyError("qualification scorecard not found")
        return {**dict(row), "metrics": _loads(row["metrics_json"], {}), "per_case": _loads(row["per_case_json"], [])}

    def _verification(self, verification_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM remediation_verifications_234 WHERE verification_id=?", (verification_id,))
        if not row: raise KeyError("remediation verification not found")
        return self._verification_payload(row)

    def _verification_payload(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "target_gate_pass": bool(row["target_gate_pass"]), "all_quality_gates_pass": bool(row["all_quality_gates_pass"]), "collateral_non_regression": bool(row["collateral_non_regression"]), "comparable_environment": bool(row["comparable_environment"]), "guardrail_deltas": _loads(row["guardrail_deltas_json"], {}), "failed_guardrails": _loads(row["failed_guardrails_json"], [])}

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError("case not found")

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> None:
        prev = self.db.one("SELECT event_hash FROM build234_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = (prev or {"event_hash": ""})["event_hash"]
        event_id, now = new_id("event234"), now_ts()
        body = {"event_id": event_id, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": dict(payload), "previous_hash": previous, "created_at": now}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build234_events VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, case_id, event_type, object_type, object_id, actor, dumps(dict(payload)), previous, event_hash, now))
