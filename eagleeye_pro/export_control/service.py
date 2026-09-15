from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.core.database import Database, dumps, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.evidence.service import EvidenceService
from eagleeye_pro.legal.service import LegalGateService

class ExportControlService:
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def evaluate_export(self, case_id: str, report_type: str="client_report", reviewer: str="local-analyst", notes: str="") -> Dict[str, Any]:
        issues: List[str] = []
        legal = LegalGateService(self.db, self.audit).evaluate_case(case_id)
        if not legal.get("ok"):
            issues.extend(["Legal Gate nicht erfüllt: " + i for i in legal.get("issues", [])])
        manifest = EvidenceService(self.db, self.audit).verify_manifest(case_id)
        if not manifest.get("ok"):
            issues.append("Evidence Manifest ist nicht sauber.")
        sensitive = self.db.all("SELECT COUNT(*) AS n FROM evidence_items WHERE case_id=? AND redaction_required=1 AND export_allowed=0", [case_id])[0]["n"]
        if sensitive:
            issues.append(f"{sensitive} Evidence Items benötigen Redaction oder Exportfreigabe.")
        candidates = self.db.all("SELECT COUNT(*) AS n FROM identity_candidates WHERE case_id=? AND status='candidate'", [case_id])[0]["n"]
        if candidates:
            issues.append(f"{candidates} Identity Candidates sind noch nicht analystisch entschieden.")
        try:
            from eagleeye_pro.privacy.service import LegalPrivacyHardeningService
            privacy_eval = LegalPrivacyHardeningService(self.db, self.audit).evaluate_privacy_export(case_id, report_type)
            if privacy_eval.get("decision") == "blocked":
                issues.extend(["Privacy Export Blocker: " + b.get("description", "") for b in privacy_eval.get("blockers", [])])
            elif privacy_eval.get("decision") == "review_required":
                issues.extend(["Privacy Review erforderlich: " + b.get("description", "") for b in privacy_eval.get("blockers", [])])
        except Exception as exc:
            issues.append(f"Privacy Hardening konnte nicht geprüft werden: {exc}")
        decision = "approved" if not issues else "blocked"
        eid = new_id("export")
        self.db.execute("""INSERT INTO export_reviews(export_id,case_id,report_type,decision,issues_json,reviewer,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?)""", [eid,case_id,report_type,decision,dumps(issues),reviewer,now_ts(),notes])
        self.audit.log("evaluate", "export_review", eid, case_id, {"decision": decision, "issues": issues})
        return {"export_id": eid, "decision": decision, "issues": issues, "report_type": report_type}

    def list_reviews(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM export_reviews WHERE case_id=? ORDER BY created_at DESC", [case_id])
