from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

from eagleeye_pro.core.database import dumps, new_id, now_ts

USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,32}$")
COMMON_PASSWORDS = {
    "password", "password123", "password1234", "passwort", "passwort123", "passwort1234",
    "123456789012345", "qwertzuiopasdfg", "qwertyuiopasdfg", "letmeinletmeinletmein",
    "correcthorsebatterystaple", "eagleeye123456789", "adminadminadminadmin",
}
GLOBAL_ROLES = {
    "system_administrator": {"*"},
    "security_administrator": {"security.*", "user.read", "session.*", "audit.read", "case.read"},
    "connector_administrator": {"connector.*", "secret.manage", "case.read"},
    "auditor": {"case.read", "audit.read", "report.read", "evidence.read", "security.read"},
    "investigator": {"case.create", "case.read", "case.update", "research.*", "intake.*", "evidence.*", "identity.create", "report.write", "ai.*", "persona.*"},
    "reviewer": {"case.read", "intake.review", "evidence.review", "identity.review", "report.review", "audit.read", "security.review"},
    "read_only": {"case.read", "report.read", "evidence.read"},
}
ROLE_TO_GOVERNANCE = {
    "system_administrator": "administrator",
    "security_administrator": "evidence_reviewer",
    "connector_administrator": "lead_investigator",
    "auditor": "auditor",
    "investigator": "research_analyst",
    "reviewer": "evidence_reviewer",
    "read_only": "auditor",
}
CASE_ROLE_TO_GOVERNANCE = {
    "case_lead": "lead_investigator",
    "investigator": "research_analyst",
    "analyst": "research_analyst",
    "reviewer": "evidence_reviewer",
    "report_author": "research_analyst",
    "read_only": "auditor",
}


class AuthenticationError(ValueError):
    pass


class AuthorizationError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class IssuedSession:
    token: str
    csrf_token: str
    session_id: str
    max_age: int
    absolute_expires_epoch: int


