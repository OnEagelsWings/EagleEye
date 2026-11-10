"""Korrelationsregeln: deklarative Regeln finden Überschneidungen zwischen Aussagen – als **Prüfhinweise**.

Übernommenes Muster aus der SpiderFoot-Analyse (dort 37 YAML-Regeln, die nach dem Sammeln über die Datenbank
laufen): Regeln sind von den Quellen entkoppelt und bestehen aus *Sammeln → Gruppieren → Schwellwert → Überschrift*.
Anders als bei SpiderFoot erzeugt eine Regel hier nie eine Bewertung der Person, sondern nur einen Hinweis,
dem ein Mensch nachgeht. Eigene Regeln legt die Administration als JSON an (keine Programmierung, kein Code).

Aufbau einer Regel::

    {"key": "gemeinsame_adresse", "label": "…", "severity": "mittel",
     "predicates": ["adresse", "firmensitz"],     # welche Aussagen werden gesammelt
     "group_by": "object",                        # object = gleicher Wert · subject = gleiches Subjekt
     "count": "subjects",                         # was wird gezählt: subjects · values · sources · facts
     "min": 2, "max": 0,                          # Schwellwert (max 0 = keine Obergrenze)
     "only_confirmed": false,
     "headline": "{count} Einträge teilen die Adresse „{value}“: {members}"}
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from .facts import PREDICATES, norm_value
from .matching import normalize

SEVERITIES = ("hoch", "mittel", "niedrig")
BUILTIN: list[dict[str, Any]] = [
    {"key": "gemeinsame_adresse", "label": "Gemeinsame Adresse", "severity": "mittel", "predicates": ["adresse", "firmensitz"],
     "group_by": "object", "count": "subjects", "min": 2, "max": 0, "only_confirmed": False,
     "headline": "{count} Einträge teilen die Adresse „{value}“: {members}"},
    {"key": "gemeinsame_firma", "label": "Mehrere Personen bei derselben Firma", "severity": "mittel",
     "predicates": ["funktion_bei", "arbeitet_bei", "offshore_funktion"], "group_by": "object", "count": "subjects", "min": 2, "max": 0,
     "only_confirmed": False, "headline": "{count} Personen sind mit „{value}“ verbunden: {members}"},
    {"key": "gemeinsame_email", "label": "Gemeinsame E-Mail-Adresse", "severity": "hoch", "predicates": ["email"],
     "group_by": "object", "count": "subjects", "min": 2, "max": 0, "only_confirmed": False,
     "headline": "{count} Einträge nutzen dieselbe E-Mail-Adresse „{value}“: {members}"},
    {"key": "gemeinsamer_nameserver", "label": "Domains mit gemeinsamer Technik", "severity": "niedrig",
     "predicates": ["nameserver", "domain_registrar"], "group_by": "object", "count": "subjects", "min": 3, "max": 0, "only_confirmed": False,
     "headline": "{count} Domains nutzen „{value}“: {members}"},
    {"key": "gemeinsamer_inhaber", "label": "Mehrere Domains – ein Inhaber", "severity": "mittel", "predicates": ["domain_inhaber"],
     "group_by": "object", "count": "subjects", "min": 2, "max": 0, "only_confirmed": False,
     "headline": "„{value}“ ist Inhaber von {count} Domains: {members}"},
    {"key": "viele_aliasse", "label": "Auffällig viele Namensvarianten", "severity": "niedrig", "predicates": ["alias"],
     "group_by": "subject", "count": "values", "min": 4, "max": 0, "only_confirmed": False,
     "headline": "„{value}“ tritt unter {count} Namen auf: {members}"},
]
ALLOWED = {"key", "label", "severity", "predicates", "group_by", "count", "min", "max", "only_confirmed", "headline"}
PLACEHOLDERS = {"count", "value", "members", "label"}


class RuleError(ValueError):
    pass


def validate(rule: Any) -> dict[str, Any]:
    """Prüft eine Regel streng – unbekannte Felder, Prädikate oder Platzhalter werden abgelehnt."""
    if not isinstance(rule, dict):
        raise RuleError("Eine Regel muss ein JSON-Objekt sein.")
    unknown = set(rule) - ALLOWED
    if unknown:
        raise RuleError("Unbekannte Felder: " + ", ".join(sorted(unknown)))
    key = str(rule.get("key") or "").strip()
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,40}", key):
        raise RuleError("„key“: 3–41 Zeichen, Kleinbuchstaben, Ziffern und Unterstrich.")
    label = str(rule.get("label") or "").strip()
    if not 3 <= len(label) <= 80:
        raise RuleError("„label“: 3–80 Zeichen.")
    severity = rule.get("severity", "mittel")
    if severity not in SEVERITIES:
        raise RuleError("„severity“: hoch, mittel oder niedrig.")
    preds = rule.get("predicates")
    if not isinstance(preds, list) or not preds or any(pr not in PREDICATES for pr in preds):
        raise RuleError("„predicates“: Liste bekannter Aussagearten, z. B. " + ", ".join(list(PREDICATES)[:6]) + " …")
    group_by = rule.get("group_by", "object")
    if group_by not in {"object", "subject"}:
        raise RuleError("„group_by“: object oder subject.")
    count = rule.get("count", "subjects" if group_by == "object" else "values")
    if count not in {"subjects", "values", "sources", "facts"}:
        raise RuleError("„count“: subjects, values, sources oder facts.")
    try:
        lo, hi = int(rule.get("min", 2)), int(rule.get("max", 0) or 0)
    except (TypeError, ValueError):
        raise RuleError("„min“ und „max“ müssen Zahlen sein.") from None
    if not 1 <= lo <= 1000 or hi < 0 or (hi and hi < lo):
        raise RuleError("„min“ 1–1000; „max“ 0 (keine Grenze) oder ≥ min.")
    headline = str(rule.get("headline") or "{label}: {value} ({count})").strip()[:200]
    used = set(re.findall(r"\{(\w*)\}", headline))
    if used - PLACEHOLDERS or "{" in re.sub(r"\{\w*\}", "", headline) or "}" in re.sub(r"\{\w*\}", "", headline):
        raise RuleError("„headline“: erlaubte Platzhalter sind {count}, {value}, {members}, {label}.")
    return {"key": key, "label": label, "severity": severity, "predicates": list(dict.fromkeys(preds)), "group_by": group_by, "count": count,
            "min": lo, "max": hi, "only_confirmed": bool(rule.get("only_confirmed")), "headline": headline}


def load_rules(p) -> list[dict[str, Any]]:
    """Eingebaute und eigene Regeln mit Zustand (aktiv/aus)."""
    disabled = set(json.loads(p._setting("correlation_disabled", "[]") or "[]"))  # noqa: SLF001
    out = [{**r, "builtin": True, "enabled": r["key"] not in disabled} for r in BUILTIN]
    for row in p.db.all("SELECT * FROM correlation_rules ORDER BY id"):
        try:
            out.append({**validate(json.loads(row["definition"])), "builtin": False, "enabled": bool(row["enabled"]), "id": row["id"],
                        "created_by": row["created_by"]})
        except (ValueError, RuleError):
            continue
    return out


def _subject_key(f: dict[str, Any]) -> str:
    return f"e{f['subject_entity_id']}" if f.get("subject_entity_id") else "n" + normalize("name", f["subject_label"])


def evaluate(rules: list[dict[str, Any]], facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wendet aktive Regeln auf die Aussagen eines Falls an. Verworfene Aussagen zählen nie."""
    out = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        pool = [f for f in facts if f["predicate"] in rule["predicates"] and f["status"] != "verworfen"
                and (f["status"] == "bestätigt" or not rule["only_confirmed"])]
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for f in pool:
            key = norm_value(f["predicate"], f["object_label"]) if rule["group_by"] == "object" else _subject_key(f)
            if key:
                buckets[key].append(f)
        for items in buckets.values():
            subjects = {_subject_key(f): f["subject_label"] for f in items}
            values = {norm_value(f["predicate"], f["object_label"]): f["object_label"] for f in items}
            n = {"subjects": len(subjects), "values": len(values), "sources": len({f["source_key"] for f in items}), "facts": len(items)}[rule["count"]]
            if n < rule["min"] or (rule["max"] and n > rule["max"]):
                continue
            first = min(items, key=lambda f: f["id"])  # älteste Aussage bestimmt die angezeigte Schreibweise
            value = first["object_label"] if rule["group_by"] == "object" else first["subject_label"]
            members = sorted(subjects.values()) if rule["group_by"] == "object" else sorted(values.values())
            shown = ", ".join(members[:6]) + (f" und {len(members) - 6} weitere" if len(members) > 6 else "")
            out.append({"rule": rule["key"], "label": rule["label"], "severity": rule["severity"],
                        "headline": rule["headline"].format(count=n, value=value, members=shown, label=rule["label"]),
                        "count": n, "value": value, "members": members[:30], "fact_ids": [f["id"] for f in items][:60],
                        "sources": sorted({f["source_label"] for f in items}),
                        "confirmed": all(f["status"] == "bestätigt" for f in items), "candidate_only": True})
    order = {s: i for i, s in enumerate(SEVERITIES)}
    return sorted(out, key=lambda c: (order[c["severity"]], -c["count"], c["headline"]))


