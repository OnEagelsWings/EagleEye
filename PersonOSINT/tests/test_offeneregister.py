"""OffeneRegister: deutscher Handelsregister-Abzug als lokaler Bestand – Rollen von Personen, Organe von Firmen."""
from __future__ import annotations

import bz2
import json

from conftest import H, build_app, setup_admin

RECORDS = [
    {"company_number": "K1101R_HRB1234", "name": "Nordhafen Projekt GmbH", "current_status": "currently registered", "jurisdiction_code": "de",
     "registered_address": "Hafenstraße 1, 24103 Kiel", "retrieved_at": "2018-10-01",
     "all_attributes": {"_registerArt": "HRB", "_registerNummer": "1234", "native_company_number": "Kiel HRB 1234"},
     "officers": [{"name": "Max Mustermann", "position": "Geschäftsführer", "start_date": "2015-03-01", "type": "person",
                   "other_attributes": {"city": "Kiel", "firstname": "Max", "lastname": "Mustermann"}},
                  {"name": "Eva Test", "position": "Prokurist", "type": "person", "other_attributes": {"city": "Lübeck"}}]},
    {"company_number": "K1101R_HRB9999", "name": "Seeblick Holding AG", "current_status": "removed", "officers": [
        {"name": "Max Mustermann", "position": "Vorstand", "start_date": "2010-01-01", "end_date": "2014-12-31", "other_attributes": {"city": "Kiel"}}]},
    {"company_number": "K1101R_HRB5555", "name": "Andere Firma KG", "officers": [{"name": "Maximiliane Musterfrau", "position": "Geschäftsführer"}]},
]


def test_import_and_find_roles_offline(tmp_path):
    src = tmp_path / "de_companies_ocdata.jsonl.bz2"
    src.write_bytes(bz2.compress(("\n".join(json.dumps(r, ensure_ascii=False) for r in RECORDS) + "\nkaputte zeile\n").encode()))
    app = build_app(tmp_path / "app")
    setup_admin(app)
    p = app.state.platform
    res = p.refdata.import_file("offeneregister", src)
    assert res["records"] == 3 + 4 and res["links"] == 4
    assert p.source_unavailable(p.source_map()["lokal_offeneregister"]) == ""
    roles = p.refdata.findings("offeneregister", "name", "Max Mustermann")
    titles = {r["title"] for r in roles}
    assert len(roles) == 2 and all("Musterfrau" not in t for t in titles)
    gf = next(r for r in roles if "Nordhafen" in r["title"])
    assert gf["claims"][0]["predicate"] == "funktion_bei" and gf["claims"][0]["attrs"]["rolle"] == "Geschäftsführer"
    assert gf["claims"][0]["valid_from"] == "2015-03-01" and "Stand 2018" in gf["snippet"]
    firm = p.refdata.findings("offeneregister", "employer", "Nordhafen Projekt GmbH")
    assert len(firm) == 1 and sum(1 for c in firm[0]["claims"] if c["predicate"] == "funktion_bei") == 2


def test_offeneregister_feeds_search_and_deep_plan(tmp_path):
    src = tmp_path / "or.jsonl"
    src.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in RECORDS), encoding="utf-8")
    app = build_app(tmp_path / "app")
    c = setup_admin(app)
    app.state.platform.refdata.import_file("offeneregister", src)
    r = c.post("/api/cases", json={"title": "Firmenrollen", "case_type": "personensuche", "purpose": "Hintergrundprüfung im Auftrag",
                                   "legal_basis": "Berechtigtes Interesse", "subject": {"label": "Max Mustermann"}}, headers=H)
    cid = r.json()["id"]
    eid = next(e["id"] for e in c.get(f"/api/cases/{cid}/entities").json() if e["type"] == "person")
    pl = c.get(f"/api/cases/{cid}/entities/{eid}/deep/plan").json()
    assert any(q["source"] == "lokal_offeneregister" and q["exposure"] == "lokal" for q in pl["queries"])
    res = c.post(f"/api/cases/{cid}/search", json={"entity_id": eid, "sources": ["lokal_offeneregister"]}, headers=H).json()
    assert res["new_findings"] == 2
    facts = c.get(f"/api/cases/{cid}/facts").json()
    preds = {f["predicate"] for f in (facts["facts"] if isinstance(facts, dict) else facts)}
    assert "funktion_bei" in preds


def test_vault_keeps_reference_data_out_of_encrypted_memory_db(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from personosint import auth as auth_mod
    from personosint import netgate
    from personosint.auth import totp_code
    from personosint.vault_app import create_vault_app
    from test_personosint import FakeHttp
    from test_vault import FAST_KDF, PASS, Clock

    clock = Clock()
    monkeypatch.setattr(auth_mod.time, "time", clock)
    app = create_vault_app(tmp_path / "vault", http=FakeHttp({}), kdf=FAST_KDF, classic_dir=tmp_path / "nichts", background=False)
    c = TestClient(app, base_url="http://127.0.0.1")
    try:
        secret = c.post("/vault/api/setup/begin", json={"display_name": "Detektei Nord", "passphrase": PASS, "passphrase2": PASS}, headers=H).json()["secret"]
        c.post("/vault/api/setup/finish", json={"code": totp_code(secret, clock.now)}, headers=H)
        src = tmp_path / "or.jsonl"
        src.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in RECORDS * 50), encoding="utf-8")
        m = app.manager
        m.inner.state.platform.refdata.import_file("offeneregister", src)
        m.save(force=True)
        enc = (tmp_path / "vault" / "vault.db.enc").read_bytes()
        assert b"Nordhafen" not in enc and (tmp_path / "vault" / "files" / "referenzdaten.sqlite3").is_file()
        assert m.db.one("SELECT COUNT(*) AS n FROM ref_records")["n"] == 0                       # nicht in der Vault-Datenbank
        assert m.refdb.one("SELECT COUNT(*) AS n FROM ref_records")["n"] > 0
    finally:
        app.manager.lock("Testende")
        netgate.uninstall()
