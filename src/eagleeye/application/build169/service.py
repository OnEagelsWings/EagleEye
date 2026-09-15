from __future__ import annotations

import hashlib
import json
import re
import threading
from pathlib import Path
from typing import Any, Mapping

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class Build169ApplicationHardeningService:
    BUILD = "169.0"
    MISSION = "Application hardening, UX smoothing, AI guardrails and system-wide OPSEC verification"
    SECRET_KEYS = re.compile(r"(password|passwd|token|secret|api[_-]?key|authorization|cookie|session|private[_-]?key)", re.I)
    INJECTION = re.compile(r"(ignore\s+(all|previous|system)|reveal\s+(the\s+)?prompt|bypass\s+(policy|guardrail)|exfiltrat|tool\s*poison)", re.I)
    SEVERITIES = {"info", "low", "medium", "high", "critical"}

    def __init__(self, db: Any, audit: Any, *, observability: Any | None = None, actor: str = "system", project_root: str | Path | None = None) -> None:
        self.db = db
        self.audit = audit
        self.observability = observability
        self.actor = actor
        candidate = Path(project_root).resolve() if project_root else Path(__file__).resolve().parents[4]
        if not (candidate / "src").exists() and not (candidate / "eagleeye_pro").exists():
            candidate = Path(__file__).resolve().parents[4]
        self.project_root = candidate
        self._ensure_ux_manifest()

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): ("[REDACTED]" if self.SECRET_KEYS.search(str(k)) else self._sanitize(v)) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize(v) for v in value]
        if isinstance(value, tuple):
            return [self._sanitize(v) for v in value]
        text = str(value)
        if self.SECRET_KEYS.search(text) and ("=" in text or ":" in text):
            return "[REDACTED]"
        return value

    def ai_assist(self, *, case_id: str | None, task_type: str, context: Mapping[str, Any], created_by: str | None = None) -> dict[str, Any]:
        sanitized = self._sanitize(dict(context))
        serialized = _canon(sanitized)
        flags: list[str] = []
        if self.INJECTION.search(serialized):
            flags.append("prompt_injection_indicator")
        if "[REDACTED]" in serialized:
            flags.append("sensitive_material_redacted")
        recommendations: list[dict[str, Any]] = []
        if flags:
            recommendations.append({"priority": "high", "action": "manual_source_review", "reason": "untrusted or sensitive instructions detected"})
        if task_type in {"next_steps", "case_review", "opsec_review"}:
            recommendations.extend([
                {"priority": "high", "action": "verify_independent_sources", "reason": "avoid single-source conclusions"},
                {"priority": "high", "action": "review_identity_merges", "reason": "false merges remain the primary identity risk"},
                {"priority": "medium", "action": "review_temporal_conflicts", "reason": "historical and current relationships must remain distinct"},
            ])
        guardrails = {
            "local_only": True,
            "external_model_called": False,
            "untrusted_content_is_data": True,
            "automatic_action": False,
            "automatic_identity_confirmation": False,
            "automatic_accusation": False,
            "human_review_required": True,
            "flags": flags,
        }
        payload = {"case_id": case_id, "task_type": task_type, "context": sanitized, "recommendations": recommendations, "guardrails": guardrails}
        assessment_id = new_id("ai169")
        created_at = now_ts()
        self.db.execute("INSERT INTO ai_guardrail_assessments_169 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
            assessment_id, case_id, task_type, _hash(context), dumps(sanitized), dumps(recommendations), dumps(guardrails),
            "needs_review", created_by or self.actor, created_at, _hash(payload),
        ))
        self.audit.log("ai_guardrail_assessment_169", "ai169", assessment_id, case_id or "", {"task_type": task_type, "flags": flags})
        return {"assessment_id": assessment_id, **payload, "status": "needs_review"}

    def runtime_cleanup_check(self) -> dict[str, Any]:
        threads = threading.enumerate()
        non_daemon = [t.name for t in threads if t.is_alive() and not t.daemon and t is not threading.current_thread()]
        open_jobs = 0
        try:
            row = self.db.one("SELECT COUNT(*) AS n FROM operation_jobs_153 WHERE status IN ('queued','running')")
            open_jobs = int(row["n"]) if row else 0
        except Exception:
            open_jobs = 0
        db_ok = 1
        try:
            self.db.one("SELECT 1 AS ok")
        except Exception:
            db_ok = 0
        details = {"thread_names": [t.name for t in threads], "non_daemon_thread_names": non_daemon}
        payload = {"active_threads": len(threads), "non_daemon_threads": len(non_daemon), "open_jobs": open_jobs, "db_ok": bool(db_ok), "details": details}
        check_id = new_id("cleanup169")
        created_at = now_ts()
        self.db.execute("INSERT INTO runtime_cleanup_checks_169 VALUES(?,?,?,?,?,?,?,?)", (
            check_id, len(threads), len(non_daemon), open_jobs, db_ok, dumps(details), created_at, _hash(payload),
        ))
        return {"check_id": check_id, **payload, "created_at": created_at}

    def run_opsec_audit(self, *, scope: str = "full_application", created_by: str | None = None, confirmation: str) -> dict[str, Any]:
        if confirmation != "OPSEC 169 VOLLPRUEFUNG AUSFUEHREN":
            raise PermissionError("explicit OPSEC audit approval required")
        audit_id = new_id("audit169")
        findings: list[dict[str, Any]] = []
        runtime = self.runtime_cleanup_check()
        if runtime["non_daemon_threads"]:
            findings.append(self._finding("runtime", "medium", "threading", "Non-daemon background threads remain active", "Add deterministic shutdown and fixture teardown", runtime))
        if runtime["open_jobs"]:
            findings.append(self._finding("runtime", "high", "observability", "Queued or running jobs remain open", "Close or recover unfinished jobs before release", runtime))
        # Static, bounded audit: detect obvious hard-coded secret assignments and silent exception handlers.
        secret_hits = 0
        silent_handlers = 0
        scanned = 0
        roots = [self.project_root / "src", self.project_root / "eagleeye_pro"]
        assignment_re = re.compile(r"(?i)(api[_-]?key|password|token|secret)\s*=\s*['\"][^'\"]{6,}['\"]")
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*.py"):
                scanned += 1
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                secret_hits += len(assignment_re.findall(text))
                silent_handlers += len(re.findall(r"except(?:\s+[^:]+)?:\s*\n\s+pass\b", text))
        if secret_hits:
            findings.append(self._finding("secrets", "critical", "source_tree", f"{secret_hits} potential hard-coded secret assignments", "Review and move credentials to the Build 161 vault", {"count": secret_hits}))
        if silent_handlers:
            findings.append(self._finding("reliability", "medium", "source_tree", f"{silent_handlers} silent exception handlers", "Replace with classified outcome and structured telemetry", {"count": silent_handlers}))
        # Verify core protective contracts are still represented by active services/tables.
        required_tables = ["connector_credentials_161", "social_collection_authorizations_162", "crawl_authorizations_164", "evidence_registry_168"]
        missing_tables = []
        for table in required_tables:
            try:
                self.db.one(f"SELECT 1 FROM {table} LIMIT 1")
            except Exception:
                missing_tables.append(table)
        if missing_tables:
            findings.append(self._finding("controls", "critical", "database", "Core protective control tables missing", "Repair schema initialization", {"missing": missing_tables}))
        weights = {"info": 0, "low": 2, "medium": 8, "high": 20, "critical": 40}
        penalty = sum(weights[f["severity"]] for f in findings)
        score = max(0.0, 100.0 - penalty)
        status = "passed" if not any(f["severity"] in {"high", "critical"} for f in findings) else "blocked"
        metrics = {"files_scanned": scanned, "secret_hits": secret_hits, "silent_handlers": silent_handlers, "runtime": runtime}
        created_at = now_ts()
        payload = {"audit_id": audit_id, "scope": scope, "status": status, "score": score, "findings": findings, "metrics": metrics}
        self.db.execute("INSERT INTO hardening_audits_169 VALUES(?,?,?,?,?,?,?,?,?)", (
            audit_id, scope, status, score, dumps(findings), dumps(metrics), created_by or self.actor, created_at, _hash(payload),
        ))
        for finding in findings:
            self.db.execute("INSERT INTO opsec_findings_169 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
                finding["finding_id"], audit_id, finding["category"], finding["severity"], finding["component"], finding["description"],
                finding["remediation"], "open", dumps(finding["evidence"]), created_at, _hash(finding),
            ))
        self.audit.log("opsec_audit_169", "audit169", audit_id, "", {"status": status, "score": score, "findings": len(findings)})
        return {**payload, "created_at": created_at}

    def release_gate(self, audit_id: str, *, created_by: str | None = None, confirmation: str) -> dict[str, Any]:
        if confirmation != f"RELEASE GATE 169 {audit_id} PRUEFEN":
            raise PermissionError("explicit release gate approval required")
        row = self.db.one("SELECT * FROM hardening_audits_169 WHERE audit_id=?", (audit_id,))
        if not row:
            raise KeyError("audit not found")
        findings = loads(row["findings_json"], [])
        blockers = [f for f in findings if f.get("severity") in {"high", "critical"}]
        status = "blocked" if blockers or float(row["score"]) < 80 else "eligible_for_build170"
        approvals = {"human_release_approval_required": True, "automatic_release": False}
        gate_id = new_id("gate169")
        created_at = now_ts()
        payload = {"gate_id": gate_id, "audit_id": audit_id, "status": status, "blockers": blockers, "approvals": approvals}
        self.db.execute("INSERT INTO release_gates_169 VALUES(?,?,?,?,?,?,?,?)", (
            gate_id, audit_id, status, dumps(blockers), dumps(approvals), created_by or self.actor, created_at, _hash(payload),
        ))
        return {**payload, "created_at": created_at}

    def dashboard(self) -> dict[str, Any]:
        latest = self.db.one("SELECT * FROM hardening_audits_169 ORDER BY created_at DESC LIMIT 1")
        manifest = self.db.one("SELECT * FROM ux_hardening_manifest_169 ORDER BY created_at DESC LIMIT 1")
        return {
            "build": self.BUILD,
            "mission": self.MISSION,
            "latest_audit": dict(latest) if latest else None,
            "navigation": loads(manifest["sections_json"], []) if manifest else [],
            "opsec_contract": {
                "public_only_by_default": True,
                "no_intrusion": True,
                "no_secret_logging": True,
                "no_automatic_identity_confirmation": True,
                "no_automatic_accusation": True,
                "human_review_required": True,
            },
        }

    def _finding(self, category: str, severity: str, component: str, description: str, remediation: str, evidence: Any) -> dict[str, Any]:
        return {"finding_id": new_id("finding169"), "category": category, "severity": severity, "component": component, "description": description, "remediation": remediation, "evidence": evidence}

    def _ensure_ux_manifest(self) -> None:
        if self.db.one("SELECT manifest_id FROM ux_hardening_manifest_169 LIMIT 1"):
            return
        sections = [
            {"key": "case_overview", "title": "Fallübersicht", "purpose": "Status, Risiken und nächste Schritte"},
            {"key": "investigation_center", "title": "Ermittlungszentrale", "purpose": "Vermissten-, Straftaten- und Gefahrenworkflows"},
            {"key": "research_sources", "title": "Recherche & Quellen", "purpose": "Connectoren, Social Media und Crawling"},
            {"key": "evidence_media", "title": "Beweise & Medien", "purpose": "Capture, Replay, Evidenz und Integrität"},
            {"key": "analysis_graph", "title": "Analyse & Graph", "purpose": "Identität, Timeline, Beziehungen und Konflikte"},
            {"key": "ai_assistance", "title": "AI-Assistenz", "purpose": "Reviewpflichtige Triage und nächste Schritte"},
            {"key": "dossier_handover", "title": "Akte & Übergabe", "purpose": "Chain of Custody und Behördenexport"},
            {"key": "security_operations", "title": "Sicherheit & Betrieb", "purpose": "OPSEC, Health, Audit und Release Gate"},
        ]
        shortcuts = {"new_case": "Fallübersicht", "collect": "Recherche & Quellen", "review": "Ermittlungszentrale", "export": "Akte & Übergabe", "opsec": "Sicherheit & Betrieb"}
        hidden = ["build-specific tabs", "duplicate graph views", "legacy security dashboards"]
        payload = {"version": self.BUILD, "sections": sections, "shortcuts": shortcuts, "hidden": hidden}
        self.db.execute("INSERT INTO ux_hardening_manifest_169 VALUES(?,?,?,?,?,?,?)", (new_id("ux169"), self.BUILD, dumps(sections), dumps(shortcuts), dumps(hidden), now_ts(), _hash(payload)))
