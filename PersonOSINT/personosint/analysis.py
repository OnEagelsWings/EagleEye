"""Schritt 2 – Auswertung: Kandidatengruppen (Namensvettern), Admiralty-Bewertung, Bestätigung durch
mehrere Quellen, Widersprüche und Red-Flag-Regeln.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from typing import Any

from .facts import PREDICATES, norm_value
from .matching import fold, name_similarity, normalize

# --------------------------------------------------------------------------- Admiralty-Code

RELIABILITY = {"A": "vollkommen zuverlässig", "B": "in der Regel zuverlässig", "C": "ziemlich zuverlässig",
               "D": "in der Regel nicht zuverlässig", "E": "unzuverlässig", "F": "nicht beurteilbar"}
CREDIBILITY = {1: "durch andere Quellen bestätigt", 2: "wahrscheinlich wahr", 3: "möglicherweise wahr",
               4: "zweifelhaft", 5: "unwahrscheinlich", 6: "nicht beurteilbar"}

STOP = {"street", "strasse", "straße", "road", "london", "limited", "house", "floor", "suite", "unit", "the", "and", "und"}


def _year_month(value: str) -> str:
    m = re.match(r"(\d{4})(?:-(\d{2}))?", value or "")
    return (m.group(1) + ("-" + m.group(2) if m.group(2) else "")) if m else ""


def _birth_compatible(a: str, b: str) -> bool:
    a, b = _year_month(a), _year_month(b)
    if not a or not b:
        return True
    return a.startswith(b) or b.startswith(a)


# --------------------------------------------------------------------------- Kandidatengruppen

def _features(f: dict[str, Any]) -> dict[str, Any]:
    data = f.get("data") or {}
    birth = ""
    orgs, locs = set(), set()
    for fa in f.get("facts") or []:
        if fa["predicate"] == "geburtsdatum" and fa["subject_label"] and not birth:
            birth = _year_month(fa["object_label"])
        if fa["predicate"] in {"funktion_bei", "arbeitet_bei", "offshore_funktion", "mitglied_von"}:
            orgs.add(norm_value("funktion_bei", fa["object_label"]))
        if fa["predicate"] == "adresse":
            locs |= _loc_tokens(fa["object_label"])
    for key in ("organisation", "institutionen"):
        vals = data.get(key)
        for v in (vals if isinstance(vals, list) else [vals] if vals else []):
            orgs.add(norm_value("funktion_bei", str(v).lstrip("@")))
    for loc in data.get("_locations") or []:
        locs |= _loc_tokens(loc)
    users = {str(data["benutzername"]).casefold().split("@")[0]} if data.get("benutzername") else set()
    if not birth and data.get("geburtsdatum"):
        birth = _year_month(str(data["geburtsdatum"]))
    return {"birth": birth, "orgs": {o for o in orgs if o}, "locs": locs, "users": users,
            "names": [n for n in (data.get("_names") or []) if n]}


def _loc_tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", fold(text or "")) if len(t) >= 4 and not t.isdigit() and t not in STOP}


def candidate_groups(findings: list[dict[str, Any]], subject: dict[str, Any]) -> list[dict[str, Any]]:
    feats = {f["id"]: _features(f) for f in findings}
    parent = {f["id"]: f["id"] for f in findings}
    births: dict[int, set[str]] = {f["id"]: ({feats[f["id"]]["birth"]} if feats[f["id"]]["birth"] else set()) for f in findings}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if any(not _birth_compatible(x, y) for x in births[ra] for y in births[rb]):
            return  # unterschiedliche Geburtsdaten = verschiedene Personen
        parent[rb] = ra
        births[ra] |= births[rb]

    ids = [f["id"] for f in findings]
    for i, a in enumerate(ids):
        fa = feats[a]
        for b in ids[i + 1:]:
            fb = feats[b]
            if fa["birth"] and fb["birth"] and not _birth_compatible(fa["birth"], fb["birth"]):
                continue
            # beide mit (verträglichem) Geburtsdatum, gemeinsame Organisation oder gemeinsamer Benutzername
            strong = bool(fa["birth"] and fb["birth"]) or bool(fa["orgs"] & fb["orgs"]) or bool(fa["users"] & fb["users"])
            weak = fa["locs"] & fb["locs"] and any(name_similarity(x, y) >= 0.9 for x in fa["names"] for y in fb["names"])
            if strong or weak:
                union(a, b)

    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for f in findings:
        groups[find(f["id"])].append(f)

    sdata = subject.get("data") or {}
    s_birth = _year_month(str(sdata.get("geburtsdatum") or ""))
    idents = subject.get("identifiers") or []
    s_locs = set().union(*[_loc_tokens(i["value"]) for i in idents if i["kind"] == "location"] or [set()]) | _loc_tokens(str(sdata.get("wohnort") or ""))
    s_orgs = {norm_value("funktion_bei", i["value"]) for i in idents if i["kind"] == "employer"}
    s_users = {i["normalized"] for i in idents if i["kind"] == "username"}

    out, loose = [], []
    for members in groups.values():
        f_all = [feats[m["id"]] for m in members]
        g_birth = sorted({x["birth"] for x in f_all if x["birth"]})
        g_orgs = Counter(o for x in f_all for o in x["orgs"])
        g_locs = Counter(lo for x in f_all for lo in x["locs"])
        g_users = sorted({u for x in f_all for u in x["users"]})
        has_features = bool(g_birth or g_orgs or len(members) > 1)  # Einzeltreffer nur mit Benutzername: einzeln prüfen
        if not has_features:
            loose.extend(members)
            continue
        score = max(m["score"] for m in members)
        reasons = [f"{len(members)} Treffer aus {len({m['source'] for m in members})} Quelle(n) gehören zusammen"]
        if s_birth and g_birth:
            if any(_birth_compatible(s_birth, b) for b in g_birth):
                score += 25
                reasons.append(f"Geburtsdatum passt zum Profil ({', '.join(g_birth)})")
            else:
                score -= 40
                reasons.append(f"Geburtsdatum passt NICHT zum Profil ({', '.join(g_birth)} statt {s_birth})")
        if s_orgs & set(g_orgs):
            score += 15
            reasons.append("Organisation aus dem Profil kommt vor")
        if s_locs & set(g_locs):
            score += 10
            reasons.append("Ort aus dem Profil kommt vor")
        if s_users & set(g_users):
            score += 15
            reasons.append("Benutzername aus dem Profil kommt vor")
        names = Counter(n for x in f_all for n in x["names"]).most_common(3)
        out.append({"finding_ids": [m["id"] for m in members], "count": len(members), "score": max(0, min(100, int(score))),
                    "reasons": reasons, "names": [n for n, _ in names], "births": g_birth,
                    "orgs": [o.title() for o, _ in g_orgs.most_common(6)], "locations": [lo.title() for lo, _ in g_locs.most_common(4)],
                    "usernames": g_users, "sources": sorted({m["source"] for m in members}),
                    "statuses": dict(Counter(m["status"] for m in members)),
                    "members": [{"id": m["id"], "title": m["title"], "source": m["source"], "score": m["score"], "status": m["status"], "url": m["url"]} for m in members]})
    out.sort(key=lambda g: (-g["score"], -g["count"]))
    for i, g in enumerate(out):
        g["label"] = f"Kandidat {chr(65 + i) if i < 26 else i + 1}"
        g["kind"] = "kandidat"
    if loose:
        out.append({"label": "Einzeltreffer ohne Unterscheidungsmerkmale", "kind": "lose", "finding_ids": [m["id"] for m in loose], "count": len(loose),
                    "score": max(m["score"] for m in loose), "reasons": ["Kein Geburtsdatum, keine Organisation, kein Benutzername – einzeln prüfen"],
                    "names": [], "births": [], "orgs": [], "locations": [], "usernames": [], "sources": sorted({m["source"] for m in loose}),
                    "statuses": dict(Counter(m["status"] for m in loose)),
                    "members": [{"id": m["id"], "title": m["title"], "source": m["source"], "score": m["score"], "status": m["status"], "url": m["url"]} for m in loose]})
    return out


# --------------------------------------------------------------------------- Bewertung, Bestätigung, Widersprüche

def _subject_key(fa: dict[str, Any]) -> str:
    return f"e{fa['subject_entity_id']}" if fa.get("subject_entity_id") else "n" + normalize("name", fa["subject_label"])


def assess(facts: list[dict[str, Any]], profiles: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Bewertet alle Aussagen eines Falls. ``profiles``: Entity-ID -> Profil (für Abgleich mit Analystenangaben)."""
    active = [f for f in facts if f["status"] != "verworfen"]
    by_norm: dict[str, list] = defaultdict(list)
    for f in active:
        by_norm[f["norm_key"]].append(f)

    # Widersprüche bei funktionalen Prädikaten (nur ein gültiger Wert möglich)
    contradictions = []
    contradicted: set[int] = set()
    func = {k for k, v in PREDICATES.items() if v.get("functional")}
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for f in active:
        if f["predicate"] in func:
            groups[(_subject_key(f), f["predicate"])].append(f)
    for (skey, pred), items in groups.items():
        values: dict[str, list] = defaultdict(list)
        for f in items:
            val = _year_month(f["object_label"]) if pred in {"geburtsdatum", "domain_registriert_am"} else norm_value(pred, f["object_label"])
            values[val].append(f)
        profile_val = ""
        if pred == "geburtsdatum" and items[0].get("subject_entity_id") in profiles:
            profile_val = str((profiles[items[0]["subject_entity_id"]].get("data") or {}).get("geburtsdatum") or "")
        keys = list(values)
        conflicting = any(not _birth_compatible(a, b) for a in keys for b in keys) if pred == "geburtsdatum" else len(keys) > 1
        if profile_val and pred == "geburtsdatum":
            conflicting = conflicting or any(not _birth_compatible(profile_val, k) for k in keys)
        if conflicting:
            contradictions.append({"subject": items[0]["subject_label"], "predicate": pred, "predicate_label": PREDICATES[pred]["label"],
                                   "profile_value": profile_val,
                                   "values": [{"value": vs[0]["object_label"], "fact_ids": [x["id"] for x in vs],
                                               "sources": sorted({x["source_label"] for x in vs}),
                                               "confirmed": any(x["status"] == "bestätigt" for x in vs),
                                               "matches_profile": bool(profile_val) and _birth_compatible(profile_val, k)} for k, vs in values.items()]})
            contradicted |= {x["id"] for x in items}

    out_facts = []
    for f in facts:
        peers = by_norm.get(f["norm_key"], [])
        sources = sorted({p["source_label"] for p in peers}) if f["status"] != "verworfen" else [f["source_label"]]
        n_src = len({p["source_key"] for p in peers}) if f["status"] != "verworfen" else 1
        rel = f["reliability"] or "F"
        if f["status"] == "verworfen":
            cred = 5
        elif f["id"] in contradicted and not (f["status"] == "bestätigt" and n_src >= 2):
            cred = 4
        elif n_src >= 2 and f["status"] == "bestätigt":
            cred = 1
        elif n_src >= 2 or (f["status"] == "bestätigt" and rel in "AB"):
            cred = 2
        elif f["status"] == "bestätigt" or rel in "AB":
            cred = 3
        else:
            cred = 6
        final = f["credibility"] or cred
        out_facts.append({**f, "credibility_auto": cred, "credibility_final": final, "code": f"{rel}{final}",
                          "code_text": f"{RELIABILITY.get(rel, '')} · {CREDIBILITY[final]}", "sources": sources, "corroboration": n_src,
                          "contradiction": f["id"] in contradicted})
    stats = {"facts": len(facts), "confirmed": sum(1 for f in facts if f["status"] == "bestätigt"),
             "rejected": sum(1 for f in facts if f["status"] == "verworfen"),
             "corroborated": sum(1 for f in out_facts if f["corroboration"] >= 2 and f["status"] != "verworfen"),
             "contradictions": len(contradictions)}
    return {"facts": out_facts, "contradictions": contradictions, "stats": stats}


