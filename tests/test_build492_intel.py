"""Build 492: web evidence capture, structure/OCR anchors, source families,
entity candidates and network analysis inside the real case workspace.

Network access is simulated with injected transports; no live third-party result is
claimed by these tests.
"""
import gzip
import hashlib
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz
import pytest

from eagleeye.application.entity_registry461 import EntityRegistry461
from eagleeye.application.intel492 import captures, docstructure, enrichjobs, webcapture
from eagleeye.application.intel492.entitymatch import compare_names, ftm_entities, suggest_case_pairs_492
from eagleeye.application.build488.candidates import suggest_case_pairs
from eagleeye.interfaces.web.app448 import COOKIE
from eagleeye.interfaces.web.app364 import CSRF_COOKIE
from eagleeye.interfaces.web.app492 import create_workspace_app492
from test_build471_local_ai import workspace  # noqa: F401  (fixture)
from test_build475_ai_checkpoint import member

ws = pytest.mark.parametrize("workspace", [create_workspace_app492], indirect=True)
DATA = Path(__file__).parent / "benchmarks"

ARTICLE = ("<html><head><title>Firma X übernimmt Y</title><meta name='author' content='Anna Muster'>"
           "<meta property='article:published_time' content='2026-03-04T10:00:00Z'></head><body>"
           "<nav>Home | Politik | Wirtschaft | Sport</nav><article><h1>Firma X übernimmt Y</h1>"
           "<p>Die Firma X hat am Montag die vollständige Übernahme der Y GmbH mit Sitz in Hamburg bekanntgegeben. "
           "Der Kaufpreis wurde nicht genannt.</p><p>Laut Handelsregister ist Max Beispiel seit 2021 Geschäftsführer "
           "der Y GmbH. Eine Anfrage an das Unternehmen blieb bis Redaktionsschluss unbeantwortet.</p></article>"
           "<footer>Impressum Datenschutz Cookies</footer></body></html>").encode("utf-8")


class FakeTransport:
    """Replaces the pinned network transport; records every requested URL."""
    calls = []
    responses = {}

    def __init__(self, *args, **kwargs):
        pass

    def get(self, url, *, accept):
        FakeTransport.calls.append(url)
        status, headers, body = FakeTransport.responses.get(url, (404, [("Content-Type", "text/html")], b"missing"))
        return webcapture.HttpResult(url, status, "OK" if status == 200 else "X", headers, body, "93.184.216.34",
                                     [("Host", url.split("/")[2]), ("User-Agent", webcapture.USER_AGENT)])


@pytest.fixture(autouse=True)
def fake_network(monkeypatch):
    FakeTransport.calls = []
    FakeTransport.responses = {}
    monkeypatch.setattr(webcapture, "PinnedTransport", FakeTransport)
    yield FakeTransport


def csrf_session(workspace, username="qa471", password="Build471!Password_88"):
    app, client, *_ = workspace
    ctx = app.state.context
    session = ctx.team_identity_359.authenticate(username=username, password=password,
        client_fingerprint=hashlib.sha256(b"testclient||testclient").hexdigest())
    client.cookies.clear()
    client.cookies.set(COOKIE, session.token)
    client.cookies.set(CSRF_COOKIE, session.csrf_token)
    return session.csrf_token


def registry(app):
    return EntityRegistry461(Path(app.state.context.base_dir) / "entity_registry_462.sqlite3")


# ---------------------------------------------------------------- workflow / hub
@ws
def test_guided_workflow_and_hub_offer_the_new_tools_once(workspace):
    app, client, user, case_id, *_ = workspace
    flow = client.get("/workbench", params={"case_id": case_id}).text
    for label in ("Webseite als Beleg sichern", "Struktur &amp; Texterkennung", "Quellenunabhängigkeit", "Netzwerkanalyse"):
        assert flow.count(label) == 1, label
    numbers = [int(part.split(".")[0]) for part in flow.split("<h2>")[1:] if part.split(".")[0].isdigit()]
    assert numbers == list(range(1, len(numbers) + 1)), "steps are numbered continuously"
    hub = client.get("/workbench/intel", params={"case_id": case_id})
    assert hub.status_code == 200 and "Prüfmaterial" in hub.text
    assert hub.headers["Referrer-Policy"] in {"same-origin", "no-referrer"}  # never leaks to other sites
    assert client.get("/workbench/intel", params={"case_id": "foreign-case"}).status_code == 403


