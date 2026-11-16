"""Schritt 1: Quellen-Baukasten, Schlüsselverwaltung, Faktenmodell, neue Quellen, lokale Referenzdaten."""
from __future__ import annotations

import io
import json
import zipfile

from conftest import add_user, build_app, setup_admin
from test_personosint import FakeHttp

CH = "https://api.company-information.service.gov.uk"
ROUTES = {
    f"{CH}/search/officers": (200, {"items": [
        {"title": "Max MUSTERMANN", "date_of_birth": {"month": 5, "year": 1980}, "address_snippet": "1 High Street, London",
         "appointment_count": 2, "links": {"self": "/officers/abc123/appointments"}},
        {"title": "Erika MUSTERFRAU", "links": {"self": "/officers/zzz/appointments"}}]}),
    f"{CH}/officers/abc123/appointments": (200, {"items": [
        {"appointed_to": {"company_name": "NORDHAFEN HOLDINGS LIMITED", "company_number": "0123", "company_status": "active"},
         "officer_role": "director", "appointed_on": "2019-03-01"},
        {"appointed_to": {"company_name": "BEISPIEL TRADING LTD", "company_number": "0456", "company_status": "dissolved"},
         "officer_role": "secretary", "appointed_on": "2015-01-01", "resigned_on": "2016-06-30"}]}),
    "https://api.opencorporates.com/v0.4/officers/search": (200, {"results": {"officers": [
        {"officer": {"name": "MAX MUSTERMANN", "position": "Geschäftsführer", "start_date": "2020-01-01", "opencorporates_url": "https://opencorporates.com/officers/1",
                     "company": {"name": "Hafen Beteiligungs GmbH", "company_number": "HRB 1", "jurisdiction_code": "de",
                                 "opencorporates_url": "https://opencorporates.com/companies/de/1"}}}]}}),
    "https://api.gleif.org/api/v1/lei-records?": (200, {"data": [{"id": "LEI0001", "attributes": {"lei": "LEI0001", "entity": {
        "legalName": {"name": "Hafen Beteiligungs GmbH"}, "legalAddress": {"addressLines": ["Kai 1"], "postalCode": "20457", "city": "Hamburg", "country": "DE"},
        "status": "ACTIVE", "registeredAs": "HRB 1"}}}]}),
    "https://api.gleif.org/api/v1/lei-records/LEI0001/direct-parent": (200, {"data": {"id": "LEI0002", "attributes": {"entity": {"legalName": {"name": "Nordhafen Holdings Limited"}}}}}),
    "https://api.gleif.org/api/v1/lei-records/LEI0001/ultimate-parent": (404, {}),
    "https://www.wikidata.org/w/api.php": (200, {"search": [{"id": "Q99", "label": "Max Mustermann", "description": "fiktiver Unternehmer"}]}),
    "https://query.wikidata.org/sparql": (200, {"results": {"bindings": [
        {"item": {"value": "http://www.wikidata.org/entity/Q99"}, "prop": {"value": "P26"}, "value": {"value": "x"}, "valueLabel": {"value": "Erika Mustermann"}},
        {"item": {"value": "http://www.wikidata.org/entity/Q99"}, "prop": {"value": "P569"}, "value": {"value": "1980-05-17T00:00:00Z"}, "valueLabel": {"value": "1980-05-17T00:00:00Z"}},
        {"item": {"value": "http://www.wikidata.org/entity/Q99"}, "prop": {"value": "P108"}, "value": {"value": "x"}, "valueLabel": {"value": "Hafen Beteiligungs GmbH"},
         "start": {"value": "2010-01-01T00:00:00Z"}}]}}),
    "https://crt.sh/": (200, [{"name_value": "mail.musterhafen.de\nmusterhafen.de", "not_before": "2021-02-03T00:00:00"},
                              {"name_value": "intern.musterhafen.de", "not_before": "2019-07-01T00:00:00"}]),
    "https://rdap.org/domain/musterhafen.de": (200, {"ldhName": "musterhafen.de", "events": [{"eventAction": "registration", "eventDate": "2005-04-01T00:00:00Z"}],
                                                     "entities": [{"roles": ["registrar"], "vcardArray": ["vcard", [["fn", {}, "text", "Beispiel Registrar AG"]]]}],
                                                     "nameservers": [{"ldhName": "NS1.BEISPIEL.NET"}]}),
    "https://api.opensanctions.org/search/default": (200, {"results": [
        {"id": "os-1", "caption": "Max Mustermann", "schema": "Person", "datasets": ["eu_fsf"],
         "properties": {"topics": ["sanction"], "birthDate": ["1980-05-17"], "nationality": ["de"]}}]}),
}

