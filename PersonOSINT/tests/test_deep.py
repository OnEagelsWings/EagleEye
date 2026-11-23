"""Tiefenrecherche, Vermisstenregister, eigene Websuche, Legenden und neue Tor-Identität."""
from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from conftest import H, build_app, setup_admin
from personosint import deepsearch
from personosint.personas import alias_email, generate
from test_personosint import FakeHttp

ROUTES = {
    "https://api.github.com/users/maxmuster": (200, {"login": "maxmuster", "name": "Max Müller", "html_url": "https://github.com/maxmuster",
                                                     "company": "Beispiel GmbH", "location": "Köln", "blog": "https://maxmuster.dev",
                                                     "created_at": "2015-01-01"}),
    "https://api.fbi.gov/wanted/v1/list": (200, {"items": [
        {"title": "MAX MÜLLER", "poster_classification": "missing", "url": "https://www.fbi.gov/wanted/kidnap/max-mueller", "uid": "m1",
         "description": "Zuletzt gesehen in Ohio", "aliases": None},
        {"title": "MAX MÜLLER", "poster_classification": "default", "url": "https://www.fbi.gov/wanted/x", "uid": "w1"}]}),
}


def _case(c, case_type="vermisst", level=1):
    body = {"title": "Vermisst: Max", "case_type": case_type, "purpose": "Aufenthaltsermittlung im Auftrag der Familie",
            "legal_basis": "Einwilligung der Angehörigen", "opsec_level": level,
            "subject": {"label": "Max Müller", "identifiers": [{"kind": "username", "value": "@maxmuster"}, {"kind": "phone", "value": "0431 123456"},
                                                               {"kind": "location", "value": "Köln"}, {"kind": "email", "value": "max@maxmuster.dev"}]}}
    r = c.post("/api/cases", json=body, headers=H)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    eid = next(e["id"] for e in c.get(f"/api/cases/{cid}/entities").json() if e["type"] == "person")
    return cid, eid


def test_variants_usernames_phones_and_dorks():
    names = [v["value"] for v in deepsearch.name_variants(["Maximilian Johannes Müller"])]
    assert names[0] == "Maximilian Johannes Müller"
    assert {"Müller, Maximilian Johannes", "Maximilian Müller", "Johannes Müller", "Maximilian Johannes Mueller", "M. Müller", "Max Müller"} <= set(names)
    assert "Mueller" in " ".join(v["value"] for v in deepsearch.name_variants(["Müller, Anna"]))
    assert "Vladimir Ivanov".casefold() in [v["value"].casefold() for v in deepsearch.name_variants(["Владимир Иванов"])]
    users = deepsearch.username_candidates(["Anna Müller"], "1988")
    assert {"anna.mueller", "amueller", "annamueller88"} <= set(users)
    assert {"+49431123456", "0431123456", "0049431123456"} <= set(deepsearch.phone_variants("0431 123456"))
    prof = {"label": "Max Müller", "names": ["Max Müller"], "usernames": ["maxmuster"], "emails": ["max@maxmuster.dev"], "phones": ["0431 123456"],
            "domains": ["maxmuster.dev"], "locations": ["Köln"], "employers": [], "urls": []}
    ds = deepsearch.dorks(prof, missing=True)
    groups = {d["group"] for d in ds}
    assert {"Profile", "Dokumente", "Kontakt", "Domains", "Vermisst", "Benutzernamen"} <= groups
    assert all(len(d["links"]) == 5 and d["links"][0]["url"].startswith("https://www.google.com/search?q=") for d in ds)
    assert not any(d["group"] == "Vermisst" for d in deepsearch.dorks(prof, missing=False))


def test_missing_register_sources_filter_and_links():
    from personosint.connectors2 import MORE_SOURCES
    from personosint.sources import research_links

    fbi = next(s for s in MORE_SOURCES if s.key == "fbi_missing")
    hits = fbi.runner(fbi, "name", "Max Müller", FakeHttp(ROUTES))
    assert len(hits) == 1 and hits[0]["data"]["art"] == "missing" and hits[0]["category"] == "Vermisstenregister"
    gd = next(s for s in MORE_SOURCES if s.key == "gdelt_missing")
    http = FakeHttp({"https://api.gdeltproject.org/": (200, {"articles": [{"title": "Max Müller vermisst", "url": "https://news.example/a", "seendate": "20261101T000000Z"}]})})
    out = gd.runner(gd, "name", "Max Müller", http)
    assert out and out[0]["title"].startswith("Vermisstenmeldung") and "vermisst+OR+missing" in http.calls[0].replace("%20", "+")
    links = [l["label"] for l in research_links({"label": "Max Müller"}, [{"kind": "name", "value": "Max Müller"}], missing=True)]
    assert any("Bundesländer" in l for l in links) and any("NCMEC" in l for l in links) and any("DRK" in l for l in links)


