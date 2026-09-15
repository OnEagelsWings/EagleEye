from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Iterable
import json, html, hashlib, re
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.evidence.service import EvidenceService
from eagleeye_pro.reporting.docx_writer import write_docx
from eagleeye_pro.reporting.pdf_writer import write_pdf

REPORT_BLUEPRINTS = [
    (
        "client_short", "Mandanten-Kurzbericht", "client", "client_safe",
        ["executive_summary", "scope", "key_findings", "uncertainties", "next_steps"],
        "legal_and_redaction_review_required",
        "Kurzer verwertbarer Bericht für Auftraggeber; keine Rohdaten, keine sensiblen Details ohne Redaction Review.",
    ),
    (
        "full_dossier", "Vollständiges PersonenOSINT-Dossier", "senior_analyst", "internal_full",
        ["executive_summary", "methodology", "targets", "review", "evidence", "graph", "timeline", "risks", "annex"],
        "internal_review_required",
        "Vollständige Fallakte für interne Analyse oder Behörden-/Kanzleiübergabe nach Freigabe.",
    ),
    (
        "internal_analyst", "Internal Analyst Report", "analyst_team", "internal_full",
        ["methodology", "worklog", "unresolved_items", "hypotheses", "counter_evidence", "audit"],
        "internal_only",
        "Arbeitsbericht mit Unsicherheiten, offenen Prüfpfaden und Audit-/Chain-Daten.",
    ),
    (
        "redacted_client", "Redacted Client Report", "client", "client_safe",
        ["executive_summary", "methodology_summary", "redacted_findings", "confidence", "evidence_manifest"],
        "legal_and_redaction_review_required",
        "Mandantenfassung mit standardmäßig redigierten Kontakt-/Technik-/sensiblen Daten.",
    ),
    (
        "evidence_annex", "Evidence-Anlagenmappe", "legal_reviewer", "evidence_index",
        ["evidence_index", "chain_of_custody", "manifest_hashes", "redaction_reviews"],
        "evidence_officer_review_required",
        "Anlagen- und Nachweismappe mit Hash-/Manifestdaten und Chain-of-Custody.",
    ),
]