SUBJECT = {"label": "Max Mustermann", "data": {"geburtsdatum": "1980-05-17"}, "identifiers": [
    {"kind": "employer", "value": "Hafen Beteiligungs GmbH"}, {"kind": "domain", "value": "musterhafen.de"}]}
CASE = {"title": "Beteiligungen Mustermann", "case_type": "investigativ", "purpose": "Investigative Recherche zu Firmenbeteiligungen",
        "legal_basis": "Journalistische Recherche (Medienprivileg)", "opsec_level": 1, "subject": SUBJECT}


def _setup(tmp_path, backend="sqlite"):
    http = FakeHttp(ROUTES)
    app = build_app(tmp_path, backend, http=http)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    case = anna.post("/api/cases", json=CASE).json()
    sid = anna.get(f"/api/cases/{case['id']}/overview").json()["subject"]["id"]
    return app, http, admin, anna, case["id"], sid


def test_source_registry_and_keys(tmp_path):
    app, http, admin, anna, cid, sid = _setup(tmp_path)
    reg = admin.get("/api/admin/sources").json()
    by = {s["key"]: s for s in reg["sources"]}
    assert {"companies_house", "opencorporates", "gleif", "wikidata_rel", "crtsh", "rdap", "opensanctions",
            "lokal_opensanctions", "lokal_icij", "lokal_eigene_liste"} <= set(by)
    assert by["companies_house"]["requires_key"] and "Schlüssel" in by["companies_house"]["unavailable"]
    assert by["companies_house"]["reliability"] == "A" and by["lokal_icij"]["exposure"] == "lokal"
    assert {d["name"] for d in reg["datasets"]} == {"opensanctions", "icij", "eigene_liste"}
    assert anna.get("/api/admin/sources").status_code == 403
    # Suche nur mit Schlüsselquelle ohne Schlüssel -> verständliche Meldung
    r = anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": ["companies_house"]})
    assert r.status_code == 422 and "API-Schlüssel fehlt" in r.json()["detail"]
    assert admin.put("/api/admin/sources/companies_house/key", json={"key": "geheimer-ch-schluessel"}).status_code == 200
    raw = app.state.platform.db.scalar("SELECT value FROM settings WHERE key = 'api_keys'")
    assert "geheimer-ch-schluessel" not in raw                      # verschlüsselt gespeichert
    by = {s["key"]: s for s in admin.get("/api/admin/sources").json()["sources"]}
    assert by["companies_house"]["key_set"] and not by["companies_house"]["unavailable"]
    assert admin.put("/api/admin/sources/gleif/key", json={"key": "x"}).status_code == 422
    t = admin.post("/api/admin/sources/companies_house/test").json()
    assert t["ok"] and t["count"] == 0          # Testabfrage „Angela Merkel“: Namensfilter greift
    assert http.calls[-1].startswith("https://api.company-information.service.gov.uk/search/officers")


