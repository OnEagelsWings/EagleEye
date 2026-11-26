"""EU public procurement (TED) page: /workbench/ted (menu: Recherche → EU-Ausschreibungen)."""
from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from eagleeye.application import ted
from .app364 import CSRF_COOKIE
from .findings478 import bounded_form, verify_post
from .operations476 import case_access, page

CSS = ('<style>.ted .muted{color:var(--muted,#6b7785);font-size:.92rem}.ted .bad{color:#b3412e}.ted .ok{color:#1d7a4a}'
       '.ted table{width:100%;border-collapse:collapse}.ted td,.ted th{text-align:left;vertical-align:top;padding:.45rem .5rem;'
       'border-bottom:1px solid rgba(127,127,127,.25)}.ted .row{display:grid;grid-template-columns:repeat(auto-fit,minmax(11rem,1fr));gap:.8rem}'
       '.ted .num{font-variant-numeric:tabular-nums;white-space:nowrap}</style>')


def _link(path: str, **params) -> str:
    return escape(path + "?" + urlencode(params), quote=True)


def attach_ted(app, build: str) -> None:
    ctx = app.state.context
    ted.initialize(ctx)

    def render(request, user, case_id, *, result=None, error="", form=None, status=200):
        form = form or {}
        token = escape(request.cookies.get(CSRF_COOKIE, ""), quote=True)
        allowed = "research.run" in ctx.team_governance_359.effective_capabilities(user, case_id)
        body = CSS + '<div class="ted">'
        if error:
            body += '<p class="card bad" role="alert">' + escape(error) + '</p>'
        body += ('<section class="card"><h2>Öffentliche Aufträge in der EU</h2>'
                 '<p>Durchsucht TED, das Amtsblatt der EU für öffentliche Ausschreibungen und Zuschläge: welche Firma von welcher '
                 'Behörde oder welchem öffentlichen Unternehmen einen Auftrag erhalten hat, mit Datum, Wert und Link zur Bekanntmachung. '
                 'Erfasst sind Aufträge oberhalb der EU-Schwellenwerte (etwa ab 220.000 € bei Lieferungen und Diensten).</p>')
        if allowed:
            body += ('<form method="post" action="/workbench/ted">'
                     '<input type="hidden" name="case_id" value="' + escape(case_id, quote=True) + '">'
                     '<input type="hidden" name="csrf" value="' + token + '">'
                     '<label>Firma oder Suchbegriff<input name="term" maxlength="120" required value="' + escape(form.get("term", ""), quote=True) + '"></label>'
                     '<div class="row"><label>Suchen<select name="role">'
                     + "".join(f'<option value="{k}"{" selected" if form.get("role", "gewinner") == k else ""}>{escape(v)}</option>' for k, v in ted.ROLES.items())
                     + '</select></label><label>Land des Auftraggebers (optional)<input name="country" maxlength="3" placeholder="DEU" value="'
                     + escape(form.get("country", ""), quote=True) + '"></label>'
                     '<label>Veröffentlicht ab<input type="date" name="date_from" value="' + escape(form.get("date_from", ""), quote=True) + '"></label>'
                     '<label>bis<input type="date" name="date_to" value="' + escape(form.get("date_to", ""), quote=True) + '"></label></div>'
                     '<label class="check"><input type="checkbox" name="opsec" value="yes" required><span>Der Suchbegriff geht an das '
                     'Amt für Veröffentlichungen der EU (api.ted.europa.eu).</span></label><button>In TED suchen</button></form>')
        body += '</section>'
        if result:
            rows = ""
            for n in result["results"]:
                save = (' · <a href="' + _link("/workbench/intel/web", case_id=case_id, url=n["url"]) + '">Als Web-Beleg sichern</a>'
                        if n["url"] and allowed else "")
                rows += ('<tr><td class="num">' + escape(n["date"]) + '</td><td><strong>' + escape(n["title"] or n["number"]) + '</strong><br>'
                         '<span class="muted">' + escape(n["type"]) + ' · Nr. ' + escape(n["number"]) + (' · CPV ' + escape(n["cpv"]) if n["cpv"] else '') + '</span></td>'
                         '<td>' + escape(n["buyer"]) + (' <span class="muted">(' + escape(n["country"]) + ')</span>' if n["country"] else '') + '</td>'
                         '<td>' + (escape(n["winner"]) or '<span class="muted">–</span>') + '</td><td class="num">' + escape(n["value"]) + '</td>'
                         '<td>' + ('<a href="' + escape(n["url"], quote=True) + '" target="_blank" rel="noopener noreferrer">Bekanntmachung</a>' if n["url"] else '')
                         + save + '</td></tr>')
            body += ('<section class="card"><h2>' + str(result["total"]) + ' Bekanntmachungen' + (f' (die neuesten {result["result_count"]} angezeigt)' if result["total"] > result["result_count"] else '')
                     + '</h2><p class="muted">Abfrage: <code>' + escape(result["query"]) + '</code></p>'
                     + ('<div style="overflow-x:auto"><table><thead><tr><th>Datum</th><th>Bekanntmachung</th><th>Auftraggeber</th><th>Gewinner</th>'
                        '<th>Wert</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>' if rows else
                        '<p>Keine Bekanntmachungen gefunden. Tipp: Firmennamen ohne Rechtsform suchen („Muster“ statt „Muster GmbH“) '
                        'oder die Suchart „Überall“ wählen.</p>')
                     + '<p class="muted">Die Suche ist mit Zeit und Trefferliste in der Akte dokumentiert. Ein Treffer belegt einen '
                     'veröffentlichten Auftrag, keine Zahlung.</p></section>')
        history = ted.searches(ctx, case_id)
        if history:
            body += ('<section class="card"><h2>Frühere Suchen in diesem Fall</h2><ul>' + "".join(
                '<li><a href="' + _link("/workbench/ted", case_id=case_id, search_id=h["search_id"]) + '">„' + escape(h["term"]) + '“</a> · '
                + escape(ted.ROLES.get(h["role"], h["role"])) + (' · ' + escape(h["country"]) if h["country"] else '') + ' · '
                + str(h["total"]) + ' Treffer · ' + escape(h["created_at"][:16].replace("T", " ")) + ' UTC</li>' for h in history) + '</ul></section>')
        body += '</div>'
        return HTMLResponse(page("EU-Ausschreibungen (TED)", case_id, body, build), status_code=status, headers={"Cache-Control": "no-store"})

    @app.get("/workbench/ted", response_class=HTMLResponse)
    def ted_view(request: Request, case_id: str = "", search_id: str = ""):
        user, _ = case_access(app, request, case_id)
        result = ted.search_row(ctx, case_id, search_id) if search_id else None
        form = {k: result[k] for k in ("term", "role", "country", "date_from", "date_to")} if result else None
        return render(request, user, case_id, result=result, form=form)

    @app.post("/workbench/ted", response_class=HTMLResponse)
    async def ted_search(request: Request):
        raw = await bounded_form(request, max_bytes=4096)
        case_id = str(raw.get("case_id") or "")
        user, _ = case_access(app, request, case_id, "research.run")
        verify_post(app, request, user, raw.get("csrf", ""))
        form = {k: str(raw.get(k) or "") for k in ("term", "role", "country", "date_from", "date_to")}
        if raw.get("opsec") != "yes":
            return render(request, user, case_id, error="Bitte die Übermittlung an TED bestätigen.", form=form, status=422)
        gate = getattr(app.state, "research_gate", None)
        refusal = gate(case_id) if gate else ""
        if refusal:
            return render(request, user, case_id, error=refusal, form=form, status=409)
        try:
            result = await run_in_threadpool(lambda: ted.search(ctx, user=user, case_id=case_id, **form))
        except ted.TedError as exc:
            return render(request, user, case_id, error=str(exc), form=form, status=422)
        return render(request, user, case_id, result=result, form=form)
