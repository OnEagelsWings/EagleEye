"""Page image through the filtering proxy, against a real headless Chromium."""
import glob
import os
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from eagleeye.application.intel492 import pageimage
from eagleeye.application.intel492.webcapture import CaptureError


def _browser():
    configured = os.environ.get("EAGLEEYE_TEST_BROWSER")
    if configured:
        return configured
    found = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
    return found[-1] if found else pageimage.find_browser()


BROWSER = _browser()
needs_browser = pytest.mark.skipif(not BROWSER, reason="kein Chromium/Edge installiert")


@pytest.fixture(autouse=True)
def ci_sandbox(monkeypatch):
    """Linux CI runners restrict user namespaces, so Chrome's sandbox cannot start there."""
    import sys
    if sys.platform.startswith("linux") and os.environ.get("CI"):
        monkeypatch.setattr(pageimage, "EXTRA_ARGS", ["--no-sandbox"])


@pytest.fixture
def site():
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            hits.append((self.headers.get("Host"), self.path))
            port = self.server.server_address[1]
            if self.path == "/slow.png":
                time.sleep(6)
            if self.path in ("/js", "/slow"):
                body = ('<!doctype html><body style="margin:0"><script>setTimeout(function(){document.body.style.background="#ff0000";'
                        'document.body.innerHTML="<div style=height:1500px>JS</div>"},300)</script>'
                        + ('<img src="/slow.png">' if self.path == "/slow" else "") + '</body>').encode()
                kind = "text/html; charset=utf-8"
            elif self.path == "/":
                body = (f'<!doctype html><title>Testseite</title><body style="margin:0">'
                        f'<div style="height:2400px;background:#123456;color:#fff">Beleg</div>'
                        f'<img src="http://site.test:{port}/ok.png">'
                        f'<img src="http://127.0.0.1:{port}/secret.png">'
                        f'<script>fetch("http://10.1.2.3/intern").catch(()=>{{}});alert("x")</script></body>').encode()
                kind = "text/html; charset=utf-8"
            else:
                body = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                        b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
                kind = "image/png"
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield {"port": server.server_address[1], "hits": hits}
    server.shutdown()


def only_site(host):
    """The test site resolves to loopback; everything else follows the real rules."""
    return ["127.0.0.1"] if host == "site.test" else pageimage.default_check(host)


def _png_size(png):
    return struct.unpack(">II", png[16:24])


@needs_browser
def test_page_image_is_taken_and_internal_requests_are_blocked(site):
    result = pageimage.take(f"http://site.test:{site['port']}/", browser=BROWSER, check=only_site, ports=None)
    width, height = _png_size(result["png"])
    facts = {k: v for k, v in result.items() if k != "png"}
    assert (width, height) == (pageimage.WIDTH, result["height"]) and height >= 2400, facts
    paths = [path for _, path in site["hits"]]
    assert "/ok.png" in paths and "/secret.png" not in paths and "/" in paths, (paths, facts)
    assert result["hosts"] == ["site.test"], facts
    assert any(b.startswith("127.0.0.1") for b in result["blocked"]), facts
    assert any(b.startswith("10.1.2.3") for b in result["blocked"]), facts
    assert result["complete"], facts


