from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import secrets
import shutil
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

PERSONA_TYPES = {"synthetic_alias", "organization_owned", "pseudonymous_research"}
PERSONA_STATUSES = {"pending_review", "approved", "rejected", "suspended", "retired"}
ACCOUNT_ORIGINS = {"manual_existing", "manual_authorized_creation", "organization_provisioned"}
ACCOUNT_STATUSES = {"active", "inactive", "expired", "revoked"}
EGRESS_MODES = {"direct", "http_proxy", "socks5", "tor_local", "system_proxy"}
EGRESS_STATUSES = {"pending_review", "approved", "rejected", "suspended", "retired"}
SESSION_STATUSES = {"draft", "pending_approval", "approved", "active", "closed", "revoked", "expired", "blocked"}
SESSION_ACTIONS = {"browse", "search", "manual_login", "manual_upload", "manual_download", "note", "other"}
RISK_LEVELS = {"low", "medium", "high"}

ACCOUNT_CONFIRMATION = "KONTO MANUELL ANGELEGT UND BERECHTIGT"
PERSONA_APPROVAL = "RESEARCH-PERSONA FREIGEBEN"
EGRESS_APPROVAL = "EGRESS-PROFIL FREIGEBEN"
SESSION_APPROVAL = "RESEARCH-PERSONA-SITZUNG FREIGEBEN"
SESSION_START = "RESEARCH-PERSONA-SITZUNG STARTEN"
SESSION_CLOSE = "RESEARCH-SITZUNG BEENDET UND BROWSER GESCHLOSSEN"
ACCESS_REVIEW_CONFIRMATION = "FALLZUGRIFF MANUELL GEPRÜFT"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canonical(value).encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: Any, limit: int = 1000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _iso_expired(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed <= datetime.now(timezone.utc)
    except ValueError:
        return True


def _https_url(value: str) -> str:
    text = _clean(value, 3000)
    if not text:
        return ""
    parts = urlsplit(text)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Startadresse muss eine öffentliche HTTPS-URL ohne eingebettete Zugangsdaten sein")
    return text


def _loopback(host: str) -> bool:
    text = str(host or "").strip().casefold()
    if text in {"localhost", "::1"}:
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


class Build143Service:
    """Build 143 controlled collaboration and research-persona sessions.

    The service provides case-bound synthetic research personas, manually
    provisioned alias-account metadata and temporary isolated Firefox profiles.
    It never creates third-party accounts, never automates login or anti-bot
    evasion, and never claims anonymity or non-attribution. Network separation
    is only as strong as the operator-provided proxy/Tor endpoint, endpoint
    security, platform behaviour and operational discipline.
    """

    BUILD = "143.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        install_dir: str | Path,
        *,
        governance: Any,
        protection: Any,
        build142: Any,
        build141: Any,
        launcher: Any | None = None,
        clock: Any | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.install_dir = Path(install_dir).resolve()
        self.governance = governance
        self.protection = protection
        self.build142 = build142
        self.build141 = build141
        self.launcher = launcher or protection.launcher
        self.clock = clock or time.time
        self.session_root = (self.base_dir / "data" / "research_persona_sessions_143").resolve()
        self.session_root.mkdir(parents=True, exist_ok=True)
        self._chmod(self.session_root, 0o700)
        self._cleanup_tombstones()

    @staticmethod
    def _chmod(path: Path, mode: int) -> None:
        try:
            path.chmod(mode)
        except OSError:
            pass

    def _cleanup_tombstones(self) -> None:
        for candidate in self.session_root.glob(".deleting_session143_*"):
            try:
                resolved = candidate.resolve()
                if resolved.parent != self.session_root:
                    continue
                if candidate.is_dir() and not candidate.is_symlink():
                    shutil.rmtree(candidate)
                else:
                    candidate.unlink(missing_ok=True)
            except OSError:
                pass

    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any] | None:
        if not target_id:
            return None
        row = self.db.one("SELECT * FROM targets WHERE case_id=? AND target_id=?", (case_id, target_id))
        if not row:
            raise KeyError("Zielperson gehört nicht zu diesem Fall")
        return row

    def _authorize(self, actor: str, case_id: str, permission: str) -> None:
        self.governance.authorize(username=actor, case_id=case_id, permission=permission)

    def _event(self, *, case_id: str, event_type: str, object_type: str, object_id: str, actor: str, payload: Mapping[str, Any] | None = None) -> None:
        previous = self.db.one("SELECT event_hash FROM build143_events WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous_hash = str((previous or {}).get("event_hash") or "GENESIS")
        safe = dict(payload or {})
        for key in list(safe):
            if any(mark in key.casefold() for mark in ("password", "secret", "token", "credential")):
                safe[key] = "[redacted]"
        stamp = now_ts()
        body = {
            "case_id": case_id,
            "event_type": event_type,
            "object_type": object_type,
            "object_id": object_id,
            "payload": safe,
            "previous_hash": previous_hash,
            "created_by": actor,
            "created_at": stamp,
        }
        event_hash = _sha(body)
        self.db.execute(
            "INSERT INTO build143_events(event_id,case_id,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (new_id("evt143"), case_id, event_type, object_type, object_id, dumps(safe), previous_hash, event_hash, actor, stamp),
        )
        self.audit.log(event_type, f"build143_{object_type}", object_id, case_id, safe)

    def _reject_target_impersonation(self, case_id: str, label: str, contact_alias: str) -> None:
        candidates = {re.sub(r"\W+", "", label.casefold()), re.sub(r"\W+", "", contact_alias.casefold())}
        candidates.discard("")
        if not candidates:
            return
        for row in self.db.all("SELECT name,aliases_json,emails_json,usernames_json FROM targets WHERE case_id=?", (case_id,)):
            values = [row.get("name") or ""]
            for key in ("aliases_json", "emails_json", "usernames_json"):
                values.extend(loads(row.get(key), []))
            normalized = {re.sub(r"\W+", "", str(value).casefold()) for value in values if value}
            if candidates & normalized:
                raise PermissionError("Research-Persona darf keine vorhandene Zielperson oder deren bekannten Account imitieren")

    # ---------- personas and manually provisioned accounts ----------
    def create_persona(
        self,
        *,
        case_id: str,
        label: str,
        persona_type: str,
        purpose: str,
        legal_basis: str,
        jurisdiction: str = "DE/EU",
        contact_alias: str = "",
        risk_level: str = "medium",
        synthetic_identity_confirmed: bool = True,
        no_existing_person_impersonation: bool = True,
        expires_at: str = "",
        notes: str = "",
        actor: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id, "persona.create")
        persona_type = _clean(persona_type, 40).casefold()
        risk_level = _clean(risk_level, 20).casefold()
        if persona_type not in PERSONA_TYPES:
            raise ValueError("Unbekannter Research-Persona-Typ")
        if risk_level not in RISK_LEVELS:
            raise ValueError("Unbekannte Risikostufe")
        label = _clean(label, 120)
        purpose = _clean(purpose, 1000)
        legal_basis = _clean(legal_basis, 1000)
        contact_alias = _clean(contact_alias, 240)
        if len(label) < 3 or len(purpose) < 10 or len(legal_basis) < 5:
            raise ValueError("Bezeichnung, Zweck und Rechtsgrundlage müssen nachvollziehbar ausgefüllt sein")
        if not synthetic_identity_confirmed or not no_existing_person_impersonation:
            raise PermissionError("EagleEye unterstützt nur synthetische oder organisationsgebundene Research-Personas ohne Identitätsübernahme")
        self._reject_target_impersonation(case_id, label, contact_alias)
        if expires_at and _iso_expired(expires_at):
            raise ValueError("Ablaufdatum ist ungültig oder liegt in der Vergangenheit")
        persona_id = new_id("persona143")
        stamp = now_ts()
        self.db.execute(
            """INSERT INTO research_personas_143(persona_id,case_id,label,persona_type,purpose,legal_basis,jurisdiction,contact_alias,risk_level,status,synthetic_identity_confirmed,no_existing_person_impersonation,requested_by,expires_at,notes,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,'pending_review',1,1,?,?,?,?,?)""",
            (persona_id, case_id, label, persona_type, purpose, legal_basis, _clean(jurisdiction, 80), contact_alias, risk_level, actor, _clean(expires_at, 64), _clean(notes, 2000), stamp, stamp),
        )
        self._event(case_id=case_id, event_type="persona_created", object_type="persona", object_id=persona_id, actor=actor, payload={"persona_type": persona_type, "risk_level": risk_level, "status": "pending_review"})
        return self.get_persona(case_id=case_id, persona_id=persona_id)

    def get_persona(self, *, case_id: str, persona_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM research_personas_143 WHERE case_id=? AND persona_id=?", (case_id, persona_id))
        if not row:
            raise KeyError("Research-Persona nicht gefunden")
        return row

    def review_persona(self, *, case_id: str, persona_id: str, decision: str, reason: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._authorize(actor, case_id, "persona.approve")
        row = self.get_persona(case_id=case_id, persona_id=persona_id)
        decision = _clean(decision, 30).casefold()
        if decision not in {"approved", "rejected", "suspended", "retired"}:
            raise ValueError("Ungültige Persona-Entscheidung")
        if decision == "approved" and confirmation.strip() != PERSONA_APPROVAL:
            raise PermissionError(f"Freigabephrase {PERSONA_APPROVAL} fehlt")
        reason = _clean(reason, 1500)
        if len(reason) < 15:
            raise ValueError("Reviewbegründung ist zu kurz")
        if decision == "approved" and row["requested_by"].casefold() == actor.casefold() and row["risk_level"] in {"medium", "high"}:
            raise PermissionError("Vier-Augen-Prinzip: Ersteller darf eine mittlere oder hohe Research-Persona nicht selbst freigeben")
        self.db.execute(
            "UPDATE research_personas_143 SET status=?,approved_by=?,approval_reason=?,updated_at=? WHERE persona_id=? AND case_id=?",
            (decision, actor, reason, now_ts(), persona_id, case_id),
        )
        self._event(case_id=case_id, event_type="persona_reviewed", object_type="persona", object_id=persona_id, actor=actor, payload={"decision": decision, "reason": reason})
        return self.get_persona(case_id=case_id, persona_id=persona_id)

    def add_persona_account(
        self,
        *,
        case_id: str,
        persona_id: str,
        platform: str,
        account_label: str,
        username_alias: str = "",
        email_alias: str = "",
        account_origin: str = "manual_existing",
        terms_reviewed: bool = False,
        expires_at: str = "",
        credential_secret: str = "",
        confirmation: str,
        actor: str,
    ) -> dict[str, Any]:
        self._authorize(actor, case_id, "persona.manage")
        persona = self.get_persona(case_id=case_id, persona_id=persona_id)
        if persona["status"] not in {"pending_review", "approved"}:
            raise PermissionError("Für eine abgelehnte, gesperrte oder ausgemusterte Persona darf kein Account hinterlegt werden")
        if confirmation.strip() != ACCOUNT_CONFIRMATION:
            raise PermissionError(f"Bestätigung {ACCOUNT_CONFIRMATION} fehlt")
        account_origin = _clean(account_origin, 50).casefold()
        if account_origin not in ACCOUNT_ORIGINS:
            raise PermissionError("Automatisierte, geliehene oder fremde Accounts werden nicht unterstützt")
        if expires_at and _iso_expired(expires_at):
            raise ValueError("Account-Ablaufdatum ist ungültig oder liegt in der Vergangenheit")
        platform = _clean(platform, 120)
        account_label = _clean(account_label, 120)
        username_alias = _clean(username_alias, 160)
        email_alias = _clean(email_alias, 240)
        if len(platform) < 2 or len(account_label) < 2 or not (username_alias or email_alias):
            raise ValueError("Plattform, Kontobezeichnung und mindestens ein Alias sind erforderlich")
        self._reject_target_impersonation(case_id, username_alias, email_alias)
        account_id = new_id("paccount143")
        secret_ref = f"persona143_account_{account_id}"
        secret_present = bool(str(credential_secret or ""))
        if secret_present:
            self.protection.set_secret(secret_ref, str(credential_secret))
        stamp = now_ts()
        self.db.execute(
            """INSERT INTO persona_accounts_143(account_id,persona_id,case_id,platform,account_label,username_alias,email_alias,account_origin,secret_ref,secret_present,terms_reviewed,manual_creation_confirmed,status,expires_at,created_by,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (account_id, persona_id, case_id, platform, account_label, username_alias, email_alias, account_origin, secret_ref if secret_present else "", int(secret_present), int(bool(terms_reviewed)), 1, "active", _clean(expires_at, 64), actor, stamp, stamp),
        )
        self._event(case_id=case_id, event_type="persona_account_added", object_type="persona_account", object_id=account_id, actor=actor, payload={"platform": platform, "account_origin": account_origin, "terms_reviewed": bool(terms_reviewed), "secret_present": secret_present, "automatic_creation": False})
        return self.get_account(case_id=case_id, account_id=account_id)

    def get_account(self, *, case_id: str, account_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM persona_accounts_143 WHERE case_id=? AND account_id=?", (case_id, account_id))
        if not row:
            raise KeyError("Research-Persona-Account nicht gefunden")
        row.pop("secret_ref", None)
        return row

    # ---------- egress profiles ----------
    def create_egress_profile(
        self,
        *,
        case_id: str,
        label: str,
        mode: str,
        proxy_host: str = "",
        proxy_port: int = 0,
        remote_dns: bool = True,
        requires_auth: bool = False,
        credential_secret: str = "",
        expires_at: str = "",
        risk_note: str = "",
        actor: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        self._authorize(actor, case_id, "egress.manage")
        mode = _clean(mode, 30).casefold()
        if mode not in EGRESS_MODES:
            raise ValueError("Unbekannter Egress-Modus")
        label = _clean(label, 120)
        host = _clean(proxy_host, 253)
        port = int(proxy_port or 0)
        if len(label) < 3:
            raise ValueError("Egress-Bezeichnung ist zu kurz")
        if mode in {"http_proxy", "socks5", "tor_local"}:
            if not host or not 1 <= port <= 65535 or not re.fullmatch(r"[A-Za-z0-9._:-]{1,253}", host):
                raise ValueError("Proxy-Host oder -Port ist ungültig")
        else:
            host, port = "", 0
        if mode == "tor_local":
            if not _loopback(host):
                raise PermissionError("Tor-Local darf ausschließlich an einen lokalen Loopback-SOCKS-Endpunkt gebunden werden")
            remote_dns = True
        if mode == "socks5" and not remote_dns:
            risk_note = (_clean(risk_note, 1600) + " | WARNUNG: Remote DNS ist deaktiviert; DNS-Leak-Risiko.").strip(" |").strip()
        if expires_at and _iso_expired(expires_at):
            raise ValueError("Egress-Ablaufdatum ist ungültig oder liegt in der Vergangenheit")
        egress_id = new_id("egress143")
        secret_ref = f"persona143_egress_{egress_id}"
        secret_present = bool(str(credential_secret or ""))
        if secret_present:
            self.protection.set_secret(secret_ref, str(credential_secret))
        stamp = now_ts()
        self.db.execute(
            """INSERT INTO network_egress_profiles_143(egress_id,case_id,label,mode,proxy_host,proxy_port,remote_dns,requires_auth,secret_ref,secret_present,status,risk_note,requested_by,expires_at,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,'pending_review',?,?,?,?,?)""",
            (egress_id, case_id, label, mode, host, port, int(bool(remote_dns)), int(bool(requires_auth)), secret_ref if secret_present else "", int(secret_present), _clean(risk_note, 2000), actor, _clean(expires_at, 64), stamp, stamp),
        )
        self._event(case_id=case_id, event_type="egress_profile_created", object_type="egress", object_id=egress_id, actor=actor, payload={"mode": mode, "remote_dns": bool(remote_dns), "requires_auth": bool(requires_auth), "automatic_provisioning": False})
        return self.get_egress(case_id=case_id, egress_id=egress_id)

    def get_egress(self, *, case_id: str, egress_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM network_egress_profiles_143 WHERE case_id=? AND egress_id=?", (case_id, egress_id))
        if not row:
            raise KeyError("Egress-Profil nicht gefunden")
        row.pop("secret_ref", None)
        return row

    def review_egress(self, *, case_id: str, egress_id: str, decision: str, reason: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._authorize(actor, case_id, "egress.approve")
        row = self.db.one("SELECT * FROM network_egress_profiles_143 WHERE case_id=? AND egress_id=?", (case_id, egress_id))
        if not row:
            raise KeyError("Egress-Profil nicht gefunden")
        decision = _clean(decision, 30).casefold()
        if decision not in {"approved", "rejected", "suspended", "retired"}:
            raise ValueError("Ungültige Egress-Entscheidung")
        if decision == "approved" and confirmation.strip() != EGRESS_APPROVAL:
            raise PermissionError(f"Freigabephrase {EGRESS_APPROVAL} fehlt")
        reason = _clean(reason, 1500)
        if len(reason) < 15:
            raise ValueError("Reviewbegründung ist zu kurz")
        if decision == "approved" and row["requested_by"].casefold() == actor.casefold():
            raise PermissionError("Vier-Augen-Prinzip: Egress-Antragsteller darf das eigene Profil nicht freigeben")
        self.db.execute("UPDATE network_egress_profiles_143 SET status=?,approved_by=?,approval_reason=?,updated_at=? WHERE egress_id=? AND case_id=?", (decision, actor, reason, now_ts(), egress_id, case_id))
        self._event(case_id=case_id, event_type="egress_profile_reviewed", object_type="egress", object_id=egress_id, actor=actor, payload={"decision": decision, "reason": reason})
        return self.get_egress(case_id=case_id, egress_id=egress_id)

    # ---------- temporary isolated research sessions ----------
    def plan_session(
        self,
        *,
        case_id: str,
        persona_id: str,
        egress_id: str,
        purpose: str,
        legal_basis: str,
        actor: str,
        target_id: str = "",
        account_id: str = "",
        start_url: str = "",
        require_origin_separation: bool = True,
        max_actions: int = 20,
        duration_minutes: int = 60,
    ) -> dict[str, Any]:
        self._case(case_id)
        self._target(case_id, target_id)
        self._authorize(actor, case_id, "persona.use")
        persona = self.get_persona(case_id=case_id, persona_id=persona_id)
        if persona["status"] != "approved" or _iso_expired(persona.get("expires_at") or ""):
            raise PermissionError("Research-Persona ist nicht freigegeben oder abgelaufen")
        egress = self.get_egress(case_id=case_id, egress_id=egress_id)
        if egress["status"] != "approved" or _iso_expired(egress.get("expires_at") or ""):
            raise PermissionError("Egress-Profil ist nicht freigegeben oder abgelaufen")
        if account_id:
            account = self.db.one("SELECT * FROM persona_accounts_143 WHERE case_id=? AND account_id=? AND persona_id=?", (case_id, account_id, persona_id))
            if not account or account["status"] != "active" or _iso_expired(account.get("expires_at") or ""):
                raise PermissionError("Research-Persona-Account ist nicht aktiv, abgelaufen oder gehört nicht zur Persona")
        purpose = _clean(purpose, 1200)
        legal_basis = _clean(legal_basis, 1200)
        if len(purpose) < 10 or len(legal_basis) < 5:
            raise ValueError("Sitzungszweck und Rechtsgrundlage müssen nachvollziehbar dokumentiert sein")
        start_url = _https_url(start_url)
        max_actions = max(1, min(int(max_actions), 100))
        duration_minutes = max(10, min(int(duration_minutes), 240))
        risk_level = "high" if account_id or persona["risk_level"] == "high" else ("medium" if require_origin_separation else "low")
        session_id = new_id("rsession143")
        stamp = now_ts()
        self.db.execute(
            """INSERT INTO research_persona_sessions_143(session_id,case_id,target_id,persona_id,account_id,egress_id,purpose,legal_basis,start_url,require_origin_separation,risk_level,status,max_actions,duration_minutes,requested_by,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,'draft',?,?,?,?,?)""",
            (session_id, case_id, target_id or None, persona_id, account_id or None, egress_id, purpose, legal_basis, start_url, int(bool(require_origin_separation)), risk_level, max_actions, duration_minutes, actor, stamp, stamp),
        )
        self._event(case_id=case_id, event_type="persona_session_planned", object_type="persona_session", object_id=session_id, actor=actor, payload={"risk_level": risk_level, "max_actions": max_actions, "duration_minutes": duration_minutes, "automatic_account_creation": False, "automatic_login": False})
        return self.get_session(case_id=case_id, session_id=session_id)

    def get_session(self, *, case_id: str, session_id: str) -> dict[str, Any]:
        row = self.db.one(
            """SELECT s.*,p.label AS persona_label,e.label AS egress_label,e.mode AS egress_mode,e.proxy_host,e.proxy_port,e.remote_dns,e.requires_auth,a.platform,a.account_label,a.username_alias,a.email_alias
               FROM research_persona_sessions_143 s
               JOIN research_personas_143 p ON p.persona_id=s.persona_id
               JOIN network_egress_profiles_143 e ON e.egress_id=s.egress_id
               LEFT JOIN persona_accounts_143 a ON a.account_id=s.account_id
               WHERE s.case_id=? AND s.session_id=?""",
            (case_id, session_id),
        )
        if not row:
            raise KeyError("Research-Persona-Sitzung nicht gefunden")
        return row

    def _preflight_findings(self, session: Mapping[str, Any]) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        def add(key: str, severity: str, ok: bool, message: str) -> None:
            findings.append({"key": key, "severity": severity, "status": "pass" if ok else ("blocker" if severity == "blocker" else "warning"), "message": message})

        persona = self.get_persona(case_id=session["case_id"], persona_id=session["persona_id"])
        egress = self.get_egress(case_id=session["case_id"], egress_id=session["egress_id"])
        add("persona_approved", "blocker", persona["status"] == "approved" and not _iso_expired(persona.get("expires_at") or ""), "Research-Persona ist freigegeben und nicht abgelaufen.")
        add("no_impersonation", "blocker", bool(persona.get("no_existing_person_impersonation")), "Keine Übernahme der Identität einer realen Zielperson.")
        add("egress_approved", "blocker", egress["status"] == "approved" and not _iso_expired(egress.get("expires_at") or ""), "Egress-Profil ist freigegeben und nicht abgelaufen.")
        mode = str(egress.get("mode") or "direct")
        origin_required = bool(session.get("require_origin_separation"))
        add("origin_separation", "blocker", not origin_required or mode not in {"direct", "system_proxy"}, "Explizites Proxy-/Tor-Egress ist für diese Sitzung erforderlich.")
        add("remote_dns", "blocker" if mode in {"socks5", "tor_local"} else "warning", mode not in {"socks5", "tor_local"} or bool(egress.get("remote_dns")), "SOCKS/Tor verwendet Remote DNS zur Reduzierung lokaler DNS-Leaks.")
        if mode == "tor_local":
            local_ok = _loopback(str(egress.get("proxy_host") or ""))
            add("tor_loopback", "blocker", local_ok, "Tor-Local ist an einen Loopback-SOCKS-Endpunkt gebunden.")
            reachable = False
            if local_ok:
                try:
                    with socket.create_connection((str(egress["proxy_host"]), int(egress["proxy_port"])), timeout=0.25):
                        reachable = True
                except OSError:
                    reachable = False
            add("tor_reachable", "blocker", reachable, "Lokaler Tor-SOCKS-Endpunkt ist erreichbar.")
        elif mode in {"http_proxy", "socks5"}:
            add("external_proxy_unverified", "warning", False, "Externer Proxy wird aus OPSEC-Gründen nicht automatisch kontaktiert; Reichweite und Exit-IP müssen im isolierten Browser manuell geprüft werden.")
        if bool(egress.get("requires_auth")):
            add("proxy_auth_manual", "warning", False, "Proxy-Authentifizierung wird nicht in Kommandozeile oder Profil injiziert; eine sichere manuelle Anmeldung kann erforderlich sein.")
        add("ephemeral_profile", "blocker", True, "Sitzung verwendet ein eigenes temporäres Firefox-Profil.")
        add("webrtc_disabled", "blocker", True, "WebRTC wird im Sitzungsprofil deaktiviert.")
        add("geolocation_disabled", "blocker", True, "Geolokalisierung wird im Sitzungsprofil deaktiviert.")
        add("no_trace_claim", "warning", False, "EagleEye garantiert keine Anonymität oder Unverfolgbarkeit; Account-, Endpunkt-, ISP- und Verhaltensspuren bleiben möglich.")
        add("no_automation", "blocker", True, "Keine automatische Kontoerstellung, Anmeldung, Bilduploads oder Anti-Bot-Umgehung.")
        return findings

    def preflight_session(self, *, case_id: str, session_id: str, actor: str) -> dict[str, Any]:
        self._authorize(actor, case_id, "persona.use")
        session = self.get_session(case_id=case_id, session_id=session_id)
        findings = self._preflight_findings(session)
        blockers = sum(1 for item in findings if item["status"] == "blocker")
        warnings = sum(1 for item in findings if item["status"] == "warning")
        status = "pass" if blockers == 0 else "blocked"
        preflight_id = new_id("preflight143")
        self.db.execute(
            "INSERT INTO persona_session_preflights_143(preflight_id,session_id,case_id,status,blocker_count,warning_count,findings_json,checked_by,checked_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (preflight_id, session_id, case_id, status, blockers, warnings, dumps(findings), actor, now_ts()),
        )
        if blockers:
            self.db.execute("UPDATE research_persona_sessions_143 SET status='blocked',updated_at=? WHERE session_id=? AND status IN ('draft','pending_approval','approved','blocked')", (now_ts(), session_id))
        self._event(case_id=case_id, event_type="persona_session_preflight", object_type="persona_session", object_id=session_id, actor=actor, payload={"status": status, "blockers": blockers, "warnings": warnings})
        return {"preflight_id": preflight_id, "status": status, "blocker_count": blockers, "warning_count": warnings, "findings": findings}

    def request_session_approval(self, *, case_id: str, session_id: str, actor: str) -> dict[str, Any]:
        self._authorize(actor, case_id, "persona.use")
        session = self.get_session(case_id=case_id, session_id=session_id)
        if session["status"] not in {"draft", "blocked"}:
            raise ValueError("Nur geplante oder nachgebesserte Sitzungen können eingereicht werden")
        preflight = self.preflight_session(case_id=case_id, session_id=session_id, actor=actor)
        if preflight["blocker_count"]:
            raise PermissionError("OPSEC-Preflight enthält Blocker")
        self.db.execute("UPDATE research_persona_sessions_143 SET status='pending_approval',updated_at=? WHERE session_id=? AND case_id=?", (now_ts(), session_id, case_id))
        self._event(case_id=case_id, event_type="persona_session_review_requested", object_type="persona_session", object_id=session_id, actor=actor, payload={"preflight_id": preflight["preflight_id"]})
        return self.get_session(case_id=case_id, session_id=session_id)

    def approve_session(self, *, case_id: str, session_id: str, reason: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._authorize(actor, case_id, "persona.approve")
        session = self.get_session(case_id=case_id, session_id=session_id)
        if session["status"] != "pending_approval":
            raise ValueError("Sitzung ist nicht zur Freigabe eingereicht")
        if confirmation.strip() != SESSION_APPROVAL:
            raise PermissionError(f"Freigabephrase {SESSION_APPROVAL} fehlt")
        if session["requested_by"].casefold() == actor.casefold():
            raise PermissionError("Vier-Augen-Prinzip: Antragsteller darf die eigene Research-Persona-Sitzung nicht freigeben")
        reason = _clean(reason, 1500)
        if len(reason) < 15:
            raise ValueError("Freigabebegründung ist zu kurz")
        self.db.execute("UPDATE research_persona_sessions_143 SET status='approved',approved_by=?,approval_reason=?,updated_at=? WHERE session_id=? AND case_id=?", (actor, reason, now_ts(), session_id, case_id))
        self._event(case_id=case_id, event_type="persona_session_approved", object_type="persona_session", object_id=session_id, actor=actor, payload={"reason": reason})
        return self.get_session(case_id=case_id, session_id=session_id)

    def _profile_path(self, case_id: str, session_id: str) -> tuple[str, Path]:
        case_token = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:20]
        rel = f"{case_token}/{session_id}/profile"
        path = (self.session_root / rel).resolve()
        if self.session_root not in path.parents:
            raise PermissionError("Ungültiger Sitzungsprofilpfad")
        return rel, path

    @staticmethod
    def _profile_prefs(egress: Mapping[str, Any]) -> dict[str, Any]:
        prefs: dict[str, Any] = {
            "browser.privatebrowsing.autostart": True,
            "browser.formfill.enable": False,
            "browser.sessionstore.resume_from_crash": False,
            "datareporting.healthreport.uploadEnabled": False,
            "datareporting.policy.dataSubmissionEnabled": False,
            "dom.battery.enabled": False,
            "geo.enabled": False,
            "media.peerconnection.enabled": False,
            "network.cookie.cookieBehavior": 5,
            "network.dns.disablePrefetch": True,
            "network.http.referer.XOriginPolicy": 2,
            "network.http.referer.XOriginTrimmingPolicy": 2,
            "network.prefetch-next": False,
            "network.predictor.enabled": False,
            "privacy.clearOnShutdown.cache": True,
            "privacy.clearOnShutdown.cookies": True,
            "privacy.clearOnShutdown.downloads": True,
            "privacy.clearOnShutdown.formdata": True,
            "privacy.clearOnShutdown.history": True,
            "privacy.clearOnShutdown.sessions": True,
            "privacy.firstparty.isolate": True,
            "privacy.globalprivacycontrol.enabled": True,
            "privacy.partition.network_state": True,
            "privacy.resistFingerprinting": True,
            "privacy.sanitize.sanitizeOnShutdown": True,
            "privacy.trackingprotection.enabled": True,
            "privacy.trackingprotection.socialtracking.enabled": True,
            "signon.rememberSignons": False,
            "toolkit.telemetry.enabled": False,
            "toolkit.telemetry.unified": False,
        }
        mode = str(egress.get("mode") or "direct")
        host = str(egress.get("proxy_host") or "")
        port = int(egress.get("proxy_port") or 0)
        if mode in {"socks5", "tor_local"}:
            prefs.update({
                "network.proxy.type": 1,
                "network.proxy.socks": host,
                "network.proxy.socks_port": port,
                "network.proxy.socks_version": 5,
                "network.proxy.socks_remote_dns": bool(egress.get("remote_dns", True)),
                "network.proxy.no_proxies_on": "",
            })
        elif mode == "http_proxy":
            prefs.update({
                "network.proxy.type": 1,
                "network.proxy.http": host,
                "network.proxy.http_port": port,
                "network.proxy.ssl": host,
                "network.proxy.ssl_port": port,
                "network.proxy.no_proxies_on": "",
            })
        return prefs

    def start_session(self, *, case_id: str, session_id: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._authorize(actor, case_id, "persona.session.start")
        session = self.get_session(case_id=case_id, session_id=session_id)
        if session["status"] != "approved":
            raise PermissionError("Research-Persona-Sitzung ist nicht freigegeben")
        if confirmation.strip() != SESSION_START:
            raise PermissionError(f"Startphrase {SESSION_START} fehlt")
        preflight = self.preflight_session(case_id=case_id, session_id=session_id, actor=actor)
        if preflight["blocker_count"]:
            raise PermissionError("OPSEC-Preflight enthält Blocker")
        firefox = self.protection._find_firefox()
        if firefox is None:
            raise PermissionError("Firefox wurde nicht gefunden; es erfolgt kein Rückfall auf das persönliche Browserprofil")
        raw_egress = self.db.one("SELECT * FROM network_egress_profiles_143 WHERE case_id=? AND egress_id=?", (case_id, session["egress_id"])) or {}
        rel, profile = self._profile_path(case_id, session_id)
        if profile.exists():
            shutil.rmtree(profile.parent, ignore_errors=True)
        profile.mkdir(parents=True, exist_ok=True)
        self._chmod(profile.parent.parent, 0o700)
        self._chmod(profile.parent, 0o700)
        self._chmod(profile, 0o700)
        prefs = self._profile_prefs(raw_egress)
        lines = [f"user_pref({json.dumps(key)}, {json.dumps(value, ensure_ascii=False)});" for key, value in sorted(prefs.items())]
        (profile / "user.js").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._chmod(profile / "user.js", 0o600)
        safe_meta = {
            "build": self.BUILD,
            "session_id": session_id,
            "case_fingerprint": _sha(case_id)[:16],
            "persona_label": session["persona_label"],
            "egress_mode": session["egress_mode"],
            "created_at": now_ts(),
            "no_anonymity_guarantee": True,
            "automatic_account_creation": False,
            "automatic_login": False,
        }
        (profile.parent / "session_manifest.json").write_text(json.dumps(safe_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        self._chmod(profile.parent / "session_manifest.json", 0o600)
        start_url = str(session.get("start_url") or "about:blank")
        command = [str(firefox), "-no-remote", "-profile", str(profile), "-private-window", start_url]
        try:
            self.launcher(command)
        except Exception:
            shutil.rmtree(profile.parent, ignore_errors=True)
            raise
        now_epoch = int(self.clock())
        expires_epoch = now_epoch + int(session["duration_minutes"]) * 60
        self.db.execute(
            "UPDATE research_persona_sessions_143 SET status='active',profile_relpath=?,launched_at=?,expires_epoch=?,updated_at=? WHERE session_id=? AND case_id=?",
            (rel, now_ts(), expires_epoch, now_ts(), session_id, case_id),
        )
        self._event(case_id=case_id, event_type="persona_session_started", object_type="persona_session", object_id=session_id, actor=actor, payload={"egress_mode": session["egress_mode"], "duration_minutes": session["duration_minutes"], "start_host": (urlsplit(start_url).hostname or "") if start_url.startswith("https://") else "", "untraceability_claim": False})
        return {"session": self.get_session(case_id=case_id, session_id=session_id), "command_contract": {"no_remote": True, "private_window": True, "personal_profile_fallback": False}, "warnings": ["Egress und Research-Persona reduzieren Verknüpfungsrisiken, garantieren jedoch keine Anonymität oder Unverfolgbarkeit."]}

    def record_session_action(self, *, case_id: str, session_id: str, action_type: str, destination_url: str = "", details: Mapping[str, Any] | None = None, actor: str) -> dict[str, Any]:
        self._authorize(actor, case_id, "persona.session.use")
        session = self.get_session(case_id=case_id, session_id=session_id)
        if session["status"] != "active":
            raise PermissionError("Research-Persona-Sitzung ist nicht aktiv")
        if int(session.get("expires_epoch") or 0) < int(self.clock()):
            self.db.execute("UPDATE research_persona_sessions_143 SET status='expired',updated_at=? WHERE session_id=?", (now_ts(), session_id))
            raise PermissionError("Research-Persona-Sitzung ist abgelaufen")
        if int(session.get("consumed_actions") or 0) >= int(session.get("max_actions") or 0):
            raise PermissionError("Aktionsbudget der Research-Persona-Sitzung ist ausgeschöpft")
        action_type = _clean(action_type, 40).casefold()
        if action_type not in SESSION_ACTIONS:
            raise ValueError("Unbekannter manueller Sitzungsschritt")
        host = ""
        if destination_url:
            parts = urlsplit(_https_url(destination_url))
            host = (parts.hostname or "").casefold()
        action_id = new_id("rsaction143")
        safe_details = dict(details or {})
        for key in list(safe_details):
            if any(mark in key.casefold() for mark in ("password", "secret", "token", "credential")):
                safe_details[key] = "[redacted]"
        self.db.execute(
            "INSERT INTO persona_session_actions_143(action_id,session_id,case_id,action_type,destination_host,details_json,manual_action,actor,created_at) VALUES(?,?,?,?,?,?,1,?,?)",
            (action_id, session_id, case_id, action_type, host, dumps(safe_details), actor, now_ts()),
        )
        self.db.execute("UPDATE research_persona_sessions_143 SET consumed_actions=consumed_actions+1,updated_at=? WHERE session_id=? AND case_id=?", (now_ts(), session_id, case_id))
        self._event(case_id=case_id, event_type="persona_session_action_recorded", object_type="persona_session", object_id=session_id, actor=actor, payload={"action_id": action_id, "action_type": action_type, "destination_host": host, "manual_action": True})
        return {"action_id": action_id, "session": self.get_session(case_id=case_id, session_id=session_id)}

    def _remove_profile(self, relpath: str, session_id: str) -> dict[str, Any]:
        if not relpath:
            return {"profile_removed": True, "profile_present": False}
        profile = (self.session_root / relpath).resolve()
        session_dir = profile.parent
        if self.session_root not in session_dir.parents or session_id not in session_dir.parts:
            raise PermissionError("Sitzungsprofil liegt außerhalb des erlaubten Tresors")
        if not session_dir.exists():
            return {"profile_removed": True, "profile_present": False}
        tombstone = self.session_root / f".deleting_session143_{session_id}_{secrets.token_hex(4)}"
        try:
            session_dir.rename(tombstone)
            shutil.rmtree(tombstone)
            return {"profile_removed": True, "profile_present": True}
        except OSError as exc:
            return {"profile_removed": False, "profile_present": True, "error": str(exc)[:300], "tombstone": tombstone.name if tombstone.exists() else ""}

    def close_session(self, *, case_id: str, session_id: str, reason: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._authorize(actor, case_id, "persona.session.close")
        session = self.get_session(case_id=case_id, session_id=session_id)
        if session["status"] not in {"active", "approved", "expired", "blocked"}:
            raise ValueError("Sitzung ist bereits geschlossen oder widerrufen")
        if confirmation.strip() != SESSION_CLOSE:
            raise PermissionError(f"Schließphrase {SESSION_CLOSE} fehlt")
        reason = _clean(reason, 1200)
        if len(reason) < 5:
            raise ValueError("Schließgrund ist erforderlich")
        removal = self._remove_profile(str(session.get("profile_relpath") or ""), session_id)
        status = "closed" if removal.get("profile_removed") else "revoked"
        self.db.execute("UPDATE research_persona_sessions_143 SET status=?,closed_at=?,close_reason=?,updated_at=? WHERE session_id=? AND case_id=?", (status, now_ts(), reason, now_ts(), session_id, case_id))
        self._event(case_id=case_id, event_type="persona_session_closed", object_type="persona_session", object_id=session_id, actor=actor, payload={"status": status, **removal})
        return {"session": self.get_session(case_id=case_id, session_id=session_id), **removal}

    def emergency_revoke(self, *, case_id: str, session_id: str, reason: str, actor: str) -> dict[str, Any]:
        self._authorize(actor, case_id, "security.review")
        session = self.get_session(case_id=case_id, session_id=session_id)
        removal = self._remove_profile(str(session.get("profile_relpath") or ""), session_id)
        self.db.execute("UPDATE research_persona_sessions_143 SET status='revoked',closed_at=?,close_reason=?,updated_at=? WHERE session_id=? AND case_id=?", (now_ts(), _clean(reason, 1200) or "Emergency revoke", now_ts(), session_id, case_id))
        self._event(case_id=case_id, event_type="persona_session_revoked", object_type="persona_session", object_id=session_id, actor=actor, payload={"reason": _clean(reason, 600), **removal, "browser_process_termination_claim": False})
        return {"session": self.get_session(case_id=case_id, session_id=session_id), **removal, "warning": "EagleEye kann ohne explizite Prozesskontrolle nicht garantieren, dass ein bereits laufender Firefox-Prozess beendet wurde."}

    # ---------- access review / controlled collaboration ----------
    def attest_case_access(self, *, case_id: str, assignment_id: str, decision: str, reason: str, confirmation: str, actor: str) -> dict[str, Any]:
        self._authorize(actor, case_id, "security.review")
        assignment = self.db.one("SELECT * FROM governance_case_assignments_132 WHERE case_id=? AND assignment_id=?", (case_id, assignment_id))
        if not assignment:
            raise KeyError("Fallzuweisung nicht gefunden")
        decision = _clean(decision, 20).casefold()
        if decision not in {"retain", "revoke", "needs_review"}:
            raise ValueError("Ungültige Zugriffsentscheidung")
        if confirmation.strip() != ACCESS_REVIEW_CONFIRMATION:
            raise PermissionError(f"Bestätigung {ACCESS_REVIEW_CONFIRMATION} fehlt")
        reason = _clean(reason, 1500)
        if len(reason) < 10:
            raise ValueError("Begründung der Zugriffsprüfung ist zu kurz")
        if decision == "revoke" and assignment.get("granted_by", "").casefold() == actor.casefold():
            # A reviewer may revoke their own historical grant only if they still
            # hold security.review; this remains explicit and audited.
            pass
        attestation_id = new_id("access143")
        self.db.execute("INSERT INTO case_access_attestations_143(attestation_id,case_id,assignment_id,decision,reason,reviewed_by,created_at) VALUES(?,?,?,?,?,?,?)", (attestation_id, case_id, assignment_id, decision, reason, actor, now_ts()))
        if decision == "revoke" and bool(assignment.get("active")):
            self.governance.revoke_case_assignment(assignment_id=assignment_id, actor=actor)
        self._event(case_id=case_id, event_type="case_access_attested", object_type="case_access", object_id=assignment_id, actor=actor, payload={"decision": decision, "reason": reason})
        return self.db.one("SELECT * FROM case_access_attestations_143 WHERE attestation_id=?", (attestation_id,)) or {}

    # ---------- presentation ----------
    def list_personas(self, case_id: str) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM research_personas_143 WHERE case_id=? ORDER BY updated_at DESC", (case_id,))

    def list_accounts(self, case_id: str) -> list[dict[str, Any]]:
        return self.db.all("SELECT a.account_id,a.persona_id,a.platform,a.account_label,a.username_alias,a.email_alias,a.account_origin,a.secret_present,a.terms_reviewed,a.status,a.expires_at,a.created_by,a.created_at,p.label AS persona_label FROM persona_accounts_143 a JOIN research_personas_143 p ON p.persona_id=a.persona_id WHERE a.case_id=? ORDER BY a.updated_at DESC", (case_id,))

    def list_egress(self, case_id: str) -> list[dict[str, Any]]:
        return self.db.all("SELECT egress_id,case_id,label,mode,proxy_host,proxy_port,remote_dns,requires_auth,secret_present,status,risk_note,requested_by,approved_by,approval_reason,expires_at,created_at,updated_at FROM network_egress_profiles_143 WHERE case_id=? ORDER BY updated_at DESC", (case_id,))

    def list_sessions(self, case_id: str) -> list[dict[str, Any]]:
        return self.db.all("""SELECT s.*,p.label AS persona_label,e.label AS egress_label,e.mode AS egress_mode,a.account_label FROM research_persona_sessions_143 s JOIN research_personas_143 p ON p.persona_id=s.persona_id JOIN network_egress_profiles_143 e ON e.egress_id=s.egress_id LEFT JOIN persona_accounts_143 a ON a.account_id=s.account_id WHERE s.case_id=? ORDER BY s.updated_at DESC""", (case_id,))

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        where = " WHERE case_id=?" if case_id else ""
        params = (case_id,) if case_id else ()
        def count(table: str, extra: str = "", extra_params: tuple[Any, ...] = ()) -> int:
            clause = where
            joined = params
            if extra:
                clause += (" AND " if clause else " WHERE ") + extra
                joined += extra_params
            row = self.db.one(f"SELECT COUNT(*) AS c FROM {table}{clause}", joined) or {}
            return int(row.get("c") or 0)
        data: dict[str, Any] = {
            "build": self.BUILD,
            "status": {
                "automatic_account_creation": 0,
                "automatic_login": 0,
                "anti_bot_bypass": 0,
                "automatic_external_actions": 0,
                "untraceability_guarantee": False,
                "temporary_isolated_profiles": True,
                "manual_alias_accounts_only": True,
                "four_eyes_for_persona_and_egress": True,
                "loopback_server_only": True,
            },
            "metrics": {
                "personas": count("research_personas_143"),
                "approved_personas": count("research_personas_143", "status='approved'"),
                "accounts": count("persona_accounts_143"),
                "egress_profiles": count("network_egress_profiles_143"),
                "active_sessions": count("research_persona_sessions_143", "status='active'"),
                "pending_sessions": count("research_persona_sessions_143", "status IN ('draft','pending_approval','approved','blocked')"),
            },
        }
        if case_id:
            self._case(case_id)
            data.update({
                "personas": self.list_personas(case_id),
                "accounts": self.list_accounts(case_id),
                "egress_profiles": self.list_egress(case_id),
                "sessions": self.list_sessions(case_id),
                "assignments": self.governance.case_assignments(case_id),
                "access_attestations": self.db.all("SELECT * FROM case_access_attestations_143 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
                "events": self.db.all("SELECT event_type,object_type,object_id,payload_json,created_by,created_at FROM build143_events WHERE case_id=? ORDER BY sequence DESC LIMIT 80", (case_id,)),
            })
        return data
