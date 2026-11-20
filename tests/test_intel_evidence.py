"""Web evidence additions: page image and independent timestamp inside the real workspace.

The timestamp authority is a local test authority (real CMS signatures); the browser is
replaced by a stub here – the real browser is exercised in test_intel_pageimage.py.
"""
import hashlib
import io
import shutil
import subprocess
import zipfile

import pytest
from cryptography.hazmat.primitives import serialization

from eagleeye.application.intel492 import captures, pageimage, stamps, timestamps
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build475_ai_checkpoint import member
from test_build492_intel import ARTICLE, csrf_session, fake_network, ws  # noqa: F401  (fixture)
from test_intel_timestamps import make_tsa, python_tsa

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
URL = "https://news.example/x"


@pytest.fixture
def tsa(monkeypatch):
    authority = python_tsa()
    real = timestamps.request
    authority["calls"] = []

    def request(url, digest, **kw):
        authority["calls"].append((url, digest))
        if authority.get("down"):
            raise timestamps.TimestampError("Zeitstempeldienst nicht erreichbar (URLError).")
        answer = real(url, digest, send=authority["send"])
        if authority.get("tamper"):
            broken = bytearray(answer["response"])
            broken[-10] ^= 1
            answer["response"] = bytes(broken)
        return answer
    monkeypatch.setattr(timestamps, "request", request)
    # The test authority's root stands in for the public roots; switch "trusted" off to simulate a forged answer.
    authority["trusted"] = True
    monkeypatch.setattr(timestamps, "_trust_roots", lambda: (authority["root"],) if authority["trusted"] else ())
    return authority


@pytest.fixture
def browser(monkeypatch):
    state = {"calls": [], "fail": False}
    monkeypatch.setattr(pageimage, "find_browser", lambda configured="": "/fake/msedge.exe")

    def take(url, *, browser, **kw):
        state["calls"].append(url)
        if state["fail"]:
            raise pageimage.ImageError("Zeitüberschreitung beim Laden der Seite.")
        return {"png": PNG, "width": 1366, "height": 2400, "complete": True, "truncated": False,
                "browser": "Edg/131", "hosts": ["news.example", "cdn.example"], "blocked": ["10.0.0.1:80 (intern)"]}
    monkeypatch.setattr(pageimage, "take", take)
    return state


def capture(client, case_id, token, **extra):
    return client.post("/workbench/intel/web", data={"case_id": case_id, "csrf": token, "url": URL, "opsec": "yes", **extra},
                       follow_redirects=False)


