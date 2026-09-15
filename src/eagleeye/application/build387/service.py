from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class Build387ControlledExecutorService:
    BUILD = "387.0"
    PACKAGE = "387.0.0"
    POLICY = "phase17.controlled-executor-build.v387"

    def __init__(self, db: Any, audit: Any, *, build386: Any, executor387: Any, install_dir: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build386 = build386
        self.executor387 = executor387
        self.install_dir = Path(install_dir)
        self.actor = actor

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build386, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "eagleeye_pro/phase17/controlled_executor387.py",
            "eagleeye_pro/phase17/execution_authority386.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/application/build387/service.py",
            "src/eagleeye/interfaces/web/app387.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "tests/test_build387_integrated.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_387_0.py",
            "tools/benchmark_build387.py",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            p = self.install_dir / rel
            h.update(rel.encode()); h.update(b"\0")
            h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def version_status(self) -> dict[str, Any]:
        vt = (self.install_dir / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        pt = (self.install_dir / "pyproject.toml").read_text(encoding="utf-8")
        def g(pattern: str, text: str) -> str:
            m = re.search(pattern, text, re.M)
            return m.group(1) if m else "unknown"
        runtime = g(r'^BUILD\s*=\s*["\']([^"\']+)', vt)
        schema = g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', vt)
        package = g(r'^version\s*=\s*["\']([^"\']+)', pt)
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == self.PACKAGE}

    def schema_metrics(self) -> dict[str, Any]:
        _ = self.executor387.status()
        rows = self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type")
        counts = {r["type"]: int(r["c"]) for r in rows}
        integrity = str((self.db.one("PRAGMA integrity_check") or {}).get("integrity_check") or "unknown")
        present = {r["name"] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}
        return {
            "tables": counts.get("table", 0), "indexes": counts.get("index", 0), "triggers": counts.get("trigger", 0), "views": counts.get("view", 0),
            "integrity_check": integrity,
            "build387_tables_present": "execution_dispatch_387" in present,
            "within_phase17_gate": counts.get("table", 0) < 200 and counts.get("index", 0) < 340 and integrity == "ok" and "execution_dispatch_387" in present,
        }

    def _evidence(self, filename: str) -> dict[str, Any]:
        value = _read_json(self.install_dir / filename)
        return value if value.get("build") == self.BUILD and value.get("code_fingerprint") == self.code_fingerprint() and value.get("result") == "pass" else {}

    def historical_build386_receipt(self) -> dict[str, Any]:
        release = _read_json(self.install_dir / "RELEASE_MANIFEST_BUILD_386_0.json")
        acceptance = _read_json(self.install_dir / "ACCEPTANCE_RESULTS_BUILD_386_0.json")
        valid = (
            release.get("build") == "386.0"
            and release.get("production_release_ready") is False
            and int((release.get("regression") or {}).get("functional_regressions", -1)) == 0
            and (release.get("acceptance") or {}).get("result") == "pass"
            and acceptance.get("build") == "386.0"
            and acceptance.get("result") == "pass"
            and acceptance.get("code_fingerprint") == release.get("code_fingerprint")
        )
        return {"build": "386.0", "valid": bool(valid), "code_fingerprint": release.get("code_fingerprint", ""), "production_release_ready": False}

    def execute_grant(self, **kwargs: Any) -> dict[str, Any]:
        return self.executor387.execute_grant(**kwargs)

    def execution_dispatch(self, **kwargs: Any) -> dict[str, Any]:
        return self.executor387.dispatch(**kwargs)

    def verify_execution_dispatch(self, **kwargs: Any) -> dict[str, Any]:
        return self.executor387.verify_dispatch_record(**kwargs)

    def phase17_status(self, case_id: str = "") -> dict[str, Any]:
        out = dict(self.build386.phase17_status(case_id))
        out.update({
            "build": self.BUILD,
            "phase17_builds_completed": 7,
            "controlled_executor": True,
            "one_time_grant_consumption": True,
            "post_reservation_revalidation": True,
            "phase16_connector_gate_reuse": True,
            "network_jobs_can_be_enqueued_after_live_confirmation": True,
            "executor_performs_direct_fetch": False,
            "executor_claims_worker_job": False,
            "automatic_scope_expansion": False,
            "executor": self.executor387.status(),
        })
        return out

    def qualified_gate(self) -> dict[str, Any]:
        version = self.version_status(); schema = self.schema_metrics()
        tests = self._evidence("BUILD_387_TEST_EVIDENCE.json")
        benchmark = self._evidence("BENCHMARK_BUILD_387_CONTROLLED_EXECUTOR.json")
        acceptance = self._evidence("ACCEPTANCE_RESULTS_BUILD_387_0.json")
        predecessor = self.historical_build386_receipt(); status = self.executor387.status()
        checks = {
            "version_coherent": bool(version["coherent"]),
            "schema_integrity": bool(schema["within_phase17_gate"]),
            "phase17_predecessor_gate": bool(predecessor.get("valid")),
            "build387_tests": bool(tests),
            "build387_benchmark": bool(benchmark) and int(benchmark.get("violations", -1)) == 0,
            "build387_acceptance": bool(acceptance),
            "one_time_grant_consumption": bool(status.get("one_time_grant_consumption")),
            "atomic_dispatch": bool(status.get("atomic_reserve_revalidate_enqueue_consume")),
            "post_reservation_revalidation": bool(status.get("post_reservation_revalidation")),
            "workflow_budget_recheck": bool(status.get("workflow_budget_recheck")),
            "phase16_connector_gate_reuse": bool(status.get("phase16_connector_gate_reuse")),
            "executor_no_direct_fetch": not bool(status.get("direct_network_fetch_by_executor")),
            "executor_no_worker_claim": not bool(status.get("worker_claim_by_executor")),
            "no_auto_scope_expansion": not bool(status.get("automatic_scope_expansion")),
            "no_host_security_mutation": not bool(status.get("host_security_mutation")),
        }
        return {
            "build": self.BUILD, "checks": checks, "build_acceptance_ready": all(checks.values()),
            "phase17_builds_completed": 7, "production_release_ready": False,
            "professional_pilot_line_preserved": bool(predecessor.get("valid")),
            "truthful_note": "Build 387 consumes an explicit Build-386 GO grant exactly once and enqueues already-reviewed read-only Phase-16 connector jobs only after exact LIVE confirmation and last-moment revalidation. The executor itself performs no network fetch and does not claim a worker lease.",
        }

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        return {"build": self.BUILD, "phase17": self.phase17_status(case_id), "executor": self.executor387.status(), "schema": self.schema_metrics(), "gate": self.qualified_gate()}
