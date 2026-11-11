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


# ------------------------------------------- enrichment as background job
import json
import time

from eagleeye.application.intel492 import docstructure, enrichjobs
from test_build475_ai_checkpoint import member
from test_build492_intel import _pdf_with_table_and_scan


def _scan_pdf(pages=3):
    """PDF whose pages carry only an image (no text layer)."""
    doc = fitz.open()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 30), 0)
    pix.clear_with(255)
    for _ in range(pages):
        doc.new_page().insert_image(fitz.Rect(72, 72, 272, 172), pixmap=pix)
    return doc.tobytes()


def _fake_ocr(monkeypatch, engine=None, available=True):
    engine = engine or (lambda image: [{"text": "Gescannter Text einer Seite", "confidence": 90.0, "box": [300, 300, 900, 360]}])
    monkeypatch.setattr(docstructure, "ocr_available", lambda: (available, "fake-ocr" if available else ""))
    monkeypatch.setattr(docstructure, "tesseract_page", engine)


def _start(workspace, document_id, path="/workbench/intel/documents", **extra):
    app, client, user, case_id, *_ = workspace
    return client.post(path, data={"case_id": case_id, "csrf": csrf_session(workspace), "document_id": document_id, **extra},
                       follow_redirects=False)


def _kinds(ctx, user, document_id):
    anchors = ctx.document_intelligence_458.anchors(identity=user, document_id=document_id)["anchors"]
    return sorted(a["anchor_kind"] for a in anchors)


@ws
def test_enrichment_is_queued_shows_progress_and_finishes(workspace, monkeypatch):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    app.state.intel492_autostart = False
    _fake_ocr(monkeypatch)
    pdf = ctx.document_intelligence_458.import_bytes(identity=user, case_id=case_id, filename="b.pdf",
                                                     raw=_pdf_with_table_and_scan(), title="Jahresbericht")
    queued = _start(workspace, pdf["document_id"])
    assert queued.status_code == 303 and "done=queued" in queued.headers["location"]
    assert _start(workspace, pdf["document_id"]).status_code == 303, "a second click joins the active job"
    status = client.get("/workbench/intel/jobs.json", params={"case_id": case_id}).json()["jobs"]
    assert len(status) == 1 and status[0]["status"] == "queued" and status[0]["document_id"] == pdf["document_id"]
    page = client.get("/workbench/intel/documents", params={"case_id": case_id, "done": "queued"}).text
    assert "wartet auf Verarbeitung" in page and "<progress" in page and "Abbrechen" in page
    assert 'src="/workbench/intel/progress.js"' in page and "Auftrag gestartet" in page
    script = client.get("/workbench/intel/progress.js")
    assert script.status_code == 200 and script.headers["content-type"].startswith("application/javascript")
    final = enrichjobs.process_next(ctx)
    assert final["status"] == "succeeded" and final["done"] == final["total"] == 2
    assert enrichjobs.process_next(ctx) is None
    assert {"table", "heading", "ocr_paragraph"} <= set(_kinds(ctx, user, pdf["document_id"]))
    assert client.get("/workbench/intel/jobs.json", params={"case_id": case_id}).json() == {"jobs": []}
    done = client.get("/workbench/intel/documents", params={"case_id": case_id}).text
    assert "1 Tabelle" in done and "bereits ergänzt" in done and "<progress" not in done and "progress.js" not in done
    assert client.get("/workbench/intel/jobs.json", params={"case_id": workspace[5]}).json() == {"jobs": []}


