from __future__ import annotations

import hashlib
from html import escape
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .app459 import create_workspace_app459
from .app448 import COOKIE
from .app449 import _drop


def create_workspace_app461(*, base_dir=None, workspace_build="461.0", workspace_title="Guided Investigator Workspace"):
    """Review-first, case-authorized workflow guide; no autonomous actions."""
    app = create_workspace_app459(
        base_dir=base_dir,
        workspace_build=workspace_build,
        workspace_title=workspace_title,
    )
    ctx = app.state.context
    team = ctx.team_identity_359
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health461():
        integrity = bool(ctx.build458.build458_status().get("integrity_valid", False))
        return {
            "ok": True, "status": "ok" if integrity else "hold",
            "integrity_valid": integrity, "build": "461.0",
            "production_release_ready": False, "next_checkpoint": "465.0",
        }

    @app.get("/workflow461", response_class=HTMLResponse)
    def workflow461(request: Request, case_id: str = ""):
        fingerprint = hashlib.sha256("|".join((
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.client.host if request.client else "",
        )).encode()).hexdigest()
        identity = team.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=fingerprint,
            touch=True,
        )
        if not identity:
            return RedirectResponse(
                "/security/bootstrap" if team.bootstrap_required() else "/security/login",
                status_code=303,
            )
        cases = ctx.team_governance_359.visible_cases(identity)
        selected = next((case for case in cases if str(case.get("case_id")) == case_id), None)
        if selected is None:
            return RedirectResponse("/", status_code=303)
        case_id = str(selected["case_id"])
        steps = (
            ("research", "1. Rechercheauftrag eingrenzen"),
            ("documents", "2. Dokumente und Fundstellen prüfen"),
            ("claims", "3. Claims und Gegenbelege abgleichen"),
            ("analysis", "4. Verbindungen und Zeitachse untersuchen"),
            ("dossier", "5. Dossier und Unsicherheiten kontrollieren"),
        )
        items = []
        for view, label in steps:
            target = (
                "/documents458?" + urlencode({"case_id": case_id})
                if view == "documents" else
                "/?" + urlencode({"case_id": case_id, "view": view})
            )
            items.append(
                '<li><a href="' + escape(target, quote=True) + '">'
                + escape(label) + '</a></li>'
            )
        home = "/?" + urlencode({"case_id": case_id})
        return HTMLResponse(
            '<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>EagleEye 461 · Ermittlungsweg</title>'
            '<style>body{font:1rem system-ui;max-width:52rem;margin:2rem auto;'
            'padding:0 1.2rem;background:#0b1524;color:#eaf2ff;line-height:1.65}'
            'a{color:#80daca}li{padding:.6rem 0}a:focus-visible{outline:3px solid #fff}'
            '.notice{border:1px solid #52718d;padding:1rem;border-radius:.7rem}</style>'
            '</head><body><main><p><a href="' + escape(home, quote=True)
            + '">← Zur Fallübersicht</a></p><h1>Ermittlungsweg · Build 461</h1>'
            '<p>Fall: ' + escape(str(selected.get("title", ""))) + '</p>'
            '<div class="notice">Alle Schritte sind fallbezogen. Erkenntnisse und '
            'Identitätszuordnungen benötigen menschliche Prüfung. '
            'Keine automatische Rechercheausführung.</div>'
            '<ol>' + "".join(items) + '</ol></main></body></html>',
            headers={"Cache-Control": "no-store"},
        )

    return app


create_app = create_workspace_app461
