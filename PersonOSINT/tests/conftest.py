"""Gemeinsame Test-Hilfen: Anwendung mit SQLite und – falls verfügbar – PostgreSQL.

PostgreSQL-Tests aktivieren:  EAGLEEYE_TEST_PG_URL=postgresql://user@host:5432/testdb
(die Datenbank wird bei jedem Test geleert!)
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from personosint.api import create_app
from personosint.config import Settings

H = {"X-Requested-With": "EagleEye"}
ADMIN_PW = "Leitstelle-Passwort-2026!"
PG_URL = os.environ.get("EAGLEEYE_TEST_PG_URL", "")
BACKENDS = ["sqlite"] + (["postgres"] if PG_URL else [])


def reset_pg() -> None:
    import psycopg

    with psycopg.connect(PG_URL, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")


def make_settings(tmp_path, backend: str, require_2fa: bool = False) -> Settings:
    s = Settings(data_dir=tmp_path)
    s.require_2fa = require_2fa
    s.backup_hour = ""
    s.backup_passphrase = ""
    s.database_url = ""
    if backend == "postgres":
        reset_pg()
        s.database_url = PG_URL
    return s


def build_app(tmp_path, backend: str = "sqlite", http=None, require_2fa: bool = False):
    return create_app(settings=make_settings(tmp_path, backend, require_2fa), http=http, auto_geocode=False, start_scheduler=False)


def login(app, username: str, password: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"username": username, "password": password}, headers=H)
    assert r.status_code == 200, r.text
    st = c.get("/api/auth/state").json()
    c.headers.update({**H, "X-CSRF-Token": st["csrf"]})
    return c


def setup_admin(app) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/setup", json={"username": "admin", "display_name": "Ada Admin", "password": ADMIN_PW}, headers=H)
    assert r.status_code == 200, r.text
    st = c.get("/api/auth/state").json()
    c.headers.update({**H, "X-CSRF-Token": st["csrf"]})
    return c


def add_user(admin: TestClient, app, username: str, role: str) -> TestClient:
    """Legt eine Person an, meldet sie an und erledigt den Pflicht-Passwortwechsel."""
    tmp_pw, new_pw = "Startkennwort-2026!", "Eigenes-Kennwort#9x"
    r = admin.post("/api/admin/users", json={"username": username, "display_name": username.title(), "role": role, "password": tmp_pw})
    assert r.status_code == 201, r.text
    c = login(app, username, tmp_pw)
    assert c.get("/api/auth/state").json()["state"] == "password"
    assert c.get("/api/cases").status_code == 401
    assert c.post("/api/auth/password", json={"old_password": tmp_pw, "new_password": new_pw}).status_code == 200
    c.uid = r.json()["id"]  # type: ignore[attr-defined]
    return c


@pytest.fixture(params=BACKENDS)
def backend(request):
    return request.param