@ws
def test_text_recognition_can_be_caught_up_after_installation(workspace, monkeypatch):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    app.state.intel492_autostart = False
    pdf = ctx.document_intelligence_458.import_bytes(identity=user, case_id=case_id, filename="b.pdf",
                                                     raw=_pdf_with_table_and_scan(), title="Jahresbericht")
    doc_id = pdf["document_id"]
    _fake_ocr(monkeypatch, available=False)
    assert _start(workspace, doc_id).status_code == 303 and enrichjobs.process_next(ctx)["status"] == "succeeded"
    first = _kinds(ctx, user, doc_id)
    assert "table" in first and "ocr_paragraph" not in first
    page = client.get("/workbench/intel/documents", params={"case_id": case_id}).text
    assert "gescannte Seiten noch ohne Texterkennung" in page and "Texterkennung nachholen" not in page
    assert _start(workspace, doc_id).status_code == 422, "nothing to do while no OCR engine is installed"
    _fake_ocr(monkeypatch, available=True)
    assert "Texterkennung nachholen" in client.get("/workbench/intel/documents", params={"case_id": case_id}).text
    assert _start(workspace, doc_id).status_code == 303 and enrichjobs.process_next(ctx)["status"] == "succeeded"
    second = _kinds(ctx, user, doc_id)
    assert second.count("ocr_paragraph") == 1 and second.count("table") == first.count("table"), "structure is not duplicated"
    row = docstructure.enrichment_for(ctx, doc_id)
    assert row["ocr_engine"] == "fake-ocr" and row["ocr_paragraphs"] == 1 and json.loads(row["ocr_pages"]) == [2]
    assert docstructure._hash(row) == row["record_hash"]
    service = ctx.document_intelligence_458
    assert service._document(doc_id)["state"] == "review_required"
    assert _start(workspace, doc_id).status_code == 422 and "bereits ergänzt" in client.get(
        "/workbench/intel/documents", params={"case_id": case_id}).text


@ws
def test_cancelled_run_writes_nothing_and_can_be_restarted(workspace, monkeypatch):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    app.state.intel492_autostart = False
    pdf = ctx.document_intelligence_458.import_bytes(identity=user, case_id=case_id, filename="scan.pdf",
                                                     raw=_scan_pdf(3), title="Scan")
    doc_id = pdf["document_id"]
    before = _kinds(ctx, user, doc_id)
    seen = []

    def cancelling_engine(image):
        seen.append(1)
        if len(seen) == 1:  # the user presses "Abbrechen" while page 1 is being read
            job = enrichjobs.jobs_for_case(ctx, case_id)[doc_id]
            assert _start(workspace, doc_id, path="/workbench/intel/documents/cancel", job_id=job["job_id"]).status_code == 303
        return [{"text": "Gescannter Text einer Seite", "confidence": 90.0, "box": [0, 0, 10, 10]}]

    _fake_ocr(monkeypatch, engine=cancelling_engine)
    assert _start(workspace, doc_id).status_code == 303
    assert enrichjobs.process_next(ctx)["status"] == "cancelled"
    assert len(seen) == 1, "the run stops before the next page"
    assert _kinds(ctx, user, doc_id) == before and docstructure.enrichment_for(ctx, doc_id) is None
    page = client.get("/workbench/intel/documents", params={"case_id": case_id, "done": "cancelled"}).text
    assert "Letzter Lauf wurde abgebrochen" in page and "Fundstellen ergänzen" in page and "keine Fundstellen geschrieben" in page
    # cancelling a queued job, then a clean restart
    _fake_ocr(monkeypatch)
    assert _start(workspace, doc_id).status_code == 303
    job = enrichjobs.jobs_for_case(ctx, case_id)[doc_id]
    assert _start(workspace, doc_id, path="/workbench/intel/documents/cancel", job_id=job["job_id"]).status_code == 303
    assert enrichjobs.process_next(ctx) is None
    assert _start(workspace, doc_id).status_code == 303 and enrichjobs.process_next(ctx)["status"] == "succeeded"
    assert _kinds(ctx, user, doc_id).count("ocr_paragraph") == 3


@ws
def test_failed_run_shows_a_reason_without_internals_and_can_be_retried(workspace, monkeypatch):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    app.state.intel492_autostart = False
    pdf = ctx.document_intelligence_458.import_bytes(identity=user, case_id=case_id, filename="scan.pdf",
                                                     raw=_scan_pdf(1), title="Scan")
    doc_id = pdf["document_id"]

    def broken(image):
        raise RuntimeError("secret/path/tesseract crashed")

    _fake_ocr(monkeypatch, engine=broken)
    assert _start(workspace, doc_id).status_code == 303
    assert enrichjobs.process_next(ctx)["status"] == "dead_letter"
    page = client.get("/workbench/intel/documents", params={"case_id": case_id}).text
    assert "Letzter Versuch fehlgeschlagen" in page and "RuntimeError" in page and "secret/path" not in page
    assert docstructure.enrichment_for(ctx, doc_id) is None and "Fundstellen ergänzen" in page
    _fake_ocr(monkeypatch)
    assert _start(workspace, doc_id).status_code == 303 and enrichjobs.process_next(ctx)["status"] == "succeeded"


