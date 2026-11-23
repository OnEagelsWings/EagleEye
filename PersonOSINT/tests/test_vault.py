"""EagleEye Vault: verschlüsselter Datenbestand, nur lokal, Netz nur auf Befehl, Sperren und Entsperren."""
from __future__ import annotations

import socket
import time

import pytest
from fastapi.testclient import TestClient

from personosint import auth as auth_mod
from personosint import netgate
from personosint.auth import totp_code
from personosint.vault import VaultStore
from personosint.vault_app import create_vault_app
from conftest import build_app, setup_admin
from test_personosint import FakeHttp

FAST_KDF = {"name": "argon2id", "time_cost": 1, "memory_kib": 8192, "parallelism": 1}
PASS = "Hafenlichter zählen sieben Möwen im Nebel"
H = {"X-Requested-With": "EagleEye"}
SECRET_WORD = "Zielperson-Quokka-4711"


class Clock:
    """TOTP-Codes dürfen nicht zweimal gelten – die Tests rücken die Uhr deshalb je Anmeldung weiter."""
    def __init__(self):
        self.now = time.time()

    def __call__(self):
        return self.now


@pytest.fixture
def vault(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(auth_mod.time, "time", clock)
    app = create_vault_app(tmp_path / "vault", http=FakeHttp({}), kdf=FAST_KDF, classic_dir=tmp_path / "keine-altdaten",
                           background=False)
    client = TestClient(app, base_url="http://127.0.0.1")
    yield app, client, clock, tmp_path / "vault"
    app.manager.lock("Testende")
    netgate.GATE.close()
    netgate.uninstall()


def _setup(client, clock):
    r = client.post("/vault/api/setup/begin", json={"display_name": "Detektei Nord", "passphrase": PASS, "passphrase2": PASS}, headers=H)
    assert r.status_code == 200, r.text
    secret = r.json()["secret"]
    assert "<svg" in r.json()["qr_svg"]
    r = client.post("/vault/api/setup/finish", json={"code": totp_code(secret, clock.now)}, headers=H)
    assert r.status_code == 200, r.text
    return secret, r.json()["recovery_key"]


def _csrf(client):
    return client.get("/api/auth/state").json()["csrf"]


def _api(client):
    return {**H, "X-CSRF-Token": _csrf(client)}


def test_setup_unlock_lock_and_nothing_readable_on_disk(vault):
    app, client, clock, folder = vault
    first = client.get("/vault/api/status").json()
    assert first["exists"] is False and first["unlocked"] is False and first["net"]["open"] is False
    assert client.get("/api/cases").status_code == 423                       # gesperrt: keine Anwendung erreichbar
    assert "EagleEye Vault" in client.get("/").text                          # Sperrbildschirm statt Anwendung
    secret, recovery = _setup(client, clock)
    assert len(recovery.split("-")) == 6
    page = client.get("/")
    assert "vaultbar.js" in page.text and page.headers["cache-control"] == "no-store"
    assert "tile.openstreetmap.org" not in page.headers["content-security-policy"]
    # Fall mit eindeutigem Begriff anlegen (über die gewohnte PersonOSINT-Schnittstelle)
    r = client.post("/api/cases", json={"title": SECRET_WORD, "kind": "person", "purpose": "Test der Verschlüsselung im Vault",
                                        "legal_basis": "Einwilligung der betroffenen Person"}, headers=_api(client))
    assert r.status_code in (200, 201), r.text
    assert client.post("/vault/api/lock", headers=_api(client)).status_code == 200
    assert client.get("/vault/api/status").json()["unlocked"] is False
    assert client.get("/api/cases").status_code == 423
    # Auf der Platte: nirgends Klartext, keine Datenbank-, keine Schlüsseldatei
    # einzige unverschlüsselte Datei: öffentliche Referenzdaten (OpenSanctions, ICIJ, OffeneRegister) – ohne Falldaten
    public = folder / "files" / "referenzdaten.sqlite3"
    files = [p for p in folder.rglob("*") if p.is_file() and p != public and not p.name.startswith("referenzdaten.sqlite3")]
    assert files and not any(p.suffix in {".sqlite3", ".db", ".key"} for p in files)
    for path in files:
        data = path.read_bytes()
        assert SECRET_WORD.encode() not in data and b"SQLite format" not in data and b"Detektei Nord" not in data, path
    for path in folder.rglob("referenzdaten.sqlite3*"):
        data = path.read_bytes()
        assert SECRET_WORD.encode() not in data and b"Detektei Nord" not in data, path
    # Wieder öffnen: falsche Passphrase, falscher Code, dann richtig
    assert client.post("/vault/api/unlock", json={"passphrase": PASS + "x", "code": "000000"}, headers=H).status_code == 401
    clock.now += 30
    assert client.post("/vault/api/unlock", json={"passphrase": PASS, "code": "000000"}, headers=H).status_code == 401
    r = client.post("/vault/api/unlock", json={"passphrase": PASS, "code": totp_code(secret, clock.now)}, headers=H)
    assert r.status_code == 200, r.text
    assert any(c["title"] == SECRET_WORD for c in client.get("/api/cases").json())
    # derselbe Code gilt nicht zweimal
    client.post("/vault/api/lock", headers=_api(client))
    assert client.post("/vault/api/unlock", json={"passphrase": PASS, "code": totp_code(secret, clock.now)}, headers=H).status_code == 401


def test_failed_attempts_slow_down_even_with_correct_passphrase(vault):
    app, client, clock, folder = vault
    _setup(client, clock)
    client.post("/vault/api/lock", headers=_api(client))
    for _ in range(3):
        client.post("/vault/api/unlock", json={"passphrase": PASS, "code": "000000"}, headers=H)
    info = VaultStore(folder).public_info()
    assert info["failed"] >= 3 and info["wait_seconds"] > 0
    r = client.post("/vault/api/unlock", json={"passphrase": PASS, "code": "000000"}, headers=H)
    assert r.status_code == 429 and "warten" in r.json()["detail"]


def test_recovery_key_opens_and_forces_new_passphrase(vault):
    app, client, clock, folder = vault
    secret, recovery = _setup(client, clock)
    client.post("/vault/api/lock", headers=_api(client))
    new = "Neue Passphrase mit vielen Wörtern 2026"
    r = client.post("/vault/api/recover", json={"recovery_key": recovery.lower().replace("-", " "), "passphrase": new, "passphrase2": new}, headers=H)
    assert r.status_code == 200, r.text
    client.post("/vault/api/lock", headers=_api(client))
    clock.now += 30
    assert client.post("/vault/api/unlock", json={"passphrase": PASS, "code": totp_code(secret, clock.now)}, headers=H).status_code == 401
    clock.now += 30
    assert client.post("/vault/api/unlock", json={"passphrase": new, "code": totp_code(secret, clock.now)}, headers=H).status_code == 200


def test_network_is_closed_until_opened_and_closes_again(vault):
    app, client, clock, folder = vault
    _setup(client, clock)
    gate = app.manager.gate
    # geschlossen: keine Namensauflösung, keine Verbindung nach außen – lokal geht
    with pytest.raises(OSError, match="Netz geschlossen"):
        socket.getaddrinfo("example.org", 443)
    with pytest.raises(OSError, match="Netz geschlossen"):
        socket.create_connection(("93.184.215.14", 443), timeout=1)
    local = socket.socket()
    local.bind(("127.0.0.1", 0))
    local.listen(1)
    socket.create_connection(local.getsockname(), timeout=1).close()
    local.close()
    # Quellenabfragen scheitern geordnet, auch über einen lokalen Proxy
    from personosint.opsec import DIRECT, build_opener
    with pytest.raises(OSError, match="Netz geschlossen"):
        build_opener(DIRECT).open("https://example.org/", timeout=1)
    # öffnen nur mit Sitzung und CSRF
    assert client.post("/vault/api/net", json={"open": True, "minutes": 15}, headers=H).status_code == 423
    r = client.post("/vault/api/net", json={"open": True, "minutes": 15, "purpose": "Testrecherche"}, headers=_api(client))
    assert r.status_code == 200 and r.json()["open"] and r.json()["seconds_left"] > 800
    assert gate.is_open()
    gate._open_until = time.time() - 1            # Zeitfenster abgelaufen
    assert not gate.is_open()
    log = client.get("/vault/api/net/log").json()
    assert any(not i["allowed"] and i["host"] == "example.org" for i in log["items"])
    assert log["sessions"][0]["reason"] == "Zeitfenster abgelaufen"
    # Sperren schließt das Netz und leert das Protokoll
    gate.open(5)
    client.post("/vault/api/lock", headers=_api(client))
    assert not gate.is_open() and not gate.recent()


def test_only_local_and_same_origin_requests(vault):
    app, client, clock, folder = vault
    foreign = TestClient(app, base_url="http://vault.example.org")
    assert foreign.get("/").status_code == 403
    assert client.post("/vault/api/setup/begin", json={}).status_code == 403                       # ohne eigene Kennung
    assert client.post("/vault/api/setup/begin", json={}, headers={**H, "Sec-Fetch-Site": "cross-site"}).status_code == 403
    _setup(client, clock)
    other_browser = TestClient(app, base_url="http://127.0.0.1")
    status = other_browser.get("/vault/api/status").json()
    assert status == {"exists": True, "unlocked": True, "signed_in": False, "version": status["version"]}  # verrät nichts
    assert other_browser.get("/api/cases").status_code == 401
    assert "vaultbar.js" not in other_browser.get("/").text


def test_idle_lock_and_autosave(vault):
    app, client, clock, folder = vault
    _setup(client, clock)
    manager = app.manager
    client.post("/api/cases", json={"title": "Autosave-Probe", "kind": "person", "purpose": "Test des Zwischenspeicherns",
                                    "legal_basis": "Einwilligung der betroffenen Person"}, headers=_api(client))
    before = (folder / "vault.db.enc").stat().st_mtime_ns
    manager.tick()
    assert (folder / "vault.db.enc").stat().st_mtime_ns != before
    manager.clock = lambda: time.time() + 16 * 60
    manager.tick()
    assert not manager.unlocked and "Minuten ohne Eingabe" in manager.lock_reason


def test_existing_personosint_data_is_taken_over_encrypted(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(auth_mod.time, "time", clock)
    classic = tmp_path / "bisher"
    old_app = build_app(classic)
    admin = setup_admin(old_app)
    cid = admin.post("/api/cases", json={"title": "Altfall Seeblick", "kind": "person", "purpose": "Übernahme in den Vault prüfen",
                                         "legal_basis": "Einwilligung der betroffenen Person"}).json()["id"]
    assert (classic / "personosint.sqlite3").is_file()
    app = create_vault_app(tmp_path / "vault", http=FakeHttp({}), kdf=FAST_KDF, classic_dir=classic, background=False)
    client = TestClient(app, base_url="http://127.0.0.1")
    try:
        assert client.get("/vault/api/status").json()["classic_data"] is True
        secret = client.post("/vault/api/setup/begin", json={"display_name": "Detektei Nord", "passphrase": PASS, "passphrase2": PASS},
                             headers=H).json()["secret"]
        done = client.post("/vault/api/setup/finish", json={"code": totp_code(secret, clock.now), "import_classic": True}, headers=H).json()
        assert done["imported"] and done["imported_cases"] == 1
        assert any(c["id"] == cid and c["title"] == "Altfall Seeblick" for c in client.get("/api/cases").json())
        stored = (tmp_path / "vault" / "vault.db.enc").read_bytes()
        assert b"Altfall Seeblick" not in stored and b"SQLite format" not in stored
    finally:
        app.manager.lock("Testende")
        netgate.uninstall()
