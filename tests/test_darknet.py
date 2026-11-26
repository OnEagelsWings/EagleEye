"""Darknet module: onion validation, Tor SOCKS transport, source register, Ahmia search, capture as evidence."""
from __future__ import annotations

import socket
import struct
import threading

import pytest

from eagleeye.application.darknet import service as darknet
from eagleeye.application.darknet import tor
from eagleeye.application.intel492 import captures
from eagleeye.application.intel492.webcapture import CaptureError, HttpResult
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.app500 import create_workspace_app500
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import csrf_session

AHMIA = darknet.AHMIA_ONION
TORPROJECT = "2gzyxa5ihm7nsggfxnu52rck2vv4rvmdlkiu3zzui5du4xyclen53wid.onion"
DDG = "duckduckgogg42xjoc72x3sjasowoarfbgcmvfimaftt6twagswzczad.onion"
ws = pytest.mark.parametrize("workspace", [create_workspace_app500], indirect=True)
PAGE = ("<html><head><title>Forum Testthread</title></head><body><main><h1>Angebot</h1>"
        "<p>" + "Datensatz der Muster GmbH wird hier angeboten, Kontakt nur über das Forum. " * 4 + "</p>"
        "<img src='/bild.jpg'></main></body></html>").encode()


# ------------------------------------------------------------------ addresses
def test_only_v3_onions_with_correct_checksum_are_accepted():
    assert tor.onion_v3_valid(AHMIA) and tor.onion_v3_valid(TORPROJECT) and tor.onion_v3_valid(DDG)
    assert tor.onion_v3_valid("forum." + DDG), "subdomains of a valid service are fine"
    assert not tor.onion_v3_valid(DDG[:-7] + "e.onion"), "one wrong character breaks the checksum"
    assert not tor.onion_v3_valid("expyuzz4wqqyqhjn.onion"), "v2 addresses are obsolete"
    assert not tor.onion_v3_valid("example.com")
    assert tor.normalize_onion_url(DDG + "/suche?q=x#frag") == f"http://{DDG}/suche?q=x"
    for bad in ("https://example.com/", f"http://user:pw@{DDG}/", f"http://{DDG}:8080/", "ftp://" + DDG, f"http://{DDG[:-7]}e.onion/"):
        with pytest.raises(CaptureError):
            tor.normalize_onion_url(bad)
    assert tor.onion_host_of(f"http://{TORPROJECT}/de/") == TORPROJECT and tor.onion_host_of("http://example.com") == ""


