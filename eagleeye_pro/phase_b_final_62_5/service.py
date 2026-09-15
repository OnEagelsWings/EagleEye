from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.redaction_policy import RedactionEngine
from eagleeye_pro.security.export_policy import ExportPolicy

SEARCH_CATEGORIES = [
    "person_core", "person_organization", "person_images",
    "person_public_personal_data", "person_court", "person_networks", "person_finance",
]

CATEGORY_LABELS = {
    "person_core": "Person",
    "person_organization": "Person in Bezug zu Organisation",
    "person_images": "Bilder / Medien",
    "person_public_personal_data": "öffentlich zugängliche personenbezogene Daten",
    "person_court": "amtliche Verfahren / Gerichte",
    "person_networks": "Netzwerke / Firmennetzwerke",
    "person_finance": "öffentlich einsehbare Finanzangaben",
}


def _sha_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value or "akte"))[:90] or "akte"


def _score_label(score: int) -> str:
    if score >= 85: return "grün / einsatzreif"
    if score >= 70: return "gelb-grün / gut, mit Prüfpunkten"
    if score >= 55: return "gelb / prüfbedürftig"
    return "rot / nicht berichtsreif"


class PersonWorkspaceFinal625Service:
    """Phase B 62.4: Final person/organization workspace.

    This service turns existing findings, Phase-A import intelligence, entity-fit gates,
    claims and dashboard signals into one analyst-facing research workspace. It does
    not create facts automatically; it exposes readiness, gaps, warnings and next steps.
    """

    def __init__(self, db: Database, audit: AuditService, *, person_detail=None, dashboard=None, phase_a_fund=None, phase_a_entity=None, osint_core=None):
        self.db = db
        self.audit = audit
        self.person_detail = person_detail
        self.dashboard = dashboard
        self.phase_a_fund = phase_a_fund
        self.phase_a_entity = phase_a_entity
        self.osint_core = osint_core
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS phase_b_workspace_snapshots_62_4 (
          workspace_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          readiness_score INTEGER DEFAULT 0,
          readiness_label TEXT NOT NULL,
          status_json TEXT NOT NULL,
          gaps_json TEXT NOT NULL,
          warnings_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_phaseb_workspace624_entity ON phase_b_workspace_snapshots_62_4(case_id, entity_id, created_at);
        ''')
        self.db.conn.commit()

    def build_workspace(self, case_id: str, entity_id: str, *, persist: bool = True) -> Dict[str, Any]:
        page = self.person_detail.build_person_page(case_id, entity_id) if self.person_detail else {"entity": self._entity(case_id, entity_id), "findings": [], "narratives": [], "metrics": {}}
        dash = self.dashboard.dashboard(case_id, entity_id) if self.dashboard else {}
        fund_profiles = self.phase_a_fund.list_profiles(case_id, entity_id, limit=500) if self.phase_a_fund else []
        fit_assessments = self.phase_a_entity.list_assessments(case_id, entity_id, limit=500) if self.phase_a_entity else []
        claims = self._claims(case_id, entity_id)
        chain = self._chain(case_id, entity_id)
        source_summary = self._source_summary(page.get("findings", []), fund_profiles)
        category_matrix = self._category_matrix(page.get("findings", []), fund_profiles)
        strongest = self._strongest_findings(page.get("findings", []), fund_profiles, fit_assessments)
        warnings = self._warnings(page, fund_profiles, fit_assessments, claims)
        gaps = self._gaps(page, category_matrix, claims, fit_assessments)
        next_steps = self._next_steps(gaps, warnings, dash)
        status = self._status_ampel(page, category_matrix, claims, fit_assessments, warnings)
        readiness = self._readiness(status, strongest, warnings, gaps, claims)
        workspace = {
            "build": "62.4/62.5 Phase B Person Workspace Final",
            "generated_at": now_ts(),
            "case_id": case_id,
            "entity_id": entity_id,
            "entity": page.get("entity", {}),
            "status_ampel": status,
            "readiness_score": readiness,
            "readiness_label": _score_label(readiness),
            "category_matrix": category_matrix,
            "source_summary": source_summary,
            "top_findings": strongest,
            "claim_summary": self._claim_summary(claims),
            "doppler_and_identity": self._identity_summary(fit_assessments),
            "warnings": warnings,
            "open_gaps": gaps,
            "next_steps": next_steps,
            "dashboard": dash,
            "chain_metrics": chain.get("metrics", {}),
            "report_sections": [
                "Kurzfazit", "Identitätsanker", "stärkste Funde", "Claims", "Unsicherheiten/Gegenbelege", "nächste Schritte"
            ],
        }
        if persist:
            workspace_id = new_id("pwsfinal624")
            self.db.execute(
                "INSERT INTO phase_b_workspace_snapshots_62_4(workspace_id,case_id,entity_id,readiness_score,readiness_label,status_json,gaps_json,warnings_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                [workspace_id, case_id, entity_id, readiness, workspace["readiness_label"], dumps(status), dumps(gaps), dumps(warnings), now_ts()],
            )
            workspace["workspace_id"] = workspace_id
            self.audit.log("snapshot", "phase_b_workspace_final_62_4", workspace_id, case_id, {"entity_id": entity_id, "readiness": readiness})
        return workspace

    def latest_snapshots(self, case_id: str, entity_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM phase_b_workspace_snapshots_62_4 WHERE case_id=?"
        params: List[Any] = [case_id]
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for r in rows:
            r["status"] = loads(r.pop("status_json", "{}"), {})
            r["gaps"] = loads(r.pop("gaps_json", "[]"), [])
            r["warnings"] = loads(r.pop("warnings_json", "[]"), [])
        return rows

    def _entity(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_entities_54 WHERE case_id=? AND entity_id=?", [case_id, entity_id]) or {}
        for col in ["known_names_json", "aliases_json", "dates_json", "places_json", "organizations_json", "roles_json", "identifiers_json", "public_links_json"]:
            if col in row:
                row[col.replace("_json", "")] = loads(row.pop(col, "[]"), [])
        return row

    def _claims(self, case_id: str, entity_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM research_claims_55_9 WHERE case_id=? AND entity_id=? ORDER BY created_at DESC LIMIT 250", [case_id, entity_id]) if self._table_exists("research_claims_55_9") else []
        for r in rows:
            if "evidence_refs_json" in r: r["evidence_refs"] = loads(r.pop("evidence_refs_json", "[]"), [])
        return rows

    def _chain(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        nodes = self.db.all("SELECT node_id,node_type,title,value,source_url,status,confidence_label,created_at FROM search_chain_nodes_54 WHERE case_id=? AND entity_id=? ORDER BY created_at", [case_id, entity_id]) if self._table_exists("search_chain_nodes_54") else []
        return {"nodes": nodes, "metrics": {"node_count": len(nodes), "included": sum(1 for n in nodes if n.get("node_type") == "included_fact"), "queries": sum(1 for n in nodes if n.get("node_type") == "search_query")}}

    def _source_summary(self, findings: List[Dict[str, Any]], profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        domains: Dict[str, int] = {}
        for f in findings:
            by_type[f.get("finding_type") or "unknown"] = by_type.get(f.get("finding_type") or "unknown", 0) + 1
            dom = self._domain(f.get("source_url", ""))
            if dom: domains[dom] = domains.get(dom, 0) + 1
        for p in profiles:
            by_type[p.get("source_type") or "unknown"] = by_type.get(p.get("source_type") or "unknown", 0) + 1
        return {"by_type": by_type, "top_domains": sorted(domains.items(), key=lambda x: -x[1])[:10], "source_diversity": len(by_type)}

    def _category_matrix(self, findings: List[Dict[str, Any]], profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        matrix: Dict[str, Dict[str, Any]] = {c: {"label": CATEGORY_LABELS.get(c, c), "findings": 0, "profiles": 0, "report_ready": 0, "review_needed": 0, "sensitive": 0, "score": 0} for c in SEARCH_CATEGORIES}
        for f in findings:
            cat = f.get("category") or "person_core"
            if cat not in matrix: matrix[cat] = {"label": CATEGORY_LABELS.get(cat, cat), "findings": 0, "profiles": 0, "report_ready": 0, "review_needed": 0, "sensitive": 0, "score": 0}
            matrix[cat]["findings"] += 1
            if f.get("status") == "report_ready": matrix[cat]["report_ready"] += 1
            if f.get("status") in {"needs_review", "counter_evidence"}: matrix[cat]["review_needed"] += 1
            if f.get("redaction_required"): matrix[cat]["sensitive"] += 1
        for p in profiles:
            cat = (p.get("claim_proposal") or {}).get("claim_type", "")
            # Map by source type if category is not explicit.
            mapped = self._category_from_source(p.get("source_type", ""), cat)
            if mapped not in matrix: matrix[mapped] = {"label": CATEGORY_LABELS.get(mapped, mapped), "findings": 0, "profiles": 0, "report_ready": 0, "review_needed": 0, "sensitive": 0, "score": 0}
            matrix[mapped]["profiles"] += 1
            if p.get("export_status") == "export_ready": matrix[mapped]["report_ready"] += 1
            if p.get("export_status") != "export_ready": matrix[mapped]["review_needed"] += 1
            if p.get("sensitivity_level") in {"medium", "high"}: matrix[mapped]["sensitive"] += 1
        for data in matrix.values():
            data["score"] = min(100, data["findings"] * 8 + data["profiles"] * 6 + data["report_ready"] * 12 - data["review_needed"] * 3 - data["sensitive"] * 2)
            data["status"] = "grün" if data["report_ready"] else ("gelb" if data["findings"] or data["profiles"] else "offen")
        return matrix

    def _strongest_findings(self, findings: List[Dict[str, Any]], profiles: List[Dict[str, Any]], assessments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        profile_by_finding = {p.get("person_finding_id"): p for p in profiles}
        assessment_by_profile = {a.get("object_id"): a for a in assessments if a.get("object_type") == "fund_final_profile"}
        out: List[Dict[str, Any]] = []
        for f in findings:
            p = profile_by_finding.get(f.get("finding_note_id"), {})
            a = assessment_by_profile.get(p.get("fund_profile_id"), {}) if p else {}
            score = 35
            if f.get("status") == "report_ready": score += 28
            if f.get("status") == "included": score += 18
            if f.get("evidence_level") in {"strong_indicator", "verified_public_fact"}: score += 18
            score += int(p.get("source_quality") or 0) // 5 if p else 0
            score += int(a.get("identity_fit") or 0) // 6 if a else 0
            score -= int(a.get("doppler_risk") or 0) // 8 if a else 0
            out.append({"finding": f, "fund_profile": p, "entity_gate": a, "score": max(0, min(100, score)), "report_gate": a.get("report_gate", "not_checked")})
        return sorted(out, key=lambda x: -x["score"])[:15]

    def _claim_summary(self, claims: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}; reportable = 0
        for c in claims:
            typ = c.get("claim_type") or c.get("claim_label") or "claim"
            by_type[typ] = by_type.get(typ, 0) + 1
            if c.get("reportability") in {"reportable", "reportable_with_redaction", "authority_only"} or c.get("confidence_label") in {"strong", "high"}:
                reportable += 1
        return {"count": len(claims), "reportable": reportable, "by_type": by_type}

    def _identity_summary(self, assessments: List[Dict[str, Any]]) -> Dict[str, Any]:
        gates: Dict[str, int] = {}; max_fit = 0; max_doppler = 0
        required: List[str] = []
        for a in assessments:
            gates[a.get("report_gate", "unknown")] = gates.get(a.get("report_gate", "unknown"), 0) + 1
            max_fit = max(max_fit, int(a.get("identity_fit") or 0)); max_doppler = max(max_doppler, int(a.get("doppler_risk") or 0))
            required.extend(a.get("required_actions", []) or [])
        return {"assessment_count": len(assessments), "gates": gates, "max_identity_fit": max_fit, "max_doppler_risk": max_doppler, "required_actions": sorted(set(required))[:12]}

    def _warnings(self, page: Dict[str, Any], profiles: List[Dict[str, Any]], assessments: List[Dict[str, Any]], claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        warnings: List[Dict[str, Any]] = []
        if any(p.get("export_status") == "blocked_until_redacted" for p in profiles):
            warnings.append({"level": "high", "type": "redaction_block", "text": "Mindestens ein Fund ist bis zur Redaction blockiert."})
        if any(int(a.get("doppler_risk") or 0) >= 60 for a in assessments):
            warnings.append({"level": "high", "type": "doppler", "text": "Hohes Namensdoppler-Risiko vorhanden; Gegenprüfung vor Bericht erforderlich."})
        if not assessments:
            warnings.append({"level": "medium", "type": "identity_fit_missing", "text": "Noch keine finale Identitäts-/Dopplerprüfung durchgeführt."})
        if not claims:
            warnings.append({"level": "medium", "type": "claims_missing", "text": "Noch keine Claims aus Funden gebildet."})
        if not page.get("narratives"):
            warnings.append({"level": "low", "type": "narrative_missing", "text": "Noch kein Fließtext-Ergebnisbericht gespeichert."})
        return warnings

    def _gaps(self, page: Dict[str, Any], matrix: Dict[str, Any], claims: List[Dict[str, Any]], assessments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        gaps: List[Dict[str, Any]] = []
        for cat in SEARCH_CATEGORIES:
            data = matrix.get(cat, {})
            if int(data.get("findings", 0)) + int(data.get("profiles", 0)) == 0:
                gaps.append({"priority": 70, "category": cat, "title": f"Kategorie offen: {CATEGORY_LABELS.get(cat, cat)}", "action": "Suchmission starten oder Treffer importieren."})
        if not claims:
            gaps.append({"priority": 90, "category": "claims", "title": "Claims fehlen", "action": "Aus geprüften Funden Claims bilden."})
        if not assessments:
            gaps.append({"priority": 95, "category": "identity", "title": "Identitätsfit fehlt", "action": "Phase-A-Doppler/Report-Gate ausführen."})
        return sorted(gaps, key=lambda x: -int(x.get("priority", 0)))[:12]

    def _next_steps(self, gaps: List[Dict[str, Any]], warnings: List[Dict[str, Any]], dash: Dict[str, Any]) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        for w in warnings:
            steps.append({"priority": 100 if w["level"] == "high" else 75, "title": w["text"], "source": "warning"})
        for g in gaps[:5]:
            steps.append({"priority": g.get("priority", 50), "title": g.get("action", g.get("title", "Prüfen")), "source": g.get("category", "gap")})
        for a in (dash or {}).get("next_actions", [])[:5]:
            steps.append({"priority": int(a.get("priority", 50)), "title": a.get("title", "nächste Aktion"), "query": a.get("query", ""), "source": a.get("type", "dashboard")})
        return sorted(steps, key=lambda x: -int(x.get("priority", 0)))[:12]

    def _status_ampel(self, page: Dict[str, Any], matrix: Dict[str, Any], claims: List[Dict[str, Any]], assessments: List[Dict[str, Any]], warnings: List[Dict[str, Any]]) -> Dict[str, str]:
        ent = page.get("entity", {})
        covered = sum(1 for c in SEARCH_CATEGORIES if matrix.get(c, {}).get("findings", 0) or matrix.get(c, {}).get("profiles", 0))
        high_warnings = any(w.get("level") == "high" for w in warnings)
        return {
            "grunddaten": "grün" if ent.get("display_name") else "rot",
            "fundlage": "grün" if page.get("metrics", {}).get("finding_count", 0) >= 5 else ("gelb" if page.get("metrics", {}).get("finding_count", 0) else "rot"),
            "suchkategorien": "grün" if covered >= 5 else ("gelb" if covered >= 2 else "rot"),
            "identitätsfit": "grün" if assessments and not high_warnings else ("gelb" if assessments else "rot"),
            "claims": "grün" if len(claims) >= 3 else ("gelb" if claims else "rot"),
            "bericht": "grün" if page.get("narratives") else "gelb",
            "export": "rot" if high_warnings else ("grün" if claims and assessments else "gelb"),
        }

    def _readiness(self, status: Dict[str, str], strongest: List[Dict[str, Any]], warnings: List[Dict[str, Any]], gaps: List[Dict[str, Any]], claims: List[Dict[str, Any]]) -> int:
        score = 45
        score += sum(8 for v in status.values() if v == "grün")
        score += sum(3 for v in status.values() if v == "gelb")
        score += min(12, len(strongest) * 2)
        score += min(10, len(claims) * 2)
        score -= sum(12 for w in warnings if w.get("level") == "high")
        score -= min(18, len(gaps) * 2)
        return max(0, min(100, score))

    def _category_from_source(self, source_type: str, claim_type: str) -> str:
        s = (source_type + " " + claim_type).lower()
        if "court" in s or "justice" in s or "legal" in s: return "person_court"
        if "financial" in s or "finance" in s: return "person_finance"
        if "image" in s: return "person_images"
        if "registry" in s or "official" in s: return "person_networks"
        if "organization" in s: return "person_organization"
        return "person_core"

    def _domain(self, url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url or "").netloc.lower().replace("www.", "")
        except Exception:
            return ""

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))


class ReportCasefileFinal625Service:
    """Phase B 62.5: final report and casefile package.

    Produces internal and redacted reports plus evidence matrix, source appendix,
    search/fund-chain and manifest. The export remains review-first and marks
    unresolved identity/doppler/privacy warnings instead of hiding them.
    """

    def __init__(self, db: Database, audit: AuditService, reports_root: str | Path, *, workspace_final=None, person_detail=None, privacy_finish=None, claim_report=None, evidence_chain=None, quality_control=None):
        self.db = db
        self.audit = audit
        self.reports_root = Path(reports_root)
        self.reports_root.mkdir(parents=True, exist_ok=True)
        self.workspace_final = workspace_final
        self.person_detail = person_detail
        self.privacy_finish = privacy_finish
        self.claim_report = claim_report
        self.evidence_chain = evidence_chain
        self.quality_control = quality_control
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS phase_b_casefile_exports_62_5 (
          export_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          export_path TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          readiness_score INTEGER DEFAULT 0,
          export_decision TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_phaseb_casefile625_entity ON phase_b_casefile_exports_62_5(case_id, entity_id, created_at);
        ''')
        self.db.conn.commit()

    def create_final_casefile(self, case_id: str, entity_id: str, *, export_mode: str = "authority_redacted") -> Dict[str, Any]:
        workspace = self.workspace_final.build_workspace(case_id, entity_id, persist=True) if self.workspace_final else {}
        entity = workspace.get("entity", {})
        report_md = self.build_report_markdown(workspace, export_mode=export_mode)
        redaction = RedactionEngine.redact(report_md, mode=export_mode)
        redacted_md = redaction["redacted_text"] if export_mode != "internal_full" else report_md
        evidence_matrix = self._evidence_matrix(workspace)
        sources = self._source_appendix(workspace)
        chain = self._chain(case_id, entity_id)
        privacy = self._privacy_review(redacted_md, workspace)
        privacy["redaction"] = redaction
        privacy["detections"] = redaction.get("detections", [])
        policy_decision = ExportPolicy.evaluate(workspace, privacy, export_mode=export_mode)
        export_decision = policy_decision["decision"]
        quality = self.quality_control.evaluate_workspace(case_id, entity_id, workspace, persist=True) if self.quality_control else {}
        export_id = new_id("casefinal625")
        outdir = self.reports_root / case_id / f"{export_id}_{_safe_name(entity.get('display_name', entity_id))}"
        outdir.mkdir(parents=True, exist_ok=True)
        files: Dict[str, str] = {
            "01_KURZBERICHT.md": self._short_brief(workspace, privacy, export_decision),
            "02_PERSONENAKTE_FINAL.md": redacted_md,
            "03_BELEGMATRIX.json": json.dumps(evidence_matrix, ensure_ascii=False, indent=2, default=str),
            "04_SEARCH_FUND_CHAIN.json": json.dumps(chain, ensure_ascii=False, indent=2, default=str),
            "05_QUELLENANHANG.json": json.dumps(sources, ensure_ascii=False, indent=2, default=str),
            "06_DATENSCHUTZ_REDIGIERUNG.md": self._privacy_markdown(privacy, workspace),
            "08_QUALITY_BIAS_REVIEW.json": json.dumps(quality, ensure_ascii=False, indent=2, default=str),
        }
        manifest = {
            "build": "65.0 Secure Architecture / Evidence Chain / Quality Control",
            "schema_version": "casefile_manifest_v2",
            "export_id": export_id,
            "case_id": case_id,
            "entity_id": entity_id,
            "entity_name": entity.get("display_name", ""),
            "export_mode": export_mode,
            "export_decision": export_decision,
            "export_policy": policy_decision,
            "redaction_decision": redaction.get("decision"),
            "quality_label": quality.get("label", ""),
            "readiness_score": workspace.get("readiness_score", 0),
            "created_at": now_ts(),
            "files": [],
        }
        for name, content in files.items():
            path = outdir / name
            path.write_text(content, encoding="utf-8")
            manifest["files"].append({"path": name, "sha256": _sha_text(content), "bytes": len(content.encode("utf-8"))})
        manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2, default=str)
        (outdir / "07_MANIFEST.json").write_text(manifest_json, encoding="utf-8")
        manifest["files"].append({"path": "07_MANIFEST.json", "sha256": _sha_text(manifest_json), "bytes": len(manifest_json.encode("utf-8"))})
        zip_path = outdir.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(outdir.iterdir()):
                if p.is_file(): zf.write(p, p.name)
        sha = self._sha_file(zip_path)
        chain_event = self.evidence_chain.append_file_event(case_id, zip_path, source_type="phase_b_casefile_zip", source_id=export_id) if self.evidence_chain else {}
        if chain_event:
            manifest["audit_chain_tip"] = chain_event.get("event_hash", "")
        self.db.execute("INSERT INTO phase_b_casefile_exports_62_5(export_id,case_id,entity_id,export_path,sha256,readiness_score,export_decision,manifest_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)", [export_id, case_id, entity_id, str(zip_path), sha, int(workspace.get("readiness_score", 0)), export_decision, dumps(manifest), now_ts()])
        self.audit.log("export", "phase_b_casefile_final_62_5", export_id, case_id, {"entity_id": entity_id, "decision": export_decision, "sha256": sha, "chain_tip": manifest.get("audit_chain_tip", "")})
        return {"export_id": export_id, "path": str(zip_path), "sha256": sha, "manifest": manifest, "workspace": workspace, "privacy": privacy, "quality": quality, "audit_chain_event": chain_event, "export_decision": export_decision}

    def build_report_markdown(self, workspace: Dict[str, Any], *, export_mode: str = "authority_redacted") -> str:
        ent = workspace.get("entity", {})
        lines = [
            f"# Personen-/Organisationsakte: {ent.get('display_name', workspace.get('entity_id', ''))}", "",
            f"**Exportmodus:** {export_mode}",
            f"**Readiness:** {workspace.get('readiness_score', 0)}/100 – {workspace.get('readiness_label', '')}",
            f"**Erstellt:** {workspace.get('generated_at', now_ts())}", "",
            "## 1. Kurzfazit",
            self._executive_summary(workspace), "",
            "## 2. Grunddaten / Identitätsanker",
        ]
        for key, label in [("entity_type", "Typ"), ("display_name", "Name"), ("known_names", "bekannte Namen"), ("aliases", "Alias"), ("places", "Orte"), ("organizations", "Organisationen"), ("roles", "Rollen"), ("public_links", "öffentliche Links")]:
            val = ent.get(key, "")
            if isinstance(val, list): val = ", ".join(val)
            lines.append(f"- **{label}:** {val}")
        lines += ["", "## 3. Stärkste dokumentierte Funde"]
        for item in workspace.get("top_findings", [])[:12]:
            f = item.get("finding", {})
            gate = item.get("entity_gate", {}) or {}
            lines.append(f"- **{f.get('title','Fund')}** – Score {item.get('score', 0)}/100, Status {f.get('status','')}, Beleggrad {f.get('evidence_level','')}, Gate {item.get('report_gate','')}")
            if f.get("source_url"): lines.append(f"  - Quelle: {f.get('source_url')}")
            if f.get("summary"): lines.append(f"  - Inhalt: {f.get('summary')}")
            if gate.get("required_actions"): lines.append(f"  - Prüfpunkte: {'; '.join(gate.get('required_actions') or [])}")
        if not workspace.get("top_findings"):
            lines.append("- Noch keine belastbaren Funde dokumentiert.")
        lines += ["", "## 4. Claims / Beleglage"]
        cs = workspace.get("claim_summary", {})
        lines.append(f"- Claims gesamt: {cs.get('count', 0)}")
        lines.append(f"- Berichtsfähige Claims: {cs.get('reportable', 0)}")
        for typ, count in (cs.get("by_type") or {}).items():
            lines.append(f"- {typ}: {count}")
        lines += ["", "## 5. Identitätsfit / Doppler / Gegenprüfung"]
        ids = workspace.get("doppler_and_identity", {})
        lines.append(f"- Assessments: {ids.get('assessment_count', 0)}")
        lines.append(f"- Max. Identitätsfit: {ids.get('max_identity_fit', 0)}/100")
        lines.append(f"- Max. Doppler-Risiko: {ids.get('max_doppler_risk', 0)}/100")
        for action in ids.get("required_actions", []): lines.append(f"- Prüfen: {action}")
        lines += ["", "## 6. Kategorienstatus"]
        for cat, data in (workspace.get("category_matrix") or {}).items():
            lines.append(f"- {data.get('label', cat)}: {data.get('status','offen')} | Funde {data.get('findings',0)}, Profile {data.get('profiles',0)}, berichtsfähig {data.get('report_ready',0)}")
        lines += ["", "## 7. Warnungen / offene Lücken"]
        for w in workspace.get("warnings", []): lines.append(f"- [{w.get('level')}] {w.get('text')}")
        for g in workspace.get("open_gaps", [])[:10]: lines.append(f"- {g.get('title')}: {g.get('action')}")
        lines += ["", "## 8. Empfohlene nächste Schritte"]
        for step in workspace.get("next_steps", [])[:12]:
            q = f" – Query: {step.get('query')}" if step.get("query") else ""
            lines.append(f"- {step.get('title')}{q}")
        lines += ["", "## 9. Redaktioneller Ergebnisbericht", "Diese Fallakte ist ein prüfbarer Arbeitsbericht. Aussagen bleiben an Quellen, Beleggrad, Identitätsfit und Gegenprüfung gebunden."]
        return "\n".join(lines) + "\n"

    def list_exports(self, case_id: str, entity_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM phase_b_casefile_exports_62_5 WHERE case_id=?"; params: List[Any] = [case_id]
        if entity_id:
            sql += " AND entity_id=?"; params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"; params.append(int(limit))
        rows = self.db.all(sql, params)
        for r in rows:
            r["manifest"] = loads(r.pop("manifest_json", "{}"), {})
        return rows

    def _executive_summary(self, workspace: Dict[str, Any]) -> str:
        score = int(workspace.get("readiness_score", 0))
        findings = len(workspace.get("top_findings", []))
        warnings = len(workspace.get("warnings", []))
        claims = workspace.get("claim_summary", {}).get("count", 0)
        return f"Die Akte erreicht aktuell {score}/100 Readiness. Es liegen {findings} priorisierte Funde und {claims} Claim-/Belegsignale vor. {warnings} Warn-/Prüfpunkte sind vor einer finalen Weitergabe zu beachten."

    def _short_brief(self, workspace: Dict[str, Any], privacy: Dict[str, Any], decision: str) -> str:
        ent = workspace.get("entity", {})
        return "\n".join([
            f"# Kurzbericht – {ent.get('display_name', workspace.get('entity_id',''))}", "",
            f"- Readiness: {workspace.get('readiness_score',0)}/100 – {workspace.get('readiness_label','')}",
            f"- Exportentscheidung: {decision}",
            f"- Datenschutz-/Redaktionsflags: {', '.join(privacy.get('flags', []) or ['keine kritischen Flags'])}",
            f"- Top-Funde: {len(workspace.get('top_findings', []))}",
            f"- offene Lücken: {len(workspace.get('open_gaps', []))}",
            "", "## Nächste Schritte",
            *[f"- {s.get('title')}" for s in workspace.get('next_steps', [])[:8]],
            "",
        ])

    def _evidence_matrix(self, workspace: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for item in workspace.get("top_findings", []):
            f = item.get("finding", {}); p = item.get("fund_profile", {}) or {}; g = item.get("entity_gate", {}) or {}
            rows.append({"finding_id": f.get("finding_note_id"), "title": f.get("title"), "source_url": f.get("source_url"), "status": f.get("status"), "evidence_level": f.get("evidence_level"), "source_quality": p.get("source_quality"), "sensitivity": p.get("sensitivity_level"), "identity_fit": g.get("identity_fit"), "doppler_risk": g.get("doppler_risk"), "report_gate": g.get("report_gate"), "score": item.get("score")})
        return rows

    def _source_appendix(self, workspace: Dict[str, Any]) -> Dict[str, Any]:
        return {"source_summary": workspace.get("source_summary", {}), "domains": workspace.get("source_summary", {}).get("top_domains", []), "category_matrix": workspace.get("category_matrix", {})}

    def _chain(self, case_id: str, entity_id: str) -> Dict[str, Any]:
        nodes = self.db.all("SELECT node_id,parent_node_id,node_type,title,value,source_url,status,confidence_label,created_at FROM search_chain_nodes_54 WHERE case_id=? AND entity_id=? ORDER BY created_at", [case_id, entity_id]) if self._table_exists("search_chain_nodes_54") else []
        return {"case_id": case_id, "entity_id": entity_id, "node_count": len(nodes), "nodes": nodes}

    def _privacy_review(self, report_text: str, workspace: Dict[str, Any]) -> Dict[str, Any]:
        flags: List[str] = []
        low = report_text.lower()
        for label, terms in {"private_address": ["wohnadresse", "privatadresse", "straße", "strasse"], "minor_data": ["minderjähr", "kind", "schüler"], "private_phone": ["telefon", "handy", "mobil"], "email": ["@"]}.items():
            if any(t in low for t in terms): flags.append(label)
        for w in workspace.get("warnings", []):
            if w.get("type") in {"redaction_block", "doppler"}: flags.append(w.get("type"))
        flags = sorted(set(flags))
        detected = RedactionEngine.detect(report_text)
        return {"flags": flags, "detections": detected.get("detections", []), "redaction_detection_decision": detected.get("decision"), "decision": "blocked_until_review" if any(f in flags for f in ["private_address", "minor_data", "redaction_block"]) else "exportable_with_review", "reviewed_at": now_ts()}

    def _privacy_markdown(self, privacy: Dict[str, Any], workspace: Dict[str, Any]) -> str:
        lines = ["# Datenschutz- und Redaktionsprüfung", "", f"Entscheidung: {privacy.get('decision')}", "", "## Flags"]
        if privacy.get("flags"):
            lines += [f"- {f}" for f in privacy.get("flags", [])]
        else:
            lines.append("- keine kritischen Flags erkannt")
        lines += ["", "## Automatische Redaction-Detektionen"]
        if privacy.get("detections"):
            lines += [f"- {d.get('type')}: {d.get('count')}" for d in privacy.get("detections", [])]
        else:
            lines.append("- keine Muster erkannt")
        lines += ["", "## Hinweise", "- Export nur mit Zweckbindung, Quellenbezug und Unsicherheitsangabe verwenden.", "- Private, minderjährigen-, opfer- oder zeugenbezogene Daten vor Weitergabe redigieren.", "- Doppler-/Identitätswarnungen nicht aus Behördenberichten entfernen, sondern als Prüfpunkte kennzeichnen."]
        return "\n".join(lines) + "\n"

    def _export_decision(self, workspace: Dict[str, Any], privacy: Dict[str, Any]) -> str:
        if privacy.get("decision") == "blocked_until_review": return "blocked_until_redaction_review"
        if int(workspace.get("readiness_score", 0)) < 65: return "draft_not_ready"
        if workspace.get("warnings"): return "exportable_with_warnings"
        return "export_ready"

    def _redact_report(self, text: str) -> str:
        return RedactionEngine.redact(text, mode="authority_redacted")["redacted_text"]

    def _sha_file(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))


class PhaseBFinalOperations625Service:
    """Consolidated Phase B workflow: workspace final + final casefile."""

    def __init__(self, db: Database, audit: AuditService, *, workspace_final=None, casefile_final=None):
        self.db = db
        self.audit = audit
        self.workspace_final = workspace_final
        self.casefile_final = casefile_final
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS phase_b_cycles_62_5 (
          phase_b_cycle_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          workspace_score INTEGER DEFAULT 0,
          export_decision TEXT NOT NULL,
          export_path TEXT DEFAULT '',
          summary_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        ''')
        self.db.conn.commit()

    def run_phase_b_cycle(self, case_id: str, entity_id: str, *, export_mode: str = "authority_redacted") -> Dict[str, Any]:
        workspace = self.workspace_final.build_workspace(case_id, entity_id, persist=True) if self.workspace_final else {}
        export = self.casefile_final.create_final_casefile(case_id, entity_id, export_mode=export_mode) if self.casefile_final else {}
        cycle_id = new_id("phaseb625")
        summary = {"workspace_score": workspace.get("readiness_score", 0), "workspace_label": workspace.get("readiness_label", ""), "export_decision": export.get("export_decision", "not_created"), "warnings": workspace.get("warnings", []), "open_gaps": workspace.get("open_gaps", [])[:6]}
        self.db.execute("INSERT INTO phase_b_cycles_62_5(phase_b_cycle_id,case_id,entity_id,workspace_score,export_decision,export_path,summary_json,created_at) VALUES(?,?,?,?,?,?,?,?)", [cycle_id, case_id, entity_id, int(workspace.get("readiness_score", 0)), export.get("export_decision", "not_created"), export.get("path", ""), dumps(summary), now_ts()])
        self.audit.log("run", "phase_b_final_cycle_62_5", cycle_id, case_id, {"entity_id": entity_id, "decision": export.get("export_decision", "")})
        return {"phase_b_cycle_id": cycle_id, "workspace": workspace, "casefile_export": export, "summary": summary}
