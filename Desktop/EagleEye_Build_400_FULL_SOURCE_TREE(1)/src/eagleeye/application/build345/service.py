from __future__ import annotations

import ast
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from eagleeye.security.search_capsule import POLICY_VERSION, SearchSessionCapsuleManager

DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class Build345SearchCapsuleService:
    BUILD = "345.0"

    def __init__(self, db: Any, audit: Any, *, build344: Any, capsule_manager: SearchSessionCapsuleManager, install_dir: str | Path, base_dir: str | Path, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build344 = build344
        self.capsules = capsule_manager
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._root = self.install_dir

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/infrastructure/schema_v1/schema.py",
            "src/eagleeye/security/search_capsule.py",
            "src/eagleeye/application/build345/service.py",
            "src/eagleeye/interfaces/web/app345.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "EAGLEEYE_PRO_345_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_345_0.py",
            "tests/test_build345.py",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            path = self._root / rel
            h.update(rel.encode()); h.update(b"\0")
            h.update(path.read_bytes() if path.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        data = _read_json(self._root / "BUILD_345_TEST_EVIDENCE.json")
        if data.get("build") == self.BUILD and data.get("result") == "pass" and data.get("code_fingerprint") == self.code_fingerprint() and isinstance(data.get("probes"), dict):
            return data
        return {}

    def _probe(self, name: str) -> bool:
        return self._test_evidence().get("probes", {}).get(name) == "pass"

    def _benchmark(self) -> dict[str, Any]:
        data = _read_json(self._root / "BENCHMARK_BUILD_345_SEARCH_CAPSULE.json")
        if data.get("build") != self.BUILD or data.get("code_fingerprint") != self.code_fingerprint():
            return {}
        if data.get("cases", 0) < 200 or data.get("violations") != 0 or data.get("result") != "pass":
            return {}
        return data

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c, ast.Constant) and c.value is True and hasattr(c, "lineno")})
        return []

    def schema_metrics(self) -> dict[str, Any]:
        return self.build344.schema_metrics()

    def version_status(self) -> dict[str, Any]:
        version_text = (self._root / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        project_text = (self._root / "pyproject.toml").read_text(encoding="utf-8")
        rb = re.search(r'^BUILD\s*=\s*["\']([^"\']+)', version_text, re.M)
        rs = re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', version_text, re.M)
        rp = re.search(r'^version\s*=\s*["\']([^"\']+)', project_text, re.M)
        runtime = rb.group(1) if rb else "unknown"
        schema = rs.group(1) if rs else "unknown"
        package = rp.group(1) if rp else "unknown"
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == "345.0.0"}

    def register_darknet_source(self, **kwargs: Any) -> dict[str, Any]:
        return self.build344.register_darknet_source(**kwargs)

    def review_darknet_source(self, source_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.build344.review_darknet_source(source_id, **kwargs)

    def create_clearnet_capsule(self, *, case_id: str, egress_hosts: list[str], max_requests: int = 25, actor: str | None = None) -> dict[str, Any]:
        return self.capsules.create_capsule(case_id=case_id, search_kind="clearnet", egress_allowlist=egress_hosts, network_profile_ref="direct_https_v1", max_requests=max_requests, actor=actor or self.actor)

    def create_darknet_research(self, *, case_id: str, query: str, source_ids: list[str], human_approved: bool, actor: str | None = None, max_requests: int = 25) -> dict[str, Any]:
        if not human_approved:
            raise PermissionError("Explicit human approval is required before a darknet search capsule can be created")
        capsule = self.capsules.create_darknet_capsule(case_id=case_id, source_ids=source_ids, actor=actor or self.actor, max_requests=max_requests)
        task = self.build344.create_darknet_research_task(case_id=case_id, query=query, source_ids=source_ids, human_approved=True, actor=actor or self.actor, search_run_id=capsule["search_run_id"])
        self.db.execute("UPDATE phase15_search_runs SET task_id=? WHERE search_run_id=?", (task["task_id"], capsule["search_run_id"]))
        self.db.execute("UPDATE phase15_search_capsules SET task_id=? WHERE search_run_id=?", (task["task_id"], capsule["search_run_id"]))
        return {"capsule": capsule, "task": task, "network_execution": False}

    def preflight_request(self, search_run_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.capsules.preflight_request(search_run_id, **kwargs)

    def close_capsule(self, search_run_id: str, *, actor: str | None = None) -> dict[str, Any]:
        return self.capsules.close_capsule(search_run_id, actor=actor or self.actor)

    def list_capsules(self, *, case_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self.capsules.list_capsules(case_id=case_id, limit=limit)

    def decisions(self, search_run_id: str) -> list[dict[str, Any]]:
        return self.capsules.decisions(search_run_id)

    def architecture_status(self) -> dict[str, Any]:
        src = (self._root / "src/eagleeye/security/search_capsule.py").read_text(encoding="utf-8")
        forbidden_imports = [name for name in ("subprocess", "socket", "requests", "httpx", "urllib.request") if re.search(rf"(^|\n)\s*(?:from\s+{re.escape(name)}\b|import\s+{re.escape(name)}\b)", src)]
        profiles = self.db.all("SELECT profile_id,profile_kind,runtime_execution_enabled,system_mutation_allowed,review_status FROM phase15_network_profiles ORDER BY profile_id")
        return {
            "policy_version": POLICY_VERSION,
            "capsule_module_network_imports": forbidden_imports,
            "system_mutation_calls_present": any(x in src for x in ("subprocess.", "os.system(", "Popen(", "socket.socket(")),
            "profiles": profiles,
            "runtime_network_execution": False,
            "per_request_preflight_required": True,
            "per_search_key": True,
            "separate_cookie_cache_browser_state": True,
        }

    @staticmethod
    def _maturity(states: dict[str, bool]) -> str:
        last = "declared"
        for key in DIMENSIONS:
            if states[key]:
                last = key
            else:
                break
        return last

    def capabilities(self) -> list[dict[str, Any]]:
        m = self.schema_metrics(); v = self.version_status(); arch = self.architecture_status(); bench = self._benchmark(); fp = self.code_fingerprint()
        specs = [
            ("schema_baseline_v1_345", "Schema Baseline v1 retained under capsule expansion", "schema", m["within_gate"], m["within_gate"], "schema", False),
            ("search_session_capsule_v1", "Per-search Search Session Capsule v1", "opsec", True, True, "capsule", bool(bench)),
            ("request_opsec_preflight_v1", "Fail-closed OPSEC decision before every external request descriptor", "opsec", True, True, "preflight", bool(bench)),
            ("encrypted_redacted_capsule_logs_v1", "Per-capsule encrypted and redacted security logs", "opsec", True, True, "encrypted_logs", bool(bench)),
            ("darknet_capsule_v1", "Reviewed Onion sources bound to isolated Tor policy capsules", "darknet", True, True, "darknet", bool(bench)),
            ("no_autonomous_network_mutation_345", "No autonomous proxy/Tor/firewall/OS mutation", "opsec", not arch["system_mutation_calls_present"] and not arch["capsule_module_network_imports"], not arch["system_mutation_calls_present"] and not arch["capsule_module_network_imports"], "boundary", bool(bench)),
            ("canonical_versioning_345", "Canonical Build 345 version contract", "packaging", v["coherent"], v["coherent"], "version", False),
            ("opsec_intelligence_v2", "OPSEC Intelligence v2 runtime leakage intelligence", "opsec", False, False, "future", False),
            ("live_search_gateway", "Live external Search/Crawler gateway", "network", False, False, "future", False),
            ("postgres_team_backend", "PostgreSQL team backend", "infrastructure", False, False, "future", False),
        ]
        rows = []
        for key, name, category, implemented, integrated, probe, benchmarkable in specs:
            tested = bool(integrated and self._probe(probe))
            states = {"implemented": bool(implemented), "integrated": bool(implemented and integrated), "tested": tested, "benchmarked": bool(tested and benchmarkable), "externally_validated": False}
            rows.append({"capability_key": key, "display_name": name, "category": category, **states, "maturity": self._maturity(states), "required_for_build": key in {"schema_baseline_v1_345", "search_session_capsule_v1", "request_opsec_preflight_v1", "encrypted_redacted_capsule_logs_v1", "darknet_capsule_v1", "no_autonomous_network_mutation_345", "canonical_versioning_345"}, "required_for_production": key not in {"schema_baseline_v1_345"}, "code_fingerprint": fp})
        return rows

    def qualified_gate(self) -> dict[str, Any]:
        rows = self.capabilities()
        required = [r for r in rows if r["required_for_build"]]
        build_tested = bool(required) and all(r["tested"] for r in required)
        capsule_benchmarked = any(r["capability_key"] == "search_session_capsule_v1" and r["benchmarked"] for r in rows)
        production = [r for r in rows if r["required_for_production"]]
        production_ready = bool(production) and all(r["externally_validated"] for r in production)
        return {
            "build": self.BUILD,
            "phase": "15",
            "gate_authority": "build345_search_capsule_evidence_gate",
            "build_acceptance_ready": build_tested and capsule_benchmarked,
            "production_release_ready": production_ready,
            "release_ready": production_ready,
            "baseline_tested": build_tested,
            "capsule_boundary_benchmarked": capsule_benchmarked,
            "active_gate_literal_true_lines": self.active_gate_literal_true_lines(),
            "rule": "A request descriptor may proceed only after its own persisted capsule preflight. Build 345 opens no network connection and never mutates proxy, Tor, firewall, OS, or credentials.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "phase": "15",
            "name": "Search Session Capsule + Darknet Research Hardening",
            "gate": self.qualified_gate(),
            "version": self.version_status(),
            "schema": self.schema_metrics(),
            "architecture": self.architecture_status(),
            "capabilities": self.capabilities(),
            "capsule_count": len(self.list_capsules(limit=500)),
            "runtime_network_execution": False,
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str, section: str = "cockpit") -> str:
        if section not in {"cockpit", "sources", "operations", "expert"}:
            return ""
        capsules = self.list_capsules(case_id=case_id, limit=20)
        rows = "".join(f"<tr><td><code>{html.escape(c['search_run_id'])}</code></td><td>{html.escape(c['search_kind'])}</td><td>{html.escape(c['capsule_state'])}</td><td>{html.escape(c['network_profile_ref'])}</td></tr>" for c in capsules) or "<tr><td colspan='4'>Noch keine Search Capsules.</td></tr>"
        return (
            "<section class='card'><h2>Build 345 · Search Session Capsules</h2>"
            "<p>Jede externe Recherche wird in einen eigenen Workspace mit eigenem Schlüssel, getrenntem HTTP-/Browserzustand, Egress-Allowlist und Request-Preflight gebunden.</p>"
            "<p><b>Netzwerkausführung:</b> in Build 345 weiterhin deaktiviert. Freigegebene Requests sind nur Gateway-Anforderungen.</p>"
            f"<table><thead><tr><th>Run</th><th>Typ</th><th>Status</th><th>Profil</th></tr></thead><tbody>{rows}</tbody></table>"
            "</section>"
        )
