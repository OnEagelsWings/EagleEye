from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

DEFAULT_ALLOWED = ["Suchmaschinen", "öffentliche Webseiten", "Presse/Archive", "Register", "öffentliche Firmenprofile", "öffentliche Fachprofile"]
DEFAULT_PROHIBITED = ["private Accounts", "Login-Umgehung", "Captcha-Bypass", "private Kommunikation", "heimliche Überwachung", "Doxxing"]

class LegalGateService:
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def create_review(self, case_id: str, purpose: str, legal_basis: str, necessity: str, balancing: str,
                      source_scope: List[str] | None = None, prohibited_scope: List[str] | None = None,
                      special_categories: bool=False, minor_data: bool=False, criminal_data: bool=False,
                      approved: bool=False, review_level: str="analyst", reviewer: str="local-analyst", notes: str="") -> Dict[str, Any]:
        rid = new_id("legal")
        self.db.execute("""INSERT INTO legal_reviews(review_id,case_id,purpose,legal_basis,necessity,balancing,source_scope_json,prohibited_scope_json,special_categories,minor_data,criminal_data,approved,review_level,created_at,reviewer,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [rid,case_id,purpose,legal_basis,necessity,balancing,dumps(source_scope or DEFAULT_ALLOWED),dumps(prohibited_scope or DEFAULT_PROHIBITED),int(special_categories),int(minor_data),int(criminal_data),int(approved),review_level,now_ts(),reviewer,notes])
        self.audit.log("create", "legal_review", rid, case_id, {"approved": approved, "review_level": review_level})
        if approved:
            self.db.execute("UPDATE cases SET status=?, updated_at=? WHERE case_id=?", ["active", now_ts(), case_id])
            self.audit.log("activate", "case", case_id, case_id, {"via": rid})
        return self.get_latest(case_id)

    def get_latest(self, case_id: str) -> Dict[str, Any] | None:
        row = self.db.one("SELECT * FROM legal_reviews WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if row:
            row["source_scope_json"] = loads(row.get("source_scope_json"), [])
            row["prohibited_scope_json"] = loads(row.get("prohibited_scope_json"), [])
        return row

    def evaluate_case(self, case_id: str) -> Dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id])
        if not case:
            return {"ok": False, "gate": "CASE_NOT_FOUND"}
        latest = self.get_latest(case_id)
        issues = []
        if not case.get("purpose"):
            issues.append("Zweck fehlt.")
        if not case.get("legal_basis"):
            issues.append("Rechtsgrundlage fehlt.")
        if not latest:
            issues.append("Legal-Gate-Prüfung fehlt.")
        else:
            if not latest.get("necessity"):
                issues.append("Erforderlichkeitsprüfung fehlt.")
            if not latest.get("balancing"):
                issues.append("Interessenabwägung fehlt.")
            if latest.get("special_categories") or latest.get("minor_data") or latest.get("criminal_data"):
                if latest.get("review_level") not in ("senior", "legal", "dpo"):
                    issues.append("Sensible Daten erfordern Senior-/Legal-Review.")
            if not latest.get("approved"):
                issues.append("Fall ist noch nicht freigegeben.")
        return {"ok": not issues, "gate": "LEGAL_GATE_PASS" if not issues else "LEGAL_GATE_REVIEW", "issues": issues, "case": case, "latest_review": latest}
