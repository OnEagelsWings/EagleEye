"""Build 494: reviewer workbench for PersonOSINT entities; no graph auto-write."""
from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.datastructures import UploadFile

from eagleeye.application.personosint493 import MAX_EXPORT_BYTES, PersonOSINTImportError
from eagleeye.application import personosint494 as integration
from .app364 import CSRF_COOKIE
from .findings478 import bounded_form, verify_post
from .operations476 import case_access, page
from .personosint493 import _bounded_multipart


def attach_personosint494(app, build: str) -> None:
    ctx = app.state.context
    integration.initialize(ctx)
    app.state.personosint494 = True

    @app.get("/workbench/personosint494", response_class=HTMLResponse)
    def review_page(request: Request, case_id: str = ""):
        user, _case = case_access(app, request, case_id)
        allowed = "research.run" in ctx.team_governance_359.effective_capabilities(user, case_id)
        rows = integration.candidates(ctx, case_id)
        token = escape(request.cookies.get(CSRF_COOKIE, ""), quote=True)
        body = (
            "<p>PersonOSINT-Entitäten erscheinen nur als <strong>unbestätigte Prüfangebote</strong>. "
            "Es werden keine Identitäten, Beziehungen, Fotos oder persönlichen Identifikatoren automatisch in "
            "den EagleEye-Graph übernommen. Jede Person muss erst die Beleglage prüfen.</p>"
        )
        if allowed:
            body += (
                '<section class="card"><h2>Entitäten aus JSON aufnehmen</h2>'
                '<form method="post" action="/workbench/personosint494" enctype="multipart/form-data">'
                '<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
                '<input type="hidden" name="csrf" value="' + token + '">'
                '<label for="entity-export">PersonOSINT-Fallexport (JSON, bis 1 MB)</label>'
                '<input type="file" id="entity-export" name="export" accept=".json,application/json" required>'
                '<label><input type="checkbox" name="confirm" value="yes" required> '
                'Entitäten ausdrücklich nur zur späteren manuellen Prüfung vormerken.</label>'
                '<button type="submit">Entitäten als Vorschläge aufnehmen</button></form></section>'
            )
        body += "<h2>Entitätsvorschläge (" + str(len(rows)) + ")</h2>"
        for candidate in rows:
            status = candidate["state"]
            body += (
                '<section class="card"><h3>' + escape(candidate["label"]) + '</h3>'
                '<p>Typ: ' + escape(candidate["kind"]) + ' · Zustand: ' + escape(status) + '</p>'
                '<p>Quelle: externer Fallexport, unverifizierte Identität.</p>'
            )
            if status == "unreviewed" and allowed:
                body += (
                    '<form method="post" action="/workbench/personosint494/review">'
                    '<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
                    '<input type="hidden" name="csrf" value="' + token + '">'
                    '<input type="hidden" name="candidate_id" value="' +
                    escape(candidate["candidate_id"], quote=True) + '">'
                    '<label>Prüfentscheidung</label><select name="decision">'
                    '<option value="for_manual_entry">Zur manuellen Erfassung vormerken</option>'
                    '<option value="dismissed">Verwerfen</option></select>'
                    '<label>Begründung</label>'
                    '<textarea name="rationale" required minlength="20" maxlength="1200"></textarea>'
                    '<button type="submit">Prüfung protokollieren</button></form>'
                )
            elif status != "unreviewed":
                body += '<p>Prüfvermerk: ' + escape(candidate["rationale"]) + '</p>'
            body += "</section>"
        if not rows:
            body += "<p>Keine Entitätsvorschläge aus PersonOSINT vorhanden.</p>"
        body += (
            '<p><a href="/entities462?' + escape(urlencode({"case_id":case_id}), quote=True) +
            '">Geprüfte Entitäten manuell in der zentralen Fallakte bearbeiten</a></p>'
        )
        return HTMLResponse(page("PersonOSINT – Entitätenprüfung", case_id, body, build),
                            headers={"Cache-Control": "no-store", "Referrer-Policy":"no-referrer"})

    @app.post("/workbench/personosint494")
    async def import_post(request: Request):
        form = await _bounded_multipart(request)
        try:
            case_id = str(form.get("case_id") or "")
            user, _case = case_access(app, request, case_id, capability="research.run")
            verify_post(app, request, user, form.get("csrf", ""))
            if form.get("confirm") != "yes":
                raise HTTPException(422, "Bestätigung für Vorschläge erforderlich.")
            uploaded = form.get("export")
            if not isinstance(uploaded, UploadFile) or not str(uploaded.filename or "").lower().endswith(".json"):
                raise HTTPException(422, "Eine JSON-Datei aus PersonOSINT ist erforderlich.")
            raw = await uploaded.read(MAX_EXPORT_BYTES + 1)
            try:
                preview = integration.parse_entity_suggestions(raw)
            except PersonOSINTImportError as exc:
                raise HTTPException(422, str(exc)) from exc
            integration.queue(ctx, user, case_id, preview)
            return RedirectResponse(
                "/workbench/personosint494?" + urlencode({"case_id":case_id}), status_code=303
            )
        finally:
            await form.close()

    @app.post("/workbench/personosint494/review")
    async def review_post(request: Request):
        form = await bounded_form(request, max_bytes=9_000)
        case_id = str(form.get("case_id") or "")
        user, _case = case_access(app, request, case_id, capability="research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        try:
            integration.review(ctx, user, case_id, str(form.get("candidate_id") or ""),
                               str(form.get("decision") or ""), str(form.get("rationale") or ""))
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409 if "already" in str(exc) or "integrity" in str(exc) else 422, str(exc)) from exc
        return RedirectResponse(
            "/workbench/personosint494?" + urlencode({"case_id":case_id}), status_code=303
        )
