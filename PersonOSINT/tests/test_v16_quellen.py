"""Version 1.6: zusätzliche freie Quellen, Ein-Klick-Prüfung aller Quellen und Serverbetrieb.

Die Antworten sind den veröffentlichten Schnittstellenbeschreibungen nachgebildet. Ob eine Quelle wirklich
antwortet, zeigt erst die Prüfung auf einem Rechner mit Internetzugang (Verwaltung → „Alle Quellen prüfen“).
"""
from __future__ import annotations

import argparse
import json

import pytest
from fastapi.testclient import TestClient

from conftest import H, add_user, build_app, make_settings, setup_admin
from personosint import opsec, pivot
from personosint.api import create_app
from personosint.connectors2 import MORE_SOURCES
from personosint.sources import HttpResponse, SourceError

SRC = {s.key: s for s in MORE_SOURCES}

ROUTES: dict[str, tuple[int, object]] = {
    "https://lobid.org/gnd/search": (200, {"totalItems": 2, "member": [
        {"gndIdentifier": "119545373", "preferredName": "Merkel, Angela", "dateOfBirth": ["1954-07-17"], "placeOfBirth": [{"label": "Hamburg"}],
         "professionOrOccupation": [{"label": "Politikerin"}, {"label": "Physikerin"}], "affiliation": [{"label": "Christlich-Demokratische Union Deutschlands"}],
         "variantName": ["Merkel, Angela Dorothea", "Kasner, Angela"]},
        {"gndIdentifier": "1", "preferredName": "Merkelbach, Reinhold", "dateOfBirth": ["1918"]}]}),
    "https://www.abgeordnetenwatch.de/api/v2/politicians": (200, {"meta": {"result": {"total": 1}}, "data": [
        {"id": 79137, "label": "Angela Merkel", "first_name": "Angela", "last_name": "Merkel", "year_of_birth": 1954, "party": {"id": 2, "label": "CDU"},
         "occupation": "Bundeskanzlerin a. D.", "education": "Physikerin", "residence": "Berlin", "qid_wikidata": "Q567",
         "abgeordnetenwatch_url": "https://www.abgeordnetenwatch.de/profile/angela-merkel"}]}),
    "https://recherche-entreprises.api.gouv.fr/search": (200, {"total_results": 2, "results": [
        {"siren": "775670417", "nom_complet": "LVMH MOET HENNESSY LOUIS VUITTON", "date_creation": "1923-01-01", "etat_administratif": "A",
         "siege": {"adresse": "22 AVENUE MONTAIGNE 75008 PARIS", "libelle_commune": "PARIS"},
         "dirigeants": [{"nom": "ARNAULT", "prenoms": "BERNARD, JEAN", "date_de_naissance": "1949-03", "qualite": "Président-directeur général", "type_dirigeant": "personne physique"},
                        {"nom": "DUPONT", "prenoms": "CLAIRE", "qualite": "Administrateur"}]},
        {"siren": "111111111", "nom_complet": "ARNAULT CONSEIL", "siege": {"libelle_commune": "LYON"}, "dirigeants": [{"nom": "MARTIN", "prenoms": "PAUL", "qualite": "Gérant"}]}]}),
    "https://offshoreleaks.icij.org/api/v1/reconcile": (200, {"q0": {"result": [
        {"id": "https://offshoreleaks.icij.org/nodes/12180773", "name": "SERGEY ROLDUGIN", "score": 90, "types": [{"id": "x/officer", "name": "Officer"}]},
        {"id": "https://offshoreleaks.icij.org/nodes/2", "name": "ROLDUGIN HOLDINGS LIMITED", "score": 40, "types": [{"name": "Entity"}]}]}}),
    "https://ws-public.interpol.int/notices/v1/red": (200, {"total": 1, "_embedded": {"notices": [
        {"forename": "JOHN", "name": "SMITH", "date_of_birth": "1970/01/02", "entity_id": "2020/12345", "nationalities": ["US"]}]}}),
    "https://api.fbi.gov/wanted/v1/list": (200, {"total": 2, "items": [
        {"title": "JOHN SMITH", "uid": "abc", "url": "https://www.fbi.gov/wanted/x/john-smith", "aliases": ["Johnny Smith"], "dates_of_birth_used": ["January 2, 1970"],
         "nationality": "American", "poster_classification": "default", "description": "Bank robbery"},
        {"title": "SMITHSONIAN BURGLARY", "uid": "def", "url": "https://www.fbi.gov/wanted/y"}]}),
    "https://api.gdeltproject.org/api/v2/doc/doc": (200, {"articles": [
        {"url": "https://zeitung.example/hafen", "title": "Hafenprojekt: Fragen an Max Mustermann", "seendate": "20261101T080000Z", "domain": "zeitung.example",
         "language": "German", "sourcecountry": "Germany"}]}),
    "https://de.wikipedia.org/w/api.php": (200, {"query": {"search": [{"title": "Angela Merkel", "pageid": 145, "snippet": "<span>Angela</span> Dorothea Merkel ist …"},
                                                                    {"title": "Kabinett Merkel I", "pageid": 9, "snippet": "Das Kabinett …"}]}}),
    "https://en.wikipedia.org/w/api.php": (200, {"query": {"search": []}}),
    "https://api.crossref.org/works": (200, {"status": "ok", "message": {"items": [
        {"DOI": "10.1/x", "title": ["On Ports"], "issued": {"date-parts": [[2021, 5]]},
         "author": [{"given": "Max", "family": "Mustermann", "affiliation": [{"name": "Universität Kiel"}]}, {"given": "Eva", "family": "Test"}]},
        {"DOI": "10.1/y", "title": ["Other"], "issued": {"date-parts": [[2019]]}, "author": [{"given": "Moritz", "family": "Mustermann"}]}]}}),
    "https://dblp.org/search/author/api": (200, {"result": {"hits": {"@total": "1", "hit": [
        {"info": {"author": "Donald E. Knuth", "url": "https://dblp.org/pid/k/DonaldEKnuth", "notes": {"note": {"@type": "affiliation", "text": "Stanford University, USA"}}}}]}}}),
    "https://keybase.io/_/api/1.0/user/lookup.json": (200, {"status": {"code": 0}, "them": [
        {"basics": {"username": "maxmuster"}, "profile": {"full_name": "Max Mustermann", "location": "Kiel"},
         "proofs_summary": {"all": [{"proof_type": "github", "nametag": "maxmuster", "service_url": "https://github.com/maxmuster"},
                                    {"proof_type": "twitter", "nametag": "mmuster", "service_url": "https://twitter.com/mmuster"}]}}]}),
    "https://codeberg.org/api/v1/users/search": (200, {"ok": True, "data": [
        {"login": "maxmuster", "full_name": "Max Mustermann", "html_url": "https://codeberg.org/maxmuster", "location": "Kiel", "website": "https://mustermann.example"},
        {"login": "maxmusterfrau", "full_name": "Erika"}]}),
    "https://hub.docker.com/v2/users/maxmuster/": (200, {"id": "1", "username": "maxmuster", "full_name": "Max Mustermann", "company": "Nordhafen Projekt GmbH",
                                                          "location": "Kiel", "date_joined": "2016-02-03T10:00:00Z"}),
}


