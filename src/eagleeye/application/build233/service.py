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


class Build233Phase8RealQualificationService:
    """Governed Phase-8 baseline-vs-current qualification campaign manager.

    Build 233 operationalizes the Build-232 harness. It does not claim real-world
    superiority from synthetic/redacted fixtures. It freezes a reproducible
    execution manifest, blind-codes the baseline/current arms, delegates scoring
    to Build 232, and converts failed gates into explicit Build-234 remediation
    tickets. No network action, model switch, source activation or policy change
    is performed by this service.
    """

    BUILD = "233.0"
    PROTOCOL_VERSION = 1
    BASELINE_BUILD = "223.0"
    CANDIDATE_BUILD = "232.0"

    REMEDIATION = {
        "precision_at_k": ("high", "Retrieval-Precision unter Soll", "Build 234: Ranking-/Retrieval-Fehler anhand der betroffenen Goldstandardfälle analysieren und gezielt korrigieren."),
        "counter_evidence_recall": ("critical", "Gegenbeleg-Recall unter Soll", "Build 234: Gegenbelegsuche und Widerspruchspriorisierung korrigieren; keine Freigabe bis der Recall-Gate erneut besteht."),
        "cross_script_accuracy": ("high", "Cross-Script-Identität unter Soll", "Build 234: Transliteration/Identity-Candidate-Generation gegen Hard Positives und Hard Negatives nachschärfen."),
        "false_merge_rate": ("critical", "False-Merge-Rate über Soll", "Build 234: konservative Merge-Gates verschärfen und betroffene Identity-Hard-Negatives als Pflichtregression übernehmen."),
        "grounding_precision": ("critical", "Grounding-Precision unter Soll", "Build 234: Citation/Claim-Binding korrigieren; unbelegte Referenzen müssen hart blockiert werden."),
        "grounding_recall": ("high", "Grounding-Recall unter Soll", "Build 234: Evidenzabdeckung und Claim-to-Evidence-Zuordnung korrigieren, ohne Precision zu verschlechtern."),
        "opsec_violation_rate": ("critical", "OPSEC-Gate verletzt", "Build 234: auslösenden Aktionspfad isolieren und durch ein hartes Human-/Policy-Gate blockieren."),
        "dialogue_correction_rate": ("high", "Dialogkorrektur unter Soll", "Build 234: Co-AI muss Gegenbelege aktiv verarbeiten, Confidence absenken und frühere Hypothesen nachvollziehbar korrigieren."),
        "runtime_p95_ms": ("medium", "p95-Laufzeit über Soll", "Build 234: Hotspots profilieren und optimieren; Qualitätsgates dürfen dabei nicht gelockert werden."),
    }

    FAMILY_BY_METRIC = {
        "precision_at_k": "retrieval_precision",
        "counter_evidence_recall": "counterevidence_recall",
        "cross_script_accuracy": "identity_resolution",
        "false_merge_rate": "identity_resolution",
        "grounding_precision": "grounding",
        "grounding_recall": "grounding",
        "opsec_violation_rate": "opsec",
        "dialogue_correction_rate": "dialogue_correction",
        "runtime_p95_ms": "*",
    }

    def __init__(self, db: Any, audit: Any, *, qualification: Any, actor: str = "local-analyst") -> None:
        self.db, self.audit, self.qualification, self.actor = db, audit, qualification, actor

    def create_campaign(self, *, case_id: str, suite_id: str, title: str, created_by: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        suite = self.db.one("SELECT * FROM qualification_suites_232 WHERE suite_id=? AND case_id=?", (suite_id, case_id))
        if not suite:
            raise KeyError("qualification suite not found for case")
        if confirmation != f"PHASE8 CAMPAIGN 233 {case_id} ERSTELLEN":
            raise PermissionError("explicit approval required")
        existing = self.db.one("SELECT * FROM qualification_campaigns_233 WHERE case_id=? AND suite_id=? AND protocol_version=?", (case_id, suite_id, self.PROTOCOL_VERSION))
        if existing:
            return self._campaign_payload(existing)
        campaign_id, now = new_id("qualcampaign233"), now_ts()
        seed = _hash({"campaign_id": campaign_id, "suite_id": suite_id, "case_id": case_id})
        baseline_code = "ARM-" + seed[:10].upper()
        candidate_code = "ARM-" + seed[10:20].upper()
        payload = {
            "campaign_id": campaign_id, "case_id": case_id, "suite_id": suite_id,
            "title": _text(title, 240).strip() or "Phase-8 223→232 Qualification Campaign",
            "baseline_build": self.BASELINE_BUILD, "candidate_build": self.CANDIDATE_BUILD,
            "baseline_arm_code": baseline_code, "candidate_arm_code": candidate_code,
            "protocol_version": self.PROTOCOL_VERSION, "created_by": created_by, "created_at": now,
            "fixture_kind": suite["fixture_kind"], "real_world_claim_allowed": False,
        }
        self.db.execute(
            "INSERT INTO qualification_campaigns_233 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (campaign_id, case_id, suite_id, payload["title"], self.BASELINE_BUILD, self.CANDIDATE_BUILD, baseline_code, candidate_code, self.PROTOCOL_VERSION, created_by, now, _hash(payload)),
        )
        self._event(case_id, "qualification_campaign_created", "qualification_campaign", campaign_id, {"suite_id": suite_id, "blind_arms": True, "real_world_claim_allowed": False}, created_by)
        return payload

    def freeze_manifest(self, *, campaign_id: str, environment: Mapping[str, Any], protocol_notes: str, created_by: str, confirmation: str) -> dict[str, Any]:
        campaign = self._campaign(campaign_id)
        if confirmation != f"PHASE8 MANIFEST 233 {campaign_id} EINFRIEREN":
            raise PermissionError("explicit approval required")
        existing = self.db.one("SELECT * FROM qualification_manifests_233 WHERE campaign_id=?", (campaign_id,))
        if existing:
            return self._manifest_payload(existing)
        env = dict(environment or {})
        if not env:
            raise ValueError("environment fingerprint data required")
        notes = _text(protocol_notes, 5000).strip()
        if len(notes) < 12:
            raise ValueError("substantive protocol notes required")
        cases = self.db.all("SELECT qualification_case_id,payload_sha256 FROM qualification_cases_232 WHERE suite_id=? ORDER BY ordinal", (campaign["suite_id"],))
        if not cases:
            raise ValueError("qualification suite has no frozen cases")
        suite_sha = _hash([(r["qualification_case_id"], r["payload_sha256"]) for r in cases])
        manifest_id, now = new_id("qualmanifest233"), now_ts()
        payload = {
            "manifest_id": manifest_id, "campaign_id": campaign_id, "case_id": campaign["case_id"],
            "environment": env, "environment_sha256": _hash(env), "suite_sha256": suite_sha,
            "protocol_notes": notes, "network_policy": "no_autonomous_network", "execution_policy": "human_governed",
            "created_by": created_by, "created_at": now,
        }
        self.db.execute(
            "INSERT INTO qualification_manifests_233 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (manifest_id, campaign_id, campaign["case_id"], dumps(env), payload["environment_sha256"], suite_sha, notes, "no_autonomous_network", "human_governed", created_by, now, _hash(payload)),
        )
        self._event(campaign["case_id"], "qualification_manifest_frozen", "qualification_manifest", manifest_id, {"environment_sha256": payload["environment_sha256"], "suite_sha256": suite_sha}, created_by)
        return payload

    def submit_arm(self, *, campaign_id: str, arm_code: str, results: Mapping[str, Any], submitted_by: str, confirmation: str) -> dict[str, Any]:
        campaign = self._campaign(campaign_id)
        manifest = self.db.one("SELECT * FROM qualification_manifests_233 WHERE campaign_id=?", (campaign_id,))
        if not manifest:
            raise PermissionError("frozen execution manifest required")
        if confirmation != f"PHASE8 ARM 233 {campaign_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        arm_code = _text(arm_code, 64).strip()
        if arm_code == campaign["baseline_arm_code"]:
            role, system_label, build_label = "baseline", self.qualification.BASELINE_LABEL, self.BASELINE_BUILD
        elif arm_code == campaign["candidate_arm_code"]:
            role, system_label, build_label = "candidate", self.qualification.CURRENT_LABEL, self.CANDIDATE_BUILD
        else:
            raise ValueError("unknown blind arm code")
        if self.db.one("SELECT trial_id FROM qualification_arm_links_233 WHERE campaign_id=? AND arm_role=?", (campaign_id, role)):
            raise ValueError(f"{role} arm already submitted")
        trial = self.qualification.submit_trial(
            suite_id=campaign["suite_id"], system_label=system_label, build_label=build_label,
            results=results, environment=_loads(manifest["environment_json"], {}), submitted_by=submitted_by,
            confirmation=f"PHASE8 TRIAL 232 {campaign['suite_id']} SPEICHERN",
        )
        link_id, now = new_id("qualarm233"), now_ts()
        payload = {"arm_link_id": link_id, "campaign_id": campaign_id, "case_id": campaign["case_id"], "arm_code": arm_code, "arm_role": role, "trial_id": trial["trial_id"], "submitted_by": submitted_by, "submitted_at": now}
        self.db.execute("INSERT INTO qualification_arm_links_233 VALUES(?,?,?,?,?,?,?,?,?)", (link_id, campaign_id, campaign["case_id"], arm_code, role, trial["trial_id"], submitted_by, now, _hash(payload)))
        self._event(campaign["case_id"], "qualification_arm_submitted", "qualification_arm", link_id, {"arm_role": role, "trial_id": trial["trial_id"], "blind_code_used": True}, submitted_by)
        return {**payload, "trial": trial}

    def review_arm(self, *, trial_id: str, decision: str, note: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        link = self.db.one("SELECT * FROM qualification_arm_links_233 WHERE trial_id=?", (trial_id,))
        if not link:
            raise KeyError("Build-233 arm trial not found")
        if confirmation != f"PHASE8 ARM REVIEW 233 {trial_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        result = self.qualification.review_trial(
            trial_id=trial_id, decision=decision, note=note, reviewer=reviewer,
            confirmation=f"PHASE8 TRIAL REVIEW 232 {trial_id} SPEICHERN",
        )
        self._event(link["case_id"], "qualification_arm_reviewed", "qualification_arm", link["arm_link_id"], {"trial_id": trial_id, "decision": decision}, reviewer)
        return result

    def finalize_cycle(self, *, campaign_id: str, created_by: str, confirmation: str) -> dict[str, Any]:
        campaign = self._campaign(campaign_id)
        if confirmation != f"PHASE8 CYCLE 233 {campaign_id} AUSWERTEN":
            raise PermissionError("explicit approval required")
        links = {r["arm_role"]: r for r in self.db.all("SELECT * FROM qualification_arm_links_233 WHERE campaign_id=?", (campaign_id,))}
        if set(links) != {"baseline", "candidate"}:
            raise PermissionError("both blind arms are required")
        scorecards = {}
        for role in ("baseline", "candidate"):
            trial_id = links[role]["trial_id"]
            review = self.db.one("SELECT * FROM qualification_trial_reviews_232 WHERE trial_id=?", (trial_id,))
            if not review or review["decision"] != "accepted":
                raise PermissionError(f"accepted independent review required for {role} arm")
            scorecards[role] = self.qualification.create_scorecard(trial_id=trial_id, created_by=created_by, confirmation=f"PHASE8 SCORECARD 232 {trial_id} ERSTELLEN")
        comparison = self.qualification.compare_scorecards(
            baseline_scorecard_id=scorecards["baseline"]["scorecard_id"], candidate_scorecard_id=scorecards["candidate"]["scorecard_id"],
            created_by=created_by, confirmation=f"PHASE8 QUALIFICATION 232 {scorecards['candidate']['scorecard_id']} VERGLEICHEN",
        )
        previous = self.db.one("SELECT MAX(cycle_number) AS n FROM qualification_cycles_233 WHERE campaign_id=?", (campaign_id,))
        cycle_number = int(previous["n"] or 0) + 1
        failed = [k for k, v in comparison["gates"].items() if not bool(v.get("pass"))]
        status = "pass_pending_review" if comparison["status"] == "pass_pending_review" else ("incomplete" if comparison["status"] == "incomplete" else "needs_remediation")
        cycle_id, now = new_id("qualcycle233"), now_ts()
        payload = {
            "cycle_id": cycle_id, "campaign_id": campaign_id, "case_id": campaign["case_id"], "cycle_number": cycle_number,
            "baseline_scorecard_id": scorecards["baseline"]["scorecard_id"], "candidate_scorecard_id": scorecards["candidate"]["scorecard_id"],
            "comparison_id": comparison["comparison_id"], "failed_gates": failed, "status": status,
            "synthetic_qualification": True, "real_world_claim_allowed": False, "created_by": created_by, "created_at": now,
        }
        self.db.execute(
            "INSERT INTO qualification_cycles_233 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (cycle_id, campaign_id, campaign["case_id"], cycle_number, payload["baseline_scorecard_id"], payload["candidate_scorecard_id"], comparison["comparison_id"], dumps(failed), status, 1, 0, created_by, now, _hash(payload)),
        )
        tickets = self._create_remediation_tickets(cycle_id=cycle_id, campaign=campaign, comparison=comparison, candidate_scorecard=scorecards["candidate"], created_by=created_by)
        self._event(campaign["case_id"], "qualification_cycle_finalized", "qualification_cycle", cycle_id, {"status": status, "failed_gates": failed, "ticket_count": len(tickets), "real_world_claim_allowed": False}, created_by)
        return {**payload, "comparison": comparison, "remediation_tickets": tickets}

    def review_cycle(self, *, cycle_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        cycle = self._cycle(cycle_id)
        if confirmation != f"PHASE8 CYCLE REVIEW 233 {cycle_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == cycle["created_by"]:
            raise PermissionError("independent reviewer required")
        if self.db.one("SELECT cycle_review_id FROM qualification_cycle_reviews_233 WHERE cycle_id=?", (cycle_id,)):
            raise ValueError("cycle already reviewed")
        if decision not in {"phase8_qualified", "needs_remediation", "rejected"}:
            raise ValueError("invalid review decision")
        rationale = _text(rationale, 5000).strip()
        if len(rationale) < 12:
            raise ValueError("substantive rationale required")
        if decision == "phase8_qualified" and cycle["status"] != "pass_pending_review":
            raise ValueError("qualification gates did not pass")
        mapped = "qualified" if decision == "phase8_qualified" else ("needs_revision" if decision == "needs_remediation" else "rejected")
        comparison_review = self.qualification.review_comparison(
            comparison_id=cycle["comparison_id"], decision=mapped, rationale=rationale, reviewer=reviewer,
            confirmation=f"PHASE8 QUALIFICATION REVIEW 232 {cycle['comparison_id']} SPEICHERN",
        )
        review_id, now = new_id("qualcyclereview233"), now_ts()
        payload = {"cycle_review_id": review_id, "cycle_id": cycle_id, "campaign_id": cycle["campaign_id"], "case_id": cycle["case_id"], "decision": decision, "rationale": rationale, "reviewer": reviewer, "reviewed_at": now, "phase8_qualified": decision == "phase8_qualified", "real_world_qualified": False, "release_authorized": False}
        self.db.execute("INSERT INTO qualification_cycle_reviews_233 VALUES(?,?,?,?,?,?,?,?,?)", (review_id, cycle_id, cycle["campaign_id"], cycle["case_id"], decision, rationale, reviewer, now, _hash(payload)))
        self._event(cycle["case_id"], "qualification_cycle_reviewed", "qualification_cycle", cycle_id, {"decision": decision, "phase8_qualified": payload["phase8_qualified"], "real_world_qualified": False}, reviewer)
        return {**payload, "comparison_review": comparison_review}

    def act_on_ticket(self, *, ticket_id: str, status: str, note: str, actor: str, confirmation: str) -> dict[str, Any]:
        ticket = self.db.one("SELECT * FROM remediation_tickets_233 WHERE ticket_id=?", (ticket_id,))
        if not ticket:
            raise KeyError("remediation ticket not found")
        if confirmation != f"REMEDIATION 233 {ticket_id} STATUS SPEICHERN":
            raise PermissionError("explicit approval required")
        if status not in {"open", "accepted_for_234", "in_progress", "resolved", "wont_fix"}:
            raise ValueError("invalid remediation status")
        note = _text(note, 5000).strip()
        if len(note) < 5:
            raise ValueError("remediation note required")
        action_id, now = new_id("remaction233"), now_ts()
        payload = {"action_id": action_id, "ticket_id": ticket_id, "case_id": ticket["case_id"], "status": status, "note": note, "actor": actor, "created_at": now}
        self.db.execute("INSERT INTO remediation_ticket_actions_233 VALUES(?,?,?,?,?,?,?,?)", (action_id, ticket_id, ticket["case_id"], status, note, actor, now, _hash(payload)))
        self._event(ticket["case_id"], "remediation_ticket_action", "remediation_ticket", ticket_id, {"status": status, "target_build": ticket["target_build"]}, actor)
        return payload

    def execution_packet(self, *, campaign_id: str) -> dict[str, Any]:
        campaign = self._campaign(campaign_id)
        manifest = self.db.one("SELECT * FROM qualification_manifests_233 WHERE campaign_id=?", (campaign_id,))
        cases = self.db.all("SELECT qualification_case_id,ordinal,metric_family,title,language,cross_script,input_json,expected_json,weight,payload_sha256 FROM qualification_cases_232 WHERE suite_id=? ORDER BY ordinal", (campaign["suite_id"],))
        return {
            "build": self.BUILD, "protocol_version": self.PROTOCOL_VERSION,
            "campaign": {k: campaign[k] for k in ("campaign_id", "case_id", "suite_id", "title", "baseline_build", "candidate_build", "baseline_arm_code", "candidate_arm_code")},
            "manifest": self._manifest_payload(manifest) if manifest else None,
            "cases": [{**dict(r), "input": _loads(r["input_json"], {}), "expected": _loads(r["expected_json"], {})} for r in cases],
            "interpretation_policy": {
                "fixture_kind": "synthetic_redacted", "phase8_internal_qualification_allowed": True,
                "real_world_performance_claim_allowed": False, "automatic_release": False,
                "automatic_model_switch": False, "automatic_source_activation": False, "network_execution": False,
            },
        }

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        campaigns = self.db.all("SELECT * FROM qualification_campaigns_233 WHERE case_id=? ORDER BY rowid DESC LIMIT 10", (case_id,))
        cycles = self.db.all("SELECT * FROM qualification_cycles_233 WHERE case_id=? ORDER BY rowid DESC LIMIT 20", (case_id,))
        tickets = self.db.all("SELECT * FROM remediation_tickets_233 WHERE case_id=? ORDER BY rowid DESC LIMIT 40", (case_id,))
        reviews = self.db.all("SELECT * FROM qualification_cycle_reviews_233 WHERE case_id=? ORDER BY rowid DESC LIMIT 20", (case_id,))
        return {
            "build": self.BUILD, "campaigns": campaigns, "cycles": cycles, "tickets": tickets, "reviews": reviews,
            "policy": {"synthetic_redacted": True, "blind_arms": True, "immutable_manifest": True, "independent_review": True, "real_world_claim_allowed": False, "automatic_release": False, "target_remediation_build": "234.0"},
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        data = self.dashboard(case_id=case_id)
        esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
        campaigns = data["campaigns"]
        latest = campaigns[0] if campaigns else None
        campaign_id = latest["campaign_id"] if latest else ""
        return f"""
<section class='card' id='build233_qualification'>
<h2>Build 233 – Phase-8 Real Qualification Campaign</h2>
<p>Operationalisiert den eingefrorenen Build-232-Harness als blind codierten, reproduzierbaren 223→232-Qualifikationsprozess. <strong>Keine Realwelt-Leistungsbehauptung</strong> aus synthetisch/redigierten Fixtures.</p>
<div class='grid'>
<div class='card'><h3>Campaign anlegen</h3><form method='post' action='/build233/campaign-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='suite_id' placeholder='Build-232 Suite-ID' required><input name='title' value='Phase-8 223→232 Qualification Campaign'><button>Campaign anlegen</button></form><p>{len(campaigns)} Campaign(s)</p></div>
<div class='card'><h3>Execution Manifest</h3><form method='post' action='/build233/manifest-freeze'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='campaign_id' value='{esc(campaign_id)}' placeholder='Campaign-ID' required><textarea name='environment_json' placeholder='{{"os":"Windows","cpu":"...","profile":"phase8-fixed"}}' required></textarea><textarea name='protocol_notes' placeholder='Vergleichbare Umgebung, gleiche Fixtures und kontrollierte Ausführung.' required></textarea><button>Manifest einfrieren</button></form></div>
<div class='card'><h3>Blind Arm importieren</h3><form method='post' action='/build233/arm-submit'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='campaign_id' value='{esc(campaign_id)}' placeholder='Campaign-ID' required><input name='arm_code' placeholder='ARM-…' required><textarea name='results_json' placeholder='Vollständige Ergebnis-JSON' required></textarea><button>Arm reviewpflichtig speichern</button></form></div>
<div class='card'><h3>Arm prüfen</h3><form method='post' action='/build233/arm-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='trial_id' placeholder='Trial-ID' required><select name='decision'><option>accepted</option><option>rejected</option></select><textarea name='note' placeholder='Unabhängige Review-Notiz' required></textarea><button>Review speichern</button></form></div>
<div class='card'><h3>Zyklus auswerten</h3><form method='post' action='/build233/cycle-finalize'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='campaign_id' value='{esc(campaign_id)}' placeholder='Campaign-ID' required><button>Scorecards + Gates + Remediation erzeugen</button></form></div>
<div class='card'><h3>Qualifikationsreview</h3><form method='post' action='/build233/cycle-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='cycle_id' placeholder='Cycle-ID' required><select name='decision'><option>phase8_qualified</option><option>needs_remediation</option><option>rejected</option></select><textarea name='rationale' placeholder='Unabhängige Entscheidung' required></textarea><button>Entscheidung speichern</button></form></div>
</div>
<p><strong>Status:</strong> {len(data['cycles'])} Auswertungszyklus/Zyklen · {len(data['tickets'])} Remediation-Ticket(s). Zielbuild für Abweichungen: 234.0.</p>
</section>
"""

    def _create_remediation_tickets(self, *, cycle_id: str, campaign: Mapping[str, Any], comparison: Mapping[str, Any], candidate_scorecard: Mapping[str, Any], created_by: str) -> list[dict[str, Any]]:
        failed = [k for k, v in comparison["gates"].items() if not bool(v.get("pass"))]
        per_case = candidate_scorecard.get("per_case") or []
        out = []
        for metric in failed:
            severity, title, action = self.REMEDIATION.get(metric, ("medium", f"Qualification-Gate {metric} verfehlt", "Build 234: Ursache analysieren und Gate gezielt reparieren."))
            family = self.FAMILY_BY_METRIC.get(metric, "*")
            impacted = [x["qualification_case_id"] for x in per_case if (family == "*" or x.get("metric_family") == family) and float(x.get("score") or 0) < 1.0]
            finding = dict(comparison["gates"].get(metric) or {})
            ticket_id, now = new_id("remticket233"), now_ts()
            payload = {"ticket_id": ticket_id, "cycle_id": cycle_id, "campaign_id": campaign["campaign_id"], "case_id": campaign["case_id"], "metric_key": metric, "severity": severity, "title": title, "finding": finding, "impacted_cases": impacted, "recommended_action": action, "target_build": "234.0", "created_by": created_by, "created_at": now}
            self.db.execute("INSERT INTO remediation_tickets_233 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (ticket_id, cycle_id, campaign["campaign_id"], campaign["case_id"], metric, severity, title, dumps(finding), dumps(impacted), action, "234.0", created_by, now, _hash(payload)))
            # append initial status event
            aid = new_id("remaction233")
            action_payload = {"action_id": aid, "ticket_id": ticket_id, "case_id": campaign["case_id"], "status": "open", "note": "Automatisch aus verfehltem Qualification-Gate erzeugt.", "actor": created_by, "created_at": now}
            self.db.execute("INSERT INTO remediation_ticket_actions_233 VALUES(?,?,?,?,?,?,?,?)", (aid, ticket_id, campaign["case_id"], "open", action_payload["note"], created_by, now, _hash(action_payload)))
            out.append(payload)
        return out

    def _campaign_payload(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "fixture_kind": "synthetic_redacted", "real_world_claim_allowed": False}

    def _manifest_payload(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "environment": _loads(row["environment_json"], {})}

    def _campaign(self, campaign_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM qualification_campaigns_233 WHERE campaign_id=?", (campaign_id,))
        if not row:
            raise KeyError("qualification campaign not found")
        return dict(row)

    def _cycle(self, cycle_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM qualification_cycles_233 WHERE cycle_id=?", (cycle_id,))
        if not row:
            raise KeyError("qualification cycle not found")
        return dict(row)

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError("case not found")

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> None:
        previous_row = self.db.one("SELECT event_hash FROM build233_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = str(previous_row["event_hash"]) if previous_row else ""
        event_id, now = new_id("event233"), now_ts()
        body = {"event_id": event_id, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": dict(payload), "previous_hash": previous, "created_at": now}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build233_events VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, case_id, event_type, object_type, object_id, actor, dumps(dict(payload)), previous, event_hash, now))
