"""Vorsortierung offener Treffer – erst nach festen Regeln, auf Wunsch zusätzlich mit lokaler KI.

Ziel: Nach einer Tiefenrecherche mit vielen Kandidaten schneller zu den wichtigen kommen. Die Vorsortierung
**entscheidet nichts**: Sie markiert nur (Dublette, vermutlich andere Person, stark, prüfen) und begründet es.
Bestätigen oder verwerfen tun Sie.

Regeln (immer, ohne KI):
* **Dubletten**: gleiche Adresse (ohne www, Schlusszeichen, Kampagnen-Parameter) oder gleiches Konto auf derselben
  Plattform → die stärkste Fundstelle bleibt, die anderen werden als Dublette markiert.
* **Vermutlich andere Person**: Geburtsjahr weicht um mehr als ein Jahr ab · Name passt nach dem gemeinsamen Namensabgleich nicht ·
  sehr schwache Übereinstimmung (Score < 15) · anderer Ort bei gleichzeitig schwacher Übereinstimmung.
* **Stark**: Score ≥ 70 ohne Gegenanzeichen.

Lokale KI (Ollama, nur auf diesem Rechner, nie über Proxy oder Internet): schätzt die übrigen Treffer ein
(passt · unklar · andere Person) und begründet jede Einschätzung in einem Satz.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from .db import now_iso
from .namematch import THRESHOLD, compare_names

VERDICTS = {"stark": "starker Treffer", "pruefen": "prüfen", "doppelt": "Dublette", "andere_person": "vermutlich andere Person"}
AI_VERDICTS = {"passt": "KI: passt", "unklar": "KI: unklar", "andere_person": "KI: andere Person"}
TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "ref", "ref_src", "igshid", "si"}
AI_BATCH = 20


def _url_key(url: str) -> str:
    parts = urlsplit(str(url or "").strip())
    if not parts.hostname:
        return ""
    host = parts.hostname.casefold().removeprefix("www.").removeprefix("m.")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if k.casefold() not in TRACKING))
    return f"{host}{parts.path.rstrip('/').casefold()}" + (f"?{query}" if query else "")


def _years(text: str) -> set[int]:
    return {int(y) for y in re.findall(r"\b(19\d\d|20[0-2]\d)\b", str(text or ""))}


def _profile(p, case_id: int, entity_id: int) -> dict[str, Any]:
    ent = p.get_entity(case_id, entity_id)
    data = ent.get("data") or {}
    names = [i["value"] for i in ent["identifiers"] if i["kind"] in ("name", "alias")] or [ent["label"]]
    locs = [i["value"] for i in ent["identifiers"] if i["kind"] == "location"]
    birth = _years(str(data.get("geburtsdatum") or data.get("birth_date") or ""))
    return {"label": ent["label"], "names": list(dict.fromkeys([ent["label"]] + names)), "locations": locs,
            "loc_tokens": {t for loc in locs for t in re.findall(r"\w{3,}", loc.casefold())}, "birth_years": birth,
            "summary": {"name": ent["label"], "weitere Namen": names[1:6], "orte": locs[:5], "geburtsjahr": sorted(birth)[:1],
                        "kennungen": [f"{i['kind']}: {i['value']}" for i in ent["identifiers"] if i["kind"] in ("username", "email", "employer")][:8]}}


def rule_triage(p, case_id: int, entity_id: int) -> dict[str, Any]:
    prof = _profile(p, case_id, entity_id)
    rows = p.db.all("SELECT id, source, title, url, snippet, score, data FROM findings WHERE case_id = ? AND entity_id = ? AND status = 'neu' "
                    "ORDER BY score DESC, id", (case_id, entity_id))
    births: dict[int, set[int]] = {}
    for fa in p.db.all("SELECT finding_id, object_label FROM facts WHERE case_id = ? AND predicate = 'geburtsdatum' AND finding_id IS NOT NULL", (case_id,)):
        births.setdefault(fa["finding_id"], set()).update(_years(fa["object_label"]))
    seen: dict[str, int] = {}
    counts = {k: 0 for k in VERDICTS}
    for f in rows:
        data = dict(f["data"] or {})
        why: list[str] = []
        verdict = ""
        keys = [k for k in (_url_key(f["url"]),) if k]
        platform, user = data.get("plattform"), data.get("benutzername")
        if platform and user:
            keys.append(f"konto:{str(platform).casefold()}:{str(user).casefold()}")
        dup = next((seen[k] for k in keys if k in seen), None)
        if dup:
            verdict, why = "doppelt", [f"gleiche Fundstelle wie Treffer #{dup}"]
        else:
            for k in keys:
                seen[k] = f["id"]
            years = births.get(f["id"], set()) | _years(data.get("geburtsdatum") or "")
            if prof["birth_years"] and years and min(abs(a - b) for a in years for b in prof["birth_years"]) > 1:
                why.append(f"Geburtsjahr {sorted(years)[0]} passt nicht zu {sorted(prof['birth_years'])[0]}")
            names = [n for n in (data.get("_names") or []) if n]
            if names and max(compare_names(n, pn)[0] for n in names for pn in prof["names"]) < THRESHOLD:
                why.append(f"Name „{names[0]}“ passt nicht")
            locs = [x for x in (data.get("_locations") or []) if x]
            other_place = bool(prof["loc_tokens"] and locs and not any(set(re.findall(r"\w{3,}", x.casefold())) & prof["loc_tokens"] for x in locs))
            if f["score"] < 15:
                why.append("sehr schwache Übereinstimmung")
            if other_place and f["score"] < 40:
                why.append(f"anderer Ort ({locs[0]}) bei schwacher Übereinstimmung")
            if why:
                verdict = "andere_person"
            elif f["score"] >= 70:
                verdict, why = "stark", ["hohe Übereinstimmung ohne Gegenanzeichen"] + (["Ort passt"] if locs and not other_place else [])
            else:
                verdict = "pruefen"
                if other_place:
                    why.append(f"anderer Ort ({locs[0]}) – genauer prüfen")
        old = data.get("_triage") or {}
        data["_triage"] = {**({"ki": old["ki"]} if old.get("ki") else {}), "verdict": verdict, "label": VERDICTS[verdict], "why": why[:4], "at": now_iso()}
        p.db.update("findings", f["id"], {"data": data})
        counts[verdict] += 1
    p.log(case_id, "Treffer vorsortiert (Regeln)", ", ".join(f"{VERDICTS[k]}: {v}" for k, v in counts.items() if v) or "keine offenen Treffer")
    return {"checked": len(rows), "counts": counts}


def _prompt(profile: dict[str, Any], items: list[dict[str, Any]]) -> str:
    return ("Du hilfst einer Detektei, Suchtreffer zu einer Person vorzusortieren. Du entscheidest nichts endgültig.\n"
            "Gesuchte Person (aus der Fallakte):\n" + json.dumps(profile, ensure_ascii=False) + "\n\n"
            "Treffer (aus öffentlichen Quellen, ungeprüft):\n" + json.dumps(items, ensure_ascii=False) + "\n\n"
            "Antworte NUR mit einem JSON-Array. Für jeden Treffer ein Objekt: {\"id\": <id>, \"einschaetzung\": \"passt\" | \"unklar\" | "
            "\"andere_person\", \"begruendung\": \"<ein kurzer deutscher Satz mit dem entscheidenden Anhaltspunkt>\"}.\n"
            "Regeln: Gleicher Name allein heißt nicht gleiche Person. Bei Zweifel \"unklar\". Erfinde nichts, nutze nur die Angaben oben.")


def _parse(text: str, allowed: set[int]) -> list[dict[str, Any]]:
    match = re.search(r"\[.*\]", text or "", re.S)
    if not match:
        return []
    try:
        raw = json.loads(match.group(0))
    except ValueError:
        return []
    out = []
    for item in raw if isinstance(raw, list) else []:
        try:
            fid = int(item.get("id"))
        except (TypeError, ValueError, AttributeError):
            continue
        verdict = str(item.get("einschaetzung") or "").strip().casefold().replace(" ", "_")
        if fid in allowed and verdict in AI_VERDICTS:
            out.append({"id": fid, "verdict": verdict, "reason": " ".join(str(item.get("begruendung") or "").split())[:300]})
    return out


def ai_triage(p, case_id: int, entity_id: int, limit: int = 60) -> dict[str, Any]:
    from . import ai

    cfg = ai.settings(p)
    if not cfg["enabled"]:
        raise ai.AiError("Der lokale KI-Assistent ist nicht eingerichtet (Verwaltung → KI-Assistent). Die Regel-Vorsortierung ist trotzdem gelaufen.")
    url = ai.validate_url(cfg["url"])
    prof = _profile(p, case_id, entity_id)
    rows = p.db.all("SELECT id, source, title, url, snippet, score, data FROM findings WHERE case_id = ? AND entity_id = ? AND status = 'neu' "
                    "ORDER BY score DESC, id", (case_id, entity_id))
    rows = [r for r in rows if ((r["data"] or {}).get("_triage") or {}).get("verdict") in (None, "stark", "pruefen")][:max(1, min(limit, 200))]
    done = 0
    for i in range(0, len(rows), AI_BATCH):
        batch = rows[i:i + AI_BATCH]
        items = [{"id": r["id"], "quelle": r["source"], "titel": r["title"][:160], "auszug": (r["snippet"] or "")[:300],
                  "host": urlsplit(r["url"] or "").hostname or "", "namen": ((r["data"] or {}).get("_names") or [])[:4],
                  "orte": ((r["data"] or {}).get("_locations") or [])[:3], "score": r["score"]} for r in batch]
        res = ai._call(url, "/api/generate", {"model": cfg["model"], "prompt": _prompt(prof["summary"], items), "stream": False,  # noqa: SLF001
                                             "format": "json", "options": {"temperature": 0.0}})
        for v in _parse(str(res.get("response") or ""), {r["id"] for r in batch}):
            row = next(r for r in batch if r["id"] == v["id"])
            data = dict(row["data"] or {})
            tri = dict(data.get("_triage") or {})
            tri["ki"] = {"verdict": v["verdict"], "label": AI_VERDICTS[v["verdict"]], "reason": v["reason"], "model": cfg["model"], "at": now_iso()}
            data["_triage"] = tri
            p.db.update("findings", row["id"], {"data": data})
            done += 1
    p.log(case_id, "Treffer vorsortiert (lokale KI)", f"Modell {cfg['model']}: {done} von {len(rows)} Treffern eingeschätzt")
    return {"ai_checked": done, "ai_candidates": len(rows), "model": cfg["model"]}


def triage(p, case_id: int, entity_id: int, use_ai: bool = False) -> dict[str, Any]:
    result = rule_triage(p, case_id, entity_id)
    if use_ai:
        try:
            result.update(ai_triage(p, case_id, entity_id))
        except Exception as exc:  # noqa: BLE001 - KI-Fehler sind kein Abbruch: die Regeln haben schon gearbeitet
            result["ai_error"] = str(exc)
    return result


__all__ = ["triage", "rule_triage", "ai_triage", "VERDICTS", "AI_VERDICTS"]
