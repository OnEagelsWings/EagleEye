from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import hashlib
import json
import re

from eagleeye_pro.version import BUILD, BUILD_NAME

FORBIDDEN_RELEASE_PATTERNS = [
    "data/*.db", "data/*.sqlite", "data/*.sqlite3", "data/*.db-wal", "data/*.db-shm",
    "logs/*", "reports/*", "*.err", "*.log", ".env", "*.pem", "*.key", "*.crt",
    ".DS_Store", "Thumbs.db", "STARTUP_DIAGNOSTICS_BUILD_44_0*", "TEST_OUTPUT_BUILD_44_0*",
]

REQUIRED_MODULES = [
    "eagleeye_pro/evidence_vault/service.py", "eagleeye_pro/verification_pro/service.py",
    "eagleeye_pro/spearhead_profile/service.py", "eagleeye_pro/emergency/service.py",
    "eagleeye_pro/jewish_life/service.py", "eagleeye_pro/provider_sdk/service.py",
    "eagleeye_pro/precision_ranking/service.py", "eagleeye_pro/link_analysis/service.py",
    "eagleeye_pro/handover/service.py", "eagleeye_pro/case_cockpit/service.py",
    "eagleeye_pro/search_chain/service.py", "eagleeye_pro/secure_storage/service.py",
    "eagleeye_pro/audit_hash_chain/service.py", "eagleeye_pro/analyst_quality/service.py",
    "eagleeye_pro/collaboration/service.py", "eagleeye_pro/one_page_output/service.py",
    "eagleeye_pro/privacy_finish/service.py", "eagleeye_pro/stable_release/service.py",
    "eagleeye_pro/phase_a_final_62_3/service.py", "eagleeye_pro/phase_b_final_62_5/service.py",
    "eagleeye_pro/security/url_policy.py", "eagleeye_pro/security/redaction_policy.py",
    "eagleeye_pro/security/export_policy.py", "eagleeye_pro/evidence_chain_64/service.py",
    "eagleeye_pro/quality_control_65/service.py", "eagleeye_pro/spearhead_architecture_66/service.py",
    "eagleeye_pro/source_adapter_architecture_67/service.py", "eagleeye_pro/graph_workspace_68/service.py",
    "eagleeye_pro/capture_vault_69/service.py", "eagleeye_pro/analyst_cockpit_70/service.py",
    "eagleeye_pro/analyst_workspace_ui_71/service.py", "eagleeye_pro/workspace_actions_72/service.py",
    "eagleeye_pro/persistent_case_db_73/service.py", "eagleeye_pro/real_capture_engine_74/service.py",
    "eagleeye_pro/local_evidence_vault_75/service.py", "eagleeye_pro/graph_ui_76/service.py",
    "eagleeye_pro/pivot_engine_77/service.py", "eagleeye_pro/identity_resolution_v3_78/service.py",
    "eagleeye_pro/counter_evidence_79/service.py", "eagleeye_pro/claim_engine_v3_80/service.py",
    "eagleeye_pro/search_adapter_81/service.py", "eagleeye_pro/web_archive_adapter_82/service.py",
    "eagleeye_pro/rdap_dns_intel_83/service.py", "eagleeye_pro/public_code_profile_84/service.py",
    "eagleeye_pro/public_document_intel_85/service.py", "eagleeye_pro/case_dashboard_v2_86/service.py",
    "eagleeye_pro/investigation_timeline_87/service.py", "eagleeye_pro/review_board_v2_88/service.py",
    "eagleeye_pro/report_builder_pro_89/service.py", "eagleeye_pro/casefile_pro_90/service.py",
    "eagleeye_pro/copy_paste_intake_91/service.py", "eagleeye_pro/gdpr_compliance_91/service.py",
    "eagleeye_pro/ethical_guardrails_92/service.py", "eagleeye_pro/analyst_training_93/service.py",
    "eagleeye_pro/team_workflow_94/service.py", "eagleeye_pro/enterprise_deployment_95/service.py",
    "eagleeye_pro/advanced_graph_analytics_96/service.py", "eagleeye_pro/ai_assisted_analyst_97/service.py",
    "eagleeye_pro/source_reliability_98/service.py", "eagleeye_pro/authority_ready_99/service.py",
    "eagleeye_pro/security_complex_100/service.py", "eagleeye_pro/local_ai_agent_101/service.py",
    "eagleeye_pro/browser_capture_bridge_102/service.py", "eagleeye_pro/interactive_graph_workspace_103/service.py",
    "eagleeye_pro/platform_consolidation_103_1/service.py", "EAGLEEYE_PRO_103_1.py",
    "START_EAGLEEYE_PRO_103_1.bat", "eagleeye_pro/source_adapter_execution_104/service.py",
    "EAGLEEYE_PRO_104_0.py", "START_EAGLEEYE_PRO_104_0.bat", "RUN_TESTS_BUILD_104_0.bat",
    "eagleeye_pro/core_recomposition_104_1/models.py", "eagleeye_pro/core_recomposition_104_1/orm.py",
    "eagleeye_pro/core_recomposition_104_1/repository.py", "eagleeye_pro/core_recomposition_104_1/connectors.py",
    "eagleeye_pro/core_recomposition_104_1/events.py", "eagleeye_pro/core_recomposition_104_1/service.py",
    "eagleeye_pro/core_recomposition_104_1/api.py", "alembic_104_1/env.py",
    "alembic_104_1/versions/1041_core_recomposition.py", "EAGLEEYE_PRO_104_1.py",
    "START_EAGLEEYE_PRO_104_1.bat", "RUN_TESTS_BUILD_104_1.bat", "EAGLEEYE_RELEASE_GATE_104_1.py",
    "README_BUILD_104_1.md", "QA_REPORT_BUILD_104_1.md", "DEPRECATION_MAP_BUILD_104_1.json", "pyproject.toml",
    "docs/BUILD_104_1_CORE_RECOMPOSITION.md", "eagleeye_pro/version.py",
    "eagleeye_pro/collection_engine_105/models.py", "eagleeye_pro/collection_engine_105/policy.py",
    "eagleeye_pro/collection_engine_105/orm.py", "eagleeye_pro/collection_engine_105/repository.py",
    "eagleeye_pro/collection_engine_105/scrapy_runner.py", "eagleeye_pro/collection_engine_105/playwright_runner.py",
    "eagleeye_pro/collection_engine_105/service.py", "eagleeye_pro/collection_engine_105/api.py",
    "alembic_104_1/versions/1050_collection_engine.py", "EAGLEEYE_COLLECTION_WORKER_105.py",
    "EAGLEEYE_PRO_105_0.py", "START_EAGLEEYE_PRO_105_0.bat", "INSTALL_COLLECTION_ENGINE_105.bat",
    "RUN_TESTS_BUILD_105_0.bat", "README_BUILD_105_0.md", "QA_REPORT_BUILD_105_0.md",
    "docs/BUILD_105_COLLECTION_ENGINE.md",
]