def test_deep_plan_and_run_follow_strong_traces(tmp_path):
    http = FakeHttp(ROUTES)
    app = build_app(tmp_path, http=http)
    agents = []
    app.state.platform.http_factory = lambda prof, ua: agents.append(ua) or http   # wechselnde Kennung, aber Testantworten
    c = setup_admin(app)
    cid, eid = _case(c)
    pl = c.get(f"/api/cases/{cid}/entities/{eid}/deep/plan", params={"depth": 2, "budget": 300, "guess_usernames": 1}).json()
    keys = {q["source"] for q in pl["queries"]}
    assert {"fbi_missing", "gdelt_missing", "interpol_yellow", "github", "gravatar", "crtsh"} <= keys
    assert any(q["value"] == "Mueller, Max" or q["value"] == "Max Mueller" for q in pl["queries"])
    assert pl["guessed_usernames"] and pl["missing"] and pl["dorks"]
    assert not pl["websearch"]["available"] and "SearXNG" in pl["websearch"]["reason"]
    job = c.post(f"/api/cases/{cid}/entities/{eid}/deep/start", json={"depth": 2, "budget": 300, "rotate_identity": True}, headers=H).json()
    for _ in range(200):
        state = c.get(f"/api/cases/{cid}/deep/{job['id']}").json()
        if state["state"] != "läuft":
            break
        time.sleep(0.1)
    assert state["state"] == "fertig", state["log"]
    assert state["used"] > 20 and state["new_findings"] >= 2
    assert len(agents) >= 3 and all(a in deepsearch.USER_AGENTS for a in agents)      # je Abfragepaket eine Browserkennung
    assert any("maxmuster.dev" in f for f in state["followed"]) and state["round"] == 2, state["log"]
    findings = c.get(f"/api/cases/{cid}/findings").json()
    assert any("vermisst" in f["title"].lower() for f in findings)
    searches = c.get(f"/api/cases/{cid}/searches").json()
    assert all((s.get("pivot") or {}).get("deep") == job["id"] for s in searches)
    # schon abgefragte Varianten werden nicht erneut eingeplant
    again = c.get(f"/api/cases/{cid}/entities/{eid}/deep/plan", params={"depth": 1}).json()
    assert len(again["queries"]) < len(pl["queries"]) and again["skipped"]["done"] > 0
    assert c.get(f"/api/cases/{cid}/deep/unbekannt").status_code == 404


def test_opsec_level_limits_deep_plan(tmp_path):
    app = build_app(tmp_path, http=FakeHttp(ROUTES))
    c = setup_admin(app)
    cid, eid = _case(c, level=3)
    pl = c.get(f"/api/cases/{cid}/entities/{eid}/deep/plan").json()
    assert pl["opsec_level"] == 3 and pl["queries"]
    r = c.post(f"/api/cases/{cid}/entities/{eid}/deep/start", json={"depth": 1}, headers=H)
    assert r.status_code == 428 and "Briefing" in r.json()["detail"]                 # Stufe 3: erst Briefing
    assert c.post(f"/api/cases/{cid}/opsec/briefing", json={}, headers=H).status_code == 200
    job = c.post(f"/api/cases/{cid}/entities/{eid}/deep/start", json={"depth": 1}, headers=H).json()
    for _ in range(100):
        st = c.get(f"/api/cases/{cid}/deep/{job['id']}").json()
        if st["state"] != "läuft":
            break
        time.sleep(0.05)
    assert st["state"] == "fehler" and "Anonymisierungs-Ausgang" in st["log"][-1]["text"]   # nie direkt senden
    assert not c.get(f"/api/cases/{cid}/findings").json()