def save_rule(p, definition: Any) -> dict[str, Any]:
    from .db import now_iso
    from .service import Invalid, current_user

    try:
        rule = validate(definition)
    except RuleError as exc:
        raise Invalid(str(exc)) from exc
    if any(r["key"] == rule["key"] for r in BUILTIN):
        raise Invalid("Dieser Schlüssel gehört zu einer eingebauten Regel – bitte einen anderen wählen.")
    user = current_user.get()
    row = p.db.one("SELECT id FROM correlation_rules WHERE rule_key = ?", (rule["key"],))
    text = json.dumps(rule, ensure_ascii=False)
    if row:
        p.db.update("correlation_rules", row["id"], {"definition": text})
    else:
        p.db.insert("correlation_rules", {"rule_key": rule["key"], "definition": text, "enabled": 1,
                                          "created_by": user["display_name"] if user else "System", "created_at": now_iso()}, returning=False)
    p.log(None, "Korrelationsregel gespeichert", f"{rule['key']}: {rule['label']}")
    return rule


def set_enabled(p, key: str, enabled: bool) -> None:
    from .service import NotFound

    if any(r["key"] == key for r in BUILTIN):
        disabled = set(json.loads(p._setting("correlation_disabled", "[]") or "[]"))  # noqa: SLF001
        disabled.discard(key) if enabled else disabled.add(key)
        p._set_setting("correlation_disabled", json.dumps(sorted(disabled)))  # noqa: SLF001
    else:
        row = p.db.one("SELECT id FROM correlation_rules WHERE rule_key = ?", (key,))
        if not row:
            raise NotFound("Regel nicht gefunden.")
        p.db.update("correlation_rules", row["id"], {"enabled": 1 if enabled else 0})
    p.log(None, "Korrelationsregel " + ("aktiviert" if enabled else "deaktiviert"), key)


def delete_rule(p, key: str) -> None:
    from .service import Invalid, NotFound

    if any(r["key"] == key for r in BUILTIN):
        raise Invalid("Eingebaute Regeln lassen sich nur deaktivieren, nicht löschen.")
    row = p.db.one("SELECT id FROM correlation_rules WHERE rule_key = ?", (key,))
    if not row:
        raise NotFound("Regel nicht gefunden.")
    p.db.execute("DELETE FROM correlation_rules WHERE id = ?", (row["id"],))
    p.log(None, "Korrelationsregel gelöscht", key)
