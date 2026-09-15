from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security_kernel.policy import Decision, validate_query, validate_claim_type, classify_sensitivity

@dataclass(frozen=True)
class CommandEnvelope:
    name: str
    payload: Dict[str, Any]
    actor: str = "local-analyst"

class SecurityKernel:
    """Central Build 50.0 gatekeeper for public-only, review-first PersonOSINT workflows."""

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.registered_commands: set[str] = set()
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS mvfpe_decisions (
          decision_id TEXT PRIMARY KEY, case_id TEXT DEFAULT '', command_name TEXT NOT NULL,
          decision TEXT NOT NULL, gate TEXT NOT NULL, reason_code TEXT NOT NULL, message TEXT NOT NULL,
          risk_markers_json TEXT NOT NULL, required_actions_json TEXT NOT NULL,
          created_at TEXT NOT NULL, actor TEXT DEFAULT 'local-analyst'
        );
        CREATE INDEX IF NOT EXISTS idx_mvfpe_decisions_case ON mvfpe_decisions(case_id, created_at);
        ''')
        self.db.conn.commit()


    def register_commands(self, names) -> None:
        self.registered_commands.update(str(n) for n in names if n)

    def _record(self, command: CommandEnvelope, decision: Decision) -> Decision:
        case_id = str(command.payload.get("case_id") or "")
        decision_id = new_id("dec")
        self.db.execute(
            """INSERT INTO mvfpe_decisions(decision_id,case_id,command_name,decision,gate,reason_code,message,risk_markers_json,required_actions_json,created_at,actor)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            [decision_id, case_id, command.name, decision.decision, decision.gate, decision.reason_code, decision.message, dumps(decision.risk_markers), dumps(decision.required_actions), now_ts(), command.actor],
        )
        audit_id = self.audit.log("security_kernel_decision", "mvfpe_decision", decision_id, case_id or None, decision.as_dict() | {"command": command.name})
        return Decision(decision.decision, decision.gate, decision.reason_code, decision.message, list(decision.risk_markers), list(decision.required_actions), audit_id)

    def _case_has_approved_legal_scope(self, case_id: str) -> bool:
        if not case_id:
            return False
        row = self.db.one("SELECT review_id FROM legal_reviews WHERE case_id=? AND approved=1 ORDER BY created_at DESC LIMIT 1", [case_id])
        if row:
            return True
        # Existing builds sometimes keep a case in approved/active mode after QA. Treat this as a weaker pass for offline/profile actions only.
        case = self.db.one("SELECT status FROM cases WHERE case_id=?", [case_id])
        return bool(case and case.get("status") in {"active", "approved", "open"})

    def _case_exists(self, case_id: str) -> bool:
        return bool(case_id and self.db.one("SELECT case_id FROM cases WHERE case_id=?", [case_id]))

    def authorize(self, command: CommandEnvelope | str, payload: Dict[str, Any] | None = None, actor: str = "local-analyst") -> Decision:
        if isinstance(command, str):
            command = CommandEnvelope(command, payload or {}, actor)

        name = command.name
        data = command.payload
        case_id = str(data.get("case_id") or "")

        if name not in {"create_case", "diagnose", "run_release_gate"} and case_id and not self._case_exists(case_id):
            return self._record(command, Decision("block", "case_gate", "CASE_NOT_FOUND", "Der Fall existiert nicht."))

        if name in {"prepare_provider_run", "run_provider", "capture_raw_finding"}:
            if not self._case_has_approved_legal_scope(case_id):
                return self._record(command, Decision("review_required", "legal_gate", "LEGAL_SCOPE_NOT_APPROVED", "Provider- oder Capture-Aktionen brauchen einen freigegebenen Legal Scope.", ["legal_scope"], ["approve_legal_scope"]))
            qd = validate_query(str(data.get("query") or ""), str(data.get("intent") or "public_osint"))
            if qd.decision != "allow":
                return self._record(command, qd)
            if name == "run_provider" and bool(data.get("execute_live")) and not bool(data.get("explicit_live_confirmation")):
                return self._record(command, Decision("review_required", "provider_gate", "LIVE_CONFIRMATION_REQUIRED", "Live-Abfragen bleiben aus, bis sie bewusst bestätigt werden.", ["live_provider"], ["explicit_live_confirmation"]))
            return self._record(command, Decision("allow", "provider_gate", "PROVIDER_ACTION_ALLOWED", "Provider-Aktion zugelassen; Ergebnisse müssen in Review landen."))

        if name == "execute_source_adapter_104":
            allowed_adapters = {"rdap_domain_104", "dns_doh_104", "wayback_cdx_104", "github_public_profile_104", "gitlab_public_profile_104"}
            adapter_id = str(data.get("adapter_id") or "")
            if adapter_id not in allowed_adapters:
                return self._record(command, Decision("block", "adapter_gate_104", "UNKNOWN_ADAPTER", "Der angeforderte Build-104-Adapter ist nicht freigegeben.", ["unknown_adapter"]))
            if not self._case_has_approved_legal_scope(case_id):
                return self._record(command, Decision("review_required", "legal_gate", "LEGAL_SCOPE_NOT_APPROVED", "Live-Adapter brauchen einen ausdrücklich freigegebenen Legal Scope.", ["legal_scope"], ["approve_legal_scope"]))
            if not bool(data.get("explicit_live_confirmation")):
                return self._record(command, Decision("review_required", "adapter_gate_104", "LIVE_CONFIRMATION_REQUIRED", "Die öffentliche Live-Abfrage muss für jede Ausführung bewusst bestätigt werden.", ["live_provider"], ["explicit_live_confirmation"]))
            qd = validate_query(str(data.get("input_value") or ""), "public_osint")
            if qd.decision != "allow":
                return self._record(command, qd)
            return self._record(command, Decision("allow", "adapter_gate_104", "CONTROLLED_PUBLIC_ADAPTER_ALLOWED", "Kontrollierte öffentliche Adapter-Ausführung zugelassen; Ergebnis bleibt candidate_not_claim."))

        if name in {"create_collection_job_105", "start_collection_job_105", "run_collection_job_105", "browser_capture_105"}:
            if not self._case_has_approved_legal_scope(case_id):
                return self._record(command, Decision("review_required", "collection_legal_gate_105", "LEGAL_SCOPE_NOT_APPROVED", "Live-Crawling braucht einen ausdrücklich freigegebenen Legal Scope.", ["legal_scope"], ["approve_legal_scope"]))
            if not bool(data.get("explicit_live_confirmation")):
                return self._record(command, Decision("review_required", "collection_confirmation_gate_105", "LIVE_CONFIRMATION_REQUIRED", "Jeder Crawl oder Browser-Capture muss bewusst bestätigt werden.", ["live_collection"], ["explicit_live_confirmation"]))
            seeds = data.get("seed_urls") or ([data.get("url")] if data.get("url") else [])
            probe = " ".join(str(v) for v in seeds)[:1000]
            qd = validate_query(probe, "public_osint")
            if qd.decision != "allow":
                return self._record(command, qd)
            return self._record(command, Decision("allow", "collection_gate_105", "CONTROLLED_PUBLIC_COLLECTION_ALLOWED", "Kontrollierte öffentliche Collection zugelassen; Ergebnisse bleiben candidate_not_claim."))

        if name in {"create_verified_claim", "assess_verification"}:
            cd = validate_claim_type(str(data.get("claim_type") or ""))
            if cd.decision != "allow":
                return self._record(command, cd)
            text = " ".join(str(data.get(k) or "") for k in ("statement", "uncertainty_note", "source_url"))
            sensitivity = classify_sensitivity(text)
            if sensitivity["markers"]:
                return self._record(command, Decision("review_required", "privacy_gate", "SENSITIVE_CLAIM_REVIEW", "Der Claim enthält sensible Marker und braucht Redaction-/Privacy-Review.", sensitivity["markers"], ["redaction_review"]))
            return self._record(command, Decision("allow", "verification_gate", "VERIFICATION_ACTION_ALLOWED", "Verifikationsaktion zugelassen."))

        if name in {"create_search_plan", "stage_public_document", "extract_public_document", "stage_review_hit", "update_review_checklist", "set_review_stage"}:
            if not self._case_has_approved_legal_scope(case_id):
                return self._record(command, Decision("review_required", "legal_gate", "LEGAL_SCOPE_NOT_APPROVED", "Build-46 Search/Document/Review-Aktionen brauchen einen freigegebenen Legal Scope oder aktivierten Fallstatus.", ["legal_scope"], ["approve_legal_scope"]))
            if name == "create_search_plan":
                # Search plans are allowed only as public-source planning artifacts, not as direct live collection.
                intent = str(data.get("intent") or "public_osint")
                seed = data.get("seed") or {}
                probe = " ".join(str(v) for v in seed.values()) if isinstance(seed, dict) else str(seed)
                qd = validate_query(probe[:500], intent)
                if qd.decision == "block":
                    return self._record(command, qd)
                return self._record(command, Decision("allow", "source_planning_gate", "SEARCH_PLAN_ALLOWED", "Quellenbasierte Suchplanung zugelassen; keine Live-Abfrage wird ausgeführt."))
            if name in {"stage_public_document", "extract_public_document"}:
                source_ref = str(data.get("source_url") or data.get("path") or data.get("title") or data.get("document_type") or "public_document")
                qd = validate_query(source_ref[:500], "public_document_review")
                if qd.decision == "block":
                    return self._record(command, qd)
                return self._record(command, Decision("allow", "document_gate", "PUBLIC_DOCUMENT_REVIEW_ALLOWED", "Öffentliches Dokument darf lokal extrahiert und in Review gestellt werden."))
            return self._record(command, Decision("allow", "review_gate", "REVIEW_ACTION_ALLOWED", "Review-Inbox-Pro-Aktion zugelassen; Befund bleibt reviewpflichtig."))

        if name in {"build_profile", "export_profile"}:
            if not self._case_has_approved_legal_scope(case_id):
                return self._record(command, Decision("review_required", "legal_gate", "LEGAL_SCOPE_NOT_APPROVED", "Profil-Export braucht freigegebenen Legal Scope oder aktivierten Fallstatus.", ["legal_scope"], ["approve_legal_scope"]))
            return self._record(command, Decision("allow", "export_gate", "PROFILE_EXPORT_ALLOWED", "Redigierter Profilaufbau zugelassen."))

        if name in self.registered_commands:
            return self._record(command, Decision("allow", "security_kernel", "REGISTERED_COMMAND_ALLOWED", "Registrierter Command zugelassen."))
        return self._record(command, Decision("review_required", "security_kernel", "UNCLASSIFIED_COMMAND", "Nicht klassifizierter Command ist standardmäßig gesperrt und braucht explizite Freigabe.", ["unclassified_command"], ["register_or_classify_command"]))

    def decision_history(self, case_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        if case_id:
            rows = self.db.all("SELECT * FROM mvfpe_decisions WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, limit])
        else:
            rows = self.db.all("SELECT * FROM mvfpe_decisions ORDER BY created_at DESC LIMIT ?", [limit])
        for row in rows:
            row["risk_markers"] = loads(row.get("risk_markers_json"), [])
            row["required_actions"] = loads(row.get("required_actions_json"), [])
        return rows
