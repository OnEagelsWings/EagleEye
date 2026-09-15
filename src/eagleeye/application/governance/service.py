from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from eagleeye.infrastructure.governance.schema import ROLE_POLICIES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _loads(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except Exception:
        return default


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8", errors="replace")).hexdigest()


class GovernanceError(ValueError):
    pass


class GovernanceAccessError(GovernanceError):
    pass


class GovernanceConflict(GovernanceError):
    pass


class CollaborationGovernance132Service:
    """Local-first role, review and collaboration governance.

    Build 132 deliberately does not expose EagleEye on a network. The existing
    loopback-only server remains the transport boundary. Team mode adds a second
    authenticated governance layer, case assignments, RBAC, revocable sessions,
    object locks and four-eyes approval. Critical actions are executed only after
    a different, authorized reviewer approves the stored, hashed action payload.
    """

    BUILD = "132.0"
    OWNER_USERNAME = "local-analyst"
    TRUST_STATE = "suggestions_only"
    CRITICAL_ACTIONS = {
        "identity.confirm": {"permission": "identity.review", "object_type": "identity_hypothesis"},
        "hypothesis.accept": {"permission": "hypothesis.review", "object_type": "graph_hypothesis"},
        "report.accept": {"permission": "report.review", "object_type": "report_draft"},
        "export.approve": {"permission": "export.approve", "object_type": "evidence_export"},
    }

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        cases: Any,
        registry_getter: Callable[[], Any] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.cases = cases
        self._registry_getter = registry_getter
        self._clock = clock or time.time
        self._expire_locks()

    # ---------- policy / users ----------
    def settings(self) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM governance_settings_132 WHERE settings_id='global'") or {}
        for key in ("team_mode_enabled", "require_four_eyes"):
            row[key] = bool(row.get(key))
        return row

    def roles(self) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM governance_roles_132 WHERE active=1 ORDER BY rank DESC,role_key")
        for row in rows:
            row["permissions"] = _loads(row.pop("permissions_json", "[]"), [])
        return rows

    def _role(self, role_key: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM governance_roles_132 WHERE role_key=? AND active=1", (str(role_key),))
        if not row:
            raise GovernanceError("Unbekannte oder inaktive Governance-Rolle")
        row["permissions"] = _loads(row.get("permissions_json"), [])
        return row

    def _user(self, username: str, *, active_only: bool = True) -> dict[str, Any]:
        sql = "SELECT * FROM governance_users_132 WHERE username=? COLLATE NOCASE"
        params: tuple[Any, ...] = (str(username).strip(),)
        if active_only:
            sql += " AND active=1"
        row = self.db.one(sql, params)
        if not row:
            raise GovernanceAccessError("Governance-Benutzer nicht gefunden oder deaktiviert")
        return row

    def list_users(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT user_id,username,display_name,role_key,active,failed_attempts,lock_until_epoch,created_by,created_at,updated_at,last_login_at FROM governance_users_132"
        if not include_inactive:
            sql += " WHERE active=1"
        return self.db.all(sql + " ORDER BY active DESC,display_name COLLATE NOCASE")

    @staticmethod
    def _password_hash(passphrase: str) -> str:
        value = str(passphrase or "")
        if len(value) < 12:
            raise GovernanceError("Passphrase muss mindestens 12 Zeichen lang sein")
        if len(value) > 512:
            raise GovernanceError("Passphrase ist zu lang")
        salt = secrets.token_bytes(16)
        derived = hashlib.scrypt(value.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return "scrypt$16384$8$1$" + base64.b64encode(salt).decode("ascii") + "$" + base64.b64encode(derived).decode("ascii")

    @staticmethod
    def _verify_hash(passphrase: str, encoded: str) -> bool:
        try:
            marker, n, r, p, salt64, digest64 = str(encoded).split("$", 5)
            if marker != "scrypt":
                return False
            candidate = hashlib.scrypt(
                str(passphrase).encode("utf-8"), salt=base64.b64decode(salt64),
                n=int(n), r=int(r), p=int(p), dklen=32,
            )
            return hmac.compare_digest(candidate, base64.b64decode(digest64))
        except Exception:
            return False

    def create_user(
        self, *, username: str, display_name: str, role_key: str, passphrase: str,
        actor: str, active: bool = True,
    ) -> dict[str, Any]:
        self.require_global_permission(actor, "user.manage")
        username = str(username or "").strip().casefold()
        if not username or len(username) > 64 or not all(ch.isalnum() or ch in "._-" for ch in username):
            raise GovernanceError("Benutzername darf nur Buchstaben, Zahlen, Punkt, Unterstrich und Bindestrich enthalten")
        display_name = str(display_name or "").strip()
        if len(display_name) < 2 or len(display_name) > 120:
            raise GovernanceError("Anzeigename muss 2 bis 120 Zeichen lang sein")
        self._role(role_key)
        password_hash = self._password_hash(passphrase)
        user_id = _id("govuser132")
        ts = _now()
        try:
            self.db.execute(
                """INSERT INTO governance_users_132(user_id,username,display_name,role_key,password_hash,active,created_by,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (user_id, username, display_name, role_key, password_hash, int(bool(active)), actor, ts, ts),
            )
        except Exception as exc:
            raise GovernanceConflict("Benutzername ist bereits vergeben") from exc
        self._opsec("user_created", actor=actor, details={"user_id": user_id, "role_key": role_key, "active": bool(active)})
        self.audit.log("create", "governance_user_132", user_id, None, {"username_hash": _sha(username), "role_key": role_key})
        return self._user(username, active_only=False)

    def set_password(self, *, username: str, passphrase: str, actor: str) -> dict[str, Any]:
        user = self._user(username, active_only=False)
        if actor.casefold() != user["username"].casefold():
            self.require_global_permission(actor, "user.manage")
        encoded = self._password_hash(passphrase)
        self.db.execute(
            """UPDATE governance_users_132 SET password_hash=?,failed_attempts=0,lock_until_epoch=0,
               session_generation=session_generation+1,updated_at=? WHERE user_id=?""",
            (encoded, _now(), user["user_id"]),
        )
        self.revoke_user_sessions(username=username, actor=actor)
        self._opsec("password_changed", actor=actor, details={"user_id": user["user_id"]})
        return self._user(username, active_only=False)

    def set_user_active(self, *, username: str, active: bool, actor: str) -> dict[str, Any]:
        self.require_global_permission(actor, "user.manage")
        user = self._user(username, active_only=False)
        if user["username"].casefold() == self.OWNER_USERNAME and not active:
            raise GovernanceConflict("Der lokale Eigentümer kann nicht deaktiviert werden")
        self.db.execute(
            "UPDATE governance_users_132 SET active=?,session_generation=session_generation+1,updated_at=? WHERE user_id=?",
            (int(bool(active)), _now(), user["user_id"]),
        )
        self.revoke_user_sessions(username=username, actor=actor)
        self._opsec("user_status_changed", actor=actor, details={"user_id": user["user_id"], "active": bool(active)})
        return self._user(username, active_only=False)

    def enable_team_mode(self, *, actor: str, confirmation: str) -> dict[str, Any]:
        self.require_global_permission(actor, "team.configure")
        owner = self._user(self.OWNER_USERNAME)
        if not owner.get("password_hash"):
            raise GovernanceConflict("Vor Aktivierung des Teammodus muss für local-analyst eine Passphrase gesetzt werden")
        if str(confirmation or "").strip() != "TEAMMODUS AKTIVIEREN":
            raise GovernanceError("Freigabephrase TEAMMODUS AKTIVIEREN fehlt")
        self.db.execute(
            "UPDATE governance_settings_132 SET team_mode_enabled=1,updated_by=?,updated_at=? WHERE settings_id='global'",
            (actor, _now()),
        )
        self._opsec("team_mode_enabled", actor=actor, details={"remote_server_mode": "disabled_loopback_only"})
        self.audit.log("enable", "team_mode_132", "global", None, {"loopback_only": True})
        return self.settings()

    def disable_team_mode(self, *, actor: str, confirmation: str) -> dict[str, Any]:
        self.require_global_permission(actor, "team.configure")
        if str(confirmation or "").strip() != "TEAMMODUS DEAKTIVIEREN":
            raise GovernanceError("Freigabephrase TEAMMODUS DEAKTIVIEREN fehlt")
        self.db.execute(
            "UPDATE governance_settings_132 SET team_mode_enabled=0,updated_by=?,updated_at=? WHERE settings_id='global'",
            (actor, _now()),
        )
        self.revoke_all_sessions(actor=actor)
        self._opsec("team_mode_disabled", actor=actor, details={})
        return self.settings()

    # ---------- authentication / revocation ----------
    def authenticate(self, *, username: str, passphrase: str, client_fingerprint: str) -> dict[str, Any]:
        username = str(username or "").strip().casefold()
        try:
            user = self._user(username)
        except GovernanceAccessError:
            # Equalize the expensive path without revealing account existence.
            hashlib.scrypt(str(passphrase or "").encode("utf-8"), salt=b"EagleEyeBuild132", n=2**14, r=8, p=1, dklen=32)
            self._opsec("login_failed", actor="unknown", details={"username_hash": _sha(username), "reason": "unknown_or_inactive"})
            raise GovernanceAccessError("Anmeldung fehlgeschlagen")
        now_epoch = int(self._clock())
        if int(user.get("lock_until_epoch") or 0) > now_epoch:
            raise GovernanceAccessError("Anmeldung vorübergehend blockiert")
        settings = self.settings()
        ok = bool(user.get("password_hash")) and self._verify_hash(passphrase, user.get("password_hash") or "")
        if not ok:
            failures = int(user.get("failed_attempts") or 0) + 1
            threshold = max(3, int(settings.get("max_failed_logins") or 5))
            lock_until = now_epoch + min(900, 2 ** min(failures, 9)) if failures >= threshold else 0
            self.db.execute(
                "UPDATE governance_users_132 SET failed_attempts=?,lock_until_epoch=?,updated_at=? WHERE user_id=?",
                (failures, lock_until, _now(), user["user_id"]),
            )
            self._opsec("login_failed", actor=username, details={"failed_attempts": failures, "rate_limited": bool(lock_until)})
            raise GovernanceAccessError("Anmeldung fehlgeschlagen")
        timeout = max(5, min(int(settings.get("session_timeout_minutes") or 30), 240)) * 60
        token = secrets.token_urlsafe(48)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        session_id = _id("govsess132")
        with self.db.transaction(immediate=True):
            self.db.execute(
                "UPDATE governance_users_132 SET failed_attempts=0,lock_until_epoch=0,last_login_at=?,updated_at=? WHERE user_id=?",
                (_now(), _now(), user["user_id"]),
            )
            self.db.execute(
                """INSERT INTO governance_sessions_132(session_id,token_hash,user_id,session_generation,client_fingerprint,created_at,last_seen_epoch,expires_epoch)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (session_id, digest, user["user_id"], int(user.get("session_generation") or 1), str(client_fingerprint or ""), _now(), now_epoch, now_epoch + timeout),
            )
        self._opsec("login_succeeded", actor=username, details={"session_id": session_id, "timeout_seconds": timeout})
        return {"token": token, "timeout": timeout, "username": user["username"], "display_name": user["display_name"], "role_key": user["role_key"]}

    def validate_session(self, token: str, *, client_fingerprint: str, touch: bool = True) -> dict[str, Any] | None:
        if not token:
            return None
        digest = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
        now_epoch = int(self._clock())
        row = self.db.one(
            """SELECT s.*,u.username,u.display_name,u.role_key,u.active,u.session_generation AS current_generation
               FROM governance_sessions_132 s JOIN governance_users_132 u ON u.user_id=s.user_id
               WHERE s.token_hash=?""",
            (digest,),
        )
        if not row or row.get("revoked") or not row.get("active"):
            return None
        if int(row.get("expires_epoch") or 0) < now_epoch or int(row.get("session_generation") or 0) != int(row.get("current_generation") or 0):
            self.db.execute("UPDATE governance_sessions_132 SET revoked=1,revoked_by='system-expiry',revoked_at=? WHERE session_id=?", (_now(), row["session_id"]))
            return None
        settings = self.settings()
        idle = max(5, min(int(settings.get("session_timeout_minutes") or 30), 240)) * 60
        if now_epoch - int(row.get("last_seen_epoch") or 0) > idle:
            self.db.execute("UPDATE governance_sessions_132 SET revoked=1,revoked_by='system-idle',revoked_at=? WHERE session_id=?", (_now(), row["session_id"]))
            return None
        if row.get("client_fingerprint") and not hmac.compare_digest(str(row["client_fingerprint"]), str(client_fingerprint or "")):
            self._opsec("session_binding_mismatch", actor=row.get("username") or "unknown", details={"session_id": row["session_id"]})
            return None
        if touch:
            self.db.execute("UPDATE governance_sessions_132 SET last_seen_epoch=? WHERE session_id=?", (now_epoch, row["session_id"]))
        return {"session_id": row["session_id"], "user_id": row["user_id"], "username": row["username"], "display_name": row["display_name"], "role_key": row["role_key"]}

    def revoke_session(self, *, session_id: str, actor: str) -> None:
        self.require_global_permission(actor, "session.revoke")
        self.db.execute("UPDATE governance_sessions_132 SET revoked=1,revoked_by=?,revoked_at=? WHERE session_id=?", (actor, _now(), session_id))
        self._opsec("session_revoked", actor=actor, details={"session_id": session_id})

    def logout_session(self, *, token: str, actor: str) -> bool:
        if not token:
            return False
        digest = hashlib.sha256(str(token).encode("utf-8")).hexdigest()
        row = self.db.one(
            """SELECT s.session_id,u.username FROM governance_sessions_132 s
               JOIN governance_users_132 u ON u.user_id=s.user_id WHERE s.token_hash=?""",
            (digest,),
        )
        if not row or row["username"].casefold() != actor.casefold():
            return False
        self.db.execute(
            "UPDATE governance_sessions_132 SET revoked=1,revoked_by=?,revoked_at=? WHERE session_id=?",
            (actor, _now(), row["session_id"]),
        )
        self._opsec("session_logout", actor=actor, details={"session_id": row["session_id"]})
        return True

    def revoke_user_sessions(self, *, username: str, actor: str) -> int:
        user = self._user(username, active_only=False)
        cur = self.db.execute(
            "UPDATE governance_sessions_132 SET revoked=1,revoked_by=?,revoked_at=? WHERE user_id=? AND revoked=0",
            (actor, _now(), user["user_id"]),
        )
        return int(cur.rowcount or 0)

    def revoke_all_sessions(self, *, actor: str) -> int:
        cur = self.db.execute(
            "UPDATE governance_sessions_132 SET revoked=1,revoked_by=?,revoked_at=? WHERE revoked=0",
            (actor, _now()),
        )
        self._opsec("all_sessions_revoked", actor=actor, details={"count": int(cur.rowcount or 0)})
        return int(cur.rowcount or 0)

    def active_sessions(self) -> list[dict[str, Any]]:
        now_epoch = int(self._clock())
        return self.db.all(
            """SELECT s.session_id,u.username,u.display_name,u.role_key,s.created_at,s.last_seen_epoch,s.expires_epoch
               FROM governance_sessions_132 s JOIN governance_users_132 u ON u.user_id=s.user_id
               WHERE s.revoked=0 AND s.expires_epoch>=? ORDER BY s.last_seen_epoch DESC""",
            (now_epoch,),
        )

    # ---------- authorization / case isolation ----------
    @staticmethod
    def _matches(permission: str, granted: list[str]) -> bool:
        if "*" in granted or permission in granted:
            return True
        prefix = permission.split(".", 1)[0] + ".*"
        return prefix in granted

    def permissions_for(self, username: str, case_id: str = "") -> set[str]:
        user = self._user(username)
        role = self._role(user["role_key"])
        permissions = set(role["permissions"])
        if case_id:
            rows = self.db.all(
                """SELECT r.permissions_json FROM governance_case_assignments_132 a
                   JOIN governance_roles_132 r ON r.role_key=a.role_key
                   WHERE a.case_id=? AND a.user_id=? AND a.active=1 AND r.active=1""",
                (case_id, user["user_id"]),
            )
            if rows:
                permissions = set()
                for row in rows:
                    permissions.update(_loads(row.get("permissions_json"), []))
            elif user["role_key"] != "administrator":
                permissions = set()
        return permissions

    def require_global_permission(self, username: str, permission: str) -> None:
        # Administrative governance capabilities are deliberately implicit only
        # for the administrator role and never copied into case roles.
        user = self._user(username)
        if user["role_key"] == "administrator":
            return
        aliases = {
            "user.manage": "case.assign",
            "team.configure": "case.assign",
            "session.revoke": "case.assign",
        }
        requested = aliases.get(permission, permission)
        if not self._matches(requested, list(self.permissions_for(username))):
            raise GovernanceAccessError("Globale Governance-Berechtigung fehlt")

    def authorize(self, *, username: str, case_id: str, permission: str) -> dict[str, Any]:
        user = self._user(username)
        if user["role_key"] == "administrator":
            return {"allowed": True, "reason": "administrator", "username": user["username"], "role_key": user["role_key"]}
        if not case_id:
            allowed = self._matches(permission, list(self.permissions_for(username)))
        else:
            allowed = self._matches(permission, list(self.permissions_for(username, case_id)))
        if not allowed:
            self._opsec("permission_denied", case_id=case_id or None, actor=username, details={"permission": permission})
            raise GovernanceAccessError("Für diesen Fall oder Arbeitsschritt fehlt die Berechtigung")
        return {"allowed": True, "reason": "assigned_role", "username": user["username"], "role_key": user["role_key"]}

    def accessible_case_ids(self, username: str) -> list[str]:
        user = self._user(username)
        if user["role_key"] == "administrator":
            return [row["case_id"] for row in self.cases.list_cases()]
        return [
            row["case_id"] for row in self.db.all(
                "SELECT DISTINCT case_id FROM governance_case_assignments_132 WHERE user_id=? AND active=1 ORDER BY case_id",
                (user["user_id"],),
            )
        ]

    def list_accessible_cases(self, username: str) -> list[dict[str, Any]]:
        ids = set(self.accessible_case_ids(username))
        return [row for row in self.cases.list_cases() if row["case_id"] in ids]

    def register_case(self, *, case_id: str, actor: str) -> dict[str, Any]:
        self.cases.get_case(case_id)
        user = self._user(actor)
        role_key = "lead_investigator" if user["role_key"] != "administrator" else "administrator"
        self._role(role_key)
        assignment_id = _id("govassign132")
        ts = _now()
        self.db.execute(
            """INSERT OR IGNORE INTO governance_case_assignments_132(assignment_id,case_id,user_id,role_key,active,granted_by,granted_at,notes)
               VALUES(?,?,?,?,1,?,?,?)""",
            (assignment_id, case_id, user["user_id"], role_key, actor, ts, "Automatic creator assignment"),
        )
        row = self.db.one(
            "SELECT * FROM governance_case_assignments_132 WHERE case_id=? AND user_id=? AND role_key=?",
            (case_id, user["user_id"], role_key),
        ) or {}
        self._opsec("case_creator_assigned", case_id=case_id, actor=actor, object_type="user", object_id=user["user_id"], details={"role_key": role_key})
        return row

    def assign_case(self, *, case_id: str, username: str, role_key: str, actor: str, notes: str = "") -> dict[str, Any]:
        self.authorize(username=actor, case_id=case_id, permission="case.assign")
        self.cases.get_case(case_id)
        user = self._user(username)
        self._role(role_key)
        assignment_id = _id("govassign132")
        ts = _now()
        with self.db.transaction(immediate=True):
            existing = self.db.one(
                "SELECT * FROM governance_case_assignments_132 WHERE case_id=? AND user_id=? AND role_key=?",
                (case_id, user["user_id"], role_key),
            )
            if existing:
                self.db.execute(
                    """UPDATE governance_case_assignments_132 SET active=1,granted_by=?,granted_at=?,revoked_by='',revoked_at='',notes=?
                       WHERE assignment_id=?""",
                    (actor, ts, str(notes or "")[:1000], existing["assignment_id"]),
                )
                assignment_id = existing["assignment_id"]
            else:
                self.db.execute(
                    """INSERT INTO governance_case_assignments_132(assignment_id,case_id,user_id,role_key,active,granted_by,granted_at,notes)
                       VALUES(?,?,?,?,1,?,?,?)""",
                    (assignment_id, case_id, user["user_id"], role_key, actor, ts, str(notes or "")[:1000]),
                )
        self.audit.log("assign", "case_access_132", assignment_id, case_id, {"user_id": user["user_id"], "role_key": role_key})
        self._opsec("case_assigned", case_id=case_id, actor=actor, object_type="user", object_id=user["user_id"], details={"role_key": role_key})
        return self.db.one("SELECT * FROM governance_case_assignments_132 WHERE assignment_id=?", (assignment_id,)) or {}

    def revoke_case_assignment(self, *, assignment_id: str, actor: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM governance_case_assignments_132 WHERE assignment_id=?", (assignment_id,))
        if not row:
            raise GovernanceError("Fallzuweisung nicht gefunden")
        self.authorize(username=actor, case_id=row["case_id"], permission="case.assign")
        self.db.execute(
            "UPDATE governance_case_assignments_132 SET active=0,revoked_by=?,revoked_at=? WHERE assignment_id=?",
            (actor, _now(), assignment_id),
        )
        self._opsec("case_assignment_revoked", case_id=row["case_id"], actor=actor, object_type="assignment", object_id=assignment_id, details={})
        return self.db.one("SELECT * FROM governance_case_assignments_132 WHERE assignment_id=?", (assignment_id,)) or {}

    def case_assignments(self, case_id: str) -> list[dict[str, Any]]:
        return self.db.all(
            """SELECT a.*,u.username,u.display_name FROM governance_case_assignments_132 a
               JOIN governance_users_132 u ON u.user_id=a.user_id
               WHERE a.case_id=? ORDER BY a.active DESC,a.granted_at DESC""",
            (case_id,),
        )

    # ---------- locks / comments ----------
    def _expire_locks(self) -> int:
        now_epoch = int(self._clock())
        cur = self.db.execute(
            "UPDATE governance_object_locks_132 SET active=0,released_by='system-expiry',released_at=? WHERE active=1 AND expires_epoch<?",
            (_now(), now_epoch),
        )
        return int(cur.rowcount or 0)

    def acquire_lock(
        self, *, case_id: str, object_type: str, object_id: str, purpose: str,
        actor: str, ttl_minutes: int = 15,
    ) -> dict[str, Any]:
        self.authorize(username=actor, case_id=case_id, permission="lock.manage")
        if not object_type or not object_id or len(str(object_type)) > 80 or len(str(object_id)) > 160:
            raise GovernanceError("Objekttyp und Objekt-ID sind erforderlich")
        if len(str(purpose or "").strip()) < 8:
            raise GovernanceError("Lock-Zweck muss mindestens acht Zeichen enthalten")
        self._expire_locks()
        expires = int(self._clock()) + max(2, min(int(ttl_minutes), 120)) * 60
        lock_id = _id("govlock132")
        with self.db.transaction(immediate=True):
            existing = self.db.one(
                "SELECT * FROM governance_object_locks_132 WHERE case_id=? AND object_type=? AND object_id=? AND active=1",
                (case_id, object_type, object_id),
            )
            if existing:
                if existing["owner_username"].casefold() != actor.casefold():
                    raise GovernanceConflict("Objekt ist bereits durch einen anderen Benutzer gesperrt")
                self.db.execute(
                    "UPDATE governance_object_locks_132 SET purpose=?,expires_epoch=? WHERE lock_id=?",
                    (str(purpose)[:1000], expires, existing["lock_id"]),
                )
                lock_id = existing["lock_id"]
            else:
                self.db.execute(
                    """INSERT INTO governance_object_locks_132(lock_id,case_id,object_type,object_id,owner_username,purpose,acquired_at,expires_epoch)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (lock_id, case_id, object_type, object_id, actor, str(purpose)[:1000], _now(), expires),
                )
        self._opsec("object_locked", case_id=case_id, actor=actor, object_type=object_type, object_id=object_id, details={"ttl_minutes": max(2, min(int(ttl_minutes), 120))})
        return self.db.one("SELECT * FROM governance_object_locks_132 WHERE lock_id=?", (lock_id,)) or {}

    def assert_editable(self, *, case_id: str, object_type: str, object_id: str, actor: str) -> None:
        self._expire_locks()
        row = self.db.one(
            "SELECT * FROM governance_object_locks_132 WHERE case_id=? AND object_type=? AND object_id=? AND active=1",
            (case_id, object_type, object_id),
        )
        if row and row["owner_username"].casefold() != actor.casefold():
            raise GovernanceConflict(f"Objekt ist durch {row['owner_username']} gesperrt")

    def release_lock(self, *, lock_id: str, actor: str, force: bool = False) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM governance_object_locks_132 WHERE lock_id=?", (lock_id,))
        if not row:
            raise GovernanceError("Objektsperre nicht gefunden")
        if row.get("active") and row["owner_username"].casefold() != actor.casefold():
            if not force:
                raise GovernanceAccessError("Nur Lock-Eigentümer oder Administrator darf die Sperre lösen")
            self.require_global_permission(actor, "user.manage")
        self.db.execute(
            "UPDATE governance_object_locks_132 SET active=0,released_by=?,released_at=? WHERE lock_id=?",
            (actor, _now(), lock_id),
        )
        self._opsec("object_unlocked", case_id=row["case_id"], actor=actor, object_type=row["object_type"], object_id=row["object_id"], details={"forced": bool(force)})
        return self.db.one("SELECT * FROM governance_object_locks_132 WHERE lock_id=?", (lock_id,)) or {}

    def active_locks(self, case_id: str) -> list[dict[str, Any]]:
        self._expire_locks()
        return self.db.all("SELECT * FROM governance_object_locks_132 WHERE case_id=? AND active=1 ORDER BY acquired_at DESC", (case_id,))

    def add_comment(self, *, case_id: str, object_type: str, object_id: str, text: str, actor: str) -> dict[str, Any]:
        self.authorize(username=actor, case_id=case_id, permission="comment.write")
        text = str(text or "").strip()
        if len(text) < 2 or len(text) > 5000:
            raise GovernanceError("Kommentar muss 2 bis 5000 Zeichen enthalten")
        comment_id = _id("govcomment132")
        ts = _now()
        self.db.execute(
            """INSERT INTO governance_comments_132(comment_id,case_id,object_type,object_id,comment_text,comment_sha256,author_username,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (comment_id, case_id, str(object_type)[:80], str(object_id)[:160], text, hashlib.sha256(text.encode("utf-8")).hexdigest(), actor, ts, ts),
        )
        # Content remains only in the controlled table, never duplicated into audit.
        self.audit.log("comment", "governance_comment_132", comment_id, case_id, {"object_type": str(object_type)[:80], "object_id": str(object_id)[:160], "comment_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
        return self.db.one("SELECT * FROM governance_comments_132 WHERE comment_id=?", (comment_id,)) or {}

    def comments(self, case_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM governance_comments_132 WHERE case_id=? AND status='active' ORDER BY created_at DESC LIMIT ?", (case_id, max(1, min(int(limit), 500))))

    # ---------- four-eyes approvals ----------
    def request_critical_action(
        self, *, case_id: str, action_key: str, object_id: str, payload: dict[str, Any],
        reason: str, actor: str,
    ) -> dict[str, Any]:
        config = self.CRITICAL_ACTIONS.get(action_key)
        if not config:
            raise GovernanceError("Unbekannte kritische Aktion")
        self.authorize(username=actor, case_id=case_id, permission="approval.request")
        reason = str(reason or "").strip()
        if len(reason) < 12:
            raise GovernanceError("Freigabeanfrage benötigt eine substanzielle Begründung")
        payload = dict(payload or {})
        payload["case_id"] = case_id
        request_id = _id("govapproval132")
        ts = _now()
        with self.db.transaction(immediate=True):
            pending = self.db.one(
                """SELECT * FROM governance_approval_requests_132
                   WHERE case_id=? AND action_key=? AND object_id=? AND status='pending'""",
                (case_id, action_key, object_id),
            )
            if pending:
                raise GovernanceConflict("Für dieses Objekt besteht bereits eine offene Freigabeanfrage")
            self.db.execute(
                """INSERT INTO governance_approval_requests_132(
                     request_id,case_id,action_key,object_type,object_id,payload_json,payload_sha256,
                     required_permission,required_approvals,status,requested_by,request_reason,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,1,'pending',?,?,?,?)""",
                (request_id, case_id, action_key, config["object_type"], object_id, _json(payload), _sha(payload), config["permission"], actor, reason, ts, ts),
            )
        self.audit.log("request", "four_eyes_approval_132", request_id, case_id, {"action_key": action_key, "object_type": config["object_type"], "object_id": object_id, "payload_sha256": _sha(payload)})
        self._opsec("approval_requested", case_id=case_id, actor=actor, object_type=config["object_type"], object_id=object_id, details={"action_key": action_key, "payload_sha256": _sha(payload)})
        return self.get_approval(request_id)

    def get_approval(self, request_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM governance_approval_requests_132 WHERE request_id=?", (request_id,))
        if not row:
            raise GovernanceError("Freigabeanfrage nicht gefunden")
        row["payload"] = _loads(row.get("payload_json"), {})
        row["decisions"] = self.db.all("SELECT * FROM governance_approval_decisions_132 WHERE request_id=? ORDER BY created_at", (request_id,))
        return row

    def approvals(self, case_id: str, *, status: str = "") -> list[dict[str, Any]]:
        if status:
            return self.db.all("SELECT * FROM governance_approval_requests_132 WHERE case_id=? AND status=? ORDER BY created_at DESC", (case_id, status))
        return self.db.all("SELECT * FROM governance_approval_requests_132 WHERE case_id=? ORDER BY created_at DESC", (case_id,))

    def decide_approval(self, *, request_id: str, decision: str, reason: str, actor: str) -> dict[str, Any]:
        if decision not in {"approved", "rejected", "needs_changes"}:
            raise GovernanceError("Ungültige Freigabeentscheidung")
        reason = str(reason or "").strip()
        if len(reason) < 12:
            raise GovernanceError("Reviewentscheidung benötigt eine substanzielle Begründung")
        with self.db.transaction(immediate=True):
            request = self.db.one("SELECT * FROM governance_approval_requests_132 WHERE request_id=?", (request_id,))
            if not request:
                raise GovernanceError("Freigabeanfrage nicht gefunden")
            if request["status"] != "pending":
                raise GovernanceConflict("Freigabeanfrage ist bereits abgeschlossen")
            if request["requested_by"].casefold() == actor.casefold():
                raise GovernanceConflict("Vier-Augen-Prinzip: Antragsteller darf nicht selbst entscheiden")
            self.authorize(username=actor, case_id=request["case_id"], permission=request["required_permission"])
            decision_id = _id("govdecision132")
            self.db.execute(
                "INSERT INTO governance_approval_decisions_132(decision_id,request_id,decision,decided_by,reason,created_at) VALUES(?,?,?,?,?,?)",
                (decision_id, request_id, decision, actor, reason, _now()),
            )
            if decision != "approved":
                self.db.execute(
                    "UPDATE governance_approval_requests_132 SET status=?,updated_at=? WHERE request_id=?",
                    ("rejected" if decision == "rejected" else "needs_changes", _now(), request_id),
                )
        execution = None
        if decision == "approved":
            execution = self._execute_approved(request_id=request_id, actor=actor)
        self.audit.log("decide", "four_eyes_approval_132", request_id, request["case_id"], {"decision": decision, "action_key": request["action_key"], "reason_sha256": hashlib.sha256(reason.encode("utf-8")).hexdigest()})
        self._opsec("approval_decided", case_id=request["case_id"], actor=actor, object_type=request["object_type"], object_id=request["object_id"], details={"decision": decision, "action_key": request["action_key"]})
        result = self.get_approval(request_id)
        result["execution"] = execution
        return result

    def _registry(self) -> Any:
        if not self._registry_getter:
            raise GovernanceConflict("Service Registry ist für die Freigabeausführung nicht verfügbar")
        registry = self._registry_getter()
        if registry is None:
            raise GovernanceConflict("Service Registry wurde bereits geschlossen")
        return registry

    def _execute_approved(self, *, request_id: str, actor: str) -> dict[str, Any]:
        req = self.db.one("SELECT * FROM governance_approval_requests_132 WHERE request_id=?", (request_id,))
        if not req or req["status"] != "pending" or req["execution_status"] != "not_executed":
            raise GovernanceConflict("Freigabe kann nicht erneut ausgeführt werden")
        payload = _loads(req.get("payload_json"), {})
        if _sha(payload) != req.get("payload_sha256"):
            # Persist the fail-closed state before raising. Keeping this update
            # outside a transaction that deliberately raises prevents rollback
            # of the integrity finding itself.
            self.db.execute(
                "UPDATE governance_approval_requests_132 SET status='blocked_integrity',execution_status='blocked',execution_error='payload_integrity_mismatch',updated_at=? WHERE request_id=?",
                (_now(), request_id),
            )
            self._opsec("approval_integrity_blocked", case_id=req["case_id"], actor=actor, object_type=req["object_type"], object_id=req["object_id"], details={"action_key": req["action_key"]})
            raise GovernanceConflict("Freigabepayload hat die Integritätsprüfung nicht bestanden")
        with self.db.transaction(immediate=True):
            current = self.db.one("SELECT status,execution_status FROM governance_approval_requests_132 WHERE request_id=?", (request_id,)) or {}
            if current.get("status") != "pending" or current.get("execution_status") != "not_executed":
                raise GovernanceConflict("Freigabe kann nicht erneut ausgeführt werden")
            self.db.execute("UPDATE governance_approval_requests_132 SET execution_status='executing',updated_at=? WHERE request_id=?", (_now(), request_id))
        try:
            registry = self._registry()
            action = req["action_key"]
            if action == "identity.confirm":
                result = registry.get("capture_identity_129").review_identity_hypothesis(
                    case_id=req["case_id"], hypothesis_id=req["object_id"], decision="same_person",
                    reason=str(payload.get("reason") or "Four-eyes approval completed."), actor=actor,
                )
            elif action == "hypothesis.accept":
                result = registry.get("graph_hypothesis_130").review_hypothesis(
                    case_id=req["case_id"], hypothesis_id=req["object_id"], decision="supported_for_working_use",
                    reason=str(payload.get("reason") or "Four-eyes approval completed."), actor=actor,
                )
            elif action == "report.accept":
                result = registry.get("investigative_synthesis_131").review_report(
                    case_id=req["case_id"], report_id=req["object_id"], decision="accepted_for_working_use",
                    reason=str(payload.get("reason") or "Four-eyes approval completed."), actor=actor,
                )
            else:
                raise GovernanceConflict("Für diese kritische Aktion ist noch kein sicherer Executor registriert")
        except Exception as exc:
            self.db.execute(
                """UPDATE governance_approval_requests_132 SET status='execution_failed',execution_status='failed',
                   execution_error=?,updated_at=? WHERE request_id=?""",
                (type(exc).__name__, _now(), request_id),
            )
            self._opsec("approval_execution_failed", case_id=req["case_id"], actor=actor, object_type=req["object_type"], object_id=req["object_id"], details={"action_key": req["action_key"], "error_type": type(exc).__name__})
            raise
        self.db.execute(
            """UPDATE governance_approval_requests_132 SET status='approved_executed',execution_status='executed',
               execution_error='',executed_at=?,updated_at=? WHERE request_id=?""",
            (_now(), _now(), request_id),
        )
        return {"executed": True, "action_key": req["action_key"], "object_id": req["object_id"], "result_status": str(result.get("review_decision") or result.get("status") or "completed") if isinstance(result, dict) else "completed"}

    # ---------- local AI reviewer and dashboard ----------
    def generate_reviewer_brief(self, *, case_id: str, actor: str) -> dict[str, Any]:
        self.authorize(username=actor, case_id=case_id, permission="ai.review")
        pending = self.approvals(case_id, status="pending")
        locks = self.active_locks(case_id)
        assignments = self.case_assignments(case_id)
        comments = self.comments(case_id, 50)
        synthesis = self.db.one(
            "SELECT COUNT(*) AS n,SUM(CASE WHEN stale=1 THEN 1 ELSE 0 END) AS stale FROM report_drafts_131 WHERE case_id=?",
            (case_id,),
        ) or {"n": 0, "stale": 0}
        conflicts = [
            {
                "type": "self_approval_risk",
                "request_id": row["request_id"],
                "requested_by": row["requested_by"],
                "instruction": "Reviewer must be a different authorized user.",
            }
            for row in pending
        ]
        recommendations: list[dict[str, Any]] = []
        if pending:
            recommendations.append({"priority": 100, "action": "Review pending four-eyes requests", "count": len(pending)})
        if int(synthesis.get("stale") or 0):
            recommendations.append({"priority": 95, "action": "Regenerate stale synthesis reports before approval", "count": int(synthesis.get("stale") or 0)})
        if locks:
            recommendations.append({"priority": 70, "action": "Review active object locks and expiry", "count": len(locks)})
        if len({row["username"] for row in assignments if row.get("active")}) < 2 and self.settings().get("team_mode_enabled"):
            recommendations.append({"priority": 90, "action": "Assign a second qualified reviewer to enable four-eyes decisions", "count": 1})
        content = {
            "case_id": case_id,
            "trust_state": self.TRUST_STATE,
            "external_actions": 0,
            "automatic_permission_changes": False,
            "automatic_approvals": False,
            "automatic_lock_release": False,
            "pending_approvals": len(pending),
            "active_locks": len(locks),
            "active_assignments": len([row for row in assignments if row.get("active")]),
            "recent_comment_count": len(comments),
            "conflict_checks": conflicts,
            "recommendations": sorted(recommendations, key=lambda item: -int(item["priority"])),
            "opsec_notice": "No case text, comment text, passwords, session tokens or approval payloads were sent to an external model.",
        }
        brief_id = _id("govbrief132")
        self.db.execute(
            """INSERT INTO governance_ai_briefs_132(brief_id,case_id,content_json,content_sha256,external_actions,model_key,model_version,created_by,created_at)
               VALUES(?,?,?,?,0,'local-governance-reviewer','132.0',?,?)""",
            (brief_id, case_id, _json(content), _sha(content), actor, _now()),
        )
        self.audit.log("generate", "governance_ai_brief_132", brief_id, case_id, {"content_sha256": _sha(content), "external_actions": 0, "recommendation_count": len(recommendations)})
        return {"brief_id": brief_id, **content}

    def dashboard(self, case_id: str, *, actor: str) -> dict[str, Any]:
        self.authorize(username=actor, case_id=case_id, permission="case.read")
        settings = self.settings()
        assignments = self.case_assignments(case_id)
        approvals = self.approvals(case_id)
        locks = self.active_locks(case_id)
        comments = self.comments(case_id, 100)
        briefs = self.db.all("SELECT * FROM governance_ai_briefs_132 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        raw_current = self._user(actor)
        current_user = {key: raw_current.get(key) for key in ("user_id", "username", "display_name", "role_key", "active", "last_login_at")}
        return {
            "settings": settings,
            "current_user": current_user,
            "roles": self.roles(),
            "users": self.list_users(include_inactive=True),
            "assignments": assignments,
            "approvals": approvals,
            "locks": locks,
            "comments": comments,
            "briefs": briefs,
            "sessions": self.active_sessions() if self._user(actor)["role_key"] == "administrator" else [],
            "metrics": {
                "active_users": len([row for row in self.list_users(include_inactive=True) if row.get("active")]),
                "active_assignments": len([row for row in assignments if row.get("active")]),
                "pending_approvals": len([row for row in approvals if row.get("status") == "pending"]),
                "active_locks": len(locks),
                "recent_comments": len(comments),
                "active_sessions": len(self.active_sessions()),
            },
            "status": {
                "trust_state": self.TRUST_STATE,
                "external_ai_actions": 0,
                "automatic_approvals": False,
                "automatic_permission_changes": False,
                "automatic_session_sharing": False,
                "remote_server_mode": settings.get("remote_server_mode"),
                "four_eyes_enforced": bool(settings.get("require_four_eyes")),
            },
        }

    # ---------- minimized OPSEC ledger ----------
    def _opsec(
        self, event_type: str, *, actor: str, details: dict[str, Any], case_id: str | None = None,
        object_type: str = "", object_id: str = "",
    ) -> None:
        safe: dict[str, Any] = {}
        forbidden = ("password", "passphrase", "token", "cookie", "comment_text", "payload_json", "reason_text", "case_text", "report_text")
        for key, value in dict(details or {}).items():
            if any(marker in str(key).casefold() for marker in forbidden):
                safe[str(key)] = "[not-recorded]"
            else:
                safe[str(key)] = value
        self.db.execute(
            """INSERT INTO governance_opsec_events_132(event_id,case_id,event_type,actor,object_type,object_id,details_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (_id("govopsec132"), case_id, event_type, actor, str(object_type)[:80], str(object_id)[:160], _json(safe), _now()),
        )
