from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.policy import PolicyGate

STRENGTH_LABELS = [
    (20, "nicht belastbar"),
    (40, "schwach"),
    (60, "plausibler Hinweis"),
    (80, "stark plausibel"),
    (101, "sehr stark – menschliche Prüfung bleibt Pflicht"),
]

PROHIBITED_DECISIONS = {
    "confirmed_identity",
    "guilty",
    "dangerous",
    "home_address_confirmed",
    "biometric_match",
}

OFFICIAL_HOST_HINTS = (".gov", ".bund.de", ".de", "handelsregister", "bundesanzeiger", "register")
PROFILE_HOST_HINTS = ("linkedin.", "xing.", "github.", "stackoverflow.", "youtube.", "reddit.")
PRESS_HINTS = ("news", "presse", "zeitung", "magazin", "journal", "press")
SOCIAL_HINTS = ("facebook.", "instagram.", "tiktok.", "x.com", "twitter.")


def _lower(text: Any) -> str:
    return str(text or "").lower()


def _tokens(values: List[str]) -> List[str]:
    out: List[str] = []
    for v in values:
        for token in re.split(r"[^\wäöüÄÖÜß@.-]+", str(v or "")):
            token = token.strip().lower()
            if len(token) >= 3:
                out.append(token)
    return sorted(set(out))


def _host(url: str) -> str:
    try:
        return urlparse(url or "").netloc.lower().replace("www.", "")
    except Exception:
        return ""


