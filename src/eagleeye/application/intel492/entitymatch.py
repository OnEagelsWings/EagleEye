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
import re
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


def _latin_forms(name: str, normalized: dict) -> set[str]:
    base = re.sub(r"[^\w\s]", " ", anyascii(name).casefold())
    forms = {normalized["latin_transliteration"], " ".join(base.split()),
             " ".join(name.casefold().translate(GERMAN_FOLD).split())}
    return {f for f in forms if f}


def _tokens(form: str) -> list[str]:
    tokens = [t.strip(".,") for t in re.split(r"[\s'\-]+", form) if t.strip(".,")]
    return [t for t in tokens if t not in PARTICLES] or tokens


def _token_similarity(a: str, b: str) -> tuple[float, str]:
    """Short name parts must match exactly; typos are tolerated only in long parts."""
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
    """Best one-to-one alignment; one extra (middle) name part is tolerated."""
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
    a, b = _normalize_name(left), _normalize_name(right)
    if a["comparison_key"] and a["comparison_key"] == b["comparison_key"]:
        return 1.0, "same_normalized_name"
    shared = (set(a["variants"]) & set(b["variants"])) - {""}
    if shared:
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
            if "initial" in kinds:
                reason = "initial_compatible"
            elif reordered and kinds == {"exact"}:
                reason = "token_order"
            else:
                reason = "spelling_similarity"
    abjad = {"Hebrew", "Arabic"}
    if best < 0.9 and (bool(abjad & set(a["scripts"])) != bool(abjad & set(b["scripts"]))):
        sa, sb = _skeleton(left), _skeleton(right)
        if len(sa) >= 4 and sa == sb:
            return 0.9, "consonant_skeleton"
    return round(best, 4), reason


def suggest_case_pairs_492(case_id: str, entities: list[dict], *, threshold: float = 0.88, limit: int = 100) -> list[dict]:
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id required")
    if not 0.0 <= threshold <= 1.0 or not 1 <= limit <= 500:
        raise ValueError("invalid threshold or limit")
    if len(entities) > 1000:
        raise ValueError("case entity limit exceeded")
    prepared, seen = [], set()
    for entity in entities:
        if entity.get("case_id") != case_id:
            raise ValueError("cross-case entity input rejected")
        entity_id = str(entity.get("entity_id") or "")
        name = str(entity.get("name") or "").strip()
        if not entity_id or not name or entity_id in seen:
            raise ValueError("missing or duplicate entity")
        seen.add(entity_id)
        prepared.append((entity_id, name, str(entity.get("entity_type") or "unknown")))
    out = []
    for i, left in enumerate(prepared):
        for right in prepared[i + 1:]:
            group = COMPARABLE.get(left[2])
            if group is None or group != COMPARABLE.get(right[2]):
                continue
            score, code = compare_names(left[1], right[1])
            if score < threshold:
                continue
            out.append({
                "case_id": case_id, "left_entity_id": left[0], "right_entity_id": right[0],
                "left_name": left[1], "right_name": right[1], "entity_type": left[2],
                "similarity_score": score, "reason": REASONS[code], "reason_code": code,
                "matcher": "492-rapidfuzz-anyascii", "review_status": "unreviewed",
                "identity_confirmed": False, "automatically_merged": False, "evidence_created": False,
            })
    return sorted(out, key=lambda x: (-x["similarity_score"], x["left_entity_id"], x["right_entity_id"]))[:limit]


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