def test_websearch_dorks_via_own_searxng(tmp_path):
    seen = []

    class Searx(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            seen.append(self.path)
            body = json.dumps({"results": [{"url": "https://forum.example/thread/1", "title": "Max Müller im Forum", "content": "…", "engines": ["bing"]},
                                           {"url": "javascript:alert(1)", "title": "böse"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Searx)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        app = build_app(tmp_path, http=FakeHttp(ROUTES))
        c = setup_admin(app)
        cid, eid = _case(c, case_type="personensuche")
        assert c.post("/api/admin/websearch", json={"url": "ftp://x"}, headers={**H}).status_code == 422
        r = c.post("/api/admin/websearch", json={"url": f"http://127.0.0.1:{server.server_address[1]}", "anonymized": False}, headers=H)
        assert r.status_code == 200, r.text
        pl = c.get(f"/api/cases/{cid}/entities/{eid}/deep/plan").json()
        assert pl["websearch"]["available"]
        job = c.post(f"/api/cases/{cid}/entities/{eid}/deep/start", json={"depth": 1, "budget": 600, "run_dorks": True}, headers=H).json()
        for _ in range(300):
            st = c.get(f"/api/cases/{cid}/deep/{job['id']}").json()
            if st["state"] != "läuft":
                break
            time.sleep(0.1)
        assert st["state"] == "fertig", st["log"]
        assert seen and all("format=json" in s for s in seen)
        web = [f for f in c.get(f"/api/cases/{cid}/findings").json() if f["title"].startswith("Web:")]
        assert len(web) == 1 and web[0]["url"] == "https://forum.example/thread/1"     # unsichere Links werden verworfen
    finally:
        server.shutdown()


def test_personas_generate_store_encrypted_and_warn(tmp_path):
    assert alias_email("{user}@alias.example.org", "anna.b88") == "anna.b88@alias.example.org"
    assert "@meine.example" in alias_email("recherche+{token}@meine.example", "x")
    g = generate("{user}@alias.example.org")
    assert g["email_alias"].startswith(g["username"]) and g["codename"] and 1972 <= int(g["birth_year"]) <= 2001
    app = build_app(tmp_path, http=FakeHttp(ROUTES))
    c = setup_admin(app)
    assert c.post("/api/personas/settings", json={"email_pattern": "ohne-at"}, headers=H).status_code == 422
    assert c.post("/api/personas/settings", json={"email_pattern": "{user}@alias.example.org"}, headers=H).status_code == 200
    sug = c.post("/api/personas/generate", json={}, headers=H).json()
    assert sug["email_alias"].endswith("@alias.example.org")
    r = c.post("/api/personas", json={**sug, "secret": "Instagram: GeheimesPasswort-9911", "platforms": ["Instagram"]}, headers=H)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    assert r.json()["has_secret"] and "secret_enc" not in r.json()
    raw = app.state.platform.db.one("SELECT secret_enc FROM personas WHERE id = ?", (pid,))["secret_enc"]
    assert "GeheimesPasswort" not in raw
    assert c.get(f"/api/personas/{pid}/secret").json()["secret"] == "Instagram: GeheimesPasswort-9911"
    first, _ = _case(c)
    second, _ = _case(c)
    assert c.post(f"/api/personas/{pid}/use", json={"case_id": first, "purpose": "Profil ansehen"}, headers=H).json()["warnings"] == []
    warn = c.post(f"/api/personas/{pid}/use", json={"case_id": second, "purpose": "Profil ansehen"}, headers=H).json()["warnings"]
    assert warn and "anderen Fall" in warn[0]
    assert [p["id"] for p in c.get(f"/api/cases/{second}/personas").json()] == [pid]
    c.put(f"/api/personas/{pid}", json={"status": "verbrannt"}, headers=H)
    assert c.post(f"/api/personas/{pid}/use", json={"case_id": first}, headers=H).status_code == 422


def test_tor_new_identity_via_control_port(tmp_path):
    got = []
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def serve():
        conn, _ = srv.accept()
        got.append(conn.recv(1024).decode())
        conn.sendall(b"250 OK\r\n250 OK\r\n250 closing connection\r\n")
        conn.close()

    threading.Thread(target=serve, daemon=True).start()
    app = build_app(tmp_path, http=FakeHttp(ROUTES))
    c = setup_admin(app)
    r = c.post("/api/admin/websearch", json={"url": "", "tor_control": {"host": "127.0.0.1", "port": srv.getsockname()[1], "password": "geheim"}}, headers=H)
    assert r.status_code == 200 and r.json()["tor_control"]["password"] == "***"
    assert app.state.platform.renew_identity() is True
    assert 'AUTHENTICATE "geheim"' in got[0] and "SIGNAL NEWNYM" in got[0]
    srv.close()