class Http:
    def __init__(self, routes=ROUTES):
        self.routes, self.calls = routes, []

    def get(self, url: str, headers=None) -> HttpResponse:
        self.calls.append(url)
        for prefix, (status, body) in self.routes.items():
            if url.startswith(prefix):
                if status == -1:
                    raise SourceError("Quelle nicht erreichbar: simuliert")
                return HttpResponse(status, body if isinstance(body, bytes) else json.dumps(body).encode(), url)
        return HttpResponse(404, b"", url)


def _run(key: str, kind: str, value: str, http=None):
    return SRC[key].run(kind, value, http or Http())


def _claims(item) -> set[tuple[str, str]]:
    return {(c["predicate"], c["object"]) for c in item.get("claims") or []}


def test_every_new_source_is_registered_with_exposure_manifest_and_licence():
    assert len(MORE_SOURCES) == 13
    for s in MORE_SOURCES:
        assert s.key in opsec.SOURCE_EXPOSURE and s.key in pivot.PRODUCES, s.key
        assert s.hosts and s.license and s.docs.startswith("https://") and s.kinds and s.test_query[0] in s.kinds, s.key
        assert not s.requires_key                                         # alle ohne Anmeldung nutzbar


def test_every_source_has_a_test_query_it_can_actually_process(tmp_path):
    """Die Ein-Klick-Prüfung deckte auf, dass ältere Quellen mit einem Personennamen statt z. B. einem Benutzernamen getestet wurden."""
    app = build_app(tmp_path, http=Http())
    for s in app.state.platform.all_sources():
        assert s.test_query[0] in s.kinds, (s.key, s.test_query, s.kinds)


