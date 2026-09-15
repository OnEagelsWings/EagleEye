from __future__ import annotations
from typing import Any, Dict, List
import json
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService

class CaseCockpitService:
    """Build 25.0: guided case cockpit and operational readiness layer.

    This service does not add new OSINT collection capabilities. It aggregates the
    existing legal, privacy, review, evidence, provider, graph, timeline, report,
    security and audit state into a single case cockpit with traffic-light status,
    blockers, queues and recommended next actions.
    """
    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def _count(self, sql: str, params: List[Any]) -> int:
        row = self.db.one(sql, params) or {}
        return int(row.get("n") or 0)

    def _latest(self, table: str, case_id: str, order_col: str = "created_at") -> Dict[str, Any] | None:
        try:
            return self.db.one(f"SELECT * FROM {table} WHERE case_id=? ORDER BY {order_col} DESC LIMIT 1", [case_id])
        except Exception:
            return None

    @staticmethod
    def _as_bool(value: Any) -> bool:
        try:
            return bool(int(value))
        except Exception:
            return bool(value)

    @staticmethod
    def _level(score: int) -> str:
        if score >= 85:
            return "green"
        if score >= 65:
            return "yellow"
        if score >= 40:
            return "orange"
        return "red"

    def build_cockpit(self, case_id: str) -> Dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id])
        if not case:
            raise KeyError("Fall nicht gefunden.")

        latest_legal = self._latest("legal_reviews", case_id, "created_at")
        latest_privacy = self._latest("privacy_assessments", case_id, "created_at")
        latest_dpia = self._latest("dpia_checks", case_id, "created_at")
        latest_report = self._latest("professional_reports", case_id, "created_at")
        latest_readiness = self._latest("report_readiness_checks", case_id, "created_at")

        kpis = {
            "targets": self._count("SELECT COUNT(*) AS n FROM targets WHERE case_id=?", [case_id]),
            "search_packages": self._count("SELECT COUNT(*) AS n FROM search_packages WHERE case_id=?", [case_id]),
            "search_tasks": self._count("SELECT COUNT(*) AS n FROM search_tasks WHERE case_id=?", [case_id]),
            "captures": self._count("SELECT COUNT(*) AS n FROM source_captures WHERE case_id=?", [case_id]),
            "provider_jobs": self._count("SELECT COUNT(*) AS n FROM provider_jobs WHERE case_id=?", [case_id]),
            "provider_results": self._count("SELECT COUNT(*) AS n FROM provider_results WHERE case_id=?", [case_id]),
            "review_total": self._count("SELECT COUNT(*) AS n FROM review_items WHERE case_id=?", [case_id]),
            "review_open": self._count("SELECT COUNT(*) AS n FROM review_items WHERE case_id=? AND status IN ('new','in_review','needs_source_review')", [case_id]),
            "review_ready": self._count("SELECT COUNT(*) AS n FROM review_items WHERE case_id=? AND status IN ('accepted_as_lead','ready_for_evidence')", [case_id]),
            "evidence_total": self._count("SELECT COUNT(*) AS n FROM evidence_items WHERE case_id=?", [case_id]),
            "evidence_exportable": self._count("SELECT COUNT(*) AS n FROM evidence_items WHERE case_id=? AND export_allowed=1 AND redaction_required=0", [case_id]),
            "evidence_redaction_blocked": self._count("SELECT COUNT(*) AS n FROM evidence_items WHERE case_id=? AND redaction_required=1", [case_id]),
            "graph_nodes": self._count("SELECT COUNT(*) AS n FROM graph_nodes WHERE case_id=?", [case_id]),
            "graph_edges": self._count("SELECT COUNT(*) AS n FROM graph_edges WHERE case_id=?", [case_id]),
            "timeline_events": self._count("SELECT COUNT(*) AS n FROM timeline_events WHERE case_id=?", [case_id]),
            "identity_candidates": self._count("SELECT COUNT(*) AS n FROM identity_candidates WHERE case_id=?", [case_id]),
            "risk_open": self._count("SELECT COUNT(*) AS n FROM risk_findings WHERE case_id=? AND status IN ('open','monitor','review_required')", [case_id]),
            "privacy_flags_open": self._count("SELECT COUNT(*) AS n FROM sensitive_data_flags WHERE case_id=? AND status IN ('open','auto_detected')", [case_id]),
            "privacy_flags_high": self._count("SELECT COUNT(*) AS n FROM sensitive_data_flags WHERE case_id=? AND severity='high' AND status IN ('open','auto_detected')", [case_id]),
            "export_blockers_open": self._count("SELECT COUNT(*) AS n FROM privacy_export_blockers WHERE case_id=? AND status IN ('open','active')", [case_id]),
            "audit_events": self._count("SELECT COUNT(*) AS n FROM audit_events WHERE case_id=?", [case_id]),
        }

        blockers: List[str] = []
        warnings: List[str] = []
        gates: Dict[str, str] = {}

        if latest_legal and self._as_bool(latest_legal.get("approved")):
            gates["legal_gate"] = "green"
        else:
            gates["legal_gate"] = "red"
            blockers.append("Legal Gate fehlt oder ist nicht freigegeben.")

        if latest_privacy and latest_privacy.get("decision") in {"approved", "review_required", "conditional"}:
            gates["privacy_assessment"] = "green" if latest_privacy.get("decision") == "approved" else "yellow"
            if latest_privacy.get("decision") != "approved":
                warnings.append("Privacy Assessment ist vorhanden, aber nicht vollständig freigegeben.")
        else:
            gates["privacy_assessment"] = "red"
            blockers.append("Legal/Privacy Case Wizard fehlt.")

        if kpis["privacy_flags_high"]:
            gates["sensitive_data"] = "red"
            blockers.append(f"{kpis['privacy_flags_high']} High-Severity Privacy-/Datenklassenflags offen.")
        elif kpis["privacy_flags_open"]:
            gates["sensitive_data"] = "yellow"
            warnings.append(f"{kpis['privacy_flags_open']} Privacy-/Datenklassenflags offen.")
        else:
            gates["sensitive_data"] = "green"

        if latest_dpia and self._as_bool(latest_dpia.get("required")) and latest_dpia.get("status") not in {"completed", "not_required"}:
            gates["dpia"] = "red"
            blockers.append("DSFA/DPIA wurde getriggert, ist aber nicht abgeschlossen.")
        else:
            gates["dpia"] = "green"

        if kpis["targets"] == 0:
            gates["target_profile"] = "red"
            blockers.append("Keine Zielperson/Ankerdaten erfasst.")
        else:
            gates["target_profile"] = "green"

        if kpis["search_tasks"] == 0 and kpis["provider_jobs"] == 0:
            gates["research_plan"] = "red"
            warnings.append("Kein Rechercheplan/Suchpaket und kein Provider Job vorhanden.")
        elif kpis["captures"] == 0 and kpis["provider_results"] == 0:
            gates["research_plan"] = "yellow"
            warnings.append("Recherche ist geplant, aber noch keine Captures/Provider Results vorhanden.")
        else:
            gates["research_plan"] = "green"

        if kpis["review_open"]:
            gates["review_queue"] = "yellow"
            warnings.append(f"{kpis['review_open']} Review Items offen.")
        else:
            gates["review_queue"] = "green" if kpis["review_total"] else "yellow"

        if kpis["evidence_total"] == 0:
            gates["evidence"] = "red"
            blockers.append("Keine Evidence Items vorhanden.")
        elif kpis["evidence_redaction_blocked"]:
            gates["evidence"] = "yellow"
            warnings.append(f"{kpis['evidence_redaction_blocked']} Evidence Items benötigen Redaction/Review.")
        else:
            gates["evidence"] = "green"

        if kpis["graph_edges"] == 0 or kpis["timeline_events"] == 0:
            gates["analysis"] = "yellow"
            warnings.append("Graph/Timeline sind noch nicht vollständig analysefähig.")
        else:
            gates["analysis"] = "green"

        if latest_readiness:
            gates["reporting"] = "green" if latest_readiness.get("status") == "ready" else ("yellow" if latest_readiness.get("status") == "review_required" else "red")
            try:
                blockers += [f"Report-Blocker: {b}" for b in loads(latest_readiness.get("blockers_json"), [])]
                warnings += [f"Report-Warnung: {w}" for w in loads(latest_readiness.get("warnings_json"), [])]
            except Exception:
                pass
        else:
            gates["reporting"] = "yellow"
            warnings.append("Noch kein Report-Readiness-Check ausgeführt.")

        if kpis["export_blockers_open"]:
            gates["export"] = "red"
            blockers.append(f"{kpis['export_blockers_open']} Privacy Export Blocker offen.")
        elif kpis["evidence_exportable"] == 0:
            gates["export"] = "yellow"
            warnings.append("Noch kein exportfähiges Evidence Item vorhanden.")
        else:
            gates["export"] = "green"

        gate_score_map = {"green": 10, "yellow": 6, "orange": 4, "red": 0}
        max_score = max(1, len(gates) * 10)
        readiness_score = round(sum(gate_score_map.get(v, 0) for v in gates.values()) / max_score * 100)
        if blockers:
            readiness_score = min(readiness_score, 64)
        traffic_light = self._level(readiness_score)

        action_items = self.recommend_next_actions(case_id, kpis, gates, blockers, warnings)
        phase_status = self.operational_phase_status(case, kpis, gates, latest_report, latest_readiness)
        queues = self.queue_summary(case_id)

        return {
            "case": case,
            "generated_at": now_ts(),
            "traffic_light": traffic_light,
            "readiness_score": readiness_score,
            "gates": gates,
            "kpis": kpis,
            "blockers": list(dict.fromkeys(blockers)),
            "warnings": list(dict.fromkeys(warnings)),
            "next_actions": action_items,
            "phase_status": phase_status,
            "queues": queues,
            "latest": {
                "legal_review": latest_legal,
                "privacy_assessment": latest_privacy,
                "dpia_check": latest_dpia,
                "report": latest_report,
                "readiness_check": latest_readiness,
            },
        }

    def operational_phase_status(self, case: Dict[str, Any], kpis: Dict[str, int], gates: Dict[str, str], latest_report: Dict[str, Any] | None, latest_readiness: Dict[str, Any] | None) -> List[Dict[str, Any]]:
        def phase(key: str, title: str, light: str, done: bool, detail: str) -> Dict[str, Any]:
            pct = 100.0 if done else (65.0 if light == "yellow" else (37.0 if light == "orange" else 0.0))
            return {"phase": key, "title": title, "status_light": light, "completion_pct": pct, "detail": detail}
        return [
            phase("01 Intake", "Auftrag, Mandant, Zweck und Grenzen", "green" if case.get("purpose") and case.get("legal_basis") else "red", bool(case.get("purpose") and case.get("legal_basis")), "Fallzweck und Rechtsgrundlage sind die Arbeitsgrundlage."),
            phase("02 Legal Gate", "Rechtsgrundlage und Interessenabwägung", gates.get("legal_gate", "red"), gates.get("legal_gate") == "green", "Kein OSINT-Workflow ohne freigegebenes Legal Gate."),
            phase("03 Target Anchors", "Zielperson und Suchanker", gates.get("target_profile", "red"), kpis.get("targets", 0) > 0, f"{kpis.get('targets', 0)} Ziel-/Ankerprofile vorhanden."),
            phase("04 Source Plan", "Quellen-/Providerplan", "green" if (kpis.get("search_tasks", 0) or kpis.get("provider_jobs", 0)) else "red", bool(kpis.get("search_tasks", 0) or kpis.get("provider_jobs", 0)), f"Tasks={kpis.get('search_tasks', 0)}, Provider Jobs={kpis.get('provider_jobs', 0)}."),
            phase("05 Search Workbench", "Treffer/Captures erfassen", gates.get("research_plan", "yellow"), bool(kpis.get("captures", 0) or kpis.get("provider_results", 0)), f"Captures={kpis.get('captures', 0)}, Provider Results={kpis.get('provider_results', 0)}."),
            phase("06 Review Inbox", "Treffer prüfen", "green" if kpis.get("review_total", 0) and kpis.get("review_open", 0) == 0 else ("yellow" if kpis.get("review_total", 0) else "orange"), kpis.get("review_total", 0) > 0 and kpis.get("review_open", 0) == 0, f"Offen={kpis.get('review_open', 0)} von {kpis.get('review_total', 0)}."),
            phase("07 Evidence Vault", "Evidence sichern", gates.get("evidence", "red"), kpis.get("evidence_total", 0) > 0 and kpis.get("evidence_redaction_blocked", 0) == 0, f"Evidence={kpis.get('evidence_total', 0)}, exportfähig={kpis.get('evidence_exportable', 0)}."),
            phase("08 Identity Resolution", "Kandidatenlogik", "green" if kpis.get("identity_candidates", 0) else "yellow", kpis.get("identity_candidates", 0) > 0, f"Identity Candidates={kpis.get('identity_candidates', 0)}."),
            phase("09 Graph & Timeline", "Beziehungen und Ereignisse", gates.get("analysis", "yellow"), kpis.get("graph_edges", 0) > 0 and kpis.get("timeline_events", 0) > 0, f"Edges={kpis.get('graph_edges', 0)}, Events={kpis.get('timeline_events', 0)}."),
            phase("10 Risk Assessment", "Risiken/Gegenbelege", "green" if kpis.get("risk_open", 0) == 0 else "yellow", kpis.get("risk_open", 0) == 0, f"Offene Risk Findings={kpis.get('risk_open', 0)}."),
            phase("11 Report Builder", "Bericht und Readiness", gates.get("reporting", "yellow"), bool(latest_report), f"Letzter Readiness-Status={(latest_readiness or {}).get('status', 'nicht geprüft')}"),
            phase("12 Retention", "Archivierung/Löschung", "green" if case.get("retention_until") else "yellow", bool(case.get("retention_until")), f"Retention until={case.get('retention_until') or 'nicht gesetzt'}."),
        ]

    def workflow_phase_status(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT phase,status,gate_required,title,owner FROM workflow_steps WHERE case_id=? ORDER BY phase", [case_id])
        if not rows:
            return []
        grouped: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            phase = str(row.get("phase") or "")
            item = grouped.setdefault(phase, {"phase": phase, "total": 0, "done": 0, "blocked": 0, "open": 0, "gate_required": 0, "owners": set(), "titles": []})
            item["total"] += 1
            status = row.get("status") or ""
            if status in {"done", "completed", "approved"}:
                item["done"] += 1
            elif status in {"blocked", "rejected"}:
                item["blocked"] += 1
            else:
                item["open"] += 1
            if row.get("gate_required"):
                item["gate_required"] += 1
            if row.get("owner"):
                item["owners"].add(row.get("owner"))
            if row.get("title"):
                item["titles"].append(row.get("title"))
        out=[]
        for item in grouped.values():
            completion = round((item["done"] / item["total"] * 100), 1) if item["total"] else 0
            status = "green" if completion == 100 else ("red" if item["blocked"] else ("yellow" if completion >= 50 else "orange"))
            item["completion_pct"] = completion
            item["status_light"] = status
            item["owners"] = sorted(item["owners"])
            item["titles"] = item["titles"][:5]
            out.append(item)
        return sorted(out, key=lambda x: x["phase"])

    def queue_summary(self, case_id: str) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "review_open": self.db.all("SELECT item_id,title,provider,status,quality_score,url FROM review_items WHERE case_id=? AND status IN ('new','in_review','needs_source_review') ORDER BY created_at DESC LIMIT 12", [case_id]),
            "evidence_redaction": self.db.all("SELECT evidence_id,title,category,review_decision,redaction_required,export_allowed FROM evidence_items WHERE case_id=? AND redaction_required=1 ORDER BY captured_at DESC LIMIT 12", [case_id]),
            "privacy_flags": self.db.all("SELECT flag_id,severity,data_category,article_reference,action_required,status FROM sensitive_data_flags WHERE case_id=? AND status IN ('open','auto_detected') ORDER BY severity DESC, detected_at DESC LIMIT 12", [case_id]),
            "export_blockers": self.db.all("SELECT blocker_id,severity,blocker_type,description AS reason,status FROM privacy_export_blockers WHERE case_id=? AND status IN ('open','active') ORDER BY severity DESC, created_at DESC LIMIT 12", [case_id]),
            "provider_jobs": self.db.all("SELECT job_id,provider_id,capability_key,status,query,result_count FROM provider_jobs WHERE case_id=? ORDER BY created_at DESC LIMIT 12", [case_id]),
        }

    def recommend_next_actions(self, case_id: str, kpis: Dict[str, int], gates: Dict[str, str], blockers: List[str], warnings: List[str]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        def add(priority: int, area: str, title: str, detail: str, target_tab: str, action_type: str = "manual_review"):
            actions.append({"priority": priority, "area": area, "title": title, "detail": detail, "target_tab": target_tab, "action_type": action_type})
        if gates.get("legal_gate") == "red":
            add(100, "Legal", "Legal Gate freigeben", "Zweck, Rechtsgrundlage, Erforderlichkeit und Interessenabwägung dokumentieren.", "Legal Gate")
        if gates.get("privacy_assessment") == "red":
            add(95, "Privacy", "Legal/Privacy Wizard ausfüllen", "Datenklassen, Scope, verbotene Quellen, DSFA-Trigger und Löschfrist prüfen.", "Legal/Privacy Hardening")
        if kpis.get("privacy_flags_high", 0):
            add(90, "Privacy", "High-Severity Datenklassenflags bearbeiten", "High-Severity Flags blockieren Export und müssen resolved oder documented werden.", "Legal/Privacy Hardening")
        if kpis.get("targets", 0) == 0:
            add(85, "Zielperson", "Zielperson/Ankerdaten erfassen", "Name/Anker, Aliasse, Usernames, Orte/Firmen und erlaubte Suchgrenzen eintragen.", "Zielperson")
        if kpis.get("search_tasks", 0) == 0 and kpis.get("provider_jobs", 0) == 0:
            add(80, "Recherche", "Recherchepakete erzeugen", "Suchpakete und Provider-Jobs anhand der Zielanker erzeugen; nur öffentliche/erlaubte Quellen nutzen.", "Search Workbench")
        elif kpis.get("captures", 0) == 0 and kpis.get("provider_results", 0) == 0:
            add(75, "Recherche", "erste Treffer erfassen", "Öffentliche Treffer als Capture/Snapshot dokumentieren oder Provider Results importieren.", "Search Workbench")
        if kpis.get("review_open", 0):
            add(70, "Review", "Review Queue abarbeiten", f"{kpis['review_open']} offene Items prüfen, ablehnen oder zu Evidence hochstufen.", "Review Inbox")
        if kpis.get("review_ready", 0) and kpis.get("evidence_total", 0) == 0:
            add(68, "Evidence", "akzeptierte Leads zu Evidence hochstufen", "Review Items mit ausreichender Qualität in den Evidence Vault übernehmen.", "Evidence Vault")
        if kpis.get("evidence_redaction_blocked", 0):
            add(65, "Redaction", "Redaction Reviews durchführen", f"{kpis['evidence_redaction_blocked']} Evidence Items sind noch redaction-blockiert.", "Evidence Vault")
        if kpis.get("evidence_total", 0) and (kpis.get("graph_edges", 0) == 0 or kpis.get("timeline_events", 0) == 0):
            add(60, "Analyse", "Graph und Timeline neu aufbauen", "Aus Evidence Items Beziehungen, Hypothesen, Gegenbelege und Ereignisse erzeugen.", "Graph & Timeline")
        if kpis.get("evidence_exportable", 0) and gates.get("reporting") != "green":
            add(55, "Reporting", "Report Readiness prüfen", "Readiness-Check für redacted_client/full_dossier ausführen und Blocker abarbeiten.", "Reporting")
        if kpis.get("export_blockers_open", 0):
            add(50, "Export", "Exportblocker schließen", "Privacy-/Legal-Exportblocker prüfen; nicht zulässige Daten redigieren oder vom Export ausschließen.", "Reporting")
        if not actions and not blockers:
            add(10, "Abschluss", "Fallbericht exportieren und archivieren", "Berichtsbundle, Evidence Manifest, Audit Chain und Retention Review finalisieren.", "Reporting", "finalize")
        return sorted(actions, key=lambda a: a["priority"], reverse=True)[:10]

    def persist_snapshot(self, case_id: str, notes: str = "") -> Dict[str, Any]:
        cockpit = self.build_cockpit(case_id)
        snap_id = new_id("cockpit")
        self.db.execute("""INSERT INTO cockpit_snapshots(snapshot_id,case_id,readiness_score,traffic_light,kpis_json,gates_json,blockers_json,warnings_json,next_actions_json,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [
            snap_id, case_id, cockpit["readiness_score"], cockpit["traffic_light"], dumps(cockpit["kpis"]), dumps(cockpit["gates"]), dumps(cockpit["blockers"]), dumps(cockpit["warnings"]), dumps(cockpit["next_actions"]), cockpit["generated_at"], notes
        ])
        self.audit.log("snapshot", "case_cockpit", snap_id, case_id, {"score": cockpit["readiness_score"], "traffic_light": cockpit["traffic_light"]})
        return self.db.one("SELECT * FROM cockpit_snapshots WHERE snapshot_id=?", [snap_id])

    def list_snapshots(self, case_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM cockpit_snapshots WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, limit])
        for r in rows:
            for key in ["kpis_json", "gates_json", "blockers_json", "warnings_json", "next_actions_json"]:
                r[key] = loads(r.get(key), [] if key.endswith("s_json") else {})
        return rows
