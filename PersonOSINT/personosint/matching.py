"""Normalisierung von Identifikatoren und nachvollziehbare Treffer-Bewertung.

Jede Bewertung liefert neben dem Score (0–100) eine Liste lesbarer Gründe,
damit Analysten erkennen, *warum* ein Treffer vorgeschlagen wird.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

_TRANSLIT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "æ": "ae", "ø": "o", "å": "aa", "ł": "l"})
_TITLES = {"dr", "prof", "herr", "frau", "mr", "mrs", "ms", "von", "van", "der", "de", "la", "le", "jr", "sr"}


def fold(text: str) -> str:
    """Kleinbuchstaben, Umlaute transliteriert, Akzente entfernt."""
    text = (text or "").casefold().translate(_TRANSLIT)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def contains_term(text: str, term: str) -> bool:
    """Ganzwort-Suche: „maxmuster“ trifft nicht „maxmustermann111“."""
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text))


def name_tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", fold(name)) if t and t not in _TITLES]


def normalize(kind: str, value: str) -> str:
    value = (value or "").strip()
    if kind == "email":
        return value.casefold()
    if kind == "phone":
        digits = re.sub(r"[^\d+]", "", value)
        if digits.startswith("00"):
            digits = "+" + digits[2:]
        elif digits.startswith("0") and not digits.startswith("+"):
            digits = "+49" + digits[1:]  # Standard: Deutschland
        return digits
    if kind == "username":
        return value.lstrip("@").casefold()
    if kind in {"name", "alias"}:
        return " ".join(name_tokens(value))
    if kind == "url":
        return re.sub(r"^https?://(www\.)?", "", value.casefold()).rstrip("/")
    return fold(value)


def jaro_winkler(a: str, b: str) -> float:
    if a == b:
        return 1.0 if a else 0.0
    la, lb = len(a), len(b)
    if not la or not lb:
        return 0.0
    window = max(la, lb) // 2 - 1
    ma, mb = [False] * la, [False] * lb
    matches = 0
    for i, ca in enumerate(a):
        for j in range(max(0, i - window), min(lb, i + window + 1)):
            if not mb[j] and b[j] == ca:
                ma[i] = mb[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    k = transpositions = 0
    for i in range(la):
        if ma[i]:
            while not mb[k]:
                k += 1
            if a[i] != b[k]:
                transpositions += 1
            k += 1
    m = float(matches)
    jaro = (m / la + m / lb + (m - transpositions / 2) / m) / 3
    prefix = 0
    for ca, cb in zip(a[:4], b[:4]):
        if ca != cb:
            break
        prefix += 1
    return jaro + prefix * 0.1 * (1 - jaro)


def name_similarity(a: str, b: str) -> float:
    """Token-basierter Namensvergleich, robust gegen Reihenfolge und Zweitnamen."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    total = 0.0
    for tok in short:
        total += max(jaro_winkler(tok, other) for other in long_)
    score = total / len(short)
    # Nachname (letztes Token) soll besonders zählen
    if ta[-1] != tb[-1] and jaro_winkler(ta[-1], tb[-1]) < 0.9 and not set(ta) & set(tb[-1:]):
        score *= 0.8
    return round(score, 3)


def score_candidate(subject: dict[str, Any], identifiers: Iterable[dict[str, Any]], candidate: dict[str, Any]) -> tuple[int, list[str]]:
    """Bewertet einen Quellentreffer gegen das Personenprofil.

    ``candidate`` enthält: title, snippet, category, match_kind (womit gesucht wurde),
    query sowie optional ``names``, ``locations``, ``usernames``, ``emails``.
    """
    reasons: list[str] = []
    score = 0.0
    idents = list(identifiers)
    by_kind: dict[str, set[str]] = {}
    for ident in idents:
        by_kind.setdefault(ident["kind"], set()).add(ident["normalized"])
    names = by_kind.get("name", set()) | by_kind.get("alias", set())
    if subject.get("label"):
        names.add(normalize("name", subject["label"]))

    match_kind = candidate.get("match_kind", "")
    if match_kind in {"email", "phone"}:
        score += 55
        reasons.append(f"Exakte Übereinstimmung über {'E-Mail' if match_kind == 'email' else 'Telefonnummer'}")
    elif match_kind == "username":
        score += 35
        reasons.append("Benutzername existiert auf der Plattform (gleicher Name ≠ gleiche Person)")

    cand_names = [n for n in candidate.get("names", []) if n]
    best = 0.0
    best_name = ""
    for cn in cand_names:
        for n in names:
            sim = name_similarity(cn, n)
            if sim > best:
                best, best_name = sim, cn
    if best >= 0.97:
        score += 40
        reasons.append(f"Name stimmt überein: „{best_name}“")
    elif best >= 0.88:
        score += 28
        reasons.append(f"Name sehr ähnlich: „{best_name}“ ({int(best * 100)} %)")
    elif best >= 0.78:
        score += 12
        reasons.append(f"Name teilweise ähnlich: „{best_name}“ ({int(best * 100)} %)")
    elif cand_names and match_kind in {"name", ""}:
        score -= 15
        reasons.append("Name weicht deutlich ab")

    text = fold(" ".join(str(candidate.get(k, "")) for k in ("title", "snippet")) + " " + " ".join(candidate.get("locations", [])))
    for loc in by_kind.get("location", set()):
        main = loc.split(",")[0].strip()
        if len(main) >= 3 and contains_term(text, main):
            score += 15
            reasons.append(f"Ort erwähnt: {main.title()}")
            break
    for emp in by_kind.get("employer", set()):
        if len(emp) >= 3 and contains_term(text, emp):
            score += 15
            reasons.append(f"Arbeitgeber/Organisation erwähnt: {emp.title()}")
            break
    for uname in by_kind.get("username", set()):
        if match_kind != "username" and len(uname) >= 4 and contains_term(text, uname):
            score += 10
            reasons.append(f"Bekannter Benutzername erwähnt: @{uname}")
            break
    birth = subject.get("data", {}).get("geburtsdatum", "") if isinstance(subject.get("data"), dict) else ""
    if birth and birth[:4].isdigit() and contains_term(text, birth[:4]):
        score += 10
        reasons.append(f"Geburtsjahr {birth[:4]} erwähnt")

    weight = candidate.get("source_weight", 1.0)
    score = max(0.0, min(100.0, score * weight))
    if not reasons:
        reasons.append("Nur Suchbegriff-Treffer, keine weiteren Übereinstimmungen")
    return int(round(score)), reasons


def confidence_label(score: int) -> str:
    if score >= 75:
        return "hoch"
    if score >= 45:
        return "mittel"
    if score >= 20:
        return "niedrig"
    return "sehr niedrig"
