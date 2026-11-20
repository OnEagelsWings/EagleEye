"""Seite „Personenanalyse“: PersonOSINT-Auswertung der Kandidaten eines Falls (nur lesend, ohne Netz)."""
from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse

from eagleeye.application import personosint_analysis502 as po_analysis
from .operations476 import case_access, page

PATH = "/workbench/personanalyse"
SEVERITY = {"hoch": "hoch", "mittel": "mittel", "niedrig": "niedrig"}


def _link(url: str, text: str) -> str:
    if not url.startswith("https://"):
        return escape(text)
    return '<a href="' + escape(url, quote=True) + '" target="_blank" rel="noopener noreferrer">' + escape(text) + '</a>'


def render(result: dict, case_id: str) -> str:
    q = escape(urlencode({"case_id": case_id}), quote=True)
    body = ('<p>Auswertung der Aussagen, die der PersonOSINT-Motor bei freigegebenen Quellenabfragen dieses Falls geliefert hat. '
            'Die Seite fragt nichts ab und bestätigt nichts: Alle Angaben sind ungeprüfte Kandidaten. Warnhinweise sind '
            'Prüfaufträge, keine Vorwürfe. Kandidaten, die im Prüfeingang abgelehnt oder als Dublette markiert sind, zählen als verworfen.</p>')
    if not result["available"]:
        return body + '<p class="warn">Der PersonOSINT-Motor ist in dieser Installation nicht vorhanden.</p>'
    s = result["stats"]
    body += ('<div class="grid"><section class="card"><h2>' + str(result["candidates"]) + '</h2><p>Kandidaten mit Aussagen</p></section>'
             '<section class="card"><h2>' + str(s.get("facts", 0)) + '</h2><p>Aussagen</p></section>'
             '<section class="card"><h2>' + str(s.get("corroborated", 0)) + '</h2><p>von mehreren unabhängigen Quellen gestützt</p></section>'
             '<section class="card"><h2>' + str(s.get("contradictions", 0)) + '</h2><p>Widersprüche</p></section></div>')
    if not result["facts"]:
        return body + ('<p>Noch keine Aussagen. Unter <a href="/workbench/public-sources?' + q + '">Quellen &amp; Personen</a> '
                       'ein Suchpaket mit Quellen des PersonOSINT-Motors (Benutzernamen-Check, Keybase, INTERPOL, ICIJ, '
                       'Firmenregister Frankreich …) anlegen, freigeben und abfragen.</p>')
    body += '<h2>Warnhinweise</h2>'
    if result["red_flags"]:
        for flag in result["red_flags"]:
            body += ('<section class="card"><h3>' + escape(flag["label"]) + ' <small>(' + escape(SEVERITY.get(flag["severity"], flag["severity"])) +
                     ')</small></h3><p>' + escape(flag["text"]) + '</p>' +
                     ('<p>Quellen: ' + escape(", ".join(flag["sources"])) + '</p>' if flag["sources"] else '<p>Belege: siehe Widersprüche.</p>') +
                     '</section>')
    else:
        body += '<p>Keine Warnhinweise aus den vorliegenden Aussagen.</p>'
    body += '<h2>Widersprüche</h2>'
    if result["contradictions"]:
        for c in result["contradictions"]:
            body += ('<section class="card"><h3>' + escape(c["subject"]) + ': ' + escape(c["predicate_label"]) + '</h3><ul>' +
                     "".join('<li>' + escape(v["value"]) + ' – ' + escape(", ".join(v["sources"])) + '</li>' for v in c["values"]) +
                     '</ul><p>Verschiedene Werte können verschiedene Personen bedeuten. Am Original klären.</p></section>')
    else:
        body += '<p>Keine widersprüchlichen Angaben.</p>'
    body += '<h2>Querbezüge</h2>'
    if result["correlations"]:
        for c in result["correlations"]:
            body += ('<section class="card"><h3>' + escape(c["label"]) + '</h3><p>' + escape(c["headline"]) + '</p><p>Quellen: ' +
                     escape(", ".join(c["sources"])) + '</p></section>')
    else:
        body += '<p>Keine Querbezüge zwischen den Kandidaten.</p>'
    body += ('<h2>Aussagen</h2><p>Code: Buchstabe = Verlässlichkeit der Quelle (A–F), Ziffer = Glaubwürdigkeit der Aussage (1–6).</p>'
             '<table><tr><th>Wer</th><th>Angabe</th><th>Wert</th><th>Quelle</th><th>Code</th><th>Stützung</th></tr>')
    for f in sorted(result["facts"], key=lambda f: (f["subject_label"].casefold(), f["predicate_label"], f["object_label"])):
        mark = " – Widerspruch" if f["contradiction"] else ""
        body += ('<tr><td>' + escape(f["subject_label"]) + '</td><td>' + escape(f["predicate_label"]) + '</td><td>' +
                 escape(f["object_label"]) + ('' if f["status"] != "verworfen" else ' <small>(verworfen)</small>') + '</td><td>' +
                 _link(f["source_url"], f["source_label"]) + '</td><td title="' + escape(f["code_text"], quote=True) + '">' +
                 escape(f["code"]) + '</td><td>' + str(f["corroboration"]) + ' Quelle(n)' + escape(mark) + '</td></tr>')
    body += ('</table><p><a href="/workbench/leads483?' + q + '">Kandidaten im Fall prüfen</a> · '
             '<a href="/workbench/public-sources?' + q + '">Weitere Quellen abfragen</a></p>')
    return body


def attach_personosint_analysis502(app, build):
    ctx = app.state.context

    @app.get("/api/research/personanalyse")
    def analysis_api(request: Request, case_id: str = ""):
        user, _ = case_access(app, request, case_id)
        result = po_analysis.analyze(ctx, user, case_id)
        return {"case_id": case_id, **result}

    @app.get(PATH, response_class=HTMLResponse)
    def analysis_page(request: Request, case_id: str = ""):
        user, _ = case_access(app, request, case_id)
        result = po_analysis.analyze(ctx, user, case_id)
        return HTMLResponse(page("Personenanalyse", case_id, render(result, case_id), build),
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
