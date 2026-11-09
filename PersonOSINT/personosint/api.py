"""HTTP-API, Anmeldung/Rechte und Auslieferung der Weboberfläche."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import Body, Depends, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .auth import CASE_CREATORS, ROLE_HELP, ROLES, Auth, AuthError
from .backup import BackupError, create_backup, list_backups, prune_backups, verify_backup
from .config import Settings, default_data_dir
from .crypto import Vault
from .db import SCHEMA_VERSION, ConflictError, Database, now_iso, redact_url
from .demo import seed_demo
from .dossier import build_dossier, build_poster, render_graph_png, safe_filename
from . import opsec as ops
from .opsec import OpsecBlocked
from .service import (CASE_STATUSES, CASE_TYPES, ENTITY_TYPES, EVENT_KINDS, IDENTIFIER_KINDS, MEMBER_ROLES, MISSING_FIELDS,
                      PERSON_FIELDS, RELATIONS, RISK_FACTORS, Forbidden, Invalid, NotFound, Platform, current_user,
                      seal_audit_chain)
from .sources import Http

log = logging.getLogger("personosint")
STATIC = Path(__file__).parent / "static"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
COOKIE = "ee_session"
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data: blob: https://tile.openstreetmap.org; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

__all__ = ["create_app", "default_data_dir"]


def _download(content: bytes, filename: str, media: str) -> Response:
    ascii_name = filename.encode("ascii", "replace").decode().replace("?", "_")
    return Response(content, media_type=media, headers={
        "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}",
        "Cache-Control": "no-store"})


def open_database(settings: Settings) -> Database:
    target = settings.database_url or str(settings.data_dir / "personosint.sqlite3")
    return Database(target, post_migrations={2: seal_audit_chain})


def create_app(data_dir: Path | str | None = None, http: Http | None = None, auto_geocode: bool = True,
               settings: Settings | None = None, start_scheduler: bool = True) -> FastAPI:
    settings = settings or Settings()
    if data_dir:
        settings.data_dir = Path(data_dir)
    settings.allowed_hosts = tuple(dict.fromkeys(settings.allowed_hosts + ("testserver",)))
    vault = Vault(settings.resolved_key_file)
    db = open_database(settings)
    p = Platform(db, settings.data_dir, http=http, auto_geocode=auto_geocode and settings.auto_geocode, vault=vault)
    auth = Auth(db, vault, settings)
    app = FastAPI(title="EagleEye PersonOSINT", version=__version__, docs_url="/api/docs", redoc_url=None)
    app.state.platform, app.state.auth, app.state.settings = p, auth, settings

    # ---------------------------------------------------------------- Middleware & Fehler
    @app.middleware("http")
    async def guard(request: Request, call_next):
        host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
        if host not in settings.allowed_hosts:
            return JSONResponse({"detail": "Unzulässiger Host"}, status_code=400)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.url.path.startswith("/api/") \
                and request.headers.get("x-requested-with") != "EagleEye":
            return JSONResponse({"detail": "Anfrage ohne gültige Client-Kennung abgelehnt"}, status_code=403)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Content-Security-Policy", CSP)
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    for exc_type, status in ((NotFound, 404), (Invalid, 422), (Forbidden, 403), (ConflictError, 409), (BackupError, 422), (OpsecBlocked, 428)):
        def _handler(_: Request, exc: Exception, status: int = status):
            return JSONResponse({"detail": str(exc)}, status_code=status)
        app.add_exception_handler(exc_type, _handler)

    @app.exception_handler(AuthError)
    async def _auth_err(_: Request, exc: AuthError):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    # ---------------------------------------------------------------- Anmeldung (Abhängigkeiten)
    def _session(request: Request) -> tuple[dict, dict] | None:
        return auth.session(request.cookies.get(COOKIE))

    def _check_csrf(request: Request, sess: dict) -> None:
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("x-csrf-token") != sess["csrf_token"]:
            raise AuthError("Sicherheitsprüfung fehlgeschlagen (CSRF). Bitte Seite neu laden.", 403)

    async def any_session(request: Request) -> tuple[dict, dict]:
        """Angemeldet, aber evtl. noch im 2FA-/Passwort-Schritt."""
        found = _session(request)
        if not found:
            raise AuthError("Bitte anmelden.")
        _check_csrf(request, found[0])
        current_user.set(found[1])
        return found

    async def user_ok(request: Request) -> dict:
        sess, user = await any_session(request)
        state = auth.session_state(sess, user)
        if state != "ok":
            raise AuthError({"mfa": "Bitte zuerst den Zwei-Faktor-Code eingeben.", "password": "Bitte zuerst das Passwort ändern.",
                             "mfa_setup": "Bitte zuerst die Zwei-Faktor-Anmeldung einrichten."}[state], 401)
        return user

    async def admin_ok(user: dict = Depends(user_ok)) -> dict:
        if user["role"] != "admin":
            raise Forbidden("Nur für die Administration.")
        return user

    def need(perm: str):
        async def dep(cid: int, user: dict = Depends(user_ok)) -> dict:
            return p.require(cid, perm)
        return Depends(dep)

    READ, WRITE, REVIEW, MANAGE, DELETE = need("read"), need("write"), need("review"), need("manage"), need("delete")

    def _set_cookie(resp: Response, token: str) -> None:
        resp.set_cookie(COOKIE, token, httponly=True, samesite="strict", secure=settings.cookie_secure,
                        max_age=settings.session_max_hours * 3600, path="/")

    def _state_payload(request: Request) -> dict[str, Any]:
        found = _session(request)
        base = {"setup_required": auth.user_count() == 0, "require_2fa": settings.require_2fa, "version": __version__}
        if not found:
            return base | {"authenticated": False}
        sess, user = found
        return base | {"authenticated": True, "state": auth.session_state(sess, user), "user": auth.public(user),
                       "csrf": sess["csrf_token"], "can_create_cases": user["role"] in CASE_CREATORS}

    # ---------------------------------------------------------------- Auth-Endpunkte
    @app.get("/api/auth/state")
    def auth_state(request: Request) -> dict:
        return _state_payload(request)

    @app.post("/api/auth/setup")
    def setup(request: Request, payload: dict = Body(...)) -> Response:
        if auth.user_count() > 0:
            raise AuthError("Die Einrichtung ist bereits abgeschlossen.", 409)
        user = auth.create_user(payload.get("username", ""), payload.get("display_name", ""), "admin", payload.get("password", ""), must_change=False)
        current_user.set(auth.get_user(user["id"]))
        p.log(None, "Ersteinrichtung", f"Administrationskonto {user['username']} angelegt")
        token, _ = auth.login(payload["username"], payload["password"], request.client.host if request.client else "", request.headers.get("user-agent", ""))
        auth.mark_login(auth.get_user(user["id"]))
        resp = JSONResponse({"ok": True})
        _set_cookie(resp, token)
        return resp

    @app.post("/api/auth/login")
    def login(request: Request, payload: dict = Body(...)) -> Response:
        ip = request.client.host if request.client else ""
        try:
            token, user = auth.login(payload.get("username", ""), payload.get("password", ""), ip, request.headers.get("user-agent", ""))
        except AuthError as exc:
            current_user.set(None)
            p.log(None, "Anmeldung fehlgeschlagen", f"{(payload.get('username') or '')[:40]} von {ip}: {exc}")
            raise
        current_user.set(user)
        if not user["totp_enabled"]:
            auth.mark_login(user)
        p.log(None, "Anmeldung", f"von {ip}" + (" – 2FA-Code ausstehend" if user["totp_enabled"] else ""))
        resp = JSONResponse({"ok": True, "state": "mfa" if user["totp_enabled"] else "check"})
        _set_cookie(resp, token)
        return resp

    @app.post("/api/auth/mfa")
    async def mfa(payload: dict = Body(...), found: tuple = Depends(any_session)) -> dict:
        sess, user = found
        auth.verify_mfa(sess, user, str(payload.get("code", "")))
        p.log(None, "Zwei-Faktor-Anmeldung bestätigt", "")
        return {"ok": True}

    @app.post("/api/auth/totp/begin")
    async def totp_begin(found: tuple = Depends(any_session)) -> dict:
        sess, user = found
        if user["totp_enabled"] and not sess["mfa_passed"]:
            raise AuthError("Bitte zuerst mit dem bisherigen Code anmelden.", 403)
        return auth.begin_totp_setup(user)

    @app.post("/api/auth/totp/confirm")
    async def totp_confirm(payload: dict = Body(...), found: tuple = Depends(any_session)) -> dict:
        sess, user = found
        auth.confirm_totp_setup(sess, auth.get_user(user["id"]), str(payload.get("code", "")))
        p.log(None, "Zwei-Faktor-Anmeldung eingerichtet", "")
        return {"ok": True}

    @app.post("/api/auth/password")
    async def change_password(payload: dict = Body(...), found: tuple = Depends(any_session)) -> dict:
        sess, user = found
        if user["totp_enabled"] and not sess["mfa_passed"]:
            raise AuthError("Bitte zuerst den Zwei-Faktor-Code eingeben.", 403)
        auth.change_password(user["id"], payload.get("old_password", ""), payload.get("new_password", ""))
        p.log(None, "Passwort geändert", "")
        return {"ok": True}

    @app.post("/api/auth/logout")
    def logout(request: Request) -> Response:
        found = _session(request)
        if found:
            current_user.set(found[1])
            p.log(None, "Abmeldung", "")
        auth.logout(request.cookies.get(COOKIE))
        resp = JSONResponse({"ok": True})
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @app.get("/api/users")
    def users_min(user: dict = Depends(user_ok)) -> list[dict]:
        return [{"id": u["id"], "display_name": u["display_name"], "role": u["role"], "role_label": u["role_label"]}
                for u in auth.list_users() if u["active"]]

    # ---------------------------------------------------------------- Verwaltung
    @app.get("/api/admin/users")
    def admin_users(_: dict = Depends(admin_ok)) -> list[dict]:
        return auth.list_users()

    @app.post("/api/admin/users", status_code=201)
    def admin_create_user(payload: dict = Body(...), _: dict = Depends(admin_ok)) -> dict:
        u = auth.create_user(payload.get("username", ""), payload.get("display_name", ""), payload.get("role", "analyst"), payload.get("password", ""), True)
        p.log(None, "Benutzer angelegt", f"{u['username']} ({ROLES[u['role']]})")
        return u

    @app.patch("/api/admin/users/{uid}")
    def admin_update_user(uid: int, payload: dict = Body(...), actor: dict = Depends(admin_ok)) -> dict:
        u = auth.update_user(uid, payload, actor["id"])
        changes = [k for k in ("display_name", "role", "active", "unlock", "reset_2fa") if k in payload] + (["neues Passwort"] if payload.get("new_password") else [])
        p.log(None, "Benutzer geändert", f"{u['username']}: " + ", ".join(f"{k}={payload[k]}" if k in {"role", "active"} else k for k in changes))
        return u

    @app.get("/api/admin/system")
    def admin_system(_: dict = Depends(admin_ok)) -> dict:
        key = settings.resolved_key_file.resolve()
        warnings = []
        if settings.data_dir.resolve() in key.parents:
            warnings.append("Die Schlüsseldatei liegt im Datenordner. Für den Serverbetrieb getrennt ablegen (EAGLEEYE_KEY_FILE).")
        if db.dialect == "sqlite":
            warnings.append("SQLite ist für den Einzelplatz gedacht. Für Teams PostgreSQL verwenden (EAGLEEYE_DATABASE_URL).")
        if not settings.cookie_secure:
            warnings.append("Sitzungs-Cookies ohne „Secure“-Flag – im Netzwerkbetrieb HTTPS + EAGLEEYE_COOKIE_SECURE=1 setzen.")
        if not settings.require_2fa:
            warnings.append("Zwei-Faktor-Anmeldung ist nicht verpflichtend (EAGLEEYE_REQUIRE_2FA=0).")
        bdir = settings.resolved_backup_dir
        if bdir.exists() and not os.access(bdir, os.W_OK):
            warnings.append(f"Sicherungsordner {bdir} ist nicht beschreibbar – Sicherungen schlagen fehl.")
        if not settings.backup_hour:
            warnings.append("Keine automatische tägliche Sicherung konfiguriert (EAGLEEYE_BACKUP_HOUR).")
        if not settings.backup_passphrase:
            warnings.append("Sicherungen werden mit dem Anwendungsschlüssel verschlüsselt – Schlüsseldatei getrennt aufbewahren oder EAGLEEYE_BACKUP_PASSPHRASE setzen.")
        return {"version": __version__, "schema_version": SCHEMA_VERSION, "database": db.dialect,
                "database_target": redact_url(db.target), "data_dir": str(settings.data_dir), "key_file": str(key),
                "require_2fa": settings.require_2fa, "cookie_secure": settings.cookie_secure, "allowed_hosts": settings.allowed_hosts,
                "backup_dir": str(settings.resolved_backup_dir), "backup_hour": settings.backup_hour, "backup_keep": settings.backup_keep,
                "backup_passphrase": bool(settings.backup_passphrase),
                "active_sessions": db.scalar("SELECT COUNT(*) AS n FROM sessions WHERE expires_at > ?", (now_iso(),)),
                "users": len(auth.list_users()), "cases": db.scalar("SELECT COUNT(*) AS n FROM cases"), "warnings": warnings}

    @app.get("/api/admin/audit/verify")
    def admin_verify(_: dict = Depends(admin_ok)) -> dict:
        res = p.verify_audit()
        p.log(None, "Protokollprüfung", "Kette intakt" if res["ok"] else f"FEHLER bei Eintrag {res['broken_at']}: {res['problem']}")
        return res

    @app.get("/api/admin/audit")
    def admin_audit(limit: int = 300, _: dict = Depends(admin_ok)) -> list[dict]:
        rows = db.all("SELECT a.*, c.reference, c.restricted FROM audit a LEFT JOIN cases c ON c.id = a.case_id ORDER BY a.id DESC LIMIT ?", (min(limit, 2000),))
        for r in rows:  # Inhalte vertraulicher Fälle bleiben auch im Gesamtprotokoll verborgen
            if r.get("restricted"):
                r["detail"] = "[vertraulicher Fall]"
        return rows

    @app.get("/api/admin/backups")
    def admin_backups(_: dict = Depends(admin_ok)) -> list[dict]:
        return list_backups(settings.resolved_backup_dir)

    @app.post("/api/admin/backups", status_code=201)
    def admin_backup_now(_: dict = Depends(admin_ok)) -> dict:
        try:
            path = create_backup(db, vault, settings.data_dir, settings.resolved_backup_dir, settings.backup_passphrase)
        except OSError as exc:
            raise BackupError(f"Sicherungsordner {settings.resolved_backup_dir} ist nicht beschreibbar ({exc.strerror}). "
                              "Rechte prüfen – bei Docker: deploy/init-secrets.sh erneut ausführen.") from exc
        prune_backups(settings.resolved_backup_dir, settings.backup_keep)
        check = verify_backup(path, vault, settings.backup_passphrase)
        p.log(None, "Sicherung erstellt", f"{path.name} ({path.stat().st_size // 1024} KB, geprüft: {'ok' if check['ok'] else 'FEHLER'})")
        return {"name": path.name, "size": path.stat().st_size, "verified": check["ok"], "tables": check["tables"]}

    @app.get("/api/admin/backups/{name}")
    def admin_backup_download(name: str, _: dict = Depends(admin_ok)) -> Response:
        path = settings.resolved_backup_dir / Path(name).name
        if not path.exists() or path.suffix != ".eebak":
            raise NotFound("Sicherung nicht gefunden.")
        p.log(None, "Sicherung heruntergeladen", path.name)
        return _download(path.read_bytes(), path.name, "application/octet-stream")

    @app.get("/api/admin/restricted-cases")
    def admin_restricted(_: dict = Depends(admin_ok)) -> list[dict]:
        return p.restricted_cases()

    @app.post("/api/admin/cases/{cid}/emergency-access")
    def admin_emergency(cid: int, payload: dict = Body(...), _: dict = Depends(admin_ok)) -> dict:
        p.emergency_access(cid, payload.get("reason", ""))
        return {"ok": True}

    # ---------------------------------------------------------------- Quellen & Referenzdaten (Schritt 1)
    @app.get("/api/admin/sources")
    def admin_sources(_: dict = Depends(admin_ok)) -> dict:
        return {"sources": p.available_sources(), "datasets": p.refdata.status()}

    @app.put("/api/admin/sources/{key}/key")
    def admin_set_key(key: str, payload: dict = Body(...), _: dict = Depends(admin_ok)) -> dict:
        p.set_api_key(key, (payload.get("key") or "").strip() or None)
        return {"ok": True}

    @app.post("/api/admin/sources/{key}/test")
    def admin_test_source(key: str, _: dict = Depends(admin_ok)) -> dict:
        return p.test_source(key)

    @app.post("/api/admin/refdata/{name}/download")
    def admin_refdata_download(name: str, _: dict = Depends(admin_ok)) -> dict:
        from .refdata import RefDataError

        prof = p.case_profile({"egress_profile": ""})
        try:
            p.refdata.download_async(name, lambda: ops.build_opener(prof))
        except RefDataError as exc:
            raise Invalid(str(exc)) from exc
        p.log(None, "Referenzdaten-Download gestartet", f"{name} über „{prof.name}“")
        return {"ok": True}

    @app.post("/api/admin/refdata/{name}/upload")
    async def admin_refdata_upload(name: str, file: UploadFile = File(...), _: dict = Depends(admin_ok)) -> dict:
        from .refdata import DATASETS

        if name not in DATASETS:
            raise NotFound("Unbekannter Datenbestand.")
        target = p.refdata.dir / f"upload-{name}-{int(time.time())}{Path(file.filename or 'x.csv').suffix.lower()}"
        with open(target, "wb") as out:
            while chunk := await file.read(1 << 20):
                out.write(chunk)
        p.refdata.import_async(name, target)
        p.log(None, "Referenzdaten-Import gestartet", f"{name}: {file.filename}")
        return {"ok": True}

    @app.delete("/api/admin/refdata/{name}", status_code=204)
    def admin_refdata_delete(name: str, _: dict = Depends(admin_ok)) -> Response:
        p.refdata.delete(name)
        p.log(None, "Referenzdaten gelöscht", name)
        return Response(status_code=204)

    @app.get("/api/sources")
    def sources_list(_: dict = Depends(user_ok)) -> list[dict]:
        return p.available_sources()

    @app.get("/api/cases/{cid}/facts")
    def case_facts(cid: int, status: str | None = None, _: dict = READ) -> list[dict]:
        return p.list_facts(cid, status)

    # ---------------------------------------------------------------- OPSEC
    @app.get("/api/egress-profiles")
    def egress_list(_: dict = Depends(user_ok)) -> list[dict]:
        return [{"id": e.id, "name": e.name, "kind": e.kind, "notes": e.notes} for e in p.egress_profiles()]

    @app.get("/api/admin/opsec")
    def admin_opsec(_: dict = Depends(admin_ok)) -> dict:
        usage = {r["egress_profile"]: r["n"] for r in db.all("SELECT egress_profile, COUNT(*) AS n FROM cases GROUP BY egress_profile")}
        return {"profiles": [e.as_dict() | {"cases": usage.get(e.id, 0)} for e in p.egress_profiles()], "settings": p.opsec_settings(),
                "levels": {k: ops.level_dict(v) for k, v in ops.LEVELS.items()},
                "level_usage": {r["opsec_level"]: r["n"] for r in db.all("SELECT opsec_level, COUNT(*) AS n FROM cases GROUP BY opsec_level")}}

    @app.post("/api/admin/egress-profiles", status_code=201)
    def admin_save_profile(payload: dict = Body(...), _: dict = Depends(admin_ok)) -> dict:
        return p.save_egress_profile(payload).as_dict()

    @app.delete("/api/admin/egress-profiles/{pid}", status_code=204)
    def admin_delete_profile(pid: str, _: dict = Depends(admin_ok)) -> Response:
        p.delete_egress_profile(pid)
        return Response(status_code=204)

    @app.post("/api/admin/egress-profiles/{pid}/test")
    def admin_test_profile(pid: str, _: dict = Depends(admin_ok)) -> dict:
        prof = p.egress_profile(pid)
        res = ops.egress_test(prof)
        direct = ops.egress_test(ops.DIRECT) if prof.kind != "direkt" else res
        res["direct_ip"] = direct.get("ip")
        res["anonymized"] = bool(res.get("ok") and direct.get("ok") and res["ip"] != direct["ip"])
        if res.get("ok") and prof.kind != "direkt" and not res["anonymized"]:
            res["warning"] = "Die Ausgangs-IP entspricht der Direkt-IP – dieser Ausgang anonymisiert NICHT."
        p.log(None, "Netzausgang getestet", f"{prof.name}: " + (f"IP {res['ip']}" if res.get("ok") else f"Fehler {res.get('error')}"))
        return res

    @app.put("/api/admin/opsec-settings")
    def admin_opsec_settings(payload: dict = Body(...), _: dict = Depends(admin_ok)) -> dict:
        return p.save_opsec_settings(payload)

    @app.get("/api/cases/{cid}/opsec")
    def case_opsec(cid: int, _: dict = READ) -> dict:
        return p.opsec_status(cid)

    @app.post("/api/cases/{cid}/opsec/briefing")
    def case_briefing(cid: int, _: dict = READ) -> dict:
        return p.ack_briefing(cid)

    # ---------------------------------------------------------------- Meta
    @app.get("/api/meta")
    def meta(_: dict = Depends(user_ok)) -> dict[str, Any]:
        return {"version": __version__, "case_types": CASE_TYPES, "entity_types": ENTITY_TYPES, "identifier_kinds": IDENTIFIER_KINDS,
                "relations": RELATIONS, "event_kinds": EVENT_KINDS, "case_statuses": CASE_STATUSES, "member_roles": MEMBER_ROLES,
                "roles": ROLES, "role_help": ROLE_HELP,
                "risk_factors": {k: v[0] for k, v in RISK_FACTORS.items() if k not in {"kind", "jugendlich", "senior"}},
                "person_fields": PERSON_FIELDS, "missing_fields": MISSING_FIELDS, "sources": p.available_sources(),
                "data_dir": str(settings.data_dir), "database": db.dialect,
                "opsec_levels": {k: ops.level_dict(v) for k, v in ops.LEVELS.items()}, "exposure": ops.EXPOSURE,
                "source_exposure": ops.SOURCE_EXPOSURE, "opsec_defaults": p.opsec_settings()}

    # ---------------------------------------------------------------- Fälle
    @app.get("/api/cases")
    def cases(view: str = "", _: dict = Depends(user_ok)) -> list[dict]:
        return p.list_cases(view)

    @app.post("/api/cases", status_code=201)
    def create_case(payload: dict = Body(...), user: dict = Depends(user_ok)) -> dict:
        if user["role"] not in CASE_CREATORS:
            raise Forbidden("Ihre Rolle darf keine Fälle anlegen.")
        return p.create_case(payload)

    @app.post("/api/demo", status_code=201)
    def demo(user: dict = Depends(user_ok)) -> dict:
        if user["role"] not in CASE_CREATORS:
            raise Forbidden("Ihre Rolle darf keine Fälle anlegen.")
        return p.get_case(seed_demo(p))

    @app.get("/api/cases/{cid}")
    def get_case(cid: int, case: dict = READ) -> dict:
        return case

    @app.patch("/api/cases/{cid}")
    def update_case(cid: int, payload: dict = Body(...), _: dict = READ) -> dict:
        return p.update_case(cid, payload)  # feinere Prüfung (Team/Status/Vier-Augen) in der Fachlogik

    @app.put("/api/cases/{cid}/members")
    def set_members(cid: int, payload: dict = Body(...), _: dict = MANAGE) -> dict:
        return p.set_members(cid, payload.get("members") or [])

    @app.delete("/api/cases/{cid}", status_code=204)
    def delete_case(cid: int, _: dict = DELETE) -> Response:
        p.delete_case(cid)
        return Response(status_code=204)

    @app.get("/api/cases/{cid}/overview")
    def overview(cid: int, _: dict = READ) -> dict:
        return p.overview(cid)

    @app.post("/api/cases/{cid}/presence")
    def presence(cid: int, payload: dict = Body(default={}), _: dict = READ) -> dict:
        return {"others": p.heartbeat(cid, str(payload.get("tab", ""))[:20]), "version": p.get_case(cid)["version"]}

    # ---------------------------------------------------------------- Einträge
    @app.get("/api/cases/{cid}/entities")
    def entities(cid: int, _: dict = READ) -> list[dict]:
        return p.list_entities(cid)

    @app.post("/api/cases/{cid}/entities", status_code=201)
    def create_entity(cid: int, payload: dict = Body(...), _: dict = WRITE) -> dict:
        return p.create_entity(cid, payload)

    @app.get("/api/cases/{cid}/entities/{eid}")
    def get_entity(cid: int, eid: int, _: dict = READ) -> dict:
        return p.get_entity(cid, eid)

    @app.patch("/api/cases/{cid}/entities/{eid}")
    def update_entity(cid: int, eid: int, payload: dict = Body(...), _: dict = WRITE) -> dict:
        return p.update_entity(cid, eid, payload)

    @app.delete("/api/cases/{cid}/entities/{eid}", status_code=204)
    def delete_entity(cid: int, eid: int, _: dict = WRITE) -> Response:
        p.delete_entity(cid, eid)
        return Response(status_code=204)

    @app.post("/api/cases/{cid}/entities/{eid}/photo")
    async def upload_photo(cid: int, eid: int, file: UploadFile = File(...), _: dict = WRITE) -> dict:
        return p.set_photo(cid, eid, await file.read(), file.filename or "foto.jpg")

    @app.get("/api/cases/{cid}/entities/{eid}/photo")
    def photo(cid: int, eid: int, _: dict = READ) -> Response:
        data = p.photo_bytes(cid, eid)
        if not data:
            raise NotFound("Kein Foto vorhanden.")
        return Response(data[0], media_type=data[1], headers={"Cache-Control": "no-store"})

    @app.post("/api/cases/{cid}/entities/{eid}/identifiers", status_code=201)
    def add_identifier(cid: int, eid: int, payload: dict = Body(...), _: dict = WRITE) -> dict:
        return p.add_identifier(cid, eid, payload)

    @app.delete("/api/cases/{cid}/identifiers/{iid}", status_code=204)
    def delete_identifier(cid: int, iid: int, _: dict = WRITE) -> Response:
        p.delete_identifier(cid, iid)
        return Response(status_code=204)

    @app.get("/api/cases/{cid}/entities/{eid}/research-links")
    def research(cid: int, eid: int, case: dict = READ) -> list[dict]:
        lv = ops.level(case["opsec_level"])
        links = p.links_for(cid, eid)
        for link in links:
            if link["exposure_rank"] > lv.max_link_exposure:
                link["blocked"] = f"Durch OPSEC-Stufe {lv.key} gesperrt: {ops.EXPOSURE[link['exposure']]['help']}"
                link["url"] = ""
        return links

    # ---------------------------------------------------------------- Suche & Treffer
    @app.post("/api/cases/{cid}/search")
    def search(cid: int, payload: dict = Body(...), _: dict = WRITE) -> dict:
        return p.run_search(cid, int(payload.get("entity_id") or 0), payload.get("sources") or None)

    @app.get("/api/cases/{cid}/searches")
    def searches(cid: int, _: dict = READ) -> list[dict]:
        return p.list_searches(cid)

    @app.get("/api/cases/{cid}/findings")
    def findings(cid: int, status: str | None = None, entity_id: int | None = None, _: dict = READ) -> list[dict]:
        return p.list_findings(cid, status, entity_id)

    @app.post("/api/cases/{cid}/findings", status_code=201)
    def manual_finding(cid: int, payload: dict = Body(...), _: dict = WRITE) -> dict:
        return p.add_manual_finding(cid, payload)

    @app.patch("/api/cases/{cid}/findings/{fid}")
    def review(cid: int, fid: int, payload: dict = Body(...), _: dict = REVIEW) -> dict:
        return p.review_finding(cid, fid, payload)

    # ---------------------------------------------------------------- Verbindungen
    @app.get("/api/cases/{cid}/links")
    def links(cid: int, _: dict = READ) -> list[dict]:
        return p.list_links(cid)

    @app.post("/api/cases/{cid}/links", status_code=201)
    def create_link(cid: int, payload: dict = Body(...), _: dict = WRITE) -> dict:
        return p.create_link(cid, payload)

    @app.delete("/api/cases/{cid}/links/{lid}", status_code=204)
    def delete_link(cid: int, lid: int, _: dict = WRITE) -> Response:
        p.delete_link(cid, lid)
        return Response(status_code=204)

    @app.get("/api/cases/{cid}/graph")
    def graph(cid: int, min_confidence: int = 0, _: dict = READ) -> dict:
        return p.graph(cid, min_confidence)

    @app.get("/api/cases/{cid}/graph.png")
    def graph_png(cid: int, min_confidence: int = 0, case: dict = READ) -> Response:
        export_id = p.register_export(cid, "Netzwerkgrafik")
        gr = p.graph(cid, min_confidence)
        subj = p.subject(cid)
        content = render_graph_png(gr, highlight={subj["id"]} if subj else None)
        p.finish_export(export_id, content)
        p.log(cid, "Netzwerkgrafik exportiert", export_id)
        return _download(content, f"Netzwerk_{safe_filename(case['reference'])}_{export_id}.png", "image/png")

    @app.get("/api/cases/{cid}/paths")
    def paths(cid: int, a: int, b: int, max_len: int = 5, _: dict = READ) -> dict:
        return p.find_paths(cid, a, b, max(1, min(max_len, 8)))

    @app.get("/api/cases/{cid}/suggestions")
    def suggestions(cid: int, _: dict = READ) -> list[dict]:
        return p.suggestions(cid)

    # ---------------------------------------------------------------- Zeitleiste & Aufgaben
    @app.get("/api/cases/{cid}/events")
    def events(cid: int, _: dict = READ) -> list[dict]:
        return p.list_events(cid)

    @app.post("/api/cases/{cid}/events", status_code=201)
    def create_event(cid: int, payload: dict = Body(...), _: dict = WRITE) -> dict:
        return p.create_event(cid, payload)

    @app.delete("/api/cases/{cid}/events/{evid}", status_code=204)
    def delete_event(cid: int, evid: int, _: dict = WRITE) -> Response:
        p.delete_event(cid, evid)
        return Response(status_code=204)

    @app.get("/api/cases/{cid}/tasks")
    def tasks(cid: int, _: dict = READ) -> list[dict]:
        return p.list_tasks(cid)

    @app.post("/api/cases/{cid}/tasks", status_code=201)
    def create_task(cid: int, payload: dict = Body(...), _: dict = WRITE) -> dict:
        return p.create_task(cid, payload)

    @app.post("/api/cases/{cid}/tasks/generate")
    def generate_tasks(cid: int, _: dict = WRITE) -> list[dict]:
        return p.generate_tasks(cid)

    @app.patch("/api/cases/{cid}/tasks/{tid}")
    def update_task(cid: int, tid: int, payload: dict = Body(...), _: dict = WRITE) -> dict:
        return p.update_task(cid, tid, payload)

    @app.delete("/api/cases/{cid}/tasks/{tid}", status_code=204)
    def delete_task(cid: int, tid: int, _: dict = WRITE) -> Response:
        p.delete_task(cid, tid)
        return Response(status_code=204)

    @app.get("/api/cases/{cid}/audit")
    def audit(cid: int, _: dict = READ) -> list[dict]:
        return p.audit(cid)

    # ---------------------------------------------------------------- Export
    @app.get("/api/cases/{cid}/export/dossier.docx")
    def export_dossier(cid: int, include_unreviewed: bool = False, include_audit: bool = True, include_graph: bool = True, case: dict = READ) -> Response:
        opts = {"include_unreviewed": include_unreviewed, "include_audit": include_audit, "include_graph": include_graph}
        export_id = p.register_export(cid, "Dossier", options=opts)
        subj = p.subject(cid)
        content = build_dossier(p, cid, opts, export_id=export_id)
        p.finish_export(export_id, content)
        label = case["codename"] if ops.level(case["opsec_level"]).codename and case["codename"] else (subj["label"] if subj else case["title"])
        name = f"Dossier_{safe_filename(label)}_{case['reference']}_{export_id}.docx"
        return _download(content, name, DOCX)

    @app.get("/api/cases/{cid}/export/poster.docx")
    def export_poster(cid: int, case: dict = READ) -> Response:
        export_id = p.register_export(cid, "Suchplakat")
        try:
            content = build_poster(p, cid, export_id)
            p.finish_export(export_id, content)
        except ValueError as exc:
            raise Invalid(str(exc)) from exc
        subj = p.subject(cid)
        return _download(content, f"Suchplakat_{safe_filename(subj['label'] if subj else case['title'])}.docx", DOCX)

    @app.get("/api/cases/{cid}/export/case.json")
    def export_json(cid: int, case: dict = READ) -> Response:
        export_id = p.register_export(cid, "Falldaten (JSON)")
        payload = {"export_id": export_id, "case": case, "entities": p.list_entities(cid), "links": p.list_links(cid), "findings": p.list_findings(cid),
                   "events": p.list_events(cid), "tasks": p.list_tasks(cid), "audit": p.audit(cid)}
        content = json.dumps(payload, ensure_ascii=False, indent=2).encode()
        p.finish_export(export_id, content)
        p.log(cid, "Datenexport (JSON)", f"Vollständiger Fallexport · {export_id}")
        return _download(content, f"Fall_{case['reference']}_{export_id}.json", "application/json")

    # ---------------------------------------------------------------- Oberfläche
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    # ---------------------------------------------------------------- Automatische Sicherung
    if start_scheduler and settings.backup_hour.strip().isdigit():
        hour = int(settings.backup_hour)

        def scheduler() -> None:
            while True:
                try:
                    now = datetime.now()
                    last = db.scalar("SELECT value FROM settings WHERE key = 'last_auto_backup'") or ""
                    if now.hour == hour and last != now.date().isoformat():
                        path = create_backup(db, vault, settings.data_dir, settings.resolved_backup_dir, settings.backup_passphrase)
                        prune_backups(settings.resolved_backup_dir, settings.backup_keep)
                        db.execute("DELETE FROM settings WHERE key = 'last_auto_backup'")
                        db.insert("settings", {"key": "last_auto_backup", "value": now.date().isoformat()}, returning=False)
                        current_user.set(None)
                        p.log(None, "Automatische Sicherung", path.name)
                    auth.purge_sessions()
                except Exception:  # noqa: BLE001 - Scheduler darf nie sterben
                    log.exception("Automatische Sicherung fehlgeschlagen")
                time.sleep(300)

        threading.Thread(target=scheduler, name="eagleeye-backup", daemon=True).start()

    return app
