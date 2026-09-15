from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

class CaseService:
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def create_case(self, title: str, client: str, purpose: str, legal_basis: str, jurisdiction: str = "DE/EU", risk_level: str = "medium", retention_until: str = "") -> Dict[str, Any]:
        if not title.strip() or not purpose.strip() or not legal_basis.strip():
            raise ValueError("Falltitel, Zweck und Rechtsgrundlage sind Pflichtfelder.")
        cid = new_id("case")
        ts = now_ts()
        self.db.execute("""INSERT INTO cases(case_id,title,client,purpose,legal_basis,jurisdiction,risk_level,status,retention_until,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [cid,title.strip(),client.strip(),purpose.strip(),legal_basis.strip(),jurisdiction,risk_level,"draft",retention_until,ts,ts])
        self.audit.log("create", "case", cid, cid, {"title": title, "purpose": purpose, "legal_basis": legal_basis})
        return self.get_case(cid)

    def update_status(self, case_id: str, status: str) -> None:
        self.db.execute("UPDATE cases SET status=?, updated_at=? WHERE case_id=?", [status, now_ts(), case_id])
        self.audit.log("status_update", "case", case_id, case_id, {"status": status})

    def get_case(self, case_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id])
        if not row:
            raise KeyError(f"Fall nicht gefunden: {case_id}")
        return row

    def list_cases(self) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM cases ORDER BY created_at DESC")

class TargetService:
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    @staticmethod
    def split_csv(text: str) -> List[str]:
        return [x.strip() for x in (text or "").replace(";", ",").split(",") if x.strip()]

    def create_target(self, case_id: str, name: str, aliases: str = "", emails: str = "", usernames: str = "", locations: str = "", companies: str = "", domains: str = "", notes: str = "") -> Dict[str, Any]:
        if not name.strip():
            raise ValueError("Name/Anker der Zielperson ist erforderlich.")
        tid = new_id("target")
        ts = now_ts()
        self.db.execute("""INSERT INTO targets(target_id,case_id,name,aliases_json,emails_json,usernames_json,locations_json,companies_json,domains_json,notes,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", [tid, case_id, name.strip(), dumps(self.split_csv(aliases)), dumps(self.split_csv(emails)), dumps(self.split_csv(usernames)), dumps(self.split_csv(locations)), dumps(self.split_csv(companies)), dumps(self.split_csv(domains)), notes, ts, ts])
        self.audit.log("create", "target", tid, case_id, {"name": name})
        return self.get_target(tid)

    def list_targets(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM targets WHERE case_id=? ORDER BY created_at DESC", [case_id])
        for r in rows:
            for k in ["aliases_json","emails_json","usernames_json","locations_json","companies_json","domains_json"]:
                r[k] = loads(r.get(k), [])
        return rows

    def get_target(self, target_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM targets WHERE target_id=?", [target_id])
        if not row:
            raise KeyError(f"Zielperson nicht gefunden: {target_id}")
        for k in ["aliases_json","emails_json","usernames_json","locations_json","companies_json","domains_json"]:
            row[k] = loads(row.get(k), [])
        return row
