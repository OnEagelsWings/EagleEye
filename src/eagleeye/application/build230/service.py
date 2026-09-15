from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts

_ALLOWED_TRANSLATION_ENGINES = {"manual", "argos_offline", "ollama_local", "reviewed_external_import"}
_ALLOWED_FUSION_ROLES = {"supports", "contradicts", "context"}
_ALLOWED_PAIR_DECISIONS = {"match_candidate", "no_match", "uncertain"}
_ALLOWED_FUSION_DECISIONS = {"accepted_candidate", "challenged", "needs_more_evidence"}

_HEBREW = {
    "א":"", "ב":"b", "ג":"g", "ד":"d", "ה":"h", "ו":"v", "ז":"z", "ח":"h", "ט":"t", "י":"y",
    "כ":"k", "ך":"k", "ל":"l", "מ":"m", "ם":"m", "נ":"n", "ן":"n", "ס":"s", "ע":"", "פ":"f", "ף":"f",
    "צ":"z", "ץ":"z", "ק":"k", "ר":"r", "ש":"sh", "ת":"t",
}
_CYRILLIC = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"yo","ж":"zh","з":"z","и":"i","й":"y",
    "к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f",
    "х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya",
}
_ARABIC = {
    "ا":"a","أ":"a","إ":"i","آ":"a","ب":"b","ت":"t","ث":"th","ج":"j","ح":"h","خ":"kh","د":"d","ذ":"dh",
    "ر":"r","ز":"z","س":"s","ش":"sh","ص":"s","ض":"d","ط":"t","ظ":"z","ع":"","غ":"gh","ف":"f","ق":"q",
    "ك":"k","ل":"l","م":"m","ن":"n","ه":"h","ة":"h","و":"w","ؤ":"w","ي":"y","ى":"a","ئ":"y",
}


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _text(value: Any, limit: int = 200_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except Exception:
        return 0.0


def _fold(value: Any) -> str:
    value = unicodedata.normalize("NFKC", _text(value, 5000)).casefold().strip()
    return " ".join(re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).split())


def _strip_marks(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))


def _latin_ascii(value: Any) -> str:
    folded = _strip_marks(_fold(value))
    return " ".join(folded.encode("ascii", "ignore").decode("ascii").split())


def _script_profile(value: Any) -> dict[str, Any]:
    counts = {"latin": 0, "hebrew": 0, "arabic": 0, "cyrillic": 0, "greek": 0, "other": 0}
    for ch in _text(value, 5000):
        if ch.isspace() or ch.isdigit() or unicodedata.category(ch).startswith("P"):
            continue
        cp = ord(ch)
        if 0x0590 <= cp <= 0x05FF:
            counts["hebrew"] += 1
        elif 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0x08A0 <= cp <= 0x08FF:
            counts["arabic"] += 1
        elif 0x0400 <= cp <= 0x052F:
            counts["cyrillic"] += 1
        elif 0x0370 <= cp <= 0x03FF:
            counts["greek"] += 1
        elif "LATIN" in unicodedata.name(ch, ""):
            counts["latin"] += 1
        else:
            counts["other"] += 1
    nonzero = [(k, v) for k, v in counts.items() if v]
    dominant = max(nonzero, key=lambda x: x[1])[0] if nonzero else "unknown"
    return {"dominant": dominant, "counts": counts, "mixed_script": len(nonzero) > 1}


def _romanize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _text(value, 5000)).casefold()
    out: list[str] = []
    for ch in text:
        if unicodedata.combining(ch):
            continue
        if ch in _HEBREW:
            out.append(_HEBREW[ch]); continue
        if ch in _CYRILLIC:
            out.append(_CYRILLIC[ch]); continue
        if ch in _ARABIC:
            out.append(_ARABIC[ch]); continue
        if ord(ch) < 128:
            out.append(ch); continue
        name = unicodedata.name(ch, "")
        if "LATIN" in name:
            out.append(ch.encode("ascii", "ignore").decode("ascii"))
        else:
            out.append(" ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", "".join(out)).split())


def _phonetic_skeleton(value: Any) -> str:
    s = _romanize(value) or _latin_ascii(value)
    s = s.replace("sh", "s").replace("ch", "h").replace("kh", "h").replace("ph", "f")
    s = s.replace("ts", "z").replace("tz", "z").replace("q", "k").replace("c", "k").replace("w", "v").replace("p", "f")
    return re.sub(r"[aeiou\s-]+", "", s)


