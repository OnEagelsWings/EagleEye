from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.core.database import Database, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

PRO_WORKFLOW_TEMPLATE = [
    ("01 Intake", "Auftrag, Mandant, Zweck und Grenzen dokumentieren", "LEGAL_GATE"),
    ("02 Legal Gate", "Rechtsgrundlage, Erforderlichkeit und Interessenabwägung prüfen", "LEGAL_GATE_PASS"),
    ("03 Target Anchors", "Zielperson und bekannte Ankerdaten erfassen", "TARGET_EXISTS"),
    ("04 Source Plan", "Quellenkategorien und Provider festlegen", "SOURCE_SCOPE"),
    ("05 Search Workbench", "Suchpakete/Dorks erzeugen und kontrolliert ausführen", "QUERY_POLICY"),
    ("06 Review Inbox", "Treffer prüfen, ablehnen oder als Lead akzeptieren", "HUMAN_REVIEW"),
    ("07 Evidence Vault", "belastbare Treffer mit Hash und Chain-of-Custody sichern", "EVIDENCE_MANIFEST"),
    ("08 Identity Resolution", "Kandidaten und Namensdoppler mit positiven/negativen Markern bewerten", "NO_AUTO_IDENTITY"),
    ("09 Graph & Timeline", "Beziehungen und Ereignisse quellenbezogen modellieren", "SOURCE_BACKED_GRAPH"),
    ("10 Risk Assessment", "Risiken, Unsicherheiten und Gegenbelege erfassen", "ANALYST_DECISION"),
    ("11 Report Builder", "Mandantenbericht und interne Arbeitsakte erzeugen", "EXPORT_REVIEW"),
    ("12 Retention", "Lösch- und Archivierungsfrist kontrollieren", "RETENTION_POLICY"),
]

class WorkflowService:
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def initialize_case_workflow(self, case_id: str, owner: str="analyst") -> int:
        existing = self.db.one("SELECT COUNT(*) AS n FROM workflow_steps WHERE case_id=?", [case_id])
        if existing and existing.get("n", 0) > 0:
            return int(existing["n"])
        ts = now_ts()
        for phase, title, gate in PRO_WORKFLOW_TEMPLATE:
            self.db.execute("""INSERT INTO workflow_steps(step_id,case_id,phase,title,status,owner,gate_required,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)""", [new_id("step"), case_id, phase, title, "todo", owner, gate, ts, ts])
        self.audit.log("initialize", "workflow", case_id, case_id, {"steps": len(PRO_WORKFLOW_TEMPLATE)})
        return len(PRO_WORKFLOW_TEMPLATE)

    def update_step(self, step_id: str, status: str, notes: str="", output_object_type: str="", output_object_id: str="") -> Dict[str, Any]:
        if status not in ("todo", "in_progress", "blocked", "done", "needs_review"):
            raise ValueError("Ungültiger Workflow-Status.")
        row = self.db.one("SELECT * FROM workflow_steps WHERE step_id=?", [step_id])
        if not row:
            raise KeyError("Workflow-Schritt nicht gefunden.")
        self.db.execute("""UPDATE workflow_steps SET status=?, notes=?, output_object_type=?, output_object_id=?, updated_at=? WHERE step_id=?""",
                        [status, notes or row.get("notes", ""), output_object_type or row.get("output_object_type", ""), output_object_id or row.get("output_object_id", ""), now_ts(), step_id])
        self.audit.log("status_update", "workflow_step", step_id, row["case_id"], {"status": status})
        return self.db.one("SELECT * FROM workflow_steps WHERE step_id=?", [step_id])

    def list_steps(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM workflow_steps WHERE case_id=? ORDER BY phase ASC", [case_id])

    def progress(self, case_id: str) -> Dict[str, Any]:
        rows = self.list_steps(case_id)
        total = len(rows)
        done = len([r for r in rows if r.get("status") == "done"])
        blocked = len([r for r in rows if r.get("status") == "blocked"])
        return {"total": total, "done": done, "blocked": blocked, "percent": round((done / total) * 100, 1) if total else 0.0}
