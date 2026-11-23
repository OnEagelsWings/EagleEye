"""EagleEye Vault: private Recherche-Website auf dem eigenen Rechner – verschlüsselt, nur lokal, Netz nur auf Befehl.

Ablauf
------
1. Start (``python -m personosint vault``): Der Server lauscht nur auf 127.0.0.1. Es gibt nur den Sperrbildschirm.
   Kein Datenbestand ist lesbar, das Netz ist geschlossen.
2. Erster Start: Einrichtung – Name, Passphrase, Zwei-Faktor-App, Wiederherstellungsschlüssel. Optional werden
   vorhandene PersonOSINT-Daten in den Vault übernommen.
3. Entsperren: Passphrase + Sechs-Stellen-Code → Datenbank wird entschlüsselt **in den Arbeitsspeicher** geladen,
   die gewohnte PersonOSINT-Oberfläche erscheint, mit Vault-Leiste (Status, Netzschalter, Sperren).
4. Recherche: „Netz öffnen“ für ein Zeitfenster → Quellen abfragen → das Netz schließt von selbst.
5. Sperren (Knopf, Strg+Alt+L, nach Untätigkeit oder beim Beenden): Daten werden verschlüsselt gespeichert, alles im
   Arbeitsspeicher verworfen, das Netz geschlossen.
"""
from __future__ import annotations

import io
import json
import logging
import secrets
import sqlite3
import threading
import time
import urllib.request
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable

from fastapi import Body, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from . import __version__, netgate
from .auth import new_totp_secret, qr_svg, totp_counter, totp_uri
from .config import Settings, default_data_dir
from .crypto import Vault
from .db import Database
from .vault import Opened, VaultError, VaultStore, WrongSecret, check_passphrase, fingerprint

log = logging.getLogger("eagleeye.vault")
STATIC = Path(__file__).parent / "static"
COOKIE = "ee_session"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY", "Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()", "Cache-Control": "no-store",
}
IDLE_CHOICES = (5, 10, 15, 30, 60)
TILE_UA = f"EagleEye-Vault/{__version__} (private research workstation)"


def default_vault_dir() -> Path:
    import os

    env = os.environ.get("EAGLEEYE_VAULT_DIR")
    if env:
        return Path(env)
    base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or Path.home() / ".local" / "share")
    return base / "EagleEye-Vault"


def _blank_tile(text: str) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (256, 256), (226, 232, 240))
    draw = ImageDraw.Draw(img)
    draw.text((14, 118), text, fill=(71, 85, 105))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


