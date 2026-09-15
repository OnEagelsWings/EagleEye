from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.core.database import Database, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

class RiskService:
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def add_finding(self, case_id: str, category: str, severity: str, title: str, rationale: str, source_evidence_id: str="", status: str="candidate") -> Dict[str, Any]:
        if severity not in ("info", "low", "medium", "high", "critical"):
            raise ValueError("Ungültige Severity.")
        fid=new_id("risk")
        self.db.execute("""INSERT INTO risk_findings(finding_id,case_id,category,severity,title,rationale,source_evidence_id,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)""", [fid,case_id,category,severity,title,rationale,source_evidence_id,status,now_ts()])
        self.audit.log("create", "risk_finding", fid, case_id, {"category": category, "severity": severity, "title": title})
        return self.db.one("SELECT * FROM risk_findings WHERE finding_id=?", [fid])

    def auto_assess_case(self, case_id: str) -> Dict[str, Any]:
        findings_added=0
        sensitive=self.db.all("SELECT * FROM review_items WHERE case_id=? AND sensitivity_level='high'", [case_id])
        blocked=self.db.all("SELECT * FROM review_items WHERE case_id=? AND status IN ('conflicting','sensitive','export_blocked')", [case_id])
        evidence=self.db.all("SELECT * FROM evidence_items WHERE case_id=?", [case_id])
        if sensitive and not self.db.one("SELECT finding_id FROM risk_findings WHERE case_id=? AND category='sensitive_data'", [case_id]):
            self.add_finding(case_id, "sensitive_data", "high", "Sensible Treffer im Review", f"{len(sensitive)} Treffer sind als sensibel markiert. Export nur nach Redaction/Legal-Review.")
            findings_added+=1
        if blocked and not self.db.one("SELECT finding_id FROM risk_findings WHERE case_id=? AND category='conflict_or_block'", [case_id]):
            self.add_finding(case_id, "conflict_or_block", "medium", "Konflikte oder Export-Blocker vorhanden", f"{len(blocked)} Treffer haben Konflikt-/Blockerstatus.")
            findings_added+=1
        if not evidence and not self.db.one("SELECT finding_id FROM risk_findings WHERE case_id=? AND category='weak_evidence'", [case_id]):
            self.add_finding(case_id, "weak_evidence", "medium", "Keine promovierte Evidence", "Der Fall enthält noch keine beweissicher promovierten Evidence Items.")
            findings_added+=1
        return {"findings_added": findings_added, "findings": self.list_findings(case_id)}

    def list_findings(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM risk_findings WHERE case_id=? ORDER BY CASE severity WHEN 'critical' THEN 5 WHEN 'high' THEN 4 WHEN 'medium' THEN 3 WHEN 'low' THEN 2 ELSE 1 END DESC, created_at DESC", [case_id])
