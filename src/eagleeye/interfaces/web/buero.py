"""Office pages for a small investigation practice.

/buero                      overview: what needs attention, all mandates
/buero/auftrag/neu          new mandate (creates the case)
/buero/auftrag              mandate file: screening, status, time, expenses, follow-ups
/buero/auftrag/ergaenzen    office data for a case created before the office module
/buero/mandanten, /buero/mandant, /buero/einstellungen
/buero/leistungsnachweis.csv|.pdf, /buero/zeiten.csv

UI rules as elsewhere: plain German, one primary action per area, every input labelled,
tables become cards on narrow screens, a failed form keeps what was typed.
"""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import date
from html import escape
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from eagleeye.application.buero import accounts, deletion, service as buero
from .app364 import CSRF_COOKIE
from .app448 import COOKIE
from .app449 import _drop
from .findings478 import verify_post
from .intel492 import EXTRA_CSS, _stack_tables, _when
from .operations476 import page, remember_page_state

CSS = EXTRA_CSS + (
    '<style>.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:.8rem}'
    '.kpi .card{margin:0}.actions{display:flex;gap:.6rem 1rem;flex-wrap:wrap;align-items:center;margin:.4rem 0 1rem}'
    'a.button,button.primary{display:inline-block;background:#9af3de;color:#0b1d2e;border:0;border-radius:8px;'
    'padding:.6rem 1rem;font-weight:600;text-decoration:none}a.button.secondary{background:transparent;color:#9af3de;'
    'border:1px solid #9af3de}fieldset{border:1px solid #647b93;border-radius:10px;padding:1rem;margin:0 0 1rem}'
    'legend{font-weight:600;padding:0 .4rem}.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));'
    'gap:0 1rem}.error{border-left:5px solid #ffb4a8;padding:.8rem;background:#4a2f36}.num{white-space:nowrap}'
    '.s-anfrage,.s-angehalten{border-color:#ffd18a;color:#ffe2b0}.s-abgelehnt{border-color:#ffb4a8;color:#ffb4a8}'
    '.overdue{color:#ffb4a8;font-weight:600}.soon{color:#ffe2b0}.voided{opacity:.6;text-decoration:line-through}'
    'label.check{margin:.2rem 0 .6rem}fieldset.q{border:0;border-top:1px solid #647b93;border-radius:0;padding:.7rem 0 .2rem;'
    'margin:0}.q legend{float:left;width:100%;padding:0;font-weight:500}.q .row{clear:both;padding-top:.4rem}'
    '.q .row label{display:inline-flex;gap:.35rem;align-items:center;margin:0 1.2rem .4rem 0}.q .row input{width:auto;margin:0}'
    'ul.attention{padding-left:1.2rem}ul.attention li{margin:.3rem 0}main th{word-break:normal;overflow-wrap:normal;hyphens:manual}'
    'td.num,td.date{white-space:nowrap;word-break:normal}.pill{white-space:nowrap}</style>')

GLOBAL_ROLES = {"investigator": "Ermittler/in – legt Aufträge an, sieht nur zugeordnete Aufträge",
                "reviewer": "Prüfer/in – prüft Befunde zugeordneter Aufträge",
                "read_only": "nur lesen – sieht zugeordnete Aufträge",
                "system_administrator": "Büroleitung – alle Rechte, alle Aufträge"}
CASE_ROLES = {"case_lead": "Fallleitung", "investigator": "Ermittler/in", "analyst": "Analyst/in",
              "reviewer": "Prüfer/in (Vier-Augen)", "report_author": "Berichtsautor/in", "read_only": "nur lesen"}

DONE = {
    "created": "Auftrag angelegt. Als Nächstes: die Auftragsprüfung unten ausfüllen.",
    "attached": "Auftragsdaten ergänzt. Als Nächstes: die Auftragsprüfung unten ausfüllen.",
    "screened": "Auftragsprüfung gespeichert.", "status": "Stand geändert.",
    "halted": "Auftrag angehalten. Recherche ruht, bis die Auftragsprüfung wiederholt ist.",
    "time": "Zeit gebucht.", "expense": "Auslage gebucht.", "voided": "Eintrag storniert.",
    "deadline": "Wiedervorlage angelegt.", "deadline_done": "Wiedervorlage erledigt.",
    "updated": "Auftragsdaten gespeichert.", "client": "Mandant gespeichert.", "settings": "Einstellungen gespeichert.",
    "deleted": "Fallakte endgültig gelöscht. Details stehen im Löschprotokoll unten.",
    "user": "Benutzer angelegt. Bitte das Startpasswort persönlich übergeben.",
    "member": "Mitarbeiter/in dem Auftrag zugeordnet.", "member_removed": "Zuordnung entzogen.",
    "password": "Passwort geändert. Andere Anmeldungen dieses Kontos sind beendet.",
    "reset": "Passwort zurückgesetzt. Beim nächsten Anmelden muss ein eigenes gewählt werden.",
    "locked": "Konto gesperrt, alle Anmeldungen beendet.", "unlocked": "Konto entsperrt.",
}


# ---------------------------------------------------------------- small HTML helpers

def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _href(path: str, **params) -> str:
    return _e(path + ("?" + urlencode(params) if params else ""))


def _field(label: str, name: str, value="", *, type="text", required=False, hint="", attrs="") -> str:
    req = " required" if required else ""
    hint_html = f'<small class="muted">{escape(hint)}</small>' if hint else ""
    return (f'<label>{escape(label)}{hint_html}<input type="{type}" name="{name}" value="{_e(value)}"{req} {attrs}>'
            '</label>')


def _area(label: str, name: str, value="", *, required=False, rows=3, maxlength=3000) -> str:
    req = " required" if required else ""
    return (f'<label>{escape(label)}<textarea name="{name}" rows="{rows}" maxlength="{maxlength}"{req}>{escape(str(value or ""))}'
            '</textarea></label>')


def _select(label: str, name: str, options: dict, value="", *, blank: str = "") -> str:
    opts = (f'<option value="">{escape(blank)}</option>' if blank else "") + "".join(
        f'<option value="{_e(k)}"{" selected" if str(k) == str(value) else ""}>{escape(str(v))}</option>'
        for k, v in options.items())
    return f'<label>{escape(label)}<select name="{name}">{opts}</select></label>'


def _check(label: str, name: str, checked=False) -> str:
    return (f'<label class="check"><input type="checkbox" name="{name}" value="on"{" checked" if checked else ""}>'
            f'<span>{escape(label)}</span></label>')


def _hidden(**values) -> str:
    return "".join(f'<input type="hidden" name="{k}" value="{_e(v)}">' for k, v in values.items())


def _pill(status: str) -> str:
    return f'<span class="pill s-{_e(status)}">{escape(buero.STATUSES.get(status, status))}</span>'


def _share(value) -> str:
    return "–" if value is None else f"{round(value * 100)} %"


# ---------------------------------------------------------------- request helpers

def _fingerprint(request: Request) -> str:
    return hashlib.sha256("|".join((request.headers.get("user-agent", ""), request.headers.get("accept-language", ""),
                                    request.client.host if request.client else "")).encode()).hexdigest()


def _maybe_user(app, request: Request):
    return app.state.context.team_identity_359.validate_session(
        request.cookies.get(COOKIE, ""), client_fingerprint=_fingerprint(request), touch=True)


def _user(app, request: Request) -> dict:
    user = _maybe_user(app, request)
    if not user:
        raise HTTPException(401, "Bitte anmelden.")
    remember_page_state(app, request, user)
    return user


async def _form(request: Request, *, max_bytes: int = 60000, max_fields: int = 40) -> dict:
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > max_bytes:
            raise HTTPException(413, "Formular zu groß.")
        data.extend(chunk)

    async def receive():
        return {"type": "http.request", "body": bytes(data), "more_body": False}
    form = await Request(request.scope, receive=receive).form(max_fields=max_fields, max_files=0, max_part_size=12000)
    return {key: str(value) for key, value in form.multi_items()}


def _csrf(request: Request) -> str:
    return _e(request.cookies.get(CSRF_COOKIE, ""))


def _status_line(request: Request) -> str:
    done = request.query_params.get("done", "")
    return f'<p role="status" class="card ok">{escape(DONE[done])}</p>' if done in DONE else ""


def _error(message: str) -> str:
    return f'<section class="error" role="alert"><strong>Bitte prüfen:</strong> {escape(message)}</section>' if message else ""


