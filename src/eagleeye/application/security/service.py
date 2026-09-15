from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import urlencode, urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from eagleeye_pro.core.database import dumps, new_id, now_ts


class SecurityConfigurationError(ValueError):
    pass


class SecurityAccessError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class RuntimeSession:
    token_hash: str
    created_epoch: float
    last_seen_epoch: float
    expires_epoch: float
    client_fingerprint: str = ""


class InvestigatorProtection124Service:
    """Build 124 investigator-protection boundary.

    The service reduces investigator exposure through local access locking,
    case-separated Firefox profiles, fail-closed external-provider egress and
    encrypted local secret storage. It deliberately does not claim anonymity or
    untraceability; endpoint compromise, ISP visibility, account logins and
    behavioural fingerprinting remain outside any absolute guarantee.
    """

    MODES = {"standard", "hardened", "proxy_required"}
    BROWSER_MODES = {"isolated_firefox", "system_browser"}
    PROXY_MODES = {"none", "socks5", "http"}
    SECRET_ENV = {
        "brave_api_key": "EAGLEEYE_BRAVE_API_KEY",
        "ollama_api_key": "OLLAMA_API_KEY",
        "companies_house_api_key": "EAGLEEYE_COMPANIES_HOUSE_API_KEY",
        "orcid_access_token": "EAGLEEYE_ORCID_ACCESS_TOKEN",
        "courtlistener_token": "EAGLEEYE_COURTLISTENER_TOKEN",
        "github_token": "EAGLEEYE_GITHUB_TOKEN",
        "google_books_api_key": "EAGLEEYE_GOOGLE_BOOKS_API_KEY",
    }
    APPROVAL_PHRASE = "NETZZUGRIFF FREIGEBEN"
    PASS_MIN_LENGTH = 12

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        *,
        launcher: Callable[[list[str]], Any] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.security_dir = self.base_dir / "data" / "security_124_0"
        self.profile_root = self.security_dir / "firefox_compartments"
        self.security_dir.mkdir(parents=True, exist_ok=True)
        self.profile_root.mkdir(parents=True, exist_ok=True)
        self._chmod(self.security_dir, 0o700)
        self._chmod(self.profile_root, 0o700)
        self.launcher = launcher or self._default_launcher
        self.clock = clock or time.time
        self._session_lock = threading.RLock()
        self._sessions: dict[str, RuntimeSession] = {}
        self._redirect_lock = threading.RLock()
        self._research_redirects: dict[str, tuple[str, str, str, float]] = {}
        self._ensure_default_settings()
        self._apply_proxy_environment()

    @staticmethod
    def _chmod(path: Path, mode: int) -> None:
        try:
            path.chmod(mode)
        except OSError:
            pass

    def _ensure_default_settings(self) -> None:
        now = now_ts()
        self.db.execute(
            """INSERT OR IGNORE INTO investigator_security_settings_124(
            settings_id,created_at,updated_at) VALUES('global',?,?)""",
            (now, now),
        )

    def _event(self, event_type: str, *, case_id: str | None = None, severity: str = "info", details: dict[str, Any] | None = None) -> str:
        event_id = new_id("sec124")
        safe = dict(details or {})
        for key in tuple(safe):
            if any(mark in key.casefold() for mark in ("password", "passphrase", "secret", "token", "api_key")):
                safe[key] = "[redacted]"
        self.db.execute(
            "INSERT INTO investigator_security_events_124(event_id,case_id,event_type,severity,details_json,created_at) VALUES(?,?,?,?,?,?)",
            (event_id, case_id, event_type, severity, dumps(safe), now_ts()),
        )
        self.audit.log("security", "investigator_protection_124", event_id, case_id, {"event_type": event_type, "severity": severity, **safe})
        return event_id

    def settings(self) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM investigator_security_settings_124 WHERE settings_id='global'") or {}
        result = dict(row)
        for key in (
            "access_lock_enabled", "proxy_remote_dns", "block_external_provider_network",
            "allow_default_browser_fallback", "clear_profile_before_launch",
            "ephemeral_profile_per_launch", "session_bind_client", "panic_purge_profiles",
        ):
            result[key] = bool(result.get(key))
        result.pop("passphrase_salt", None)
        result.pop("passphrase_verifier", None)
        result["passphrase_configured"] = bool(row.get("passphrase_salt") and row.get("passphrase_verifier"))
        return result

    def configure(
        self,
        *,
        protection_mode: str,
        research_browser_mode: str,
        proxy_mode: str,
        proxy_host: str = "",
        proxy_port: int = 0,
        proxy_remote_dns: bool = True,
        block_external_provider_network: bool = True,
        allow_default_browser_fallback: bool = False,
        clear_profile_before_launch: bool = True,
        ephemeral_profile_per_launch: bool = True,
        session_bind_client: bool = True,
        panic_purge_profiles: bool = True,
        session_timeout_minutes: int = 20,
        actor: str = "local-analyst",
    ) -> dict[str, Any]:
        protection_mode = protection_mode.strip().casefold()
        research_browser_mode = research_browser_mode.strip().casefold()
        proxy_mode = proxy_mode.strip().casefold()
        if protection_mode not in self.MODES:
            raise SecurityConfigurationError("Unbekannter Schutzmodus")
        if research_browser_mode not in self.BROWSER_MODES:
            raise SecurityConfigurationError("Unbekannter Browsermodus")
        if proxy_mode not in self.PROXY_MODES:
            raise SecurityConfigurationError("Unbekannter Proxymodus")
        proxy_host = proxy_host.strip()
        proxy_port = int(proxy_port or 0)
        if proxy_mode != "none":
            if not re.fullmatch(r"[A-Za-z0-9._:-]{1,253}", proxy_host) or not 1 <= proxy_port <= 65535:
                raise SecurityConfigurationError("Proxy-Host oder -Port ist ungültig")
        else:
            proxy_host, proxy_port = "", 0
        if protection_mode == "proxy_required" and proxy_mode == "none":
            raise SecurityConfigurationError("Proxy-required benötigt einen konfigurierten Proxy")
        timeout = max(5, min(int(session_timeout_minutes), 240))
        self.db.execute(
            """UPDATE investigator_security_settings_124 SET protection_mode=?,research_browser_mode=?,
            proxy_mode=?,proxy_host=?,proxy_port=?,proxy_remote_dns=?,block_external_provider_network=?,
            allow_default_browser_fallback=?,clear_profile_before_launch=?,ephemeral_profile_per_launch=?,
            session_bind_client=?,panic_purge_profiles=?,session_timeout_minutes=?,updated_at=?
            WHERE settings_id='global'""",
            (
                protection_mode, research_browser_mode, proxy_mode, proxy_host, proxy_port,
                int(bool(proxy_remote_dns)), int(bool(block_external_provider_network)),
                int(bool(allow_default_browser_fallback)), int(bool(clear_profile_before_launch)),
                int(bool(ephemeral_profile_per_launch)), int(bool(session_bind_client)),
                int(bool(panic_purge_profiles)), timeout, now_ts(),
            ),
        )
        self._apply_proxy_environment()
        self._event("configuration_updated", details={"actor": actor, "protection_mode": protection_mode, "browser_mode": research_browser_mode, "proxy_mode": proxy_mode, "external_provider_blocked": bool(block_external_provider_network)})
        return self.settings()

    @staticmethod
    def _derive_passphrase(passphrase: str, salt: bytes) -> bytes:
        return hashlib.scrypt(passphrase.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)

    def set_access_passphrase(self, *, new_passphrase: str, current_passphrase: str = "", actor: str = "local-analyst") -> dict[str, Any]:
        row = self.db.one("SELECT * FROM investigator_security_settings_124 WHERE settings_id='global'") or {}
        if row.get("passphrase_verifier") and not self.verify_passphrase(current_passphrase, record_attempt=False):
            raise SecurityAccessError("Aktuelle Passphrase ist falsch")
        if len(new_passphrase) < self.PASS_MIN_LENGTH or new_passphrase.casefold() in {"password1234", "passwort1234", "eagleeye1234"}:
            raise SecurityConfigurationError(f"Passphrase muss mindestens {self.PASS_MIN_LENGTH} Zeichen lang und nicht trivial sein")
        salt = secrets.token_bytes(16)
        verifier = self._derive_passphrase(new_passphrase, salt)
        self.db.execute(
            """UPDATE investigator_security_settings_124 SET access_lock_enabled=1,passphrase_salt=?,
            passphrase_verifier=?,failed_attempts=0,lock_until_epoch=0,updated_at=? WHERE settings_id='global'""",
            (base64.b64encode(salt).decode("ascii"), base64.b64encode(verifier).decode("ascii"), now_ts()),
        )
        self.invalidate_sessions()
        self._event("access_lock_enabled", details={"actor": actor})
        return self.settings()

    def disable_access_lock(self, *, current_passphrase: str, actor: str = "local-analyst") -> dict[str, Any]:
        if not self.verify_passphrase(current_passphrase, record_attempt=True):
            raise SecurityAccessError("Passphrase ist falsch")
        self.db.execute(
            """UPDATE investigator_security_settings_124 SET access_lock_enabled=0,failed_attempts=0,
            lock_until_epoch=0,updated_at=? WHERE settings_id='global'""",
            (now_ts(),),
        )
        self.invalidate_sessions()
        self._event("access_lock_disabled", severity="warning", details={"actor": actor})
        return self.settings()

    def verify_passphrase(self, passphrase: str, *, record_attempt: bool = True) -> bool:
        row = self.db.one("SELECT * FROM investigator_security_settings_124 WHERE settings_id='global'") or {}
        if not row.get("passphrase_verifier"):
            return False
        now = int(self.clock())
        if int(row.get("lock_until_epoch") or 0) > now:
            if record_attempt:
                self._event("login_blocked_rate_limit", severity="warning", details={"remaining_seconds": int(row["lock_until_epoch"]) - now})
            return False
        try:
            expected = base64.b64decode(row["passphrase_verifier"])
            salt = base64.b64decode(row["passphrase_salt"])
            candidate = self._derive_passphrase(passphrase, salt)
            ok = hmac.compare_digest(expected, candidate)
        except Exception:
            ok = False
        if record_attempt:
            if ok:
                self.db.execute("UPDATE investigator_security_settings_124 SET failed_attempts=0,lock_until_epoch=0 WHERE settings_id='global'")
                self._event("login_succeeded")
            else:
                failures = int(row.get("failed_attempts") or 0) + 1
                lock_until = now + min(900, 2 ** min(failures, 9)) if failures >= 5 else 0
                self.db.execute("UPDATE investigator_security_settings_124 SET failed_attempts=?,lock_until_epoch=? WHERE settings_id='global'", (failures, lock_until))
                self._event("login_failed", severity="warning", details={"failed_attempts": failures, "rate_limited": bool(lock_until)})
        return ok

    def issue_session(self, client_fingerprint: str = "") -> tuple[str, int]:
        settings = self.settings()
        timeout = int(settings.get("session_timeout_minutes") or 20) * 60
        token = secrets.token_urlsafe(48)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = self.clock()
        bound = str(client_fingerprint or "") if settings.get("session_bind_client") else ""
        with self._session_lock:
            self._sessions[digest] = RuntimeSession(digest, now, now, now + timeout, bound)
        return token, timeout

    def validate_session(self, token: str, *, touch: bool = True, client_fingerprint: str = "") -> bool:
        if not token:
            return False
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = self.clock()
        timeout = int(self.settings().get("session_timeout_minutes") or 20) * 60
        with self._session_lock:
            session = self._sessions.get(digest)
            if not session or session.expires_epoch < now or now - session.last_seen_epoch > timeout:
                self._sessions.pop(digest, None)
                return False
            supplied = str(client_fingerprint or "")
            if session.client_fingerprint and not hmac.compare_digest(session.client_fingerprint, supplied):
                self._event("session_binding_mismatch", severity="warning")
                return False
            if touch:
                self._sessions[digest] = RuntimeSession(session.token_hash, session.created_epoch, now, now + timeout, session.client_fingerprint)
            return True

    def invalidate_sessions(self) -> None:
        with self._session_lock:
            self._sessions.clear()

    def _apply_proxy_environment(self) -> None:
        settings = self.settings()
        if settings.get("proxy_mode") == "http" and settings.get("proxy_host") and int(settings.get("proxy_port") or 0):
            os.environ["EAGLEEYE_OUTBOUND_PROXY"] = f"http://{settings['proxy_host']}:{int(settings['proxy_port'])}"
        else:
            os.environ.pop("EAGLEEYE_OUTBOUND_PROXY", None)

    # ---------- encrypted local vault ----------
    def _master_key_path(self) -> Path:
        return self.security_dir / "vault_master.key"

    def _load_master_key(self) -> bytes:
        path = self._master_key_path()
        if path.exists():
            raw = path.read_bytes()
            if raw.startswith(b"DPAPI1:") and os.name == "nt":
                return self._dpapi_unprotect(base64.b64decode(raw.split(b":", 1)[1]))
            if raw.startswith(b"RAW1:"):
                return base64.b64decode(raw.split(b":", 1)[1])
            raise SecurityAccessError("Unbekanntes Master-Key-Format")
        key = AESGCM.generate_key(bit_length=256)
        if os.name == "nt":
            payload = b"DPAPI1:" + base64.b64encode(self._dpapi_protect(key))
        else:
            payload = b"RAW1:" + base64.b64encode(key)
        path.write_bytes(payload)
        self._chmod(path, 0o600)
        return key

    @staticmethod
    def _dpapi_protect(data: bytes) -> bytes:
        if os.name != "nt":
            return data
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

        def blob(payload: bytes) -> tuple[DATA_BLOB, Any]:
            buffer = ctypes.create_string_buffer(payload)
            return DATA_BLOB(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
        ]
        crypt32.CryptProtectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        in_blob, in_buffer = blob(data)
        entropy_blob, entropy_buffer = blob(b"EagleEye-PersonOSINT-Pro-124")
        out_blob = DATA_BLOB()
        ok = crypt32.CryptProtectData(
            ctypes.byref(in_blob), "EagleEye Investigator Vault 124", ctypes.byref(entropy_blob),
            None, None, 0x1, ctypes.byref(out_blob),
        )
        _ = (in_buffer, entropy_buffer)  # keep buffers alive for the native call
        if not ok:
            raise OSError(ctypes.get_last_error(), "Windows DPAPI CryptProtectData failed")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)

    @staticmethod
    def _dpapi_unprotect(data: bytes) -> bytes:
        if os.name != "nt":
            return data
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

        def blob(payload: bytes) -> tuple[DATA_BLOB, Any]:
            buffer = ctypes.create_string_buffer(payload)
            return DATA_BLOB(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(DATA_BLOB),
            ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
        ]
        crypt32.CryptUnprotectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        in_blob, in_buffer = blob(data)
        entropy_blob, entropy_buffer = blob(b"EagleEye-PersonOSINT-Pro-124")
        out_blob = DATA_BLOB()
        description = wintypes.LPWSTR()
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob), ctypes.byref(description), ctypes.byref(entropy_blob),
            None, None, 0x1, ctypes.byref(out_blob),
        )
        _ = (in_buffer, entropy_buffer)
        if not ok:
            raise OSError(ctypes.get_last_error(), "Windows DPAPI CryptUnprotectData failed")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            if description:
                kernel32.LocalFree(description)
            kernel32.LocalFree(out_blob.pbData)

    def set_secret(self, name: str, value: str) -> None:
        clean_name = name.strip().casefold()
        if not re.fullmatch(r"[a-z0-9_.-]{3,80}", clean_name):
            raise SecurityConfigurationError("Ungültiger Secret-Name")
        if not value:
            self.db.execute("DELETE FROM encrypted_secrets_124 WHERE secret_name=?", (clean_name,))
            return
        key = self._load_master_key()
        nonce = secrets.token_bytes(12)
        aad = f"eagleeye124:{clean_name}".encode("utf-8")
        ciphertext = AESGCM(key).encrypt(nonce, value.encode("utf-8"), aad)
        now = now_ts()
        self.db.execute(
            """INSERT INTO encrypted_secrets_124(secret_name,nonce_b64,ciphertext_b64,aad_sha256,created_at,updated_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(secret_name) DO UPDATE SET nonce_b64=excluded.nonce_b64,
            ciphertext_b64=excluded.ciphertext_b64,aad_sha256=excluded.aad_sha256,updated_at=excluded.updated_at""",
            (clean_name, base64.b64encode(nonce).decode("ascii"), base64.b64encode(ciphertext).decode("ascii"), hashlib.sha256(aad).hexdigest(), now, now),
        )
        self._event("secret_updated", details={"secret_name": clean_name})

    def get_secret(self, name: str) -> str:
        clean_name = name.strip().casefold()
        row = self.db.one("SELECT * FROM encrypted_secrets_124 WHERE secret_name=?", (clean_name,))
        if not row:
            return ""
        aad = f"eagleeye124:{clean_name}".encode("utf-8")
        if not hmac.compare_digest(hashlib.sha256(aad).hexdigest(), row["aad_sha256"]):
            raise SecurityAccessError("Secret-AAD-Integrität verletzt")
        return AESGCM(self._load_master_key()).decrypt(base64.b64decode(row["nonce_b64"]), base64.b64decode(row["ciphertext_b64"]), aad).decode("utf-8")

    def save_provider_secret(self, name: str, value: str) -> None:
        if name not in self.SECRET_ENV:
            raise SecurityConfigurationError("Nicht unterstütztes Provider-Secret")
        self.set_secret(name, value)
        # Canonical Build 124 consumers resolve secrets directly from this vault.
        # Do not copy them into the process environment, where child processes
        # and same-user diagnostics could inherit them.
        os.environ.pop(self.SECRET_ENV[name], None)

    # ---------- provider egress ----------
    def authorize_egress(self, *, case_id: str, provider: str, purpose: str, approved_by: str, confirmation: str, minutes: int = 15) -> dict[str, Any]:
        provider = provider.strip().casefold()
        if provider == "browser_queue":
            raise SecurityConfigurationError("Browser-Queue benötigt keine externe Providerfreigabe")
        if confirmation.strip() != self.APPROVAL_PHRASE:
            raise SecurityAccessError("Freigabephrase fehlt")
        if len(purpose.strip()) < 12 or not approved_by.strip():
            raise SecurityConfigurationError("Dokumentierter Zweck und Freigebender sind erforderlich")
        expires = int(self.clock()) + max(5, min(int(minutes), 60)) * 60
        approval_id = new_id("egress124")
        self.db.execute(
            "INSERT INTO provider_egress_approvals_124(approval_id,case_id,provider,purpose,approved_by,status,expires_epoch,created_at) VALUES(?,?,?,?,?,'approved_once',?,?)",
            (approval_id, case_id, provider, purpose.strip(), approved_by.strip(), expires, now_ts()),
        )
        self._event("provider_egress_approved", case_id=case_id, severity="warning", details={"provider": provider, "approval_id": approval_id, "expires_epoch": expires})
        return self.db.one("SELECT * FROM provider_egress_approvals_124 WHERE approval_id=?", (approval_id,)) or {}

    def require_provider_egress(self, *, case_id: str, provider: str) -> str:
        provider = provider.strip().casefold()
        if provider == "browser_queue":
            return "browser_queue"
        settings = self.settings()
        if settings.get("protection_mode") == "proxy_required" and settings.get("proxy_mode") != "http":
            raise SecurityAccessError("Proxy-required blockiert Prozess-Providerverkehr ohne HTTP-Proxy. Nutze Browser-Queue oder konfiguriere einen geprüften HTTP-Proxy; SOCKS5 wird nur im isolierten Firefox mit Remote-DNS verwendet.")
        if not settings.get("block_external_provider_network"):
            return "policy_allows"
        now = int(self.clock())
        row = self.db.one(
            """SELECT * FROM provider_egress_approvals_124 WHERE case_id=? AND provider=?
            AND status='approved_once' AND expires_epoch>=? ORDER BY created_at DESC LIMIT 1""",
            (case_id, provider, now),
        )
        if not row:
            raise SecurityAccessError("Externer Providerzugang ist im Ermittlerschutz blockiert. Erstelle zuerst unter Sicherheit eine einmalige Netzfreigabe oder nutze Browser-Queue.")
        return str(row["approval_id"])

    def reserve_provider_egress(self, *, case_id: str, provider: str) -> str:
        approval_id = self.require_provider_egress(case_id=case_id, provider=provider)
        if approval_id in {"browser_queue", "policy_allows", ""}:
            return approval_id
        now = int(self.clock())
        with self.db.transaction(immediate=True):
            cur = self.db.execute(
                """UPDATE provider_egress_approvals_124 SET status='reserved',consumed_at=?
                WHERE approval_id=? AND case_id=? AND provider=? AND status='approved_once' AND expires_epoch>=?""",
                (now_ts(), approval_id, case_id, provider.strip().casefold(), now),
            )
            if cur.rowcount != 1:
                raise SecurityAccessError("Netzfreigabe wird bereits verwendet, ist abgelaufen oder wurde verbraucht")
        self._event("provider_egress_reserved", case_id=case_id, details={"provider": provider.strip().casefold(), "approval_id": approval_id})
        return approval_id

    def release_provider_egress(self, approval_id: str) -> None:
        if approval_id in {"browser_queue", "policy_allows", ""}:
            return
        now = int(self.clock())
        cur = self.db.execute(
            """UPDATE provider_egress_approvals_124 SET status='approved_once',consumed_at=''
            WHERE approval_id=? AND status='reserved' AND expires_epoch>=?""",
            (approval_id, now),
        )
        if cur.rowcount == 1:
            row = self.db.one("SELECT case_id,provider FROM provider_egress_approvals_124 WHERE approval_id=?", (approval_id,)) or {}
            self._event("provider_egress_released", case_id=row.get("case_id"), details={"provider": row.get("provider", ""), "approval_id": approval_id})

    def consume_provider_egress(self, approval_id: str) -> None:
        if approval_id in {"browser_queue", "policy_allows", ""}:
            return
        cur = self.db.execute(
            "UPDATE provider_egress_approvals_124 SET status='consumed',consumed_at=? WHERE approval_id=? AND status IN ('reserved','approved_once')",
            (now_ts(), approval_id),
        )
        if cur.rowcount != 1:
            raise SecurityAccessError("Netzfreigabe wurde bereits verbraucht oder ist abgelaufen")

    # ---------- protected research browser ----------
    @staticmethod
    def _firefox_candidates() -> Iterable[Path]:
        env = os.environ.get("FIREFOX_PATH", "").strip()
        if env:
            yield Path(env)
        found = shutil.which("firefox") or shutil.which("firefox.exe")
        if found:
            yield Path(found)
        if os.name == "nt":
            for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
                if base:
                    yield Path(base) / "Mozilla Firefox" / "firefox.exe"

    def _find_firefox(self) -> Path | None:
        for candidate in self._firefox_candidates():
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _default_launcher(command: list[str]) -> Any:
        return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)

    def _compartment(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM investigator_case_compartments_124 WHERE case_id=?", (case_id,))
        if row:
            return row
        profile_token = secrets.token_hex(16)
        rel = f"firefox_compartments/{profile_token}"
        compartment_id = new_id("comp124")
        now = now_ts()
        self.db.execute(
            "INSERT INTO investigator_case_compartments_124(compartment_id,case_id,profile_token,profile_relpath,created_at) VALUES(?,?,?,?,?)",
            (compartment_id, case_id, profile_token, rel, now),
        )
        return self.db.one("SELECT * FROM investigator_case_compartments_124 WHERE compartment_id=?", (compartment_id,)) or {}

    def rotate_case_compartment(self, case_id: str, *, actor: str = "local-analyst", purge_old: bool = True) -> dict[str, Any]:
        existing = self._compartment(case_id)
        old_profile = self.security_dir / existing["profile_relpath"]
        token = secrets.token_hex(16)
        rel = f"firefox_compartments/{token}"
        with self.db.transaction(immediate=True):
            self.db.execute(
                "UPDATE investigator_case_compartments_124 SET profile_token=?,profile_relpath=?,rotation_count=rotation_count+1,last_used_at=? WHERE compartment_id=? AND case_id=?",
                (token, rel, now_ts(), existing["compartment_id"], case_id),
            )
        if purge_old:
            shutil.rmtree(old_profile, ignore_errors=True)
        rotated = self.db.one("SELECT * FROM investigator_case_compartments_124 WHERE case_id=?", (case_id,)) or {}
        self._event("research_compartment_rotated", case_id=case_id, details={"actor": actor, "purged_old": bool(purge_old), "rotation_count": rotated.get("rotation_count", 0)})
        return rotated

    def emergency_lockdown(self, *, case_id: str | None = None, actor: str = "local-analyst", purge_profiles: bool | None = None) -> dict[str, Any]:
        settings = self.settings()
        should_purge = bool(settings.get("panic_purge_profiles")) if purge_profiles is None else bool(purge_profiles)
        self.invalidate_sessions()
        with self._redirect_lock:
            redirect_count = len(self._research_redirects)
            self._research_redirects.clear()
        if case_id:
            self.db.execute("UPDATE provider_egress_approvals_124 SET status='revoked' WHERE case_id=? AND status IN ('approved_once','reserved')", (case_id,))
            compartments = self.db.all("SELECT * FROM investigator_case_compartments_124 WHERE case_id=?", (case_id,))
        else:
            self.db.execute("UPDATE provider_egress_approvals_124 SET status='revoked' WHERE status IN ('approved_once','reserved')")
            compartments = self.db.all("SELECT * FROM investigator_case_compartments_124")
        purged = 0
        if should_purge:
            for item in compartments:
                profile = self.security_dir / item["profile_relpath"]
                if profile.exists():
                    shutil.rmtree(profile, ignore_errors=True)
                    purged += 1
        self.db.execute("UPDATE investigator_security_settings_124 SET last_lockdown_at=?,updated_at=? WHERE settings_id='global'", (now_ts(), now_ts()))
        self._event("emergency_lockdown", case_id=case_id, severity="warning", details={"actor": actor, "profiles_purged": purged, "redirects_cleared": redirect_count})
        return {"locked": True, "profiles_purged": purged, "redirects_cleared": redirect_count}

    def _clear_profile_residue(self, profile: Path) -> None:
        files = (
            "cookies.sqlite", "cookies.sqlite-wal", "cookies.sqlite-shm", "places.sqlite", "places.sqlite-wal",
            "formhistory.sqlite", "permissions.sqlite", "content-prefs.sqlite", "webappsstore.sqlite",
            "sessionstore.jsonlz4", "sessionCheckpoints.json", "search.json.mozlz4",
        )
        dirs = ("cache2", "startupCache", "storage", "sessionstore-backups", "thumbnails", "saved-telemetry-pings")
        for name in files:
            try:
                (profile / name).unlink(missing_ok=True)
            except OSError:
                pass
        for name in dirs:
            shutil.rmtree(profile / name, ignore_errors=True)

    def _write_firefox_profile(self, case_id: str, *, persistent_session: bool = False) -> tuple[dict[str, Any], Path]:
        settings = self.settings()
        compartment = self._compartment(case_id)
        if not persistent_session and settings.get("ephemeral_profile_per_launch") and int(compartment.get("launch_count") or 0) > 0:
            compartment = self.rotate_case_compartment(case_id, actor="automatic-profile-rotation", purge_old=True)
        profile = self.security_dir / compartment["profile_relpath"]
        profile.mkdir(parents=True, exist_ok=True)
        self._chmod(profile, 0o700)
        if settings.get("clear_profile_before_launch") and not (persistent_session and int(compartment.get("launch_count") or 0) > 0):
            self._clear_profile_residue(profile)
        prefs: dict[str, Any] = {
            "browser.privatebrowsing.autostart": True,
            "browser.send_pings": False,
            "browser.formfill.enable": False,
            "browser.sessionstore.privacy_level": 2,
            "browser.sessionstore.resume_from_crash": False,
            "browser.safebrowsing.downloads.remote.enabled": False,
            "browser.urlbar.speculativeConnect.enabled": False,
            "datareporting.healthreport.uploadEnabled": False,
            "datareporting.policy.dataSubmissionEnabled": False,
            "dom.battery.enabled": False,
            "dom.event.clipboardevents.enabled": False,
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
            "privacy.clearOnShutdown.offlineApps": True,
            "privacy.clearOnShutdown.sessions": True,
            "privacy.clearOnShutdown_v2.cache": True,
            "privacy.clearOnShutdown_v2.cookiesAndStorage": True,
            "privacy.clearOnShutdown_v2.historyFormDataAndDownloads": True,
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
        proxy_mode = str(settings.get("proxy_mode") or "none")
        if proxy_mode != "none":
            host, port = str(settings.get("proxy_host") or ""), int(settings.get("proxy_port") or 0)
            prefs["network.proxy.type"] = 1
            if proxy_mode == "socks5":
                prefs.update({
                    "network.proxy.socks": host, "network.proxy.socks_port": port,
                    "network.proxy.socks_version": 5,
                    "network.proxy.socks_remote_dns": bool(settings.get("proxy_remote_dns", True)),
                    "network.proxy.no_proxies_on": "",
                })
            else:
                prefs.update({
                    "network.proxy.http": host, "network.proxy.http_port": port,
                    "network.proxy.ssl": host, "network.proxy.ssl_port": port,
                    "network.proxy.no_proxies_on": "",
                })
        lines = []
        for key, value in sorted(prefs.items()):
            literal = json.dumps(value, ensure_ascii=False)
            lines.append(f"user_pref({json.dumps(key)}, {literal});")
        (profile / "user.js").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self._chmod(profile / "user.js", 0o600)
        return compartment, profile

    def _issue_research_redirect(self, *, case_id: str, task_id: str, destination_url: str, ttl_seconds: int = 90) -> str:
        token = secrets.token_urlsafe(40)
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._redirect_lock:
            now = self.clock()
            self._research_redirects = {
                key: value for key, value in self._research_redirects.items() if value[3] >= now
            }
            self._research_redirects[digest] = (case_id, task_id, destination_url, now + max(15, min(int(ttl_seconds), 300)))
        return token

    def consume_research_redirect(self, token: str) -> str:
        if not token:
            raise SecurityAccessError("Recherche-Weiterleitung fehlt")
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._redirect_lock:
            item = self._research_redirects.pop(digest, None)
        if not item or item[3] < self.clock():
            raise SecurityAccessError("Recherche-Weiterleitung ist ungültig oder abgelaufen")
        _case_id, _task_id, destination_url, _expires = item
        parts = urlsplit(destination_url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise SecurityAccessError("Ungültiges Ziel der Recherche-Weiterleitung")
        return destination_url

    @staticmethod
    def _validated_loopback_origin(origin: str) -> str:
        parts = urlsplit((origin or "").strip())
        host = (parts.hostname or "").casefold()
        if parts.scheme != "http" or host not in {"127.0.0.1", "localhost", "::1"} or not parts.port:
            raise SecurityConfigurationError("Lokale Recherche-Weiterleitung muss an einen expliziten Loopback-Port gebunden sein")
        return f"http://127.0.0.1:{parts.port}"

    def launch_research_task(
        self, *, case_id: str, task_id: str, actor: str = "local-analyst",
        local_redirect_origin: str = "http://127.0.0.1:8765",
    ) -> dict[str, Any]:
        task = self.db.one("SELECT * FROM search_tasks WHERE task_id=? AND case_id=?", (task_id, case_id))
        if not task:
            raise KeyError("Suchaufgabe nicht gefunden oder falscher Fall")
        parts = urlsplit(str(task.get("url") or ""))
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise SecurityAccessError("Geschützter Recherchebrowser erlaubt ausschließlich öffentliche HTTPS-Ziele ohne eingebettete Zugangsdaten")
        settings = self.settings()
        if settings.get("protection_mode") == "proxy_required" and settings.get("proxy_mode") == "none":
            raise SecurityAccessError("Proxy-required ist aktiv, aber kein Proxy konfiguriert")
        compartment, profile = self._write_firefox_profile(case_id)
        launch_id = new_id("launch124")
        fingerprint = hashlib.sha256(str(task["url"]).encode("utf-8")).hexdigest()
        firefox = self._find_firefox()
        mode = str(settings.get("research_browser_mode") or "isolated_firefox")
        try:
            if mode == "isolated_firefox":
                if firefox is None:
                    raise SecurityAccessError("Firefox wurde nicht gefunden. Aus Schutzgründen erfolgt kein automatischer Rückfall auf das normale Browserprofil.")
                origin = self._validated_loopback_origin(local_redirect_origin)
                redirect_ticket = self._issue_research_redirect(
                    case_id=case_id, task_id=task_id, destination_url=str(task["url"]),
                )
                local_url = origin + "/security/research-redirect?" + urlencode({"ticket": redirect_ticket})
                command = [str(firefox), "-no-remote", "-profile", str(profile), "-private-window", local_url]
                self.launcher(command)
            else:
                if not settings.get("allow_default_browser_fallback"):
                    raise SecurityAccessError("Systembrowser ist im Ermittlerschutz nicht freigegeben")
                import webbrowser
                if not webbrowser.open_new_tab(str(task["url"])):
                    raise SecurityAccessError("Systembrowser konnte nicht geöffnet werden")
            self.db.execute("UPDATE search_tasks SET status='opened' WHERE task_id=? AND case_id=?", (task_id, case_id))
            self.db.execute(
                "INSERT INTO protected_research_launches_124(launch_id,case_id,task_id,compartment_id,browser_mode,destination_host,destination_fingerprint,status,launched_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (launch_id, case_id, task_id, compartment["compartment_id"], mode, parts.hostname.casefold(), fingerprint, "launched", now_ts()),
            )
            self.db.execute("UPDATE investigator_case_compartments_124 SET last_used_at=?,launch_count=launch_count+1 WHERE compartment_id=?", (now_ts(), compartment["compartment_id"]))
            self._event("protected_research_launched", case_id=case_id, details={"task_id": task_id, "launch_id": launch_id, "destination_host": parts.hostname.casefold(), "browser_mode": mode, "actor": actor})
            return {"launch_id": launch_id, "status": "launched", "browser_mode": mode, "destination_host": parts.hostname.casefold(), "compartment_id": compartment["compartment_id"]}
        except Exception as exc:
            self.db.execute(
                "INSERT INTO protected_research_launches_124(launch_id,case_id,task_id,compartment_id,browser_mode,destination_host,destination_fingerprint,status,error_text,launched_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (launch_id, case_id, task_id, compartment["compartment_id"], mode, parts.hostname.casefold(), fingerprint, "blocked", str(exc)[:1000], now_ts()),
            )
            self._event("protected_research_blocked", case_id=case_id, severity="warning", details={"task_id": task_id, "destination_host": parts.hostname.casefold(), "error": str(exc)[:300]})
            raise


    def launch_research_tasks_parallel(
        self, *, case_id: str, seed_task_id: str, actor: str = "local-analyst",
        local_redirect_origin: str = "http://127.0.0.1:8765",
        preferred_engines: tuple[str, ...] = ("Google", "Bing", "DuckDuckGo", "Brave", "Startpage"),
        max_engines: int = 3,
    ) -> dict[str, Any]:
        """Open one person-specific query in up to three search engines at once.

        All URLs are validated, wrapped in one-time loopback tickets and opened in
        a single isolated Firefox process/profile so they appear as parallel tabs.
        """
        seed = self.db.one("SELECT * FROM search_tasks WHERE task_id=? AND case_id=?", (seed_task_id, case_id))
        if not seed:
            raise KeyError("Suchaufgabe nicht gefunden oder falscher Fall")
        query = str(seed.get("query") or "").strip()
        target_id = str(seed.get("target_id") or "")
        if not query:
            raise SecurityAccessError("Suchaufgabe enthält keine Suchanfrage")
        rows = self.db.all(
            "SELECT * FROM search_tasks WHERE case_id=? AND target_id=? AND query=? ORDER BY created_at DESC",
            (case_id, target_id, query),
        )
        by_engine = {}
        for row in rows:
            engine = str(row.get("engine") or "")
            if engine and engine not in by_engine:
                by_engine[engine] = row
        selected = [by_engine[e] for e in preferred_engines if e in by_engine][:max(1, min(int(max_engines), 5))]
        if len(selected) < 2:
            raise SecurityAccessError("Für diese Suchanfrage sind nicht genügend Suchmaschinen-Aufgaben vorhanden. Erzeuge das Paket mit mindestens fünf Engines neu.")
        settings = self.settings()
        if settings.get("protection_mode") == "proxy_required" and settings.get("proxy_mode") == "none":
            raise SecurityAccessError("Proxy-required ist aktiv, aber kein Proxy konfiguriert")
        compartment, profile = self._write_firefox_profile(case_id)
        firefox = self._find_firefox()
        mode = str(settings.get("research_browser_mode") or "isolated_firefox")
        if mode != "isolated_firefox":
            raise SecurityAccessError("Parallele Recherche ist nur im isolierten Firefox-Profil freigegeben")
        if firefox is None:
            raise SecurityAccessError("Firefox wurde nicht gefunden. Aus Schutzgründen erfolgt kein Rückfall auf das persönliche Browserprofil.")
        origin = self._validated_loopback_origin(local_redirect_origin)
        urls=[]
        hosts=[]
        for row in selected:
            parts=urlsplit(str(row.get("url") or ""))
            if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
                raise SecurityAccessError("Eine Suchmaschinen-URL ist für den geschützten Start ungültig")
            ticket=self._issue_research_redirect(case_id=case_id, task_id=str(row["task_id"]), destination_url=str(row["url"]))
            urls.append(origin + "/security/research-redirect?" + urlencode({"ticket": ticket}))
            hosts.append(parts.hostname.casefold())
        command=[str(firefox), "-no-remote", "-profile", str(profile), "-private-window", urls[0]]
        for url in urls[1:]:
            command.extend(["-new-tab", url])
        self.launcher(command)
        ts=now_ts()
        for row, host in zip(selected, hosts):
            self.db.execute("UPDATE search_tasks SET status='opened' WHERE task_id=? AND case_id=?", (row["task_id"], case_id))
            launch_id=new_id("launch127")
            fingerprint=hashlib.sha256(str(row["url"]).encode("utf-8")).hexdigest()
            self.db.execute(
                "INSERT INTO protected_research_launches_124(launch_id,case_id,task_id,compartment_id,browser_mode,destination_host,destination_fingerprint,status,launched_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (launch_id, case_id, row["task_id"], compartment["compartment_id"], mode, host, fingerprint, "launched", ts),
            )
        self.db.execute("UPDATE investigator_case_compartments_124 SET last_used_at=?,launch_count=launch_count+1 WHERE compartment_id=?", (ts, compartment["compartment_id"]))
        self._event("protected_parallel_research_launched", case_id=case_id, details={"seed_task_id": seed_task_id, "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(), "engines": [r.get("engine") for r in selected], "count": len(selected), "actor": actor})
        return {"status":"launched", "count":len(selected), "engines":[r.get("engine") for r in selected], "compartment_id":compartment["compartment_id"]}

    def launch_external_https(
        self, *, case_id: str, destination_url: str, tool_key: str, actor: str = "local-analyst",
        local_redirect_origin: str = "http://127.0.0.1:8765",
    ) -> dict[str, Any]:
        """Open a fixed external HTTPS tool in the protected case browser.

        No prompt, query, case identifier or other case content is appended to the
        destination. The local redirect ticket is one-time and short-lived.
        """
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError("Fall nicht gefunden")
        clean_tool = re.sub(r"[^a-z0-9_.-]", "", str(tool_key).strip().casefold())[:50]
        if not clean_tool:
            raise SecurityConfigurationError("Tool-Kennung fehlt")
        parts = urlsplit(str(destination_url or ""))
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise SecurityAccessError("Externes Werkzeug muss eine feste HTTPS-Adresse ohne Zugangsdaten, Query oder Fragment verwenden")
        settings = self.settings()
        if settings.get("protection_mode") == "proxy_required" and settings.get("proxy_mode") == "none":
            raise SecurityAccessError("Proxy-required ist aktiv, aber kein Proxy konfiguriert")
        compartment, profile = self._write_firefox_profile(case_id)
        firefox = self._find_firefox()
        mode = str(settings.get("research_browser_mode") or "isolated_firefox")
        launch_id = new_id("tool124")
        try:
            if mode == "isolated_firefox":
                if firefox is None:
                    raise SecurityAccessError("Firefox wurde nicht gefunden. Das externe Werkzeug wird nicht im persönlichen Browserprofil geöffnet.")
                origin = self._validated_loopback_origin(local_redirect_origin)
                redirect_ticket = self._issue_research_redirect(
                    case_id=case_id, task_id=f"external:{clean_tool}", destination_url=str(destination_url),
                )
                local_url = origin + "/security/research-redirect?" + urlencode({"ticket": redirect_ticket})
                command = [str(firefox), "-no-remote", "-profile", str(profile), "-private-window", local_url]
                self.launcher(command)
            else:
                if not settings.get("allow_default_browser_fallback"):
                    raise SecurityAccessError("Systembrowser ist im Ermittlerschutz nicht freigegeben")
                import webbrowser
                if not webbrowser.open_new_tab(str(destination_url)):
                    raise SecurityAccessError("Systembrowser konnte nicht geöffnet werden")
            self.db.execute(
                "UPDATE investigator_case_compartments_124 SET last_used_at=?,launch_count=launch_count+1 WHERE compartment_id=?",
                (now_ts(), compartment["compartment_id"]),
            )
            self._event(
                "protected_external_tool_launched", case_id=case_id,
                details={"launch_id": launch_id, "tool_key": clean_tool, "destination_host": parts.hostname.casefold(), "browser_mode": mode, "actor": actor},
            )
            return {"launch_id": launch_id, "status": "launched", "browser_mode": mode, "destination_host": parts.hostname.casefold(), "compartment_id": compartment["compartment_id"]}
        except Exception as exc:
            self._event(
                "protected_external_tool_blocked", case_id=case_id, severity="warning",
                details={"launch_id": launch_id, "tool_key": clean_tool, "destination_host": parts.hostname.casefold(), "error": str(exc)[:300]},
            )
            raise

    # ---------- evidence checkpoint ----------
    def _evidence_checkpoint_digest(self, case_id: str, previous_sha: str) -> tuple[str, list[dict[str, Any]]]:
        packages = self.db.all(
            "SELECT package_id,package_sha256,raw_sha256,metadata_sha256,status,candidate_only FROM evidence_packages_121 WHERE case_id=? ORDER BY package_id",
            (case_id,),
        )
        canonical = json.dumps({"case_id": case_id, "previous": previous_sha, "packages": packages}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), packages

    def create_evidence_checkpoint(self, *, case_id: str, actor: str) -> dict[str, Any]:
        previous = self.db.one("SELECT checkpoint_sha256 FROM evidence_trust_checkpoints_124 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", (case_id,))
        previous_sha = str((previous or {}).get("checkpoint_sha256") or "")
        checkpoint_sha, packages = self._evidence_checkpoint_digest(case_id, previous_sha)
        signing_key = self.get_secret("trust_checkpoint_key")
        if not signing_key:
            signing_key = secrets.token_urlsafe(48)
            self.set_secret("trust_checkpoint_key", signing_key)
        signature = hmac.new(signing_key.encode("utf-8"), checkpoint_sha.encode("ascii"), hashlib.sha256).hexdigest()
        checkpoint_id = new_id("trust124")
        self.db.execute(
            "INSERT INTO evidence_trust_checkpoints_124(checkpoint_id,case_id,package_count,checkpoint_sha256,previous_sha256,signature_hmac_sha256,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (checkpoint_id, case_id, len(packages), checkpoint_sha, previous_sha, signature, actor, now_ts()),
        )
        self._event("evidence_checkpoint_created", case_id=case_id, details={"checkpoint_id": checkpoint_id, "package_count": len(packages), "checkpoint_sha256": checkpoint_sha})
        return self.db.one("SELECT * FROM evidence_trust_checkpoints_124 WHERE checkpoint_id=?", (checkpoint_id,)) or {}

    def verify_evidence_checkpoints(self, case_id: str) -> dict[str, Any]:
        rows = self.db.all("SELECT * FROM evidence_trust_checkpoints_124 WHERE case_id=? ORDER BY created_at,checkpoint_id", (case_id,))
        key = self.get_secret("trust_checkpoint_key")
        previous = ""
        valid = bool(key) or not rows
        errors: list[str] = []
        for row in rows:
            if row["previous_sha256"] != previous:
                valid = False
                errors.append(f"chain:{row['checkpoint_id']}")
            expected = hmac.new(key.encode("utf-8"), row["checkpoint_sha256"].encode("ascii"), hashlib.sha256).hexdigest() if key else ""
            if not expected or not hmac.compare_digest(expected, row["signature_hmac_sha256"]):
                valid = False
                errors.append(f"signature:{row['checkpoint_id']}")
            previous = row["checkpoint_sha256"]
        current_matches_latest = True
        if rows:
            current_digest, _packages = self._evidence_checkpoint_digest(case_id, rows[-1]["previous_sha256"])
            current_matches_latest = hmac.compare_digest(current_digest, rows[-1]["checkpoint_sha256"])
            if not current_matches_latest:
                valid = False
                errors.append("evidence_changed_since_latest_checkpoint")
        return {"valid": valid, "checkpoint_count": len(rows), "latest_sha256": previous, "current_matches_latest": current_matches_latest, "errors": errors, "limitation": "Lokaler signierter Checkpoint; kein unabhängiger externer Zeitstempel."}

    def security_events(self, case_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if case_id:
            return self.db.all("SELECT * FROM investigator_security_events_124 WHERE case_id=? OR case_id IS NULL ORDER BY created_at DESC LIMIT ?", (case_id, int(limit)))
        return self.db.all("SELECT * FROM investigator_security_events_124 ORDER BY created_at DESC LIMIT ?", (int(limit),))

    def active_egress_approvals(self, case_id: str, limit: int = 30) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM provider_egress_approvals_124 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, int(limit)))

    def launches(self, case_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM protected_research_launches_124 WHERE case_id=? ORDER BY launched_at DESC LIMIT ?", (case_id, int(limit)))

    def assess(self, case_id: str | None = None) -> dict[str, Any]:
        settings = self.settings()
        findings: list[dict[str, Any]] = []
        score = 100
        def add(key: str, ok: bool, impact: int, detail: str) -> None:
            nonlocal score
            findings.append({"key": key, "ok": ok, "detail": detail})
            if not ok:
                score -= impact
        add("access_lock", bool(settings.get("access_lock_enabled")), 25, "Lokale Passphrase schützt vor fremdem Zugriff" if settings.get("access_lock_enabled") else "Zugriffsschutz ist noch nicht aktiviert")
        add("isolated_firefox", settings.get("research_browser_mode") == "isolated_firefox", 20, "Fallgetrenntes Firefox-Profil" if settings.get("research_browser_mode") == "isolated_firefox" else "Normales Browserprofil kann Ermittlerspuren vermischen")
        add("external_provider_gate", bool(settings.get("block_external_provider_network")), 15, "Externer Providerverkehr ist fail-closed" if settings.get("block_external_provider_network") else "Externe Provider dürfen ohne zusätzliche Netzfreigabe senden")
        add("no_browser_fallback", not bool(settings.get("allow_default_browser_fallback")), 10, "Kein Rückfall auf das persönliche Browserprofil" if not settings.get("allow_default_browser_fallback") else "Systembrowser-Fallback ist aktiviert")
        add("profile_cleanup", bool(settings.get("clear_profile_before_launch")), 8, "Rechercheprofil wird vor dem Start bereinigt" if settings.get("clear_profile_before_launch") else "Profilreste bleiben zwischen Läufen erhalten")
        add("ephemeral_profiles", bool(settings.get("ephemeral_profile_per_launch")), 8, "Neues pseudonymes Firefox-Profil je Recherchelauf" if settings.get("ephemeral_profile_per_launch") else "Fallprofil wird zwischen mehreren Läufen wiederverwendet")
        add("session_binding", bool(settings.get("session_bind_client")), 6, "Geschützte Sitzung ist an den lokalen Browser-Fingerprint gebunden" if settings.get("session_bind_client") else "Sitzungstoken ist nicht an den lokalen Browser gebunden")
        add("panic_lock", bool(settings.get("panic_purge_profiles")), 6, "Notfallsperre verwirft Sitzungen, Freigaben und Profilreste" if settings.get("panic_purge_profiles") else "Notfallsperre verwirft Profilreste nicht automatisch")
        add("firefox_available", self._find_firefox() is not None, 10, "Firefox gefunden" if self._find_firefox() else "Firefox nicht gefunden; geschützte Recherche startet fail-closed")
        try:
            self._load_master_key()
            vault_ok = True
        except Exception:
            vault_ok = False
        add("vault", vault_ok, 20, "AES-GCM-Vault mit Windows-DPAPI-Schlüsselbindung" if os.name == "nt" and vault_ok else "AES-GCM-Vault mit lokal geschützter Schlüsseldatei" if vault_ok else "Vault-Schlüssel konnte nicht geladen werden")
        if settings.get("protection_mode") == "proxy_required":
            add("proxy", settings.get("proxy_mode") != "none", 30, "Proxy ist konfiguriert" if settings.get("proxy_mode") != "none" else "Proxy-required ohne Proxy")
        score = max(0, min(100, score))
        level = "strong" if score >= 85 else "review" if score >= 65 else "weak"
        return {
            "score": score, "level": level, "findings": findings, "settings": settings,
            "limitations": [
                "Keine Software kann vollständige Unverfolgbarkeit garantieren.",
                "ISP/VPN/Proxy-Betreiber, kompromittierte Endgeräte, Account-Logins und Verhaltensmuster können weiterhin Rückschlüsse ermöglichen.",
                "Der Schutzmodus ersetzt keine rechtliche Freigabe und keine organisatorische OPSEC.",
            ],
        }
