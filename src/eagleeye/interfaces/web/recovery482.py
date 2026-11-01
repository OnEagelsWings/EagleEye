"""Build 482: restore real legacy DorkEngine and Build-354 local image inspection.

All routes require an authenticated, operational case. Nothing automatically
queries external search engines or upgrades image similarities into identity.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import PurePath
from urllib.parse import urlencode

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from eagleeye_pro.providers.dork_engine import DorkEngine, ENGINES
from eagleeye_pro.security.policy import PolicyGate
from .app364 import CSRF_COOKIE
from .findings478 import verify_post
from .operations476 import case_access, page

MAX_IMAGE = 20 * 1024 * 1024
MAX_MULTIPART = MAX_IMAGE + 32768
SEARCH_ENGINES = ("Google", "Bing", "DuckDuckGo", "Brave", "Mojeek")
IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif", "image/tiff", "image/bmp"}


def _case_url(route, cid, **kwargs):
    return escape(route + "?" + urlencode({"case_id": cid, **kwargs}), quote=True)


def _metadata(asset):
    metadata = asset.get("metadata") or {}
    if not isinstance(metadata, dict):
        return {}
    inspection = metadata.get("inspection") or {}
    return inspection if isinstance(inspection, dict) else {}


def attach_recovery482(app, build):
    ctx = app.state.context

    @app.get("/workbench/dorks482", response_class=HTMLResponse)
    def dork_workspace(request: Request, case_id: str = "", topic: str = "",
                       domain: str = "", engine: str = "DuckDuckGo"):
        user, case = case_access(app, request, case_id)
        del user
        topic = " ".join(topic.split())
        domain = " ".join(domain.split()).lower()
        if len(topic) > 180 or len(domain) > 120:
            raise HTTPException(422, "Suchparameter zu lang.")
        if domain and (not all(c.isalnum() or c in ".-" for c in domain)
                       or domain.startswith("-") or domain.endswith("-")
                       or ".." in domain or "." not in domain):
            raise HTTPException(422, "Nur vollständige öffentliche Domainnamen eingeben.")
        if engine not in SEARCH_ENGINES:
            raise HTTPException(422, "Unbekannter Suchanbieter.")
        if topic and not PolicyGate.evaluate_query(topic).get("ok"):
            raise HTTPException(422, "Suchanfrage durch OPSEC-Regeln gesperrt.")
        rows = []
        if topic:
            generated = DorkEngine(ctx.db, ctx.audit).generate_queries({
                "name": topic, "domains_json": [domain] if domain else [],
                "aliases_json": [], "companies_json": [], "usernames_json": [],
                "emails_json": [], "locations_json": [],
            })
            # Use the existing provider URLs; there is no server-side fetch.
            tasks = DorkEngine(ctx.db, ctx.audit).build_search_urls(
                generated[:18], [engine]
            )
            for task in tasks:
                link = str(task["url"])
                if not link.startswith(("https://www.", "https://duckduckgo.com/",
                                        "https://search.brave.com/", "https://www.mojeek.com/")):
                    continue
                rows.append(
                    "<tr><td>" + escape(task["category"]) + "</td><td>" +
                    escape(task["query"]) + "</td><td><a target=\"_blank\" "
                    "rel=\"noopener noreferrer\" referrerpolicy=\"no-referrer\" href=\"" +
                    escape(link, quote=True) + "\">Im Suchdienst öffnen</a></td></tr>"
                )
        form = (
            '<section class="card"><h2>1. Suchstrategie vorbereiten</h2>'
            '<p>Die vorhandene Dork-Engine erzeugt öffentliche Suchanfragen.'
            ' Keine automatischen Treffer und keine Hintergrundsuche.</p>'
            '<form method="get" action="/workbench/dorks482">'
            '<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
            '<label>Organisation, Thema oder öffentliche Kennung</label>'
            '<input name="topic" required maxlength="180" value="' + escape(topic, quote=True) + '">'
            '<label>Optional: öffentliche Domain, z. B. example.org</label>'
            '<input name="domain" maxlength="120" value="' + escape(domain, quote=True) + '">'
            '<label>Suchdienst</label><select name="engine">' +
            "".join('<option value="' + escape(k, quote=True) + '"' +
                    (" selected" if engine == k else "") + '>' + escape(k) +
                    '</option>' for k in SEARCH_ENGINES) +
            '</select><button type="submit">Dorks erzeugen</button></form></section>'
        )
        results = (
            '<section class="card"><h2>2. Recherchelinks (' + str(len(rows)) +
            ')</h2><p>Jeder Klick öffnet den Suchanbieter direkt im Browser.'
            ' Dabei werden die Suchbegriffe an diesen Anbieter übertragen.'
            ' Suchlinks sind <strong>keine gesicherten Belege</strong>.'
            ' Bei personenbezogenen Begriffen vorher Auftrag und Rechtsgrundlage prüfen.</p>'
            '<table><thead><tr><th>Typ</th><th>Abfrage</th><th>Öffnen</th></tr></thead><tbody>' +
            "".join(rows) + '</tbody></table></section>'
            if topic else '<p>Suchthema eingeben, um vorhandene Dork-Methoden zu nutzen.</p>'
        )
        body = (
            '<p>Fall: <strong>' + escape(str(case.get("title") or "")) + '</strong>.'
            ' Recherchieren → öffentlichen Treffer prüfen → Originalbeleg in EagleEye speichern.'
            ' Keine automatisierten Suchabfragen oder Speicherung der eingegebenen Suchbegriffe'
            ' durch dieses Werkzeug; die Browser-URL enthält die Eingabe.</p>' +
            form + results +
            '<section class="card"><h2>3. Gefundene Quelle sichern</h2>'
            '<p>Originaldokument prüfen und importieren; danach als ungeprüfte Evidence'
            ' registrieren. Links allein stellen keine Provenienz sicher.</p>'
            '<p><a href="' + _case_url("/documents458", case_id) +
            '">Dokument importieren</a> · <a href="' +
            _case_url("/workbench/bridge481", case_id) +
            '">Quelle → Evidence</a></p></section>'
        )
        return HTMLResponse(
            page("Dork-Recherche und öffentliche Suchlinks", case_id, body, build),
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                     "X-Content-Type-Options": "nosniff"}
        )

    @app.get("/workbench/images482", response_class=HTMLResponse)
    def image_workspace(request: Request, case_id: str = ""):
        user, case = case_access(app, request, case_id)
        del user
        assets = ctx.build354.image_assets(case_id=case_id, limit=100)
        blocks = []
        for asset in assets:
            aid = str(asset["media_id"])
            meta = _metadata(asset)
            security = str(asset.get("review_status") or (asset.get("metadata") or {}).get("security_state") or "unreviewed")
            dims = str(meta.get("width") or meta.get("width_px") or "?") + " × " + str(
                meta.get("height") or meta.get("height_px") or "?")
            preview = (
                '<img style="max-width:280px;max-height:230px;object-fit:contain" '
                'alt="Lokal geprüftes Bild – keine automatische Identifizierung" src="' +
                _case_url("/workbench/image482/" + aid, case_id) + '">'
                if security != "quarantined" else
                '<p>Bild ist in Quarantäne und wird nicht angezeigt.</p>'
            )
            blocks.append(
                '<section class="card"><h2>Bildobjekt ' + escape(aid) + '</h2>' +
                preview + '<p>Erfasst: ' + escape(str(asset.get("created_at") or "?")) +
                ' · Status: <strong>' + escape(security) + '</strong></p>'
                '<p>Abmessungen: ' + escape(dims) + '</p>'
                '<p>SHA-256: <code>' + escape(str(asset.get("sha256") or
                    meta.get("sha256") or "im Originalobjekt gespeichert")) + '</code></p>'
                '<details><summary>Technische Bildprüfung und Metadaten</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere">' +
                escape(json.dumps(meta, ensure_ascii=False, indent=2, default=str)[:12000]) +
                '</pre></details></section>'
            )
        form = (
            '<section class="card"><h2>Bild zur Fallakte hinzufügen</h2>'
            '<p>Verwendet die bereits vorhandene lokale Bildprüfung und Ähnlichkeitsanalyse'
            ' aus Build 353/354. EXIF- und GPS-Angaben sind Metadaten, keine bestätigten'
            ' Orts- oder Identitätsbeweise. Maximal 20 MB.</p>'
            '<form method="post" action="/workbench/images482" enctype="multipart/form-data">'
            '<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
            '<input type="hidden" name="csrf" value="' +
            escape(request.cookies.get(CSRF_COOKIE, ""), quote=True) + '">'
            '<label>Originalbild auswählen</label>'
            '<input type="file" name="image" accept="image/png,image/jpeg,image/webp,image/gif,image/tiff,image/bmp" required>'
            '<button type="submit">Lokal prüfen und sichern</button></form></section>'
        )
        body = (
            '<p>Fall: <strong>' + escape(str(case.get("title") or "")) +
            '</strong> · ' + str(len(assets)) + ' gesicherte Bildbelege.</p>' +
            form + '<h2>Bildakte – Prüfstatus statt Identitätsbehauptungen</h2>' +
            '<div class="grid">' + "".join(blocks) + '</div>' +
            ('<p>Noch keine Bilder importiert.</p>' if not blocks else '') +
            '<p><a href="' + _case_url("/graph464", case_id) +
            '">Verbindungen im bestehenden Graph prüfen</a></p>'
        )
        return HTMLResponse(
            page("Bildakte und lokale Metadatenprüfung", case_id, body, build),
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
        )

    @app.post("/workbench/images482")
    async def upload_image(request: Request):
        size = int(request.headers.get("content-length", "0") or 0)
        if size > MAX_MULTIPART:
            raise HTTPException(413, "Bild-Upload überschreitet 20 MB.")
        try:
            async with request.form(max_files=1, max_fields=5, max_part_size=MAX_MULTIPART) as fields:
                case_id = str(fields.get("case_id") or "")
                user, _case = case_access(app, request, case_id, capability="research.run")
                verify_post(app, request, user, fields.get("csrf", ""))
                source = fields.get("image")
                if not isinstance(source, UploadFile):
                    raise HTTPException(422, "Eine Bilddatei muss ausgewählt werden.")
                data = await source.read(MAX_IMAGE + 1)
                if not data or len(data) > MAX_IMAGE:
                    raise HTTPException(413, "Bild leer oder über 20 MB.")
                declared = str(source.content_type or "").split(";", 1)[0].lower()
                if declared not in IMAGE_TYPES:
                    raise HTTPException(422, "Nur unterstützte lokale Bildformate erlaubt.")
                filename = str(source.filename or "Bild").replace("\\", "/").split("/")[-1][:160]
                try:
                    with ctx.audit.actor_scope(user["username"]):
                        ctx.build354.ingest_image(
                            case_id=case_id, content=data,
                            declared_media_type=declared, filename=filename,
                            provenance={
                                "ui": "case_workbench482",
                                "human_import": True,
                                "truth_or_identity_verified": False,
                            }
                        )
                except (ValueError, PermissionError) as exc:
                    raise HTTPException(422, "Bildprüfung verweigert: " + str(exc)[:250]) from exc
        except HTTPException:
            raise
        return RedirectResponse(
            "/workbench/images482?" + urlencode({"case_id": case_id}), status_code=303
        )

    @app.get("/workbench/image482/{media_id}")
    def case_image(request: Request, media_id: str, case_id: str = ""):
        user, _case = case_access(app, request, case_id)
        del user
        try:
            asset = ctx.build354.image_asset(media_id)
        except KeyError:
            raise HTTPException(404, "Bild nicht vorhanden.") from None
        if str(asset.get("case_id")) != case_id:
            raise HTTPException(403, "Bild gehört nicht zu diesem Fall.")
        meta = asset.get("metadata") or {}
        security = str(asset.get("review_status") or meta.get("security_state") or "")
        if security == "quarantined":
            raise HTTPException(403, "Quarantänisiertes Bild darf nicht angezeigt werden.")
        raw = ctx.build354.build353.build352.artifact_bytes(asset["object_ref"])
        media_type = str(_metadata(asset).get("magic_media_type") or "")
        if media_type not in IMAGE_TYPES:
            # Do not let a stored metadata field produce arbitrary active HTML/SVG.
            raise HTTPException(422, "Kein zulässiges Bildformat.")
        return Response(
            raw, media_type=media_type,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "default-src 'none'; sandbox",
                "Referrer-Policy": "no-referrer",
            },
        )
