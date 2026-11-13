"""Schritt 4: Überwachung mit Benachrichtigungen, lokaler KI-Assistent mit Fußnotenprüfung und Freigabe."""
from __future__ import annotations

import io
import json
import re
import threading
import zipfile
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import add_user, build_app, setup_admin
from personosint import monitor
from test_personosint import FakeHttp
from test_step2_analysis import ROUTES as R2, SUBJECT

CH = "https://api.company-information.service.gov.uk"


def _setup(tmp_path, backend="sqlite", level=1):
    routes = dict(R2)
    http = FakeHttp(routes)
    app = build_app(tmp_path, backend, http=http)
    admin = setup_admin(app)
    anna = add_user(admin, app, "anna", "analyst")
    rita = add_user(admin, app, "rita", "pruefer")
    admin.put("/api/admin/sources/companies_house/key", json={"key": "k"})
    cid = anna.post("/api/cases", json={"title": "Monitoring", "case_type": "investigativ", "purpose": "Laufende Beobachtung von Firmenfunktionen",
                                        "legal_basis": "Journalistische Recherche (Medienprivileg)", "opsec_level": level, "subject": SUBJECT}).json()["id"]
    anna.patch(f"/api/cases/{cid}", json={"reviewer_id": rita.uid})
    sid = anna.get(f"/api/cases/{cid}/overview").json()["subject"]["id"]
    return app, http, routes, admin, anna, rita, cid, sid


def test_watch_reports_only_new_findings(tmp_path, backend):
    app, http, routes, admin, anna, rita, cid, sid = _setup(tmp_path, backend)
    p = app.state.platform
    assert anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": ["companies_house"]}).json()["new_findings"] == 2
    w = anna.post(f"/api/cases/{cid}/watches", json={"entity_id": sid, "sources": ["companies_house"], "interval_hours": 24})
    assert w.status_code == 201 and w.json()["interval_label"] == "täglich"
    wid = w.json()["id"]
    assert monitor.run_due(p) == 0                                         # noch nicht fällig
    # Neue Funktion taucht im Register auf
    routes[f"{CH}/search/officers"] = (200, {"items": R2[f"{CH}/search/officers"][1]["items"] + [
        {"title": "Max MUSTERMANN", "date_of_birth": {"month": 5, "year": 1980}, "links": {"self": "/officers/c3/appointments"}}]})
    routes[f"{CH}/officers/c3/appointments"] = (200, {"items": [{"appointed_to": {"company_name": "NEUE HOLDING LTD"}, "officer_role": "director", "appointed_on": "2026-10-01"}]})
    later = datetime.now(timezone.utc) + timedelta(hours=25)
    assert monitor.run_due(p, later) == 1
    wl = anna.get(f"/api/cases/{cid}/watches").json()[0]
    assert wl["last_new"] == 1 and wl["runs"] == 1 and "1 neue Treffer" in wl["last_result"]
    for c in (anna, rita):
        n = c.get("/api/notifications").json()
        assert n["unread"] == 1 and "1 neue Treffer" in n["items"][0]["text"] and n["items"][0]["link"] == f"#/case/{cid}/search"
    assert admin.get("/api/notifications").json()["unread"] == 0          # Administration ist nicht im Fallteam
    anna.post("/api/notifications/seen", json={})
    assert anna.get("/api/notifications").json()["unread"] == 0
    # erneuter Lauf ohne Neues: keine weitere Benachrichtigung
    r = anna.post(f"/api/cases/{cid}/watches/{wid}/run").json()
    assert r["ok"] and r["new"] == 0 and rita.get("/api/notifications").json()["unread"] == 1
    # Pausieren / Löschen; Leserechte reichen nicht
    assert anna.patch(f"/api/cases/{cid}/watches/{wid}", json={"active": False}).json()["active"] == 0
    assert monitor.run_due(p, later + timedelta(days=10)) == 0
    lea = add_user(admin, app, "lea", "leser")
    anna.put(f"/api/cases/{cid}/members", json={"members": [{"user_id": lea.uid, "role": "leser"}]})
    assert lea.post(f"/api/cases/{cid}/watches", json={"entity_id": sid, "sources": ["companies_house"]}).status_code == 403
    assert anna.delete(f"/api/cases/{cid}/watches/{wid}").status_code == 204


def test_watch_respects_opsec(tmp_path):
    app, http, routes, admin, anna, rita, cid, sid = _setup(tmp_path, level=2)
    anna.post(f"/api/cases/{cid}/opsec/briefing")
    wid = anna.post(f"/api/cases/{cid}/watches", json={"entity_id": sid, "sources": ["companies_house"], "interval_hours": 6}).json()["id"]
    calls = len(http.calls)
    res = anna.post(f"/api/cases/{cid}/watches/{wid}/run").json()
    assert not res["ok"] and "Direktabfragen" in res["message"] and len(http.calls) == calls     # fail closed
    n = anna.get("/api/notifications").json()["items"][0]
    assert n["kind"] == "warnung" and "konnte nicht laufen" in n["text"] and "Monitoring" not in n["text"]   # Deckname statt Titel


