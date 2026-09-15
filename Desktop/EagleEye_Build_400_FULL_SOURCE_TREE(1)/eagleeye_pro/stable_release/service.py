from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import ast
import hashlib
import json
import re

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, new_id, now_ts, dumps, loads


class StableReleaseService:
    """Build 62.5 stable audit layer.

    Provides deterministic static checks for packaging, UI duplication markers,
    risky Python constructs and required Build 55 modules. This does not replace
    pytest or compileall; it records a stable-release audit inside the case DB.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS stable_release_audits_55 (
          audit_id TEXT PRIMARY KEY,
          root_dir TEXT NOT NULL,
          decision TEXT NOT NULL,
          checks_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def run_static_audit(self, root_dir: str | Path | None = None) -> Dict[str, Any]:
        root = Path(root_dir or Path(__file__).resolve().parents[2]).resolve()
        checks: List[Dict[str, Any]] = []
        def add(name: str, ok: bool, details: Any = None):
            checks.append({"name": name, "status": "pass" if ok else "fail", "details": details})

        py_files = list((root / "eagleeye_pro").rglob("*.py")) if (root / "eagleeye_pro").exists() else []
        add("root_exists", root.exists(), str(root))
        add("python_files_present", bool(py_files), len(py_files))
        required = [
            "eagleeye_pro/privacy_finish/service.py",
            "eagleeye_pro/stable_release/service.py",
            "eagleeye_pro/one_page_output/service.py",
            "eagleeye_pro/search_chain/service.py",
            "eagleeye_pro/case_cockpit/service.py",
            "eagleeye_pro/categorized_search/service.py",
            "eagleeye_pro/person_detail/service.py",
            "eagleeye_pro/search_quality/service.py",
            "eagleeye_pro/result_capture/service.py",
            "eagleeye_pro/entity_resolution/service.py",
            "eagleeye_pro/query_optimizer/service.py",
            "eagleeye_pro/claim_builder/service.py",
            "eagleeye_pro/research_stable/service.py",
            "eagleeye_pro/person_workspace/service.py",
            "eagleeye_pro/source_intelligence_pro/service.py",
            "eagleeye_pro/deep_research_session/service.py",
            "eagleeye_pro/research_benchmark/service.py",
            "eagleeye_pro/document_intelligence/service.py",
            "eagleeye_pro/register_archive_intelligence/service.py",
            "eagleeye_pro/professional_operations/service.py",
            "eagleeye_pro/search_spearhead/service.py",
            "eagleeye_pro/osint_search_core/service.py",
            "eagleeye_pro/provider_connectors_60/service.py",
            "eagleeye_pro/browser_capture_60/service.py",
            "eagleeye_pro/osint_evaluation_lab_60/service.py",
            "eagleeye_pro/professional_osint_60/service.py",
            "eagleeye_pro/capture_pro/service.py",
            "eagleeye_pro/fund_intelligence/service.py",
            "eagleeye_pro/entity_resolution_hardening/service.py",
            "eagleeye_pro/person_dashboard/service.py",
            "eagleeye_pro/osint_calibration_lab/service.py",
            "eagleeye_pro/operational_research_stable/service.py",
            "eagleeye_pro/osint_performance_tuning/service.py",
            "eagleeye_pro/ux_polish/service.py",
            "eagleeye_pro/browser_helper_62/service.py",
            "eagleeye_pro/claim_report_62/service.py",
            "eagleeye_pro/osint_benchmark_suite_62/service.py",
            "eagleeye_pro/adaptive_tuning_62/service.py",
            "eagleeye_pro/professional_research_62/service.py",
            "eagleeye_pro/phase_a_final_62_3/service.py",
            "eagleeye_pro/phase_b_final_62_5/service.py",
        ]
        missing = [p for p in required if not (root / p).exists()]
        add("build55_required_modules_present", not missing, missing)

        risk = self._scan_python_risks(py_files)
        add("no_eval_exec_os_system_pickle_shell_true", not any(risk.values()), risk)
        runtime_artifacts = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and p.suffix in {".db", ".log", ".err"}]
        add("no_runtime_data_artifacts", not runtime_artifacts, runtime_artifacts[:50])
        cache_artifacts = [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and (p.suffix == ".pyc" or "__pycache__" in p.parts or ".pytest_cache" in p.parts)]
        add("python_cache_cleanup_hint", True, cache_artifacts[:50])

        ui = root / "eagleeye_pro" / "ui" / "desktop.py"
        ui_text = ui.read_text(encoding="utf-8", errors="ignore") if ui.exists() else ""
        active_mounts = re.findall(r"self\._tab_[a-zA-Z0-9_]+\(\)", ui_text[ui_text.find("def _build") : ui_text.find("def _tab_verification") if "def _tab_verification" in ui_text else len(ui_text)])
        add("only_consolidated_ui_tabs_mounted", active_mounts == ["self._tab_one_page_intake()", "self._tab_person_detail_page()", "self._tab_quality_engine()", "self._tab_spearhead_engine()", "self._tab_one_page_outputs()"], active_mounts)
        add("no_duplicate_visible_case_intake_labels", ui_text.count("0 Intake: Fall + Person/Org") == 1, ui_text.count("0 Intake: Fall + Person/Org"))
        add("person_detail_tab_present", "1 Personenakte" in ui_text, "1 Personenakte" in ui_text)
        add("output_tab_present", "3 Profil / Bericht / Fallakte" in ui_text, "3 Profil / Bericht / Fallakte" in ui_text)

        release_refs = []
        for p in py_files:
            if p.name == "release_gate.py":
                continue
            txt = p.read_text(encoding="utf-8", errors="ignore")
            old_gate = "BUILD_44_0" + "_SELFTEST_PASS"
            old_db = "eagleeye_pro_54" + "_8.db"
            if old_gate in txt or old_db in txt:
                release_refs.append(str(p.relative_to(root)))
        add("no_old_gate_or_runtime_marker", not release_refs, release_refs)

        decision = "pass" if all(c["status"] == "pass" for c in checks) else "fail"
        audit_id = new_id("stable55")
        self.db.execute("INSERT INTO stable_release_audits_55(audit_id,root_dir,decision,checks_json,created_at) VALUES(?,?,?,?,?)", [audit_id, str(root), decision, dumps(checks), now_ts()])
        self.audit.log("stable_release_audit", "build62_0", audit_id, None, {"decision": decision, "checks": len(checks)})
        return {"audit_id": audit_id, "decision": decision, "checks": checks}

    def latest_audits(self, limit: int = 10) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM stable_release_audits_55 ORDER BY created_at DESC LIMIT ?", [int(limit)])
        for r in rows:
            r["checks"] = loads(r.pop("checks_json", "[]"), [])
        return rows

    def _scan_python_risks(self, py_files: List[Path]) -> Dict[str, int]:
        counts = {"eval_calls": 0, "exec_calls": 0, "os_system": 0, "subprocess_shell_true": 0, "pickle_loads": 0}
        for path in py_files:
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                counts["exec_calls"] += 1
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "eval":
                        counts["eval_calls"] += 1
                    if isinstance(func, ast.Name) and func.id == "exec":
                        counts["exec_calls"] += 1
                    if isinstance(func, ast.Attribute):
                        name = f"{getattr(func.value, 'id', '')}.{func.attr}" if isinstance(func.value, ast.Name) else func.attr
                        if name == "os.system":
                            counts["os_system"] += 1
                        if name in {"pickle.load", "pickle.loads"}:
                            counts["pickle_loads"] += 1
                        if func.attr in {"run", "Popen", "call", "check_call", "check_output"}:
                            for kw in node.keywords:
                                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                    counts["subprocess_shell_true"] += 1
        return counts
