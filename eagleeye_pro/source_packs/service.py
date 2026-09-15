from __future__ import annotations
from typing import Any, Dict, List, Optional
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.security.policy import PolicyGate, MAX_MULTI_SEARCH_URLS

SOURCE_PACKS: List[Dict[str, Any]] = [
    {
        "pack_key": "person_identity",
        "title": "Person & Identität",
        "workflow_phase": "02_identity_web",
        "primary_question": "Wer ist die Zielperson öffentlich belegbar, und welche Namens-/Aliasanker sind tragfähig?",
        "source_types": ["web_search", "exact_name", "alias", "username", "email", "location_company"],
        "default_preset": "standard",
        "engines": ["Google", "Bing", "DuckDuckGo", "Brave"],
        "coverage_weight": 1.0,
        "guardrails": ["public_sources_only", "candidate_identity_only", "check_name_dopplers"],
        "capture_category": "Identitätsanker",
        "queries": [
            ("Exakter Name", '"{name}"', 95),
            ("Name + Ort", '"{name}" "{location}"', 84),
            ("Name + Firma", '"{name}" "{company}"', 88),
            ("Name + Alias", '"{name}" "{alias}"', 78),
            ("Username", '"{username}" "{name}"', 76),
            ("E-Mail", '"{email}"', 90),
        ],
    },
    {
        "pack_key": "profiles_accounts",
        "title": "Profile & Accounts",
        "workflow_phase": "03_profiles_context",
        "primary_question": "Welche öffentlichen Profil- und Accountspuren sind plausibel und welche Plattformkontexte passen?",
        "source_types": ["public_profiles", "professional_profiles", "developer_profiles", "community_mentions"],
        "default_preset": "deep_public",
        "engines": ["Google", "Bing", "DuckDuckGo", "Brave", "Startpage", "Ecosia", "Mojeek", "Yahoo"],
        "coverage_weight": 0.9,
        "guardrails": ["no_private_account_access", "no_login_bypass", "second_marker_required"],
        "capture_category": "Öffentliche Profile",
        "queries": [
            ("LinkedIn via Suchmaschine", '"{name}" site:linkedin.com', 82),
            ("Xing via Suchmaschine", '"{name}" site:xing.com', 79),
            ("GitHub Public", '"{username}" site:github.com', 74),
            ("Reddit/Foren", '"{username}" OR "{name}" reddit OR forum', 63),
            ("YouTube/Podcast", '"{name}" YouTube OR Podcast OR Vortrag', 61),
        ],
    },
    {
        "pack_key": "image_media",
        "title": "Bild & Medien",
        "workflow_phase": "04_image_media",
        "primary_question": "Welche öffentlichen Bild-, Medien- und Reverse-Spuren existieren ohne automatische biometrische Identifikation?",
        "source_types": ["image_search", "reverse_image", "media_pages", "news_images"],
        "default_preset": "image_reverse",
        "engines": ["Google Bilder", "Bing Bilder", "Yandex Bilder", "TinEye URL", "Google", "Bing"],
        "coverage_weight": 0.85,
        "guardrails": ["no_auto_face_id", "image_upload_opsec_review", "manual_visual_context_only"],
        "capture_category": "Bild-/Medienfund",
        "queries": [
            ("Name Bildsuche", '"{name}" Foto OR Bild OR portrait OR team', 72),
            ("Name + Firma Bild", '"{name}" "{company}" Foto OR Team OR Presse', 70),
            ("Name + Ort Medien", '"{name}" "{location}" Presse OR Foto OR Veranstaltung', 64),
            ("Bild-URL Reverse", '{image_url}', 90),
        ],
    },
    {
        "pack_key": "geo_places",
        "title": "Geo & Orte",
        "workflow_phase": "05_geo_places",
        "primary_question": "Welche öffentlichen Orts-, Event-, Firmen- und Kartenkontexte sind belegt oder widersprüchlich?",
        "source_types": ["maps", "local_web", "events", "news_place_context"],
        "default_preset": "geo_maps",
        "engines": ["Google Maps", "OpenStreetMap", "Google", "Google News", "Bing", "DuckDuckGo", "Brave"],
        "coverage_weight": 0.8,
        "guardrails": ["no_private_address_claim", "context_location_only", "classify_location_confidence"],
        "capture_category": "Geo-/Ortskontext",
        "queries": [
            ("Name + Ort", '"{name}" "{location}"', 76),
            ("Firma + Ort", '"{company}" "{location}"', 78),
            ("Name + Eventort", '"{name}" "{location}" Veranstaltung OR Vortrag OR Verein', 62),
            ("Maps Firma", '"{company}"', 70),
        ],
    },
    {
        "pack_key": "documents_archives",
        "title": "Dokumente & Archive",
        "workflow_phase": "06_docs_business_archives",
        "primary_question": "Welche PDFs, Office-Dokumente, Presse- und Archivspuren sind öffentlich/lizenziert verfügbar?",
        "source_types": ["pdf", "office_docs", "press", "archives", "wayback"],
        "default_preset": "document_media",
        "engines": ["Google", "Bing", "DuckDuckGo", "Brave", "Google News"],
        "coverage_weight": 0.95,
        "guardrails": ["no_paywall_bypass", "capture_source_context", "check_document_date"],
        "capture_category": "Dokument/Presse/Archiv",
        "queries": [
            ("PDF", '"{name}" filetype:pdf', 82),
            ("DOC/DOCX", '"{name}" filetype:doc OR filetype:docx', 62),
            ("Presse", '"{name}" Presse OR Interview OR Bericht', 70),
            ("Firma Dokument", '"{company}" "{name}" filetype:pdf OR Presse', 72),
            ("Domain Archivsuche", 'site:{domain} "{name}"', 74),
        ],
    },
    {
        "pack_key": "business_domain_infra",
        "title": "Firma / Domain / Infrastruktur",
        "workflow_phase": "06_docs_business_archives",
        "primary_question": "Welche öffentlichen Firmen-, Impressums-, Domain-, RDAP/DNS- und Zertifikatsspuren existieren?",
        "source_types": ["company", "register", "impressum", "rdap", "dns", "certificates"],
        "default_preset": "document_media",
        "engines": ["Google", "Bing", "DuckDuckGo", "Brave"],
        "coverage_weight": 0.9,
        "guardrails": ["non_invasive_only", "no_active_intrusion", "public_registry_context"],
        "capture_category": "Firma/Register/Domain",
        "queries": [
            ("Firma + Name", '"{company}" "{name}"', 86),
            ("Impressum", '"{company}" Impressum "{name}"', 84),
            ("Domain Site", 'site:{domain} "{name}"', 80),
            ("Domain Impressum", 'site:{domain} impressum OR kontakt', 74),
            ("Open Company Context", '"{company}" Handelsregister OR Register OR Bekanntmachung', 78),
        ],
    },
    {
        "pack_key": "counter_evidence",
        "title": "Gegenbelege & Namensdoppler",
        "workflow_phase": "07_counter_evidence",
        "primary_question": "Welche Gegenbelege, Namensdoppler, Alternativorte oder Widersprüche verhindern Fehlzuordnung?",
        "source_types": ["negative_matching", "name_doppler", "contradictions", "exclusion_markers"],
        "default_preset": "standard",
        "engines": ["Google", "Bing", "DuckDuckGo", "Brave"],
        "coverage_weight": 1.0,
        "guardrails": ["counter_evidence_required", "no_conclusion_without_review", "document_uncertainty"],
        "capture_category": "Gegenbeleg/Namensdoppler",
        "queries": [
            ("Namensdoppler", '"{name}" Namensdoppler OR "same name"', 72),
            ("Name ohne Firma", '"{name}" -"{company}"', 62),
            ("Name anderer Ort", '"{name}" -"{location}"', 60),
            ("Alias ohne Realname", '"{alias}" -"{name}"', 64),
            ("Username ohne Zielperson", '"{username}" -"{name}"', 64),
        ],
    },
]