# ---------------------------------------------------------------- KI

class _Ollama(BaseHTTPRequestHandler):
    mode = "gut"
    prompts: list[str] = []

    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        self._send({"models": [{"name": "llama3.1:8b"}, {"name": "qwen2.5:7b"}]})

    def do_POST(self):  # noqa: N802
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Ollama.prompts.append(req["prompt"])
        ids = re.findall(r"\[F(\d+)\]", req["prompt"])
        if _Ollama.mode == "gut":
            text = f"Max Mustermann ist als Direktor mehrerer Gesellschaften registriert [F{ids[0]}, F{ids[1]}]. Mehrere dieser Firmen wurden aufgelöst [F{ids[2]}]."
        else:
            text = f"Max Mustermann leitet die Hafen Beteiligungs GmbH [F{ids[0]}]. Er gilt als sehr wohlhabend. Laut Quelle [F999999] lebt er in Monaco."
        self._send({"response": text, "model": req["model"]})

    def log_message(self, *a):
        pass


@pytest.fixture()
def ollama():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Ollama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    _Ollama.prompts = []
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_local_ai_summary_with_citation_checks(tmp_path, ollama):
    app, http, routes, admin, anna, rita, cid, sid = _setup(tmp_path)
    anna.post(f"/api/cases/{cid}/search", json={"entity_id": sid, "sources": ["companies_house", "opencorporates"]})
    groups = anna.get(f"/api/cases/{cid}/candidates", params={"entity_id": sid}).json()
    assert anna.post(f"/api/cases/{cid}/ai").status_code == 422                       # noch nicht eingerichtet
    assert admin.put("/api/admin/ai", json={"url": "http://8.8.8.8:11434", "model": "x", "enabled": True}).status_code == 422
    assert admin.post("/api/admin/ai/test", json={"url": ollama}).json()["models"] == ["llama3.1:8b", "qwen2.5:7b"]
    assert admin.put("/api/admin/ai", json={"url": ollama, "model": "llama3.1:8b", "enabled": True}).json()["enabled"]
    r = anna.post(f"/api/cases/{cid}/ai")
    assert r.status_code == 422 and "bestätigten" in r.json()["detail"]                 # nur geprüfte Fakten
    anna.post(f"/api/cases/{cid}/candidates/review", json={"finding_ids": groups[0]["finding_ids"], "status": "bestätigt"})

    _Ollama.mode = "schlecht"
    d = anna.post(f"/api/cases/{cid}/ai").json()
    assert d["checks"]["unknown"] == [999999] and len(d["checks"]["uncited"]) == 1 and not d["checks"]["ok"]
    prompt = _Ollama.prompts[-1]
    assert "Lyon Boulangerie" not in prompt and "[F" in prompt                         # nur bestätigte Fakten
    assert rita.patch(f"/api/cases/{cid}/ai/{d['id']}", json={"status": "freigegeben"}).status_code == 422
    fixed = re.sub(r" Er gilt als sehr wohlhabend\.| Laut Quelle \[F999999\] lebt er in Monaco\.", "", d["text"])
    e = anna.patch(f"/api/cases/{cid}/ai/{d['id']}", json={"text": fixed}).json()
    assert e["checks"]["ok"]

    _Ollama.mode = "gut"
    g = anna.post(f"/api/cases/{cid}/ai").json()
    assert g["checks"]["ok"] and len(g["checks"]["cited"]) == 3
    assert rita.patch(f"/api/cases/{cid}/ai/{g['id']}", json={"status": "freigegeben"}).json()["approved_by"] == "Rita"
    assert rita.patch(f"/api/cases/{cid}/ai/{g['id']}", json={"text": "geändert"}).status_code == 422
    doc = anna.get(f"/api/cases/{cid}/export/dossier.docx", params={"template": "kurzprofil"}).content
    with zipfile.ZipFile(io.BytesIO(doc)) as z:
        xml = z.read("word/document.xml").decode()
    assert "registriert" in xml and "KI-gestützter Entwurf" in xml and "freigegeben von Rita" in xml
    assert "[F" not in xml and re.search(r"Gesellschaften registriert \[\d+\]", xml)       # Kennungen -> Fußnoten
    pv = anna.get(f"/api/cases/{cid}/dossier/preview", params={"template": "kurzprofil"}).json()
    assert pv["ai"]
    actions = [a["action"] for a in anna.get(f"/api/cases/{cid}/audit").json()]
    assert "KI-Entwurf erzeugt" in actions and "KI-Entwurf freigegeben" in actions
