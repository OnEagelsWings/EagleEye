"""Erklärbarer Namensabgleich über Schreibweisen und Schriften hinweg.

Übernommen aus EagleEye Build 492 (``intel492/entitymatch.py``, Tool-Auswahl A5; Normalisierung aus Build 456):
Umlaut-Schreibweisen, Initialen, vertauschte Reihenfolge, Tippfehler in langen Namensteilen sowie Kyrillisch,
Griechisch, Arabisch und Hebräisch. Jeder Vorschlag trägt eine deutsche Begründung, damit die prüfende Person
sieht, *warum* er entstand. Es wird nie automatisch zusammengeführt.

Gemessen am unabhängigen Prüfsatz ``tests/data/entity_pairs_holdout.json`` (27 Paare): Präzision 0,93 / Trefferquote 0,93.
"""
from __future__ import annotations

import re
import unicodedata
from itertools import permutations

from anyascii import anyascii
from rapidfuzz.distance import JaroWinkler, Levenshtein

THRESHOLD = 0.88
GERMAN_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
PARTICLES = {"de", "del", "della", "di", "da", "van", "von", "der", "den", "al", "el", "bin", "ibn", "bat", "ben", "bar"}
REASONS = {
    "same_normalized_name": "gleiche Schreibweise nach Normalisierung",
    "shared_name_variant": "gleiche Namensvariante (z. B. andere Reihenfolge oder Transliteration)",
    "umlaut_spelling": "gleicher Name in Umlaut-Schreibweise (ä/ae, ß/ss)",
    "initial_compatible": "gleicher Nachname, Vorname als Initiale kompatibel",
    "token_order": "gleiche Namensbestandteile in anderer Reihenfolge",
    "spelling_similarity": "sehr ähnliche Schreibweise (möglicher Tippfehler)",
    "consonant_skeleton": "gleiches Konsonantengerüst (Schrift ohne Vokalzeichen) – besonders sorgfältig prüfen",
}

_HEBREW = {"א": "a", "ב": "v", "ג": "g", "ד": "d", "ה": "h", "ו": "v", "ז": "z", "ח": "h", "ט": "t", "י": "y", "כ": "kh", "ך": "kh", "ל": "l",
           "מ": "m", "ם": "m", "נ": "n", "ן": "n", "ס": "s", "ע": "a", "פ": "f", "ף": "f", "צ": "ts", "ץ": "ts", "ק": "k", "ר": "r", "ש": "sh", "ת": "t"}
_ARABIC = {"ا": "a", "أ": "a", "إ": "i", "آ": "a", "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "h", "خ": "kh", "د": "d", "ذ": "dh", "ر": "r",
           "ز": "z", "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "ع": "a", "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ل": "l",
           "م": "m", "ن": "n", "ه": "h", "و": "w", "ي": "y", "ى": "a", "ة": "a", "ء": ""}
_CYRILLIC = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l",
             "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh",
             "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya", "і": "i", "ї": "yi", "є": "ye", "ґ": "g"}


def _script(ch: str) -> str:
    name = unicodedata.name(ch, "")
    for key, label in (("HEBREW", "Hebrew"), ("ARABIC", "Arabic"), ("CYRILLIC", "Cyrillic"), ("LATIN", "Latin")):
        if key in name:
            return label
    return "Common" if not ch.isalpha() else "Other"


