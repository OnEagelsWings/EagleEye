from __future__ import annotations

from typing import Any, Dict, List

from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.audit.service import AuditService


DEFAULT_PLAYBOOKS: List[Dict[str, Any]] = [
    {
        "key": "due_diligence",
        "title": "Due Diligence / Reputationsprüfung",
        "case_type": "private_intelligence",
        "risk_level": "medium",
        "purpose_template": "Rechtmäßige Prüfung öffentlich verfügbarer Reputations-, Identitäts- und Unternehmensanker im Mandatsauftrag.",
        "legal_basis_hint": "Art. 6 Abs. 1 lit. f DSGVO / Mandatsauftrag / berechtigtes Interesse; Interessenabwägung dokumentieren.",
        "description": "Strukturierter Workflow für Mandanten-, Register-, Presse-, Firmen- und Reputationsprüfung ohne private Quellenumgehung.",
        "allowed_sources": ["öffentliche Suchmaschinen", "Presse/Archive", "Unternehmensregister", "Firmenwebseiten", "öffentliche Profile", "Wayback/RDAP/DNS"],
        "forbidden_actions": ["private Accounts", "Login-/Captcha-Bypass", "heimliche Kontaktaufnahme", "biometrische Identitätsbehauptung", "Doxxing/Adressfixierung"],
        "phases": [
            "Mandat, Zweck und Scope dokumentieren", "Legal/Privacy Assessment abschließen", "Identitätsanker und Namensvarianten erfassen",
            "Quellenplan: Presse, Register, Firma, Webarchive", "Search Workbench mit Gegenbelegsuche ausführen", "Review/Duplikate/Source Reliability prüfen",
            "Evidence Vault und Redaction vorbereiten", "Graph/Timeline für Firmen- und Reputationsbezüge", "Mandantenbericht und internes Dossier erzeugen",
        ],
        "deliverables": ["Redacted Client Report", "Internal Analyst Report", "Evidence Annex", "Graph/Timeline Export"],
        "quality_gates": ["Legal Gate approved", "Privacy Export Blocker cleared", "Evidence Manifest OK", "Gegenbelege geprüft", "Vier-Augen-Freigabe bei Export"],
    },
    {
        "key": "missing_person_leads",
        "title": "Vermisstenhinweise / Missing-Person Leads",
        "case_type": "safety_support",
        "risk_level": "high",
        "purpose_template": "Strukturierte Sammlung und Bewertung öffentlich verfügbarer Hinweise zur Unterstützung zuständiger Stellen und Angehöriger im rechtmäßigen Rahmen.",
        "legal_basis_hint": "Mandatsauftrag/lebenswichtige Interessen können berührt sein; Behördenzuständigkeit, Datenminimierung und Schutzinteressen besonders prüfen.",
        "description": "Hinweisworkflow für öffentlich zugängliche Spuren, Timeline und Sichtungs-/Kontaktkandidaten. Keine Selbstjustiz, keine verdeckte Überwachung.",
        "allowed_sources": ["öffentliche Suchmaschinen", "offizielle Vermisstenmeldungen", "Presse", "öffentliche Social-Posts", "Karten-/Ortskontext", "Kontakt zu Behörden nur außerhalb des Tools dokumentieren"],
        "forbidden_actions": ["Stalking", "private Accounts", "Kontaktaufnahme mit Minderjährigen", "heimliche Ortung", "Doxxing", "Konfrontation von Verdächtigen"],
        "phases": [
            "Schutzstatus, Alter und Behördenbezug prüfen", "Legal/Privacy High-Risk-Assessment", "letzte bestätigte öffentliche Hinweise erfassen",
            "Timeline und Sichtungsorte als Kandidaten modellieren", "öffentlich belegte Online-Spuren sammeln", "Hinweise streng als Leads klassifizieren",
            "Gegenbelege und Namensdoppler prüfen", "sensitive Daten redigieren", "Hinweisbericht für berechtigte Stelle erstellen",
        ],
        "deliverables": ["Lead Summary", "Timeline Report", "Redacted Evidence Annex", "Hand-off Notes"],
        "quality_gates": ["Minderjährigen-/Schutzinteressen geprüft", "DPIA/DSFA Trigger geprüft", "keine privaten Adressen im Client Export", "Behörden-/Angehörigen-Scope dokumentiert"],
    },
    {
        "key": "fraud_scam",
        "title": "Betrug / Scam / Alias-Analyse",
        "case_type": "fraud_investigation",
        "risk_level": "medium",
        "purpose_template": "Prüfung öffentlich belegbarer Alias-, Domain-, Zahlungs-/Kontakt- und Reputationsspuren im Zusammenhang mit einem Betrugsverdacht.",
        "legal_basis_hint": "Berechtigtes Interesse / Rechtsverteidigung / Mandatsauftrag; strafrechtliche Verdachtsdaten besonders vorsichtig und als Verdacht kennzeichnen.",
        "description": "Workflow für Alias-Clustering, Domain-/Infrastrukturspuren, öffentliche Beschwerden, Screenshots, Evidence-Chain und Gegenhypothesen.",
        "allowed_sources": ["öffentliche Suchmaschinen", "Domain/RDAP/DNS", "Webarchive", "öffentliche Foren/Beschwerdeportale", "Presse", "Screenshots aus mandatsbezogenen Unterlagen"],
        "forbidden_actions": ["Hackback", "Credential Stuffing", "Phishing", "Social Engineering", "private Konten", "Schuldbehauptung ohne Beleg"],
        "phases": [
            "Mandatsmaterial und Scope erfassen", "Verdachtsdaten als sensitiv markieren", "Alias-/Username-/Domainanker erfassen",
            "RDAP/DNS/Webarchive prüfen", "öffentliche Beschwerde-/Pressehinweise suchen", "Review mit Duplicate-/Source-Reliability",
            "Graph: Alias–Domain–Kontakt–Dokument", "Gegenhypothesen erstellen", "Internal Analyst Report mit Evidenzindex",
        ],
        "deliverables": ["Internal Analyst Report", "Alias Graph", "Evidence Annex", "Client-safe Summary"],
        "quality_gates": ["Art.-10-Hinweis geprüft", "keine Schuldentscheidung", "Gegenhypothesen vorhanden", "Evidence Hash Manifest OK"],
    },
    {
        "key": "corporate_security",
        "title": "Corporate Security / Insider- und Umfeldprüfung",
        "case_type": "corporate_security",
        "risk_level": "high",
        "purpose_template": "Rechtmäßige Prüfung öffentlich verfügbarer Risiko-, Umfeld- und Expositionshinweise für Corporate-Security-Zwecke.",
        "legal_basis_hint": "Berechtigtes Interesse mit strenger Verhältnismäßigkeit; Beschäftigtendaten, Betriebsrat, Arbeitsrecht und Datenschutz besonders prüfen.",
        "description": "Corporate-Security-Workflow mit Scope, Risikoindikatoren, Redaction, Legal Review und strenger Datenminimierung.",
        "allowed_sources": ["Presse", "Unternehmensquellen", "öffentliche Register", "öffentliche Fach-/Konferenzprofile", "öffentliche technische Spuren"],
        "forbidden_actions": ["Mitarbeiterüberwachung", "private Accounts", "Gesinnungsprofile", "verdeckte Kontaktaufnahme", "heimliche Kommunikationsanalyse"],
        "phases": [
            "Corporate Scope und Schutzgut definieren", "Arbeits-/Datenschutzrisiken markieren", "öffentliche Rollen-/Firmenanker erfassen",
            "Expositions- und Reputationshinweise suchen", "Source Reliability und Relevanz prüfen", "Sensitive Flags und Redaction",
            "Risk Findings mit Gegenbelegen", "Legal Review vor Export", "Corporate Security Briefing erstellen",
        ],
        "deliverables": ["Corporate Security Briefing", "Risk Register", "Redacted Client Report", "Evidence Annex"],
        "quality_gates": ["Beschäftigtendaten-Prüfung", "Betriebs-/Datenschutzrisiken dokumentiert", "Export Legal Review", "Datenminimierung bestätigt"],
    },
    {
        "key": "background_check",
        "title": "Background Check / öffentliche Plausibilitätsprüfung",
        "case_type": "background_check",
        "risk_level": "medium",
        "purpose_template": "Plausibilitätsprüfung öffentlich verfügbarer beruflicher, öffentlicher und reputationsbezogener Angaben im zulässigen Mandatsrahmen.",
        "legal_basis_hint": "Mandatsauftrag / berechtigtes Interesse; Einwilligung oder klare Auftragssituation prüfen, besonders bei Bewerbungs-/Beschäftigungskontext.",
        "description": "Kandidatenlogik für öffentliche Profil-, Presse-, Publikations- und Unternehmensanker mit Namensdopplerprüfung.",
        "allowed_sources": ["öffentliche berufliche Profile", "Presse", "Publikationen", "Firmenwebseiten", "öffentliche Register"],
        "forbidden_actions": ["private Social-Media-Bereiche", "sensible Kategorien", "automatische Ablehnungsentscheidung", "private Adresse"],
        "phases": [
            "Zweck und Einwilligungs-/Mandatslage prüfen", "öffentliche Identitätsanker erfassen", "berufliche Profile und Publikationen prüfen",
            "Presse-/Registerhinweise suchen", "Namensdoppler und Gegenbelege prüfen", "Evidence nur bei Relevanz sichern",
            "redigierten Kurzbericht erzeugen", "Aufbewahrung und Löschung terminieren",
        ],
        "deliverables": ["Client Short Report", "Redacted Client Report", "Evidence Annex"],
        "quality_gates": ["keine automatisierte Entscheidung", "sensible Kategorien ausgeschlossen", "Retention gesetzt", "Redaction geprüft"],
    },
    {
        "key": "online_reputation",
        "title": "Online Reputation / öffentliche Sichtbarkeit",
        "case_type": "reputation",
        "risk_level": "low",
        "purpose_template": "Erhebung öffentlich sichtbarer Reputations-, Medien- und Profilhinweise für legitime Schutz-, Kommunikations- oder Beratungszwecke.",
        "legal_basis_hint": "Berechtigtes Interesse / Mandatsauftrag; nur öffentliche Inhalte und verhältnismäßige Speicherung.",
        "description": "Reputationsmonitoring als fallbezogene Momentaufnahme mit Quellenkritik, Redaction und klarer Trennung zwischen Meinung, Behauptung und Beleg.",
        "allowed_sources": ["Suchmaschinen", "Presse", "öffentliche Webseiten", "öffentliche Profile", "Bewertungs-/Diskussionsseiten soweit rechtmäßig"],
        "forbidden_actions": ["Massenprofiling", "private Accounts", "Manipulationskampagnen", "Doxxing", "unverhältnismäßige Speicherung"],
        "phases": [
            "Reputationsziel und Scope definieren", "Quellenkorb und Suchbegriffe festlegen", "öffentliche Treffer sammeln",
            "Sentiment nur als Hinweis, nicht als Tatsache bewerten", "Quellenkritik und Gegenbelege", "Reputations-Graph und Timeline",
            "Kurzbericht mit Maßnahmenhinweisen", "Retention und erneute Prüfung planen",
        ],
        "deliverables": ["Reputation Snapshot", "Source Matrix", "Timeline", "Client Short Report"],
        "quality_gates": ["Meinung vs. Tatsache getrennt", "Source Reliability bewertet", "Redaction geprüft", "Monitoring nicht dauerhaft ohne neue Grundlage"],
    },
    {
        "key": "threat_assessment",
        "title": "Threat Assessment / öffentliche Bedrohungshinweise",
        "case_type": "security_risk",
        "risk_level": "high",
        "purpose_template": "Bewertung öffentlich zugänglicher Bedrohungs-, Expositions- oder Risikohinweise für Schutz- und Sicherheitsmaßnahmen.",
        "legal_basis_hint": "Berechtigtes Interesse / Schutzinteressen; hohe Anforderungen an Verhältnismäßigkeit, Art.-9-/Art.-10-Prüfung und menschliche Bewertung.",
        "description": "Sicherheitsbezogene OSINT-Auswertung mit Warnhinweisen, Gegenhypothesen, Eskalationsnotizen und strenger Exportkontrolle.",
        "allowed_sources": ["öffentliche Posts/Statements", "Presse", "offizielle Warnungen", "öffentliche Webseiten", "fallbezogene Mandatsunterlagen"],
        "forbidden_actions": ["Gefährlichkeitsautomatik", "politische/religiöse Profilbildung", "private Gruppen", "Konfrontation", "verdeckte Überwachung"],
        "phases": [
            "Schutzgut, Dringlichkeit und Zuständigkeit prüfen", "High-Risk Privacy Assessment", "öffentliche Bedrohungshinweise als Kandidaten erfassen",
            "Kontext, Ironie, Zitat und Gegenbelege prüfen", "Risk Findings menschlich bewerten", "Eskalations-/Behördenhinweis dokumentieren",
            "redigierten Security Brief erzeugen", "enge Lösch-/Reviewfrist setzen",
        ],
        "deliverables": ["Security Brief", "Risk Register", "Counter-Hypotheses", "Redacted Evidence Annex"],
        "quality_gates": ["keine automatische Gefährlichkeitsentscheidung", "High-Risk Review", "Gegenbelege vorhanden", "Export nur mit Legal/Senior Review"],
    },
]


