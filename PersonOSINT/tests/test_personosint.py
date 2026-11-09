"""Ende-zu-Ende-Tests für EagleEye PersonOSINT (Quellen werden simuliert, kein Netzzugriff)."""
from __future__ import annotations

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from personosint.api import create_app
from personosint.matching import name_similarity, normalize, score_candidate
from personosint.sources import HttpResponse, SourceError, research_links

H = {"X-Requested-With": "EagleEye"}


class FakeHttp:
    """Liefert vorbereitete Antworten je URL-Präfix; alles andere = 404."""

    def __init__(self, routes: dict[str, tuple[int, object]]):
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url: str, headers=None) -> HttpResponse:
        self.calls.append(url)
        for prefix, (status, body) in self.routes.items():
            if url.startswith(prefix):
                if status == -1:
                    raise SourceError("Quelle nicht erreichbar: simuliert")
                raw = body if isinstance(body, bytes) else json.dumps(body).encode()
                return HttpResponse(status, raw, url)
        return HttpResponse(404, b"", url)


ROUTES = {
    "https://api.github.com/users/maxmuster": (200, {"login": "maxmuster", "name": "Max Mustermann", "html_url": "https://github.com/maxmuster",
                                                      "bio": "Entwickler", "company": "@Beispiel GmbH", "location": "Köln", "created_at": "2015-01-01"}),
    "https://api.github.com/search/users": (200, {"items": [{"login": "mmustermann", "html_url": "https://github.com/mmustermann"}]}),
    "https://www.wikidata.org/": (200, {"search": [{"id": "Q1", "label": "Max Mustermann", "description": "fiktive Beispielperson", "concepturi": "https://www.wikidata.org/entity/Q1"},
                                                    {"id": "Q2", "label": "Erika Musterfrau", "description": "andere Person", "concepturi": "https://www.wikidata.org/entity/Q2"}]}),
    "https://lichess.org/api/user/maxmuster": (200, {"id": "maxmuster"}),
    "https://hacker-news.firebaseio.com/v0/user/maxmuster.json": (200, b"null"),
    "https://ws-public.interpol.int/": (200, {"_embedded": {"notices": []}}),
    "https://api.openalex.org/": (-1, None),
}


@pytest.fixture()
def client(tmp_path):
    http = FakeHttp(ROUTES)
    app = create_app(tmp_path, http=http, auto_geocode=False)
    c = TestClient(app)
    c.http = http  # type: ignore[attr-defined]
    return c


def make_case(c, **kw):
    payload = {"title": "Testfall", "case_type": "personensuche", "purpose": "Aufenthaltsermittlung im Testauftrag",
               "legal_basis": "Einwilligung", "subject": {"label": "Max Mustermann", "identifiers": [
                   {"kind": "username", "value": "@MaxMuster"}, {"kind": "location", "value": "Köln"}, {"kind": "employer", "value": "Beispiel GmbH"}]}}
    payload.update(kw)
    r = c.post("/api/cases", json=payload, headers=H)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- Einheiten

def test_normalize_and_similarity():
    assert normalize("phone", "0170 / 123 456") == "+49170123456"
    assert normalize("phone", "0044 20 1234") == "+44201234"
    assert normalize("username", "@MaxMuster") == "maxmuster"
    assert normalize("name", "Dr. Jürgen Müller") == "juergen mueller"
    assert name_similarity("Jürgen Müller", "Juergen Mueller") == 1.0
    assert name_similarity("Max Mustermann", "Mustermann, Max") >= 0.97
    assert name_similarity("Max Mustermann", "Erika Musterfrau") < 0.85


def test_score_explains_reasons():
    subj = {"label": "Max Mustermann", "data": {"geburtsdatum": "1990-05-01"}}
    idents = [{"kind": "name", "normalized": "max mustermann"}, {"kind": "location", "normalized": "koeln"}]
    s_good, r_good = score_candidate(subj, idents, {"names": ["Max Mustermann"], "title": "Max Mustermann", "snippet": "lebt in Köln, geb. 1990", "match_kind": "name"})
    s_bad, r_bad = score_candidate(subj, idents, {"names": ["Erika Musterfrau"], "title": "Erika", "snippet": "Berlin", "match_kind": "name"})
    assert s_good >= 60 and any("Ort" in r for r in r_good) and any("1990" in r for r in r_good)
    assert s_bad < 20 and any("weicht" in r for r in r_bad)


def test_research_links_missing_person():
    links = research_links({"label": "Max Mustermann"}, [{"kind": "username", "value": "maxmuster"}, {"kind": "location", "value": "Köln"}], missing=True)
    groups = {l["group"] for l in links}
    assert {"Suchmaschinen", "Soziale Netzwerke", "Vermisstenfälle", "Bildersuche", "Benutzernamen"} <= groups
    assert all(l["url"].startswith("https://") for l in links)


# ---------------------------------------------------------------- API / Ablauf