def test_new_sources_produce_facts_and_graph(tmp_path, backend):
    app, http, admin, anna, cid, sid = _setup(tmp_path, backend)
    admin.put("/api/admin/sources/companies_house/key", json={"key": "k1"})
    admin.put("/api/admin/sources/opensanctions/key", json={"key": "k2"})
    r = anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": [
        "companies_house", "opencorporates", "gleif", "wikidata_rel", "crtsh", "rdap", "opensanctions"]})
    assert r.status_code == 200, r.text
    res = r.json()
    assert all(s["ok"] for s in res["status"]), res["status"]
    assert res["new_findings"] == 7 and res["new_facts"] >= 15
    findings = {f["source"]: f for f in anna.get(f"/api/cases/{cid}/findings").json()}
    ch = findings["UK Companies House"]
    assert any(f["predicate"] == "funktion_bei" and f["object_label"] == "Nordhafen Holdings Limited" for f in ch["facts"])
    assert any("Geburtsmonat" in reason for reason in ch["reasons"])          # Geburtsdatum-Abgleich im Score
    gl = findings["GLEIF (LEI-Register)"]
    assert any(f["predicate"] == "tochter_von" and f["subject_label"] == "Hafen Beteiligungs GmbH" for f in gl["facts"])
    facts = anna.get(f"/api/cases/{cid}/facts").json()
    preds = {f["predicate"] for f in facts}
    assert {"funktion_bei", "geburtsdatum", "verheiratet_mit", "arbeitet_bei", "subdomain", "domain_registrar", "sanktioniert", "tochter_von"} <= preds
    assert all(f["status"] == "neu" and f["reliability"] for f in facts)
    assert next(f for f in facts if f["source_key"] == "companies_house")["reliability"] == "A"
    # externe Abfragen im Außenkontakt-Protokoll als „passiv“
    hosts = {h["host"]: h["exposure"] for h in anna.get(f"/api/cases/{cid}/opsec").json()["hosts"]}
    assert hosts["api.company-information.service.gov.uk"] == "passiv" and hosts["crt.sh"] == "passiv"

    # Bestätigen -> Fakten bestätigt, Beziehungen im Graphen
    for name in ("UK Companies House", "GLEIF (LEI-Register)", "Wikidata – Beziehungen"):
        assert anna.patch(f"/api/cases/{cid}/findings/{findings[name]['id']}", json={"status": "bestätigt"}).status_code == 200
    anna.patch(f"/api/cases/{cid}/findings/{findings['OpenCorporates']['id']}", json={"status": "verworfen"})
    facts = anna.get(f"/api/cases/{cid}/facts").json()
    assert all(f["status"] == "bestätigt" for f in facts if f["source_key"] in {"companies_house", "gleif", "wikidata_rel"})
    assert all(f["status"] == "verworfen" for f in facts if f["source_key"] == "opencorporates")
    g = anna.get(f"/api/cases/{cid}/graph").json()
    labels = {n["label"]: n for n in g["nodes"]}
    assert "Nordhafen Holdings Limited" in labels and "Erika Mustermann" in labels and "Hafen Beteiligungs GmbH" in labels
    rels = {e["relation"] for e in g["edges"]}
    assert "Funktion bei (director)" in rels and "Partner/in von" in rels and "beteiligt an" in rels
    # Pfad: Person -> Firma (Wikidata) -> Mutter (GLEIF) == Firma (Companies House) – gleiche Firma über zwei Quellen
    nord = labels["Nordhafen Holdings Limited"]["id"]
    paths = anna.get(f"/api/cases/{cid}/paths", params={"a": sid, "b": nord}).json()
    assert paths["shortest_length"] == 1 and any(p["length"] == 2 for p in paths["paths"])


def _opensanctions_csv() -> bytes:
    rows = [
        "id,schema,name,aliases,birth_date,countries,addresses,identifiers,sanctions,phones,emails,dataset,first_seen,last_seen,last_change",
        'os-9,Person,Max Mustermann,Maks Mustermann;M. Mustermann,1980-05-17,de,,,"EU Finanzsanktionen (2022)",,,EU Financial Sanctions Files,2022-01-01,2026-10-01,2026-10-01',
        'os-10,Person,Erika Beispiel,,1970-01-01,at,,,,,,Wikidata Politically Exposed Persons,2022-01-01,2026-10-01,2026-10-01',
        'os-11,Person,Max Mustermann-Völlig-Anders,,1950,fr,,,,,,Interpol Red Notices,2022-01-01,2026-10-01,2026-10-01',
    ]
    return ("\n".join(rows) + "\n").encode()