def _csv(rows: list[list], filename: str) -> Response:
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    for row in rows:
        # Spreadsheet programs execute cells that start with = + - @; neutralise them.
        writer.writerow(["'" + c if isinstance(c, str) and c[:1] in ("=", "+", "-", "@", "\t", "\r") else c for c in row])
    return Response(("﻿" + out.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


# ---------------------------------------------------------------- page bodies

def _overview(app, request, user, *, show_all: bool) -> str:
    ctx = app.state.context
    view = buero.dashboard(ctx, user)
    office = buero.settings(ctx)
    body = _status_line(request)
    if buero._is_admin(user) and (not office["firma"] or office["stundensatz_cent"] == "0"):
        body += ('<p class="warn">Bitte zuerst <a href="/buero/einstellungen">Briefkopf und Stundensatz festlegen</a> – '
                 'sie erscheinen in Leistungsnachweis und Bericht.</p>')
    month_name = date.fromisoformat(view["today"]).strftime("%m/%Y")
    overdue = [d for d in view["deadlines"] if d["overdue"]]
    body += ('<div class="kpi">'
             f'<section class="card"><span class="stat">{len(view["open"])}</span>offene Aufträge</section>'
             f'<section class="card"><span class="stat">{len(view["screening_open"])}</span>Auftragsprüfungen offen</section>'
             f'<section class="card"><span class="stat">{len(view["deadlines"])}</span>Wiedervorlagen bis 7 Tage'
             + (f' <span class="overdue">({len(overdue)} überfällig)</span>' if overdue else "") + '</section>'
             f'<section class="card"><span class="stat">{buero.hours(view["month_minutes"])}</span>meine Zeit {month_name}</section>'
             '</div>')
    if buero.may_use_clients(user):
        body += '<div class="actions"><a class="button" href="/buero/auftrag/neu">Neuen Auftrag anlegen</a></div>'

    attention = []
    for row in view["screening_open"]:
        attention.append(f'<li><a href="{_href("/buero/auftrag", case_id=row["case_id"])}">{escape(row["aktenzeichen"])}</a> '
                         f'{escape(row["title"])}: {"Warnsignal – Auftragsprüfung wiederholen" if row["status"] == "angehalten" else "Auftragsprüfung offen"}</li>')
    for row in view["due_mandates"]:
        word = "Abgabefrist überschritten" if row["due_state"] == "overdue" else "Abgabe bald fällig"
        attention.append(f'<li><a href="{_href("/buero/auftrag", case_id=row["case_id"])}">{escape(row["aktenzeichen"])}</a> '
                         f'<span class="{row["due_state"]}">{word}: {_when(row["due_on"])}</span></li>')
    for item in view["deadlines"]:
        attention.append(f'<li><a href="{_href("/buero/auftrag", case_id=item["case_id"])}">{escape(item["aktenzeichen"])}</a> '
                         f'Wiedervorlage <span class="{"overdue" if item["overdue"] else "soon"}">{_when(item["due_on"])}</span>: '
                         f'{escape(item["title"])}</li>')
    for row in view["over_budget"]:
        attention.append(f'<li><a href="{_href("/buero/auftrag", case_id=row["case_id"])}">{escape(row["aktenzeichen"])}</a> '
                         f'Budget zu {_share(row["totals"]["budget_share"])} ausgeschöpft</li>')
    for row in view["retention_due"]:
        attention.append(f'<li><a href="{_href("/buero/auftrag", case_id=row["case_id"])}">{escape(row["aktenzeichen"])}</a> '
                         f'Aufbewahrungsfrist abgelaufen ({_when(row["retention_until"])}) – '
                         + (f'<a href="{_href("/buero/loeschen", case_id=row["case_id"])}">Löschung vorbereiten</a></li>'
                            if buero._is_admin(user) else 'Büroleitung informieren</li>'))
    if buero._is_admin(user):
        for job in deletion.open_jobs(app.state.context):
            attention.append(f'<li>{escape(job["aktenzeichen"])} <span class="overdue">Löschung unvollständig</span> – '
                             '<a href="/buero/loeschprotokoll">im Löschprotokoll fortsetzen</a></li>')
    if attention:
        body += '<section class="card warn" aria-label="Braucht Aufmerksamkeit"><h2>Braucht Aufmerksamkeit</h2><ul class="attention">' \
                + "".join(attention) + '</ul></section>'

    rows = view["mandates"] if show_all else view["open"]
    closed = len(view["mandates"]) - len(view["open"])
    toggle = ('' if not closed else '<a href="/buero">Nur offene zeigen</a>' if show_all else
              f'<a href="/buero?alle=1">Auch {closed} abgeschlossene oder abgelehnte zeigen</a>')
    if rows:
        table = ('<table><thead><tr><th>Aktenzeichen</th><th>Mandant</th><th>Auftrag</th><th>Stand</th><th>Abgabe</th>'
                 '<th>Aufwand</th><th>Netto</th><th>Budget</th></tr></thead><tbody>')
        for row in rows:
            money = row["totals"]
            due = (f'<span class="{row["due_state"]}">{_when(row["due_on"])}</span>' if row["due_on"] else "–")
            table += (f'<tr><td class="date"><a href="{_href("/buero/auftrag", case_id=row["case_id"])}">{escape(row["aktenzeichen"])}</a></td>'
                      f'<td>{escape(row["client_name"])}</td><td>{escape(row["title"])}</td><td>{_pill(row["status"])}</td>'
                      f'<td class="date">{due}</td><td class="num">{buero.hours(money["minutes"])}</td>'
                      f'<td class="num">{buero.euro(money["net_cents"])}</td><td class="num">{_share(money["budget_share"])}</td></tr>')
        body += '<section aria-label="Aufträge"><h2>Aufträge</h2>' + (f'<p>{toggle}</p>' if toggle else '') + _stack_tables(table + '</tbody></table>') + '</section>'
    else:
        body += ('<section class="card"><h2>Aufträge</h2><p>' + ("Noch keine Aufträge." if not view["mandates"] else
                 "Keine offenen Aufträge. " + toggle) + '</p></section>')
    if view["without_mandate"]:
        items = "".join(f'<li>{escape(str(c.get("title") or c["case_id"]))} – <a href="{_href("/buero/auftrag/ergaenzen", case_id=c["case_id"])}">'
                        'Auftragsdaten ergänzen</a></li>' for c in view["without_mandate"][:50])
        body += ('<section class="card"><h2>Fälle ohne Auftragsdaten</h2><p class="muted">Diese Fälle wurden ohne Mandant und '
                 'Aktenzeichen angelegt. Mit den Auftragsdaten erscheinen sie in Fristen, Zeiterfassung und Abrechnung.</p>'
                 f'<ul>{items}</ul></section>')
    if buero.may_use_clients(user):
        body += ('<section class="card"><h2>Zeiten für die Buchhaltung</h2><form method="get" action="/buero/zeiten.csv" class="row">'
                 f'<label>Monat<input type="month" name="monat" value="{_e(view["today"][:7])}" required></label>'
                 '<button type="submit">Zeiten als CSV herunterladen</button></form></section>')
    return body


def _client_fields(values: dict, prefix: str = "") -> str:
    v = lambda k, d="": values.get(prefix + k, d)
    return ('<div class="two">' + _select("Art des Mandanten", prefix + "kind", buero.CLIENT_KINDS, v("kind", "unternehmen"))
            + _field("Name", prefix + "name", v("name"), attrs='maxlength="160"')
            + _field("Ansprechpartner", prefix + "contact_person", v("contact_person"), attrs='maxlength="160"')
            + _field("E-Mail", prefix + "email", v("email"), type="email", attrs='maxlength="160"')
            + _field("Telefon", prefix + "phone", v("phone"), attrs='maxlength="60"') + '</div>'
            + _area("Anschrift", prefix + "address", v("address"), rows=2, maxlength=400))


def _mandate_fields(values: dict, office: dict, *, with_case: bool) -> str:
    v = lambda k, d="": values.get(k, d)
    out = ""
    if with_case:
        out += ('<fieldset><legend>Auftrag</legend>'
                + _field("Titel des Auftrags", "title", v("title"), required=True, attrs='maxlength="160"',
                         hint=" (erscheint in Übersicht und Bericht)")
                + _select("Auftragsart", "kind", buero.MANDATE_KINDS, v("kind", "hintergrund"))
                + _area("Auftrag und Zweck (was soll geklärt werden, wofür?)", "purpose", v("purpose"), required=True, rows=4)
                + '</fieldset>')
    else:
        out += '<fieldset><legend>Auftrag</legend>' + _select("Auftragsart", "kind", buero.MANDATE_KINDS, v("kind", "hintergrund")) + '</fieldset>'
    out += ('<fieldset><legend>Rechtsgrundlage und Fristen</legend>'
            + _select("Rechtsgrundlage", "legal_basis_key", buero.LEGAL_BASES, v("legal_basis_key", "berechtigtes_interesse"))
            + _field("Erläuterung (z. B. welches Interesse, welcher Anspruch)", "legal_basis_note", v("legal_basis_note"),
                     attrs='maxlength="600"')
            + '<div class="two">' + _field("Eingangsdatum", "received_on", v("received_on", date.today().isoformat()), type="date", required=True)
            + _field("Abgabefrist (optional)", "due_on", v("due_on"), type="date") + '</div></fieldset>')
    rate_default = int(office["stundensatz_cent"])
    rate = v("hourly_rate", (f"{rate_default // 100},{rate_default % 100:02d}" if rate_default else ""))
    out += ('<fieldset><legend>Honorar</legend><div class="two">'
            + _select("Honorarmodell", "fee_model", buero.FEE_MODELS, v("fee_model", "stunden"))
            + _field("Stundensatz netto in €", "hourly_rate", rate, attrs='inputmode="decimal" maxlength="12"')
            + _field("Pauschale netto in € (nur bei Pauschalhonorar)", "flat_fee", v("flat_fee"), attrs='inputmode="decimal" maxlength="14"')
            + _field("Budget-Obergrenze netto in € (optional)", "budget", v("budget"), attrs='inputmode="decimal" maxlength="14"')
            + '</div></fieldset>')
    out += ('<fieldset><legend>Ergebnis</legend><div class="two">'
            + _field("Ergebnisempfänger", "recipient", v("recipient"), attrs='maxlength="200"')
            + _select("Empfängerstufe des Berichts", "recipient_level", buero.RECIPIENT_LEVELS, v("recipient_level", "mandant"))
            + '</div><p class="muted">Die Empfängerstufe entscheidet, welche Befunde der Mandantenbericht enthalten darf '
            '(Schutzklassen).</p></fieldset>')
    return out


def _client_choice(ctx, user, values: dict) -> str:
    known = buero.clients(ctx, user)
    options = {"neu": "Neuer Mandant (unten erfassen)"}
    options.update({c["client_id"]: c["name"] + (" (archiviert)" if c["archived"] else "") for c in known})
    selected = values.get("client_id") or ("neu" if not known else known[0]["client_id"])
    return ('<fieldset><legend>Mandant</legend>' + _select("Mandant", "client_id", options, selected)
            + f'<details{" open" if selected == "neu" else ""}><summary>Neuen Mandanten erfassen</summary>'
            + _client_fields(values, "client_") + '</details></fieldset>')


def _screening_form(request, row: dict, values: dict) -> str:
    v = lambda k, d="": values.get(k, d)
    questions = ""
    for q in buero.SCREENING_QUESTIONS:
        if q.get("optional") and row["kind"] != "vermisst":
            continue
        current = v("q_" + q["key"])
        radios = "".join(f'<label><input type="radio" name="q_{q["key"]}" value="{a}" required'
                         f'{" checked" if current == a else ""}>{label}</label>'
                         for a, label in buero.ANSWERS.items() if a != "entfaellt")
        questions += (f'<fieldset class="q"><legend>{escape(q["text"])}</legend><div class="row">{radios}</div></fieldset>')
    checklist = "".join(_check(label, "c_" + key, bool(v("c_" + key))) for key, label in buero.CHECKLIST.items())
    halted = row["status"] == "angehalten"
    return ('<section class="card" aria-label="Auftragsprüfung"><h2>Auftragsprüfung</h2>'
            '<p>Schützt Zielpersonen vor Missbrauch der Ergebnisse (Stalking, Bedrohung, Umgehen von Schutzanordnungen) '
            'und dokumentiert, warum der Auftrag angenommen wurde. „Unklar“ gilt als Warnsignal.</p>'
            + ('<p class="warn">Der Auftrag wurde wegen eines Warnsignals angehalten. Bitte neu prüfen und die Entscheidung begründen.</p>' if halted else "")
            + f'<form method="post" action="/buero/auftrag/pruefung">{_hidden(case_id=row["case_id"], version=row["version"])}'
            f'<input type="hidden" name="csrf" value="{_csrf(request)}">' + questions
            + '<fieldset><legend>Identitätsprüfung des Auftraggebers</legend>' + checklist + '</fieldset>'
            + '<fieldset class="q"><legend>Entscheidung</legend><div class="row">'
            + "".join(f'<label><input type="radio" name="decision" value="{d}" required{" checked" if v("decision") == d else ""}>{t}</label>'
                      for d, t in (("annehmen", "Auftrag annehmen"), ("ablehnen", "Auftrag ablehnen")))
            + '</div></fieldset>'
            + _area(f"Begründung (Pflicht bei Warnsignalen und Ablehnung, mindestens {buero.MIN_REASON} Zeichen)", "reason",
                    v("reason"), rows=3, maxlength=2000)
            + '<p class="muted">Bei bekannter Schutzanordnung oder Auskunftssperre ist nur eine Ablehnung möglich, '
              'außer ein Gericht oder eine Behörde ist Auftraggeber.</p>'
            + '<button class="primary" type="submit">Prüfung speichern</button></form></section>')


def _screening_result(screening: dict) -> str:
    warn = [q["text"] for q in buero.SCREENING_QUESTIONS if q["key"] in screening["warnings"]]
    ticks = [buero.CHECKLIST[k] for k in screening["checklist"]]
    return ('<details class="card"><summary><strong>Auftragsprüfung:</strong> '
            + ("angenommen" if screening["decision"] == "annehmen" else "abgelehnt")
            + f' am {_when(screening["decided_at"])} von {escape(screening["decided_by"])}'
            + (f' · {len(warn)} Warnsignal{"e" if len(warn) != 1 else ""}' if warn else ' · keine Warnsignale') + '</summary>'
            + ('<p>Warnsignale:</p><ul>' + "".join(f"<li>{escape(t)}</li>" for t in warn) + '</ul>' if warn else "")
            + ('<p>Begründung: ' + escape(screening["reason"]) + '</p>' if screening["reason"] else "")
            + '<p>Identitätsprüfung: ' + (escape(", ".join(ticks)) if ticks else "keine Punkte abgehakt") + '</p></details>')


def _akte(app, request, user, case_id: str, *, error: str = "", failed: str = "", values: dict | None = None) -> str:
    ctx = app.state.context
    row = buero.mandate(ctx, user, case_id)
    if row is None:
        raise HTTPException(404, "Für diesen Fall sind noch keine Auftragsdaten angelegt.")
    values = values or {}
    vals = lambda form: values if failed == form else {}
    office = buero.settings(ctx)
    manage = buero.may_manage(ctx, user, case_id)
    book = buero.may_book(ctx, user, case_id)
    csrf = f'<input type="hidden" name="csrf" value="{_csrf(request)}">'
    money = row["totals"]
    tax = buero.vat(office, money["net_cents"])
    client = row["client"]
    body = _status_line(request) + _error(error)
    body += (f'<p>{_pill(row["status"])} <strong>{escape(row["title"])}</strong> · Mandant: '
             + (f'<a href="{_href("/buero/mandant", client_id=client["client_id"])}">{escape(client["name"])}</a>'
                if buero.may_use_clients(user) else escape(client["name"]))
             + f' · {escape(buero.MANDATE_KINDS.get(row["kind"], row["kind"]))}</p>'
             + f'<p class="muted">Eingang {_when(row["received_on"])}'
             + (f' · Abgabe bis {_when(row["due_on"])}' if row["due_on"] else "")
             + (f' · abgeschlossen {_when(row["closed_on"])} · aufbewahren bis {_when(row["retention_until"])}' if row["closed_on"] else "")
             + '</p>')
    body += ('<div class="actions">'
             + (f'<a class="button" href="{_href("/workbench", case_id=case_id)}">Zur Recherche</a>' if row["status"] in buero.ACTIVE_STATUSES else "")
             + f'<a class="button secondary" href="{_href("/workbench/report", case_id=case_id)}">Arbeitsbericht</a>'
             + (f'<a class="button secondary" href="{_href("/buero/bericht.pdf", case_id=case_id)}">'
                f'Bericht für {escape(buero.RECIPIENT_LEVELS.get(row["recipient_level"], "Mandant"))} (PDF)</a>'
                if getattr(app.state, "buero_report_pdf", False) else "")
             + f'<a class="button secondary" href="{_href("/buero/leistungsnachweis.pdf", case_id=case_id)}">Leistungsnachweis (PDF)</a>'
             + f'<a href="{_href("/buero/leistungsnachweis.csv", case_id=case_id)}">als CSV</a></div>')
    preview = getattr(app.state, "buero_report_preview", None)
    if preview:
        body += preview(user, case_id, row["recipient_level"])

    if row["status"] in {"anfrage", "angehalten"}:
        body += _screening_form(request, row, vals("pruefung")) if manage else (
            '<section class="card warn"><h2>Auftragsprüfung offen</h2><p>Die Fallleitung muss die Auftragsprüfung abschließen, '
            'bevor recherchiert wird.</p></section>')
    elif row["screening"]:
        body += _screening_result(row["screening"])

    if manage and buero.TRANSITIONS.get(row["status"]):
        options = {s: buero.STATUSES[s] for s in sorted(buero.TRANSITIONS[row["status"]], key=list(buero.STATUSES).index)}
        v = vals("status")
        body += ('<section class="card"><h2>Stand ändern</h2><form method="post" action="/buero/auftrag/status">'
                 + _hidden(case_id=case_id, version=row["version"]) + csrf
                 + '<div class="two">' + _select("Neuer Stand", "status", options, v.get("status", ""))
                 + _field("Notiz" + (" (Pflicht beim Wiedereröffnen)" if row["status"] == "abgeschlossen" else " (optional)"),
                          "note", v.get("note", ""), attrs='maxlength="600"') + '</div>'
                 + ('<p class="muted">Mit „Abgeschlossen“ beginnt die Aufbewahrungsfrist '
                    f'({escape(office["aufbewahrung_monate"])} Monate laut Einstellungen).</p>' if "abgeschlossen" in options else "")
                 + '<button type="submit">Stand speichern</button></form></section>')
    if book and row["status"] in buero.ACTIVE_STATUSES:
        body += ('<details class="card"><summary>Warnsignal im laufenden Auftrag melden</summary>'
                 '<p>Ergeben sich Hinweise auf eine Schutzsituation (z. B. Frauenhaus, Auskunftssperre), die Recherche stoppen. '
                 'Der Auftrag ruht, bis die Fallleitung die Auftragsprüfung wiederholt hat.</p>'
                 '<form method="post" action="/buero/auftrag/anhalten">' + _hidden(case_id=case_id) + csrf
                 + _area("Was ist aufgefallen?", "note", vals("anhalten").get("note", ""), required=True, rows=2, maxlength=600)
                 + '<button type="submit">Auftrag anhalten</button></form></details>')

    # money summary
    share = money["budget_share"]
    body += ('<section class="card" aria-label="Aufwand und Kosten"><h2>Aufwand und Kosten</h2><div class="kpi">'
             f'<div><span class="stat">{buero.hours(money["minutes"])}</span>Zeit gesamt, davon {buero.hours(money["billable_minutes"])} abrechenbar</div>'
             f'<div><span class="stat">{buero.euro(money["fee_cents"])}</span>Honorar ('
             + (escape(buero.FEE_MODELS["pauschal"]) if row["fee_model"] == "pauschal" else f'{buero.euro(row["hourly_rate_cents"])}/Std.')
             + f')</div><div><span class="stat">{buero.euro(money["expenses_cents"])}</span>Auslagen</div>'
             f'<div><span class="stat">{buero.euro(tax["gross_cents"])}</span>brutto'
             + (f' (netto {buero.euro(money["net_cents"])} + {tax["rate"]} % USt.)' if tax["rate"] else ' (§ 19 UStG)') + '</div></div>'
             + (f'<p>Budget {buero.euro(money["budget_cents"])}: <progress max="100" value="{min(100, round(share * 100))}" '
                f'aria-label="Budget ausgeschöpft">{round(share * 100)} %</progress> {round(share * 100)} % ausgeschöpft'
                + (' <span class="overdue">– Budget fast erreicht, Mandanten informieren</span>' if share >= 0.8 else "") + '</p>'
                if share is not None else "")
             + '</section>')

    # time
    entries = buero.time_entries(ctx, user, case_id)
    v = vals("zeit")
    if book and row["status"] != "abgelehnt":
        body += ('<section class="card" aria-label="Zeit buchen"><h2>Zeit buchen</h2><form method="post" action="/buero/zeit">'
                 + _hidden(case_id=case_id) + csrf + '<div class="two">'
                 + _field("Datum", "work_date", v.get("work_date", date.today().isoformat()), type="date", required=True)
                 + _field("Dauer in Stunden (z. B. 1,5 oder 1:30)", "duration", v.get("duration", ""), required=True,
                          attrs='inputmode="decimal" maxlength="6"')
                 + _select("Tätigkeit", "activity", buero.ACTIVITIES, v.get("activity", "recherche"))
                 + _field("Beschreibung", "note", v.get("note", ""), attrs='maxlength="500"') + '</div>'
                 + _check("abrechenbar", "billable_box", v.get("billable_box", "on") == "on" if v else True)
                 + '<button class="primary" type="submit">Zeit buchen</button></form></section>')
    if entries:
        table = '<table><thead><tr><th>Datum</th><th>Wer</th><th>Tätigkeit</th><th>Beschreibung</th><th>Dauer</th><th>Aktion</th></tr></thead><tbody>'
        for entry in entries:
            voided = bool(entry["voided_at"])
            action = ""
            if voided:
                action = "storniert: " + escape(entry["void_reason"])
            elif book and (entry["username"] == user["username"] or manage):
                action = _void_form(case_id, "time", entry["entry_id"], csrf)
            table += (f'<tr{" class=\"voided\"" if voided else ""}><td class="date">{_when(entry["work_date"])}</td><td>{escape(entry["username"])}</td>'
                      f'<td>{escape(buero.ACTIVITIES.get(entry["activity"], entry["activity"]))}</td><td>{escape(entry["note"])}</td>'
                      f'<td class="num">{buero.hours(entry["minutes"])}{"" if entry["billable"] else " (nicht abrechenbar)"}</td>'
                      f'<td>{action}</td></tr>')
        body += '<section aria-label="Gebuchte Zeiten"><h2>Gebuchte Zeiten</h2>' + _stack_tables(table + '</tbody></table>') + '</section>'

    # expenses
    spent = buero.expenses(ctx, user, case_id)
    v = vals("auslage")
    if book and row["status"] != "abgelehnt":
        km_rate = int(office["km_satz_cent"])
        body += ('<section class="card" aria-label="Auslage buchen"><h2>Auslage buchen</h2><form method="post" action="/buero/auslage">'
                 + _hidden(case_id=case_id) + csrf + '<div class="two">'
                 + _field("Datum", "spent_on", v.get("spent_on", date.today().isoformat()), type="date", required=True)
                 + _select("Art", "kind", buero.EXPENSE_KINDS, v.get("kind", "gebuehr"))
                 + _field(f"Kilometer (nur Fahrtkilometer, {buero.euro(km_rate)}/km)", "km", v.get("km", ""), attrs='inputmode="numeric" maxlength="5"')
                 + _field("Betrag netto in € (alle anderen Arten)", "amount", v.get("amount", ""), attrs='inputmode="decimal" maxlength="12"')
                 + _field("Beschreibung", "note", v.get("note", ""), attrs='maxlength="500"') + '</div>'
                 + _check("abrechenbar", "billable_box", v.get("billable_box", "on") == "on" if v else True)
                 + '<button class="primary" type="submit">Auslage buchen</button></form></section>')
    if spent:
        table = '<table><thead><tr><th>Datum</th><th>Wer</th><th>Art</th><th>Beschreibung</th><th>Betrag</th><th>Aktion</th></tr></thead><tbody>'
        for entry in spent:
            voided = bool(entry["voided_at"])
            action = ""
            if voided:
                action = "storniert: " + escape(entry["void_reason"])
            elif book and (entry["username"] == user["username"] or manage):
                action = _void_form(case_id, "expense", entry["expense_id"], csrf)
            what = buero.EXPENSE_KINDS.get(entry["kind"], entry["kind"]) + (f' ({entry["km"]} km)' if entry["km"] else "")
            table += (f'<tr{" class=\"voided\"" if voided else ""}><td class="date">{_when(entry["spent_on"])}</td><td>{escape(entry["username"])}</td>'
                      f'<td>{escape(what)}</td><td>{escape(entry["note"])}</td>'
                      f'<td class="num">{buero.euro(entry["amount_cents"])}{"" if entry["billable"] else " (nicht abrechenbar)"}</td>'
                      f'<td>{action}</td></tr>')
        body += '<section aria-label="Gebuchte Auslagen"><h2>Gebuchte Auslagen</h2>' + _stack_tables(table + '</tbody></table>') + '</section>'

    # follow-ups
    items = buero.deadlines(ctx, user, case_id)
    v = vals("frist")
    today = date.today().isoformat()
    lis = ""
    for item in items:
        if item["done_at"]:
            lis += f'<li class="voided">{_when(item["due_on"])}: {escape(item["title"])} (erledigt)</li>'
        else:
            state = "overdue" if item["due_on"] < today else ""
            done_form = (f'<form method="post" action="/buero/frist/erledigt" style="display:inline">{_hidden(case_id=case_id, deadline_id=item["deadline_id"])}'
                         f'{csrf}<button type="submit">erledigt</button></form>') if book else ""
            lis += f'<li><span class="{state}">{_when(item["due_on"])}</span>: {escape(item["title"])} {done_form}</li>'
    body += ('<section class="card" aria-label="Wiedervorlagen"><h2>Wiedervorlagen</h2>' + (f'<ul>{lis}</ul>' if lis else '<p>Keine.</p>')
             + (('<form method="post" action="/buero/frist">' + _hidden(case_id=case_id) + csrf + '<div class="two">'
                 + _field("Datum", "due_on", v.get("due_on", ""), type="date", required=True)
                 + _field("Was ist zu tun?", "title", v.get("title", ""), required=True, attrs='maxlength="200"')
                 + '</div><button type="submit">Wiedervorlage anlegen</button></form>') if book else "") + '</section>')

    members = [m for m in ctx.team_identity_359.list_case_memberships(case_id) if m["active"]]
    v = vals("team")
    lis = ""
    for m in members:
        remove = ""
        if manage and m["username"] != user["username"]:
            remove = ('<details><summary>entziehen</summary><form method="post" action="/buero/auftrag/team/entziehen">'
                      + _hidden(case_id=case_id, username=m["username"], case_role=m["case_role"]) + csrf
                      + '<label>Grund<input name="reason" required minlength="8" maxlength="300"></label>'
                      '<button type="submit">Zuordnung entziehen</button></form></details>')
        lis += (f'<li>{escape(m["display_name"] or m["username"])} ({escape(m["username"])}) – '
                f'{escape(CASE_ROLES.get(m["case_role"], m["case_role"]))}{remove}</li>')
    assignable = ""
    if manage:
        users = {u["username"]: (u["display_name"] or u["username"]) for u in ctx.team_identity_359.list_users()
                 if u["active"] and u["global_role"] != "system_administrator"}
        if users:
            assignable = ('<form method="post" action="/buero/auftrag/team">' + _hidden(case_id=case_id) + csrf + '<div class="two">'
                          + _select("Mitarbeiter/in", "username", users, v.get("username", ""))
                          + _select("Rolle in diesem Auftrag", "case_role", CASE_ROLES, v.get("case_role", "investigator"))
                          + '</div><button type="submit">Zuordnen</button></form>')
        else:
            assignable = ('<p class="muted">Weitere Benutzer legt die Büroleitung unter '
                          '<a href="/buero/team">Team</a> an.</p>' if buero._is_admin(user) else "")
    body += ('<details class="card"' + (" open" if failed == "team" else "") + '><summary>Team dieses Auftrags ('
             + str(len(members)) + ')</summary><p class="muted">Die Büroleitung sieht alle Aufträge. Andere sehen nur Aufträge, '
             'denen sie zugeordnet sind.</p>' + (f'<ul>{lis}</ul>' if lis else '') + assignable + '</details>')

    if row["status"] in {"abgeschlossen", "abgelehnt"} and row["retention_until"]:
        is_due = deletion.due(row)
        body += ('<section class="card' + (' warn' if is_due else '') + '" aria-label="Aufbewahrung"><h2>Aufbewahrung und Löschung</h2>'
                 f'<p>Aufbewahren bis {_when(row["retention_until"])}'
                 + (' – <strong>Frist abgelaufen.</strong>' if is_due else '.') + '</p>'
                 + (f'<a class="button{"" if is_due else " secondary"}" href="{_href("/buero/loeschen", case_id=case_id)}">'
                    'Löschung vorbereiten</a>' if buero._is_admin(user) else '<p class="muted">Löschen kann die Büroleitung.</p>')
                 + '</section>')
    if manage:
        edit = values if failed == "bearbeiten" else {
            "kind": row["kind"], "legal_basis_key": row["legal_basis_key"], "received_on": row["received_on"],
            "due_on": row["due_on"], "fee_model": row["fee_model"],
            "hourly_rate": f'{row["hourly_rate_cents"] // 100},{row["hourly_rate_cents"] % 100:02d}',
            "flat_fee": (f'{row["flat_fee_cents"] // 100},{row["flat_fee_cents"] % 100:02d}' if row["flat_fee_cents"] else ""),
            "budget": (f'{row["budget_cents"] // 100},{row["budget_cents"] % 100:02d}' if row["budget_cents"] else ""),
            "recipient": row["recipient"], "recipient_level": row["recipient_level"]}
        body += ('<details class="card"' + (" open" if failed == "bearbeiten" else "") + '><summary>Auftragsdaten bearbeiten</summary>'
                 '<form method="post" action="/buero/auftrag/bearbeiten">' + _hidden(case_id=case_id, version=row["version"]) + csrf
                 + _mandate_fields(edit, office, with_case=False) + '<button type="submit">Änderungen speichern</button></form></details>')
    log = buero.status_log(ctx, user, case_id)
    body += ('<details class="card"><summary>Verlauf</summary><ul>' + "".join(
        f'<li>{_when(e["at"])} – {escape(e["actor"])}: {escape(buero.STATUSES.get(e["from_status"], "neu"))} → '
        f'{escape(buero.STATUSES.get(e["to_status"], e["to_status"]))}{(" – " + escape(e["note"])) if e["note"] else ""}</li>'
        for e in log) + '</ul></details>')
    return body


def _void_form(case_id: str, kind: str, entry_id: str, csrf: str) -> str:
    return ('<details><summary>stornieren</summary><form method="post" action="/buero/storno">'
            + _hidden(case_id=case_id, entry_type=kind, entry_id=entry_id) + csrf
            + '<label>Grund<input name="reason" required minlength="5" maxlength="300"></label>'
            '<button type="submit">Stornieren</button></form></details>')


def _settings_body(request, office: dict, error: str = "", values: dict | None = None) -> str:
    v = values or {**office, "stundensatz": f'{int(office["stundensatz_cent"]) // 100},{int(office["stundensatz_cent"]) % 100:02d}',
                   "km_satz": f'{int(office["km_satz_cent"]) // 100},{int(office["km_satz_cent"]) % 100:02d}'}
    return (_status_line(request) + _error(error)
            + f'<form method="post" action="/buero/einstellungen"><input type="hidden" name="csrf" value="{_csrf(request)}">'
            '<fieldset><legend>Briefkopf</legend>'
            + _field("Name des Büros", "firma", v.get("firma", ""), attrs='maxlength="120"')
            + _area("Anschrift", "anschrift", v.get("anschrift", ""), rows=3, maxlength=400)
            + _field("Kontakt (Telefon, E-Mail, Web)", "kontakt", v.get("kontakt", ""), attrs='maxlength="200"')
            + _field("Fußzeile für Berichte", "bericht_fusszeile", v.get("bericht_fusszeile", ""), attrs='maxlength="200"')
            + '</fieldset><fieldset><legend>Abrechnung</legend><div class="two">'
            + _field("Standard-Stundensatz netto in €", "stundensatz", v.get("stundensatz", ""), attrs='inputmode="decimal" maxlength="10"')
            + _field("Kilometersatz in €", "km_satz", v.get("km_satz", ""), attrs='inputmode="decimal" maxlength="6"')
            + _select("Umsatzsteuer", "ust_modus", buero.VAT_MODES, v.get("ust_modus", "regel"))
            + _field("Umsatzsteuersatz in %", "ust_satz", v.get("ust_satz", "19"), attrs='inputmode="numeric" maxlength="2"')
            + '</div></fieldset><fieldset><legend>Akten</legend><div class="two">'
            + _field("Präfix für Aktenzeichen (optional, z. B. Kürzel des Büros)", "az_praefix", v.get("az_praefix", ""), attrs='maxlength="12"')
            + _field("Aufbewahrung nach Abschluss in Monaten", "aufbewahrung_monate", v.get("aufbewahrung_monate", "36"),
                     attrs='inputmode="numeric" maxlength="3"')
            + '</div><p class="muted">Vorgabe 36 Monate. Bitte an das eigene Löschkonzept anpassen; Rechnungen und '
              'Buchungsbelege gehören in die Buchhaltung und unterliegen eigenen Fristen.</p></fieldset>'
            + '<button class="primary" type="submit">Einstellungen speichern</button></form>'
            + '<p><a href="/buero/loeschprotokoll">Löschprotokoll ansehen</a></p>')


# ---------------------------------------------------------------- PDF statement

def statement_pdf(sheet: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    office, row = sheet["office"], sheet["mandate"]
    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=8.5, leading=11)
    esc = lambda value: escape(str(value or "")).replace("\n", "<br/>")
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f'Leistungsnachweis {row["aktenzeichen"]}', author=office["firma"] or "EagleEye")
    story = []
    if office["firma"] or office["anschrift"]:
        story.append(Paragraph("<b>" + esc(office["firma"]) + "</b><br/>" + esc(office["anschrift"]) +
                               ("<br/>" + esc(office["kontakt"]) if office["kontakt"] else ""), small))
        story.append(Spacer(1, 8 * mm))
    client = row["client"]
    story.append(Paragraph(esc(client["name"]) + ("<br/>" + esc(client.get("contact_person")) if client.get("contact_person") else "")
                           + ("<br/>" + esc(client.get("address")) if client.get("address") else ""), styles["BodyText"]))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("Leistungsnachweis", styles["Title"]))
    story.append(Paragraph(f'Aktenzeichen {esc(row["aktenzeichen"])} · {esc(row["title"])}<br/>Stand {date.today().strftime("%d.%m.%Y")}',
                           styles["BodyText"]))
    story.append(Spacer(1, 5 * mm))
    grid = TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef3")),
                       ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 8.5)])
    if sheet["times"]:
        data = [["Datum", "Tätigkeit", "Beschreibung", "Dauer"]]
        for e in sheet["times"]:
            data.append([_when(e["work_date"]), Paragraph(esc(buero.ACTIVITIES.get(e["activity"], e["activity"])), small),
                         Paragraph(esc(e["note"]) + ("" if e["billable"] else " <i>(nicht abrechenbar)</i>"), small),
                         buero.hours(e["minutes"])])
        story += [Paragraph("Zeitaufwand", styles["Heading3"]),
                  Table(data, colWidths=[22 * mm, 38 * mm, 88 * mm, 22 * mm], style=grid, repeatRows=1), Spacer(1, 4 * mm)]
    if sheet["expenses"]:
        data = [["Datum", "Art", "Beschreibung", "Betrag"]]
        for e in sheet["expenses"]:
            what = buero.EXPENSE_KINDS.get(e["kind"], e["kind"]) + (f' ({e["km"]} km)' if e["km"] else "")
            data.append([_when(e["spent_on"]), Paragraph(esc(what), small),
                         Paragraph(esc(e["note"]) + ("" if e["billable"] else " <i>(nicht abrechenbar)</i>"), small),
                         buero.euro(e["amount_cents"])])
        story += [Paragraph("Auslagen", styles["Heading3"]),
                  Table(data, colWidths=[22 * mm, 38 * mm, 88 * mm, 22 * mm], style=grid, repeatRows=1), Spacer(1, 4 * mm)]
    money, tax = sheet["totals"], sheet["vat"]
    fee_label = ("Pauschalhonorar" if row["fee_model"] == "pauschal" else
                 f'Honorar ({buero.hours(money["billable_minutes"])} × {buero.euro(row["hourly_rate_cents"])})')
    summary = [[fee_label, buero.euro(money["fee_cents"])], ["Auslagen", buero.euro(money["expenses_cents"])],
               ["Summe netto", buero.euro(money["net_cents"])]]
    if tax["rate"]:
        summary += [[f'Umsatzsteuer {tax["rate"]} %', buero.euro(tax["vat_cents"])], ["Summe brutto", buero.euro(tax["gross_cents"])]]
    story += [Paragraph("Zusammenfassung", styles["Heading3"]),
              Table(summary, colWidths=[128 * mm, 42 * mm], style=TableStyle([
                  ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.black), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                  ("ALIGN", (1, 0), (1, -1), "RIGHT")]))]
    notes = [tax["note"]] if tax["note"] else []
    notes.append("Dieser Leistungsnachweis ist keine Rechnung.")
    story += [Spacer(1, 6 * mm), Paragraph(" ".join(esc(n) for n in notes), small)]
    if office["bericht_fusszeile"]:
        story.append(Paragraph(esc(office["bericht_fusszeile"]), small))
    doc.build(story)
    return out.getvalue()


