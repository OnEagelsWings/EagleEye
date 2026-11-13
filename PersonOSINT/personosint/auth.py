"""Benutzer, Rollen, Anmeldung mit Zwei-Faktor (TOTP) und Sitzungen."""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import Settings
from .crypto import Vault
from .db import Database, now_iso

ROLES = {
    "admin": "Administration",
    "leitung": "Teamleitung",
    "analyst": "Analyst/in",
    "pruefer": "Prüfer/in",
    "leser": "Leser/in (nur lesen)",
}
ROLE_HELP = {
    "admin": "Benutzer, Sicherheit, Sicherungen; sieht alle nicht-vertraulichen Fälle.",
    "leitung": "Sieht alle nicht-vertraulichen Fälle, weist zu, gibt frei, löscht Fälle.",
    "analyst": "Legt Fälle an und bearbeitet eigene bzw. zugewiesene Fälle.",
    "pruefer": "Prüft zugewiesene Fälle (Vier-Augen-Prinzip) und gibt sie frei.",
    "leser": "Liest zugewiesene Fälle und exportiert Dossiers, ändert nichts.",
}
CASE_CREATORS = {"admin", "leitung", "analyst"}
SUPERVISORS = {"admin", "leitung"}

_ph = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2)
_DUMMY_HASH = _ph.hash("eagleeye-dummy-password")


