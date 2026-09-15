from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import quote_plus

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

REGISTER_PATHS = {
    "civil_registry_archive": {"label": "Personenstandsarchive", "risk": "high", "review": True, "queries": ["Geburtsregister", "Heiratsregister", "Sterberegister", "Personenstandsarchiv"]},
    "church_register": {"label": "Kirchen-/Tauf-/Trauungsregister", "risk": "medium_high", "review": True, "queries": ["Kirchenbuch", "Taufe", "Trauung", "Begräbnis", "Archion"]},
    "newspaper_archive": {"label": "Zeitungsarchive", "risk": "medium", "review": True, "queries": ["Zeitungsportal", "Deutsche Digitale Bibliothek", "Pressebericht", "Nachruf"]},
    "court_public": {"label": "Gerichts-/Justizquellen", "risk": "high", "review": True, "queries": ["Urteil", "Beschluss", "Aktenzeichen", "Justiz"]},
    "company_register": {"label": "Handels-/Unternehmensregister", "risk": "medium_high", "review": True, "queries": ["Handelsregister", "Unternehmensregister", "Bundesanzeiger", "Jahresabschluss"]},
    "association_register": {"label": "Vereinsregister", "risk": "medium", "review": True, "queries": ["Vereinsregister", "Satzung", "Vorstand", "Amtsgericht"]},
    "insolvency_gazette": {"label": "Insolvenz/Amtsblatt/Bekanntmachung", "risk": "medium_high", "review": True, "queries": ["Insolvenz", "Amtsblatt", "Bekanntmachung", "Vergabe", "Zuwendung"]},
}

class RegisterArchiveIntelligenceService:
    """Build 57.2 – Register & Archive Intelligence.

    Generates structured, review-first source paths for registers/archives. It
    does not scrape protected portals; it prepares lawful, manual/public search
    paths and records source intent, risk and expected evidence.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS register_archive_paths_57_2 (
          path_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT DEFAULT '',
          source_key TEXT NOT NULL,
          label TEXT NOT NULL,
          query TEXT NOT NULL,
          url TEXT NOT NULL,
          risk_level TEXT NOT NULL,
          expected_evidence TEXT NOT NULL,
          manual_review_required INTEGER DEFAULT 1,
          status TEXT DEFAULT 'planned',
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def build_paths(self, case_id: str, entity: Dict[str, Any], *, source_keys: List[str] | None = None) -> Dict[str, Any]:
        entity_id = entity.get("entity_id", "")
        name = entity.get("display_name") or entity.get("name") or ""
        places = entity.get("places") or []
        orgs = entity.get("organizations") or []
        dates = entity.get("dates") or []
        if isinstance(places, str): places = [places]
        if isinstance(orgs, str): orgs = [orgs]
        if isinstance(dates, str): dates = [dates]
        keys = source_keys or list(REGISTER_PATHS)
        created: List[Dict[str, Any]] = []
        for key in keys:
            profile = REGISTER_PATHS.get(key)
            if not profile:
                continue
            anchors = [name] + places[:2] + orgs[:2] + dates[:2]
            anchor_text = " ".join(a for a in anchors if a).strip()
            for qpart in profile["queries"][:4]:
                query = f'"{name}" "{qpart}" {" ".join(places[:1])}'.strip() if name else qpart
                url = f"https://www.google.com/search?q={quote_plus(query)}"
                pid = new_id("rap572")
                self.db.execute("INSERT INTO register_archive_paths_57_2(path_id,case_id,entity_id,source_key,label,query,url,risk_level,expected_evidence,manual_review_required,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", [pid, case_id, entity_id, key, profile["label"], query, url, profile["risk"], f"Öffentlicher Kandidat aus {profile['label']}; Anker: {anchor_text}", 1, "planned", now_ts()])
                created.append(self.get_path(pid))
        self.audit.log("create", "register_archive_paths_57_2", entity_id or case_id, case_id, {"paths": len(created)})
        return {"case_id": case_id, "entity_id": entity_id, "path_count": len(created), "paths": created}

    def mark_path_status(self, path_id: str, status: str) -> Dict[str, Any]:
        if status not in {"planned", "opened", "found", "not_relevant", "included", "review_required"}:
            raise ValueError("unsupported path status")
        self.db.execute("UPDATE register_archive_paths_57_2 SET status=? WHERE path_id=?", [status, path_id])
        path = self.get_path(path_id)
        self.audit.log("update", "register_archive_path_status_57_2", path_id, path["case_id"], {"status": status})
        return path

    def get_path(self, path_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM register_archive_paths_57_2 WHERE path_id=?", [path_id])
        if not row:
            raise KeyError(path_id)
        row["manual_review_required"] = bool(row.get("manual_review_required"))
        return row

    def list_paths(self, case_id: str, entity_id: str = "", limit: int = 300) -> List[Dict[str, Any]]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM register_archive_paths_57_2 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for r in rows:
            r["manual_review_required"] = bool(r.get("manual_review_required"))
        return rows

    def dashboard(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        paths = self.list_paths(case_id, entity_id, limit=500)
        by_source: Dict[str, int] = {}; by_status: Dict[str, int] = {}
        for p in paths:
            by_source[p["source_key"]] = by_source.get(p["source_key"], 0) + 1
            by_status[p["status"]] = by_status.get(p["status"], 0) + 1
        return {"case_id": case_id, "entity_id": entity_id, "path_count": len(paths), "by_source": by_source, "by_status": by_status, "paths": paths}
