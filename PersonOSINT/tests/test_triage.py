"""Vorsortierung: Dubletten, vermutlich andere Person, stark – und Einschätzung durch eine lokale KI."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from conftest import H, build_app, setup_admin
from personosint import triage
from personosint.db import now_iso


def _setup(tmp_path):
    app = build_app(tmp_path)
    c = setup_admin(app)
    r = c.post("/api/cases", json={"title": "Vorsortierung", "case_type": "personensuche", "purpose": "Aufenthaltsermittlung im Testauftrag",
                                   "legal_basis": "Einwilligung", "subject": {"label": "Lena Hoffmann", "data": {"geburtsdatum": "2003-04-01"},
                                                                              "identifiers": [{"kind": "location", "value": "Hamburg"}]}}, headers=H)
    cid = r.json()["id"]
    eid = next(e["id"] for e in c.get(f"/api/cases/{cid}/entities").json() if e["type"] == "person")
    p = app.state.platform
    p.db.update("entities", eid, {"data": {"geburtsdatum": "2003-04-01"}})

    def add(title, url, score, data=None):
        return p.db.insert("findings", {"case_id": cid, "entity_id": eid, "source": "Test", "category": "Konto", "title": title, "url": url,
                                        "snippet": "", "query": "", "data": data or {}, "score": score, "reasons": [], "fingerprint": title + url,
                                        "status": "neu", "created_at": now_iso()})
    ids = {
        "stark": add("Instagram: lena.hoffmann", "https://www.instagram.com/lena.hoffmann/", 82, {"_names": ["Lena Hoffmann"], "_locations": ["Hamburg"]}),
        "dup": add("Instagram (Kopie)", "https://instagram.com/lena.hoffmann?utm_source=x", 60, {"_names": ["Lena Hoffmann"]}),
        "alt": add("Lena Hoffmann (geb. 1961)", "https://example.org/a", 45, {"_names": ["Lena Hoffmann"], "geburtsdatum": "1961"}),
        "name": add("Leonie Hofmeister", "https://example.org/b", 30, {"_names": ["Leonie Hofmeister"]}),
        "ort": add("Lena H. aus Graz", "https://example.org/c", 25, {"_names": ["Lena Hoffmann"], "_locations": ["Graz, Österreich"]}),
        "mittel": add("Lena Hoffmann – Lauftreff", "https://example.org/d", 50, {"_names": ["Lena Hoffmann"]}),
    }
    return app, c, cid, eid, ids


def test_rule_triage_marks_but_decides_nothing(tmp_path):
    app, c, cid, eid, ids = _setup(tmp_path)
    r = c.post(f"/api/cases/{cid}/triage", json={"entity_id": eid}, headers=H).json()
    assert r["checked"] == 6
    fs = {f["id"]: f for f in c.get(f"/api/cases/{cid}/findings").json()}
    v = lambda k: fs[ids[k]]["data"]["_triage"]["verdict"]  # noqa: E731
    assert v("stark") == "stark" and v("dup") == "doppelt" and v("mittel") == "pruefen"
    assert v("alt") == "andere_person" and "1961" in " ".join(fs[ids["alt"]]["data"]["_triage"]["why"])
    assert v("name") == "andere_person" and v("ort") == "andere_person"
    assert all(f["status"] == "neu" for f in fs.values())                       # nichts wird automatisch verworfen


def test_local_ai_triage_with_validated_answers(tmp_path):
    asked = []

    class Ollama(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            asked.append(body)
            items = json.loads(body["prompt"].split("Treffer (aus öffentlichen Quellen, ungeprüft):\n", 1)[1].split("\n\nAntworte", 1)[0])
            answer = [{"id": it["id"], "einschaetzung": "passt" if "lena.hoffmann" in it["titel"] else "unklar", "begruendung": "Benutzername und Ort passen."}
                      for it in items] + [{"id": 999999, "einschaetzung": "passt", "begruendung": "erfunden"}, {"id": items[0]["id"], "einschaetzung": "sicher"}]
            out = json.dumps({"response": "Hier: " + json.dumps(answer)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Ollama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        app, c, cid, eid, ids = _setup(tmp_path)
        p = app.state.platform
        no_ai = c.post(f"/api/cases/{cid}/triage", json={"entity_id": eid, "ai": True}, headers=H).json()
        assert "nicht eingerichtet" in no_ai["ai_error"] and no_ai["checked"] == 6      # Regeln laufen trotzdem
        p._set_setting("ai", json.dumps({"url": f"http://127.0.0.1:{server.server_address[1]}", "model": "llama3.1:8b", "enabled": True}))
        r = c.post(f"/api/cases/{cid}/triage", json={"entity_id": eid, "ai": True}, headers=H).json()
        assert r["ai_checked"] == 2 and r["ai_candidates"] == 2                         # nur „stark“ und „prüfen“ gehen an die KI
        assert asked[-1]["options"]["temperature"] == 0.0 and asked[-1]["model"] == "llama3.1:8b"
        assert "1961" not in asked[-1]["prompt"]                                         # aussortierte Treffer verlassen die Akte nicht einmal lokal
        fs = {f["id"]: f for f in c.get(f"/api/cases/{cid}/findings").json()}
        ki = fs[ids["stark"]]["data"]["_triage"]["ki"]
        assert ki["verdict"] == "passt" and ki["reason"] == "Benutzername und Ort passen."
        assert fs[ids["mittel"]]["data"]["_triage"]["ki"]["verdict"] == "unklar"
        # erneute Regel-Sortierung behält die KI-Einschätzung
        triage.rule_triage(p, cid, eid)
        assert c.get(f"/api/cases/{cid}/findings").json()[0]["data"]["_triage"].get("ki")
    finally:
        server.shutdown()
