from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import hashlib
import re

from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]{1,64}@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s()./-]{6,}\d)(?!\d)")
# conservative German-address-style marker; intentionally flags for review rather than claiming certainty
ADDRESS_RE = re.compile(r"(?i)\b([A-ZÄÖÜ][A-Za-zÄÖÜäöüß.-]{2,}(?:straße|str\.|weg|platz|gasse|allee|ring|ufer|damm)\s*\d{1,4}[a-z]?)\b")
POSTAL_CITY_RE = re.compile(r"\b\d{5}\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß.-]{2,}\b")

SENSITIVE_PATTERNS: List[Tuple[str, str, re.Pattern[str], str]] = [
    ("private_email", "sensibel", EMAIL_RE, "E-Mail-Adressen vor externem Export redigieren oder Zweckbindung dokumentieren."),
    ("private_phone", "sensibel", PHONE_RE, "Telefonnummern vor externem Export redigieren oder Exportfreigabe dokumentieren."),
    ("private_address", "nicht_exportfähig", ADDRESS_RE, "Mögliche Privatadresse: standardmäßig nicht exportieren."),
    ("postal_place_context", "sensibel", POSTAL_CITY_RE, "PLZ/Ort-Kontext prüfen; kann bei Schutzfällen sensibel sein."),
    ("minor_data", "kindbezogen", re.compile(r"(?i)\b(kind|kinder|minderjährig|schüler|schülerin|jugendlich|entführt|vermisstes kind|16 jahre|15 jahre|14 jahre|13 jahre|12 jahre)\b"), "Minderjährige/Kinderschutzdaten nur minimal, zweckgebunden und redigiert exportieren."),
    ("victim_data", "opferbezogen", re.compile(r"(?i)\b(opfer|geschädigt|betroffene person|verletzte person|bedrohte person|vermisste person)\b"), "Opfer-/Betroffenendaten schützen; keine unnötigen privaten Details exportieren."),
    ("witness_data", "intern", re.compile(r"(?i)\b(zeuge|zeugin|hinweisgeber|informant|kontaktperson)\b"), "Zeugen-/Hinweisgeberdaten intern halten oder stark redigieren."),
    ("health_data", "sensibel", re.compile(r"(?i)\b(gesundheit|krankheit|diagnose|therapie|psychisch|trauma|medikation|arzt|klinikum)\b"), "Gesundheitsdaten sind besonders sensibel und in Behördenpaketen nur bei Erforderlichkeit."),
    ("religion_jewish_context", "sensibel", re.compile(r"(?i)\b(jüdisch|judentum|synagoge|gemeinde|rabbi|antisemit|israelbezogen|tora|koscher)\b"), "Religions-/Gemeindebezüge als sensible Schutzdaten behandeln."),
    ("criminal_allegation", "prüfpflichtig", re.compile(r"(?i)\b(straftat|tatverdacht|beschuldig|täter|schuld|gefährlich|gewalt|drohung|terror|entführung|missbrauch|mord|raub|betrug)\b"), "Strafrechtliche Vorwürfe nur als geprüfte Hinweise mit Quellen- und Unsicherheitsangabe exportieren."),
]

RECIPIENT_INTERNAL = {"internal", "internal_analyst", "internal_casefile"}
SAFE_REDACTION_LEVELS = {"redacted", "minimal_public", "authority_sensitive"}


