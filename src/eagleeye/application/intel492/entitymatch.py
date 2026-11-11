"""Build 492: stronger, explainable entity candidates and FollowTheMoney-compatible export.

Same contract as Build 488 (review-only, case-scoped, no merges), with better recall for
umlaut spellings, initials, word order, typos and non-Latin scripts. Every candidate
carries a German explanation so the reviewer sees *why* it was proposed.

FollowTheMoney (FtM) is written as plain JSON in the FtM entity format. The official
``followthemoney`` package is not required (it depends on PyICU, which has no standard
Windows wheels).
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from functools import lru_cache
from itertools import permutations

from anyascii import anyascii
from rapidfuzz.distance import Levenshtein
from rapidfuzz.distance import JaroWinkler

from eagleeye_pro.phase20.entity_lineage456 import PARTICLES, _normalize_name

COMPARABLE = {"person": "person", "organization": "org", "company": "org", "place": "place",
              "event": "event", "document": "document"}
GERMAN_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
REASONS = {
    "same_normalized_name": "gleiche Schreibweise nach Normalisierung",
    "shared_name_variant": "gleiche Namensvariante (z. B. andere Reihenfolge oder Transliteration)",
    "umlaut_spelling": "gleicher Name in Umlaut-Schreibweise (ä/ae, ß/ss)",
    "initial_compatible": "gleicher Nachname, Vorname als Initiale kompatibel",
    "token_order": "gleiche Namensbestandteile in anderer Reihenfolge",
    "spelling_similarity": "sehr ähnliche Schreibweise (möglicher Tippfehler)",
    "consonant_skeleton": "gleiches Konsonantengerüst (Schrift ohne Vokalzeichen) – besonders sorgfältig prüfen",
}


# Tokens that say nothing about *which* entity it is. They take part in the comparison but
# cannot be the only real agreement between two names (and are not used for blocking).
NON_ANCHORS = frozenset({
    "gmbh", "mbh", "ag", "kg", "ohg", "gbr", "ug", "se", "ev", "kgaa", "co", "ltd", "limited", "inc", "llc",
    "llp", "plc", "corp", "corporation", "sa", "sarl", "sas", "bv", "nv", "spa", "srl", "ab", "oy", "aps",
    "sro", "ooo", "zao", "oao", "pao", "&", "und", "and", "of", "the", "für", "fuer", "for"})
TYPO_MIN_LENGTH = 7
TYPO_MAX_DISTANCE = 2
DELETION_KEY_MAX_LENGTH = 32


def _latin_forms(name: str, normalized: dict) -> set[str]:
    base = re.sub(r"[^\w\s]", " ", anyascii(name).casefold())
    forms = {normalized["latin_transliteration"], " ".join(base.split()),
             " ".join(name.casefold().translate(GERMAN_FOLD).split())}
    return {f for f in forms if f}


def _tokens(form: str) -> list[str]:
    tokens = [t.strip(".,") for t in re.split(r"[\s'\-]+", form) if t.strip(".,")]
    return [t for t in tokens if t not in PARTICLES] or tokens


@lru_cache(maxsize=200_000)
def _token_similarity(a: str, b: str) -> tuple[float, str]:
    """Short name parts must match exactly; typos are tolerated only in long parts."""
    if a == b:
        return 1.0, "exact"
    if (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b)):
        return 0.9, "initial"
    if min(len(a), len(b)) >= TYPO_MIN_LENGTH and Levenshtein.distance(a, b, score_cutoff=TYPO_MAX_DISTANCE) <= TYPO_MAX_DISTANCE:
        score = JaroWinkler.normalized_similarity(a, b)
        if score >= 0.93:
            return score, "typo"
    return 0.0, "different"


def _align(tx: tuple[str, ...], ty: tuple[str, ...]) -> tuple[float, frozenset, bool]:
    """Best one-to-one alignment; one extra (middle) name part is tolerated.

    An alignment needs an anchor: at least one exactly or nearly equal name part that is not
    a legal form or filler word. Initials and "GmbH" alone never make two names a candidate.
    """
    if not tx or not ty or abs(len(tx) - len(ty)) > 1 or max(len(tx), len(ty)) > 6:
        return 0.0, frozenset(), False
    short, long_ = (tx, ty) if len(tx) <= len(ty) else (ty, tx)
    best, best_kinds, best_order = 0.0, frozenset(), False
    for perm in permutations(range(len(long_)), len(short)):
        total, kinds, anchored = 0.0, set(), False
        for i, j in enumerate(perm):
            s, kind = _token_similarity(short[i], long_[j])
            if s == 0.0:
                break
            total += s
            kinds.add(kind)
            anchored = anchored or kind == "typo" or (kind == "exact" and short[i] not in NON_ANCHORS)
        else:
            if not anchored:
                continue
            score = total / len(short) * (0.92 if len(short) != len(long_) else 1.0)
            if score > best:
                best, best_kinds, best_order = score, frozenset(kinds), list(perm) != sorted(perm)
    return best, best_kinds, best_order


def _skeleton(value: str) -> str:
    text = anyascii(value).casefold().replace("ch", "kh").replace("c", "k")
    text = re.sub(r"[aeiouyvw\W_]+", "", text)
    return re.sub(r"(.)\1+", r"\1", text)


_ABJAD = {"Hebrew", "Arabic"}


class _Prepared:
    """Everything needed to compare one name, computed once per entity."""
    __slots__ = ("key", "variants", "folded", "forms", "token_lists", "abjad", "skeleton")

    def __init__(self, name: str) -> None:
        normalized = _normalize_name(name)
        self.key = normalized["comparison_key"]
        self.variants = frozenset(normalized["variants"]) - {""}
        self.folded = name.casefold().translate(GERMAN_FOLD)
        forms = sorted(_latin_forms(name, normalized))
        self.forms = frozenset(" ".join(f.split()) for f in forms)
        self.token_lists = tuple(dict.fromkeys(tuple(_tokens(f)) for f in forms))
        self.abjad = bool(_ABJAD & set(normalized["scripts"]))
        self.skeleton = _skeleton(name)


def _compare(a: _Prepared, b: _Prepared) -> tuple[float, str]:
    if a.key and a.key == b.key:
        return 1.0, "same_normalized_name"
    if a.variants & b.variants:
        return 0.96, "shared_name_variant"
    if a.folded == b.folded or (a.forms & b.forms):
        return 0.95, "umlaut_spelling"
    best, reason = 0.0, "spelling_similarity"
    for tx in a.token_lists:
        for ty in b.token_lists:
            score, kinds, reordered = _align(tx, ty)
            if score <= best:
                continue
            best = score
            if "initial" in kinds:
                reason = "initial_compatible"
            elif reordered and kinds == {"exact"}:
                reason = "token_order"
            else:
                reason = "spelling_similarity"
    if best < 0.9 and a.abjad != b.abjad and len(a.skeleton) >= 4 and a.skeleton == b.skeleton:
        return 0.9, "consonant_skeleton"
    return round(best, 4), reason


def compare_names(left: str, right: str) -> tuple[float, str]:
    return _compare(_Prepared(left), _Prepared(right))


def _deletion_keys(token: str) -> set[str]:
    """All strings reachable by deleting up to two characters. Two tokens within edit
    distance two always share at least one such string, so no typo pair is missed."""
    keys = {token}
    for i in range(len(token)):
        once = token[:i] + token[i + 1:]
        keys.add(once)
        for j in range(i, len(once)):
            keys.add(once[:j] + once[j + 1:])
    return keys


def _blocking_keys(p: _Prepared) -> set[str]:
    """Keys such that every pair with a non-zero score shares at least one of them."""
    keys = {"f:" + p.folded}
    if p.key:
        keys.add("k:" + p.key)
    keys.update("v:" + v for v in p.variants)
    keys.update("m:" + f for f in p.forms)
    if len(p.skeleton) >= 4:
        keys.add("s:" + p.skeleton)
    for tokens in p.token_lists:
        for token in tokens:
            if token in NON_ANCHORS:
                continue
            keys.add("t:" + token)
            if TYPO_MIN_LENGTH <= len(token) <= DELETION_KEY_MAX_LENGTH:
                keys.update("d:" + k for k in _deletion_keys(token))
            elif len(token) > DELETION_KEY_MAX_LENGTH:
                keys.add("l:long")  # extremely long parts are compared among themselves
    return keys


def _candidate_pairs(prepared: list[_Prepared], groups: list[str | None], blocking: bool) -> list[tuple[int, int]]:
    n = len(prepared)
    if not blocking:
        return [(i, j) for i in range(n) for j in range(i + 1, n) if groups[i] is not None and groups[i] == groups[j]]
    blocks: dict[tuple[str, str], list[int]] = {}
    for index, item in enumerate(prepared):
        if groups[index] is None:
            continue
        for key in _blocking_keys(item):
            blocks.setdefault((groups[index], key), []).append(index)
    pairs: set[tuple[int, int]] = set()
    for members in blocks.values():
        if len(members) > 1:
            for a in range(len(members)):
                for b in range(a + 1, len(members)):
                    pairs.add((members[a], members[b]))
    return sorted(pairs)


def _all_candidates(case_id: str, checked: list[tuple[str, str, str]], threshold: float, blocking: bool) -> list[dict]:
    prepared = [_Prepared(name) for _, name, _ in checked]
    groups = [COMPARABLE.get(kind) for _, _, kind in checked]
    out = []
    # A threshold of zero admits pairs without any agreement; blocking cannot find those.
    for i, j in _candidate_pairs(prepared, groups, blocking and threshold > 0):
        score, code = _compare(prepared[i], prepared[j])
        if score < threshold:
            continue
        left, right = checked[i], checked[j]
        out.append({
            "case_id": case_id, "left_entity_id": left[0], "right_entity_id": right[0],
            "left_name": left[1], "right_name": right[1], "entity_type": left[2],
            "similarity_score": score, "reason": REASONS[code], "reason_code": code,
            "matcher": "492-rapidfuzz-anyascii", "review_status": "unreviewed",
            "identity_confirmed": False, "automatically_merged": False, "evidence_created": False,
        })
    return sorted(out, key=lambda x: (-x["similarity_score"], x["left_entity_id"], x["right_entity_id"]))


def suggest_case_pairs_492(case_id: str, entities: list[dict], *, threshold: float = 0.88, limit: int = 100,
                           blocking: bool = True) -> list[dict]:
    """Review-only candidates. ``blocking=False`` compares every pair (reference for tests)."""
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id required")
    if not 0.0 <= threshold <= 1.0 or not 1 <= limit <= 500:
        raise ValueError("invalid threshold or limit")
    if len(entities) > 1000:
        raise ValueError("case entity limit exceeded")
    checked, seen = [], set()
    for entity in entities:
        if entity.get("case_id") != case_id:
            raise ValueError("cross-case entity input rejected")
        entity_id = str(entity.get("entity_id") or "")
        name = str(entity.get("name") or "").strip()
        if not entity_id or not name or entity_id in seen:
            raise ValueError("missing or duplicate entity")
        seen.add(entity_id)
        checked.append((entity_id, name, str(entity.get("entity_type") or "unknown")))
    return _all_candidates(case_id, checked, threshold, blocking)[:limit]


class CandidateCache:
    """Remember the candidates for an unchanged set of case entities.

    The review page computes candidates on every view and again on every saved decision.
    The key covers ids, names and types, so any change to the entities recomputes.
    """

    def __init__(self, matcher=suggest_case_pairs_492, max_entries: int = 16) -> None:
        self.matcher, self.max_entries = matcher, max_entries
        self._lock = threading.Lock()
        self._entries: dict[str, list[dict]] = {}
        self.hits = self.misses = 0

    def __call__(self, case_id: str, entities: list[dict]) -> list[dict]:
        digest = hashlib.sha256(json.dumps(
            [case_id, sorted((str(e.get("case_id")), str(e.get("entity_id")), str(e.get("name")), str(e.get("entity_type")))
                             for e in entities)], ensure_ascii=False).encode("utf-8")).hexdigest()
        with self._lock:
            cached = self._entries.get(digest)
            if cached is not None:
                self.hits += 1
                self._entries[digest] = self._entries.pop(digest)  # most recently used last
                return [dict(item) for item in cached]
        result = self.matcher(case_id, entities)
        with self._lock:
            self.misses += 1
            self._entries[digest] = result
            while len(self._entries) > self.max_entries:
                self._entries.pop(next(iter(self._entries)))
        return [dict(item) for item in result]


FTM_SCHEMA = {"person": "Person", "organization": "Organization", "company": "Company",
              "place": "Address", "event": "Event", "document": "Document"}


def _ftm_id(case_id: str, local_id: str) -> str:
    return "ee-" + hashlib.sha1(f"{case_id}:{local_id}".encode("utf-8")).hexdigest()


def ftm_entities(graph: dict, reviews: list[dict] | None = None) -> list[dict]:
    """Case graph → FtM entities. Relations are exported as UnknownLink (role = predicate)."""
    case_id = graph["case_id"]
    names = {}
    out = []
    for entity in graph["entities"]:
        schema = FTM_SCHEMA.get(entity["kind"], "LegalEntity")
        prop = "full" if schema == "Address" else ("title" if schema == "Document" else "name")
        props = {prop: [entity["label"]]}
        if entity.get("notes"):
            props["notes" if schema != "Address" else "summary"] = [str(entity["notes"])[:2000]]
        names[str(entity["id"])] = _ftm_id(case_id, str(entity["id"]))
        out.append({"id": names[str(entity["id"])], "schema": schema, "properties": props,
                    "datasets": ["eagleeye-case"], "eagleeye": {"case_id": case_id, "entity_id": str(entity["id"]),
                                                                 "verified": False}})
    for rel in graph["relations"]:
        if str(rel["source_id"]) not in names or str(rel["target_id"]) not in names:
            continue
        props = {"subject": [names[str(rel["source_id"])]], "object": [names[str(rel["target_id"])]],
                 "role": [rel["predicate"]]}
        if rel.get("valid_from"):
            props["startDate"] = [rel["valid_from"]]
        if rel.get("valid_until"):
            props["endDate"] = [rel["valid_until"]]
        props["sourceUrl"] = [s["source_ref"] for s in rel.get("sources", []) if str(s.get("source_ref", "")).startswith(("http://", "https://"))][:20]
        if not props["sourceUrl"]:
            props.pop("sourceUrl")
        out.append({"id": _ftm_id(case_id, "rel:" + str(rel["id"])), "schema": "UnknownLink", "properties": props,
                    "datasets": ["eagleeye-case"], "eagleeye": {"state": rel.get("state"), "verified": False}})
    for review in reviews or []:
        if review.get("decision") == "possible_match":
            left, right = names.get(review["left_entity_id"]), names.get(review["right_entity_id"])
            if left and right:
                out.append({"id": _ftm_id(case_id, "match:" + left + right), "schema": "Note",
                            "properties": {"entity": [left, right], "description":
                                           ["Mögliche Übereinstimmung laut menschlicher Prüfung (nicht bestätigt): " + review["rationale"][:500]]},
                            "datasets": ["eagleeye-case"], "eagleeye": {"verified": False}})
    return out
