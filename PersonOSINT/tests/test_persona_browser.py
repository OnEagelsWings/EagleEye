"""Legenden-Browser: Profil nur verschlüsselt im Vault, nur über Tor/Proxy, schließt mit Netz und Vault."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from personosint import auth as auth_mod
from personosint import netgate
from personosint.auth import totp_code
from personosint.crypto import Vault
from personosint.persona_browser import BrowserError, PersonaBrowsers, browser_args
from personosint.vault_app import create_vault_app
from test_personosint import FakeHttp
from test_vault import FAST_KDF, PASS, Clock

FAKE_BROWSER = r'''
import sys, time, pathlib
args = dict(a.split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
prof = pathlib.Path(args["--user-data-dir"])
(prof / "Default").mkdir(parents=True, exist_ok=True)
cookies = prof / "Default" / "Cookies"
old = cookies.read_text() if cookies.exists() else ""
cookies.write_text(old + "anmeldung-instagram-LEGENDENKEKS;")
(prof / "Default" / "Cache").mkdir(exist_ok=True)
(prof / "Default" / "Cache" / "gross.bin").write_bytes(b"x" * 1000)
(prof / "args.txt").write_text("\n".join(sys.argv[1:]))
time.sleep(float(args.get("--fake-sleep", "0.2")))
'''


def _launcher(script: Path, sleep: float = 0.2):
    return lambda cmd: subprocess.Popen([sys.executable, str(script)] + cmd[1:] + [f"--fake-sleep={sleep}"])


def test_browser_args_force_proxy_and_block_leaks():
    args = browser_args("/tmp/x", "http://127.0.0.1:9080", "Legende UFER-901")
    assert "--proxy-server=http://127.0.0.1:9080" in args
    assert "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1" in args
    assert "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" in args and "--disable-quic" in args
    with pytest.raises(BrowserError, match="Anmeldung"):
        browser_args("/tmp/x", "http://nutzer:geheim@proxy.example:3128", "x")
    with pytest.raises(BrowserError):
        browser_args("/tmp/x", "", "x")


def test_profile_is_encrypted_between_sessions_and_restored(tmp_path):
    script = tmp_path / "fakebrowser.py"
    script.write_text(FAKE_BROWSER)
    vault = Vault.from_key(b"0" * 43 + b"=")
    pb = PersonaBrowsers(tmp_path / "store", vault, lambda: sys.executable, _launcher(script))
    persona = {"id": 7, "codename": "UFER-901"}
    first = pb.open(persona, "http://127.0.0.1:9080", "Tor")
    assert first["restored"] is False
    with pytest.raises(BrowserError, match="schon offen"):
        pb.open(persona, "http://127.0.0.1:9080", "Tor")
    for _ in range(100):
        if not pb.status():
            break
        time.sleep(0.05)
    archive = tmp_path / "store" / "7.zip.enc"
    data = archive.read_bytes()
    assert b"LEGENDENKEKS" not in data and b"Cookies" not in data       # verschlüsselt, nicht einmal Dateinamen lesbar
    assert not list(Path(tmp_path).glob("eagleeye-legende-*"))
    second = pb.open(persona, "http://127.0.0.1:9080", "Tor")
    assert second["restored"] is True
    for _ in range(100):
        if not pb.status():
            break
        time.sleep(0.05)
    import io
    import zipfile
    z = zipfile.ZipFile(io.BytesIO(vault.decrypt(archive.read_bytes())))
    assert z.read("Default/Cookies").decode().count("LEGENDENKEKS") == 2   # Sitzung blieb erhalten
    assert not any("Cache" in n for n in z.namelist())                      # Zwischenspeicher wird nicht gesichert
    assert "--proxy-server=http://127.0.0.1:9080" in z.read("args.txt").decode()


def test_vault_opens_persona_window_only_with_open_net_and_closes_with_it(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(auth_mod.time, "time", clock)
    script = tmp_path / "fakebrowser.py"
    script.write_text(FAKE_BROWSER)
    app = create_vault_app(tmp_path / "vault", http=FakeHttp({}), kdf=FAST_KDF, classic_dir=tmp_path / "nichts", background=False)
    c = TestClient(app, base_url="http://127.0.0.1")
    H = {"X-Requested-With": "EagleEye"}
    try:
        secret = c.post("/vault/api/setup/begin", json={"display_name": "Detektei Nord", "passphrase": PASS, "passphrase2": PASS}, headers=H).json()["secret"]
        c.post("/vault/api/setup/finish", json={"code": totp_code(secret, clock.now)}, headers=H)
        api = {**H, "X-CSRF-Token": c.get("/api/auth/state").json()["csrf"]}
        m = app.manager
        m.browsers.browser = lambda: sys.executable
        m.browsers.launcher = _launcher(script, sleep=30)
        platform = m.inner.state.platform
        platform.proxy_check = lambda prof: None
        prof = platform.save_egress_profile({"name": "Tor", "kind": "proxy", "proxy_url": "http://127.0.0.1:9080"})
        direct_err = c.post("/api/personas", json={"codename": "X-1", "display_name": "Anna Brandt", "egress_profile": "direkt"}, headers=api)
        assert direct_err.status_code == 422 and "Anonymisierungs-Ausgang" in direct_err.json()["detail"]
        pid = c.post("/api/personas", json={"codename": "UFER-901", "display_name": "Katrin Wendt"}, headers=api).json()["id"]
        r = c.post(f"/vault/api/personas/{pid}/browser", json={"open": True}, headers=api)
        assert r.status_code == 409 and "Netz" in r.json()["detail"]                       # Netz zu
        c.post("/vault/api/net", json={"open": True, "minutes": 15}, headers=api)
        r = c.post(f"/vault/api/personas/{pid}/browser", json={"open": True}, headers=api)
        assert r.status_code == 409 and "Ausgang" in r.json()["detail"]                    # kein Ausgang zugeordnet
        c.put(f"/api/personas/{pid}", json={"egress_profile": prof.id}, headers=api)
        r = c.post(f"/vault/api/personas/{pid}/browser", json={"open": True}, headers=api)
        assert r.status_code == 200, r.text
        assert c.get("/vault/api/personas/browsers").json()["items"][0]["codename"] == "UFER-901"
        c.post("/vault/api/net", json={"open": False}, headers=api)                         # Netz zu ⇒ Fenster zu
        for _ in range(200):
            if not m.browsers.status():
                break
            time.sleep(0.05)
        assert not m.browsers.status()
        assert (tmp_path / "vault" / "files" / "persona-browser" / f"{pid}.zip.enc").is_file()
        uses = platform.db.all("SELECT purpose FROM persona_use WHERE persona_id = ?", (pid,))
        assert any("Legenden-Browser" in u["purpose"] for u in uses)
        # Sperren schließt offene Fenster ebenfalls
        c.post("/vault/api/net", json={"open": True, "minutes": 15}, headers=api)
        assert c.post(f"/vault/api/personas/{pid}/browser", json={"open": True}, headers=api).status_code == 200
        browsers = m.browsers
        m.lock("Test")
        assert not browsers.status()
    finally:
        app.manager.lock("Testende")
        netgate.GATE.close()
        netgate.uninstall()
