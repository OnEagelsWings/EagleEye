from __future__ import annotations
from typing import Any, Dict, List, Iterable
from pathlib import Path
import os
import re
import shutil
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.legal.service import LegalGateService, DEFAULT_ALLOWED, DEFAULT_PROHIBITED

DEFAULT_ALLOWED_DATA_CLASSES = [
    "Identitätsanker", "Berufs-/Firmenbezug", "öffentliche Kontaktanker", "öffentliche Presse-/Registerhinweise",
    "öffentliche technische Metadaten", "Gegenbelege/Ausschlussbelege"
]
DEFAULT_PROHIBITED_DATA_CLASSES = [
    "private Kommunikation", "private Account-Inhalte", "Gesundheitsdaten", "Religion/Weltanschauung",
    "politische Meinung", "Sexualleben/sexuelle Orientierung", "biometrische eindeutige Identifizierung",
    "Daten Minderjähriger", "strafrechtliche Vorwürfe ohne Mandats-/Rechtsprüfung"
]
DEFAULT_PROHIBITED_PROCESSING = [
    "Login-Umgehung", "Captcha-Bypass", "private Accounts", "heimliche Überwachung", "Doxxing",
    "automatische Identitätsbehauptung", "automatische Wohnortfeststellung als Tatsache", "verdeckte Kontaktaufnahme aus dem Tool"
]

SPECIAL_KEYWORDS = {
    "Gesundheitsdaten": ["krankheit", "diagnose", "therapie", "arzt", "psychotherapie", "depression", "trauma", "medikament"],
    "Religion/Weltanschauung": ["kirche", "gemeinde", "religion", "christ", "muslim", "jude", "synagoge", "moschee"],
    "politische Meinung": ["partei", "wahlkampf", "politisch", "aktivist", "demonstration", "afd", "spd", "cdu", "grüne"],
    "Sexualleben/sexuelle Orientierung": ["sexualität", "orientation", "dating", "lgbt", "queer"],
    "strafrechtliche Daten": ["straftat", "verurteilung", "anklage", "ermittlung", "polizei", "haft", "betrug", "gewalt"],
    "Minderjährige": ["minderjährig", "kind", "schüler", "klasse", "jugendlich", "geburtsjahr 20"],
}

