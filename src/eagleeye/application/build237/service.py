from __future__ import annotations

import hashlib
import html
import json
import re
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse, urlsplit, urlunsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts

_HANDLE = re.compile(r"[^\w.\-]+", re.UNICODE)
_ALLOWED_REL = {"mentions", "reply_to", "reposts", "references", "cooccurs_with", "follows_candidate", "associated_with"}


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


def _text(value: Any, limit: int = 20_000) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except Exception:
        return 0.0


def _norm_handle(value: str) -> str:
    v = _text(value, 200).casefold().lstrip("@").strip()
    return _HANDLE.sub("", v)[:160]


def _canonical_url(value: str) -> str:
    raw = _text(value, 4000)
    if not raw:
        return ""
    p = urlsplit(raw)
    if p.scheme.casefold() not in {"http", "https"} or not p.hostname:
        raise ValueError("public http(s) profile URL required")
    netloc = p.hostname.casefold()
    if p.port and not ((p.scheme == "http" and p.port == 80) or (p.scheme == "https" and p.port == 443)):
        netloc += f":{p.port}"
    return urlunsplit((p.scheme.casefold(), netloc, p.path or "/", p.query, ""))


def _sim(a: str, b: str) -> float:
    a, b = " ".join(_text(a, 1000).casefold().split()), " ".join(_text(b, 1000).casefold().split())
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


