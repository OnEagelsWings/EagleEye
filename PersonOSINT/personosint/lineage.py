"""Quellenunabhängigkeit: Belege mit (nahezu) gleichem Text bilden eine **Quellfamilie**.

Zwanzig Übernahmen einer Agenturmeldung sind ein Ursprung, nicht zwanzig Bestätigungen. Übernommen aus
Build 492 (Tool-Auswahl A4). Abweichung: statt MinHash/LSH (``datasketch``, zieht numpy/scipy) wird die
Ähnlichkeit **exakt** berechnet (Jaccard über 5-Wort-Folgen). Für die Größe eines Falls (bis einige hundert
Belege) ist das schnell genug, liefert reproduzierbare Werte und braucht keine zusätzliche Bibliothek.

Das Ergebnis ist ein Analysehinweis. Es entscheidet nichts über Wahrheit oder den tatsächlichen Urheber.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

SHINGLE = 5
MIN_WORDS = 30
MAX_DOCS = 600
LEVELS = {"streng": 0.7, "normal": 0.5, "locker": 0.3}
_WORD = re.compile(r"\w+", re.UNICODE)


def shingles(text: str, size: int = SHINGLE) -> set[str]:
    words = [w.casefold() for w in _WORD.findall(text or "")]
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


def source_families(documents: list[dict[str, Any]], level: str = "normal") -> dict[str, Any]:
    """documents: [{id, title, url, first_seen, text}] eines Falls → Familien nahezu gleicher Texte."""
    if level not in LEVELS:
        raise ValueError("Unbekannte Stufe.")
    threshold = LEVELS[level]
    usable, skipped = [], []
    for doc in documents[:MAX_DOCS]:
        if len(_WORD.findall(doc.get("text") or "")) < MIN_WORDS:
            skipped.append({"id": doc["id"], "title": doc.get("title", "")})
            continue
        usable.append((doc, shingles(doc["text"])))
    parent = {doc["id"]: doc["id"] for doc, _ in usable}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    similarities: dict[tuple, float] = {}
    for i, (da, sa) in enumerate(usable):
        for db, sb in usable[i + 1:]:
            small, large = sorted((len(sa), len(sb)))
            if small / large < threshold:  # Jaccard kann den Schwellwert rechnerisch nicht mehr erreichen
                continue
            score = jaccard(sa, sb)
            if score >= threshold:
                similarities[(da["id"], db["id"])] = round(score, 3)
                a, b = find(da["id"]), find(db["id"])
                if a != b:
                    parent[b] = a
    groups: dict[Any, list[dict[str, Any]]] = {}
    for doc, _ in usable:
        groups.setdefault(find(doc["id"]), []).append(doc)
    families = []
    for members in groups.values():
        members = sorted(members, key=lambda d: (d.get("first_seen") or "9999", d["id"]))
        ids = {m["id"] for m in members}
        hosts = sorted({(urlsplit(m.get("url") or "").hostname or "importiertes Dokument") for m in members})
        scores = [s for (a, b), s in similarities.items() if a in ids and b in ids]
        families.append({"members": [{k: m.get(k) for k in ("id", "title", "url", "first_seen", "kind")} for m in members],
                         "size": len(members), "hosts": hosts, "earliest": members[0]["id"],
                         "max_similarity": max(scores) if scores else None, "min_similarity": min(scores) if scores else None})
    families.sort(key=lambda f: (-f["size"], f["members"][0].get("first_seen") or ""))
    for n, fam in enumerate(families, 1):
        fam["family"] = n
    return {"level": level, "threshold": threshold, "documents": len(documents), "compared": len(usable), "skipped": skipped,
            "families": families, "independent_origins": len(families),
            "duplicate_documents": sum(f["size"] - 1 for f in families), "truth_determined": False}


def origin_map(result: dict[str, Any]) -> dict[Any, int]:
    """Beleg-ID → Nummer der Quellfamilie (nur Familien mit mehr als einem Mitglied sind für die Bewertung relevant)."""
    return {m["id"]: fam["family"] for fam in result["families"] for m in fam["members"]}