class LegalPrivacyHardeningService:
    """Build 25.0: Security Hardening.

    This service intentionally does not bypass access controls or enrich private data. It adds
    structured privacy gates around already-collected public/authorized OSINT data.
    """
    def __init__(self, db: Database, audit: AuditService, base_dir: str | Path | None = None):
        self.db = db
        self.audit = audit
        if base_dir is not None:
            self.base_dir = Path(base_dir).resolve()
        else:
            db_parent = Path(getattr(db, "path", Path.cwd())).resolve().parent
            self.base_dir = db_parent.parent if db_parent.name.casefold() == "data" else db_parent
        self.photo_root_136 = (self.base_dir / "data" / "photo_evidence_136").resolve()

    # ---------- Legal Case Wizard ----------
    def create_legal_case_wizard(
        self,
        case_id: str,
        lawful_basis: str,
        legitimate_interest: str,
        necessity_test: str,
        balancing_test: str,
        proportionality_test: str = "",
        data_minimization_notes: str = "",
        expected_data_classes: List[str] | None = None,
        prohibited_processing: List[str] | None = None,
        allowed_sources: List[str] | None = None,
        prohibited_sources: List[str] | None = None,
        retention_until: str = "",
        decision: str = "approved",
        risk_level: str = "medium",
        reviewer: str = "local-analyst",
        notes: str = "",
        special_categories: bool = False,
        minor_data: bool = False,
        criminal_data: bool = False,
    ) -> Dict[str, Any]:
        expected = expected_data_classes or DEFAULT_ALLOWED_DATA_CLASSES
        prohibited = prohibited_processing or DEFAULT_PROHIBITED_PROCESSING
        assessment_id = new_id("pa")
        self.db.execute("""INSERT INTO privacy_assessments(
            assessment_id,case_id,assessment_type,lawful_basis,legitimate_interest,necessity_test,balancing_test,
            proportionality_test,data_minimization_notes,expected_data_classes_json,prohibited_processing_json,
            decision,risk_level,reviewer,created_at,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [
            assessment_id, case_id, "legal_case_wizard", lawful_basis, legitimate_interest, necessity_test,
            balancing_test, proportionality_test, data_minimization_notes, dumps(expected), dumps(prohibited),
            decision, risk_level, reviewer, now_ts(), notes
        ])
        rule_id = new_id("scope")
        self.db.execute("""INSERT INTO processing_scope_rules(
            rule_id,case_id,allowed_sources_json,prohibited_sources_json,allowed_data_classes_json,
            prohibited_data_classes_json,retention_until,active,created_at,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", [
            rule_id, case_id, dumps(allowed_sources or DEFAULT_ALLOWED), dumps(prohibited_sources or DEFAULT_PROHIBITED),
            dumps(expected), dumps(DEFAULT_PROHIBITED_DATA_CLASSES), retention_until, 1, now_ts(), notes
        ])
        # Use the existing legal gate, but require senior/legal/dpo when risky flags are present.
        review_level = "senior" if (special_categories or minor_data or criminal_data or risk_level in {"high", "very_high"}) else "analyst"
        approved = decision == "approved" and review_level in {"analyst", "senior", "legal", "dpo"}
        LegalGateService(self.db, self.audit).create_review(
            case_id, legitimate_interest or "Fallzweck gemäß Privacy Wizard", lawful_basis, necessity_test, balancing_test,
            source_scope=allowed_sources or DEFAULT_ALLOWED, prohibited_scope=prohibited_sources or DEFAULT_PROHIBITED,
            special_categories=special_categories, minor_data=minor_data, criminal_data=criminal_data,
            approved=approved, review_level=review_level, reviewer=reviewer, notes=f"Build 25 Privacy Wizard: {notes}"
        )
        if retention_until:
            # Insert retention policy without importing ComplianceService to keep this service standalone.
            policy_id = new_id("ret")
            self.db.execute("""INSERT INTO retention_policies(policy_id,case_id,retention_until,deletion_mode,reason,created_at)
            VALUES(?,?,?,?,?,?)""", [policy_id, case_id, retention_until, "review_required", "Privacy Wizard Retention", now_ts()])
            self.db.execute("UPDATE cases SET retention_until=?, updated_at=? WHERE case_id=?", [retention_until, now_ts(), case_id])
        dpia = self.run_dpia_check(case_id, declared_special=special_categories, declared_minor=minor_data, declared_criminal=criminal_data)
        self.audit.log("create", "privacy_assessment", assessment_id, case_id, {"decision": decision, "risk_level": risk_level, "dpia_required": dpia.get("required")})
        return self.get_privacy_dashboard(case_id)

    def latest_assessment(self, case_id: str) -> Dict[str, Any] | None:
        row = self.db.one("SELECT * FROM privacy_assessments WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if row:
            row["expected_data_classes_json"] = loads(row.get("expected_data_classes_json"), [])
            row["prohibited_processing_json"] = loads(row.get("prohibited_processing_json"), [])
        return row

    # ---------- Data classification ----------
    def classify_case_data(self, case_id: str, reviewer: str = "local-analyst") -> Dict[str, Any]:
        scanned = 0
        created = 0
        # Clear stale automatic flags for rescans while preserving human-reviewed flags.
        self.db.execute("DELETE FROM sensitive_data_flags WHERE case_id=? AND status='auto_detected'", [case_id])
        rows: List[Dict[str, Any]] = []
        rows.extend([{**r, "_object_type": "review_item", "_object_id": r["item_id"], "_text": " ".join([r.get("title") or "", r.get("snippet") or "", r.get("notes") or ""])} for r in self.db.all("SELECT * FROM review_items WHERE case_id=?", [case_id])])
        rows.extend([{**r, "_object_type": "evidence_item", "_object_id": r["evidence_id"], "_text": " ".join([r.get("title") or "", r.get("statement") or "", r.get("notes") or ""])} for r in self.db.all("SELECT * FROM evidence_items WHERE case_id=?", [case_id])])
        rows.extend([{**r, "_object_type": "provider_result", "_object_id": r["result_id"], "_text": " ".join([r.get("title") or "", r.get("snippet") or "", r.get("raw_payload_json") or ""])} for r in self.db.all("SELECT * FROM provider_results WHERE case_id=?", [case_id])])
        for row in rows:
            scanned += 1
            text = (row.get("_text") or "").lower()
            # PII is not blocked by itself, but warns for redaction/data minimization.
            if re.search(r"\b[\w.%-]+@[\w.-]+\.[A-Za-z]{2,}\b", row.get("_text") or ""):
                self._create_flag(case_id, row["_object_type"], row["_object_id"], "Kontakt-/E-Mail-Datum", "Art. 5 DSGVO", "low", "Redaction/Data-Minimization vor Client-Export prüfen.", "auto_detected", reviewer, "Automatische PII-Erkennung.")
                created += 1
            for category, needles in SPECIAL_KEYWORDS.items():
                if any(n in text for n in needles):
                    article = "Art. 9 DSGVO" if category in {"Gesundheitsdaten", "Religion/Weltanschauung", "politische Meinung", "Sexualleben/sexuelle Orientierung"} else ("Art. 10 DSGVO" if category == "strafrechtliche Daten" else "DSGVO/Kinder- und Schutzinteressen")
                    severity = "high" if article in {"Art. 9 DSGVO", "Art. 10 DSGVO"} or category == "Minderjährige" else "medium"
                    self._create_flag(case_id, row["_object_type"], row["_object_id"], category, article, severity, "Senior/Legal Review erforderlich; Export blockieren bis geklärt.", "auto_detected", reviewer, "Automatische Stichwortprüfung; menschliche Bewertung erforderlich.")
                    created += 1
        self.audit.log("classify", "privacy_data_classes", case_id, case_id, {"scanned": scanned, "created_flags": created})
        self.run_dpia_check(case_id)
        return {"scanned_objects": scanned, "created_flags": created, "flags": self.list_flags(case_id)}

    def _create_flag(self, case_id: str, object_type: str, object_id: str, data_category: str, article_reference: str,
                     severity: str, action_required: str, status: str, reviewer: str, notes: str) -> Dict[str, Any]:
        fid = new_id("sflag")
        self.db.execute("""INSERT INTO sensitive_data_flags(flag_id,case_id,object_type,object_id,data_category,article_reference,severity,action_required,status,detected_at,reviewer,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", [fid, case_id, object_type, object_id, data_category, article_reference, severity, action_required, status, now_ts(), reviewer, notes])
        return self.db.one("SELECT * FROM sensitive_data_flags WHERE flag_id=?", [fid])

    def list_flags(self, case_id: str, status: str | None = None) -> List[Dict[str, Any]]:
        if status:
            return self.db.all("SELECT * FROM sensitive_data_flags WHERE case_id=? AND status=? ORDER BY severity DESC, detected_at DESC", [case_id, status])
        return self.db.all("SELECT * FROM sensitive_data_flags WHERE case_id=? ORDER BY status, severity DESC, detected_at DESC", [case_id])

    def resolve_flag(self, flag_id: str, decision: str = "resolved", notes: str = "", reviewer: str = "local-analyst") -> Dict[str, Any]:
        self.db.execute("UPDATE sensitive_data_flags SET status=?, reviewer=?, notes=notes||? WHERE flag_id=?", [decision, reviewer, "\n" + notes if notes else "", flag_id])
        row = self.db.one("SELECT * FROM sensitive_data_flags WHERE flag_id=?", [flag_id])
        if row:
            self.audit.log("resolve", "sensitive_data_flag", flag_id, row.get("case_id"), {"decision": decision})
        return row or {}

    # ---------- DPIA / DSFA ----------
    def run_dpia_check(self, case_id: str, declared_special: bool = False, declared_minor: bool = False, declared_criminal: bool = False,
                       reviewer: str = "local-analyst") -> Dict[str, Any]:
        triggers: List[str] = []
        latest_legal = self.db.one("SELECT * FROM legal_reviews WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id]) or {}
        open_high_flags = self.db.one("SELECT COUNT(*) AS n FROM sensitive_data_flags WHERE case_id=? AND status IN ('open','auto_detected') AND severity='high'", [case_id])["n"]
        review_items = self.db.one("SELECT COUNT(*) AS n FROM review_items WHERE case_id=?", [case_id])["n"]
        provider_jobs = self.db.one("SELECT COUNT(*) AS n FROM provider_jobs WHERE case_id=?", [case_id])["n"]
        if declared_special or latest_legal.get("special_categories"):
            triggers.append("Besondere Kategorien personenbezogener Daten möglich (Art. 9 DSGVO).")
        if declared_minor or latest_legal.get("minor_data"):
            triggers.append("Minderjährige/Schutzinteressen möglich.")
        if declared_criminal or latest_legal.get("criminal_data"):
            triggers.append("Strafrechtliche Daten/Vorwürfe möglich (Art. 10 DSGVO).")
        if open_high_flags:
            triggers.append(f"{open_high_flags} offene High-Severity-Datenflags.")
        if review_items >= 50 or provider_jobs >= 20:
            triggers.append("Umfangreiche systematische Recherche/Profilbildung möglich.")
        required = bool(triggers)
        trigger_level = "high" if required and (open_high_flags or declared_special or declared_criminal or declared_minor) else ("medium" if required else "low")
        status = "required_open" if required else "not_required"
        dpia_id = new_id("dpia")
        self.db.execute("""INSERT INTO dpia_checks(dpia_id,case_id,trigger_level,required,triggers_json,status,reviewer,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?)""", [dpia_id, case_id, trigger_level, int(required), dumps(triggers), status, reviewer, now_ts(), "Build 25 DSFA/DPIA trigger check."])
        self.audit.log("check", "dpia", dpia_id, case_id, {"required": required, "trigger_level": trigger_level, "triggers": triggers})
        return {"dpia_id": dpia_id, "required": required, "trigger_level": trigger_level, "status": status, "triggers": triggers}

    def decide_dpia(self, dpia_id: str, status: str = "completed", notes: str = "", reviewer: str = "local-analyst") -> Dict[str, Any]:
        self.db.execute("UPDATE dpia_checks SET status=?, decided_at=?, reviewer=?, notes=notes||? WHERE dpia_id=?", [status, now_ts(), reviewer, "\n" + notes if notes else "", dpia_id])
        row = self.db.one("SELECT * FROM dpia_checks WHERE dpia_id=?", [dpia_id])
        if row:
            self.audit.log("decide", "dpia", dpia_id, row.get("case_id"), {"status": status})
        return row or {}

    # ---------- Export privacy blockers ----------
    def evaluate_privacy_export(self, case_id: str, report_type: str = "redacted_client") -> Dict[str, Any]:
        self.db.execute("DELETE FROM privacy_export_blockers WHERE case_id=? AND status='open'", [case_id])
        blockers: List[Dict[str, Any]] = []
        def block(kind: str, severity: str, description: str, obj_type: str = "", obj_id: str = ""):
            bid = new_id("pblk")
            self.db.execute("""INSERT INTO privacy_export_blockers(blocker_id,case_id,blocker_type,severity,description,status,related_object_type,related_object_id,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""", [bid, case_id, kind, severity, description, "open", obj_type, obj_id, now_ts()])
            blockers.append({"blocker_id": bid, "blocker_type": kind, "severity": severity, "description": description, "related_object_type": obj_type, "related_object_id": obj_id})
        assessment = self.latest_assessment(case_id)
        legal_eval = LegalGateService(self.db, self.audit).evaluate_case(case_id)
        if not assessment or assessment.get("decision") not in {"approved", "review_required"}:
            block("privacy_assessment_missing", "high", "Legal Case Wizard / Privacy Assessment fehlt oder ist nicht freigegeben.")
        if not legal_eval.get("ok"):
            block("legal_gate", "high", "Legal Gate ist nicht erfüllt: " + "; ".join(legal_eval.get("issues", [])))
        open_flags = self.list_flags(case_id)
        unresolved_high = [f for f in open_flags if f.get("status") in {"open", "auto_detected"} and f.get("severity") == "high"]
        unresolved_any = [f for f in open_flags if f.get("status") in {"open", "auto_detected"}]
        if unresolved_high:
            for f in unresolved_high[:20]:
                block("sensitive_data", "high", f"Offenes High-Severity-Flag: {f['data_category']} / {f['article_reference']}", f.get("object_type",""), f.get("object_id",""))
        elif report_type in {"client_short", "redacted_client"} and unresolved_any:
            block("sensitive_data_review", "medium", f"{len(unresolved_any)} offene Datenklassen-/Redaction-Flags vor Client-Export prüfen.")
        dpia = self.db.one("SELECT * FROM dpia_checks WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if dpia and dpia.get("required") and dpia.get("status") not in {"completed", "not_required"}:
            block("dpia_required", "high", "DSFA/DPIA wurde getriggert, ist aber nicht abgeschlossen.", "dpia_check", dpia.get("dpia_id",""))
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id]) or {}
        if not case.get("retention_until"):
            block("retention_missing", "medium", "Keine Lösch-/Reviewfrist gesetzt.")
        decision = "blocked" if any(b["severity"] == "high" for b in blockers) else ("review_required" if blockers else "approved")
        self.audit.log("evaluate", "privacy_export", case_id, case_id, {"report_type": report_type, "decision": decision, "blockers": blockers})
        return {"decision": decision, "report_type": report_type, "blockers": blockers, "blocker_count": len(blockers)}

    # ---------- Retention / Deletion engine ----------
    def create_retention_deletion_job(self, case_id: str, action: str = "review_retention", reason: str = "", scheduled_for: str = "", reviewer: str = "local-analyst", notes: str = "") -> Dict[str, Any]:
        counts = self._affected_counts(case_id)
        jid = new_id("deljob")
        self.db.execute("""INSERT INTO retention_deletion_jobs(job_id,case_id,action,reason,status,scheduled_for,affected_counts_json,reviewer,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?)""", [jid, case_id, action, reason or "Retention/Deletion review", "planned", scheduled_for, dumps(counts), reviewer, now_ts(), notes])
        self.audit.log("create", "retention_deletion_job", jid, case_id, {"action": action, "counts": counts})
        return self.db.one("SELECT * FROM retention_deletion_jobs WHERE job_id=?", [jid])

    def execute_retention_deletion_job(self, job_id: str, dry_run: bool = True, reviewer: str = "local-analyst") -> Dict[str, Any]:
        job = self.db.one("SELECT * FROM retention_deletion_jobs WHERE job_id=?", [job_id])
        if not job:
            return {"ok": False, "error": "JOB_NOT_FOUND"}
        case_id = job["case_id"]
        counts = self._affected_counts(case_id)
        if dry_run:
            self.db.execute("UPDATE retention_deletion_jobs SET status=?, executed_at=?, affected_counts_json=? WHERE job_id=?", ["dry_run_completed", now_ts(), dumps(counts), job_id])
            self.audit.log("dry_run", "retention_deletion_job", job_id, case_id, {"counts": counts})
            return {"ok": True, "dry_run": True, "job_id": job_id, "affected_counts": counts}
        # Conservative deletion: requires action == delete_case_data and no open high blockers.
        if job.get("action") != "delete_case_data":
            return {"ok": False, "error": "JOB_ACTION_NOT_DESTRUCTIVE", "hint": "Set action='delete_case_data' for confirmed deletion."}
        high = self.db.one("SELECT COUNT(*) AS n FROM privacy_export_blockers WHERE case_id=? AND status='open' AND severity='high'", [case_id])["n"]
        if high:
            return {"ok": False, "error": "OPEN_PRIVACY_BLOCKERS", "high_blockers": high}
        staged_photo_dir: Path | None = None
        original_photo_dir: Path | None = None
        try:
            staged_photo_dir, original_photo_dir = self._stage_build136_photo_vault(case_id=case_id, job_id=job_id)
        except OSError as exc:
            self.audit.log("delete_blocked", "retention_deletion_job", job_id, case_id, {"reason": "photo_vault_stage_failed", "error": str(exc)})
            return {"ok": False, "error": "PHOTO_VAULT_STAGE_FAILED", "detail": str(exc)}

        try:
            # Database rows are removed only after the local photo vault has
            # been atomically moved out of its live case path. A failed DB
            # transaction restores that directory before returning.
            with self.db.transaction(immediate=True):
                self.db.execute("DELETE FROM cases WHERE case_id=?", [case_id])
        except Exception:
            self._restore_staged_build136_photo_vault(staged_photo_dir, original_photo_dir)
            raise

        cleanup_pending = False
        cleanup_error = ""
        if staged_photo_dir is not None and staged_photo_dir.exists():
            try:
                shutil.rmtree(staged_photo_dir)
            except OSError as exc:
                # The directory is no longer reachable through any live case
                # record. Build 136 retries these explicit tombstones at the
                # next startup instead of silently leaving a normal case vault.
                cleanup_pending = True
                cleanup_error = str(exc)

        details = {"counts": counts, "photo_cleanup_pending": cleanup_pending}
        if cleanup_error:
            details["photo_cleanup_error"] = cleanup_error
        self.audit.log("execute", "retention_deletion_job", job_id, case_id, details)
        return {
            "ok": True,
            "dry_run": False,
            "job_id": job_id,
            "affected_counts": counts,
            "photo_cleanup_pending": cleanup_pending,
            "warning": "PHOTO_VAULT_CLEANUP_PENDING" if cleanup_pending else "",
        }

    def _stage_build136_photo_vault(self, *, case_id: str, job_id: str) -> tuple[Path | None, Path | None]:
        root = self.photo_root_136
        original = (root / case_id).resolve()
        if original.parent != root:
            raise OSError("Ungültiger Build-136-Fototresorpfad")
        if not original.exists():
            return None, None
        if not original.is_dir() or original.is_symlink():
            raise OSError("Build-136-Fototresor ist kein reguläres Fallverzeichnis")
        safe_job = re.sub(r"[^A-Za-z0-9_.-]", "_", job_id)[:120]
        safe_case = re.sub(r"[^A-Za-z0-9_.-]", "_", case_id)[:120]
        staged = (root / f".deleting_build136_{safe_job}_{safe_case}").resolve()
        if staged.parent != root or staged.exists():
            raise OSError("Sicheres Lösch-Staging konnte nicht vorbereitet werden")
        os.replace(original, staged)
        return staged, original

    @staticmethod
    def _restore_staged_build136_photo_vault(staged: Path | None, original: Path | None) -> None:
        if staged is None or original is None or not staged.exists():
            return
        if original.exists():
            raise OSError("Fototresor-Rollback blockiert: Zielpfad existiert bereits")
        os.replace(staged, original)

    def _affected_counts(self, case_id: str) -> Dict[str, int]:
        tables = [
            "targets", "legal_reviews", "privacy_assessments", "processing_scope_rules", "sensitive_data_flags",
            "dpia_checks", "review_items", "evidence_items", "source_captures", "provider_jobs", "provider_results",
            "graph_nodes", "graph_edges", "timeline_events", "professional_reports", "audit_events",
            "photo_assets_136", "photo_asset_events_136"
        ]
        out: Dict[str, int] = {}
        for t in tables:
            try:
                out[t] = int(self.db.one(f"SELECT COUNT(*) AS n FROM {t} WHERE case_id=?", [case_id])["n"])
            except Exception:
                out[t] = 0
        return out

    def get_privacy_dashboard(self, case_id: str) -> Dict[str, Any]:
        assessment = self.latest_assessment(case_id)
        latest_dpia = self.db.one("SELECT * FROM dpia_checks WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        flags = self.list_flags(case_id)
        blockers = self.db.all("SELECT * FROM privacy_export_blockers WHERE case_id=? AND status='open' ORDER BY severity DESC, created_at DESC", [case_id])
        rules = self.db.all("SELECT * FROM processing_scope_rules WHERE case_id=? AND active=1 ORDER BY created_at DESC", [case_id])
        jobs = self.db.all("SELECT * FROM retention_deletion_jobs WHERE case_id=? ORDER BY created_at DESC", [case_id])
        flag_summary: Dict[str, int] = {}
        for f in flags:
            key = f"{f.get('severity')}:{f.get('status')}"
            flag_summary[key] = flag_summary.get(key, 0) + 1
        readiness = "privacy_ready" if assessment and not [f for f in flags if f.get("severity") == "high" and f.get("status") in {"open","auto_detected"}] and not (latest_dpia and latest_dpia.get("required") and latest_dpia.get("status") not in {"completed","not_required"}) else "privacy_review_required"
        return {
            "assessment": assessment,
            "latest_dpia": latest_dpia,
            "open_flags": len([f for f in flags if f.get("status") in {"open", "auto_detected"}]),
            "high_open_flags": len([f for f in flags if f.get("status") in {"open", "auto_detected"} and f.get("severity") == "high"]),
            "flag_summary": flag_summary,
            "active_scope_rules": len(rules),
            "open_privacy_blockers": len(blockers),
            "retention_jobs": len(jobs),
            "readiness": readiness,
        }