class Build237SocialIntelligence3Service:
    """Review-first social intelligence consolidation.

    Build 237 normalizes already captured or manually entered PUBLIC social data,
    creates cross-platform identity and relationship candidates, links reviewed
    material into the Build-235 kernel, and stages reviewed decisions for Build-228
    training. It does not authenticate to social platforms, bypass access controls,
    interact with accounts, or autonomously collect network data.
    """

    BUILD = "237.0"

    def __init__(self, db: Any, audit: Any, *, source_fabric: Any, kernel: Any, multilingual: Any, training: Any, conversation: Any, actor: str = "local-analyst") -> None:
        self.db, self.audit = db, audit
        self.source_fabric, self.kernel, self.multilingual, self.training, self.conversation = source_fabric, kernel, multilingual, training, conversation
        self.actor = actor
        self.conversation._social_intelligence_v3 = self

    # ---------- public profile observations ----------
    def add_profile_observation(self, *, case_id: str, platform: str, source_key: str, handle: str, display_name: str = "", profile_url: str = "", bio: str = "", language: str = "und", aliases: Sequence[str] = (), location: str = "", website: str = "", follower_count: int = -1, following_count: int = -1, observed_at: str = "", confidence: float = .5, evidence_refs: Sequence[str] = (), provenance: Mapping[str, Any] | None = None, created_by: str, confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"SOCIAL PROFILE 237 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        p = _text(platform, 80).casefold()
        h = _norm_handle(handle)
        if not p or not h:
            raise ValueError("platform and handle required")
        url = _canonical_url(profile_url) if profile_url else ""
        self._assert_source_allowed(source_key)
        existing = self.db.one("SELECT * FROM social_profiles_237 WHERE case_id=? AND platform=? AND handle_normalized=?", (case_id, p, h))
        if existing:
            profile_id = existing["profile_id"]
        else:
            profile_id, now = new_id("socialprofile237"), now_ts()
            payload = {"profile_id": profile_id, "case_id": case_id, "platform": p, "source_key": source_key, "handle_normalized": h, "canonical_profile_url": url, "created_by": created_by, "created_at": now}
            self.db.execute("INSERT INTO social_profiles_237 VALUES(?,?,?,?,?,?,?,?,?,?)", (profile_id, case_id, p, _text(source_key, 200), h, url, "", created_by, now, _hash(payload)))
        oid, now = new_id("socialobs237"), now_ts()
        obs = observed_at or now
        alias_list = list(dict.fromkeys(_text(x, 300) for x in [handle, display_name, *aliases] if _text(x, 300)))[:60]
        refs = list(dict.fromkeys(_text(x, 300) for x in evidence_refs if _text(x, 300)))[:100]
        prov = {**dict(provenance or {}), "public_only": True, "automatic_collection": False, "source_key": source_key}
        payload = {"observation_id": oid, "profile_id": profile_id, "case_id": case_id, "handle": _text(handle, 200), "display_name": _text(display_name, 500), "bio": _text(bio, 12_000), "language": _text(language, 20) or "und", "aliases": alias_list, "location": _text(location, 500), "website": _text(website, 3000), "follower_count": int(follower_count), "following_count": int(following_count), "observed_at": obs, "confidence": _clamp(confidence), "evidence_refs": refs, "provenance": prov, "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO social_profile_observations_237 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (oid, profile_id, case_id, payload["handle"], payload["display_name"], payload["bio"], payload["language"], dumps(alias_list), payload["location"], payload["website"], payload["follower_count"], payload["following_count"], obs, payload["confidence"], dumps(refs), dumps(prov), created_by, now, _hash(payload)))
        self._event(case_id, "social_profile_observed", "social_profile", profile_id, {"observation_id": oid, "platform": p, "public_only": True}, created_by)
        return {**payload, "platform": p, "source_key": source_key, "profile_url": url, "review_status": "pending", "identity_confirmed": False}

    def review_profile_observation(self, *, observation_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self._observation(observation_id)
        if confirmation != f"SOCIAL PROFILE REVIEW 237 {observation_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == row["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"accepted", "rejected", "deferred"}:
            raise ValueError("invalid decision")
        if len(_text(rationale, 5000)) < 12:
            raise ValueError("substantive rationale required")
        if self.db.one("SELECT review_id FROM social_profile_reviews_237 WHERE observation_id=?", (observation_id,)):
            raise ValueError("observation already reviewed")
        rid, now = new_id("socialprofilereview237"), now_ts()
        payload = {"review_id": rid, "observation_id": observation_id, "profile_id": row["profile_id"], "case_id": row["case_id"], "decision": decision, "rationale": _text(rationale, 5000), "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO social_profile_reviews_237 VALUES(?,?,?,?,?,?,?,?,?)", (rid, observation_id, row["profile_id"], row["case_id"], decision, payload["rationale"], reviewer, now, _hash(payload)))
        self._event(row["case_id"], "social_profile_reviewed", "social_profile", row["profile_id"], {"observation_id": observation_id, "decision": decision}, reviewer)
        return payload

    # ---------- posts / timeline ----------
    def add_public_post(self, *, case_id: str, profile_id: str, source_key: str, content_original: str, canonical_url: str = "", platform_post_id: str = "", language: str = "und", published_at: str = "", observed_at: str = "", evidence_refs: Sequence[str] = (), provenance: Mapping[str, Any] | None = None, created_by: str, confirmation: str) -> dict[str, Any]:
        profile = self._profile(profile_id)
        if profile["case_id"] != case_id:
            raise ValueError("profile/case mismatch")
        if confirmation != f"SOCIAL POST 237 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        self._assert_source_allowed(source_key)
        text = _text(content_original, 50_000)
        if not text:
            raise ValueError("content required")
        url = _canonical_url(canonical_url) if canonical_url else ""
        content_hash = _hash({"profile_id": profile_id, "platform_post_id": _text(platform_post_id, 500), "url": url, "content": text})
        existing = self.db.one("SELECT * FROM social_posts_237 WHERE case_id=? AND profile_id=? AND content_sha256=?", (case_id, profile_id, content_hash))
        if existing:
            return {**existing, "idempotent": True}
        pid, now = new_id("socialpost237"), now_ts()
        refs = list(dict.fromkeys(_text(x, 300) for x in evidence_refs if _text(x, 300)))[:100]
        prov = {**dict(provenance or {}), "public_only": True, "automatic_collection": False, "source_key": source_key}
        payload = {"post_id": pid, "case_id": case_id, "profile_id": profile_id, "source_key": source_key, "platform_post_id": _text(platform_post_id, 500), "canonical_url": url, "content_original": text, "language": _text(language, 20) or "und", "published_at": _text(published_at, 80), "observed_at": observed_at or now, "evidence_refs": refs, "provenance": prov, "created_by": created_by, "created_at": now, "content_sha256": content_hash}
        self.db.execute("INSERT INTO social_posts_237 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (pid, case_id, profile_id, source_key, payload["platform_post_id"], url, text, payload["language"], payload["published_at"], payload["observed_at"], dumps(refs), dumps(prov), created_by, now, content_hash, _hash(payload)))
        self._event(case_id, "social_post_observed", "social_post", pid, {"profile_id": profile_id, "public_only": True}, created_by)
        return {**payload, "review_status": "pending", "idempotent": False}

    def review_post(self, *, post_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self._post(post_id)
        if confirmation != f"SOCIAL POST REVIEW 237 {post_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == row["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"accepted", "rejected", "deferred"}:
            raise ValueError("invalid decision")
        if len(_text(rationale, 5000)) < 12:
            raise ValueError("substantive rationale required")
        if self.db.one("SELECT review_id FROM social_post_reviews_237 WHERE post_id=?", (post_id,)):
            raise ValueError("post already reviewed")
        rid, now = new_id("socialpostreview237"), now_ts()
        payload = {"review_id": rid, "post_id": post_id, "case_id": row["case_id"], "decision": decision, "rationale": _text(rationale, 5000), "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO social_post_reviews_237 VALUES(?,?,?,?,?,?,?,?)", (rid, post_id, row["case_id"], decision, payload["rationale"], reviewer, now, _hash(payload)))
        if decision == "accepted":
            self._bind_profile(profile_id=row["profile_id"], actor=reviewer)
            binding = self.db.one("SELECT canonical_entity_object_id FROM social_kernel_bindings_237 WHERE profile_id=?", (row["profile_id"],))
            source = self.source_fabric.bind_source_to_case(case_id=row["case_id"], source_key=row["source_key"], actor=reviewer, confirmation=f"SOURCE FABRIC BIND 236 {row['case_id']} {row['source_key']}")
            ev = self.kernel.create_evidence(case_id=row["case_id"], title=f"Social post {row['profile_id']}", statement=row["content_original"], source_object_id=source["canonical_source_object_id"], confidence=.7, actor=reviewer, confirmation=f"KERNEL OBJECT 235 {row['case_id']} ANLEGEN")
            if binding:
                self.kernel.create_link(case_id=row["case_id"], source_object_id=ev["object_id"], relation_type="about", target_object_id=binding["canonical_entity_object_id"], confidence=.7, evidence_refs=[post_id], actor=reviewer, confirmation=f"KERNEL LINK 235 {row['case_id']} ANLEGEN")
            payload["canonical_evidence_object_id"] = ev["object_id"]
        self._event(row["case_id"], "social_post_reviewed", "social_post", post_id, {"decision": decision}, reviewer)
        return payload

    # ---------- cross-platform identity ----------
    def compare_profiles(self, *, left_profile_id: str, right_profile_id: str, created_by: str, confirmation: str) -> dict[str, Any]:
        left, right = self._profile(left_profile_id), self._profile(right_profile_id)
        if left["case_id"] != right["case_id"] or left_profile_id == right_profile_id:
            raise ValueError("profiles must be distinct and case-local")
        case_id = left["case_id"]
        if confirmation != f"SOCIAL IDENTITY 237 {case_id} VERGLEICHEN":
            raise PermissionError("explicit approval required")
        if left_profile_id > right_profile_id:
            left, right = right, left
            left_profile_id, right_profile_id = right_profile_id, left_profile_id
        existing = self.db.one("SELECT * FROM social_identity_candidates_237 WHERE case_id=? AND left_profile_id=? AND right_profile_id=?", (case_id, left_profile_id, right_profile_id))
        if existing:
            return self._identity_payload(existing)
        lo, ro = self._latest_accepted_observation(left_profile_id), self._latest_accepted_observation(right_profile_id)
        if not lo or not ro:
            raise PermissionError("accepted profile observations required")
        handle_sim = _sim(lo["handle"], ro["handle"])
        name_sim = _sim(lo["display_name"], ro["display_name"])
        aliases_l = set(_loads(lo["aliases_json"], [])); aliases_r = set(_loads(ro["aliases_json"], []))
        alias_overlap = len({x.casefold() for x in aliases_l} & {x.casefold() for x in aliases_r}) / max(1, min(len(aliases_l), len(aliases_r)))
        bio_sim = _sim(lo["bio"], ro["bio"])
        location_support = 1.0 if lo["location"] and ro["location"] and lo["location"].casefold() == ro["location"].casefold() else 0.0
        contradictions = []
        if lo["location"] and ro["location"] and lo["location"].casefold() != ro["location"].casefold():
            contradictions.append({"field": "location", "left": lo["location"], "right": ro["location"], "penalty": .08})
        if left["platform"] == right["platform"] and left["handle_normalized"] != right["handle_normalized"]:
            contradictions.append({"field": "same_platform_distinct_handle", "penalty": .12})
        score = _clamp(.34 * handle_sim + .25 * name_sim + .17 * alias_overlap + .12 * bio_sim + .12 * location_support - sum(float(x["penalty"]) for x in contradictions))
        band = "high" if score >= .78 and not contradictions else "medium" if score >= .58 else "low"
        state = "strong_candidate" if band == "high" else "review_candidate" if band == "medium" else "weak_candidate"
        cid, now = new_id("socialidentity237"), now_ts()
        signals = {"handle_similarity": round(handle_sim, 6), "display_name_similarity": round(name_sim, 6), "alias_overlap": round(alias_overlap, 6), "bio_similarity": round(bio_sim, 6), "location_support": location_support}
        payload = {"candidate_id": cid, "case_id": case_id, "left_profile_id": left_profile_id, "right_profile_id": right_profile_id, "signals": signals, "contradictions": contradictions, "score": round(score, 6), "confidence_band": band, "candidate_state": state, "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO social_identity_candidates_237 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (cid, case_id, left_profile_id, right_profile_id, dumps(signals), dumps(contradictions), payload["score"], band, state, created_by, now, _hash(payload)))
        self._event(case_id, "social_identity_candidate_created", "social_identity_candidate", cid, {"score": payload["score"], "automatic_merge": False}, created_by)
        return {**payload, "human_review_required": True, "automatic_merge": False}

    def review_identity_candidate(self, *, candidate_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self._identity(candidate_id)
        if confirmation != f"SOCIAL IDENTITY REVIEW 237 {candidate_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == row["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"match_candidate", "no_match", "uncertain"}:
            raise ValueError("invalid decision")
        if len(_text(rationale, 5000)) < 15:
            raise ValueError("substantive rationale required")
        if decision == "match_candidate" and (float(row["score"]) < .58 or _loads(row["contradictions_json"], [])):
            raise PermissionError("score/contradiction gate blocks match candidate")
        if self.db.one("SELECT review_id FROM social_identity_reviews_237 WHERE candidate_id=?", (candidate_id,)):
            raise ValueError("candidate already reviewed")
        kernel_link_id = ""
        if decision == "match_candidate":
            left_oid = self._bind_profile(profile_id=row["left_profile_id"], actor=reviewer)["canonical_entity_object_id"]
            right_oid = self._bind_profile(profile_id=row["right_profile_id"], actor=reviewer)["canonical_entity_object_id"]
            link = self.kernel.create_link(case_id=row["case_id"], source_object_id=left_oid, relation_type="same_as_candidate", target_object_id=right_oid, confidence=float(row["score"]), evidence_refs=[candidate_id], actor=reviewer, confirmation=f"KERNEL LINK 235 {row['case_id']} ANLEGEN")
            kernel_link_id = link["link_id"]
        rid, now = new_id("socialidentityreview237"), now_ts()
        payload = {"review_id": rid, "candidate_id": candidate_id, "case_id": row["case_id"], "decision": decision, "rationale": _text(rationale, 5000), "reviewer": reviewer, "reviewed_at": now, "kernel_link_id": kernel_link_id}
        self.db.execute("INSERT INTO social_identity_reviews_237 VALUES(?,?,?,?,?,?,?,?,?)", (rid, candidate_id, row["case_id"], decision, payload["rationale"], reviewer, now, kernel_link_id, _hash(payload)))
        self._event(row["case_id"], "social_identity_reviewed", "social_identity_candidate", candidate_id, {"decision": decision, "kernel_link_id": kernel_link_id, "automatic_merge": False}, reviewer)
        return {**payload, "automatic_merge": False, "kernel_link_requires_separate_review": bool(kernel_link_id)}

    # ---------- public relationship candidates ----------
    def add_relationship_candidate(self, *, case_id: str, actor_profile_id: str, relation_type: str, target_profile_id: str = "", target_label: str = "", evidence_refs: Sequence[str] = (), confidence: float = .5, observed_at: str = "", created_by: str, confirmation: str) -> dict[str, Any]:
        actor_profile = self._profile(actor_profile_id)
        if actor_profile["case_id"] != case_id:
            raise ValueError("actor profile/case mismatch")
        if confirmation != f"SOCIAL RELATIONSHIP 237 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        rel = _text(relation_type, 80).casefold()
        if rel not in _ALLOWED_REL:
            raise ValueError("unsupported relation type")
        if target_profile_id:
            target = self._profile(target_profile_id)
            if target["case_id"] != case_id:
                raise ValueError("target profile/case mismatch")
        elif not _text(target_label, 500):
            raise ValueError("target profile or label required")
        refs = list(dict.fromkeys(_text(x, 300) for x in evidence_refs if _text(x, 300)))[:100]
        if not refs:
            raise ValueError("evidence refs required")
        rid, now = new_id("socialrel237"), now_ts()
        payload = {"relationship_id": rid, "case_id": case_id, "actor_profile_id": actor_profile_id, "target_profile_id": target_profile_id, "target_label": _text(target_label, 500), "relation_type": rel, "evidence_refs": refs, "confidence": _clamp(confidence), "observed_at": observed_at or now, "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO social_relationship_candidates_237 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (rid, case_id, actor_profile_id, target_profile_id, payload["target_label"], rel, dumps(refs), payload["confidence"], payload["observed_at"], created_by, now, _hash(payload)))
        self._event(case_id, "social_relationship_candidate_created", "social_relationship", rid, {"relation_type": rel, "automatic_acceptance": False}, created_by)
        return {**payload, "review_status": "pending", "automatic_acceptance": False}

    def review_relationship(self, *, relationship_id: str, decision: str, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self._relationship(relationship_id)
        if confirmation != f"SOCIAL RELATIONSHIP REVIEW 237 {relationship_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == row["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"accepted", "rejected", "needs_more_evidence"}:
            raise ValueError("invalid decision")
        if len(_text(rationale, 5000)) < 12:
            raise ValueError("substantive rationale required")
        if self.db.one("SELECT review_id FROM social_relationship_reviews_237 WHERE relationship_id=?", (relationship_id,)):
            raise ValueError("relationship already reviewed")
        kernel_link_id = ""
        if decision == "accepted" and row["target_profile_id"]:
            left = self._bind_profile(profile_id=row["actor_profile_id"], actor=reviewer)["canonical_entity_object_id"]
            right = self._bind_profile(profile_id=row["target_profile_id"], actor=reviewer)["canonical_entity_object_id"]
            link = self.kernel.create_link(case_id=row["case_id"], source_object_id=left, relation_type="relationship:social_" + row["relation_type"], target_object_id=right, confidence=float(row["confidence"]), evidence_refs=_loads(row["evidence_refs_json"], []), actor=reviewer, confirmation=f"KERNEL LINK 235 {row['case_id']} ANLEGEN")
            kernel_link_id = link["link_id"]
        rid, now = new_id("socialrelreview237"), now_ts()
        payload = {"review_id": rid, "relationship_id": relationship_id, "case_id": row["case_id"], "decision": decision, "rationale": _text(rationale, 5000), "reviewer": reviewer, "reviewed_at": now, "kernel_link_id": kernel_link_id}
        self.db.execute("INSERT INTO social_relationship_reviews_237 VALUES(?,?,?,?,?,?,?,?,?)", (rid, relationship_id, row["case_id"], decision, payload["rationale"], reviewer, now, kernel_link_id, _hash(payload)))
        self._event(row["case_id"], "social_relationship_reviewed", "social_relationship", relationship_id, {"decision": decision, "kernel_link_id": kernel_link_id}, reviewer)
        return {**payload, "kernel_link_requires_separate_review": bool(kernel_link_id)}

    # ---------- compatibility adoption ----------
    def adopt_legacy_social(self, *, case_id: str, actor: str, confirmation: str, limit: int = 200) -> dict[str, Any]:
        if confirmation != f"SOCIAL LEGACY 237 {case_id} UEBERNEHMEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        imported, skipped = 0, 0
        # Build 213: only candidates already independently marked relevant are inherited as observations.
        rows = self.db.all("""SELECT c.*,r.reviewer,r.reason FROM social_candidates_213 c JOIN social_candidate_reviews_213 r ON r.candidate_id=c.candidate_id AND r.decision='relevant' WHERE c.case_id=? ORDER BY c.created_at LIMIT ?""", (case_id, max(1, min(int(limit), 1000)))) if self._table_exists("social_candidates_213") else []
        for row in rows:
            source_key = self._social_source_key(row.get("site_key") or "legacy_social_213")
            handle = row.get("target_value") or row.get("display_name") or row["candidate_id"]
            try:
                result = self.add_profile_observation(case_id=case_id, platform=row.get("site_key") or "legacy", source_key=source_key, handle=handle, display_name=row.get("display_name") or "", profile_url=row.get("profile_url") or "", bio=row.get("bio_original") or "", language=row.get("content_language") or "und", aliases=[handle], observed_at=row.get("observed_at") or row.get("created_at") or now_ts(), confidence=float(row.get("confidence") or .5), evidence_refs=_loads(row.get("evidence_refs_json"), []), provenance={"origin": "build213", "candidate_id": row["candidate_id"], "legacy_review": row.get("reason") or ""}, created_by=actor, confirmation=f"SOCIAL PROFILE 237 {case_id} ANLEGEN")
                # Preserve the existence of the older independent review without declaring a person merge.
                if not self.db.one("SELECT review_id FROM social_profile_reviews_237 WHERE observation_id=?", (result["observation_id"],)):
                    self.review_profile_observation(observation_id=result["observation_id"], decision="accepted", rationale="Inherited from an independently reviewed Build-213 relevant public profile candidate.", reviewer=f"legacy-review:{row.get('reviewer') or '213'}", confirmation=f"SOCIAL PROFILE REVIEW 237 {result['observation_id']} SPEICHERN")
                imported += 1
            except Exception:
                skipped += 1
        result = {"case_id": case_id, "imported": imported, "skipped": skipped, "destructive_migration": False, "automatic_network_access": False, "automatic_identity_merge": False}
        self._event(case_id, "legacy_social_adopted", "case", case_id, result, actor)
        return result

    # ---------- AI training continuity ----------
    def stage_training_from_reviewed_social(self, *, case_id: str, actor: str, confirmation: str, limit: int = 30) -> dict[str, Any]:
        if confirmation != f"SOCIAL TRAINING 237 {case_id} VORBEREITEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        staged = []
        candidates = self.db.all("""SELECT c.*,r.decision,r.rationale,r.reviewer FROM social_identity_candidates_237 c JOIN social_identity_reviews_237 r ON r.candidate_id=c.candidate_id WHERE c.case_id=? ORDER BY r.reviewed_at""", (case_id,))
        relationships = self.db.all("""SELECT c.*,r.decision,r.rationale,r.reviewer FROM social_relationship_candidates_237 c JOIN social_relationship_reviews_237 r ON r.relationship_id=c.relationship_id WHERE c.case_id=? ORDER BY r.reviewed_at""", (case_id,))
        for item_type, rows in (("identity", candidates), ("relationship", relationships)):
            for row in rows:
                item_id = row["candidate_id"] if item_type == "identity" else row["relationship_id"]
                if self.db.one("SELECT training_link_id FROM social_training_links_237 WHERE item_type=? AND item_id=?", (item_type, item_id)):
                    continue
                if len(staged) >= max(1, min(int(limit), 100)):
                    break
                if item_type == "identity":
                    instruction = "Bewerte einen Cross-Platform-Social-Identity-Kandidaten. Trenne Ähnlichkeitssignale, Widersprüche und Reviewentscheidung; bestätige keine Identität automatisch."
                    response = _canon({"decision": row["decision"], "rationale": row["rationale"], "score": row["score"], "signals": _loads(row["signals_json"], {}), "contradictions": _loads(row["contradictions_json"], []), "rule": "candidate_only_no_automatic_merge"})
                else:
                    instruction = "Bewerte eine öffentliche Social-Beziehung anhand der angegebenen Evidenz. Trenne beobachtete Interaktion von Schlussfolgerungen und verlange Review."
                    response = _canon({"decision": row["decision"], "rationale": row["rationale"], "relation_type": row["relation_type"], "confidence": row["confidence"], "evidence_refs": _loads(row["evidence_refs_json"], []), "rule": "public_observation_not_personal_relationship_fact"})
                ex = self.training.add_example(case_id=case_id, instruction=instruction, response=response, context={"build": self.BUILD, "item_type": item_type, "item_id": item_id, "reviewer": row["reviewer"]}, evidence_refs=_loads(row.get("evidence_refs_json"), []) if item_type == "relationship" else [item_id], language="de", source_type="social_intelligence_237", source_ref=item_id, created_by=actor, confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")
                tid, now = new_id("socialtrain237"), now_ts()
                payload = {"training_link_id": tid, "case_id": case_id, "item_type": item_type, "item_id": item_id, "training_example_id": ex["example_id"], "created_by": actor, "created_at": now}
                self.db.execute("INSERT INTO social_training_links_237 VALUES(?,?,?,?,?,?,?,?)", (tid, case_id, item_type, item_id, ex["example_id"], actor, now, _hash(payload)))
                staged.append(payload)
        self._event(case_id, "social_training_staged", "case", case_id, {"staged": len(staged), "automatic_model_activation": False}, actor)
        return {"case_id": case_id, "staged": staged, "automatic_training_execution": False, "automatic_model_activation": False, "next_gate": "build228_human_review"}

    # ---------- views / chat context ----------
    def timeline(self, *, case_id: str, limit: int = 100) -> list[dict[str, Any]]:
        lim = max(1, min(int(limit), 500))
        out = []
        for row in self.db.all("""SELECT p.post_id,p.profile_id,p.content_original,p.language,p.published_at,p.observed_at,r.decision FROM social_posts_237 p JOIN social_post_reviews_237 r ON r.post_id=p.post_id AND r.decision='accepted' WHERE p.case_id=? ORDER BY COALESCE(NULLIF(p.published_at,''),p.observed_at) DESC LIMIT ?""", (case_id, lim)):
            out.append({"kind": "public_post", "item_id": row["post_id"], "profile_id": row["profile_id"], "time": row["published_at"] or row["observed_at"], "content": row["content_original"], "language": row["language"]})
        return out

    def conversation_context(self, *, case_id: str, limit: int = 20) -> dict[str, Any]:
        lim = max(1, min(int(limit), 100))
        profiles = []
        for row in self.db.all("SELECT * FROM social_profiles_237 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, lim)):
            obs = self._latest_accepted_observation(row["profile_id"])
            if obs:
                profiles.append({"profile_id": row["profile_id"], "platform": row["platform"], "handle": obs["handle"], "display_name": obs["display_name"], "bio": obs["bio"][:1200], "language": obs["language"], "confidence": obs["confidence"], "public_only": True})
        ids = []
        for row in self.db.all("""SELECT c.*,r.decision FROM social_identity_candidates_237 c JOIN social_identity_reviews_237 r ON r.candidate_id=c.candidate_id WHERE c.case_id=? ORDER BY r.reviewed_at DESC LIMIT ?""", (case_id, lim)):
            ids.append({"candidate_id": row["candidate_id"], "left_profile_id": row["left_profile_id"], "right_profile_id": row["right_profile_id"], "score": row["score"], "decision": row["decision"], "contradictions": _loads(row["contradictions_json"], []), "identity_confirmed": False})
        rels = []
        for row in self.db.all("""SELECT c.*,r.decision FROM social_relationship_candidates_237 c JOIN social_relationship_reviews_237 r ON r.relationship_id=c.relationship_id WHERE c.case_id=? ORDER BY r.reviewed_at DESC LIMIT ?""", (case_id, lim)):
            rels.append({"relationship_id": row["relationship_id"], "actor_profile_id": row["actor_profile_id"], "target_profile_id": row["target_profile_id"], "target_label": row["target_label"], "relation_type": row["relation_type"], "confidence": row["confidence"], "decision": row["decision"], "evidence_refs": _loads(row["evidence_refs_json"], [])})
        return {"build": self.BUILD, "profiles_reviewed": profiles, "identity_candidates_reviewed_not_automatic_merges": ids, "public_relationships_reviewed": rels, "timeline": self.timeline(case_id=case_id, limit=lim), "policy": {"public_only": True, "no_private_access": True, "no_interaction": True, "no_automatic_identity_merge": True, "human_review_required": True}}

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        def c(table: str) -> int:
            return int(self.db.one(f"SELECT COUNT(*) AS n FROM {table} WHERE case_id=?", (case_id,))["n"])
        reviewed_profiles = int(self.db.one("SELECT COUNT(*) AS n FROM social_profile_reviews_237 WHERE case_id=? AND decision='accepted'", (case_id,))["n"])
        pending_training = int(self.db.one("SELECT COUNT(*) AS n FROM training_examples_228 WHERE case_id=? AND source_type='social_intelligence_237' AND review_status='pending'", (case_id,))["n"])
        return {"case_id": case_id, "profiles": c("social_profiles_237"), "reviewed_profiles": reviewed_profiles, "posts": c("social_posts_237"), "identity_candidates": c("social_identity_candidates_237"), "relationship_candidates": c("social_relationship_candidates_237"), "timeline_items": len(self.timeline(case_id=case_id, limit=500)), "training_examples": c("social_training_links_237"), "pending_training_review": pending_training, "automatic_network_access": False, "automatic_identity_merge": False}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        d = self.dashboard(case_id=case_id); esc = html.escape
        return f"""
<section class='card' id='build237_social_intelligence'><h2>Social Intelligence 3.0 + AI Training · Build 237</h2>
<p>Öffentliche Social-Beobachtungen werden fallzentriert normalisiert, reviewt und an Kernel 235 / Source Fabric 236 gebunden. Keine private Anmeldung, keine Interaktion, kein automatischer Identity-Merge.</p>
<div class='metrics'><div class='metric'><div class='label'>Profile</div><div class='value'>{d['profiles']}</div></div><div class='metric'><div class='label'>Reviewte Profile</div><div class='value'>{d['reviewed_profiles']}</div></div><div class='metric'><div class='label'>Posts</div><div class='value'>{d['posts']}</div></div><div class='metric'><div class='label'>Identity-Kandidaten</div><div class='value'>{d['identity_candidates']}</div></div><div class='metric'><div class='label'>Beziehungen</div><div class='value'>{d['relationship_candidates']}</div></div><div class='metric'><div class='label'>Training</div><div class='value'>{d['training_examples']}</div></div></div>
<div class='grid'>
<div class='card'><h3>Öffentliches Profil erfassen</h3><form method='post' action='/build237/profile-add'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='platform' placeholder='platform' required><input name='source_key' value='local_case_evidence' required><input name='handle' placeholder='@handle' required><input name='display_name' placeholder='Anzeigename'><input name='profile_url' placeholder='öffentliche https:// URL'><input name='language' value='und'><input name='aliases' placeholder='Aliases, komma-getrennt'><input name='location' placeholder='Ort laut öffentlichem Profil'><textarea name='bio' placeholder='öffentliche Bio'></textarea><button>Als reviewpflichtige Beobachtung speichern</button></form></div>
<div class='card'><h3>Profilbeobachtung prüfen</h3><form method='post' action='/build237/profile-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='observation_id' placeholder='Observation-ID' required><select name='decision'><option>accepted</option><option>deferred</option><option>rejected</option></select><textarea name='rationale' placeholder='Unabhängige Begründung' required></textarea><button>Review speichern</button></form></div>
<div class='card'><h3>Öffentlichen Post erfassen</h3><form method='post' action='/build237/post-add'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='profile_id' placeholder='Profile-ID' required><input name='source_key' value='local_case_evidence' required><input name='canonical_url' placeholder='öffentliche https:// URL'><input name='platform_post_id' placeholder='Post-ID optional'><input name='language' value='und'><input name='published_at' placeholder='Zeitstempel optional'><textarea name='content_original' placeholder='öffentlicher Originalinhalt' required></textarea><button>Als reviewpflichtigen Post speichern</button></form></div>
<div class='card'><h3>Öffentlichen Post prüfen</h3><form method='post' action='/build237/post-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='post_id' placeholder='Post-ID' required><select name='decision'><option>accepted</option><option>deferred</option><option>rejected</option></select><textarea name='rationale' placeholder='Unabhängige Begründung' required></textarea><button>Post-Review speichern</button></form></div>
<div class='card'><h3>Cross-Platform vergleichen</h3><form method='post' action='/build237/identity-compare'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='left_profile_id' placeholder='linkes Profil' required><input name='right_profile_id' placeholder='rechtes Profil' required><button>Identity-Kandidat berechnen</button></form></div>
<div class='card'><h3>Identity-Kandidat prüfen</h3><form method='post' action='/build237/identity-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='candidate_id' placeholder='Candidate-ID' required><select name='decision'><option>match_candidate</option><option>uncertain</option><option>no_match</option></select><textarea name='rationale' placeholder='Unabhängige Begründung' required></textarea><button>Review speichern</button></form></div>
<div class='card'><h3>Öffentliche Beziehung als Kandidat</h3><form method='post' action='/build237/relationship-add'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='actor_profile_id' placeholder='Akteur Profile-ID' required><input name='target_profile_id' placeholder='Ziel Profile-ID optional'><input name='target_label' placeholder='oder Zielbezeichnung'><select name='relation_type'><option>mentions</option><option>reply_to</option><option>reposts</option><option>references</option><option>cooccurs_with</option><option>follows_candidate</option><option>associated_with</option></select><input name='evidence_refs' placeholder='Evidence-Refs, komma-getrennt' required><input name='confidence' type='number' min='0' max='1' step='0.01' value='0.5'><button>Beziehungskandidat speichern</button></form></div>
<div class='card'><h3>Social-Beziehung prüfen</h3><form method='post' action='/build237/relationship-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='relationship_id' placeholder='Relationship-ID' required><select name='decision'><option>accepted</option><option>needs_more_evidence</option><option>rejected</option></select><textarea name='rationale' placeholder='Unabhängige Begründung' required></textarea><button>Beziehungsreview speichern</button></form></div>
<div class='card'><h3>Reviewte Social-Entscheidungen trainieren</h3><form method='post' action='/build237/training-stage'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='limit' type='number' min='1' max='100' value='30'><button>Trainingskandidaten für Build 228 vorbereiten</button></form><p class='muted'>Weiterhin Human Review, Holdout und Qualifikationsgates; keine automatische Adapteraktivierung.</p></div>
<div class='card'><h3>Legacy Social übernehmen</h3><form method='post' action='/build237/legacy-adopt'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><button>Bereits reviewte Build-213-Profile verlustfrei übernehmen</button></form></div>
</div></section>"""

    # ---------- helpers ----------
    def _bind_profile(self, *, profile_id: str, actor: str) -> dict[str, Any]:
        existing = self.db.one("SELECT * FROM social_kernel_bindings_237 WHERE profile_id=?", (profile_id,))
        if existing:
            return existing
        profile = self._profile(profile_id)
        obs = self._latest_accepted_observation(profile_id)
        if not obs:
            raise PermissionError("accepted profile observation required before kernel binding")
        label = obs["display_name"] or f"@{obs['handle']} ({profile['platform']})"
        obj = self.kernel.create_object(case_id=profile["case_id"], object_type="entity", subtype="social_account", label=label, canonical_key=f"social237:{profile_id}", state="candidate", confidence=float(obs["confidence"]), payload={"attributes": {"platform": profile["platform"], "handle": obs["handle"], "profile_url": profile["canonical_profile_url"], "public_only": True, "social_profile_id_237": profile_id}}, provenance={"origin": "build237_reviewed_social_profile", "observation_id": obs["observation_id"]}, actor=actor, confirmation=f"KERNEL OBJECT 235 {profile['case_id']} ANLEGEN")
        bid, now = new_id("socialkernel237"), now_ts()
        payload = {"binding_id": bid, "case_id": profile["case_id"], "profile_id": profile_id, "canonical_entity_object_id": obj["object_id"], "bound_by": actor, "bound_at": now}
        self.db.execute("INSERT INTO social_kernel_bindings_237 VALUES(?,?,?,?,?,?,?)", (bid, profile["case_id"], profile_id, obj["object_id"], actor, now, _hash(payload)))
        return payload

    def _assert_source_allowed(self, source_key: str) -> None:
        key = _text(source_key, 200)
        try:
            self.source_fabric.source(key)
        except Exception as exc:
            raise PermissionError("source must be registered in Source Fabric 236") from exc
        decision = self.source_fabric.ranking_constraint(source_key=key)
        if not decision.get("eligible"):
            raise PermissionError("source fabric governance/health blocks this source")

    def _social_source_key(self, site_key: str) -> str:
        key = _text(site_key, 160).casefold()
        try:
            self.source_fabric.source(key)
            return key
        except Exception:
            return "local_case_evidence"

    def _latest_accepted_observation(self, profile_id: str) -> dict[str, Any] | None:
        return self.db.one("""SELECT o.* FROM social_profile_observations_237 o JOIN social_profile_reviews_237 r ON r.observation_id=o.observation_id AND r.decision='accepted' WHERE o.profile_id=? ORDER BY o.observed_at DESC,o.created_at DESC LIMIT 1""", (profile_id,))

    def _case(self, case_id: str) -> None:
        self.kernel.cases.get_case(case_id)

    def _profile(self, profile_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM social_profiles_237 WHERE profile_id=?", (profile_id,))
        if not row:
            raise KeyError("social profile not found")
        return row

    def _observation(self, observation_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM social_profile_observations_237 WHERE observation_id=?", (observation_id,))
        if not row:
            raise KeyError("social observation not found")
        return row

    def _post(self, post_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM social_posts_237 WHERE post_id=?", (post_id,))
        if not row:
            raise KeyError("social post not found")
        return row

    def _identity(self, candidate_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM social_identity_candidates_237 WHERE candidate_id=?", (candidate_id,))
        if not row:
            raise KeyError("social identity candidate not found")
        return row

    def _relationship(self, relationship_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM social_relationship_candidates_237 WHERE relationship_id=?", (relationship_id,))
        if not row:
            raise KeyError("social relationship candidate not found")
        return row

    def _identity_payload(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "signals": _loads(row.get("signals_json"), {}), "contradictions": _loads(row.get("contradictions_json"), []), "automatic_merge": False}

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> None:
        prev = self.db.one("SELECT event_hash FROM build237_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = (prev or {}).get("event_hash", "GENESIS")
        eid, now = new_id("event237"), now_ts()
        event_hash = _hash({"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": dict(payload), "previous_hash": previous, "created_at": now})
        self.db.execute("INSERT INTO build237_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, actor, dumps(dict(payload)), previous, event_hash, now))
        try:
            self.audit.log(f"build237_{event_type}", object_type, object_id, case_id, dict(payload))
        except Exception:
            pass
