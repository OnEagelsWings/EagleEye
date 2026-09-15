from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

SESSION_PHASES = [
    ("identity_anchor", "Identitätsanker", "Name, Ort, Zeitraum und Namensvarianten absichern."),
    ("organization_context", "Organisationsbezug", "Person + Organisation/Rolle/Impressum/Register prüfen."),
    ("public_documents", "Öffentliche Dokumente", "PDFs, Amtsblätter, Archive, Presse und öffentliche Dokumente prüfen."),
    ("court_registry", "Gericht/Register", "Amtliche Verfahren, Register, Gerichts- und Verfahrensbezüge prüfen."),
    ("network_finance", "Netzwerk/Finanzen", "Firmen-, Vereins-, Förder-, Insolvenz- und Netzwerkbezüge prüfen."),
    ("images_media", "Bilder/Medien", "Bild-/Medienkontext nur als prüfpflichtigen Hinweis erfassen."),
    ("counter_doppler", "Gegenprüfung/Namensdoppler", "Namensdoppler, Gegenbelege und Widersprüche aktiv prüfen."),
    ("report_prepare", "Berichtsvorbereitung", "Claims, offene Fragen und exportfähige Aussagen konsolidieren."),
]

PHASE_CATEGORIES = {
    "identity_anchor": "person_core",
    "organization_context": "person_organization",
    "public_documents": "person_public_data",
    "court_registry": "person_legal",
    "network_finance": "person_networks",
    "images_media": "person_images",
    "counter_doppler": "person_core",
    "report_prepare": "person_core",
}

