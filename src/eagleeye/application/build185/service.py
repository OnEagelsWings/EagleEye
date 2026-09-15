from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts
from eagleeye_pro.version import BUILD as CURRENT_BUILD


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class Build185OperationalRedTeamService:
    """Operational red-team, workflow-conformance and legacy-route audit.

    The service is intentionally non-destructive: it reports findings and gates a
    release candidate, but never rewrites evidence or activates sources itself.
    """

    BUILD = "185.5"
    WORKFLOW_STAGES = (
        ("01_intake", "Person und Auftrag", "Person, bekannte Merkmale, Zweck und Rechtsgrundlage erfassen."),
        ("02_plan", "Rechercheplan", "Suchziele und zulässige Quellen auswählen."),
        ("03_collect", "Öffentliche Recherche", "Treffer als Kandidaten erfassen; keine ungeprüfte Übernahme."),
        ("04_review", "Prüfen und verifizieren", "Quellen, Identität, Widersprüche sowie Fake-/Deepfake-Signale prüfen."),
        ("05_analyze", "Zusammenhänge", "Timeline, Graph und Hypothesen quellengebunden auswerten."),
        ("06_casefile", "Fallakte", "Nur freigegebene Erkenntnisse, Quellen und Einschränkungen exportieren."),
    )
    SOURCE_PROFILES = (
        {"source_id":"owasp_asvs","title":"OWASP Application Security Verification Standard","category":"application_security","access_mode":"official_standard","base_url":"https://owasp.org","constraints":["version_pinned","controls_mapped"]},
        {"source_id":"owasp_samm","title":"OWASP Software Assurance Maturity Model","category":"secure_development","access_mode":"official_standard","base_url":"https://owaspsamm.org","constraints":["maturity_context_required"]},
        {"source_id":"nist_ssdf","title":"NIST Secure Software Development Framework","category":"secure_development","access_mode":"official_standard","base_url":"https://csrc.nist.gov","constraints":["practice_mapping_required"]},
        {"source_id":"mitre_atlas","title":"MITRE ATLAS","category":"ai_red_team","access_mode":"official_knowledge_base","base_url":"https://atlas.mitre.org","constraints":["threat_model_not_case_fact"]},
        {"source_id":"eu_ai_act_reference","title":"EU AI Act official reference","category":"ai_governance","access_mode":"official_legal_reference","base_url":"https://eur-lex.europa.eu","constraints":["legal_review_required"]},
        {"source_id":"bsi_secure_software","title":"BSI sichere Softwareentwicklung","category":"application_security","access_mode":"official_guidance","base_url":"https://www.bsi.bund.de","constraints":["current_guidance_review"]},
    )

    def __init__(self, db: Any, audit: Any, *, project_root: str | Path, actor: str = "system"):
        self.db = db
        self.audit = audit
        candidate = Path(project_root).resolve()
        packaged_root = Path(__file__).resolve().parents[4]
        self.project_root = candidate if (candidate / "eagleeye_pro").exists() else packaged_root
        self.actor = actor

    def seed_sources(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "RED TEAM SOURCES 185 ERWEITERN":
            raise PermissionError("explicit source approval required")
        for item in self.SOURCE_PROFILES:
            payload = {**item, "status":"DOCUMENTED", "production_active":False}
            self.db.execute(
                "INSERT OR REPLACE INTO redteam_source_profiles_185 VALUES(?,?,?,?,?,?,?,?,?)",
                (item["source_id"], item["title"], item["category"], item["access_mode"], item["base_url"], dumps(item["constraints"]), "DOCUMENTED", now_ts(), _hash(payload)),
            )
        return {"created":len(self.SOURCE_PROFILES), "production_active":0, "review_required":True}

    def workflow_blueprint(self) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "single_canonical_workflow": True,
            "stages":[{"stage_id":sid,"title":title,"purpose":purpose,"required":True} for sid,title,purpose in self.WORKFLOW_STAGES],
            "rules":[
                "one_case_one_primary_person_record",
                "all_findings_start_as_candidates",
                "source_and_capture_required_before_evidence",
                "verification_before_casefile",
                "no_automatic_identity_or_fake_verdict",
                "no_legacy_ui_fallback",
            ],
        }

    def case_progress(self, case_id: str) -> dict[str, Any]:
        def count(table: str, where: str = "case_id=?") -> int:
            try:
                row = self.db.one(f"SELECT COUNT(*) n FROM {table} WHERE {where}", (case_id,))
                return int(row["n"] if row else 0)
            except Exception:
                return 0
        signals = {
            "01_intake": int(bool(self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)))),
            "02_plan": count("search_tasks", "case_id=?") + count("monitor_profiles_178", "case_id=?"),
            "03_collect": count("review_items", "case_id=?") + count("monitor_observations_178", "case_id=?"),
            "04_review": count("evidence_items", "case_id=?") + count("workspace_reviews_181", "case_id=?"),
            "05_analyze": count("graph_analysis_runs_177", "case_id=?") + count("pattern_findings_179", "case_id=?"),
            "06_casefile": count("reports", "case_id=?") + count("federation_packages_182", "case_id=?"),
        }
        stages=[]
        blocked=False
        for sid,title,purpose in self.WORKFLOW_STAGES:
            complete=signals[sid] > 0
            state="complete" if complete else ("blocked" if blocked else "next")
            if not complete: blocked=True
            stages.append({"stage_id":sid,"title":title,"purpose":purpose,"state":state,"signal_count":signals[sid]})
        next_stage=next((x for x in stages if x["state"]=="next"), None)
        return {"case_id":case_id,"stages":stages,"next_stage":next_stage,"completion_percent":round(sum(x["state"]=="complete" for x in stages)/len(stages)*100)}

    def static_audit(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "RED TEAM 185 CODE AUDIT":
            raise PermissionError("explicit code audit required")
        py_files=[p for p in self.project_root.rglob("*.py") if not any(x in p.parts for x in {".venv","__pycache__","site-packages"})]
        findings=[]; lines=0; syntax_errors=0
        rules=(
            ("bare_except", re.compile(r"^\s*except\s*:\s*$"), "medium"),
            ("shell_true", re.compile(r"shell\s*=\s*True"), "high"),
            ("unsafe_eval", re.compile(r"\b(eval|exec)\s*\("), "high"),
            ("hardcoded_secret", re.compile(r"(?i)(api[_-]?key|password|secret)\s*=\s*['\"][^'\"]{8,}"), "high"),
            ("automatic_ui_fallback", re.compile(r"Opening Safe Mode UI|run_pilot_desktop\(base_dir=base, startup_error=tb\)"), "high"),
        )
        for path in py_files:
            try:
                text=path.read_text(encoding="utf-8", errors="replace"); lines += text.count("\n")+1
                try: ast.parse(text)
                except SyntaxError as exc:
                    syntax_errors += 1; findings.append({"rule":"syntax_error","severity":"critical","file":str(path.relative_to(self.project_root)),"line":exc.lineno,"message":str(exc)})
                rel = str(path.relative_to(self.project_root))
                for no,line in enumerate(text.splitlines(),1):
                    for rule,pattern,severity in rules:
                        if rel == "src/eagleeye/application/build185/service.py" and rule == "automatic_ui_fallback":
                            continue
                        if rel.startswith("tests/") and rule in {"hardcoded_secret", "automatic_ui_fallback"}:
                            continue
                        if pattern.search(line): findings.append({"rule":rule,"severity":severity,"file":rel,"line":no,"excerpt":line.strip()[:240]})
            except OSError as exc:
                findings.append({"rule":"unreadable_file","severity":"medium","file":str(path),"message":str(exc)})
        build_suffix = CURRENT_BUILD.replace(".", "_")
        current_python = self.project_root / f"EAGLEEYE_PRO_{build_suffix}.py"
        current_windows = self.project_root / f"START_EAGLEEYE_PRO_{build_suffix}.bat"
        # Maintenance contract: historical launchers are archival compatibility artifacts,
        # not a release blocker. Only the current canonical launchers must exist and agree.
        if not current_python.is_file():
            findings.append({"rule":"current_python_launcher_missing","severity":"high","file":current_python.name})
        if not current_windows.is_file():
            findings.append({"rule":"current_windows_launcher_missing","severity":"high","file":current_windows.name})
        severity_counts={s:sum(1 for f in findings if f.get("severity")==s) for s in ("critical","high","medium","low")}
        status="blocked" if severity_counts["critical"] or severity_counts["high"] else "candidate_pass"
        run_id=new_id("red185"); payload={"run_id":run_id,"files":len(py_files),"lines":lines,"syntax_errors":syntax_errors,"findings":findings,"severity_counts":severity_counts,"status":status,"automatic_release":False}
        self.db.execute("INSERT INTO redteam_runs_185 VALUES(?,?,?,?,?,?,?,?,?)",(run_id,"static_code_audit",status,len(py_files),lines,dumps(severity_counts),dumps(findings),now_ts(),_hash(payload)))
        return payload

    def workflow_audit(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "RED TEAM 185 WORKFLOW AUDIT":
            raise PermissionError("explicit workflow audit required")
        build_suffix = CURRENT_BUILD.replace(".", "_")
        launcher = self.project_root / f"EAGLEEYE_PRO_{build_suffix}.py"
        win_launcher = self.project_root / f"START_EAGLEEYE_PRO_{build_suffix}.bat"
        general_launcher = self.project_root / "START_EAGLEEYE_PRO.bat"
        launcher_text = launcher.read_text(encoding="utf-8", errors="replace") if launcher.is_file() else ""
        win_text = win_launcher.read_text(encoding="utf-8", errors="replace") if win_launcher.is_file() else ""
        general_text = general_launcher.read_text(encoding="utf-8", errors="replace") if general_launcher.is_file() else ""
        checks = {
            "current_build_launcher": launcher.is_file(),
            "browser_workspace_only": ("--serve" in launcher_text and "--browser" in launcher_text and "firefox" in launcher_text and "--desktop" not in launcher_text),
            "automatic_runtime_setup": bool(launcher.name in win_text and "python" in win_text.casefold()),
            "general_launcher_matches": bool(win_launcher.is_file() and (win_launcher.name in general_text or general_text.strip() == win_text.strip())),
            "no_automatic_legacy_ui_fallback": "--desktop" not in launcher_text and "--safe-mode" not in launcher_text,
            "single_current_python_launcher": len(list(self.project_root.glob(f"EAGLEEYE_PRO_{build_suffix}.py"))) == 1,
            "single_current_windows_launcher": len(list(self.project_root.glob(f"START_EAGLEEYE_PRO_{build_suffix}.bat"))) == 1,
            "historical_launchers_allowed": True,
        }
        status = "candidate_pass" if all(checks.values()) else "blocked"
        return {"status": status, "checks": checks, "beginner_usable": all(checks.values()), "automatic_release": False, "human_review_required": True}
