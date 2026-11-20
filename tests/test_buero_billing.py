"""Billing per mandate: invoice numbers, no double billing, flat fee once, cancellation, payment, PDF, journal."""
from datetime import date, timedelta

import pymupdf
import pytest

from eagleeye.application.buero import billing, service as buero
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.app492 import create_workspace_app492
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import csrf_session

ws = pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
PW = "Herbstlaub!Fenster_2026"
TODAY = date.today()
CLEAN = {"q_beziehung": "nein", "q_schutz": "nein", "q_schutzanordnung": "nein", "q_anschrift": "nein",
         "q_identitaet": "ja", "decision": "annehmen"}
OFFICE = {**buero.DEFAULT_SETTINGS, "firma": "Detektei Adler & Partner", "anschrift": "Marktplatz 3\n70173 Stuttgart",
          "stundensatz": "80", "km_satz": "0,30", "ust_modus": "regel", "ust_satz": "19", "aufbewahrung_monate": "36"}
BILL = {"re_praefix": "RE", "steuernummer": "99/123/45678", "ust_idnr": "", "iban": "DE89 3704 0044 0532 0130 00",
        "bic": "COBADEFFXXX", "bank": "Commerzbank", "zahlungsziel_tage": "14"}


def _text(pdf: bytes) -> str:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        return " ".join(" ".join(page.get_text().split()) for page in doc)


def _mandate(ctx, user, case_id, **extra):
    form = {"kind": "due_diligence", "legal_basis_key": "berechtigtes_interesse", "client_id": "neu", "client_kind": "unternehmen",
            "client_name": "Muster Handels AG", "client_address": "Hafenstraße 1\n20457 Hamburg", "hourly_rate": "80", **extra}
    buero.attach_mandate(ctx, user, case_id, form)
    buero.screen(ctx, user, case_id, CLEAN)
    buero.set_status(ctx, user, case_id, {"status": "in_arbeit"})


def _book(ctx, user, case_id, day, duration="1:30", activity="recherche"):
    return buero.add_time(ctx, user, case_id, {"work_date": day.isoformat(), "duration": duration, "activity": activity,
                                               "note": "Register"}, today=TODAY)


def test_iban_check_digits():
    assert billing.iban_valid("DE89 3704 0044 0532 0130 00")
    assert not billing.iban_valid("DE89 3704 0044 0532 0130 01")
    assert not billing.iban_valid("kein iban")


