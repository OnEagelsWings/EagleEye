"""Schritt 3: Beweissicherung, Top-Dossier (Vorlagen, Management Summary, Belegdichte, Fußnoten), Berichtslayout, PDF."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest

from conftest import add_user, build_app, setup_admin
from personosint import report
from test_personosint import FakeHttp
from test_step2_analysis import ROUTES as R2, SUBJECT

PAGE = b"<!doctype html><html><head><title>Registerauszug Nordhafen</title><script>alert(1)</script></head><body><h1>Max Mustermann</h1> Direktor seit 2019</body></html>"
ROUTES = {**R2,
          "https://register.example.com/auszug": (200, PAGE),
          "https://archive.org/wayback/available": (200, {"archived_snapshots": {"closest": {"available": True, "url": "http://web.archive.org/web/2024/https://register.example.com/auszug"}}})}


def _docx_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        return " ".join(z.read(n).decode() for n in z.namelist() if n.startswith("word/") and n.endswith(".xml"))


def _setup(tmp_path, backend="sqlite"):
    app = build_app(tmp_path, backend, http=FakeHttp(ROUTES))
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    admin.put("/api/admin/sources/companies_house/key", json={"key": "k"})
    cid = anna.post("/api/cases", json={"title": "Dossiertest", "case_type": "investigativ", "purpose": "Recherche zu Firmenverflechtungen",
                                        "legal_basis": "Journalistische Recherche (Medienprivileg)", "opsec_level": 1, "subject": SUBJECT}).json()["id"]
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": ["companies_house", "opencorporates"]})
    groups = anna.get(f"/api/cases/{cid}/candidates", params={"entity_id": sid}).json()
    anna.post(f"/api/cases/{cid}/candidates/review", json={"finding_ids": groups[0]["finding_ids"], "status": "bestätigt"})
    return app, admin, anna, cid, sid


def test_evidence_capture_and_package(tmp_path, backend):
    app, admin, anna, cid, sid = _setup(tmp_path, backend)
    r = anna.post(f"/api/cases/{cid}/evidence", json={"url": "https://register.example.com/auszug", "note": "Registerauszug"})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["sha256"] == hashlib.sha256(PAGE).hexdigest() and ev["title"] == "Registerauszug Nordhafen"
    assert "alert" not in ev["excerpt"] and ev["archive_url"].startswith("http://web.archive.org/") and "file" not in ev
    files = sorted((tmp_path / "evidence").iterdir())
    assert len(files) == 3 and all(PAGE not in f.read_bytes() for f in files)   # Original, WARC und Textfassung – alles verschlüsselt
    stored = [f for f in files if f.name.endswith(".enc") and ".warc." not in f.name and ".txt." not in f.name]
    assert len(stored) == 1 and ev["has_warc"] and ev["has_text"] and "warc_file" not in ev
    dl = anna.get(f"/api/cases/{cid}/evidence/{ev['id']}/download")
    assert dl.content == PAGE and dl.headers["content-type"] == "application/octet-stream" and "attachment" in dl.headers["content-disposition"]
    # SSRF-Schutz
    for bad in ("http://127.0.0.1:8380/api/cases", "http://10.1.2.3/", "file:///etc/passwd", "http://localhost/x", "http://[::1]/"):
        assert anna.post(f"/api/cases/{cid}/evidence", json={"url": bad}).status_code == 422, bad
    # Außenkontakt-Protokoll enthält die Sicherung
    hosts = {h["host"] for h in anna.get(f"/api/cases/{cid}/opsec").json()["hosts"]}
    assert "register.example.com" in hosts
    # Beweispaket
    z = zipfile.ZipFile(io.BytesIO(anna.get(f"/api/cases/{cid}/export/beweispaket.zip").content))
    man = json.loads(z.read("manifest.json"))
    entry = man["belege"][0]
    assert hashlib.sha256(z.read(entry["datei"])).hexdigest() == entry["sha256"] and "PRUEFANLEITUNG.txt" in z.namelist()
    assert man["export_id"].startswith("EX-")
    # Manipulation wird erkannt
    stored[0].write_bytes(app.state.platform.vault.encrypt(b"manipuliert"))
    assert anna.get(f"/api/cases/{cid}/evidence/{ev['id']}/download").status_code == 422


def test_dossier_templates_summary_density_and_footnotes(tmp_path):
    app, admin, anna, cid, sid = _setup(tmp_path)
    finding = next(f for f in anna.get(f"/api/cases/{cid}/findings").json() if f["source"] == "UK Companies House" and f["status"] == "bestätigt")
    anna.post(f"/api/cases/{cid}/evidence", json={"url": "https://register.example.com/auszug", "finding_id": finding["id"]})
    pv = anna.get(f"/api/cases/{cid}/dossier/preview", params={"template": "due_diligence"}).json()
    keys = [s["key"] for s in pv["sections"]]
    assert keys == report.TEMPLATES["due_diligence"]["sections"]
    wirt = next(s for s in pv["sections"] if s["key"] == "wirtschaft")
    assert wirt["statements"] >= 4 and wirt["density"] == 100            # alle über Beleg gesichert bzw. mehrfach belegt
    assert pv["overall"]["density"] is not None and pv["redflags"] >= 1 and pv["evidence"] == 1
    assert any("Kandidatengruppen" in w or "ungeprüft" in w for w in pv["warnings"])

    d = anna.get(f"/api/cases/{cid}/export/dossier.docx", params={"template": "due_diligence"})
    assert d.status_code == 200
    text = _docx_text(d.content)
    for needle in ("Management Summary", "Kernaussagen", "Auffälligkeiten", "Belegstärke insgesamt", "Belegdichte:", "Funktion bei",
                   "Hafen Beteiligungs Gmbh", "A1", "Funktionen bei mehreren aufgelösten", "Quellenverzeichnis", "SHA-256",
                   "Bewertungsschlüssel (Admiralty-Code)", "Due-Diligence-Bericht", "Widersprüche und offene Identitätsfragen"):
        assert needle in text, needle
    assert "Lyon Boulangerie" not in text.split("Widersprüche und offene")[0]   # verworfener Namensvetter nicht in den Aussagen
    kurz = _docx_text(anna.get(f"/api/cases/{cid}/export/dossier.docx", params={"template": "kurzprofil"}).content)
    assert "Kurzprofil" in kurz and "Bearbeitungsprotokoll" not in kurz and "Verbindungen und Netzwerk" not in kurz
    # ungeprüfte Aussagen nur auf Wunsch und gekennzeichnet
    with_unrev = _docx_text(anna.get(f"/api/cases/{cid}/export/dossier.docx", params={"template": "volldossier", "include_unreviewed": True}).content)
    assert "(ungeprüft)" in with_unrev


def test_branding_applied(tmp_path):
    from PIL import Image
    app, admin, anna, cid, sid = _setup(tmp_path)
    assert admin.put("/api/admin/branding", json={"org_name": "Recherchebüro Nord", "footer": "Recherchebüro Nord GmbH · Hamburg",
                                                  "disclaimer": "Nur für den internen Gebrauch.", "color": "#7c3aed"}).status_code == 200
    assert admin.put("/api/admin/branding", json={"color": "lila"}).status_code == 422
    buf = io.BytesIO()
    Image.new("RGB", (300, 100), (124, 58, 237)).save(buf, "PNG")
    assert admin.post("/api/admin/branding/logo", files={"file": ("logo.png", buf.getvalue(), "image/png")}).json()["has_logo"]
    d = anna.get(f"/api/cases/{cid}/export/dossier.docx").content
    text = _docx_text(d)
    assert "Recherchebüro Nord ·" in text and "Recherchebüro Nord GmbH · Hamburg" in text and "Nur für den internen Gebrauch." in text
    assert "7C3AED" in text.upper()
    with zipfile.ZipFile(io.BytesIO(d)) as z:
        assert len([n for n in z.namelist() if n.startswith("word/media/")]) >= 2   # Logo + Netzwerkgrafik
    assert anna.put("/api/admin/branding", json={}).status_code == 403


@pytest.mark.skipif(not report.pdf_available(), reason="LibreOffice nicht installiert")
def test_pdf_export(tmp_path):
    app, admin, anna, cid, sid = _setup(tmp_path)
    r = anna.get(f"/api/cases/{cid}/export/dossier.docx", params={"template": "kurzprofil", "format": "pdf"})
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and r.headers["content-type"] == "application/pdf"
    assert b"pdfaid" in r.content or b"PDF/A" in r.content or b"/GTS_PDFA" in r.content
