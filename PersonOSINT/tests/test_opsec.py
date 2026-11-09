"""OPSEC-Struktur: Stufen, Netzausgang (fail closed), Spurenkontrolle, Metadaten, Exporte, Briefing."""
from __future__ import annotations

import io
import json
import socket
import threading
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import add_user, build_app, setup_admin
from personosint.opsec import LEVELS, EgressProfile
from personosint.sources import Http
from test_personosint import ROUTES, FakeHttp

INV = {"title": "Recherche Hafenprojekt", "case_type": "investigativ", "purpose": "Investigative Recherche zu Beteiligungen",
       "legal_basis": "Journalistische Recherche (Medienprivileg)",
       "subject": {"label": "Max Mustermann", "identifiers": [{"kind": "username", "value": "maxmuster"}]}}


# ---------------------------------------------------------------- lokaler Test-Proxy & Zielserver

class _Target(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = json.dumps({"ok": True, "path": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class _Proxy(BaseHTTPRequestHandler):
    seen: list[tuple[str, str]] = []

    def do_GET(self):  # noqa: N802 – Weiterleitungs-Proxy für http://
        _Proxy.seen.append((self.path, self.headers.get("User-Agent", "")))
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(self.path, timeout=5) as r:
            body = r.read()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _serve(handler) -> tuple[ThreadingHTTPServer, int]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def proxy():
    _Proxy.seen = []
    srv, port = _serve(_Proxy)
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


# ---------------------------------------------------------------- Netzausgang

def test_proxy_profile_routes_everything_through_proxy(proxy, monkeypatch):
    target, tport = _serve(_Target)
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")      # Systemausnahmen dürfen NICHT greifen
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    http = Http(profile=EgressProfile("p1", "Testproxy", "proxy", proxy), user_agent="Mozilla/5.0")
    r = http.get(f"http://127.0.0.1:{tport}/probe?q=1")
    assert r.status == 200 and json.loads(r.body)["path"] == "/probe?q=1"
    assert _Proxy.seen == [(f"http://127.0.0.1:{tport}/probe?q=1", "Mozilla/5.0")]
    target.shutdown()


def _setup_case(tmp_path, backend="sqlite", level=2):
    http = FakeHttp(ROUTES)
    app = build_app(tmp_path, backend, http=http)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    case = anna.post("/api/cases", json={**INV, "opsec_level": level}).json()
    return app, http, admin, anna, case


def test_level2_fail_closed_and_egress_log(tmp_path, backend, proxy):
    app, http, admin, anna, case = _setup_case(tmp_path, backend, level=2)
    cid = case["id"]
    assert case["opsec_level"] == 2 and case["codename"]            # Deckname automatisch
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    search = lambda: anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": ["github", "wikidata"]})

    r = search()
    assert r.status_code == 428 and "Briefing" in r.json()["detail"]
    st = anna.post(f"/api/cases/{cid}/opsec/briefing").json()
    assert st["briefing_done"] and st["acks"][0]["display_name"] == "Anna"

    r = search()                                                   # Standard-Ausgang = direkt -> blockiert
    assert r.status_code == 428 and "Direktabfragen" in r.json()["detail"]

    dead = admin.post("/api/admin/egress-profiles", json={"name": "Tor (aus)", "proxy_url": f"http://127.0.0.1:{_free_port()}"}).json()
    assert anna.patch(f"/api/cases/{cid}", json={"egress_profile": dead["id"]}).status_code == 200
    r = search()
    assert r.status_code == 428 and "nicht erreichbar" in r.json()["detail"]
    assert http.calls == []                                        # nichts ist direkt hinausgegangen

    live = admin.post("/api/admin/egress-profiles", json={"name": "Recherche-Proxy", "proxy_url": proxy}).json()
    seen_ua = []
    app.state.platform.http_factory = lambda prof, ua: (seen_ua.append((prof.name, ua)), http)[1]
    anna.patch(f"/api/cases/{cid}", json={"egress_profile": live["id"]})
    r = search()
    assert r.status_code == 200, r.text
    assert r.json()["egress"] == "Recherche-Proxy" and r.json()["new_findings"] >= 2
    assert seen_ua == [("Recherche-Proxy", "Mozilla/5.0")]       # neutraler User-Agent ab Stufe 2

    st = anna.get(f"/api/cases/{cid}/opsec").json()
    assert st["totals"]["requests"] == len(http.calls) and st["totals"]["direct_requests"] == 0
    hosts = {h["host"]: h for h in st["hosts"]}
    assert hosts["www.wikidata.org"]["exposure"] == "passiv" and hosts["api.github.com"]["exposure"] == "plattform"
    assert all(h["egress"] == "Recherche-Proxy" for h in st["hosts"])
    assert admin.delete(f"/api/admin/egress-profiles/{live['id']}").status_code == 422   # noch in Benutzung


def test_level3_rules(tmp_path):
    app, http, admin, anna, case = _setup_case(tmp_path, level=3)
    cid = case["id"]
    lea = add_user(admin, app, "lea", "leser")
    assert case["restricted"] == 1 and case["codename"]
    assert anna.patch(f"/api/cases/{cid}", json={"restricted": False}).status_code == 422
    # Liste zeigt nur den Decknamen
    listed = next(c for c in anna.get("/api/cases").json() if c["id"] == cid)
    assert listed["display_name"] == case["codename"] and listed["subject_label"] is None and "Hafenprojekt" not in json.dumps(listed)
    # keine automatische Verortung (OSM erfährt nichts)
    anna.post(f"/api/cases/{cid}/opsec/briefing")
    app.state.platform.auto_geocode = True
    anna.post(f"/api/cases/{cid}/entities", json={"type": "ort", "label": "Geheimer Treffpunkt"})
    assert http.calls == []
    # sichtbare Recherchelinks gesperrt
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    links = anna.get(f"/api/cases/{cid}/entities/{sid}/research-links").json()
    linkedin = next(lk for lk in links if "LinkedIn" in lk["label"])
    assert linkedin["exposure"] == "sichtbar" and linkedin["blocked"] and linkedin["url"] == ""
    assert next(lk for lk in links if "Google:" in lk["label"]).get("blocked") is None
    # Export: Leserin darf auf Stufe 3 nicht, Verantwortliche schon – mit Kennung und ohne Metadaten
    anna.put(f"/api/cases/{cid}/members", json={"members": [{"user_id": lea.uid, "role": "leser"}]})
    assert lea.get(f"/api/cases/{cid}/export/dossier.docx").status_code == 403
    d = anna.get(f"/api/cases/{cid}/export/dossier.docx")
    assert d.status_code == 200 and case["codename"] in d.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(d.content)) as z:
        core = z.read("docProps/core.xml").decode()
        footer = " ".join(z.read(n).decode() for n in z.namelist() if n.startswith("word/footer"))
        header = " ".join(z.read(n).decode() for n in z.namelist() if n.startswith("word/header"))
    assert "python-docx" not in core and "Anna" not in core and case["codename"] in core
    st = anna.get(f"/api/cases/{cid}/opsec").json()
    export_id = st["exports"][0]["export_id"]
    assert export_id in footer and "OPSEC-Stufe 3" in footer and "Max Mustermann" not in header
    assert len(st["exports"][0]["sha256"]) == 64


def test_lowering_level_needs_reason_and_is_logged(tmp_path):
    app, http, admin, anna, case = _setup_case(tmp_path, level=3)
    cid = case["id"]
    assert anna.patch(f"/api/cases/{cid}", json={"opsec_level": 1}).status_code == 422
    assert anna.patch(f"/api/cases/{cid}", json={"opsec_level": 1, "opsec_reason": "Recherche veröffentlicht, Quelle geschützt"}).status_code == 200
    log = anna.get(f"/api/cases/{cid}/audit").json()
    assert any(a["action"] == "OPSEC-Stufe geändert" and "3 → 1" in a["detail"] and "veröffentlicht" in a["detail"] for a in log)


def test_photo_metadata_removed(tmp_path):
    from PIL import Image
    app, http, admin, anna, case = _setup_case(tmp_path, level=1)
    cid = case["id"]
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    img = Image.new("RGB", (30, 20), (200, 10, 10))
    exif = Image.Exif()
    exif[0x010F] = "GeheimKamera"                                # Hersteller
    exif[0x0132] = "2026:11:01 10:00:00"                         # Aufnahmezeit
    exif[0x8825] = {1: "N", 2: (53.0, 33.0, 0.0), 3: "E", 4: (9.0, 59.0, 0.0)}  # GPS
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    raw = buf.getvalue()
    assert b"GeheimKamera" in raw
    r = anna.post(f"/api/cases/{cid}/entities/{sid}/photo", files={"file": ("quelle.jpg", raw, "image/jpeg")})
    assert r.status_code == 200
    stored = anna.get(f"/api/cases/{cid}/entities/{sid}/photo").content
    assert b"GeheimKamera" not in stored and not Image.open(io.BytesIO(stored)).getexif()
    log = anna.get(f"/api/cases/{cid}/audit").json()
    detail = next(a["detail"] for a in log if a["action"] == "Foto hinterlegt")
    assert "GPS-Position" in detail and "Kameramodell" in detail


def test_egress_profiles_secret_at_rest_and_in_backup(tmp_path, proxy):
    from personosint.backup import create_backup, restore_backup
    from personosint.api import open_database
    from personosint.crypto import Vault
    from conftest import make_settings

    app = build_app(tmp_path / "a")
    admin = setup_admin(app)
    secret_url = proxy.replace("http://", "http://user:GeheimesPw@")
    prof = admin.post("/api/admin/egress-profiles", json={"name": "VPN-Gateway", "proxy_url": secret_url}).json()
    assert "GeheimesPw" not in prof["proxy_url"] and "***" in prof["proxy_url"]
    raw = app.state.platform.db.scalar("SELECT value FROM settings WHERE key = 'egress_profiles'")
    assert "GeheimesPw" not in raw and "VPN-Gateway" not in raw   # verschlüsselt gespeichert
    # Bearbeiten mit maskierter URL behält das Passwort
    admin.post("/api/admin/egress-profiles", json={"id": prof["id"], "name": "VPN-Gateway 2", "proxy_url": prof["proxy_url"]})
    assert app.state.platform.egress_profile(prof["id"]).proxy_url == secret_url
    assert admin.put("/api/admin/opsec-settings", json={"default_egress": prof["id"], "default_level": 2}).status_code == 200
    # Sicherung -> neue Installation mit anderem Schlüssel
    p = app.state.platform
    bk = create_backup(p.db, p.vault, tmp_path / "a", tmp_path / "bk", passphrase="lange Passphrase 123")
    s2 = make_settings(tmp_path / "b", "sqlite")
    db2, v2 = open_database(s2), Vault(s2.resolved_key_file)
    restore_backup(bk, db2, v2, tmp_path / "b", passphrase="lange Passphrase 123")
    from personosint.service import Platform
    p2 = Platform(db2, tmp_path / "b", vault=v2)
    assert p2.egress_profile(prof["id"]).proxy_url == secret_url
    assert p2.opsec_settings() == {"default_egress": prof["id"], "default_level": 2}


def test_levels_are_strictly_ordered():
    a, b, c = LEVELS[1], LEVELS[2], LEVELS[3]
    assert not a.require_egress and b.require_egress and c.require_egress
    assert a.max_exposure >= b.max_exposure >= c.max_exposure and a.max_link_exposure > b.max_link_exposure > c.max_link_exposure
    assert c.force_restricted and not c.auto_geocode and "leser" not in c.export_roles