def _icij_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("full/nodes-officers.csv", "node_id,name,countries,country_codes,sourceID,valid_until,note\n"
                                              "1001,MAX MUSTERMANN,Germany,DEU,Panama Papers,,\n1002,JOHN DOE,UK,GBR,Paradise Papers,,\n")
        z.writestr("full/nodes-entities.csv", "node_id,name,original_name,former_name,jurisdiction,jurisdiction_description,company_type,address,internal_id,"
                                              "incorporation_date,inactivation_date,struck_off_date,dorm_date,status,service_provider,ibcRUC,country_codes,countries,sourceID,valid_until,note\n"
                                              "2001,SEAGULL TRADING INC.,,,BVI,British Virgin Islands,,,,01-JAN-2008,,,,Active,Mossack Fonseca,,VGB,British Virgin Islands,Panama Papers,,\n")
        z.writestr("full/nodes-intermediaries.csv", "node_id,name,countries,country_codes,sourceID,valid_until,note,status\n")
        z.writestr("full/nodes-addresses.csv", "node_id,address,name,countries,country_codes,sourceID,valid_until,note\n3001,Hafenstrasse 1 Hamburg,,Germany,DEU,Panama Papers,,\n")
        z.writestr("full/relationships.csv", "node_id_start,node_id_end,rel_type,link,status,start_date,end_date,sourceID\n"
                                             "1001,2001,officer_of,shareholder of,,2008-02-01,2012-12-31,Panama Papers\n"
                                             "1001,3001,registered_address,registered address,,,,Panama Papers\n")
    return buf.getvalue()


def test_local_reference_datasets(tmp_path, backend):
    app, http, admin, anna, cid, sid = _setup(tmp_path, backend)
    p = app.state.platform
    assert admin.post("/api/admin/refdata/opensanctions/upload", files={"file": ("targets.simple.csv", _opensanctions_csv(), "text/csv")}).status_code == 200
    p.refdata.wait("opensanctions")
    assert admin.post("/api/admin/refdata/icij/upload", files={"file": ("full-oldb.zip", _icij_zip(), "application/zip")}).status_code == 200
    p.refdata.wait("icij")
    assert admin.post("/api/admin/refdata/eigene_liste/upload",
                      files={"file": ("liste.csv", "name;x\n".replace(";", ",").encode() + b"Max Mustermann,1\n", "text/csv")}).status_code == 200
    p.refdata.wait("eigene_liste")
    st = {d["name"]: d for d in admin.get("/api/admin/sources").json()["datasets"]}
    assert st["opensanctions"]["records"] == 3 and st["opensanctions"]["status"] == "bereit"
    assert st["icij"]["records"] == 4 and st["icij"]["links"] == 2
    assert st["eigene_liste"]["records"] == 1
    calls_before = len(http.calls)
    r = anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": ["lokal_opensanctions", "lokal_icij", "lokal_eigene_liste"]})
    assert r.status_code == 200, r.text
    assert len(http.calls) == calls_before                      # lokal: nichts verlässt den Server
    findings = anna.get(f"/api/cases/{cid}/findings").json()
    titles = " | ".join(f["title"] for f in findings)
    assert "OpenSanctions (SANKTIONIERT): Max Mustermann" in titles and "Völlig-Anders" not in titles
    icij = next(f for f in findings if f["title"].startswith("ICIJ"))
    off = next(f for f in icij["facts"] if f["predicate"] == "offshore_funktion")
    assert off["object_label"] == "SEAGULL TRADING INC." and off["valid_from"] == "2008-02-01" and off["data"]["leak"] == "Panama Papers"
    assert any(f["predicate"] == "adresse" and "Hafenstrasse" in f["object_label"] for f in icij["facts"])
    # Alias-Suche findet denselben Eintrag
    assert p.refdata.search("opensanctions", "Maks Mustermann")[0]["ext_id"] == "os-9"
    # Löschen
    assert admin.delete("/api/admin/refdata/icij").status_code == 204
    assert not p.refdata.available("icij")


def test_bad_import_reports_error(tmp_path):
    app, http, admin, anna, cid, sid = _setup(tmp_path)
    admin.post("/api/admin/refdata/icij/upload", files={"file": ("x.zip", b"kein zip", "application/zip")})
    app.state.platform.refdata.wait("icij")
    st = {d["name"]: d for d in admin.get("/api/admin/sources").json()["datasets"]}
    assert st["icij"]["status"] == "fehler" and st["icij"]["message"]


def test_cli_import(tmp_path):
    from personosint.__main__ import main
    app, http, admin, anna, cid, sid = _setup(tmp_path)
    f = tmp_path / "targets.simple.csv"
    f.write_bytes(_opensanctions_csv())
    main(["--data", str(tmp_path), "import-refdata", "opensanctions", str(f)])
    assert app.state.platform.refdata.available("opensanctions")
    assert json.dumps(app.state.platform.refdata.status())