class CasePlaybookService:
    """Build 29.0: case templates and operational playbooks.

    Playbooks are safe-by-design workflow templates. They do not run searches automatically and do
    not promote results to evidence. They create scope, steps, source plans, deliverables and quality
    gates so a professional analyst can work consistently, legally and auditable.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit

    def seed_defaults(self) -> Dict[str, Any]:
        created = 0
        for pb in DEFAULT_PLAYBOOKS:
            existing = self.db.one("SELECT playbook_id FROM case_playbooks WHERE playbook_key=?", [pb["key"]])
            if existing:
                continue
            playbook_id = new_id("pb")
            self.db.execute(
                """INSERT INTO case_playbooks(playbook_id,playbook_key,title,case_type,risk_level,purpose_template,legal_basis_hint,description,allowed_sources_json,forbidden_actions_json,deliverables_json,quality_gates_json,created_at,active)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                [playbook_id, pb["key"], pb["title"], pb["case_type"], pb["risk_level"], pb["purpose_template"], pb["legal_basis_hint"], pb["description"], dumps(pb["allowed_sources"]), dumps(pb["forbidden_actions"]), dumps(pb["deliverables"]), dumps(pb["quality_gates"]), now_ts()],
            )
            for idx, phase in enumerate(pb["phases"], start=1):
                self.db.execute(
                    """INSERT INTO playbook_phase_templates(phase_template_id,playbook_id,phase_order,title,objective,required_gate,created_at)
                    VALUES(?,?,?,?,?,?,?)""",
                    [new_id("pbphase"), playbook_id, idx, phase, self._phase_objective(phase), self._phase_gate(phase), now_ts()],
                )
            for src in pb["allowed_sources"]:
                self.db.execute(
                    """INSERT INTO playbook_source_profiles(source_profile_id,playbook_id,source_name,source_category,allowed_use,risk_level,created_at)
                    VALUES(?,?,?,?,?,?,?)""",
                    [new_id("pbsrc"), playbook_id, src, self._source_category(src), f"Nur fallzweckbezogene öffentliche/autorisierte Nutzung: {src}", pb["risk_level"], now_ts()],
                )
            for action in pb["forbidden_actions"]:
                self.db.execute(
                    """INSERT INTO playbook_guardrails(guardrail_id,playbook_id,guardrail_type,rule_text,severity,created_at)
                    VALUES(?,?,?,?,?,?)""",
                    [new_id("pbgr"), playbook_id, "forbidden_action", action, "high", now_ts()],
                )
            created += 1
        self.audit.log("seed_defaults", "case_playbooks", None, None, {"created": created, "total": len(self.list_playbooks())})
        return {"created": created, "total": len(self.list_playbooks())}

    @staticmethod
    def _phase_objective(title: str) -> str:
        if "Legal" in title or "Privacy" in title or "Schutz" in title:
            return "Rechtsgrundlage, Schutzinteressen und Grenzen dokumentieren."
        if "Evidence" in title or "Beleg" in title:
            return "Nur geprüfte, quellenbezogene Belege mit Hash/Chain-of-Custody sichern."
        if "Graph" in title or "Timeline" in title:
            return "Zusammenhänge nur als quellengestützte Kandidaten modellieren."
        if "Bericht" in title or "Report" in title or "Brief" in title:
            return "Redigierten, nachvollziehbaren Bericht mit Unsicherheiten und Gegenbelegen erzeugen."
        return "Fallbezogene OSINT-Arbeit kontrolliert, dokumentiert und reviewpflichtig durchführen."

    @staticmethod
    def _phase_gate(title: str) -> str:
        low = title.lower()
        if "legal" in low or "privacy" in low or "schutz" in low:
            return "LEGAL_PRIVACY_REVIEW"
        if "evidence" in low or "beleg" in low:
            return "EVIDENCE_MANIFEST"
        if "bericht" in low or "report" in low or "brief" in low:
            return "EXPORT_REVIEW"
        if "gegen" in low or "widerspruch" in low:
            return "COUNTER_EVIDENCE"
        return "HUMAN_REVIEW"

    @staticmethod
    def _source_category(source: str) -> str:
        low = source.lower()
        if "presse" in low or "archive" in low:
            return "media_archive"
        if "register" in low or "firma" in low or "unternehmens" in low:
            return "corporate_registry"
        if "domain" in low or "dns" in low or "rdap" in low:
            return "infrastructure_public"
        if "social" in low or "profil" in low or "posts" in low:
            return "public_profile"
        if "karten" in low or "ort" in low:
            return "geo_context"
        return "public_web"

    def list_playbooks(self, active_only: bool = True) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM case_playbooks" + (" WHERE active=1" if active_only else "") + " ORDER BY case_type,title"
        rows = self.db.all(sql)
        for row in rows:
            for key in ["allowed_sources_json", "forbidden_actions_json", "deliverables_json", "quality_gates_json"]:
                row[key] = loads(row.get(key), [])
        return rows

    def get_playbook(self, playbook_key_or_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM case_playbooks WHERE playbook_key=? OR playbook_id=?", [playbook_key_or_id, playbook_key_or_id])
        if not row:
            raise KeyError(f"Playbook nicht gefunden: {playbook_key_or_id}")
        for key in ["allowed_sources_json", "forbidden_actions_json", "deliverables_json", "quality_gates_json"]:
            row[key] = loads(row.get(key), [])
        return row

    def phases_for_playbook(self, playbook_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM playbook_phase_templates WHERE playbook_id=? ORDER BY phase_order", [playbook_id])

    def sources_for_playbook(self, playbook_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM playbook_source_profiles WHERE playbook_id=? ORDER BY source_category,source_name", [playbook_id])

    def guardrails_for_playbook(self, playbook_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM playbook_guardrails WHERE playbook_id=? ORDER BY severity DESC,rule_text", [playbook_id])

    def recommend_playbooks(self, purpose_text: str, limit: int = 3) -> List[Dict[str, Any]]:
        purpose = (purpose_text or "").lower()
        scored = []
        hints = {
            "due_diligence": ["due", "diligence", "reputation", "geschäft", "mandant", "firma"],
            "missing_person_leads": ["vermisst", "missing", "verschwunden", "sichtung", "angehör"],
            "fraud_scam": ["betrug", "scam", "alias", "domain", "fake", "verdacht"],
            "corporate_security": ["corporate", "security", "schutz", "insider", "unternehmen", "mitarbeiter"],
            "background_check": ["background", "bewerb", "plausibilität", "lebenslauf", "prüfung"],
            "online_reputation": ["online", "reputation", "sichtbarkeit", "bewertung", "ruf"],
            "threat_assessment": ["threat", "bedroh", "gefähr", "schutz", "risiko", "eskalation"],
        }
        for pb in self.list_playbooks():
            score = sum(1 for token in hints.get(pb["playbook_key"], []) if token in purpose)
            if pb["risk_level"] == "high" and any(k in purpose for k in ["bedroh", "vermisst", "schutz", "straf", "verdacht"]):
                score += 1
            scored.append({**pb, "recommendation_score": score})
        return sorted(scored, key=lambda x: (x["recommendation_score"], x["title"]), reverse=True)[:limit]

    def apply_playbook_to_case(self, case_id: str, playbook_key_or_id: str, assigned_by: str = "local-analyst", notes: str = "") -> Dict[str, Any]:
        pb = self.get_playbook(playbook_key_or_id)
        existing = self.db.one("SELECT * FROM case_playbook_assignments WHERE case_id=? AND playbook_id=? AND status IN ('active','in_progress')", [case_id, pb["playbook_id"]])
        if existing:
            return self.assignment_detail(existing["assignment_id"])
        assignment_id = new_id("pbass")
        ts = now_ts()
        self.db.execute(
            """INSERT INTO case_playbook_assignments(assignment_id,case_id,playbook_id,playbook_key,title,status,assigned_by,assigned_at,notes)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            [assignment_id, case_id, pb["playbook_id"], pb["playbook_key"], pb["title"], "active", assigned_by, ts, notes],
        )
        created_steps = 0
        for phase in self.phases_for_playbook(pb["playbook_id"]):
            self.db.execute(
                """INSERT INTO playbook_case_steps(case_step_id,assignment_id,case_id,playbook_id,phase_order,title,objective,required_gate,status,owner,created_at,updated_at,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                [new_id("pbstep"), assignment_id, case_id, pb["playbook_id"], phase["phase_order"], phase["title"], phase["objective"], phase["required_gate"], "todo", "analyst", ts, ts, ""],
            )
            created_steps += 1
        for source in self.sources_for_playbook(pb["playbook_id"]):
            self.db.execute(
                """INSERT INTO playbook_source_plans(plan_id,assignment_id,case_id,source_name,source_category,allowed_use,risk_level,status,created_at,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                [new_id("pbplan"), assignment_id, case_id, source["source_name"], source["source_category"], source["allowed_use"], source["risk_level"], "planned", ts, ""],
            )
        for deliverable in pb["deliverables_json"]:
            self.db.execute(
                """INSERT INTO playbook_deliverables(deliverable_id,assignment_id,case_id,deliverable_type,status,required_review,created_at,notes)
                VALUES(?,?,?,?,?,?,?,?)""",
                [new_id("pbdel"), assignment_id, case_id, deliverable, "planned", 1 if "Report" in deliverable or "Brief" in deliverable or "Annex" in deliverable else 0, ts, ""],
            )
        for gate in pb["quality_gates_json"]:
            self.db.execute(
                """INSERT INTO playbook_quality_gates(gate_id,assignment_id,case_id,gate_name,status,severity,created_at,notes)
                VALUES(?,?,?,?,?,?,?,?)""",
                [new_id("pbgate"), assignment_id, case_id, gate, "open", "high" if any(k in gate.lower() for k in ["legal", "privacy", "art", "export", "minder"] ) else "medium", ts, ""],
            )
        self.audit.log("apply_playbook", "case_playbook", assignment_id, case_id, {"playbook_key": pb["playbook_key"], "steps": created_steps})
        return self.assignment_detail(assignment_id)

    def assignment_detail(self, assignment_id: str) -> Dict[str, Any]:
        assignment = self.db.one("SELECT * FROM case_playbook_assignments WHERE assignment_id=?", [assignment_id])
        if not assignment:
            raise KeyError(f"Playbook-Zuweisung nicht gefunden: {assignment_id}")
        assignment["steps"] = self.db.all("SELECT * FROM playbook_case_steps WHERE assignment_id=? ORDER BY phase_order", [assignment_id])
        assignment["sources"] = self.db.all("SELECT * FROM playbook_source_plans WHERE assignment_id=? ORDER BY source_category,source_name", [assignment_id])
        assignment["deliverables"] = self.db.all("SELECT * FROM playbook_deliverables WHERE assignment_id=? ORDER BY deliverable_type", [assignment_id])
        assignment["quality_gates"] = self.db.all("SELECT * FROM playbook_quality_gates WHERE assignment_id=? ORDER BY severity DESC,gate_name", [assignment_id])
        return assignment

    def list_case_assignments(self, case_id: str) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM case_playbook_assignments WHERE case_id=? ORDER BY assigned_at DESC", [case_id])
        for row in rows:
            progress = self.progress_for_assignment(row["assignment_id"])
            row.update(progress)
        return rows

    def update_step(self, case_step_id: str, status: str, notes: str = "") -> Dict[str, Any]:
        if status not in {"todo", "in_progress", "blocked", "done", "needs_review"}:
            raise ValueError("Ungültiger Playbook-Schrittstatus.")
        row = self.db.one("SELECT * FROM playbook_case_steps WHERE case_step_id=?", [case_step_id])
        if not row:
            raise KeyError("Playbook-Schritt nicht gefunden.")
        self.db.execute("UPDATE playbook_case_steps SET status=?, notes=?, updated_at=? WHERE case_step_id=?", [status, notes or row.get("notes", ""), now_ts(), case_step_id])
        self.audit.log("update_playbook_step", "playbook_case_step", case_step_id, row["case_id"], {"status": status})
        return self.db.one("SELECT * FROM playbook_case_steps WHERE case_step_id=?", [case_step_id])

    def update_quality_gate(self, gate_id: str, status: str, notes: str = "") -> Dict[str, Any]:
        if status not in {"open", "passed", "blocked", "waived_with_reason"}:
            raise ValueError("Ungültiger Quality-Gate-Status.")
        row = self.db.one("SELECT * FROM playbook_quality_gates WHERE gate_id=?", [gate_id])
        if not row:
            raise KeyError("Quality Gate nicht gefunden.")
        self.db.execute("UPDATE playbook_quality_gates SET status=?, notes=? WHERE gate_id=?", [status, notes or row.get("notes", ""), gate_id])
        self.audit.log("update_playbook_quality_gate", "playbook_quality_gate", gate_id, row["case_id"], {"status": status})
        return self.db.one("SELECT * FROM playbook_quality_gates WHERE gate_id=?", [gate_id])

    def progress_for_assignment(self, assignment_id: str) -> Dict[str, Any]:
        steps = self.db.all("SELECT status FROM playbook_case_steps WHERE assignment_id=?", [assignment_id])
        gates = self.db.all("SELECT status,severity FROM playbook_quality_gates WHERE assignment_id=?", [assignment_id])
        total = len(steps)
        done = len([s for s in steps if s.get("status") == "done"])
        blocked = len([s for s in steps if s.get("status") == "blocked"])
        open_high_gates = len([g for g in gates if g.get("severity") == "high" and g.get("status") not in {"passed", "waived_with_reason"}])
        pct = round((done / total) * 100, 1) if total else 0.0
        return {"step_total": total, "step_done": done, "step_blocked": blocked, "progress_pct": pct, "open_high_gates": open_high_gates}

    def dashboard(self, case_id: str) -> Dict[str, Any]:
        assignments = self.list_case_assignments(case_id)
        steps = self.db.all("SELECT * FROM playbook_case_steps WHERE case_id=? ORDER BY phase_order", [case_id])
        gates = self.db.all("SELECT * FROM playbook_quality_gates WHERE case_id=? ORDER BY severity DESC,gate_name", [case_id])
        deliverables = self.db.all("SELECT * FROM playbook_deliverables WHERE case_id=? ORDER BY status,deliverable_type", [case_id])
        source_plans = self.db.all("SELECT * FROM playbook_source_plans WHERE case_id=? ORDER BY status,source_category,source_name", [case_id])
        open_gates = [g for g in gates if g.get("status") not in {"passed", "waived_with_reason"}]
        active_assignments = [a for a in assignments if a.get("status") in {"active", "in_progress"}]
        if not assignments:
            status = "no_playbook"
        elif any(g.get("severity") == "high" for g in open_gates):
            status = "quality_gates_open"
        elif all(a.get("progress_pct", 0) >= 80 for a in active_assignments or assignments):
            status = "playbook_near_ready"
        else:
            status = "playbook_active"
        next_steps = [s for s in steps if s.get("status") in {"todo", "blocked", "needs_review"}][:7]
        return {
            "status": status,
            "assignments": assignments,
            "counts": {
                "assignments": len(assignments),
                "steps_total": len(steps),
                "steps_done": len([s for s in steps if s.get("status") == "done"]),
                "open_quality_gates": len(open_gates),
                "deliverables": len(deliverables),
                "source_plans": len(source_plans),
            },
            "open_quality_gates": open_gates[:10],
            "next_steps": next_steps,
            "deliverables": deliverables,
            "source_plans": source_plans,
        }
