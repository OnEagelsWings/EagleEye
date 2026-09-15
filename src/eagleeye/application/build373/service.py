from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Sequence

DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class Build373AnalystGraphUXService:
    BUILD = "373.0"
    PACKAGE = "373.0.0"
    POLICY = "phase16.analyst-graph-ux-build.v373"

    def __init__(self, db: Any, audit: Any, *, build372: Any, graph373: Any, navigation373: Any, ai373: Any, opsec373: Any, install_dir: Any, base_dir: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build372 = build372
        self.graph373 = graph373
        self.navigation373 = navigation373
        self.ai373 = ai373
        self.opsec373 = opsec373
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build372, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/phase16/analyst_graph373.py",
            "src/eagleeye/application/build373/service.py",
            "src/eagleeye/interfaces/web/app373.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "tests/test_build373.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_373_0.py",
            "tools/benchmark_build373.py",
            "tools/live_graph_validate_373.py",
            "tools/generate_build373_evidence.py",
            "CRAWLER_ROADMAP_BUILD_370_TO_380.md",
            "PHASE_16_MASTERPLAN_BUILD_361_TO_380.md",
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

    def _test_evidence(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "BUILD_373_TEST_EVIDENCE.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() else {}

    def _benchmark(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "BENCHMARK_BUILD_373_GRAPH_UX.json")
        return value if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint() and int(value.get("cases", 0)) >= 4200 and int(value.get("violations", -1)) == 0 else {}

    def _live_validation(self) -> dict[str, Any]:
        value = _read_json(self.install_dir / "LIVE_VALIDATION_BUILD_373_GRAPH_UX.json")
        return value if value.get("build") == self.BUILD and value.get("code_fingerprint") == self.code_fingerprint() else {}

    def _probe(self, key: str) -> bool:
        return self._test_evidence().get("probes", {}).get(key) == "pass"

    def schema_metrics(self) -> dict[str, Any]:
        rows = self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type")
        counts = {r["type"]: int(r["c"]) for r in rows}
        logical = int((self.db.one("SELECT page_count*page_size AS n FROM pragma_page_count(),pragma_page_size()") or {}).get("n") or 0)
        integrity = str((self.db.one("PRAGMA integrity_check") or {}).get("integrity_check") or "unknown")
        file_bytes = self.db.path.stat().st_size if self.db.path.exists() else 0
        out = {
            "table": counts.get("table", 0),
            "index": counts.get("index", 0),
            "trigger": counts.get("trigger", 0),
            "view": counts.get("view", 0),
            "logical_bytes": logical,
            "file_bytes": file_bytes,
            "integrity_check": integrity,
            "targets": {"tables_lt": 180, "indexes_lt": 300, "logical_bytes_lt": 5 * 1024 * 1024},
            "canonical_entity_ledger_activated": True,
            "graph_projection_new_tables": 0,
            "graph_navigation_new_tables": 0,
        }
        out["within_gate"] = out["table"] < 180 and out["index"] < 300 and logical < 5 * 1024 * 1024 and integrity == "ok"
        return out

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

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c, ast.Constant) and c.value is True and hasattr(c, "lineno")})
        return []

    def analyst_graph(self, *, case_id: str, identity: dict[str, Any], max_nodes: int = 180, max_edges: int = 360) -> dict[str, Any]:
        return self.graph373.snapshot(case_id=case_id, identity=identity, max_nodes=max_nodes, max_edges=max_edges)

    def analyst_graph_focus(self, *, case_id: str, node_id: str, identity: dict[str, Any], depth: int = 1, max_nodes: int = 60) -> dict[str, Any]:
        return self.graph373.focus(case_id=case_id, node_id=node_id, identity=identity, depth=depth, max_nodes=max_nodes)

    def graph_navigation_plan(self, *, case_id: str, root_entity_id: str, source_ids: Sequence[str], identity: dict[str, Any]) -> dict[str, Any]:
        return self.navigation373.plan(case_id=case_id, root_entity_id=root_entity_id, source_ids=source_ids, identity=identity)

    def graph_navigate(self, *, case_id: str, root_entity_id: str, source_ids: Sequence[str], identity: dict[str, Any], confirmation: str) -> dict[str, Any]:
        return self.navigation373.navigate(case_id=case_id, root_entity_id=root_entity_id, source_ids=source_ids, identity=identity, confirmation=confirmation)

    def graph_navigation_status(self, *, case_id: str) -> dict[str, Any]:
        return self.navigation373.case_status(case_id=case_id)

    def run_autonomous_investigation(self, **kw: Any) -> dict[str, Any]:
        return self.ai373.run_cycle(**kw)

    def autonomous_opsec_protect(self, **kw: Any) -> dict[str, Any]:
        return self.opsec373.protect_case(**kw)

    def protect_remote_session(self, **kw: Any) -> dict[str, Any]:
        return self.opsec373.protect_remote_session(**kw)

    def phase16_status(self) -> dict[str, Any]:
        base = dict(self.build372.phase16_status())
        base.update({
            "build": self.BUILD,
            "builds_completed": 13,
            "analyst_graph_ux": self.graph373.status(),
            "crawler_graph_navigation": self.navigation373.status(),
            "ai": self.ai373.status(),
            "opsec": self.opsec373.status(),
            "crawler_improvement_build": 373,
            "continuous_crawler_expansion_370_380": True,
        })
        return base

    def crawler_status(self) -> dict[str, Any]:
        base = dict(self.build372.crawler_status())
        base.update({
            "crawler_improvement_build": 373,
            "graph_aware_navigation": True,
            "analyst_selected_sources_only": True,
            "already_evidenced_sources_only": True,
            "explicit_navigation_confirmation": "NAVIGATE",
            "graph_navigation_source_health_gate": True,
            "graph_navigation_backpressure_gate": True,
            "graph_navigation_max_sources": 2,
            "graph_navigation_max_source_pages": 10,
            "graph_navigation_max_total_requests": 30,
            "automatic_graph_scope_expansion": False,
            "automatic_graph_source_discovery": False,
            "entity_lead_auto_merge": False,
            "continuous_crawler_expansion_370_380": True,
            "automatic_external_connections_on_boot": 0,
            "background_workers_started_on_boot": 0,
        })
        return base

    def capabilities(self) -> list[dict[str, Any]]:
        benchmarked = bool(self._benchmark())
        live = self._live_validation()
        local = live.get("local_graph_workflow_validation") == "pass"
        specs = [
            ("analyst_graph_projection_v373", "graph_projection"),
            ("review_state_graph_edges_v373", "review_edges"),
            ("crawler_provenance_graph_edges_v373", "crawler_edges"),
            ("offline_graph_focus_v373", "focus"),
            ("bounded_graph_navigation_plan_v373", "navigation_plan"),
            ("human_confirmed_graph_navigation_v373", "navigation_execute"),
            ("graph_navigation_opsec_v373", "opsec"),
            ("graph_aware_ai_context_v373", "ai"),
            ("local_graph_workflow_validation_v373", "local"),
        ]
        out: list[dict[str, Any]] = []
        for key, probe in specs:
            tested = local if probe == "local" else self._probe(probe)
            states = {"implemented": True, "integrated": True, "tested": tested, "benchmarked": benchmarked, "externally_validated": False}
            maturity = next((k for k in reversed(DIMENSIONS) if states[k]), "declared")
            out.append({"key": key, "states": states, "maturity": maturity})
        return out

    def qualified_gate(self) -> dict[str, Any]:
        schema = self.schema_metrics()
        version = self.version_status()
        live = self._live_validation()
        checks = {
            "schema_within_gate": schema["within_gate"],
            "version_coherent": version["coherent"],
            "test_evidence_current": bool(self._test_evidence()),
            "benchmark_4200_no_violations": bool(self._benchmark()),
            "local_graph_workflow_validation": live.get("local_graph_workflow_validation") == "pass",
            "graph_projection_tested": self._probe("graph_projection"),
            "review_edges_tested": self._probe("review_edges"),
            "crawler_edges_tested": self._probe("crawler_edges"),
            "focus_tested": self._probe("focus"),
            "navigation_plan_tested": self._probe("navigation_plan"),
            "navigation_execute_tested": self._probe("navigation_execute"),
            "opsec_tested": self._probe("opsec"),
            "ai_tested": self._probe("ai"),
            "no_literal_true_gate": self.active_gate_literal_true_lines() == [],
        }
        return {
            "build": self.BUILD,
            "checks": checks,
            "build_acceptance_ready": all(bool(v) for v in checks.values()),
            "external_graph_ux_validation": "not_run",
            "external_graph_navigation_validation": "not_run",
            "production_release_ready": False,
            "truthful_note": "Build 373 adds a case-scoped analyst graph projection and human-confirmed bounded graph pivots into already-evidenced approved crawler sources. Local qualification does not validate analyst usability in a professional pilot or authorize autonomous scope expansion.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "phase16": self.phase16_status(),
            "crawler": self.crawler_status(),
            "graph": self.graph373.status(),
            "navigation": self.navigation373.status(),
            "local_validation": self._live_validation(),
            "capabilities": self.capabilities(),
            "gate": self.qualified_gate(),
        }