# ----------------------------------------------------------------- web capture
@ws
def test_live_capture_stores_warc_and_reviewable_text_document(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    fake_network.responses["https://news.example/x"] = (200, [("Content-Type", "text/html; charset=utf-8")], ARTICLE)
    token = csrf_session(workspace)
    response = client.post("/workbench/intel/web", data={"case_id": case_id, "csrf": token,
                           "url": "https://news.example/x", "opsec": "yes"}, follow_redirects=False)
    assert response.status_code == 303
    row = captures.captures_for_case(ctx, case_id)[0]
    assert row["integrity_ok"] and row["kind"] == "live" and row["page_author"] == "Anna Muster"
    doc = ctx.document_intelligence_458._document(row["document_id"])
    assert doc["state"] == "review_required" and doc["source_url"] == "https://news.example/x"
    anchors = ctx.document_intelligence_458.anchors(identity=user, document_id=row["document_id"])["anchors"]
    texts = " ".join(a["text_excerpt"] for a in anchors)
    assert "Max Beispiel seit 2021" in texts and "Impressum" not in texts and "Politik | Wirtschaft" not in texts
    assert row["body_sha256"] == hashlib.sha256(ARTICLE).hexdigest() and row["body_sha256"] in texts
    listing = client.get("/workbench/intel/web", params={"case_id": case_id, "done": "live"}).text
    assert "Seite gesichert" in listing and "✓ unverändert" in listing and "Befund notieren" in listing
    warc = client.get("/workbench/intel/warc", params={"case_id": case_id, "capture_id": row["capture_id"]})
    assert warc.status_code == 200 and warc.headers["content-type"] == "application/warc"
    assert webcapture.read_warc_response(warc.content) == ("https://news.example/x", 200, ARTICLE)
    assert b"WARC/1.1" in gzip.decompress(warc.content)
    # Tampering is detected and the download refused.
    path = captures.warc_root(ctx) / row["warc_relpath"]
    path.write_bytes(path.read_bytes()[:-5] + b"xxxxx")
    assert not captures.captures_for_case(ctx, case_id)[0]["integrity_ok"]
    assert client.get("/workbench/intel/warc", params={"case_id": case_id, "capture_id": row["capture_id"]}).status_code == 409
    other = workspace[5]
    assert client.get("/workbench/intel/warc", params={"case_id": other, "capture_id": row["capture_id"]}).status_code in {403, 409}


@ws
@pytest.mark.parametrize("mode", ["no_opsec", "csrf", "origin", "private", "redirect", "not_html", "no_text", "too_large"])
def test_capture_guards_store_nothing(workspace, fake_network, mode):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    url = "https://news.example/x"
    fake_network.responses[url] = (200, [("Content-Type", "text/html")], ARTICLE)
    data = {"case_id": case_id, "csrf": csrf_session(workspace), "url": url, "opsec": "yes"}
    headers = {}
    if mode == "no_opsec":
        data.pop("opsec")
    if mode == "csrf":
        data["csrf"] = "forged"
    if mode == "origin":
        headers["Origin"] = "https://evil.example"
    if mode == "private":
        data["url"] = "http://192.168.0.10/admin"
    if mode == "redirect":
        fake_network.responses[url] = (302, [("Location", "https://other.example/login")], b"")
    if mode == "not_html":
        fake_network.responses[url] = (200, [("Content-Type", "image/png")], b"\x89PNG....")
    if mode == "no_text":
        fake_network.responses[url] = (200, [("Content-Type", "text/html")], b"<html><body><nav>x</nav></body></html>")
    if mode == "too_large":
        fake_network.responses[url] = (200, [("Content-Type", "text/html")], b"a" * (webcapture.MAX_BODY + 1))
    response = client.post("/workbench/intel/web", data=data, headers=headers, follow_redirects=False)
    if mode in {"csrf", "origin"}:
        assert response.status_code == 403
    elif mode == "redirect":
        assert response.status_code == 200 and "Die Seite leitet weiter" in response.text
        assert "https://other.example/login" in response.text and fake_network.calls == [url]
    else:
        assert response.status_code == 422 and 'role="alert"' in response.text
    if mode == "private":
        assert fake_network.calls == [] and "nicht-öffentliches Netz" in response.text
    assert captures.captures_for_case(ctx, case_id) == []
    assert len(ctx.document_intelligence_458.documents(identity=user, case_id=case_id)) == 1
    assert list(captures.warc_root(ctx).iterdir()) == []


@ws
def test_read_only_member_can_view_but_not_capture(workspace, fake_network):
    app, client, admin, case_id, *_ = workspace
    member(workspace, "read_only")
    token = csrf_session(workspace, "member475", "Independent!Secret_881")
    view = client.get("/workbench/intel/web", params={"case_id": case_id}).text
    assert "Rechercheberechtigung" in view and 'name="url"' not in view
    response = client.post("/workbench/intel/web", data={"case_id": case_id, "csrf": token,
                           "url": "https://news.example/x", "opsec": "yes"})
    assert response.status_code == 403 and fake_network.calls == []


@ws
def test_wayback_versions_are_listed_and_archived_bytes_captured(workspace, fake_network):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    original = "https://news.example/x"
    cdx = json.dumps([["timestamp", "original", "statuscode", "mimetype", "digest"],
                      ["20250101120000", original, "200", "text/html", "AAA"],
                      ["20260101120000", original, "200", "text/html", "BBB"]]).encode()
    fake_network.responses.update({
        "https://web.archive.org/cdx/search/cdx?url=https%3A%2F%2Fnews.example%2Fx&output=json&limit=30&"
        "fl=timestamp%2Coriginal%2Cstatuscode%2Cmimetype%2Cdigest&filter=statuscode%3A200&collapse=digest":
            (200, [("Content-Type", "application/json")], cdx),
        "https://web.archive.org/web/20250101120000id_/https://news.example/x":
            (200, [("Content-Type", "text/html; charset=utf-8")], ARTICLE)})
    token = csrf_session(workspace)
    listed = client.post("/workbench/intel/web/wayback", data={"case_id": case_id, "csrf": token,
                         "archive_url": original, "opsec": "yes"})
    assert listed.status_code == 200 and "2 unterschiedliche archivierte Fassungen" in listed.text
    assert "01.01.2025 12:00 UTC" in listed.text
    stored = client.post("/workbench/intel/web/archive", data={"case_id": case_id, "csrf": token, "url": original,
                         "timestamp": "20250101120000", "opsec": "yes"}, follow_redirects=False)
    assert stored.status_code == 303
    row = captures.captures_for_case(ctx, case_id)[0]
    assert row["kind"] == "archive" and row["url"] == original
    assert row["archive_url"] == "https://web.archive.org/web/20250101120000id_/https://news.example/x"
    assert ctx.document_intelligence_458._document(row["document_id"])["title"].startswith("Archiv: ")
    assert client.post("/workbench/intel/web/wayback", data={"case_id": case_id, "csrf": token,
                       "archive_url": original}).status_code == 422


def test_url_and_address_guards():
    for bad in ["http://127.0.0.1/", "https://10.1.2.3/", "http://[::1]/", "https://169.254.169.254/x",
                "ftp://files.example/", "https://user:pw@x.example/", "https://x.example:8443/", "https://intranet.local/",
                "https://abc.onion/", "javascript:alert(1)", "https://x.example/a b"]:
        with pytest.raises(webcapture.CaptureError):
            url = webcapture.normalize_public_url(bad)
            webcapture.public_addresses(url.split("/")[2].strip("[]"), resolver=lambda h: ["93.184.216.34"])
    with pytest.raises(webcapture.CaptureError):
        webcapture.public_addresses("rebind.example", resolver=lambda h: ["93.184.216.34", "10.0.0.5"])
    assert webcapture.normalize_public_url("HTTPS://Bücher.Example/a?b=1#frag") == "https://xn--bcher-kva.example/a?b=1"
    with pytest.raises(webcapture.CaptureError):
        webcapture.wayback_raw_url("2025", "https://x.example/")


# ------------------------------------------------------------ structure / OCR
def _pdf_with_table_and_scan():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 80), "Jahresbericht 2025", fontsize=22)
    page.insert_text((72, 120), "Die Y GmbH wurde 2001 gegründet und hat ihren Sitz in Hamburg.", fontsize=11)
    x0, y0, w, h = 72, 150, 300, 20
    for r in range(4):
        page.draw_line((x0, y0 + r * h), (x0 + w, y0 + r * h))
    for c in range(3):
        page.draw_line((x0 + c * 150, y0), (x0 + c * 150, y0 + 3 * h))
    for r, row in enumerate([["Name", "Funktion"], ["Max Beispiel", "Geschäftsführer"], ["Eva Test", "Prokuristin"]]):
        for c, text in enumerate(row):
            page.insert_text((x0 + 5 + c * 150, y0 + 14 + r * h), text, fontsize=10)
    scan = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 50), 0)
    pix.clear_with(255)
    scan.insert_image(fitz.Rect(72, 72, 272, 122), pixmap=pix)
    return doc.tobytes()