@ws
def test_worker_thread_drains_the_queue_on_its_own(workspace, monkeypatch):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    _fake_ocr(monkeypatch)
    ids = [ctx.document_intelligence_458.import_bytes(identity=user, case_id=case_id, filename=f"s{i}.pdf",
                                                      raw=_scan_pdf(2), title=f"Scan {i}")["document_id"] for i in range(2)]
    for doc_id in ids:
        assert _start(workspace, doc_id).status_code == 303
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        jobs = enrichjobs.jobs_for_case(ctx, case_id)
        if all(jobs[d]["status"] == "succeeded" for d in ids):
            break
        time.sleep(0.05)
    assert all(enrichjobs.jobs_for_case(ctx, case_id)[d]["status"] == "succeeded" for d in ids)
    assert all(_kinds(ctx, user, d).count("ocr_paragraph") == 2 for d in ids)
    deadline = time.monotonic() + 5
    while app.state.intel492_worker is not None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert app.state.intel492_worker is None, "the worker thread ends when the queue is empty"


@ws
def test_job_permissions_type_isolation_and_restart_recovery(workspace, monkeypatch):
    app, client, admin, case_id, doc_id, other_case, other_doc = workspace
    ctx = app.state.context
    app.state.intel492_autostart = False
    _fake_ocr(monkeypatch)
    pdf = ctx.document_intelligence_458.import_bytes(identity=admin, case_id=case_id, filename="scan.pdf",
                                                     raw=_scan_pdf(1), title="Scan")["document_id"]
    engine = ctx.job_engine_348
    foreign = engine.enqueue(job_type="crawler_demo", payload={"x": 1}, case_id=case_id)
    assert _start(workspace, pdf).status_code == 303
    job = enrichjobs.jobs_for_case(ctx, case_id)[pdf]
    # a job of another case cannot be cancelled through this case
    data = {"case_id": other_case, "csrf": csrf_session(workspace), "job_id": job["job_id"]}
    assert client.post("/workbench/intel/documents/cancel", data=data).status_code == 404
    # simulate a crash mid-run: the job stays "running" with our worker id
    assert engine.claim(worker_id=enrichjobs.WORKER_ID, lease_seconds=3600, job_types=[enrichjobs.JOB_TYPE])["job_id"] == job["job_id"]
    assert enrichjobs.process_next(ctx) is None, "foreign job types are never claimed by this worker"
    assert engine.get(foreign["job_id"])["status"] == "queued"
    assert enrichjobs.recover_interrupted(ctx) == 1 and engine.get(job["job_id"])["status"] == "queued"
    assert enrichjobs.process_next(ctx)["status"] == "succeeded"
    assert engine.claim(worker_id="generic")["job_id"] == foreign["job_id"], "unfiltered claim keeps its behaviour"
    # read-only members can watch but neither start nor cancel
    second = ctx.document_intelligence_458.import_bytes(identity=admin, case_id=case_id, filename="scan2.pdf",
                                                        raw=_scan_pdf(1), title="Scan 2")["document_id"]
    member(workspace, "read_only")
    token = csrf_session(workspace, "member475", "Independent!Secret_881")
    assert client.post("/workbench/intel/documents", data={"case_id": case_id, "csrf": token, "document_id": second}).status_code == 403
    assert client.post("/workbench/intel/documents/cancel", data={"case_id": case_id, "csrf": token, "job_id": job["job_id"]}).status_code == 403
    assert "Rechercheberechtigung nötig" in client.get("/workbench/intel/documents", params={"case_id": case_id}).text
