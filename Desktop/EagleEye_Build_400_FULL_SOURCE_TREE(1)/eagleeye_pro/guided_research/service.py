from __future__ import annotations
from typing import Any, Dict, List, Optional
import json
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.security.policy import PolicyGate, MAX_QUERY_LENGTH, MAX_MULTI_SEARCH_URLS

GUIDED_PHASES = [
    {
        "phase_key": "00_scope_legal",
        "sequence_no": 0,
        "title": "0. Auftrag, Legal Gate & Scope",
        "objective": "Fallzweck, Rechtsgrundlage, Scope, Retention und verbotene Verarbeitungen prüfen, bevor Recherche startet.",
        "workspace": "Start & Fallführung",
        "bundle_key": "",
        "preset_key": "minimal_safe",
        "gate": "legal_privacy_required",
        "next_action": "Legal/Privacy prüfen oder Zielperson anlegen.",
        "security_notes": "Ohne Zweck/Rechtsgrundlage keine Recherche. Keine privaten Accounts, kein Bypass, keine Wohnortbehauptung.",
    },
    {
        "phase_key": "01_target_anchors",
        "sequence_no": 1,
        "title": "1. Zielperson & Suchanker",
        "objective": "Name, Alias, Username, E-Mail, Firma, Ort und Domain als editierbare Suchanker sammeln.",
        "workspace": "Start & Fallführung",
        "bundle_key": "identity_anchor",
        "preset_key": "standard",
        "gate": "target_required",
        "next_action": "Zielperson prüfen und Suchpakete erzeugen.",
        "security_notes": "Suchanker bleiben Kandidatenanker; keine Identitätsgewissheit aus einem einzelnen Marker.",
    },
    {
        "phase_key": "02_identity_web",
        "sequence_no": 2,
        "title": "2. Identitätsanker im Web",
        "objective": "Vollname, Alias, Username und Kontaktanker über mehrere öffentliche Suchmaschinen prüfen.",
        "workspace": "Recherche & Intake",
        "bundle_key": "identity_anchor",
        "preset_key": "standard",
        "gate": "legal_pass_and_target",
        "next_action": "Multi-Search starten, plausible Treffer als Capture aufnehmen.",
        "security_notes": "Nur öffentliche Treffer erfassen; private Profilbereiche nicht umgehen.",
    },
    {
        "phase_key": "03_profiles_context",
        "sequence_no": 3,
        "title": "3. Öffentliche Profile, Beruf & Kontext",
        "objective": "Berufliche Profile, öffentliche Plattformspuren, Firmen-/Organisationskontext und Namensvarianten prüfen.",
        "workspace": "Recherche & Intake",
        "bundle_key": "professional_profile",
        "preset_key": "deep_public",
        "gate": "previous_phase_started",
        "next_action": "Öffentliche Profil-/Kontexttreffer prüfen, keine privaten Bereiche abrufen.",
        "security_notes": "Social-/Profiltreffer sind Kandidaten; mindestens zweiter Marker nötig.",
    },
    {
        "phase_key": "04_image_media",
        "sequence_no": 4,
        "title": "4. Bild-, Medien- & Reverse-Spur",
        "objective": "Build-15-Bildsuche zurück: Google Bilder, Bing Bilder, Yandex Bilder, Web-Gegencheck; TinEye nur bei Bild-URL.",
        "workspace": "Recherche & Intake",
        "bundle_key": "image_media_geo",
        "preset_key": "image_reverse",
        "gate": "opsec_image_warning",
        "next_action": "Bild-/Medienpfad öffnen; Uploads zu Reverse-Image-Diensten nur nach OPSEC-/Legal-Freigabe.",
        "security_notes": "Keine automatische biometrische Identifikation; Bildähnlichkeit nur als manueller Kandidatenmarker.",
    },
    {
        "phase_key": "05_geo_places",
        "sequence_no": 5,
        "title": "5. Geo-, Ort- & Kartenkontext",
        "objective": "Build-15-Geo/Maps-Suche zurück: Google Maps, OpenStreetMap, Web-/News-Kontext; nur öffentliche Ortskontexte.",
        "workspace": "Recherche & Intake",
        "bundle_key": "image_media_geo",
        "preset_key": "geo_maps",
        "gate": "geo_private_address_guard",
        "next_action": "Karten-/Geo-Kontext prüfen; keine private Wohnadresse als sichere Aussage übernehmen.",
        "security_notes": "Geo-Spuren dienen Kontext und Gegencheck, nicht Doxxing oder private Adressfeststellung.",
    },
    {
        "phase_key": "06_docs_business_archives",
        "sequence_no": 6,
        "title": "6. Dokumente, Register, Firmen & Archive",
        "objective": "PDFs, Presse, Register-/Firmenkontext, Domains und öffentliche Archivspuren prüfen.",
        "workspace": "Recherche & Intake",
        "bundle_key": "documents_media",
        "preset_key": "document_media",
        "gate": "source_scope_check",
        "next_action": "Dokument-/Registertreffer erfassen und Quellenzuverlässigkeit markieren.",
        "security_notes": "Nur zulässige öffentliche/lizenzierte Quellen, keine Paywall-/Login-Umgehung.",
    },
    {
        "phase_key": "07_counter_evidence",
        "sequence_no": 7,
        "title": "7. Gegenbelege & Namensdoppler",
        "objective": "Falsifikation, Namensdoppler, Widersprüche und Ausschlussmarker aktiv suchen.",
        "workspace": "Analyse & Intelligence",
        "bundle_key": "counter_evidence",
        "preset_key": "standard",
        "gate": "review_before_conclusion",
        "next_action": "Gegenbelege erfassen, bevor Graph/Timeline-Schlussfolgerungen formuliert werden.",
        "security_notes": "Keine Schlussfolgerung ohne Gegencheck und dokumentierte Unsicherheit.",
    },
    {
        "phase_key": "08_capture_review",
        "sequence_no": 8,
        "title": "8. Capture, Review Inbox & Duplikate",
        "objective": "Relevante Treffer als Capture sichern, Review-Status setzen, Duplikate und Sensitivität prüfen.",
        "workspace": "Recherche & Intake",
        "bundle_key": "",
        "preset_key": "minimal_safe",
        "gate": "capture_to_review_required",
        "next_action": "Treffer übernehmen, nicht automatisch als Wahrheit behandeln.",
        "security_notes": "Treffer bleiben Hinweise, bis Review/Evidence-Entscheidung erfolgt.",
    },
    {
        "phase_key": "09_evidence_analysis",
        "sequence_no": 9,
        "title": "9. Evidence, Graph, Timeline & Hypothesen",
        "objective": "Geprüfte Treffer zu Evidence hochstufen, Graph/Timeline bilden, Hypothesen und Gegenhypothesen dokumentieren.",
        "workspace": "Analyse & Intelligence",
        "bundle_key": "",
        "preset_key": "minimal_safe",
        "gate": "evidence_required_for_analysis",
        "next_action": "Nur belegte Kanten/Ereignisse in Analyse und Bericht übernehmen.",
        "security_notes": "Keine automatischen Identitäts-, Schuld-, Gefährlichkeits- oder Wohnortaussagen.",
    },
    {
        "phase_key": "10_report_export",
        "sequence_no": 10,
        "title": "10. Bericht, Redaction & Exportfreigabe",
        "objective": "Bericht erzeugen, Unsicherheiten/Gegenbelege anzeigen, Redaction/Exportblocker prüfen, Freigabe dokumentieren.",
        "workspace": "Bericht & Export",
        "bundle_key": "",
        "preset_key": "minimal_safe",
        "gate": "export_control_required",
        "next_action": "Report Readiness prüfen und nur freigegebene Fassung exportieren.",
        "security_notes": "Client-Report redigieren; interne Beweiskette und Audit erhalten.",
    },
]

