"""Rechtliche Vorbereitung: Auftragsprüfung (Missbrauchsschutz) und Löschfristen."""
from __future__ import annotations

from datetime import date

from conftest import add_user, build_app, setup_admin
from test_step3_dossier import _docx_text

CLEAN = {"beziehung": False, "schutz": False, "aufenthalt": False, "identitaet": True}
RISKY = {**CLEAN, "beziehung": True, "aufenthalt": True}


def _case(client, answers=None, reason="", ctype="personensuche", **extra):
    body = {"title": "Auftrag X", "case_type": ctype, "purpose": "Hintergrundrecherche im Auftrag", "legal_basis": "Berechtigtes Interesse",
            "opsec_level": 1, "subject": {"label": "Max Mustermann"}, **extra}
    if answers is not None:
        body["mandate_check"] = {"answers": answers, "override_reason": reason}
    return client.post("/api/cases", json=body)


def test_mandate_questions_in_meta(tmp_path):
    app = build_app(tmp_path)
    admin = setup_admin(app)
    keys = [q["key"] for q in admin.get("/api/meta").json()["mandate_questions"]]
    assert {"beziehung", "schutz", "aufenthalt", "freiwillig", "identitaet"} <= set(keys)


def test_analyst_cannot_accept_mandate_with_warning_signs(tmp_path):
    app = build_app(tmp_path)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    r = _case(anna, RISKY)
    assert r.status_code == 403 and "Teamleitung" in r.json()["detail"]
    assert anna.get("/api/cases").json() == []
    assert _case(anna, {"beziehung": False}).status_code == 422          # unvollständig beantwortet
    ok = _case(anna, CLEAN)
    assert ok.status_code == 201
    case = anna.get(f"/api/cases/{ok.json()['id']}/overview").json()["case"]
    assert '"warnings": []' in case["mandate_check"]
    audit = anna.get(f"/api/cases/{ok.json()['id']}/audit").json()
    assert any(a["action"] == "Auftragsprüfung" and "unauffällig" in str(a) for a in audit)


def test_lead_needs_reason_and_check_appears_in_dossier(tmp_path):
    app = build_app(tmp_path)
    admin = setup_admin(app)
    lea = add_user(admin, app, "lea", "leitung")
    assert _case(lea, RISKY, "zu kurz").status_code == 422
    reason = "Vollstreckungstitel des Amtsgerichts liegt vor, Ergebnis nur an Gerichtsvollzieher."
    r = _case(lea, RISKY, reason)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    text = _docx_text(lea.get(f"/api/cases/{cid}/export/dossier.docx").content)
    assert "Auftragsprüfung" in text and "2 Warnsignal(e)" in text and "Vollstreckungstitel" in text


def test_voluntary_contact_break_only_asked_for_missing_persons(tmp_path):
    app = build_app(tmp_path)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    assert _case(anna, CLEAN, ctype="vermisst").status_code == 422      # Frage „freiwillig" fehlt
    assert _case(anna, {**CLEAN, "freiwillig": True}, ctype="vermisst").status_code == 403
    assert _case(anna, {**CLEAN, "freiwillig": False}, ctype="vermisst").status_code == 201


def test_retention_deadline_set_on_close_and_reminder_sent_once(tmp_path):
    app = build_app(tmp_path)
    admin = setup_admin(app)
    lea = add_user(admin, app, "lea", "leitung")
    assert admin.put("/api/admin/retention", json={"months": 0}).status_code == 422
    assert admin.put("/api/admin/retention", json={"months": 6}).json()["months"] == 6
    cid = _case(admin, CLEAN).json()["id"]
    case = admin.get(f"/api/cases/{cid}/overview").json()["case"]
    r = admin.patch(f"/api/cases/{cid}", json={"status": "abgeschlossen", "version": case["version"]})
    assert r.status_code == 200, r.text
    case = admin.get(f"/api/cases/{cid}/overview").json()["case"]
    until = date.fromisoformat(case["retention_until"])
    assert 150 <= (until - date.today()).days <= 190
    assert admin.patch(f"/api/cases/{cid}", json={"retention_until": "morgen", "version": case["version"]}).status_code == 422
    admin.patch(f"/api/cases/{cid}", json={"retention_until": "2020-01-01", "version": case["version"]})
    ov = admin.get("/api/admin/retention").json()
    assert [c["id"] for c in ov["cases"]] == [cid] and ov["cases"][0]["due"]
    p = app.state.platform
    assert p.retention_reminders() >= 1
    assert p.retention_reminders() == 0                                  # nur einmal
    items = lea.get("/api/notifications").json()["items"]
    assert any(i["kind"] == "loeschfrist" for i in items)
