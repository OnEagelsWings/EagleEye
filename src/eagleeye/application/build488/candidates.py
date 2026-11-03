"""Build 488: deterministic, review-only case entity candidates.

No persistence, network calls, automatic merges, or claims of identity.
Inputs must be independently authorized and scoped to one case by the caller.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from eagleeye_pro.phase20.entity_lineage456 import _normalize_name


def suggest_case_pairs(case_id: str, entities: list[dict], *, threshold: float = 0.84, limit: int = 100) -> list[dict]:
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id required")
    if not 0.0 <= threshold <= 1.0 or not 1 <= limit <= 500:
        raise ValueError("invalid threshold or limit")
    if len(entities) > 1000:
        raise ValueError("case entity limit exceeded")
    prepared = []
    seen = set()
    for entity in entities:
        if entity.get("case_id") != case_id:
            raise ValueError("cross-case entity input rejected")
        entity_id = str(entity.get("entity_id") or "")
        name = str(entity.get("name") or "").strip()
        if not entity_id or not name or entity_id in seen:
            raise ValueError("missing or duplicate entity")
        seen.add(entity_id)
        normalized = _normalize_name(name)
        prepared.append((entity_id, name, str(entity.get("entity_type") or "unknown"), normalized))
    candidates = []
    for i, left in enumerate(prepared):
        for right in prepared[i + 1:]:
            if left[2] != right[2] or left[2] == "unknown":
                continue
            a, b = left[3], right[3]
            exact = bool(a["comparison_key"] and a["comparison_key"] == b["comparison_key"])
            shared = set(a["variants"]) & set(b["variants"])
            score = 1.0 if exact else (0.96 if shared and "" not in shared else
                SequenceMatcher(None, a["latin_transliteration"], b["latin_transliteration"]).ratio())
            if score < threshold:
                continue
            candidates.append({
                "case_id": case_id,
                "left_entity_id": left[0],
                "right_entity_id": right[0],
                "left_name": left[1],
                "right_name": right[1],
                "entity_type": left[2],
                "similarity_score": round(score, 4),
                "reason": "same_normalized_name" if exact else ("shared_name_variant" if shared else "transliteration_similarity"),
                "review_status": "unreviewed",
                "identity_confirmed": False,
                "automatically_merged": False,
                "evidence_created": False,
            })
    return sorted(candidates, key=lambda x: (-x["similarity_score"], x["left_entity_id"], x["right_entity_id"]))[:limit]