# ------------------------------------------------------------------ SOCKS5 transport against a fake Tor
class FakeTor:
    """Speaks SOCKS5 like Tor: requires username/password (isolation), takes the onion name, answers HTTP."""

    def __init__(self, responses):
        self.responses = responses  # path -> (status, headers, body)
        self.requests = []          # (isolation user, host, port, request line)
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(8)
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        with conn:
            ver, n = conn.recv(2)
            methods = conn.recv(n)
            if 2 not in methods:
                conn.sendall(b"\x05\xff")
                return
            conn.sendall(b"\x05\x02")
            conn.recv(1)
            user = conn.recv(conn.recv(1)[0]).decode()
            conn.recv(conn.recv(1)[0])
            conn.sendall(b"\x01\x00")
            head = conn.recv(4)
            assert head[3] == 3, "the onion name goes to Tor, no local resolution"
            host = conn.recv(conn.recv(1)[0]).decode()
            port = struct.unpack("!H", conn.recv(2))[0]
            conn.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
            data = b""
            while b"\r\n\r\n" not in data:
                data += conn.recv(4096)
            line = data.split(b"\r\n")[0].decode()
            self.requests.append((user, host, port, line))
            path = line.split(" ")[1]
            status, headers, body = self.responses.get(path, (404, {"Content-Type": "text/plain"}, b"nicht da"))
            conn.sendall((f"HTTP/1.1 {status} X\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
                          + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n").encode() + body)

    def close(self):
        self.server.close()


@pytest.fixture
def fake_tor():
    servers = []

    def make(responses):
        srv = FakeTor(responses)
        servers.append(srv)
        return srv
    yield make
    for srv in servers:
        srv.close()


def test_tor_transport_isolates_cases_and_never_resolves_locally(fake_tor):
    srv = fake_tor({"/forum/1": (200, {"Content-Type": "text/html; charset=utf-8"}, PAGE)})
    a = tor.TorTransport(socks_port=srv.port, isolation="fall-a")
    b = tor.TorTransport(socks_port=srv.port, isolation="fall-b")
    result = a.get(f"http://{DDG}/forum/1")
    b.get(f"http://{DDG}/forum/1")
    assert result.status == 200 and result.body == PAGE and result.ip_address.startswith("Tor")
    assert [r[:3] for r in srv.requests] == [("fall-a", DDG, 80), ("fall-b", DDG, 80)]
    assert srv.requests[0][3] == "GET /forum/1 HTTP/1.1"
    with pytest.raises(ValueError, match="diesem Rechner"):
        tor.TorTransport(socks_host="10.0.0.5", isolation="x")
    with pytest.raises(CaptureError, match="antwortet nicht"):
        tor.TorTransport(socks_port=1, isolation="x").get(f"http://{DDG}/")
    assert tor.probe(socks_port=srv.port)["ok"] and not tor.probe(socks_port=1)["ok"]


# ------------------------------------------------------------------ Ahmia parsing
AHMIA_HOME = b'<form id="searchForm" action="/search/"><input type="text" name="q"><input type="hidden" name="a3f9" value="7c21"></form>'
AHMIA_RESULTS = (
    '<ol class="searchResults"><li class="result"><h4><a href="/search/redirect?search_term=muster&redirect_url=http://'
    + DDG + '/thread/7">Muster GmbH Daten</a></h4><p>Leak der Kundendaten</p><cite>' + DDG + '/thread/7</cite></li>'
    '<li class="result"><h4><a href="http://' + TORPROJECT + '/">Tor Project</a></h4><p>Projektseite</p></li>'
    '<li class="result"><h4><a href="http://kaputt.onion/">kaputt</a></h4></li></ol>').encode()


def test_ahmia_search_form_and_results_are_parsed():
    assert darknet.search_form_fields(AHMIA_HOME.decode()) == [("a3f9", "7c21")]
    results = darknet.parse_results(AHMIA_RESULTS.decode(), f"http://{AHMIA}/")
    assert [r["host"] for r in results] == [DDG, TORPROJECT], "invalid onions are dropped"
    assert results[0]["url"] == f"http://{DDG}/thread/7" and results[0]["description"] == "Leak der Kundendaten"
    fallback = darknet.parse_results(f"<p>siehe http://{TORPROJECT}/x und http://{AHMIA}/</p>", f"http://{AHMIA}/")
    assert [r["host"] for r in fallback] == [TORPROJECT]


# ------------------------------------------------------------------ service rules
class CannedTransport:
    def __init__(self, pages):
        self.pages = pages
        self.urls = []

    def get(self, url, *, accept=tor.ACCEPT):
        self.urls.append(url)
        status, ctype, body, location = self.pages.get(url, (404, "text/plain", b"", ""))
        headers = [("Content-Type", ctype)] + ([("Location", location)] if location else [])
        return HttpResult(url=url, status=status, reason="", headers=headers, body=body, ip_address="Tor (1.0 s)")


@ws
def test_settings_register_and_capture_follow_the_rules(workspace):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    investigator = {"username": "ermittler", "global_role": "investigator"}
    with pytest.raises(PermissionError):
        darknet.transport(ctx, case_id)
    with pytest.raises(PermissionError):
        darknet.save_settings(ctx, user=investigator, enabled=True, socks_port=9050, confirmation=darknet.CONFIRMATION)
    with pytest.raises(ValueError, match="eintippen"):
        darknet.save_settings(ctx, user=user, enabled=True, socks_port=9050, confirmation="ja")
    assert darknet.save_settings(ctx, user=user, enabled=True, socks_port=9150, confirmation="darknet freigeben")["enabled"]

    with pytest.raises(ValueError, match="Prüfsumme"):
        darknet.propose_source(ctx, user=investigator, case_id=case_id, address="http://kaputt.onion", label="X", category="forum", reason="für den Auftrag nötig")
    with pytest.raises(ValueError, match="begründen"):
        darknet.propose_source(ctx, user=investigator, case_id=case_id, address=DDG, label="Forum", category="forum", reason="kurz")
    source = darknet.propose_source(ctx, user=investigator, case_id=case_id, address=f"http://forum.{DDG}/x",
                                    label="Testforum", category="forum", reason="Hinweis auf Datenangebot zur Muster GmbH")
    assert source["onion_host"] == DDG and source["status"] == "vorgeschlagen"
    with pytest.raises(ValueError, match="bereits"):
        darknet.propose_source(ctx, user=investigator, case_id=case_id, address=DDG, label="Doppelt", category="forum", reason="noch einmal erfasst")

    canned = CannedTransport({
        f"http://{DDG}/thread/7": (200, "text/html; charset=utf-8", PAGE, ""),
        f"http://{DDG}/datei.pdf": (200, "application/pdf", b"%PDF-1.4 ...", ""),
        f"http://{DDG}/weiter": (302, "text/html", b"", f"http://{TORPROJECT}/"),
    })
    with pytest.raises(PermissionError, match="nicht freigegeben"):
        darknet.capture(ctx, user=user, case_id=case_id, url=f"http://{DDG}/thread/7", transport_factory=lambda: canned)
    assert canned.urls == [], "nothing is fetched from a source that is not released"
    with pytest.raises(PermissionError):
        darknet.decide_source(ctx, user=investigator, source_id=source["source_id"], status="freigegeben")
    darknet.decide_source(ctx, user=user, source_id=source["source_id"], status="freigegeben")

    row = darknet.capture(ctx, user=user, case_id=case_id, url=f"http://{DDG}/thread/7", transport_factory=lambda: canned)
    assert row["kind"] == "darknet" and row["url"] == f"http://{DDG}/thread/7" and row["ip_address"].startswith("Tor")
    assert captures.verify_capture(ctx, captures.capture_row(ctx, row["capture_id"]))
    doc = ctx.db.one("SELECT title FROM case_documents_458 WHERE document_id=?", (row["document_id"],)) if ctx.db.one(
        "SELECT name FROM sqlite_master WHERE name='case_documents_458'") else None
    assert doc is None or doc["title"].startswith("Darknet: ")
    assert [r["capture_id"] for r in darknet.captures_for_case(ctx, case_id)] == [row["capture_id"]]
    with pytest.raises(CaptureError, match="PDF"):
        darknet.capture(ctx, user=user, case_id=case_id, url=f"http://{DDG}/datei.pdf", transport_factory=lambda: canned)
    with pytest.raises(CaptureError, match="leitet weiter"):
        darknet.capture(ctx, user=user, case_id=case_id, url=f"http://{DDG}/weiter", transport_factory=lambda: canned)

    darknet.decide_source(ctx, user=user, source_id=source["source_id"], status="gesperrt", note="Inhalte unzulässig")
    with pytest.raises(PermissionError):
        darknet.capture(ctx, user=user, case_id=case_id, url=f"http://{DDG}/thread/7", transport_factory=lambda: canned)
    actions = [r["action"] for r in ctx.db.all("SELECT action FROM audit_events WHERE action LIKE 'darknet_%'")]
    assert {"darknet_settings_500", "darknet_source_proposed_500", "darknet_source_released_500",
            "darknet_capture_500", "darknet_source_blocked_500"} <= set(actions)

    search_pages = CannedTransport({f"http://{AHMIA}/": (200, "text/html", AHMIA_HOME, ""),
                                    f"http://{AHMIA}/search/?q=Muster+GmbH&a3f9=7c21": (200, "text/html", AHMIA_RESULTS, "")})
    result = darknet.search(ctx, user=user, case_id=case_id, query="Muster  GmbH", transport_factory=lambda: search_pages)
    assert result["result_count"] == 2 and result["results"][0]["source_status"] == "gesperrt"
    assert darknet.searches(ctx, case_id)[0]["query"] == "Muster GmbH"


@ws
def test_darknet_page_menu_and_forms(workspace, monkeypatch):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    csrf = csrf_session(workspace)
    page = client.get("/workbench/darknet", params={"case_id": case_id})
    assert page.status_code == 200 and "Darknet (Tor)" in page.text and "Dienstanweisung Darknet" in page.text
    assert 'href="/workbench/darknet?case_id=' in page.text, "the module is in the menu"
    assert "ausgeschaltet" in page.text and "Einstellungen (Büroleitung)" in page.text

    off = client.post("/workbench/darknet/suche", data={"case_id": case_id, "csrf": csrf, "query": "Muster", "opsec": "yes"})
    assert off.status_code == 422 and "ausgeschaltet" in off.text
    on = client.post("/workbench/darknet/einstellungen", data={"case_id": case_id, "csrf": csrf, "enabled": "yes",
                                                               "socks_port": "9050", "confirmation": darknet.CONFIRMATION},
                     follow_redirects=False)
    assert on.status_code == 303 and darknet.settings(ctx)["enabled"]
    proposed = client.post("/workbench/darknet/quelle", data={"case_id": case_id, "csrf": csrf, "address": DDG, "label": "Testforum",
                                                               "category": "forum", "reason": "Hinweis aus dem Auftrag prüfen"},
                           follow_redirects=False)
    assert proposed.status_code == 303
    source = darknet.sources(ctx)[0]
    released = client.post("/workbench/darknet/entscheidung", data={"case_id": case_id, "csrf": csrf, "source_id": source["source_id"],
                                                                    "status": "freigegeben"}, follow_redirects=False)
    assert released.status_code == 303 and darknet.sources(ctx)[0]["status"] == "freigegeben"
    canned = CannedTransport({f"http://{DDG}/thread/7": (200, "text/html", PAGE, ""),
                              f"http://{AHMIA}/": (200, "text/html", AHMIA_HOME, ""),
                              f"http://{AHMIA}/search/?q=Muster&a3f9=7c21": (200, "text/html", AHMIA_RESULTS, "")})
    monkeypatch.setattr(darknet, "transport", lambda ctx, case_id: canned)
    found = client.post("/workbench/darknet/suche", data={"case_id": case_id, "csrf": csrf, "query": "Muster", "opsec": "yes"})
    assert found.status_code == 200 and "2 Treffer" in found.text and "Seite sichern" in found.text and "Als Quelle vorschlagen" in found.text
    saved = client.post("/workbench/darknet/sichern", data={"case_id": case_id, "csrf": csrf, "url": f"http://{DDG}/thread/7", "opsec": "yes"},
                        follow_redirects=False)
    assert saved.status_code == 303 and "done=gesichert" in saved.headers["location"]
    listing = client.get("/workbench/darknet", params={"case_id": case_id}).text
    assert "Angebot" in listing and f"{DDG}/thread/7" in listing and "WARC" in listing
    web = client.get("/workbench/intel/web", params={"case_id": case_id}).text
    assert "Darknet (Tor)" in web and "<summary>Seitenbild aufnehmen</summary>" not in web, "no page image for onion pages"
    missing_csrf = client.post("/workbench/darknet/quelle", data={"case_id": case_id, "csrf": "0" * 64, "address": TORPROJECT,
                                                                   "label": "x", "category": "forum", "reason": "zum Test der Prüfung"})
    assert missing_csrf.status_code == 403
