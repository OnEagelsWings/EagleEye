"""Office pages over HTTP: forms keep input, CSRF, research gate, exports, navigation."""
import csv
import io

import pytest

from eagleeye.application.buero import service as buero
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.app492 import create_workspace_app492
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import csrf_session

ws = pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
PW = "Build471!Password_88"


def _new(client, **extra):
    data = {"csrf": client.cookies.get(CSRF_COOKIE), "client_id": "neu", "client_kind": "unternehmen",
            "client_name": "Muster AG", "client_contact_person": "Frau Beispiel", "client_address": "Hauptstr. 1\n12345 Musterstadt",
            "title": "Lieferantenprüfung Beispiel GmbH", "kind": "due_diligence",
            "purpose": "Prüfen, ob Geschäftsführung und Beteiligungen der Beispiel GmbH Risiken bergen.",
            "legal_basis_key": "berechtigtes_interesse", "legal_basis_note": "Vertragsanbahnung",
            "received_on": "2026-11-10", "due_on": "2026-11-30", "fee_model": "stunden", "hourly_rate": "90",
            "budget": "2.000", "recipient": "Muster AG, Einkauf", "recipient_level": "mandant"}
    data.update(extra)
    return client.post("/buero/auftrag/neu", data=data, follow_redirects=False)


def _screen(client, case_id, version, **extra):
    data = {"csrf": client.cookies.get(CSRF_COOKIE), "case_id": case_id, "version": str(version), "q_beziehung": "nein",
            "q_schutz": "nein", "q_schutzanordnung": "nein", "q_anschrift": "nein", "q_identitaet": "ja",
            "c_ausweis": "on", "c_zweck": "on", "decision": "annehmen", "reason": ""}
    data.update(extra)
    return client.post("/buero/auftrag/pruefung", data=data, follow_redirects=False)


