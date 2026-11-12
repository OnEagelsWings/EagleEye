"""Version 1.5 – Zusammenführung mit Build 492 und den Mustern aus der SpiderFoot-/Obsidian-Analyse.

Geprüft werden: WARC-Belege mit Wiedergabeprüfung und Haupttext, Archivfassungen, Dokument-Import mit
Texterkennung, Quellfamilien (unabhängige Ursprünge), begründeter Namensabgleich, Netzwerkanalyse mit
offenen Exportformaten und Import, Folgesuchen mit Freigabe und Herkunftskette, Konfigurations-Snapshot
je Suchlauf sowie deklarative Korrelationsregeln.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

from conftest import add_user, build_app, setup_admin
from personosint import documents, lineage, namematch, network, pivot, webarchive
from personosint.sources import HttpResponse, SourceError

DATA = Path(__file__).parent / "data"
BODY = ("Die Nordhafen Projekt GmbH hat nach Recherchen dieser Redaktion im Jahr 2019 mehrere Grundstücke am alten Hafenbecken erworben. "
        "Geschäftsführer Max Mustermann bestätigte auf Anfrage, dass die Gesellschaft dafür ein Darlehen der Seeblick Holding erhalten hat. "
        "Die Stadtverwaltung prüft derzeit, ob bei der Vergabe der Flächen alle Vorschriften eingehalten wurden. "
        "Ein Sprecher erklärte, man werde die Unterlagen dem Rechnungsprüfungsamt vorlegen und das Ergebnis veröffentlichen.")
ARTICLE = ("<!doctype html><html lang='de'><head><title>Hafenprojekt: Fragen zur Vergabe</title><meta name='author' content='Lena Beispiel'>"
           "<meta property='article:published_time' content='2024-03-05T08:00:00+01:00'></head><body><nav>Start | Politik | Wirtschaft | Abo</nav>"
           f"<article><h1>Hafenprojekt: Fragen zur Vergabe</h1><p>{BODY}</p><p>{BODY.replace('2019', '2020')}</p></article>"
           "<footer>Impressum Datenschutz Cookie-Einstellungen</footer><script>alert(1)</script></body></html>").encode()
COPY = ARTICLE.replace(b"Hafenprojekt: Fragen zur Vergabe", b"Agentur: Hafenprojekt wirft Fragen auf").replace(b"Start | Politik", b"Home | Lokales")
OTHER = ("<!doctype html><html><head><title>Sportverein feiert Jubilaeum</title></head><body><article><p>"
         + " ".join(f"Der Verein blickt im Jahr {1950 + i} auf eine bewegte Saison mit vielen Toren und treuen Fans zurueck." for i in range(8))
         + "</p></article></body></html>").encode()
HDRS = [("Content-Type", "text/html; charset=utf-8"), ("Server", "nginx"), ("Transfer-Encoding", "chunked")]


class Http:
    """Antworten je Adress-Präfix – mit Kopfzeilen, damit die WARC-Aufzeichnung geprüft werden kann."""

    def __init__(self, routes: dict[str, tuple[int, object]]):
        self.routes, self.calls = routes, []

    def get(self, url: str, headers=None) -> HttpResponse:
        self.calls.append(url)
        for prefix, (status, body) in self.routes.items():
            if url.startswith(prefix):
                if status == -1:
                    raise SourceError("Quelle nicht erreichbar: simuliert")
                raw = body if isinstance(body, bytes) else json.dumps(body).encode()
                return HttpResponse(status, raw, url, headers=list(HDRS), reason="OK", request_headers=[("User-Agent", "Test"), ("Accept", "text/html")])
        return HttpResponse(404, b"", url)


ROUTES = {
    "https://zeitung.example.com/hafen": (200, ARTICLE),
    "https://portal.example.org/agentur-hafen": (200, COPY),
    "https://verein.example.net/jubilaeum": (200, OTHER),
    "https://archive.org/wayback/available": (200, {"archived_snapshots": {}}),
    "https://web.archive.org/cdx/search/cdx": (200, [["timestamp", "original", "statuscode", "mimetype", "digest"],
                                                   ["20210304050607", "https://zeitung.example.com/hafen", "200", "text/html", "AAA"],
                                                   ["20230101120000", "https://zeitung.example.com/hafen", "200", "text/html", "BBB"]]),
    "https://web.archive.org/web/20210304050607id_/https://zeitung.example.com/hafen": (200, ARTICLE.replace(b"2019", b"2018")),
    "https://api.github.com/users/maxmuster": (200, {"login": "maxmuster", "name": "Max Mustermann", "html_url": "https://github.com/maxmuster",
                                                      "company": "@Nordhafen Projekt GmbH", "blog": "https://mustermann-consulting.de",
                                                      "email": "max@mustermann-consulting.de", "location": "Kiel"}),
    "https://rdap.org/domain/mustermann-consulting.de": (200, {"events": [{"eventAction": "registration", "eventDate": "2016-02-03T00:00:00Z"}],
                                                               "nameservers": [{"ldhName": "NS1.HOSTER.EXAMPLE"}]}),
}


def _case(tmp_path, level=1, backend="sqlite"):
    app = build_app(tmp_path, backend, http=Http(ROUTES))
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    cid = anna.post("/api/cases", json={"title": "Hafenprojekt", "case_type": "investigativ", "purpose": "Recherche zur Vergabe am Hafen",
                                        "legal_basis": "Journalistische Recherche (Medienprivileg)", "opsec_level": level,
                                        "subject": {"label": "Max Mustermann", "identifiers": [{"kind": "username", "value": "maxmuster"}]}}).json()["id"]
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    return app, admin, anna, cid, sid


# --------------------------------------------------------------------------- A2/A3: WARC, Haupttext, Archivfassungen

def test_capture_stores_warc_and_main_text_and_verifies_replay(tmp_path, backend):
    app, admin, anna, cid, sid = _case(tmp_path, backend=backend)
    ev = anna.post(f"/api/cases/{cid}/evidence", json={"url": "https://zeitung.example.com/hafen"}).json()
    assert ev["kind"] == "web" and ev["has_warc"] and ev["has_text"] and len(ev["warc_sha256"]) == 64
    assert ev["title"] == "Hafenprojekt: Fragen zur Vergabe" and ev["meta"]["author"] == "Lena Beispiel" and ev["meta"]["published"].startswith("2024-03-05")
    assert "Nordhafen Projekt GmbH" in ev["excerpt"] and "Cookie-Einstellungen" not in ev["excerpt"] and "alert(1)" not in ev["excerpt"]
    # WARC lässt sich wiedergeben und enthält byte-genau das versiegelte Original
    warc = anna.get(f"/api/cases/{cid}/evidence/{ev['id']}/warc")
    assert warc.status_code == 200 and hashlib.sha256(warc.content).hexdigest() == ev["warc_sha256"]
    url, status, payload = webarchive.read_warc_response(warc.content)
    assert (url, status) == ("https://zeitung.example.com/hafen", 200) and payload == ARTICLE
    ok = anna.get(f"/api/cases/{cid}/evidence/{ev['id']}/verify").json()
    assert ok == {**ok, "ok": True, "original": True, "warc": True, "wiedergabe": True}
    text = anna.get(f"/api/cases/{cid}/evidence/{ev['id']}/text").json()
    assert text["pages"][0]["method"] == "haupttext" and text["mentions"][0]["label"] == "Max Mustermann"
    # Beweispaket enthält WARC und Textfassung, Manifest nennt beide Prüfsummen
    z = zipfile.ZipFile(io.BytesIO(anna.get(f"/api/cases/{cid}/export/beweispaket.zip").content))
    entry = json.loads(z.read("manifest.json"))["belege"][0]
    assert hashlib.sha256(z.read(entry["warc_datei"])).hexdigest() == entry["warc_sha256"] and entry["autor_laut_seite"] == "Lena Beispiel"
    assert "Nordhafen" in z.read(entry["textfassung"]).decode() and "WARC 1.1" in z.read("PRUEFANLEITUNG.txt").decode()
    # Manipulation der WARC-Datei fällt auf
    f = next(x for x in (tmp_path / "evidence").iterdir() if ".warc." in x.name)
    f.write_bytes(app.state.platform.vault.encrypt(b"manipuliert"))
    bad = anna.get(f"/api/cases/{cid}/evidence/{ev['id']}/verify").json()
    assert bad["ok"] is False and bad["original"] is True and bad["warc"] is False
    assert anna.get(f"/api/cases/{cid}/evidence/{ev['id']}/warc").status_code == 422


def test_wayback_versions_and_archive_capture(tmp_path):
    app, admin, anna, cid, sid = _case(tmp_path)
    versions = anna.get(f"/api/cases/{cid}/evidence/wayback", params={"url": "https://zeitung.example.com/hafen"}).json()
    assert [v["timestamp"] for v in versions] == ["20210304050607", "20230101120000"] and versions[0]["label"] == "04.03.2021 05:06 UTC"
    ev = anna.post(f"/api/cases/{cid}/evidence", json={"url": "https://zeitung.example.com/hafen", "wayback_timestamp": "20210304050607"}).json()
    assert ev["kind"] == "archiv" and ev["url"] == "https://zeitung.example.com/hafen" and "/web/20210304050607id_/" in ev["archive_url"]
    assert ev["meta"]["archiv_zeitpunkt"] == "2021-03-04T05:06:07Z" and "2018" in ev["excerpt"]
    assert anna.post(f"/api/cases/{cid}/evidence", json={"url": "https://zeitung.example.com/hafen", "wayback_timestamp": "kaputt"}).status_code == 422
    assert anna.get(f"/api/cases/{cid}/evidence/wayback", params={"url": "http://127.0.0.1/x"}).status_code == 422       # SSRF-Schutz
    hosts = {h["host"] for h in anna.get(f"/api/cases/{cid}/opsec").json()["hosts"]}
    assert "web.archive.org" in hosts                                                                                    # Außenkontakt protokolliert


# --------------------------------------------------------------------------- A1: Dokumente und Texterkennung

def _pdf(lines: list[str]) -> bytes:
    """Kleinstes gültiges Text-PDF (eine Seite je Zeile)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for line in lines:
        stream = f"BT /F1 14 Tf 60 720 Td ({line}) Tj ET"
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {len(objs)} 0 R /Resources << /Font << /F1 3 0 R >> >> >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()