@ws
def test_structure_and_ocr_anchors_are_added_before_review_only(workspace, monkeypatch):
    app, client, user, case_id, *_ = workspace
    ctx = app.state.context
    service = ctx.document_intelligence_458
    pdf = service.import_bytes(identity=user, case_id=case_id, filename="bericht.pdf", raw=_pdf_with_table_and_scan(),
                               title="Jahresbericht", source_url="https://example.org/bericht.pdf")
    before = service.anchors(identity=user, document_id=pdf["document_id"])["anchors"]
    fake_ocr = lambda image: [{"text": "Gescannter Text der zweiten Seite", "confidence": 91.5, "box": [300, 300, 900, 360]}]
    monkeypatch.setattr(docstructure, "ocr_available", lambda: (True, "fake-ocr"))
    monkeypatch.setattr(docstructure, "tesseract_page", fake_ocr)
    token = csrf_session(workspace)
    app.state.intel492_autostart = False  # run the queued job in this thread, deterministically
    view = client.get("/workbench/intel/documents", params={"case_id": case_id}).text
    assert "Jahresbericht" in view and "Fundstellen ergänzen" in view
    assert client.post("/workbench/intel/documents", data={"case_id": case_id, "csrf": token,
                       "document_id": pdf["document_id"]}, follow_redirects=False).status_code == 303
    assert len(service.anchors(identity=user, document_id=pdf["document_id"])["anchors"]) == len(before)
    assert enrichjobs.process_next(ctx)["status"] == "succeeded"
    after = service.anchors(identity=user, document_id=pdf["document_id"])["anchors"]
    kinds = {a["anchor_kind"] for a in after}
    assert {"table", "heading", "ocr_paragraph"} <= kinds and len(after) > len(before)
    table = next(a for a in after if a["anchor_kind"] == "table")
    assert "Max Beispiel | Geschäftsführer" in table["text_excerpt"] and table["bbox"]
    ocr = next(a for a in after if a["anchor_kind"] == "ocr_paragraph")
    assert ocr["page_number"] == 2 and ocr["extraction_method"] == "ocr_tesseract"
    assert all(service._rh(service._anchor(a["anchor_id"])) == service._anchor(a["anchor_id"])["record_hash"] for a in after)
    doc = service._document(pdf["document_id"])
    assert doc["state"] == "review_required" and doc["record_hash"] == service._rh(doc)
    assert "Ø Erkennungssicherheit 91,5" in client.get("/workbench/intel/documents", params={"case_id": case_id}).text
    # second run and wrong case are refused
    assert client.post("/workbench/intel/documents", data={"case_id": case_id, "csrf": token,
                       "document_id": pdf["document_id"]}).status_code == 422
    assert client.post("/workbench/intel/documents", data={"case_id": workspace[5], "csrf": token,
                       "document_id": pdf["document_id"]}).status_code == 403