class VerificationCorroborationService:
    """Build 45.0 – Verification & Corroboration Engine.

    This service scores the strength of OSINT artefacts, not the person. It never confirms
    identity, guilt, dangerousness, residence or biometrics automatically. It helps analysts
    decide which items need a second source, counter-evidence or exclusion handling.
    """

    def __init__(self, db: Database, audit: AuditService):
        self.db = db
        self.audit = audit
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS verification_rules (
          rule_id TEXT PRIMARY KEY, rule_key TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
          weight REAL DEFAULT 1.0, active INTEGER DEFAULT 1, guardrail_json TEXT NOT NULL,
          created_at TEXT NOT NULL, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS verification_runs (
          run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_id TEXT DEFAULT '', scope TEXT NOT NULL,
          status TEXT DEFAULT 'completed', evidence_count INTEGER DEFAULT 0, review_count INTEGER DEFAULT 0,
          assessment_count INTEGER DEFAULT 0, corroboration_avg REAL DEFAULT 0.0, strong_count INTEGER DEFAULT 0,
          weak_count INTEGER DEFAULT 0, contradiction_count INTEGER DEFAULT 0, second_source_needed INTEGER DEFAULT 0,
          created_at TEXT NOT NULL, created_by TEXT DEFAULT 'local-analyst', notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS corroboration_assessments (
          assessment_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, case_id TEXT NOT NULL,
          object_type TEXT NOT NULL, object_id TEXT NOT NULL, title TEXT NOT NULL, source_url TEXT DEFAULT '',
          source_type TEXT DEFAULT '', source_reliability REAL DEFAULT 0.0, identity_fit REAL DEFAULT 0.0,
          source_independence REAL DEFAULT 0.0, freshness REAL DEFAULT 0.0, counter_evidence REAL DEFAULT 0.0,
          time_consistency REAL DEFAULT 0.0, geo_consistency REAL DEFAULT 0.0, name_doppler_risk REAL DEFAULT 0.0,
          corroboration_score INTEGER DEFAULT 0, strength_label TEXT DEFAULT 'nicht belastbar',
          decision_hint TEXT DEFAULT '', markers_json TEXT NOT NULL, issues_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES verification_runs(run_id) ON DELETE CASCADE,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS verification_second_source_checks (
          check_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, primary_object_type TEXT NOT NULL,
          primary_object_id TEXT NOT NULL, query_text TEXT NOT NULL, status TEXT DEFAULT 'planned',
          candidate_count INTEGER DEFAULT 0, created_at TEXT NOT NULL, notes TEXT DEFAULT '',
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS verification_contradictions (
          flag_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, run_id TEXT DEFAULT '', object_type TEXT NOT NULL,
          object_id TEXT NOT NULL, contradiction_type TEXT NOT NULL, severity TEXT DEFAULT 'medium',
          description TEXT NOT NULL, action_required TEXT NOT NULL, status TEXT DEFAULT 'open', created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS verification_decisions (
          decision_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, assessment_id TEXT NOT NULL,
          reviewer TEXT DEFAULT 'local-analyst', decision TEXT NOT NULL, notes TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
          FOREIGN KEY(assessment_id) REFERENCES corroboration_assessments(assessment_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_verification_runs_case ON verification_runs(case_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_corroboration_case ON corroboration_assessments(case_id, corroboration_score);
        CREATE INDEX IF NOT EXISTS idx_verification_flags_case ON verification_contradictions(case_id, status, severity);
        ''')
        self.db.conn.commit()

    def seed_defaults(self) -> Dict[str, int]:
        self.ensure_schema()
        ts = now_ts(); created = 0
        defaults = [
            ("second_source", "Zweitquelle erforderlich", 1.0, ["no_auto_truth", "independent_source_preferred"], "Starke Claims brauchen eine unabhängige Quelle."),
            ("counter_evidence", "Gegenbelegprüfung", 1.0, ["counter_evidence_before_conclusion"], "Vor Schlussfolgerungen Gegenbelege und Namensdoppler prüfen."),
            ("identity_candidate", "Identität nur Kandidatenlogik", 1.0, ["no_identity_confirmation"], "Keine automatische Identitätsbestätigung."),
            ("sensitive_blocks", "Sensibilität blockiert Export", 1.0, ["privacy_review_first"], "Sensible/Art.-9-/Art.-10-nahe Hinweise erfordern Review."),
        ]
        for key, title, weight, guardrails, notes in defaults:
            if not self.db.one("SELECT rule_id FROM verification_rules WHERE rule_key=?", [key]):
                self.db.execute('''INSERT INTO verification_rules(rule_id,rule_key,title,weight,active,guardrail_json,created_at,notes)
                VALUES(?,?,?,?,?,?,?,?)''', [new_id("vrule"), key, title, weight, 1, dumps(guardrails), ts, notes])
                created += 1
        return {"created_rules": created, "total_rules": len(self.db.all("SELECT rule_id FROM verification_rules"))}

    def _target(self, target_id: str) -> Dict[str, Any]:
        if not target_id:
            return {}
        row = self.db.one("SELECT * FROM targets WHERE target_id=?", [target_id])
        if not row:
            return {}
        for k in ["aliases_json", "emails_json", "usernames_json", "locations_json", "companies_json", "domains_json"]:
            row[k] = loads(row.get(k), [])
        return row

    def _first_target(self, case_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT target_id FROM targets WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])
        return self._target(row["target_id"]) if row else {}

    def _target_tokens(self, target: Dict[str, Any]) -> Dict[str, List[str]]:
        if not target:
            return {"all": [], "name": [], "alias": [], "company": [], "location": [], "username": [], "email": [], "domain": []}
        name = target.get("name", "")
        return {
            "name": _tokens([name]),
            "alias": _tokens(loads(target.get("aliases_json"), target.get("aliases_json", [])) if isinstance(target.get("aliases_json"), str) else target.get("aliases_json", [])),
            "company": _tokens(target.get("companies_json", [])),
            "location": _tokens(target.get("locations_json", [])),
            "username": _tokens(target.get("usernames_json", [])),
            "email": _tokens(target.get("emails_json", [])),
            "domain": _tokens(target.get("domains_json", [])),
        } | {"all": []}

    @staticmethod
    def strength_label(score: int) -> str:
        for upper, label in STRENGTH_LABELS:
            if score < upper:
                return label
        return STRENGTH_LABELS[-1][1]

    def _source_reliability(self, url: str, source_type: str, provider: str = "", category: str = "") -> float:
        host = _host(url)
        text = " ".join([host, source_type or "", provider or "", category or ""]).lower()
        if any(x in text for x in ["bundesanzeiger", "handelsregister", ".gov", ".bund.de", "register", "rdap", "dns", "crt.sh"]):
            return 0.86
        if any(x in text for x in ["news", "presse", "press", "journal", "zeitung"]):
            return 0.72
        if any(x in text for x in ["linkedin", "xing", "github", "stackoverflow"]):
            return 0.66
        if any(x in text for x in ["archive", "wayback"]):
            return 0.62
        if any(x in text for x in ["forum", "reddit", "social", "facebook", "instagram", "tiktok"]):
            return 0.48
        if "example." in text:
            return 0.25
        if host:
            return 0.55
        return 0.35

    def _identity_fit(self, text: str, target: Dict[str, Any]) -> tuple[float, List[str], List[str]]:
        txt = _lower(text)
        if not target:
            return 0.35, [], ["Keine Zielperson für Ankervergleich ausgewählt."]
        name_tokens = _tokens([target.get("name", "")])
        aliases = _tokens(target.get("aliases_json", []))
        companies = _tokens(target.get("companies_json", []))
        locations = _tokens(target.get("locations_json", []))
        users = _tokens(target.get("usernames_json", []))
        emails = _tokens(target.get("emails_json", []))
        domains = _tokens(target.get("domains_json", []))
        markers: List[str] = []
        issues: List[str] = []
        score = 0.05
        def hit(tokens, label, add):
            nonlocal score
            count = sum(1 for t in tokens if t in txt)
            if count:
                markers.append(f"{label}:{count}")
                score += add * min(1.0, count / max(1, min(len(tokens), 3)))
            return count
        hit(name_tokens, "name", 0.34)
        hit(aliases, "alias", 0.18)
        hit(users, "username", 0.16)
        hit(emails, "email", 0.18)
        hit(companies, "company", 0.14)
        hit(locations, "location", 0.10)
        hit(domains, "domain", 0.12)
        if not markers:
            issues.append("Keine klaren Zielanker im Treffertext gefunden.")
        if name_tokens and sum(1 for t in name_tokens if t in txt) < min(2, len(name_tokens)):
            issues.append("Namensanker unvollständig; Namensdoppler-/Falschzuordnungsprüfung erforderlich.")
        return round(min(1.0, score), 3), markers, issues

    def _freshness(self, text: str) -> float:
        years = [int(y) for y in re.findall(r"\b(20[0-3]\d|19[8-9]\d)\b", text or "")]
        if not years:
            return 0.5
        newest = max(years)
        if newest >= 2025: return 0.9
        if newest >= 2022: return 0.75
        if newest >= 2018: return 0.58
        return 0.35

    def _counter_evidence_score(self, text: str) -> tuple[float, List[str]]:
        txt = _lower(text)
        markers = []
        score = 0.45
        for kw in ["not the same", "same name", "namensdoppler", "gleichnamig", "andere firma", "anderer ort", "widerspruch", "gegenbeleg"]:
            if kw in txt:
                markers.append(kw)
                score += 0.12
        if not markers:
            markers.append("Gegenbeleg noch nicht explizit dokumentiert.")
        return round(min(1.0, score), 3), markers

    def _name_doppler_risk(self, text: str, target: Dict[str, Any]) -> tuple[float, List[str]]:
        txt = _lower(text)
        markers: List[str] = []
        risk = 0.2
        if not target:
            return 0.55, ["kein Zielanker"]
        name_tokens = _tokens([target.get("name", "")])
        if name_tokens and sum(1 for t in name_tokens if t in txt) >= min(2, len(name_tokens)):
            risk += 0.18
            markers.append("Name vorhanden")
        for key, label in [("companies_json", "Firma"), ("locations_json", "Ort"), ("usernames_json", "Username"), ("emails_json", "E-Mail")]:
            tokens = _tokens(target.get(key, []))
            if tokens and any(t in txt for t in tokens):
                risk -= 0.08
                markers.append(f"{label} stützt Zuordnung")
        if any(kw in txt for kw in ["same name", "namensdoppler", "gleichnamig", "anderer ort", "andere firma"]):
            risk += 0.35
            markers.append("expliziter Doppler-/Widerspruchshinweis")
        return round(max(0.0, min(1.0, risk)), 3), markers

    def _assess_payload(self, case_id: str, run_id: str, obj: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        object_type = obj["object_type"]
        object_id = obj["object_id"]
        title = obj.get("title") or "OSINT-Artefakt"
        source_url = obj.get("source_url") or obj.get("url") or ""
        statement = obj.get("statement") or obj.get("snippet") or obj.get("notes") or ""
        provider = obj.get("provider") or obj.get("source_reliability") or ""
        source_type = obj.get("source_type") or obj.get("category") or provider or "public_web"
        text = " ".join([title, source_url, statement, provider, source_type])
        policy = PolicyGate.evaluate_query(text[:700])
        src_rel = self._source_reliability(source_url, source_type, provider, obj.get("category") or "")
        identity_fit, id_markers, id_issues = self._identity_fit(text, target)
        freshness = self._freshness(text)
        counter_score, counter_markers = self._counter_evidence_score(text)
        doppler_risk, doppler_markers = self._name_doppler_risk(text, target)
        host = _host(source_url)
        source_independence = 0.70 if host else 0.45
        if object_type == "review_item":
            source_independence -= 0.08
        time_consistency = 0.72 if freshness >= 0.5 else 0.45
        geo_consistency = 0.62
        if target and target.get("locations_json"):
            geo_terms = _tokens(target.get("locations_json", []))
            geo_consistency = 0.78 if any(t in _lower(text) for t in geo_terms) else 0.45
        raw_score = (
            src_rel * 0.22 + identity_fit * 0.28 + source_independence * 0.12 + freshness * 0.10 +
            counter_score * 0.10 + time_consistency * 0.07 + geo_consistency * 0.06 + (1.0 - doppler_risk) * 0.05
        ) * 100
        score = int(round(max(0, min(100, raw_score))))
        if not policy.get("ok"):
            score = min(score, 35)
        label = self.strength_label(score)
        issues = list(id_issues)
        if src_rel < 0.5:
            issues.append("Quelle hat niedrige oder unbekannte Zuverlässigkeit.")
        if doppler_risk >= 0.55:
            issues.append("Namensdoppler-/Falschzuordnungsrisiko erhöht.")
        if counter_score < 0.55:
            issues.append("Gegenbeleg-/Ausschlussprüfung fehlt oder ist schwach dokumentiert.")
        if not policy.get("ok"):
            issues.append("PolicyGate: " + policy.get("reason", "blockiert"))
        markers = {
            "identity": id_markers,
            "counter": counter_markers,
            "doppler": doppler_markers,
            "host": host,
            "policy_status": "allowed" if policy.get("ok") else "blocked",
        }
        if score >= 80:
            hint = "Sehr starke Kandidatenlage – Zweitquelle und menschliche Review vor Schlussfolgerung dokumentieren."
        elif score >= 60:
            hint = "Plausibler/starker Hinweis – weitere Quelle oder Gegenbeleg prüfen."
        elif score >= 40:
            hint = "Schwacher bis plausibler Hinweis – nicht für Berichtsfazit nutzen ohne weitere Belege."
        else:
            hint = "Nicht belastbar – verwerfen, Doppler prüfen oder nur als offene Spur führen."
        aid = new_id("corr")
        self.db.execute('''INSERT INTO corroboration_assessments(assessment_id,run_id,case_id,object_type,object_id,title,source_url,source_type,source_reliability,identity_fit,source_independence,freshness,counter_evidence,time_consistency,geo_consistency,name_doppler_risk,corroboration_score,strength_label,decision_hint,markers_json,issues_json,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', [aid, run_id, case_id, object_type, object_id, title, source_url, source_type, src_rel, identity_fit, source_independence, freshness, counter_score, time_consistency, geo_consistency, doppler_risk, score, label, hint, dumps(markers), dumps(issues), now_ts()])
        return self.get_assessment(aid)

    def _objects_for_case(self, case_id: str, include_review: bool = True) -> List[Dict[str, Any]]:
        objects: List[Dict[str, Any]] = []
        for ev in self.db.all("SELECT * FROM evidence_items WHERE case_id=? ORDER BY captured_at DESC", [case_id]):
            ev["object_type"] = "evidence_item"; ev["object_id"] = ev["evidence_id"]
            objects.append(ev)
        if include_review:
            for r in self.db.all("SELECT * FROM review_items WHERE case_id=? ORDER BY created_at DESC", [case_id]):
                if r.get("status") not in ("rejected", "duplicate"):
                    r["object_type"] = "review_item"; r["object_id"] = r["item_id"]; r["source_url"] = r.get("url")
                    objects.append(r)
        return objects

    def assess_case(self, case_id: str, target_id: str = "", include_review: bool = True, notes: str = "") -> Dict[str, Any]:
        self.ensure_schema()
        target = self._target(target_id) if target_id else self._first_target(case_id)
        run_id = new_id("vrun")
        ts = now_ts()
        scope = "evidence_plus_review" if include_review else "evidence_only"
        objects = self._objects_for_case(case_id, include_review=include_review)
        self.db.execute('''INSERT INTO verification_runs(run_id,case_id,target_id,scope,status,evidence_count,review_count,assessment_count,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?,?)''', [run_id, case_id, target.get("target_id", ""), scope, "running", sum(1 for o in objects if o["object_type"] == "evidence_item"), sum(1 for o in objects if o["object_type"] == "review_item"), 0, ts, notes])
        assessments = [self._assess_payload(case_id, run_id, obj, target) for obj in objects]
        contradictions = self._create_flags(case_id, run_id, assessments)
        avg = round(sum(a["corroboration_score"] for a in assessments) / max(1, len(assessments)), 2)
        strong = sum(1 for a in assessments if int(a["corroboration_score"]) >= 70)
        weak = sum(1 for a in assessments if int(a["corroboration_score"]) < 45)
        second = sum(1 for a in assessments if int(a["corroboration_score"]) >= 60 and float(a["source_independence"] or 0) < 0.75)
        self.db.execute('''UPDATE verification_runs SET status=?, assessment_count=?, corroboration_avg=?, strong_count=?, weak_count=?, contradiction_count=?, second_source_needed=? WHERE run_id=?''', ["completed", len(assessments), avg, strong, weak, len(contradictions), second, run_id])
        self.audit.log("assess", "verification_run", run_id, case_id, {"assessments": len(assessments), "avg": avg, "contradictions": len(contradictions)})
        return self.run_dashboard(case_id, run_id)

    def _create_flags(self, case_id: str, run_id: str, assessments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        flags: List[Dict[str, Any]] = []
        for a in assessments:
            if float(a.get("name_doppler_risk") or 0) >= 0.55:
                flags.append(self._flag(case_id, run_id, a, "name_doppler_risk", "high", "Namensdoppler-/Falschzuordnungsrisiko ist erhöht.", "Gegenbeleg- und Ausschlussprüfung durchführen."))
            if float(a.get("counter_evidence") or 0) < 0.55 and int(a.get("corroboration_score") or 0) >= 55:
                flags.append(self._flag(case_id, run_id, a, "counter_evidence_missing", "medium", "Plausibler Hinweis ohne ausreichende Gegenbelegprüfung.", "Gegenbeleg-Queries ausführen und dokumentieren."))
            if int(a.get("corroboration_score") or 0) >= 60 and float(a.get("source_independence") or 0) < 0.75:
                flags.append(self._flag(case_id, run_id, a, "second_source_needed", "medium", "Starker Hinweis benötigt unabhängige Zweitquelle.", "Second-source-check planen."))
                self.plan_second_source(case_id, a["object_type"], a["object_id"], a.get("title") or "", notes="Automatisch aus Build 45 Corroboration Engine.")
        return flags

    def _flag(self, case_id: str, run_id: str, a: Dict[str, Any], ftype: str, severity: str, description: str, action_required: str) -> Dict[str, Any]:
        fid = new_id("vflag")
        self.db.execute('''INSERT INTO verification_contradictions(flag_id,case_id,run_id,object_type,object_id,contradiction_type,severity,description,action_required,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)''', [fid, case_id, run_id, a["object_type"], a["object_id"], ftype, severity, description, action_required, "open", now_ts()])
        return self.db.one("SELECT * FROM verification_contradictions WHERE flag_id=?", [fid])

    def plan_second_source(self, case_id: str, object_type: str, object_id: str, title: str, notes: str = "") -> Dict[str, Any]:
        policy = PolicyGate.evaluate_query(title[:500])
        if not policy.get("ok"):
            raise ValueError("Second-source-check blockiert: Query verletzt Guardrails.")
        q = f'"{title[:90].strip()}" Zweitquelle OR Presse OR Register OR Archiv'
        cid = new_id("v2src")
        self.db.execute('''INSERT INTO verification_second_source_checks(check_id,case_id,primary_object_type,primary_object_id,query_text,status,candidate_count,created_at,notes)
        VALUES(?,?,?,?,?,?,?,?,?)''', [cid, case_id, object_type, object_id, q, "planned", 0, now_ts(), notes])
        return self.db.one("SELECT * FROM verification_second_source_checks WHERE check_id=?", [cid])

    def get_assessment(self, assessment_id: str) -> Dict[str, Any]:
        row = self.db.one("SELECT * FROM corroboration_assessments WHERE assessment_id=?", [assessment_id])
        if not row:
            raise KeyError("Corroboration Assessment nicht gefunden.")
        row["markers_json"] = loads(row.get("markers_json"), {})
        row["issues_json"] = loads(row.get("issues_json"), [])
        return row

    def latest_run(self, case_id: str) -> Optional[Dict[str, Any]]:
        return self.db.one("SELECT * FROM verification_runs WHERE case_id=? ORDER BY created_at DESC LIMIT 1", [case_id])

    def list_assessments(self, case_id: str, run_id: str = "") -> List[Dict[str, Any]]:
        if run_id:
            rows = self.db.all("SELECT * FROM corroboration_assessments WHERE case_id=? AND run_id=? ORDER BY corroboration_score DESC", [case_id, run_id])
        else:
            latest = self.latest_run(case_id)
            rows = self.db.all("SELECT * FROM corroboration_assessments WHERE case_id=? AND run_id=? ORDER BY corroboration_score DESC", [case_id, latest["run_id"]]) if latest else []
        for r in rows:
            r["markers_json"] = loads(r.get("markers_json"), {})
            r["issues_json"] = loads(r.get("issues_json"), [])
        return rows

    def list_flags(self, case_id: str, open_only: bool = True) -> List[Dict[str, Any]]:
        if open_only:
            return self.db.all("SELECT * FROM verification_contradictions WHERE case_id=? AND status='open' ORDER BY severity DESC, created_at DESC", [case_id])
        return self.db.all("SELECT * FROM verification_contradictions WHERE case_id=? ORDER BY created_at DESC", [case_id])

    def list_second_source_checks(self, case_id: str) -> List[Dict[str, Any]]:
        return self.db.all("SELECT * FROM verification_second_source_checks WHERE case_id=? ORDER BY created_at DESC", [case_id])

    def record_decision(self, assessment_id: str, decision: str, notes: str, reviewer: str = "local-analyst") -> Dict[str, Any]:
        if decision in PROHIBITED_DECISIONS:
            raise ValueError("Unzulässige Entscheidung: keine automatische Identitäts-/Schuld-/Gefährlichkeits-/Wohnort-/Biometrie-Bestätigung.")
        allowed = {"accepted_as_candidate", "needs_second_source", "counter_evidence_required", "name_doppler", "not_sufficient", "excluded", "internal_only"}
        if decision not in allowed:
            raise ValueError("Unbekannte oder nicht erlaubte Verification-Entscheidung.")
        assessment = self.get_assessment(assessment_id)
        did = new_id("vdec")
        self.db.execute('''INSERT INTO verification_decisions(decision_id,case_id,assessment_id,reviewer,decision,notes,created_at)
        VALUES(?,?,?,?,?,?,?)''', [did, assessment["case_id"], assessment_id, reviewer, decision, notes or "Analystische Verification-Entscheidung.", now_ts()])
        self.audit.log("decide", "corroboration_assessment", assessment_id, assessment["case_id"], {"decision": decision})
        return self.db.one("SELECT * FROM verification_decisions WHERE decision_id=?", [did])

    def run_dashboard(self, case_id: str, run_id: str = "") -> Dict[str, Any]:
        run = self.db.one("SELECT * FROM verification_runs WHERE run_id=?", [run_id]) if run_id else self.latest_run(case_id)
        assessments = self.list_assessments(case_id, run.get("run_id") if run else "") if run else []
        flags = self.list_flags(case_id)
        second = self.list_second_source_checks(case_id)
        buckets = {"not_reliable": 0, "weak": 0, "plausible": 0, "strong": 0, "very_strong": 0}
        for a in assessments:
            score = int(a.get("corroboration_score") or 0)
            if score < 20: buckets["not_reliable"] += 1
            elif score < 40: buckets["weak"] += 1
            elif score < 60: buckets["plausible"] += 1
            elif score < 80: buckets["strong"] += 1
            else: buckets["very_strong"] += 1
        return {
            "status": "verification_ready" if run else "no_verification_run",
            "run": run or {},
            "assessment_count": len(assessments),
            "average_score": round(sum(int(a.get("corroboration_score") or 0) for a in assessments) / max(1, len(assessments)), 2),
            "buckets": buckets,
            "open_flags": len(flags),
            "second_source_checks": len(second),
            "top_assessments": assessments[:10],
            "flags": flags[:20],
            "second_source": second[:20],
            "guardrails": [
                "Keine automatische Identitätsbestätigung",
                "Keine Schuld-/Gefährlichkeitsbewertung",
                "Keine private Wohnortgewissheit",
                "Keine biometrische Identifikation",
                "Zweitquelle/Gegenbeleg vor Berichtsfazit",
            ],
        }

    def security_check(self, case_id: str) -> Dict[str, Any]:
        rules = self.db.all("SELECT * FROM verification_rules WHERE active=1")
        bad = []
        for row in self.db.all("SELECT decision FROM verification_decisions WHERE case_id=?", [case_id]):
            if row.get("decision") in PROHIBITED_DECISIONS:
                bad.append(row.get("decision"))
        return {
            "gate": "VERIFICATION_SECURITY_PASS" if not bad and rules else "VERIFICATION_SECURITY_REVIEW",
            "active_rules": len(rules),
            "prohibited_decisions_found": bad,
            "guardrails": [loads(r.get("guardrail_json"), []) for r in rules],
        }
