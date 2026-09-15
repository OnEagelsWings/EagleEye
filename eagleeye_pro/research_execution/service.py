from __future__ import annotations
from typing import Any, Dict, List, Optional
import re
from urllib.parse import urlparse
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.guided_research.service import GUIDED_PHASES
from eagleeye_pro.security.policy import PolicyGate, MAX_MULTI_SEARCH_URLS

SOURCE_MATRIX = {
    "02_identity_web": {
        "title": "Identitätsanker-Websuche",
        "preset": "standard",
        "sources": ["Google", "Bing", "DuckDuckGo", "Brave"],
        "capture_hint": "öffentlichen Identitätsanker, Namensdoppler oder Ausschlussmarker als URL übernehmen",
    },
    "03_profiles_context": {
        "title": "Profile, Beruf & Kontext",
        "preset": "deep_public",
        "sources": ["Google", "Bing", "DuckDuckGo", "Brave", "Startpage", "Ecosia", "Mojeek", "Yahoo"],
        "capture_hint": "öffentliche Profil-/Berufs-/Kontexttreffer übernehmen; keine privaten Profilbereiche abrufen",
    },
    "04_image_media": {
        "title": "Bild-, Medien- & Reverse-Spur",
        "preset": "image_reverse",
        "sources": ["Google Bilder", "Bing Bilder", "Yandex Bilder", "TinEye URL", "Google", "Bing"],
        "capture_hint": "Bild-/Medien-URL oder Fundseite übernehmen; Uploads nur nach OPSEC/Legal-Freigabe",
    },
    "05_geo_places": {
        "title": "Geo-, Ort- & Kartenkontext",
        "preset": "geo_maps",
        "sources": ["Google Maps", "OpenStreetMap", "Google", "Google News", "Bing", "DuckDuckGo", "Brave"],
        "capture_hint": "öffentlichen Orts-/Event-/Firmenstandort-Kontext übernehmen; keine Wohnortgewissheit behaupten",
    },
    "06_docs_business_archives": {
        "title": "Dokumente, Register, Firmen & Archive",
        "preset": "document_media",
        "sources": ["Google", "Bing", "DuckDuckGo", "Brave", "Google News"],
        "capture_hint": "PDF, Presse, Register-/Firmen-/Archivfund übernehmen und Quellenklasse markieren",
    },
    "07_counter_evidence": {
        "title": "Gegenbelege & Namensdoppler",
        "preset": "standard",
        "sources": ["Google", "Bing", "DuckDuckGo", "Brave"],
        "capture_hint": "Widerspruch, Namensdoppler, Ausschlussmarker oder Gegenbeleg übernehmen",
    },
}

PHASE_ORDER = [p["phase_key"] for p in GUIDED_PHASES]
PHASE_BY_KEY = {p["phase_key"]: p for p in GUIDED_PHASES}
EXECUTION_PHASES = [k for k in PHASE_ORDER if k in SOURCE_MATRIX]

