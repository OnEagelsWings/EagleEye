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


class Build379ExternalQualificationService:
    BUILD = "379.0"
    PACKAGE = "379.0.0"
    POLICY = "phase16.external-qualification-build.v379"

    def __init__(self, db: Any, audit: Any, *, build378: Any, qualification379: Any, ai379: Any, opsec379: Any, install_dir: Any, base_dir: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build378 = build378
        self.qualification379 = qualification379
        self.ai379 = ai379
        self.opsec379 = opsec379
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build378, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/phase16/external_qualification379.py",
            "src/eagleeye/application/build379/service.py",
            "src/eagleeye/interfaces/web/app379.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "tests/test_build379.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_379_0.py",
            "tools/benchmark_build379.py",
            "tools/local_prequalify_379.py",
            "tools/generate_build379_evidence.py",
            "CRAWLER_ROADMAP_BUILD_370_TO_380.md",
            "PHASE_16_MASTERPLAN_BUILD_361_TO_380.md",
            "EXTERNAL_QUALIFICATION_GUIDE_BUILD_379.md",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            p = self.install_dir / rel
            h.update(rel.encode()); h.update(b"\0")
            h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "BUILD_379_TEST_EVIDENCE.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() else {}

    def _benchmark(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "BENCHMARK_BUILD_379_EXTERNAL_QUALIFICATION.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() and int(value.get("cases", 0)) >= 5600 and int(value.get("violations", -1)) == 0 else {}

    def _local_prequalification(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "LOCAL_PREQUALIFICATION_BUILD_379.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() else {}

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
            "external_qualification_new_tables": 0,
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

    def external_qualification_contract(self) -> dict[str, Any]:
        return self.qualification379.contract()

    def external_qualification_status(self) -> dict[str, Any]:
        return self.qualification379.external_receipt_status(code_fingerprint=self.code_fingerprint())

    def qualification_snapshot(self, *, case_id: str = "") -> dict[str, Any]:
        return self.qualification379.runtime_snapshot(case_id=case_id)

    def run_autonomous_investigation(self, **kwargs: Any) -> dict[str, Any]:
        return self.ai379.run_cycle(**kwargs)

    def autonomous_opsec_protect(self, **kwargs: Any) -> dict[str, Any]:
        return self.opsec379.protect_case(**kwargs)

    def phase16_status(self) -> dict[str, Any]:
        base = dict(self.build378.phase16_status())
        base.update({
            "build": self.BUILD,
            "builds_completed": 19,
            "external_qualification": self.qualification379.status(),
            "ai": self.ai379.status(),
            "opsec": self.opsec379.status(),
            "crawler_improvement_build": 379,
            "continuous_crawler_expansion_370_380": True,
        })
        return base

    def crawler_status(self) -> dict[str, Any]:
        base = dict(self.build378.crawler_status())
        base.update({
            "crawler_improvement_build": 379,
            "qualification_soak_load_failure_harness": True,
            "qualification_recovery_slo_measurement": True,
            "qualification_queue_lease_stability": True,
            "qualification_case_isolation": True,
            "qualification_object_store_pressure_gate": True,
            "production_fault_injection_api": False,
            "external_qualification_requires_signed_receipt": True,
            "external_receipt_grants_network_scope": False,
            "automatic_evidence_eviction": False,
            "continuous_crawler_expansion_370_380": True,
            "automatic_external_connections_on_boot": 0,
            "background_workers_started_on_boot": 0,
        })
        return base

    def capabilities(self) -> list[dict[str, Any]]:
        bench = bool(self._benchmark())
        local = bool(self._local_prequalification())
        external = bool(self.external_qualification_status().get("externally_validated"))
        specs = [
            ("qualification_runtime_snapshot_v379", "snapshot"),
            ("crawler_recovery_slo_prequalification_v379", "recovery"),
            ("queue_lease_stability_prequalification_v379", "queue"),
            ("case_isolation_prequalification_v379", "case_isolation"),
            ("object_store_pressure_prequalification_v379", "pressure"),
            ("external_receipt_ed25519_v379", "receipt"),
            ("opsec_fault_injection_containment_v379", "opsec"),
            ("local_external_qualification_preflight_v379", "local"),
        ]
        out = []
        for key, probe in specs:
            tested = local if probe == "local" else self._probe(probe)
            states = {"implemented": True, "integrated": True, "tested": tested, "benchmarked": bench, "externally_validated": external if probe == "receipt" else False}
            maturity = next((k for k in reversed(DIMENSIONS) if states[k]), "declared")
            out.append({"key": key, "states": states, "maturity": maturity})
        return out

    def qualified_gate(self) -> dict[str, Any]:
        schema_ok = self.schema_metrics()["within_gate"]
        version_ok = self.version_status()["coherent"]
        tests_ok = bool(self._test_evidence())
        benchmark_ok = bool(self._benchmark())
        local_ok = bool(self._local_prequalification())
        literal_gate_ok = self.active_gate_literal_true_lines() == []
        checks = {
            "schema_within_gate": schema_ok,
            "version_coherent": version_ok,
            "test_evidence_current": tests_ok,
            "benchmark_5600_no_violations": benchmark_ok,
            "local_prequalification_current": local_ok,
            "snapshot_tested": self._probe("snapshot"),
            "recovery_slo_tested": self._probe("recovery"),
            "queue_lease_tested": self._probe("queue"),
            "case_isolation_tested": self._probe("case_isolation"),
            "object_store_pressure_tested": self._probe("pressure"),
            "receipt_verification_tested": self._probe("receipt"),
            "opsec_tested": self._probe("opsec"),
            "no_literal_true_gate": literal_gate_ok,
        }
        external = self.external_qualification_status()
        acceptance = all(bool(x) for x in checks.values())
        production = acceptance and bool(external.get("externally_validated")) and False
        final_decision_required = self.BUILD == "379.0"
        return {
            "build": self.BUILD,
            "checks": checks,
            "build_acceptance_ready": acceptance,
            "local_prequalification": "pass" if local_ok else "not_run",
            "external_qualification": "validated" if external.get("externally_validated") else "not_run",
            "external_qualification_detail": external,
            "production_release_ready": production,
            "build380_final_decision_required": final_decision_required,
            "truthful_note": "Build 379 can prequalify stability locally, but external validation requires an independently signed fingerprint-bound receipt. Build 380 owns the final production/pilot decision.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "phase16": self.phase16_status(),
            "crawler": self.crawler_status(),
            "qualification": self.qualification379.status(),
            "local_prequalification": self._local_prequalification(),
            "external_receipt": self.external_qualification_status(),
            "capabilities": self.capabilities(),
            "gate": self.qualified_gate(),
        }
