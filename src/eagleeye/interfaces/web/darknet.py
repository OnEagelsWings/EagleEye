"""Darknet module page: /workbench/darknet (menu: Recherche → Darknet)."""
from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from eagleeye.application.darknet import service as darknet
from eagleeye.application.darknet import tor
from eagleeye.application.intel492.webcapture import CaptureError
from .app364 import CSRF_COOKIE
from .findings478 import bounded_form, verify_post
from .operations476 import case_access, page

CSS = ('<style>.dn .muted{color:var(--muted,#6b7785);font-size:.92rem}.dn .ok{color:#1d7a4a}.dn .bad{color:#b3412e}'
       '.dn table{width:100%;border-collapse:collapse}.dn td,.dn th{text-align:left;vertical-align:top;padding:.45rem .5rem;'
       'border-bottom:1px solid rgba(127,127,127,.25)}.dn code{overflow-wrap:anywhere}.dn .pill{display:inline-block;'
       'border-radius:999px;padding:0 .55rem;font-size:.85rem;border:1px solid currentColor}.dn .inline{display:inline}'
       '.dn details{margin:.3rem 0}.dn .rule{border-left:4px solid #b3412e;padding-left:.8rem}</style>')

DONE = {
    "an": "Darknet-Modul eingeschaltet.", "aus": "Darknet-Modul ausgeschaltet.",
    "vorgeschlagen": "Quelle vorgeschlagen. Sie kann genutzt werden, sobald die Büroleitung sie freigibt.",
    "freigegeben": "Quelle freigegeben.", "gesperrt": "Quelle gesperrt.",
    "gesichert": "Seite über Tor gesichert: WARC-Datei, Prüfsumme und Text liegen in der Akte. Zeitstempel und Prüfpaket unter „Web-Belege“.",
}

RULES = ('<section class="card rule"><h2>Dienstanweisung Darknet</h2><ul>'
         '<li>Nur im Rahmen eines angenommenen Auftrags mit Rechtsgrundlage; jeder Schritt wird protokolliert.</li>'
         '<li>Nur lesen: keine Konten anlegen, nichts kaufen, nichts herunterladen, nicht mit Personen in Kontakt treten.</li>'
         '<li>Gesichert werden nur Textseiten. Bilder, Skripte, PDFs und Dateien werden nie geladen.</li>'
         '<li>Stößt du auf Darstellungen von Kindesmissbrauch: sofort abbrechen, nichts sichern, nicht weiterverbreiten, '
         'Büroleitung informieren; Meldung an die Polizei bzw. jugendschutz.net.</li>'
         '<li>Ahmia filtert bekannte Missbrauchsseiten aus seinen Ergebnissen. Das ist kein vollständiger Schutz.</li>'
         '</ul></section>')


def _link(path: str, **params) -> str:
    return escape(path + "?" + urlencode(params), quote=True)


