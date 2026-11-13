"""Build 492 UI: document view in the shared layout, with extraction review.

Replaces the stand-alone Build-458 page for the current workspace (``/documents458``
redirects here and keeps ``#anchor-…`` jump marks). Adds what the guided workflow
was missing: the human extraction review that 'Quelle -> Evidence' requires, a filter
by anchor type, search within the document, protection class, web provenance and the
next steps. All checks of the Build-458 page (record hashes, unchanged original,
anchor hashes, case scope) are kept.
"""
from __future__ import annotations

from html import escape
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from eagleeye.application.intel492 import captures, docstructure, markings
from eagleeye_pro.phase20.document_intelligence458 import REVIEW_CONFIRMATION
from .app364 import CSRF_COOKIE
from .app449 import _drop
from .findings478 import bounded_form, verify_post
from .operations476 import case_access, page

PER_PAGE = 100
KIND_LABELS = {"paragraph": "Absatz", "caption": "Bild- oder Tabellentitel", "footnote_candidate": "Fußnote (vermutet)",
               "table": "Tabelle", "heading": "Überschrift", "ocr_paragraph": "OCR-Absatz"}
FILTERS = {"": "Alle", "paragraph": "Absätze", "table": "Tabellen", "heading": "Überschriften",
           "ocr_paragraph": "OCR", "other": "Titel und Fußnoten"}
METHOD_LABELS = {"native_pdf_text": "Text aus dem PDF", "native_utf8_text": "Textdatei",
                 "pymupdf_table": "Tabellenerkennung", "pymupdf_font_heading": "Überschrift nach Schriftgröße",
                 "ocr_tesseract": "Texterkennung (OCR)"}
STATE_LABELS = {"review_required": "Extraktion noch nicht geprüft", "extraction_approved": "Extraktion freigegeben",
                "extraction_rejected": "Extraktion verworfen"}
CSS = ('<style>.ok{color:#9af3de}.bad{color:#ffb4a8}.muted{color:#c2d3e3;font-size:.92rem}'
       '.pill{display:inline-block;border:1px solid #647b93;border-radius:999px;padding:.1rem .6rem;margin:.15rem .25rem .15rem 0;font-size:.88rem}'
       '.row{display:flex;gap:.6rem;flex-wrap:wrap;align-items:center}.row form{margin:0}'
       'label.check{display:flex;gap:.5rem;align-items:flex-start}label.check input{width:auto;margin:.35rem 0 0}'
       'dl{display:grid;grid-template-columns:max-content 1fr;gap:.2rem 1rem;margin:0}dt{color:#c2d3e3}dd{margin:0;overflow-wrap:anywhere}'
       '@media (max-width:640px){dl{grid-template-columns:1fr}dd{margin-bottom:.4rem}}'
       'article.anchor{border-left:3px solid #647b93;padding:.3rem .8rem;margin:.8rem 0}article.anchor:target{border-left-color:#f9e099;background:#24405f}'
       'mark{background:#f9e099;color:#102238}fieldset{border:1px solid #647b93;border-radius:8px;margin:0 0 1rem}</style>')


def _link(path: str, fragment: str = "", **params) -> str:
    return escape(path + "?" + urlencode(params) + (("#" + fragment) if fragment else ""), quote=True)


def _highlight(text: str, query: str) -> str:
    if not query:
        return escape(text)
    lower, needle, out, start = text.casefold(), query.casefold(), [], 0
    while True:
        hit = lower.find(needle, start)
        if hit < 0 or len(lower) != len(text):  # casefold changed lengths: no inline marking
            out.append(escape(text[start:]))
            return "".join(out)
        out.append(escape(text[start:hit]) + "<mark>" + escape(text[hit:hit + len(needle)]) + "</mark>")
        start = hit + len(needle)


