"""Fiktiver Beispielfall zum Kennenlernen der Oberfläche (keine realen Personen)."""
from __future__ import annotations

import hashlib

from .db import now_iso
from .service import Platform

DEMO_NOTE = "BEISPIELFALL – alle Personen, Konten und Ereignisse sind frei erfunden."


def seed_demo(p: Platform) -> int:
    auto = p.auto_geocode
    p.auto_geocode = False  # Beispieldaten bringen Koordinaten mit, keine Netzabfrage nötig
    try:
        case = p.create_case({
            "title": "Beispiel: Vermisste Studentin Lena Hoffmann",
            "case_type": "vermisst",
            "purpose": "Unterstützung der Angehörigen bei der Suche nach einer vermissten Person (Beispielfall zum Kennenlernen).",
            "legal_basis": "Auftrag der Angehörigen; Abstimmung mit Polizei Hamburg (fiktiv)",
            "client": "Familie Hoffmann (fiktiv)", "analyst": "Demo-Analyst", "notes": DEMO_NOTE,
            "subject": {
                "label": "Lena Hoffmann",
                "data": {
                    "geburtsdatum": "2003-04-17", "geschlecht": "weiblich", "nationalitaet": "deutsch", "wohnort": "Hamburg-Altona",
                    "beruf": "Studentin (Biologie)", "groesse": "168 cm", "statur": "schlank", "haare": "dunkelblond, schulterlang",
                    "augen": "blaugrün", "merkmale": "kleines Tattoo (Schwalbe) am linken Handgelenk",
                    "vermisst_status": "vermisst", "vermisst_seit": "2026-10-28", "zuletzt_gesehen_zeit": "2026-10-28 22:40",
                    "zuletzt_gesehen_ort": "Hamburg, S-Bahn Holstenstraße", "kleidung": "grüne Regenjacke, Jeans, weiße Sneaker, grauer Rucksack",
                    "mitgefuehrt": "Smartphone (seit 23:15 aus), Fahrrad nicht mitgenommen",
                    "umstaende": "Verließ nach einem Streit eine WG-Feier; wollte angeblich zu einer Freundin nach Eimsbüttel.",
                    "gesundheit": "Asthma, Inhalator vermutlich nicht dabei", "anlaufpunkte": "Elbstrand Övelgönne, Uni-Bibliothek, Kletterhalle",
                    "polizei_dienststelle": "Polizeikommissariat 21 (fiktiv)", "aktenzeichen": "VM-0000/26 (fiktiv)",
                    "kontakt_hinweise": "Polizeinotruf 110", "risiko": ["untypisch", "medizinisch", "ohne_mittel"],
                    "notizen": DEMO_NOTE,
                },
                "identifiers": [
                    {"kind": "username", "value": "lena.hoff.example"},
                    {"kind": "email", "value": "lena.hoffmann@example.org"},
                    {"kind": "location", "value": "Hamburg"},
                    {"kind": "employer", "value": "Universität Hamburg"},
                    {"kind": "alias", "value": "Leni"},
                ],
            },
        })
        cid = case["id"]
        subj = p.subject(cid)
        assert subj
        sid = subj["id"]

        def person(label: str, notes: str, idents: list[dict] | None = None) -> int:
            return p.create_entity(cid, {"type": "person", "label": label, "data": {"notizen": notes}, "identifiers": idents or []})["id"]

        def ent(t: str, label: str, data: dict | None = None) -> int:
            return p.create_entity(cid, {"type": t, "label": label, "data": data or {}})["id"]

        jonas = person("Jonas Brandt", "Ex-Freund; Streit am Abend des Verschwindens (fiktiv)", [{"kind": "username", "value": "jbrandt_hh"}, {"kind": "location", "value": "Hamburg"}])
        mara = person("Mara Yilmaz", "Freundin in Eimsbüttel, Ziel laut Zeugen (fiktiv)", [{"kind": "phone", "value": "0170 0000001"}])
        tim = person("Tim Wagner", "Mitbewohner, Gastgeber der WG-Feier (fiktiv)")
        sofia = person("Sofia Lange", "Kommilitonin, Kletterpartnerin (fiktiv)", [{"kind": "username", "value": "lena.hoff.example"}])
        uni = ent("organisation", "Universität Hamburg")
        climb = ent("organisation", "Kletterhalle Nordwand (fiktiv)")
        wg = ent("ort", "WG Bahrenfelder Straße", {"lat": 53.5566, "lon": 9.9285})
        sbahn = ent("ort", "S-Bahn Holstenstraße", {"lat": 53.5591, "lon": 9.9445})
        oevel = ent("ort", "Elbstrand Övelgönne", {"lat": 53.5450, "lon": 9.9135})
        insta = ent("konto", "Instagram: lena.hoff.example", {"url": "https://example.org/insta/lena.hoff.example", "plattform": "Instagram"})
        phone = ent("telefon", "+49 170 0000002 (Lena)")

        for s, t, rel, conf, ev in [
            (sid, jonas, "Partner/in von", 70, "Aussage Mitbewohner: Beziehung bis September"),
            (sid, mara, "befreundet mit", 90, "Chatverlauf laut Familie"),
            (sid, tim, "Kontakt mit", 95, "Mitbewohner"),
            (sid, sofia, "befreundet mit", 85, "Gemeinsame Fotos auf Instagram"),
            (sid, uni, "Mitglied von", 95, "Immatrikulation laut Familie"),
            (sofia, uni, "Mitglied von", 80, "Profilangabe"),
            (sid, climb, "Mitglied von", 75, "Mitgliedskarte im Zimmer"),
            (sofia, climb, "Mitglied von", 70, "Instagram-Fotos"),
            (jonas, climb, "Mitglied von", 40, "Unbestätigter Hinweis"),
            (tim, wg, "wohnt in", 95, "Meldeadresse"),
            (sid, wg, "wohnt in", 95, "Meldeadresse"),
            (sid, sbahn, "zuletzt gesehen in", 80, "Zeugin (Nachbarin)"),
            (sid, insta, "besitzt Konto", 95, "Von Familie bestätigt"),
            (sid, phone, "nutzt Telefon", 95, "Familie"),
            (jonas, mara, "Kontakt mit", 35, "Gemeinsamer Freundeskreis (unsicher)"),
            (sid, oevel, "hält sich auf in", 50, "Lieblingsort laut Familie"),
        ]:
            p.create_link(cid, {"source_id": s, "target_id": t, "relation": rel, "confidence": conf, "evidence": ev})

        for when, kind, loc, lat, lon, desc, src, rel, who in [
            ("2026-10-28T19:30", "Ereignis", "WG Bahrenfelder Straße, Hamburg", 53.5566, 9.9285, "Ankunft auf WG-Feier", "Tim Wagner", "bestätigt", sid),
            ("2026-10-28T22:15", "Letzter Kontakt", "WG Bahrenfelder Straße, Hamburg", 53.5566, 9.9285, "Streit mit Jonas Brandt, verlässt die Feier", "Mehrere Gäste", "bestätigt", sid),
            ("2026-10-28T22:40", "Letzte Sichtung", "S-Bahn Holstenstraße, Hamburg", 53.5591, 9.9445, "Am Bahnsteig Richtung Eimsbüttel gesehen", "Nachbarin", "wahrscheinlich", sid),
            ("2026-10-28T23:15", "Online-Aktivität", "Hamburg", 53.5600, 9.9500, "Letzte WhatsApp-Online-Anzeige, danach Handy aus", "Familie", "bestätigt", sid),
            ("2026-10-29T08:10", "Sichtung (Hinweis)", "Elbstrand Övelgönne, Hamburg", 53.5450, 9.9135, "Spaziergänger meldet Frau mit grüner Jacke", "Hinweistelefon", "ungeprüft", sid),
            ("2026-10-28T23:30", "Bewegung/Reise", "Eimsbüttel, Hamburg", 53.5755, 9.9530, "Jonas Brandt nach eigener Aussage auf dem Heimweg", "Jonas Brandt", "ungeprüft", jonas),
        ]:
            p.create_event(cid, {"occurred_at": when, "kind": kind, "location": loc, "lat": lat, "lon": lon, "description": desc,
                                 "source": src, "reliability": rel, "entity_id": who})

        demo_findings = [
            ("Konto", "Instagram: lena.hoff.example", "https://example.org/insta/lena.hoff.example", "Letzter Beitrag 27.10.2026, Kletterhalle", "bestätigt", 88,
             ["Benutzername stimmt überein", "Ort erwähnt: Hamburg"], {"plattform": "Instagram", "benutzername": "lena.hoff.example"}),
            ("Beruf/Bildung", "Uni Hamburg – Tutorenliste Biologie (fiktiv)", "https://example.org/uni/tutoren", "Lena Hoffmann, Tutorin Zellbiologie", "bestätigt", 76,
             ["Name stimmt überein: „Lena Hoffmann“", "Arbeitgeber/Organisation erwähnt: Universität Hamburg"], {"institutionen": ["Universität Hamburg"]}),
            ("Konto", "Strava: lenah_runs (fiktiv)", "https://example.org/strava/lenah_runs", "Laufstrecken entlang der Elbe, letzte Aktivität 26.10.", "neu", 52,
             ["Name sehr ähnlich: „Lena H.“ (91 %)", "Ort erwähnt: Hamburg"], {"plattform": "Strava", "benutzername": "lenah_runs"}),
            ("Öffentliche Person", "Lena Hoffmann – Schauspielerin (fiktiv)", "https://example.org/wiki/lena-hoffmann-actress", "Deutsche Schauspielerin, geb. 1979", "verworfen", 31,
             ["Name stimmt überein: „Lena Hoffmann“", "Geburtsjahr weicht ab"], {}),
            ("Konto", "Bluesky: lenahoffmann.bsky.social (fiktiv)", "https://example.org/bsky/lenahoffmann", "Grafikdesignerin aus München", "neu", 38,
             ["Name stimmt überein: „Lena Hoffmann“", "Ort weicht ab"], {"plattform": "Bluesky", "benutzername": "lenahoffmann"}),
        ]
        for cat, title, url, snip, status, score, reasons, data in demo_findings:
            p.db.insert("findings", {"case_id": cid, "entity_id": sid, "source": "Beispieldaten", "category": cat, "title": title, "url": url,
                                     "snippet": snip, "query": "Lena Hoffmann", "data": data, "score": score, "reasons": reasons,
                                     "fingerprint": hashlib.sha1(url.encode()).hexdigest(), "status": status,
                                     "review_note": "Beispielprüfung" if status != "neu" else "", "created_at": now_iso(),
                                     "reviewed_at": now_iso() if status != "neu" else None})
        tasks = p.list_tasks(cid)
        for t in tasks[:3]:
            p.update_task(cid, t["id"], {"done": True})
        p.log(cid, "Beispielfall geladen", DEMO_NOTE)
        return cid
    finally:
        p.auto_geocode = auto