PLACEHOLDERS = ["name", "alias", "username", "email", "location", "company", "domain", "image_url"]

class OSINTSourcePacksService:
    """Build 44.0: OSINT Source Packs Pro.

    Bündelt Suchmaschinen, Operator-Strategien, Guardrails und Capture-Zweck
    nach Ermittlungsfrage. Source Packs erzeugen keine Wahrheitsbehauptungen;
    sie liefern strukturierte öffentliche Suchaufträge, die weiterhin in Review
    und Evidence geprüft werden müssen.
    """

    def __init__(self, db: Database, audit: AuditService, search_workbench=None, query_factory=None, research_execution=None, intelligence_gap=None):
        self.db = db
        self.audit = audit
        self.search_workbench = search_workbench
        self.query_factory = query_factory
        self.research_execution = research_execution
        self.intelligence_gap = intelligence_gap
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS osint_source_packs (
          pack_id TEXT PRIMARY KEY, pack_key TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
          workflow_phase TEXT NOT NULL, primary_question TEXT NOT NULL, source_types_json TEXT NOT NULL,
          default_preset TEXT NOT NULL, engines_json TEXT NOT NULL, coverage_weight REAL DEFAULT 1.0,
          guardrails_json TEXT NOT NULL, capture_category TEXT NOT NULL, active INTEGER DEFAULT 1,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS osint_source_pack_queries (
          template_id TEXT PRIMARY KEY, pack_key TEXT NOT NULL, label TEXT NOT NULL,
          query_template TEXT NOT NULL, priority INTEGER DEFAULT 50, active INTEGER DEFAULT 1,
          created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(pack_key) REFERENCES osint_source_packs(pack_key) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS osint_source_pack_runs (
          run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT DEFAULT '',
          pack_key TEXT NOT NULL, query_count INTEGER DEFAULT 0, allowed_count INTEGER DEFAULT 0,
          blocked_count INTEGER DEFAULT 0, status TEXT DEFAULT 'generated', created_at TEXT NOT NULL,
          created_by TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS osint_source_pack_run_queries (
          run_query_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL, target_id TEXT DEFAULT '',
          pack_key TEXT NOT NULL, label TEXT NOT NULL, query_text TEXT NOT NULL, priority INTEGER DEFAULT 50,
          preset_key TEXT NOT NULL, engines_json TEXT NOT NULL, policy_status TEXT DEFAULT 'allowed', policy_reason TEXT DEFAULT '',
          phase_key TEXT DEFAULT '', capture_category TEXT DEFAULT '', created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES osint_source_pack_runs(run_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS osint_source_pack_coverage (
          coverage_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, pack_key TEXT NOT NULL,
          pack_title TEXT NOT NULL, status TEXT NOT NULL, query_count INTEGER DEFAULT 0,
          captures INTEGER DEFAULT 0, review_items INTEGER DEFAULT 0, evidence_items INTEGER DEFAULT 0,
          gap_level TEXT DEFAULT 'open', next_action TEXT DEFAULT '', updated_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS osint_source_pack_security_checks (
          check_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, run_id TEXT DEFAULT '', check_key TEXT NOT NULL,
          status TEXT NOT NULL, severity TEXT DEFAULT 'info', details_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        ''')
        self.db.conn.commit()

    def seed_defaults(self) -> Dict[str, Any]:
        self.ensure_schema()
        ts = now_ts(); created_packs = 0; created_queries = 0
        for pack in SOURCE_PACKS:
            exists = self.db.one("SELECT pack_key FROM osint_source_packs WHERE pack_key=?", [pack["pack_key"]])
            if not exists:
                self.db.execute('''INSERT INTO osint_source_packs(pack_id,pack_key,title,workflow_phase,primary_question,source_types_json,default_preset,engines_json,coverage_weight,guardrails_json,capture_category,active,created_at,updated_at,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [
                    new_id("osp"), pack["pack_key"], pack["title"], pack["workflow_phase"], pack["primary_question"],
                    dumps(pack["source_types"]), pack["default_preset"], dumps(pack["engines"]), pack["coverage_weight"],
                    dumps(pack["guardrails"]), pack["capture_category"], 1, ts, ts, "Build 44.0 Source Pack Seed"
                ])
                created_packs += 1
            existing_labels = {r["label"] for r in self.db.all("SELECT label FROM osint_source_pack_queries WHERE pack_key=?", [pack["pack_key"]])}
            for label, template, priority in pack["queries"]:
                if label not in existing_labels:
                    self.db.execute('''INSERT INTO osint_source_pack_queries(template_id,pack_key,label,query_template,priority,active,created_at,notes)
                    VALUES(?,?,?,?,?,?,?,?)''', [new_id("osq"), pack["pack_key"], label, template, int(priority), 1, ts, "Build 44.0 Query Template"])
                    created_queries += 1
        return {"created_packs": created_packs, "created_queries": created_queries, "total_packs": len(self.list_packs())}

    def list_packs(self, active_only: bool = True) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM osint_source_packs" + (" WHERE active=1" if active_only else "") + " ORDER BY rowid"
        rows = self.db.all(sql)
        for r in rows:
            r["source_types"] = loads(r.get("source_types_json"), [])
            r["engines"] = loads(r.get("engines_json"), [])
            r["guardrails"] = loads(r.get("guardrails_json"), [])
        return rows

    def get_pack(self, pack_key: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM osint_source_packs WHERE pack_key=?", [pack_key])
        if not row:
            raise KeyError("Source Pack nicht gefunden.")
        row["source_types"] = loads(row.get("source_types_json"), [])
        row["engines"] = loads(row.get("engines_json"), [])
        row["guardrails"] = loads(row.get("guardrails_json"), [])
        return row

    def _first_values(self, target: Dict[str, Any]) -> Dict[str, str]:
        def first(json_key: str) -> str:
            vals = loads(target.get(json_key), [])
            return str(vals[0]).strip() if vals else ""
        return {
            "name": (target.get("name") or "").strip(),
            "alias": first("aliases_json"),
            "username": first("usernames_json"),
            "email": first("emails_json"),
            "location": first("locations_json"),
            "company": first("companies_json"),
            "domain": first("domains_json"),
            "image_url": "",
        }

    def _target(self, case_id: str, target_id: str = "") -> Dict[str, Any]:
        row = None
        if target_id:
            row = self.db.one("SELECT * FROM targets WHERE case_id=? AND target_id=?", [case_id, target_id])
        if not row:
            row = self.db.one("SELECT * FROM targets WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        if not row:
            raise ValueError("Source Packs brauchen zuerst eine Zielperson mit Suchankern.")
        return row

    @staticmethod
    def _missing_required(template: str, values: Dict[str, str]) -> bool:
        for ph in PLACEHOLDERS:
            if "{" + ph + "}" in template and not values.get(ph):
                return True
        return False

    @staticmethod
    def _render_query(template: str, values: Dict[str, str]) -> str:
        # Leave no empty quotes behind because templates with missing required fields are skipped.
        rendered = template.format(**{k: v for k, v in values.items()})
        return " ".join(rendered.split()).strip()

    def generate_pack_queries(self, case_id: str, pack_key: str, target_id: str = "", created_by: str = "local-analyst", notes: str = "") -> Dict[str, Any]:
        pack = self.get_pack(pack_key)
        target = self._target(case_id, target_id)
        values = self._first_values(target)
        templates = self.db.all("SELECT * FROM osint_source_pack_queries WHERE pack_key=? AND active=1 ORDER BY priority DESC,label", [pack_key])
        ts = now_ts(); run_id = new_id("osr")
        rendered: List[Dict[str, Any]] = []
        for tmpl in templates:
            if self._missing_required(tmpl["query_template"], values):
                continue
            q = self._render_query(tmpl["query_template"], values)
            if not q or len(q) > 512:
                continue
            policy = PolicyGate.evaluate_query(q)
            rendered.append({
                "label": tmpl["label"], "query_text": q, "priority": int(tmpl.get("priority") or 50),
                "policy_status": "allowed" if policy.get("ok") else "blocked",
                "policy_reason": policy.get("reason", ""),
            })
        allowed = [r for r in rendered if r["policy_status"] == "allowed"]
        blocked = [r for r in rendered if r["policy_status"] != "allowed"]
        self.db.execute('''INSERT INTO osint_source_pack_runs(run_id,case_id,target_id,pack_key,query_count,allowed_count,blocked_count,status,created_at,created_by,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [run_id, case_id, target["target_id"], pack_key, len(rendered), len(allowed), len(blocked), "generated", ts, created_by, notes or "Build 44.0 Source Pack Run"])
        engines = (pack.get("engines") or [])[:MAX_MULTI_SEARCH_URLS]
        for r in rendered:
            self.db.execute('''INSERT INTO osint_source_pack_run_queries(run_query_id,run_id,case_id,target_id,pack_key,label,query_text,priority,preset_key,engines_json,policy_status,policy_reason,phase_key,capture_category,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [
                new_id("osrq"), run_id, case_id, target["target_id"], pack_key, r["label"], r["query_text"], r["priority"],
                pack["default_preset"], dumps(engines), r["policy_status"], r["policy_reason"], pack["workflow_phase"], pack["capture_category"], ts
            ])
        self.audit.log("generate", "osint_source_pack_run", run_id, case_id, {"pack_key": pack_key, "queries": len(rendered), "blocked": len(blocked)})
        self.run_security_checks(case_id, run_id=run_id)
        self.update_coverage(case_id)
        return self.dashboard(case_id, run_id=run_id)

    def generate_all_packs(self, case_id: str, target_id: str = "", created_by: str = "local-analyst") -> Dict[str, Any]:
        runs = []
        for p in self.list_packs():
            try:
                d = self.generate_pack_queries(case_id, p["pack_key"], target_id=target_id, created_by=created_by, notes="Build 44.0 Generate All Source Packs")
                runs.append(d.get("run"))
            except Exception as exc:
                self.audit.log("error", "osint_source_pack", p["pack_key"], case_id, {"error": str(exc)})
        dash = self.dashboard(case_id)
        dash["generated_runs"] = len([r for r in runs if r])
        return dash

    def latest_run(self, case_id: str, pack_key: str = "") -> Optional[Dict[str, Any]]:
        if pack_key:
            return self.db.one("SELECT * FROM osint_source_pack_runs WHERE case_id=? AND pack_key=? ORDER BY created_at DESC LIMIT 1", [case_id, pack_key])
        return self.db.one("SELECT * FROM osint_source_pack_runs WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])

    def list_run_queries(self, case_id: str, run_id: str = "", pack_key: str = "", allowed_only: bool = True) -> List[Dict[str, Any]]:
        clauses = ["case_id=?"]; params: List[Any] = [case_id]
        if run_id:
            clauses.append("run_id=?"); params.append(run_id)
        if pack_key:
            clauses.append("pack_key=?"); params.append(pack_key)
        if allowed_only:
            clauses.append("policy_status='allowed'")
        rows = self.db.all("SELECT * FROM osint_source_pack_run_queries WHERE " + " AND ".join(clauses) + " ORDER BY priority DESC,label", params)
        for r in rows:
            r["engines"] = loads(r.get("engines_json"), [])
        return rows

    def send_query_to_research_center(self, case_id: str, run_query_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM osint_source_pack_run_queries WHERE case_id=? AND run_query_id=?", [case_id, run_query_id])
        if not row:
            raise KeyError("Source-Pack-Query nicht gefunden.")
        if row.get("policy_status") != "allowed":
            raise ValueError("Diese Source-Pack-Query ist durch Guardrails blockiert.")
        if self.research_execution:
            rc = self.research_execution.set_active_phase(case_id, row["phase_key"], target_id=row.get("target_id", ""), query=row["query_text"])
        else:
            rc = {}
        return {"query": row["query_text"], "phase_key": row["phase_key"], "preset_key": row["preset_key"], "engines": loads(row.get("engines_json"), []), "research_center": rc}

    def run_multi_search_for_query(self, case_id: str, run_query_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM osint_source_pack_run_queries WHERE case_id=? AND run_query_id=?", [case_id, run_query_id])
        if not row:
            raise KeyError("Source-Pack-Query nicht gefunden.")
        if row.get("policy_status") != "allowed":
            raise ValueError("Diese Source-Pack-Query ist blockiert.")
        if not self.search_workbench:
            raise RuntimeError("Search Workbench nicht verfügbar.")
        launch = self.search_workbench.create_multi_search_launch(
            case_id, row["query_text"], preset_key=row["preset_key"], target_id=row.get("target_id", ""), bundle_key=row["pack_key"], notes="Build 44.0 Source Pack Multi-Search"
        )
        self.audit.log("launch", "osint_source_pack_query", run_query_id, case_id, {"launch_id": launch["launch_id"], "pack_key": row["pack_key"]})
        return launch

    def update_coverage(self, case_id: str) -> List[Dict[str, Any]]:
        self.ensure_schema()
        packs = self.list_packs()
        rows_out = []
        for p in packs:
            q_count = self.db.one("SELECT COUNT(*) AS c FROM osint_source_pack_run_queries WHERE case_id=? AND pack_key=? AND policy_status='allowed'", [case_id, p["pack_key"]])["c"] or 0
            captures = self.db.one("SELECT COUNT(*) AS c FROM source_captures WHERE case_id=?", [case_id])["c"] or 0
            review_items = self.db.one("SELECT COUNT(*) AS c FROM review_items WHERE case_id=?", [case_id])["c"] or 0
            evidence_items = self.db.one("SELECT COUNT(*) AS c FROM evidence_items WHERE case_id=?", [case_id])["c"] or 0
            # Coverage remains workflow-oriented, not person-scoring.
            if q_count == 0:
                status, gap, action = "open", "red", "Source Pack Queries erzeugen."
            elif captures == 0:
                status, gap, action = "queries_ready", "yellow", "Passende Source-Pack-Query im Research Center öffnen und Treffer capturen."
            elif evidence_items == 0:
                status, gap, action = "captured_needs_review", "yellow", "Captures in Review Fast Lane prüfen und Evidence freigeben."
            else:
                status, gap, action = "covered", "green", "Gegenbelege prüfen und Berichtslücken auswerten."
            existing = self.db.one("SELECT coverage_id FROM osint_source_pack_coverage WHERE case_id=? AND pack_key=?", [case_id, p["pack_key"]])
            ts = now_ts()
            if existing:
                self.db.execute('''UPDATE osint_source_pack_coverage SET pack_title=?,status=?,query_count=?,captures=?,review_items=?,evidence_items=?,gap_level=?,next_action=?,updated_at=? WHERE coverage_id=?''',
                                [p["title"], status, q_count, captures, review_items, evidence_items, gap, action, ts, existing["coverage_id"]])
                cov_id = existing["coverage_id"]
            else:
                cov_id = new_id("osc")
                self.db.execute('''INSERT INTO osint_source_pack_coverage(coverage_id,case_id,pack_key,pack_title,status,query_count,captures,review_items,evidence_items,gap_level,next_action,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', [cov_id, case_id, p["pack_key"], p["title"], status, q_count, captures, review_items, evidence_items, gap, action, ts])
            row = self.db.one("SELECT * FROM osint_source_pack_coverage WHERE coverage_id=?", [cov_id])
            rows_out.append(row)
        return rows_out

    def coverage(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM osint_source_pack_coverage WHERE case_id=? ORDER BY rowid", [case_id])
        if not rows:
            rows = self.update_coverage(case_id)
        return rows

    def run_security_checks(self, case_id: str, run_id: str = "") -> Dict[str, Any]:
        rows = self.list_run_queries(case_id, run_id=run_id, allowed_only=False) if run_id else self.list_run_queries(case_id, allowed_only=False)
        blocked = [r for r in rows if r.get("policy_status") != "allowed"]
        over = []
        for r in rows:
            if len(r.get("engines") or []) > MAX_MULTI_SEARCH_URLS:
                over.append(r.get("run_query_id"))
        status = "OSINT_SOURCE_PACKS_SECURITY_PASS" if not blocked and not over else "OSINT_SOURCE_PACKS_SECURITY_REVIEW"
        details = {
            "query_count": len(rows), "blocked_count": len(blocked), "over_url_limit": len(over),
            "guardrails": ["public_or_authorized_sources_only", "no_private_account_bypass", "no_captcha_bypass", "no_doxxing", "no_auto_face_id", "no_private_address_claim", "review_before_evidence"],
        }
        check_id = new_id("ossc")
        self.db.execute('''INSERT INTO osint_source_pack_security_checks(check_id,case_id,run_id,check_key,status,severity,details_json,created_at)
        VALUES(?,?,?,?,?,?,?,?)''', [check_id, case_id, run_id or "", "source_pack_guardrails", status, "info" if status.endswith("PASS") else "warning", dumps(details), now_ts()])
        return {"check_id": check_id, "status": status, **details}

    def dashboard(self, case_id: str, run_id: str = "") -> Dict[str, Any]:
        self.seed_defaults()
        run = self.db.one("SELECT * FROM osint_source_pack_runs WHERE run_id=? AND case_id=?", [run_id, case_id]) if run_id else self.latest_run(case_id)
        packs = self.list_packs()
        coverage = self.update_coverage(case_id)
        queries = self.list_run_queries(case_id, run_id=run["run_id"], allowed_only=False) if run else []
        checks = self.db.all("SELECT * FROM osint_source_pack_security_checks WHERE case_id=? ORDER BY created_at DESC LIMIT 5", [case_id])
        for c in checks:
            c["details"] = loads(c.get("details_json"), {})
        open_gaps = [c for c in coverage if c.get("gap_level") in {"red", "yellow"}]
        next_action = open_gaps[0]["next_action"] if open_gaps else "Source Pack Coverage vollständig genug; Gegenbelege und Report-Readiness prüfen."
        return {
            "status": "source_packs_ready", "packs": packs, "coverage": coverage, "run": run,
            "queries": queries, "query_count": len(queries), "allowed_count": len([q for q in queries if q.get("policy_status") == "allowed"]),
            "blocked_count": len([q for q in queries if q.get("policy_status") != "allowed"]),
            "open_gap_count": len(open_gaps), "next_action": next_action, "security_checks": checks,
            "guardrails": ["öffentliche/autorisierte Quellen", "Capture zuerst in Review", "Gegenbelege Pflicht vor Schlussfolgerung", "keine biometrische/Adress-Gewissheit"],
        }