# --------------------------------------------------------------------------- Red Flags

INSOLVENT = re.compile(r"dissolv|liquidat|insolv|struck|inactive|aufgel|gelöscht|geloescht|defunct|closed", re.I)


def _days(a: str, b: str) -> int | None:
    try:
        return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days
    except ValueError:
        return None


def _r_sanktion(facts):
    hits = [f for f in facts if f["predicate"] == "sanktioniert"]
    return [(f"{f['subject_label']}: {f['object_label']}", [f]) for f in hits]


def _r_pep(facts):
    return [(f"{f['subject_label']}: {f['object_label']}", [f]) for f in facts if f["predicate"] == "pep"]


def _r_offshore(facts):
    by = defaultdict(list)
    for f in facts:
        if f["predicate"] in {"offshore_funktion", "offshore_vermittler"}:
            by[f["subject_label"]].append(f)
    out = []
    for subj, fs in by.items():
        leaks = sorted({(f["data"] or {}).get("leak") for f in fs if (f["data"] or {}).get("leak")})
        out.append((f"{subj}: {len(fs)} Verknüpfung(en) zu Offshore-Gesellschaften" + (f" ({', '.join(leaks)})" if leaks else "") +
                    " – Nennung ist kein Beleg für Fehlverhalten", fs))
    return out