@ws
def test_reviewed_pdf_cannot_be_enriched(workspace):
    app, client, user, case_id, *_ = workspace
    service = app.state.context.document_intelligence_458
    pdf = service.import_bytes(identity=user, case_id=case_id, filename="b.pdf", raw=_pdf_with_table_and_scan(), title="B")
    doc = service._document(pdf["document_id"])
    service.review_extraction(identity=user, document_id=pdf["document_id"], expected_document_hash=doc["record_hash"],
                              decision="approve", note="Extraktion stichprobenartig geprüft.", confirmation="REVIEW DOCUMENT EXTRACTION 458")
    with pytest.raises(ValueError, match="bereits geprüft"):
        docstructure.enrich_document(app.state.context, identity=user, document_id=pdf["document_id"])
    assert "bereits geprüft" in client.get("/workbench/intel/documents", params={"case_id": case_id}).text


@pytest.mark.skipif(not docstructure.ocr_available()[0], reason="Tesseract binary not installed")
def test_real_tesseract_reads_scanned_page():
    src = fitz.open()
    page = src.new_page()
    page.insert_text((72, 100), "Die Y GmbH hat ihren Sitz in Hamburg.", fontsize=16)
    pix = page.get_pixmap(dpi=200)
    scanned = fitz.open()
    scanned.new_page().insert_image(fitz.Rect(0, 0, 595, 842), pixmap=pix)
    result = docstructure.analyse_pdf(scanned.tobytes(), ocr_pages=[1], ocr_engine=docstructure.tesseract_page)
    text = " ".join(i["text_excerpt"] for i in result["items"] if i["anchor_kind"] == "ocr_paragraph")
    assert "Hamburg" in text and result["ocr_mean_confidence"] > 60