class VaultManager:
    """Zustand des Vaults: gesperrt oder geöffnet (dann mit innerer Anwendung, Datenbank, Speicher-Thread)."""

    def __init__(self, folder: Path, *, http=None, kdf: dict | None = None, gate: netgate.NetGate | None = None,
                 classic_dir: Path | None = None, clock: Callable[[], float] = time.time, autosave_seconds: float = 2.0):
        self.store = VaultStore(folder, kdf=kdf)
        self.gate = gate or netgate.GATE
        self.http = http
        self.classic_dir = Path(classic_dir) if classic_dir else default_data_dir()
        self.clock = clock
        self.autosave_seconds = autosave_seconds
        self._lock = threading.RLock()
        self.opened: Opened | None = None
        self.inner = None
        self.db: Database | None = None
        self._saved_changes = -1
        self.last_saved = 0.0
        self.last_activity = 0.0
        self.lock_reason = ""
        self._pending_setup: dict[str, Any] | None = None
        self._tiles: OrderedDict[str, bytes] = OrderedDict()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------ Hintergrund: Speichern, Auto-Sperre, Überwachung
    def start_background(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._loop, name="eagleeye-vault", daemon=True)
        self._thread.start()

    def stop_background(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        last_monitor = 0.0
        while not self._stop.wait(self.autosave_seconds):
            try:
                self.tick()
                if self.opened and self.gate.is_open() and self.clock() - last_monitor > 60:
                    last_monitor = self.clock()
                    from . import monitor

                    monitor.run_due(self.inner.state.platform)
            except Exception:  # noqa: BLE001 - der Hintergrund darf nie sterben
                log.exception("Vault-Hintergrundaufgabe fehlgeschlagen")

    def tick(self) -> None:
        """Speichert Änderungen und sperrt nach Untätigkeit (wird alle paar Sekunden aufgerufen)."""
        with self._lock:
            if not self.opened:
                return
            idle = int(self.opened.owner.get("idle_minutes", 15)) * 60
            if self.clock() - self.last_activity > idle:
                self.lock(f"Automatisch gesperrt nach {idle // 60} Minuten ohne Eingabe")
                return
            self.save()

    # ------------------------------------------------------------------ Zustand
    @property
    def unlocked(self) -> bool:
        return self.opened is not None

    def status(self) -> dict[str, Any]:
        info = self.store.public_info()
        # Gesperrt verrät der Status nichts über frühere Sitzungen (keine Zähler, kein Zweck).
        net = self.gate.status() if self.unlocked else {"open": False, "seconds_left": 0, "purpose": "", "allowed": 0, "blocked": 0,
                                                        "durations": list(netgate.DURATIONS)}
        out: dict[str, Any] = {"exists": info["exists"], "unlocked": self.unlocked, "version": __version__,
                               "net": net, "lock_reason": self.lock_reason if not self.unlocked else ""}
        if info["exists"] and not self.unlocked:
            out["wait_seconds"] = info["wait_seconds"]
        if not info["exists"]:
            out["classic_data"] = self.classic_available()
        if self.unlocked:
            owner = self.opened.owner
            idle = int(owner.get("idle_minutes", 15)) * 60
            out.update({"owner": owner.get("display_name", ""), "vault_id": fingerprint(self.opened.data_key),
                        "idle_minutes": idle // 60, "idle_left": max(0, int(idle - (self.clock() - self.last_activity))),
                        "net_minutes": int(owner.get("net_minutes", 30)), "last_saved": self.last_saved,
                        # „ungespeichert“ erst melden, wenn der Zwischenspeicher-Takt verpasst wurde
                        "unsaved": self.db is not None and self.db.changes() != self._saved_changes
                        and self.clock() - self.last_saved > 2 * self.autosave_seconds + 1,
                        "folder": str(self.store.folder), "idle_choices": list(IDLE_CHOICES)})
        return out

    def classic_available(self) -> bool:
        return (self.classic_dir / "personosint.sqlite3").is_file() and (self.classic_dir / "secret.key").is_file()

    def touch(self) -> None:
        self.last_activity = self.clock()

    # ------------------------------------------------------------------ Einrichtung
    def setup_begin(self, display_name: str, passphrase: str, passphrase2: str) -> dict[str, Any]:
        if self.store.exists():
            raise VaultError("Der Vault ist bereits eingerichtet.")
        display_name = " ".join(str(display_name or "").split())[:80]
        if len(display_name) < 2:
            raise VaultError("Bitte Ihren Namen (oder ein Kürzel) angeben.")
        if passphrase != passphrase2:
            raise VaultError("Die beiden Passphrasen stimmen nicht überein.")
        check_passphrase(passphrase)
        secret = new_totp_secret()
        self._pending_setup = {"display_name": display_name, "passphrase": passphrase, "secret": secret, "at": self.clock()}
        uri = totp_uri(secret, display_name, issuer="EagleEye Vault")
        return {"secret": secret, "qr_svg": qr_svg(uri), "uri": uri}

    def setup_finish(self, code: str, import_classic: bool = False) -> dict[str, Any]:
        pending = self._pending_setup
        if not pending or self.clock() - pending["at"] > 900:
            raise VaultError("Die Einrichtung ist abgelaufen. Bitte noch einmal beginnen.")
        counter = totp_counter(pending["secret"], str(code or "").strip())
        if counter is None:
            raise VaultError("Der Code passt nicht. Bitte die Uhrzeit des Telefons prüfen und den aktuellen Code eingeben.")
        owner = {"display_name": pending["display_name"], "totp_secret": pending["secret"], "totp_last": counter,
                 "idle_minutes": 15, "net_minutes": 30}
        with self._lock:
            opened, recovery = self.store.create(pending["passphrase"], owner)
            self._pending_setup = None
            imported = self._import_classic(opened) if import_classic else None
            self._open_inner(opened, imported)
            if not imported:
                # Das Konto meldet sich nie mit Passwort an (der Vault weist den Inhaber aus); das Passwort ist ein Zufallswert.
                user = self.inner.state.auth.create_user("inhaber", owner["display_name"], "admin",
                                                         "Vx!" + secrets.token_urlsafe(30) + "9a", must_change=False)
                opened.owner["user_id"] = user["id"]
            else:
                opened.owner["user_id"] = imported["owner_id"]
            self.store.save_owner(opened)
            self.save(force=True)
        return {"recovery_key": recovery, "imported": bool(imported), "imported_cases": (imported or {}).get("cases", 0)}

    def _import_classic(self, opened: Opened) -> dict[str, Any]:
        """Übernimmt einen bisherigen PersonOSINT-Datenordner (Datenbank + verschlüsselte Fotos/Belege)."""
        src_db = self.classic_dir / "personosint.sqlite3"
        if not self.classic_available():
            raise VaultError("Keine bisherigen PersonOSINT-Daten gefunden.")
        # normal öffnen (WAL-Datenbanken lassen sich nur mit Schreibzugriff auf die -shm-Datei konsistent lesen); es wird nur gelesen
        src = sqlite3.connect(str(src_db))
        mem = sqlite3.connect(":memory:")
        try:
            src.backup(mem)
            raw = mem.serialize()
            owner_id = mem.execute("SELECT id FROM users WHERE role = 'admin' AND active = 1 ORDER BY id LIMIT 1").fetchone()
            cases = mem.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        finally:
            src.close()
            mem.close()
        if not owner_id:
            raise VaultError("In den bisherigen Daten gibt es kein aktives Administrationskonto.")
        old = Vault(self.classic_dir / "secret.key")
        new = Vault.from_key(opened.files_key)
        for folder in ("photos", "evidence"):
            source = self.classic_dir / folder
            if not source.is_dir():
                continue
            target = self.store.files_dir / folder
            target.mkdir(parents=True, exist_ok=True)
            for item in source.iterdir():
                if item.is_file():
                    (target / item.name).write_bytes(new.encrypt(old.decrypt(item.read_bytes())))
        return {"owner_id": owner_id[0], "cases": cases, "raw": raw}

    # ------------------------------------------------------------------ Öffnen und Sperren
    def unlock(self, passphrase: str, code: str) -> None:
        with self._lock:
            if self.unlocked:
                return
            opened = self.store.open(passphrase, reset=False)
            owner = opened.owner
            counter = totp_counter(owner["totp_secret"], str(code or "").strip())
            if counter is None or counter <= int(owner.get("totp_last", -1)):
                self.store.note_failure()
                raise WrongSecret("Der Zwei-Faktor-Code ist falsch oder wurde schon benutzt.")
            owner["totp_last"] = counter
            self.store.save_owner(opened)
            self.store.reset_failures()
            self._open_inner(opened, None)

    def unlock_recovery(self, recovery_key: str, new_passphrase: str, new_passphrase2: str) -> None:
        """Notfall: Passphrase vergessen. Der Wiederherstellungsschlüssel öffnet den Vault; eine neue Passphrase ist Pflicht."""
        if new_passphrase != new_passphrase2:
            raise VaultError("Die beiden neuen Passphrasen stimmen nicht überein.")
        check_passphrase(new_passphrase)
        with self._lock:
            opened = self.store.open(recovery_key, recovery=True)
            self.store.change_passphrase(opened, new_passphrase)
            self._open_inner(opened, None)

    def _open_inner(self, opened: Opened, imported: dict[str, Any] | None) -> None:
        from .api import create_app

        raw = imported["raw"] if imported else self.store.load_db(opened)
        db = Database(":memory:", post_migrations=_post_migrations(), initial=raw)
        files = self.store.files_dir
        files.mkdir(parents=True, exist_ok=True)
        settings = Settings(data_dir=files, require_2fa=False, cookie_secure=False, session_idle_minutes=24 * 60,
                            session_max_hours=24, backup_hour="", backup_dir=str(files / "backups"))
        settings.allowed_hosts = ("127.0.0.1", "localhost")
        self.inner = create_app(settings=settings, http=self.http, start_scheduler=False, db=db,
                                vault=Vault.from_key(opened.files_key))
        self.db, self.opened = db, opened
        self._saved_changes = -1 if imported else db.changes()
        self.lock_reason = ""
        self.touch()

    def issue_session(self, request: Request) -> str:
        user_id = int(self.opened.owner["user_id"])
        return self.inner.state.auth.vault_session(user_id, request.client.host if request.client else "",
                                                   request.headers.get("user-agent", ""))

    def save(self, force: bool = False) -> bool:
        with self._lock:
            if not self.opened or not self.db:
                return False
            changes = self.db.changes()
            if not force and changes == self._saved_changes:
                return False
            self.store.save_db(self.opened, self.db.serialize())
            self._saved_changes = changes
            self.last_saved = self.clock()
            return True

    def lock(self, reason: str = "Gesperrt") -> None:
        with self._lock:
            self.gate.close("Vault gesperrt")
            self.gate.log.clear()
            self.gate.sessions.clear()
            self.gate.allowed = self.gate.blocked = 0
            if not self.opened:
                return
            try:
                self.save(force=True)
            finally:
                if self.db:
                    self.db.close()
                self.inner = self.db = self.opened = None
                self._tiles.clear()
                self.lock_reason = reason
                log.info("Vault gesperrt: %s", reason)

    # ------------------------------------------------------------------ Einstellungen
    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            owner = self.opened.owner
            if "idle_minutes" in payload:
                value = int(payload["idle_minutes"])
                if value not in IDLE_CHOICES:
                    raise VaultError("Unzulässige Sperrzeit.")
                owner["idle_minutes"] = value
            if "net_minutes" in payload:
                value = int(payload["net_minutes"])
                if value not in netgate.DURATIONS:
                    raise VaultError("Unzulässiges Zeitfenster.")
                owner["net_minutes"] = value
            self.store.save_owner(self.opened)
        return self.status()

    def change_passphrase(self, old: str, new: str, new2: str) -> None:
        if new != new2:
            raise VaultError("Die beiden neuen Passphrasen stimmen nicht überein.")
        self.store.open(old)  # prüft die alte Passphrase (mit Fehlversuchszähler)
        self.store.change_passphrase(self.opened, new)

    # ------------------------------------------------------------------ Kartenkacheln über den Netzschalter
    def tile(self, z: int, x: int, y: int) -> bytes:
        key = f"{z}/{x}/{y}"
        with self._lock:
            if key in self._tiles:
                self._tiles.move_to_end(key)
                return self._tiles[key]
        if not self.gate.is_open():
            return _blank_tile("Netz geschlossen – Karte offline")
        req = urllib.request.Request(f"https://tile.openstreetmap.org/{key}.png", headers={"User-Agent": TILE_UA})
        try:
            netgate.require_open("tile.openstreetmap.org")
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=10) as resp:
                data = resp.read(500_000)
        except OSError:
            return _blank_tile("Kartenkachel nicht erreichbar")
        with self._lock:
            self._tiles[key] = data
            while len(self._tiles) > 800:
                self._tiles.popitem(last=False)
        return data


