from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.core.database import Database, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

class ComplianceService:
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def set_retention_policy(self, case_id: str, retention_until: str, reason: str, deletion_mode: str="review_required") -> Dict[str, Any]:
        pid = new_id("ret")
        self.db.execute("""INSERT INTO retention_policies(policy_id,case_id,retention_until,deletion_mode,reason,created_at)
        VALUES(?,?,?,?,?,?)""", [pid, case_id, retention_until, deletion_mode, reason, now_ts()])
        self.db.execute("UPDATE cases SET retention_until=?, updated_at=? WHERE case_id=?", [retention_until, now_ts(), case_id])
        self.audit.log("set", "retention_policy", pid, case_id, {"retention_until": retention_until, "deletion_mode": deletion_mode})
        return self.db.one("SELECT * FROM retention_policies WHERE policy_id=?", [pid])

    def compliance_dashboard(self, case_id: str) -> Dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id])
        legal = self.db.one("SELECT * FROM legal_reviews WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        evidence_count = self.db.one("SELECT COUNT(*) AS n FROM evidence_items WHERE case_id=?", [case_id])["n"]
        redaction_open = self.db.one("SELECT COUNT(*) AS n FROM evidence_items WHERE case_id=? AND redaction_required=1 AND export_allowed=0", [case_id])["n"]
        review_open = self.db.one("SELECT COUNT(*) AS n FROM review_items WHERE case_id=? AND status IN ('new','in_review','sensitive','conflicting')", [case_id])["n"]
        export_blocked = self.db.one("SELECT COUNT(*) AS n FROM export_reviews WHERE case_id=? AND decision='blocked'", [case_id])["n"]
        return {
            "case_status": case.get("status") if case else "missing",
            "legal_approved": bool(legal and legal.get("approved")),
            "retention_until": case.get("retention_until") if case else "",
            "evidence_count": evidence_count,
            "redaction_open": redaction_open,
            "review_open": review_open,
            "blocked_exports": export_blocked,
            "overall": "ready_for_internal_review" if legal and legal.get("approved") and evidence_count else "needs_work",
        }

    def list_retention_policies(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM retention_policies WHERE case_id=? ORDER BY created_at DESC", [case_id])