def test_case_requires_purpose_and_legal_basis(client):
    r = client.post("/api/cases", json={"title": "X", "case_type": "personensuche", "purpose": "kurz", "legal_basis": ""}, headers=H)
    assert r.status_code == 422
    assert "Zweck" in r.json()["detail"]


def test_write_requests_need_client_header_and_local_host(client):
    assert client.post("/api/cases", json={}).status_code == 403
    assert client.get("/api/cases", headers={"host": "evil.example"}).status_code == 400


def test_full_person_search_flow(client):
    case = make_case(client)
    cid = case["id"]
    subj = client.get(f"/api/cases/{cid}/overview").json()["subject"]
    assert {i["kind"] for i in subj["identifiers"]} >= {"name", "username", "location", "employer"}

    r = client.post(f"/api/cases/{cid}/search", json={"entity_id": subj["id"], "sources": ["github", "wikidata", "username_presence", "openalex"]}, headers=H)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["new_findings"] >= 4
    failed = [s for s in res["status"] if not s["ok"]]
    assert failed and failed[0]["source"] == "OpenAlex"  # defekte Quelle bricht Suche nicht ab

    findings = client.get(f"/api/cases/{cid}/findings").json()
    gh = next(f for f in findings if f["url"] == "https://github.com/maxmuster")
    assert gh["score"] >= 75 and gh["confidence"] == "hoch"
    erika = next(f for f in findings if "Erika" in f["title"])
    assert erika["score"] < gh["score"]
    titles = " ".join(f["title"] for f in findings)
    assert "Lichess" in titles and "Hacker News" not in titles  # "null" = nicht vorhanden

    # Wiederholte Suche erzeugt keine Duplikate
    again = client.post(f"/api/cases/{cid}/search", json={"entity_id": subj["id"], "sources": ["github"]}, headers=H).json()
    assert again["new_findings"] == 0

    # Bestätigen -> Konto + Organisation im Graphen
    r = client.patch(f"/api/cases/{cid}/findings/{gh['id']}", json={"status": "bestätigt", "note": "Profilfoto passt"}, headers=H)
    assert r.status_code == 200 and r.json()["created"]
    graph = client.get(f"/api/cases/{cid}/graph").json()
    labels = {n["label"] for n in graph["nodes"]}
    assert "GitHub: maxmuster" in labels and "Beispiel GmbH" in labels
    assert {e["relation"] for e in graph["edges"]} >= {"besitzt Konto", "arbeitet bei"}
    client.patch(f"/api/cases/{cid}/findings/{erika['id']}", json={"status": "verworfen"}, headers=H)

    ov = client.get(f"/api/cases/{cid}/overview").json()
    assert ov["counts"]["confirmed"] == 1 and ov["counts"]["rejected"] == 1
    assert next(s for s in ov["steps"] if s["key"] == "search")["done"]


def test_connections_paths_and_suggestions(client):
    cid = make_case(client, case_type="verbindungen")["id"]
    ids = {}
    for name, idents in [("Anna Beispiel", [{"kind": "phone", "value": "0170 1111111"}]), ("Bert Beispiel", [{"kind": "phone", "value": "+49 170 1111111"}]),
                         ("Carla Test", []), ("Dora Test", [])]:
        ids[name] = client.post(f"/api/cases/{cid}/entities", json={"type": "person", "label": name, "identifiers": idents}, headers=H).json()["id"]
    firma = client.post(f"/api/cases/{cid}/entities", json={"type": "organisation", "label": "Testfirma"}, headers=H).json()["id"]
    subj = client.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    for s, t, rel, conf in [(subj, ids["Anna Beispiel"], "befreundet mit", 80), (ids["Anna Beispiel"], ids["Carla Test"], "Kollege/Kollegin von", 60),
                            (ids["Carla Test"], ids["Dora Test"], "verwandt mit", 90), (subj, firma, "arbeitet bei", 70), (ids["Dora Test"], firma, "arbeitet bei", 40),
                            (ids["Carla Test"], firma, "arbeitet bei", 50)]:
        assert client.post(f"/api/cases/{cid}/links", json={"source_id": s, "target_id": t, "relation": rel, "confidence": conf}, headers=H).status_code == 201
    paths = client.get(f"/api/cases/{cid}/paths", params={"a": subj, "b": ids["Dora Test"]}).json()
    assert paths["shortest_length"] == 2
    assert paths["paths"][0]["labels"] == ["Max Mustermann", "Testfirma", "Dora Test"]
    assert any(p["length"] == 3 for p in paths["paths"])
    assert 0 < paths["paths"][0]["combined_confidence"] <= 100

    sugg = client.get(f"/api/cases/{cid}/suggestions").json()
    reasons = " | ".join(s["reason"] for s in sugg)
    assert "Telefon" in reasons  # gleiche Nummer, unterschiedlich geschrieben
    assert any("gemeinsame Verbindungen" in s["reason"] for s in sugg)

    graph = client.get(f"/api/cases/{cid}/graph").json()
    assert graph["key_nodes"][0]["label"] in {"Testfirma", "Max Mustermann", "Carla Test", "Anna Beispiel"}
    png = client.get(f"/api/cases/{cid}/graph.png")
    assert png.status_code == 200 and png.content[:8] == b"\x89PNG\r\n\x1a\n"

    assert client.post(f"/api/cases/{cid}/links", json={"source_id": subj, "target_id": subj}, headers=H).status_code == 422