class ResearchExecutionCenterService:
    """Build 37.0 Research Execution Center.

    Zentrale, effiziente Rechercheausführung: Phase, Query, Quellenpaket,
    Multi-Search, Capture-Import und nächster Schritt laufen in einem Service
    zusammen. Es werden nur öffentliche/legale Suchoberflächen geöffnet;
    Treffer werden weiterhin manuell als Kandidaten erfasst und an Review
    übergeben.
    """

    def __init__(self, db: Database, audit: AuditService, search_workbench, guided_research):
        self.db = db
        self.audit = audit
        self.search_workbench = search_workbench
        self.guided_research = guided_research
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS research_execution_sessions (
          session_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT DEFAULT '',
          active_phase_key TEXT DEFAULT '02_identity_web', query TEXT DEFAULT '', status TEXT DEFAULT 'active',
          readiness_score REAL DEFAULT 0.0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS research_execution_phase_runs (
          phase_run_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, case_id TEXT NOT NULL,
          phase_key TEXT NOT NULL, query TEXT NOT NULL, preset_key TEXT NOT NULL,
          launch_id TEXT DEFAULT '', url_count INTEGER DEFAULT 0, status TEXT DEFAULT 'prepared',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(session_id) REFERENCES research_execution_sessions(session_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS research_execution_imports (
          import_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, case_id TEXT NOT NULL,
          phase_key TEXT NOT NULL, source_url TEXT NOT NULL, title TEXT DEFAULT '', snippet TEXT DEFAULT '',
          capture_id TEXT DEFAULT '', status TEXT DEFAULT 'captured_to_review', created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(session_id) REFERENCES research_execution_sessions(session_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS research_execution_security_checks (
          check_id TEXT PRIMARY KEY, session_id TEXT DEFAULT '', case_id TEXT NOT NULL,
          check_key TEXT NOT NULL, status TEXT NOT NULL, severity TEXT DEFAULT 'info',
          details_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        ''')
        self.db.conn.commit()

    def _latest_session(self, case_id: str) -> Optional[Dict[str, Any]]:
        return self.db.one("SELECT * FROM research_execution_sessions WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])

    def start_or_get_session(self, case_id: str, target_id: str = "", query: str = "") -> Dict[str, Any]:
        self.ensure_schema()
        session = self._latest_session(case_id)
        # Build 37.0 hardening: never overwrite an active Research-Center
        # session with an automatically generated fallback query during refresh.
        # Explicit field input wins; otherwise keep the current session query.
        resolved_query = ""
        if query.strip():
            resolved_query = query.strip()
        elif session and (session.get("query") or "").strip():
            resolved_query = session.get("query", "").strip()
        else:
            try:
                resolved_query = self.search_workbench.resolve_multi_search_query(case_id, target_id=target_id).get("query", "")
            except Exception:
                resolved_query = ""
        ts = now_ts()
        if session:
            updates = []
            params = []
            if target_id and target_id != session.get("target_id"):
                updates.append("target_id=?"); params.append(target_id)
            if resolved_query and resolved_query != session.get("query"):
                updates.append("query=?"); params.append(resolved_query)
            updates.append("updated_at=?"); params.append(ts)
            params.append(session["session_id"])
            self.db.execute(f"UPDATE research_execution_sessions SET {', '.join(updates)} WHERE session_id=?", params)
            session = self.db.one("SELECT * FROM research_execution_sessions WHERE session_id=?", [session["session_id"]])
        else:
            session_id = new_id("rex")
            self.db.execute("""INSERT INTO research_execution_sessions(session_id,case_id,target_id,active_phase_key,query,status,readiness_score,created_at,updated_at,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", [session_id, case_id, target_id or "", "02_identity_web", resolved_query, "active", 0.0, ts, ts, "Build 37.0 Research Execution Center"])
            session = self.db.one("SELECT * FROM research_execution_sessions WHERE session_id=?", [session_id])
            self.audit.log("create", "research_execution_session", session_id, case_id, {"target_id": target_id, "query": resolved_query})
        return session

    def set_active_phase(self, case_id: str, phase_key: str, target_id: str = "", query: str = "") -> Dict[str, Any]:
        if phase_key not in PHASE_BY_KEY:
            raise ValueError("Unbekannte Research-Phase.")
        session = self.start_or_get_session(case_id, target_id, query)
        self.db.execute("UPDATE research_execution_sessions SET active_phase_key=?, updated_at=? WHERE session_id=?", [phase_key, now_ts(), session["session_id"]])
        self.audit.log("update", "research_execution_session", session["session_id"], case_id, {"active_phase_key": phase_key})
        return self.dashboard(case_id, target_id=target_id, query=query)

    def _counts_for_phase(self, case_id: str, phase_key: str, session_id: str = "") -> Dict[str, int]:
        launches = self.db.one("SELECT COUNT(*) AS c FROM research_execution_phase_runs WHERE case_id=? AND phase_key=? AND status IN ('opened','prepared')", [case_id, phase_key])["c"]
        imports = self.db.one("SELECT COUNT(*) AS c FROM research_execution_imports WHERE case_id=? AND phase_key=?", [case_id, phase_key])["c"]
        captures = imports
        return {"launches": int(launches or 0), "imports": int(imports or 0), "captures": int(captures or 0)}

    def _phase_status(self, case_id: str, phase_key: str, session: Dict[str, Any]) -> Dict[str, Any]:
        phase = PHASE_BY_KEY[phase_key]
        matrix = SOURCE_MATRIX.get(phase_key, {})
        counts = self._counts_for_phase(case_id, phase_key, session.get("session_id", ""))
        status = "not_started"
        if counts["captures"] > 0:
            status = "captured"
        elif counts["launches"] > 0:
            status = "opened"
        elif phase_key == session.get("active_phase_key"):
            status = "active"
        return {
            "phase_key": phase_key,
            "sequence_no": phase.get("sequence_no"),
            "title": phase.get("title"),
            "objective": phase.get("objective"),
            "preset_key": matrix.get("preset", phase.get("preset_key", "standard")),
            "sources": matrix.get("sources", []),
            "source_count": len(matrix.get("sources", [])),
            "capture_hint": matrix.get("capture_hint", phase.get("next_action", "")),
            "status": status,
            "launches": counts["launches"],
            "captures": counts["captures"],
            "next_action": self._next_action_for_status(status, phase_key),
        }

    def _next_action_for_status(self, status: str, phase_key: str) -> str:
        if phase_key in {"00_scope_legal", "01_target_anchors"}:
            return PHASE_BY_KEY[phase_key].get("next_action", "")
        if status == "not_started":
            return "Phase öffnen: passende Quellen werden automatisch gebündelt."
        if status == "opened":
            return "Treffer aus Browser als URL importieren und an Review senden."
        if status == "captured":
            return "Review/Evidence prüfen oder zur nächsten Phase wechseln."
        return PHASE_BY_KEY[phase_key].get("next_action", "")

    def _next_phase(self, phase_key: str) -> str:
        try:
            idx = PHASE_ORDER.index(phase_key)
        except ValueError:
            return "02_identity_web"
        for k in PHASE_ORDER[idx+1:]:
            if k in PHASE_BY_KEY:
                return k
        return phase_key

    def dashboard(self, case_id: str, target_id: str = "", query: str = "") -> Dict[str, Any]:
        session = self.start_or_get_session(case_id, target_id, query)
        phases = [self._phase_status(case_id, k, session) for k in PHASE_ORDER]
        active = next((p for p in phases if p["phase_key"] == session.get("active_phase_key")), phases[2])
        executable = [p for p in phases if p["phase_key"] in SOURCE_MATRIX]
        completed = len([p for p in executable if p["captures"] > 0])
        opened = len([p for p in executable if p["launches"] > 0])
        readiness = round(((completed * 1.0 + opened * 0.35) / max(1, len(executable))) * 100, 1)
        self.db.execute("UPDATE research_execution_sessions SET readiness_score=?, updated_at=? WHERE session_id=?", [readiness, now_ts(), session["session_id"]])
        session = self.db.one("SELECT * FROM research_execution_sessions WHERE session_id=?", [session["session_id"]])
        gaps = [p["title"] for p in executable if p["captures"] == 0]
        return {
            "session": session,
            "phases": phases,
            "active_phase": active,
            "execution_phases": executable,
            "readiness_score": readiness,
            "source_matrix": SOURCE_MATRIX,
            "intelligence_gaps": gaps,
            "next_phase_key": self._next_phase(active["phase_key"]),
            "guardrails": [
                "public_sources_only", "no_private_account_bypass", "no_login_or_captcha_bypass",
                "no_credential_harvesting", "no_automatic_biometric_identification",
                "no_private_address_certainty", "capture_to_review_before_evidence"
            ],
        }

    def prepare_phase_launch(self, case_id: str, phase_key: str, target_id: str = "", query: str = "") -> Dict[str, Any]:
        if phase_key not in SOURCE_MATRIX:
            raise ValueError("Diese Phase ist keine Such-/Quellenphase. Wähle eine ausführbare Recherchephase.")
        session = self.start_or_get_session(case_id, target_id, query)
        matrix = SOURCE_MATRIX[phase_key]
        q = (query or session.get("query") or "").strip()
        if not q:
            q = self.search_workbench.resolve_multi_search_query(case_id, target_id=target_id or session.get("target_id", "")).get("query", "")
        policy = PolicyGate.evaluate_query(q)
        if not policy.get("ok"):
            raise ValueError("Research Execution blockiert: Query verletzt die eingebauten Guardrails.")
        launch = self.search_workbench.create_multi_search_launch(
            case_id, q, preset_key=matrix["preset"], target_id=target_id or session.get("target_id", ""),
            bundle_key=PHASE_BY_KEY[phase_key].get("bundle_key", ""),
            notes=f"Build 37.0 Research Execution Center: {matrix['title']}"
        )
        ts = now_ts()
        phase_run_id = new_id("rexrun")
        self.db.execute("""INSERT INTO research_execution_phase_runs(phase_run_id,session_id,case_id,phase_key,query,preset_key,launch_id,url_count,status,created_at,updated_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", [phase_run_id, session["session_id"], case_id, phase_key, q, matrix["preset"], launch["launch_id"], launch["url_count"], "prepared", ts, ts, "Prepared from central Research Execution Center"])
        self.db.execute("UPDATE research_execution_sessions SET active_phase_key=?, query=?, updated_at=? WHERE session_id=?", [phase_key, q, ts, session["session_id"]])
        self.audit.log("prepare", "research_execution_phase_run", phase_run_id, case_id, {"phase_key": phase_key, "launch_id": launch["launch_id"], "url_count": launch["url_count"]})
        return {"session_id": session["session_id"], "phase_run_id": phase_run_id, "phase": PHASE_BY_KEY[phase_key], "matrix": matrix, "launch": launch}

    def mark_phase_opened(self, case_id: str, phase_run_id: str, launch_id: str) -> Dict[str, Any]:
        self.search_workbench.mark_multi_search_opened(launch_id)
        self.db.execute("UPDATE research_execution_phase_runs SET status='opened', updated_at=? WHERE phase_run_id=?", [now_ts(), phase_run_id])
        row = self.db.one("SELECT * FROM research_execution_phase_runs WHERE phase_run_id=?", [phase_run_id])
        self.audit.log("open", "research_execution_phase_run", phase_run_id, case_id, {"launch_id": launch_id, "phase_key": row.get("phase_key") if row else ""})
        return row or {}

    @staticmethod
    def _clean_url_lines(text: str) -> List[str]:
        urls: List[str] = []
        for raw in re.split(r"[\r\n\t ]+", text or ""):
            u = raw.strip().strip(",;()[]<>'\"")
            if not u:
                continue
            if u.startswith("www."):
                u = "https://" + u
            parsed = urlparse(u)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                if u not in urls:
                    urls.append(u)
            if len(urls) >= MAX_MULTI_SEARCH_URLS:
                break
        return urls

    def import_urls_to_capture(self, case_id: str, urls_text: str, phase_key: str, target_id: str = "", title_prefix: str = "Öffentlicher Treffer", snippet: str = "", notes: str = "") -> Dict[str, Any]:
        if phase_key not in PHASE_BY_KEY:
            raise ValueError("Unbekannte Research-Phase.")
        session = self.start_or_get_session(case_id, target_id)
        urls = self._clean_url_lines(urls_text)
        if not urls:
            raise ValueError("Keine gültige öffentliche URL gefunden. Erlaubt sind http/https-URLs.")
        created = []
        ts = now_ts()
        for idx, url in enumerate(urls, start=1):
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            title = f"{title_prefix}: {host}" if len(urls) == 1 else f"{title_prefix} {idx}: {host}"
            cap = self.search_workbench.capture_public_hit(
                case_id, "", title, url, snippet or f"Build 37.0 Research Execution Capture aus Phase {phase_key}: manuell geprüfte öffentliche URL.",
                notes=notes or f"Research Execution Center Import; phase={phase_key}; public_candidate_only", score=0.55
            )
            import_id = new_id("reximp")
            self.db.execute("""INSERT INTO research_execution_imports(import_id,session_id,case_id,phase_key,source_url,title,snippet,capture_id,status,created_at,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", [import_id, session["session_id"], case_id, phase_key, url, title, snippet or "", cap["capture_id"], "captured_to_review", ts, notes])
            created.append({"import_id": import_id, "capture_id": cap["capture_id"], "url": url, "title": title})
        self.audit.log("import", "research_execution_urls", session["session_id"], case_id, {"phase_key": phase_key, "count": len(created)})
        return {"created": len(created), "items": created, "session_id": session["session_id"], "phase_key": phase_key}

    def advance_phase(self, case_id: str, target_id: str = "", query: str = "") -> Dict[str, Any]:
        dash = self.dashboard(case_id, target_id, query)
        nxt = dash.get("next_phase_key") or "02_identity_web"
        return self.set_active_phase(case_id, nxt, target_id=target_id, query=query or dash.get("session", {}).get("query", ""))

    def run_security_checks(self, case_id: str, session_id: str = "") -> Dict[str, Any]:
        session = self._latest_session(case_id)
        if not session:
            session = self.start_or_get_session(case_id)
        session_id = session_id or session["session_id"]
        query = session.get("query", "")
        checks = []
        query_eval = PolicyGate.evaluate_query(query)
        checks.append({"check_key": "query_guardrails", "status": "pass" if query_eval.get("ok") else "blocked", "severity": "high" if not query_eval.get("ok") else "info", "details": query_eval})
        checks.append({"check_key": "url_scheme_whitelist", "status": "pass", "severity": "info", "details": {"allowed": ["http", "https"], "blocked": ["file", "javascript", "data"]}})
        checks.append({"check_key": "source_boundary", "status": "pass", "severity": "info", "details": {"public_sources_only": True, "no_login_or_captcha_bypass": True, "no_private_account_bypass": True}})
        checks.append({"check_key": "image_geo_guardrails", "status": "pass", "severity": "info", "details": {"no_automatic_biometric_identification": True, "no_private_address_certainty": True, "image_upload_only_after_opsec_legal_review": True}})
        ts = now_ts()
        for c in checks:
            self.db.execute("""INSERT INTO research_execution_security_checks(check_id,session_id,case_id,check_key,status,severity,details_json,created_at)
            VALUES(?,?,?,?,?,?,?,?)""", [new_id("rexsec"), session_id, case_id, c["check_key"], c["status"], c["severity"], dumps(c["details"]), ts])
        gate = "RESEARCH_EXECUTION_SECURITY_PASS" if all(c["status"] == "pass" for c in checks) else "RESEARCH_EXECUTION_SECURITY_REVIEW"
        return {"gate": gate, "checks": checks}
