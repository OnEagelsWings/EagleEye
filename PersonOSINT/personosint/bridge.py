"""Übergabe an die EagleEye-Fallakte (Build 493/494 – von ChatGPT gebaute Übernahme).

EagleEye übernimmt aus einem PersonOSINT-Fallexport bewusst nur zwei Dinge, beide als **ungeprüft**:
öffentliche HTTPS-Fundstellen als Recherchehinweise (Build 493) und Namen von Personen, Organisationen,
Orten, Ereignissen und Dokumenten als Prüfkandidaten (Build 494). Die Übernahme lehnt Dateien ab, die
mehr als 50 nutzbare Fundstellen oder mehr als 150 Einträge enthalten.

Dieses Modul erzeugt deshalb ein Paket aus passend geteilten Dateien – und gibt nur weiter, was
EagleEye auch verarbeitet (Datensparsamkeit): keine Kennungen, Notizen, Fotos, Aussagen oder Bewertungen.
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

LEADS_PER_FILE = 50       # Grenze in src/eagleeye/application/personosint493.py (MAX_LEADS)
ENTITIES_PER_FILE = 150   # Grenze in src/eagleeye/application/personosint494.py (MAX_ENTITIES)
CASE_LEAD_LIMIT = 250     # Obergrenze je EagleEye-Fall (research483)
ENTITY_TYPES = ("person", "organisation", "ort", "ereignis", "dokument")


def eligible_leads(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Fundstellen, die EagleEye annimmt: https, Standardport, keine Zugangsdaten, nicht verworfen, je Adresse einmal."""
    ordered = sorted(findings, key=lambda f: (f["status"] != "bestätigt", -int(f.get("score") or 0), f["id"]))
    out, seen = [], set()
    for f in ordered:
        url = " ".join(str(f.get("url") or "").split())
        if f["status"] == "verworfen" or not url or len(url) > 1800 or url in seen:
            continue
        try:
            parts = urlsplit(url)
            ok = parts.scheme == "https" and bool(parts.hostname) and not parts.username and not parts.password and parts.port in (None, 443)
        except ValueError:
            ok = False
        if not ok:
            continue
        seen.add(url)
        out.append({"url": url, "title": " ".join(str(f.get("title") or "").split())[:240], "source": str(f.get("source") or "")[:100],
                    "status": f["status"]})
    return out


def eligible_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": e["id"], "type": e["type"], "label": " ".join(str(e["label"]).split())[:512]}
            for e in entities if e["type"] in ENTITY_TYPES and str(e.get("label") or "").strip()]


def package(p, case_id: int, export_id: str) -> bytes:
    """ZIP mit „Hinweise_NN.json“ (je ≤ 50 Fundstellen) und „Entitaeten_NN.json“ (je ≤ 150 Einträge) samt Anleitung."""
    case = p.get_case(case_id)
    ref = {"reference": case["reference"]}
    leads = eligible_leads(p.list_findings(case_id))
    ents = eligible_entities(p.list_entities(case_id))
    buf = io.BytesIO()
    names: list[str] = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for n, start in enumerate(range(0, len(leads), LEADS_PER_FILE), 1):
            name = f"Hinweise_{n:02d}.json"
            z.writestr(name, json.dumps({"case": ref, "export_id": export_id, "findings": leads[start:start + LEADS_PER_FILE], "entities": []},
                                        ensure_ascii=False, indent=1))
            names.append(name)
        for n, start in enumerate(range(0, len(ents), ENTITIES_PER_FILE), 1):
            name = f"Entitaeten_{n:02d}.json"
            z.writestr(name, json.dumps({"case": ref, "export_id": export_id, "findings": [], "entities": ents[start:start + ENTITIES_PER_FILE]},
                                        ensure_ascii=False, indent=1))
            names.append(name)
        z.writestr("LIESMICH.txt", "\n".join([
            "Übergabe PersonOSINT → EagleEye (Build 493/494 und neuer)", "",
            f"Fall {case['reference']} · Export-ID {export_id} · erstellt {datetime.now().isoformat(timespec='seconds')}", "",
            f"Inhalt: {len(leads)} öffentliche HTTPS-Fundstellen und {len(ents)} Einträge – in EagleEye bleibt alles UNGEPRÜFT.",
            "Nicht enthalten (bewusst): Kennungen wie E-Mail/Telefon, Notizen, Fotos, Aussagen, Bewertungen, Belege.", "",
            "So übernehmen Sie in EagleEye:",
            "1. In EagleEye den passenden Fall öffnen.",
            "2. „PersonOSINT-Quellen importieren“ (/workbench/personosint493): die Dateien Hinweise_01.json, Hinweise_02.json … nacheinander hochladen.",
            f"   EagleEye nimmt je Datei höchstens {LEADS_PER_FILE} Fundstellen und je Fall höchstens {CASE_LEAD_LIMIT} Recherchehinweise an.",
            "3. „PersonOSINT-Entitäten prüfen“ (/workbench/personosint494): die Dateien Entitaeten_01.json … hochladen und jeden Kandidaten prüfen.",
            "4. Fundstellen, die als Beleg dienen sollen, in EagleEye über „Original-Webbeleg sichern (WARC)“ neu sichern.", "",
            "Dateien in diesem Paket: " + (", ".join(names) if names else "keine – der Fall enthält weder geeignete Fundstellen noch Einträge."), ""]))
    return buf.getvalue()
