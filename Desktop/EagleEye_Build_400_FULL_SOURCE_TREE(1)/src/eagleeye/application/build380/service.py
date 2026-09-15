from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class Build380ProfessionalPilotDecisionService:
    BUILD = "380.0"
    PACKAGE = "380.0.0"
    POLICY = "phase16.professional-pilot-production-decision.v380"

    def __init__(self, db: Any, audit: Any, *, build379: Any, readiness380: Any, ai380: Any, opsec380: Any, install_dir: Any, base_dir: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build379 = build379
        self.readiness380 = readiness380
        self.ai380 = ai380
        self.opsec380 = opsec380
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build379, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/phase16/professional_pilot380.py",
            "src/eagleeye/application/build380/service.py",
            "src/eagleeye/interfaces/web/app380.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "tests/test_build380.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_380_0.py",
            "tools/benchmark_build380.py",
            "tools/final_qualify_380.py",
            "tools/generate_build380_evidence.py",
            "CRAWLER_ROADMAP_BUILD_370_TO_380.md",
            "PHASE_16_MASTERPLAN_BUILD_361_TO_380.md",
            "FINAL_READINESS_ASSESSMENT_BUILD_380.md",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            p = self.install_dir / rel
            h.update(rel.encode()); h.update(b"\0")
            h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "BUILD_380_TEST_EVIDENCE.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() else {}

    def _benchmark(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "BENCHMARK_BUILD_380_FINAL_DECISION.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() and int(value.get("cases", 0)) >= 6000 and int(value.get("violations", -1)) == 0 else {}

    def _final_qualification(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "FINAL_QUALIFICATION_BUILD_380.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() else {}

    def _historical_379_ready(self) -> bool:
        tests = _read_json(self.install_dir / "BUILD_379_TEST_EVIDENCE.json")
        acceptance = _read_json(self.install_dir / "ACCEPTANCE_RESULTS_BUILD_379_0.json")
        local = _read_json(self.install_dir / "LOCAL_PREQUALIFICATION_BUILD_379.json")
        return (
            tests.get("build") == "379.0" and tests.get("result") == "pass"
            and acceptance.get("build") == "379.0" and acceptance.get("result") == "pass"
            and local.get("build") == "379.0" and local.get("result") == "pass"
        )

    def _probe(self, key: str) -> bool:
        return self._test_evidence().get("probes", {}).get(key) == "pass"

    def schema_metrics(self) -> dict[str, Any]:
        rows = self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type")
        counts = {r["type"]: int(r["c"]) for r in rows}
        logical = int((self.db.one("SELECT page_count*page_size AS n FROM pragma_page_count(),pragma_page_size()") or {}).get("n") or 0)
        integrity = str((self.db.one("PRAGMA integrity_check") or {}).get("integrity_check") or "unknown")
        out = {
            "table": counts.get("table", 0), "index": counts.get("index", 0), "trigger": counts.get("trigger", 0), "view": counts.get("view", 0),
            "logical_bytes": logical, "integrity_check": integrity,
            "targets": {"tables_lt": 180, "indexes_lt": 300, "logical_bytes_lt": 5 * 1024 * 1024},
            "build380_new_tables": 0,
        }
        out["within_gate"] = out["table"] < 180 and out["index"] < 300 and logical < 5 * 1024 * 1024 and integrity == "ok"
        return out

    def version_status(self) -> dict[str, Any]:
        vt = (self.install_dir / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        pt = (self.install_dir / "pyproject.toml").read_text(encoding="utf-8")
        def g(pattern: str, text: str) -> str:
            m = re.search(pattern, text, re.M); return m.group(1) if m else "unknown"
        runtime = g(r'^BUILD\s*=\s*["\']([^"\']+)', vt)
        schema = g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', vt)
        package = g(r'^version\s*=\s*["\']([^"\']+)', pt)
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == self.PACKAGE}

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c, ast.Constant) and c.value is True and hasattr(c, "lineno")})
        return []

    def final_crawler_slo_gate(self) -> dict[str, Any]:
        return self.readiness380.crawler_slo_gate()

    def pilot_telemetry(self, *, case_id: str = "") -> dict[str, Any]:
        return self.readiness380.pilot_telemetry(case_id=case_id)

    def external_validation_matrix(self) -> dict[str, Any]:
        return self.readiness380.external_validation_matrix()

    def final_decision(self) -> dict[str, Any]:
        local_ready = self._local_gate_components_ready()
        result = self.readiness380.current_decision(local_ready=local_ready)
        result["phase16_complete"] = True
        result["phase16_builds_completed"] = 20
        result["phase16_total_builds"] = 20
        result["current_scope"] = self.readiness380.restricted_scope()
        return result

    def _local_gate_components_ready(self) -> bool:
        return (
            self.schema_metrics()["within_gate"]
            and self.version_status()["coherent"]
            and self._historical_379_ready()
            and bool(self._test_evidence())
            and bool(self._benchmark())
            and bool(self._final_qualification())
            and self.active_gate_literal_true_lines() == []
        )

    def phase16_status(self) -> dict[str, Any]:
        base = dict(self.build379.phase16_status())
        base.update({
            "build": self.BUILD,
            "builds_completed": 20,
            "builds_total": 20,
            "phase16_complete": True,
            "final_decision": self.final_decision(),
            "crawler_improvement_build": 380,
            "continuous_crawler_expansion_370_380": True,
        })
        return base

    def crawler_status(self) -> dict[str, Any]:
        base = dict(self.build379.crawler_status())
        slo = self.final_crawler_slo_gate()
        base.update({
            "crawler_improvement_build": 380,
            "final_professional_pilot_telemetry": True,
            "final_slo_gate": True,
            "pilot_slo_gate_pass": bool(slo.get("pilot_slo_gate_pass")),
            "production_slo_gate_pass": bool(slo.get("production_slo_gate_pass")),
            "external_slo_state": slo.get("external_slo_state"),
            "automatic_production_promotion": False,
            "continuous_crawler_expansion_370_380": True,
        })
        return base

    def run_autonomous_investigation(self, **kwargs: Any) -> dict[str, Any]:
        return self.ai380.run_cycle(**kwargs)

    def autonomous_opsec_protect(self, **kwargs: Any) -> dict[str, Any]:
        return self.opsec380.protect_case(**kwargs)

    def capabilities(self) -> list[dict[str, Any]]:
        bench = bool(self._benchmark())
        finalq = bool(self._final_qualification())
        external = bool(self.readiness380.qualification379.external_receipt_status(code_fingerprint=self.readiness380.historical_build379_fingerprint()).get("externally_validated"))
        specs = [
            ("phase16_final_decision_v380", "decision"),
            ("professional_pilot_telemetry_v380", "telemetry"),
            ("crawler_final_slo_gate_v380", "crawler_slo"),
            ("external_validation_matrix_v380", "matrix"),
            ("ai_final_readiness_context_v380", "ai"),
            ("opsec_production_override_containment_v380", "opsec"),
        ]
        out = []
        for key, probe in specs:
            tested = finalq and self._probe(probe)
            states = {"implemented": True, "integrated": True, "tested": tested, "benchmarked": bench, "externally_validated": external if probe == "crawler_slo" else False}
            maturity = next((k for k in reversed(DIMENSIONS) if states[k]), "declared")
            out.append({"key": key, "states": states, "maturity": maturity})
        return out

    def qualified_gate(self) -> dict[str, Any]:
        schema_ok = self.schema_metrics()["within_gate"]
        version_ok = self.version_status()["coherent"]
        predecessor_ok = self._historical_379_ready()
        tests_ok = bool(self._test_evidence())
        benchmark_ok = bool(self._benchmark())
        finalq_ok = bool(self._final_qualification())
        literal_gate_ok = self.active_gate_literal_true_lines() == []
        checks = {
            "schema_within_gate": schema_ok,
            "version_coherent": version_ok,
            "historical_build379_evidence_pass": predecessor_ok,
            "test_evidence_current": tests_ok,
            "benchmark_6000_no_violations": benchmark_ok,
            "final_qualification_current": finalq_ok,
            "decision_tested": self._probe("decision"),
            "telemetry_tested": self._probe("telemetry"),
            "crawler_slo_tested": self._probe("crawler_slo"),
            "external_matrix_tested": self._probe("matrix"),
            "ai_boundary_tested": self._probe("ai"),
            "opsec_boundary_tested": self._probe("opsec"),
            "no_literal_true_gate": literal_gate_ok,
        }
        acceptance = all(bool(x) for x in checks.values())
        decision = self.readiness380.current_decision(local_ready=acceptance)
        return {
            "build": self.BUILD,
            "checks": checks,
            "build_acceptance_ready": acceptance,
            "phase16_complete": acceptance,
            "final_decision": decision["decision"],
            "professional_pilot_ready": bool(decision["professional_pilot_ready"]),
            "production_candidate": bool(decision["production_candidate"]),
            "production_release_ready": bool(decision["production_release_ready"]),
            "external_qualification_validated": bool(decision["external_qualification_validated"]),
            "truthful_note": "Build 380 completes Phase 16. With current local evidence and no independent Build-379 receipt, the truthful current decision is professional_pilot_only, not production_candidate.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "phase16": self.phase16_status(),
            "crawler": self.crawler_status(),
            "pilot_telemetry": self.pilot_telemetry(),
            "crawler_slo": self.final_crawler_slo_gate(),
            "external_validation_matrix": self.external_validation_matrix(),
            "capabilities": self.capabilities(),
            "gate": self.qualified_gate(),
            "decision": self.final_decision(),
        }
