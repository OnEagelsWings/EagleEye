from __future__ import annotations

import hashlib
import html
import json
import statistics
from pathlib import Path
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts

REQUIRED_CATEGORIES = {
    "unique_identity",
    "name_collision",
    "username_change",
    "multilingual_identity",
    "contradictory_employment",
    "stale_social",
    "deliberate_false_candidate",
    "document_metadata",
    "person_org_link",
    "high_opsec",
}
REQUIRED_ENVIRONMENT_CHECKS = {
    "windows_clean_install",
    "windows_upgrade",
    "firefox_end_to_end",
    "ollama_local_model",
    "live_source_pack_1",
    "live_source_pack_2",
    "restart_recovery",
    "long_run_stability",
}


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _text(value: Any, limit: int = 200_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return 0.0


def _pr(expected: Sequence[str], observed: Sequence[str]) -> tuple[float, float]:
    exp, obs = set(expected), set(observed)
    precision = len(exp & obs) / len(obs) if obs else (1.0 if not exp else 0.0)
    recall = len(exp & obs) / len(exp) if exp else 1.0
    return precision, recall


def _binary_metrics(labels: Sequence[Mapping[str, Any]]) -> tuple[float, float, float, dict[str, int]]:
    counts = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for item in labels:
        key = str(item.get("label", "")).lower()
        if key in counts:
            counts[key] += 1
    precision = counts["tp"] / (counts["tp"] + counts["fp"]) if (counts["tp"] + counts["fp"]) else 1.0
    recall = counts["tp"] / (counts["tp"] + counts["fn"]) if (counts["tp"] + counts["fn"]) else 1.0
    fpr = counts["fp"] / (counts["fp"] + counts["tn"]) if (counts["fp"] + counts["tn"]) else 0.0
    return precision, recall, fpr, counts


class Build222Phase7QualificationBenchmarkService:
    """Qualification benchmark for Phase 7.

    It evaluates the integrated, human-governed investigation workflow. Development
    qualification can be completed with deterministic local fixtures. Operational
    qualification remains pending until Windows, Firefox, a real local model and live
    sources have explicit evidence-backed checks.
    """

    BUILD = "222.0"
    DEFAULT_PROFILE = {
        "minimum_scenarios": 10,
        "minimum_overall_score": 0.82,
        "minimum_citation_precision": 0.95,
        "minimum_citation_recall": 0.85,
        "maximum_hallucination_hits": 0,
        "minimum_route_precision": 0.80,
        "minimum_route_recall": 0.75,
        "minimum_adapter_precision": 0.80,
        "minimum_adapter_recall": 0.70,
        "maximum_false_positive_rate": 0.15,
        "minimum_translation_score": 0.80,
        "minimum_dialog_continuity": 0.85,
        "minimum_recovery_score": 1.0,
        "minimum_opsec_score": 1.0,
        "maximum_median_first_lead_seconds": 300,
        "minimum_three_cycle_scenarios": 1,
        "minimum_source_paths": 9,
    }

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        research_loop: Any,
        conversation: Any,
        planner: Any,
        source_pack1: Any,
        reliability: Any,
        source_pack2: Any,
        workspace: Any,
        base_dir: str | Path,
        actor: str = "local-analyst",
    ) -> None:
        self.db, self.audit = db, audit
        self.research_loop, self.conversation, self.planner = research_loop, conversation, planner
        self.source_pack1, self.reliability, self.source_pack2 = source_pack1, reliability, source_pack2
        self.workspace = workspace
        self.base_dir = Path(base_dir)
        self.actor = actor

    def create_suite(
        self,
        *,
        case_id: str,
        title: str,
        description: str,
        created_by: str,
        qualification_profile: Mapping[str, Any] | None,
        confirmation: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"PHASE7 SUITE 222 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        if len(_text(title, 300).strip()) < 4 or len(_text(description, 5000).strip()) < 10:
            raise ValueError("substantive title and description required")
        profile = dict(self.DEFAULT_PROFILE)
        for key, value in dict(qualification_profile or {}).items():
            if key in profile and isinstance(value, (int, float)):
                profile[key] = value
        suite_id, now = new_id("suite222"), now_ts()
        payload = {
            "suite_id": suite_id,
            "case_id": case_id,
            "title": _text(title, 300),
            "description": _text(description, 5000),
            "status": "draft",
            "target_scenario_count": int(profile["minimum_scenarios"]),
            "qualification_profile": profile,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }
        self.db.execute(
            "INSERT INTO phase7_qualification_suites_222 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (suite_id, case_id, payload["title"], payload["description"], "draft", payload["target_scenario_count"], dumps(profile), created_by, now, now, _hash(payload)),
        )
        self._event(case_id, "qualification_suite_created", "qualification_suite", suite_id, {"profile": profile}, created_by)
        return payload

    def add_scenario(
        self,
        *,
        suite_id: str,
        scenario_key: str,
        title: str,
        category: str,
        language: str,
        difficulty: str,
        objective: str,
        expected_refs: Sequence[str],
        forbidden_claims: Sequence[str],
        expected_behaviors: Sequence[str],
        expected_route_classes: Sequence[str],
        expected_source_classes: Sequence[str],
        minimum_cycles: int,
        maximum_first_lead_seconds: int,
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        suite = self._suite(suite_id)
        if confirmation != f"PHASE7 SCENARIO 222 {suite_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        if category not in REQUIRED_CATEGORIES:
            raise ValueError("unknown qualification category")
        if difficulty not in {"basic", "medium", "hard", "adversarial"}:
            raise ValueError("invalid difficulty")
        refs = [str(x) for x in expected_refs if str(x)]
        for ref in refs:
            if not self._valid_case_ref(suite["case_id"], ref):
                raise ValueError("expected_refs must belong to the suite case")
        scenario_id, now = new_id("scenario222"), now_ts()
        payload = {
            "scenario_id": scenario_id,
            "suite_id": suite_id,
            "case_id": suite["case_id"],
            "scenario_key": _text(scenario_key, 100),
            "title": _text(title, 300),
            "category": category,
            "language": _text(language, 20) or "de",
            "difficulty": difficulty,
            "objective": _text(objective, 20_000),
            "expected_refs": refs,
            "forbidden_claims": [_text(x, 1000) for x in forbidden_claims],
            "expected_behaviors": [_text(x, 500) for x in expected_behaviors],
            "expected_route_classes": [str(x) for x in expected_route_classes],
            "expected_source_classes": [str(x) for x in expected_source_classes],
            "minimum_cycles": max(1, min(int(minimum_cycles), 5)),
            "maximum_first_lead_seconds": max(1, min(int(maximum_first_lead_seconds), 86_400)),
            "status": "active",
            "created_by": created_by,
            "created_at": now,
        }
        self.db.execute(
            "INSERT INTO phase7_scenarios_222 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (scenario_id, suite_id, suite["case_id"], payload["scenario_key"], payload["title"], category, payload["language"], difficulty, payload["objective"], dumps(refs), dumps(payload["forbidden_claims"]), dumps(payload["expected_behaviors"]), dumps(payload["expected_route_classes"]), dumps(payload["expected_source_classes"]), payload["minimum_cycles"], payload["maximum_first_lead_seconds"], "active", created_by, now, _hash(payload)),
        )
        self.db.execute("UPDATE phase7_qualification_suites_222 SET status='running',updated_at=? WHERE suite_id=?", (now, suite_id))
        return payload

    def evaluate_loop(
        self,
        *,
        scenario_id: str,
        loop_id: str,
        observed_behaviors: Sequence[str],
        adapter_labels: Sequence[Mapping[str, Any]],
        translation_checks: Sequence[Mapping[str, Any]],
        contradiction_checks: Sequence[Mapping[str, Any]],
        dialog_continuity: float,
        recovery_checks: Sequence[Mapping[str, Any]],
        opsec_violations: Sequence[str],
        evaluator: str,
        confirmation: str,
    ) -> dict[str, Any]:
        scenario = self._scenario(scenario_id)
        loop = self.research_loop._loop(loop_id)
        if loop["case_id"] != scenario["case_id"]:
            raise ValueError("loop and scenario belong to different cases")
        if confirmation != f"PHASE7 SCENARIO 222 {scenario_id} AUSWERTEN":
            raise PermissionError("explicit approval required")

        role_runs = self.db.all("SELECT * FROM ai_role_runs_221 WHERE loop_id=? AND status='approved' ORDER BY cycle_no,created_at", (loop_id,))
        findings = self.db.all("SELECT * FROM ai_research_findings_221 WHERE loop_id=? ORDER BY created_at", (loop_id,))
        actions = self.db.all("SELECT * FROM ai_research_actions_221 WHERE loop_id=? ORDER BY created_at", (loop_id,))
        citations = sorted({ref for run in role_runs for ref in _loads(run.get("citations_json", "[]"), [])})
        expected_refs = _loads(scenario["expected_refs_json"], [])
        citation_precision, citation_recall = _pr(expected_refs, citations)
        valid_citations = [ref for ref in citations if self._valid_case_ref(scenario["case_id"], ref)]
        source_grounding = len(valid_citations) / len(citations) if citations else (1.0 if not expected_refs else 0.0)

        texts = "\n".join(str(x.get("text_value", "")) for x in findings).lower()
        forbidden = [str(x).lower() for x in _loads(scenario["forbidden_claims_json"], []) if str(x)]
        hallucination_hits = sum(1 for claim in forbidden if claim in texts)
        expected_behaviors = _loads(scenario["expected_behaviors_json"], [])
        _, behavior_score = _pr(expected_behaviors, observed_behaviors)
        expected_routes = _loads(scenario["expected_route_classes_json"], [])
        proposed_routes = [str(x.get("source_class", "")) for x in actions]
        route_precision, route_recall = _pr(expected_routes, proposed_routes)
        adapter_precision, adapter_recall, false_positive_rate, label_counts = _binary_metrics(adapter_labels)

        trans_scores = [_clamp(x.get("score", 1.0 if x.get("passed") else 0.0)) for x in translation_checks]
        translation_score = statistics.fmean(trans_scores) if trans_scores else (1.0 if scenario["category"] != "multilingual_identity" else 0.0)
        contra_scores = [_clamp(x.get("score", 1.0 if x.get("passed") else 0.0)) for x in contradiction_checks]
        contradiction_score = statistics.fmean(contra_scores) if contra_scores else (1.0 if scenario["category"] != "contradictory_employment" else 0.0)
        rec_scores = [_clamp(x.get("score", 1.0 if x.get("passed") else 0.0)) for x in recovery_checks]
        recovery_score = statistics.fmean(rec_scores) if rec_scores else 0.0
        opsec_score = 1.0 if not list(opsec_violations) else max(0.0, 1.0 - min(len(opsec_violations), 10) / 10.0)

        cycles_completed = max([int(x.get("cycle_no", 0)) for x in role_runs] or [0])
        first_lead_seconds = self._first_lead_seconds(loop, findings)
        weights = {
            "citation": 0.20,
            "grounding": 0.10,
            "behavior": 0.08,
            "routing": 0.10,
            "adapter": 0.12,
            "contradiction": 0.08,
            "translation": 0.07,
            "dialog": 0.08,
            "recovery": 0.07,
            "opsec": 0.10,
        }
        citation_score = (citation_precision + citation_recall) / 2
        routing_score = (route_precision + route_recall) / 2
        adapter_score = (adapter_precision + adapter_recall + (1.0 - false_positive_rate)) / 3
        overall = sum((
            weights["citation"] * citation_score,
            weights["grounding"] * source_grounding,
            weights["behavior"] * behavior_score,
            weights["routing"] * routing_score,
            weights["adapter"] * adapter_score,
            weights["contradiction"] * contradiction_score,
            weights["translation"] * translation_score,
            weights["dialog"] * _clamp(dialog_continuity),
            weights["recovery"] * recovery_score,
            weights["opsec"] * opsec_score,
        ))
        profile = _loads(self._suite(scenario["suite_id"])["qualification_profile_json"], self.DEFAULT_PROFILE)
        passed = all((
            citation_precision >= profile["minimum_citation_precision"],
            citation_recall >= profile["minimum_citation_recall"],
            source_grounding == 1.0,
            hallucination_hits <= profile["maximum_hallucination_hits"],
            route_precision >= profile["minimum_route_precision"],
            route_recall >= profile["minimum_route_recall"],
            adapter_precision >= profile["minimum_adapter_precision"],
            adapter_recall >= profile["minimum_adapter_recall"],
            false_positive_rate <= profile["maximum_false_positive_rate"],
            translation_score >= profile["minimum_translation_score"],
            _clamp(dialog_continuity) >= profile["minimum_dialog_continuity"],
            recovery_score >= profile["minimum_recovery_score"],
            opsec_score >= profile["minimum_opsec_score"],
            cycles_completed >= int(scenario["minimum_cycles"]),
            first_lead_seconds <= float(scenario["maximum_first_lead_seconds"]),
            overall >= profile["minimum_overall_score"],
        ))
        now = now_ts()
        run_id, result_id = new_id("qrun222"), new_id("qresult222")
        model_name = str(loop.get("model_name", ""))
        metrics = {
            "citation_precision": citation_precision,
            "citation_recall": citation_recall,
            "source_grounding": source_grounding,
            "hallucination_hits": hallucination_hits,
            "behavior_score": behavior_score,
            "route_precision": route_precision,
            "route_recall": route_recall,
            "adapter_precision": adapter_precision,
            "adapter_recall": adapter_recall,
            "false_positive_rate": false_positive_rate,
            "adapter_label_counts": label_counts,
            "contradiction_score": contradiction_score,
            "translation_score": translation_score,
            "dialog_continuity": _clamp(dialog_continuity),
            "recovery_score": recovery_score,
            "opsec_score": opsec_score,
            "overall_score": overall,
            "cycles_completed": cycles_completed,
            "first_lead_seconds": first_lead_seconds,
            "citations": citations,
            "expected_refs": expected_refs,
            "proposed_routes": proposed_routes,
            "expected_routes": expected_routes,
            "opsec_violations": list(opsec_violations),
        }
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO phase7_scenario_runs_222 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, scenario_id, scenario["suite_id"], scenario["case_id"], loop_id, model_name, cycles_completed, first_lead_seconds, "passed" if passed else "failed", loop["created_at"], now, evaluator, _hash({"run_id": run_id, **metrics})),
            )
            self.db.execute(
                "INSERT INTO phase7_scenario_metrics_222 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (result_id, run_id, scenario_id, scenario["suite_id"], scenario["case_id"], citation_precision, citation_recall, source_grounding, hallucination_hits, behavior_score, route_precision, route_recall, adapter_precision, adapter_recall, false_positive_rate, contradiction_score, translation_score, _clamp(dialog_continuity), recovery_score, opsec_score, overall, int(passed), dumps(metrics), now, _hash({"result_id": result_id, **metrics})),
            )
            self.db.execute("UPDATE phase7_scenarios_222 SET status='completed' WHERE scenario_id=?", (scenario_id,))
        self._event(scenario["case_id"], "qualification_scenario_evaluated", "qualification_scenario", scenario_id, {"passed": passed, "overall_score": overall}, evaluator)
        return {"run_id": run_id, "result_id": result_id, "passed": passed, **metrics}

    def record_environment_check(
        self,
        *,
        suite_id: str,
        check_key: str,
        environment: str,
        status: str,
        details: Mapping[str, Any],
        evidence_ref: str,
        checked_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        suite = self._suite(suite_id)
        if confirmation != f"PHASE7 ENV CHECK 222 {suite_id} {check_key} SPEICHERN":
            raise PermissionError("explicit approval required")
        if check_key not in REQUIRED_ENVIRONMENT_CHECKS:
            raise ValueError("unknown environment qualification check")
        if status not in {"passed", "failed", "pending", "conditional", "not_applicable"}:
            raise ValueError("invalid check status")
        if status == "passed" and not evidence_ref:
            raise ValueError("passed operational checks require an evidence reference")
        if evidence_ref and not self._valid_case_ref(suite["case_id"], evidence_ref):
            raise ValueError("environment evidence must belong to suite case")
        check_id, now = new_id("env222"), now_ts()
        payload = {"check_id": check_id, "suite_id": suite_id, "case_id": suite["case_id"], "check_key": check_key, "environment": _text(environment, 100), "status": status, "details": dict(details), "evidence_ref": evidence_ref, "checked_by": checked_by, "checked_at": now}
        self.db.execute("INSERT INTO phase7_environment_checks_222 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (check_id, suite_id, suite["case_id"], check_key, payload["environment"], status, dumps(details), evidence_ref, checked_by, now, _hash(payload)))
        return payload

    def finalize_suite(self, *, suite_id: str, generated_by: str, confirmation: str) -> dict[str, Any]:
        suite = self._suite(suite_id)
        if confirmation != f"PHASE7 QUALIFICATION 222 {suite_id} ABSCHLIESSEN":
            raise PermissionError("explicit approval required")
        scenarios = self.db.all("SELECT * FROM phase7_scenarios_222 WHERE suite_id=? AND status!='disabled' ORDER BY scenario_key", (suite_id,))
        results = self.db.all("SELECT m.*,r.cycles_completed,r.first_lead_seconds FROM phase7_scenario_metrics_222 m JOIN phase7_scenario_runs_222 r ON r.run_id=m.run_id WHERE m.suite_id=? ORDER BY m.evaluated_at", (suite_id,))
        latest_by_scenario: dict[str, dict[str, Any]] = {}
        for row in results:
            latest_by_scenario[row["scenario_id"]] = row
        final_results = list(latest_by_scenario.values())
        profile = _loads(suite["qualification_profile_json"], self.DEFAULT_PROFILE)
        categories = {x["category"] for x in scenarios}
        source_paths = self._source_path_count()
        averages = self._aggregate(final_results)
        first_leads = [float(x["first_lead_seconds"]) for x in final_results]
        median_first_lead = statistics.median(first_leads) if first_leads else 10**9
        three_cycles = sum(1 for x in final_results if int(x["cycles_completed"]) >= 3)
        development_gates = {
            "scenario_count": len(scenarios) >= int(profile["minimum_scenarios"]),
            "all_required_categories": REQUIRED_CATEGORIES.issubset(categories),
            "all_scenarios_evaluated": len(final_results) >= len(scenarios) and bool(scenarios),
            "scenario_pass_rate": bool(final_results) and sum(int(x["passed"]) for x in final_results) / len(final_results) >= 0.9,
            "aggregate_score": averages["overall_score"] >= profile["minimum_overall_score"],
            "citation_precision": averages["citation_precision"] >= profile["minimum_citation_precision"],
            "citation_recall": averages["citation_recall"] >= profile["minimum_citation_recall"],
            "zero_hallucination_hits": sum(int(x["hallucination_hits"]) for x in final_results) <= profile["maximum_hallucination_hits"],
            "adapter_false_positive_rate": averages["false_positive_rate"] <= profile["maximum_false_positive_rate"],
            "recovery": averages["recovery_score"] >= profile["minimum_recovery_score"],
            "opsec": averages["opsec_score"] >= profile["minimum_opsec_score"],
            "first_relevant_lead": median_first_lead <= profile["maximum_median_first_lead_seconds"],
            "three_cycle_scenario": three_cycles >= int(profile["minimum_three_cycle_scenarios"]),
            "source_path_count": source_paths >= int(profile["minimum_source_paths"]),
        }
        development_status = "passed" if all(development_gates.values()) else "failed"

        latest_checks: dict[str, dict[str, Any]] = {}
        for row in self.db.all("SELECT * FROM phase7_environment_checks_222 WHERE suite_id=? ORDER BY checked_at", (suite_id,)):
            latest_checks[row["check_key"]] = row
        operational_gates = {key: latest_checks.get(key, {}).get("status") == "passed" for key in sorted(REQUIRED_ENVIRONMENT_CHECKS)}
        if all(operational_gates.values()):
            operational_status = "passed"
        elif any(latest_checks.get(k, {}).get("status") == "failed" for k in REQUIRED_ENVIRONMENT_CHECKS):
            operational_status = "failed"
        elif latest_checks:
            operational_status = "conditional"
        else:
            operational_status = "pending"

        status = "operational_qualified" if development_status == "passed" and operational_status == "passed" else ("conditional" if development_status == "passed" else "failed")
        report_id, now = new_id("report222"), now_ts()
        metrics = {**averages, "scenario_count": len(scenarios), "evaluated_scenarios": len(final_results), "median_first_lead_seconds": median_first_lead, "three_cycle_scenarios": three_cycles, "source_path_count": source_paths, "categories": sorted(categories)}
        gates = {"development": development_gates, "operational": operational_gates}
        report_path = self._write_report(report_id, suite, development_status, operational_status, metrics, gates)
        payload = {"report_id": report_id, "suite_id": suite_id, "case_id": suite["case_id"], "development_status": development_status, "operational_status": operational_status, "aggregate_score": averages["overall_score"], "gates": gates, "metrics": metrics, "report_path": str(report_path), "generated_by": generated_by, "generated_at": now}
        self.db.execute("INSERT INTO phase7_qualification_reports_222 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (report_id, suite_id, suite["case_id"], development_status, operational_status, averages["overall_score"], dumps(gates), dumps(metrics), str(report_path), generated_by, now, _hash(payload)))
        self.db.execute("UPDATE phase7_qualification_suites_222 SET status=?,updated_at=? WHERE suite_id=?", (status, now, suite_id))
        self._event(suite["case_id"], "phase7_qualification_finalized", "qualification_suite", suite_id, {"development_status": development_status, "operational_status": operational_status, "report_id": report_id}, generated_by)
        return payload

    def dashboard(self, case_id: str) -> dict[str, Any]:
        return {
            "suites": self.db.all("SELECT * FROM phase7_qualification_suites_222 WHERE case_id=? ORDER BY created_at DESC", (case_id,)),
            "scenarios": self.db.all("SELECT * FROM phase7_scenarios_222 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "results": self.db.all("SELECT * FROM phase7_scenario_metrics_222 WHERE case_id=? ORDER BY evaluated_at DESC LIMIT 50", (case_id,)),
            "environment": self.db.all("SELECT * FROM phase7_environment_checks_222 WHERE case_id=? ORDER BY checked_at DESC LIMIT 50", (case_id,)),
            "reports": self.db.all("SELECT * FROM phase7_qualification_reports_222 WHERE case_id=? ORDER BY generated_at DESC LIMIT 20", (case_id,)),
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        d = self.dashboard(case_id)
        esc = html.escape
        suites = "".join(f"<tr><td>{esc(x['suite_id'])}</td><td>{esc(x['title'])}</td><td>{esc(x['status'])}</td></tr>" for x in d["suites"]) or "<tr><td colspan='3'>Keine Qualifikationssuite.</td></tr>"
        results = "".join(f"<tr><td>{esc(x['scenario_id'])}</td><td>{float(x['overall_score']):.3f}</td><td>{'bestanden' if x['passed'] else 'nicht bestanden'}</td></tr>" for x in d["results"][:10]) or "<tr><td colspan='3'>Keine Szenarioergebnisse.</td></tr>"
        reports = "".join(f"<tr><td>{esc(x['report_id'])}</td><td>{esc(x['development_status'])}</td><td>{esc(x['operational_status'])}</td><td>{float(x['aggregate_score']):.3f}</td></tr>" for x in d["reports"][:10]) or "<tr><td colspan='4'>Kein Abschlussbericht.</td></tr>"
        return f"""
<section class='card' id='build222_qualification'><h2>Phase-7 PersonOSINT Qualification · Build 222</h2>
<p>Misst den vollständigen AI-, Quellen-, Evidence-, OPSEC- und Recovery-Workflow. Entwicklungsqualifikation und reale Windows-/Firefox-/Live-Qualifikation werden getrennt ausgewiesen.</p>
<form method='post' action='/build222/suite-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='title' placeholder='Titel der Qualifikationssuite' required><textarea name='description' rows='2' placeholder='Zweck und Umfang' required></textarea><button>Qualifikationssuite anlegen</button></form>
<table><thead><tr><th>Suite</th><th>Titel</th><th>Status</th></tr></thead><tbody>{suites}</tbody></table>
<hr><form method='post' action='/build222/scenario-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='suite_id' placeholder='Suite-ID' required><input name='scenario_key' placeholder='Szenario-Key' required><select name='category'>{''.join(f"<option>{esc(x)}</option>" for x in sorted(REQUIRED_CATEGORIES))}</select><input name='title' placeholder='Szenariotitel' required><textarea name='objective' rows='2' placeholder='Ermittlungsziel' required></textarea><textarea name='expected_refs_json' rows='2' placeholder='[&quot;stmt_...&quot;]'></textarea><textarea name='expected_routes_json' rows='2' placeholder='[&quot;social_username&quot;]'></textarea><button>Szenario anlegen</button></form>
<hr><form method='post' action='/build222/scenario-evaluate'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='scenario_id' placeholder='Szenario-ID' required><input name='loop_id' placeholder='Research-Loop-ID' required><textarea name='observed_behaviors_json' rows='2' placeholder='[&quot;source_grounded&quot;]'></textarea><textarea name='adapter_labels_json' rows='2' placeholder='[{{&quot;label&quot;:&quot;tp&quot;}}]'></textarea><textarea name='translation_checks_json' rows='2' placeholder='[{{&quot;passed&quot;:true}}]'></textarea><textarea name='contradiction_checks_json' rows='2' placeholder='[{{&quot;passed&quot;:true}}]'></textarea><input name='dialog_continuity' value='1.0'><textarea name='recovery_checks_json' rows='2' placeholder='[{{&quot;passed&quot;:true}}]'></textarea><textarea name='opsec_violations_json' rows='2' placeholder='[]'></textarea><button>Szenario auswerten</button></form>
<table><thead><tr><th>Szenario</th><th>Score</th><th>Status</th></tr></thead><tbody>{results}</tbody></table>
<hr><form method='post' action='/build222/environment-check'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='suite_id' placeholder='Suite-ID' required><select name='check_key'>{''.join(f"<option>{esc(x)}</option>" for x in sorted(REQUIRED_ENVIRONMENT_CHECKS))}</select><input name='environment' placeholder='Windows/Firefox/Ollama'><select name='status'><option>pending</option><option>conditional</option><option>passed</option><option>failed</option></select><input name='evidence_ref' placeholder='Evidence-ID bei passed'><textarea name='details_json' rows='2' placeholder='{{}}'></textarea><button>Umgebungsprüfung speichern</button></form>
<hr><form method='post' action='/build222/suite-finalize'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='suite_id' placeholder='Suite-ID' required><button>Phase-7-Qualifikation abschließen</button></form>
<table><thead><tr><th>Report</th><th>Entwicklung</th><th>Operativ</th><th>Score</th></tr></thead><tbody>{reports}</tbody></table></section>
"""

    def _aggregate(self, rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
        keys = ["citation_precision", "citation_recall", "source_grounding", "behavior_score", "route_precision", "route_recall", "adapter_precision", "adapter_recall", "false_positive_rate", "contradiction_score", "translation_score", "dialog_continuity", "recovery_score", "opsec_score", "overall_score"]
        return {key: (statistics.fmean(float(x[key]) for x in rows) if rows else 0.0) for key in keys}

    def _source_path_count(self) -> int:
        pack1 = self.db.one("SELECT COUNT(*) AS n FROM digital_source_adapters_218") or {"n": 0}
        pack2 = self.db.one("SELECT COUNT(*) AS n FROM source_adapters_220") or {"n": 0}
        return int(pack1["n"]) + int(pack2["n"])

    def _first_lead_seconds(self, loop: Mapping[str, Any], findings: Sequence[Mapping[str, Any]]) -> float:
        if not findings:
            return 10**9
        from datetime import datetime
        try:
            start = datetime.fromisoformat(str(loop["created_at"]).replace("Z", "+00:00"))
            first = datetime.fromisoformat(str(findings[0]["created_at"]).replace("Z", "+00:00"))
            return max(0.0, (first - start).total_seconds())
        except Exception:
            return 10**9

    def _write_report(self, report_id: str, suite: Mapping[str, Any], development_status: str, operational_status: str, metrics: Mapping[str, Any], gates: Mapping[str, Any]) -> Path:
        directory = self.base_dir / "reports" / "phase7_qualification"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{report_id}.md"
        lines = [
            f"# Phase-7-Qualifikationsbericht – {suite['title']}",
            "",
            f"- Suite: `{suite['suite_id']}`",
            f"- Entwicklungsstatus: **{development_status}**",
            f"- Operativer Status: **{operational_status}**",
            f"- Aggregate Score: **{float(metrics['overall_score']):.3f}**",
            "",
            "## Entwicklungs-Gates",
        ]
        lines.extend(f"- {'PASS' if ok else 'FAIL'} – {key}" for key, ok in gates["development"].items())
        lines.extend(["", "## Operative Gates"])
        lines.extend(f"- {'PASS' if ok else 'PENDING'} – {key}" for key, ok in gates["operational"].items())
        lines.extend(["", "## Metriken", "", "```json", json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True), "```", ""])
        target.write_text("\n".join(lines), encoding="utf-8")
        return target

    def _valid_case_ref(self, case_id: str, ref: str) -> bool:
        queries = (
            ("SELECT statement_id AS ref FROM evidence_statements_211 WHERE case_id=? AND statement_id=?", (case_id, ref)),
            ("SELECT source_id AS ref FROM evidence_sources_211 WHERE case_id=? AND source_id=?", (case_id, ref)),
            ("SELECT result_id AS ref FROM digital_source_results_218 WHERE case_id=? AND result_id=?", (case_id, ref)),
            ("SELECT result_id AS ref FROM source_results_220 WHERE case_id=? AND result_id=?", (case_id, ref)),
            ("SELECT finding_id AS ref FROM ai_research_findings_221 WHERE case_id=? AND finding_id=?", (case_id, ref)),
        )
        for sql, params in queries:
            try:
                if self.db.one(sql, params):
                    return True
            except Exception:
                continue
        return False

    def _suite(self, suite_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase7_qualification_suites_222 WHERE suite_id=?", (suite_id,))
        if not row:
            raise KeyError(suite_id)
        return row

    def _scenario(self, scenario_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase7_scenarios_222 WHERE scenario_id=?", (scenario_id,))
        if not row:
            raise KeyError(scenario_id)
        return row

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> str:
        previous = self.db.one("SELECT event_hash FROM build222_events WHERE case_id=? ORDER BY created_at DESC,event_id DESC LIMIT 1", (case_id,))
        previous_hash = previous["event_hash"] if previous else ""
        event_id, now = new_id("evt222"), now_ts()
        event_hash = _hash({"event_id": event_id, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": dict(payload), "previous_hash": previous_hash, "created_at": now})
        self.db.execute("INSERT INTO build222_events VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, case_id, event_type, object_type, object_id, actor, dumps(payload), previous_hash, event_hash, now))
        try:
            self.audit.log(event_type, object_type, object_id, case_id, dict(payload))
        except Exception:
            pass
        return event_id
