from __future__ import annotations

import importlib
import json
import platform
import sys
import traceback
from datetime import datetime
from pathlib import Path

from eagleeye_pro.version import BUILD, BUILD_NAME


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def log_dir(base_dir: str | Path | None = None) -> Path:
    base = Path(base_dir) if base_dir else project_root()
    path = base / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_startup_log(message: str, base_dir: str | Path | None = None) -> Path:
    directory = log_dir(base_dir)
    latest = directory / "startup_latest.log"
    timestamped = directory / f"startup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    payload = f"{BUILD_NAME}\n{datetime.now().isoformat()}\n\n{message}\n"
    latest.write_text(payload, encoding="utf-8")
    timestamped.write_text(payload, encoding="utf-8")
    return latest


def diagnose(base_dir: str | Path | None = None) -> dict:
    base = Path(base_dir) if base_dir else project_root()
    checks: list[dict] = []

    def check(name: str, operation):
        try:
            checks.append({"name": name, "status": "pass", "value": operation()})
        except Exception as exc:  # diagnostics must continue after individual failures
            checks.append({"name": name, "status": "fail", "error": repr(exc), "traceback": traceback.format_exc()})

    check("python_version", lambda: sys.version)
    check("platform", platform.platform)
    check("project_root", lambda: str(project_root()))
    check("base_dir", lambda: str(base))
    check("service_registry_import", lambda: importlib.import_module("eagleeye.bootstrap.registry").ServiceRegistry.__name__)
    check("app_context_import", lambda: importlib.import_module("eagleeye_pro.core.app_context").AppContext.__name__)

    def database_check():
        from eagleeye_pro.core.app_context import AppContext

        ctx = AppContext(base_dir=base)
        try:
            schema = ctx.db.one("SELECT value FROM meta WHERE key='schema_version'")
            integrity = ctx.db.one("PRAGMA integrity_check")
            providers = ctx.provider_collection_120.list_providers()
            return {
                "db_path": str(ctx.db.path),
                "schema_version": schema,
                "integrity": integrity,
                "provider_framework": {
                    "registered_providers": len(providers),
                    "provider_keys": [item["provider_key"] for item in providers],
                },
                "workspace": {"registered": ctx.service_registry.is_registered("investigation_workspace_122"), "initialized": ctx.service_registry.is_initialized("investigation_workspace_122"), "connected_flow_registered": ctx.service_registry.is_registered("investigation_flow_1222"), "connected_flow_initialized": ctx.service_registry.is_initialized("investigation_flow_1222"), "scale_performance_123_registered": ctx.service_registry.is_registered("scale_performance_123"), "scale_performance_123_initialized": ctx.service_registry.is_initialized("scale_performance_123"), "investigator_protection_124_registered": ctx.service_registry.is_registered("investigator_protection_124"), "investigator_protection_124_initialized": ctx.service_registry.is_initialized("investigator_protection_124"), "reliability_quality_125_registered": ctx.service_registry.is_registered("reliability_quality_125"), "reliability_quality_125_initialized": ctx.service_registry.is_initialized("reliability_quality_125"), "production_candidate_126_registered": ctx.service_registry.is_registered("production_candidate_126"), "production_candidate_126_initialized": ctx.service_registry.is_initialized("production_candidate_126"), "intelligence_orchestrator_127_registered": ctx.service_registry.is_registered("intelligence_orchestrator_127"), "intelligence_orchestrator_127_initialized": ctx.service_registry.is_initialized("intelligence_orchestrator_127"), "research_strategy_128_registered": ctx.service_registry.is_registered("research_strategy_128"), "research_strategy_128_initialized": ctx.service_registry.is_initialized("research_strategy_128"), "capture_identity_129_registered": ctx.service_registry.is_registered("capture_identity_129"), "capture_identity_129_initialized": ctx.service_registry.is_initialized("capture_identity_129"), "graph_hypothesis_130_registered": ctx.service_registry.is_registered("graph_hypothesis_130"), "graph_hypothesis_130_initialized": ctx.service_registry.is_initialized("graph_hypothesis_130"), "investigative_synthesis_131_registered": ctx.service_registry.is_registered("investigative_synthesis_131"), "investigative_synthesis_131_initialized": ctx.service_registry.is_initialized("investigative_synthesis_131"), "collaboration_governance_132_registered": ctx.service_registry.is_registered("collaboration_governance_132"), "collaboration_governance_132_initialized": ctx.service_registry.is_initialized("collaboration_governance_132"), "phase3_production_candidate_133_registered": ctx.service_registry.is_registered("phase3_production_candidate_133"), "phase3_production_candidate_133_initialized": ctx.service_registry.is_initialized("phase3_production_candidate_133"), "phase4_operations_134_registered": ctx.service_registry.is_registered("phase4_operations_134"), "phase4_operations_134_initialized": ctx.service_registry.is_initialized("phase4_operations_134"), "build135_registered": ctx.service_registry.is_registered("build135"), "build135_initialized": ctx.service_registry.is_initialized("build135"), "build136_registered": ctx.service_registry.is_registered("build136"), "build136_initialized": ctx.service_registry.is_initialized("build136"), "build137_registered": ctx.service_registry.is_registered("build137"), "build137_initialized": ctx.service_registry.is_initialized("build137"), "build138_registered": ctx.service_registry.is_registered("build138"), "build138_initialized": ctx.service_registry.is_initialized("build138"), "build139_registered": ctx.service_registry.is_registered("build139"), "build139_initialized": ctx.service_registry.is_initialized("build139"), "build140_registered": ctx.service_registry.is_registered("build140"), "build140_initialized": ctx.service_registry.is_initialized("build140"), "build141_registered": ctx.service_registry.is_registered("build141"), "build141_initialized": ctx.service_registry.is_initialized("build141"), "build142_registered": ctx.service_registry.is_registered("build142"), "build142_initialized": ctx.service_registry.is_initialized("build142"), "build143_registered": ctx.service_registry.is_registered("build143"), "build143_initialized": ctx.service_registry.is_initialized("build143"), "build144_registered": ctx.service_registry.is_registered("build144"), "build144_initialized": ctx.service_registry.is_initialized("build144"), "build145_registered": ctx.service_registry.is_registered("build145"), "build145_initialized": ctx.service_registry.is_initialized("build145")},
                "initialized_services": list(ctx.service_registry.initialized_names()),
            }
        finally:
            ctx.close()

    check("database_open", database_check)
    status = "pass" if all(item["status"] == "pass" for item in checks) else "fail"
    result = {"build": BUILD, "build_name": BUILD_NAME, "status": status, "checks": checks}
    (log_dir(base) / "startup_diagnostics_build_145_0.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_startup_log(json.dumps(result, ensure_ascii=False, indent=2), base)
    return result



def run_browser(base_dir: str | Path | None = None, *, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True, browser: str = "firefox") -> int:
    base = Path(base_dir) if base_dir else project_root()
    try:
        serve_workspace = importlib.import_module("eagleeye.interfaces.web.server").serve_workspace
        return int(serve_workspace(base_dir=base, host=host, port=port, open_browser=open_browser, browser=browser))
    except Exception:
        full_error = traceback.format_exc()
        write_startup_log("BROWSER WORKSPACE START FAILED\n\n" + full_error, base)
        raise

def run_gui(base_dir: str | Path | None = None, *, safe_mode: bool = False) -> int:
    base = Path(base_dir) if base_dir else project_root()
    try:
        if safe_mode:
            raise RuntimeError("Safe Mode requested")
        run_desktop = importlib.import_module("eagleeye.interfaces.desktop.app").run_desktop
        run_desktop(base_dir=base)
        return 0
    except Exception:
        full_error = traceback.format_exc()
        write_startup_log("FULL GUI START FAILED\n\n" + full_error, base)
        try:
            run_pilot_desktop = importlib.import_module("eagleeye.interfaces.desktop.safe_mode").run_pilot_desktop
            run_pilot_desktop(base_dir=base, startup_error=full_error)
            return 0
        except Exception:
            safe_error = traceback.format_exc()
            write_startup_log(
                "FULL GUI AND SAFE MODE FAILED\n\nFULL GUI ERROR:\n"
                + full_error
                + "\n\nSAFE MODE ERROR:\n"
                + safe_error,
                base,
            )
            return 2
