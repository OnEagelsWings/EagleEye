from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts


class EvidenceMatrixClaimBuilderService:
    """Build 55.9: turns reviewed findings/results into reportable claims."""

    def __init__(self, db: Database, audit: AuditService, person_detail=None, search_quality=None, entity_resolution=None):
        self.db = db
        self.audit = audit
        self.person_detail = person_detail
        self.search_quality = search_quality
        self.entity_resolution = entity_resolution
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS research_claims_55_9 (
          claim_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          claim_type TEXT NOT NULL,
          statement TEXT NOT NULL,
          confidence_label TEXT NOT NULL,
          evidence_count INTEGER DEFAULT 0,
          counter_evidence_count INTEGER DEFAULT 0,
          reportability TEXT NOT NULL,
          sensitivity_label TEXT NOT NULL,
          evidence_refs_json TEXT NOT NULL,
          uncertainty_notes TEXT DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_research_claims_559_entity ON research_claims_55_9(case_id, entity_id, created_at DESC);
        ''')
        self.db.conn.commit()

    def build_claims_from_person_findings(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        if not self.person_detail:
            raise RuntimeError("PersonDetailPageService required")
        findings = self.person_detail.list_findings(case_id, entity_id)
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for f in findings:
            key = self._claim_type(f.get("category") or f.get("finding_type"))
            groups.setdefault(key, []).append(f)
        claims = []
        for ctype, rows in groups.items():
            include = [r for r in rows if r.get("status") in {"included", "reportable", "relevant", "candidate", "review_required"}]
            counter = [r for r in rows if r.get("status") == "counter_evidence"]
            if not include and not counter:
                continue
            statement = self._statement_for(ctype, include, counter)
            confidence = "strong_public_indicator" if len(include) >= 2 else "weak_public_indicator" if include else "counter_evidence"
            sensitivity = "sensitive_review" if any(r.get("redaction_required") for r in include + counter) else "normal"
            reportability = "reportable_with_redaction" if sensitivity == "sensitive_review" else "reportable_with_uncertainty"
            claim = self.create_claim(case_id, entity_id, ctype, statement, confidence_label=confidence, evidence_refs=include, counter_evidence_count=len(counter), reportability=reportability, sensitivity_label=sensitivity, uncertainty_notes="Manuelle Prüfung und Quellenkontext erforderlich; keine automatische Identitäts-/Schuldbehauptung.")
            claims.append(claim)
        return {"case_id": case_id, "entity_id": entity_id, "claim_count": len(claims), "claims": claims}

    def create_claim(self, case_id: str, entity_id: str, claim_type: str, statement: str, *, confidence_label: str = "weak_public_indicator", evidence_refs: List[Dict[str, Any]] | None = None, counter_evidence_count: int = 0, reportability: str = "internal_only", sensitivity_label: str = "normal", uncertainty_notes: str = "") -> Dict[str, Any]:
        evidence_refs = evidence_refs or []
        cid = new_id("claim559")
        now = now_ts()
        refs = [{"finding_note_id": r.get("finding_note_id", ""), "title": r.get("title", ""), "source_url": r.get("source_url", ""), "status": r.get("status", ""), "evidence_level": r.get("evidence_level", "")} for r in evidence_refs]
        self.db.execute('''INSERT INTO research_claims_55_9(claim_id,case_id,entity_id,claim_type,statement,confidence_label,evidence_count,counter_evidence_count,reportability,sensitivity_label,evidence_refs_json,uncertainty_notes,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [cid, case_id, entity_id, claim_type, statement.strip(), confidence_label, len(refs), counter_evidence_count, reportability, sensitivity_label, dumps(refs), uncertainty_notes, now, now])
        self.audit.log("create", "research_claim_55_9", cid, case_id, {"entity_id": entity_id, "type": claim_type, "evidence_count": len(refs)})
        return self.get_claim(cid)

    def list_claims(self, case_id: str, entity_id: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        params: List[Any] = [case_id]
        sql = "SELECT * FROM research_claims_55_9 WHERE case_id=?"
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY evidence_count DESC, updated_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for r in rows:
            r["evidence_refs"] = loads(r.pop("evidence_refs_json", "[]"), [])
        return rows

    def get_claim(self, claim_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM research_claims_55_9 WHERE claim_id=?", [claim_id])
        if not row:
            raise KeyError(claim_id)
        row["evidence_refs"] = loads(row.pop("evidence_refs_json", "[]"), [])
        return row

    def evidence_matrix(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        claims = self.list_claims(case_id, entity_id)
        rows = []
        for c in claims:
            rows.append({
                "claim": c["statement"], "type": c["claim_type"], "confidence": c["confidence_label"],
                "evidence_count": c["evidence_count"], "counter_evidence_count": c["counter_evidence_count"],
                "reportability": c["reportability"], "sensitivity": c["sensitivity_label"],
                "sources": [r.get("source_url", "") for r in c.get("evidence_refs", []) if r.get("source_url")],
            })
        return {"case_id": case_id, "entity_id": entity_id, "claim_count": len(claims), "matrix": rows}

    def _claim_type(self, category: str) -> str:
        c = (category or "").lower()
        if "legal" in c or "court" in c or "gericht" in c:
            return "gerichts_oder_verfahrenshinweis"
        if "finance" in c or "finanz" in c or "insolv" in c:
            return "finanz_registerhinweis"
        if "network" in c or "company" in c or "firma" in c:
            return "netzwerk_organisationshinweis"
        if "image" in c or "bild" in c:
            return "bild_medienhinweis"
        if "personal" in c or "person" in c:
            return "oeffentliche_personeninformation"
        if "organization" in c or "org" in c:
            return "organisationsbezug"
        return "oeffentlicher_hinweis"

    def _statement_for(self, claim_type: str, include: List[Dict[str, Any]], counter: List[Dict[str, Any]]) -> str:
        if include:
            titles = "; ".join(r.get("title", "") for r in include[:3] if r.get("title"))
            return f"Öffentliche Funde stützen einen {claim_type.replace('_', ' ')}. Relevante Quellen: {titles}."
        return f"Es liegen Gegenbelege oder widersprüchliche Hinweise zum Bereich {claim_type.replace('_', ' ')} vor."
