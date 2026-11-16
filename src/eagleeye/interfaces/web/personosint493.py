"""Build 493: controlled PersonOSINT JSON -> canonical EagleEye research leads.

No PersonOSINT code/database is executed or connected. External export fields
are untrusted input; the existing research483 provenance/audit workflow owns
all writes. Import never creates entities, relationships, Claims or Evidence.
"""
from __future__ import annotations

import hashlib
from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.datastructures import UploadFile

from eagleeye.application.personosint493 import (
    MAX_EXPORT_BYTES, PersonOSINTImportError, parse_personosint_export,
)
from .app364 import CSRF_COOKIE
from .findings478 import verify_post
from .operations476 import case_access, page
from .research483 import MAX_LEADS, listed, propose, validate_public_lead_url

MAX_REQUEST_BYTES = MAX_EXPORT_BYTES + 16_384


async def _bounded_multipart(request: Request):
    """Bound total multipart size before Starlette handles any upload."""
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_REQUEST_BYTES:
            raise HTTPException(413, "PersonOSINT-Export ist zu groß (max. 1 MB).")
        raw.extend(chunk)

    async def receive():
        return {"type": "http.request", "body": bytes(raw), "more_body": False}

    return await Request(request.scope, receive=receive).form(
        max_files=1, max_fields=4, max_part_size=4096
    )


def attach_personosint493(app, build: str) -> None:
    ctx = app.state.context
    app.state.personosint493 = True

    @app.get("/workbench/personosint493", response_class=HTMLResponse)
    def intake_page(request: Request, case_id: str = ""):
        user, case = case_access(app, request, case_id)
        allowed = "research.run" in ctx.team_governance_359.effective_capabilities(user, case_id)
        token = escape(request.cookies.get(CSRF_COOKIE, ""), quote=True)
        body = (
            "<p>Übernahme aus PersonOSINT 1.4 in die vorhandene EagleEye-Fallakte: "
            "<strong>nur öffentliche HTTPS-Recherchehinweise</strong>, keine Identitäten, "
            "Prüfentscheidungen, Belege, Nutzerkonten oder fremde Falldatenbanken.</p>"
            "<p>Bitte PersonOSINT unter Dossier &amp; Export → Falldaten (JSON) exportieren. "
            "Die Datei wird nicht dauerhaft auf EagleEye gespeichert.</p>"
        )
        if allowed:
            body += (
                '<form method="post" action="/workbench/personosint493" enctype="multipart/form-data">'
                '<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
                '<input type="hidden" name="csrf" value="' + token + '">'
                '<label for="po-export">PersonOSINT-Fallexport (.json, max. 1 MB)</label>'
                '<input id="po-export" name="export" type="file" accept=".json,application/json" required>'
                '<label><input type="checkbox" name="confirm" value="yes" required>'
                ' Externe Treffer ausdrücklich nur als ungeprüfte Suchhinweise in diesen Fall übernehmen.</label>'
                '<button type="submit">Kontrolliert übernehmen</button></form>'
            )
        else:
            body += "<p>Für einen Import fehlt die Berechtigung zur Recherche.</p>"
        body += ('<p><a href="/workbench/leads483?' +
                 escape(urlencode({"case_id": case_id}), quote=True) +
                 '">Ungeprüfte Suchhinweise ansehen</a></p>')
        return HTMLResponse(page("PersonOSINT – kontrollierte Übernahme", case_id, body, build),
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    @app.post("/workbench/personosint493")
    async def intake_post(request: Request):
        form = await _bounded_multipart(request)
        try:
            case_id = str(form.get("case_id") or "")
            user, _case = case_access(app, request, case_id, capability="research.run")
            verify_post(app, request, user, form.get("csrf", ""))
            if form.get("confirm") != "yes":
                raise HTTPException(422, "Ausdrückliche Übernahmebestätigung erforderlich.")
            uploaded = form.get("export")
            if not isinstance(uploaded, UploadFile) or not str(uploaded.filename or "").lower().endswith(".json"):
                raise HTTPException(422, "Eine PersonOSINT-JSON-Datei ist erforderlich.")
            contents = await uploaded.read(MAX_EXPORT_BYTES + 1)
            try:
                preview = parse_personosint_export(contents)
            except PersonOSINTImportError as exc:
                raise HTTPException(422, str(exc)) from exc

            # Validate ALL candidates against EagleEye's canonical URL policy
            # before any insert, so one bad URL cannot leave a partial import.
            for lead in preview.leads:
                validate_public_lead_url(lead.url)
            current = listed(ctx, case_id)
            existing = {entry["url"] for entry in current}
            new = [lead for lead in preview.leads if lead.url not in existing]
            if len(existing) + len(new) > MAX_LEADS:
                raise HTTPException(409, "Der Fall überschreitet das Limit von 250 Recherchehinweisen.")
            with ctx.audit.actor_scope(user["username"]), ctx.db.transaction(immediate=True):
                for lead in new:
                    propose(ctx, user, case_id, lead.url, lead.title, lead.note)
                ctx.audit.log(
                    "personosint_export_leads_intake_493", "research_leads_483", case_id,
                    case_id, {
                        "foreign_case_ref_sha256": hashlib.sha256(preview.foreign_case.encode()).hexdigest(),
                        "imported": len(new), "duplicates": len(preview.leads) - len(new),
                        "skipped_in_source": preview.skipped,
                        "evidence_created": False, "identity_confirmed": False,
                        "external_database_connected": False,
                    }
                )
            return RedirectResponse(
                "/workbench/leads483?" + urlencode({"case_id": case_id}),
                status_code=303,
            )
        finally:
            await form.close()
