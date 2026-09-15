from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class PersonWorkspaceProService:
    """Build 56.1 – Personenakte Pro II.

    Aggregates identity anchors, documented findings, ranked results, claims,
    open questions and export readiness into one person/entity workspace. The
    service deliberately stays review-first: it highlights reportability but does
    not turn findings into facts automatically.
    """

    def __init__(self, db: Database, audit: AuditService, person_detail=None, search_quality=None, claim_builder=None, entity_resolution=None):
        self.db = db
        self.audit = audit
        self.person_detail = person_detail
        self.search_quality = search_quality
        self.claim_builder = claim_builder
        self.entity_resolution = entity_resolution
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS person_workspace_snapshots_56_1 (
          snapshot_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          readiness_score INTEGER DEFAULT 0,
          readiness_label TEXT NOT NULL,
          open_questions_json TEXT NOT NULL,
          metrics_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def build_workspace(self, case_id: str, entity_id: str, *, persist_snapshot: bool = True) -> Dict[str, Any]:
        entity = self._entity(case_id, entity_id)
        findings = self._findings(case_id, entity_id)
        narratives = self._narratives(case_id, entity_id)
        ranked_results = self._ranked_results(case_id, entity_id)
        claims = self._claims(case_id, entity_id)
        resolutions = self._resolutions(case_id, entity_id)
        fingerprint = self._fingerprint(case_id, entity_id)
        open_questions = self._open_questions(entity, findings, claims, resolutions)
        metrics = self._metrics(entity, findings, narratives, ranked_results, claims, resolutions, fingerprint)
        readiness_score, readiness_label = self._readiness(metrics, open_questions)
        snapshot = {
            "case_id": case_id,
            "entity_id": entity_id,
            "entity": entity,
            "fingerprint": fingerprint,
            "findings": findings,
            "narratives": narratives,
            "ranked_results": ranked_results,
            "claims": claims,
            "entity_resolutions": resolutions,
            "open_questions": open_questions,
            "metrics": metrics,
            "readiness_score": readiness_score,
            "readiness_label": readiness_label,
            "status_lanes": self._status_lanes(findings, claims),
        }
        if persist_snapshot:
            snapshot_id = new_id("pws561")
            self.db.execute(
                "INSERT INTO person_workspace_snapshots_56_1(snapshot_id,case_id,entity_id,readiness_score,readiness_label,open_questions_json,metrics_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                [snapshot_id, case_id, entity_id, readiness_score, readiness_label, dumps(open_questions), dumps(metrics), now_ts()],
            )
            snapshot["snapshot_id"] = snapshot_id
            self.audit.log("snapshot", "person_workspace_pro_56_1", snapshot_id, case_id, {"entity_id": entity_id, "readiness": readiness_label, "score": readiness_score})
        return snapshot

    def latest_snapshots(self, case_id: str, entity_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM person_workspace_snapshots_56_1 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for row in rows:
            row["open_questions"] = loads(row.pop("open_questions_json", "[]"), [])
            row["metrics"] = loads(row.pop("metrics_json", "{}"), {})
        return rows

    def _entity(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_entities_54 WHERE entity_id=? AND case_id=?", [entity_id, case_id])
        if not row:
            target = self.db.one("SELECT * FROM targets WHERE target_id=? AND case_id=?", [entity_id, case_id])
            if not target:
                raise KeyError(entity_id)
            return {"entity_id": target["target_id"], "case_id": case_id, "entity_type": "person", "display_name": target.get("name", ""), "known_names": [target.get("name", "")], "aliases": loads(target.get("aliases_json"), []), "places": loads(target.get("locations_json"), []), "organizations": loads(target.get("companies_json"), []), "roles": [], "public_links": []}
        for key in ["known_names", "aliases", "dates", "places", "organizations", "roles", "identifiers", "public_links"]:
            row[key] = loads(row.pop(f"{key}_json", "[]"), [])
        return row

    def _findings(self, case_id: str, entity_id: str) -> List[Dict[str, Any]]:
        if self.person_detail:
            return self.person_detail.list_findings(case_id, entity_id, limit=500)
        return []

    def _narratives(self, case_id: str, entity_id: str) -> List[Dict[str, Any]]:
        if self.person_detail:
            return self.person_detail.list_narratives(case_id, entity_id, limit=50)
        return []

    def _ranked_results(self, case_id: str, entity_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM search_quality_results_55_5 WHERE case_id=? AND entity_id=? ORDER BY total_score DESC, updated_at DESC LIMIT 100", [case_id, entity_id])
        for r in rows:
            r["flags"] = loads(r.pop("flags_json", "[]"), [])
        return rows

    def _claims(self, case_id: str, entity_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM research_claims_55_9 WHERE case_id=? AND entity_id=? ORDER BY created_at DESC LIMIT 150", [case_id, entity_id]) if self._table_exists("research_claims_55_9") else []
        for r in rows:
            r["evidence_refs"] = loads(r.pop("evidence_refs_json", "[]"), [])
            r["uncertainties"] = [r.get("uncertainty_notes", "")] if r.get("uncertainty_notes") else []
            r["claim_label"] = r.get("confidence_label", "")
            r["claim_text"] = r.get("statement", "")
        return rows

    def _resolutions(self, case_id: str, entity_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM entity_resolution_assessments_55_7 WHERE case_id=? AND entity_id=? ORDER BY created_at DESC LIMIT 100", [case_id, entity_id]) if self._table_exists("entity_resolution_assessments_55_7") else []
        for r in rows:
            r["anchor_hits"] = loads(r.pop("matched_anchors_json", "[]"), [])
            r["contradictions"] = loads(r.pop("contradictions_json", "[]"), [])
        return rows

    def _fingerprint(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM search_quality_fingerprints_55_5 WHERE case_id=? AND entity_id=?", [case_id, entity_id]) if self._table_exists("search_quality_fingerprints_55_5") else None
        return loads(row.get("fingerprint_json"), {}) if row else {}

    def _open_questions(self, entity: Dict[str, Any], findings: List[Dict[str, Any]], claims: List[Dict[str, Any]], resolutions: List[Dict[str, Any]]) -> List[str]:
        questions: List[str] = []
        if not entity.get("places"):
            questions.append("Ortsanker fehlen: gezielt nach Ort/Region/letztem bekannten Kontext suchen.")
        if not entity.get("organizations"):
            questions.append("Organisationsanker fehlen: Person + Verein/Firma/Gemeinde/Arbeitgeber prüfen.")
        if not findings:
            questions.append("Noch keine dokumentierten Funde in der Personenakte.")
        if not claims:
            questions.append("Noch keine geprüften Claims aus Funden gebildet.")
        if not resolutions:
            questions.append("Entity-Resolution/Namensdoppler-Prüfung noch nicht durchgeführt.")
        if any(r.get("identity_fit_label") in {"name_doppler_risk", "likely_other_person"} for r in resolutions):
            questions.append("Namensdoppler-Risiko vorhanden: Gegenprüfung vor Export erforderlich.")
        if not any(f.get("status") in {"included", "report_ready"} for f in findings):
            questions.append("Keine inkludierten/berichtsfähigen Funde markiert.")
        return questions

    def _metrics(self, entity: Dict[str, Any], findings: List[Dict[str, Any]], narratives: List[Dict[str, Any]], ranked_results: List[Dict[str, Any]], claims: List[Dict[str, Any]], resolutions: List[Dict[str, Any]], fingerprint: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "finding_count": len(findings),
            "report_ready_findings": sum(1 for f in findings if f.get("status") == "report_ready"),
            "included_findings": sum(1 for f in findings if f.get("status") == "included"),
            "counter_evidence": sum(1 for f in findings if f.get("status") == "counter_evidence"),
            "narrative_count": len(narratives),
            "ranked_result_count": len(ranked_results),
            "strong_ranked_results": sum(1 for r in ranked_results if int(r.get("total_score") or 0) >= 70),
            "claim_count": len(claims),
            "reportable_claims": sum(1 for c in claims if c.get("reportability") in {"reportable", "reportable_with_redaction", "authority_only"}),
            "entity_resolution_count": len(resolutions),
            "doppler_risks": sum(1 for r in resolutions if "doppler" in str(r.get("identity_label", ""))),
            "fingerprint_fields": len([k for k, v in fingerprint.items() if v]),
            "anchor_completeness": sum(1 for k in ["display_name", "places", "organizations", "roles", "public_links"] if entity.get(k))
        }

    def _readiness(self, metrics: Dict[str, Any], open_questions: List[str]) -> tuple[int, str]:
        score = 20
        score += min(20, metrics.get("included_findings", 0) * 5)
        score += min(15, metrics.get("strong_ranked_results", 0) * 3)
        score += min(20, metrics.get("reportable_claims", 0) * 5)
        score += 10 if metrics.get("entity_resolution_count", 0) else 0
        score += 10 if metrics.get("narrative_count", 0) else 0
        score += min(5, metrics.get("anchor_completeness", 0))
        score -= min(20, len(open_questions) * 3)
        score -= min(20, metrics.get("doppler_risks", 0) * 7)
        score = max(0, min(100, score))
        if score >= 85:
            return score, "arbeitsbereit / reportnah"
        if score >= 65:
            return score, "solide, aber Prüfpunkte offen"
        if score >= 40:
            return score, "Research unvollständig"
        return score, "früher Arbeitsstand"

    def _status_lanes(self, findings: List[Dict[str, Any]], claims: List[Dict[str, Any]]) -> Dict[str, Any]:
        lanes: Dict[str, List[Dict[str, Any]]] = {"fakten_hinweise": [], "review": [], "gegenbelege": [], "nicht_exportfaehig": []}
        for f in findings:
            if f.get("status") in {"included", "report_ready"}:
                lanes["fakten_hinweise"].append(f)
            elif f.get("status") == "counter_evidence":
                lanes["gegenbelege"].append(f)
            elif f.get("status") == "discarded":
                lanes["nicht_exportfaehig"].append(f)
            else:
                lanes["review"].append(f)
        for c in claims:
            if c.get("claim_label") == "counter_evidence":
                lanes["gegenbelege"].append(c)
            elif c.get("reportability") in {"not_reportable", "blocked"}:
                lanes["nicht_exportfaehig"].append(c)
            elif c.get("confidence_label") in {"verified_public_fact", "strong_public_indicator"} or c.get("reportability") in {"reportable_with_uncertainty", "reportable_with_redaction", "authority_only"}:
                lanes["fakten_hinweise"].append(c)
            else:
                lanes["review"].append(c)
        return lanes

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))