class PrivacySecurityFinishService:
    """Build 55.0 privacy, redaction and stable export gate.

    This service is deliberately conservative: it does not decide that data is
    unlawful, but it flags sensitive data classes and blocks external exports when
    high-risk classes are still unredacted or unreviewed.
    """

    def __init__(self, db: Database, audit: AuditService, one_page_output: Any | None = None):
        self.db = db
        self.audit = audit
        self.one_page_output = one_page_output
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS privacy_export_reviews_55 (
          review_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          entity_id TEXT DEFAULT '',
          draft_id TEXT DEFAULT '',
          recipient_class TEXT NOT NULL,
          redaction_level TEXT NOT NULL,
          decision TEXT NOT NULL,
          severity TEXT NOT NULL,
          flags_json TEXT NOT NULL,
          blockers_json TEXT NOT NULL,
          actions_json TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_privexp55_case ON privacy_export_reviews_55(case_id, created_at);
        CREATE TABLE IF NOT EXISTS case_retention_reviews_55 (
          retention_review_id TEXT PRIMARY KEY,
          case_id TEXT NOT NULL,
          retention_until TEXT DEFAULT '',
          recommendation TEXT NOT NULL,
          actions_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
        );
        ''')
        self.db.conn.commit()

    def scan_text(self, text: str) -> Dict[str, Any]:
        text = text or ""
        flags: List[Dict[str, Any]] = []
        seen: set[Tuple[str, str]] = set()
        for code, data_class, pattern, action in SENSITIVE_PATTERNS:
            for m in pattern.finditer(text):
                sample = m.group(0).strip()
                key = (code, sample.lower())
                if key in seen:
                    continue
                seen.add(key)
                flags.append({
                    "code": code,
                    "data_class": data_class,
                    "sample": self._mask_sample(code, sample),
                    "start": m.start(),
                    "end": m.end(),
                    "severity": self._severity_for(code),
                    "recommended_action": action,
                })
        severity_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        max_sev = "low"
        for f in flags:
            if severity_order[f["severity"]] > severity_order[max_sev]:
                max_sev = f["severity"]
        return {"flag_count": len(flags), "severity": max_sev if flags else "low", "flags": flags, "content_hash": self._sha_text(text)}

    def assess_export(
        self,
        case_id: str,
        *,
        entity_id: str = "",
        draft_id: str = "",
        recipient_class: str = "authority_or_meldestelle",
        redaction_level: str = "redacted",
        text: str = "",
    ) -> Dict[str, Any]:
        if not text:
            text = self._load_export_text(case_id, entity_id=entity_id, draft_id=draft_id, recipient_class=recipient_class, redaction_level=redaction_level)
        scan = self.scan_text(text)
        blockers, actions = self._evaluate_flags(scan["flags"], recipient_class=recipient_class, redaction_level=redaction_level)
        chain_issues = self._chain_export_issues(case_id, entity_id)
        actions.extend(chain_issues)
        if any(i.get("blocker") for i in chain_issues):
            blockers.extend(i for i in chain_issues if i.get("blocker"))
        decision = "allow"
        if blockers:
            decision = "block"
        elif scan["flags"] or chain_issues:
            decision = "review_required"
        review_id = new_id("priv55")
        row = {
            "review_id": review_id,
            "case_id": case_id,
            "entity_id": entity_id,
            "draft_id": draft_id,
            "recipient_class": recipient_class,
            "redaction_level": redaction_level,
            "decision": decision,
            "severity": scan["severity"],
            "flags": scan["flags"],
            "blockers": blockers,
            "actions": actions,
            "content_hash": scan["content_hash"],
            "created_at": now_ts(),
        }
        self.db.execute(
            '''INSERT INTO privacy_export_reviews_55(review_id,case_id,entity_id,draft_id,recipient_class,redaction_level,decision,severity,flags_json,blockers_json,actions_json,content_hash,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            [review_id, case_id, entity_id, draft_id, recipient_class, redaction_level, decision, scan["severity"], dumps(scan["flags"]), dumps(blockers), dumps(actions), scan["content_hash"], row["created_at"]],
        )
        self.audit.log("privacy_gate", "privacy_export_review_55", review_id, case_id, {"decision": decision, "severity": scan["severity"], "blockers": len(blockers), "flags": len(scan["flags"])})
        return row

    def latest_reviews(self, case_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        rows = self.db.all("SELECT * FROM privacy_export_reviews_55 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", [case_id, int(limit)])
        for r in rows:
            r["flags"] = loads(r.pop("flags_json", "[]"), [])
            r["blockers"] = loads(r.pop("blockers_json", "[]"), [])
            r["actions"] = loads(r.pop("actions_json", "[]"), [])
        return rows

    def redact_text(self, text: str, *, level: str = "redacted") -> Dict[str, Any]:
        original = text or ""
        redacted = original
        replacements: List[Dict[str, str]] = []
        def repl_email(m: re.Match[str]) -> str:
            value = m.group(0)
            replacement = value[:2] + "***@" + value.split("@", 1)[1]
            replacements.append({"type": "private_email", "from": self._mask_sample("private_email", value), "to": replacement})
            return replacement
        def repl_phone(m: re.Match[str]) -> str:
            value = m.group(0)
            replacements.append({"type": "private_phone", "from": self._mask_sample("private_phone", value), "to": "[REDACTED_PHONE]"})
            return "[REDACTED_PHONE]"
        def repl_addr(m: re.Match[str]) -> str:
            value = m.group(0)
            replacements.append({"type": "private_address", "from": self._mask_sample("private_address", value), "to": "[REDACTED_ADDRESS]"})
            return "[REDACTED_ADDRESS]"
        redacted = EMAIL_RE.sub(repl_email, redacted)
        redacted = PHONE_RE.sub(repl_phone, redacted)
        if level in {"redacted", "minimal_public"}:
            redacted = ADDRESS_RE.sub(repl_addr, redacted)
        return {"text": redacted, "replacement_count": len(replacements), "replacements": replacements, "sha256": self._sha_text(redacted)}

    def create_retention_review(self, case_id: str) -> Dict[str, Any]:
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id]) or {}
        retention_until = case.get("retention_until") or ""
        actions: List[Dict[str, Any]] = []
        if not retention_until:
            recommendation = "set_retention_date"
            actions.append({"action": "set_retention_until", "reason": "Keine Lösch-/Reviewfrist am Fall hinterlegt."})
        else:
            recommendation = "review_on_retention_date"
            actions.append({"action": "calendar_review", "retention_until": retention_until, "reason": "Fall spätestens zum angegebenen Datum prüfen, archivieren oder löschen."})
        if self._count_rows("search_chain_nodes_54", case_id) > 0:
            actions.append({"action": "review_chain_minimization", "reason": "Nicht inkludierte oder verworfene Treffer nach Fallabschluss entfernen/archivieren."})
        if self._count_rows("one_page_outputs_54", case_id) > 0:
            actions.append({"action": "review_export_storage", "reason": "Exportpakete auf Empfängerklasse, Redaktion und sichere Ablage prüfen."})
        retention_review_id = new_id("ret55")
        self.db.execute(
            '''INSERT INTO case_retention_reviews_55(retention_review_id,case_id,retention_until,recommendation,actions_json,created_at)
               VALUES(?,?,?,?,?,?)''',
            [retention_review_id, case_id, retention_until, recommendation, dumps(actions), now_ts()],
        )
        self.audit.log("create", "case_retention_review_55", retention_review_id, case_id, {"recommendation": recommendation, "actions": len(actions)})
        return {"retention_review_id": retention_review_id, "case_id": case_id, "retention_until": retention_until, "recommendation": recommendation, "actions": actions}

    def _load_export_text(self, case_id: str, *, entity_id: str, draft_id: str, recipient_class: str, redaction_level: str) -> str:
        if draft_id and self._table_exists("profile_report_drafts_54"):
            row = self.db.one("SELECT body FROM profile_report_drafts_54 WHERE draft_id=? AND case_id=?", [draft_id, case_id])
            if row:
                return row.get("body", "")
        if self.one_page_output is not None:
            return self.one_page_output.build_markdown(case_id, entity_id=entity_id, output_type="casefile", recipient_class=recipient_class, redaction_level=redaction_level)
        case = self.db.one("SELECT * FROM cases WHERE case_id=?", [case_id]) or {}
        return "\n".join([str(case.get("title", "")), str(case.get("purpose", "")), str(case.get("legal_basis", ""))])

    def _evaluate_flags(self, flags: List[Dict[str, Any]], *, recipient_class: str, redaction_level: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        external = recipient_class not in RECIPIENT_INTERNAL
        blockers: List[Dict[str, Any]] = []
        actions: List[Dict[str, Any]] = []
        for f in flags:
            code = f.get("code")
            action = {"code": code, "severity": f.get("severity"), "action": f.get("recommended_action")}
            actions.append(action)
            if not external:
                continue
            if code in {"private_address", "witness_data"}:
                blockers.append({"code": code, "reason": "External export blocked unless explicitly redacted/removed.", "sample": f.get("sample")})
            if code in {"minor_data", "victim_data", "health_data", "religion_jewish_context", "criminal_allegation"} and redaction_level not in SAFE_REDACTION_LEVELS:
                blockers.append({"code": code, "reason": "Sensitive class requires redacted/minimal/authority-sensitive export profile.", "sample": f.get("sample")})
        return blockers, actions

    def _chain_export_issues(self, case_id: str, entity_id: str) -> List[Dict[str, Any]]:
        if not self._table_exists("search_chain_nodes_54"):
            return []
        params: List[Any] = [case_id]
        where = "case_id=?"
        if entity_id:
            where += " AND entity_id=?"
            params.append(entity_id)
        issues: List[Dict[str, Any]] = []
        included = self.db.all(f"SELECT node_id,status,confidence_label,parent_node_id FROM search_chain_nodes_54 WHERE {where} AND node_type='included_fact'", params)
        ready = [r for r in included if r.get("status") == "report_released"]
        needs_review = [r for r in included if r.get("status") in {"needs_review", "active", "included", "profile_candidate"}]
        if included and not ready:
            issues.append({"code": "no_report_released_chain_nodes", "blocker": False, "action": "Markiere mindestens die stärksten inkludierten Informationen als 'für Bericht freigegeben' oder dokumentiere Review-Entscheidung."})
        if needs_review:
            issues.append({"code": "included_nodes_need_review", "blocker": False, "count": len(needs_review), "action": "Inkludierte Informationen vor Behördenexport final prüfen."})
        orphan = [r for r in included if not r.get("parent_node_id")]
        if orphan:
            issues.append({"code": "orphan_profile_points", "blocker": True, "count": len(orphan), "action": "Profilpunkte ohne Chain-Ursprung korrigieren."})
        return issues

    def _severity_for(self, code: str) -> str:
        if code in {"private_address", "minor_data"}:
            return "critical"
        if code in {"victim_data", "witness_data", "health_data", "religion_jewish_context", "criminal_allegation"}:
            return "high"
        if code in {"private_phone", "private_email"}:
            return "medium"
        return "low"

    def _mask_sample(self, code: str, sample: str) -> str:
        sample = sample or ""
        if code == "private_email" and "@" in sample:
            return sample[:2] + "***@" + sample.split("@", 1)[1]
        if code == "private_phone":
            return "[PHONE:" + hashlib.sha256(sample.encode("utf-8")).hexdigest()[:8] + "]"
        if code == "private_address":
            return "[ADDRESS:" + hashlib.sha256(sample.encode("utf-8")).hexdigest()[:8] + "]"
        return sample[:80]

    def _sha_text(self, text: str) -> str:
        return hashlib.sha256((text or "").encode("utf-8")).hexdigest()

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))

    def _count_rows(self, table: str, case_id: str) -> int:
        if not self._table_exists(table):
            return 0
        row = self.db.one(f"SELECT COUNT(*) AS c FROM {table} WHERE case_id=?", [case_id]) or {"c": 0}
        return int(row.get("c", 0))