def attach_document_view(app, build: str) -> None:
    ctx = app.state.context
    service = ctx.document_intelligence_458

    def render(title, case_id, body, status=200):
        return HTMLResponse(page(title, case_id, CSS + body, build), status_code=status, headers={"Cache-Control": "no-store"})

    def caps(user, case_id):
        return ctx.team_governance_359.effective_capabilities(user, case_id)

    _drop(app, "/documents458", {"GET"})

    @app.get("/documents458")
    def legacy_document_path(request: Request, case_id: str, document_id: str = "", anchor_id: str = ""):
        params = {k: v for k, v in (("case_id", case_id), ("document_id", document_id), ("anchor_id", anchor_id)) if v}
        return RedirectResponse("/workbench/document?" + urlencode(params), status_code=303)

    def library(request, user, case_id):
        docs = service.documents(identity=user, case_id=case_id)
        marks = markings.current(ctx, case_id)
        rows = ""
        for d in docs:
            cls, _ = markings.marking_of(marks, "document", d["document_id"])
            state = STATE_LABELS.get(d["state"], d["state"])
            rows += ('<tr><td><a href="' + _link("/workbench/document", case_id=case_id, document_id=d["document_id"]) + '">' + escape(d["title"]) +
                     '</a><br><span class="muted">' + escape(urlsplit(d["source_url"] or "").hostname or "ohne Quellen-URL") + '</span></td>'
                     '<td>' + str(d["page_count"]) + '</td><td>' + escape(state) + ('<br><span class="bad">OCR erforderlich</span>' if d["ocr_required"] else '') +
                     '</td><td>' + escape(markings.CLASSES[cls]) + '</td></tr>')
        upload = ""
        if "research.run" in caps(user, case_id):
            upload = ('<section class="card"><h2>Dokument aufnehmen</h2>'
                      '<form id="upload" data-case-id="' + escape(case_id, quote=True) + '" enctype="multipart/form-data">'
                      '<label>Datei (PDF, TXT, MD bis 12 MB)<input name="file" type="file" accept=".pdf,.txt,.md" required></label>'
                      '<label>Titel<input name="title" maxlength="300"></label>'
                      '<label>Öffentliche Quellen-URL (optional)<input name="source_url" type="url" maxlength="1500"></label>'
                      '<button type="submit">Dokument lokal aufnehmen</button></form><p id="feedback" role="status"></p>'
                      '<p class="muted">Webseiten und PDFs aus dem Netz lassen sich mit Herkunftsnachweis über '
                      '<a href="' + _link("/workbench/intel/web", case_id=case_id) + '">Webseite als Beleg sichern</a> aufnehmen.</p>'
                      '<script src="/assets/build458/documents.js" defer></script></section>')
        table = ('<table><thead><tr><th>Dokument</th><th>Seiten</th><th>Extraktion</th><th>Schutzklasse</th></tr></thead><tbody>' + rows + '</tbody></table>'
                 if docs else '<p>Noch keine Dokumente im Fall.</p>')
        return render("Dokumente und Fundstellen", case_id, upload + '<section class="card"><h2>' + str(len(docs)) +
                      ' Dokumente</h2>' + table + '</section>')

    @app.get("/workbench/document", response_class=HTMLResponse)
    def document_view(request: Request, case_id: str = "", document_id: str = "", anchor_id: str = "",
                      kind: str = "", q: str = Query("", max_length=200), offset: int = Query(0, ge=0, le=100000), done: str = ""):
        user, case = case_access(app, request, case_id)
        if not document_id:
            return library(request, user, case_id)
        try:
            doc = service._document(document_id)
        except KeyError:
            raise HTTPException(404, "Dokument nicht gefunden.") from None
        if doc["case_id"] != case_id:
            raise HTTPException(403, "Dokument gehört nicht zu diesem Fall.")
        packet = service.anchors(identity=user, document_id=document_id)
        if doc["record_hash"] != service._rh(doc) or not service._payload_current(doc):
            raise HTTPException(409, "Originalbeleg wurde verändert oder ist nicht verfügbar.")
        anchors = packet["anchors"]
        kind = kind if kind in FILTERS else ""
        query = " ".join(q.split())

        def keep(a):
            if kind == "other" and a["anchor_kind"] not in ("caption", "footnote_candidate"):
                return False
            if kind and kind != "other" and a["anchor_kind"] != kind:
                return False
            return not query or query.casefold() in a["text_excerpt"].casefold()

        shown = [a for a in anchors if keep(a)]
        if anchor_id:
            index = next((i for i, a in enumerate(shown) if a["anchor_id"] == anchor_id), None)
            if index is None and any(a["anchor_id"] == anchor_id for a in anchors):
                kind, query, shown = "", "", anchors  # jump target hidden by a filter: show all
                index = next(i for i, a in enumerate(shown) if a["anchor_id"] == anchor_id)
            if index is None:
                raise HTTPException(404, "Fundstelle nicht in diesem Dokument vorhanden.")
            offset = (index // PER_PAGE) * PER_PAGE
        else:
            offset = min(offset, (max(0, len(shown) - 1) // PER_PAGE) * PER_PAGE)
        counts = {}
        for a in anchors:
            key = "other" if a["anchor_kind"] in ("caption", "footnote_candidate") else a["anchor_kind"]
            counts[key] = counts.get(key, 0) + 1
        capabilities = caps(user, case_id)

        # --- facts
        marks = markings.current(ctx, case_id)
        cls, cls_set = markings.marking_of(marks, "document", document_id)
        provenance = captures.provenance_for_document(ctx, case_id, document_id)
        source = doc["source_url"]
        facts = [("Titel", escape(doc["title"])),
                 ("Quelle", ('<a href="' + escape(source, quote=True) + '" target="_blank" rel="noopener noreferrer">' + escape(source[:200]) + '</a>'
                             + ('' if provenance else ' <span class="muted">(Angabe beim Import, unbestätigt)</span>')) if source else "ohne Quellen-URL"),
                 ("Seiten · Fundstellen", f'{doc["page_count"]} · {len(anchors)}'),
                 ("SHA-256 des Originals", '<code>' + escape(doc["document_sha256"]) + '</code>'),
                 ("Extraktion", escape(STATE_LABELS.get(doc["state"], doc["state"])) +
                  (' – ' + escape(doc["review_by"]) + ', ' + escape(doc["review_at"][:16].replace("T", " ")) + ': ' + escape(doc["review_note"]) if doc["review_by"] else '')),
                 ("Schutzklasse", escape(markings.CLASSES[cls]) + ('' if cls_set else ' <span class="muted">(Voreinstellung)</span>'))]
        if provenance:
            facts.append(("Web-Beleg", ("Archivfassung" if provenance["kind"] == "archive" else "Live-Abruf") + ' am ' +
                          escape(provenance["captured_at"][:16].replace("T", " ")) + ' UTC · ' +
                          ('<span class="ok">WARC unverändert</span>' if provenance["integrity_verified"] else '<span class="bad">WARC verändert – nicht verwenden</span>') +
                          ' · <a href="' + _link("/workbench/intel/warc", case_id=case_id, capture_id=provenance["capture_id"]) + '">WARC herunterladen</a>'))
        if doc["ocr_required"]:
            facts.append(("Hinweis", '<span class="bad">Enthält gescannte Seiten ohne Textschicht.</span>'))
        fact_html = '<dl>' + "".join('<dt>' + k + '</dt><dd>' + v + '</dd>' for k, v in facts) + '</dl>'

        # --- next steps
        steps = ['<a href="' + _link("/workbench/findings", case_id=case_id, document_id=document_id) + '">Befund notieren</a>']
        if doc["media_type"] == "application/pdf" and doc["state"] == "review_required":
            steps.append('<a href="' + _link("/workbench/intel/documents", case_id=case_id) + '">Tabellen, Überschriften, OCR ergänzen</a>')
        if doc["state"] == "extraction_approved":
            steps.append('<a href="' + _link("/workbench/bridge481", case_id=case_id, document_id=document_id) + '">Als Evidence übernehmen</a>')
        steps.append('<a href="' + _link("/workbench/document", case_id=case_id) + '">Alle Dokumente</a>')
        notice = {"reviewed": '<p class="card ok" role="status">Extraktionsprüfung gespeichert.</p>',
                  "marked": '<p class="card ok" role="status">Schutzklasse gespeichert.</p>'}.get(done, "")

        # --- review and class forms
        token = escape(request.cookies.get(CSRF_COOKIE, ""), quote=True)
        forms = ""
        if doc["state"] == "review_required":
            if "source.review" in capabilities:
                forms += ('<section class="card"><h2>Extraktion prüfen</h2>'
                          '<p>Vergleiche die Fundstellen unten mit dem Original. Erst eine freigegebene Extraktion kann als Evidence übernommen werden. '
                          'Die Freigabe bestätigt die Textübernahme, nicht den Inhalt.</p>'
                          '<form method="post" action="/workbench/document/review"><input type="hidden" name="case_id" value="' + escape(case_id, quote=True) +
                          '"><input type="hidden" name="csrf" value="' + token + '"><input type="hidden" name="document_id" value="' + escape(document_id, quote=True) +
                          '"><input type="hidden" name="expected_hash" value="' + escape(doc["record_hash"], quote=True) + '">'
                          '<fieldset><legend>Entscheidung</legend>'
                          '<label class="check"><input type="radio" name="decision" value="approve" required><span>Extraktion freigeben</span></label>'
                          '<label class="check"><input type="radio" name="decision" value="reject"><span>Extraktion verwerfen (Text unbrauchbar oder fehlerhaft)</span></label></fieldset>'
                          '<label>Begründung (was wurde wie verglichen?)<textarea name="note" required minlength="12" maxlength="3000" rows="3"></textarea></label>'
                          '<label class="check"><input type="checkbox" name="confirm" value="yes" required><span>Ich habe die Fundstellen mit dem Original verglichen.</span></label>'
                          '<button>Prüfung speichern</button></form></section>')
            else:
                forms += '<p class="card">Die Extraktion wartet auf Prüfung durch eine Person mit Quellenprüfungsrecht.</p>'
        if "research.run" in capabilities:
            options = "".join('<option value="' + k + '"' + (' selected' if k == cls else '') + '>' + escape(v) + '</option>'
                              for k, v in markings.CLASSES.items())
            forms += ('<details class="card"><summary>Schutzklasse des Dokuments ändern</summary>'
                      '<form method="post" action="/workbench/document/class"><input type="hidden" name="case_id" value="' + escape(case_id, quote=True) +
                      '"><input type="hidden" name="csrf" value="' + token + '"><input type="hidden" name="document_id" value="' + escape(document_id, quote=True) + '">'
                      '<label>Schutzklasse<select name="document_class">' + options + '</select></label>'
                      '<label>Begründung<input name="reason" required minlength="3" maxlength="600"></label>'
                      '<button>Schutzklasse speichern</button></form>'
                      '<p class="muted">Gilt für alle Befunde aus diesem Dokument; wirksam ist die strengere Klasse.</p></details>')

        # --- anchors with filter and search
        chips = "".join('<a class="pill" href="' + _link("/workbench/document", case_id=case_id, document_id=document_id, kind=k, q=query) + '"' +
                        (' aria-current="true"><strong>' + escape(v) + '</strong>' if k == kind else '>' + escape(v)) +
                        (' (' + str(counts.get(k, 0) if k else len(anchors)) + ')') + '</a>'
                        for k, v in FILTERS.items() if not k or counts.get(k))
        search = ('<form method="get" action="/workbench/document" class="row"><input type="hidden" name="case_id" value="' + escape(case_id, quote=True) +
                  '"><input type="hidden" name="document_id" value="' + escape(document_id, quote=True) + '"><input type="hidden" name="kind" value="' + escape(kind, quote=True) +
                  '"><label style="flex:1 1 14rem">Im Dokument suchen<input name="q" type="search" maxlength="200" value="' + escape(query, quote=True) +
                  '"></label><button>Suchen</button></form>')
        items = ""
        for a in shown[offset:offset + PER_PAGE]:
            raw = service._anchor(a["anchor_id"])
            if raw["record_hash"] != service._rh(raw):
                raise HTTPException(409, "Integrität einer Fundstelle verletzt.")
            items += ('<article class="anchor" id="anchor-' + escape(a["anchor_id"], quote=True) + '"><p class="muted">Seite ' + str(a["page_number"]) +
                      ' · ' + escape(KIND_LABELS.get(a["anchor_kind"], a["anchor_kind"])) + ' · ' +
                      escape(METHOD_LABELS.get(a["extraction_method"], a["extraction_method"])) + '</p><p>' + _highlight(a["text_excerpt"], query) +
                      '</p><p class="muted"><a href="' + _link("/workbench/findings", case_id=case_id, document_id=document_id) + '">Befund notieren</a> · '
                      '<code>' + escape(a["locator"]) + '</code></p></article>')
        paging = ""
        for value, label in ((offset - PER_PAGE, "Vorherige Fundstellen"), (offset + PER_PAGE, "Weitere Fundstellen")):
            if 0 <= value < len(shown) and value != offset:
                paging += '<a href="' + _link("/workbench/document", case_id=case_id, document_id=document_id, kind=kind, q=query, offset=value) + '">' + label + '</a> '
        found = (str(len(shown)) + ' von ' + str(len(anchors)) + ' Fundstellen' + (' passen zur Suche' if query else '') +
                 (f' · angezeigt {offset + 1}–{min(offset + PER_PAGE, len(shown))}' if shown else ''))
        anchors_html = ('<section class="card"><h2>Fundstellen</h2><p class="row">' + chips + '</p>' + search + '<p class="muted">' + found + '</p>' +
                        (items or '<p>Keine Fundstelle passt zu Filter oder Suche.</p>') + '<p>' + paging + '</p></section>')
        body = (notice + '<section class="card">' + fact_html + '<p class="row">' + ' · '.join(steps) + '</p></section>' + forms + anchors_html)
        return render(doc["title"][:120] or "Dokument", case_id, body)

    @app.post("/workbench/document/review")
    async def document_review(request: Request):
        form = await bounded_form(request, max_bytes=8192)
        case_id = str(form.get("case_id") or "")
        user, _ = case_access(app, request, case_id, "source.review")
        verify_post(app, request, user, form.get("csrf", ""))
        document_id = str(form.get("document_id") or "")
        try:
            doc = service._document(document_id)
        except KeyError:
            raise HTTPException(404, "Dokument nicht gefunden.") from None
        if doc["case_id"] != case_id:
            raise HTTPException(403, "Dokument gehört nicht zu diesem Fall.")
        if form.get("confirm") != "yes":
            raise HTTPException(422, "Bitte bestätige den Vergleich mit dem Original.")
        if not service._payload_current(doc):
            raise HTTPException(409, "Originalbeleg wurde verändert oder ist nicht verfügbar.")
        try:
            with ctx.audit.actor_scope(user["username"]):
                service.review_extraction(identity=user, document_id=document_id,
                                          expected_document_hash=str(form.get("expected_hash") or ""),
                                          decision=str(form.get("decision") or ""), note=str(form.get("note") or ""),
                                          confirmation=REVIEW_CONFIRMATION)
        except PermissionError:
            raise HTTPException(409, "Das Dokument wurde seit dem Öffnen verändert oder bereits geprüft. Bitte neu laden.") from None
        except ValueError as exc:
            message = {"document has already been reviewed": "Diese Extraktion wurde bereits geprüft.",
                       "document review rationale required": "Bitte die Prüfung begründen (mindestens 12 Zeichen).",
                       "invalid extraction review decision": "Bitte freigeben oder verwerfen auswählen."}.get(str(exc), str(exc))
            raise HTTPException(422, message) from None
        return RedirectResponse("/workbench/document?" + urlencode({"case_id": case_id, "document_id": document_id, "done": "reviewed"}), status_code=303)

    @app.post("/workbench/document/class")
    async def document_class(request: Request):
        form = await bounded_form(request, max_bytes=4096)
        case_id = str(form.get("case_id") or "")
        user, _ = case_access(app, request, case_id, "research.run")
        verify_post(app, request, user, form.get("csrf", ""))
        document_id = str(form.get("document_id") or "")
        try:
            doc = service._document(document_id)
        except KeyError:
            raise HTTPException(404, "Dokument nicht gefunden.") from None
        if doc["case_id"] != case_id:
            raise HTTPException(403, "Dokument gehört nicht zu diesem Fall.")
        try:
            with ctx.db.transaction(immediate=True), ctx.audit.actor_scope(user["username"]):
                markings.set_marking(ctx, case_id=case_id, object_type="document", object_id=document_id,
                                     marking=str(form.get("document_class") or ""), reason=str(form.get("reason") or ""),
                                     actor=user["username"])
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return RedirectResponse("/workbench/document?" + urlencode({"case_id": case_id, "document_id": document_id, "done": "marked"}), status_code=303)