def _variants(label: str, aliases: Sequence[str]) -> list[str]:
    values = [label, *aliases]
    out: list[str] = []
    for value in values:
        for item in (_fold(value), _latin_ascii(value), _romanize(value), _phonetic_skeleton(value)):
            item = _text(item, 1000).strip()
            if item and item not in out:
                out.append(item)
    return out[:100]


def _best_similarity(left: Sequence[str], right: Sequence[str]) -> float:
    return max((SequenceMatcher(None, a, b).ratio() for a in left for b in right if a and b), default=0.0)


def _anchors(value: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {"birth_date", "birth_year", "location", "locations", "organisation", "organization", "organisations", "valid_from", "valid_to"}
    clean: dict[str, Any] = {}
    for key, raw in dict(value or {}).items():
        if str(key) not in allowed:
            continue
        if isinstance(raw, (list, tuple, set)):
            clean[str(key)] = [_text(x, 500).strip() for x in raw if _text(x, 500).strip()][:50]
        else:
            clean[str(key)] = _text(raw, 1000).strip()
    return clean


class Build230MultilingualIdentitySourceFusionService:
    """Cross-script identity and source fusion with preserved provenance.

    Build 230 deliberately produces candidates, not autonomous identity facts.
    Transliteration and translation are treated as interpretations. Original text
    and source references remain authoritative, and Build 229 remains the final
    claim-verification layer.
    """

    BUILD = "230.0"

    def __init__(self, db: Any, audit: Any, *, identity_ai: Any, evidence: Any, workspace: Any, retrieval: Any, verified_loop: Any, conversation: Any, actor: str = "local-analyst") -> None:
        self.db, self.audit = db, audit
        self.identity_ai, self.evidence, self.workspace = identity_ai, evidence, workspace
        self.retrieval, self.verified_loop, self.conversation, self.actor = retrieval, verified_loop, conversation, actor
        # Build 227 remains the conversational boundary; Build 230 only contributes reviewed multilingual context.
        self.conversation._multilingual_fusion_v2 = self

    # ---------------- identity ----------------
    def create_identity_record(self, *, case_id: str, source_ref: str, record_ref: str, label: str, language: str = "und", aliases: Sequence[str] = (), anchors: Mapping[str, Any] | None = None, statement_refs: Sequence[str] = (), source_reliability: float = .5, created_by: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"MULTILINGUAL IDENTITY 230 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        label = _text(label, 1000).strip()
        if len(label) < 2 or not _text(source_ref, 2000).strip() or not _text(record_ref, 1000).strip():
            raise ValueError("label, source_ref and record_ref required")
        refs = self._statement_refs(case_id, statement_refs)
        explicit_aliases = list(dict.fromkeys(_text(x, 1000).strip() for x in aliases if _text(x, 1000).strip()))[:50]
        clean_anchors = _anchors(anchors or {})
        variants = _variants(label, explicit_aliases)
        profile = _script_profile(label)
        base_fields = {
            "name": _romanize(label) or label,
            "aliases": list(dict.fromkeys([label, *explicit_aliases, *variants])),
            "birth_date": clean_anchors.get("birth_date", ""),
            "locations": clean_anchors.get("locations") or ([clean_anchors["location"]] if clean_anchors.get("location") else []),
            "organisations": clean_anchors.get("organisations") or ([clean_anchors.get("organisation") or clean_anchors.get("organization")] if (clean_anchors.get("organisation") or clean_anchors.get("organization")) else []),
            "valid_from": clean_anchors.get("valid_from", ""), "valid_to": clean_anchors.get("valid_to", ""),
        }
        base = self.identity_ai.add_identity_record(
            case_id=case_id, source_ref=_text(source_ref, 2000), record_ref=_text(record_ref, 1000), fields=base_fields,
            provenance_refs=refs, source_reliability=_clamp(source_reliability), created_by=created_by,
            confirmation=f"IDENTITY RECORD 212 {case_id} ANLEGEN",
        )
        rid, now = new_id("mid230"), now_ts()
        payload = {
            "multilingual_record_id": rid, "case_id": case_id, "base_record_id": base["record_id"], "source_ref": _text(source_ref, 2000),
            "record_ref": _text(record_ref, 1000), "original_label": label, "language": _text(language, 20) or "und", "script_profile": profile,
            "transliterations": variants, "explicit_aliases": explicit_aliases, "anchors": clean_anchors, "statement_refs": refs,
            "source_reliability": _clamp(source_reliability), "status": "candidate", "created_by": created_by, "created_at": now,
        }
        self.db.execute("INSERT INTO multilingual_identity_records_230 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            rid, case_id, base["record_id"], payload["source_ref"], payload["record_ref"], label, payload["language"], dumps(profile), dumps(variants),
            dumps(explicit_aliases), dumps(clean_anchors), dumps(refs), payload["source_reliability"], "candidate", created_by, now, _hash(payload),
        ))
        self._event(case_id, "multilingual_identity_record_created", "multilingual_identity_record", rid, {"language": payload["language"], "script": profile["dominant"], "base_record_id": base["record_id"]}, created_by)
        return {**payload, "identity_confirmed": False, "automatic_merge": False}

    def compare_identity_records(self, *, left_record_id: str, right_record_id: str, created_by: str, confirmation: str) -> dict[str, Any]:
        left, right = self._identity(left_record_id), self._identity(right_record_id)
        if left["case_id"] != right["case_id"] or left_record_id == right_record_id:
            raise ValueError("records must be distinct and case-local")
        case_id = left["case_id"]
        if confirmation != f"MULTILINGUAL IDENTITY COMPARE 230 {case_id} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        if left_record_id > right_record_id:
            left, right = right, left
            left_record_id, right_record_id = right_record_id, left_record_id
        existing = self.db.one("SELECT * FROM multilingual_identity_pairs_230 WHERE case_id=? AND left_record_id=? AND right_record_id=?", (case_id, left_record_id, right_record_id))
        if existing:
            return self._pair_payload(existing)
        base = self.identity_ai.compare_records(case_id=case_id, left_record_id=left["base_record_id"], right_record_id=right["base_record_id"], created_by=created_by, confirmation=f"IDENTITY COMPARE 212 {case_id} AUSFUEHREN")
        lv, rv = _loads(left["transliterations_json"], []), _loads(right["transliterations_json"], [])
        translit = _best_similarity(lv, rv)
        phonetic = SequenceMatcher(None, _phonetic_skeleton(left["original_label"]), _phonetic_skeleton(right["original_label"])).ratio()
        la, ra = _loads(left["anchors_json"], {}), _loads(right["anchors_json"], {})
        anchor_support, conflicts = self._anchor_comparison(la, ra)
        scripts = (_loads(left["script_profile_json"], {}).get("dominant", "unknown"), _loads(right["script_profile_json"], {}).get("dominant", "unknown"))
        script_relation = "cross_script" if scripts[0] != scripts[1] else "same_script"
        base_probability = _clamp(base.get("probability", 0))
        reliability = (float(left["source_reliability"]) + float(right["source_reliability"])) / 2
        penalty = min(.55, sum(float(x.get("penalty", .2)) for x in conflicts))
        score = _clamp(.34 * translit + .22 * phonetic + .22 * base_probability + .14 * anchor_support + .08 * reliability - penalty)
        state = "strong_cross_language_candidate" if score >= .78 and not conflicts else "probable_candidate" if score >= .60 and not conflicts else "uncertain" if score >= .35 else "likely_distinct"
        pid, now = new_id("idpair230"), now_ts()
        payload = {"pair_id": pid, "case_id": case_id, "left_record_id": left_record_id, "right_record_id": right_record_id, "base_comparison_id": base["comparison_id"], "script_relation": script_relation, "transliteration_similarity": round(translit, 6), "phonetic_similarity": round(phonetic, 6), "anchor_support": round(anchor_support, 6), "conflicts": conflicts, "fusion_score": round(score, 6), "candidate_state": state, "status": "review_required", "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO multilingual_identity_pairs_230 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            pid, case_id, left_record_id, right_record_id, base["comparison_id"], script_relation, payload["transliteration_similarity"], payload["phonetic_similarity"], payload["anchor_support"], dumps(conflicts), payload["fusion_score"], state, "review_required", created_by, "", "", "", now, "", _hash(payload),
        ))
        self._event(case_id, "multilingual_identity_compared", "multilingual_identity_pair", pid, {"state": state, "fusion_score": payload["fusion_score"], "automatic_merge": False}, created_by)
        return {**payload, "identity_confirmed": False, "human_review_required": True, "automatic_merge": False}

    def review_identity_pair(self, *, pair_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self._pair(pair_id)
        if confirmation != f"MULTILINGUAL IDENTITY REVIEW 230 {pair_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if decision not in _ALLOWED_PAIR_DECISIONS:
            raise ValueError("invalid review decision")
        if reviewer.strip() == row["created_by"].strip():
            raise PermissionError("independent reviewer required")
        if len(_text(rationale, 5000).strip()) < 15:
            raise ValueError("substantive rationale required")
        if decision == "match_candidate" and (_loads(row["conflicts_json"], []) or float(row["fusion_score"]) < .60):
            raise PermissionError("conflict/score gate blocks match candidate")
        now = now_ts(); status = "reviewed_match_candidate" if decision == "match_candidate" else "reviewed_distinct" if decision == "no_match" else "reviewed_uncertain"
        self.db.execute("UPDATE multilingual_identity_pairs_230 SET status=?,reviewed_by=?,review_decision=?,rationale=?,reviewed_at=? WHERE pair_id=?", (status, reviewer, decision, _text(rationale, 5000), now, pair_id))
        self._event(row["case_id"], "multilingual_identity_reviewed", "multilingual_identity_pair", pair_id, {"decision": decision, "automatic_merge": False}, reviewer)
        updated = self._pair(pair_id)
        return {**self._pair_payload(updated), "identity_confirmed": False, "automatic_merge": False, "base_merge_requires_existing_build212_dual_review": True}

    # ---------------- translation/rendering ----------------
    def register_statement_rendering(self, *, case_id: str, statement_id: str, target_language: str, translated_text: str, engine: str, engine_version: str = "", transliteration_text: str = "", uncertainties: Sequence[str] = (), named_entities_preserved: bool = False, created_by: str, confirmation: str) -> dict[str, Any]:
        statement = self._statement(statement_id, case_id)
        if confirmation != f"STATEMENT RENDERING 230 {statement_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        engine = _text(engine, 80).casefold().strip()
        if engine not in _ALLOWED_TRANSLATION_ENGINES:
            raise ValueError("only manual or approved local/import translation engines are allowed")
        translated = _text(translated_text, 200_000).strip()
        if not translated:
            raise ValueError("translated text required")
        original = _text(statement.get("original_value"), 200_000).strip() or _text(statement.get("value_json"), 200_000)
        rid, now = new_id("render230"), now_ts()
        items = list(dict.fromkeys(_text(x, 1000).strip() for x in uncertainties if _text(x, 1000).strip()))[:100]
        payload = {"rendering_id": rid, "case_id": case_id, "statement_id": statement_id, "source_language": statement.get("value_language") or "und", "target_language": _text(target_language, 20) or "de", "original_text": original, "translated_text": translated, "transliteration_text": _text(transliteration_text, 50_000), "engine": engine, "engine_version": _text(engine_version, 100), "uncertainties": items, "named_entities_preserved": bool(named_entities_preserved), "status": "review_required", "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO statement_renderings_230 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            rid, case_id, statement_id, payload["source_language"], payload["target_language"], original, translated, payload["transliteration_text"], engine, payload["engine_version"], dumps(items), int(payload["named_entities_preserved"]), "review_required", created_by, "", "", now, "", _hash(payload),
        ))
        self._event(case_id, "statement_rendering_created", "statement_rendering", rid, {"statement_id": statement_id, "engine": engine, "target_language": payload["target_language"]}, created_by)
        return {**payload, "original_preserved": True, "external_upload": False, "human_review_required": True}

    def review_statement_rendering(self, *, rendering_id: str, decision: str, review_note: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self._rendering(rendering_id)
        if confirmation != f"STATEMENT RENDERING REVIEW 230 {rendering_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if decision not in {"approved", "rejected"}:
            raise ValueError("invalid rendering decision")
        if reviewer.strip() == row["created_by"].strip():
            raise PermissionError("independent reviewer required")
        if len(_text(review_note, 5000).strip()) < 12:
            raise ValueError("substantive review note required")
        if decision == "approved" and not bool(row["named_entities_preserved"]):
            raise PermissionError("named-entity preservation must be confirmed before approval")
        status = "approved" if decision == "approved" else "rejected"; now = now_ts()
        self.db.execute("UPDATE statement_renderings_230 SET status=?,reviewed_by=?,review_note=?,reviewed_at=? WHERE rendering_id=?", (status, reviewer, _text(review_note, 5000), now, rendering_id))
        self._event(row["case_id"], "statement_rendering_reviewed", "statement_rendering", rendering_id, {"decision": decision}, reviewer)
        updated = self._rendering(rendering_id)
        return self._rendering_payload(updated)

    # ---------------- source fusion ----------------
    def create_source_fusion(self, *, case_id: str, subject_ref: str, predicate: str, working_language: str, canonical_value: Any, evidence_roles: Mapping[str, str], created_by: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"MULTILINGUAL SOURCE FUSION 230 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        if not _text(subject_ref, 1000).strip() or not _text(predicate, 500).strip():
            raise ValueError("subject_ref and predicate required")
        if not evidence_roles:
            raise ValueError("at least one evidence reference required")
        statements: dict[str, dict[str, Any]] = {}
        roles: dict[str, str] = {}
        for ref, role in dict(evidence_roles).items():
            role = _text(role, 30)
            if role not in _ALLOWED_FUSION_ROLES:
                raise ValueError(f"invalid evidence role for {ref}")
            statement = self._statement(str(ref), case_id)
            statements[str(ref)] = statement; roles[str(ref)] = role
        working = _text(working_language, 20) or "de"
        rendering_map: dict[str, str] = {}
        language_map: dict[str, str] = {}
        for ref, statement in statements.items():
            lang = _text(statement.get("value_language"), 20) or "und"; language_map[ref] = lang
            if lang not in {"", "und", working} and roles[ref] in {"supports", "contradicts"}:
                approved = self.db.one("SELECT rendering_id FROM statement_renderings_230 WHERE case_id=? AND statement_id=? AND target_language=? AND status='approved' ORDER BY reviewed_at DESC LIMIT 1", (case_id, ref, working))
                if not approved:
                    raise PermissionError(f"reviewed translation/rendering required for non-{working} evidence {ref}")
                rendering_map[ref] = approved["rendering_id"]
        supporting = [r for r, role in roles.items() if role == "supports"]
        contradicting = [r for r, role in roles.items() if role == "contradicts"]
        context = [r for r, role in roles.items() if role == "context"]
        origin_groups = self._origin_groups(case_id, [*supporting, *contradicting])
        languages = {language_map[r] for r in [*supporting, *contradicting] if language_map.get(r)}
        source_types = self._source_types(case_id, [*supporting, *contradicting, *context])
        source_diversity = min(1.0, len(source_types) / max(1, len(set([*supporting, *contradicting, *context]))))
        confidences = [float(statements[r].get("confidence") or 0) for r in [*supporting, *contradicting]]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        independence = min(1.0, len(origin_groups) / 2.0)
        language_diversity = min(1.0, len(languages) / 2.0)
        contradiction_penalty = min(.60, len(contradicting) * .25)
        score = _clamp(.38 * independence + .25 * avg_conf + .17 * language_diversity + .20 * source_diversity - contradiction_penalty)
        fid, now = new_id("fusion230"), now_ts(); status = "challenged_candidate" if contradicting else "candidate"
        payload = {"fusion_id": fid, "case_id": case_id, "subject_ref": _text(subject_ref, 1000), "predicate": _text(predicate, 500), "working_language": working, "canonical_value": canonical_value, "supporting_refs": supporting, "contradicting_refs": contradicting, "context_refs": context, "language_map": language_map, "rendering_map": rendering_map, "independent_origin_count": len(origin_groups), "language_count": len(languages), "source_diversity": round(source_diversity, 6), "average_confidence": round(avg_conf, 6), "fusion_score": round(score, 6), "contradiction_count": len(contradicting), "status": status, "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO multilingual_source_fusions_230 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            fid, case_id, payload["subject_ref"], payload["predicate"], working, dumps(canonical_value), dumps(supporting), dumps(contradicting), dumps(context), dumps(language_map), dumps(rendering_map), payload["independent_origin_count"], payload["language_count"], payload["source_diversity"], payload["average_confidence"], payload["fusion_score"], payload["contradiction_count"], status, created_by, "", "", "", now, "", _hash(payload),
        ))
        self._event(case_id, "multilingual_source_fusion_created", "multilingual_source_fusion", fid, {"independent_origins": payload["independent_origin_count"], "languages": payload["language_count"], "score": payload["fusion_score"], "contradictions": len(contradicting)}, created_by)
        return {**payload, "verified": False, "human_review_required": True, "automatic_claim_creation": False}

    def review_source_fusion(self, *, fusion_id: str, decision: str, review_note: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self._fusion(fusion_id)
        if confirmation != f"MULTILINGUAL SOURCE FUSION REVIEW 230 {fusion_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if decision not in _ALLOWED_FUSION_DECISIONS:
            raise ValueError("invalid fusion decision")
        if reviewer.strip() == row["created_by"].strip():
            raise PermissionError("independent reviewer required")
        if len(_text(review_note, 5000).strip()) < 15:
            raise ValueError("substantive review note required")
        if decision == "accepted_candidate":
            if int(row["contradiction_count"]) > 0:
                raise PermissionError("contradiction gate blocks accepted candidate")
            if int(row["independent_origin_count"]) < 2:
                raise PermissionError("independent-source gate blocks accepted candidate")
            if float(row["fusion_score"]) < .60:
                raise PermissionError("fusion score below candidate threshold")
        status = "accepted_for_verification" if decision == "accepted_candidate" else "challenged" if decision == "challenged" else "needs_more_evidence"
        now = now_ts(); self.db.execute("UPDATE multilingual_source_fusions_230 SET status=?,reviewed_by=?,review_decision=?,review_note=?,reviewed_at=? WHERE fusion_id=?", (status, reviewer, decision, _text(review_note, 5000), now, fusion_id))
        self._event(row["case_id"], "multilingual_source_fusion_reviewed", "multilingual_source_fusion", fusion_id, {"decision": decision, "verified": False}, reviewer)
        return self.fusion(fusion_id)

    def handoff_to_verified_loop(self, *, fusion_id: str, cycle_id: str, claim_text: str, confidence: float, actor: str, confirmation: str) -> dict[str, Any]:
        fusion = self._fusion(fusion_id)
        if confirmation != f"MULTILINGUAL FUSION 230 {fusion_id} AN BUILD229 UEBERGEBEN":
            raise PermissionError("explicit approval required")
        if fusion["status"] != "accepted_for_verification":
            raise PermissionError("fusion must first be accepted as a verification candidate")
        cycle = self.db.one("SELECT * FROM verified_research_cycles_229 WHERE cycle_id=? AND case_id=?", (cycle_id, fusion["case_id"]))
        if not cycle:
            raise ValueError("Build-229 cycle not found in the same case")
        result = self.verified_loop.add_claim(
            cycle_id=cycle_id, claim_text=_text(claim_text, 20_000), claim_kind="observation", confidence=_clamp(confidence),
            supporting_refs=_loads(fusion["supporting_refs_json"], []), contradicting_refs=_loads(fusion["contradicting_refs_json"], []),
            actor=actor, confirmation=f"VERIFIED CLAIM 229 {cycle_id} ANLEGEN",
        )
        self._event(fusion["case_id"], "multilingual_fusion_handed_to_build229", "multilingual_source_fusion", fusion_id, {"cycle_id": cycle_id, "verified_claim_id": result["verified_claim_id"], "automatic_verification": False}, actor)
        return {"fusion_id": fusion_id, "verified_claim_id": result["verified_claim_id"], "status": result["status"], "automatic_verification": False, "build229_review_required": True}

    # ---------------- dashboard/UI ----------------
    def conversation_context(self, *, case_id: str, limit: int = 12) -> dict[str, Any]:
        """Return only reviewed multilingual context for the conversational investigator."""
        self._case(case_id)
        pairs = self.db.all("SELECT pair_id,left_record_id,right_record_id,fusion_score,candidate_state,status,review_decision,rationale FROM multilingual_identity_pairs_230 WHERE case_id=? AND status LIKE 'reviewed_%' ORDER BY reviewed_at DESC LIMIT ?", (case_id, max(1, min(int(limit), 30))))
        fusions = self.db.all("SELECT fusion_id,subject_ref,predicate,canonical_value_json,supporting_refs_json,contradicting_refs_json,language_map_json,independent_origin_count,language_count,fusion_score,status,review_decision,review_note FROM multilingual_source_fusions_230 WHERE case_id=? AND status IN ('accepted_for_verification','challenged','needs_more_evidence') ORDER BY reviewed_at DESC LIMIT ?", (case_id, max(1, min(int(limit), 30))))
        return {
            "identity_candidates": [{**x, "identity_confirmed": False} for x in pairs],
            "source_fusions": [{"fusion_id": x["fusion_id"], "subject_ref": x["subject_ref"], "predicate": x["predicate"], "canonical_value": _loads(x["canonical_value_json"], {}), "supporting_refs": _loads(x["supporting_refs_json"], []), "contradicting_refs": _loads(x["contradicting_refs_json"], []), "languages": sorted(set(_loads(x["language_map_json"], {}).values())), "independent_origins": x["independent_origin_count"], "fusion_score": x["fusion_score"], "status": x["status"], "review_decision": x["review_decision"], "review_note": x["review_note"], "verified": False} for x in fusions],
            "rules": ["Transliteration is candidate evidence, not identity proof.", "Translations are reviewed interpretations; original evidence remains authoritative.", "Accepted source fusions still require Build-229 verification."],
        }

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        identities = self.db.all("SELECT multilingual_record_id,original_label,language,status,created_at FROM multilingual_identity_records_230 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,))
        pairs = self.db.all("SELECT pair_id,fusion_score,candidate_state,status,created_at FROM multilingual_identity_pairs_230 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,))
        fusions = self.db.all("SELECT fusion_id,predicate,independent_origin_count,language_count,fusion_score,status,created_at FROM multilingual_source_fusions_230 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,))
        return {"case_id": case_id, "identity_records": identities, "identity_pairs": pairs, "source_fusions": fusions, "approved_renderings": int((self.db.one("SELECT COUNT(*) AS n FROM statement_renderings_230 WHERE case_id=? AND status='approved'", (case_id,)) or {"n": 0})["n"]), "automatic_identity_merge": False, "automatic_source_execution": False}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        d = self.dashboard(case_id=case_id); esc = html.escape
        identities = "".join(f"<tr><td>{esc(x['original_label'])}</td><td>{esc(x['language'])}</td><td><code>{esc(x['multilingual_record_id'])}</code></td><td>{esc(x['status'])}</td></tr>" for x in d["identity_records"][:12]) or "<tr><td colspan='4'>Noch keine mehrsprachigen Identitätskandidaten.</td></tr>"
        fusions = "".join(f"<tr><td>{esc(x['predicate'])}</td><td>{x['independent_origin_count']}</td><td>{x['language_count']}</td><td>{float(x['fusion_score']):.2f}</td><td>{esc(x['status'])}</td></tr>" for x in d["source_fusions"][:12]) or "<tr><td colspan='5'>Noch keine Source-Fusion.</td></tr>"
        return f"""<section class='card' id='build230_multilingual_fusion'><h2>Multilingual Identity &amp; Source Fusion · Build 230</h2>
<p>Schrift- und sprachübergreifende Identitätskandidaten, überprüfte Übersetzungen und Quellenfusion. Originalbelege bleiben maßgeblich; keine automatische Identitätsverschmelzung und keine automatische Verifikation.</p>
<div class='grid two'><div><h3>Identitätskandidat anlegen</h3><form method='post' action='/build230/identity-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='source_ref' placeholder='Source-Ref' required><input name='record_ref' placeholder='Record-Ref' required><input name='label' placeholder='Name in Originalschrift' required><input name='language' value='und'><input name='aliases' placeholder='Aliase, kommagetrennt'><button>Mehrsprachigen Kandidaten anlegen</button></form></div>
<div><h3>Source-Fusion</h3><p>Mehrsprachige Aussagen werden erst nach geprüfter Rendering-/Übersetzung zusammengeführt und anschließend als Kandidat an Build 229 übergeben.</p><p><strong>Status:</strong> {len(d['identity_records'])} Identitätsrecords · {len(d['identity_pairs'])} Vergleiche · {len(d['source_fusions'])} Fusionen · {d['approved_renderings']} geprüfte Renderings.</p></div></div>
<div class='table-wrap'><table><thead><tr><th>Originalname</th><th>Sprache</th><th>ID</th><th>Status</th></tr></thead><tbody>{identities}</tbody></table></div>
<div class='table-wrap'><table><thead><tr><th>Prädikat</th><th>Ursprünge</th><th>Sprachen</th><th>Score</th><th>Status</th></tr></thead><tbody>{fusions}</tbody></table></div></section>"""

    # ---------------- helpers ----------------
    def fusion(self, fusion_id: str) -> dict[str, Any]:
        row = self._fusion(fusion_id)
        return {**row, "canonical_value": _loads(row["canonical_value_json"], {}), "supporting_refs": _loads(row["supporting_refs_json"], []), "contradicting_refs": _loads(row["contradicting_refs_json"], []), "context_refs": _loads(row["context_refs_json"], []), "language_map": _loads(row["language_map_json"], {}), "rendering_map": _loads(row["rendering_map_json"], {}), "verified": False, "automatic_verification": False}

    def _anchor_comparison(self, left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[float, list[dict[str, Any]]]:
        checks = 0; matches = 0; conflicts: list[dict[str, Any]] = []
        for key in ("birth_date", "birth_year"):
            lv, rv = _text(left.get(key), 100), _text(right.get(key), 100)
            if lv and rv:
                checks += 1
                if _fold(lv) == _fold(rv): matches += 1
                else: conflicts.append({"feature": key, "penalty": .45, "left": lv, "right": rv})
        for keys in (("location", "locations"), ("organisation", "organisations")):
            vals: list[set[str]] = []
            for obj in (left, right):
                raw = obj.get(keys[1]) or obj.get(keys[0]) or []
                if not isinstance(raw, (list, tuple, set)): raw = [raw]
                vals.append({_latin_ascii(x) or _fold(x) for x in raw if _text(x, 500).strip()})
            if vals[0] and vals[1]:
                checks += 1
                if vals[0] & vals[1]: matches += 1
        return (matches / checks if checks else 0.0), conflicts

    def _statement_refs(self, case_id: str, refs: Sequence[str]) -> list[str]:
        out: list[str] = []
        for ref in refs:
            ref = _text(ref, 200).strip()
            if not ref or ref in out: continue
            self._statement(ref, case_id); out.append(ref)
        return out

    def _origin_groups(self, case_id: str, refs: Sequence[str]) -> set[str]:
        groups: set[str] = set()
        for ref in refs:
            row = self.db.one("SELECT independence_group,origin_key FROM source_lineage_nodes_225 WHERE case_id=? AND source_ref=? AND status='active' ORDER BY updated_at DESC LIMIT 1", (case_id, ref))
            key = _text((row or {}).get("independence_group") or (row or {}).get("origin_key"), 1000).strip()
            if not key:
                source = self.db.one("SELECT s.source_id,s.canonical_url,s.original_url,s.collector_id FROM evidence_statements_211 st JOIN evidence_sources_211 s ON s.source_id=st.source_id WHERE st.case_id=? AND st.statement_id=?", (case_id, ref))
                if source:
                    url = _text(source.get("canonical_url") or source.get("original_url"), 4000)
                    try:
                        host = (urlsplit(url).hostname or "").casefold()
                    except Exception:
                        host = ""
                    key = host or _text(source.get("collector_id") or source.get("source_id"), 1000)
            if key:
                groups.add(key)
        return groups

    def _source_types(self, case_id: str, refs: Sequence[str]) -> set[str]:
        out: set[str] = set()
        for ref in refs:
            row = self.db.one("SELECT source_type FROM ai_memory_chunks_216 WHERE case_id=? AND source_ref=? ORDER BY created_at DESC LIMIT 1", (case_id, ref))
            out.add(_text((row or {}).get("source_type") or "evidence_statement", 100))
        return out

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _statement(self, statement_id: str, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_statements_211 WHERE statement_id=? AND case_id=?", (statement_id, case_id))
        if not row: raise KeyError(statement_id)
        return row

    def _identity(self, record_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM multilingual_identity_records_230 WHERE multilingual_record_id=?", (record_id,))
        if not row: raise KeyError(record_id)
        return row

    def _pair(self, pair_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM multilingual_identity_pairs_230 WHERE pair_id=?", (pair_id,))
        if not row: raise KeyError(pair_id)
        return row

    def _pair_payload(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "conflicts": _loads(row.get("conflicts_json"), []), "identity_confirmed": False, "automatic_merge": False}

    def _rendering(self, rendering_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM statement_renderings_230 WHERE rendering_id=?", (rendering_id,))
        if not row: raise KeyError(rendering_id)
        return row

    def _rendering_payload(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "uncertainties": _loads(row.get("uncertainties_json"), []), "original_preserved": True, "human_review_required": row.get("status") != "approved"}

    def _fusion(self, fusion_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM multilingual_source_fusions_230 WHERE fusion_id=?", (fusion_id,))
        if not row: raise KeyError(fusion_id)
        return row

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> None:
        previous = self.db.one("SELECT event_hash FROM build230_events WHERE case_id=? ORDER BY created_at DESC,event_id DESC LIMIT 1", (case_id,))
        previous_hash = (previous or {}).get("event_hash", "")
        eid, now = new_id("event230"), now_ts()
        event_hash = _hash({"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "payload": dict(payload), "actor": actor, "created_at": now, "previous_hash": previous_hash})
        self.db.execute("INSERT INTO build230_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, dumps(dict(payload)), actor, now, previous_hash, event_hash))
        try:
            self.audit.log(event_type, f"build230:{object_type}", object_id, case_id, {"event_hash": event_hash})
        except Exception:
            pass