# ---------------------------------------------------------------- routes

def attach_buero(app, build: str) -> None:
    ctx = app.state.context
    buero.initialize(ctx)
    deletion.initialize(ctx)
    app.state.buero = True
    from .buero_report import attach_report_pdf
    attach_report_pdf(app, build)

    def render(title: str, body: str, status: int = 200, case_id: str = "") -> HTMLResponse:
        return HTMLResponse(page(title, case_id, CSS + body, build), status_code=status, headers={"Cache-Control": "no-store"})

    def akte_response(request, user, case_id, *, error="", failed="", values=None, status=422):
        row = buero.mandate(ctx, user, case_id)
        title = f'Auftrag {row["aktenzeichen"]}' if row else "Auftrag"
        return render(title, _akte(app, request, user, case_id, error=error, failed=failed, values=values), status, case_id)

    # Research may only contact the network while the mandate is accepted and open.
    def research_gate(case_id: str) -> str:
        state = buero.mandate_state(ctx, case_id)
        if not state or state in buero.ACTIVE_STATUSES:
            return ""
        reason = {"anfrage": "die Auftragsprüfung ist noch nicht abgeschlossen",
                  "angehalten": "der Auftrag wurde wegen eines Warnsignals angehalten",
                  "abgelehnt": "der Auftrag wurde abgelehnt",
                  "abgeschlossen": "der Auftrag ist abgeschlossen"}.get(state, "der Auftrag ist nicht freigegeben")
        return f"Kein Abruf: {reason}. Bitte in der Büroverwaltung (Auftragsakte) klären."
    app.state.research_gate = research_gate

    def sidebar_case_header(case_id, user):
        """Case box at the top of the menu: current mandate and a switcher between open mandates."""
        visible = {str(c["case_id"]) for c in buero.visible_cases(ctx, user)}
        marks = ",".join("?" for _ in buero.OPEN_STATUSES)
        open_rows = [r for r in ctx.db.all(
            "SELECT m.case_id, m.aktenzeichen, c.title FROM buero_mandates m JOIN cases c ON c.case_id=m.case_id "
            f"WHERE m.status IN ({marks}) ORDER BY m.az_year DESC, m.az_number DESC LIMIT 200", tuple(buero.OPEN_STATUSES))
            if r["case_id"] in visible]
        head = '<div class="case">'
        if case_id:
            row = ctx.db.one("SELECT c.title, m.aktenzeichen, m.status FROM cases c LEFT JOIN buero_mandates m "
                             "ON m.case_id=c.case_id WHERE c.case_id=?", (case_id,))
            if row and row["aktenzeichen"]:
                head += (f'<b>{escape(row["aktenzeichen"])}</b>{escape(str(row["title"] or ""))}<br>'
                         f'<small>{escape(buero.STATUSES.get(row["status"], row["status"]))}</small><br>'
                         f'<a href="{_href("/buero/auftrag", case_id=case_id)}">Auftragsakte</a>')
            elif row:
                head += (f'<b>{escape(str(row["title"] or case_id))}</b><small>ohne Auftragsdaten</small><br>'
                         f'<a href="{_href("/buero/auftrag/ergaenzen", case_id=case_id)}">Auftragsdaten ergänzen</a>')
        else:
            head += '<b>Kein Auftrag geöffnet</b>'
        choices = [r for r in open_rows if r["case_id"] != case_id]
        if choices:
            options = "".join(f'<option value="{_e(r["case_id"])}">{escape(r["aktenzeichen"])} – {escape(str(r["title"] or "")[:40])}</option>'
                              for r in choices)
            head += ('<form method="get" action="/buero/auftrag"><label>' + ("Anderen Auftrag öffnen" if case_id else "Auftrag öffnen")
                     + f'<select name="case_id">{options}</select></label><button type="submit">Öffnen</button></form>')
        return head + '</div>'
    ctx.sidebar_case_header = sidebar_case_header
    ctx.research_gate = research_gate  # service level: execution497 checks before reserving a step

    # Second line of defence for any other caller of live provider runs.
    providers = getattr(ctx, "provider_collection_120", None)
    if providers is not None and not getattr(providers, "_buero_gated", False):
        live_execute = providers.execute

        def gated_execute(*, case_id, mode="replay", **kwargs):
            refusal = research_gate(case_id) if mode == "live" else ""
            if refusal:
                raise PermissionError(refusal)
            return live_execute(case_id=case_id, mode=mode, **kwargs)
        providers.execute = gated_execute
        providers._buero_gated = True

    previous_status = getattr(app.state, "workflow_status", None)

    def workflow_status(user, case_id):
        statuses, next_html = previous_status(user, case_id) if previous_status else ({}, "")
        row = ctx.db.one("SELECT aktenzeichen, status FROM buero_mandates WHERE case_id=?", (case_id,))
        link = _href("/buero/auftrag", case_id=case_id)
        if row is None:
            banner = (f'<p class="muted">Ohne Auftragsdaten: <a href="{_href("/buero/auftrag/ergaenzen", case_id=case_id)}">'
                      'Mandant, Aktenzeichen und Auftragsprüfung ergänzen</a>.</p>')
        elif row["status"] in buero.ACTIVE_STATUSES:
            banner = (f'<p class="muted">Auftrag <a href="{link}">{escape(row["aktenzeichen"])}</a> · '
                      f'{escape(buero.STATUSES[row["status"]])}</p>')
        else:
            banner = (f'<section class="card warn" aria-label="Auftragsstand"><h2>Auftrag {escape(row["aktenzeichen"])}: '
                      f'{escape(buero.STATUSES[row["status"]])}</h2><p>{escape(research_gate(case_id))}</p>'
                      f'<a href="{link}">Zur Auftragsakte →</a></section>')
        return statuses, banner + next_html
    app.state.workflow_status = workflow_status

    # Home: without any case the office is the starting point; the old overview gets an office link.
    old_home = next((r.endpoint for r in reversed(app.router.routes) if getattr(r, "path", None) == "/" and "GET" in (r.methods or set())), None)
    old_workbench = next((r.endpoint for r in reversed(app.router.routes)
                          if getattr(r, "path", None) == "/workbench" and "GET" in (r.methods or set())), None)
    if old_home is not None:
        _drop(app, "/", {"GET"})

        @app.get("/")
        def home(request: Request, view: str = "overview", case_id: str = ""):
            if not case_id and _maybe_user(app, request):
                return RedirectResponse("/buero", status_code=303)  # the office is the start page
            result = old_home(request, view=view, case_id=case_id)
            if isinstance(result, HTMLResponse):
                html = result.body.decode("utf-8").replace(
                    '<nav class="nav" aria-label="Hauptnavigation">',
                    '<nav class="nav" aria-label="Hauptnavigation"><a href="/buero">Büro – alle Aufträge</a>', 1)
                return HTMLResponse(html, status_code=result.status_code, headers={"Cache-Control": "no-store"})
            return result
    if old_workbench is not None:
        _drop(app, "/workbench", {"GET"})

        @app.get("/workbench", response_class=HTMLResponse)
        def workbench(request: Request, case_id: str = ""):
            if not case_id:
                user = _maybe_user(app, request)
                if user and not buero.visible_cases(ctx, user):
                    return RedirectResponse("/buero", status_code=303)
            return old_workbench(request, case_id=case_id)

    @app.get("/buero", response_class=HTMLResponse)
    def overview(request: Request, alle: str = ""):
        user = _user(app, request)
        return render("Büro – Übersicht", _overview(app, request, user, show_all=bool(alle)))

    # ------------------------------------------------ new mandate
    def new_body(request, user, values: dict, error: str = "") -> str:
        office = buero.settings(ctx)
        return (_error(error) + '<p>Legt Fall und Auftragsakte in einem Schritt an. Danach folgt die Auftragsprüfung; '
                'erst nach der Annahme startet die Recherche.</p>'
                f'<form method="post" action="/buero/auftrag/neu"><input type="hidden" name="csrf" value="{_csrf(request)}">'
                + _client_choice(ctx, user, values) + _mandate_fields(values, office, with_case=True)
                + '<button class="primary" type="submit">Auftrag anlegen</button></form>')

    @app.get("/buero/auftrag/neu", response_class=HTMLResponse)
    def new_mandate(request: Request):
        user = _user(app, request)
        try:
            ctx.team_identity_359.require_global(user, "case.create")
        except PermissionError:
            raise HTTPException(403, "Neue Aufträge legen Büroleitung und Ermittler an.") from None
        return render("Neuen Auftrag anlegen", new_body(request, user, {}))

    @app.post("/buero/auftrag/neu")
    async def create(request: Request):
        form = await _form(request)
        user = _user(app, request)
        verify_post(app, request, user, form.get("csrf", ""))
        try:
            row = buero.create_mandate(ctx, user, form)
        except buero.BueroError as exc:
            return render("Neuen Auftrag anlegen", new_body(request, user, form, str(exc)), 422)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        return RedirectResponse("/buero/auftrag?" + urlencode({"case_id": row["case_id"], "done": "created"}), status_code=303)

    # ------------------------------------------------ office data for an existing case
    def attach_body(request, user, case_id, values, error="") -> str:
        case = ctx.db.one("SELECT title FROM cases WHERE case_id=?", (case_id,)) or {}
        return (_error(error) + f'<p>Fall: <strong>{escape(str(case.get("title") or case_id))}</strong></p>'
                f'<form method="post" action="/buero/auftrag/ergaenzen"><input type="hidden" name="csrf" value="{_csrf(request)}">'
                + _hidden(case_id=case_id) + _client_choice(ctx, user, values) + _mandate_fields(values, buero.settings(ctx), with_case=False)
                + '<button class="primary" type="submit">Auftragsdaten speichern</button></form>')

    @app.get("/buero/auftrag/ergaenzen", response_class=HTMLResponse)
    def attach_form(request: Request, case_id: str = ""):
        user = _user(app, request)
        if not buero.case_exists(ctx, case_id):
            raise HTTPException(404, "Diesen Fall gibt es nicht (mehr).")
        if not buero.may_manage(ctx, user, case_id) or not buero.may_use_clients(user):
            raise HTTPException(403, "Auftragsdaten ergänzt die Fallleitung.")
        if buero.mandate_state(ctx, case_id):
            return RedirectResponse("/buero/auftrag?" + urlencode({"case_id": case_id}), status_code=303)
        return render("Auftragsdaten ergänzen", attach_body(request, user, case_id, {}), case_id=case_id)

    @app.post("/buero/auftrag/ergaenzen")
    async def attach_post(request: Request):
        form = await _form(request)
        user = _user(app, request)
        verify_post(app, request, user, form.get("csrf", ""))
        case_id = form.get("case_id", "")
        try:
            buero.attach_mandate(ctx, user, case_id, form)
        except buero.BueroError as exc:
            return render("Auftragsdaten ergänzen", attach_body(request, user, case_id, form, str(exc)), 422, case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        return RedirectResponse("/buero/auftrag?" + urlencode({"case_id": case_id, "done": "attached"}), status_code=303)

    # ------------------------------------------------ mandate file
    @app.get("/buero/auftrag", response_class=HTMLResponse)
    def akte(request: Request, case_id: str = ""):
        user = _user(app, request)
        try:
            row = buero.mandate(ctx, user, case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        if row is None:
            if not buero.case_exists(ctx, case_id):
                raise HTTPException(404, "Diesen Fall gibt es nicht (mehr).")
            return RedirectResponse("/buero/auftrag/ergaenzen?" + urlencode({"case_id": case_id}), status_code=303)
        return render(f'Auftrag {row["aktenzeichen"]}', _akte(app, request, user, case_id), case_id=case_id)

    def akte_post(path: str, form_name: str, action, done: str):
        @app.post(path)
        async def handler(request: Request):
            form = await _form(request)
            user = _user(app, request)
            verify_post(app, request, user, form.get("csrf", ""))
            case_id = form.get("case_id", "")
            try:
                action(user, case_id, form)
            except buero.StaleError as exc:
                return akte_response(request, user, case_id, error=str(exc), status=409)
            except buero.BueroError as exc:
                return akte_response(request, user, case_id, error=str(exc), failed=form_name, values=form)
            except PermissionError as exc:
                raise HTTPException(403, str(exc)) from None
            anchor = {"zeit": "#zeit", "auslage": "#auslage"}.get(form_name, "")
            return RedirectResponse("/buero/auftrag?" + urlencode({"case_id": case_id, "done": done}) + anchor, status_code=303)
        handler.__name__ = "buero_" + form_name
        return handler

    def _billable(form):
        return {**form, "billable": "1" if form.get("billable_box") == "on" else "0"}

    akte_post("/buero/auftrag/pruefung", "pruefung", lambda u, c, f: buero.screen(ctx, u, c, f), "screened")
    akte_post("/buero/auftrag/status", "status", lambda u, c, f: buero.set_status(ctx, u, c, f), "status")
    akte_post("/buero/auftrag/anhalten", "anhalten", lambda u, c, f: buero.halt(ctx, u, c, f), "halted")
    akte_post("/buero/auftrag/bearbeiten", "bearbeiten", lambda u, c, f: buero.update_mandate(ctx, u, c, f), "updated")
    akte_post("/buero/zeit", "zeit", lambda u, c, f: buero.add_time(ctx, u, c, _billable(f)), "time")
    akte_post("/buero/auslage", "auslage", lambda u, c, f: buero.add_expense(ctx, u, c, _billable(f)), "expense")
    akte_post("/buero/storno", "storno", lambda u, c, f: buero.void_entry(ctx, u, c, f), "voided")
    akte_post("/buero/frist", "frist", lambda u, c, f: buero.add_deadline(ctx, u, c, f), "deadline")
    akte_post("/buero/frist/erledigt", "frist_erledigt", lambda u, c, f: buero.complete_deadline(ctx, u, c, f), "deadline_done")

    def _assign(user, case_id, form):
        if form.get("case_role") not in CASE_ROLES:
            raise buero.BueroError("Bitte eine Rolle auswählen.")
        buero._mandate_row(ctx, case_id)
        try:
            ctx.team_governance_359.assign_case_role(identity=user, case_id=case_id, username=form.get("username", ""),
                                                     case_role=form["case_role"], notes="Büro: Zuordnung zum Auftrag")
        except (ValueError, KeyError) as exc:
            raise buero.BueroError(str(exc).strip("'")) from None

    def _revoke(user, case_id, form):
        try:
            ctx.team_governance_359.revoke_case_role(identity=user, case_id=case_id, username=form.get("username", ""),
                                                     case_role=form.get("case_role", ""), reason=form.get("reason", ""))
        except (ValueError, KeyError) as exc:
            raise buero.BueroError(str(exc).strip("'")) from None

    akte_post("/buero/auftrag/team", "team", _assign, "member")
    akte_post("/buero/auftrag/team/entziehen", "team", _revoke, "member_removed")

    # ------------------------------------------------ statements
    @app.get("/buero/leistungsnachweis.csv")
    def statement_csv(request: Request, case_id: str = ""):
        user = _user(app, request)
        try:
            sheet = buero.statement(ctx, user, case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except buero.BueroError as exc:
            raise HTTPException(404, str(exc)) from None
        row = sheet["mandate"]
        rows = [["Aktenzeichen", "Typ", "Datum", "Art/Tätigkeit", "Beschreibung", "Minuten", "Kilometer", "Betrag netto (EUR)",
                 "abrechenbar", "erfasst von"]]
        for e in sheet["times"]:
            rows.append([row["aktenzeichen"], "Zeit", e["work_date"], buero.ACTIVITIES.get(e["activity"], e["activity"]), e["note"],
                         e["minutes"], "", "", "ja" if e["billable"] else "nein", e["username"]])
        for e in sheet["expenses"]:
            rows.append([row["aktenzeichen"], "Auslage", e["spent_on"], buero.EXPENSE_KINDS.get(e["kind"], e["kind"]), e["note"], "",
                         e["km"] or "", f'{e["amount_cents"] / 100:.2f}'.replace(".", ","), "ja" if e["billable"] else "nein", e["username"]])
        return _csv(rows, f'Leistungsnachweis_{row["aktenzeichen"]}.csv')

    @app.get("/buero/leistungsnachweis.pdf")
    def statement_pdf_route(request: Request, case_id: str = ""):
        user = _user(app, request)
        try:
            sheet = buero.statement(ctx, user, case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except buero.BueroError as exc:
            raise HTTPException(404, str(exc)) from None
        ctx.audit.log("buero_statement_exported", "buero_mandate", case_id, case_id, {"format": "pdf"})
        return Response(statement_pdf(sheet), media_type="application/pdf", headers={
            "Content-Disposition": f'attachment; filename="Leistungsnachweis_{sheet["mandate"]["aktenzeichen"]}.pdf"',
            "Cache-Control": "no-store"})

    @app.get("/buero/zeiten.csv")
    def month_csv(request: Request, monat: str = ""):
        user = _user(app, request)
        if not buero.may_use_clients(user):
            raise HTTPException(403, "Die Zeitenliste ist der Büroleitung und Ermittlern vorbehalten.")
        try:
            entries = buero.time_export(ctx, user, monat)
        except buero.BueroError as exc:
            raise HTTPException(422, str(exc)) from None
        rows = [["Datum", "Aktenzeichen", "Mandant", "Auftrag", "Tätigkeit", "Beschreibung", "Minuten", "Stunden", "abrechenbar", "erfasst von"]]
        for e in entries:
            rows.append([e["work_date"], e["aktenzeichen"], e["client_name"], e["title"], buero.ACTIVITIES.get(e["activity"], e["activity"]),
                         e["note"], e["minutes"], f'{e["minutes"] / 60:.2f}'.replace(".", ","), "ja" if e["billable"] else "nein", e["username"]])
        return _csv(rows, f"Zeiten_{monat}.csv")

    # ------------------------------------------------ clients
    def clients_body(request, user, values=None, error="") -> str:
        rows = buero.clients(ctx, user)
        body = _status_line(request) + _error(error)
        if rows:
            table = '<table><thead><tr><th>Name</th><th>Art</th><th>Ansprechpartner</th><th>Aufträge</th></tr></thead><tbody>'
            for c in rows:
                table += (f'<tr><td><a href="{_href("/buero/mandant", client_id=c["client_id"])}">{escape(c["name"])}</a></td>'
                          f'<td>{escape(buero.CLIENT_KINDS.get(c["kind"], c["kind"]))}</td><td>{escape(c["contact_person"])}</td>'
                          f'<td class="num">{c["mandates"]}</td></tr>')
            body += _stack_tables(table + '</tbody></table>')
        else:
            body += '<p>Noch keine Mandanten. Sie entstehen auch direkt beim Anlegen eines Auftrags.</p>'
        body += ('<details class="card"' + (" open" if error or not rows else "") + '><summary>Neuen Mandanten erfassen</summary>'
                 f'<form method="post" action="/buero/mandant"><input type="hidden" name="csrf" value="{_csrf(request)}">'
                 + _client_fields(values or {}) + _area("Notizen", "notes", (values or {}).get("notes", ""), rows=2, maxlength=2000)
                 + '<button class="primary" type="submit">Mandant speichern</button></form></details>')
        return body

    @app.get("/buero/mandanten", response_class=HTMLResponse)
    def clients_page(request: Request):
        user = _user(app, request)
        try:
            return render("Mandanten", clients_body(request, user))
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None

    def client_body(request, user, client_id, values=None, error="") -> str:
        c = buero.client(ctx, user, client_id)
        mine = [m for m in buero.mandates(ctx, user) if m["client_id"] == client_id]
        lis = "".join(f'<li><a href="{_href("/buero/auftrag", case_id=m["case_id"])}">{escape(m["aktenzeichen"])}</a> '
                      f'{escape(m["title"])} {_pill(m["status"])}</li>' for m in mine)
        return (_status_line(request) + _error(error) + f'<section class="card"><h2>Aufträge</h2>'
                + (f'<ul>{lis}</ul>' if lis else '<p>Keine sichtbaren Aufträge.</p>') + '</section>'
                + f'<form method="post" action="/buero/mandant"><input type="hidden" name="csrf" value="{_csrf(request)}">'
                + _hidden(client_id=client_id) + _client_fields(values or c)
                + _area("Notizen", "notes", (values or c).get("notes", ""), rows=3, maxlength=2000)
                + '<button class="primary" type="submit">Änderungen speichern</button></form>')

    @app.get("/buero/mandant", response_class=HTMLResponse)
    def client_page(request: Request, client_id: str = ""):
        user = _user(app, request)
        try:
            name = buero.client(ctx, user, client_id)["name"]
            return render("Mandant: " + name, client_body(request, user, client_id))
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except buero.BueroError as exc:
            raise HTTPException(404, str(exc)) from None

    @app.post("/buero/mandant")
    async def client_save(request: Request):
        form = await _form(request)
        user = _user(app, request)
        verify_post(app, request, user, form.get("csrf", ""))
        client_id = form.get("client_id", "")
        try:
            saved = buero.save_client(ctx, user, form, client_id)
        except buero.BueroError as exc:
            if client_id:
                return render("Mandant", client_body(request, user, client_id, form, str(exc)), 422)
            return render("Mandanten", clients_body(request, user, form, str(exc)), 422)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        return RedirectResponse("/buero/mandant?" + urlencode({"client_id": saved["client_id"], "done": "client"}), status_code=303)

    # ------------------------------------------------ settings
    @app.get("/buero/einstellungen", response_class=HTMLResponse)
    def settings_page(request: Request):
        user = _user(app, request)
        if not buero._is_admin(user):
            raise HTTPException(403, "Nur die Büroleitung (Administration) ändert die Büroeinstellungen.")
        return render("Büroeinstellungen", _settings_body(request, buero.settings(ctx)))

    @app.post("/buero/einstellungen")
    async def settings_save(request: Request):
        form = await _form(request)
        user = _user(app, request)
        verify_post(app, request, user, form.get("csrf", ""))
        try:
            buero.save_settings(ctx, user, form)
        except buero.BueroError as exc:
            return render("Büroeinstellungen", _settings_body(request, buero.settings(ctx), str(exc), form), 422)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        return RedirectResponse("/buero/einstellungen?done=settings", status_code=303)

    # ------------------------------------------------ final deletion after the retention period
    def deletion_body(request, user, case_id, error="", values=None) -> str:
        info = deletion.plan(ctx, user, case_id)
        row = info["mandate"]
        v = values or {}
        kept = "".join(f"<li>{escape(deletion.residual_label(k))}: {n}</li>" for k, n in sorted(info["kept"].items()))
        biggest = sorted(info["rows"].items(), key=lambda kv: -kv[1])[:8]
        return (_error(error)
                + f'<p>{_pill(row["status"])} <strong>{escape(row["aktenzeichen"])}</strong> · aufbewahren bis '
                f'{_when(row["retention_until"]) or "–"}' + ('' if info["due"] else ' · <span class="overdue">Frist läuft noch</span>') + '</p>'
                + '<section class="card"><h2>Was gelöscht wird</h2>'
                f'<p>{info["row_total"]} Datensätze in {len(info["rows"])} Bereichen, {info["documents"]} Dokumente, '
                f'{info["files"]} Dateien – darunter Zeiten, Auslagen, Prüfung und Verlauf der Auftragsakte.</p>'
                + '<details><summary>Größte Bereiche</summary><ul>'
                + "".join(f"<li>{escape(name)}: {n}</li>" for name, n in biggest) + '</ul></details>'
                + ('<p>Bleibt erhalten (fallübergreifend verkettete Protokolle, ein Entfernen bräche deren Prüfkette):</p>'
                   f'<ul>{kept}</ul>' if kept else '')
                + ('<p>Diese Dateien erwähnen den Fall im Inhalt, gehören aber nicht eindeutig zu ihm. Sie werden <strong>nicht</strong> '
                   'gelöscht – bitte selbst prüfen:</p><ul>' + "".join(f"<li><code>{escape(m)}</code></li>" for m in info["mentions"][:30])
                   + '</ul>' if info["mentions"] else '')
                + '<p class="muted">Der Mandant selbst bleibt in der Mandantenliste. Frühere Sicherungen enthalten den Fall, '
                  'bis sie turnusgemäß ersetzt werden. Für die Buchhaltung vorher den '
                  f'<a href="{_href("/buero/leistungsnachweis.pdf", case_id=case_id)}">Leistungsnachweis</a> ablegen.</p></section>'
                + (_error(deletion._unreadable_message(info["unreadable"])) if info["unreadable"] else
                   f'<form method="post" action="/buero/loeschen" class="card"><h2>Endgültig löschen</h2>'
                f'<input type="hidden" name="csrf" value="{_csrf(request)}">' + _hidden(case_id=case_id)
                + ('' if info["due"] else _area(f"Begründung für die Löschung vor Fristablauf (z. B. Löschverlangen), mindestens "
                                                f"{buero.MIN_REASON} Zeichen", "reason", v.get("reason", ""), required=True, rows=2, maxlength=600))
                + _field(f'Zur Bestätigung das Aktenzeichen abtippen: {row["aktenzeichen"]}', "confirm", "", required=True,
                         attrs='autocomplete="off" maxlength="40"')
                + _check("Ich habe geprüft, dass keine gesetzliche Aufbewahrungspflicht und kein laufendes Verfahren entgegensteht.",
                         "checked", False)
                + '<button class="primary" type="submit">Fallakte endgültig löschen</button></form>'))

    @app.get("/buero/loeschen", response_class=HTMLResponse)
    def deletion_page(request: Request, case_id: str = ""):
        user = _user(app, request)
        try:
            return render("Fallakte löschen", deletion_body(request, user, case_id), case_id=case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except buero.BueroError as exc:
            raise HTTPException(409, str(exc)) from None

    @app.post("/buero/loeschen")
    async def deletion_post(request: Request):
        form = await _form(request)
        user = _user(app, request)
        verify_post(app, request, user, form.get("csrf", ""))
        case_id = form.get("case_id", "")
        try:
            deletion.delete_case(ctx, user, case_id, form)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except deletion.IncompleteDeletion as exc:
            return deletion_log_page(request, user, str(exc), 409)
        except buero.BueroError as exc:
            try:
                return render("Fallakte löschen", deletion_body(request, user, case_id, str(exc), form), 422, case_id)
            except buero.BueroError:
                raise HTTPException(409, str(exc)) from None
        return RedirectResponse("/buero/loeschprotokoll?done=deleted", status_code=303)

    def deletion_log_page(request, user, error="", status=200):
        rows = deletion.deletions(ctx, user)
        body = _status_line(request) + _error(error)
        if not rows:
            return render("Löschprotokoll", body + "<p>Noch keine Löschungen.</p>", status)
        csrf = f'<input type="hidden" name="csrf" value="{_csrf(request)}">'
        table = ('<table><thead><tr><th>Aktenzeichen</th><th>Stand</th><th>Gelöscht am</th><th>Von</th><th>Frist</th>'
                 '<th>Umfang</th><th>Restfundstellen</th></tr></thead><tbody>')
        for r in rows:
            rest = "; ".join(f"{escape(deletion.residual_label(k))}: {n}" for k, n in sorted(r["residual"].items())) or "keine"
            state = escape(deletion.STATUS_LABELS.get(r["status"], r["status"]))
            if r["status"] != "abgeschlossen":
                state = (f'<span class="overdue">{state}</span>' + (f'<br><small>{escape(r["error"])}</small>' if r["error"] else "")
                         + '<form method="post" action="/buero/loeschen/fortsetzen">' + _hidden(deletion_id=r["deletion_id"]) + csrf
                         + '<button class="primary" type="submit">Löschung fortsetzen</button></form>')
            table += (f'<tr><td>{escape(r["aktenzeichen"])}</td><td>{state}</td><td class="date">{_when(r["deleted_at"])}</td>'
                      f'<td>{escape(r["deleted_by"])}</td><td class="date">{_when(r["retention_until"])}'
                      + (f'<br><small>vorzeitig: {escape(r["early_reason"])}</small>' if r["early_reason"] else "") + '</td>'
                      f'<td>{r["rows_deleted"]} Datensätze, {r["files_deleted"]} Dateien</td><td>{rest}</td></tr>')
        return render("Löschprotokoll", body + '<p class="muted">Das Protokoll enthält keine Inhalte der gelöschten Akte, nur '
                      'Aktenzeichen, Daten und Umfang. Restfundstellen sind Einträge in fallübergreifend verketteten '
                      'Protokollen (nur Kennungen) und Dateien, die den Fall noch erwähnen.</p>'
                      + _stack_tables(table + '</tbody></table>'), status)

    @app.get("/buero/loeschprotokoll", response_class=HTMLResponse)
    def deletion_log(request: Request):
        user = _user(app, request)
        try:
            return deletion_log_page(request, user)
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None

    @app.post("/buero/loeschen/fortsetzen")
    async def deletion_resume(request: Request):
        form = await _form(request)
        user = _user(app, request)
        verify_post(app, request, user, form.get("csrf", ""))
        try:
            deletion.resume(ctx, user, form.get("deletion_id", ""))
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except buero.BueroError as exc:
            return deletion_log_page(request, user, str(exc), 409)
        return RedirectResponse("/buero/loeschprotokoll?done=deleted", status_code=303)

    # ------------------------------------------------ team (office management)
    def team_body(request, error="", values=None) -> str:
        v = values or {}
        rows = ctx.team_identity_359.list_users()
        table = ('<table><thead><tr><th>Name</th><th>Anmeldename</th><th>Rolle im Büro</th><th>Aufträge</th><th>Konto</th></tr></thead><tbody>')
        me = _user(app, request)["username"]
        csrf = f'<input type="hidden" name="csrf" value="{_csrf(request)}">'
        memberships = ctx.team_identity_359.list_case_memberships()
        for u in rows:
            count = len({m["case_id"] for m in memberships if m["username"] == u["username"] and m["active"]})
            table += (f'<tr><td>{escape(u["display_name"])}</td><td>{escape(u["username"])}'
                      + ('' if u["active"] else ' (deaktiviert)') + f'</td><td>{escape(GLOBAL_ROLES.get(u["global_role"], u["global_role"]).split(" – ")[0])}</td>'
                      f'<td class="num">{"alle" if u["global_role"] == "system_administrator" else count}</td>'
                      f'<td>{account_actions(u, me, csrf)}</td></tr>')
        return (_status_line(request) + _error(error) + _stack_tables(table + '</tbody></table>')
                + f'<form method="post" action="/buero/team/benutzer" class="card"><h2>Benutzer anlegen</h2>'
                f'<input type="hidden" name="csrf" value="{_csrf(request)}"><div class="two">'
                + _field("Anmeldename (3–32 Zeichen: a–z, 0–9, Punkt, Bindestrich)", "username", v.get("username", ""), required=True,
                         attrs='maxlength="32" autocomplete="off"')
                + _field("Anzeigename", "display_name", v.get("display_name", ""), required=True, attrs='maxlength="120"')
                + '</div>' + _select("Rolle im Büro", "global_role", GLOBAL_ROLES, v.get("global_role", "investigator"))
                + _field("Startpasswort (mindestens 12 Zeichen, nicht der Name)", "password", "", type="password", required=True,
                         attrs='autocomplete="new-password" maxlength="256"')
                + '<p class="muted">Nach dem Anlegen den Benutzer in der Auftragsakte dem jeweiligen Auftrag zuordnen. '
                  'Die Büroleitung sieht alle Aufträge.</p><button class="primary" type="submit">Benutzer anlegen</button></form>')

    def account_actions(u, me, csrf) -> str:
        if u["username"] == me:
            return '<a href="/buero/konto">Mein Konto</a>'
        toggle = ('<form method="post" action="/buero/team/sperren">' + _hidden(username=u["username"], active="0" if u["active"] else "1")
                  + csrf + f'<button type="submit">{"Sperren" if u["active"] else "Entsperren"}</button></form>')
        reset = ('<details><summary>Passwort zurücksetzen</summary><form method="post" action="/buero/team/passwort">'
                 + _hidden(username=u["username"]) + csrf
                 + _field("Neues Startpasswort", "password", "", type="password", required=True, attrs='autocomplete="new-password" maxlength="256"')
                 + '<button type="submit">Zurücksetzen</button></form></details>')
        return toggle + reset

    def team_action(path, action, done):
        @app.post(path)
        async def handler(request: Request):
            form = await _form(request)
            user = _user(app, request)
            verify_post(app, request, user, form.get("csrf", ""))
            try:
                action(ctx, user, form)
            except PermissionError as exc:
                raise HTTPException(403, str(exc)) from None
            except buero.BueroError as exc:
                return render("Team", team_body(request, str(exc)), 422)
            return RedirectResponse("/buero/team?done=" + (done(form) if callable(done) else done), status_code=303)
        handler.__name__ = "team_" + path.rsplit("/", 1)[-1]

    team_action("/buero/team/passwort", accounts.reset_password, "reset")
    team_action("/buero/team/sperren", accounts.set_active, lambda f: "unlocked" if f.get("active") == "1" else "locked")

    # ------------------------------------------------ own account
    def account_body(request, user, error="") -> str:
        forced = accounts.must_change(ctx, user)
        return (_status_line(request) + _error(error)
                + ('<p class="warn">Dein Passwort wurde von der Büroleitung gesetzt. Bitte jetzt ein eigenes wählen, '
                   'bevor du weiterarbeitest.</p>' if forced else '')
                + f'<p>{escape(user["display_name"])} ({escape(user["username"])}) · '
                f'{escape(GLOBAL_ROLES.get(user["global_role"], user["global_role"]).split(" – ")[0])}</p>'
                + f'<form method="post" action="/buero/konto" class="card"><h2>Passwort ändern</h2>'
                f'<input type="hidden" name="csrf" value="{_csrf(request)}">'
                + _field("Bisheriges Passwort", "current", "", type="password", required=True, attrs='autocomplete="current-password" maxlength="256"')
                + _field("Neues Passwort (mindestens 12 Zeichen, nicht der Name)", "new", "", type="password", required=True,
                         attrs='autocomplete="new-password" maxlength="256"')
                + _field("Neues Passwort wiederholen", "repeat", "", type="password", required=True,
                         attrs='autocomplete="new-password" maxlength="256"')
                + '<button class="primary" type="submit">Passwort ändern</button></form>')

    @app.get("/buero/konto", response_class=HTMLResponse)
    def account_page(request: Request):
        user = _user(app, request)
        return render("Mein Konto", account_body(request, user))

    @app.post("/buero/konto")
    async def account_save(request: Request):
        form = await _form(request)
        user = _user(app, request)
        verify_post(app, request, user, form.get("csrf", ""))
        try:
            accounts.change_own_password(ctx, user, form)
        except buero.BueroError as exc:
            return render("Mein Konto", account_body(request, user, str(exc)), 422)
        return RedirectResponse("/buero/konto?done=password", status_code=303)

    # A password set by the office management must be replaced before the account may do
    # anything else: every request with a session is checked (pages, forms and API calls).
    # Only the password change itself, login/logout and static files stay reachable.
    exempt_exact = {"/buero/konto", "/security/logout", "/security/login", "/security/start", "/security/bootstrap",
                    "/health", "/favicon.ico"}
    exempt_prefix = ("/assets/", "/static/")

    @app.middleware("http")
    async def require_own_password(request: Request, call_next):
        path = request.url.path
        if request.cookies.get(COOKIE) and path not in exempt_exact and not path.startswith(exempt_prefix):
            from starlette.concurrency import run_in_threadpool
            current = await run_in_threadpool(lambda: ctx.team_identity_359.validate_session(
                request.cookies.get(COOKIE, ""), client_fingerprint=_fingerprint(request), touch=False))
            if accounts.must_change(ctx, current):
                if "text/html" in request.headers.get("accept", ""):
                    return RedirectResponse("/buero/konto", status_code=303)
                return JSONResponse({"detail": "Bitte zuerst unter „Mein Konto“ ein eigenes Passwort festlegen."},
                                    status_code=403)
        return await call_next(request)

    @app.get("/buero/team", response_class=HTMLResponse)
    def team_page(request: Request):
        user = _user(app, request)
        if not buero._is_admin(user):
            raise HTTPException(403, "Benutzer verwaltet die Büroleitung (Administration).")
        return render("Team", team_body(request))

    @app.post("/buero/team/benutzer")
    async def team_create(request: Request):
        form = await _form(request)
        user = _user(app, request)
        verify_post(app, request, user, form.get("csrf", ""))
        if form.get("global_role") not in GLOBAL_ROLES:
            return render("Team", team_body(request, "Bitte eine Rolle auswählen.", form), 422)
        try:
            ctx.team_governance_359.create_user(identity=user, username=form.get("username", ""),
                                               display_name=form.get("display_name", ""), global_role=form["global_role"],
                                               password=form.get("password", ""))
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from None
        except ValueError as exc:
            return render("Team", team_body(request, str(exc), {**form, "password": ""}), 422)
        except Exception as exc:  # duplicate user name (database constraint)
            if "UNIQUE" in str(exc).upper():
                return render("Team", team_body(request, "Diesen Anmeldenamen gibt es schon.", {**form, "password": ""}), 422)
            raise
        return RedirectResponse("/buero/team?done=user", status_code=303)
