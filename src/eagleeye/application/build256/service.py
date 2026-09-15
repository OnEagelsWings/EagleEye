from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _text(value: Any, limit: int = 10000) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _loads(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


HEBREW = {
    "א":"a","ב":"b","ג":"g","ד":"d","ה":"h","ו":"v","ז":"z","ח":"h","ט":"t","י":"y",
    "כ":"k","ך":"k","ל":"l","מ":"m","ם":"m","נ":"n","ן":"n","ס":"s","ע":"a","פ":"p","ף":"p",
    "צ":"ts","ץ":"ts","ק":"q","ר":"r","ש":"sh","ת":"t",
}
ARABIC = {
    "ا":"a","أ":"a","إ":"i","آ":"a","ب":"b","ت":"t","ث":"th","ج":"j","ح":"h","خ":"kh",
    "د":"d","ذ":"dh","ر":"r","ز":"z","س":"s","ش":"sh","ص":"s","ض":"d","ط":"t","ظ":"z",
    "ع":"a","غ":"gh","ف":"f","ق":"q","ك":"k","ک":"k","ل":"l","م":"m","ن":"n","ه":"h",
    "ة":"h","و":"w","ؤ":"w","ي":"y","ى":"a","ئ":"y","ء":"",
}
CYRILLIC = {
    "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"i",
    "к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f",
    "х":"kh","ц":"ts","ч":"ch","ш":"sh","щ":"shch","ъ":"","ы":"y","ь":"","э":"e","ю":"iu","я":"ia",
    "і":"i","ї":"i","є":"ie","ґ":"g",
}
ALLOWED_ENTITY_TYPES = {
    "company","ngo","think_tank","foundation","party_affiliated_foundation","party","ministry_or_authority",
    "parliament_or_committee","media_company","editorial_office","university","intelligence_service","program","project",
    "grant","contract","event","study_or_publication",
}
ALLOWED_IDENTIFIER_TYPES = {
    "commercial_register","association_register","lei","tax_or_charity_id","fara_registration","official_domain_id","other_public_id",
    "company_number","eu_transparency_id","uk_company_number","us_uei","israel_corporation_number",
}
SENSITIVE_IDENTIFIER_TYPES = {
    "passport","national_id","social_security","ssn","personal_tax_id","driver_license","private_email","private_phone","home_address",
}
LEGAL_FORMS = {
    "gmbh","ag","kg","ug","ev","e v","ltd","limited","llc","inc","incorporated","plc","corp","corporation","sas","sa","sarl","bv","nv","oy","ab","aps","sp zoo","ooy","association",
}


class Build256InternationalEntityResolutionService:
    BUILD = "256.0"

    def __init__(self, db: Any, audit: Any, *, influence: Any, parent_documents: Any, training: Any, opsec: Any, conversation: Any, actor: str = "local-analyst") -> None:
        self.db, self.audit = db, audit
        self.influence, self.parent_documents, self.training, self.opsec, self.conversation = influence, parent_documents, training, opsec, conversation
        self.actor = actor
        setattr(conversation, "_entity_resolution256", self)

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: dict[str, Any], actor: str) -> None:
        prev = self.db.one("SELECT event_hash FROM build256_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = (prev or {}).get("event_hash", "")
        eid, at = new_id("evt256"), now_ts()
        event_hash = _hash({"previous": previous, "event_id": eid, "event_type": event_type, "object_id": object_id, "payload": payload, "actor": actor, "at": at})
        self.db.execute("INSERT INTO build256_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, actor, dumps(payload), previous, event_hash, at))
        try:
            self.audit.log("build256_" + event_type, object_type, object_id, case_id, payload)
        except Exception:
            pass

    @staticmethod
    def detect_script(value: str) -> str:
        counts = {"hebrew": 0, "arabic": 0, "cyrillic": 0, "latin": 0, "other": 0}
        for ch in value:
            cp = ord(ch)
            if 0x0590 <= cp <= 0x05FF: counts["hebrew"] += 1
            elif 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F: counts["arabic"] += 1
            elif 0x0400 <= cp <= 0x052F: counts["cyrillic"] += 1
            elif "LATIN" in unicodedata.name(ch, ""): counts["latin"] += 1
            elif ch.isalpha(): counts["other"] += 1
        return max(counts, key=counts.get) if any(counts.values()) else "unknown"

    @staticmethod
    def _clean_spaces(value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^0-9a-zA-Z]+", " ", value)).strip().lower()

    @classmethod
    def transliterate(cls, value: str) -> str:
        src = unicodedata.normalize("NFKD", _text(value, 2000)).casefold()
        out: list[str] = []
        for ch in src:
            if unicodedata.combining(ch):
                continue
            if ch in HEBREW: out.append(HEBREW[ch])
            elif ch in ARABIC: out.append(ARABIC[ch])
            elif ch in CYRILLIC: out.append(CYRILLIC[ch])
            elif ch.isascii(): out.append(ch)
            elif ch.isspace(): out.append(" ")
        return cls._clean_spaces("".join(out))

    @classmethod
    def normalize_name(cls, value: str) -> str:
        return cls.transliterate(value)

    @classmethod
    def _legal_form(cls, normalized: str) -> str:
        tokens = normalized.split()
        hits: list[str] = []
        for form in sorted(LEGAL_FORMS, key=len, reverse=True):
            if normalized == form or normalized.endswith(" " + form):
                hits.append(form)
                break
        return hits[0] if hits else ""

    @classmethod
    def _core_name(cls, normalized: str) -> str:
        form = cls._legal_form(normalized)
        if form and normalized.endswith(form):
            core = normalized[: -len(form)].strip()
            return core or normalized
        return normalized

    @staticmethod
    def _domain(value: str) -> str:
        raw = _text(value, 500).lower()
        if not raw:
            return ""
        try:
            parsed = urlsplit(raw if "://" in raw else "https://" + raw)
            host = (parsed.hostname or "").strip(".")
        except Exception:
            host = raw.split("/")[0].split(":")[0]
        return host[4:] if host.startswith("www.") else host

    @staticmethod
    def _mask_identifier(value: str) -> str:
        clean = re.sub(r"\s+", "", _text(value, 500))
        if len(clean) <= 4:
            return "•" * len(clean)
        return "•" * min(12, max(4, len(clean) - 4)) + clean[-4:]

    @staticmethod
    def _identifier_hash(identifier_type: str, value: str) -> str:
        canonical = re.sub(r"[^A-Z0-9]", "", _text(value, 500).upper())
        return hashlib.sha256(f"{identifier_type}:{canonical}".encode("utf-8")).hexdigest()

    def _entity(self, influence_entity_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM influence_entities_251 WHERE influence_entity_id=?", (influence_entity_id,))
        if not row:
            raise KeyError(influence_entity_id)
        item = dict(row)
        item["identifiers"] = _loads(item.get("identifiers_json"), {})
        return item

    def stage_entity(self, *, case_id: str, influence_entity_id: str, identifiers: dict[str, str] | None, actor: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"ENTITY PROFILE 256 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        entity = self._entity(influence_entity_id)
        if entity["case_id"] != case_id:
            raise ValueError("cross-case entity staging prohibited")
        if entity["entity_type"] not in ALLOWED_ENTITY_TYPES:
            self._event(case_id, "entity_scope_rejected", "entity", influence_entity_id, {"entity_type": entity["entity_type"], "reason": "organization_only"}, actor)
            raise PermissionError("Build 256 automatic entity resolution is restricted to organizations/legal entities; person entities require separate human handling")
        existing = self.db.one("SELECT * FROM entity_profiles_256 WHERE case_id=? AND influence_entity_id=?", (case_id, influence_entity_id))
        if existing:
            return {**dict(existing), "idempotent": True, "identifiers": self.identifiers(profile_id=existing["profile_id"])}
        name = _text(entity["display_name"], 1000)
        normalized = self.normalize_name(name)
        if len(normalized) < 2:
            raise ValueError("name cannot be normalized")
        transliterated = self.transliterate(name)
        domain = self._domain(entity.get("official_domain", ""))
        combined = dict(entity.get("identifiers") or {})
        combined.update(dict(identifiers or {}))
        for key, value in combined.items():
            itype = _text(key, 80).lower()
            if _text(value, 500) and itype in SENSITIVE_IDENTIFIER_TYPES:
                self._event(case_id, "identifier_rejected", "entity", influence_entity_id, {"identifier_type": itype, "reason": "sensitive_private_identifier"}, actor)
                raise PermissionError(f"sensitive/private identifier type rejected: {itype}")
        pid, at = new_id("entprof256"), now_ts()
        payload = {
            "profile_id": pid, "case_id": case_id, "influence_entity_id": influence_entity_id, "entity_type": entity["entity_type"],
            "jurisdiction": _text(entity.get("jurisdiction"), 200), "display_name": name, "detected_script": self.detect_script(name),
            "normalized_name": normalized, "transliterated_name": transliterated, "legal_form_normalized": self._legal_form(normalized),
            "official_domain_normalized": domain, "pii_class": "organization_public_identity", "raw_sensitive_identifier_storage": 0,
            "created_by": actor, "created_at": at,
        }
        self.db.execute("INSERT INTO entity_profiles_256 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (pid, case_id, influence_entity_id, entity["entity_type"], payload["jurisdiction"], name, payload["detected_script"], normalized, transliterated, payload["legal_form_normalized"], domain, payload["pii_class"], 0, actor, at, _hash(payload)))
        stored = 0
        for key, value in combined.items():
            itype = _text(key, 80).lower()
            val = _text(value, 500)
            if not val:
                continue
            if itype not in ALLOWED_IDENTIFIER_TYPES:
                continue
            digest = self._identifier_hash(itype, val)
            iid = new_id("entid256")
            ipayload = {"identifier_id": iid, "case_id": case_id, "profile_id": pid, "identifier_type": itype, "identifier_hash": digest, "masked_value": self._mask_identifier(val), "value_class": "public_organization_identifier", "source_class": "case_supplied_or_inherited_public_id", "created_at": at}
            self.db.execute("INSERT OR IGNORE INTO entity_identifiers_256 VALUES(?,?,?,?,?,?,?,?,?,?)", (iid, case_id, pid, itype, digest, ipayload["masked_value"], ipayload["value_class"], ipayload["source_class"], at, _hash(ipayload)))
            stored += 1
        self._event(case_id, "entity_profile_staged", "entity_profile", pid, {"entity_type": entity["entity_type"], "detected_script": payload["detected_script"], "identifier_count": stored, "raw_sensitive_identifier_storage": 0, "network_used": False}, actor)
        return {**payload, "identifiers": self.identifiers(profile_id=pid), "idempotent": False}

    def identifiers(self, *, profile_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.all("SELECT identifier_id,identifier_type,identifier_hash,masked_value,value_class,source_class,created_at FROM entity_identifiers_256 WHERE profile_id=? ORDER BY identifier_type,identifier_id", (profile_id,))]

    def profiles(self, *, case_id: str) -> list[dict[str, Any]]:
        rows = []
        for row in self.db.all("SELECT * FROM entity_profiles_256 WHERE case_id=? ORDER BY created_at,profile_id", (case_id,)):
            item = dict(row)
            item["identifiers"] = self.identifiers(profile_id=item["profile_id"])
            rows.append(item)
        return rows

    def _identifier_sets(self, profile_id: str) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for row in self.db.all("SELECT identifier_type,identifier_hash FROM entity_identifiers_256 WHERE profile_id=?", (profile_id,)):
            result.setdefault(row["identifier_type"], set()).add(row["identifier_hash"])
        return result

    def _pair_score(self, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        left_core, right_core = self._core_name(left["normalized_name"]), self._core_name(right["normalized_name"])
        name_similarity = SequenceMatcher(None, left_core, right_core).ratio()
        translit_similarity = SequenceMatcher(None, left["transliterated_name"], right["transliterated_name"]).ratio()
        lids, rids = self._identifier_sets(left["profile_id"]), self._identifier_sets(right["profile_id"])
        overlap = 0
        conflict = 0
        for key in set(lids) & set(rids):
            if lids[key] & rids[key]: overlap += 1
            elif lids[key] and rids[key]: conflict += 1
        domain_match = bool(left["official_domain_normalized"] and left["official_domain_normalized"] == right["official_domain_normalized"])
        jurisdiction_match = bool(left["jurisdiction"] and right["jurisdiction"] and left["jurisdiction"].casefold() == right["jurisdiction"].casefold())
        legal_form_match = bool(left["legal_form_normalized"] and left["legal_form_normalized"] == right["legal_form_normalized"])
        score = max(name_similarity, translit_similarity) * 0.55 + (0.25 if overlap else 0.0) + (0.12 if domain_match else 0.0) + (0.05 if jurisdiction_match else 0.0) + (0.03 if legal_form_match else 0.0)
        if conflict:
            score -= 0.35
        score = round(max(0.0, min(1.0, score)), 4)
        if conflict:
            suggested = "possible_distinct_identifier_conflict"
        elif overlap and score >= 0.70:
            suggested = "strong_same_entity_candidate"
        elif score >= 0.78:
            suggested = "same_entity_candidate"
        elif score >= 0.58:
            suggested = "abstain_needs_more_evidence"
        else:
            suggested = "likely_distinct_candidate"
        return {"name_similarity": round(name_similarity,4), "transliteration_similarity": round(translit_similarity,4), "identifier_overlap": overlap, "identifier_conflict": conflict, "domain_match": domain_match, "jurisdiction_match": jurisdiction_match, "legal_form_match": legal_form_match, "composite_score": score, "suggested_class": suggested}

    def generate_candidates(self, *, case_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"ENTITY MATCH 256 {case_id} GENERIEREN":
            raise PermissionError("explicit approval required")
        profiles = self.profiles(case_id=case_id)[:200]
        created: list[dict[str, Any]] = []
        pairs = 0
        for i, left in enumerate(profiles):
            for right in profiles[i+1:]:
                if pairs >= 1000:
                    break
                pairs += 1
                lp, rp = left["profile_id"], right["profile_id"]
                existing = self.db.one("SELECT * FROM entity_match_candidates_256 WHERE case_id=? AND left_profile_id=? AND right_profile_id=?", (case_id, lp, rp))
                if existing:
                    continue
                score = self._pair_score(left, right)
                cid, at = new_id("entmatch256"), now_ts()
                payload = {"candidate_id": cid, "case_id": case_id, "left_profile_id": lp, "right_profile_id": rp, "left_entity_id": left["influence_entity_id"], "right_entity_id": right["influence_entity_id"], **score, "candidate_only": True, "created_by": actor, "created_at": at}
                self.db.execute("INSERT INTO entity_match_candidates_256 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid, case_id, lp, rp, left["influence_entity_id"], right["influence_entity_id"], score["name_similarity"], score["transliteration_similarity"], score["identifier_overlap"], score["identifier_conflict"], 1 if score["domain_match"] else 0, 1 if score["jurisdiction_match"] else 0, 1 if score["legal_form_match"] else 0, score["composite_score"], score["suggested_class"], 1, actor, at, _hash(payload)))
                created.append(payload)
            if pairs >= 1000:
                break
        self._event(case_id, "entity_match_candidates_generated", "case", case_id, {"profiles_considered": len(profiles), "pairs_considered": pairs, "created": len(created), "pair_cap": 1000, "network_used": False, "automatic_merge": False}, actor)
        return {"profiles_considered": len(profiles), "pairs_considered": pairs, "created_count": len(created), "candidates": created, "automatic_merge": False, "network_used": False}

    def candidates(self, *, case_id: str) -> list[dict[str, Any]]:
        query = """SELECT c.*,r.decision review_decision,r.canonical_entity_id,r.reviewer,r.reviewed_at,
                  l.display_name left_name,rp.display_name right_name
                  FROM entity_match_candidates_256 c
                  JOIN entity_profiles_256 l ON l.profile_id=c.left_profile_id
                  JOIN entity_profiles_256 rp ON rp.profile_id=c.right_profile_id
                  LEFT JOIN entity_match_reviews_256 r ON r.candidate_id=c.candidate_id
                  WHERE c.case_id=? ORDER BY c.composite_score DESC,c.created_at,c.candidate_id"""
        return [dict(x) for x in self.db.all(query, (case_id,))]

    def review_candidate(self, *, candidate_id: str, decision: str, canonical_entity_id: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM entity_match_candidates_256 WHERE candidate_id=?", (candidate_id,))
        if not row:
            raise KeyError(candidate_id)
        if confirmation != f"ENTITY MATCH REVIEW 256 {candidate_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == row["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"same_entity", "distinct_entity", "needs_more_evidence"}:
            raise ValueError("invalid decision")
        rationale = _text(rationale, 5000)
        if len(rationale) < 15:
            raise ValueError("substantive rationale required")
        canonical = _text(canonical_entity_id, 200)
        if decision == "same_entity" and canonical not in {row["left_entity_id"], row["right_entity_id"]}:
            raise ValueError("canonical entity must be one of candidate entities")
        if decision != "same_entity":
            canonical = ""
        rid, at = new_id("entrev256"), now_ts()
        payload = {"review_id": rid, "case_id": row["case_id"], "candidate_id": candidate_id, "decision": decision, "canonical_entity_id": canonical, "rationale": rationale, "reviewer": reviewer, "reviewed_at": at}
        self.db.execute("INSERT INTO entity_match_reviews_256 VALUES(?,?,?,?,?,?,?,?,?)", (rid, row["case_id"], candidate_id, decision, canonical, rationale, reviewer, at, _hash(payload)))
        binding = None
        if decision == "same_entity":
            alias = row["right_entity_id"] if canonical == row["left_entity_id"] else row["left_entity_id"]
            bid = new_id("entbind256")
            bpayload = {"binding_id": bid, "case_id": row["case_id"], "canonical_entity_id": canonical, "alias_entity_id": alias, "review_id": rid, "binding_class": "reviewed_same_entity_alias", "created_at": at}
            self.db.execute("INSERT INTO entity_alias_bindings_256 VALUES(?,?,?,?,?,?,?,?)", (bid, row["case_id"], canonical, alias, rid, "reviewed_same_entity_alias", at, _hash(bpayload)))
            binding = bpayload
        self._event(row["case_id"], "entity_match_reviewed", "entity_match_candidate", candidate_id, {"decision": decision, "binding_created": bool(binding), "underlying_kernel_merge": False, "reviewer_independent": True}, reviewer)
        return {**payload, "binding": binding, "underlying_kernel_merge": False}

    def stage_training_candidate_from_review(self, *, review_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        review = self.db.one("SELECT * FROM entity_match_reviews_256 WHERE review_id=?", (review_id,))
        if not review:
            raise KeyError(review_id)
        case_id = review["case_id"]
        if confirmation != f"AI TRAINING CANDIDATE 256 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        cand = self.db.one("SELECT * FROM entity_match_candidates_256 WHERE candidate_id=?", (review["candidate_id"],))
        left = self.db.one("SELECT * FROM entity_profiles_256 WHERE profile_id=?", (cand["left_profile_id"],))
        right = self.db.one("SELECT * FROM entity_profiles_256 WHERE profile_id=?", (cand["right_profile_id"],))
        instruction = "Resolve whether two organization records represent the same legal/institutional entity. Use transliteration and public identifiers, abstain when evidence is insufficient, and never merge automatically."
        response = f"decision={review['decision']}; left={left['transliterated_name']}; right={right['transliterated_name']}; identifier_overlap={cand['identifier_overlap']}; identifier_conflict={cand['identifier_conflict']}"
        example = self.training.add_example(case_id=case_id, instruction=instruction, response=response, context={"build": "256.0", "candidate_id": cand["candidate_id"], "review_id": review_id, "jurisdiction_left": left["jurisdiction"], "jurisdiction_right": right["jurisdiction"], "raw_identifiers_in_context": False, "human_resolution_review": True}, evidence_refs=(), language="multi", source_type="build256_reviewed_entity_resolution", source_ref=review_id, created_by=actor, confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")
        self._event(case_id, "training_candidate_staged", "training_example", example["example_id"], {"review_id": review_id, "review_status": example["review_status"], "redaction_status": example["redaction_status"], "automatic_approval": False, "automatic_adapter_activation": False}, actor)
        return {"example": example, "automatic_approval": False, "automatic_dataset_inclusion": False, "automatic_model_activation": False, "automatic_adapter_activation": False}

    def benchmarks(self) -> list[dict[str, Any]]:
        return [dict(x) for x in self.db.all("SELECT * FROM ai_entity_benchmarks_256 ORDER BY benchmark_id")]

    def record_ai_evaluation(self, *, case_id: str, benchmark_id: str, predicted_left_transliteration: str, predicted_right_transliteration: str, predicted_resolution: str, model_or_ruleset: str, evaluated_by: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"AI BENCHMARK 256 {case_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        b = self.db.one("SELECT * FROM ai_entity_benchmarks_256 WHERE benchmark_id=?", (benchmark_id,))
        if not b:
            raise KeyError(benchmark_id)
        left = self.normalize_name(predicted_left_transliteration)
        right = self.normalize_name(predicted_right_transliteration)
        lsim = SequenceMatcher(None, left, self.normalize_name(b["expected_left_transliteration"])).ratio()
        rsim = SequenceMatcher(None, right, self.normalize_name(b["expected_right_transliteration"])).ratio()
        decision_match = predicted_resolution == b["expected_resolution"]
        passed = bool(lsim >= 0.82 and rsim >= 0.82 and decision_match)
        eid, at = new_id("aient256"), now_ts()
        payload = {"evaluation_id": eid, "case_id": case_id, "benchmark_id": benchmark_id, "predicted_left_transliteration": left, "predicted_right_transliteration": right, "predicted_resolution": predicted_resolution, "left_similarity": round(lsim,4), "right_similarity": round(rsim,4), "decision_match": decision_match, "passed": passed, "model_or_ruleset": _text(model_or_ruleset, 300), "evaluated_by": evaluated_by, "evaluated_at": at}
        self.db.execute("INSERT INTO ai_entity_evaluations_256 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (eid, case_id, benchmark_id, left, right, predicted_resolution, payload["left_similarity"], payload["right_similarity"], 1 if decision_match else 0, 1 if passed else 0, payload["model_or_ruleset"], evaluated_by, at, _hash(payload)))
        return payload

    def ai_metrics(self, *, case_id: str) -> dict[str, Any]:
        curated = int(self.db.one("SELECT COUNT(*) n FROM ai_entity_benchmarks_256 WHERE review_status='curated_reviewed'")["n"])
        families = int(self.db.one("SELECT COUNT(DISTINCT task_family) n FROM ai_entity_benchmarks_256 WHERE review_status='curated_reviewed'")["n"])
        scripts = len({self.detect_script(x["left_name"]) for x in self.benchmarks()} | {self.detect_script(x["right_name"]) for x in self.benchmarks()})
        evals = self.db.all("SELECT passed FROM ai_entity_evaluations_256 WHERE case_id=?", (case_id,))
        training_candidates = int(self.db.one("SELECT COUNT(*) n FROM training_examples_228 WHERE case_id=? AND source_type='build256_reviewed_entity_resolution'", (case_id,))["n"])
        approved = int(self.db.one("SELECT COUNT(*) n FROM training_examples_228 WHERE case_id=? AND source_type='build256_reviewed_entity_resolution' AND review_status='approved' AND redaction_status='clean'", (case_id,))["n"])
        return {"curated_reviewed_benchmarks": curated, "task_family_coverage": families, "script_coverage": scripts, "evaluations": len(evals), "evaluation_pass_rate": round(sum(int(x["passed"]) for x in evals)/len(evals),4) if evals else None, "build256_training_candidates": training_candidates, "build256_approved_clean_training_examples": approved, "false_merge_false_split_cases_present": bool(self.db.one("SELECT COUNT(*) n FROM ai_entity_benchmarks_256 WHERE task_family IN ('false_merge','false_split','identifier_conflict')")["n"] >= 6), "auto_model_activation": False, "auto_adapter_activation": False}

    def opsec_metrics(self, *, case_id: str) -> dict[str, Any]:
        total = int(self.db.one("SELECT COUNT(*) n FROM entity_opsec_controls_256")["n"])
        verified = int(self.db.one("SELECT COUNT(*) n FROM entity_opsec_controls_256 WHERE review_status='verified'")["n"])
        raw_sensitive = int(self.db.one("SELECT COUNT(*) n FROM entity_profiles_256 WHERE case_id=? AND raw_sensitive_identifier_storage!=0", (case_id,))["n"])
        person_profiles = int(self.db.one("SELECT COUNT(*) n FROM entity_profiles_256 WHERE case_id=? AND entity_type='person'", (case_id,))["n"])
        cross_case = int(self.db.one("SELECT COUNT(*) n FROM entity_match_candidates_256 c JOIN entity_profiles_256 l ON l.profile_id=c.left_profile_id JOIN entity_profiles_256 r ON r.profile_id=c.right_profile_id WHERE c.case_id=? AND (l.case_id!=c.case_id OR r.case_id!=c.case_id)", (case_id,))["n"])
        return {"verified_controls": verified, "control_coverage": round(verified/total,4) if total else 0.0, "raw_sensitive_identifier_records": raw_sensitive, "person_profiles_in_automated_resolution": person_profiles, "cross_case_candidates": cross_case, "raw_identifier_values_rendered": 0, "biometric_resolution": 0, "automated_source_contact": 0, "network_requests": 0, "autonomous_network_changes": 0}

    def capabilities(self) -> dict[str, Any]:
        return {"unicode_nfkd_normalization": True, "hebrew_transliteration": True, "arabic_transliteration": True, "cyrillic_transliteration": True, "latin_legal_form_normalization": True, "public_identifier_hash_matching": True, "masked_identifier_display": True, "case_scoped_candidate_generation": True, "independent_resolution_review": True, "automatic_merge": False, "facial_recognition": False, "network_required": False}

    def crosscut_release_gate(self, *, case_id: str) -> dict[str, Any]:
        ai = self.ai_metrics(case_id=case_id)
        op = self.opsec_metrics(case_id=case_id)
        parent = self.parent_documents.crosscut_release_gate(case_id=case_id)
        caps = self.capabilities()
        main_ready = bool(caps["hebrew_transliteration"] and caps["arabic_transliteration"] and caps["cyrillic_transliteration"] and caps["public_identifier_hash_matching"] and caps["independent_resolution_review"] and not caps["automatic_merge"])
        ai_ready = bool(ai["curated_reviewed_benchmarks"] >= 20 and ai["task_family_coverage"] >= 6 and ai["false_merge_false_split_cases_present"] and not ai["auto_model_activation"] and not ai["auto_adapter_activation"])
        opsec_ready = bool(op["verified_controls"] >= 12 and op["control_coverage"] == 1.0 and op["raw_sensitive_identifier_records"] == 0 and op["person_profiles_in_automated_resolution"] == 0 and op["cross_case_candidates"] == 0 and op["raw_identifier_values_rendered"] == 0 and op["biometric_resolution"] == 0 and op["automated_source_contact"] == 0 and op["network_requests"] == 0 and op["autonomous_network_changes"] == 0)
        parent_ready = bool(parent.get("release_ready"))
        return {"build": self.BUILD, "main_goal_ready": main_ready, "ai_delta_ready": ai_ready, "opsec_delta_ready": opsec_ready, "parent_255_gate_ready": parent_ready, "release_ready": bool(main_ready and ai_ready and opsec_ready and parent_ready), "capabilities": caps, "policy": "Build 256 resolves organization/legal-entity aliases locally across scripts; similarity is candidate evidence only, raw sensitive identifiers are not stored, and same-entity bindings require independent human review."}

    def status(self, *, case_id: str) -> dict[str, Any]:
        return {"build": self.BUILD, "profiles": self.profiles(case_id=case_id), "candidates": self.candidates(case_id=case_id), "bindings": [dict(x) for x in self.db.all("SELECT * FROM entity_alias_bindings_256 WHERE case_id=? ORDER BY created_at,binding_id", (case_id,))], "ai": self.ai_metrics(case_id=case_id), "opsec": self.opsec_metrics(case_id=case_id), "gate": self.crosscut_release_gate(case_id=case_id)}

    def co_ai_context(self, case_id: str) -> dict[str, Any]:
        return {"entity_resolution_256": {"reviewed_same_entity_bindings": [dict(x) for x in self.db.all("SELECT canonical_entity_id,alias_entity_id,binding_class FROM entity_alias_bindings_256 WHERE case_id=?", (case_id,))], "pending_candidates_not_facts": [{"candidate_id": x["candidate_id"], "left_entity_id": x["left_entity_id"], "right_entity_id": x["right_entity_id"], "score": x["composite_score"], "suggested_class": x["suggested_class"]} for x in self.candidates(case_id=case_id) if not x.get("review_decision")][:100], "rules": ["Transliteration similarity is not identity proof.", "Identifier conflicts block automatic same-entity inference.", "Only independently reviewed same_entity decisions become alias bindings.", "Underlying kernel entities are not automatically merged."]}}

    def render_workspace_panel(self, *, case_id: str, csrf: str = "") -> str:
        esc = html.escape
        status = self.status(case_id=case_id)
        influence_entities = [dict(x) for x in self.db.all("SELECT influence_entity_id,display_name,entity_type,jurisdiction FROM influence_entities_251 WHERE case_id=? ORDER BY display_name", (case_id,)) if x["entity_type"] in ALLOWED_ENTITY_TYPES]
        options = "".join(f"<option value='{esc(x['influence_entity_id'])}'>{esc(x['display_name'])} · {esc(x['entity_type'])} · {esc(x['jurisdiction'])}</option>" for x in influence_entities)
        profile_rows = "".join(f"<tr><td>{esc(p['display_name'])}</td><td>{esc(p['detected_script'])}</td><td>{esc(p['transliterated_name'])}</td><td>{esc(p['jurisdiction'])}</td><td>{', '.join(esc(i['identifier_type']+':'+i['masked_value']) for i in p['identifiers'])}</td><td><code>{esc(p['profile_id'])}</code></td></tr>" for p in status["profiles"]) or "<tr><td colspan='6' class='muted'>Noch keine Organisationsprofile für Build 256 gestaged.</td></tr>"
        candidate_rows = "".join(f"<tr><td>{esc(c['left_name'])}</td><td>{esc(c['right_name'])}</td><td>{float(c['composite_score']):.2f}</td><td>{esc(c['suggested_class'])}</td><td>{esc(c.get('review_decision') or 'pending')}</td><td><code>{esc(c['candidate_id'])}</code></td></tr>" for c in status["candidates"]) or "<tr><td colspan='6' class='muted'>Noch keine Match-Kandidaten.</td></tr>"
        ai, op, gate = status["ai"], status["opsec"], status["gate"]
        return f"""<section class='cockpit244'><h2>Influence &amp; Funding Investigation Pack · International Entity Resolution 256</h2>
<div class='notice'>Build 256 normalisiert Organisationsnamen, transliteriert Hebräisch/Arabisch/Kyrillisch/Latin und vergleicht öffentliche Organisations-Identifier. Ähnlichkeit erzeugt ausschließlich Kandidaten – niemals einen automatischen Merge.</div>
<div class='metrics'><div class='metric'><div class='label'>Profiles</div><div class='value'>{len(status['profiles'])}</div></div><div class='metric'><div class='label'>Candidates</div><div class='value'>{len(status['candidates'])}</div></div><div class='metric'><div class='label'>Reviewed bindings</div><div class='value'>{len(status['bindings'])}</div></div><div class='metric'><div class='label'>Release gate</div><div class='value'>{'PASS' if gate['release_ready'] else 'BLOCK'}</div></div></div>
<div class='grid'><div class='card'><h3>Organisationsprofil normalisieren</h3><form method='post' action='/build256/stage'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='influence_entity_id' required>{options}</select><textarea name='identifiers' placeholder='Optionale öffentliche IDs: lei=...; commercial_register=...; us_uei=...'></textarea><button>Lokales Profil erzeugen</button></form><p class='muted'>Personenentitäten und private/sensitive Identifier werden von diesem automatisierten Modul abgewiesen. Identifier werden in 256 nur gehasht + maskiert gespeichert.</p></div>
<div class='card'><h3>Match-Kandidaten</h3><form method='post' action='/build256/generate'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><button>Kandidaten lokal berechnen</button></form><p class='muted'>Max. 200 Profile / 1000 Paare pro Lauf; kein Netzwerk, kein automatischer Merge.</p></div>
<div class='card'><h3>Vier-Augen-Review</h3><form method='post' action='/build256/review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='candidate_id' placeholder='Candidate-ID' required><select name='decision'><option>same_entity</option><option>distinct_entity</option><option>needs_more_evidence</option></select><input name='canonical_entity_id' placeholder='Canonical Entity-ID (nur bei same_entity)'><textarea name='rationale' placeholder='Unabhängige Begründung' required></textarea><button>Review speichern</button></form></div>
<div class='card'><h3>AI-Trainingskandidat</h3><form method='post' action='/build256/training-candidate'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='review_id' placeholder='Review-ID' required><button>Reviewtes Beispiel an Build 228 übergeben</button></form><p class='muted'>Bleibt pending; kein automatisches Dataset, Modell oder Adapter.</p></div></div>
<div class='card'><h3>Normalisierte Profile</h3><div class='table-wrap'><table><tr><th>Name</th><th>Script</th><th>Transliteration</th><th>Jurisdiktion</th><th>Maskierte IDs</th><th>Profile-ID</th></tr>{profile_rows}</table></div></div>
<div class='card'><h3>Resolution-Kandidaten</h3><div class='table-wrap'><table><tr><th>Links</th><th>Rechts</th><th>Score</th><th>Vorschlag</th><th>Review</th><th>ID</th></tr>{candidate_rows}</table></div></div>
<div class='grid'><div class='card'><h3>AI-Delta 256</h3><p><b>{ai['curated_reviewed_benchmarks']}</b> reviewte Benchmarks · {ai['task_family_coverage']} Aufgabenfamilien · False-Merge/False-Split/Identifier-Konflikte enthalten.</p><p>Reviewte Resolution-Entscheidungen können kontrolliert als pending Trainingskandidaten an Build 228 übergeben werden.</p></div><div class='card'><h3>OPSEC-Delta 256</h3><p>{int(op['control_coverage']*100)}% Control-Coverage · rohe sensitive Identifier: <b>{op['raw_sensitive_identifier_records']}</b> · Personenprofile im automatischen Resolver: <b>{op['person_profiles_in_automated_resolution']}</b> · Cross-Case-Kandidaten: <b>{op['cross_case_candidates']}</b>.</p></div></div>
<div class='notice warn'>Transliteration, Namensähnlichkeit, gleiche Domains oder institutionelle Nähe sind keine Identitätsbeweise. Ein same_entity-Binding benötigt einen unabhängigen Review und verschmilzt die zugrunde liegenden Kernel-Objekte nicht automatisch.</div></section>"""