@ws
def test_office_flow_over_http(workspace):
    app, client, user, legacy_case, *_ = workspace
    ctx = app.state.context
    csrf_session(workspace)
    overview = client.get("/buero")
    assert overview.status_code == 200 and "offene Aufträge" in overview.text
    assert "Briefkopf und Stundensatz festlegen" in overview.text, "admin is reminded to set up the letterhead"
    assert "Fälle ohne Auftragsdaten" in overview.text and "Synthetic AI case" in overview.text

    form = client.get("/buero/auftrag/neu").text
    for label in ("Titel des Auftrags", "Auftragsart", "Rechtsgrundlage", "Abgabefrist (optional)", "Stundensatz netto in €",
                  "Ergebnisempfänger", "Empfängerstufe des Berichts"):
        assert label in form, label

    failed = _new(client, title="", purpose="Kurz")
    assert failed.status_code == 422 and "Bitte prüfen" in failed.text
    assert 'value="Muster AG"' in failed.text, "typed input survives a failed submit"
    missing_csrf = _new(client, csrf="0" * 64)
    assert missing_csrf.status_code == 403

    created = _new(client)
    assert created.status_code == 303 and "done=created" in created.headers["location"]
    case_id = created.headers["location"].split("case_id=")[1].split("&")[0]
    row = buero.mandate(ctx, user, case_id)
    assert row["aktenzeichen"] == "2026-0001" and row["budget_cents"] == 200000

    akte = client.get("/buero/auftrag", params={"case_id": case_id, "done": "created"}).text
    assert "Auftrag angelegt" in akte and "Auftragsprüfung" in akte and 'name="q_schutzanordnung"' in akte
    assert 'name="q_vermisst_freiwillig"' not in akte, "missing-person question only for missing-person mandates"
    assert "Zur Recherche" not in akte, "research starts after acceptance"

    # The research gate: no network contact before the screening.
    blocked = client.post("/workbench/intel/web", data={"csrf": client.cookies.get(CSRF_COOKIE), "case_id": case_id,
                                                        "url": "https://news.example/x", "opsec": "yes"})
    assert blocked.status_code == 409 and "Auftragsprüfung ist noch nicht abgeschlossen" in blocked.text
    flow = client.get("/workbench", params={"case_id": case_id}).text
    assert "Anfrage – Prüfung offen" in flow and "Zur Auftragsakte" in flow
    legacy_flow = client.get("/workbench", params={"case_id": legacy_case}).text
    assert "Mandant, Aktenzeichen und Auftragsprüfung ergänzen" in legacy_flow

    short = _screen(client, case_id, row["version"], q_beziehung="ja")
    assert short.status_code == 422 and "mindestens 30" in short.text and 'value="ja" required checked' in short.text
    stale = _screen(client, case_id, row["version"] + 5)
    assert stale.status_code == 409 and "inzwischen geändert" in stale.text
    assert _screen(client, case_id, row["version"]).status_code == 303
    akte = client.get("/buero/auftrag", params={"case_id": case_id}).text
    assert "Auftragsprüfung:</strong> angenommen" in akte and "Zur Recherche" in akte

    token = client.cookies.get(CSRF_COOKIE)
    assert client.post("/buero/zeit", data={"csrf": token, "case_id": case_id, "work_date": "2026-11-12", "duration": "2:15",
                                            "activity": "recherche", "note": "=HYPERLINK(\"x\")", "billable_box": "on"},
                       follow_redirects=False).status_code == 303
    bad_time = client.post("/buero/zeit", data={"csrf": token, "case_id": case_id, "work_date": "2026-11-12",
                                                "duration": "viel", "activity": "recherche", "note": "Notiz bleibt"})
    assert bad_time.status_code == 422 and "Dauer" in bad_time.text and 'value="Notiz bleibt"' in bad_time.text
    assert client.post("/buero/auslage", data={"csrf": token, "case_id": case_id, "spent_on": "2026-11-12", "kind": "km",
                                               "km": "80", "billable_box": "on"}, follow_redirects=False).status_code == 303
    assert client.post("/buero/auslage", data={"csrf": token, "case_id": case_id, "spent_on": "2026-11-12", "kind": "gebuehr",
                                               "amount": "4,50", "note": "Registerauszug"},
                       follow_redirects=False).status_code == 303
    assert client.post("/buero/frist", data={"csrf": token, "case_id": case_id, "due_on": "2026-11-20",
                                             "title": "Zwischenbericht an Mandanten"}, follow_redirects=False).status_code == 303
    akte = client.get("/buero/auftrag", params={"case_id": case_id}).text
    assert "2:15 Std." in akte and "80 km" in akte and "Zwischenbericht an Mandanten" in akte
    assert "(nicht abrechenbar)" in akte, "the fee without the checkbox is booked as not billable"

    sheet = client.get("/buero/leistungsnachweis.csv", params={"case_id": case_id})
    assert sheet.status_code == 200 and sheet.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(sheet.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0][0] == "Aktenzeichen" and rows[1][4] == "'=HYPERLINK(\"x\")", "formula cells are neutralised"
    pdf = client.get("/buero/leistungsnachweis.pdf", params={"case_id": case_id})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["content-type"] == "application/pdf"
    month = client.get("/buero/zeiten.csv", params={"monat": "2026-11"})
    assert month.status_code == 200 and "2026-0001" in month.content.decode("utf-8-sig")
    assert client.get("/buero/zeiten.csv", params={"monat": "11/2026"}).status_code == 422

    current = buero.mandate(ctx, user, case_id)
    assert client.post("/buero/auftrag/status", data={"csrf": token, "case_id": case_id, "version": current["version"],
                                                      "status": "in_arbeit"}, follow_redirects=False).status_code == 303
    overview = client.get("/buero").text
    assert "2026-0001" in overview and "Muster AG" in overview and "In Bearbeitung" in overview

    # Clients and settings pages.
    clients_page = client.get("/buero/mandanten").text
    assert "Muster AG" in clients_page
    settings = client.post("/buero/einstellungen", data={"csrf": token, "firma": "Detektei Beispiel", "anschrift": "Weg 2",
                           "kontakt": "", "bericht_fusszeile": "Vertraulich", "stundensatz": "85", "km_satz": "0,35",
                           "ust_modus": "kleinunternehmer", "ust_satz": "19", "az_praefix": "DB", "aufbewahrung_monate": "24"},
                           follow_redirects=False)
    assert settings.status_code == 303
    assert buero.settings(ctx)["km_satz_cent"] == "35"
    wrong = client.post("/buero/einstellungen", data={"csrf": token, "firma": "Detektei Beispiel", "stundensatz": "85",
                        "km_satz": "0,35", "ust_modus": "regel", "ust_satz": "19", "az_praefix": "D B",
                        "aufbewahrung_monate": "24"})
    assert wrong.status_code == 422 and "Präfix" in wrong.text


