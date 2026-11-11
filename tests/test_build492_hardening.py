"""Build 492 hardening (plan stage 1): redirects, compression, charset, PDF capture,
address fallback and rate limits. Network access is simulated; no live result is claimed.
"""
import gzip
import hashlib
import re
import zlib

import fitz
import pytest

from eagleeye.application.intel492 import captures, webcapture
from eagleeye.application.intel492.throttle import Throttle
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build492_intel import ARTICLE, FakeTransport, csrf_session, fake_network, ws  # noqa: F401

HTML = [("Content-Type", "text/html; charset=utf-8")]
RealTransport = webcapture.PinnedTransport  # the autouse fixture replaces the module attribute per test


def post(workspace, url, **extra):
    app, client, user, case_id, *_ = workspace
    data = {"case_id": case_id, "csrf": csrf_session(workspace), "url": url, "opsec": "yes", **extra}
    return client.post("/workbench/intel/web", data=data, follow_redirects=False)


def hidden(html, name):
    return re.findall(r'<input type="hidden" name="' + name + r'" value="([^"]*)"', html)


# ------------------------------------------------------------------ redirects
@ws
def test_same_server_redirects_are_followed_and_recorded_in_the_warc(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    fake_network.responses.update({
        "http://news.example/": (301, [("Location", "https://www.news.example/")], b""),
        "https://www.news.example/": (302, [("Location", "/de/")], b""),
        "https://www.news.example/de/": (200, HTML, ARTICLE)})
    assert post(workspace, "http://news.example/").status_code == 303
    assert fake_network.calls == ["http://news.example/", "https://www.news.example/", "https://www.news.example/de/"]
    row = captures.captures_for_case(ctx, case_id)[0]
    assert row["integrity_ok"] and row["url"] == "https://www.news.example/de/"
    responses = webcapture.read_warc_responses(captures.warc_bytes(ctx, row))
    assert [(u, s) for u, s, _ in responses] == [("http://news.example/", 301), ("https://www.news.example/", 302),
                                                ("https://www.news.example/de/", 200)]
    text = " ".join(a["text_excerpt"] for a in ctx.document_intelligence_458.anchors(
        identity=user, document_id=row["document_id"])["anchors"])
    assert "Angefragte Adresse: http://news.example/" in text and "Automatisch gefolgt (gleicher Server)" in text


@ws
def test_other_server_redirect_needs_confirmation_and_keeps_the_chain(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    fake_network.responses.update({
        "https://short.example/abc": (302, [("Location", "//news.example/x?utm=1")], b""),
        "https://news.example/x?utm=1": (200, HTML, ARTICLE)})
    first = post(workspace, "https://short.example/abc")
    assert first.status_code == 200 and "Die Seite leitet weiter" in first.text
    assert fake_network.calls == ["https://short.example/abc"], "the other server is not contacted without consent"
    assert captures.captures_for_case(ctx, case_id) == []
    target, via = hidden(first.text, "url"), hidden(first.text, "via")
    assert target == ["https://news.example/x?utm=1"] and via == ["https://short.example/abc"]
    assert post(workspace, target[0], via=via).status_code == 303
    row = captures.captures_for_case(ctx, case_id)[0]
    text = " ".join(a["text_excerpt"] for a in ctx.document_intelligence_458.anchors(
        identity=user, document_id=row["document_id"])["anchors"])
    assert "Weiterleitungskette (einzeln bestätigt): https://short.example/abc → https://news.example/x?utm=1" in text


@ws
def test_confirmed_redirect_chain_is_limited_to_three_steps(workspace, fake_network):
    hosts = ["a", "b", "c", "d", "e"]
    for here, there in zip(hosts, hosts[1:]):
        fake_network.responses[f"https://{here}.example/"] = (302, [("Location", f"https://{there}.example/")], b"")
    page = post(workspace, "https://a.example/")
    for step in range(3):
        via = hidden(page.text, "via")
        assert len(via) == step + 1 and "Weiterleitungsziel sichern" in page.text
        page = post(workspace, hidden(page.text, "url")[0], via=via)
    assert "länger als 3 bestätigte Schritte" in page.text and "Weiterleitungsziel sichern" not in page.text
    assert fake_network.calls == [f"https://{h}.example/" for h in "abcd"]


@ws
@pytest.mark.parametrize("location,reason", [
    ("http://192.168.1.1/admin", "nicht-öffentliches Netz"),
    ("/start", "Weiterleitungsschleife"),
    ("ftp://files.example/x", "Nur http- und https-Adressen"),
    ("", "kein Weiterleitungsziel"),
])
def test_unsafe_or_looping_redirect_targets_offer_no_button(workspace, fake_network, location, reason):
    fake_network.responses["https://news.example/start"] = (302, [("Location", location)] if location else [], b"")
    page = post(workspace, "https://news.example/start")
    assert page.status_code == 200 and reason in page.text and "Weiterleitungsziel sichern" not in page.text
    assert fake_network.calls == ["https://news.example/start"]


# ------------------------------------------------- compression and charset
@ws
def test_compressed_latin1_page_is_decoded_and_original_bytes_are_kept(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    page = ("<html><head><meta charset=\"iso-8859-1\"><title>Prüfung</title></head><body><article><p>"
            "Jürgen Müller prüft die Übernahme der Größe nach. Der Kaufpreis wurde bislang nicht öffentlich genannt."
            "</p></article></body></html>").encode("iso-8859-1")
    packed = gzip.compress(page)
    fake_network.responses["https://news.example/x"] = (200, [("Content-Type", "text/html"), ("Content-Encoding", "gzip")], packed)
    assert post(workspace, "https://news.example/x").status_code == 303
    row = captures.captures_for_case(ctx, case_id)[0]
    assert row["integrity_ok"] and row["body_sha256"] == hashlib.sha256(packed).hexdigest()
    assert webcapture.read_warc_response(captures.warc_bytes(ctx, row))[2] == packed
    text = " ".join(a["text_excerpt"] for a in ctx.document_intelligence_458.anchors(
        identity=user, document_id=row["document_id"])["anchors"])
    assert "Jürgen Müller prüft die Übernahme der Größe" in text and "Zeichensatz: Meta-Angabe der Seite" in text


@ws
@pytest.mark.parametrize("mode", ["bomb", "brotli", "corrupt"])
def test_unsafe_compression_stores_nothing(workspace, fake_network, mode):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    body, encoding = {"bomb": (gzip.compress(b"a" * (8 * 1024 * 1024)), "gzip"), "brotli": (b"\x1b\x00", "br"),
                      "corrupt": (b"not gzip at all", "gzip")}[mode]
    fake_network.responses["https://news.example/x"] = (200, [("Content-Type", "text/html"), ("Content-Encoding", encoding)], body)
    response = post(workspace, "https://news.example/x")
    assert response.status_code == 422 and 'role="alert"' in response.text
    assert captures.captures_for_case(ctx, case_id) == [] and list(captures.warc_root(ctx).iterdir()) == []


def test_charset_precedence_and_fallbacks():
    cyr = "Владимир Иванов сообщил, что компания не комментирует сделку. " * 4
    assert webcapture.decode_text(cyr.encode("cp1251"), "text/html; charset=windows-1251")[0] == cyr
    assert webcapture.decode_text(cyr.encode("cp1251"), "text/html")[0] == cyr  # detected
    assert webcapture.decode_text("﻿Größe".encode("utf-8"), "text/html; charset=iso-8859-1") == ("Größe", "BOM")
    text, how = webcapture.decode_text("Größe Müller äöü ".encode("iso-8859-1") * 5, "text/plain; charset=utf-8")
    assert "Größe Müller" in text and "windows-1252" in how  # wrong header must not garble umlauts
    assert webcapture.decode_text(b"plain ascii", "text/plain; charset=does-not-exist")[0] == "plain ascii"
    raw = zlib.compress(b"x" * 100)[2:-4]  # raw deflate without zlib wrapper
    result = webcapture.HttpResult("u", 200, "OK", [("Content-Encoding", "deflate")], raw, "1.1.1.1")
    assert webcapture.decoded_body(result, 1000) == b"x" * 100


# ------------------------------------------------------------------------ PDF
def _pdf(text="Handelsregisterauszug der Y GmbH mit Sitz in Hamburg, Stand März 2025."):
    doc = fitz.open()
    doc.new_page().insert_text((72, 100), text, fontsize=12)
    doc.set_metadata({"title": "Registerauszug Y GmbH", "author": "Amtsgericht Hamburg", "creationDate": "D:20250304120000+01'00'"})
    return doc.tobytes()


@ws
def test_pdf_address_is_stored_as_warc_and_imported_as_pdf_document(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    pdf = _pdf()
    url = "https://register.example/docs/auszug%20y.pdf"
    fake_network.responses[url] = (200, [("Content-Type", "application/pdf")], pdf)
    done = post(workspace, url)
    assert done.status_code == 303 and "done=pdf" in done.headers["location"]
    row = captures.captures_for_case(ctx, case_id)[0]
    assert row["integrity_ok"] and row["content_type"] == "application/pdf"
    assert row["page_title"] == "Registerauszug Y GmbH" and row["page_author"] == "Amtsgericht Hamburg"
    assert row["page_published"] == "2025-03-04" and row["body_sha256"] == hashlib.sha256(pdf).hexdigest()
    doc = ctx.document_intelligence_458._document(row["document_id"])
    assert doc["media_type"] == "application/pdf" and doc["document_sha256"] == hashlib.sha256(pdf).hexdigest()
    assert doc["source_url"] == url and doc["state"] == "review_required"
    anchors = ctx.document_intelligence_458.anchors(identity=user, document_id=row["document_id"])["anchors"]
    assert any("Handelsregisterauszug der Y GmbH" in a["text_excerpt"] for a in anchors)
    listing = client.get("/workbench/intel/web", params={"case_id": case_id, "done": "pdf"}).text
    assert "PDF gesichert" in listing and '<span class="pill">PDF</span>' in listing
    # The captured PDF can be enriched like an uploaded one.
    assert "Registerauszug Y GmbH" in client.get("/workbench/intel/documents", params={"case_id": case_id}).text


@ws
@pytest.mark.parametrize("mode", ["broken", "mislabelled", "too_large"])
def test_unusable_pdf_stores_nothing_and_explains(workspace, fake_network, mode):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    body = {"broken": b"%PDF-1.4 garbage", "mislabelled": b"<html>not a pdf</html>",
            "too_large": b"%PDF-" + b"0" * webcapture.MAX_PDF}[mode]
    fake_network.responses["https://register.example/a.pdf"] = (200, [("Content-Type", "application/pdf")], body)
    response = post(workspace, "https://register.example/a.pdf")
    assert response.status_code == 422 and 'role="alert"' in response.text
    assert "pymupdf" not in response.text.lower() and "traceback" not in response.text.lower()
    assert captures.captures_for_case(ctx, case_id) == [] and list(captures.warc_root(ctx).iterdir()) == []
    assert len(ctx.document_intelligence_458.documents(identity=user, case_id=case_id)) == 1


# ----------------------------------------------------------------- rate limit
@ws
def test_rate_limit_per_server_and_per_user(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    now = [1000.0]
    app.state.intel492_throttle = Throttle(per_user=4, per_host=2, clock=lambda: now[0])
    for host in ("a", "b", "c"):
        fake_network.responses[f"https://{host}.example/"] = (200, HTML, ARTICLE)
    assert post(workspace, "https://a.example/").status_code == 303
    assert post(workspace, "https://a.example/").status_code == 303
    blocked = post(workspace, "https://a.example/")
    assert blocked.status_code == 429 and "höchstens 2 Abrufe pro Minute je Zielserver" in blocked.text
    assert fake_network.calls.count("https://a.example/") == 2, "a throttled request never reaches the network"
    assert post(workspace, "https://b.example/").status_code == 303
    assert post(workspace, "https://b.example/").status_code == 303
    limited = post(workspace, "https://c.example/")
    assert limited.status_code == 429 and "höchstens 4 Abrufe pro Minute." in limited.text
    now[0] += 61
    assert post(workspace, "https://c.example/").status_code == 303
    # Listing archive versions counts against web.archive.org.
    app.state.intel492_throttle = Throttle(per_user=10, per_host=1, clock=lambda: now[0])
    data = {"case_id": case_id, "csrf": csrf_session(workspace), "archive_url": "https://a.example/", "opsec": "yes"}
    assert client.post("/workbench/intel/web/wayback", data=data).status_code == 422  # simulated 404 from archive
    assert client.post("/workbench/intel/web/wayback", data=data).status_code == 429


def test_throttle_does_not_count_refused_attempts():
    now = [0.0]
    throttle = Throttle(per_user=2, per_host=5, clock=lambda: now[0])
    assert throttle.check("u", "h1") == (0, "") and throttle.check("u", "h2") == (0, "")
    for _ in range(5):
        wait, scope = throttle.check("u", "h3")
        assert scope == "user" and 1 <= wait <= 61
    now[0] = 61
    assert throttle.check("u", "h3") == (0, "")


# ------------------------------------------------------------ address fallback
class _Conn:
    tried, body = [], b"ok"

    def __init__(self, host, ip, **kw):
        self.ip = ip

    def connect(self):
        _Conn.tried.append(self.ip)
        if self.ip.startswith("2001"):
            raise OSError("network unreachable")

    def close(self):
        pass

    def putrequest(self, *a, **k):
        pass

    putheader = endheaders = lambda self, *a: None

    def getresponse(self):
        class Response:
            status, reason = 200, "OK"

            def getheaders(self):
                return [("Content-Type", "text/html")]

            def read(self, n):
                return _Conn.body
        return Response()


def test_transport_validates_every_address_then_tries_them_in_order():
    _Conn.tried = []
    transport = RealTransport(resolver=lambda host: ["2001:4860:4860::8888", "93.184.216.34"])
    transport.connection_classes = {"https": _Conn, "http": _Conn}
    result = transport.get("https://news.example/", accept="text/html")
    assert _Conn.tried == ["2001:4860:4860::8888", "93.184.216.34"] and result.ip_address == "93.184.216.34"
    assert result.fetched_at
    _Conn.tried = []
    mixed = RealTransport(resolver=lambda host: ["93.184.216.34", "10.0.0.7"])
    mixed.connection_classes = {"https": _Conn, "http": _Conn}
    with pytest.raises(webcapture.CaptureError):
        mixed.get("https://rebind.example/", accept="text/html")
    assert _Conn.tried == [], "one private answer blocks the host before any connection"
    dead = RealTransport(resolver=lambda host: ["2001:4860:4860::8888", "2001:4860:4860::8844"])
    dead.connection_classes = {"https": _Conn, "http": _Conn}
    with pytest.raises(webcapture.CaptureError, match="nicht erreichbar"):
        dead.get("https://news.example/", accept="text/html")
