"""Build 492: secure web evidence, document structure/OCR, source families, network analysis.

UI principles: one entry point in the guided workflow per task, plain German labels,
explicit OPSEC confirmation before any network contact, results always shown as
review material with a link back to the original anchor.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye.application.build488.reviews import reviews_for_case
from eagleeye.application.intel492 import captures, docstructure, entitymatch, lineage, network, webcapture
from .app364 import CSRF_COOKIE
from .findings478 import bounded_form, verify_post
from .operations476 import case_access, page

EXTRA_CSS = ('<style>.ok{color:#9af3de}.bad{color:#ffb4a8}.muted{color:#c2d3e3;font-size:.92rem}'
             '.pill{display:inline-block;border:1px solid #647b93;border-radius:999px;padding:.1rem .6rem;margin:.1rem .2rem .1rem 0;font-size:.85rem}'
             '.stat{font-size:1.6rem;font-weight:700;display:block}.row{display:flex;gap:.6rem;flex-wrap:wrap;align-items:center}'
             '.row form{margin:0}label.check{display:flex;gap:.5rem;align-items:flex-start}label.check input{width:auto;margin:.35rem 0 0}'
             'details summary{cursor:pointer}'
             '@media (max-width:640px){table.stack thead{position:absolute;left:-9999px}'
             'table.stack tr{display:block;border:1px solid #647b93;border-radius:10px;padding:.4rem .8rem;margin:.6rem 0}'
             'table.stack td{display:block;border:0;padding:.25rem 0;word-break:normal;overflow-wrap:anywhere}'
             'table.stack td::before{content:attr(data-label);display:block;font-size:.8rem;color:#c2d3e3}}</style>')


def _stack_tables(html: str) -> str:
    """Give every table cell its column label so narrow screens can show rows as cards."""
    def table(match):
        markup = match.group(0)
        labels = [re.sub(r"<[^>]+>", "", h) for h in re.findall(r"<th>(.*?)</th>", markup)]
        if not labels:
            return markup

        def row(rm):
            cells = iter(labels)
            return re.sub(r"<td(?=[ >])", lambda _: '<td data-label="' + escape(next(cells, ""), quote=True) + '"', rm.group(0))
        body = re.sub(r"<tbody>.*</tbody>", lambda b: re.sub(r"<tr>.*?</tr>", row, b.group(0), flags=re.S), markup, flags=re.S)
        return body.replace("<table>", '<table class="stack">', 1)
    return re.sub(r"<table>.*?</table>", table, html, flags=re.S)


KIND_DE = {"person": "Person", "organization": "Organisation", "company": "Unternehmen", "place": "Ort",
           "event": "Ereignis", "document": "Dokument"}


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _link(path: str, **params) -> str:
    return escape(path + "?" + urlencode(params), quote=True)


def _csrf(request: Request) -> str:
    return escape(request.cookies.get(CSRF_COOKIE, ""), quote=True)


def _can_run(ctx, user, case_id) -> bool:
    return "research.run" in ctx.team_governance_359.effective_capabilities(user, case_id)


def _registry_path(base_dir) -> Path:
    return (Path(base_dir) if base_dir is not None else Path.home() / ".eagleeye") / "entity_registry_462.sqlite3"


def _case_graph(base_dir, case_id: str) -> dict:
    with EntityRegistry461(_registry_path(base_dir)) as store:
        return store.graph(case_id)


def _first_seen(doc: dict, capture: dict | None) -> str:
    if capture:
        return (capture.get("page_published") or capture.get("captured_at") or "")[:19]
    return str(doc.get("created_at") or "")[:19]


def attach_intel492(app, build: str, base_dir) -> None:
    ctx = app.state.context
    captures.initialize(ctx)
    docstructure.initialize(ctx)
    ctx.entity_candidate_matcher = entitymatch.suggest_case_pairs_492
    app.state.intel492 = True

    def render(title, case_id, body, status=200):
        return HTMLResponse(page(title, case_id, EXTRA_CSS + _stack_tables(body), build), status_code=status,
                            headers={"Cache-Control": "no-store"})

    def back(case_id):
        return '<p><a href="' + _link("/workbench/intel", case_id=case_id) + '">← Übersicht Sichern &amp; Auswerten</a></p>'

    # ------------------------------------------------------------------ hub
    @app.get("/workbench/intel", response_class=HTMLResponse)
    def hub(request: Request, case_id: str = ""):
        user, case = case_access(app, request, case_id)
        docs = ctx.document_intelligence_458.documents(identity=user, case_id=case_id)
        caps = captures.captures_for_case(ctx, case_id)
        pdfs = [d for d in docs if d["media_type"] == "application/pdf"]
        enriched = sum(1 for d in pdfs if docstructure.enrichment_for(ctx, d["document_id"]))
        ocr_ok, engine = docstructure.ocr_available()
        graph = _case_graph(base_dir, case_id)

        def card(title, stat, text, path, label):
            return ('<section class="card"><h2>' + escape(title) + '</h2><span class="stat">' + escape(stat) +
                    '</span><p>' + escape(text) + '</p><a href="' + _link(path, case_id=case_id) + '">' +
                    escape(label) + ' →</a></section>')

        body = ('<p>Werkzeuge, um Quellen beweisfest zu sichern und den Fall auszuwerten. Alle Ergebnisse sind '
                '<strong>Prüfmaterial</strong> – sie bestätigen keine Tatsachen und führen nichts automatisch zusammen.</p>'
                '<div class="grid">'
                + card("Webseite als Beleg sichern", _count(len(caps), "Web-Beleg", "Web-Belege"),
                       "Eine öffentliche Seite oder eine archivierte Fassung als WARC-Original sichern; "
                       "der Haupttext wird als prüfbares Dokument mit Textankern angelegt.", "/workbench/intel/web", "Seite sichern")
                + card("Struktur & Texterkennung", f"{enriched} / {len(pdfs)} PDFs ergänzt",
                       "Tabellen, Überschriften und – bei Scans – OCR-Text als zusätzliche Fundstellen anlegen. "
                       + ("Texterkennung verfügbar." if ocr_ok else "Texterkennung nicht installiert."),
                       "/workbench/intel/documents", "Dokumente erschließen")
                + card("Quellenunabhängigkeit", _count(len(docs), "Dokument", "Dokumente"),
                       "Erkennt übernommene und gespiegelte Texte: wie viele unabhängige Ursprünge stehen hinter den Belegen?",
                       "/workbench/intel/lineage", "Quellfamilien ansehen")
                + card("Entitäten abgleichen", _count(len(graph['entities']), "Entität", "Entitäten"),
                       "Mögliche Doppelungen (Schreibweisen, Transliteration, Initialen) mit Begründung prüfen.",
                       "/workbench/entities488", "Kandidaten prüfen")
                + card("Netzwerkanalyse", _count(len(graph['relations']), "Beziehung", "Beziehungen"),
                       "Gruppen, Brückenpersonen und am besten belegte Verbindungswege im Beziehungsgraph.",
                       "/workbench/intel/network", "Netzwerk auswerten")
                + (card("PersonOSINT-Export übernehmen", "Fallimport",
                        "PersonOSINT-JSON manuell in die vorhandene Fallakte übernehmen: nur ungeprüfte öffentliche HTTPS-Links, "
                        "keine Entitäten und keine automatische Evidence.",
                        "/workbench/personosint493", "PersonOSINT-Import öffnen")
                   if getattr(app.state, "personosint493", False) else "")
                + '</div>')
        return render("Sichern & Auswerten", case_id, body)

    # ------------------------------------------------------------- web capture
    def web_page(request, user, case_id, *, url="", message="", error="", redirect=None, snapshots=None, status=200):
        rows = captures.captures_for_case(ctx, case_id)
        allowed = _can_run(ctx, user, case_id)
        token = _csrf(request)
        notice = ""
        if message:
            notice += '<p class="card ok" role="status">' + escape(message) + '</p>'
        if error:
            notice += '<p class="card bad" role="alert">' + escape(error) + '</p>'
        opsec = ('<label class="check"><input type="checkbox" name="opsec" value="yes" required>'
                 '<span>Mir ist bewusst, dass der Zielserver bzw. das Internet Archive diesen Abruf und meine '
                 'IP-Adresse sieht. Die Adresse enthält keine vertraulichen Angaben.</span></label>')
        if redirect:
            notice += ('<section class="card warn"><h2>Die Seite leitet weiter</h2><p>HTTP ' + str(redirect["status"]) +
                       ' nach: <code>' + escape(redirect["location"] or "unbekannt") + '</code></p>'
                       '<p>Weiterleitungen werden nicht automatisch verfolgt. Prüfe das Ziel und sichere es bei Bedarf bewusst.</p>'
                       + ('<form method="post" action="/workbench/intel/web"><input type="hidden" name="case_id" value="' + escape(case_id, quote=True) +
                          '"><input type="hidden" name="csrf" value="' + token + '"><input type="hidden" name="url" value="' +
                          escape(redirect["location"], quote=True) + '">' + opsec + '<button>Weiterleitungsziel sichern</button></form>'
                          if allowed and redirect["location"].startswith(("http://", "https://")) else "") + '</section>')
        if allowed:
            forms = ('<section class="card"><h2>Live-Seite sichern</h2>'
                     '<form method="post" action="/workbench/intel/web"><input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
                     '<input type="hidden" name="csrf" value="' + token + '">'
                     '<label>Öffentliche Adresse<input name="url" type="url" required maxlength="2000" placeholder="https://…" value="' + escape(url, quote=True) + '"></label>'
                     + opsec + '<button>Seite jetzt sichern</button></form>'
                     '<p class="muted">Gespeichert werden: die unveränderte Serverantwort als WARC-Datei (Archivstandard), deren SHA-256 und der '
                     'erkannte Haupttext als Dokument mit Fundstellen. Keine Weiterleitungen, keine internen Adressen, max. 3 MB.</p></section>'
                     '<section class="card"><h2>Archivierte Fassungen (Internet Archive)</h2>'
                     '<form method="post" action="/workbench/intel/web/wayback"><input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
                     '<input type="hidden" name="csrf" value="' + token + '">'
                     '<label>Adresse, deren frühere Fassungen du suchst<input name="archive_url" type="url" required maxlength="2000" value="' + escape(url, quote=True) + '"></label>'
                     '<label class="check"><input type="checkbox" name="opsec" value="yes" required><span>Die Adresse wird an web.archive.org übermittelt.</span></label>'
                     '<button>Fassungen auflisten</button></form></section>')
        else:
            forms = '<p class="card">Du kannst gesicherte Web-Belege ansehen. Zum Sichern ist eine Rechercheberechtigung in diesem Fall nötig.</p>'
        snap_html = ""
        if snapshots is not None:
            if not snapshots:
                snap_html = '<section class="card"><h2>Keine archivierten Fassungen gefunden</h2><p>Das Internet Archive kennt für diese Adresse keine erfolgreichen Aufnahmen.</p></section>'
            else:
                items = ""
                for snap in snapshots:
                    items += ('<tr><td>' + escape(snap["label"]) + '</td><td>' + escape(snap["mimetype"]) + '</td><td>'
                              '<form method="post" action="/workbench/intel/web/archive"><input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
                              '<input type="hidden" name="csrf" value="' + token + '"><input type="hidden" name="timestamp" value="' + escape(snap["timestamp"], quote=True) + '">'
                              '<input type="hidden" name="url" value="' + escape(snap["original"], quote=True) + '"><input type="hidden" name="opsec" value="yes">'
                              '<button>Diese Fassung sichern</button></form></td></tr>')
                snap_html = ('<section class="card"><h2>' + str(len(snapshots)) + ' unterschiedliche archivierte Fassungen</h2>'
                             '<p class="muted">Gleiche Inhalte sind zusammengefasst. Die Sicherung lädt die Originalbytes der Archivaufnahme.</p>'
                             '<table><thead><tr><th>Aufnahme</th><th>Typ</th><th>Aktion</th></tr></thead><tbody>' + items + '</tbody></table></section>')
        table = ""
        for row in rows:
            integrity = '<span class="ok">✓ unverändert</span>' if row["integrity_ok"] else '<span class="bad">✗ Integrität verletzt</span>'
            table += ('<tr><td><a href="' + _link("/documents458", case_id=case_id, document_id=row["document_id"]) + '">' +
                      escape(row["page_title"] or row["url"]) + '</a><br><span class="muted">' + escape(row["url"][:160]) + '</span></td>'
                      '<td>' + ("Archiv" if row["kind"] == "archive" else "Live") + '<br><span class="muted">' + escape(row["captured_at"][:16].replace("T", " ")) + ' UTC</span></td>'
                      '<td>' + escape(row["page_published"] or "–") + '</td><td>' + integrity + '</td>'
                      '<td><a href="' + _link("/workbench/intel/warc", case_id=case_id, capture_id=row["capture_id"]) + '">WARC</a> · '
                      '<a href="' + _link("/workbench/findings", case_id=case_id, document_id=row["document_id"]) + '">Befund notieren</a></td></tr>')
        listing = ('<section class="card"><h2>Gesicherte Web-Belege (' + str(len(rows)) + ')</h2>'
                   + ('<table><thead><tr><th>Seite</th><th>Art / erfasst</th><th>Veröffentlicht laut Seite</th><th>Original</th><th>Weiter</th></tr></thead><tbody>'
                      + table + '</tbody></table>' if rows else '<p>Noch keine Web-Belege gesichert.</p>') + '</section>')
        body = back(case_id) + notice + snap_html + forms + listing
        return render("Webseite als Beleg sichern", case_id, body, status)

    @app.get("/workbench/intel/web", response_class=HTMLResponse)
    def web_view(request: Request, case_id: str = "", done: str = ""):
        user, _ = case_access(app, request, case_id)
        message = {"live": "Seite gesichert. Bitte Haupttext und Fundstellen im Dokument prüfen.",
                   "archive": "Archivierte Fassung gesichert. Bitte Haupttext und Fundstellen prüfen."}.get(done, "")
        return web_page(request, user, case_id, message=message)

    @app.post("/workbench/intel/web/wayback", response_class=HTMLResponse)
    async def wayback_list(request: Request):
        form = await bounded_form(request, max_bytes=8192)
        case_id = str(form.get("case_id") or "")
        user, _ = case_access(app, request, case_id, "research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        archive_url = str(form.get("archive_url") or "").strip()
        if form.get("opsec") != "yes":
            return web_page(request, user, case_id, url=archive_url, error="Bitte die Übermittlung an web.archive.org bestätigen.", status=422)
        try:
            snaps = await run_in_threadpool(webcapture.wayback_snapshots, archive_url)
        except webcapture.CaptureError as exc:
            return web_page(request, user, case_id, url=archive_url, error=str(exc), status=422)
        ctx.audit.log("wayback_listed_492", "web_capture", "", case_id, {"actor": user["username"], "results": len(snaps)})
        return web_page(request, user, case_id, url=archive_url, snapshots=snaps)

    async def _capture_post(request: Request, kind: str):
        form = await bounded_form(request, max_bytes=8192)
        case_id = str(form.get("case_id") or "")
        user, _ = case_access(app, request, case_id, "research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        url = str(form.get("url") or "").strip()
        if form.get("opsec") != "yes":
            return web_page(request, user, case_id, url=url, error="Bitte bestätige den OPSEC-Hinweis vor dem Abruf.", status=422)
        try:
            archive_url = webcapture.wayback_raw_url(str(form.get("timestamp") or ""), url) if kind == "archive" else ""
            result = await run_in_threadpool(webcapture.capture, url, archive_url=archive_url,
                                             kind="Archivfassung" if kind == "archive" else "Live-Seite")
            if result.get("redirect"):
                return web_page(request, user, case_id, url=url, redirect=result)

            def store():
                with ctx.audit.actor_scope(user["username"]):
                    return captures.store_capture(ctx, identity=user, case_id=case_id, result=result, kind=kind)
            await run_in_threadpool(store)
        except webcapture.CaptureError as exc:
            return web_page(request, user, case_id, url=url, error=str(exc), status=422)
        except (ValueError, PermissionError) as exc:
            return web_page(request, user, case_id, url=url, error="Speichern nicht möglich: " + str(exc)[:200], status=422)
        return RedirectResponse("/workbench/intel/web?" + urlencode({"case_id": case_id, "done": kind}), status_code=303)

    @app.post("/workbench/intel/web")
    async def web_capture(request: Request):
        return await _capture_post(request, "live")

    @app.post("/workbench/intel/web/archive")
    async def web_capture_archive(request: Request):
        return await _capture_post(request, "archive")

    @app.get("/workbench/intel/warc")
    def warc_download(request: Request, case_id: str = "", capture_id: str = ""):
        case_access(app, request, case_id)
        try:
            row = captures.capture_row(ctx, capture_id)
        except KeyError:
            raise HTTPException(404, "Web-Beleg nicht gefunden.") from None
        if row["case_id"] != case_id:
            raise HTTPException(403, "Web-Beleg gehört nicht zu diesem Fall.")
        if not captures.verify_capture(ctx, row):
            raise HTTPException(409, "Integrität des Web-Belegs verletzt.")
        return Response(captures.warc_bytes(ctx, row), media_type="application/warc",
                        headers={"Content-Disposition": f'attachment; filename="{capture_id}.warc.gz"',
                                 "Cache-Control": "no-store"})

    # ------------------------------------------------------- documents / OCR
    @app.get("/workbench/intel/documents", response_class=HTMLResponse)
    def documents_view(request: Request, case_id: str = "", done: str = ""):
        user, _ = case_access(app, request, case_id)
        docs = [d for d in ctx.document_intelligence_458.documents(identity=user, case_id=case_id)
                if d["media_type"] == "application/pdf"]
        ocr_ok, engine = docstructure.ocr_available()
        allowed = _can_run(ctx, user, case_id)
        info = ('<p class="card">' + ('<span class="ok">✓ Texterkennung verfügbar</span> (' + escape(engine) + ')'
                if ocr_ok else '<span class="bad">Texterkennung (Tesseract) ist auf diesem Rechner nicht installiert.</span> '
                'Tabellen und Überschriften werden trotzdem erkannt. Für gescannte Seiten Tesseract installieren '
                '(Windows: Installer der UB Mannheim, Sprachpaket Deutsch) und EagleEye neu starten.') + '</p>')
        if done:
            info = '<p class="card ok" role="status">Fundstellen ergänzt. Bitte die Extraktion im Dokument prüfen.</p>' + info
        rows = ""
        for d in docs:
            enr = docstructure.enrichment_for(ctx, d["document_id"])
            if enr:
                state = (f'{enr["tables"]} Tabellen · {enr["headings"]} Überschriften · {enr["ocr_paragraphs"]} OCR-Absätze'
                         + (f' (Ø Erkennungssicherheit {enr["ocr_mean_confidence"]} %)' if enr["ocr_mean_confidence"] is not None else ""))
                action = '<span class="muted">bereits ergänzt</span>'
            else:
                state = "OCR erforderlich" if d["ocr_required"] else "nur Fließtext-Anker"
                if not allowed:
                    action = '<span class="muted">Rechercheberechtigung nötig</span>'
                elif d["state"] != "review_required":
                    action = '<span class="muted">bereits geprüft – nicht mehr ergänzbar</span>'
                else:
                    action = ('<form method="post" action="/workbench/intel/documents"><input type="hidden" name="case_id" value="' + escape(case_id, quote=True) +
                              '"><input type="hidden" name="csrf" value="' + _csrf(request) + '"><input type="hidden" name="document_id" value="' +
                              escape(d["document_id"], quote=True) + '"><button>Fundstellen ergänzen</button></form>')
            rows += ('<tr><td><a href="' + _link("/documents458", case_id=case_id, document_id=d["document_id"]) + '">' + escape(d["title"]) +
                     '</a><br><span class="muted">' + str(d["page_count"]) + ' Seiten</span></td><td>' + escape(state) + '</td><td>' + action + '</td></tr>')
        body = (back(case_id) + '<p>Ergänzt Fundstellen für Tabellen, Überschriften und gescannte Seiten. Bestehende Fundstellen und das '
                'Original bleiben unverändert. Möglich, solange die Extraktion noch nicht geprüft wurde.</p>' + info +
                ('<table><thead><tr><th>PDF</th><th>Stand</th><th>Aktion</th></tr></thead><tbody>' + rows + '</tbody></table>'
                 if docs else '<p class="card">Noch keine PDF-Dokumente im Fall. <a href="' + _link("/documents458", case_id=case_id) + '">PDF importieren →</a></p>'))
        return render("Struktur & Texterkennung", case_id, body)

    @app.post("/workbench/intel/documents")
    async def documents_enrich(request: Request):
        form = await bounded_form(request, max_bytes=4096)
        case_id = str(form.get("case_id") or "")
        user, _ = case_access(app, request, case_id, "research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        document_id = str(form.get("document_id") or "")
        try:
            doc = ctx.document_intelligence_458._document(document_id)
        except KeyError:
            raise HTTPException(404, "Dokument nicht gefunden.") from None
        if doc["case_id"] != case_id:
            raise HTTPException(403, "Dokument gehört nicht zu diesem Fall.")
        ocr_ok, engine = docstructure.ocr_available()

        def work():
            with ctx.audit.actor_scope(user["username"]):
                return docstructure.enrich_document(ctx, identity=user, document_id=document_id,
                                                    ocr_engine=docstructure.tesseract_page if ocr_ok else None,
                                                    engine_name=engine)
        try:
            await run_in_threadpool(work)
        except (ValueError, PermissionError) as exc:
            raise HTTPException(422, str(exc)) from None
        return RedirectResponse("/workbench/intel/documents?" + urlencode({"case_id": case_id, "done": "1"}), status_code=303)

    # ---------------------------------------------------------------- lineage
    @app.get("/workbench/intel/lineage", response_class=HTMLResponse)
    def lineage_view(request: Request, case_id: str = "", level: str = Query("normal")):
        user, _ = case_access(app, request, case_id)
        if level not in lineage.LEVELS:
            level = "normal"
        service = ctx.document_intelligence_458
        docs = service.documents(identity=user, case_id=case_id)[:500]
        cap_by_doc = {c["document_id"]: c for c in captures.captures_for_case(ctx, case_id, limit=500)}
        prepared = []
        for d in docs:
            anchors = service.anchors(identity=user, document_id=d["document_id"])["anchors"]
            prepared.append({"document_id": d["document_id"], "title": d["title"], "source_url": d["source_url"],
                             "first_seen": _first_seen(d, cap_by_doc.get(d["document_id"])),
                             "text": lineage.document_text(anchors)})
        result = lineage.source_families(prepared, level=level)
        levels = "".join('<a class="pill" href="' + _link("/workbench/intel/lineage", case_id=case_id, level=k) + '"' +
                         (' aria-current="true"><strong>' + escape(k) + '</strong>' if k == level else '>' + escape(k)) +
                         '</a>' for k in lineage.LEVELS)
        summary = ('<div class="grid"><section class="card"><span class="stat">' + str(result["compared"]) + '</span>Dokumente verglichen</section>'
                   '<section class="card"><span class="stat">' + str(result["independent_origins"]) + '</span>unabhängige Ursprünge</section>'
                   '<section class="card"><span class="stat">' + str(result["duplicate_documents"]) + '</span>Übernahmen / Spiegelungen</section></div>')
        cards = ""
        for fam in result["families"]:
            if fam["size"] < 2:
                continue
            members = "".join('<li><a href="' + _link("/documents458", case_id=case_id, document_id=m["document_id"]) + '">' + escape(m["title"]) +
                              '</a> <span class="muted">' + escape(urlsplit(m["source_url"]).hostname or "ohne Quellen-URL") + ' · ' +
                              escape(m["first_seen"] or "Zeit unbekannt") + '</span></li>' for m in fam["members"])
            cards += ('<section class="card"><h2>' + str(fam["size"]) + ' Dokumente mit weitgehend gleichem Text</h2>'
                      '<p>Ähnlichkeit ' + escape(str(fam["min_similarity"])) + '–' + escape(str(fam["max_similarity"])) +
                      ' · ' + str(len(fam["hosts"])) + ' Websites. Frühester Beleg im Fall: <strong>' + escape(fam["earliest"]["title"]) +
                      '</strong> – das ist ein Hinweis, kein Nachweis des Ursprungs.</p><ol>' + members + '</ol></section>')
        singles = sum(1 for f in result["families"] if f["size"] == 1)
        skipped = ""
        if result["skipped"]:
            skipped = ('<details class="card"><summary>' + str(len(result["skipped"])) + ' Dokumente mit zu wenig Text nicht verglichen</summary><ul>' +
                       "".join('<li>' + escape(s["title"]) + '</li>' for s in result["skipped"]) + '</ul></details>')
        body = (back(case_id) + '<p>Zählt, wie viele <strong>voneinander unabhängige Ursprünge</strong> hinter den Belegen stehen. '
                'Übernommene Agenturmeldungen oder gespiegelte Seiten sind keine unabhängige Bestätigung.</p>'
                '<p class="row">Vergleich: ' + levels + '<span class="muted">streng = nahezu identisch, locker = auch stark bearbeitete Übernahmen</span></p>'
                + summary + (cards or ('<p class="card">Keine übernommenen oder gespiegelten Texte gefunden.</p>' if result["compared"] >= 2 else
                '<p class="card warn">Für einen Vergleich werden mindestens zwei Dokumente mit jeweils mindestens '
                + str(lineage.MIN_WORDS) + ' Wörtern Text benötigt.</p>')) +
                ('<p class="muted">' + _count(singles, "Dokument steht", "Dokumente stehen") + ' für sich.</p>' if singles and result["compared"] >= 2 else "") + skipped)
        return render("Quellenunabhängigkeit", case_id, body)

    # ---------------------------------------------------------------- network
    @app.get("/workbench/intel/network", response_class=HTMLResponse)
    def network_view(request: Request, case_id: str = "", source: str = "", target: str = ""):
        _user, _ = case_access(app, request, case_id)
        graph = _case_graph(base_dir, case_id)
        result = network.analyse(graph)
        labels = {str(e["id"]): e["label"] for e in graph["entities"]}

        def names(items, extra=lambda x: ""):
            return "".join('<li>' + escape(i["label"]) + ' <span class="muted">' + escape(KIND_DE.get(i["kind"], i["kind"])) + extra(i) + '</span></li>' for i in items)

        options = lambda sel: "".join('<option value="' + escape(k, quote=True) + '"' + (' selected' if k == sel else '') + '>' + escape(v) + '</option>'
                                      for k, v in sorted(labels.items(), key=lambda kv: kv[1].casefold()))
        path_html = ""
        if source and target:
            if source not in labels or target not in labels:
                raise HTTPException(422, "Unbekannte Entität.")
            steps = network.path_between(graph, source, target)
            path_html = ('<ol>' + "".join('<li>' + escape(s["from"]) + ' → ' + escape(s["to"]) + ' <span class="muted">(' + escape(", ".join(s["predicates"])) +
                                          ', Gewicht ' + str(s["weight"]) + ')</span></li>' for s in steps) + '</ol>'
                         if steps else '<p>Keine Verbindung im Graph.</p>')
        groups = "".join('<section class="card"><h2>Gruppe ' + str(i + 1) + ' · ' + str(len(g)) + ' Entitäten</h2><ul>' + names(g[:15]) +
                         ('</ul><p class="muted">… und ' + str(len(g) - 15) + ' weitere</p>' if len(g) > 15 else '</ul>') + '</section>'
                         for i, g in enumerate(result["groups"]))
        body = (back(case_id) + '<p>Auswertung des Beziehungsgraphen. Beziehungen sind Hypothesen: unterstützte Beziehungen und geprüfte Quellen '
                'zählen stärker, verworfene gar nicht. Kennzahlen sind Orientierung für die weitere Recherche, keine Feststellung.</p>'
                '<div class="grid"><section class="card"><span class="stat">' + str(result["nodes"]) + '</span>Entitäten</section>'
                '<section class="card"><span class="stat">' + str(result["edges"]) + '</span>gewertete Verbindungen</section>'
                '<section class="card"><span class="stat">' + str(len(result["groups"])) + '</span>Gruppen</section>'
                '<section class="card"><span class="stat">' + str(len(result["isolated"])) + '</span>ohne Verbindung</section></div>'
                + ('<section class="card"><h2>Brückenpersonen und -organisationen</h2><p class="muted">Verbinden sonst getrennte Gruppen – oft lohnende Ansatzpunkte.</p><ul>'
                   + names(result["bridges"], lambda b: (' · verbindet ' + str(b["connects_groups"]) + ' Gruppen' if b["connects_groups"] > 1 else ' · Knotenpunkt: ohne diese Verbindung zerfällt das Netz')) + '</ul></section>' if result["bridges"] else "")
                + ('<section class="card"><h2>Am stärksten vernetzt</h2><ul>' + names(result["central"], lambda c: ' · ' + _count(c["links"], "Verbindung", "Verbindungen")) + '</ul></section>'
                   if result["central"] else '<p class="card">Noch keine Beziehungen erfasst. <a href="' + _link("/graph464", case_id=case_id) + '">Beziehungsgraph öffnen →</a></p>')
                + groups
                + ('<section class="card"><h2>Am besten belegter Verbindungsweg</h2><form method="get" action="/workbench/intel/network">'
                   '<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '"><div class="grid"><label>Von<select name="source">' + options(source) +
                   '</select></label><label>Nach<select name="target">' + options(target or (sorted(labels, key=lambda k: labels[k].casefold())[1] if len(labels) > 1 else "")) + '</select></label></div><button>Weg suchen</button></form>' + path_html + '</section>'
                   if len(labels) >= 2 else "")
                + '<p><a href="' + _link("/workbench/intel/network.gexf", case_id=case_id) + '">Graph als GEXF herunterladen (Gephi)</a> · '
                '<a href="' + _link("/workbench/intel/ftm.json", case_id=case_id) + '">Entitäten im FollowTheMoney-Format (JSON)</a></p>')
        return render("Netzwerkanalyse", case_id, body)

    @app.get("/workbench/intel/network.gexf")
    def network_gexf(request: Request, case_id: str = ""):
        case_access(app, request, case_id)
        ctx.audit.log("network_exported_492", "operational_case", case_id, case_id, {"format": "gexf", "verified": False})
        return Response(network.gexf(_case_graph(base_dir, case_id)), media_type="application/gexf+xml",
                        headers={"Content-Disposition": 'attachment; filename="eagleeye-case-network.gexf"', "Cache-Control": "no-store"})

    @app.get("/workbench/intel/ftm.json")
    def ftm_export(request: Request, case_id: str = ""):
        user, _ = case_access(app, request, case_id)
        entities = entitymatch.ftm_entities(_case_graph(base_dir, case_id), reviews_for_case(ctx, user, case_id))
        ctx.audit.log("ftm_exported_492", "operational_case", case_id, case_id, {"entities": len(entities), "verified": False})
        payload = "\n".join(json.dumps(e, ensure_ascii=False, sort_keys=True) for e in entities) + "\n"
        return Response(payload.encode("utf-8"), media_type="application/x-ndjson",
                        headers={"Content-Disposition": 'attachment; filename="eagleeye-case-ftm.jsonl"', "Cache-Control": "no-store"})
