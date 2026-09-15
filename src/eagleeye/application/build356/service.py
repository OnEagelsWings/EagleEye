from __future__ import annotations

import ast
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from eagleeye.investigation.supervisor356 import DOSSIER_VERSION, POLICY_VERSION, InvestigationSupervisor356

DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class Build356CrossModalInvestigationService:
    BUILD = "356.0"

    def __init__(self, db: Any, audit: Any, *, build355: Any, supervisor: InvestigationSupervisor356, install_dir: str | Path, base_dir: str | Path, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build355 = build355
        self.supervisor = supervisor
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._root = self.install_dir

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build355, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/infrastructure/schema_v1/schema.py",
            "src/eagleeye/investigation/supervisor356.py",
            "src/eagleeye/application/build356/service.py",
            "src/eagleeye/interfaces/web/app356.py",
            "src/eagleeye/crawler/engine.py",
            "src/eagleeye/crawler/frontier.py",
            "src/eagleeye/crawler/media.py",
            "src/eagleeye/crawler/visual_context.py",
            "src/eagleeye/image_intelligence/agent.py",
            "src/eagleeye/image_intelligence/similarity.py",
            "src/eagleeye/image_intelligence/geolocation.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "EAGLEEYE_PRO_356_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_356_0.py",
            "tests/test_build356.py",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            p = self._root / rel
            h.update(rel.encode("utf-8")); h.update(b"\0")
            h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        value = _read_json(self._root / "BUILD_356_TEST_EVIDENCE.json")
        if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint():
            return value
        return {}

    def _probe(self, key: str) -> bool:
        return self._test_evidence().get("probes", {}).get(key) == "pass"

    def _benchmark(self) -> dict[str, Any]:
        value = _read_json(self._root / "BENCHMARK_BUILD_356_AI_FUSION.json")
        if value.get("build") == self.BUILD and value.get("code_fingerprint") == self.code_fingerprint() and int(value.get("cases", 0)) >= 700 and int(value.get("violations", -1)) == 0 and value.get("result") == "pass":
            return value
        return {}

    def training_basis(self) -> dict[str, Any]:
        value = _read_json(self._root / "TRAINING_BASIS_BUILD_356_AI_INVESTIGATION.json")
        if value.get("build") != self.BUILD:
            return {"build": self.BUILD, "status": "not_generated", "human_reviewed_training_examples": 0}
        return value

    def schema_metrics(self) -> dict[str, Any]:
        return self.build355.schema_metrics()

    def version_status(self) -> dict[str, Any]:
        vt = (self._root / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        pt = (self._root / "pyproject.toml").read_text(encoding="utf-8")
        rb = re.search(r'^BUILD\s*=\s*["\']([^"\']+)', vt, re.M)
        rs = re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', vt, re.M)
        rp = re.search(r'^version\s*=\s*["\']([^"\']+)', pt, re.M)
        runtime = rb.group(1) if rb else "unknown"
        schema = rs.group(1) if rs else "unknown"
        package = rp.group(1) if rp else "unknown"
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == "356.0.0"}

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c, ast.Constant) and c.value is True and hasattr(c, "lineno")})
        return []

    # Investigation-supervisor vertical slice.
    def create_investigation_intake(self, **kwargs: Any) -> dict[str, Any]: return self.supervisor.create_intake(**kwargs)
    def latest_investigation_intake(self, case_id: str) -> dict[str, Any] | None: return self.supervisor.latest_intake(case_id)
    def start_investigation_go(self, **kwargs: Any) -> dict[str, Any]: return self.supervisor.start_go(**kwargs)
    def active_investigation_go(self, case_id: str) -> dict[str, Any] | None: return self.supervisor.active_go(case_id)
    def monitor_investigation_crawler(self, case_id: str) -> dict[str, Any]: return self.supervisor.crawler_monitor(case_id)
    def investigation_snapshot(self, case_id: str) -> dict[str, Any]: return self.supervisor.collect_case_snapshot(case_id)
    def form_initial_hypotheses(self, **kwargs: Any) -> list[dict[str, Any]]: return self.supervisor.form_initial_hypotheses(**kwargs)
    def build_investigation_dossier(self, **kwargs: Any) -> dict[str, Any]: return self.supervisor.build_dossier(**kwargs)
    def latest_investigation_dossier(self, case_id: str) -> dict[str, Any] | None: return self.supervisor.latest_dossier(case_id)
    def investigation_supervisor_tick(self, **kwargs: Any) -> dict[str, Any]: return self.supervisor.supervisor_tick(**kwargs)

    def ai_investigation_status(self) -> dict[str, Any]:
        reports = self.db.one("SELECT COUNT(*) c FROM professional_reports WHERE report_type='phase15_ai_dossier_v356'")
        hyps = self.db.one("SELECT COUNT(*) c FROM ai_hypothesis_suggestions WHERE suggestion_id LIKE 'aih356_%'")
        intakes = self.db.one("SELECT COUNT(*) c FROM phase15_agent_tasks WHERE agent_role='investigation_supervisor' AND action_class='local_analysis' AND task_json LIKE '%case_intake_v356%'")
        go = self.db.one("SELECT COUNT(*) c FROM phase15_agent_tasks WHERE agent_role='investigation_supervisor' AND action_class='external_research' AND approval_state='approved' AND task_json LIKE '%research_wave_go_v356%'")
        return {
            **self.supervisor.status(),
            "dossier_version": DOSSIER_VERSION,
            "intake_count": int(intakes["c"] if intakes else 0),
            "go_wave_count": int(go["c"] if go else 0),
            "dossier_count": int(reports["c"] if reports else 0),
            "ai_hypothesis_count": int(hyps["c"] if hyps else 0),
            "training_basis": self.training_basis(),
        }

    def crawler_status(self) -> dict[str, Any]:
        state = dict(self.build355.crawler_status())
        state.update({
            "crawler_improvement_build": 356,
            "build356_cross_modal_provenance": True,
            "cross_modal_fusion_provenance_v356": True,
            "supervisor_reads_crawl_and_job_state": True,
            "supervisor_network_execution": False,
            "go_gated_delegation": True,
            "dossier_trace_chain": "crawl_run->fetch->object_hash->parse/media/link->hypothesis/dossier",
        })
        return state

    def architecture_status(self) -> dict[str, Any]:
        return {
            "investigation_policy": POLICY_VERSION,
            "dossier_version": DOSSIER_VERSION,
            "case_wide_read_fusion": True,
            "intake_supported": True,
            "explicit_go_required": True,
            "approved_source_jobs_auto_enqueued_after_go": True,
            "new_source_auto_approval": False,
            "supervisor_direct_network": False,
            "supervisor_direct_shell": False,
            "crawler_monitored_and_evaluated": True,
            "cross_modal_media_document_entity_graph_timeline_fusion": True,
            "first_hypotheses_candidate_only": True,
            "identity_auto_confirmation": False,
            "scene_location_auto_confirmation": False,
            "hypothesis_auto_fact_promotion": False,
            "written_dossier": True,
            "speech_output": "local_browser_speech_synthesis",
            "voice_input": False,
            "built_in_live_tor_transport": False,
        }

    @staticmethod
    def _maturity(states: dict[str, bool]) -> str:
        last = "declared"
        for key in DIMENSIONS:
            if states[key]: last = key
            else: break
        return last

    def capabilities(self) -> list[dict[str, Any]]:
        m = self.schema_metrics(); v = self.version_status(); bench = bool(self._benchmark()); fp = self.code_fingerprint()
        specs = [
            ("schema_baseline_v1_356", "Schema baseline retained", "schema", m["within_gate"], m["within_gate"], "schema", False, False),
            ("ai_investigation_intake_v356", "AI Investigation structured intake", "ai", True, True, "intake", bench, False),
            ("ai_investigation_go_v356", "Explicit-GO governed research-wave delegation", "ai", True, True, "go", bench, False),
            ("ai_casewide_fusion_v356", "Case-wide evidence/media/entity/graph/timeline fusion", "ai", True, True, "fusion", bench, False),
            ("ai_crawler_supervision_v356", "Crawler/job/OPSEC/parser monitoring and evaluation", "ai", True, True, "crawler_monitor", bench, False),
            ("ai_hypothesis_candidates_v356", "Evidence-linked initial hypotheses", "ai", True, True, "hypotheses", bench, False),
            ("ai_dossier_v356", "Evidence-first dossier draft with provenance annex", "dossier", True, True, "dossier", bench, False),
            ("ai_speech_output_v356", "Local browser speech output for dossier briefing", "voice", True, True, "speech", bench, False),
            ("crawler_cross_modal_provenance_v356", "Crawler-to-dossier trace chain", "crawler", True, True, "crawler", bench, False),
            ("voice_input_v358", "Push-to-talk voice command input", "voice", False, False, "future", False, False),
            ("tor_live_transport_v1", "Built-in live Tor gateway transport", "network", False, False, "future", False, True),
            ("canonical_versioning_356", "Canonical Build 356 version contract", "packaging", v["coherent"], v["coherent"], "version", False, False),
        ]
        required = {"schema_baseline_v1_356","ai_investigation_intake_v356","ai_investigation_go_v356","ai_casewide_fusion_v356","ai_crawler_supervision_v356","ai_hypothesis_candidates_v356","ai_dossier_v356","ai_speech_output_v356","crawler_cross_modal_provenance_v356","canonical_versioning_356"}
        rows = []
        for key, name, category, implemented, integrated, probe, benchmarkable, requires_external in specs:
            tested = bool(integrated and self._probe(probe))
            states = {"implemented": bool(implemented), "integrated": bool(implemented and integrated), "tested": tested, "benchmarked": bool(tested and benchmarkable), "externally_validated": False}
            rows.append({"capability_key": key, "display_name": name, "category": category, **states, "maturity": self._maturity(states), "required_for_build": key in required, "required_for_production": key not in {"schema_baseline_v1_356", "voice_input_v358"}, "external_validation_required": requires_external, "code_fingerprint": fp})
        return rows

    def qualified_gate(self) -> dict[str, Any]:
        rows = self.capabilities(); req = [r for r in rows if r["required_for_build"]]
        tested = bool(req) and all(r["tested"] for r in req)
        bench = all(r["benchmarked"] for r in req if r["capability_key"] not in {"schema_baseline_v1_356", "canonical_versioning_356"})
        production = bool(rows) and all(r["externally_validated"] for r in rows if r["required_for_production"])
        return {
            "build": self.BUILD,
            "phase": "15",
            "gate_authority": "build356_cross_modal_investigation_evidence_gate",
            "build_acceptance_ready": tested and bench and self.schema_metrics()["within_gate"],
            "production_release_ready": production,
            "release_ready": production,
            "baseline_tested": tested,
            "ai_fusion_benchmarked": bench,
            "active_gate_literal_true_lines": self.active_gate_literal_true_lines(),
            "rule": "External research begins only after explicit GO and only for already-reviewed governed sources. The AI supervisor may fuse, monitor, draft and hypothesize, but may not auto-approve sources, auto-confirm identity/location, export, merge, delete or release findings.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {"build": self.BUILD, "phase": "15", "name": "Cross-Modal Investigation Supervisor & Dossier Fusion", "schema": self.schema_metrics(), "ai_investigation": self.ai_investigation_status(), "crawler": self.crawler_status(), "architecture": self.architecture_status(), "gate": self.qualified_gate(), "version": self.version_status(), "capabilities": self.capabilities(), "crawler_improvement_commitment": "349-360"}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        intake = self.latest_investigation_intake(case_id)
        go = self.active_investigation_go(case_id)
        monitor = self.monitor_investigation_crawler(case_id)
        latest_report = self.db.one("SELECT report_id,executive_summary,created_at FROM professional_reports WHERE case_id=? AND report_type='phase15_ai_dossier_v356' ORDER BY created_at DESC LIMIT 1", (case_id,))
        objective = html.escape(str((intake or {}).get("input_payload", {}).get("objective", "")))
        go_state = "AKTIV" if go else "NOCH NICHT ERTEILT"
        report = f"<p><b>Letztes Dossier:</b> {html.escape(str(latest_report['report_id']))} · {html.escape(str(latest_report['created_at']))}</p>" if latest_report else "<p>Noch kein Build-356-Dossier.</p>"
        return (
            "<section class='card'><h2>Phase 15 · Build 356 · AI-Ermittlung</h2>"
            f"<p><b>Go:</b> {go_state} · <b>Crawl-Runs:</b> {monitor['crawl_runs']} · <b>Stored pages:</b> {monitor['pages_stored']} · <b>Security blocks:</b> {monitor['security_blocks']}.</p>"
            "<p>Fallführender evidence-first Supervisor: Intake → GO → freigegebene Research-Waves → Crawler-Monitoring → Cross-Modal Fusion → Hypothesen → Dossier. Kein automatischer Identity-/Geo-Fakt und keine externe Aktion vor GO.</p>"
            f"<form method='post' action='/cases/{html.escape(case_id)}/ai/intake'><input type='hidden' name='csrf' value='{html.escape(csrf)}'><label>Ermittlungsziel</label><textarea name='objective' required>{objective}</textarea><label>Leitfragen (eine pro Zeile)</label><textarea name='key_questions'></textarea><label>Scope/Notizen</label><textarea name='scope_notes'></textarea><button>Intake speichern</button></form>"
            f"<form method='post' action='/cases/{html.escape(case_id)}/ai/go'><input type='hidden' name='csrf' value='{html.escape(csrf)}'><label>Freigabe</label><input name='go' placeholder='GO' required><button>GO – Research-Wave starten</button></form>"
            f"<form method='post' action='/cases/{html.escape(case_id)}/ai/tick'><input type='hidden' name='csrf' value='{html.escape(csrf)}'><button>AI-Ermittlung auswerten & Dossier aktualisieren</button></form>"
            f"{report}<p><a href='/api/cases/{html.escape(case_id)}/ai/dossier'>Dossier JSON</a> · <a href='/cases/{html.escape(case_id)}/ai/briefing'>Briefing / Vorlesen</a></p></section>"
        )