def _roles(facts):
    by = defaultdict(list)
    for f in facts:
        if f["predicate"] == "funktion_bei":
            by[f["subject_label"]].append(f)
    return by


def _r_viele_mandate(facts):
    out = []
    for subj, fs in _roles(facts).items():
        firms = {norm_value("funktion_bei", f["object_label"]) for f in fs}
        if len(firms) >= 10:
            out.append((f"{subj}: {len(firms)} verschiedene Firmenfunktionen", fs))
    return out


def _r_kurze_mandate(facts):
    out = []
    for subj, fs in _roles(facts).items():
        short = [f for f in fs if f["valid_from"] and f["valid_to"] and (_days(f["valid_from"], f["valid_to"]) or 999) < 183]
        if len(short) >= 2:
            out.append((f"{subj}: {len(short)} Funktionen kürzer als 6 Monate", short))
    return out


def _r_wechsel(facts):
    out = []
    for subj, fs in _roles(facts).items():
        ends = sorted([f for f in fs if f["valid_to"]], key=lambda f: f["valid_to"])
        for i in range(len(ends) - 2):
            d = _days(ends[i]["valid_to"], ends[i + 2]["valid_to"])
            if d is not None and d <= 730:
                out.append((f"{subj}: mindestens 3 beendete Funktionen innerhalb von 24 Monaten", ends[i:i + 3]))
                break
    return out