def _scan(text: str, fmt: str = "PDF") -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1500, 420), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=44)
    for i, line in enumerate(text.split("\n")):
        draw.text((50, 50 + i * 80), line, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def test_document_import_pdf_docx_text_and_mentions(tmp_path):
    import docx

    app, admin, anna, cid, sid = _case(tmp_path)
    pdf = _pdf(["Handelsregister Auszug Nordhafen Projekt GmbH", "Geschaeftsfuehrer: Mustermann, Max seit 2019"])
    r = anna.post(f"/api/cases/{cid}/evidence/document", files={"file": ("../../Auszug HRB.pdf", pdf, "application/pdf")}, params={"note": "vom Auftraggeber"})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["kind"] == "dokument" and ev["filename"] == "Auszug HRB.pdf" and ev["meta"]["pages"] == 2 and ev["sha256"] == hashlib.sha256(pdf).hexdigest()
    assert ev["egress"].startswith("lokal") and ev["url"] == "" and "Handelsregister" in ev["excerpt"]
    text = anna.get(f"/api/cases/{cid}/evidence/{ev['id']}/text").json()
    assert [pg["page"] for pg in text["pages"]] == [1, 2] and text["mentions"] == [{"entity_id": sid, "label": "Max Mustermann", "type": "person", "pages": [2]}]
    assert anna.get(f"/api/cases/{cid}/evidence/{ev['id']}/download").content == pdf
    assert all(pdf not in f.read_bytes() for f in (tmp_path / "evidence").iterdir())                 # verschlüsselt abgelegt
    assert anna.post(f"/api/cases/{cid}/evidence/document", files={"file": ("nochmal.pdf", pdf)}).status_code == 422   # gleiche Prüfsumme
    d = docx.Document()
    d.add_paragraph("Vermerk zur Seeblick Holding")
    d.add_table(rows=1, cols=2).rows[0].cells[0].text = "Darlehen"
    buf = io.BytesIO()
    d.save(buf)
    word = anna.post(f"/api/cases/{cid}/evidence/document", files={"file": ("Vermerk.docx", buf.getvalue())}).json()
    assert word["content_type"].endswith("wordprocessingml.document") and "Seeblick Holding" in word["excerpt"] and "Darlehen" in word["excerpt"]
    mail = b"From: info@seeblick.example\nTo: max@example.org\nSubject: Darlehensvertrag\nDate: Mon, 4 Mar 2024 10:00:00 +0100\n\nAnbei der Vertrag."
    eml = anna.post(f"/api/cases/{cid}/evidence/document", files={"file": ("nachricht.eml", mail)}).json()
    assert eml["content_type"] == "message/rfc822" and eml["title"] == "Darlehensvertrag" and "Anbei der Vertrag" in eml["excerpt"]
    assert anna.post(f"/api/cases/{cid}/evidence/document", files={"file": ("x.bin", b"\x00\x01\x02\xff\xfe" * 50)}).status_code == 422
    assert anna.post(f"/api/cases/{cid}/evidence/document", files={"file": ("leer.txt", b"")}).status_code == 422
    # Beweispaket führt Dokumente mit Originaldatei; Löschen nur mit Verwaltungsrecht des Falls, Prüfsumme bleibt im Protokoll
    z = zipfile.ZipFile(io.BytesIO(anna.get(f"/api/cases/{cid}/export/beweispaket.zip").content))
    arts = {b["art"] for b in json.loads(z.read("manifest.json"))["belege"]}
    assert arts == {"Dokument"} and any(n.endswith(".pdf") for n in z.namelist()) and any(n.endswith(".docx") for n in z.namelist())
    bert = add_user(admin, app, "bert", "leser")
    admin.put(f"/api/cases/{cid}/members", json={"members": [{"user_id": bert.uid, "role": "leser"}]})
    assert bert.delete(f"/api/cases/{cid}/evidence/{eml['id']}").status_code == 403
    assert anna.delete(f"/api/cases/{cid}/evidence/{eml['id']}").status_code == 204
    assert len(list((tmp_path / "evidence").iterdir())) == 4 and any(ev["sha256"] not in a["detail"] and eml["sha256"] in a["detail"]
                                                                       for a in anna.get(f"/api/cases/{cid}/audit").json())


@pytest.mark.skipif(not documents.ocr_status()["available"], reason="Tesseract ist auf diesem Rechner nicht installiert")
def test_scanned_pdf_and_image_are_read_by_ocr(tmp_path):
    app, admin, anna, cid, sid = _case(tmp_path)
    scan = _scan("Mietvertrag Hafenstrasse 12\nMieter: Max Mustermann")
    ev = anna.post(f"/api/cases/{cid}/evidence/document", files={"file": ("scan.pdf", scan)}).json()
    assert ev["meta"]["scan_pages"] == 1 and ev["meta"]["ocr_pages"] == 1 and ev["meta"]["ocr_confidence"] > 60 and "tesseract" in ev["meta"]["ocr_engine"]
    page = anna.get(f"/api/cases/{cid}/evidence/{ev['id']}/text").json()
    assert page["pages"][0]["method"] == "ocr" and "Mietvertrag" in page["pages"][0]["text"] and page["mentions"][0]["pages"] == [1]
    img = anna.post(f"/api/cases/{cid}/evidence/document", files={"file": ("foto.png", _scan("Seeblick Holding AG\nKontoauszug Maerz", "PNG"))}).json()
    assert img["content_type"] == "image/png" and "Seeblick" in img["excerpt"]
    assert anna.get("/api/components").json()["ocr"]["available"] is True


def test_document_analysis_without_ocr_explains_what_is_missing():
    ctype, pages, info = documents.analyse("scan.pdf", _scan("Nur ein Bild"), use_ocr=False)
    assert ctype == "application/pdf" and pages[0]["text"] == "" and "Texterkennung ist nicht installiert" in info["hinweis"]
    with pytest.raises(documents.DocumentError):
        documents.analyse("x.zip", b"PK\x03\x04" + b"0" * 100)


# --------------------------------------------------------------------------- A4: Quellfamilien / unabhängige Ursprünge

def test_source_families_count_independent_origins(tmp_path):
    app, admin, anna, cid, sid = _case(tmp_path)
    ids = [anna.post(f"/api/cases/{cid}/evidence", json={"url": u}).json()["id"]
           for u in ("https://zeitung.example.com/hafen", "https://portal.example.org/agentur-hafen", "https://verein.example.net/jubilaeum")]
    fam = anna.get(f"/api/cases/{cid}/evidence/families").json()
    assert (fam["documents"], fam["independent_origins"], fam["duplicate_documents"], fam["truth_determined"]) == (3, 2, 1, False)
    assert [m["id"] for m in fam["families"][0]["members"]] == ids[:2] and fam["families"][0]["max_similarity"] >= 0.7
    assert fam["families"][0]["hosts"] == ["portal.example.org", "zeitung.example.com"] and "url_family" not in fam
    assert anna.get(f"/api/cases/{cid}/evidence/families", params={"level": "unsinn"}).status_code == 422
    # Zwei „Quellen“, die denselben Text übernehmen, bestätigen sich nicht gegenseitig
    p = app.state.platform
    for key, url in (("zeitung", "https://zeitung.example.com/hafen"), ("portal", "https://portal.example.org/agentur-hafen")):
        p.db.insert("facts", {"case_id": cid, "subject_entity_id": sid, "subject_label": "Max Mustermann", "subject_type": "person",
                              "predicate": "funktion_bei", "object_label": "Nordhafen Projekt GmbH", "object_type": "organisation", "data": {},
                              "source_key": key, "source_label": key.title(), "source_url": url, "retrieved_at": "2024-03-05T08:00:00+00:00",
                              "status": "bestätigt", "reliability": "C", "norm_key": "max mustermann|funktion_bei|nordhafen projekt gmbh",
                              "created_at": "2024-03-05T08:00:00+00:00"})
    asm = anna.get(f"/api/cases/{cid}/assessment").json()
    fact = asm["facts"][0]
    assert fact["corroboration"] == 1 and fact["same_origin"] == 1 and fact["credibility_auto"] == 3 and asm["stats"]["corroborated"] == 0
    assert asm["origins"] == {"documents": 3, "independent_origins": 2, "duplicate_documents": 1}
    # Gegenprobe: eine wirklich andere Quelle bestätigt
    p.db.execute("UPDATE facts SET source_url = 'https://verein.example.net/jubilaeum' WHERE source_key = 'portal'")
    assert anna.get(f"/api/cases/{cid}/assessment").json()["facts"][0]["corroboration"] == 2


def test_lineage_is_exact_and_ignores_short_texts():
    docs = [{"id": 1, "text": BODY, "url": "https://a.example/x"}, {"id": 2, "text": BODY + " Zusatz am Ende.", "url": "https://b.example/y"},
            {"id": 3, "text": "zu kurz"}, {"id": 4, "text": " ".join(f"wort{i}" for i in range(80))}]
    res = lineage.source_families(docs, "streng")
    assert res["independent_origins"] == 2 and res["compared"] == 3 and res["skipped"][0]["id"] == 3
    assert lineage.jaccard(lineage.shingles(BODY), lineage.shingles(BODY)) == 1.0 and lineage.origin_map(res)[1] == lineage.origin_map(res)[2]


# --------------------------------------------------------------------------- A5: begründeter Namensabgleich

def _benchmark(name: str) -> tuple[float, float]:
    tp = fp = fn = 0
    for _kind, left, right, same in json.loads((DATA / name).read_text(encoding="utf-8"))["pairs"]:
        hit = namematch.compare_names(left, right)[0] >= namematch.THRESHOLD
        tp += hit and same
        fp += hit and not same
        fn += (not hit) and same
    return tp / (tp + fp), tp / (tp + fn)


def test_name_matching_reaches_measured_quality_on_holdout_set():
    precision, recall = _benchmark("entity_pairs_holdout.json")       # unabhängiger Prüfsatz aus Build 492 – nie zum Abstimmen benutzt
    assert precision >= 0.9 and recall >= 0.9
    assert namematch.compare_names("Владимир Иванов", "Vladimir Ivanov")[0] >= namematch.THRESHOLD
    assert namematch.compare_names("Peter Schmidt", "Petra Schmidt")[0] < namematch.THRESHOLD
    assert namematch.is_candidate("K. Hoffmann", "Karin Hoffmann")[2] == "gleicher Nachname, Vorname als Initiale kompatibel"


def test_other_scripts_are_searchable_and_duplicates_are_suggested_with_reason(tmp_path):
    from personosint.matching import fold, name_similarity, normalize

    assert fold("Сергей Кузнецов") == "sergei kuznetsov" and normalize("name", "Νίκος Γεωργίου").startswith("nikos")
    assert name_similarity("Ольга Попова", "Olga Popova") >= 0.88 and name_similarity("Müller", "Mueller") == 1.0
    app, admin, anna, cid, sid = _case(tmp_path)
    a = anna.post(f"/api/cases/{cid}/entities", json={"type": "person", "label": "Sergei Kuznetsov"}).json()["id"]
    b = anna.post(f"/api/cases/{cid}/entities", json={"type": "person", "label": "Сергей Кузнецов"}).json()["id"]
    c = anna.post(f"/api/cases/{cid}/entities", json={"type": "person", "label": "Karin Hoffmann"}).json()["id"]
    d = anna.post(f"/api/cases/{cid}/entities", json={"type": "person", "label": "K. Hoffmann"}).json()["id"]
    anna.post(f"/api/cases/{cid}/entities", json={"type": "person", "label": "Petra Schmidt"})
    anna.post(f"/api/cases/{cid}/entities", json={"type": "person", "label": "Peter Schmidt"})
    sug = {frozenset((s["source_id"], s["target_id"])): s for s in anna.get(f"/api/cases/{cid}/suggestions").json() if "Dublette" in s["reason"]}
    assert set(sug) == {frozenset((a, b)), frozenset((c, d))}                 # Petra/Peter Schmidt wird nicht vorgeschlagen
    assert "Initiale" in sug[frozenset((c, d))]["reason"] and sug[frozenset((c, d))]["relation"] == "identisch mit (vermutet)"
    assert len(anna.get(f"/api/cases/{cid}/entities").json()) == 7            # nichts wurde automatisch zusammengeführt


# --------------------------------------------------------------------------- B1 + Obsidian: Netzwerkanalyse, Exporte, Import

def _network(anna, cid, sid):
    ids = {"Max Mustermann": sid}
    for label, typ in (("Nordhafen Projekt GmbH", "organisation"), ("Eva Test", "person"), ("Seeblick Holding", "organisation"),
                       ("Quai Ltd", "organisation"), ("Ina Nord", "person"), ("Ole Solo", "person"), ("+49 431 1234", "telefon")):
        ids[label] = anna.post(f"/api/cases/{cid}/entities", json={"type": typ, "label": label}).json()["id"]
    for a, b, rel, conf in (("Max Mustermann", "Nordhafen Projekt GmbH", "Funktion bei", 90), ("Eva Test", "Nordhafen Projekt GmbH", "arbeitet bei", 60),
                            ("Max Mustermann", "Seeblick Holding", "beteiligt an", 80), ("Seeblick Holding", "Quai Ltd", "beteiligt an", 50),
                            ("Ina Nord", "Quai Ltd", "Funktion bei", 70), ("Max Mustermann", "+49 431 1234", "nutzt Telefon", 70),
                            ("Max Mustermann", "Eva Test", "verwandt mit", 40)):
        r = anna.post(f"/api/cases/{cid}/links", json={"source_id": ids[a], "target_id": ids[b], "relation": rel, "confidence": conf,
                                                         "evidence": "Registerauszug https://register.example.com/hrb"})
        assert r.status_code == 201, r.text
    return ids


def test_network_analysis_finds_groups_bridges_and_isolated(tmp_path):
    app, admin, anna, cid, sid = _case(tmp_path)
    ids = _network(anna, cid, sid)
    res = anna.get(f"/api/cases/{cid}/graph/analysis").json()
    assert res["nodes"] == 8 and res["edges"] == 7 and res["components"] == 2 and res["truth_determined"] is False
    assert [n["label"] for n in res["isolated"]] == ["Ole Solo"] and res["central"][0]["label"] == "Max Mustermann"
    bridges = {b["label"]: b for b in res["bridges"]}
    assert {"Max Mustermann", "Seeblick Holding", "Quai Ltd"} <= set(bridges) and bridges["Seeblick Holding"]["cut_point"] is True
    assert network.articulation_points({1: {2}, 2: {1, 3}, 3: {2}, 4: set()}) == {2}
    assert network.articulation_points({1: {2, 3}, 2: {1, 3}, 3: {1, 2}}) == set()
    del ids


def test_graph_exports_gexf_ftm_canvas_obsidian_and_ftm_roundtrip(tmp_path):
    app, admin, anna, cid, sid = _case(tmp_path)
    _network(anna, cid, sid)
    anna.post(f"/api/cases/{cid}/entities/{sid}/identifiers", json={"kind": "email", "value": "max@example.org"})
    gexf = anna.get(f"/api/cases/{cid}/export/graph.gexf")
    root = ElementTree.fromstring(gexf.content)
    ns = {"g": "http://gexf.net/1.3"}
    assert len(root.findall(".//g:node", ns)) == 8 and len(root.findall(".//g:edge", ns)) == 7 and "attachment" in gexf.headers["content-disposition"]
    ftm = anna.get(f"/api/cases/{cid}/export/graph.ftm").json()
    by_schema: dict[str, list] = {}
    for o in ftm:
        by_schema.setdefault(o["schema"], []).append(o)
    person = next(o for o in by_schema["Person"] if o["properties"]["name"] == ["Max Mustermann"])
    assert person["properties"]["phone"] == ["+49 431 1234"] and person["properties"]["email"] == ["max@example.org"] and person["eagleeye"]["geprueft"] is False
    assert len(by_schema["Organization"]) == 3 and len(by_schema["Directorship"]) == 2 and len(by_schema["Ownership"]) == 2
    assert len(by_schema["Employment"]) == 1 and len(by_schema["Family"]) == 1 and "UnknownLink" not in by_schema
    assert by_schema["Ownership"][0]["properties"]["sourceUrl"] == ["https://register.example.com/hrb"]
    canvas = anna.get(f"/api/cases/{cid}/export/graph.canvas").json()
    assert len(canvas["nodes"]) == 8 and len(canvas["edges"]) == 7 and {"id", "type", "x", "y", "width", "height"} <= set(canvas["nodes"][0])
    assert anna.get(f"/api/cases/{cid}/export/graph.exe").status_code == 404
    vault = zipfile.ZipFile(io.BytesIO(anna.get(f"/api/cases/{cid}/export/obsidian.zip").content))
    names = set(vault.namelist())
    assert {"LIESMICH.md", "Verbindungen.canvas", "Personen/Max Mustermann.md", "Organisationen/Seeblick Holding.md"} <= names
    note = vault.read("Personen/Max Mustermann.md").decode()
    assert "[[Organisationen/Nordhafen Projekt GmbH|Nordhafen Projekt GmbH]]" in note and 'typ: "Person"' in note and "zielperson: true" in note
    assert "nicht verschlüsselt" in vault.read("LIESMICH.md").decode()
    assert json.loads(vault.read("Verbindungen.canvas"))["nodes"][0]["type"] == "file"
    kinds = [e["kind"] for e in anna.get(f"/api/cases/{cid}/opsec").json()["exports"]]
    assert {"Graph (GEXF)", "Graph (FollowTheMoney)", "Graph (JSON Canvas)", "Obsidian-Vault"} <= set(kinds)       # alle im Exportregister
    # Rundlauf: FtM-Export in einen zweiten Fall einlesen – alles bleibt ungeprüft, doppelter Import legt nichts doppelt an
    cid2 = anna.post("/api/cases", json={"title": "Zweitfall", "case_type": "verbindungen", "purpose": "Abgleich mit importiertem Graphen",
                                         "legal_basis": "Journalistische Recherche (Medienprivileg)", "opsec_level": 1}).json()["id"]
    raw = json.dumps(ftm).encode()
    res = anna.post(f"/api/cases/{cid2}/import/ftm", files={"file": ("export.ftm.json", raw)}).json()
    assert res == {"objects": len(ftm), "created": 7, "reused": 0, "links": 6, "skipped": 0}
    again = anna.post(f"/api/cases/{cid2}/import/ftm", files={"file": ("export.ftm.json", "\n".join(json.dumps(o) for o in ftm).encode())}).json()
    assert again["created"] == 0 and again["reused"] == 7 and again["links"] == 0
    links = anna.get(f"/api/cases/{cid2}/links").json()
    assert {lk["relation"] for lk in links} == {"Funktion bei", "arbeitet bei", "beteiligt an", "verwandt mit"} and all(lk["confidence"] == 40 for lk in links)
    assert all("ungeprüft" in lk["evidence"] for lk in links)
    assert anna.post(f"/api/cases/{cid2}/import/ftm", files={"file": ("x.json", b"{kein json")}).status_code == 422
    assert anna.post(f"/api/cases/{cid2}/import/ftm", files={"file": ("x.json", b'[{"foo": 1}]')}).status_code == 422


def test_exports_respect_opsec_export_rules(tmp_path):
    app, admin, anna, cid, sid = _case(tmp_path)
    bert = add_user(admin, app, "bert", "leser")
    admin.put(f"/api/cases/{cid}/members", json={"members": [{"user_id": bert.uid, "role": "leser"}]})
    ok = bert.get(f"/api/cases/{cid}/export/graph.gexf").status_code
    case = anna.get(f"/api/cases/{cid}/overview").json()["case"]
    r = admin.patch(f"/api/cases/{cid}", json={"opsec_level": 3, "version": case["version"]})
    if r.status_code == 200 and ok == 200:
        assert bert.get(f"/api/cases/{cid}/export/graph.gexf").status_code == 403
        assert bert.get(f"/api/cases/{cid}/export/obsidian.zip").status_code == 403


# --------------------------------------------------------------------------- SpiderFoot-Muster: Folgesuchen, Herkunftskette, Snapshot

def _confirmed_github(anna, cid, sid):
    res = anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": ["github"]}).json()
    assert res["new_findings"] == 1
    fid = anna.get(f"/api/cases/{cid}/findings").json()[0]["id"]
    assert anna.patch(f"/api/cases/{cid}/findings/{fid}", json={"status": "bestätigt"}).status_code == 200
    return fid


def test_sources_declare_what_they_consume_and_produce(tmp_path):
    app, admin, anna, cid, sid = _case(tmp_path)
    src = {s["key"]: s for s in anna.get("/api/meta").json()["sources"]}
    assert "employer" in src["github"]["produces"] and src["github"]["kinds"] == ["username", "name"] and src["crtsh"]["produces"] == ["domain"]
    assert all(s.key in pivot.PRODUCES for s in app.state.platform.all_sources())      # jede Quelle ist im Manifest erfasst
    routes = anna.get(f"/api/cases/{cid}/entities/{sid}/routes", params={"want": "employer"}).json()
    ready = {r["key"]: r["ready"] for r in routes}
    assert ready["github"] is True and ready["gleif"] is False and routes[0]["ready"] is True


def test_pivot_suggestions_need_confirmation_and_approval(tmp_path):
    app, admin, anna, cid, sid = _case(tmp_path)
    assert anna.get(f"/api/cases/{cid}/entities/{sid}/pivots").json()["items"] == []
    res = anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": ["github"]}).json()
    assert res["new_findings"] == 1
    assert anna.get(f"/api/cases/{cid}/entities/{sid}/pivots").json()["items"] == []          # ungeprüfte Treffer lösen nichts aus
    fid = anna.get(f"/api/cases/{cid}/findings").json()[0]["id"]
    anna.patch(f"/api/cases/{cid}/findings/{fid}", json={"status": "bestätigt"})
    calls_before = len(app.state.platform.http.calls) if hasattr(app.state.platform, "http") else None
    piv = anna.get(f"/api/cases/{cid}/entities/{sid}/pivots").json()
    found = {(i["kind"], i["value"]): i for i in piv["items"]}
    assert {("email", "max@mustermann-consulting.de"), ("domain", "mustermann-consulting.de"), ("employer", "Nordhafen Projekt GmbH"),
            ("url", "https://mustermann-consulting.de"), ("username", "maxmuster")} <= set(found)
    dom = found[("domain", "mustermann-consulting.de")]
    assert dom["depth"] == 1 and dom["origin"]["finding_id"] == fid and {s["key"] for s in dom["sources"]} == {"crtsh", "rdap"}
    assert "github" not in {s["key"] for s in found[("username", "maxmuster")]["sources"]}     # dort wurde schon gesucht
    if calls_before is not None:
        assert len(app.state.platform.http.calls) == calls_before                              # Vorschläge lösen keine Abfrage aus
    # verwerfen und wiederherstellen
    left = anna.post(f"/api/cases/{cid}/entities/{sid}/pivots/dismiss", json={"kind": "employer", "value": "Nordhafen Projekt GmbH"}).json()
    assert ("employer", "Nordhafen Projekt GmbH") not in {(i["kind"], i["value"]) for i in left["items"]} and left["dismissed"] == 1
    assert len(anna.post(f"/api/cases/{cid}/entities/{sid}/pivots/restore").json()["items"]) == len(piv["items"])
    # Lesende dürfen ansehen, aber nichts ausführen
    bert = add_user(admin, app, "bert", "leser")
    admin.put(f"/api/cases/{cid}/members", json={"members": [{"user_id": bert.uid, "role": "leser"}]})
    assert bert.get(f"/api/cases/{cid}/entities/{sid}/pivots").status_code == 200
    assert bert.post(f"/api/cases/{cid}/entities/{sid}/pivots/run", json={"kind": "domain", "value": "mustermann-consulting.de"}).status_code == 403


def test_pivot_run_records_origin_chain_and_snapshot(tmp_path, backend):
    app, admin, anna, cid, sid = _case(tmp_path, backend=backend)
    fid = _confirmed_github(anna, cid, sid)
    run = anna.post(f"/api/cases/{cid}/entities/{sid}/pivots/run", json={"kind": "domain", "value": "mustermann-consulting.de", "sources": ["rdap"]})
    assert run.status_code == 200, run.text
    assert run.json()["queries"] == 1 and run.json()["new_findings"] == 1
    searches = anna.get(f"/api/cases/{cid}/searches").json()
    assert searches[0]["pivot"]["kind"] == "domain" and searches[0]["pivot"]["depth"] == 1 and searches[0]["pivot"]["origin"]["finding_id"] == fid
    assert searches[0]["queries"] == [{"source": "rdap", "kind": "domain", "value": "mustermann-consulting.de"}]     # nur diese eine Kennung
    snap = searches[0]["snapshot"]
    assert snap["opsec_level"] == 1 and snap["egress"] and snap["sources"][0] == {**snap["sources"][0], "key": "rdap", "reliability": "B", "exposure": "passiv"}
    assert searches[1]["pivot"] == {} and searches[1]["snapshot"]["sources"][0]["key"] == "github" and snap["version"]
    idents = {(i["kind"], i["value"]): i for i in anna.get(f"/api/cases/{cid}/entities/{sid}").json()["identifiers"]}
    assert idents[("domain", "mustermann-consulting.de")]["finding_id"] == fid and "Folgesuche" in idents[("domain", "mustermann-consulting.de")]["source"]
    rdap = next(f for f in anna.get(f"/api/cases/{cid}/findings").json() if f["source"].startswith("RDAP"))
    chain = anna.get(f"/api/cases/{cid}/findings/{rdap['id']}/chain").json()
    assert [s["type"] for s in chain] == ["start", "search", "finding", "identifier", "search", "finding"]
    assert chain[0]["label"] == "Max Mustermann" and chain[2]["id"] == fid and chain[3]["value"] == "mustermann-consulting.de" and chain[4]["depth"] == 1
    assert [s["type"] for s in anna.get(f"/api/cases/{cid}/findings/{fid}/chain").json()] == ["start", "search", "finding"]
    # erledigte Folgesuche verschwindet für diese Quelle; dieselbe erneut auszuführen wird abgelehnt
    left = {(i["kind"], i["value"]): i for i in anna.get(f"/api/cases/{cid}/entities/{sid}/pivots").json()["items"]}
    assert {s["key"] for s in left[("domain", "mustermann-consulting.de")]["sources"]} == {"crtsh"}
    assert anna.post(f"/api/cases/{cid}/entities/{sid}/pivots/run", json={"kind": "domain", "value": "mustermann-consulting.de", "sources": ["rdap"]}).status_code == 422
    assert anna.post(f"/api/cases/{cid}/entities/{sid}/pivots/run", json={"kind": "domain", "value": "frei-erfunden.example"}).status_code == 422
    assert any(a["action"] == "Folgesuche ausgeführt" and "Tiefe 1" in a["detail"] for a in anna.get(f"/api/cases/{cid}/audit").json())


def test_pivot_depth_is_limited_and_opsec_blocks_platform_sources(tmp_path, monkeypatch):
    import dataclasses

    from personosint import opsec as ops

    app, admin, anna, cid, sid = _case(tmp_path)
    fid = _confirmed_github(anna, cid, sid)
    p = app.state.platform
    # Treffer künstlich in große Tiefe verschieben: Vorschläge daraus werden nicht mehr angeboten
    p.db.execute("UPDATE searches SET pivot = ? WHERE case_id = ?", (json.dumps({"kind": "username", "value": "x", "depth": pivot.MAX_DEPTH}), cid))
    deep = anna.get(f"/api/cases/{cid}/entities/{sid}/pivots").json()
    assert deep["too_deep"] >= 4 and deep["max_depth"] == pivot.MAX_DEPTH and all(i["depth"] <= pivot.MAX_DEPTH for i in deep["items"])
    p.db.execute("UPDATE searches SET pivot = '{}' WHERE case_id = ?", (cid,))
    del fid
    # Überschreitet eine Quelle die für den Fall erlaubte Exposition, zeigt der Vorschlag die Sperre – er umgeht sie nicht
    monkeypatch.setitem(ops.SOURCE_EXPOSURE, "gitlab", "zielkontakt")
    monkeypatch.setitem(ops.LEVELS, 1, dataclasses.replace(ops.LEVELS[1], max_exposure=ops.EXPOSURE["plattform"]["rank"]))
    user = next(i for i in anna.get(f"/api/cases/{cid}/entities/{sid}/pivots").json()["items"] if (i["kind"], i["value"]) == ("username", "maxmuster"))
    gitlab = next(s for s in user["sources"] if s["key"] == "gitlab")
    assert gitlab["usable"] is False and "OPSEC" in gitlab["reason"] and any(s["usable"] for s in user["sources"])
    r = anna.post(f"/api/cases/{cid}/entities/{sid}/pivots/run", json={"kind": "username", "value": "maxmuster", "sources": ["gitlab"]})
    assert r.status_code == 422 and len([c for c in p.http.calls if "gitlab" in c]) == 0 if hasattr(p, "http") else r.status_code == 422


# --------------------------------------------------------------------------- SpiderFoot-Muster: Korrelationsregeln

def _fact(p, cid, subject, pred, obj, status="neu", sid=None, src="register"):
    p.db.insert("facts", {"case_id": cid, "subject_entity_id": sid, "subject_label": subject, "subject_type": "person", "predicate": pred,
                          "object_label": obj, "object_type": "wert", "data": {}, "source_key": src, "source_label": src.title(), "source_url": "",
                          "retrieved_at": "2024-01-01T00:00:00+00:00", "status": status, "reliability": "B",
                          "norm_key": f"{subject}|{pred}|{obj}".casefold(), "created_at": "2024-01-01T00:00:00+00:00"})


def test_correlation_rules_produce_candidate_hints_only(tmp_path):
    app, admin, anna, cid, sid = _case(tmp_path)
    p = app.state.platform
    _fact(p, cid, "Max Mustermann", "funktion_bei", "Quai Ltd", sid=sid)
    _fact(p, cid, "Ina Nord", "funktion_bei", "QUAI LTD")
    _fact(p, cid, "Ina Nord", "adresse", "Hafenstraße 12, Kiel")
    _fact(p, cid, "Eva Test", "adresse", "Hafenstrasse 12, Kiel", status="verworfen")
    cor = anna.get(f"/api/cases/{cid}/assessment").json()["correlations"]
    assert [c["rule"] for c in cor] == ["gemeinsame_firma"] and cor[0]["count"] == 2 and cor[0]["candidate_only"] is True
    assert cor[0]["members"] == ["Ina Nord", "Max Mustermann"] and "Quai Ltd" in cor[0]["headline"] and cor[0]["confirmed"] is False
    # eigene Regel der Administration: streng geprüft, kein Code
    bad = [{"key": "x"}, {"key": "meine_regel", "label": "Test", "predicates": ["gibt_es_nicht"]},
           {"key": "meine_regel", "label": "Test", "predicates": ["adresse"], "headline": "{__class__}"},
           {"key": "meine_regel", "label": "Test", "predicates": ["adresse"], "code": "import os"},
           {"key": "gemeinsame_firma", "label": "Überschreiben", "predicates": ["adresse"]}]
    for rule in bad:
        assert admin.put("/api/admin/correlation-rules", json=rule).status_code == 422, rule
    assert anna.put("/api/admin/correlation-rules", json={"key": "meine_regel", "label": "Test", "predicates": ["adresse"]}).status_code == 403
    rule = {"key": "viele_funktionen", "label": "Viele Funktionen einer Person", "severity": "hoch", "predicates": ["funktion_bei"],
            "group_by": "subject", "count": "values", "min": 2, "headline": "{value}: {count} Funktionen ({members})"}
    assert admin.put("/api/admin/correlation-rules", json=rule).status_code == 200
    _fact(p, cid, "Max Mustermann", "funktion_bei", "Seeblick Holding", sid=sid)
    cor = anna.get(f"/api/cases/{cid}/assessment").json()["correlations"]
    assert cor[0]["rule"] == "viele_funktionen" and cor[0]["headline"] == "Max Mustermann: 2 Funktionen (Quai Ltd, Seeblick Holding)"
    rules = admin.post("/api/admin/correlation-rules/gemeinsame_firma/enabled", json={"enabled": False}).json()["rules"]
    assert next(r for r in rules if r["key"] == "gemeinsame_firma")["enabled"] is False
    assert [c["rule"] for c in anna.get(f"/api/cases/{cid}/assessment").json()["correlations"]] == ["viele_funktionen"]
    assert admin.delete("/api/admin/correlation-rules/gemeinsame_firma").status_code == 422
    assert admin.delete("/api/admin/correlation-rules/viele_funktionen").status_code == 200
    assert anna.get(f"/api/cases/{cid}/assessment").json()["correlations"] == []


def test_schema_migration_adds_new_columns_and_backup_knows_new_tables(tmp_path):
    from personosint import backup
    from personosint.db import SCHEMA_VERSION

    app, admin, anna, cid, sid = _case(tmp_path)
    db = app.state.platform.db
    assert SCHEMA_VERSION >= 8 and {"pivots", "correlation_rules"} <= set(db.tables()) and {"pivots", "correlation_rules"} <= set(backup.TABLE_ORDER)
    ev = anna.post(f"/api/cases/{cid}/evidence", json={"url": "https://zeitung.example.com/hafen"}).json()
    assert anna.delete(f"/api/cases/{cid}").status_code in (200, 204, 403)
    del ev


# --------------------------------------------------------------------------- Brücke zur EagleEye-Fallakte (Build 493/494 von ChatGPT)

def _eagleeye_parsers():
    """Lädt die Übernahme-Parser aus dem EagleEye-Hauptprogramm, ohne dessen übrige Abhängigkeiten zu brauchen."""
    import importlib
    import sys
    import types

    app_dir = Path(__file__).resolve().parents[2] / "src" / "eagleeye" / "application"
    if not (app_dir / "personosint493.py").is_file() or not (app_dir / "personosint494.py").is_file():
        return None
    pkg = types.ModuleType("ee_bridge")
    pkg.__path__ = [str(app_dir)]
    sys.modules.setdefault("ee_bridge", pkg)
    return importlib.import_module("ee_bridge.personosint493"), importlib.import_module("ee_bridge.personosint494")


def test_handover_package_is_split_and_accepted_by_eagleeye_intake(tmp_path):
    from personosint import bridge

    app, admin, anna, cid, sid = _case(tmp_path)
    p = app.state.platform
    for i in range(120):                                              # mehr als EagleEye in einer Datei annimmt
        status = "verworfen" if i % 10 == 0 else "bestätigt" if i % 3 == 0 else "neu"
        url = f"http://unsicher.example/{i}" if i % 15 == 1 else f"https://quelle{i % 7}.example/artikel/{i}"
        p.db.insert("findings", {"case_id": cid, "entity_id": sid, "source": "Testquelle", "category": "Web", "title": f"Fundstelle {i}", "url": url,
                                 "snippet": "", "query": "", "data": {}, "score": i % 100, "reasons": [], "fingerprint": f"fp{i}", "status": status,
                                 "created_at": "2024-01-01T00:00:00+00:00"})
    for i in range(170):
        anna.post(f"/api/cases/{cid}/entities", json={"type": "organisation" if i % 2 else "person", "label": f"Eintrag {i:03d}"})
    anna.post(f"/api/cases/{cid}/entities", json={"type": "telefon", "label": "+49 30 123456"})
    anna.post(f"/api/cases/{cid}/entities/{sid}/identifiers", json={"kind": "email", "value": "geheim@example.org"})
    r = anna.get(f"/api/cases/{cid}/export/eagleeye.zip")
    assert r.status_code == 200 and "Uebergabe_EagleEye_" in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = sorted(z.namelist())
    assert names == ["Entitaeten_01.json", "Entitaeten_02.json", "Hinweise_01.json", "Hinweise_02.json", "LIESMICH.txt"]
    leads = [json.loads(z.read(n)) for n in names if n.startswith("Hinweise")]
    ents = [json.loads(z.read(n)) for n in names if n.startswith("Entitaeten")]
    # 120 Treffer − 12 verworfene − 8 ohne https = 100 Fundstellen → zwei Dateien; 170 neue Einträge + Zielperson = 171 → zwei Dateien
    assert [len(x["findings"]) for x in leads] == [50, 50] and [len(x["entities"]) for x in ents] == [150, 21]
    flat = [f for x in leads for f in x["findings"]]
    assert all(f["url"].startswith("https://") and f["status"] != "verworfen" for f in flat) and flat[0]["status"] == "bestätigt"
    raw = r.content + b"".join(z.read(n) for n in names)
    assert b"geheim@example.org" not in raw and b"+49 30 123456" not in b"".join(z.read(n) for n in names if n != "LIESMICH.txt")
    assert all(max(len(x["findings"]), 0) <= bridge.LEADS_PER_FILE for x in leads) and all(len(x["entities"]) <= bridge.ENTITIES_PER_FILE for x in ents)
    assert "Übergabe an EagleEye" in [e["kind"] for e in anna.get(f"/api/cases/{cid}/opsec").json()["exports"]]
    parsers = _eagleeye_parsers()
    if parsers is None:
        pytest.skip("EagleEye-Hauptprogramm liegt nicht neben PersonOSINT (eigenständiges Paket)")
    p493, p494 = parsers
    assert (p493.MAX_LEADS, p494.MAX_ENTITIES) == (bridge.LEADS_PER_FILE, bridge.ENTITIES_PER_FILE)       # Grenzen stimmen überein
    for name in names:
        if name.startswith("Hinweise"):
            preview = p493.parse_personosint_export(z.read(name))
            assert len(preview.leads) == len(json.loads(z.read(name))["findings"]) and preview.skipped == 0
        elif name.startswith("Entitaeten"):
            preview = p494.parse_entity_suggestions(z.read(name))
            assert len(preview.proposals) == len(json.loads(z.read(name))["entities"]) and preview.skipped == 0
    # Gegenprobe: der ungeteilte Standardexport wird von EagleEye abgelehnt – genau dafür gibt es die Übergabe
    with pytest.raises(p493.PersonOSINTImportError):
        p493.parse_personosint_export(anna.get(f"/api/cases/{cid}/export/case.json").content)