def _post_migrations():
    from .service import seal_audit_chain

    return {2: seal_audit_chain}


# ---------------------------------------------------------------------- Web
def create_vault_app(folder: Path | str | None = None, *, http=None, kdf: dict | None = None, classic_dir: Path | None = None,
                     install_gate: bool = True, background: bool = True) -> Callable:
    manager = VaultManager(Path(folder) if folder else default_vault_dir(), http=http, kdf=kdf, classic_dir=classic_dir)
    if install_gate:
        netgate.install(manager.gate)
    vapp = FastAPI(title="EagleEye Vault", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    vapp.state.manager = manager

    def fail(exc: Exception, status: int = 422) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status)

    def _session_ok(request: Request) -> bool:
        if not manager.unlocked:
            return False
        found = manager.inner.state.auth.session(request.cookies.get(COOKIE))
        if not found:
            return False
        if request.method not in {"GET", "HEAD"} and request.headers.get("x-csrf-token") != found[0]["csrf_token"]:
            return False
        return True

    def _set_cookie(resp: Response, token: str) -> None:
        resp.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=False, path="/")

    # ---------------- ohne Anmeldung: Status, Einrichtung, Entsperren
    @vapp.get("/vault/api/status")
    def status(request: Request) -> dict:
        out = manager.status()
        out["signed_in"] = _session_ok(request) if manager.unlocked else False
        if not out["signed_in"] and manager.unlocked:
            # Geöffnet, aber dieser Browser hat keine Sitzung: nichts preisgeben außer „gesperrt für diesen Browser“.
            out = {"exists": True, "unlocked": True, "signed_in": False, "version": __version__}
        return out

    @vapp.post("/vault/api/setup/begin")
    def setup_begin(payload: dict = Body(...)) -> Response:
        try:
            return JSONResponse(manager.setup_begin(payload.get("display_name", ""), payload.get("passphrase", ""),
                                                    payload.get("passphrase2", "")))
        except VaultError as exc:
            return fail(exc)

    @vapp.post("/vault/api/setup/finish")
    def setup_finish(request: Request, payload: dict = Body(...)) -> Response:
        try:
            result = manager.setup_finish(payload.get("code", ""), bool(payload.get("import_classic")))
        except VaultError as exc:
            return fail(exc)
        resp = JSONResponse(result)
        _set_cookie(resp, manager.issue_session(request))
        return resp

    @vapp.post("/vault/api/unlock")
    def unlock(request: Request, payload: dict = Body(...)) -> Response:
        if manager.unlocked:
            return fail(VaultError("Der Vault ist bereits in einem anderen Fenster geöffnet. Dort sperren oder das Programm neu starten."), 409)
        try:
            manager.unlock(payload.get("passphrase", ""), payload.get("code", ""))
        except WrongSecret as exc:
            return fail(exc, 401)
        except VaultError as exc:
            return fail(exc, 429 if "warten" in str(exc) else 422)
        resp = JSONResponse({"ok": True})
        _set_cookie(resp, manager.issue_session(request))
        return resp

    @vapp.post("/vault/api/recover")
    def recover(request: Request, payload: dict = Body(...)) -> Response:
        if manager.unlocked:
            return fail(VaultError("Der Vault ist bereits geöffnet."), 409)
        try:
            manager.unlock_recovery(payload.get("recovery_key", ""), payload.get("passphrase", ""), payload.get("passphrase2", ""))
        except WrongSecret as exc:
            return fail(exc, 401)
        except VaultError as exc:
            return fail(exc)
        resp = JSONResponse({"ok": True})
        _set_cookie(resp, manager.issue_session(request))
        return resp

    # ---------------- mit Sitzung: Sperren, Netz, Einstellungen
    def _need(request: Request) -> JSONResponse | None:
        if not _session_ok(request):
            return JSONResponse({"detail": "Vault gesperrt oder Sitzung abgelaufen."}, status_code=423)
        return None

    @vapp.post("/vault/api/lock")
    def lock(request: Request) -> Response:
        if (denied := _need(request)) is not None:
            return denied
        manager.lock("Von Hand gesperrt")
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @vapp.post("/vault/api/activity")
    def activity(request: Request) -> Response:
        if (denied := _need(request)) is not None:
            return denied
        manager.touch()
        return JSONResponse({"ok": True})

    @vapp.post("/vault/api/net")
    def net(request: Request, payload: dict = Body(...)) -> Response:
        if (denied := _need(request)) is not None:
            return denied
        manager.touch()
        try:
            if payload.get("open"):
                manager.gate.open(int(payload.get("minutes") or manager.opened.owner.get("net_minutes", 30)),
                                  str(payload.get("purpose") or ""))
                manager.inner.state.platform.log(None, "Vault: Netz geöffnet",
                                                 f"{payload.get('minutes')} Minuten · {str(payload.get('purpose') or '')[:120]}")
            else:
                manager.gate.close("von Hand geschlossen")
                manager.inner.state.platform.log(None, "Vault: Netz geschlossen", "von Hand")
        except ValueError as exc:
            return fail(exc)
        return JSONResponse(manager.gate.status())

    @vapp.get("/vault/api/net/log")
    def net_log(request: Request) -> Response:
        if (denied := _need(request)) is not None:
            return denied
        return JSONResponse({"items": manager.gate.recent(200), "sessions": list(manager.gate.sessions)[::-1]})

    @vapp.post("/vault/api/settings")
    def settings(request: Request, payload: dict = Body(...)) -> Response:
        if (denied := _need(request)) is not None:
            return denied
        try:
            return JSONResponse(manager.update_settings(payload))
        except (VaultError, ValueError) as exc:
            return fail(exc)

    @vapp.post("/vault/api/passphrase")
    def passphrase(request: Request, payload: dict = Body(...)) -> Response:
        if (denied := _need(request)) is not None:
            return denied
        try:
            manager.change_passphrase(payload.get("old", ""), payload.get("new", ""), payload.get("new2", ""))
        except WrongSecret as exc:
            return fail(exc, 401)
        except VaultError as exc:
            return fail(exc)
        return JSONResponse({"ok": True})

    @vapp.post("/vault/api/recovery-key")
    def recovery_key(request: Request, payload: dict = Body(...)) -> Response:
        if (denied := _need(request)) is not None:
            return denied
        try:
            manager.store.open(payload.get("passphrase", ""))
        except (WrongSecret, VaultError) as exc:
            return fail(exc, 401)
        return JSONResponse({"recovery_key": manager.store.new_recovery(manager.opened)})

    @vapp.post("/vault/api/save")
    def save(request: Request) -> Response:
        if (denied := _need(request)) is not None:
            return denied
        manager.save(force=True)
        return JSONResponse({"ok": True, "last_saved": manager.last_saved})

    @vapp.get("/vault/tiles/{z}/{x}/{y}.png")
    def tiles(request: Request, z: int, x: int, y: int) -> Response:
        if not _session_ok(request):
            return Response(status_code=423)
        if not (0 <= z <= 19 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
            return Response(status_code=404)
        return Response(manager.tile(z, x, y), media_type="image/png", headers={"Cache-Control": "no-store"})

    @vapp.get("/vault/static/{name}")
    def vault_static(name: str) -> Response:
        if name not in {"vault.js", "vault.css", "vaultbar.js", "vaultbar.css"}:
            return Response(status_code=404)
        media = "text/css" if name.endswith(".css") else "text/javascript"
        return FileResponse(STATIC / name, media_type=media, headers={"Cache-Control": "no-store"})

    lock_page = (STATIC / "vault.html").read_bytes()

    # ---------------- Verteiler: Vault-Teil, gesperrt → Sperrbildschirm, geöffnet → PersonOSINT
    async def send_json(send, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
                    + [(k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]})
        await send({"type": "http.response.body", "body": body})

    def with_headers(send):
        async def wrapped(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in
                           {b"content-security-policy", b"cache-control", b"x-frame-options", b"referrer-policy"}]
                headers += [(k.lower().encode(), v.encode()) for k, v in SECURITY_HEADERS.items()]
                message = {**message, "headers": headers}
            await send(message)
        return wrapped

    async def app(scope, receive, send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    if background:
                        manager.start_background()
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    manager.stop_background()
                    manager.lock("Programm beendet")
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            return
        headers = {k.decode().lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        host = headers.get("host", "").rsplit(":", 1)[0] if not headers.get("host", "").startswith("[") else "[::1]"
        client = (scope.get("client") or ("", 0))[0]
        if host not in LOCAL_HOSTS | {"testserver"} or (client and client not in {"127.0.0.1", "::1", "testclient"}):
            await send_json(send, 403, {"detail": "Der Vault ist nur auf diesem Rechner erreichbar."})
            return
        method, path = scope["method"], scope["path"]
        if method not in {"GET", "HEAD", "OPTIONS"}:
            # Nur eigene Seiten dürfen schreiben: eigener Header erzwingt CORS-Vorabprüfung; fremde Herkunft wird abgewiesen.
            site = headers.get("sec-fetch-site", "")
            if headers.get("x-requested-with") != "EagleEye" or site not in {"", "same-origin", "none"}:
                await send_json(send, 403, {"detail": "Anfrage ohne gültige Herkunft abgelehnt."})
                return
        send = with_headers(send)
        if path.startswith("/vault/"):
            await vapp(scope, receive, send)
            return
        if not manager.unlocked:
            if path.startswith("/api/"):
                await send_json(send, 423, {"detail": "Vault gesperrt."})
                return
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"text/html; charset=utf-8"), (b"content-length", str(len(lock_page)).encode())]})
            await send({"type": "http.response.body", "body": lock_page if method != "HEAD" else b""})
            return
        inner = manager.inner
        if path == "/api/auth/logout" and method == "POST":
            # Abmelden heißt im Vault: sperren.
            if inner.state.auth.session(_cookie(headers)):
                manager.lock("Abgemeldet")
            await send_json(send, 200, {"ok": True})
            return
        if path in {"/", "/index.html"} and method in {"GET", "HEAD"}:
            if not inner.state.auth.session(_cookie(headers)):
                # Geöffnet, aber dieser Browser hat keine Sitzung (z. B. zweites Fenster): Sperrbildschirm.
                body = lock_page
            else:
                body = (STATIC / "index.html").read_bytes().replace(
                    b'<script src="/static/vendor/leaflet/leaflet.js"></script>',
                    b'<link rel="stylesheet" href="/vault/static/vaultbar.css">\n  <script src="/vault/static/vaultbar.js"></script>\n'
                    b'  <script src="/static/vendor/leaflet/leaflet.js"></script>')
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"text/html; charset=utf-8"), (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body if method != "HEAD" else b""})
            return
        await inner(scope, receive, send)

    app.manager = manager  # type: ignore[attr-defined]
    app.vapp = vapp  # type: ignore[attr-defined]
    return app


def _cookie(headers: dict[str, str]) -> str | None:
    from http.cookies import SimpleCookie

    jar = SimpleCookie()
    try:
        jar.load(headers.get("cookie", ""))
    except Exception:  # noqa: BLE001
        return None
    return jar[COOKIE].value if COOKIE in jar else None


__all__ = ["create_vault_app", "VaultManager", "default_vault_dir"]
