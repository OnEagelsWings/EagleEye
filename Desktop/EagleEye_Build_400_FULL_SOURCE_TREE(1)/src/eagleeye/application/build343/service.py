from __future__ import annotations

import ast
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from eagleeye.application.kernel.use_cases import InvestigationKernelUseCases
from eagleeye.kernel.contracts import CONTRACT_VERSION

DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Build343ModularKernelService:
    """Phase-15 Build 343 composition and truthful status layer.

    The build-independent kernel lives under eagleeye.kernel and
    eagleeye.application.kernel. This Build service composes those ports with the
    temporary Build-343 repository and keeps legacy Build-340 UI compatibility.
    It does not inherit a historical build service.
    """

    BUILD = "343.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        use_cases: InvestigationKernelUseCases,
        repository: Any,
        build342: Any,
        build340: Any,
        install_dir: str | Path,
        base_dir: str | Path,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.use_cases = use_cases
        self.repository = repository
        self.build342 = build342
        self.build340 = build340
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._root = self.install_dir

    # ---------- evidence binding ----------
    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/kernel/__init__.py",
            "src/eagleeye/kernel/contracts.py",
            "src/eagleeye/kernel/ports.py",
            "src/eagleeye/kernel/policy.py",
            "src/eagleeye/kernel/dispatcher.py",
            "src/eagleeye/application/kernel/use_cases.py",
            "src/eagleeye/application/build343/service.py",
            "src/eagleeye/infrastructure/build343/schema.py",
            "src/eagleeye/infrastructure/build343/repository.py",
            "src/eagleeye/interfaces/web/build343_routes.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/app.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "EAGLEEYE_PRO_343_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_343_0.py",
            "START_EAGLEEYE_PRO.bat",
            "START_EAGLEEYE_PRO_343_0.bat",
            "START_EAGLEEYE_PRO.sh",
            "tools/build_release_343.py",
            "tools/generate_sbom_343.py",
            "tests/test_build343.py",
            ".github/workflows/build343.yml",
            "RELEASE_PROFILE_BUILD_343_0.json",
            "DARKNET_RESEARCH_ROADMAP_BUILD_342_TO_360.md",
        )

    def code_fingerprint(self) -> str:
        digest = hashlib.sha256()
        for rel in self._fingerprint_paths():
            path = self._root / rel
            digest.update(rel.encode("utf-8")); digest.update(b"\0")
            digest.update(path.read_bytes() if path.is_file() else b"<missing>"); digest.update(b"\0")
        return digest.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        data = _read_json(self._root / "BUILD_343_TEST_EVIDENCE.json")
        if data.get("build") != self.BUILD or data.get("result") != "pass" or data.get("code_fingerprint") != self.code_fingerprint():
            return {}
        return data if isinstance(data.get("probes"), dict) else {}

    def _probe_passed(self, probe: str) -> bool:
        return self._test_evidence().get("probes", {}).get(probe) == "pass"

    def _benchmark_evidence(self) -> dict[str, Any]:
        data = _read_json(self._root / "BENCHMARK_BUILD_343_KERNEL_BOUNDARY.json")
        if data.get("build") != self.BUILD or data.get("result") != "pass" or data.get("code_fingerprint") != self.code_fingerprint():
            return {}
        if int(data.get("cases", 0)) < 100 or int(data.get("boundary_violations", -1)) != 0:
            return {}
        return data

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=str(Path(__file__)))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({int(child.lineno) for child in ast.walk(node) if isinstance(child, ast.Constant) and child.value is True and hasattr(child, "lineno")})
        return []

    # ---------- architecture truth ----------
    def version_status(self) -> dict[str, Any]:
        version_text = (self._root / "eagleeye_pro/version.py").read_text(encoding="utf-8", errors="replace")
        project_text = (self._root / "pyproject.toml").read_text(encoding="utf-8", errors="replace")
        runtime = re.search(r'^BUILD\s*=\s*["\']([^"\']+)', version_text, re.MULTILINE)
        schema = re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', version_text, re.MULTILINE)
        package = re.search(r'^version\s*=\s*["\']([^"\']+)', project_text, re.MULTILINE)
        runtime_v = runtime.group(1) if runtime else "unknown"; schema_v = schema.group(1) if schema else "unknown"; package_v = package.group(1) if package else "unknown"
        normalized = runtime_v if runtime_v.count(".") >= 2 else runtime_v + ".0"
        win = (self._root / "START_EAGLEEYE_PRO.bat").read_text(encoding="utf-8", errors="replace") if (self._root / "START_EAGLEEYE_PRO.bat").is_file() else ""
        posix = (self._root / "START_EAGLEEYE_PRO.sh").read_text(encoding="utf-8", errors="replace") if (self._root / "START_EAGLEEYE_PRO.sh").is_file() else ""
        return {"runtime_build": runtime_v, "schema_version": schema_v, "package_version": package_v,
                "coherent": normalized == package_v and runtime_v == schema_v == self.BUILD,
                "windows_launcher_current": "EAGLEEYE_PRO_343_0.py" in win, "posix_launcher_current": "EAGLEEYE_PRO_343_0.py" in posix}

    def kernel_architecture_status(self) -> dict[str, Any]:
        core = [
            self._root / "src/eagleeye/kernel/contracts.py", self._root / "src/eagleeye/kernel/ports.py",
            self._root / "src/eagleeye/kernel/policy.py", self._root / "src/eagleeye/kernel/dispatcher.py",
            self._root / "src/eagleeye/application/kernel/use_cases.py",
        ]
        forbidden_roots = {"subprocess", "socket", "sqlite3", "requests", "httpx", "aiohttp", "urllib3", "playwright", "selenium"}
        forbidden_imports: list[str] = []
        build_imports: list[str] = []
        db_handle_refs: list[str] = []
        for path in core:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    names = []
                for name in names:
                    root = name.split(".")[0]
                    if root in forbidden_roots: forbidden_imports.append(f"{path.name}:{getattr(node,'lineno',0)}:{name}")
                    if re.search(r"(^|\.)build\d+($|\.)", name): build_imports.append(f"{path.name}:{getattr(node,'lineno',0)}:{name}")
            text = path.read_text(encoding="utf-8")
            if re.search(r"\bself\.db\b|\bsqlite3\b", text): db_handle_refs.append(path.name)
        repository_text = (self._root / "src/eagleeye/infrastructure/build343/repository.py").read_text(encoding="utf-8")
        route_text = (self._root / "src/eagleeye/interfaces/web/build343_routes.py").read_text(encoding="utf-8")
        app_text = (self._root / "src/eagleeye/interfaces/web/app.py").read_text(encoding="utf-8")
        return {
            "contract_version": CONTRACT_VERSION,
            "kernel_core_build_independent": not build_imports,
            "kernel_core_forbidden_io_imports": forbidden_imports,
            "kernel_core_direct_db_refs": db_handle_refs,
            "repository_isolated": "self.db" in repository_text and not db_handle_refs,
            "dedicated_router": "mount_build343_routes" in route_text and "mount_build343_routes(app" in app_text,
            "workspace_current": app_text.count("ctx.build343.render_workspace_panel") >= 8,
            "build_service_inheritance": "composition_only",
        }

    def runtime_manifest_status(self) -> dict[str, Any]:
        data = _read_json(self._root / "RUNTIME_MANIFEST_BUILD_343_0.json"); files = data.get("files", [])
        failures: list[str] = []
        if data.get("build") != self.BUILD or not isinstance(files, list) or not files: failures.append("manifest_shape"); files = []
        for item in files:
            rel = str(item.get("path", "")); expected = str(item.get("sha256", "")); target = self._root / rel
            if not rel or not target.is_file() or _file_sha(target) != expected: failures.append(rel or "missing_path")
        return {"valid": not failures, "file_count": len(files), "failures": failures[:20]}

    def sbom_status(self) -> dict[str, Any]:
        data = _read_json(self._root / "SBOM_BUILD_343_0.cdx.json"); components = data.get("components", [])
        valid = data.get("bomFormat") == "CycloneDX" and str(data.get("specVersion")) in {"1.5","1.6"} and isinstance(components, list) and len(components) >= 10
        return {"valid": valid, "component_count": len(components) if isinstance(components,list) else 0}

    # ---------- use cases ----------
    def create_local_analysis_task(self, *, case_id: str, objective: str, context_refs: list[str] | None = None, actor: str | None = None) -> dict[str, Any]:
        return self.use_cases.submit_local_analysis(case_id=case_id, actor=actor or self.actor, objective=objective, context_refs=context_refs)

    def create_darknet_research_task(self, *, case_id: str, query: str, source_ids: list[str], human_approved: bool, actor: str | None = None, search_run_id: str | None = None) -> dict[str, Any]:
        # Build-342 remains only a compatibility source-governance adapter. The kernel never imports it.
        plan = self.build342.create_darknet_research_plan(case_id=case_id, query=query, source_ids=source_ids)
        task = self.use_cases.submit_darknet_research(case_id=case_id, actor=actor or self.actor, query=query,
            source_ids=source_ids, source_plan_id=plan["plan_id"], human_approved=human_approved, search_run_id=search_run_id)
        return task | {"source_plan_hash": plan["plan_hash"], "network_execution": False}

    def evaluate_task(self, task_id: str) -> dict[str, Any]:
        return self.use_cases.evaluate(task_id)

    def dispatch_task(self, task_id: str) -> dict[str, Any]:
        return self.use_cases.dispatch(task_id)

    def tasks(self, *, case_id: str | None = None, limit: int = 100) -> list[dict]:
        return self.repository.list_tasks(case_id=case_id, limit=limit)

    # ---------- capability truth ----------
    @staticmethod
    def _maturity(states: dict[str, bool]) -> str:
        last = "declared"
        for key in DIMENSIONS:
            if states[key]: last = key
            else: break
        return last

    def _capability_specs(self) -> list[dict[str, Any]]:
        arch = self.kernel_architecture_status(); version = self.version_status(); benchmark = self._benchmark_evidence()
        kernel_clean = arch["kernel_core_build_independent"] and not arch["kernel_core_forbidden_io_imports"] and not arch["kernel_core_direct_db_refs"]
        return [
            {"key":"agent_contract_v1_343","name":"Versioned Agent Task/Result Contract v1","category":"kernel","implemented":CONTRACT_VERSION=="phase15.agent-task-result.v1","integrated":True,"probe":"contract","baseline":True,"production":True,"benchmark":bool(benchmark),"limits":["contract stability beyond v1 remains future compatibility work"]},
            {"key":"modular_kernel_boundary_343","name":"Build-independent Modular Investigation Kernel","category":"kernel","implemented":kernel_clean,"integrated":kernel_clean,"probe":"kernel_boundary","baseline":True,"production":True,"benchmark":bool(benchmark),"limits":["legacy feature services still exist outside the new kernel until later migration"]},
            {"key":"kernel_repository_port_343","name":"Kernel Repository Port + Immutable Audit Persistence","category":"kernel","implemented":arch["repository_isolated"],"integrated":arch["repository_isolated"],"probe":"repository","baseline":True,"production":True,"benchmark":False,"limits":["temporary Build-343 tables migrate into Schema Baseline v1 in Build 344"]},
            {"key":"dedicated_phase15_router_343","name":"Dedicated Phase-15 Router Slice","category":"web","implemented":arch["dedicated_router"],"integrated":arch["workspace_current"],"probe":"router","baseline":True,"production":True,"benchmark":False,"limits":["the remaining legacy web monolith is split incrementally after this first slice"]},
            {"key":"darknet_task_delegation_343","name":"Darknet Research as Controlled Agent Task","category":"darknet","implemented":True,"integrated":True,"probe":"darknet_task","baseline":True,"production":True,"benchmark":bool(benchmark),"limits":["runtime darknet gateway intentionally deferred until Search Session Capsule and OPSEC runtime gates"]},
            {"key":"canonical_versioning_343","name":"Canonical 343 Version/Launch Contract","category":"packaging","implemented":version["coherent"],"integrated":version["windows_launcher_current"] and version["posix_launcher_current"],"probe":"version","baseline":True,"production":True,"benchmark":False,"limits":[]},
            {"key":"search_session_capsule","name":"Per-search Search Session Capsule","category":"opsec","implemented":False,"integrated":False,"probe":"future","baseline":False,"production":True,"benchmark":False,"limits":["target Build 345"]},
            {"key":"opsec_intelligence_v2","name":"OPSEC Intelligence v2 Runtime Gate","category":"opsec","implemented":False,"integrated":False,"probe":"future","baseline":False,"production":True,"benchmark":False,"limits":["target Build 346"]},
            {"key":"darknet_runtime_gateway","name":"Runtime Darknet Search Gateway","category":"darknet","implemented":False,"integrated":False,"probe":"future","baseline":False,"production":True,"benchmark":False,"limits":["Build 343 persists/delegates tasks but deliberately cannot execute Tor/browser/network requests"]},
        ]

    def capabilities(self) -> list[dict[str, Any]]:
        rows=[]; fingerprint=self.code_fingerprint()
        for spec in self._capability_specs():
            implemented=bool(spec["implemented"]); integrated=implemented and bool(spec["integrated"]); tested=integrated and self._probe_passed(spec["probe"]); benchmarked=tested and bool(spec["benchmark"]); externally_validated=False
            states={"implemented":implemented,"integrated":integrated,"tested":tested,"benchmarked":benchmarked,"externally_validated":externally_validated}
            rows.append({"capability_key":spec["key"],"display_name":spec["name"],"category":spec["category"],**states,"maturity":self._maturity(states),"required_for_baseline":bool(spec["baseline"]),"required_for_production":bool(spec["production"]),"limitations":spec["limits"],"code_fingerprint":fingerprint})
        return rows

    def qualified_gate(self) -> dict[str, Any]:
        rows=self.capabilities(); baseline=[r for r in rows if r["required_for_baseline"]]; production=[r for r in rows if r["required_for_production"]]
        baseline_tested=bool(baseline) and all(r["tested"] for r in baseline)
        benchmarked=any(r["capability_key"]=="modular_kernel_boundary_343" and r["benchmarked"] for r in rows)
        build_acceptance=baseline_tested and benchmarked
        production_ready=bool(production) and all(r["externally_validated"] for r in production)
        return {"build":self.BUILD,"phase":"15","gate_authority":"build343_modular_kernel_evidence_gate","build_acceptance_ready":build_acceptance,
                "production_release_ready":production_ready,"release_ready":production_ready,"baseline_tested":baseline_tested,"kernel_boundary_benchmarked":benchmarked,
                "active_gate_literal_true_lines":self.active_gate_literal_true_lines(),
                "rule":"Models receive contracts only; repository and side-effect gateways remain outside the agent boundary. Internal validation never creates external validation."}

    def dashboard(self) -> dict[str, Any]:
        return {"build":self.BUILD,"phase":"15","name":"Modular Investigation Kernel + Darknet Agent Delegation","gate":self.qualified_gate(),
                "version":self.version_status(),"architecture":self.kernel_architecture_status(),"capabilities":self.capabilities(),"task_count":len(self.tasks(limit=500)),
                "darknet_runtime_execution":False,"contract_version":CONTRACT_VERSION}

    def _panel(self) -> str:
        gate=self.qualified_gate(); arch=self.kernel_architecture_status()
        return ('<section class="card" id="phase15-build343"><h2>Phase 15 · Build 343 · Modular Investigation Kernel</h2>'
                f'<p><b>Build-Abnahme:</b> {"bereit" if gate["build_acceptance_ready"] else "unvollständig"} · <b>Produktionsfreigabe:</b> {"extern validiert" if gate["production_release_ready"] else "nicht qualifiziert"}</p>'
                '<p>KI-Agenten erhalten ab diesem Kernel nur versionierte Task/Result-Contracts. DB, Browser, Tor, Shell und Netzwerk sind keine Agent-Objekte und können nur über explizite Gateways angebunden werden.</p>'
                f'<p><small>Contract: <code>{html.escape(str(arch["contract_version"]))}</code> · Darknet Runtime: <b>deferred</b> bis Search Session Capsule/OPSEC Gate.</small></p>'
                '<p><small>Maschinenlesbar: <code>/api/build343</code></small></p></section>')

    def render_workspace_panel(self, *, case_id: str, csrf: str, section: str) -> str:
        legacy=self.build340.render_workspace_panel(case_id=case_id, csrf=csrf, section=section)
        if section in {"cockpit","sources","operations","expert"}: return self._panel()+legacy
        return legacy
