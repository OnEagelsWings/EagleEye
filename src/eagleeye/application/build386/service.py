from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class Build386CapabilityScopedGOService:
    BUILD = "386.0"
    PACKAGE = "386.0.0"
    POLICY = "phase17.capability-scoped-go-build.v386"

    def __init__(self, db: Any, audit: Any, *, build385: Any, authority386: Any, install_dir: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build385 = build385
        self.authority386 = authority386
        self.install_dir = Path(install_dir)
        self.actor = actor

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build385, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "eagleeye_pro/phase17/execution_authority386.py",
            "eagleeye_pro/phase17/acquisition_orchestrator385.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/application/build386/service.py",
            "src/eagleeye/interfaces/web/app386.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "tests/test_build386_integrated.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_386_0.py",
            "tools/benchmark_build386.py",
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
        _ = self.authority386.status()
        rows = self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type")
        counts = {r["type"]: int(r["c"]) for r in rows}
        integrity = str((self.db.one("PRAGMA integrity_check") or {}).get("integrity_check") or "unknown")
        present = {r["name"] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}
        return {
            "tables": counts.get("table", 0), "indexes": counts.get("index", 0), "triggers": counts.get("trigger", 0), "views": counts.get("view", 0),
            "integrity_check": integrity,
            "build386_tables_present": "execution_grant_386" in present,
            "within_phase17_gate": counts.get("table", 0) < 195 and counts.get("index", 0) < 330 and integrity == "ok" and "execution_grant_386" in present,
        }

    def _evidence(self, filename: str) -> dict[str, Any]:
        value = _read_json(self.install_dir / filename)
        return value if value.get("build") == self.BUILD and value.get("code_fingerprint") == self.code_fingerprint() and value.get("result") == "pass" else {}

    def historical_build385_receipt(self) -> dict[str, Any]:
        release = _read_json(self.install_dir / "RELEASE_MANIFEST_BUILD_385_0.json")
        acceptance = _read_json(self.install_dir / "ACCEPTANCE_RESULTS_BUILD_385_0.json")
        valid = (
            release.get("build") == "385.0"
            and release.get("production_release_ready") is False
            and int((release.get("regression") or {}).get("functional_regressions", -1)) == 0
            and (release.get("acceptance") or {}).get("result") == "pass"
            and acceptance.get("build") == "385.0"
            and acceptance.get("result") == "pass"
            and acceptance.get("code_fingerprint") == release.get("code_fingerprint")
        )
        return {"build": "385.0", "valid": bool(valid), "code_fingerprint": release.get("code_fingerprint", ""), "production_release_ready": False}

    def execution_preflight(self, **kwargs: Any) -> dict[str, Any]:
        return self.authority386.preflight(**kwargs)

    def issue_execution_grant(self, **kwargs: Any) -> dict[str, Any]:
        return self.authority386.issue_grant(**kwargs)

    def execution_grant(self, **kwargs: Any) -> dict[str, Any]:
        return self.authority386.grant(**kwargs)

    def verify_execution_grant(self, **kwargs: Any) -> dict[str, Any]:
        return self.authority386.verify_grant(**kwargs)

    def revoke_execution_grant(self, **kwargs: Any) -> dict[str, Any]:
        return self.authority386.revoke_grant(**kwargs)

    def phase17_status(self, case_id: str = "") -> dict[str, Any]:
        out = dict(self.build385.phase17_status(case_id))
        out.update({
            "build": self.BUILD,
            "phase17_builds_completed": 6,
            "capability_scoped_go": True,
            "execution_packet_binding": True,
            "request_budget_binding": True,
            "operations_opsec_preflight_binding": True,
            "network_execution_added": False,
            "automatic_execution": False,
            "automatic_scope_expansion": False,
            "execution_authority": self.authority386.status(),
        })
        return out

    def qualified_gate(self) -> dict[str, Any]:
        version = self.version_status(); schema = self.schema_metrics()
        tests = self._evidence("BUILD_386_TEST_EVIDENCE.json")
        benchmark = self._evidence("BENCHMARK_BUILD_386_GO_GRANTS.json")
        acceptance = self._evidence("ACCEPTANCE_RESULTS_BUILD_386_0.json")
        predecessor = self.historical_build385_receipt(); status = self.authority386.status()
        checks = {
            "version_coherent": bool(version["coherent"]),
            "schema_integrity": bool(schema["within_phase17_gate"]),
            "phase17_predecessor_gate": bool(predecessor.get("valid")),
            "build386_tests": bool(tests),
            "build386_benchmark": bool(benchmark) and int(benchmark.get("violations", -1)) == 0,
            "build386_acceptance": bool(acceptance),
            "capability_scoped_go": bool(status.get("capability_scoped_go")),
            "token_hash_only": bool(status.get("token_hash_only_persistence")),
            "packet_hash_binding": bool(status.get("packet_hash_binding")),
            "workflow_generation_binding": bool(status.get("workflow_generation_binding")),
            "operations_preflight_binding": bool(status.get("operations_preflight_binding")),
            "opsec_preflight_binding": bool(status.get("opsec_preflight_binding")),
            "request_budget_binding": bool(status.get("request_budget_binding")),
            "no_direct_network_authority": not bool(status.get("direct_network_authority")),
            "no_automatic_execution": not bool(status.get("automatic_execution")),
            "no_auto_scope_expansion": not bool(status.get("automatic_scope_expansion")),
            "no_host_security_mutation": not bool(status.get("host_security_mutation")),
        }
        return {
            "build": self.BUILD, "checks": checks, "build_acceptance_ready": all(checks.values()),
            "phase17_builds_completed": 6, "production_release_ready": False,
            "professional_pilot_line_preserved": bool(predecessor.get("valid")),
            "truthful_note": "Build 386 issues short-lived capability-scoped GO grants only after source review, workflow-budget, Operations and OPSEC preflight. It does not enqueue or execute external work.",
        }

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        return {"build": self.BUILD, "phase17": self.phase17_status(case_id), "execution_authority": self.authority386.status(), "schema": self.schema_metrics(), "gate": self.qualified_gate()}