class ReleaseGate:
    """Current release validator for Build 105.0 collection engine."""
    def __init__(self, audit=None): self.audit = audit
    def _sha256_file(self, path: Path) -> str:
        h=hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
        return h.hexdigest()

    def run_checks(self, root_dir: str | Path | None=None, create_manifest: bool=True) -> Dict[str,Any]:
        root=Path(root_dir or Path(__file__).resolve().parents[2]).resolve(); checks=[]
        def add(name,ok,details=None): checks.append({"name":name,"status":"pass" if ok else "fail","details":details})
        add("root_exists",root.exists(),str(root))
        py_files=list((root/"eagleeye_pro").rglob("*.py")) if (root/"eagleeye_pro").exists() else []
        add("python_files_present",bool(py_files),len(py_files))
        missing=[m for m in REQUIRED_MODULES if not (root/m).exists()]
        add("build50_required_modules_present",not [m for m in REQUIRED_MODULES[:9] if not (root/m).exists()],missing[:9])
        add("build54_required_modules_present",not missing,missing)
        add("build103_1_required_modules_present",not [m for m in missing if "source_adapter_execution_104" not in m and "104_0" not in m],missing)
        add("build104_0_required_modules_present",not [m for m in missing if "104_1" not in m and "alembic_104_1" not in m],missing)
        add("build104_1_required_modules_present",not [m for m in missing if "collection_engine_105" not in m and "1050_collection" not in m and "105_0" not in m and "COLLECTION_WORKER_105" not in m],missing)
        add("build105_0_required_modules_present",not missing,missing)
        try:
            import pydantic, sqlalchemy, alembic, fastapi, uvicorn  # noqa: F401
            dependency_details = {"pydantic": pydantic.__version__, "sqlalchemy": sqlalchemy.__version__, "alembic": alembic.__version__, "fastapi": fastapi.__version__, "uvicorn": uvicorn.__version__}
            optional = {}
            for name in ("scrapy", "playwright", "tldextract"):
                try:
                    module = __import__(name)
                    optional[name] = getattr(module, "__version__", "installed")
                except Exception:
                    optional[name] = "not_installed_optional_collection_extra"
            dependency_details["optional_collection"] = optional
            add("build105_0_runtime_dependencies", True, dependency_details)
        except Exception as exc:
            add("build105_0_runtime_dependencies", False, str(exc))
        runtime=[]
        for pattern in FORBIDDEN_RELEASE_PATTERNS: runtime.extend(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
        add("no_runtime_artifacts",not runtime,runtime[:30])
        cache=[str(p.relative_to(root)) for p in root.rglob("*") if p.name=="__pycache__" or p.suffix in {".pyc",".pyo"} or ".pytest_cache" in p.parts]
        add("no_python_cache_artifacts",not cache if create_manifest else True,cache[:30])
        secret=[]; rx=re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{20,}['\"]")
        for p in py_files:
            if rx.search(p.read_text(encoding="utf-8",errors="ignore")): secret.append(str(p.relative_to(root)))
        add("no_literal_secrets",not secret,secret)
        metadata_files = [root/"eagleeye_pro/version.py", root/"eagleeye_pro/main.py", root/"eagleeye_pro/startup.py", root/"eagleeye_pro/core/database.py"]
        metadata_text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in metadata_files if p.exists())
        stale=[]
        if re.search(r'(?m)^BUILD\s*=\s*["\']62\.3["\']', metadata_text): stale.append('BUILD=62.3')
        if re.search(r'(?m)^SCHEMA_VERSION\s*=\s*["\']54\.0["\']', metadata_text): stale.append('SCHEMA_VERSION=54.0')
        add("current_build_metadata",not stale,stale)
        manifest_path=root/f"RELEASE_MANIFEST_BUILD_{BUILD.replace('.','_')}.json"
        if create_manifest:
            files=[]
            for p in sorted(root.rglob("*")):
                if not p.is_file() or p==manifest_path: continue
                rel=p.relative_to(root)
                if any(x in {".git","__pycache__",".pytest_cache"} for x in rel.parts) or p.suffix in {".pyc",".pyo"}: continue
                files.append({"path":str(rel).replace("\\","/"),"sha256":self._sha256_file(p),"size":p.stat().st_size})
            manifest={"build":BUILD,"name":BUILD_NAME,"schema_version":BUILD,"files":files,"checks":checks}
            manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
            add("manifest_created",manifest_path.exists(),str(manifest_path))
        status="pass" if all(c["status"]=="pass" for c in checks) else "fail"
        result={"status":status,"build":BUILD,"checks":checks,"manifest_path":str(manifest_path) if create_manifest else ""}
        if self.audit: self.audit.log("release_gate","release",BUILD,None,result)
        return result