def transliterate(value: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFKD", str(value or "")):
        if unicodedata.combining(ch):
            continue
        low = ch.casefold()
        out.append(_HEBREW.get(ch) if ch in _HEBREW else _ARABIC.get(ch) if ch in _ARABIC else _CYRILLIC.get(low, low))
    return re.sub(r"\s+", " ", "".join(out)).strip()


def normalize_name(value: str) -> dict:
    original = re.sub(r"\s+", " ", str(value or "")).strip()[:500]
    folded = unicodedata.normalize("NFKC", original).casefold()
    cleaned = re.sub(r"\s+", " ", re.sub(r"[^\w\s'\-]+", " ", folded, flags=re.UNICODE)).strip()
    markless = "".join(ch for ch in unicodedata.normalize("NFKD", cleaned) if not unicodedata.combining(ch))
    tokens = [x for x in markless.split() if x]
    core = [x for x in tokens if x not in PARTICLES] or tokens
    latin = transliterate(original)
    variants = sorted({markless, " ".join(tokens), " ".join(reversed(tokens)) if len(tokens) > 1 else markless, latin,
                       " ".join(core), " ".join(reversed(core)) if len(core) > 1 else " ".join(core)})
    return {"comparison_key": markless, "tokens": tokens, "scripts": sorted({_script(ch) for ch in original if ch.isalpha()}),
            "latin_transliteration": latin, "variants": variants}


def _latin_forms(name: str, normalized: dict) -> set[str]:
    base = re.sub(r"[^\w\s]", " ", anyascii(name).casefold())
    forms = {normalized["latin_transliteration"], " ".join(base.split()), " ".join(name.casefold().translate(GERMAN_FOLD).split())}
    return {f for f in forms if f}


def _tokens(form: str) -> list[str]:
    tokens = [t.strip(".,") for t in re.split(r"[\s'\-]+", form) if t.strip(".,")]
    return [t for t in tokens if t not in PARTICLES] or tokens


def _token_similarity(a: str, b: str) -> tuple[float, str]:
    """Kurze Namensteile müssen exakt passen; Tippfehler werden nur in langen Teilen toleriert."""
    if a == b:
        return 1.0, "exact"
    if (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b)):
        return 0.9, "initial"
    if min(len(a), len(b)) >= 7 and Levenshtein.distance(a, b) <= 2:
        score = JaroWinkler.normalized_similarity(a, b)
        if score >= 0.93:
            return score, "typo"
    return 0.0, "different"


def _align(tx: list[str], ty: list[str]) -> tuple[float, set[str], bool]:
    """Beste Eins-zu-eins-Zuordnung; ein zusätzlicher (zweiter) Vorname wird toleriert."""
    if not tx or not ty or abs(len(tx) - len(ty)) > 1 or max(len(tx), len(ty)) > 6:
        return 0.0, set(), False
    short, long_ = (tx, ty) if len(tx) <= len(ty) else (ty, tx)
    best, best_kinds, best_order = 0.0, set(), False
    for perm in permutations(range(len(long_)), len(short)):
        scores, kinds = [], set()
        for i, j in enumerate(perm):
            s, kind = _token_similarity(short[i], long_[j])
            if s == 0.0:
                break
            scores.append(s)
            kinds.add(kind)
        else:
            score = sum(scores) / len(scores) * (0.92 if len(short) != len(long_) else 1.0)
            if score > best:
                best, best_kinds, best_order = score, kinds, list(perm) != sorted(perm)
    return best, best_kinds, best_order


def _skeleton(value: str) -> str:
    text = anyascii(value).casefold().replace("ch", "kh").replace("c", "k")
    text = re.sub(r"[aeiouyvw\W_]+", "", text)
    return re.sub(r"(.)\1+", r"\1", text)


def compare_names(left: str, right: str) -> tuple[float, str]:
    """Ähnlichkeit 0–1 und Begründungscode (siehe REASONS). Ab THRESHOLD gilt ein Paar als Prüfkandidat."""
    a, b = normalize_name(left), normalize_name(right)
    if a["comparison_key"] and a["comparison_key"] == b["comparison_key"]:
        return 1.0, "same_normalized_name"
    if (set(a["variants"]) & set(b["variants"])) - {""}:
        return 0.96, "shared_name_variant"
    fa, fb = _latin_forms(left, a), _latin_forms(right, b)
    if left.casefold().translate(GERMAN_FOLD) == right.casefold().translate(GERMAN_FOLD) or \
            any(" ".join(x.split()) == " ".join(y.split()) for x in fa for y in fb):
        return 0.95, "umlaut_spelling"
    best, reason = 0.0, "spelling_similarity"
    for x in fa:
        for y in fb:
            score, kinds, reordered = _align(_tokens(x), _tokens(y))
            if score <= best:
                continue
            best = score
            reason = "initial_compatible" if "initial" in kinds else "token_order" if reordered and kinds == {"exact"} else "spelling_similarity"
    abjad = {"Hebrew", "Arabic"}
    if best < 0.9 and (bool(abjad & set(a["scripts"])) != bool(abjad & set(b["scripts"]))):
        sa, sb = _skeleton(left), _skeleton(right)
        if len(sa) >= 4 and sa == sb:
            return 0.9, "consonant_skeleton"
    return round(best, 4), reason


def is_candidate(left: str, right: str) -> tuple[bool, float, str]:
    score, code = compare_names(left, right)
    return score >= THRESHOLD, score, REASONS[code]
