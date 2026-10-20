"""Build 462: case-authorized interactive entity and relationship workbench."""
from __future__ import annotations

import hashlib
from html import escape
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from eagleeye.application.entity_registry461 import EntityRegistry461, KINDS
from .app461 import create_workspace_app461
from .app448 import COOKIE
from .app449 import _drop


def create_workspace_app462(*, base_dir=None):
    app = create_workspace_app461(
        base_dir=base_dir, workspace_build="462.0",
        workspace_title="Interactive Case Intelligence",
    )
    ctx = app.state.context
    team = ctx.team_identity_359
    path = (Path(base_dir) if base_dir is not None else Path.home() / ".eagleeye") / "entity_registry_462.sqlite3"
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health462():
        integrity = bool(ctx.build458.build458_status().get("integrity_valid", False))
        return {"ok": True, "build": "462.0", "status": "ok" if integrity else "hold",
                "integrity_valid": integrity, "production_release_ready": False,
                "next_checkpoint": "465.0"}

    def authorize(request: Request, case_id: str):
        fingerprint = hashlib.sha256("|".join((
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.client.host if request.client else "",
        )).encode()).hexdigest()
        identity = team.validate_session(
            request.cookies.get(COOKIE, ""),
            client_fingerprint=fingerprint, touch=True,
        )
        if not identity:
            return None, RedirectResponse(
                "/security/bootstrap" if team.bootstrap_required() else "/security/login",
                status_code=303,
            )
        selected = next((case for case in ctx.team_governance_359.visible_cases(identity)
                         if str(case.get("case_id")) == case_id), None)
        if selected is None:
            return None, RedirectResponse("/", status_code=303)
        return selected, None

    @app.get("/entities462", response_class=HTMLResponse)
    def entities_page(request: Request, case_id: str = "", message: str = ""):
        selected, redirect = authorize(request, case_id)
        if redirect is not None:
            return redirect
        with EntityRegistry461(path) as store:
            graph = store.graph(case_id)
        nodes = graph["entities"]
        edges = graph["relations"]
        back = "/?" + urlencode({"case_id": case_id})
        q = escape(case_id, quote=True)
        option_nodes = "".join(
            '<option value="' + escape(item["id"], quote=True) + '">' +
            escape(item["label"]) + " (" + escape(item["kind"]) + ")</option>"
            for item in nodes
        )
        kind_opts = "".join('<option value="' + escape(k) + '">' + escape(k) + "</option>" for k in sorted(KINDS))
        listing = "".join("<li><b>" + escape(n["label"]) + "</b> · " + escape(n["kind"])
                          + (" — " + escape(n["notes"]) if n["notes"] else "") + "</li>" for n in nodes)
        by_id = {n["id"]: n["label"] for n in nodes}
        links = "".join(
            "<li>" + escape(by_id.get(r["source_id"], "unbekannt")) + " → "
            + escape(r["predicate"]) + " → "
            + escape(by_id.get(r["target_id"], "unbekannt"))
            + " · <em>" + escape(r["state"]) + "</em>"
            + " · Quellenverweis: " + ", ".join(escape(s["source_ref"]) for s in r["sources"])
            + " (nicht unabhängig verifiziert)</li>" for r in edges
        )
        info = "<p role='status'>" + escape(message) + "</p>" if message in {"entity_saved", "relation_saved"} else ""
        return HTMLResponse(
            '<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>EagleEye 462 · Entitäten</title>'
            '<style>body{font:1rem system-ui;max-width:70rem;margin:2rem auto;padding:0 1rem;'
            'background:#101b2c;color:#eef4ff;line-height:1.6}'
            'a{color:#7ee0d1}input,select,button{padding:.7rem;font:inherit;margin:.25rem}'
            'input,select{background:#192a40;color:white;border:1px solid #63788e}'
            'button{background:#77dac7;color:#102030;border:0;cursor:pointer}'
            'section{border:1px solid #4a5f76;padding:1rem;border-radius:.7rem;margin:1rem 0}'
            'label{display:block} :focus-visible{outline:3px solid #fff}'
            '.note{color:#c5d8e9}</style></head><body><main>'
            '<p><a href="' + escape(back,quote=True) + '">← Zur Fallübersicht</a></p>'
            '<h1>Entitäten und Beziehungen · Build 462</h1><p>Fall: <strong>' +
            escape(str(selected.get("title",""))) + '</strong></p>' + info +
            '<section><h2>Entität anlegen</h2><form method="post" action="/entities462/create">'
            '<input type="hidden" name="case_id" value="' + q + '">'
            '<label>Typ<select name="kind" required>' + kind_opts + '</select></label>'
            '<label>Name<input name="label" maxlength="512" required></label>'
            '<label>Notiz<input name="notes" maxlength="10000"></label>'
            '<button type="submit">Entität speichern</button></form></section>'
            '<section><h2>Gespeicherte Entitäten (' + str(len(nodes)) + ')</h2><ul>' + listing + '</ul></section>'
            '<section><h2>Beziehung mit Quellenverweis anlegen</h2>'
            '<p class="note">Ein Quellenverweis ist kein überprüfter Beleg. Neue Beziehungen sind Hypothesen.</p>'
            '<form method="post" action="/entities462/link">'
            '<input type="hidden" name="case_id" value="' + q + '">'
            '<label>Von<select name="source_id" required>' + option_nodes + '</select></label>'
            '<label>Zu<select name="target_id" required>' + option_nodes + '</select></label>'
            '<label>Beziehung<input name="predicate" maxlength="128" required></label>'
            '<label>Quellen-ID oder Fundort<input name="source_ref" maxlength="256" required></label>'
            '<button type="submit">Beziehung speichern</button></form></section>'
            '<section><h2>Beziehungen (' + str(len(edges)) + ')</h2><ul>' + links + '</ul></section>'
            '</main></body></html>',
            headers={"Cache-Control": "no-store"},
        )

    def same_origin(request: Request) -> bool:
        origin = request.headers.get("origin", "")
        host = request.headers.get("host", "")
        # Browsers submit Origin on cross-site POST; reject those submissions.
        from urllib.parse import urlsplit
        return not origin or (urlsplit(origin).netloc == host and urlsplit(origin).scheme in {"http", "https"})

    @app.post("/entities462/create")
    async def entity_create(request: Request):
        data = await request.form()
        case_id = str(data.get("case_id", ""))
        selected, redirect = authorize(request, case_id)
        if redirect is not None:
            return redirect
        if not same_origin(request):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Cross-origin submission denied")
        try:
            with EntityRegistry461(path) as store:
                store.create_entity(case_id=case_id, kind=str(data.get("kind", "")),
                                    label=str(data.get("label", "")), notes=str(data.get("notes", "")))
        except ValueError as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return RedirectResponse("/entities462?" + urlencode({"case_id": case_id, "message": "entity_saved"}), status_code=303)

    @app.post("/entities462/link")
    async def relation_create(request: Request):
        data = await request.form()
        case_id = str(data.get("case_id", ""))
        selected, redirect = authorize(request, case_id)
        if redirect is not None:
            return redirect
        if not same_origin(request):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Cross-origin submission denied")
        try:
            with EntityRegistry461(path) as store:
                store.create_relation(case_id=case_id, source_id=str(data.get("source_id","")),
                                      target_id=str(data.get("target_id","")),
                                      predicate=str(data.get("predicate","")),
                                      source_refs=[str(data.get("source_ref",""))])
        except ValueError as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return RedirectResponse("/entities462?" + urlencode({"case_id": case_id, "message": "relation_saved"}), status_code=303)

    return app


create_app = create_workspace_app462
