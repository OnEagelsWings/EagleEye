from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

from eagleeye_pro.core.database import dumps, new_id, now_ts
from eagleeye_pro.core.versioning import version_at_least
from eagleeye_pro.version import BUILD, SCHEMA_VERSION


class Phase3GateError(RuntimeError):
    pass


class Phase3ProductionCandidate133Service:
    """Feature-frozen Phase-3 production-candidate gate.

    This service adds no investigative reach. It verifies the complete Phase-3
    trust model, local OPSEC boundaries, release profile and operational
    readiness. External field validations remain explicit and never fabricated.
    """

    BUILD = BUILD
    REQUIRED_PHASE3 = {
        "intelligence_orchestrator_127",
        "research_strategy_128",
        "capture_identity_129",
        "graph_hypothesis_130",
        "investigative_synthesis_131",
        "collaboration_governance_132",
        "phase3_production_candidate_133",
    }
    FIELD_COMPONENTS = (
        "windows_launcher",
        "windows_shortcut",
        "firefox_workspace",
        "firefox_companion",
        "backup_restore",
        "live_connectors",
        "external_security_review",
    )

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        *,
        reliability: Any,
        protection: Any,
        registry_getter: Callable[[], Any],
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.reliability = reliability
        self.protection = protection
        self._registry_getter = registry_getter

    @staticmethod
    def _check(key: str, title: str, severity: str, ok: bool, details: Any = None, *, warning: bool = False) -> dict[str, Any]:
        return {
            "key": key,
            "title": title,
            "severity": severity,
            "status": "pass" if ok else ("warning" if warning else "fail"),
            "details": details or {},
        }

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    def _latest_field(self, component: str) -> dict[str, Any]:
        return self.db.one(
            "SELECT * FROM phase3_field_validations_133 WHERE component_key=? ORDER BY validated_at DESC LIMIT 1",
            (component,),
        ) or {}

    def source_release_profile(self) -> dict[str, Any]:
        historical = []
        current = []
        pattern = re.compile(r"(?:BUILD_|PRO_)(\d{2,3})(?:_|\.)", re.IGNORECASE)
        for path in sorted(self.base_dir.iterdir()) if self.base_dir.is_dir() else []:
            if not path.is_file():
                continue
            match = pattern.search(path.name)
            if match and match.group(1) not in {"150"}:
                historical.append(path.name)
            else:
                current.append(path.name)
        return {
            "profile": "production_slim",
            "historical_top_level_files": len(historical),
            "historical_examples": historical[:15],
            "current_top_level_files": len(current),
            "compatibility_package_retained": (self.base_dir / "eagleeye_pro").is_dir(),
        }

    def _launcher_contract(self) -> dict[str, Any]:
        generic = self.base_dir / "START_EAGLEEYE_PRO.bat"
        specific = self.base_dir / "START_EAGLEEYE_PRO_150_0.bat"
        python_entry = self.base_dir / "EAGLEEYE_PRO_150_0.py"
        ps1 = self.base_dir / "tools" / "windows" / "create_shortcut.ps1"
        vbs = self.base_dir / "tools" / "windows" / "create_shortcut.vbs"
        installer = self.base_dir / "INSTALL_EAGLEEYE_RUNTIME_150_0.bat"
        requirements = self.base_dir / "requirements-runtime.txt"
        acceptance = self.base_dir / "RUN_WINDOWS_ACCEPTANCE_150_0.bat"
        acceptance_ps1 = self.base_dir / "tools" / "windows" / "run_acceptance_150_0.ps1"
        firefox_probe = self.base_dir / "tools" / "windows" / "firefox_acceptance_probe_150.py"
        generic_text = generic.read_text(encoding="utf-8", errors="replace") if generic.is_file() else ""
        specific_text = specific.read_text(encoding="utf-8", errors="replace") if specific.is_file() else ""
        entry_text = python_entry.read_text(encoding="utf-8", errors="replace") if python_entry.is_file() else ""
        acceptance_text = acceptance_ps1.read_text(encoding="utf-8", errors="replace") if acceptance_ps1.is_file() else ""
        ok = (
            specific.name in generic_text
            and python_entry.name in specific_text
            and "PYTHONPATH" in specific_text
            and "--gui" in specific_text
            and 'sys.argv[1:] or ["--gui"]' in entry_text
            and installer.is_file()
            and requirements.is_file()
            and acceptance.is_file()
            and acceptance_ps1.is_file()
            and firefox_probe.is_file()
            and "$env:PYTHONPATH" in acceptance_text
            and "workspace_smoke_status" in acceptance_text
            and python_entry.is_file()
            and ps1.is_file()
            and vbs.is_file()
        )
        return {
            "ok": ok, "generic": generic.is_file(), "specific": specific.is_file(),
            "entry": python_entry.is_file(), "runtime_installer": installer.is_file(),
            "runtime_requirements": requirements.is_file(), "acceptance": acceptance.is_file(),
            "acceptance_sets_pythonpath": "$env:PYTHONPATH" in acceptance_text,
            "acceptance_workspace_smoke": "workspace_smoke_status" in acceptance_text,
            "acceptance_firefox_probe": firefox_probe.is_file() and "firefox_acceptance_probe_150.py" in acceptance_text,
            "default_gui": "--gui" in specific_text and 'sys.argv[1:] or ["--gui"]' in entry_text,
            "powershell": ps1.is_file(), "vbs_fallback": vbs.is_file(),
        }

    def _companion_contract(self) -> dict[str, Any]:
        root = self.base_dir / "tools" / "firefox_companion_136"
        manifest = root / "manifest.json"
        if not manifest.is_file():
            return {"ok": False, "reason": "manifest_missing"}
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"ok": False, "reason": type(exc).__name__}
        permissions = set(payload.get("permissions") or [])
        host_permissions = set(payload.get("host_permissions") or [])
        allowed_permissions = {
            "activeTab", "tabs", "storage", "<all_urls>",
            "http://127.0.0.1/*", "http://localhost/*",
            "http://127.0.0.1:8765/*", "http://localhost:8765/*",
        }
        allowed_hosts = {"http://127.0.0.1/*", "http://localhost/*", "http://127.0.0.1:8765/*", "http://localhost:8765/*"}
        content_scripts = payload.get("content_scripts") or []
        https_capture = any(
            isinstance(item, dict)
            and item.get("matches") == ["https://*/*"]
            and "capture_content.js" in (item.get("js") or [])
            for item in content_scripts
        )
        no_plain_http_capture = not any(
            isinstance(item, dict)
            and any(str(match).startswith("http://*") for match in (item.get("matches") or []))
            for item in content_scripts
        )
        capture_script = root / "capture_content.js"
        background_script = root / "background.js"
        capture_text = capture_script.read_text(encoding="utf-8", errors="replace") if capture_script.is_file() else ""
        background_text = background_script.read_text(encoding="utf-8", errors="replace") if background_script.is_file() else ""
        no_cookie_or_storage_read = all(token not in capture_text for token in ("document.cookie", "localStorage", "sessionStorage"))
        no_network_interception = all(token not in permissions for token in ("webRequest", "webRequestBlocking", "cookies"))
        bounded_capture_logic = all(token in background_text for token in ("allowed_hosts", "auto_approved", "/api/capture150/config", "/api/capture150/submit"))
        csp = str(payload.get("content_security_policy") or "")
        strict_csp = "script-src 'self'" in csp and "object-src 'none'" in csp
        ok = (
            permissions <= allowed_permissions
            and host_permissions <= allowed_hosts
            and https_capture
            and no_plain_http_capture
            and no_cookie_or_storage_read
            and no_network_interception
            and bounded_capture_logic
            and strict_csp
        )
        return {
            "ok": ok,
            "permissions": sorted(permissions),
            "host_permissions": sorted(host_permissions),
            "signed": False,
            "temporary_extension": True,
            "elevated_capture_permission": "<all_urls>" in permissions,
            "https_capture_only": https_capture and no_plain_http_capture,
            "cookie_or_storage_read": not no_cookie_or_storage_read,
            "network_interception_permissions": not no_network_interception,
            "server_bounded_capture": bounded_capture_logic,
            "strict_csp": strict_csp,
        }

    def record_field_validation(
        self,
        *,
        component_key: str,
        platform_key: str,
        status: str,
        actor: str,
        notes: str = "",
        evidence_fingerprint: str = "",
    ) -> dict[str, Any]:
        if component_key not in self.FIELD_COMPONENTS:
            raise ValueError("Unbekannte Feldabnahme-Komponente")
        if status not in {"pass", "fail", "not_run"}:
            raise ValueError("Ungültiger Feldabnahmestatus")
        clean_notes = str(notes or "")[:2000]
        fingerprint = str(evidence_fingerprint or "").strip().lower()
        if fingerprint and not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise ValueError("Evidence-Fingerprint muss SHA-256 sein")
        validation_id = new_id("field133")
        self.db.execute(
            """INSERT INTO phase3_field_validations_133(
                 validation_id,component_key,platform_key,status,evidence_fingerprint,notes,validated_by,validated_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (validation_id, component_key, str(platform_key or "unknown")[:100], status, fingerprint, clean_notes, actor, now_ts()),
        )
        self.db.execute(
            "INSERT INTO phase3_opsec_events_133(event_id,event_type,object_type,object_id,actor,details_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (new_id("opsec133"), "field_validation", "validation", validation_id, actor, dumps({"component": component_key, "platform": platform_key, "status": status, "notes_sha256": hashlib.sha256(clean_notes.encode()).hexdigest() if clean_notes else "", "raw_notes_in_audit": False}), now_ts()),
        )
        self.audit.log("field_validation", "phase3_release_133", validation_id, None, {"component": component_key, "platform": platform_key, "status": status, "raw_notes_in_audit": False})
        return self.db.one("SELECT * FROM phase3_field_validations_133 WHERE validation_id=?", (validation_id,)) or {}

    def create_ai_opsec_assessment(self, *, case_id: str | None, actor: str) -> dict[str, Any]:
        gate = self.run_gate(case_id=case_id, actor=actor, persist=False)
        failures = [item for item in gate["checks"] if item["status"] == "fail"]
        warnings = [item for item in gate["checks"] if item["status"] == "warning"]
        content = {
            "title": "Phase-3 AI/OPSEC Production Assessment",
            "trust_state": "suggestions_only",
            "external_actions": 0,
            "automatic_approvals": False,
            "automatic_fact_promotion": False,
            "gate_status": gate["status"],
            "priority_findings": [item["title"] for item in failures[:8]],
            "operational_warnings": [item["title"] for item in warnings[:12]],
            "recommendations": [
                "Führe reale Windows- und Firefox-Feldabnahmen aus und hinterlege nur SHA-256-Nachweise.",
                "Behalte externe AI-Aktionen auf null, bis Redaction-, Provider- und Reviewer-Gates unabhängig geprüft sind.",
                "Nutze ausschließlich das production_slim Release; historische Buildartefakte bleiben außerhalb des Produktpakets.",
                "Behandle Connectorantworten, Browserinhalte und AI-Ausgaben weiterhin als untrusted candidate data.",
            ],
        }
        raw = dumps(content)
        assessment_id = new_id("aiopsec133")
        self.db.execute(
            """INSERT INTO phase3_ai_opsec_assessments_133(
                 assessment_id,case_id,trust_state,review_status,external_actions,content_json,content_sha256,created_by,created_at)
               VALUES(?,?,'suggestions_only','pending',0,?,?,?,?)""",
            (assessment_id, case_id, raw, hashlib.sha256(raw.encode()).hexdigest(), actor, now_ts()),
        )
        self.audit.log("ai_opsec_assessment", "phase3_release_133", assessment_id, case_id, {"trust_state": "suggestions_only", "external_actions": 0, "content_sha256": hashlib.sha256(raw.encode()).hexdigest()})
        return self.db.one("SELECT * FROM phase3_ai_opsec_assessments_133 WHERE assessment_id=?", (assessment_id,)) or {}

    def run_gate(self, *, case_id: str | None = None, actor: str = "local-analyst", persist: bool = True) -> dict[str, Any]:
        if case_id and not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError("Fall nicht gefunden")
        checks: list[dict[str, Any]] = []
        schema = (self.db.one("SELECT value FROM meta WHERE key='schema_version'") or {}).get("value", "")
        checks.append(self._check("schema", "Schema mindestens 133.0", "critical", version_at_least(schema, "133.0") and version_at_least(SCHEMA_VERSION, "133.0"), {"observed": schema, "expected": SCHEMA_VERSION, "phase3_baseline": "133.0"}))
        quick = (self.db.one("PRAGMA quick_check") or {}).get("quick_check", "")
        checks.append(self._check("sqlite", "SQLite-Integrität", "critical", quick == "ok", {"quick_check": quick}))
        foreign = self.db.all("PRAGMA foreign_key_check")
        checks.append(self._check("foreign_keys", "Fremdschlüssel", "critical", not foreign, {"issues": len(foreign)}))

        registry = self._registry_getter()
        missing = sorted(name for name in self.REQUIRED_PHASE3 if not registry.is_registered(name))
        checks.append(self._check("phase3_services", "Alle Phase-3-Services registriert", "critical", not missing, {"missing": missing}))

        policy = self.db.one("SELECT * FROM phase3_release_policy_133 WHERE policy_id='phase3'") or {}
        checks.append(self._check("feature_freeze", "Phase-3 Feature Freeze", "critical", bool(policy.get("feature_freeze")), policy))
        checks.append(self._check("ai_policy", "AI bleibt suggestions-only und ohne externe Aktionen", "critical", policy.get("ai_trust_state") == "suggestions_only" and int(policy.get("max_external_ai_actions", -1)) == 0, {"trust_state": policy.get("ai_trust_state"), "max_external_actions": policy.get("max_external_ai_actions")}))

        phase2 = registry.get("production_candidate_126").run_gate(case_id=case_id, actor=actor)
        checks.append(self._check("phase2_baseline", "Phase-2-Basisgate bleibt blockerfrei", "critical", int(phase2.get("blocker_count") or 0) == 0, {"status": phase2.get("status"), "score": phase2.get("score"), "blockers": phase2.get("blocker_count")}))

        orch = self.db.one("SELECT * FROM orchestrator_policy_127 WHERE policy_id='default'") or {}
        checks.append(self._check("orchestrator", "Orchestrator ist approval- und review-first", "critical", orch.get("external_network_default") == "blocked" and orch.get("output_trust_state") == "suggestions_only" and int(orch.get("max_external_actions_hard", -1)) == 0 and bool(orch.get("require_plan_approval")) and bool(orch.get("require_output_review")), orch))

        registry.get("research_strategy_128")
        connectors = self.db.all("SELECT * FROM connector_catalog_128 WHERE enabled=1") if self._table_exists("connector_catalog_128") else []
        invalid_connectors = [row.get("connector_key") for row in connectors if not bool(row.get("public_only")) or row.get("network_policy") != "human_approved" or row.get("query_minimization") != "required"]
        checks.append(self._check("connector_contracts", "Connector-SDK ist public-only, minimiert und human-approved", "critical", len(connectors) >= 10 and not invalid_connectors, {"enabled": len(connectors), "invalid": invalid_connectors}))

        unsafe_ai = 0
        for table in ("orchestration_outputs_127", "research_ai_suggestions_128", "identity_ai_suggestions_129", "graph_ai_suggestions_130", "synthesis_ai_suggestions_131", "governance_ai_briefs_132"):
            if self._table_exists(table):
                unsafe_ai += int((self.db.one(f"SELECT COUNT(*) AS n FROM {table} WHERE trust_state!='suggestions_only'") or {}).get("n") or 0)
        checks.append(self._check("ai_output_trust", "Keine AI-Ausgabe außerhalb suggestions_only", "critical", unsafe_ai == 0, {"unsafe_outputs": unsafe_ai}))

        auto_merges = int((self.db.one("SELECT COUNT(*) AS n FROM identity_hypotheses_129 WHERE review_decision IN ('auto_merged','automatic_merge') OR reviewed_by='system-auto-merge'") or {}).get("n") or 0) if self._table_exists("identity_hypotheses_129") else 0
        checks.append(self._check("identity_no_auto_merge", "Keine automatische Identitätszusammenführung", "critical", auto_merges == 0, {"auto_merges": auto_merges}))

        governance = registry.get("collaboration_governance_132")
        gov = governance.settings()
        failed_approvals = int((self.db.one("SELECT COUNT(*) AS n FROM governance_approval_requests_132 WHERE execution_status='failed'") or {}).get("n") or 0)
        checks.append(self._check("governance", "Governance bleibt loopback-only und Vier-Augen", "critical", gov.get("remote_server_mode") == "disabled_loopback_only" and bool(gov.get("require_four_eyes")) and failed_approvals == 0, {"remote_server_mode": gov.get("remote_server_mode"), "four_eyes": bool(gov.get("require_four_eyes")), "failed_approvals": failed_approvals}))

        protection = self.protection.settings()
        checks.append(self._check("opsec", "Investigator Protection bleibt fail-closed", "critical", protection.get("protection_mode") in {"hardened", "proxy_required"} and bool(protection.get("block_external_provider_network")) and not bool(protection.get("allow_default_browser_fallback")), {"mode": protection.get("protection_mode"), "provider_network_blocked": bool(protection.get("block_external_provider_network")), "default_browser_fallback": bool(protection.get("allow_default_browser_fallback"))}))

        integrity = self.reliability.run_integrity_check(case_id=case_id, actor=actor)
        checks.append(self._check("reliability", "Reliability- und Recovery-Gate", "critical", integrity.get("status") == "pass", {"score": integrity.get("score"), "issues": integrity.get("issues", [])}))

        launcher = self._launcher_contract()
        portable_launcher_present = bool(launcher.get("generic") or launcher.get("specific") or launcher.get("entry"))
        launcher["install_mode"] = "portable" if portable_launcher_present else "wheel"
        checks.append(self._check(
            "windows_launcher", "Windows-Launcher- und Shortcutvertrag", "critical",
            bool(launcher.get("ok")), launcher, warning=not portable_launcher_present,
        ))
        companion = self._companion_contract()
        companion_present = companion.get("reason") != "manifest_missing"
        companion["install_mode"] = "portable" if companion_present else "wheel"
        checks.append(self._check(
            "firefox_companion", "Firefox-Companion besitzt gebundene und auditierte Capture-Rechte", "critical",
            bool(companion.get("ok")), companion, warning=not companion_present,
        ))

        profile = self.source_release_profile()
        checks.append(self._check("release_profile", "Production-Slim-Profil ohne historische Top-Level-Artefakte", "high", profile["historical_top_level_files"] == 0, profile, warning=True))

        for component in self.FIELD_COMPONENTS:
            latest = self._latest_field(component)
            passed = latest.get("status") == "pass"
            checks.append(self._check(f"field_{component}", f"Reale Feldabnahme: {component}", "high", passed, {"status": latest.get("status") or "not_run", "platform": latest.get("platform_key") or "", "validated_at": latest.get("validated_at") or ""}, warning=True))

        blocker_count = sum(1 for item in checks if item["status"] == "fail" and item["severity"] in {"critical", "high"})
        warning_count = sum(1 for item in checks if item["status"] == "warning")
        deductions = sum(20 if item["severity"] == "critical" else 10 if item["severity"] == "high" else 4 for item in checks if item["status"] == "fail") + warning_count
        score = max(0, 100 - deductions)
        status = "fail" if blocker_count else ("conditional" if warning_count else "pass")
        report = {"build": BUILD, "schema": SCHEMA_VERSION, "case_id": case_id or "", "status": status, "score": score, "checks": checks, "field_validations_required": True}
        if not persist:
            return {**report, "run_id": "", "blocker_count": blocker_count, "warning_count": warning_count}
        run_id = new_id("pc133")
        with self.db.transaction(immediate=True):
            self.db.execute(
                """INSERT INTO phase3_candidate_runs_133(
                     run_id,case_id,status,score,check_count,blocker_count,warning_count,report_json,created_by,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (run_id, case_id, status, score, len(checks), blocker_count, warning_count, dumps(report), actor, now_ts()),
            )
            for item in checks:
                self.db.execute(
                    "INSERT INTO phase3_candidate_checks_133(check_id,run_id,check_key,title,severity,status,details_json) VALUES(?,?,?,?,?,?,?)",
                    (new_id("pcc133"), run_id, item["key"], item["title"], item["severity"], item["status"], dumps(item["details"])),
                )
        self.audit.log("phase3_production_gate", "phase3_release_133", run_id, case_id, {"status": status, "score": score, "blockers": blocker_count, "warnings": warning_count})
        return {**report, "run_id": run_id, "blocker_count": blocker_count, "warning_count": warning_count}

    def prepare_freeze(self, *, case_id: str | None, actor: str, notes: str = "") -> dict[str, Any]:
        backup = self.reliability.create_backup(actor=actor, case_id=case_id, include_evidence=True)
        gate = self.run_gate(case_id=case_id, actor=actor)
        if gate["status"] == "fail":
            raise Phase3GateError("Phase-3-Freeze verweigert: Production Gate enthält Blocker")
        manifest = self.base_dir / "RELEASE_MANIFEST_BUILD_133_1.json"
        manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else ""
        freeze_id = new_id("freeze133")
        status = "frozen" if gate["status"] == "pass" else "candidate_conditional"
        self.db.execute(
            """INSERT INTO phase3_release_freezes_133(
                 freeze_id,case_id,gate_run_id,backup_id,manifest_sha256,release_profile,status,notes,created_by,created_at)
               VALUES(?,?,?,?,?,'production_slim',?,?,?,?)""",
            (freeze_id, case_id, gate["run_id"], backup["backup_id"], manifest_sha, status, str(notes or "")[:2000], actor, now_ts()),
        )
        self.audit.log("phase3_freeze", "phase3_release_133", freeze_id, case_id, {"gate_run_id": gate["run_id"], "backup_id": backup["backup_id"], "status": status, "manifest_sha256": manifest_sha})
        return self.db.one("SELECT * FROM phase3_release_freezes_133 WHERE freeze_id=?", (freeze_id,)) or {}

    def recent_runs(self, case_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if case_id:
            return self.db.all("SELECT * FROM phase3_candidate_runs_133 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, max(1, min(limit, 100))))
        return self.db.all("SELECT * FROM phase3_candidate_runs_133 ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 100)),))

    def recent_freezes(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM phase3_release_freezes_133 ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 100)),))

    def field_validations(self) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM phase3_field_validations_133 ORDER BY validated_at DESC LIMIT 100")