def test_gnd_and_abgeordnetenwatch_yield_structured_statements():
    gnd = _run("lobid_gnd", "name", "Angela Merkel")
    assert [g["title"] for g in gnd] == ["GND: Angela Merkel (1954)"] and gnd[0]["url"] == "https://lobid.org/gnd/119545373"
    assert {("geburtsdatum", "1954-07-17"), ("geburtsort", "Hamburg"), ("beschreibung", "Politikerin"), ("alias", "Angela Kasner"),
            ("arbeitet_bei", "Christlich-Demokratische Union Deutschlands")} <= _claims(gnd[0])
    assert gnd[0]["names"] == ["Angela Merkel"] and gnd[0]["source_key"] == "lobid_gnd"
    aw = _run("abgeordnetenwatch", "name", "Angela Merkel")
    assert aw[0]["url"].endswith("/profile/angela-merkel") and {("partei", "CDU"), ("amt", "Bundeskanzlerin a. D."), ("geburtsdatum", "1954")} <= _claims(aw[0])
    http = Http()
    _run("abgeordnetenwatch", "name", "Merkel", http)
    assert "label%5Bcn%5D=Merkel" in http.calls[0]                         # ein einzelnes Wort sucht im vollen Namen


def test_french_register_matches_person_as_officer_and_company_by_name():
    person = _run("fr_entreprises", "name", "Bernard Arnault")
    assert len(person) == 1 and person[0]["names"] == ["Bernard Arnault"] and person[0]["data"]["siren"] == "775670417"
    c = {x["predicate"]: x for x in person[0]["claims"]}
    assert c["funktion_bei"]["object"] == "Lvmh Moet Hennessy Louis Vuitton" and c["funktion_bei"]["attrs"]["rolle"] == "Président-directeur général"
    assert c["geburtsdatum"]["object"] == "1949-03" and c["funktion_bei"]["subject"] == ""          # Aussage über die gesuchte Person
    company = _run("fr_entreprises", "employer", "LVMH")
    officers = [x for x in company[0]["claims"] if x["predicate"] == "funktion_bei"]
    assert {o["subject"] for o in officers} == {"Bernard Arnault", "Claire Dupont"} and all(o["subject_type"] == "person" for o in officers)
    assert ("registriert_als", "SIREN 775670417") in _claims(company[0]) and ("firmenstatus", "aktiv") in _claims(company[0])


def test_risk_sources_icij_interpol_fbi():
    icij = _run("icij_online", "name", "Sergey Roldugin")
    assert len(icij) == 1 and icij[0]["url"] == "https://offshoreleaks.icij.org/nodes/12180773" and icij[0]["category"] == "Risiko"
    assert icij[0]["claims"][0]["predicate"] == "offshore_funktion" and icij[0]["claims"][0]["attrs"]["quelle_url"] == icij[0]["url"]
    red = _run("interpol_red", "name", "John Smith")
    assert red[0]["title"] == "INTERPOL Rote Ausschreibung (Fahndung): John Smith" and ("geburtsdatum", "1970-01-02") in _claims(red[0])
    fbi = _run("fbi_wanted", "name", "John Smith")
    assert [f["title"] for f in fbi] == ["FBI Wanted: John Smith"] and ("alias", "Johnny Smith") in _claims(fbi[0])   # „Smithsonian Burglary“ fällt heraus