# ------------------------------------------------------------- source families
@ws
def test_source_families_count_independent_origins(workspace):
    app, client, user, case_id, *_ = workspace
    service = app.state.context.document_intelligence_458
    agency = ("Die Firma X hat am Montag die vollständige Übernahme der Y GmbH mit Sitz in Hamburg bekanntgegeben. "
              "Der Kaufpreis wurde nicht genannt. Nach Angaben aus Unternehmenskreisen soll die Transaktion bis Ende "
              "des Jahres abgeschlossen sein. Die Kartellbehörde muss noch zustimmen. Beide Unternehmen beschäftigen "
              "zusammen rund 2000 Mitarbeiter in Deutschland und Österreich.")
    texts = {"agentur": agency, "zeitung1": agency + " Die Redaktion hat bei X nachgefragt.",
             "zeitung2": "Hamburg (dpa) " + agency.replace("Montag", "Dienstag"),
             "eigen": "Im Handelsregister ist seit 2021 Max Beispiel als Geschäftsführer der Y GmbH eingetragen. "
                      "Er war zuvor bei einer Beratungsfirma in München tätig und ist an zwei weiteren Gesellschaften "
                      "beteiligt, deren Jahresabschlüsse seit 2023 fehlen. Eine Anfrage blieb unbeantwortet."}
    for name, text in texts.items():
        service.import_bytes(identity=user, case_id=case_id, filename=name + ".txt", raw=text.encode(), title=name,
                             source_url=f"https://{name}.example/a")
    view = client.get("/workbench/intel/lineage", params={"case_id": case_id})
    assert view.status_code == 200
    html = view.text
    assert '<span class="stat">4</span>Dokumente verglichen' in html
    assert '<span class="stat">2</span>unabhängige Ursprünge' in html
    assert '<span class="stat">2</span>Übernahmen / Spiegelungen' in html
    assert "3 Dokumente mit weitgehend gleichem Text" in html and "kein Nachweis des Ursprungs" in html
    assert "zu wenig Text" in html  # the short fixture document is listed, not silently dropped
    assert client.get("/workbench/intel/lineage", params={"case_id": case_id, "level": "<script>"}).status_code == 200


