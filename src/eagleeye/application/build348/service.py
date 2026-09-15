from __future__ import annotations

import ast
import hashlib
import html
import json
import re
import uuid
from pathlib import Path
from typing import Any

from eagleeye.jobs.engine import POLICY_VERSION as JOB_POLICY
from eagleeye.search_platform.backends import POLICY_VERSION as SEARCH_POLICY, PostgresSearchBackend

DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class Build348SearchJobInfrastructureService:
    BUILD = "348.0"

    def __init__(self, db: Any, audit: Any, *, build347: Any, search: Any, jobs: Any, install_dir: str | Path, base_dir: str | Path, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build347 = build347
        self.search = search
        self.jobs = jobs
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._root = self.install_dir

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/infrastructure/schema_v1/schema.py",
            "src/eagleeye/search_platform/backends.py",
            "src/eagleeye/jobs/engine.py",
            "src/eagleeye/application/build348/service.py",
            "src/eagleeye/interfaces/web/app348.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "EAGLEEYE_PRO_348_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_348_0.py",
            "tests/test_build348.py",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            path = self._root / rel
            h.update(rel.encode()); h.update(b"\0"); h.update(path.read_bytes() if path.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        data = _read_json(self._root / "BUILD_348_TEST_EVIDENCE.json")
        if data.get("build") == self.BUILD and data.get("result") == "pass" and data.get("code_fingerprint") == self.code_fingerprint() and isinstance(data.get("probes"), dict):
            return data
        return {}

    def _probe(self, key: str) -> bool:
        return self._test_evidence().get("probes", {}).get(key) == "pass"

    def _benchmark(self) -> dict[str, Any]:
        data = _read_json(self._root / "BENCHMARK_BUILD_348_SEARCH_JOBS.json")
        if data.get("build") != self.BUILD or data.get("code_fingerprint") != self.code_fingerprint():
            return {}
        if data.get("cases", 0) < 300 or data.get("violations") != 0 or data.get("result") != "pass":
            return {}
        return data

    def schema_metrics(self) -> dict[str, Any]:
        return self.build347.schema_metrics()

    def version_status(self) -> dict[str, Any]:
        version_text = (self._root / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        project_text = (self._root / "pyproject.toml").read_text(encoding="utf-8")
        rb = re.search(r'^BUILD\s*=\s*["\']([^"\']+)', version_text, re.M)
        rs = re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', version_text, re.M)
        rp = re.search(r'^version\s*=\s*["\']([^"\']+)', project_text, re.M)
        runtime, schema, package = (rb.group(1) if rb else "unknown"), (rs.group(1) if rs else "unknown"), (rp.group(1) if rp else "unknown")
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == "348.0.0"}

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c, ast.Constant) and c.value is True and hasattr(c, "lineno")})
        return []

    # Retained security/data services are delegated by composition, never inherited.
    def register_darknet_source(self, **kwargs: Any) -> dict[str, Any]: return self.build347.register_darknet_source(**kwargs)
    def review_darknet_source(self, source_id: str, **kwargs: Any) -> dict[str, Any]: return self.build347.review_darknet_source(source_id, **kwargs)
    def create_clearnet_capsule(self, **kwargs: Any) -> dict[str, Any]: return self.build347.create_clearnet_capsule(**kwargs)
    def create_darknet_research(self, **kwargs: Any) -> dict[str, Any]: return self.build347.create_darknet_research(**kwargs)
    def preflight_request(self, search_run_id: str, **kwargs: Any) -> dict[str, Any]: return self.build347.preflight_request(search_run_id, **kwargs)
    def close_capsule(self, search_run_id: str, **kwargs: Any) -> dict[str, Any]: return self.build347.close_capsule(search_run_id, **kwargs)
    def list_capsules(self, **kwargs: Any) -> list[dict[str, Any]]: return self.build347.list_capsules(**kwargs)
    def decisions(self, search_run_id: str) -> list[dict[str, Any]]: return self.build347.decisions(search_run_id)
    def assessments(self, search_run_id: str) -> list[dict[str, Any]]: return self.build347.assessments(search_run_id)
    def ingest_artifact(self, **kwargs: Any) -> dict[str, Any]: return self.build347.ingest_artifact(**kwargs)
    def artifact(self, object_id: str) -> dict[str, Any]: return self.build347.artifact(object_id)
    def artifact_bytes(self, object_id: str) -> bytes: return self.build347.artifact_bytes(object_id)
    def artifacts(self, **kwargs: Any) -> list[dict[str, Any]]: return self.build347.artifacts(**kwargs)
    def review_artifact(self, object_id: str, **kwargs: Any) -> dict[str, Any]: return self.build347.review_artifact(object_id, **kwargs)

    def _object_indexable(self, object_id: str) -> tuple[bool, str]:
        meta = self.artifact(object_id)
        if meta["media_type"] not in {"text/plain", "text/markdown", "application/json", "text/html"}:
            return False, "non_text_media"
        if meta["security_state"] in {"reviewed_safe", "safe_text"}:
            return True, "safe_ingest_state"
        approved = self.db.one("SELECT event_id FROM phase15_object_events WHERE object_id=? AND event_type='human_review' AND decision='approve_safe' ORDER BY created_at DESC LIMIT 1", (object_id,))
        return (bool(approved), "human_approve_safe" if approved else "human_review_required")

    def index_artifact(self, object_id: str, *, title: str = "") -> dict[str, Any]:
        meta = self.artifact(object_id)
        allowed, reason = self._object_indexable(object_id)
        if not allowed:
            raise PermissionError(f"artifact is not indexable: {reason}")
        raw = self.artifact_bytes(object_id)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("artifact is not UTF-8 text") from exc
        return self.search.local.index_document(
            doc_id="doc_" + object_id,
            case_id=meta["case_id"],
            object_id=object_id,
            source_id=meta.get("source_id") or "",
            title=title or f"Artifact {object_id}",
            body=text,
            security_state="reviewed_safe",
            provenance={"object_sha256": meta["sha256"], "review_basis": reason, "search_policy": SEARCH_POLICY},
        )

    def index_local_text(self, *, case_id: str, title: str, text: str, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.search.local.index_document(doc_id="doc_" + uuid.uuid4().hex[:24], case_id=case_id, title=title, body=text, security_state="local_safe", provenance=provenance or {"mode": "analyst_local_text"})

    def search_case(self, *, case_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.search.local.search(case_id=case_id, query=query, limit=limit)

    def enqueue_job(self, **kwargs: Any) -> dict[str, Any]: return self.jobs.enqueue(**kwargs)
    def claim_job(self, **kwargs: Any) -> dict[str, Any] | None: return self.jobs.claim(**kwargs)
    def checkpoint_job(self, job_id: str, checkpoint: dict[str, Any], *, worker_id: str) -> dict[str, Any]: return self.jobs.checkpoint(job_id, checkpoint, worker_id=worker_id)
    def consume_job_request_budget(self, job_id: str, *, worker_id: str, units: int = 1) -> dict[str, Any]: return self.jobs.consume_request_budget(job_id, worker_id=worker_id, units=units)
    def complete_job(self, job_id: str, result: dict[str, Any], *, worker_id: str) -> dict[str, Any]: return self.jobs.complete(job_id, result, worker_id=worker_id)
    def fail_job(self, job_id: str, error: str, *, worker_id: str, retry_delay_seconds: int = 30) -> dict[str, Any]: return self.jobs.fail(job_id, error, worker_id=worker_id, retry_delay_seconds=retry_delay_seconds)
    def cancel_job(self, job_id: str) -> dict[str, Any]: return self.jobs.cancel(job_id, actor=self.actor)
    def resume_job(self, job_id: str) -> dict[str, Any]: return self.jobs.resume(job_id, actor=self.actor)
    def list_jobs(self, **kwargs: Any) -> list[dict[str, Any]]: return self.jobs.list(**kwargs)

    def enqueue_darknet_research_job(self, *, case_id: str, search_run_id: str, source_id: str, request_url: str) -> dict[str, Any]:
        run = self.db.one("SELECT case_id,search_kind FROM phase15_search_runs WHERE search_run_id=?", (search_run_id,))
        if not run or run["case_id"] != case_id or run["search_kind"] != "darknet":
            raise PermissionError("active darknet search_run_id for the case required")
        source = self.db.one("SELECT source_kind,review_status,locator FROM phase15_sources WHERE source_id=?", (source_id,))
        if not source or source["source_kind"] != "darknet_onion" or source["review_status"] != "approved_read_only":
            raise PermissionError("reviewed read-only onion source required")
        preflight = self.preflight_request(search_run_id, url=request_url, source_id=source_id, resolved_ips=[], browser_webrtc_disabled=True, dns_via_approved_profile=True)
        if preflight.get("final_disposition") != "allow_for_gateway":
            raise PermissionError("OPSEC-v2 preflight did not authorize gateway handoff")
        return self.jobs.enqueue(
            job_type="darknet_readonly_gateway_handoff",
            case_id=case_id,
            search_run_id=search_run_id,
            idempotency_key=hashlib.sha256(f"{search_run_id}|{source_id}|{request_url}".encode()).hexdigest(),
            payload={"source_id": source_id, "url": request_url, "opsec_decision_id": preflight.get("decision_id"), "network_execution_by_build348": False, "requires_worker_gateway": True},
            max_attempts=3,
            resource_budget={"max_runtime_seconds": 300, "max_memory_mb": 256, "max_output_bytes": 10 * 1024 * 1024},
            rate_budget={"max_requests": 1, "requests_per_minute": 1},
        )

    def search_status(self) -> dict[str, Any]: return self.search.status()
    def job_status(self) -> dict[str, Any]: return self.jobs.stats()

    def architecture_status(self) -> dict[str, Any]:
        search_text = (self._root / "src/eagleeye/search_platform/backends.py").read_text(encoding="utf-8")
        jobs_text = (self._root / "src/eagleeye/jobs/engine.py").read_text(encoding="utf-8")
        imported: set[str] = set()
        for text in (search_text, jobs_text):
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
        return {
            "search_policy": SEARCH_POLICY,
            "job_policy": JOB_POLICY,
            "portable_search_backend": "sqlite_fts5",
            "team_search_backend": "postgresql_fts_opt_in",
            "team_search_auto_connect": False,
            "persistent_jobs": True,
            "auto_background_workers": False,
            "job_idempotency": True,
            "job_retry_backoff": True,
            "job_checkpoint": True,
            "job_cancel_resume": True,
            "dead_letter_queue": True,
            "darknet_jobs_require_capsule_opsec_preflight": True,
            "runtime_network_execution": False,
            "subprocess_in_new_modules": "subprocess" in search_text or "subprocess" in jobs_text,
            "network_client_imports_in_new_modules": any(name == "requests" or name.startswith("requests.") or name == "httpx" or name.startswith("httpx.") or name == "urllib.request" or name == "socket" or name.startswith("socket.") for name in imported),
        }

    @staticmethod
    def _maturity(states: dict[str, bool]) -> str:
        last = "declared"
        for key in DIMENSIONS:
            if states[key]: last = key
            else: break
        return last

    def capabilities(self) -> list[dict[str, Any]]:
        metrics = self.schema_metrics(); version = self.version_status(); bench = bool(self._benchmark()); fp = self.code_fingerprint()
        specs = [
            ("schema_baseline_retained_348", "Schema Baseline retained", "schema", metrics["within_gate"], "schema", False, False),
            ("fts5_portable_search_v1", "SQLite FTS5 portable search backend", "search", True, "fts5", bench, False),
            ("postgres_team_search_contract_v1", "PostgreSQL team search adapter contract", "search", True, "team_search_contract", bench, False),
            ("persistent_job_engine_v1", "Persistent idempotent job engine", "jobs", True, "jobs", bench, False),
            ("darknet_job_handoff_v1", "Darknet Capsule + OPSEC controlled job handoff", "darknet", True, "darknet_job", bench, False),
            ("data_platform_347_retained", "Build 347 data platform retained", "data", True, "data_retained", False, False),
            ("canonical_versioning_348", "Canonical Build 348 version contract", "packaging", version["coherent"], "version", False, False),
        ]
        rows=[]
        for key,name,category,integrated,probe,benchmarked,external in specs:
            tested=bool(integrated and self._probe(probe))
            states={"implemented":bool(integrated),"integrated":bool(integrated),"tested":tested,"benchmarked":bool(tested and benchmarked),"externally_validated":bool(tested and external)}
            rows.append({"capability_key":key,"display_name":name,"category":category,**states,"maturity":self._maturity(states),"required_for_baseline":True,"required_for_production":True,"live_external_validation":"not_run" if key=="postgres_team_search_contract_v1" else "pending_or_not_applicable","code_fingerprint":fp})
        return rows

    def qualified_gate(self) -> dict[str, Any]:
        rows=self.capabilities(); baseline=[r for r in rows if r["required_for_baseline"]]
        baseline_tested=bool(baseline) and all(r["tested"] for r in baseline)
        schema_gate=self.schema_metrics()["within_gate"]
        build_acceptance=baseline_tested and schema_gate
        production=bool(rows) and all(r["externally_validated"] for r in rows if r["required_for_production"])
        return {"build":self.BUILD,"phase":"15","gate_authority":"build348_search_job_evidence_gate","build_acceptance_ready":build_acceptance,"production_release_ready":production,"release_ready":production,"baseline_tested":baseline_tested,"schema_gate":schema_gate,"external_team_search_validated":False,"active_gate_literal_true_lines":self.active_gate_literal_true_lines(),"rule":"Local FTS5 and durable jobs are active. Team search is opt-in; contract tests do not equal external validation. Darknet jobs require reviewed source + capsule + OPSEC-v2 preflight and are not executed by Build 348."}

    def dashboard(self) -> dict[str, Any]:
        return {"build":self.BUILD,"phase":"15","name":"Search & Job Infrastructure","schema":self.schema_metrics(),"search":self.search_status(),"jobs":self.job_status(),"architecture":self.architecture_status(),"gate":self.qualified_gate(),"version":self.version_status(),"capabilities":self.capabilities(),"darknet_runtime_execution":False}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        s=self.search_status(); j=self.job_status(); gate=self.qualified_gate()
        return (
            "<section class='card'><h2>Phase 15 · Build 348 · Search & Job Infrastructure</h2>"
            f"<p><b>FTS5:</b> {'aktiv' if s['fts5_available'] else 'nicht verfügbar'} · <b>Indexierte Dokumente:</b> {s['indexed_documents']} · <b>Jobs:</b> {sum(j['counts'].values())} · <b>Build-Gate:</b> {'PASS' if gate['build_acceptance_ready'] else 'offen'}.</p>"
            "<p>Darknet-Artefakte bleiben bis zu einem menschlichen approve_safe außerhalb des Volltextindex. Netzwerkjobs sind nur kontrollierte Gateway-Handoffs; Build 348 führt selbst keine externe Verbindung aus.</p>"
            f"<form method='post' action='/cases/{html.escape(case_id)}/search/local'><input type='hidden' name='csrf' value='{html.escape(csrf)}'><label>Lokale Fallnotiz indexieren</label><input name='title' placeholder='Titel' required><textarea name='text' required></textarea><button>Indexieren</button></form>"
            f"<form method='get' action='/cases/{html.escape(case_id)}/search'><label>Fall durchsuchen</label><input name='q' required><button>Suchen</button></form>"
            "<p><small>Status: <code>/api/build348</code></small></p></section>"
        )
