"""Sicherheitsprüfung: Zugriffsschutz aller Endpunkte und Regressionstests für die behobenen Befunde."""
from __future__ import annotations

import io
import re
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi.testclient import TestClient

from conftest import ADMIN_PW, H, add_user, build_app, login, setup_admin
from personosint.auth import totp_code
from personosint.sources import Http
from test_personosint import FakeHttp

PUBLIC = {"/api/auth/state", "/api/auth/setup", "/api/auth/login", "/api/auth/logout"}


def _routes(app):
    for r in app.routes:
        path = getattr(r, "path", "")
        if path.startswith("/api/") and path not in PUBLIC and path != "/api/docs" and not path.startswith("/api/docs"):
            for m in sorted(getattr(r, "methods", set()) - {"HEAD", "OPTIONS"}):
                yield m, re.sub(r"\{[^}]+\}", "1", path), path


def test_every_api_endpoint_requires_login_and_admin_endpoints_require_admin(tmp_path):
    app = build_app(tmp_path)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    anon = TestClient(app)
    checked = 0
    for method, url, raw in _routes(app):
        if raw in {"/api/openapi.json"} or raw.startswith("/openapi"):
            continue
        r = anon.request(method, url, json={}, headers=H)
        assert r.status_code == 401, (method, raw, r.status_code, r.text[:120])
        if raw.startswith("/api/admin/"):
            r2 = anna.request(method, url, json={})
            assert r2.status_code in {403, 404, 422} and r2.status_code != 200, (method, raw, r2.status_code)
            assert r2.status_code == 403 or "Administration" in r2.text or r2.status_code == 404, (method, raw, r2.text[:120])
        checked += 1
    assert checked > 80


def test_redirect_to_internal_target_is_blocked():
    hits = []

    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            hits.append(self.path)
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    r = Http(timeout=5).get(f"http://127.0.0.1:{srv.server_address[1]}/start")
    srv.shutdown()
    assert r.status == 403 and hits == ["/start"]


def test_javascript_links_from_sources_are_dropped(tmp_path):
    routes = {"https://mastodon.social/api/v2/search": (200, {"accounts": [
        {"acct": "evil@evil.example", "display_name": "Max Mustermann", "url": "javascript:alert(document.cookie)", "note": ""}]})}
    app = build_app(tmp_path, http=FakeHttp(routes))
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    cid = anna.post("/api/cases", json={"title": "X", "case_type": "personensuche", "purpose": "Testrecherche zum Schutz",
                                        "legal_basis": "Einwilligung", "opsec_level": 1, "subject": {"label": "Max Mustermann"}}).json()["id"]
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": ["mastodon"]})
    f = anna.get(f"/api/cases/{cid}/findings").json()[0]
    assert f["url"] == ""
    m = anna.post(f"/api/cases/{cid}/findings", json={"entity_id": sid, "title": "Hinweis", "url": "javascript:alert(1)"}).json()
    assert m["url"] == ""


def test_csv_formula_injection_in_evidence_manifest(tmp_path):
    page = b"<html><head><title>=HYPERLINK(\"http://evil\",\"x\")</title></head><body>x</body></html>"
    app = build_app(tmp_path, http=FakeHttp({"https://example.com/p": (200, page), "https://archive.org/": (404, b"")}))
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    cid = anna.post("/api/cases", json={"title": "X", "case_type": "personensuche", "purpose": "Testrecherche zum Schutz",
                                        "legal_basis": "Einwilligung", "opsec_level": 1}).json()["id"]
    assert anna.post(f"/api/cases/{cid}/evidence", json={"url": "https://example.com/p"}).status_code == 201
    z = zipfile.ZipFile(io.BytesIO(anna.get(f"/api/cases/{cid}/export/beweispaket.zip").content))
    csv_text = z.read("manifest.csv").decode()
    assert "'=HYPERLINK" in csv_text and ";=HYPERLINK" not in csv_text and ';"=HYPERLINK' not in csv_text


def test_totp_code_cannot_be_replayed(tmp_path):
    app = build_app(tmp_path, require_2fa=True)
    admin = setup_admin(app)
    secret = admin.post("/api/auth/totp/begin").json()["secret"].replace(" ", "")
    code = totp_code(secret)
    assert admin.post("/api/auth/totp/confirm", json={"code": code}).status_code == 200
    again = login(app, "admin", ADMIN_PW)
    r = again.post("/api/auth/mfa", json={"code": code})          # derselbe Code noch im Zeitfenster
    assert r.status_code == 422 and "bereits verwendet" in r.json()["detail"]


def test_login_throttled_per_ip_address(tmp_path):
    app = build_app(tmp_path)
    setup_admin(app)
    c = TestClient(app)
    for i in range(20):
        assert c.post("/api/auth/login", json={"username": f"user{i}", "password": "x"}, headers=H).status_code == 401
    assert c.post("/api/auth/login", json={"username": "admin", "password": ADMIN_PW}, headers=H).status_code == 429


def test_remote_first_setup_requires_code(tmp_path):
    app = build_app(tmp_path)
    remote = TestClient(app, client=("203.0.113.7", 40000))
    st = remote.get("/api/auth/state").json()
    assert st["setup_required"] and st["setup_code_required"]
    body = {"username": "chefin", "display_name": "Chefin", "password": ADMIN_PW}
    assert remote.post("/api/auth/setup", json=body, headers=H).status_code == 403
    assert remote.post("/api/auth/setup", json={**body, "setup_code": "FALSCH"}, headers=H).status_code == 403
    assert remote.post("/api/auth/setup", json={**body, "setup_code": app.state.setup_code.lower()}, headers=H).status_code == 200
    assert TestClient(app).get("/api/auth/state").json()["setup_required"] is False


def test_oversized_photo_rejected(tmp_path):
    app = build_app(tmp_path)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    cid = anna.post("/api/cases", json={"title": "X", "case_type": "personensuche", "purpose": "Testrecherche zum Schutz",
                                        "legal_basis": "Einwilligung", "subject": {"label": "Max"}}).json()["id"]
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    r = anna.post(f"/api/cases/{cid}/entities/{sid}/photo", files={"file": ("x.png", b"\x89PNG" + b"0" * 9_000_000, "image/png")})
    assert r.status_code == 422 and "8 MB" in r.json()["detail"]