class Build146IdentityAccessService:
    """Build 146 local identity, password, session and authorization boundary.

    Passwords are Argon2id hashed after a local HMAC pepper transformation.
    Only token and CSRF hashes are persisted. The service mirrors users and case
    memberships into the Build-132 governance layer so all historical route and
    four-eyes checks keep enforcing the same actor identity.
    """

    BUILD = "146.0"
    POLICY_VERSION = "146.0"
    COOKIE_NAME = "ee_auth_session"
    MIN_PASSWORD = 15
    MAX_PASSWORD = 128
    MAX_FAILED = 10
    STEP_UP_ACTIONS = {
        "report.release", "phase4.seal", "persona.session.start",
        "backup.restore", "secret.manage", "security.lockdown",
        "user.manage", "session.revoke", "case.delete",
    }

    def __init__(self, db: Any, audit: Any, *, governance: Any, protection: Any, cases: Any, clock: Any | None = None) -> None:
        self.db = db
        self.audit = audit
        self.governance = governance
        self.protection = protection
        self.cases = cases
        self.clock = clock or time.time
        self.hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16, type=Type.ID)
        self._dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))
        self._ensure_pepper()
        self._expire_sessions()

    @staticmethod
    def normalize_username(username: str) -> str:
        value = unicodedata.normalize("NFKC", str(username or "")).strip().casefold()
        if not USERNAME_RE.fullmatch(value):
            raise AuthenticationError("Benutzername muss 3–32 Zeichen lang sein und darf nur a–z, 0–9, Punkt, Unterstrich und Bindestrich enthalten")
        return value

    @staticmethod
    def _hash_text(value: str) -> str:
        return hashlib.sha256(str(value or "").encode("utf-8", errors="replace")).hexdigest()

    def _settings(self) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM auth_settings_146 WHERE settings_id='global'") or {}
        for key in ("bootstrap_complete", "bind_client_fingerprint", "secure_cookie_required"):
            row[key] = bool(row.get(key))
        return row

    def status(self) -> dict[str, Any]:
        settings = self._settings()
        users = int((self.db.one("SELECT COUNT(*) AS n FROM auth_users_146") or {}).get("n") or 0)
        active_sessions = int((self.db.one("SELECT COUNT(*) AS n FROM auth_sessions_146 WHERE revoked=0 AND idle_expires_epoch>? AND absolute_expires_epoch>?", (int(self.clock()), int(self.clock()))) or {}).get("n") or 0)
        return {
            "build": self.BUILD,
            "schema": str((self.db.one("SELECT value FROM meta WHERE key='schema_version'") or {}).get("value") or ""),
            "bootstrap_required": users == 0 or not settings.get("bootstrap_complete"),
            "users": users,
            "active_sessions": active_sessions,
            "password_algorithm": "argon2id",
            "password_parameters": {"time_cost": self.hasher.time_cost, "memory_cost_kib": self.hasher.memory_cost, "parallelism": self.hasher.parallelism, "hash_len": self.hasher.hash_len},
            "session_cookie": self.COOKIE_NAME,
            "webauthn_available": self.webauthn_available(),
            "external_identity_provider": False,
            "anonymous_case_access": False,
        }

    def bootstrap_required(self) -> bool:
        return bool(self.status()["bootstrap_required"])

    def _ensure_pepper(self) -> None:
        if not self.protection.get_secret("auth146.password_pepper.v1"):
            self.protection.set_secret("auth146.password_pepper.v1", secrets.token_urlsafe(64))

    def _peppered(self, password: str, version: int = 1) -> str:
        secret = self.protection.get_secret(f"auth146.password_pepper.v{int(version)}")
        if not secret:
            raise AuthenticationError("Passwort-Pepper ist nicht verfügbar")
        return hmac.new(secret.encode("utf-8"), str(password).encode("utf-8"), hashlib.sha256).hexdigest()

    def validate_password(self, password: str, *, username: str = "", display_name: str = "") -> None:
        value = str(password or "")
        settings = self._settings()
        min_len = int(settings.get("password_min_length") or self.MIN_PASSWORD)
        max_len = int(settings.get("password_max_length") or self.MAX_PASSWORD)
        if len(value) < min_len:
            raise AuthenticationError(f"Passwort muss mindestens {min_len} Zeichen lang sein")
        if len(value) > max_len:
            raise AuthenticationError(f"Passwort darf höchstens {max_len} Zeichen lang sein")
        folded = unicodedata.normalize("NFKC", value).casefold().strip()
        compact = re.sub(r"\s+", "", folded)
        if folded in COMMON_PASSWORDS or compact in COMMON_PASSWORDS:
            raise AuthenticationError("Dieses Passwort ist zu häufig oder vorhersehbar")
        uname = str(username or "").casefold()
        dname = re.sub(r"\s+", "", str(display_name or "").casefold())
        if uname and (uname in folded or folded in uname):
            raise AuthenticationError("Passwort darf den Benutzernamen nicht enthalten")
        if len(dname) >= 4 and dname in compact:
            raise AuthenticationError("Passwort darf den Anzeigenamen nicht enthalten")

    def _password_hash(self, password: str, pepper_version: int = 1) -> str:
        return self.hasher.hash(self._peppered(password, pepper_version))

    def _verify_password(self, encoded: str, password: str, pepper_version: int = 1) -> bool:
        try:
            return bool(self.hasher.verify(encoded, self._peppered(password, pepper_version)))
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def _event(self, event_type: str, *, user_id: str = "", username: str = "", session_id: str = "", case_id: str = "", severity: str = "info", details: dict[str, Any] | None = None) -> None:
        previous = self.db.one("SELECT event_hash FROM auth_security_events_146 ORDER BY sequence DESC LIMIT 1")
        previous_hash = str((previous or {}).get("event_hash") or "GENESIS")
        safe = dict(details or {})
        for key in list(safe):
            if any(marker in key.casefold() for marker in ("password", "secret", "token", "credential", "recovery_code", "csrf")):
                safe[key] = "[redacted]"
        payload = {
            "event_type": event_type, "user_id": user_id, "username_hash": self._hash_text(username) if username else "",
            "session_id": session_id, "case_id": case_id, "severity": severity, "details": safe,
            "previous_hash": previous_hash, "created_at": now_ts(),
        }
        event_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        self.db.execute(
            "INSERT INTO auth_security_events_146(event_id,event_type,user_id,username_hash,session_id,case_id,severity,details_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (new_id("auth146evt"), event_type, user_id or None, payload["username_hash"], session_id, case_id, severity, dumps(safe), previous_hash, event_hash, payload["created_at"]),
        )
        self.audit.log("auth", "identity_access_146", event_type, case_id or None, {"severity": severity, **safe})

    def _sync_governance_user(self, *, user_id: str, username: str, display_name: str, global_role: str, active: bool = True) -> None:
        role_key = ROLE_TO_GOVERNANCE.get(global_role, "research_analyst")
        now = now_ts()
        row = self.db.one("SELECT * FROM governance_users_132 WHERE username=? COLLATE NOCASE", (username,))
        if row:
            self.db.execute("UPDATE governance_users_132 SET display_name=?,role_key=?,active=?,updated_at=? WHERE username=? COLLATE NOCASE", (display_name, role_key, int(active), now, username))
        else:
            self.db.execute(
                "INSERT INTO governance_users_132(user_id,username,display_name,role_key,password_hash,active,created_by,created_at,updated_at) VALUES(?,?,?,?, '',?,?,?,?)",
                (f"gov146_{user_id}", username, display_name, role_key, int(active), "build146", now, now),
            )

    def create_initial_admin(self, *, username: str, display_name: str, password: str) -> dict[str, Any]:
        with self.db.transaction(immediate=True):
            if int((self.db.one("SELECT COUNT(*) AS n FROM auth_users_146") or {}).get("n") or 0):
                raise AuthenticationError("Bootstrap wurde bereits abgeschlossen")
            uname = self.normalize_username(username)
            dname = str(display_name or "").strip()
            if len(dname) < 2 or len(dname) > 120:
                raise AuthenticationError("Anzeigename muss 2–120 Zeichen lang sein")
            self.validate_password(password, username=uname, display_name=dname)
            user_id = new_id("authuser146")
            stamp = now_ts()
            password_hash = self._password_hash(password)
            self.db.execute(
                "INSERT INTO auth_users_146(user_id,username,username_normalized,display_name,global_role,active,created_by,created_at,updated_at,password_changed_at) VALUES(?,?,?,?, 'system_administrator',1,'bootstrap',?,?,?)",
                (user_id, uname, uname, dname, stamp, stamp, stamp),
            )
            self.db.execute(
                "INSERT INTO password_credentials_146(credential_id,user_id,password_hash,hash_algorithm,pepper_version,parameters_json,created_at,updated_at) VALUES(?,?,?,'argon2id',1,?,?,?)",
                (new_id("pwd146"), user_id, password_hash, dumps({"time_cost": self.hasher.time_cost, "memory_cost": self.hasher.memory_cost, "parallelism": self.hasher.parallelism, "hash_len": self.hasher.hash_len}), stamp, stamp),
            )
            self.db.execute("UPDATE auth_settings_146 SET bootstrap_complete=1,updated_by=?,updated_at=? WHERE settings_id='global'", (uname, stamp))
            self._sync_governance_user(user_id=user_id, username=uname, display_name=dname, global_role="system_administrator")
            for case in self.cases.list_cases():
                self.assign_case(case_id=case["case_id"], username=uname, case_role="case_lead", actor=uname, bootstrap=True)
        self._event("bootstrap_completed", user_id=user_id, username=uname, severity="warning", details={"global_role": "system_administrator", "legacy_cases_assigned": len(self.cases.list_cases())})
        return self.public_user(uname)

    def public_user(self, username: str) -> dict[str, Any]:
        uname = self.normalize_username(username)
        row = self.db.one("SELECT user_id,username,display_name,global_role,active,must_change_password,created_at,updated_at,last_login_at,password_changed_at FROM auth_users_146 WHERE username_normalized=?", (uname,))
        if not row:
            raise AuthenticationError("Benutzer nicht gefunden")
        row["active"] = bool(row.get("active"))
        row["must_change_password"] = bool(row.get("must_change_password"))
        return row

    def list_users(self) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT user_id,username,display_name,global_role,active,must_change_password,created_at,updated_at,last_login_at FROM auth_users_146 ORDER BY active DESC,username_normalized")
        for row in rows:
            row["active"] = bool(row.get("active")); row["must_change_password"] = bool(row.get("must_change_password"))
        return rows

    def create_user(self, *, username: str, display_name: str, global_role: str, password: str, actor: str) -> dict[str, Any]:
        self.require_global(actor, "user.manage")
        uname = self.normalize_username(username)
        dname = str(display_name or "").strip()
        if global_role not in GLOBAL_ROLES:
            raise AuthenticationError("Unbekannte globale Rolle")
        if len(dname) < 2 or len(dname) > 120:
            raise AuthenticationError("Anzeigename muss 2–120 Zeichen lang sein")
        self.validate_password(password, username=uname, display_name=dname)
        user_id = new_id("authuser146"); stamp = now_ts()
        try:
            with self.db.transaction(immediate=True):
                self.db.execute("INSERT INTO auth_users_146(user_id,username,username_normalized,display_name,global_role,active,must_change_password,created_by,created_at,updated_at,password_changed_at) VALUES(?,?,?,?,?,1,1,?,?,?,?)", (user_id, uname, uname, dname, global_role, actor, stamp, stamp, stamp))
                self.db.execute("INSERT INTO password_credentials_146(credential_id,user_id,password_hash,hash_algorithm,pepper_version,parameters_json,created_at,updated_at) VALUES(?,?,?,'argon2id',1,?,?,?)", (new_id("pwd146"), user_id, self._password_hash(password), dumps({"time_cost": self.hasher.time_cost, "memory_cost": self.hasher.memory_cost, "parallelism": self.hasher.parallelism}), stamp, stamp))
                self._sync_governance_user(user_id=user_id, username=uname, display_name=dname, global_role=global_role)
        except Exception as exc:
            raise AuthenticationError("Benutzername ist bereits vergeben") from exc
        self._event("user_created", user_id=user_id, username=uname, details={"global_role": global_role, "created_by": actor})
        return self.public_user(uname)


    def update_user(
        self, *, username: str, actor: str, global_role: str | None = None,
        active: bool | None = None, must_change_password: bool | None = None,
    ) -> dict[str, Any]:
        self.require_global(actor, "user.manage")
        target = self.public_user(username)
        actor_name = self.normalize_username(actor)
        if target["username"] == actor_name and (active is False or (global_role and global_role != target["global_role"])):
            raise AuthorizationError("Die eigene Administratorrolle oder Aktivierung darf nicht in derselben Sitzung herabgesetzt werden")
        new_role = global_role or target["global_role"]
        if new_role not in GLOBAL_ROLES:
            raise AuthorizationError("Unbekannte globale Rolle")
        new_active = target["active"] if active is None else bool(active)
        if target["global_role"] == "system_administrator" and (new_role != "system_administrator" or not new_active):
            remaining = int((self.db.one(
                "SELECT COUNT(*) AS n FROM auth_users_146 WHERE global_role='system_administrator' AND active=1 AND user_id<>?",
                (target["user_id"],),
            ) or {}).get("n") or 0)
            if remaining < 1:
                raise AuthorizationError("Das letzte aktive Systemadministratorkonto darf nicht deaktiviert oder herabgestuft werden")
        change_required = target["must_change_password"] if must_change_password is None else bool(must_change_password)
        with self.db.transaction(immediate=True):
            self.db.execute(
                "UPDATE auth_users_146 SET global_role=?,active=?,must_change_password=?,session_generation=session_generation+1,updated_at=? WHERE user_id=?",
                (new_role, int(new_active), int(change_required), now_ts(), target["user_id"]),
            )
            self._sync_governance_user(
                user_id=target["user_id"], username=target["username"], display_name=target["display_name"],
                global_role=new_role, active=new_active,
            )
            self.revoke_user_sessions(user_id=target["user_id"], reason="user_security_state_changed", actor=actor)
        self._event(
            "user_security_state_changed", user_id=target["user_id"], username=target["username"], severity="warning",
            details={"global_role": new_role, "active": new_active, "must_change_password": change_required, "actor": actor},
        )
        return self.public_user(target["username"])

    def revoke_case_membership(self, *, case_id: str, username: str, case_role: str, actor: str, reason: str) -> dict[str, Any]:
        self.require_global(actor, "user.manage")
        user = self.public_user(username)
        membership = self.db.one(
            "SELECT * FROM auth_case_memberships_146 WHERE case_id=? AND user_id=? AND case_role=? AND active=1",
            (case_id, user["user_id"], case_role),
        )
        if not membership:
            raise AuthorizationError("Aktive Fallmitgliedschaft wurde nicht gefunden")
        if len(str(reason or "").strip()) < 8:
            raise AuthorizationError("Der Entzugsgrund muss nachvollziehbar dokumentiert werden")
        stamp = now_ts()
        with self.db.transaction(immediate=True):
            self.db.execute(
                "UPDATE auth_case_memberships_146 SET active=0,revoked_by=?,revoked_at=?,notes=? WHERE membership_id=?",
                (actor, stamp, str(reason)[:1000], membership["membership_id"]),
            )
            gov_role = CASE_ROLE_TO_GOVERNANCE.get(case_role)
            gov_user = self.db.one("SELECT user_id FROM governance_users_132 WHERE username=? COLLATE NOCASE", (user["username"],))
            if gov_user and gov_role:
                self.db.execute(
                    "UPDATE governance_case_assignments_132 SET active=0,revoked_by=?,revoked_at=? WHERE case_id=? AND user_id=? AND role_key=?",
                    (actor, stamp, case_id, gov_user["user_id"], gov_role),
                )
        self._event(
            "case_membership_revoked", user_id=user["user_id"], username=user["username"], case_id=case_id,
            severity="warning", details={"case_role": case_role, "actor": actor, "reason": reason},
        )
        return self.db.one("SELECT * FROM auth_case_memberships_146 WHERE membership_id=?", (membership["membership_id"],)) or {}

    def revoke_session_by_id(self, *, session_id: str, actor: str, reason: str = "administrator_revoked") -> None:
        self.require_global(actor, "session.revoke")
        row = self.db.one("SELECT s.*,u.username FROM auth_sessions_146 s JOIN auth_users_146 u ON u.user_id=s.user_id WHERE s.session_id=?", (session_id,))
        if not row:
            raise AuthenticationError("Sitzung wurde nicht gefunden")
        self.db.execute(
            "UPDATE auth_sessions_146 SET revoked=1,revoked_reason=?,revoked_by=?,revoked_at=? WHERE session_id=?",
            (str(reason)[:200], actor, now_ts(), session_id),
        )
        self._event("session_revoked", user_id=row["user_id"], username=row["username"], session_id=session_id, severity="warning", details={"reason": reason, "actor": actor})

    def list_case_memberships(self, case_id: str = "") -> list[dict[str, Any]]:
        if case_id:
            return self.db.all(
                "SELECT m.membership_id,m.case_id,u.username,u.display_name,m.case_role,m.active,m.granted_by,m.granted_at,m.revoked_by,m.revoked_at,m.notes FROM auth_case_memberships_146 m JOIN auth_users_146 u ON u.user_id=m.user_id WHERE m.case_id=? ORDER BY m.active DESC,u.username,m.case_role",
                (case_id,),
            )
        return self.db.all(
            "SELECT m.membership_id,m.case_id,u.username,u.display_name,m.case_role,m.active,m.granted_by,m.granted_at,m.revoked_by,m.revoked_at,m.notes FROM auth_case_memberships_146 m JOIN auth_users_146 u ON u.user_id=m.user_id ORDER BY m.active DESC,m.case_id,u.username,m.case_role LIMIT 500"
        )

    def _attempt_counts(self, username_hash: str, client_hash: str) -> tuple[int, int]:
        since = int(self.clock()) - 900
        user_count = int((self.db.one("SELECT COUNT(*) AS n FROM login_attempts_146 WHERE username_hash=? AND success=0 AND created_epoch>=?", (username_hash, since)) or {}).get("n") or 0)
        client_count = int((self.db.one("SELECT COUNT(*) AS n FROM login_attempts_146 WHERE client_hash=? AND success=0 AND created_epoch>=?", (client_hash, since)) or {}).get("n") or 0)
        return user_count, client_count

    def _record_attempt(self, *, username_hash: str, client_hash: str, success: bool, blocked: bool, reason: str, elapsed_ms: int) -> None:
        self.db.execute("INSERT INTO login_attempts_146(attempt_id,username_hash,client_hash,success,blocked,reason_code,elapsed_ms,created_epoch,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (new_id("login146"), username_hash, client_hash, int(success), int(blocked), reason, max(0, int(elapsed_ms)), int(self.clock()), now_ts()))

    def authenticate(self, *, username: str, password: str, client_fingerprint: str = "") -> IssuedSession | None:
        started = time.perf_counter()
        raw_username = unicodedata.normalize("NFKC", str(username or "")).strip().casefold()[:128]
        username_hash = self._hash_text(raw_username); client_hash = self._hash_text(client_fingerprint or "unknown")
        user_attempts, client_attempts = self._attempt_counts(username_hash, client_hash)
        if user_attempts >= 10 or client_attempts >= 30:
            self._record_attempt(username_hash=username_hash, client_hash=client_hash, success=False, blocked=True, reason="rate_limited", elapsed_ms=int((time.perf_counter()-started)*1000))
            self._event("login_rate_limited", username=raw_username, severity="warning", details={"user_window_attempts": user_attempts, "client_window_attempts": client_attempts})
            return None
        row = self.db.one("SELECT u.*,c.password_hash,c.pepper_version FROM auth_users_146 u JOIN password_credentials_146 c ON c.user_id=u.user_id WHERE u.username_normalized=?", (raw_username,))
        now_epoch = int(self.clock())
        blocked = bool(row and int(row.get("lock_until_epoch") or 0) > now_epoch)
        if row and not blocked and bool(row.get("active")):
            ok = self._verify_password(str(row.get("password_hash") or ""), password, int(row.get("pepper_version") or 1))
        else:
            try:
                self.hasher.verify(self._dummy_hash, self._peppered(password))
            except Exception:
                pass
            ok = False
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        if not ok:
            if row:
                failures = int(row.get("failed_attempts") or 0) + 1
                delay = 0 if failures < 5 else min(900, 2 ** min(failures, 9))
                self.db.execute("UPDATE auth_users_146 SET failed_attempts=?,lock_until_epoch=?,updated_at=? WHERE user_id=?", (failures, now_epoch + delay if delay else 0, now_ts(), row["user_id"]))
            self._record_attempt(username_hash=username_hash, client_hash=client_hash, success=False, blocked=blocked, reason="invalid_credentials", elapsed_ms=elapsed_ms)
            self._event("login_failed", user_id=str((row or {}).get("user_id") or ""), username=raw_username, severity="warning", details={"blocked": blocked})
            return None
        if self.hasher.check_needs_rehash(str(row["password_hash"])):
            self.db.execute("UPDATE password_credentials_146 SET password_hash=?,parameters_json=?,updated_at=? WHERE user_id=?", (self._password_hash(password, int(row.get("pepper_version") or 1)), dumps({"time_cost": self.hasher.time_cost, "memory_cost": self.hasher.memory_cost, "parallelism": self.hasher.parallelism}), now_ts(), row["user_id"]))
        self.db.execute("UPDATE auth_users_146 SET failed_attempts=0,lock_until_epoch=0,last_login_at=?,updated_at=? WHERE user_id=?", (now_ts(), now_ts(), row["user_id"]))
        self._record_attempt(username_hash=username_hash, client_hash=client_hash, success=True, blocked=False, reason="success", elapsed_ms=elapsed_ms)
        issued = self.issue_session(user_id=row["user_id"], client_fingerprint=client_fingerprint)
        self._event("login_succeeded", user_id=row["user_id"], username=row["username"], session_id=issued.session_id, details={"assurance_level": "password"})
        return issued

    def issue_session(self, *, user_id: str, client_fingerprint: str = "") -> IssuedSession:
        user = self.db.one("SELECT * FROM auth_users_146 WHERE user_id=? AND active=1", (user_id,))
        if not user:
            raise AuthenticationError("Aktives Benutzerkonto fehlt")
        settings = self._settings(); now = int(self.clock())
        idle_seconds = int(settings.get("session_idle_minutes") or 30) * 60
        absolute_seconds = int(settings.get("session_absolute_hours") or 12) * 3600
        token = secrets.token_urlsafe(48); csrf_token = secrets.token_urlsafe(32); session_id = new_id("session146")
        bound = str(client_fingerprint or "") if settings.get("bind_client_fingerprint") else ""
        self.db.execute(
            "INSERT INTO auth_sessions_146(session_id,token_hash,csrf_hash,user_id,session_generation,assurance_level,client_fingerprint,created_epoch,last_seen_epoch,idle_expires_epoch,absolute_expires_epoch,last_rotated_at) VALUES(?,?,?,?,?,'password',?,?,?,?,?,?)",
            (session_id, self._hash_text(token), self._hash_text(csrf_token), user_id, int(user.get("session_generation") or 1), bound, now, now, now + idle_seconds, now + absolute_seconds, now_ts()),
        )
        return IssuedSession(token, csrf_token, session_id, absolute_seconds, now + absolute_seconds)

    def _expire_sessions(self) -> int:
        now = int(self.clock())
        cur = self.db.execute("UPDATE auth_sessions_146 SET revoked=1,revoked_reason='expired',revoked_by='system',revoked_at=? WHERE revoked=0 AND (idle_expires_epoch<=? OR absolute_expires_epoch<=?)", (now_ts(), now, now))
        return int(cur.rowcount or 0)

    def validate_session(self, token: str, *, client_fingerprint: str = "", touch: bool = True) -> dict[str, Any] | None:
        if not token:
            return None
        now = int(self.clock()); digest = self._hash_text(token)
        row = self.db.one("SELECT s.*,u.username,u.display_name,u.global_role,u.active,u.must_change_password,u.session_generation AS user_generation FROM auth_sessions_146 s JOIN auth_users_146 u ON u.user_id=s.user_id WHERE s.token_hash=?", (digest,))
        if not row or row.get("revoked") or not row.get("active"):
            return None
        if int(row.get("idle_expires_epoch") or 0) <= now or int(row.get("absolute_expires_epoch") or 0) <= now:
            self.revoke_session(token=token, reason="expired", actor="system")
            return None
        if int(row.get("session_generation") or 0) != int(row.get("user_generation") or 0):
            self.revoke_session(token=token, reason="generation_changed", actor="system")
            return None
        bound = str(row.get("client_fingerprint") or "")
        if bound and not hmac.compare_digest(bound, str(client_fingerprint or "")):
            self._event("session_binding_failed", user_id=row["user_id"], username=row["username"], session_id=row["session_id"], severity="warning")
            return None
        if touch and now - int(row.get("last_seen_epoch") or 0) >= 30:
            idle_seconds = int(self._settings().get("session_idle_minutes") or 30) * 60
            new_idle = min(now + idle_seconds, int(row["absolute_expires_epoch"]))
            self.db.execute("UPDATE auth_sessions_146 SET last_seen_epoch=?,idle_expires_epoch=? WHERE session_id=?", (now, new_idle, row["session_id"]))
            row["last_seen_epoch"] = now; row["idle_expires_epoch"] = new_idle
        return {
            "user_id": row["user_id"], "username": row["username"], "display_name": row["display_name"],
            "global_role": row["global_role"], "role_key": ROLE_TO_GOVERNANCE.get(row["global_role"], "research_analyst"),
            "session_id": row["session_id"], "assurance_level": row["assurance_level"],
            "must_change_password": bool(row.get("must_change_password")), "absolute_expires_epoch": int(row["absolute_expires_epoch"]),
        }

    def csrf_token_valid(self, *, session_token: str, submitted: str) -> bool:
        row = self.db.one("SELECT csrf_hash FROM auth_sessions_146 WHERE token_hash=? AND revoked=0", (self._hash_text(session_token),)) if session_token else None
        return bool(row and submitted and hmac.compare_digest(str(row["csrf_hash"]), self._hash_text(submitted)))

    def csrf_for_session(self, session_token: str) -> str:
        # The raw CSRF token is not persisted. Rotate session to obtain a new token.
        # Web integration stores it in a separate Strict/HttpOnly cookie and mirrors
        # it into forms server-side after validation of the session cookie.
        raise AuthenticationError("Raw CSRF token is available only when a session is issued")

    def revoke_session(self, *, token: str, reason: str, actor: str) -> None:
        digest = self._hash_text(token)
        row = self.db.one("SELECT * FROM auth_sessions_146 WHERE token_hash=?", (digest,))
        if row and not row.get("revoked"):
            self.db.execute("UPDATE auth_sessions_146 SET revoked=1,revoked_reason=?,revoked_by=?,revoked_at=? WHERE session_id=?", (str(reason)[:120], actor, now_ts(), row["session_id"]))
            self._event("session_revoked", user_id=row["user_id"], session_id=row["session_id"], severity="warning", details={"reason": reason, "revoked_by": actor})

    def revoke_user_sessions(self, *, user_id: str, reason: str, actor: str, except_session_id: str = "") -> int:
        sql = "UPDATE auth_sessions_146 SET revoked=1,revoked_reason=?,revoked_by=?,revoked_at=? WHERE user_id=? AND revoked=0"
        params: list[Any] = [reason, actor, now_ts(), user_id]
        if except_session_id:
            sql += " AND session_id!=?"; params.append(except_session_id)
        cur = self.db.execute(sql, params)
        return int(cur.rowcount or 0)

    def change_password(self, *, username: str, current_password: str, new_password: str, actor: str, current_session_id: str = "") -> dict[str, Any]:
        uname = self.normalize_username(username)
        row = self.db.one("SELECT u.*,c.password_hash,c.pepper_version FROM auth_users_146 u JOIN password_credentials_146 c ON c.user_id=u.user_id WHERE u.username_normalized=?", (uname,))
        if not row:
            raise AuthenticationError("Anmeldung nicht möglich")
        if actor.casefold() != uname:
            self.require_global(actor, "user.manage")
        elif not self._verify_password(row["password_hash"], current_password, int(row.get("pepper_version") or 1)):
            raise AuthenticationError("Anmeldung nicht möglich")
        self.validate_password(new_password, username=uname, display_name=row["display_name"])
        stamp = now_ts()
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE password_credentials_146 SET password_hash=?,hash_algorithm='argon2id',pepper_version=1,parameters_json=?,updated_at=? WHERE user_id=?", (self._password_hash(new_password), dumps({"time_cost": self.hasher.time_cost, "memory_cost": self.hasher.memory_cost, "parallelism": self.hasher.parallelism}), stamp, row["user_id"]))
            self.db.execute("UPDATE auth_users_146 SET session_generation=session_generation+1,must_change_password=0,password_changed_at=?,updated_at=? WHERE user_id=?", (stamp, stamp, row["user_id"]))
            self.revoke_user_sessions(user_id=row["user_id"], reason="password_changed", actor=actor)
        self._event("password_changed", user_id=row["user_id"], username=uname, severity="warning", details={"actor": actor})
        return self.public_user(uname)

    def generate_recovery_codes(self, *, username: str, actor: str, count: int = 10) -> list[str]:
        uname = self.normalize_username(username); user = self.public_user(uname)
        if actor.casefold() != uname:
            self.require_global(actor, "user.manage")
        count = max(5, min(int(count), 20)); codes = [f"EE-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}" for _ in range(count)]
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE recovery_codes_146 SET status='revoked' WHERE user_id=? AND status='active'", (user["user_id"],))
            for code in codes:
                self.db.execute("INSERT INTO recovery_codes_146(recovery_id,user_id,code_hash,status,created_at) VALUES(?,?,?,'active',?)", (new_id("recovery146"), user["user_id"], self._hash_text(code), now_ts()))
        self._event("recovery_codes_generated", user_id=user["user_id"], username=uname, severity="warning", details={"count": count, "actor": actor})
        return codes

    def recover_account(self, *, username: str, recovery_code: str, new_password: str, client_fingerprint: str = "") -> bool:
        raw = unicodedata.normalize("NFKC", str(username or "")).strip().casefold()
        row = self.db.one("SELECT * FROM auth_users_146 WHERE username_normalized=?", (raw,))
        code_hash = self._hash_text(str(recovery_code or "").strip().upper())
        recovery = self.db.one("SELECT * FROM recovery_codes_146 WHERE code_hash=? AND status='active'", (code_hash,))
        if not row or not recovery or recovery["user_id"] != row["user_id"]:
            self._event("recovery_failed", username=raw, severity="warning")
            return False
        self.validate_password(new_password, username=raw, display_name=row["display_name"])
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE recovery_codes_146 SET status='used',used_at=?,used_client_hash=? WHERE recovery_id=?", (now_ts(), self._hash_text(client_fingerprint), recovery["recovery_id"]))
            self.db.execute("UPDATE password_credentials_146 SET password_hash=?,pepper_version=1,parameters_json=?,updated_at=? WHERE user_id=?", (self._password_hash(new_password), dumps({"time_cost": self.hasher.time_cost, "memory_cost": self.hasher.memory_cost, "parallelism": self.hasher.parallelism}), now_ts(), row["user_id"]))
            self.db.execute("UPDATE auth_users_146 SET session_generation=session_generation+1,failed_attempts=0,lock_until_epoch=0,must_change_password=0,password_changed_at=?,updated_at=? WHERE user_id=?", (now_ts(), now_ts(), row["user_id"]))
            self.revoke_user_sessions(user_id=row["user_id"], reason="account_recovery", actor="recovery")
        self._event("account_recovered", user_id=row["user_id"], username=raw, severity="critical")
        return True

    @staticmethod
    def _matches(permission: str, grants: Iterable[str]) -> bool:
        for grant in grants:
            if grant == "*" or grant == permission or (grant.endswith(".*") and permission.startswith(grant[:-1])):
                return True
        return False

    def require_global(self, username: str, permission: str) -> None:
        user = self.public_user(username)
        if not user.get("active"):
            raise AuthorizationError("Benutzerkonto ist deaktiviert")
        grants = GLOBAL_ROLES.get(user["global_role"], set())
        if not self._matches(permission, grants):
            raise AuthorizationError("Globale Berechtigung fehlt")

    def assign_case(self, *, case_id: str, username: str, case_role: str, actor: str, notes: str = "", bootstrap: bool = False) -> dict[str, Any]:
        if not bootstrap:
            self.require_global(actor, "user.manage")
        if case_role not in CASE_ROLE_TO_GOVERNANCE:
            raise AuthorizationError("Unbekannte Fallrolle")
        user = self.public_user(username); self.cases.get_case(case_id)
        membership_id = new_id("membership146"); stamp = now_ts()
        existing = self.db.one("SELECT * FROM auth_case_memberships_146 WHERE case_id=? AND user_id=? AND case_role=?", (case_id, user["user_id"], case_role))
        if existing:
            membership_id = existing["membership_id"]
            self.db.execute("UPDATE auth_case_memberships_146 SET active=1,granted_by=?,granted_at=?,revoked_by='',revoked_at='',notes=? WHERE membership_id=?", (actor, stamp, str(notes)[:1000], membership_id))
        else:
            self.db.execute("INSERT INTO auth_case_memberships_146(membership_id,case_id,user_id,case_role,active,granted_by,granted_at,notes) VALUES(?,?,?,?,1,?,?,?)", (membership_id, case_id, user["user_id"], case_role, actor, stamp, str(notes)[:1000]))
        gov_role = CASE_ROLE_TO_GOVERNANCE[case_role]
        gov_user = self.db.one("SELECT user_id FROM governance_users_132 WHERE username=? COLLATE NOCASE", (user["username"],))
        if gov_user:
            gov_existing = self.db.one("SELECT assignment_id FROM governance_case_assignments_132 WHERE case_id=? AND user_id=? AND role_key=?", (case_id, gov_user["user_id"], gov_role))
            if gov_existing:
                self.db.execute("UPDATE governance_case_assignments_132 SET active=1,granted_by=?,granted_at=?,revoked_by='',revoked_at='' WHERE assignment_id=?", (actor, stamp, gov_existing["assignment_id"]))
            else:
                self.db.execute("INSERT INTO governance_case_assignments_132(assignment_id,case_id,user_id,role_key,active,granted_by,granted_at,notes) VALUES(?,?,?,?,1,?,?,?)", (new_id("govassign146"), case_id, gov_user["user_id"], gov_role, actor, stamp, "Build 146 synchronized assignment"))
        self._event("case_membership_granted", user_id=user["user_id"], username=user["username"], case_id=case_id, details={"case_role": case_role, "actor": actor})
        return self.db.one("SELECT * FROM auth_case_memberships_146 WHERE membership_id=?", (membership_id,)) or {}

    def authorize(self, *, identity: dict[str, Any], case_id: str, permission: str, object_type: str = "", object_id: str = "", correlation_id: str = "") -> dict[str, Any]:
        user_id = str(identity.get("user_id") or ""); username = str(identity.get("username") or "")
        user = self.public_user(username); allowed = False; reason = "deny_by_default"
        global_grants = GLOBAL_ROLES.get(user["global_role"], set())
        if self._matches(permission, global_grants):
            if user["global_role"] in {"system_administrator", "security_administrator", "connector_administrator"} or not case_id:
                allowed = True; reason = "global_role"
        if case_id and not allowed:
            memberships = self.db.all("SELECT case_role FROM auth_case_memberships_146 WHERE case_id=? AND user_id=? AND active=1", (case_id, user_id))
            for membership in memberships:
                gov_role = CASE_ROLE_TO_GOVERNANCE.get(membership["case_role"])
                policy = self.db.one("SELECT permissions_json FROM governance_roles_132 WHERE role_key=?", (gov_role,)) if gov_role else None
                grants = json.loads(str((policy or {}).get("permissions_json") or "[]"))
                if self._matches(permission, grants):
                    allowed = True; reason = f"case_role:{membership['case_role']}"; break
        decision_id = new_id("access146"); corr = correlation_id or secrets.token_hex(12)
        self.db.execute("INSERT INTO access_decisions_146(decision_id,user_id,session_id,case_id,object_type,object_id,action_key,allowed,reason_code,policy_version,correlation_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (decision_id, user_id or None, str(identity.get("session_id") or ""), case_id, object_type, object_id, permission, int(allowed), reason, self.POLICY_VERSION, corr, now_ts()))
        if not allowed:
            self._event("access_denied", user_id=user_id, username=username, session_id=str(identity.get("session_id") or ""), case_id=case_id, severity="warning", details={"permission": permission, "reason": reason, "object_type": object_type, "object_id": object_id})
            raise AuthorizationError("Für diesen Fall oder Arbeitsschritt fehlt die Berechtigung")
        return {"allowed": True, "reason": reason, "decision_id": decision_id, "correlation_id": corr}

    def issue_step_up(self, *, session_token: str, password: str, action_key: str, case_id: str = "", client_fingerprint: str = "") -> dict[str, Any]:
        action_key = str(action_key or "").strip()
        if action_key not in self.STEP_UP_ACTIONS:
            raise AuthorizationError("Unbekannte oder nicht freigabefähige Step-up-Aktion")
        identity = self.validate_session(session_token, client_fingerprint=client_fingerprint, touch=False)
        if not identity:
            raise AuthenticationError("Sitzung ist abgelaufen")
        row = self.db.one("SELECT c.password_hash,c.pepper_version FROM password_credentials_146 c WHERE c.user_id=?", (identity["user_id"],))
        if not row or not self._verify_password(row["password_hash"], password, int(row.get("pepper_version") or 1)):
            self._event("step_up_failed", user_id=identity["user_id"], username=identity["username"], session_id=identity["session_id"], case_id=case_id, severity="warning", details={"action_key": action_key})
            raise AuthenticationError("Erneute Authentifizierung fehlgeschlagen")
        now = int(self.clock()); minutes = int(self._settings().get("step_up_minutes") or 15); grant_id = new_id("stepup146")
        self.db.execute("INSERT INTO step_up_grants_146(grant_id,session_id,user_id,action_key,case_id,assurance_level,created_epoch,expires_epoch) VALUES(?,?,?,?,?,'password_reauth',?,?)", (grant_id, identity["session_id"], identity["user_id"], action_key, case_id, now, now + minutes * 60))
        self._event("step_up_granted", user_id=identity["user_id"], username=identity["username"], session_id=identity["session_id"], case_id=case_id, details={"action_key": action_key, "expires_epoch": now + minutes * 60})
        return {"grant_id": grant_id, "action_key": action_key, "case_id": case_id, "expires_epoch": now + minutes * 60}

    def require_step_up(self, *, session_id: str, action_key: str, case_id: str = "", consume: bool = False) -> dict[str, Any]:
        now = int(self.clock())
        row = self.db.one("SELECT * FROM step_up_grants_146 WHERE session_id=? AND action_key=? AND case_id=? AND consumed=0 AND expires_epoch>? ORDER BY created_epoch DESC LIMIT 1", (session_id, action_key, case_id, now))
        if not row:
            raise AuthorizationError("Für diese kritische Aktion ist eine erneute Authentifizierung erforderlich")
        if consume:
            self.db.execute("UPDATE step_up_grants_146 SET consumed=1,consumed_at=? WHERE grant_id=?", (now_ts(), row["grant_id"]))
        return row

    def webauthn_available(self) -> bool:
        try:
            import webauthn  # noqa: F401
            return True
        except Exception:
            return False

    def dashboard(self) -> dict[str, Any]:
        status = self.status()
        status["recent_events"] = self.db.all("SELECT event_type,severity,case_id,created_at FROM auth_security_events_146 ORDER BY sequence DESC LIMIT 30")
        status["users_detail"] = self.list_users()
        status["active_sessions_detail"] = self.db.all("SELECT s.session_id,u.username,s.assurance_level,s.created_epoch,s.last_seen_epoch,s.idle_expires_epoch,s.absolute_expires_epoch FROM auth_sessions_146 s JOIN auth_users_146 u ON u.user_id=s.user_id WHERE s.revoked=0 AND s.absolute_expires_epoch>? ORDER BY s.created_epoch DESC", (int(self.clock()),))
        return status