def test_missing_person_module_and_exports(client, tmp_path):
    case = make_case(client, case_type="vermisst", title="Vermisst: Max")
    cid = case["id"]
    tasks = client.get(f"/api/cases/{cid}/tasks").json()
    assert any("Krankenhäuser" in t["title"] for t in tasks)  # Leitfaden automatisch erzeugt
    subj = client.get(f"/api/cases/{cid}/overview").json()["subject"]
    r = client.patch(f"/api/cases/{cid}/entities/{subj['id']}", json={"data": {
        "geburtsdatum": "2015-01-01", "vermisst_seit": "2026-11-01", "zuletzt_gesehen_ort": "Köln Hbf", "kleidung": "rote Jacke",
        "risiko": ["medizinisch"]}}, headers=H)
    risk = r.json()["risk"]
    assert risk["level"] == "hoch" and any(f["key"] == "kind" for f in risk["factors"])

    ev = client.post(f"/api/cases/{cid}/events", json={"occurred_at": "2026-11-01T18:00", "kind": "Letzte Sichtung", "location": "Köln Hbf",
                                                       "lat": 50.943, "lon": 6.958, "entity_id": subj["id"], "reliability": "bestätigt"}, headers=H)
    assert ev.status_code == 201

    # Foto hochladen
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (60, 80), (200, 120, 90)).save(buf, "PNG")
    up = client.post(f"/api/cases/{cid}/entities/{subj['id']}/photo", files={"file": ("foto.png", buf.getvalue(), "image/png")}, headers=H)
    assert up.status_code == 200 and up.json()["photo"]
    bad = client.post(f"/api/cases/{cid}/entities/{subj['id']}/photo", files={"file": ("x.png", b"keinbild", "image/png")}, headers=H)
    assert bad.status_code == 422

    client.post(f"/api/cases/{cid}/findings", json={"entity_id": subj["id"], "title": "Wurde am Bahnhof gesehen", "url": "https://example.org/hinweis",
                                                    "confirmed": True}, headers=H)
    d = client.get(f"/api/cases/{cid}/export/dossier.docx")
    assert d.status_code == 200 and "Dossier_Max_Mustermann" in d.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(d.content)) as z:
        xml = z.read("word/document.xml").decode()
        media = [n for n in z.namelist() if n.startswith("word/media/")]
    for needle in ("Vermisstendossier", "Vermisstenangaben", "Gefährdungseinschätzung", "Zeitleiste", "Wurde am Bahnhof gesehen",
                   "Quellenverzeichnis", "Aufenthaltsermittlung im Testauftrag", "rote Jacke"):
        assert needle in xml, needle
    assert len(media) >= 2  # Foto + Netzwerkgrafik

    poster = client.get(f"/api/cases/{cid}/export/poster.docx")
    with zipfile.ZipFile(io.BytesIO(poster.content)) as z:
        pxml = z.read("word/document.xml").decode()
    assert "VERMISST" in pxml and "Köln Hbf" in pxml

    audit = client.get(f"/api/cases/{cid}/audit").json()
    assert {"Fall angelegt", "Dossier exportiert", "Suchplakat exportiert", "Foto hinterlegt"} <= {a["action"] for a in audit}
    exported = json.loads(client.get(f"/api/cases/{cid}/export/case.json").content)
    assert exported["case"]["reference"] == case["reference"]

    # Löschen entfernt Fall samt Foto
    assert client.delete(f"/api/cases/{cid}", headers=H).status_code == 204
    assert not list((tmp_path / "photos").iterdir())
    assert client.get(f"/api/cases/{cid}").status_code == 404


def test_demo_case_and_ui(client):
    r = client.post("/api/demo", headers=H)
    assert r.status_code == 201
    cid = r.json()["id"]
    ov = client.get(f"/api/cases/{cid}/overview").json()
    assert ov["subject"]["label"] == "Lena Hoffmann" and ov["counts"]["links"] >= 10
    page = client.get("/")
    assert page.status_code == 200 and "EagleEye" in page.text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/vendor/leaflet/leaflet.js").status_code == 200


def test_username_partial_match_not_counted():
    subj = {"label": "Max Mustermann", "data": {}}
    idents = [{"kind": "username", "normalized": "maxmuster"}]
    _, reasons = score_candidate(subj, idents, {"names": [], "title": "GitHub: MaxMustermann111", "snippet": "", "match_kind": "name"})
    assert not any("Benutzername" in r for r in reasons)
    _, reasons = score_candidate(subj, idents, {"names": [], "title": "Profil von @maxmuster", "snippet": "", "match_kind": "name"})
    assert any("Benutzername" in r for r in reasons)