def test_press_wikipedia_and_science_sources():
    news = _run("gdelt_news", "name", "Max Mustermann")
    assert news[0]["category"] == "Presse" and news[0]["url"] == "https://zeitung.example/hafen" and news[0]["data"]["erschienen"] == "2026-11-01"
    assert news[0]["names"] == [] and "claims" not in news[0] or not news[0].get("claims")           # Presse behauptet nichts über die Person
    http = Http({**ROUTES, "https://api.gdeltproject.org/api/v2/doc/doc": (200, b"Your query was too short")})
    with pytest.raises(SourceError):
        _run("gdelt_news", "name", "ab", http)
    wiki = _run("wikipedia", "name", "Angela Merkel")
    assert [(w["title"], w["category"]) for w in wiki] == [("Wikipedia (de): Angela Merkel", "Öffentliche Person"), ("Wikipedia (de): Kabinett Merkel I", "Erwähnung")]
    assert wiki[0]["url"] == "https://de.wikipedia.org/?curid=145" and "<span>" not in wiki[0]["snippet"]
    cr = _run("crossref", "name", "Max Mustermann")
    assert len(cr) == 1 and "1 Veröffentlichung" in cr[0]["title"] and cr[0]["data"]["institutionen"] == ["Universität Kiel"]   # Moritz M. zählt nicht
    dblp = _run("dblp", "name", "Donald E. Knuth")
    assert dblp[0]["url"].startswith("https://dblp.org/pid/") and ("arbeitet_bei", "Stanford University, USA") in _claims(dblp[0])


def test_account_sources_keybase_codeberg_dockerhub():
    kb = _run("keybase", "username", "@maxmuster")
    assert kb[0]["data"]["benutzername"] == "maxmuster" and kb[0]["data"]["verknuepfte_konten"] == ["github: maxmuster", "twitter: mmuster"]
    assert ("konto", "github: maxmuster") in _claims(kb[0]) and kb[0]["names"] == ["Max Mustermann"]
    cb = _run("codeberg", "username", "maxmuster")
    assert [c["data"]["benutzername"] for c in cb] == ["maxmuster"] and cb[0]["data"]["webseite"] == "https://mustermann.example"
    assert [c["data"]["benutzername"] for c in _run("codeberg", "name", "Max Mustermann")] == ["maxmuster"]
    dh = _run("dockerhub", "username", "maxmuster")
    assert dh[0]["data"] == {"plattform": "Docker Hub", "benutzername": "maxmuster", "organisation": "Nordhafen Projekt GmbH", "erstellt": "2016-02-03T10:00:00Z"}
    assert _run("dockerhub", "username", "gibt-es-nicht") == [] and _run("dockerhub", "username", "../../etc") == []


def test_sources_only_talk_to_their_declared_hosts():
    class Spy(Http):
        def get(self, url, headers=None):
            from urllib.parse import urlsplit
            assert urlsplit(url).hostname in allowed, url
            return super().get(url, headers)

    for s in MORE_SOURCES:
        allowed = set(s.hosts)
        s.run(*s.test_query, Spy())


def test_new_sources_feed_search_facts_and_follow_up_suggestions(tmp_path):
    app = build_app(tmp_path, http=Http())
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    cid = anna.post("/api/cases", json={"title": "Quellen", "case_type": "personensuche", "purpose": "Test der neuen Quellen im Suchablauf",
                                        "legal_basis": "Einwilligung", "opsec_level": 1,
                                        "subject": {"label": "Max Mustermann", "identifiers": [{"kind": "username", "value": "maxmuster"}]}}).json()["id"]
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    res = anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": ["dockerhub", "keybase", "gdelt_news", "crossref"]}).json()
    assert res["queries"] == 4 and res["new_findings"] == 4 and all(s["ok"] for s in res["status"])
    findings = {f["source"]: f for f in anna.get(f"/api/cases/{cid}/findings").json()}
    assert findings["Docker Hub"]["score"] > findings["Presse weltweit (GDELT)"]["score"]            # Konto mit Namen wiegt mehr als eine Erwähnung
    anna.patch(f"/api/cases/{cid}/findings/{findings['Docker Hub']['id']}", json={"status": "bestätigt"})
    piv = {(i["kind"], i["value"]) for i in anna.get(f"/api/cases/{cid}/entities/{sid}/pivots").json()["items"]}
    assert ("employer", "Nordhafen Projekt GmbH") in piv                                            # die Firma aus dem Profil wird als Folgesuche vorgeschlagen
    meta = {s["key"]: s for s in anna.get("/api/meta").json()["sources"]}
    assert meta["fr_entreprises"]["exposure"] == "passiv" and meta["keybase"]["exposure"] == "plattform" and len(meta) == 35              # 12 + 7 + 13 Online-Quellen, 3 lokale Bestände