@ws
def test_capture_with_image_and_timestamp_gives_a_verifiable_package(workspace, fake_network, tsa, browser):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    fake_network.responses[URL] = (200, [("Content-Type", "text/html; charset=utf-8")], ARTICLE)
    token = csrf_session(workspace)
    response = capture(client, case_id, token, stempel="yes", seitenbild="yes")
    assert response.status_code == 303 and "zusatz=bild_ok%2Cstempel_ok" in response.headers["location"]
    row = captures.captures_for_case(ctx, case_id)[0]
    # Only the manifest digest went to the authority – never the address or content.
    (url, digest), = tsa["calls"]
    text = stamps.manifest(ctx, row["capture_id"])
    assert url == timestamps.DEFAULT_URL and digest == hashlib.sha256(text.encode()).digest()
    assert row["warc_sha256"] in text and hashlib.sha256(PNG).hexdigest() in text and URL in text
    listing = client.get(response.headers["location"]).text
    assert "Seitenbild aufgenommen." in listing and "Unabhängiger Zeitstempel eingeholt und geprüft." in listing
    assert "✓ Zeitstempel" in listing and "Prüfpaket" in listing and "Zeitstempel einholen</button>" not in listing
    assert "1 interne Anfrage gesperrt" in listing
    image = client.get("/workbench/intel/seitenbild.png", params={"case_id": case_id, "capture_id": row["capture_id"]})
    assert image.status_code == 200 and image.content == PNG and image.headers["content-type"] == "image/png"
    package = client.get("/workbench/intel/pruefpaket.zip", params={"case_id": case_id, "capture_id": row["capture_id"]})
    assert package.status_code == 200
    files = zipfile.ZipFile(io.BytesIO(package.content))
    names = set(files.namelist())
    assert names == {row["capture_id"] + ".warc.gz", "seitenbild.png", "seitenbild-info.txt", "manifest.txt", "zeitstempel.tsr",
                     "zertifikatskette.pem", "pruefsummen.txt", "LIESMICH.txt"}
    manifest = files.read("manifest.txt")
    assert manifest == text.encode()
    assert hashlib.sha256(files.read(row["capture_id"] + ".warc.gz")).hexdigest() == row["warc_sha256"]
    for line in files.read("pruefsummen.txt").decode().splitlines():
        value, name = line.split("  ", 1)
        assert hashlib.sha256(files.read(name)).hexdigest() == value
    facts = timestamps.verify(files.read("zeitstempel.tsr"), hashlib.sha256(manifest).digest(), roots=[tsa["root"]])
    assert facts["chain_trusted"]
    assert "certutil -hashfile" in files.read("LIESMICH.txt").decode()
    info = files.read("seitenbild-info.txt").decode()
    assert "news.example, cdn.example" in info and "interne Adressen: 1" in info
    # The report names the image and the verified timestamp.
    fields = dict(app.state.report_web_fields(case_id, row["document_id"]))
    assert fields["Seitenbild (SHA-256, aufgenommen UTC)"].startswith(hashlib.sha256(PNG).hexdigest())
    assert "Python Zeitstempel" in fields["Unabhängiger Zeitstempel (RFC 3161)"]
    summary = stamps.client_summary(ctx, case_id, row["capture_id"])
    assert summary[0] == "Seitenbild gesichert" and summary[1].startswith("unabhängiger Zeitstempel ")
    # A changed image is refused instead of shown.
    ctx.db.execute("UPDATE web_capture_image_492 SET png=? WHERE capture_id=?", (PNG + b"x", row["capture_id"]))
    assert client.get("/workbench/intel/seitenbild.png", params={"case_id": case_id, "capture_id": row["capture_id"]}).status_code == 409
    assert "seitenbild.png" not in zipfile.ZipFile(io.BytesIO(client.get(
        "/workbench/intel/pruefpaket.zip", params={"case_id": case_id, "capture_id": row["capture_id"]}).content)).namelist()


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL nicht installiert")
@ws
def test_package_verifies_with_openssl(workspace, fake_network, tsa, browser, tmp_path):
    app, client, user, case_id, *_ = workspace
    tsa.update(make_tsa(tmp_path / "authority"))  # OpenSSL's own authority: full ESS attributes
    fake_network.responses[URL] = (200, [("Content-Type", "text/html; charset=utf-8")], ARTICLE)
    capture(client, case_id, csrf_session(workspace), stempel="yes")
    row = captures.captures_for_case(app.state.context, case_id)[0]
    package = client.get("/workbench/intel/pruefpaket.zip", params={"case_id": case_id, "capture_id": row["capture_id"]})
    zipfile.ZipFile(io.BytesIO(package.content)).extractall(tmp_path)
    (tmp_path / "root.pem").write_bytes(tsa["root"].public_bytes(serialization.Encoding.PEM))
    result = subprocess.run(["openssl", "ts", "-verify", "-data", "manifest.txt", "-in", "zeitstempel.tsr",
                             "-CAfile", "root.pem", "-untrusted", "zertifikatskette.pem"],
                            cwd=tmp_path, capture_output=True, text=True)
    assert "Verification: OK" in result.stdout, result.stdout + result.stderr


@ws
def test_failed_additions_keep_the_capture_and_can_be_repeated(workspace, fake_network, tsa, browser):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    fake_network.responses[URL] = (200, [("Content-Type", "text/html; charset=utf-8")], ARTICLE)
    token = csrf_session(workspace)
    tsa["down"], browser["fail"] = True, True
    response = capture(client, case_id, token, stempel="yes", seitenbild="yes")
    assert "zusatz=bild_fehler%2Cstempel_netz" in response.headers["location"]
    row = captures.captures_for_case(ctx, case_id)[0]
    assert row["integrity_ok"]
    listing = client.get(response.headers["location"]).text
    assert "Sicherung selbst ist vollständig" in listing and "nicht erreichbar" in listing
    assert "Zeitstempel einholen</button>" in listing and "Seitenbild aufnehmen" in listing
    events = {r["action"] for r in ctx.db.all("SELECT action FROM audit_events WHERE case_id=?", (case_id,))}
    assert {"web_capture_image_failed_492", "web_capture_stamp_failed_492"} <= events
    # A broken authority response is never stored.
    tsa["down"], tsa["tamper"] = False, True
    again = client.post("/workbench/intel/stempel", data={"case_id": case_id, "csrf": token, "capture_id": row["capture_id"]},
                        follow_redirects=False)
    assert "zusatz=stempel_fehler" in again.headers["location"]
    assert ctx.db.one("SELECT COUNT(*) AS n FROM web_capture_stamp_492")["n"] == 0
    # A correctly signed answer whose certificate leads to no trusted root (e.g. someone on the
    # plain-HTTP path answering with a self-made certificate) is not evidence either.
    tsa["tamper"], tsa["trusted"] = False, False
    forged = client.post("/workbench/intel/stempel", data={"case_id": case_id, "csrf": token, "capture_id": row["capture_id"]},
                         follow_redirects=False)
    assert "zusatz=stempel_fehler" in forged.headers["location"]
    assert ctx.db.one("SELECT COUNT(*) AS n FROM web_capture_stamp_492")["n"] == 0
    reasons = [r["details_json"] for r in ctx.db.all("SELECT details_json FROM audit_events WHERE action='web_capture_stamp_failed_492'")]
    assert any("vertrauenswürdig" in r for r in reasons)
    tsa["trusted"] = True
    # Stamp later, then add an image later: the first stamp is outdated, a new one is taken.
    client.post("/workbench/intel/stempel", data={"case_id": case_id, "csrf": token, "capture_id": row["capture_id"]})
    first = stamps.latest(ctx, case_id)[row["capture_id"]]
    browser["fail"] = False
    refused = client.post("/workbench/intel/seitenbild", data={"case_id": case_id, "csrf": token, "capture_id": row["capture_id"]})
    assert refused.status_code == 422 and browser["calls"] == [URL]  # opsec confirmation is required
    later = client.post("/workbench/intel/seitenbild", data={"case_id": case_id, "csrf": token, "capture_id": row["capture_id"],
                                                           "opsec": "yes"}, follow_redirects=False)
    assert "zusatz=bild_ok%2Cstempel_ok" in later.headers["location"]
    assert not stamps.check(ctx, first["stamp_id"])["current"]
    newest = stamps.latest(ctx, case_id)[row["capture_id"]]
    assert newest["stamp_id"] != first["stamp_id"] and stamps.check(ctx, newest["stamp_id"])["current"]
    tsa["trusted"] = False
    assert not stamps.check(ctx, newest["stamp_id"])["ok"]
    assert "✗ Zeitstempel nicht prüfbar" in client.get("/workbench/intel/web", params={"case_id": case_id}).text
    assert stamps.client_summary(ctx, case_id, row["capture_id"]) == ["Seitenbild gesichert"]
    tsa["trusted"] = True
    # A second image for the same capture is refused (the first one stays the evidence).
    with pytest.raises(ValueError):
        stamps.store_image(ctx, identity=user, case_id=case_id, capture_id=row["capture_id"],
                           shot={"png": PNG, "width": 1, "height": 1})