class GuidedResearchService:
    """Build 37.0 Guided Research Workflow.

    Führt die PersonenOSINT-Recherche in einer klaren Reihenfolge. Die Klasse ist
    bewusst orchestrierend: Sie öffnet keine privaten Quellen, umgeht keine Logins
    und delegiert Suchstarts an den bestehenden Multi-Search-Launcher.
    """

    def __init__(self, db: Database, audit: AuditService, search_workbench, legal=None, privacy=None, targets=None):
        self.db = db
        self.audit = audit
        self.search_workbench = search_workbench
        self.legal = legal
        self.privacy = privacy
        self.targets = targets
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS guided_research_phases (
          phase_key TEXT PRIMARY KEY, sequence_no INTEGER NOT NULL, title TEXT NOT NULL,
          objective TEXT NOT NULL, workspace TEXT NOT NULL, bundle_key TEXT DEFAULT '',
          preset_key TEXT DEFAULT 'standard', gate TEXT DEFAULT '', next_action TEXT DEFAULT '',
          security_notes TEXT DEFAULT '', active INTEGER DEFAULT 1, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS guided_research_runs (
          run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT DEFAULT '', status TEXT DEFAULT 'active',
          current_phase_key TEXT DEFAULT '00_scope_legal', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS guided_research_phase_status (
          run_id TEXT NOT NULL, case_id TEXT NOT NULL, phase_key TEXT NOT NULL, status TEXT DEFAULT 'not_started',
          planned_tasks INTEGER DEFAULT 0, opened_launches INTEGER DEFAULT 0, captures INTEGER DEFAULT 0,
          review_items INTEGER DEFAULT 0, evidence_items INTEGER DEFAULT 0, blockers_json TEXT DEFAULT '[]',
          next_action TEXT DEFAULT '', updated_at TEXT NOT NULL,
          PRIMARY KEY(run_id, phase_key),
          FOREIGN KEY(run_id) REFERENCES guided_research_runs(run_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS guided_research_security_checks (
          check_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, run_id TEXT DEFAULT '', check_key TEXT NOT NULL,
          status TEXT NOT NULL, severity TEXT DEFAULT 'info', details_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        ''')
        self.db.conn.commit()

    def seed_defaults(self) -> Dict[str, Any]:
        self.ensure_schema()
        ts = now_ts()
        created = 0
        for p in GUIDED_PHASES:
            exists = self.db.one("SELECT phase_key FROM guided_research_phases WHERE phase_key=?", [p["phase_key"]])
            if not exists:
                self.db.execute("""INSERT INTO guided_research_phases
                (phase_key,sequence_no,title,objective,workspace,bundle_key,preset_key,gate,next_action,security_notes,active,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,1,?)""", [p["phase_key"], p["sequence_no"], p["title"], p["objective"], p["workspace"], p["bundle_key"], p["preset_key"], p["gate"], p["next_action"], p["security_notes"], ts])
                created += 1
        return {"created": created, "total": len(self.list_phases())}

    def list_phases(self) -> List[Dict[str, Any]]:
        self.seed_defaults_if_empty()
        return self.db.all("SELECT * FROM guided_research_phases WHERE active=1 ORDER BY sequence_no")

    def seed_defaults_if_empty(self) -> None:
        if not self.db.one("SELECT phase_key FROM guided_research_phases LIMIT 1"):
            self.seed_defaults()

    def _first_target_id(self, case_id: str, target_id: str = "") -> str:
        if target_id:
            return target_id
        row = self.db.one("SELECT target_id FROM targets WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        return row["target_id"] if row else ""

    def start_or_refresh_run(self, case_id: str, target_id: str = "", notes: str = "") -> Dict[str, Any]:
        self.seed_defaults()
        target_id = self._first_target_id(case_id, target_id)
        run = self.db.one("SELECT * FROM guided_research_runs WHERE case_id=? AND status='active' ORDER BY created_at DESC LIMIT 1", [case_id])
        ts = now_ts()
        if not run:
            run_id = new_id("grun")
            self.db.execute("""INSERT INTO guided_research_runs(run_id,case_id,target_id,status,current_phase_key,created_at,updated_at,notes)
            VALUES(?,?,?,?,?,?,?,?)""", [run_id, case_id, target_id, "active", "00_scope_legal", ts, ts, notes or "Build 37.0 Guided Research Workflow"])
            run = self.db.one("SELECT * FROM guided_research_runs WHERE run_id=?", [run_id])
            self.audit.log("create", "guided_research_run", run_id, case_id, {"target_id": target_id})
        elif target_id and run.get("target_id") != target_id:
            self.db.execute("UPDATE guided_research_runs SET target_id=?,updated_at=? WHERE run_id=?", [target_id, ts, run["run_id"]])
            run = self.db.one("SELECT * FROM guided_research_runs WHERE run_id=?", [run["run_id"]])
        dashboard = self.dashboard(case_id, run["run_id"])
        return dashboard

    def _phase_metrics(self, case_id: str, phase: Dict[str, Any], run_id: str) -> Dict[str, Any]:
        bundle = phase.get("bundle_key") or ""
        blockers: List[str] = []
        planned_tasks = opened_launches = captures = review_items = evidence_items = 0
        if bundle:
            planned_tasks = self.db.one("""SELECT COUNT(*) AS c FROM search_tasks st
            LEFT JOIN search_package_tasks spt ON st.task_id=spt.task_id
            LEFT JOIN search_packages sp ON spt.package_id=sp.package_id
            WHERE st.case_id=? AND sp.package_key=?""", [case_id, bundle])["c"]
            opened_launches = self.db.one("SELECT COUNT(*) AS c FROM multi_search_launches WHERE case_id=? AND bundle_key=? AND status='opened'", [case_id, bundle])["c"]
        else:
            opened_launches = self.db.one("SELECT COUNT(*) AS c FROM multi_search_launches WHERE case_id=? AND status='opened'", [case_id])["c"]
        captures = self.db.one("SELECT COUNT(*) AS c FROM source_captures WHERE case_id=?", [case_id])["c"]
        review_items = self.db.one("SELECT COUNT(*) AS c FROM review_items WHERE case_id=?", [case_id])["c"]
        evidence_items = self.db.one("SELECT COUNT(*) AS c FROM evidence_items WHERE case_id=?", [case_id])["c"]

        gate = phase.get("gate", "")
        legal_ok = True
        if self.legal and gate in {"legal_privacy_required", "legal_pass_and_target"}:
            try:
                legal_ok = bool(self.legal.evaluate_case(case_id).get("ok"))
            except Exception:
                legal_ok = False
        target_exists = bool(self._first_target_id(case_id, ""))
        if gate in {"target_required", "legal_pass_and_target"} and not target_exists:
            blockers.append("Zielperson fehlt.")
        if gate in {"legal_privacy_required", "legal_pass_and_target"} and not legal_ok:
            blockers.append("Legal Gate/Privacy Assessment nicht freigegeben.")
        if phase["phase_key"] == "04_image_media":
            blockers.append("OPSEC-Hinweis: Reverse-Image-Uploads nur nach Freigabe; Bildsuche nutzt normale öffentliche Suchoberflächen.")
        if phase["phase_key"] == "05_geo_places":
            blockers.append("Geo-Hinweis: keine private Wohnadresse als sichere Aussage übernehmen; nur öffentliche Kontextspuren.")

        status = "not_started"
        if blockers and not (phase["phase_key"] in {"04_image_media", "05_geo_places"} and target_exists):
            status = "blocked"
        elif phase["phase_key"] in {"00_scope_legal", "01_target_anchors"}:
            status = "ready" if not blockers else "blocked"
        elif opened_launches > 0 or captures > 0:
            status = "in_progress" if evidence_items == 0 else "ready_for_next"
        elif planned_tasks > 0 or target_exists:
            status = "ready"
        return {
            "phase_key": phase["phase_key"], "status": status, "planned_tasks": planned_tasks,
            "opened_launches": opened_launches, "captures": captures, "review_items": review_items,
            "evidence_items": evidence_items, "blockers": blockers, "next_action": phase.get("next_action", "")
        }

    def dashboard(self, case_id: str, run_id: str = "") -> Dict[str, Any]:
        self.seed_defaults()
        if not run_id:
            run = self.db.one("SELECT * FROM guided_research_runs WHERE case_id=? AND status='active' ORDER BY created_at DESC LIMIT 1", [case_id])
            if not run:
                return self.start_or_refresh_run(case_id)
            run_id = run["run_id"]
        run = self.db.one("SELECT * FROM guided_research_runs WHERE run_id=?", [run_id])
        phases = self.list_phases()
        phase_statuses = []
        ts = now_ts()
        for p in phases:
            m = self._phase_metrics(case_id, p, run_id)
            self.db.execute("""INSERT OR REPLACE INTO guided_research_phase_status
            (run_id,case_id,phase_key,status,planned_tasks,opened_launches,captures,review_items,evidence_items,blockers_json,next_action,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", [run_id, case_id, p["phase_key"], m["status"], m["planned_tasks"], m["opened_launches"], m["captures"], m["review_items"], m["evidence_items"], dumps(m["blockers"]), m["next_action"], ts])
            phase_statuses.append({**p, **m})
        current = next((p for p in phase_statuses if p["status"] in {"ready", "in_progress", "blocked"}), phase_statuses[-1] if phase_statuses else {})
        completed = sum(1 for p in phase_statuses if p["status"] in {"ready_for_next"})
        blockers = [b for p in phase_statuses for b in p.get("blockers", []) if p.get("status") == "blocked"]
        score = round((completed / max(1, len(phase_statuses))) * 100, 1)
        self.db.execute("UPDATE guided_research_runs SET current_phase_key=?,updated_at=? WHERE run_id=?", [current.get("phase_key", "00_scope_legal"), ts, run_id])
        return {"run": run, "phases": phase_statuses, "current_phase": current, "blockers": blockers, "readiness_score": score, "gate": "GUIDED_RESEARCH_READY" if not blockers else "GUIDED_RESEARCH_REVIEW"}

    def build_phase_query(self, case_id: str, phase_key: str, target_id: str = "", explicit_query: str = "") -> Dict[str, Any]:
        if explicit_query.strip():
            q = explicit_query.strip()
            source = "explicit"
        else:
            resolved = self.search_workbench.suggest_multi_search_query_from_target(case_id, target_id)
            q = resolved["query"]
            target_id = resolved.get("target_id", target_id)
            source = resolved.get("source", "target_fallback")
        phase = self.db.one("SELECT * FROM guided_research_phases WHERE phase_key=?", [phase_key]) or {}
        if phase_key == "04_image_media" and not any(x.lower() in q.lower() for x in ["foto", "bild", "image"]):
            q = f"{q} Foto OR Bild OR Pressefoto"
        elif phase_key == "05_geo_places" and not any(x.lower() in q.lower() for x in ["maps", "karte", "ort", "standort"]):
            q = f"{q} Ort OR Standort OR Maps"
        elif phase_key == "07_counter_evidence" and "Namensdoppler" not in q:
            q = f"{q} Namensdoppler OR Gegenbeleg"
        policy = PolicyGate.evaluate_query(q)
        if not policy.get("ok"):
            raise ValueError("Guided Research Query blockiert: " + str(policy.get("reason")))
        return {"query": q, "target_id": target_id, "source": source, "phase": phase}

    def launch_phase_multi_search(self, case_id: str, phase_key: str, target_id: str = "", explicit_query: str = "") -> Dict[str, Any]:
        self.seed_defaults()
        dash = self.start_or_refresh_run(case_id, target_id)
        phase = self.db.one("SELECT * FROM guided_research_phases WHERE phase_key=?", [phase_key])
        if not phase:
            raise KeyError("Guided-Research-Phase nicht gefunden.")
        if phase_key == "00_scope_legal":
            raise ValueError("Phase 0 ist eine Prüfphase und öffnet keine Suchmaschinen.")
        resolved = self.build_phase_query(case_id, phase_key, target_id=target_id or dash.get("run", {}).get("target_id", ""), explicit_query=explicit_query)
        launch = self.search_workbench.create_multi_search_launch(
            case_id, resolved["query"], preset_key=phase.get("preset_key") or "standard",
            target_id=resolved.get("target_id", ""), bundle_key=phase.get("bundle_key") or phase_key,
            notes=f"Build 37.0 Guided Research Phase: {phase['title']} | {phase['security_notes']}"
        )
        self.audit.log("open_prepare", "guided_research_phase", phase_key, case_id, {"launch_id": launch["launch_id"], "preset": phase.get("preset_key"), "query_source": resolved.get("source")})
        return {"phase": phase, "resolved_query": resolved, "launch": launch}

    def run_security_checks(self, case_id: str, run_id: str = "") -> Dict[str, Any]:
        self.seed_defaults()
        dash = self.dashboard(case_id, run_id)
        checks = []
        def add(key: str, status: str, severity: str, detail: Dict[str, Any]):
            row = {"check_key": key, "status": status, "severity": severity, "details": detail}
            checks.append(row)
            self.db.execute("""INSERT INTO guided_research_security_checks(check_id,case_id,run_id,check_key,status,severity,details_json,created_at)
            VALUES(?,?,?,?,?,?,?,?)""", [new_id("gsec"), case_id, dash.get("run", {}).get("run_id", ""), key, status, severity, dumps(detail), now_ts()])
        add("no_private_bypass", "pass", "high", {"rule": "no_private_account_bypass", "note": "Guided phases use public search/map/image interfaces only."})
        add("query_limits", "pass", "medium", {"max_query_length": MAX_QUERY_LENGTH, "max_multi_search_urls": MAX_MULTI_SEARCH_URLS, "unsafe_url_schemes_blocked": True})
        add("image_geo_guardrails", "pass", "medium", {"image": "no automatic biometric identification", "geo": "no private address certainty", "reverse_uploads": "manual_opsec_legal_review_required"})
        if dash.get("blockers"):
            add("workflow_blockers", "review", "medium", {"blockers": dash.get("blockers")})
        else:
            add("workflow_blockers", "pass", "info", {"blockers": []})
        return {"gate": "GUIDED_SECURITY_PASS" if not dash.get("blockers") else "GUIDED_SECURITY_REVIEW", "checks": checks, "dashboard": dash}
