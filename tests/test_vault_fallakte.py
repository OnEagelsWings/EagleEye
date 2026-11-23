"""EagleEye-Fallakte im Vault: verschlüsselt im Ruhezustand, eine Anmeldung, Netzschalter, beim Sperren gesichert und entfernt."""
from __future__ import annotations

import socket
import time

import pytest
from fastapi.testclient import TestClient

from eagleeye.infrastructure.providers.personosint_bridge import _personosint

for _dep in ("docx", "argon2", "segno"):  # PersonOSINT-Laufzeit; in reinen EagleEye-Umgebungen überspringen
    pytest.importorskip(_dep)
_personosint()
from personosint import auth as auth_mod  # noqa: E402
from personosint import netgate  # noqa: E402
from personosint.auth import totp_code  # noqa: E402
from personosint.vault_app import create_fallakte_asgi, create_vault_app  # noqa: E402

FAST_KDF = {"name": "argon2id", "time_cost": 1, "memory_kib": 8192, "parallelism": 1}
PASS = "Hafenlichter zählen sieben Möwen im Nebel"
H = {"X-Requested-With": "EagleEye", "Accept-Language": "de-DE"}
MARK = "Mandant-Quokka-Nordhafen-4711"


class Clock:
    def __init__(self):
        self.now = time.time()

    def __call__(self):
        return self.now


@pytest.fixture
def vault(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(auth_mod.time, "time", clock)
    app = create_vault_app(tmp_path / "vault", kdf=FAST_KDF, classic_dir=tmp_path / "nichts", background=False)
    app.manager.fallakte_port = 8378
    client = TestClient(app, base_url="http://127.0.0.1", headers=H)
    secret = client.post("/vault/api/setup/begin", json={"display_name": "Detektei Nord", "passphrase": PASS, "passphrase2": PASS}).json()["secret"]
    assert client.post("/vault/api/setup/finish", json={"code": totp_code(secret, clock.now)}).status_code == 200
    yield app, client, clock, secret, tmp_path / "vault"
    app.manager.lock("Testende")
    netgate.GATE.close()
    netgate.uninstall()


def test_fallakte_single_sign_on_encrypted_at_rest_and_closed_on_lock(vault):
    app, client, clock, secret, folder = vault
    m = app.manager
    assert m.status()["fallakte"]["available"] and not m.status()["fallakte"]["open"]
    fa_client = TestClient(create_fallakte_asgi(app), base_url="http://127.0.0.1", headers=H)
    assert fa_client.get("/").status_code == 423                                    # erst über den Vault
    r = client.get("/vault/fallakte", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "http://127.0.0.1:8378/"
    assert "ee_auth_session" in r.cookies and m.fallakte.is_open
    work = m.fallakte.workdir
    fa_client.cookies.set("ee_auth_session", r.cookies["ee_auth_session"])
    fa_client.cookies.set("ee_auth_csrf", r.cookies["ee_auth_csrf"])
    page = fa_client.get("/workbench")
    assert page.status_code == 200, page.text[:300]
    assert "Anmeldung erforderlich" not in page.text
    # eine Notiz in der Fallakte-Datenbank, dann sperren
    ctx = m.fallakte.app.state.context
    ctx.db.execute("CREATE TABLE IF NOT EXISTS vault_probe(note TEXT)")
    ctx.db.execute("INSERT INTO vault_probe(note) VALUES (?)", (MARK,))
    assert m.fallakte.sync() >= 1
    client.post("/vault/api/lock", headers={**H, "X-CSRF-Token": client.get("/api/auth/state").json().get("csrf", "")})
    assert not m.unlocked and not work.exists()                                    # Arbeitsordner gelöscht
    assert fa_client.get("/workbench").status_code == 423
    for path in (folder / "files" / "fallakte").rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            assert MARK.encode() not in data and b"SQLite format" not in data and b"eagleeye.db" not in data, path
    # wieder öffnen: Inhalt ist da
    clock.now += 30
    assert client.post("/vault/api/unlock", json={"passphrase": PASS, "code": totp_code(secret, clock.now)}).status_code == 200
    client.get("/vault/fallakte", follow_redirects=False)
    rows = m.fallakte.app.state.context.db.all("SELECT note FROM vault_probe")
    assert [r["note"] for r in rows] == [MARK]


def test_fallakte_shares_the_vault_network_switch(vault):
    app, client, clock, secret, folder = vault
    client.get("/vault/fallakte", follow_redirects=False)
    assert app.manager.fallakte.is_open
    with pytest.raises(OSError, match="Netz geschlossen"):
        socket.getaddrinfo("example.org", 443)                                     # gilt im selben Prozess auch für die Fallakte
