"""Vermisstenüberwachung: Register + Presse mit allen Varianten, dringende Meldung, im Vault bei jedem Netzöffnen (höchstens stündlich)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import H, build_app, setup_admin
from personosint import monitor
from test_deep import ROUTES, _case
from test_personosint import FakeHttp


def test_missing_watch_runs_registers_variants_and_notifies(tmp_path):
    http = FakeHttp(ROUTES)
    app = build_app(tmp_path, http=http)
    c = setup_admin(app)
    cid, eid = _case(c)
    r = c.post(f"/api/cases/{cid}/watches", json={"entity_id": eid, "sources": [], "mode": "vermisst", "interval_hours": 1}, headers=H)
    assert r.status_code in (200, 201), r.text
    w = r.json()
    assert w["mode"] == "vermisst" and {"interpol_yellow", "fbi_missing", "gdelt_missing"} <= set(w["sources"]) and w["interval_label"] == "stündlich"
    p = app.state.platform
    queries = monitor.missing_queries(p, cid, eid, w["sources"])
    assert ("fbi_missing", "name", "Müller, Max") in queries or ("fbi_missing", "name", "Mueller, Max") in queries
    res = c.post(f"/api/cases/{cid}/watches/{w['id']}/run", headers=H).json()
    assert res["ok"] and res["new"] >= 1
    notes = c.get("/api/notifications").json()["items"]
    assert notes and notes[0]["kind"] == "dringend" and "Vermisstenüberwachung" in notes[0]["text"]
    # zweiter Lauf: keine doppelten Treffer, keine neue Meldung
    again = c.post(f"/api/cases/{cid}/watches/{w['id']}/run", headers=H).json()
    assert again["ok"] and again["new"] == 0
    # beim Netzöffnen: gerade gelaufen ⇒ nicht erneut; eine Stunde später ⇒ ja
    assert monitor.run_on_net_open(p) == 0
    assert monitor.run_on_net_open(p, now=datetime.now(timezone.utc) + timedelta(minutes=61)) == 1
    assert c.post(f"/api/cases/{cid}/watches", json={"entity_id": eid, "sources": [], "mode": "unsinn"}, headers=H).status_code == 422
