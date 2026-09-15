from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

EMERGENCY_CONTACTS = [
    {"label": "Polizei", "number": "110", "purpose": "Akute Gefahr, Entführung, Straftat, unmittelbare Vermisstenlage"},
    {"label": "Rettungsdienst / Feuerwehr", "number": "112", "purpose": "medizinische Notlage oder unmittelbare Gefahr"},
    {"label": "Hotline Vermisste Kinder", "number": "116000", "purpose": "Unterstützung bei vermissten Kindern, Hinweise und Beratung"},
]


class MissingChildWorkflowService:
    """Build 50 emergency workflow for missing-child cases.

    It creates a structured situation brief. It never creates a private suspect profile and
    keeps the focus on confirmed last-sighting facts, official/public sources and authority handover.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS missing_child_cases_50 (
          missing_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          child_name TEXT NOT NULL,
          age_hint TEXT DEFAULT '',
          last_seen_time TEXT NOT NULL,
          last_seen_place TEXT NOT NULL,
          last_confirmed_by TEXT DEFAULT '',
          clothing_description TEXT DEFAULT '',
          risk_notes TEXT DEFAULT '',
          official_refs_json TEXT NOT NULL,
          public_notice_urls_json TEXT NOT NULL,
          open_questions_json TEXT NOT NULL,
          status TEXT DEFAULT 'active',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_missing50_case ON missing_child_cases_50(case_id, created_at);
        ''')
        self.db.conn.commit()

    def register(self, case_id: str, child_name: str, last_seen_time: str, last_seen_place: str, *, age_hint: str = "", last_confirmed_by: str = "", clothing_description: str = "", risk_notes: str = "", official_refs: List[str] | None = None, public_notice_urls: List[str] | None = None, open_questions: List[str] | None = None) -> Dict[str, Any]:
        if not child_name.strip() or not last_seen_time.strip() or not last_seen_place.strip():
            raise ValueError("child_name, last_seen_time and last_seen_place are required.")
        missing_id = new_id("miss50")
        ts = now_ts()
        self.db.execute('''INSERT INTO missing_child_cases_50(missing_id,case_id,child_name,age_hint,last_seen_time,last_seen_place,last_confirmed_by,clothing_description,risk_notes,official_refs_json,public_notice_urls_json,open_questions_json,status,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [missing_id, case_id, child_name.strip(), age_hint, last_seen_time, last_seen_place, last_confirmed_by, clothing_description, risk_notes, dumps(official_refs or []), dumps(public_notice_urls or []), dumps(open_questions or []), "active", ts, ts])
        self.audit.log("register", "missing_child_case_50", missing_id, case_id, {"child_name": child_name, "last_seen_place": last_seen_place})
        return self.get(missing_id)

    def get(self, missing_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM missing_child_cases_50 WHERE missing_id=?", [missing_id])
        if not row:
            raise KeyError(missing_id)
        for key in ["official_refs_json", "public_notice_urls_json", "open_questions_json"]:
            row[key.replace("_json", "")] = loads(row.pop(key, "[]"), [])
        row["emergency_contacts"] = EMERGENCY_CONTACTS
        return row

    def latest_for_case(self, case_id: str) -> Dict[str, Any] | None:
        row = self.db.one("SELECT missing_id FROM missing_child_cases_50 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        return self.get(row["missing_id"]) if row else None

    def build_situation_brief(self, case_id: str) -> Dict[str, Any]:
        item = self.latest_for_case(case_id)
        if not item:
            raise KeyError("No missing-child emergency record for case.")
        timeline = [
            {"time": item["last_seen_time"], "event": "Letzte bestätigte Sichtung", "place": item["last_seen_place"], "confirmed_by": item.get("last_confirmed_by", "")},
        ]
        open_questions = item.get("open_questions", []) or [
            "Welche Sichtung ist sicher bestätigt?",
            "Welche Zeitlücke besteht zwischen letzter Sichtung und Meldung?",
            "Welche öffentlichen/behördlichen Meldungen existieren bereits?",
        ]
        brief = {
            "brief_type": "missing_child_situation_brief",
            "case_id": case_id,
            "missing_id": item["missing_id"],
            "emergency_contacts": EMERGENCY_CONTACTS,
            "core_facts": {
                "child_name": item["child_name"],
                "age_hint": item.get("age_hint", ""),
                "last_seen_time": item["last_seen_time"],
                "last_seen_place": item["last_seen_place"],
                "clothing_description": item.get("clothing_description", ""),
            },
            "timeline": timeline,
            "official_refs": item.get("official_refs", []),
            "public_notice_urls": item.get("public_notice_urls", []),
            "open_questions": open_questions,
            "guardrails": [
                "Keine private Verdächtigung oder Täteransprache.",
                "Keine Veröffentlichung privater Adressen/Telefonnummern.",
                "Polizei/Notruf und 116000 haben Vorrang vor Eigenrecherche.",
            ],
            "created_at": now_ts(),
        }
        self.audit.log("build_brief", "missing_child_situation_brief_50", item["missing_id"], case_id, {"brief_type": brief["brief_type"]})
        return brief