class ReportService:
    """Build 22.0 Provider Integration Pro.

    The service turns the existing OSINT workflow into report-ready products:
    readiness checks, executive summaries, source critique, uncertainty register,
    redacted client reports, internal analyst reports and evidence annexes.
    It does not create truth claims; it reports candidate status, confidence,
    evidence, limitations and counter-evidence.
    """
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.seed_blueprints()

    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()

    def seed_blueprints(self) -> int:
        count = 0
        for report_type, name, audience, redaction, sections, policy, notes in REPORT_BLUEPRINTS:
            self.db.execute("""INSERT OR IGNORE INTO report_blueprints(blueprint_id,report_type,name,audience,default_redaction_profile,mandatory_sections_json,export_policy,notes,active,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", [new_id("rbp"), report_type, name, audience, redaction, dumps(sections), policy, notes, 1, now_ts()])
            count += 1
        return count

    def list_blueprints(self) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM report_blueprints WHERE active=1 ORDER BY report_type")

    def collect_case_data(self, case_id: str) -> Dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id])
        if not case:
            raise KeyError("Fall nicht gefunden.")
        evidence_service = EvidenceService(self.db, self.audit)
        return {
            "case": case,
            "legal_review": self.db.one("SELECT * FROM legal_reviews WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id]),
            "targets": self.db.all("SELECT * FROM targets WHERE case_id=?", [case_id]),
            "review_items": self.db.all("SELECT * FROM review_items WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "search_packages": self.db.all("SELECT * FROM search_packages WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "search_tasks": self.db.all("SELECT * FROM search_tasks WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "source_captures": self.db.all("SELECT * FROM source_captures WHERE case_id=? ORDER BY captured_at DESC", [case_id]),
            "chain_events": self.db.all("SELECT * FROM chain_events WHERE case_id=? ORDER BY timestamp DESC LIMIT 500", [case_id]),
            "evidence_items": self.db.all("SELECT * FROM evidence_items WHERE case_id=? ORDER BY captured_at DESC", [case_id]),
            "duplicate_clusters": self.db.all("SELECT * FROM duplicate_clusters WHERE case_id=? ORDER BY updated_at DESC", [case_id]),
            "review_quality_checks": self.db.all("SELECT * FROM review_quality_checks WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "redaction_reviews": self.db.all("SELECT * FROM redaction_reviews WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "evidence_package_manifests": self.db.all("SELECT * FROM evidence_package_manifests WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "evidence_categories": self.db.all("SELECT * FROM evidence_categories ORDER BY risk_level DESC, name"),
            "graph_nodes": self.db.all("SELECT * FROM graph_nodes WHERE case_id=? ORDER BY node_type,label", [case_id]),
            "graph_edges": self.db.all("SELECT * FROM graph_edges WHERE case_id=? ORDER BY relationship_type, confidence DESC", [case_id]),
            "graph_hypotheses": self.db.all("SELECT * FROM graph_hypotheses WHERE case_id=? ORDER BY updated_at DESC", [case_id]),
            "graph_contradictions": self.db.all("SELECT * FROM graph_contradictions WHERE case_id=? ORDER BY severity DESC, updated_at DESC", [case_id]),
            "analysis_narratives": self.db.all("SELECT * FROM analysis_narratives WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "timeline_events": self.db.all("SELECT * FROM timeline_events WHERE case_id=? ORDER BY event_date, narrative_weight DESC", [case_id]),
            "workflow_steps": self.db.all("SELECT * FROM workflow_steps WHERE case_id=? ORDER BY phase", [case_id]),
            "identity_candidates": self.db.all("SELECT * FROM identity_candidates WHERE case_id=? ORDER BY score DESC", [case_id]),
            "risk_findings": self.db.all("SELECT * FROM risk_findings WHERE case_id=? ORDER BY severity DESC, created_at DESC", [case_id]),
            "export_reviews": self.db.all("SELECT * FROM export_reviews WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "provider_matrix": self.db.all("SELECT * FROM provider_registry ORDER BY provider_type,name"),
            "source_catalog": self.db.all("SELECT * FROM source_catalog ORDER BY default_risk,category,name"),
            "audit_events": self.db.all("SELECT * FROM audit_events WHERE case_id=? ORDER BY timestamp DESC LIMIT 150", [case_id]),
            "report_blueprints": self.list_blueprints(),
            "professional_reports": self.db.all("SELECT * FROM professional_reports WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "report_readiness_checks": self.db.all("SELECT * FROM report_readiness_checks WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "privacy_assessments": self.db.all("SELECT * FROM privacy_assessments WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "sensitive_data_flags": self.db.all("SELECT * FROM sensitive_data_flags WHERE case_id=? ORDER BY status, severity DESC, detected_at DESC", [case_id]),
            "dpia_checks": self.db.all("SELECT * FROM dpia_checks WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "privacy_export_blockers": self.db.all("SELECT * FROM privacy_export_blockers WHERE case_id=? ORDER BY status, severity DESC, created_at DESC", [case_id]),
            "retention_deletion_jobs": self.db.all("SELECT * FROM retention_deletion_jobs WHERE case_id=? ORDER BY created_at DESC", [case_id]),
            "evidence_manifest": evidence_service.verify_manifest(case_id),
            "evidence_dashboard": evidence_service.evidence_dashboard(case_id),
            "graph_dashboard": self._graph_dashboard(case_id),
            "timeline_dashboard": self._timeline_dashboard(case_id),
            "exported_at": now_ts(),
        }

    def _graph_dashboard(self, case_id: str) -> Dict[str, Any]:
        total = self.db.one("SELECT (SELECT COUNT(*) FROM graph_nodes WHERE case_id=?) AS nodes, (SELECT COUNT(*) FROM graph_edges WHERE case_id=?) AS edges", [case_id, case_id]) or {"nodes": 0, "edges": 0}
        hypotheses = self.db.all("SELECT status, COUNT(*) AS n FROM graph_hypotheses WHERE case_id=? GROUP BY status", [case_id])
        contradictions = self.db.all("SELECT severity, status, COUNT(*) AS n FROM graph_contradictions WHERE case_id=? GROUP BY severity,status", [case_id])
        return {"nodes": int(total.get("nodes") or 0), "edges": int(total.get("edges") or 0), "hypotheses": {r["status"]: r["n"] for r in hypotheses}, "contradictions": contradictions}

    def _timeline_dashboard(self, case_id: str) -> Dict[str, Any]:
        total = self.db.one("SELECT COUNT(*) AS n, MIN(event_date) AS first_date, MAX(event_date) AS last_date, AVG(narrative_weight) AS avg_weight FROM timeline_events WHERE case_id=?", [case_id]) or {}
        types = self.db.all("SELECT event_type, COUNT(*) AS n FROM timeline_events WHERE case_id=? GROUP BY event_type", [case_id])
        status = self.db.all("SELECT review_status, COUNT(*) AS n FROM timeline_events WHERE case_id=? GROUP BY review_status", [case_id])
        return {"events": int(total.get("n") or 0), "first_date": total.get("first_date") or "", "last_date": total.get("last_date") or "", "avg_narrative_weight": round(float(total.get("avg_weight") or 0), 3), "event_types": {r["event_type"]: r["n"] for r in types}, "statuses": {r["review_status"]: r["n"] for r in status}}

    # ---------- Build 21/22 Pro reporting logic ----------
    def report_readiness(self, case_id: str, report_type: str = "redacted_client") -> Dict[str, Any]:
        data = self.collect_case_data(case_id)
        legal = data.get("legal_review") or {}
        blockers: List[str] = []
        warnings: List[str] = []
        metrics = {
            "targets": len(data.get("targets", [])),
            "review_items": len(data.get("review_items", [])),
            "evidence_items": len(data.get("evidence_items", [])),
            "exportable_evidence": len([e for e in data.get("evidence_items", []) if e.get("export_allowed") and not e.get("redaction_required")]),
            "open_hypotheses": len([h for h in data.get("graph_hypotheses", []) if h.get("status") == "open"]),
            "open_contradictions": len([c for c in data.get("graph_contradictions", []) if c.get("status") == "open"]),
            "timeline_events": len(data.get("timeline_events", [])),
            "graph_edges": len(data.get("graph_edges", [])),
            "privacy_assessments": len(data.get("privacy_assessments", [])),
            "open_sensitive_flags": len([f for f in data.get("sensitive_data_flags", []) if f.get("status") in {"open", "auto_detected"}]),
            "dpia_checks": len(data.get("dpia_checks", [])),
        }
        if not legal or not legal.get("approved"):
            blockers.append("Legal Gate ist nicht freigegeben.")
        if not data.get("privacy_assessments"):
            blockers.append("Build-23 Privacy Assessment / Legal Case Wizard fehlt.")
        open_high_privacy = [f for f in data.get("sensitive_data_flags", []) if f.get("severity") == "high" and f.get("status") in {"open", "auto_detected"}]
        if open_high_privacy:
            blockers.append(f"{len(open_high_privacy)} offene High-Severity Privacy-/Datenklassenflags.")
        latest_dpia = data.get("dpia_checks", [None])[0] if data.get("dpia_checks") else None
        if latest_dpia and latest_dpia.get("required") and latest_dpia.get("status") not in {"completed", "not_required"}:
            blockers.append("DSFA/DPIA wurde getriggert, ist aber nicht abgeschlossen.")
        if not data.get("targets"):
            blockers.append("Keine Zielperson/Ankerdaten erfasst.")
        if not data.get("evidence_items"):
            blockers.append("Keine Evidence Items vorhanden.")
        if not data.get("evidence_manifest", {}).get("ok"):
            blockers.append("Evidence Manifest enthält Probleme.")
        if report_type in {"client_short", "redacted_client"}:
            blocked_redaction = [e for e in data.get("evidence_items", []) if e.get("redaction_required") and e.get("export_allowed")]
            if blocked_redaction:
                blockers.append(f"{len(blocked_redaction)} Evidence Items sind exportfähig markiert, benötigen aber noch Redaction.")
            non_exportable = [e for e in data.get("evidence_items", []) if not e.get("export_allowed")]
            if non_exportable and not metrics["exportable_evidence"]:
                blockers.append("Für Client-Report ist kein exportfreigegebenes Evidence Item vorhanden.")
        pending_review = [r for r in data.get("review_items", []) if r.get("status") in {"new", "needs_source_review", "in_review"}]
        if pending_review:
            warnings.append(f"{len(pending_review)} Review Items sind noch offen oder benötigen Quellenprüfung.")
        candidates = [i for i in data.get("identity_candidates", []) if i.get("status") == "candidate"]
        if candidates:
            warnings.append(f"{len(candidates)} Identity Candidates sind noch als Kandidat offen.")
        if metrics["open_contradictions"]:
            warnings.append(f"{metrics['open_contradictions']} offene Gegenbelege/Widersprüche müssen im Bericht genannt werden.")
        if metrics["graph_edges"] == 0 and report_type in {"full_dossier", "internal_analyst"}:
            warnings.append("Graph enthält noch keine belastbaren Beziehungen/Kanten.")
        if metrics["timeline_events"] == 0:
            warnings.append("Timeline enthält noch keine Ereignisse.")
        status = "blocked" if blockers else ("review_required" if warnings else "ready")
        check_id = new_id("rcheck")
        self.db.execute("""INSERT INTO report_readiness_checks(check_id,case_id,report_type,status,blockers_json,warnings_json,metrics_json,created_at)
        VALUES(?,?,?,?,?,?,?,?)""", [check_id, case_id, report_type, status, dumps(blockers), dumps(warnings), dumps(metrics), now_ts()])
        self.audit.log("check", "report_readiness", check_id, case_id, {"report_type": report_type, "status": status, "blockers": blockers, "warnings": warnings})
        return {"check_id": check_id, "status": status, "blockers": blockers, "warnings": warnings, "metrics": metrics}

    def build_executive_summary(self, data: Dict[str, Any], report_type: str = "redacted_client") -> str:
        c = data["case"]
        evidence = data.get("evidence_items", [])
        accepted = [e for e in evidence if e.get("review_decision") == "accepted"]
        identities = data.get("identity_candidates", [])
        top_identity = identities[0] if identities else {}
        risk_counts: Dict[str, int] = {}
        for r in data.get("risk_findings", []):
            risk_counts[r.get("severity", "info")] = risk_counts.get(r.get("severity", "info"), 0) + 1
        lines = [
            f"Fall '{c.get('title')}' wurde als fallzentrierte PersonenOSINT-Recherche mit dokumentiertem Zweck bearbeitet.",
            f"Zweck/Rechtsgrundlage: {c.get('purpose')} / {c.get('legal_basis')}.",
            f"Auswertungsstand: {len(data.get('review_items', []))} Review Items, {len(evidence)} Evidence Items, {len(data.get('graph_edges', []))} Graph-Beziehungen und {len(data.get('timeline_events', []))} Timeline-Ereignisse.",
            f"Belastbare, reviewte Evidence Items: {len(accepted)}. Exportfähige Evidence Items: {len([e for e in evidence if e.get('export_allowed') and not e.get('redaction_required')])}.",
        ]
        if top_identity:
            lines.append(f"Identitätszuordnung wird nur als Kandidatenlogik berichtet. Führender Kandidat: {top_identity.get('label')} mit Score {top_identity.get('score')} und Status {top_identity.get('status')}.")
        if risk_counts:
            lines.append("Risikobefunde nach Schweregrad: " + ", ".join(f"{k}: {v}" for k, v in sorted(risk_counts.items())) + ".")
        if data.get("graph_contradictions"):
            lines.append(f"Es liegen {len(data.get('graph_contradictions', []))} Gegenbelege/Widerspruchseinträge vor; diese sind im Bericht ausdrücklich als Unsicherheit zu führen.")
        lines.append("Der Bericht enthält keine automatische Identitätsbestätigung und keine Schuld-, Gefährlichkeits- oder Wohnortbehauptung; alle Aussagen bleiben quellen- und reviewgebunden.")
        return "\n".join(lines)

    def build_methodology(self, data: Dict[str, Any], detail: str = "full") -> str:
        base = [
            "Methodik: fallzentrierte OSINT-Auswertung öffentlicher oder autorisierter Quellen.",
            "Jeder Treffer wird als Kandidat behandelt, in der Review Inbox geprüft und erst nach menschlicher Bewertung in den Evidence Vault übernommen.",
            "Evidence Items werden mit Quelle, Zeitpunkt, SHA-256-Hash, Review-Entscheidung, Reliability Score und Export-/Redaction-Status dokumentiert.",
            "Graph- und Timeline-Elemente dienen der strukturierten Analyse von Beziehungen und Ereignissen; jede Beziehung bleibt erklärungs- und quellenpflichtig.",
            "Gegenbelege, Namensdoppler, offene Hypothesen und Unsicherheiten werden nicht entfernt, sondern gesondert ausgewiesen.",
            "Ausgeschlossen sind private Accounts, Login-/Captcha-Umgehung, heimliche Überwachung, Doxxing-Workflows und automatische biometrische Identitätsbestätigung.",
        ]
        if detail == "short":
            return " ".join(base[:3] + [base[-1]])
        return "\n".join(base)

    def build_source_critique(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        buckets: Dict[str, Dict[str, Any]] = {}
        for ev in data.get("evidence_items", []):
            key = ev.get("source_reliability") or "unknown"
            b = buckets.setdefault(key, {"source_reliability": key, "count": 0, "avg_reliability_score": 0.0, "exportable": 0, "notes": []})
            b["count"] += 1
            b["avg_reliability_score"] += float(ev.get("reliability_score") or 0)
            if ev.get("export_allowed") and not ev.get("redaction_required"):
                b["exportable"] += 1
        for b in buckets.values():
            if b["count"]:
                b["avg_reliability_score"] = round(b["avg_reliability_score"] / b["count"], 3)
            if b["source_reliability"] in {"unknown", "public_web", "manual_public_capture"}:
                b["notes"].append("Quellenkontext manuell prüfen; allein nicht als harte Identitätsbestätigung verwenden.")
            if b["source_reliability"] == "official_or_register":
                b["notes"].append("Register-/offizielle Quelle; dennoch Aktualität und Kontext prüfen.")
        return list(buckets.values()) or [{"source_reliability": "none", "count": 0, "avg_reliability_score": 0.0, "exportable": 0, "notes": ["Noch keine Evidence-Quellen vorhanden."]}]

    def build_uncertainty_register(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for c in data.get("graph_contradictions", []):
            out.append({"type": "counter_evidence", "severity": c.get("severity", "medium"), "title": c.get("title", ""), "description": c.get("description", ""), "status": c.get("status", "open")})
        for h in data.get("graph_hypotheses", []):
            if h.get("status") != "confirmed":
                out.append({"type": "open_hypothesis", "severity": "medium", "title": h.get("title", ""), "description": h.get("statement", ""), "status": h.get("status", "open")})
        for i in data.get("identity_candidates", []):
            if i.get("status") == "candidate":
                out.append({"type": "identity_candidate", "severity": "high", "title": i.get("label", ""), "description": "Identitätskandidat ohne finale Analystenentscheidung.", "status": i.get("status", "candidate")})
        for r in data.get("risk_findings", []):
            if r.get("status") == "candidate":
                out.append({"type": "risk_candidate", "severity": r.get("severity", "info"), "title": r.get("title", ""), "description": r.get("rationale", ""), "status": r.get("status", "candidate")})
        return out or [{"type": "none_recorded", "severity": "info", "title": "Keine dokumentierten Unsicherheiten", "description": "Es wurden keine Unsicherheiten/Gegenbelege erfasst; dies sollte vor externem Export fachlich geprüft werden.", "status": "review_required"}]

    def _redact_text(self, text: str, profile: str = "client_safe") -> str:
        if profile in {"internal_full", "evidence_index"}:
            return text or ""
        value = text or ""
        value = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[E-MAIL REDACTED]", value)
        value = re.sub(r"(?<!\w)(?:\+?\d[\d\s()./-]{6,}\d)(?!\w)", "[PHONE REDACTED]", value)
        value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP REDACTED]", value)
        return value

    def build_evidence_annex(self, data: Dict[str, Any], redaction_profile: str = "client_safe") -> List[Dict[str, Any]]:
        rows=[]
        redaction_map = {r.get("evidence_id"): r for r in data.get("redaction_reviews", [])}
        for ev in data.get("evidence_items", []):
            statement = ev.get("statement") or ""
            if redaction_profile == "client_safe" and redaction_map.get(ev.get("evidence_id")):
                statement = redaction_map[ev.get("evidence_id")].get("redacted_statement") or self._redact_text(statement, redaction_profile)
            else:
                statement = self._redact_text(statement, redaction_profile)
            rows.append({
                "evidence_id": ev.get("evidence_id"),
                "category": ev.get("category"),
                "title": ev.get("title"),
                "source_url": ev.get("source_url") if redaction_profile != "public" else "[SOURCE URL HELD IN INTERNAL ANNEX]",
                "statement": statement,
                "confidence": ev.get("confidence"),
                "review_decision": ev.get("review_decision"),
                "reliability_score": ev.get("reliability_score"),
                "content_hash": ev.get("content_hash"),
                "metadata_hash": ev.get("metadata_hash"),
                "captured_at": ev.get("captured_at"),
                "export_allowed": bool(ev.get("export_allowed")),
                "redaction_required": bool(ev.get("redaction_required")),
            })
        return rows

    def _rows_from_dicts(self, rows: List[Dict[str, Any]], headers: List[str]) -> List[List[str]]:
        table=[headers]
        for r in rows:
            table.append([str(r.get(h, "")) for h in headers])
        return table

    def _professional_sections(self, data: Dict[str, Any], report_type: str, redaction_profile: str, readiness: Dict[str, Any]) -> List[tuple[str, list]]:
        executive = self.build_executive_summary(data, report_type)
        methodology = self.build_methodology(data, detail="short" if report_type in {"client_short", "redacted_client"} else "full")
        source_critique = self.build_source_critique(data)
        uncertainty = self.build_uncertainty_register(data)
        annex = self.build_evidence_annex(data, redaction_profile)
        c = data["case"]
        sections: List[tuple[str, list]] = []
        sections.append(("1. Executive Summary", executive.splitlines()))
        sections.append(("2. Auftrag, Zweck und Grenzen", [
            f"Fall-ID: {c.get('case_id')}",
            f"Titel: {c.get('title')}",
            f"Mandant/Auftraggeber: {c.get('client') or ''}",
            f"Zweck: {c.get('purpose')}",
            f"Rechtsgrundlage: {c.get('legal_basis')}",
            "Grenze: Der Bericht enthält OSINT-Kandidaten und reviewte Belege, keine automatische Identitäts- oder Schuldbehauptung.",
        ]))
        sections.append(("3. Methodik", methodology.splitlines()))
        sections.append(("4. Report Readiness / Export-Prüfung", [
            f"Status: {readiness.get('status')}",
            "Blocker: " + ("; ".join(readiness.get("blockers") or []) or "keine"),
            "Warnings: " + ("; ".join(readiness.get("warnings") or []) or "keine"),
            "Metriken: " + json.dumps(readiness.get("metrics", {}), ensure_ascii=False),
        ]))
        target_rows=[["Name/Anker", "Aliasse", "Usernames", "Orte", "Firmen"]]
        for t in data.get("targets", []):
            target_rows.append([t.get("name", ""), t.get("aliases_json", ""), t.get("usernames_json", ""), t.get("locations_json", ""), t.get("companies_json", "")])
        sections.append(("5. Zielperson und Suchanker", target_rows))
        key_rows=[["Kategorie", "Titel", "Entscheidung", "Reliability", "Statement"]]
        for ev in annex[:80]:
            key_rows.append([ev.get("category", ""), ev.get("title", ""), ev.get("review_decision", ""), str(ev.get("reliability_score", "")), (ev.get("statement", "") or "")[:500]])
        sections.append(("6. Key Findings / Evidence-Auswertung", key_rows))
        sections.append(("7. Quellenkritik", self._rows_from_dicts(source_critique, ["source_reliability", "count", "avg_reliability_score", "exportable", "notes"])))
        ident_rows=[["Label", "Score", "Status", "Positive Marker", "Negative Marker", "Entscheidung"]]
        for ic in data.get("identity_candidates", []):
            ident_rows.append([ic.get("label", ""), str(ic.get("score", "")), ic.get("status", ""), ic.get("positive_markers_json", ""), ic.get("negative_markers_json", ""), ic.get("analyst_decision", "")])
        sections.append(("8. Identity Resolution – Kandidatenlogik", ident_rows))
        graph_rows=[["Quelle", "Beziehung", "Ziel", "Confidence", "Status", "Explanation"]]
        node_lookup={n.get("node_id"): n for n in data.get("graph_nodes", [])}
        for ge in data.get("graph_edges", [])[:120]:
            src=node_lookup.get(ge.get("source_node_id"), {})
            tgt=node_lookup.get(ge.get("target_node_id"), {})
            graph_rows.append([src.get("label", ""), ge.get("relationship_type", ""), tgt.get("label", ""), str(ge.get("confidence", "")), ge.get("review_status", ""), ge.get("explanation", "")])
        sections.append(("9. Graph-Auswertung", graph_rows))
        timeline_rows=[["Datum", "Typ", "Titel", "Akteur", "Ort", "Status", "Unsicherheit"]]
        for te in data.get("timeline_events", [])[:120]:
            timeline_rows.append([te.get("event_date", ""), te.get("event_type", ""), te.get("title", ""), te.get("actor", ""), te.get("location", ""), te.get("review_status", ""), te.get("uncertainty_note", "")])
        sections.append(("10. Timeline-Auswertung", timeline_rows))
        sections.append(("11. Unsicherheiten, Gegenbelege und offene Prüfpfade", self._rows_from_dicts(uncertainty, ["type", "severity", "title", "description", "status"])))
        risk_rows=[["Severity", "Kategorie", "Titel", "Status", "Rationale"]]
        for rf in data.get("risk_findings", []):
            risk_rows.append([rf.get("severity", ""), rf.get("category", ""), rf.get("title", ""), rf.get("status", ""), rf.get("rationale", "")])
        sections.append(("12. Risiko- und Reputationshinweise", risk_rows))
        sections.append(("13. Evidence-Anlagenindex", [["Evidence-ID", "Kategorie", "Titel", "Hash", "Export", "Redaction"]] + [[a.get("evidence_id", ""), a.get("category", ""), a.get("title", ""), (a.get("content_hash", "") or "")[:18], str(a.get("export_allowed")), str(a.get("redaction_required"))] for a in annex]))
        chain_rows=[["Zeit", "Typ", "Objekt", "ID"]]
        for ce in data.get("chain_events", [])[:160]:
            chain_rows.append([ce.get("timestamp", ""), ce.get("event_type", ""), ce.get("object_type", ""), ce.get("object_id", "")])
        if report_type in {"full_dossier", "internal_analyst", "evidence_annex"}:
            sections.append(("14. Chain-of-Custody", chain_rows))
            sections.append(("15. Audit-Auszug", [["Zeit", "Akteur", "Action", "Objekt", "ID"]] + [[a.get("timestamp", ""), a.get("actor", ""), a.get("action", ""), a.get("object_type", ""), a.get("object_id", "")] for a in data.get("audit_events", [])[:120]]))
        sections.append(("16. Schlussvermerk", [
            "Alle Aussagen sind quellengebunden und müssen im Kontext des Auftragszwecks gelesen werden.",
            "Offene Unsicherheiten und Gegenbelege sind integraler Bestandteil der Bewertung und dürfen nicht als Fehler entfernt werden.",
            "Weitergabe nur nach Legal-/Exportfreigabe, Datenminimierung und Redaction Review.",
        ]))
        return sections

    def export_professional_report(self, case_id: str, outdir: str | Path, report_type: str = "redacted_client", redaction_profile: str | None = None, notes: str = "") -> Dict[str, str]:
        outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
        bp = self.db.one("SELECT * FROM report_blueprints WHERE report_type=?", [report_type])
        if not bp:
            raise ValueError(f"Unbekannter Reporttyp: {report_type}")
        redaction_profile = redaction_profile or bp.get("default_redaction_profile") or "client_safe"
        readiness = self.report_readiness(case_id, report_type)
        data = self.collect_case_data(case_id)
        executive = self.build_executive_summary(data, report_type)
        methodology = self.build_methodology(data, detail="short" if report_type in {"client_short", "redacted_client"} else "full")
        source_critique = self.build_source_critique(data)
        uncertainty = self.build_uncertainty_register(data)
        annex = self.build_evidence_annex(data, redaction_profile)
        sections = self._professional_sections(data, report_type, redaction_profile, readiness)
        c = data["case"]
        safe_title=''.join(ch if ch.isalnum() or ch in ('-','_') else '_' for ch in c['title'])[:60]
        base = outdir / f"EagleEye_{report_type}_{safe_title}_{case_id[-6:]}"
        title = f"EagleEye PersonOSINT Pro – {bp.get('name')} – {c['title']}"
        json_payload = {
            "report_type": report_type,
            "report_name": bp.get("name"),
            "audience": bp.get("audience"),
            "redaction_profile": redaction_profile,
            "readiness": readiness,
            "executive_summary": executive,
            "methodology": methodology,
            "source_critique": source_critique,
            "uncertainty_register": uncertainty,
            "evidence_annex": annex,
            "section_manifest": [{"heading": h, "items": len(content)} for h, content in sections],
            "created_at": now_ts(),
        }
        json_raw = json.dumps(json_payload, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        content_hash = self.sha256_text(json_raw)
        json_path = base.with_suffix('.json')
        json_path.write_text(json_raw, encoding='utf-8')
        docx_path = write_docx(base.with_suffix('.docx'), title, sections)
        html_path = base.with_suffix('.html')
        html_lines=[f"<h1>{html.escape(title)}</h1>", f"<p><strong>Content Hash:</strong> {html.escape(content_hash)}</p>"]
        for h, content in sections:
            html_lines.append(f"<h2>{html.escape(h)}</h2>")
            if content and isinstance(content[0], list):
                html_lines.append('<table border="1" cellspacing="0" cellpadding="4">')
                for row in content:
                    html_lines.append('<tr>' + ''.join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + '</tr>')
                html_lines.append('</table>')
            else:
                for line in content:
                    html_lines.append(f"<p>{html.escape(str(line))}</p>")
        html_path.write_text('<html><head><meta charset="utf-8"><title>EagleEye Report</title></head><body>'+'\n'.join(html_lines)+'</body></html>', encoding='utf-8')
        pdf_text=[f"Content Hash: {content_hash}"]
        for h, content in sections:
            pdf_text.append(h)
            if content and isinstance(content[0], list):
                for row in content:
                    pdf_text.append(' | '.join(str(x) for x in row))
            else:
                pdf_text.extend(str(x) for x in content)
            pdf_text.append('')
        pdf_path = write_pdf(base.with_suffix('.pdf'), title, pdf_text)
        paths = {"json": str(json_path), "docx": str(docx_path), "html": str(html_path), "pdf": str(pdf_path)}
        report_id = new_id("rpt")
        self.db.execute("""INSERT INTO professional_reports(report_id,case_id,report_type,audience,redaction_profile,readiness_status,executive_summary,methodology,source_critique_json,uncertainty_register_json,evidence_annex_json,section_manifest_json,export_paths_json,content_hash,created_at,created_by,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", [
            report_id, case_id, report_type, bp.get("audience"), redaction_profile, readiness.get("status"), executive, methodology,
            dumps(source_critique), dumps(uncertainty), dumps(annex), dumps(json_payload["section_manifest"]), dumps(paths), content_hash, now_ts(), "local-analyst", notes
        ])
        self.audit.log("export", "professional_report", report_id, case_id, {"report_type": report_type, "paths": paths, "content_hash": content_hash, "readiness": readiness.get("status")})
        paths["report_id"] = report_id
        paths["content_hash"] = content_hash
        paths["readiness_status"] = readiness.get("status", "")
        return paths

    def export_report_bundle(self, case_id: str, outdir: str | Path) -> Dict[str, Dict[str, str]]:
        return {
            "redacted_client": self.export_professional_report(case_id, outdir, "redacted_client", "client_safe"),
            "internal_analyst": self.export_professional_report(case_id, outdir, "internal_analyst", "internal_full"),
            "full_dossier": self.export_professional_report(case_id, outdir, "full_dossier", "internal_full"),
            "evidence_annex": self.export_professional_report(case_id, outdir, "evidence_annex", "evidence_index"),
        }

    # ---------- Comprehensive legacy-compatible report ----------
    def _sections(self, data: Dict[str, Any]) -> List[tuple[str, list]]:
        c=data["case"]
        sections=[]
        sections.append(("1. Auftrag und Fallrahmen", [
            f"Fall-ID: {c['case_id']}", f"Titel: {c['title']}", f"Mandant/Auftraggeber: {c.get('client') or ''}",
            f"Zweck: {c.get('purpose')}", f"Rechtsgrundlage: {c.get('legal_basis')}", f"Status: {c.get('status')}",
            "Hinweis: Alle Ergebnisse sind OSINT-Kandidaten und benötigen menschliche Prüfung; keine automatische Identitätsbestätigung."
        ]))
        legal=data.get("legal_review") or {}
        sections.append(("2. Legal Gate / Compliance", [
            f"Review-Level: {legal.get('review_level','nicht vorhanden')}", f"Freigegeben: {bool(legal.get('approved'))}",
            f"Erforderlichkeit: {legal.get('necessity','')}", f"Interessenabwägung: {legal.get('balancing','')}",
            f"Besondere Kategorien: {bool(legal.get('special_categories'))}; Minderjährige: {bool(legal.get('minor_data'))}; Strafdaten: {bool(legal.get('criminal_data'))}"
        ]))
        sections.append(("3. Executive Summary Pro", self.build_executive_summary(data, "full_dossier").splitlines()))
        sections.append(("4. Methodik Pro", self.build_methodology(data, "full").splitlines()))
        review_rows=[["Status", "Score", "Quality", "Sens.", "Quelle", "Titel", "URL", "Triage"]]
        for r in data["review_items"]:
            review_rows.append([r.get("status",""), str(r.get("score","")), str(r.get("quality_score","")), r.get("sensitivity_level",""), r.get("provider",""), r.get("title",""), r.get("url",""), r.get("triage_reason","")])
        sections.append(("5. Review Inbox Pro", review_rows))
        ev_rows=[["Kategorie", "Confidence", "Entscheidung", "Reliability", "Titel", "Hash", "Export", "Redaction"]]
        for ev in data["evidence_items"]:
            ev_rows.append([ev.get("category",""), ev.get("confidence",""), ev.get("review_decision",""), str(ev.get("reliability_score","")), ev.get("title",""), (ev.get("content_hash","")[:16]+"...") if ev.get("content_hash") else "", str(bool(ev.get("export_allowed"))), str(bool(ev.get("redaction_required")))])
        sections.append(("6. Evidence Vault Pro", ev_rows))
        sections.append(("7. Quellenkritik", self._rows_from_dicts(self.build_source_critique(data), ["source_reliability", "count", "avg_reliability_score", "exportable", "notes"])))
        sections.append(("8. Unsicherheitenregister", self._rows_from_dicts(self.build_uncertainty_register(data), ["type", "severity", "title", "description", "status"])))
        timeline_rows=[["Datum", "Typ", "Titel", "Akteur", "Ort", "Confidence", "Status", "Unsicherheit"]]
        for te in data["timeline_events"]:
            timeline_rows.append([te.get("event_date",""), te.get("event_type",""), te.get("title",""), te.get("actor",""), te.get("location",""), te.get("confidence",""), te.get("review_status",""), te.get("uncertainty_note","")])
        sections.append(("9. Timeline Pro", timeline_rows))
        graph_rows=[["Quelle", "Beziehung", "Ziel", "Confidence", "Status", "Evidence", "Explanation"]]
        node_lookup={n.get("node_id"): n for n in data.get("graph_nodes", [])}
        for ge in data.get("graph_edges", [])[:150]:
            src=node_lookup.get(ge.get("source_node_id"), {})
            tgt=node_lookup.get(ge.get("target_node_id"), {})
            graph_rows.append([src.get("label",""), ge.get("relationship_type",""), tgt.get("label",""), str(ge.get("confidence","")), ge.get("review_status",""), ge.get("source_evidence_id",""), ge.get("explanation","")])
        sections.append(("10. Graph Pro – Explainable Relationship Map", graph_rows))
        hyp_rows=[["Status", "Confidence", "Typ", "Titel", "Statement", "Supporting Evidence", "Counter Evidence"]]
        for h in data.get("graph_hypotheses", []):
            hyp_rows.append([h.get("status",""), str(h.get("confidence","")), h.get("hypothesis_type",""), h.get("title",""), h.get("statement",""), h.get("supporting_evidence_json",""), h.get("counter_evidence_json","")])
        sections.append(("11. Hypothesenmodell", hyp_rows))
        con_rows=[["Severity", "Status", "Typ", "Titel", "Beschreibung", "Evidence"]]
        for c in data.get("graph_contradictions", []):
            con_rows.append([c.get("severity",""), c.get("status",""), c.get("contradiction_type",""), c.get("title",""), c.get("description",""), c.get("related_evidence_ids_json","")])
        sections.append(("12. Gegenbelege / Widersprüche", con_rows))
        sections.append(("13. Evidence Manifest", [json.dumps(data["evidence_manifest"], ensure_ascii=False)]))
        sections.append(("14. Report Blueprints", [["Typ", "Name", "Audience", "Redaction", "Policy"]] + [[b.get("report_type", ""), b.get("name", ""), b.get("audience", ""), b.get("default_redaction_profile", ""), b.get("export_policy", "")] for b in data.get("report_blueprints", [])]))
        sections.append(("15. Professional Reports", [["Report", "Typ", "Status", "Hash", "Zeit"]] + [[r.get("report_id", ""), r.get("report_type", ""), r.get("readiness_status", ""), (r.get("content_hash", "") or "")[:18], r.get("created_at", "")] for r in data.get("professional_reports", [])]))
        return sections

    def export_case_report(self, case_id: str, outdir: str | Path) -> Dict[str, str]:
        outdir=Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
        data=self.collect_case_data(case_id)
        c=data["case"]
        safe_title=''.join(ch if ch.isalnum() or ch in ('-','_') else '_' for ch in c['title'])[:60]
        base=outdir / f"EagleEye_Comprehensive_Report_{safe_title}_{case_id[-6:]}"
        json_path=base.with_suffix('.json')
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        sections=self._sections(data)
        docx_path=write_docx(base.with_suffix('.docx'), f"EagleEye PersonOSINT Pro Gesamtbericht – {c['title']}", sections)
        html_lines=[f"<h1>EagleEye PersonOSINT Pro Gesamtbericht – {html.escape(c['title'])}</h1>"]
        for h, content in sections:
            html_lines.append(f"<h2>{html.escape(h)}</h2>")
            if content and isinstance(content[0], list):
                html_lines.append('<table border="1" cellspacing="0" cellpadding="4">')
                for row in content:
                    html_lines.append('<tr>' + ''.join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + '</tr>')
                html_lines.append('</table>')
            else:
                for line in content:
                    html_lines.append(f"<p>{html.escape(str(line))}</p>")
        html_path=base.with_suffix('.html')
        html_path.write_text('<html><head><meta charset="utf-8"><title>EagleEye Report</title></head><body>'+'\n'.join(html_lines)+'</body></html>', encoding='utf-8')
        pdf_text=[]
        for h, content in sections:
            pdf_text.append(h)
            if content and isinstance(content[0], list):
                for row in content:
                    pdf_text.append(' | '.join(str(x) for x in row))
            else:
                pdf_text.extend(str(x) for x in content)
            pdf_text.append('')
        pdf_path=write_pdf(base.with_suffix('.pdf'), f"EagleEye PersonOSINT Pro Gesamtbericht - {c['title']}", pdf_text)
        self.audit.log("export", "report", str(base), case_id, {"formats": ["json","docx","html","pdf"], "build": "22.0"})
        return {"json": str(json_path), "docx": str(docx_path), "html": str(html_path), "pdf": str(pdf_path)}
