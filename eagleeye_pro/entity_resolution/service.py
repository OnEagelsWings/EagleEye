from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class EntityResolutionProService:
    """Build 55.7: entity fit and name-doppler resolution layer."""

    def __init__(self, db: Database, audit: AuditService, search_quality=None):
        self.db = db
        self.audit = audit
        self.search_quality = search_quality
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS entity_resolution_assessments_55_7 (
          assessment_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          result_id TEXT NOT NULL,
          identity_fit_label TEXT NOT NULL,
          identity_fit_score INTEGER DEFAULT 0,
          doppler_risk_label TEXT NOT NULL,
          doppler_risk_score INTEGER DEFAULT 0,
          contradictions_json TEXT NOT NULL,
          matched_anchors_json TEXT NOT NULL,
          recommended_action TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_entity_resolution_557_entity ON entity_resolution_assessments_55_7(case_id, entity_id, created_at DESC);
        ''')
        self.db.conn.commit()

    def assess_result(self, result_id: str) -> Dict[str, Any]:
        if not self.search_quality:
            raise RuntimeError("SearchQualityEngineService is required")
        result = self.search_quality.get_result(result_id)
        fp = self.search_quality.get_fingerprint(result["case_id"], result["entity_id"])["fingerprint"]
        text = f"{result.get('title','')} {result.get('snippet','')} {result.get('url','')}".lower()
        matched = []
        for field in ["places", "organizations", "roles", "dates", "identifiers", "domain_anchors"]:
            for val in fp.get(field, []) or []:
                if str(val).lower() in text:
                    matched.append({"field": field, "value": val})
        contradictions = []
        for place in ["berlin", "hamburg", "münchen", "munich", "frankfurt", "köln", "cologne", "leipzig", "dresden"]:
            if place in text and not any(place in str(p).lower() for p in fp.get("places", []) or []):
                if fp.get("places"):
                    contradictions.append({"type": "place_mismatch_hint", "value": place})
        score = int(result.get("entity_match_score") or 0)
        doppler = 0
        flags = result.get("flags", [])
        if "name_doppler_risk" in flags:
            doppler += 35
        if "missing_context_anchor" in flags:
            doppler += 25
        if contradictions:
            doppler += 25
        if score >= 75 and doppler < 25:
            fit_label = "hoher Identitätsfit"; action = "als starker Kandidat prüfen"
        elif score >= 55 and doppler < 45:
            fit_label = "mittlerer Identitätsfit"; action = "zweite Quelle oder Zusatzanker prüfen"
        elif score >= 35:
            fit_label = "unklarer Identitätsfit"; action = "Namensdoppler-/Kontextprüfung erforderlich"
        else:
            fit_label = "vermutlich andere Person"; action = "nur als Gegenprüfung oder verwerfen nutzen"
        doppler_label = "niedrig" if doppler < 25 else "mittel" if doppler < 55 else "hoch"
        aid = new_id("er557")
        self.db.execute('''INSERT INTO entity_resolution_assessments_55_7(assessment_id,case_id,entity_id,result_id,identity_fit_label,identity_fit_score,doppler_risk_label,doppler_risk_score,contradictions_json,matched_anchors_json,recommended_action,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', [aid, result["case_id"], result["entity_id"], result_id, fit_label, score, doppler_label, min(doppler, 100), dumps(contradictions), dumps(matched), action, now_ts()])
        self.audit.log("assess", "entity_resolution_55_7", aid, result["case_id"], {"result_id": result_id, "fit": fit_label, "doppler": doppler_label})
        return self.get_assessment(aid)

    def assess_ranked_results(self, case_id: str, entity_id: str, limit: int = 25) -> Dict[str, Any]:
        if not self.search_quality:
            raise RuntimeError("SearchQualityEngineService is required")
        out = []
        for r in self.search_quality.ranked_results(case_id, entity_id=entity_id, limit=limit):
            out.append(self.assess_result(r["result_id"]))
        return {"case_id": case_id, "entity_id": entity_id, "assessment_count": len(out), "assessments": out}

    def get_assessment(self, assessment_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM entity_resolution_assessments_55_7 WHERE assessment_id=?", [assessment_id])
        if not row:
            raise KeyError(assessment_id)
        row["contradictions"] = loads(row.pop("contradictions_json", "[]"), [])
        row["matched_anchors"] = loads(row.pop("matched_anchors_json", "[]"), [])
        return row

    def latest_assessments(self, case_id: str, entity_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM entity_resolution_assessments_55_7 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for r in rows:
            r["contradictions"] = loads(r.pop("contradictions_json", "[]"), [])
            r["matched_anchors"] = loads(r.pop("matched_anchors_json", "[]"), [])
        return rows
