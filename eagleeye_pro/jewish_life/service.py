from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

INCIDENT_TYPES = {"threat", "insult", "property_damage", "online_hate", "school_context", "synagogue_context", "demonstration_context", "press_public_event", "other"}
ANTISEMITISM_MARKERS = {
    "ns_relativization", "israel_related_antisemitism", "conspiracy_myth", "dehumanization", "violence_threat", "religious_targeting", "shoah_reference", "symbol_or_slogan",
}


class JewishLifeProtectionService:
    """Build 50 incident workflow for antisemitic public incidents and handover."""

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS antisemitism_incidents_50 (
          incident_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          incident_type TEXT NOT NULL,
          title TEXT NOT NULL,
          incident_time TEXT DEFAULT '',
          incident_place TEXT DEFAULT '',
          public_urls_json TEXT NOT NULL,
          evidence_artifacts_json TEXT NOT NULL,
          markers_json TEXT NOT NULL,
          risk_level TEXT DEFAULT 'medium',
          description TEXT DEFAULT '',
          recommended_handover_json TEXT NOT NULL,
          status TEXT DEFAULT 'open',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_antisemitism50_case ON antisemitism_incidents_50(case_id, created_at);
        ''')
        self.db.conn.commit()

    def register_incident(self, case_id: str, incident_type: str, title: str, *, incident_time: str = "", incident_place: str = "", public_urls: List[str] | None = None, evidence_artifacts: List[str] | None = None, markers: List[str] | None = None, risk_level: str = "medium", description: str = "") -> Dict[str, Any]:
        if incident_type not in INCIDENT_TYPES:
            raise ValueError(f"Invalid incident_type: {incident_type}")
        marker_set = sorted(set(markers or []))
        unknown = [m for m in marker_set if m not in ANTISEMITISM_MARKERS]
        if unknown:
            raise ValueError("Unknown antisemitism markers: " + ", ".join(unknown))
        recommended = ["Polizei bei Gefahr/Straftat", "RIAS/report-antisemitism.de für dokumentierende Meldung"]
        if risk_level in {"high", "critical"}:
            recommended.insert(0, "Akute Schutz-/Sicherheitsprüfung")
        incident_id = new_id("as50")
        ts = now_ts()
        self.db.execute('''INSERT INTO antisemitism_incidents_50(incident_id,case_id,incident_type,title,incident_time,incident_place,public_urls_json,evidence_artifacts_json,markers_json,risk_level,description,recommended_handover_json,status,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [incident_id, case_id, incident_type, title.strip(), incident_time, incident_place, dumps(public_urls or []), dumps(evidence_artifacts or []), dumps(marker_set), risk_level, description, dumps(recommended), "open", ts, ts])
        self.audit.log("register", "antisemitism_incident_50", incident_id, case_id, {"incident_type": incident_type, "risk_level": risk_level, "markers": marker_set})
        return self.get_incident(incident_id)

    def get_incident(self, incident_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM antisemitism_incidents_50 WHERE incident_id=?", [incident_id])
        if not row:
            raise KeyError(incident_id)
        for key in ["public_urls_json", "evidence_artifacts_json", "markers_json", "recommended_handover_json"]:
            row[key.replace("_json", "")] = loads(row.pop(key, "[]"), [])
        row["reporting_hint"] = "RIAS/report-antisemitism.de kann für dokumentierende Meldungen genutzt werden; Polizei hat Vorrang bei Gefahr/Straftat."
        return row

    def list_incidents(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT incident_id FROM antisemitism_incidents_50 WHERE case_id=? ORDER BY created_at DESC", [case_id])
        return [self.get_incident(r["incident_id"]) for r in rows]