@ws
def test_navigation_home_and_permissions(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    csrf_session(workspace)
    flow = client.get("/workbench", params={"case_id": case_id}).text
    assert '<a href="/buero">Übersicht</a>' in flow and "Neuer Auftrag" in flow and 'aria-current="page"' in flow
    home = client.get("/", params={"case_id": case_id}).text
    assert "Büro – alle Aufträge" in home

    ctx.team_identity_359.create_user(identity=user, username="neuling", display_name="Neu", global_role="investigator", password=PW)
    csrf_session(workspace, "neuling", PW)
    assert client.get("/", follow_redirects=False).headers["location"] == "/buero"
    assert client.get("/workbench", follow_redirects=False).headers["location"] == "/buero"
    assert client.get("/buero/einstellungen").status_code == 403
    assert client.get("/buero/auftrag", params={"case_id": case_id}).status_code == 403

    csrf_session(workspace)
    row = buero.create_mandate(ctx, user, {"title": "Fall für Leserechte", "purpose": "Prüfung", "kind": "online",
                                           "legal_basis_key": "einwilligung", "client_id": "neu", "client_kind": "privat",
                                           "client_name": "Herr Beispiel"})
    ctx.team_identity_359.create_user(identity=user, username="leser", display_name="Leser", global_role="read_only", password=PW)
    ctx.team_governance_359.assign_case_role(identity=user, case_id=row["case_id"], username="leser", case_role="read_only")
    csrf_session(workspace, "leser", PW)
    akte = client.get("/buero/auftrag", params={"case_id": row["case_id"]})
    assert akte.status_code == 200 and "Zeit buchen" not in akte.text and "Die Fallleitung muss" in akte.text
    assert "Mandant: Herr Beispiel" in akte.text and "/buero/mandant?" not in akte.text
    denied = client.post("/buero/zeit", data={"csrf": client.cookies.get(CSRF_COOKIE), "case_id": row["case_id"],
                                              "duration": "1", "activity": "recherche"})
    assert denied.status_code == 403
    assert client.get("/buero/mandanten").status_code == 403


@ws
def test_team_page_and_mandate_assignment(workspace):
    app, client, user, legacy_case, *_ = workspace
    ctx = app.state.context
    csrf_session(workspace)
    token = client.cookies.get(CSRF_COOKIE)
    assert "Benutzer anlegen" in client.get("/buero/team").text
    new_user = {"csrf": token, "username": "anna.ermittlerin", "display_name": "Anna Beispiel", "global_role": "investigator",
                "password": "Herbstlaub!Fenster_2026"}
    weak = client.post("/buero/team/benutzer", data={**new_user, "password": "kurz"})
    assert weak.status_code == 422 and "mindestens" in weak.text and 'value="anna.ermittlerin"' in weak.text
    assert client.post("/buero/team/benutzer", data=new_user, follow_redirects=False).status_code == 303
    duplicate = client.post("/buero/team/benutzer", data=new_user)
    assert duplicate.status_code == 422
    assert "Anna Beispiel" in client.get("/buero/team").text

    created = _new(client)
    case_id = created.headers["location"].split("case_id=")[1].split("&")[0]
    other = _new(client, title="Anderer Auftrag")
    other_id = other.headers["location"].split("case_id=")[1].split("&")[0]
    akte = client.get("/buero/auftrag", params={"case_id": case_id}).text
    assert "Team dieses Auftrags" in akte and 'name="username"' in akte
    assigned = client.post("/buero/auftrag/team", data={"csrf": token, "case_id": case_id, "username": "anna.ermittlerin",
                                                        "case_role": "investigator"}, follow_redirects=False)
    assert assigned.status_code == 303

    csrf_session(workspace, "anna.ermittlerin", "Herbstlaub!Fenster_2026")
    overview = client.get("/buero").text
    assert "Lieferantenprüfung Beispiel GmbH" in overview and "Anderer Auftrag" not in overview
    assert client.get("/buero/auftrag", params={"case_id": other_id}).status_code == 403
    assert client.get("/buero/team").status_code == 403

    csrf_session(workspace)
    token = client.cookies.get(CSRF_COOKIE)
    short = client.post("/buero/auftrag/team/entziehen", data={"csrf": token, "case_id": case_id, "username": "anna.ermittlerin",
                                                                "case_role": "investigator", "reason": "kurz"})
    assert short.status_code == 422
    assert client.post("/buero/auftrag/team/entziehen", data={"csrf": token, "case_id": case_id, "username": "anna.ermittlerin",
                                                               "case_role": "investigator", "reason": "Auftrag an Kollegin übergeben"},
                       follow_redirects=False).status_code == 303
    csrf_session(workspace, "anna.ermittlerin", "Herbstlaub!Fenster_2026")
    assert "Lieferantenprüfung Beispiel GmbH" not in client.get("/buero").text


@ws
def test_accounts_change_reset_and_lock(workspace):
    import hashlib
    app, client, user, *_ = workspace
    ident = app.state.context.team_identity_359
    fp = hashlib.sha256(b"testclient||testclient").hexdigest()
    csrf_session(workspace)
    token = client.cookies.get(CSRF_COOKIE)
    client.post("/buero/team/benutzer", data={"csrf": token, "username": "anna", "display_name": "Anna Beispiel",
                                              "global_role": "investigator", "password": "Herbstlaub!Fenster_2026"})
    # Own password: current password required, both new entries equal, rules apply.
    csrf_session(workspace, "anna", "Herbstlaub!Fenster_2026")
    token = client.cookies.get(CSRF_COOKIE)
    assert client.post("/buero/konto", data={"csrf": token, "current": "falsch", "new": "Winterwald#Lampe_77",
                                             "repeat": "Winterwald#Lampe_77"}).status_code == 422
    assert "stimmen nicht" in client.post("/buero/konto", data={"csrf": token, "current": "Herbstlaub!Fenster_2026",
                                                                "new": "Winterwald#Lampe_77", "repeat": "anders"}).text
    assert client.post("/buero/konto", data={"csrf": token, "current": "Herbstlaub!Fenster_2026", "new": "Winterwald#Lampe_77",
                                             "repeat": "Winterwald#Lampe_77"}, follow_redirects=False).status_code == 303
    assert client.get("/buero").status_code == 200, "the session in use stays valid"
    assert ident.authenticate(username="anna", password="Herbstlaub!Fenster_2026", client_fingerprint=fp) is None
    assert ident.authenticate(username="anna", password="Winterwald#Lampe_77", client_fingerprint=fp) is not None

    # Reset by the office management: anna must choose a new password before anything else opens.
    anna_cookies = dict(client.cookies)
    csrf_session(workspace)
    token = client.cookies.get(CSRF_COOKIE)
    assert client.post("/buero/team/passwort", data={"csrf": token, "username": "anna", "password": "Sommerregen?Tasse_31"},
                       follow_redirects=False).status_code == 303
    assert client.post("/buero/team/passwort", data={"csrf": token, "username": "qa471", "password": "Sommerregen?Tasse_31"}).status_code == 422
    client.cookies.clear()
    client.cookies.update(anna_cookies)
    assert client.get("/buero").status_code == 401, "the reset ends anna's sessions"
    csrf_session(workspace, "anna", "Sommerregen?Tasse_31")
    forced = client.get("/buero", headers={"accept": "text/html"}, follow_redirects=False)
    assert forced.status_code == 303 and forced.headers["location"] == "/buero/konto"
    assert "bitte jetzt ein eigenes" in client.get("/buero/konto").text.lower()
    token = client.cookies.get(CSRF_COOKIE)
    client.post("/buero/konto", data={"csrf": token, "current": "Sommerregen?Tasse_31", "new": "Morgenrot&Kanne_58",
                                      "repeat": "Morgenrot&Kanne_58"})
    assert client.get("/buero", headers={"accept": "text/html"}, follow_redirects=False).status_code == 200

    # Locking ends access; one cannot lock oneself.
    csrf_session(workspace)
    token = client.cookies.get(CSRF_COOKIE)
    assert client.post("/buero/team/sperren", data={"csrf": token, "username": "anna", "active": "0"},
                       follow_redirects=False).headers["location"] == "/buero/team?done=locked"
    assert ident.authenticate(username="anna", password="Morgenrot&Kanne_58", client_fingerprint=fp) is None
    assert "(deaktiviert)" in client.get("/buero/team").text
    assert client.post("/buero/team/sperren", data={"csrf": token, "username": "qa471", "active": "0"}).status_code == 422
    client.post("/buero/team/sperren", data={"csrf": token, "username": "anna", "active": "1"})
    assert ident.authenticate(username="anna", password="Morgenrot&Kanne_58", client_fingerprint=fp) is not None