class DeepResearchSessionService:
    """Build 56.3 – guided deep-research session mode.

    Drives an analyst through a deterministic, category-aware research sequence.
    It proposes the next phase based on missing anchors, low precision, absent
    claims or unresolved doppler risks.
    """

    def __init__(self, db: Database, audit: AuditService, search_quality=None, query_optimizer=None, entity_resolution=None, claim_builder=None):
        self.db = db
        self.audit = audit
        self.search_quality = search_quality
        self.query_optimizer = query_optimizer
        self.entity_resolution = entity_resolution
        self.claim_builder = claim_builder
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS deep_research_sessions_56_3 (
          session_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          status TEXT NOT NULL,
          current_phase TEXT NOT NULL,
          objective TEXT NOT NULL,
          metrics_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS deep_research_phase_runs_56_3 (
          phase_run_id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          phase_key TEXT NOT NULL,
          category_key TEXT NOT NULL,
          status TEXT NOT NULL,
          actions_json TEXT NOT NULL,
          result_json TEXT NOT NULL,
          started_at TEXT NOT NULL,
          completed_at TEXT DEFAULT ''
        );
        ''')
        self.db.conn.commit()

    def start_session(self, case_id: str, entity_id: str, *, objective: str = "Präzise öffentliche Personen-/Organisationsrecherche") -> Dict[str, Any]:
        sid = new_id("drs563")
        now = now_ts()
        metrics = {"phase_count": len(SESSION_PHASES), "completed": 0, "recommendation": "identity_anchor"}
        self.db.execute("INSERT INTO deep_research_sessions_56_3(session_id,case_id,entity_id,status,current_phase,objective,metrics_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", [sid, case_id, entity_id, "active", "identity_anchor", objective, dumps(metrics), now, now])
        self.audit.log("create", "deep_research_session_56_3", sid, case_id, {"entity_id": entity_id})
        return self.get_session(sid)

    def run_phase(self, session_id: str, phase_key: str | None = None) -> Dict[str, Any]:
        session = self.get_session(session_id)
        phase_key = phase_key or session["current_phase"]
        if phase_key not in PHASE_CATEGORIES:
            raise ValueError("unsupported phase")
        category = PHASE_CATEGORIES[phase_key]
        actions: List[str] = []
        result: Dict[str, Any] = {}
        if self.search_quality:
            pyramid = self.search_quality.build_query_pyramid(session["case_id"], self._entity_payload(session["case_id"], session["entity_id"]), category, max_per_level=3)
            result["query_count"] = pyramid.get("query_count", 0); actions.append("query_pyramid_built")
        if phase_key in {"identity_anchor", "counter_doppler"} and self.entity_resolution:
            er = self.entity_resolution.assess_ranked_results(session["case_id"], session["entity_id"], limit=30)
            result["entity_resolution"] = er.get("assessment_count", 0); actions.append("entity_resolution_assessed")
        if phase_key in {"organization_context", "public_documents", "court_registry", "network_finance"} and self.query_optimizer:
            opt = self.query_optimizer.optimize_entity_queries(session["case_id"], session["entity_id"])
            result["query_reviews"] = opt.get("review_count", 0); actions.append("queries_optimized")
        if phase_key == "report_prepare" and self.claim_builder:
            claims = self.claim_builder.build_claims_from_person_findings(session["case_id"], session["entity_id"])
            result["claims"] = claims.get("claim_count", 0); actions.append("claims_built")
        rid = new_id("drp563")
        now = now_ts()
        self.db.execute("INSERT INTO deep_research_phase_runs_56_3(phase_run_id,session_id,case_id,entity_id,phase_key,category_key,status,actions_json,result_json,started_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", [rid, session_id, session["case_id"], session["entity_id"], phase_key, category, "completed", dumps(actions), dumps(result), now, now])
        next_phase = self.recommend_next_phase(session_id, after_phase=phase_key)["next_phase"]
        self.db.execute("UPDATE deep_research_sessions_56_3 SET current_phase=?, updated_at=? WHERE session_id=?", [next_phase, now, session_id])
        self.audit.log("run", "deep_research_phase_56_3", rid, session["case_id"], {"phase": phase_key, "next": next_phase})
        return {"phase_run_id": rid, "session_id": session_id, "phase_key": phase_key, "category_key": category, "actions": actions, "result": result, "next_phase": next_phase}

    def recommend_next_phase(self, session_id: str, *, after_phase: str = "") -> Dict[str, Any]:
        session = self.get_session(session_id)
        completed = {r["phase_key"] for r in self.phase_runs(session_id)}
        if after_phase:
            completed.add(after_phase)
        # priority: finish current sequence, but revisit counter_doppler if risk flags exist
        next_key = "report_prepare"
        for key, _, _ in SESSION_PHASES:
            if key not in completed:
                next_key = key; break
        if self._doppler_risk(session["case_id"], session["entity_id"]) and "counter_doppler" not in completed:
            next_key = "counter_doppler"
        phase_meta = next((p for p in SESSION_PHASES if p[0] == next_key), SESSION_PHASES[-1])
        return {"session_id": session_id, "next_phase": next_key, "label": phase_meta[1], "reason": phase_meta[2], "category_key": PHASE_CATEGORIES.get(next_key, "person_core")}

    def dashboard(self, case_id: str, entity_id: str = "") -> Dict[str, Any]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM deep_research_sessions_56_3 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY updated_at DESC LIMIT 30"
        sessions = self.db.all(sql, params)
        for s in sessions:
            s["metrics"] = loads(s.pop("metrics_json", "{}"), {})
            s["phase_runs"] = self.phase_runs(s["session_id"])
        return {"case_id": case_id, "entity_id": entity_id, "sessions": sessions, "session_count": len(sessions)}

    def get_session(self, session_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM deep_research_sessions_56_3 WHERE session_id=?", [session_id])
        if not row:
            raise KeyError(session_id)
        row["metrics"] = loads(row.pop("metrics_json", "{}"), {})
        return row

    def phase_runs(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM deep_research_phase_runs_56_3 WHERE session_id=? ORDER BY started_at", [session_id])
        for r in rows:
            r["actions"] = loads(r.pop("actions_json", "[]"), [])
            r["result"] = loads(r.pop("result_json", "{}"), {})
        return rows


    def _entity_payload(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_entities_54 WHERE case_id=? AND entity_id=?", [case_id, entity_id])
        if row:
            for key in ["known_names", "aliases", "dates", "places", "organizations", "roles", "identifiers", "public_links"]:
                row[key] = loads(row.pop(f"{key}_json", "[]"), [])
            return row
        target = self.db.one("SELECT * FROM targets WHERE case_id=? AND target_id=?", [case_id, entity_id])
        if target:
            return {"entity_id": target["target_id"], "display_name": target.get("name", ""), "known_names": [target.get("name", "")], "aliases": loads(target.get("aliases_json"), []), "places": loads(target.get("locations_json"), []), "organizations": loads(target.get("companies_json"), []), "roles": [], "identifiers": [], "public_links": []}
        return {"entity_id": entity_id, "display_name": entity_id}

    def _doppler_risk(self, case_id: str, entity_id: str) -> bool:
        if not self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='entity_resolution_assessments_55_7'", []):
            return False
        row = self.db.one("SELECT COUNT(*) AS c FROM entity_resolution_assessments_55_7 WHERE case_id=? AND entity_id=? AND doppler_risk_label LIKE '%hoch%' OR doppler_risk_label LIKE '%mittel%'", [case_id, entity_id])
        return bool(row and row.get("c"))