@ws
def test_issue_marks_entries_and_numbers_run_without_gaps(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    _mandate(ctx, user, case_id)
    t1 = _book(ctx, user, case_id, TODAY - timedelta(days=3))
    _book(ctx, user, case_id, TODAY - timedelta(days=2), "2", "bericht")
    buero.add_expense(ctx, user, case_id, {"spent_on": (TODAY - timedelta(days=2)).isoformat(), "kind": "km", "km": "64"}, today=TODAY)
    buero.add_expense(ctx, user, case_id, {"spent_on": (TODAY - timedelta(days=2)).isoformat(), "kind": "gebuehr", "amount": "4,50"}, today=TODAY)
    form = {"issued_on": TODAY.isoformat(), "geprueft": "on"}
    with pytest.raises(buero.BueroError, match="Name des Büros"):
        billing.issue(ctx, user, case_id, form)
    buero.save_settings(ctx, user, OFFICE)
    with pytest.raises(buero.BueroError, match="Steuernummer oder USt-IdNr"):
        billing.issue(ctx, user, case_id, form)
    with pytest.raises(buero.BueroError, match="IBAN"):
        billing.save_settings(ctx, user, {**BILL, "iban": "DE00 1234"})
    billing.save_settings(ctx, user, BILL)
    with pytest.raises(buero.BueroError, match="geprüft"):
        billing.issue(ctx, user, case_id, {"issued_on": TODAY.isoformat()})

    first = billing.issue(ctx, user, case_id, form)
    assert first["number"] == f"RE-{TODAY.year}-0001" and first["due_on"] == (TODAY + timedelta(days=14)).isoformat()
    texts = [p["text"] for p in billing.invoice(ctx, user, first["invoice_id"])["positions"]]
    assert texts == ["Recherche", "Berichtserstellung", "Fahrtkilometer", "Register- oder Behördengebühr (Auslage)"]
    assert first["net_cents"] == 12000 + 16000 + 64 * 30 + 450 and first["vat_cents"] == round(first["net_cents"] * 0.19)
    with pytest.raises(buero.BueroError, match="nichts abzurechnen"):
        billing.issue(ctx, user, case_id, form)
    with pytest.raises(buero.BueroError, match="bereits abgerechnet"):
        buero.void_entry(ctx, user, case_id, {"entry_type": "time", "entry_id": t1["entry_id"], "reason": "falsch gebucht"})

    _book(ctx, user, case_id, TODAY, "0:45")
    second = billing.issue(ctx, user, case_id, form)
    assert second["number"] == f"RE-{TODAY.year}-0002" and second["net_cents"] == 6000

    storno = billing.cancel(ctx, user, case_id, {"invoice_id": first["invoice_id"], "reason": "Falscher Stundensatz"})
    assert storno["number"] == f"RE-{TODAY.year}-0003" and storno["gross_cents"] == -first["gross_cents"]
    assert storno["refers_to"] == first["number"]
    with pytest.raises(buero.BueroError, match="bereits storniert"):
        billing.cancel(ctx, user, case_id, {"invoice_id": first["invoice_id"], "reason": "nochmal storniert"})
    again = billing.issue(ctx, user, case_id, form)
    assert again["number"] == f"RE-{TODAY.year}-0004" and again["net_cents"] == first["net_cents"], "freed entries are billed again"

    with pytest.raises(buero.BueroError, match="Nur gestellte"):
        billing.mark_paid(ctx, user, case_id, {"invoice_id": first["invoice_id"]})
    with pytest.raises(buero.BueroError, match="vor dem Rechnungsdatum"):
        billing.mark_paid(ctx, user, case_id, {"invoice_id": second["invoice_id"], "paid_on": (TODAY - timedelta(days=5)).isoformat()})
    billing.mark_paid(ctx, user, case_id, {"invoice_id": second["invoice_id"]})
    states = {i["number"]: i["status"] for i in billing.invoices(ctx, user, case_id)}
    assert states == {first["number"]: "storniert", second["number"]: "bezahlt", storno["number"]: "storno", again["number"]: "gestellt"}
    journal = billing.journal(ctx, user, TODAY.year)
    assert [r["seq"] for r in journal] == [1, 2, 3, 4]
    assert sum(r["net_cents"] for r in journal) == second["net_cents"] + again["net_cents"]


@ws
def test_flat_fee_is_billed_once(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    buero.save_settings(ctx, user, OFFICE)
    billing.save_settings(ctx, user, BILL)
    _mandate(ctx, user, case_id, fee_model="pauschal", flat_fee="1.200")
    _book(ctx, user, case_id, TODAY)
    first = billing.issue(ctx, user, case_id, {"geprueft": "on"})
    assert [p["text"] for p in billing.invoice(ctx, user, first["invoice_id"])["positions"]] == ["Pauschalhonorar gemäß Auftrag"]
    assert first["net_cents"] == 120000, "time is covered by the flat fee"
    buero.add_expense(ctx, user, case_id, {"kind": "gebuehr", "amount": "10"}, today=TODAY)
    second = billing.issue(ctx, user, case_id, {"geprueft": "on"})
    assert second["net_cents"] == 1000 and not second["flat_fee"]


@ws
def test_invoice_pdf_carries_the_mandatory_content(workspace):
    from eagleeye.interfaces.web.buero_invoice import invoice_pdf
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    buero.save_settings(ctx, user, OFFICE)
    billing.save_settings(ctx, user, BILL)
    _mandate(ctx, user, case_id)
    _book(ctx, user, case_id, TODAY - timedelta(days=1))
    inv = billing.issue(ctx, user, case_id, {"geprueft": "on"})
    text = _text(invoice_pdf(billing.invoice(ctx, user, inv["invoice_id"])))
    for expected in ("Detektei Adler & Partner", "Marktplatz 3", "Muster Handels AG", "Hafenstraße 1", "Rechnungsnummer",
                     inv["number"], "Rechnungsdatum", "Leistungszeitraum", "Steuernummer", "99/123/45678", "Recherche",
                     "Umsatzsteuer 19 %", "Rechnungsbetrag", "DE89 3704 0044 0532 0130 00", "Anlage zu Rechnung", "Leistungsnachweis"):
        assert expected in text, expected
    storno = billing.cancel(ctx, user, case_id, {"invoice_id": inv["invoice_id"], "reason": "Mandant storniert Auftrag"})
    text = _text(invoice_pdf(billing.invoice(ctx, user, storno["invoice_id"])))
    assert "Stornorechnung zu Rechnung " + inv["number"] in text and "-" in text

    buero.save_settings(ctx, user, {**OFFICE, "ust_modus": "kleinunternehmer"})
    small = billing.issue(ctx, user, case_id, {"geprueft": "on"})
    text = _text(invoice_pdf(billing.invoice(ctx, user, small["invoice_id"])))
    assert "§ 19 UStG" in text and "Umsatzsteuer 19 %" not in text and small["vat_cents"] == 0


@ws
def test_billing_pages_rights_csv_and_overdue_reminder(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    csrf_session(workspace)
    buero.save_settings(ctx, user, OFFICE)
    _mandate(ctx, user, case_id)
    _book(ctx, user, case_id, TODAY)
    akte = client.get("/buero/auftrag", params={"case_id": case_id}).text
    assert "Abrechnung" in akte and "Steuernummer oder USt-IdNr." in akte and "Rechnung erstellen" not in akte
    token = client.cookies.get(CSRF_COOKIE)
    saved = client.post("/buero/rechnungen", data={"csrf": token, **BILL}, follow_redirects=False)
    assert saved.status_code == 303
    akte = client.get("/buero/auftrag", params={"case_id": case_id}).text
    assert "Rechnung erstellen" in akte and "Positionen der nächsten Rechnung" in akte
    made = client.post("/buero/rechnung", data={"csrf": token, "case_id": case_id, "issued_on": (TODAY - timedelta(days=30)).isoformat(),
                                                "until": TODAY.isoformat(), "geprueft": "on"}, follow_redirects=False)
    assert made.status_code == 303 and made.headers["location"].endswith("#abrechnung")
    inv = billing.invoices(ctx, user, case_id)[0]
    assert "überfällig" in client.get("/buero").text, "issued 30 days ago with 14 days to pay"
    pdf = client.get("/buero/rechnung.pdf", params={"invoice_id": inv["invoice_id"]})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    page = client.get("/buero/rechnungen", params={"jahr": inv["year"]}).text
    assert "Rechnungsausgangsbuch" in page and inv["number"] in page
    journal = client.get("/buero/rechnungen.csv", params={"jahr": inv["year"]})
    assert journal.status_code == 200 and inv["number"] in journal.content.decode("utf-8-sig")
    positions = client.get("/buero/rechnungen.csv", params={"jahr": inv["year"], "art": "positionen"}).content.decode("utf-8-sig")
    assert "Recherche" in positions
    assert "abgerechnet (" + inv["number"] + ")" in client.get("/buero/auftrag", params={"case_id": case_id}).text

    ctx.team_identity_359.create_user(identity=user, username="anna", display_name="Anna Beispiel", global_role="investigator", password=PW)
    ctx.team_governance_359.assign_case_role(identity=user, case_id=case_id, username="anna", case_role="investigator")
    csrf_session(workspace, "anna", PW)
    assert client.get("/buero/rechnungen").status_code == 403
    assert client.post("/buero/rechnung", data={"csrf": client.cookies.get(CSRF_COOKIE), "case_id": case_id, "geprueft": "on"}).status_code == 403
    assert client.get("/buero/rechnung.pdf", params={"invoice_id": inv["invoice_id"]}).status_code == 200, "case members may read"
