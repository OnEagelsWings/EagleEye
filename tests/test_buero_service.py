"""Office management: mandates, screening, status, time, expenses, deadlines, permissions."""
from datetime import date

import pytest

from eagleeye.application.buero import service as buero
from eagleeye.interfaces.web.app492 import create_workspace_app492
from test_build471_local_ai import workspace  # noqa: F401  (fixture)

TODAY = date(2026, 11, 16)
PW = "Build471!Password_88"


def _mandate_form(**extra):
    form = {"title": "Hintergrundprüfung Muster GmbH", "purpose": "Prüfung der Geschäftsführung vor Vertragsabschluss",
            "kind": "due_diligence", "legal_basis_key": "berechtigtes_interesse", "received_on": "2026-11-10",
            "due_on": "2026-11-20", "fee_model": "stunden", "hourly_rate": "80", "budget": "1.000",
            "recipient": "Kanzlei Beispiel, RA Muster", "recipient_level": "mandant", "client_id": "neu",
            "client_kind": "kanzlei", "client_name": "Kanzlei Beispiel"}
    form.update(extra)
    return form


def _clean_answers(**changes):
    answers = {"q_beziehung": "nein", "q_schutz": "nein", "q_schutzanordnung": "nein", "q_anschrift": "nein",
               "q_vermisst_freiwillig": "entfaellt", "q_identitaet": "ja"}
    answers.update(changes)
    return answers


def _user(ctx, admin, name, global_role="investigator", case_id="", case_role=""):
    ctx.team_identity_359.create_user(identity=admin, username=name, display_name=name, global_role=global_role, password=PW)
    if case_id:
        ctx.team_governance_359.assign_case_role(identity=admin, case_id=case_id, username=name, case_role=case_role)
    return ctx.team_identity_359.public_user(name)


@pytest.fixture
def office(workspace):
    app, client, user, *_ = workspace
    ctx = app.state.context
    buero.initialize(ctx)
    return ctx, user


def test_parsers_use_german_formats():
    assert buero.parse_euro("85", "x") == 8500
    assert buero.parse_euro("85,5", "x") == 8550
    assert buero.parse_euro("1.250,50", "x") == 125050
    assert buero.parse_euro("1250.5", "x") == 125050
    assert buero.parse_euro("", "x") == 0
    with pytest.raises(buero.BueroError):
        buero.parse_euro("-5", "x")
    assert buero.parse_duration("1:30") == 90
    assert buero.parse_duration("1,5") == 90
    assert buero.parse_duration("2") == 120
    assert buero.parse_duration("0:05") == 5
    for bad in ("0", "25", "1:75", "abc"):
        with pytest.raises(buero.BueroError):
            buero.parse_duration(bad)
    assert buero.parse_date("16.11.2026", "x") == "2026-11-16"
    assert buero.euro(123456789) == "1.234.567,89 €"
    assert buero.hours(95) == "1:35 Std."


@pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
def test_mandate_gets_case_and_running_file_number(office):
    ctx, admin = office
    buero.save_settings(ctx, admin, {**{k: v for k, v in buero.DEFAULT_SETTINGS.items()}, "az_praefix": "DE",
                                     "stundensatz": "75", "km_satz": "0,30", "ust_modus": "regel",
                                     "aufbewahrung_monate": "36"})
    first = buero.create_mandate(ctx, admin, _mandate_form())
    second = buero.create_mandate(ctx, admin, _mandate_form(title="Zweiter Auftrag", client_id=first["client_id"],
                                                            hourly_rate=""))
    assert first["aktenzeichen"] == "DE-2026-0001" and second["aktenzeichen"] == "DE-2026-0002"
    assert first["status"] == "anfrage" and first["hourly_rate_cents"] == 8000
    assert second["hourly_rate_cents"] == 7500, "empty rate falls back to the office default"
    case = ctx.db.one("SELECT * FROM cases WHERE case_id=?", (first["case_id"],))
    assert case["client"] == "Kanzlei Beispiel" and case["legal_basis"].startswith("Berechtigtes Interesse")
    assert first["client"]["kind"] == "kanzlei"
    assert [c["mandates"] for c in buero.clients(ctx, admin)] == [2]
    with pytest.raises(buero.BueroError, match="erläutern"):
        buero.create_mandate(ctx, admin, _mandate_form(legal_basis_key="sonstiges"))
    with pytest.raises(buero.BueroError, match="Abgabefrist"):
        buero.create_mandate(ctx, admin, _mandate_form(due_on="2026-11-01"))
    with pytest.raises(buero.BueroError, match="Pauschal"):
        buero.create_mandate(ctx, admin, _mandate_form(fee_model="pauschal"))


@pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
def test_screening_rules(office):
    ctx, admin = office
    clean = buero.create_mandate(ctx, admin, _mandate_form())
    result = buero.screen(ctx, admin, clean["case_id"], {**_clean_answers(), "decision": "annehmen", "c_ausweis": "on"})
    assert result["warnings"] == [] and result["checklist"] == ["ausweis"]
    assert buero.mandate(ctx, admin, clean["case_id"])["status"] == "angenommen"
    with pytest.raises(buero.BueroError, match="neue oder angehaltene"):
        buero.screen(ctx, admin, clean["case_id"], {**_clean_answers(), "decision": "annehmen"})

    warned = buero.create_mandate(ctx, admin, _mandate_form())
    form = {**_clean_answers(q_beziehung="ja"), "decision": "annehmen", "reason": "zu kurz"}
    with pytest.raises(buero.BueroError, match="mindestens 30"):
        buero.screen(ctx, admin, warned["case_id"], form)
    form["reason"] = "Ex-Partner, aber Unterhaltsverfahren belegt; nur Vermögensauskunft, keine Anschrift."
    assert buero.screen(ctx, admin, warned["case_id"], form)["warnings"] == ["beziehung"]

    unclear = buero.create_mandate(ctx, admin, _mandate_form())
    with pytest.raises(buero.BueroError, match="mindestens 30"):
        buero.screen(ctx, admin, unclear["case_id"], {**_clean_answers(q_identitaet="unklar"), "decision": "annehmen"})
    with pytest.raises(buero.BueroError, match="jede Frage"):
        buero.screen(ctx, admin, unclear["case_id"], {**_clean_answers(q_schutz=""), "decision": "annehmen"})

    blocked = buero.create_mandate(ctx, admin, _mandate_form())
    form = {**_clean_answers(q_schutzanordnung="ja"), "decision": "annehmen",
            "reason": "Auftraggeber versichert, die Sperre sei aufgehoben worden."}
    with pytest.raises(buero.BueroError, match="Bitte ablehnen"):
        buero.screen(ctx, admin, blocked["case_id"], form)
    assert buero.screen(ctx, admin, blocked["case_id"], {**form, "decision": "ablehnen"})["decision"] == "ablehnen"
    assert buero.mandate(ctx, admin, blocked["case_id"])["status"] == "abgelehnt"

    court = buero.create_mandate(ctx, admin, _mandate_form(client_kind="behoerde", client_name="Amtsgericht Musterstadt",
                                                           legal_basis_key="behoerde"))
    assert buero.screen(ctx, admin, court["case_id"], {**form, "reason": "Beschluss des Amtsgerichts liegt vor, Az. 1 F 23/26."}
                        )["decision"] == "annehmen"

    missing = buero.create_mandate(ctx, admin, _mandate_form(kind="vermisst"))
    with pytest.raises(buero.BueroError, match="jede Frage"):
        buero.screen(ctx, admin, missing["case_id"], {**_clean_answers(), "decision": "annehmen"})
    result = buero.screen(ctx, admin, missing["case_id"], {**_clean_answers(q_vermisst_freiwillig="ja"), "decision": "annehmen",
                          "reason": "Nur Lebenszeichen an die Familie, keine Anschrift; Polizei informiert."})
    assert result["warnings"] == ["vermisst_freiwillig"]


@pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
def test_status_flow_retention_halt_and_stale_forms(office):
    ctx, admin = office
    row = buero.create_mandate(ctx, admin, _mandate_form())
    case_id = row["case_id"]
    with pytest.raises(buero.BueroError, match="nicht direkt"):
        buero.set_status(ctx, admin, case_id, {"status": "in_arbeit"})
    buero.screen(ctx, admin, case_id, {**_clean_answers(), "decision": "annehmen"})
    current = buero.mandate(ctx, admin, case_id)
    with pytest.raises(buero.StaleError):
        buero.set_status(ctx, admin, case_id, {"status": "in_arbeit", "version": str(current["version"] - 1)})
    buero.set_status(ctx, admin, case_id, {"status": "in_arbeit", "version": str(current["version"])})
    halted = buero.halt(ctx, admin, case_id, {"note": "Hinweis auf Frauenhaus in Quelle gefunden"})
    assert halted["status"] == "angehalten"
    with pytest.raises(buero.BueroError, match="mindestens 30"):
        buero.screen(ctx, admin, case_id, {**_clean_answers(), "decision": "annehmen"})
    buero.screen(ctx, admin, case_id, {**_clean_answers(q_schutz="nein"), "decision": "annehmen",
                                       "reason": "Hinweis betraf eine andere Person gleichen Namens, geprüft."})
    assert buero.mandate(ctx, admin, case_id)["status"] == "in_arbeit"
    buero.set_status(ctx, admin, case_id, {"status": "bericht"})
    closed = buero.set_status(ctx, admin, case_id, {"status": "abgeschlossen"}, today=TODAY)
    assert closed["closed_on"] == "2026-11-16" and closed["retention_until"] == "2029-11-16"
    assert ctx.db.one("SELECT retention_until FROM cases WHERE case_id=?", (case_id,))["retention_until"] == "2029-11-16"
    with pytest.raises(buero.BueroError, match="Wiedereröffnen"):
        buero.set_status(ctx, admin, case_id, {"status": "in_arbeit"})
    reopened = buero.set_status(ctx, admin, case_id, {"status": "in_arbeit", "note": "Nachtrag vom Mandanten erbeten"})
    assert reopened["closed_on"] == "" and reopened["retention_until"] == ""
    log = [(e["from_status"], e["to_status"]) for e in buero.status_log(ctx, admin, case_id)]
    assert log[0] == ("", "anfrage") and log[-1] == ("abgeschlossen", "in_arbeit") and ("in_arbeit", "angehalten") in log


@pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
def test_time_expenses_totals_and_cancellation(office):
    ctx, admin = office
    buero.save_settings(ctx, admin, {**buero.DEFAULT_SETTINGS, "stundensatz": "60", "km_satz": "0,30",
                                     "ust_modus": "regel", "aufbewahrung_monate": "36"})
    row = buero.create_mandate(ctx, admin, _mandate_form(hourly_rate="90", budget="300"))
    case_id = row["case_id"]
    buero.screen(ctx, admin, case_id, {**_clean_answers(), "decision": "annehmen"})
    t1 = buero.add_time(ctx, admin, case_id, {"work_date": "2026-11-12", "duration": "1:30", "activity": "recherche",
                                              "note": "Handelsregister"}, today=TODAY)
    buero.add_time(ctx, admin, case_id, {"work_date": "2026-11-13", "duration": "0,5", "activity": "verwaltung",
                                         "billable": "0"}, today=TODAY)
    with pytest.raises(buero.BueroError, match="im Voraus"):
        buero.add_time(ctx, admin, case_id, {"work_date": "2026-11-17", "duration": "1", "activity": "recherche"},
                       today=TODAY)
    buero.add_expense(ctx, admin, case_id, {"spent_on": "2026-11-12", "kind": "km", "km": "42"}, today=TODAY)
    buero.add_expense(ctx, admin, case_id, {"spent_on": "2026-11-12", "kind": "gebuehr", "amount": "4,50",
                                            "note": "Handelsregisterauszug"}, today=TODAY)
    money = buero.mandate(ctx, admin, case_id)["totals"]
    assert money["minutes"] == 120 and money["billable_minutes"] == 90
    assert money["fee_cents"] == 13500 and money["expenses_cents"] == 42 * 30 + 450
    assert money["net_cents"] == 13500 + 1260 + 450 and round(money["budget_share"], 3) == round(15210 / 30000, 3)

    colleague = _user(ctx, admin, "kollege", case_id=case_id, case_role="investigator")
    with pytest.raises(PermissionError):
        buero.void_entry(ctx, colleague, case_id, {"entry_type": "time", "entry_id": t1["entry_id"], "reason": "falsch"})
    own = buero.add_time(ctx, colleague, case_id, {"duration": "1", "activity": "recherche"}, today=TODAY)
    buero.void_entry(ctx, colleague, case_id, {"entry_type": "time", "entry_id": own["entry_id"], "reason": "doppelt gebucht"})
    buero.void_entry(ctx, admin, case_id, {"entry_type": "time", "entry_id": t1["entry_id"], "reason": "falscher Fall"})
    with pytest.raises(buero.BueroError, match="bereits storniert"):
        buero.void_entry(ctx, admin, case_id, {"entry_type": "time", "entry_id": t1["entry_id"], "reason": "nochmal"})
    assert buero.mandate(ctx, admin, case_id)["totals"]["billable_minutes"] == 0
    assert len(buero.time_entries(ctx, admin, case_id)) == 3, "cancelled entries stay visible"

    sheet = buero.statement(ctx, admin, case_id)
    assert len(sheet["times"]) == 1 and len(sheet["expenses"]) == 2
    assert sheet["vat"]["rate"] == 19 and sheet["vat"]["gross_cents"] == sheet["totals"]["net_cents"] + sheet["vat"]["vat_cents"]
    small = buero.vat({**buero.DEFAULT_SETTINGS, "ust_modus": "kleinunternehmer"}, 10000)
    assert small["gross_cents"] == 10000 and "§ 19 UStG" in small["note"]
    assert [e["aktenzeichen"] for e in buero.time_export(ctx, admin, "2026-11")] == [row["aktenzeichen"]]


@pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
def test_permissions_follow_case_roles(office):
    ctx, admin = office
    row = buero.create_mandate(ctx, admin, _mandate_form())
    case_id = row["case_id"]
    reader = _user(ctx, admin, "leser", global_role="read_only", case_id=case_id, case_role="read_only")
    outsider = _user(ctx, admin, "fremd", global_role="investigator")
    assert buero.mandate(ctx, reader, case_id)["aktenzeichen"] == row["aktenzeichen"]
    with pytest.raises(PermissionError):
        buero.add_time(ctx, reader, case_id, {"duration": "1", "activity": "recherche"}, today=TODAY)
    with pytest.raises(PermissionError):
        buero.screen(ctx, reader, case_id, {**_clean_answers(), "decision": "annehmen"})
    with pytest.raises(PermissionError):
        buero.clients(ctx, reader)
    with pytest.raises(PermissionError):
        buero.mandate(ctx, outsider, case_id)
    assert buero.mandates(ctx, outsider) == [] and buero.dashboard(ctx, outsider)["mandates"] == []
    with pytest.raises(PermissionError):
        buero.save_settings(ctx, outsider, buero.DEFAULT_SETTINGS)
    own = buero.create_mandate(ctx, outsider, _mandate_form(title="Eigener Auftrag"))
    assert [m["case_id"] for m in buero.mandates(ctx, outsider)] == [own["case_id"]]


@pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
def test_dashboard_collects_what_needs_attention(office, workspace):
    ctx, admin = office
    legacy_case = workspace[3]  # case created without office data
    a = buero.create_mandate(ctx, admin, _mandate_form(due_on="2026-11-14", budget="100"))
    b = buero.create_mandate(ctx, admin, _mandate_form(due_on="2026-11-20"))
    c = buero.create_mandate(ctx, admin, _mandate_form(due_on=""))
    for row in (a, b, c):
        buero.screen(ctx, admin, row["case_id"], {**_clean_answers(), "decision": "annehmen"})
    buero.add_time(ctx, admin, a["case_id"], {"work_date": "2026-11-10", "duration": "1", "activity": "recherche"},
                   today=TODAY)
    buero.add_deadline(ctx, admin, b["case_id"], {"due_on": "2026-11-15", "title": "Rückruf Mandant"})
    later = buero.add_deadline(ctx, admin, b["case_id"], {"due_on": "2026-12-15", "title": "Registerabfrage wiederholen"})
    buero.set_status(ctx, admin, c["case_id"], {"status": "abgeschlossen"}, today=date(2023, 1, 2))
    view = buero.dashboard(ctx, admin, today=TODAY)
    assert [r["case_id"] for r in view["due_mandates"]] == [b["case_id"], a["case_id"]] or \
        {r["case_id"] for r in view["due_mandates"]} == {a["case_id"], b["case_id"]}
    states = {r["case_id"]: r["due_state"] for r in view["mandates"]}
    assert states[a["case_id"]] == "overdue" and states[b["case_id"]] == "soon" and states[c["case_id"]] == ""
    assert [d["title"] for d in view["deadlines"]] == ["Rückruf Mandant"] and view["deadlines"][0]["overdue"]
    assert [r["case_id"] for r in view["retention_due"]] == [c["case_id"]]
    assert [r["case_id"] for r in view["over_budget"]] == [a["case_id"]]
    assert view["month_minutes"] == 60
    assert legacy_case in {str(x["case_id"]) for x in view["without_mandate"]}
    buero.complete_deadline(ctx, admin, b["case_id"], {"deadline_id": later["deadline_id"]})
    with pytest.raises(buero.BueroError):
        buero.complete_deadline(ctx, admin, b["case_id"], {"deadline_id": later["deadline_id"]})
    attached = buero.attach_mandate(ctx, admin, legacy_case, {**_mandate_form(), "client_id": a["client_id"]})
    assert attached["aktenzeichen"].endswith("-0004") and attached["status"] == "anfrage"
    with pytest.raises(buero.BueroError, match="bereits"):
        buero.attach_mandate(ctx, admin, legacy_case, _mandate_form())