@ws
def test_read_only_member_sees_but_cannot_add(workspace, fake_network, tsa, browser):
    app, client, admin, case_id, *_ = workspace
    ctx = app.state.context
    fake_network.responses[URL] = (200, [("Content-Type", "text/html; charset=utf-8")], ARTICLE)
    capture(client, case_id, csrf_session(workspace), stempel="yes", seitenbild="yes")
    row = captures.captures_for_case(ctx, case_id)[0]
    member(workspace, "read_only")
    token = csrf_session(workspace, "member475", "Independent!Secret_881")
    view = client.get("/workbench/intel/web", params={"case_id": case_id}).text
    assert "✓ Zeitstempel" in view and "Seitenbild aufnehmen" not in view
    assert client.get("/workbench/intel/pruefpaket.zip", params={"case_id": case_id, "capture_id": row["capture_id"]}).status_code == 200
    for path in ("/workbench/intel/stempel", "/workbench/intel/seitenbild"):
        assert client.post(path, data={"case_id": case_id, "csrf": token, "capture_id": row["capture_id"], "opsec": "yes"}).status_code == 403
    other = workspace[5]
    assert client.get("/workbench/intel/seitenbild.png", params={"case_id": other, "capture_id": row["capture_id"]}).status_code == 403


@ws
def test_evidence_settings_are_kept_by_the_office_lead(workspace, tsa, tmp_path):
    app, client, admin, case_id, *_ = workspace
    ctx = app.state.context
    token = csrf_session(workspace)
    page = client.get("/buero/einstellungen").text
    assert "Beweissicherung (Web-Belege)" in page and "timestamp.digicert.com" in page
    bad = client.post("/buero/beweissicherung", data={"csrf": token, "tsa_url": "ftp://x", "browser_path": ""})
    assert bad.status_code == 422 and "http" in bad.text
    for path, why in (("/nicht/vorhanden/msedge.exe", "existiert nicht"), (str(tmp_path / "notepad.exe"), "msedge.exe")):
        (tmp_path / "notepad.exe").write_bytes(b"MZ")
        refused = client.post("/buero/beweissicherung", data={"csrf": token, "tsa_url": "", "browser_path": path})
        assert refused.status_code == 422 and why in refused.text
    fake = tmp_path / "msedge.exe"
    fake.write_bytes(b"MZ")
    ok = client.post("/buero/beweissicherung", data={"csrf": token, "tsa_url": "https://tsa.example/tsr",
                                                     "browser_path": str(fake)}, follow_redirects=False)
    assert ok.status_code == 303
    assert stamps.settings(ctx) == {"tsa_url": "https://tsa.example/tsr", "browser_path": str(fake)}
    fake.unlink()  # uninstalled later: the page says so instead of failing silently
    assert "Kein Browser gefunden" in client.get("/buero/einstellungen").text
    web = client.get("/workbench/intel/web", params={"case_id": case_id}).text
    assert "tsa.example" in web and "kein Edge oder Chrome gefunden" in web
    member(workspace, "case_lead")
    token = csrf_session(workspace, "member475", "Independent!Secret_881")
    assert client.post("/buero/beweissicherung", data={"csrf": token, "tsa_url": "https://evil.example/"}).status_code == 403