# ---------------------------------------------------------- entities / network
@ws
def test_entity_review_page_uses_stronger_explained_candidates(workspace):
    app, client, user, case_id, *_ = workspace
    with registry(app) as reg:
        a = reg.create_entity(case_id=case_id, kind="person", label="Max Müller")
        b = reg.create_entity(case_id=case_id, kind="person", label="Mueller, Max")
        reg.create_entity(case_id=case_id, kind="person", label="Moritz Müller")
        reg.create_entity(case_id=case_id, kind="company", label="Y GmbH")
        reg.create_entity(case_id=case_id, kind="organization", label="Y Gmbh")
    page = client.get("/workbench/entities488", params={"case_id": case_id}).text
    assert "Max Müller" in page and "Mueller, Max" in page
    assert "Moritz Müller ↔" not in page and "↔ Moritz Müller" not in page
    assert "gleiche Schreibweise nach Normalisierung" in page  # company vs organization compared
    token = csrf_session(workspace)
    saved = client.post("/workbench/entities488", data={"case_id": case_id, "csrf": token, "left_entity_id": a["id"],
                        "right_entity_id": b["id"], "decision": "possible_match", "confirm": "yes",
                        "rationale": "Gleiche Person laut Impressum und Handelsregister, noch unbestätigt."},
                        follow_redirects=False)
    assert saved.status_code == 303
    lines = client.get("/workbench/intel/ftm.json", params={"case_id": case_id}).text.strip().splitlines()
    entities = [json.loads(line) for line in lines]
    assert {e["schema"] for e in entities} >= {"Person", "Company", "Organization", "Note"}
    assert all(e["eagleeye"]["verified"] is False for e in entities)


def test_holdout_benchmark_improves_precision_and_recall():
    pairs = json.loads((DATA / "entity_pairs_492_holdout.json").read_text(encoding="utf-8"))["pairs"]

    def score(fn):
        tp = fp = fn_ = 0
        for kind, left, right, same in pairs:
            hit = bool(fn("c", [{"case_id": "c", "entity_id": "l", "name": left, "entity_type": kind},
                                {"case_id": "c", "entity_id": "r", "name": right, "entity_type": kind}]))
            tp += hit and same
            fp += hit and not same
            fn_ += (not hit) and same
        return tp / (tp + fp), tp / (tp + fn_)

    old_p, old_r = score(suggest_case_pairs)
    new_p, new_r = score(suggest_case_pairs_492)
    assert new_p >= 0.9 and new_r >= 0.9
    assert new_p > old_p and new_r > old_r
    assert compare_names("Владимир Иванов", "Vladimir Ivanov")[0] >= 0.88
    assert compare_names("Peter Schmidt", "Petra Schmidt")[0] < 0.88


@ws
def test_network_analysis_finds_groups_bridges_and_exports(workspace):
    app, client, user, case_id, *_ = workspace
    with registry(app) as reg:
        ids = {name: reg.create_entity(case_id=case_id, kind=kind, label=name)["id"] for name, kind in
               [("Max Beispiel", "person"), ("Y GmbH", "company"), ("Eva Test", "person"), ("Z AG", "company"),
                ("Q Ltd", "company"), ("Ina Nord", "person"), ("Ole Solo", "person")]}
        for a, b, pred, state in [("Max Beispiel", "Y GmbH", "Geschäftsführer", "supported"), ("Eva Test", "Y GmbH", "Prokuristin", "hypothesis"),
                                  ("Max Beispiel", "Z AG", "Gesellschafter", "supported"), ("Z AG", "Q Ltd", "Tochter", "hypothesis"),
                                  ("Ina Nord", "Q Ltd", "Direktorin", "hypothesis"), ("Eva Test", "Max Beispiel", "Ehepartner", "hypothesis"),
                                  ("Ole Solo", "Y GmbH", "Gerücht", "rejected")]:
            reg.create_relation(case_id=case_id, source_id=ids[a], target_id=ids[b], predicate=pred,
                                source_refs=["https://example.org/register"], state=state)
    view = client.get("/workbench/intel/network", params={"case_id": case_id})
    assert view.status_code == 200
    html = view.text
    assert "Brückenpersonen" in html and "Max Beispiel" in html
    assert '<span class="stat">6</span>gewertete Verbindungen' in html  # rejected relation not counted
    assert '<span class="stat">1</span>ohne Verbindung' in html
    path = client.get("/workbench/intel/network", params={"case_id": case_id, "source": ids["Eva Test"],
                      "target": ids["Ina Nord"]}).text
    assert "Eva Test → Max Beispiel" in path and "Q Ltd → Ina Nord" in path
    assert client.get("/workbench/intel/network", params={"case_id": case_id, "source": "x", "target": "y"}).status_code == 422
    gexf = client.get("/workbench/intel/network.gexf", params={"case_id": case_id})
    assert gexf.status_code == 200
    root = ET.fromstring(gexf.content)
    assert root.tag.endswith("gexf")
    ftm = ftm_entities({"case_id": case_id, "entities": [], "relations": []})
    assert ftm == []