class AuthError(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


# --------------------------------------------------------------------------- Passwörter

def check_password_policy(password: str, username: str = "") -> None:
    if len(password) < 12:
        raise AuthError("Das Passwort muss mindestens 12 Zeichen lang sein.", 422)
    classes = sum(bool(re.search(p, password)) for p in (r"[a-zäöü]", r"[A-ZÄÖÜ]", r"\d", r"[^\w\s]"))
    if classes < 3:
        raise AuthError("Das Passwort braucht mindestens drei von: Kleinbuchstaben, Großbuchstaben, Ziffern, Sonderzeichen.", 422)
    if username and username.casefold() in password.casefold():
        raise AuthError("Das Passwort darf den Benutzernamen nicht enthalten.", 422)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored: str, password: str) -> bool:
    try:
        return _ph.verify(stored, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# --------------------------------------------------------------------------- TOTP (RFC 6238)

def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp_code(secret: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    counter = int((at if at is not None else time.time()) // step)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(value).zfill(digits)


def totp_counter(secret: str, code: str, window: int = 1) -> int | None:
    """Zeitschritt des passenden Codes (für den Wiederverwendungsschutz) oder None."""
    code = re.sub(r"\s", "", code or "")
    if not re.fullmatch(r"\d{6}", code):
        return None
    now = time.time()
    for i in range(-window, window + 1):
        if hmac.compare_digest(totp_code(secret, now + i * 30), code):
            return int((now + i * 30) // 30)
    return None


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    return totp_counter(secret, code, window) is not None


def totp_uri(secret: str, username: str, issuer: str = "EagleEye PersonOSINT") -> str:
    return f"otpauth://totp/{quote(issuer)}:{quote(username)}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"


def qr_svg(data: str) -> str:
    try:
        import segno
    except ImportError:  # QR-Code ist Komfort; das Geheimnis wird zusätzlich als Text angezeigt
        return ""
    return segno.make(data, error="m").svg_inline(scale=5, dark="#0f2a4a")


# --------------------------------------------------------------------------- Dienst

def _utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Auth:
    def __init__(self, db: Database, vault: Vault, settings: Settings):
        self.db = db
        self.vault = vault
        self.settings = settings

    # ------------------------------------------------------------------ Benutzer
    @staticmethod
    def public(user: dict[str, Any] | None) -> dict[str, Any] | None:
        if not user:
            return None
        return {k: user[k] for k in ("id", "username", "display_name", "role", "totp_enabled", "must_change_password",
                                     "active", "created_at", "last_login", "locked_until")} | {"role_label": ROLES.get(user["role"], user["role"])}

    def user_count(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) AS n FROM users") or 0)

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        return self.db.one("SELECT * FROM users WHERE id = ?", (user_id,))

    def list_users(self) -> list[dict[str, Any]]:
        return [self.public(u) for u in self.db.all("SELECT * FROM users ORDER BY active DESC, display_name")]  # type: ignore[misc]

    def create_user(self, username: str, display_name: str, role: str, password: str, must_change: bool = True) -> dict[str, Any]:
        username = (username or "").strip().casefold()
        if not re.fullmatch(r"[a-z0-9._-]{3,40}", username):
            raise AuthError("Benutzername: 3–40 Zeichen, nur a–z, 0–9, Punkt, Unterstrich, Bindestrich.", 422)
        if role not in ROLES:
            raise AuthError("Unbekannte Rolle.", 422)
        if self.db.one("SELECT id FROM users WHERE username = ?", (username,)):
            raise AuthError("Benutzername ist bereits vergeben.", 409)
        check_password_policy(password, username)
        uid = self.db.insert("users", {"username": username, "display_name": (display_name or username).strip(), "role": role,
                                       "password_hash": hash_password(password), "must_change_password": 1 if must_change else 0,
                                       "created_at": now_iso()})
        return self.public(self.get_user(uid))  # type: ignore[return-value]

    def update_user(self, user_id: int, payload: dict[str, Any], actor_id: int) -> dict[str, Any]:
        user = self.get_user(user_id)
        if not user:
            raise AuthError("Benutzer nicht gefunden.", 404)
        values: dict[str, Any] = {}
        if "display_name" in payload and payload["display_name"]:
            values["display_name"] = payload["display_name"].strip()
        if "role" in payload:
            if payload["role"] not in ROLES:
                raise AuthError("Unbekannte Rolle.", 422)
            if user_id == actor_id and payload["role"] != "admin" and user["role"] == "admin":
                raise AuthError("Sie können sich die Administrationsrolle nicht selbst entziehen.", 422)
            values["role"] = payload["role"]
        if "active" in payload:
            if user_id == actor_id and not payload["active"]:
                raise AuthError("Sie können Ihr eigenes Konto nicht deaktivieren.", 422)
            values["active"] = 1 if payload["active"] else 0
        if payload.get("unlock"):
            values.update({"failed_logins": 0, "locked_until": ""})
        if payload.get("reset_2fa"):
            values.update({"totp_secret": "", "totp_enabled": 0})
        if payload.get("new_password"):
            check_password_policy(payload["new_password"], user["username"])
            values.update({"password_hash": hash_password(payload["new_password"]), "must_change_password": 1})
        if values:
            self.db.update("users", user_id, values)
        if values.get("active") == 0 or payload.get("reset_2fa") or payload.get("new_password") or "role" in values:
            self.db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))  # Sitzungen beenden
        return self.public(self.get_user(user_id))  # type: ignore[return-value]

    def change_password(self, user_id: int, old: str, new: str) -> None:
        user = self.get_user(user_id)
        if not user or not verify_password(user["password_hash"], old):
            raise AuthError("Das bisherige Passwort ist falsch.", 422)
        if old == new:
            raise AuthError("Das neue Passwort muss sich vom bisherigen unterscheiden.", 422)
        check_password_policy(new, user["username"])
        self.db.update("users", user_id, {"password_hash": hash_password(new), "must_change_password": 0})

    # ------------------------------------------------------------------ Anmeldung
    def login(self, username: str, password: str, ip: str = "", user_agent: str = "") -> tuple[str, dict[str, Any]]:
        username = (username or "").strip().casefold()
        user = self.db.one("SELECT * FROM users WHERE username = ?", (username,))
        if not user:
            verify_password(_DUMMY_HASH, password or "")  # gleiche Laufzeit wie bei existierenden Konten
            raise AuthError("Benutzername oder Passwort ist falsch.")
        if user["locked_until"] and _utc(user["locked_until"]) > datetime.now(timezone.utc):
            raise AuthError(f"Konto nach mehreren Fehlversuchen vorübergehend gesperrt (bis {_utc(user['locked_until']).astimezone():%H:%M} Uhr).", 423)
        if not verify_password(user["password_hash"], password or ""):
            failed = user["failed_logins"] + 1
            values: dict[str, Any] = {"failed_logins": failed}
            if failed >= self.settings.max_failed_logins:
                values.update({"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=self.settings.lockout_minutes)).replace(microsecond=0).isoformat(),
                               "failed_logins": 0})
            self.db.update("users", user["id"], values)
            raise AuthError("Benutzername oder Passwort ist falsch.")
        if not user["active"]:
            raise AuthError("Dieses Konto ist deaktiviert.", 403)
        if _ph.check_needs_rehash(user["password_hash"]):
            self.db.update("users", user["id"], {"password_hash": hash_password(password)})
        self.db.update("users", user["id"], {"failed_logins": 0, "locked_until": ""})
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.db.insert("sessions", {"token_hash": _token_hash(token), "user_id": user["id"], "csrf_token": secrets.token_urlsafe(24),
                                    "mfa_passed": 0, "created_at": now.isoformat(), "last_seen": now.isoformat(),
                                    "expires_at": (now + timedelta(hours=self.settings.session_max_hours)).isoformat(),
                                    "ip": ip[:64], "user_agent": user_agent[:200]})
        return token, user

    def session(self, token: str | None) -> tuple[dict[str, Any], dict[str, Any]] | None:
        if not token:
            return None
        sess = self.db.one("SELECT * FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        if not sess:
            return None
        now = datetime.now(timezone.utc)
        if _utc(sess["expires_at"]) < now or _utc(sess["last_seen"]) + timedelta(minutes=self.settings.session_idle_minutes) < now:
            self.db.execute("DELETE FROM sessions WHERE id = ?", (sess["id"],))
            return None
        user = self.get_user(sess["user_id"])
        if not user or not user["active"]:
            return None
        if (now - _utc(sess["last_seen"])).total_seconds() > 60:
            self.db.update("sessions", sess["id"], {"last_seen": now.replace(microsecond=0).isoformat()})
        return sess, user

    def logout(self, token: str | None) -> None:
        if token:
            self.db.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

    def purge_sessions(self) -> None:
        self.db.execute("DELETE FROM sessions WHERE expires_at < ?", (now_iso(),))

    def needs_2fa_setup(self, user: dict[str, Any]) -> bool:
        return self.settings.require_2fa and not user["totp_enabled"]

    def session_state(self, sess: dict[str, Any], user: dict[str, Any]) -> str:
        """``ok`` | ``mfa`` (Code eingeben) | ``mfa_setup`` (2FA einrichten) | ``password`` (Passwort ändern)."""
        if user["totp_enabled"] and not sess["mfa_passed"]:
            return "mfa"
        if user["must_change_password"]:
            return "password"
        if self.needs_2fa_setup(user):
            return "mfa_setup"
        return "ok"

    def verify_mfa(self, sess: dict[str, Any], user: dict[str, Any], code: str) -> None:
        if not user["totp_enabled"]:
            raise AuthError("Für dieses Konto ist keine Zwei-Faktor-Anmeldung eingerichtet.", 422)
        counter = totp_counter(self.vault.decrypt_text(user["totp_secret"]), code)
        if counter is not None and counter <= int(user.get("totp_last") or 0):
            raise AuthError("Dieser Code wurde bereits verwendet – bitte den nächsten Code abwarten.", 422)
        if counter is None:
            failed = user["failed_logins"] + 1
            self.db.update("users", user["id"], {"failed_logins": failed})
            if failed >= self.settings.max_failed_logins:
                self.db.update("users", user["id"], {"failed_logins": 0, "locked_until": (datetime.now(timezone.utc) + timedelta(minutes=self.settings.lockout_minutes)).replace(microsecond=0).isoformat()})
                self.db.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
                raise AuthError("Zu viele falsche Codes – Konto vorübergehend gesperrt.", 423)
            raise AuthError("Der Code ist falsch oder abgelaufen.", 422)
        self.db.update("users", user["id"], {"failed_logins": 0, "last_login": now_iso(), "totp_last": counter})
        self.db.update("sessions", sess["id"], {"mfa_passed": 1})

    def begin_totp_setup(self, user: dict[str, Any]) -> dict[str, str]:
        secret = new_totp_secret()
        self.db.update("users", user["id"], {"totp_secret": self.vault.encrypt_text(secret), "totp_enabled": 0})
        uri = totp_uri(secret, user["username"])
        return {"secret": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)), "uri": uri, "qr_svg": qr_svg(uri)}

    def confirm_totp_setup(self, sess: dict[str, Any], user: dict[str, Any], code: str) -> None:
        if not user["totp_secret"]:
            raise AuthError("Bitte die Einrichtung zuerst starten.", 422)
        counter = totp_counter(self.vault.decrypt_text(user["totp_secret"]), code)
        if counter is None:
            raise AuthError("Der Code passt nicht. Uhrzeit des Smartphones prüfen und erneut versuchen.", 422)
        self.db.update("users", user["id"], {"totp_enabled": 1, "last_login": now_iso(), "totp_last": counter})
        self.db.execute("DELETE FROM sessions WHERE user_id = ? AND id != ?", (user["id"], sess["id"]))
        self.db.update("sessions", sess["id"], {"mfa_passed": 1})

    def mark_login(self, user: dict[str, Any]) -> None:
        self.db.update("users", user["id"], {"last_login": now_iso()})