def test_check_all_sources_reports_what_really_answers(tmp_path):
    routes = {k: v for k, v in ROUTES.items() if "lobid" in k or "dblp" in k}
    routes["https://www.abgeordnetenwatch.de/"] = (-1, None)                                        # nicht erreichbar
    routes["https://api.crossref.org/works"] = (200, {"message": {"items": []}})                    # erreichbar, aber kein Treffer
    app = build_app(tmp_path, http=Http(routes))
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    assert anna.post("/api/admin/sources/check", json={}).status_code == 403
    assert all(s["health"] is None for s in admin.get("/api/admin/sources").json()["sources"])      # vor der Prüfung wird nichts behauptet
    res = admin.post("/api/admin/sources/check", json={"keys": ["lobid_gnd", "dblp", "abgeordnetenwatch", "crossref", "companies_house"]}).json()
    state = {r["key"]: r["state"] for r in res["results"]}
    assert state == {"lobid_gnd": "ok", "dblp": "ok", "abgeordnetenwatch": "fehler", "crossref": "leer", "companies_house": "nicht_pruefbar"}
    assert res["summary"] == {"ok": 2, "leer": 1, "fehler": 1, "nicht_pruefbar": 1}
    health = {s["key"]: s["health"] for s in admin.get("/api/admin/sources").json()["sources"]}
    assert health["lobid_gnd"]["state"] == "ok" and health["lobid_gnd"]["count"] == 1 and health["wikipedia"] is None
    assert "nicht erreichbar" in health["abgeordnetenwatch"]["message"] and "Schlüssel" in health["companies_house"]["message"]
    report = admin.get("/api/admin/sources/report.md")
    assert report.status_code == 200 and "attachment" in report.headers["content-disposition"]
    text = report.content.decode()
    assert "| GND – Deutsche Nationalbibliothek (lobid) |" in text and "✓ liefert Treffer" in text and "noch nicht geprüft" in text and "✗ Fehler" in text
    assert anna.get("/api/admin/sources/report.md").status_code == 403


def test_server_option_requires_2fa_and_admits_lan_names_only(tmp_path, monkeypatch):
    from personosint import __main__ as cli

    monkeypatch.setattr(cli, "_lan_addresses", lambda: ["buero-pc", "192.168.1.20"])
    monkeypatch.setenv("EAGLEEYE_REQUIRE_2FA", "0")
    local = cli._settings(argparse.Namespace(data=str(tmp_path), server=False))
    server = cli._settings(argparse.Namespace(data=str(tmp_path), server=True))
    assert local.require_2fa is False and "buero-pc" not in local.allowed_hosts
    assert server.require_2fa is True and {"buero-pc", "192.168.1.20", "127.0.0.1"} <= set(server.allowed_hosts)   # 2FA lässt sich im Serverbetrieb nicht abschalten
    s = make_settings(tmp_path, "sqlite")
    s.allowed_hosts = tuple(server.allowed_hosts)
    app = create_app(settings=s, auto_geocode=False, start_scheduler=False)
    assert TestClient(app, base_url="http://buero-pc:8380").get("/api/auth/state", headers=H).status_code == 200
    assert TestClient(app, base_url="http://192.168.1.20:8380").get("/api/auth/state", headers=H).status_code == 200
    assert TestClient(app, base_url="http://fremd.example").get("/api/auth/state", headers=H).status_code in (400, 403, 421)
    real = cli._lan_addresses.__wrapped__() if hasattr(cli._lan_addresses, "__wrapped__") else None
    del real