def _r_aufgeloest(facts):
    out = []
    for subj, fs in _roles(facts).items():
        bad = [f for f in fs if INSOLVENT.search(str((f["data"] or {}).get("firmenstatus") or ""))]
        if len(bad) >= 2:
            out.append((f"{subj}: Funktionen bei {len(bad)} aufgelösten/insolventen Firmen", bad))
    return out


def _r_sammeladresse(facts):
    by = defaultdict(list)
    for f in facts:
        if f["predicate"] in {"firmensitz", "adresse"} and f["object_label"]:
            by[norm_value("adresse", f["object_label"])].append(f)
    out = []
    for addr, fs in by.items():
        subjects = {f["subject_label"] for f in fs}
        if len(subjects) >= 3:
            out.append((f"{len(subjects)} Personen/Firmen mit derselben Adresse „{fs[0]['object_label']}“ (Sammel-/Briefkastenadresse?)", fs))
    return out


def _r_eigene_liste(facts):
    return [(f"{f['subject_label']}: {f['object_label']}", [f]) for f in facts if f["predicate"] == "gelistet_in" and "Eigene Referenzliste" in f["object_label"]]


RULES: dict[str, dict[str, Any]] = {
    "sanktion": {"label": "Treffer auf Sanktionsliste", "severity": "hoch", "fn": _r_sanktion},
    "pep": {"label": "Politisch exponierte Person (PEP)", "severity": "mittel", "fn": _r_pep},
    "offshore": {"label": "Verbindung zu Offshore-Gesellschaften", "severity": "mittel", "fn": _r_offshore},
    "viele_mandate": {"label": "Ungewöhnlich viele Firmenfunktionen (≥ 10)", "severity": "mittel", "fn": _r_viele_mandate},
    "kurze_mandate": {"label": "Mehrere sehr kurze Funktionen (< 6 Monate)", "severity": "niedrig", "fn": _r_kurze_mandate},
    "haeufige_wechsel": {"label": "Häufige Wechsel (3 Funktionen in 24 Monaten beendet)", "severity": "niedrig", "fn": _r_wechsel},
    "aufgeloeste_firmen": {"label": "Funktionen bei mehreren aufgelösten/insolventen Firmen", "severity": "mittel", "fn": _r_aufgeloest},
    "sammeladresse": {"label": "Sammel- oder Briefkastenadresse", "severity": "mittel", "fn": _r_sammeladresse},
    "eigene_liste": {"label": "Treffer auf eigener Referenzliste", "severity": "mittel", "fn": _r_eigene_liste},
    "identitaet_unsicher": {"label": "Widersprüchliche Identitätsangaben", "severity": "mittel", "fn": None},
}
SEVERITY_ORDER = {"hoch": 0, "mittel": 1, "niedrig": 2}


def rule_config(raw: str) -> dict[str, dict[str, Any]]:
    cfg = json.loads(raw) if raw else {}
    return {k: {"label": v["label"], "enabled": cfg.get(k, {}).get("enabled", True), "severity": cfg.get(k, {}).get("severity", v["severity"]),
                "default_severity": v["severity"]} for k, v in RULES.items()}


def red_flags(assessed: dict[str, Any], config: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    facts = [f for f in assessed["facts"] if f["status"] != "verworfen"]
    out = []
    for key, rule in RULES.items():
        cfg = config.get(key, {})
        if not cfg.get("enabled", True):
            continue
        if key == "identitaet_unsicher":
            hits = [(f"{c['subject']}: {c['predicate_label']} – " + " / ".join(v["value"] for v in c["values"]), [])
                    for c in assessed["contradictions"] if c["predicate"] in {"geburtsdatum", "geburtsort"}]
        else:
            hits = rule["fn"](facts)
        for text, fs in hits:
            out.append({"rule": key, "label": rule["label"], "severity": cfg.get("severity", rule["severity"]), "text": text,
                        "fact_ids": [f["id"] for f in fs], "confirmed": bool(fs) and all(f["status"] == "bestätigt" for f in fs),
                        "sources": sorted({f["source_label"] for f in fs})})
    out.sort(key=lambda r: (SEVERITY_ORDER.get(r["severity"], 9), not r["confirmed"]))
    return out


__all__ = ["assess", "candidate_groups", "red_flags", "rule_config", "RULES", "RELIABILITY", "CREDIBILITY"]