def _ask(proxy, request: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", proxy.port), timeout=5) as conn:
        conn.sendall(request)
        data = b""
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                return data
            data += chunk
            if request.startswith(b"CONNECT") and data.endswith(b"\r\n\r\n") and b" 200 " in data.split(b"\r\n")[0]:
                return data


def test_proxy_tunnels_public_and_refuses_internal_targets(site):
    with pageimage.FilterProxy(check=only_site, ports=None) as proxy:
        assert b" 403 " in _ask(proxy, b"CONNECT 127.0.0.1:443 HTTP/1.1\r\nHost: 127.0.0.1:443\r\n\r\n")
        assert b" 403 " in _ask(proxy, b"CONNECT localhost:443 HTTP/1.1\r\n\r\n")
        assert b" 403 " in _ask(proxy, b"GET http://192.168.0.1/ HTTP/1.1\r\nHost: 192.168.0.1\r\n\r\n")
        assert b" 403 " in _ask(proxy, b"GET file:///etc/passwd HTTP/1.1\r\n\r\n")
        answer = _ask(proxy, f"GET http://site.test:{site['port']}/ HTTP/1.1\r\nHost: site.test\r\nProxy-Connection: keep-alive\r\n\r\n".encode())
        assert b" 200 " in answer and b"Testseite" in answer
        with socket.create_connection(("127.0.0.1", proxy.port), timeout=5) as conn:
            conn.sendall(f"CONNECT site.test:{site['port']} HTTP/1.1\r\n\r\n".encode())
            assert b" 200 " in conn.recv(4096)
            conn.sendall(b"GET / HTTP/1.0\r\nHost: site.test\r\n\r\n")
            data = b""
            while chunk := conn.recv(65536):
                data += chunk
            assert b"Testseite" in data
        assert proxy.hosts == {"site.test"}
    with pageimage.FilterProxy() as strict:  # the real rules: standard ports only
        assert b" 403 " in _ask(strict, b"CONNECT example.com:8443 HTTP/1.1\r\n\r\n")
        assert any("8443" in b for b in strict.blocked)


def test_default_rules_and_missing_browser():
    for host in ("localhost", "printer.local", "10.0.0.5", "169.254.169.254", "[::1]", "x.onion"):
        with pytest.raises(CaptureError):
            pageimage.default_check(host)
    with pytest.raises(pageimage.ImageError, match="Kein Edge oder Chrome"):
        pageimage.take("https://example.com/", browser="")
    with pytest.raises(pageimage.ImageError, match="Kein Edge oder Chrome"):
        pageimage.take("https://example.com/", browser="/nicht/vorhanden/msedge.exe")
    assert pageimage.find_browser("/nicht/vorhanden") is None
    row = {"kind": "archive", "url": "https://a.example/", "archive_url": "https://web.archive.org/web/20200101000000id_/https://a.example/"}
    assert pageimage.target_url(row) == "https://web.archive.org/web/20200101000000if_/https://a.example/"


@needs_browser
def test_script_built_pages_are_rendered_and_slow_pages_still_give_an_image(site, monkeypatch):
    import fitz

    result = pageimage.take(f"http://site.test:{site['port']}/js", browser=BROWSER, check=only_site, ports=None)
    pixel = fitz.Pixmap(result["png"]).pixel(20, 20)
    assert tuple(pixel[:3]) == (255, 0, 0) and result["height"] >= 1500  # content made by JavaScript is in the image
    monkeypatch.setattr(pageimage, "LOAD_TIMEOUT", 2.0)
    slow = pageimage.take(f"http://site.test:{site['port']}/slow", browser=BROWSER, check=only_site, ports=None)
    assert not slow["complete"] and slow["png"].startswith(b"\x89PNG")


def test_hung_browser_start_is_retried_once_and_lock_released(monkeypatch, tmp_path):
    """A browser that hangs before opening the page is started once more; the page is never requested twice."""
    fake = tmp_path / "browser"
    fake.write_text("", encoding="utf-8")
    calls = []

    def once(url, **kw):
        calls.append(url)
        if len(calls) == 1:
            raise pageimage._StartStalled("Der Browser hat beim Start nicht rechtzeitig geantwortet.")
        return {"png": b"ok", "complete": True}

    monkeypatch.setattr(pageimage, "_take_once", once)
    assert pageimage.take("http://site.test/", browser=str(fake))["complete"] is True
    assert len(calls) == 2
    assert pageimage._ONE_AT_A_TIME.acquire(timeout=0.1)  # Sperre wieder frei
    pageimage._ONE_AT_A_TIME.release()


def test_browser_hanging_twice_gives_readable_message(monkeypatch, tmp_path):
    fake = tmp_path / "browser"
    fake.write_text("", encoding="utf-8")
    calls = []

    def stalled(url, **kw):
        calls.append(url)
        raise pageimage._StartStalled("hängt")

    monkeypatch.setattr(pageimage, "_take_once", stalled)
    with pytest.raises(pageimage.ImageError, match="nicht rechtzeitig geantwortet"):
        pageimage.take("http://site.test/", browser=str(fake))
    assert len(calls) == pageimage.START_ATTEMPTS == 2
    assert pageimage._ONE_AT_A_TIME.acquire(timeout=0.1)
    pageimage._ONE_AT_A_TIME.release()


def test_other_errors_are_not_retried(monkeypatch, tmp_path):
    fake = tmp_path / "browser"
    fake.write_text("", encoding="utf-8")
    calls = []

    def fails(url, **kw):
        calls.append(url)
        raise pageimage.ImageError("Die Seite ließ sich im Browser nicht laden (net::ERR_FAILED).")

    monkeypatch.setattr(pageimage, "_take_once", fails)
    with pytest.raises(pageimage.ImageError, match="nicht laden"):
        pageimage.take("http://site.test/", browser=str(fake))
    assert len(calls) == 1
