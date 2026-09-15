from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts
from eagleeye_pro.core.versioning import version_at_least
from eagleeye_pro.version import BUILD, SCHEMA_VERSION


class ProductionGateError(RuntimeError):
    pass


class ProductionCandidate126Service:
    """Phase-2 production-candidate gate and controlled desktop integration.

    The service adds no investigative reach. It freezes and verifies the existing
    workflow, records deliberate launches of external AI tools, and creates an
    optional Windows shortcut through a fixed, bundled PowerShell script.
    """

    CHATGPT_URL = "https://chatgpt.com/"

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        *,
        reliability: Any,
        protection: Any,
        registry_getter: Callable[[], Any],
        process_runner: Callable[..., Any] | None = None,
        platform_name: str | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.reliability = reliability
        self.protection = protection
        self._registry_getter = registry_getter
        self.process_runner = process_runner or subprocess.run
        self.platform_name = platform_name or os.name

    @staticmethod
    def _check(key: str, title: str, severity: str, ok: bool, details: Any = None, *, warning: bool = False) -> dict[str, Any]:
        status = "pass" if ok else ("warning" if warning else "fail")
        return {"key": key, "title": title, "severity": severity, "status": status, "details": details or {}}

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    def run_gate(self, *, case_id: str | None = None, actor: str = "local-analyst") -> dict[str, Any]:
        if case_id and not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError("Fall nicht gefunden")
        checks: list[dict[str, Any]] = []
        schema = (self.db.one("SELECT value FROM meta WHERE key='schema_version'") or {}).get("value", "")
        checks.append(self._check("schema", "Schema mindestens 126.0", "critical", version_at_least(schema, "126.0") and version_at_least(SCHEMA_VERSION, "126.0"), {"observed": schema, "expected": SCHEMA_VERSION, "phase2_baseline": "126.0"}))
        quick = (self.db.one("PRAGMA quick_check") or {}).get("quick_check", "")
        checks.append(self._check("sqlite", "SQLite-Integrität", "critical", quick == "ok", {"quick_check": quick}))
        foreign = self.db.all("PRAGMA foreign_key_check")
        checks.append(self._check("foreign_keys", "Fremdschlüssel", "critical", not foreign, {"issues": len(foreign)}))

        settings = self.protection.settings()
        checks.append(self._check("protection_mode", "Investigator Protection", "critical", settings.get("protection_mode") in {"hardened", "proxy_required"}, {"mode": settings.get("protection_mode")}))
        checks.append(self._check("provider_fail_closed", "Externe Provider fail-closed", "critical", bool(settings.get("block_external_provider_network")), {}))
        checks.append(self._check("browser_fallback", "Kein Rückfall auf persönliches Browserprofil", "critical", not bool(settings.get("allow_default_browser_fallback")), {}))
        checks.append(self._check("access_lock", "Lokale Passphrasensperre", "high", bool(settings.get("access_lock_enabled")), {"configured": bool(settings.get("passphrase_configured"))}, warning=True))

        integrity = self.reliability.run_integrity_check(case_id=case_id, actor=actor)
        checks.append(self._check("reliability", "Reliability Gate", "critical", integrity.get("status") == "pass", {"score": integrity.get("score"), "issues": integrity.get("issues", [])}))

        active_operations = int((self.db.one("SELECT COUNT(*) AS n FROM reliability_operations_125 WHERE state IN ('starting','running')") or {}).get("n") or 0)
        # The integrity operation used above has completed before this query.
        checks.append(self._check("active_operations", "Keine offenen Reliability-Operationen", "high", active_operations == 0, {"count": active_operations}))
        active_restore = int((self.db.one("SELECT COUNT(*) AS n FROM reliability_restore_stages_125 WHERE status='staged'") or {}).get("n") or 0)
        checks.append(self._check("restore_stages", "Keine offenen Restore-Stufen", "high", active_restore == 0, {"count": active_restore}, warning=True))
        unresolved_faults = int((self.db.one("SELECT COUNT(*) AS n FROM reliability_fault_events_125 WHERE resolved=0 AND severity IN ('critical','high')") or {}).get("n") or 0)
        checks.append(self._check("faults", "Keine ungelösten schweren Reliability-Befunde", "critical", unresolved_faults == 0, {"count": unresolved_faults}))

        if case_id:
            targets = int((self.db.one("SELECT COUNT(*) AS n FROM targets WHERE case_id=?", (case_id,)) or {}).get("n") or 0)
            tasks = int((self.db.one("SELECT COUNT(*) AS n FROM search_tasks WHERE case_id=?", (case_id,)) or {}).get("n") or 0)
            checks.append(self._check("case_subject", "Fall besitzt Person/Entität", "high", targets > 0, {"targets": targets}, warning=True))
            checks.append(self._check("case_research", "Recherchefluss ist initialisiert", "high", tasks > 0, {"tasks": tasks}, warning=True))
            packages = int((self.db.one("SELECT COUNT(*) AS n FROM evidence_packages_121 WHERE case_id=?", (case_id,)) or {}).get("n") or 0)
            if packages:
                checkpoint = self.protection.verify_evidence_checkpoints(case_id)
                checks.append(self._check("evidence_checkpoint", "Evidence-Trust-Chain", "critical", bool(checkpoint.get("valid")), checkpoint))
            else:
                checks.append(self._check("evidence_checkpoint", "Evidence-Trust-Chain", "medium", True, {"not_applicable": True, "packages": 0}))

        policy = self.db.one("SELECT * FROM production_policy_126 WHERE policy_id='phase2'") or {}
        checks.append(self._check("feature_freeze", "Phase-2 Feature Freeze", "high", bool(policy.get("feature_freeze")), policy))
        registry = self._registry_getter()
        required = {
            "investigation_workspace_122", "investigation_flow_1222", "scale_performance_123",
            "investigator_protection_124", "reliability_quality_125", "production_candidate_126",
        }
        if version_at_least(schema, "127.0"):
            required.add("intelligence_orchestrator_127")
            if version_at_least(schema, "128.0"):
                required.add("research_strategy_128")
            if version_at_least(schema, "129.0"):
                required.add("capture_identity_129")
            if version_at_least(schema, "130.0"):
                required.add("graph_hypothesis_130")
                status130 = self.db.one("SELECT COUNT(*) AS n FROM graph_analysis_runs_130") or {"n": 0}
                checks.append(self._check(
                    "phase3_graph_hypothesis",
                    "Graph- und Hypothesenschicht ist review-first",
                    "critical",
                    registry.is_registered("graph_hypothesis_130"),
                    {"registered": registry.is_registered("graph_hypothesis_130"), "analysis_runs": int(status130.get("n") or 0), "automatic_promotion": False},
                ))
                if version_at_least(schema, "131.0"):
                    required.add("investigative_synthesis_131")
                    synthesis_registered = registry.is_registered("investigative_synthesis_131")
                    checks.append(self._check(
                        "phase3_investigative_synthesis",
                        "Investigative Synthesis ist quellengebunden und review-first",
                        "critical",
                        synthesis_registered,
                        {"registered": synthesis_registered, "trust_state": "suggestions_only", "external_actions": 0, "automatic_export": False, "automatic_fact_promotion": False},
                    ))
                if version_at_least(schema, "132.0"):
                    required.add("collaboration_governance_132")
                    governance_registered = registry.is_registered("collaboration_governance_132")
                    governance_details: dict[str, Any] = {
                        "registered": governance_registered,
                        "remote_server_mode": "unknown",
                        "four_eyes_enforced": False,
                        "automatic_approvals": False,
                        "external_ai_actions": 0,
                    }
                    governance_ok = governance_registered
                    if governance_registered:
                        governance = registry.get("collaboration_governance_132")
                        governance_settings = governance.settings()
                        governance_details.update({
                            "remote_server_mode": governance_settings.get("remote_server_mode"),
                            "four_eyes_enforced": bool(governance_settings.get("require_four_eyes")),
                            "team_mode_enabled": bool(governance_settings.get("team_mode_enabled")),
                        })
                        governance_ok = (
                            governance_settings.get("remote_server_mode") == "disabled_loopback_only"
                            and bool(governance_settings.get("require_four_eyes"))
                        )
                        owner = self.db.one(
                            "SELECT password_hash FROM governance_users_132 WHERE username='local-analyst' COLLATE NOCASE"
                        ) or {}
                        active_users = int((self.db.one(
                            "SELECT COUNT(*) AS n FROM governance_users_132 WHERE active=1"
                        ) or {}).get("n") or 0)
                        active_sessions = int((self.db.one(
                            "SELECT COUNT(*) AS n FROM governance_sessions_132 WHERE revoked=0 AND expires_epoch>=strftime('%s','now')"
                        ) or {}).get("n") or 0)
                        pending_failed = int((self.db.one(
                            "SELECT COUNT(*) AS n FROM governance_approval_requests_132 WHERE execution_status='failed'"
                        ) or {}).get("n") or 0)
                        expired_locks = int((self.db.one(
                            "SELECT COUNT(*) AS n FROM governance_object_locks_132 WHERE active=1 AND expires_epoch<strftime('%s','now')"
                        ) or {}).get("n") or 0)
                        governance_details.update({
                            "active_users": active_users,
                            "active_sessions": active_sessions,
                            "failed_approval_executions": pending_failed,
                            "expired_active_locks": expired_locks,
                            "owner_passphrase_configured": bool(owner.get("password_hash")),
                        })
                        checks.append(self._check(
                            "governance_execution_failures",
                            "Keine fehlgeschlagenen kritischen Freigabeausführungen",
                            "critical",
                            pending_failed == 0,
                            {"count": pending_failed},
                        ))
                        checks.append(self._check(
                            "governance_expired_locks",
                            "Keine abgelaufenen aktiven Objektsperren",
                            "high",
                            expired_locks == 0,
                            {"count": expired_locks},
                        ))
                        if governance_settings.get("team_mode_enabled"):
                            checks.append(self._check(
                                "governance_team_readiness",
                                "Teammodus besitzt Eigentümer-Passphrase und zweiten aktiven Benutzer",
                                "high",
                                bool(owner.get("password_hash")) and active_users >= 2,
                                {"owner_passphrase_configured": bool(owner.get("password_hash")), "active_users": active_users},
                                warning=True,
                            ))
                    checks.append(self._check(
                        "phase3_collaboration_governance",
                        "Collaboration & Governance ist loopback-only, vier-Augen- und review-first",
                        "critical",
                        governance_ok,
                        governance_details,
                    ))
            policy127 = self.db.one("SELECT * FROM orchestrator_policy_127 WHERE policy_id='default'") or {}
            checks.append(self._check(
                "phase3_orchestrator",
                "Phase-3-Orchestrator ist kontrolliert",
                "critical",
                policy127.get("external_network_default") == "blocked"
                and policy127.get("output_trust_state") == "suggestions_only"
                and int(policy127.get("max_external_actions_hard", -1)) == 0,
                policy127,
            ))
        registered = {name for name in required if registry.is_registered(name)}
        checks.append(self._check("services", "Kanonische Services registriert", "critical", registered == required, {"missing": sorted(required - registered)}))

        blocker_count = sum(1 for item in checks if item["status"] == "fail" and item["severity"] in {"critical", "high"})
        warning_count = sum(1 for item in checks if item["status"] == "warning")
        deductions = sum(20 if item["severity"] == "critical" else 10 if item["severity"] == "high" else 4 for item in checks if item["status"] == "fail") + 2 * warning_count
        score = max(0, 100 - deductions)
        status = "fail" if blocker_count else ("conditional" if warning_count else "pass")
        run_id = new_id("pc126")
        report = {"build": BUILD, "schema": SCHEMA_VERSION, "case_id": case_id or "", "status": status, "score": score, "checks": checks}
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO production_candidate_runs_126(run_id,case_id,status,score,check_count,blocker_count,warning_count,report_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (run_id, case_id, status, score, len(checks), blocker_count, warning_count, dumps(report), actor, now_ts()),
            )
            for item in checks:
                self.db.execute(
                    "INSERT INTO production_candidate_checks_126(check_id,run_id,check_key,title,severity,status,details_json) VALUES(?,?,?,?,?,?,?)",
                    (new_id("pcc126"), run_id, item["key"], item["title"], item["severity"], item["status"], dumps(item["details"])),
                )
        self.audit.log("production_gate", "production_candidate_126", run_id, case_id, {"status": status, "score": score, "blockers": blocker_count, "warnings": warning_count})
        return {**report, "run_id": run_id, "blocker_count": blocker_count, "warning_count": warning_count}

    def prepare_freeze(self, *, case_id: str | None, actor: str, notes: str = "") -> dict[str, Any]:
        backup = self.reliability.create_backup(actor=actor, case_id=case_id, include_evidence=True)
        if case_id and self.db.one("SELECT package_id FROM evidence_packages_121 WHERE case_id=? LIMIT 1", (case_id,)):
            self.protection.create_evidence_checkpoint(case_id=case_id, actor=actor)
        gate = self.run_gate(case_id=case_id, actor=actor)
        if gate["status"] == "fail":
            raise ProductionGateError("Phase-2-Freeze verweigert: Production Gate enthält Blocker")
        manifest = self.base_dir / "RELEASE_MANIFEST_BUILD_133_1.json"
        if not manifest.is_file():
            manifest = self.base_dir / "RELEASE_MANIFEST_BUILD_132_0.json"
        if not manifest.is_file():
            manifest = self.base_dir / "RELEASE_MANIFEST_BUILD_131_0.json"
        if not manifest.is_file():
            manifest = self.base_dir / "RELEASE_MANIFEST_BUILD_130_0.json"
        if not manifest.is_file():
            manifest = self.base_dir / "RELEASE_MANIFEST_BUILD_129_0.json"
        if not manifest.is_file():
            manifest = self.base_dir / "RELEASE_MANIFEST_BUILD_128_0.json"
        if not manifest.is_file():
            manifest = self.base_dir / "RELEASE_MANIFEST_BUILD_126_3.json"
        if not manifest.is_file():
            manifest = self.base_dir / "RELEASE_MANIFEST_BUILD_126_1.json"
        if not manifest.is_file():
            manifest = self.base_dir / "RELEASE_MANIFEST_BUILD_126_0.json"
        manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else ""
        freeze_id = new_id("freeze126")
        self.db.execute(
            "INSERT INTO phase2_release_freezes_126(freeze_id,case_id,gate_run_id,backup_id,manifest_sha256,status,notes,created_by,created_at) VALUES(?,?,?,?,?,'frozen',?,?,?)",
            (freeze_id, case_id, gate["run_id"], backup["backup_id"], manifest_sha, str(notes or "")[:2000], actor, now_ts()),
        )
        self.audit.log("freeze", "phase2_release_126", freeze_id, case_id, {"gate_run_id": gate["run_id"], "backup_id": backup["backup_id"], "manifest_sha256": manifest_sha})
        return self.db.one("SELECT * FROM phase2_release_freezes_126 WHERE freeze_id=?", (freeze_id,)) or {}

    def record_external_ai_launch(self, *, case_id: str | None, tool_key: str, destination_url: str, launch_mode: str, status: str, actor: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        parts = urlsplit(destination_url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise ValueError("Externes AI-Ziel muss eine öffentliche HTTPS-Adresse ohne Zugangsdaten sein")
        launch_id = new_id("extai126")
        safe_details = dict(details or {})
        for key in tuple(safe_details):
            if any(marker in key.casefold() for marker in ("prompt", "query", "token", "secret", "case_data")):
                safe_details[key] = "[not-recorded]"
        self.db.execute(
            "INSERT INTO external_ai_launches_126(launch_id,case_id,tool_key,destination_host,launch_mode,status,actor,details_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (launch_id, case_id, tool_key, parts.hostname.casefold(), launch_mode, status, actor, dumps(safe_details), now_ts()),
        )
        self.audit.log("external_ai_launch", "external_ai_126", launch_id, case_id, {"tool_key": tool_key, "destination_host": parts.hostname.casefold(), "launch_mode": launch_mode, "status": status})
        return self.db.one("SELECT * FROM external_ai_launches_126 WHERE launch_id=?", (launch_id,)) or {}

    def launch_chatgpt_protected(self, *, case_id: str, actor: str, local_redirect_origin: str) -> dict[str, Any]:
        result = self.protection.launch_external_https(
            case_id=case_id,
            destination_url=self.CHATGPT_URL,
            tool_key="chatgpt",
            actor=actor,
            local_redirect_origin=local_redirect_origin,
        )
        self.record_external_ai_launch(case_id=case_id, tool_key="chatgpt", destination_url=self.CHATGPT_URL, launch_mode=result["browser_mode"], status=result["status"], actor=actor, details={"automatic_case_transfer": False})
        return result

    @staticmethod
    def _parse_installer_payload(stdout: str) -> dict[str, Any]:
        for line in reversed((stdout or "").splitlines()):
            line = line.strip().lstrip("\ufeff")
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise RuntimeError("Der Windows-Installer hat kein gültiges Ergebnis geliefert")

    def _windows_tool(self, executable: str, relative_fallback: str) -> str | None:
        found = shutil.which(executable)
        if found:
            return found
        system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR")
        if system_root:
            candidate = Path(system_root) / relative_fallback
            if candidate.is_file():
                return str(candidate)
        return None

    def create_windows_shortcut(self, *, actor: str = "local-analyst", include_start_menu: bool = True) -> dict[str, Any]:
        install_id = new_id("shortcut1261")
        ps_script = self.base_dir / "tools" / "windows" / "create_shortcut.ps1"
        vbs_script = self.base_dir / "tools" / "windows" / "create_shortcut.vbs"
        icon = self.base_dir / "assets" / "windows" / "eagleeye.ico"
        launcher = self.base_dir / "START_EAGLEEYE_PRO.bat"
        attempts: list[str] = []
        engine = ""
        payload: dict[str, Any] = {}
        try:
            if self.platform_name != "nt":
                raise OSError("Windows-Verknüpfungen können nur unter Windows erstellt werden")
            if not icon.is_file() or not launcher.is_file():
                raise FileNotFoundError("Windows-Launcher oder Icon fehlt")

            powershell = self._windows_tool("powershell.exe", "System32/WindowsPowerShell/v1.0/powershell.exe")
            if powershell and ps_script.is_file():
                command = [
                    powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", str(ps_script), "-Root", str(self.base_dir),
                ]
                if include_start_menu:
                    command.append("-CreateStartMenu")
                completed = self.process_runner(command, capture_output=True, text=True, timeout=45, check=False)
                if int(getattr(completed, "returncode", 1)) == 0:
                    try:
                        payload = self._parse_installer_payload(getattr(completed, "stdout", ""))
                        engine = "powershell"
                    except Exception as exc:
                        attempts.append(f"PowerShell-Ausgabe: {exc}")
                else:
                    attempts.append((getattr(completed, "stderr", "") or "PowerShell fehlgeschlagen")[:1000])

            if not payload:
                cscript = self._windows_tool("cscript.exe", "System32/cscript.exe")
                if cscript and vbs_script.is_file():
                    command = [cscript, "//nologo", str(vbs_script), str(self.base_dir), "1" if include_start_menu else "0"]
                    completed = self.process_runner(command, capture_output=True, text=True, timeout=45, check=False)
                    if int(getattr(completed, "returncode", 1)) == 0:
                        payload = self._parse_installer_payload(getattr(completed, "stdout", ""))
                        engine = "vbscript"
                    else:
                        attempts.append((getattr(completed, "stderr", "") or getattr(completed, "stdout", "") or "VBScript fehlgeschlagen")[:1000])

            if not payload:
                detail = " | ".join(item.strip() for item in attempts if item.strip()) or "Weder PowerShell noch Windows Script Host ist verfügbar"
                raise RuntimeError(detail[:1800])
            desktop_path = str(payload.get("desktop_path") or "")
            if not desktop_path:
                raise RuntimeError("Installer meldete keinen Desktop-Link")
            self.db.execute(
                "INSERT INTO windows_shortcut_installs_126(install_id,status,desktop_path,start_menu_path,icon_path,error_text,requested_by,created_at) VALUES(?,'installed',?,?,?,?,?,?)",
                (install_id, desktop_path, str(payload.get("start_menu_path") or ""), str(icon), "", actor, now_ts()),
            )
        except Exception as exc:
            self.db.execute(
                "INSERT INTO windows_shortcut_installs_126(install_id,status,icon_path,error_text,requested_by,created_at) VALUES(?,'failed',?,?,?,?)",
                (install_id, str(icon), str(exc)[:1000], actor, now_ts()),
            )
            self.audit.log("shortcut_failed", "windows_shortcut_126", install_id, None, {"error_type": type(exc).__name__, "fallback_attempted": bool(attempts)})
            raise
        result = self.db.one("SELECT * FROM windows_shortcut_installs_126 WHERE install_id=?", (install_id,)) or {}
        result = dict(result)
        result["installer_engine"] = engine or str(payload.get("engine") or "")
        self.audit.log("shortcut_installed", "windows_shortcut_126", install_id, None, {"desktop_path": True, "start_menu_path": bool(result.get("start_menu_path")), "engine": result["installer_engine"]})
        return result

    def recent_runs(self, case_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        if case_id:
            return self.db.all("SELECT * FROM production_candidate_runs_126 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, max(1, min(limit, 100))))
        return self.db.all("SELECT * FROM production_candidate_runs_126 ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 100)),))

    def recent_freezes(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM phase2_release_freezes_126 ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 100)),))

    def recent_external_ai(self, case_id: str, limit: int = 30) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM external_ai_launches_126 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, max(1, min(limit, 100))))
