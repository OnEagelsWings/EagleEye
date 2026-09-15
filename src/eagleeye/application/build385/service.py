from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class Build385AcquisitionOrchestrationService:
    BUILD = "385.0"
    PACKAGE = "385.0.0"
    POLICY = "phase17.acquisition-orchestration-build.v385"

    def __init__(self, db: Any, audit: Any, *, build384: Any, acquisition385: Any, install_dir: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build384 = build384
        self.acquisition385 = acquisition385
        self.install_dir = Path(install_dir)
        self.actor = actor

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build384, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "eagleeye_pro/phase17/acquisition_orchestrator385.py",
            "eagleeye_pro/phase17/__init__.py",
            "eagleeye_pro/phase17/integration.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/application/build385/service.py",
            "src/eagleeye/interfaces/web/app385.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "tests/test_build385_integrated.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_385_0.py",
            "tools/benchmark_build385.py",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            p = self.install_dir / rel
            h.update(rel.encode())
            h.update(b"\0")
            h.update(p.read_bytes() if p.is_file() else b"<missing>")
            h.update(b"\0")
        return h.hexdigest()

    def version_status(self) -> dict[str, Any]:
        vt = (self.install_dir / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        pt = (self.install_dir / "pyproject.toml").read_text(encoding="utf-8")
        def g(pattern: str, text: str) -> str:
            match = re.search(pattern, text, re.M)
            return match.group(1) if match else "unknown"
        runtime = g(r'^BUILD\s*=\s*["\']([^"\']+)', vt)
        schema = g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', vt)
        package = g(r'^version\s*=\s*["\']([^"\']+)', pt)
        return {
            "runtime_build": runtime,
            "schema_version": schema,
            "package_version": package,
            "coherent": runtime == schema == self.BUILD and package == self.PACKAGE,
        }

    def schema_metrics(self) -> dict[str, Any]:
        _ = self.acquisition385.status()
        rows = self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type")
        counts = {r["type"]: int(r["c"]) for r in rows}
        integrity = str((self.db.one("PRAGMA integrity_check") or {}).get("integrity_check") or "unknown")
        required = {"source_capability_385", "acquisition_packet_385", "acquisition_preparation_385"}
        present = {r["name"] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}
        return {
            "tables": counts.get("table", 0),
            "indexes": counts.get("index", 0),
            "triggers": counts.get("trigger", 0),
            "views": counts.get("view", 0),
            "integrity_check": integrity,
            "build385_tables_present": required.issubset(present),
            "within_phase17_gate": counts.get("table", 0) < 190 and counts.get("index", 0) < 325 and integrity == "ok" and required.issubset(present),
        }

    def _evidence(self, filename: str) -> dict[str, Any]:
        value = _read_json(self.install_dir / filename)
        return value if value.get("build") == self.BUILD and value.get("code_fingerprint") == self.code_fingerprint() and value.get("result") == "pass" else {}


    def historical_build384_receipt(self) -> dict[str, Any]:
        release = _read_json(self.install_dir / "RELEASE_MANIFEST_BUILD_384_0.json")
        acceptance = _read_json(self.install_dir / "ACCEPTANCE_RESULTS_BUILD_384_0.json")
        valid = (
            release.get("build") == "384.0"
            and release.get("current_decision") == "phase17_integrated_professional_pilot_line"
            and release.get("production_release_ready") is False
            and int((release.get("regression") or {}).get("functional_regressions", -1)) == 0
            and (release.get("acceptance") or {}).get("result") == "pass"
            and acceptance.get("build") == "384.0"
            and acceptance.get("result") == "pass"
            and acceptance.get("code_fingerprint") == release.get("code_fingerprint")
        )
        return {
            "build": "384.0",
            "valid": bool(valid),
            "code_fingerprint": release.get("code_fingerprint", ""),
            "professional_pilot_line_preserved": release.get("current_decision") == "phase17_integrated_professional_pilot_line",
            "production_release_ready": False,
        }

    def acquisition_capabilities(self) -> list[dict[str, Any]]:
        return self.acquisition385.capabilities()

    def compile_acquisition_packet(self, **kwargs: Any) -> dict[str, Any]:
        packet = self.acquisition385.compile_packet(**kwargs)
        from dataclasses import asdict
        return asdict(packet) | {"packet_hash": packet.packet_hash}

    def acquisition_packet(self, **kwargs: Any) -> dict[str, Any]:
        return self.acquisition385.packet(**kwargs)

    def prepare_acquisition_packet(self, **kwargs: Any) -> dict[str, Any]:
        return self.acquisition385.prepare_packet(**kwargs)

    def acquisition_execution_readiness(self, **kwargs: Any) -> dict[str, Any]:
        return self.acquisition385.execution_readiness(**kwargs)

    def phase17_status(self, case_id: str = "") -> dict[str, Any]:
        out = dict(self.build384.phase17_status(case_id))
        out.update({
            "build": self.BUILD,
            "phase17_builds_completed": 5,
            "acquisition_orchestration_v2": True,
            "source_capability_matrix": True,
            "phase16_connector_bridge": True,
            "network_execution_added": False,
            "automatic_source_approval": False,
            "automatic_crawl_enqueue": False,
            "automatic_scope_expansion": False,
            "acquisition": self.acquisition385.status(),
        })
        return out

    def qualified_gate(self) -> dict[str, Any]:
        version = self.version_status()
        schema = self.schema_metrics()
        tests = self._evidence("BUILD_385_TEST_EVIDENCE.json")
        benchmark = self._evidence("BENCHMARK_BUILD_385_ACQUISITION.json")
        acceptance = self._evidence("ACCEPTANCE_RESULTS_BUILD_385_0.json")
        predecessor = self.historical_build384_receipt()
        status = self.acquisition385.status()
        checks = {
            "version_coherent": bool(version["coherent"]),
            "schema_integrity": bool(schema["within_phase17_gate"]),
            "phase17_predecessor_gate": bool(predecessor.get("valid")),
            "build385_tests": bool(tests),
            "build385_benchmark": bool(benchmark) and int(benchmark.get("violations", -1)) == 0,
            "build385_acceptance": bool(acceptance),
            "capability_matrix_seeded": int(status.get("capabilities", 0)) >= 6,
            "no_network_execution_added": not bool(status.get("network_execution_added")),
            "no_arbitrary_url_execution": not bool(status.get("arbitrary_url_execution")),
            "no_credential_injection": not bool(status.get("credential_injection")),
            "no_automatic_source_approval": not bool(status.get("automatic_source_approval")),
            "no_automatic_crawl_enqueue": not bool(status.get("automatic_crawl_enqueue")),
            "no_auto_scope_expansion": not bool(status.get("automatic_scope_expansion")),
            "no_host_security_mutation": not bool(status.get("host_security_mutation")),
        }
        return {
            "build": self.BUILD,
            "checks": checks,
            "build_acceptance_ready": all(checks.values()),
            "phase17_builds_completed": 5,
            "production_release_ready": False,
            "professional_pilot_line_preserved": bool(predecessor.get("professional_pilot_line_preserved")),
            "truthful_note": "Build 385 bridges confirmed Phase-17 research waves to governed Phase-16 source preparation. It creates no external requests, grants no execution authority, and does not promote pending sources to approved or queued state.",
        }

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "phase17": self.phase17_status(case_id),
            "acquisition": self.acquisition385.status(),
            "schema": self.schema_metrics(),
            "gate": self.qualified_gate(),
        }