def attach_darknet(app, build: str) -> None:
    ctx = app.state.context
    darknet.initialize(ctx)

    def csrf(request: Request) -> str:
        return escape(request.cookies.get(CSRF_COOKIE, ""), quote=True)

    def can_run(user, case_id) -> bool:
        return "research.run" in ctx.team_governance_359.effective_capabilities(user, case_id)

    def hidden(request, case_id) -> str:
        return ('<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
                '<input type="hidden" name="csrf" value="' + csrf(request) + '">')

    def render(request, user, case_id, *, message="", error="", result=None, status=200, query=""):
        settings = darknet.settings(ctx)
        lead = darknet.is_lead(user)
        allowed = can_run(user, case_id)
        h = hidden(request, case_id)
        body = CSS + '<div class="dn">'
        if message:
            body += '<p class="card ok" role="status">' + escape(message) + '</p>'
        if error:
            body += '<p class="card bad" role="alert">' + escape(error) + '</p>'
        # status and settings
        state = ('<span class="pill ok">eingeschaltet</span>' if settings["enabled"] else '<span class="pill bad">ausgeschaltet</span>')
        body += ('<section class="card"><h2>Verbindung</h2><p>Darknet-Modul: ' + state + ' · Tor-Dienst auf <code>127.0.0.1:'
                 + str(settings["socks_port"]) + '</code>'
                 + (' · zuletzt geändert von ' + escape(settings["changed_by"]) + ', ' + escape(settings["changed_at"][:16].replace("T", " ")) + ' UTC'
                    if settings["changed_by"] else '') + '</p>'
                 '<p class="muted">Abgerufen wird ausschließlich über Tor auf diesem Rechner: den Tor-Dienst (Port 9050) oder den '
                 'geöffneten Tor Browser (Port 9150). Jeder Fall nutzt eine eigene Tor-Verbindung.</p>'
                 '<form method="post" action="/workbench/darknet/pruefen" class="inline">' + h +
                 '<button>Verbindung prüfen</button></form>')
        if lead:
            body += ('<details><summary>Einstellungen (Büroleitung)</summary><form method="post" action="/workbench/darknet/einstellungen">' + h +
                     '<label>Port des Tor-Dienstes<select name="socks_port">'
                     + "".join(f'<option value="{p}"{" selected" if settings["socks_port"] == p else ""}>{p} – {t}</option>'
                               for p, t in ((9050, "Tor-Dienst"), (9150, "Tor Browser")))
                     + '</select></label>'
                     '<label class="check"><input type="checkbox" name="enabled" value="yes"' + (" checked" if settings["enabled"] else "") +
                     '><span>Darknet-Modul eingeschaltet</span></label>'
                     '<label>Zum Einschalten bestätigen: „' + darknet.CONFIRMATION + '“ eintippen<input name="confirmation" autocomplete="off"></label>'
                     '<label>Vermerk (z. B. Bezug zur Dienstanweisung)<input name="note" maxlength="500" value="' + escape(settings["note"], quote=True) + '"></label>'
                     '<button>Speichern</button></form></details>')
        body += '</section>'
        # search
        if allowed:
            body += ('<section class="card"><h2>Im Darknet suchen</h2>'
                     '<p class="muted">Suche über Ahmia (Tor-Suchmaschine mit Filter gegen Missbrauchsdarstellungen). Gefundene Dienste '
                     'erscheinen mit ihrem Status im Quellenregister.</p>'
                     '<form method="post" action="/workbench/darknet/suche">' + h +
                     '<label>Suchbegriff (Firma, Name, E-Mail, Benutzername, Produkt …)<input name="query" maxlength="200" required value="'
                     + escape(query, quote=True) + '"></label>'
                     '<label class="check"><input type="checkbox" name="opsec" value="yes" required><span>Der Suchbegriff wird über Tor an '
                     'Ahmia übermittelt; Ahmia sieht den Begriff, nicht die IP-Adresse des Büros.</span></label>'
                     '<button>Suchen</button></form></section>')
        if result:
            rows = ""
            for item in result["results"]:
                status_label = darknet.STATUS.get(item.get("source_status"), "nicht im Register")
                actions = ""
                if item.get("source_status") == "freigegeben":
                    actions = ('<form method="post" action="/workbench/darknet/sichern" class="inline">' + h +
                               '<input type="hidden" name="url" value="' + escape(item["url"], quote=True) + '">'
                               '<input type="hidden" name="opsec" value="yes"><button>Seite sichern</button></form>')
                elif not item.get("source_status"):
                    actions = ('<a href="' + _link("/workbench/darknet", case_id=case_id, vorschlag=item["url"]) + '#vorschlag">Als Quelle vorschlagen</a>')
                rows += ('<tr><td><strong>' + escape(item["title"]) + '</strong><br><code>' + escape(item["url"]) + '</code>'
                         + ('<br><span class="muted">' + escape(item["description"]) + '</span>' if item["description"] else '')
                         + '</td><td>' + escape(status_label) + '</td><td>' + actions + '</td></tr>')
            body += ('<section class="card"><h2>' + str(result["result_count"]) + ' Treffer für „' + escape(result["query"]) + '“</h2>'
                     + ('<table><thead><tr><th>Dienst</th><th>Register</th><th></th></tr></thead><tbody>' + rows + '</tbody></table>'
                        if rows else '<p>Keine Treffer. Ahmia findet nur Dienste, die es indexiert hat; andere Schreibweisen oder '
                                     'englische Begriffe versuchen.</p>')
                     + '<p class="muted">Die Suche ist mit Zeit, Begriff und Trefferliste in der Akte dokumentiert.</p></section>')
        # capture by address
        if allowed:
            body += ('<section class="card"><h2>Seite einer freigegebenen Quelle sichern</h2>'
                     '<form method="post" action="/workbench/darknet/sichern">' + h +
                     '<label>Onion-Adresse der Seite<input name="url" maxlength="2000" required placeholder="http://…onion/…"></label>'
                     '<label class="check"><input type="checkbox" name="opsec" value="yes" required><span>Ich rufe nur lesend ab und '
                     'beachte die Dienstanweisung.</span></label><button>Über Tor sichern</button></form></section>')
        # propose source
        proposal = str(request.query_params.get("vorschlag") or "")[:500]
        if allowed:
            body += ('<section class="card" id="vorschlag"><h2>Quelle vorschlagen</h2>'
                     '<form method="post" action="/workbench/darknet/quelle">' + h +
                     '<label>Onion-Adresse<input name="address" required maxlength="500" value="' + escape(proposal, quote=True) + '"></label>'
                     '<label>Name der Quelle<input name="label" required maxlength="120"></label>'
                     '<label>Art<select name="category">' + "".join(f'<option value="{k}">{escape(v)}</option>' for k, v in darknet.CATEGORIES.items()) +
                     '</select></label><label>Wofür wird sie im Auftrag gebraucht?<textarea name="reason" required maxlength="1000"></textarea></label>'
                     '<button>Vorschlagen</button></form></section>')
        # register
        register = darknet.sources(ctx)
        reg_rows = ""
        for s in register:
            decide = ""
            if lead and s["status"] != "freigegeben":
                decide += ('<form method="post" action="/workbench/darknet/entscheidung" class="inline">' + h +
                           '<input type="hidden" name="source_id" value="' + escape(s["source_id"], quote=True) + '">'
                           '<input type="hidden" name="status" value="freigegeben"><button>Freigeben</button></form> ')
            if lead and s["status"] != "gesperrt":
                decide += ('<details><summary>Sperren</summary><form method="post" action="/workbench/darknet/entscheidung">' + h +
                           '<input type="hidden" name="source_id" value="' + escape(s["source_id"], quote=True) + '">'
                           '<input type="hidden" name="status" value="gesperrt"><label>Grund<input name="note" required maxlength="500"></label>'
                           '<button>Sperren</button></form></details>')
            reg_rows += ('<tr><td><strong>' + escape(s["label"]) + '</strong><br><code>' + escape(s["onion_host"]) + '</code><br>'
                         '<span class="muted">' + escape(darknet.CATEGORIES.get(s["category"], s["category"])) + ' · ' + escape(s["reason"]) + '</span></td>'
                         '<td>' + escape(darknet.STATUS[s["status"]]) + '<br><span class="muted">vorgeschlagen von ' + escape(s["proposed_by"])
                         + (', entschieden von ' + escape(s["decided_by"]) if s["decided_by"] else '')
                         + (' – ' + escape(s["decision_note"]) if s["decision_note"] else '') + '</span></td><td>' + decide + '</td></tr>')
        body += ('<section class="card"><h2>Quellenregister</h2>'
                 + ('<table><thead><tr><th>Quelle</th><th>Status</th><th></th></tr></thead><tbody>' + reg_rows + '</tbody></table>'
                    if reg_rows else '<p>Noch keine Quellen erfasst.</p>')
                 + '<p class="muted">Das Register gilt für das ganze Büro. Abgerufen wird nur von freigegebenen Quellen.</p></section>')
        # captures and searches of this case
        rows = darknet.captures_for_case(ctx, case_id)
        cap_rows = "".join('<tr><td>' + escape(r["page_title"] or r["url"]) + '<br><code>' + escape(r["url"]) + '</code></td><td>'
                           + escape(r["captured_at"][:16].replace("T", " ")) + ' UTC<br><span class="muted">SHA-256 '
                           + escape(r["body_sha256"][:16]) + '…</span></td><td><a href="'
                           + _link("/workbench/intel/warc", case_id=case_id, capture_id=r["capture_id"]) + '">WARC</a> · <a href="'
                           + _link("/workbench/document", case_id=case_id, document_id=r["document_id"]) + '">Text</a></td></tr>' for r in rows)
        history = darknet.searches(ctx, case_id, limit=10)
        hist_rows = "".join('<li>' + escape(s["created_at"][:16].replace("T", " ")) + ' UTC · „' + escape(s["query"]) + '“ · '
                            + str(s["result_count"]) + ' Treffer · ' + escape(s["created_by"]) + '</li>' for s in history)
        body += ('<section class="card"><h2>In diesem Fall</h2><h3>Gesicherte Darknet-Seiten</h3>'
                 + ('<table><tbody>' + cap_rows + '</tbody></table>' if cap_rows else '<p>Noch keine.</p>')
                 + '<p class="muted">Zeitstempel und Prüfpaket für jede Seite unter <a href="' + _link("/workbench/intel/web", case_id=case_id)
                 + '">Belege → Web-Belege</a>.</p><h3>Suchen</h3>' + ('<ul>' + hist_rows + '</ul>' if hist_rows else '<p>Noch keine.</p>')
                 + '</section>')
        body += RULES + '</div>'
        return HTMLResponse(page("Darknet (Tor)", case_id, body, build), status_code=status, headers={"Cache-Control": "no-store"})

    @app.get("/workbench/darknet", response_class=HTMLResponse)
    def darknet_view(request: Request, case_id: str = "", done: str = ""):
        user, _ = case_access(app, request, case_id)
        return render(request, user, case_id, message=DONE.get(done, ""))

    async def guarded(request, capability="research.run", max_bytes=8192):
        form = await bounded_form(request, max_bytes=max_bytes)
        case_id = str(form.get("case_id") or "")
        user, _ = case_access(app, request, case_id, capability)
        verify_post(app, request, user, form.get("csrf", ""))
        return form, case_id, user

    def done(case_id, code):
        return RedirectResponse("/workbench/darknet?" + urlencode({"case_id": case_id, "done": code}), status_code=303)

    @app.post("/workbench/darknet/einstellungen")
    async def save_settings(request: Request):
        form, case_id, user = await guarded(request, "case.read")
        try:
            current = darknet.save_settings(ctx, user=user, enabled=form.get("enabled") == "yes",
                                            socks_port=int(form.get("socks_port") or tor.DEFAULT_PORT),
                                            confirmation=str(form.get("confirmation") or ""), note=str(form.get("note") or ""))
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except ValueError as exc:
            return render(request, user, case_id, error=str(exc), status=422)
        return done(case_id, "an" if current["enabled"] else "aus")

    @app.post("/workbench/darknet/pruefen", response_class=HTMLResponse)
    async def check_connection(request: Request):
        form, case_id, user = await guarded(request, "case.read")
        current = darknet.settings(ctx)
        local = tor.probe(socks_port=current["socks_port"])
        if not local["ok"]:
            return render(request, user, case_id, error=local["detail"] + " Tor Browser öffnen oder den Tor-Dienst starten.", status=200)
        if not current["enabled"]:
            return render(request, user, case_id, message=local["detail"] + " Das Modul ist noch ausgeschaltet.")
        try:
            result = await run_in_threadpool(lambda: darknet.transport(ctx, case_id).get(f"http://{darknet.AHMIA_ONION}/"))
        except (CaptureError, PermissionError) as exc:
            return render(request, user, case_id, error=local["detail"] + " Onion-Test fehlgeschlagen: " + str(exc))
        ctx.audit.log("darknet_connection_checked_500", "darknet", "settings", case_id, {"status": result.status})
        return render(request, user, case_id, message=local["detail"] + f" Onion-Test: Ahmia antwortet (HTTP {result.status}, {result.ip_address}).")

    @app.post("/workbench/darknet/suche", response_class=HTMLResponse)
    async def run_search(request: Request):
        form, case_id, user = await guarded(request)
        query = str(form.get("query") or "")
        if form.get("opsec") != "yes":
            return render(request, user, case_id, error="Bitte die Übermittlung an Ahmia bestätigen.", status=422, query=query)
        gate = getattr(app.state, "research_gate", None)
        refusal = gate(case_id) if gate else ""
        if refusal:
            return render(request, user, case_id, error=refusal, status=409, query=query)
        try:
            result = await run_in_threadpool(lambda: darknet.search(ctx, user=user, case_id=case_id, query=query))
        except (CaptureError, PermissionError, ValueError) as exc:
            return render(request, user, case_id, error=str(exc), status=422, query=query)
        return render(request, user, case_id, result=result, query=query)

    @app.post("/workbench/darknet/quelle", response_class=HTMLResponse)
    async def propose(request: Request):
        form, case_id, user = await guarded(request)
        try:
            darknet.propose_source(ctx, user=user, case_id=case_id, address=str(form.get("address") or ""),
                                   label=str(form.get("label") or ""), category=str(form.get("category") or ""),
                                   reason=str(form.get("reason") or ""))
        except ValueError as exc:
            return render(request, user, case_id, error=str(exc), status=422)
        return done(case_id, "vorgeschlagen")

    @app.post("/workbench/darknet/entscheidung", response_class=HTMLResponse)
    async def decide(request: Request):
        form, case_id, user = await guarded(request, "case.read")
        try:
            row = darknet.decide_source(ctx, user=user, source_id=str(form.get("source_id") or ""),
                                        status=str(form.get("status") or ""), note=str(form.get("note") or ""))
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except KeyError:
            raise HTTPException(404, "Quelle nicht gefunden.") from None
        except ValueError as exc:
            return render(request, user, case_id, error=str(exc), status=422)
        return done(case_id, row["status"])

    @app.post("/workbench/darknet/sichern", response_class=HTMLResponse)
    async def save_page(request: Request):
        form, case_id, user = await guarded(request)
        if form.get("opsec") != "yes":
            return render(request, user, case_id, error="Bitte bestätige die Dienstanweisung vor dem Abruf.", status=422)
        gate = getattr(app.state, "research_gate", None)
        refusal = gate(case_id) if gate else ""
        if refusal:
            return render(request, user, case_id, error=refusal, status=409)
        try:
            await run_in_threadpool(lambda: darknet.capture(ctx, user=user, case_id=case_id, url=str(form.get("url") or "")))
        except (CaptureError, PermissionError, ValueError) as exc:
            return render(request, user, case_id, error=str(exc), status=422)
        return done(case_id, "gesichert")
