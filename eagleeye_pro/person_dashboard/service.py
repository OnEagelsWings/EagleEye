from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, now_ts

SEARCH_CATEGORIES = ["person_core", "person_organization", "person_images", "person_public_personal_data", "person_court", "person_networks", "person_finance"]


class PersonResearchDashboardService:
    """Build 60.4: central person/organization research dashboard."""

    def __init__(self, db: Database, audit: AuditService, *, person_detail=None, fund_intelligence=None, entity_resolution=None, osint_core=None):
        self.db = db
        self.audit = audit
        self.person_detail = person_detail
        self.fund_intelligence = fund_intelligence
        self.entity_resolution = entity_resolution
        self.osint_core = osint_core

    def dashboard(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        page = self.person_detail.build_person_page(case_id, entity_id) if self.person_detail else {"entity": {"entity_id": entity_id}, "findings": [], "narratives": [], "metrics": {}}
        findings = page.get("findings", [])
        intelligence = self.fund_intelligence.list_intelligence(case_id, entity_id) if self.fund_intelligence else []
        fits = self.entity_resolution.list_assessments(case_id, entity_id) if self.entity_resolution else []
        clusters = self.entity_resolution.doppler_clusters(case_id, entity_id) if self.entity_resolution else {"clusters": {}, "counts": {}}
        sessions = self.osint_core.list_sessions(case_id, entity_id, limit=3) if self.osint_core else []
        latest_core = None
        if sessions and self.osint_core:
            latest_core = self.osint_core.dashboard(sessions[0]["session_id"])
        category_progress = self._category_progress(findings, intelligence)
        top_findings = sorted(findings, key=lambda f: (self._finding_score(f, intelligence, fits), f.get("updated_at", "")), reverse=True)[:10]
        claims = (latest_core or {}).get("claims", []) if latest_core else []
        next_actions = self.next_actions(case_id, entity_id, findings=findings, fits=fits, category_progress=category_progress, core=latest_core)
        status = self._status_ampel(page, findings, fits, claims, category_progress)
        return {
            "build": "60.4/61.0",
            "generated_at": now_ts(),
            "case_id": case_id,
            "entity_id": entity_id,
            "entity": page.get("entity", {}),
            "metrics": {
                "finding_count": len(findings),
                "intelligence_count": len(intelligence),
                "fit_assessment_count": len(fits),
                "claim_count": len(claims),
                "doppler_high": clusters.get("counts", {}).get("likely_other", 0),
                "narrative_count": len(page.get("narratives", [])),
            },
            "status_ampel": status,
            "category_progress": category_progress,
            "top_findings": top_findings,
            "doppler_clusters": clusters,
            "claims": claims[:20],
            "next_actions": next_actions,
            "latest_core": latest_core,
        }

    def next_actions(self, case_id: str, entity_id: str, *, findings: List[Dict[str, Any]] | None = None, fits: List[Dict[str, Any]] | None = None, category_progress: Dict[str, Any] | None = None, core: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        findings = findings if findings is not None else (self.person_detail.list_findings(case_id, entity_id) if self.person_detail else [])
        fits = fits if fits is not None else (self.entity_resolution.list_assessments(case_id, entity_id) if self.entity_resolution else [])
        category_progress = category_progress if category_progress is not None else self._category_progress(findings, [])
        actions: List[Dict[str, Any]] = []
        for cat, data in category_progress.items():
            if data["count"] == 0:
                actions.append({"priority": 75, "type": "missing_category", "title": f"Kategorie prüfen: {cat}", "rationale": "Noch keine Funde in dieser Suchkategorie."})
        if any(f.get("doppler_label") == "hoch" for f in fits):
            actions.append({"priority": 95, "type": "doppler_review", "title": "Namensdoppler hart gegenprüfen", "rationale": "Mindestens ein Treffer hat hohes Doppler-Risiko."})
        if not any(f.get("status") == "report_ready" for f in findings):
            actions.append({"priority": 70, "type": "report_readiness", "title": "berichtsfähige Funde markieren", "rationale": "Noch kein Fund ist für den Bericht freigegeben."})
        if core:
            for a in core.get("next_actions", [])[:5]:
                actions.append({"priority": int(a.get("priority", 50)), "type": a.get("action_type", "core_next_action"), "title": a.get("title", "nächste Suchaktion"), "query": a.get("query", ""), "rationale": a.get("rationale", "")})
        return sorted(actions, key=lambda x: -int(x.get("priority", 0)))[:12]

    def _category_progress(self, findings: List[Dict[str, Any]], intelligence: List[Dict[str, Any]]) -> Dict[str, Any]:
        out = {c: {"count": 0, "report_ready": 0, "needs_review": 0} for c in SEARCH_CATEGORIES}
        for f in findings:
            cat = f.get("category") or "unknown"
            key = cat if cat in out else "other"
            out.setdefault(key, {"count": 0, "report_ready": 0, "needs_review": 0})
            out[key]["count"] += 1
            if f.get("status") == "report_ready": out[key]["report_ready"] += 1
            if f.get("status") in {"needs_review", "counter_evidence"}: out[key]["needs_review"] += 1
        for i in intelligence:
            cat = i.get("chain_origin", {}).get("category_key") or i.get("source_type") or "unknown"
            key = cat if cat in out else "other"
            out.setdefault(key, {"count": 0, "report_ready": 0, "needs_review": 0})
        return out

    def _finding_score(self, finding: Dict[str, Any], intelligence: List[Dict[str, Any]], fits: List[Dict[str, Any]]) -> int:
        score = 30
        if finding.get("status") == "report_ready": score += 30
        if finding.get("status") == "included": score += 20
        if finding.get("evidence_level") in {"strong_indicator", "verified_public_fact"}: score += 20
        fid = finding.get("finding_note_id")
        for i in intelligence:
            if i.get("person_finding_id") == fid: score += int(i.get("relevance_score", 0)) // 4
        for fit in fits:
            if fit.get("object_id") == fid:
                score += int(fit.get("identity_fit", 0)) // 4
                score -= int(fit.get("doppler_risk", 0)) // 5
        return score

    def _status_ampel(self, page: Dict[str, Any], findings: List[Dict[str, Any]], fits: List[Dict[str, Any]], claims: List[Dict[str, Any]], progress: Dict[str, Any]) -> Dict[str, str]:
        ent = page.get("entity", {})
        return {
            "grunddaten": "grün" if ent.get("display_name") else "rot",
            "funde": "grün" if len(findings) >= 5 else ("gelb" if findings else "rot"),
            "doppler": "grün" if fits and not any(f.get("doppler_label") == "hoch" for f in fits) else ("gelb" if fits else "rot"),
            "claims": "grün" if len(claims) >= 3 else ("gelb" if claims else "rot"),
            "bericht": "grün" if page.get("narratives") else "gelb",
            "kategorien": "grün" if sum(1 for v in progress.values() if v["count"] > 0) >= 4 else "gelb",
        }
