from __future__ import annotations

from typing import Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database


class ProfessionalUXPolishService:
    """Build 61.2: compact UX wording and workflow health checks."""

    FRIENDLY = {
        "No entity context": "Bitte zuerst eine Person oder Organisation auswählen.",
        "entity_id is required": "Bitte zuerst eine Person oder Organisation auswählen.",
        "case_id is required": "Bitte zuerst einen Fall anlegen oder auswählen.",
        "raw SERP text is required": "Bitte Suchergebnis-Text aus dem Browser einfügen.",
        "title and url are required": "Bitte Titel und öffentliche URL des Treffers einfügen.",
    }

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def humanize_error(self, message: str) -> str:
        for raw, nice in self.FRIENDLY.items():
            if raw.lower() in str(message).lower():
                return nice
        return str(message)

    def workflow_health(self, case_id: str, entity_id: str = "") -> Dict[str, object]:
        checks: List[Dict[str, str]] = []
        case_ok = bool(self.db.one("SELECT case_id FROM cases WHERE case_id=?", [case_id])) if case_id else False
        checks.append({"check": "Fall ausgewählt", "status": "ok" if case_ok else "missing"})
        if entity_id:
            ent_ok = bool(self.db.one("SELECT entity_id FROM investigation_entities_54 WHERE entity_id=?", [entity_id]))
        else:
            ent_ok = False
        checks.append({"check": "Person/Organisation ausgewählt", "status": "ok" if ent_ok else "missing"})
        findings = self.db.one("SELECT COUNT(*) c FROM person_finding_notes_55_4 WHERE case_id=? AND (?='' OR entity_id=?)", [case_id, entity_id, entity_id]) if case_ok else {"c": 0}
        checks.append({"check": "Funde dokumentiert", "status": "ok" if int(findings.get("c", 0)) > 0 else "open"})
        return {"build": "61.2", "case_id": case_id, "entity_id": entity_id, "checks": checks, "ready": all(c["status"] == "ok" for c in checks[:2])}
