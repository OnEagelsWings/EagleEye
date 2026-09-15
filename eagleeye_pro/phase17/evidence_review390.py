from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import secrets
from typing import Any, Mapping, Sequence

BUILD = "390.0"
POLICY_ID = "phase17.evidence-review-corroboration.v390"
CONFIRM_INDEPENDENCE = "REVIEW SOURCE INDEPENDENCE"
CONFIRM_ASSESS = "ASSESS CORROBORATION"
CONFIRM_FINALIZE = "FINALIZE CORROBORATION REVIEW"

STANCE_SUPPORTS = "supports"
STANCE_CONTRADICTS = "contradicts"
STANCE_CONTEXT = "context"
_ALLOWED_STANCES = {STANCE_SUPPORTS, STANCE_CONTRADICTS, STANCE_CONTEXT}
_ALLOWED_DISPOSITIONS = {
    "needs_more_evidence",
    "ready_for_evidence_review",
    "contested_requires_analysis",
    "close_review_no_determination",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _j(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else (value if value is not None else default)
    except Exception:
        return default


@dataclass(frozen=True, slots=True)
class SourceIndependenceProfile390:
    phase17_source_id: str
    source_family: str
    independence_group: str
    source_role: str
    countable_default: bool
    review_state: str
    rationale: str

    @property
    def profile_hash(self) -> str:
        return _sha(asdict(self))


DEFAULT_SOURCE_PROFILES_390: tuple[SourceIndependenceProfile390, ...] = (
    SourceIndependenceProfile390("gleif.lei", "gleif", "publisher:gleif.org", "reference_primary", True, "policy_seeded", "Distinct first-party GLEIF publisher group; candidate remains review material."),
    SourceIndependenceProfile390("sec.edgar", "sec_edgar", "publisher:sec.gov", "regulatory_primary", True, "policy_seeded", "Distinct first-party SEC EDGAR publisher group; candidate remains review material."),
    SourceIndependenceProfile390("usaspending.awards", "usaspending", "publisher:usaspending.gov", "government_primary", True, "policy_seeded", "Distinct first-party USAspending publisher group; candidate remains review material."),
    SourceIndependenceProfile390("eu.ted", "ted", "publisher:ted.europa.eu", "procurement_primary", True, "policy_seeded", "Distinct TED publisher group; candidate remains review material and live execution may still be unavailable."),
    SourceIndependenceProfile390("us.federal_register", "federal_register", "publisher:federalregister.gov", "government_primary", True, "policy_seeded", "Distinct Federal Register publisher group; candidate remains review material."),
    SourceIndependenceProfile390("internet_archive.metadata", "internet_archive", "mirror:archive.org", "archive_mirror", False, "policy_seeded", "Archive metadata is not independent corroboration of the archived publisher by default; origin review is required."),
)


class EvidenceReviewCorroboration390:
    """Review-only corroboration engine for Build 390.

    The service groups candidate observations by source-origin independence and
    evidence stance.  It never infers truth, never assigns truth probability, never
    auto-promotes a candidate, and never treats exact duplicates or mirrors as
    additional independent corroboration.  Stance is analyst supplied; source
    independence can be conservatively seeded and overridden only by explicit review.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        intake389: Any,
        review_board88: Any,
        governance: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.intake389 = intake389
        self.review_board88 = review_board88
        self.governance = governance
        self.actor = actor
        self._init_schema()
        self._seed_profiles()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_independence_profile_390 (
              phase17_source_id TEXT PRIMARY KEY,
              source_family TEXT NOT NULL,
              independence_group TEXT NOT NULL,
              source_role TEXT NOT NULL,
              countable_default INTEGER NOT NULL,
              review_state TEXT NOT NULL,
              rationale TEXT NOT NULL,
              updated_by TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              profile_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS candidate_independence_review_390 (
              candidate_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              source_family TEXT NOT NULL,
              independence_group TEXT NOT NULL,
              origin_key TEXT NOT NULL,
              countable INTEGER NOT NULL,
              rationale TEXT NOT NULL,
              reviewed_by TEXT NOT NULL,
              reviewed_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              FOREIGN KEY(candidate_id) REFERENCES evidence_candidate_389(candidate_id)
            );
            CREATE INDEX IF NOT EXISTS idx_candidate_independence_390_case
              ON candidate_independence_review_390(case_id, reviewed_at);

            CREATE TABLE IF NOT EXISTS corroboration_review_390 (
              review_id TEXT PRIMARY KEY,
              case_id TEXT NOT NULL,
              proposition TEXT NOT NULL,
              proposition_hash TEXT NOT NULL,
              status TEXT NOT NULL,
              disposition TEXT NOT NULL DEFAULT '',
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_corroboration_review_390_case
              ON corroboration_review_390(case_id, updated_at);

            CREATE TABLE IF NOT EXISTS corroboration_link_390 (
              link_id TEXT PRIMARY KEY,
              review_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              candidate_id TEXT NOT NULL,
              stance TEXT NOT NULL,
              candidate_hash TEXT NOT NULL,
              assignment_origin TEXT NOT NULL,
              created_by TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(review_id, candidate_id),
              FOREIGN KEY(review_id) REFERENCES corroboration_review_390(review_id),
              FOREIGN KEY(candidate_id) REFERENCES evidence_candidate_389(candidate_id)
            );
            CREATE INDEX IF NOT EXISTS idx_corroboration_link_390_review
              ON corroboration_link_390(review_id, stance);

            CREATE TABLE IF NOT EXISTS corroboration_assessment_390 (
              assessment_id TEXT PRIMARY KEY,
              review_id TEXT NOT NULL,
              case_id TEXT NOT NULL,
              assessment_no INTEGER NOT NULL,
              assessment_state TEXT NOT NULL,
              support_groups INTEGER NOT NULL,
              contradiction_groups INTEGER NOT NULL,
              context_groups INTEGER NOT NULL,
              unresolved_observations INTEGER NOT NULL,
              non_countable_observations INTEGER NOT NULL,
              invalid_candidates INTEGER NOT NULL,
              exact_duplicate_links INTEGER NOT NULL,
              assessment_json TEXT NOT NULL,
              assessed_by TEXT NOT NULL,
              assessed_at TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              UNIQUE(review_id, assessment_no),
              FOREIGN KEY(review_id) REFERENCES corroboration_review_390(review_id)
            );
            CREATE INDEX IF NOT EXISTS idx_corroboration_assessment_390_review
              ON corroboration_assessment_390(review_id, assessment_no);
            """
        )
        self.db.conn.commit()

    def _seed_profiles(self) -> None:
        now = _now()
        with self.db.transaction(immediate=True):
            for p in DEFAULT_SOURCE_PROFILES_390:
                row = {
                    "phase17_source_id": p.phase17_source_id,
                    "source_family": p.source_family,
                    "independence_group": p.independence_group,
                    "source_role": p.source_role,
                    "countable_default": int(p.countable_default),
                    "review_state": p.review_state,
                    "rationale": p.rationale,
                    "updated_by": "build390-policy-seed",
                    "updated_at": now,
                }
                self.db.execute(
                    "INSERT INTO source_independence_profile_390(phase17_source_id,source_family,independence_group,source_role,countable_default,review_state,rationale,updated_by,updated_at,profile_hash) VALUES(?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(phase17_source_id) DO NOTHING",
                    (*row.values(), _sha(row)),
                )

    def _authorize(self, identity: Mapping[str, Any], case_id: str, capability: str, object_id: str) -> None:
        self.governance.authorize(dict(identity), case_id=case_id, capability=capability, object_type="phase17_corroboration_review_v390", object_id=object_id)

    def _candidate(self, case_id: str, candidate_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_candidate_389 WHERE candidate_id=? AND case_id=?", (candidate_id, case_id))
        if not row:
            raise KeyError(candidate_id)
        return dict(row)

    def _profile(self, phase17_source_id: str) -> dict[str, Any] | None:
        row = self.db.one("SELECT * FROM source_independence_profile_390 WHERE phase17_source_id=?", (phase17_source_id,))
        return dict(row) if row else None

    def source_profiles(self) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM source_independence_profile_390 ORDER BY phase17_source_id")
        out = []
        for row in rows:
            r = dict(row)
            r["countable_default"] = bool(r.get("countable_default"))
            out.append(r)
        return out

    def review_candidate_independence(
        self,
        *,
        case_id: str,
        candidate_id: str,
        identity: Mapping[str, Any],
        source_family: str,
        independence_group: str,
        origin_key: str,
        countable: bool,
        rationale: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_INDEPENDENCE:
            raise PermissionError(f"explicit confirmation {CONFIRM_INDEPENDENCE} required")
        self._authorize(identity, case_id, "source.review", candidate_id)
        candidate = self._candidate(case_id, candidate_id)
        if not self.intake389.verify_candidate(case_id=case_id, candidate_id=candidate_id).get("valid"):
            raise PermissionError("candidate integrity must be valid before independence review")
        fam = str(source_family or "").strip()[:200]
        grp = str(independence_group or "").strip()[:300]
        origin = str(origin_key or "").strip()[:1000]
        why = str(rationale or "").strip()[:4000]
        if not fam or not grp or not origin:
            raise ValueError("source_family, independence_group and origin_key are required")
        if len(why) < 12:
            raise ValueError("independence review rationale must be at least 12 characters")
        actor = str(identity.get("username") or self.actor)[:120]
        now = _now()
        body = {
            "candidate_id": candidate_id,
            "case_id": case_id,
            "source_family": fam,
            "independence_group": grp,
            "origin_key": origin,
            "countable": int(bool(countable)),
            "rationale": why,
            "reviewed_by": actor,
            "reviewed_at": now,
        }
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO candidate_independence_review_390(candidate_id,case_id,source_family,independence_group,origin_key,countable,rationale,reviewed_by,reviewed_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(candidate_id) DO UPDATE SET source_family=excluded.source_family,independence_group=excluded.independence_group,origin_key=excluded.origin_key,countable=excluded.countable,rationale=excluded.rationale,reviewed_by=excluded.reviewed_by,reviewed_at=excluded.reviewed_at,record_hash=excluded.record_hash",
                (*body.values(), _sha(body)),
            )
        self.audit.log("review_independence", "evidence_candidate_389", candidate_id, case_id, {"source_family": fam, "independence_group": grp, "countable": bool(countable)})
        return {**body, "countable": bool(countable), "truth_assigned": False}

    def _resolve_independence(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        candidate_id = str(candidate.get("candidate_id") or "")
        case_id = str(candidate.get("case_id") or "")
        override = self.db.one("SELECT * FROM candidate_independence_review_390 WHERE candidate_id=? AND case_id=?", (candidate_id, case_id))
        if override:
            return {
                "source_family": str(override.get("source_family") or ""),
                "independence_group": str(override.get("independence_group") or ""),
                "origin_key": str(override.get("origin_key") or ""),
                "countable": bool(override.get("countable")),
                "resolution": "candidate_reviewed",
                "source_role": "reviewed_origin",
                "rationale": str(override.get("rationale") or ""),
            }
        sid = str(candidate.get("phase17_source_id") or "")
        profile = self._profile(sid)
        if profile:
            return {
                "source_family": str(profile.get("source_family") or ""),
                "independence_group": str(profile.get("independence_group") or ""),
                "origin_key": str(profile.get("independence_group") or ""),
                "countable": bool(profile.get("countable_default")),
                "resolution": str(profile.get("review_state") or "policy_seeded"),
                "source_role": str(profile.get("source_role") or "unknown"),
                "rationale": str(profile.get("rationale") or ""),
            }
        # Conservative fail-closed behavior: all unresolved origins share one bucket
        # and do not count toward independent corroboration.
        return {
            "source_family": "unresolved",
            "independence_group": "unresolved",
            "origin_key": "",
            "countable": False,
            "resolution": "unresolved",
            "source_role": "unknown",
            "rationale": "No reviewed or policy-seeded independence profile is available.",
        }

    def create_review(
        self,
        *,
        case_id: str,
        proposition: str,
        candidate_stances: Mapping[str, str],
        identity: Mapping[str, Any],
    ) -> dict[str, Any]:
        prop = " ".join(str(proposition or "").split())[:12000]
        if not prop:
            raise ValueError("proposition is required")
        if not candidate_stances or len(candidate_stances) > 100:
            raise ValueError("1..100 candidate stances are required")
        self._authorize(identity, case_id, "source.review", case_id)
        actor = str(identity.get("username") or self.actor)[:120]
        review_id = "corr390_" + secrets.token_hex(12)
        now = _now()
        review = {
            "review_id": review_id,
            "case_id": case_id,
            "proposition": prop,
            "proposition_hash": _sha(prop),
            "status": "draft_needs_assessment",
            "disposition": "",
            "created_by": actor,
            "created_at": now,
            "updated_at": now,
        }
        links: list[dict[str, Any]] = []
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO corroboration_review_390(review_id,case_id,proposition,proposition_hash,status,disposition,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (*review.values(), _sha(review)),
            )
            for candidate_id, stance_raw in candidate_stances.items():
                stance = str(stance_raw or "").strip().lower()
                if stance not in _ALLOWED_STANCES:
                    raise ValueError(f"unsupported stance for {candidate_id}: {stance}")
                candidate = self._candidate(case_id, str(candidate_id))
                link = {
                    "link_id": "corrlnk390_" + secrets.token_hex(10),
                    "review_id": review_id,
                    "case_id": case_id,
                    "candidate_id": str(candidate_id),
                    "stance": stance,
                    "candidate_hash": str(candidate.get("record_hash") or ""),
                    "assignment_origin": "analyst_assigned",
                    "created_by": actor,
                    "created_at": now,
                }
                self.db.execute(
                    "INSERT INTO corroboration_link_390(link_id,review_id,case_id,candidate_id,stance,candidate_hash,assignment_origin,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (*link.values(), _sha(link)),
                )
                links.append(link)
        self.audit.log("create", "corroboration_review_390", review_id, case_id, {"candidate_count": len(links), "truth_assigned": False})
        return {**review, "links": links, "truth_assigned": False, "probability_assigned": False}

    def _review_row(self, case_id: str, review_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM corroboration_review_390 WHERE review_id=? AND case_id=?", (review_id, case_id))
        if not row:
            raise KeyError(review_id)
        return dict(row)

    @staticmethod
    def _state(support_groups: int, contradiction_groups: int, context_groups: int, unresolved: int, invalid: int) -> str:
        if invalid:
            return "integrity_review_required"
        if support_groups >= 2 and contradiction_groups >= 1:
            return "contested_multi_source"
        if support_groups >= 2:
            return "multi_group_support"
        if support_groups == 1 and contradiction_groups >= 1:
            return "contested_single_support_group"
        if support_groups == 1:
            return "single_independence_group"
        if contradiction_groups >= 1:
            return "contradiction_only"
        if context_groups >= 1:
            return "context_only"
        if unresolved:
            return "independence_unresolved"
        return "insufficient_review_material"

    def assess_review(
        self,
        *,
        case_id: str,
        review_id: str,
        identity: Mapping[str, Any],
        confirmation: str,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_ASSESS:
            raise PermissionError(f"explicit confirmation {CONFIRM_ASSESS} required")
        self._authorize(identity, case_id, "source.review", review_id)
        review = self._review_row(case_id, review_id)
        if str(review.get("status") or "") == "finalized":
            raise PermissionError("finalized review is immutable")
        links = self.db.all("SELECT * FROM corroboration_link_390 WHERE review_id=? ORDER BY created_at,link_id", (review_id,))
        if not links:
            raise ValueError("review has no candidate links")

        group_sets: dict[str, set[str]] = {STANCE_SUPPORTS: set(), STANCE_CONTRADICTS: set(), STANCE_CONTEXT: set()}
        observations: list[dict[str, Any]] = []
        unresolved = 0
        non_countable = 0
        invalid = 0
        exact_duplicates = 0
        seen_exact: set[tuple[str, str, str]] = set()
        for link in links:
            candidate = self._candidate(case_id, str(link["candidate_id"]))
            integrity = self.intake389.verify_candidate(case_id=case_id, candidate_id=str(link["candidate_id"]))
            independence = self._resolve_independence(candidate)
            stance = str(link.get("stance") or "")
            candidate_hash = str(candidate.get("canonical_hash") or "")
            blocked = str(candidate.get("review_status") or "").startswith("blocked_")
            countable = bool(independence.get("countable")) and bool(integrity.get("valid")) and not blocked
            if not bool(integrity.get("valid")):
                invalid += 1
            if str(independence.get("resolution")) == "unresolved":
                unresolved += 1
            if not bool(independence.get("countable")) or blocked:
                non_countable += 1
            exact_key = (stance, str(independence.get("independence_group") or "unresolved"), candidate_hash)
            if exact_key in seen_exact:
                exact_duplicates += 1
            else:
                seen_exact.add(exact_key)
            if countable:
                group_sets[stance].add(str(independence.get("independence_group") or "unresolved"))
            observations.append({
                "candidate_id": str(candidate.get("candidate_id") or ""),
                "stance": stance,
                "phase17_source_id": str(candidate.get("phase17_source_id") or ""),
                "canonical_hash": candidate_hash,
                "duplicate_of_candidate_id": str(candidate.get("duplicate_of_candidate_id") or ""),
                "review_status": str(candidate.get("review_status") or ""),
                "candidate_integrity_valid": bool(integrity.get("valid")),
                "source_family": independence.get("source_family"),
                "independence_group": independence.get("independence_group"),
                "source_role": independence.get("source_role"),
                "independence_resolution": independence.get("resolution"),
                "counted_as_independent": countable,
            })

        support_groups = len(group_sets[STANCE_SUPPORTS])
        contradiction_groups = len(group_sets[STANCE_CONTRADICTS])
        context_groups = len(group_sets[STANCE_CONTEXT])
        state = self._state(support_groups, contradiction_groups, context_groups, unresolved, invalid)
        assessment = {
            "review_id": review_id,
            "case_id": case_id,
            "proposition": str(review.get("proposition") or ""),
            "assessment_state": state,
            "support_groups": support_groups,
            "contradiction_groups": contradiction_groups,
            "context_groups": context_groups,
            "support_group_ids": sorted(group_sets[STANCE_SUPPORTS]),
            "contradiction_group_ids": sorted(group_sets[STANCE_CONTRADICTS]),
            "context_group_ids": sorted(group_sets[STANCE_CONTEXT]),
            "unresolved_observations": unresolved,
            "non_countable_observations": non_countable,
            "invalid_candidates": invalid,
            "exact_duplicate_links": exact_duplicates,
            "observations": observations,
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_evidence_promotion": False,
            "automatic_claim_acceptance": False,
            "principle": "Independent corroboration groups are counted, not raw hit counts; mirrors, unresolved origins and exact duplicates do not create extra independent support.",
        }
        nrow = self.db.one("SELECT COALESCE(MAX(assessment_no),0)+1 n FROM corroboration_assessment_390 WHERE review_id=?", (review_id,)) or {"n": 1}
        no = int(nrow.get("n") or 1)
        actor = str(identity.get("username") or self.actor)[:120]
        assessed_at = _now()
        body = {
            "assessment_id": "assess390_" + secrets.token_hex(12),
            "review_id": review_id,
            "case_id": case_id,
            "assessment_no": no,
            "assessment_state": state,
            "support_groups": support_groups,
            "contradiction_groups": contradiction_groups,
            "context_groups": context_groups,
            "unresolved_observations": unresolved,
            "non_countable_observations": non_countable,
            "invalid_candidates": invalid,
            "exact_duplicate_links": exact_duplicates,
            "assessment_json": _canon(assessment),
            "assessed_by": actor,
            "assessed_at": assessed_at,
        }
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO corroboration_assessment_390(assessment_id,review_id,case_id,assessment_no,assessment_state,support_groups,contradiction_groups,context_groups,unresolved_observations,non_countable_observations,invalid_candidates,exact_duplicate_links,assessment_json,assessed_by,assessed_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*body.values(), _sha(body)),
            )
            updated = {k: review[k] for k in review if k != "record_hash"}
            updated.update({"status": "assessed_needs_review", "updated_at": assessed_at})
            self.db.execute("UPDATE corroboration_review_390 SET status=?,updated_at=?,record_hash=? WHERE review_id=?", ("assessed_needs_review", assessed_at, _sha(updated), review_id))
        self.audit.log("assess", "corroboration_review_390", review_id, case_id, {"assessment_state": state, "support_groups": support_groups, "contradiction_groups": contradiction_groups, "truth_determined": False})
        return {"assessment_id": body["assessment_id"], **assessment}

    def finalize_review(
        self,
        *,
        case_id: str,
        review_id: str,
        identity: Mapping[str, Any],
        disposition: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_FINALIZE:
            raise PermissionError(f"explicit confirmation {CONFIRM_FINALIZE} required")
        self._authorize(identity, case_id, "source.review", review_id)
        disp = str(disposition or "").strip().lower()
        if disp not in _ALLOWED_DISPOSITIONS:
            raise ValueError("unsupported corroboration review disposition")
        review = self._review_row(case_id, review_id)
        latest = self.db.one("SELECT * FROM corroboration_assessment_390 WHERE review_id=? ORDER BY assessment_no DESC LIMIT 1", (review_id,))
        if not latest:
            raise PermissionError("review must be assessed before finalization")
        if int(latest.get("invalid_candidates") or 0) > 0:
            raise PermissionError("review with invalid candidate integrity cannot be finalized")
        now = _now()
        updated = {k: review[k] for k in review if k != "record_hash"}
        updated.update({"status": "finalized", "disposition": disp, "updated_at": now})
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE corroboration_review_390 SET status=?,disposition=?,updated_at=?,record_hash=? WHERE review_id=?", ("finalized", disp, now, _sha(updated), review_id))
        self.audit.log("finalize", "corroboration_review_390", review_id, case_id, {"disposition": disp, "truth_determined": False})
        return {
            "review_id": review_id,
            "case_id": case_id,
            "status": "finalized",
            "disposition": disp,
            "latest_assessment_id": str(latest.get("assessment_id") or ""),
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_evidence_promotion": False,
        }

    def review(self, *, case_id: str, review_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", review_id)
        review = self._review_row(case_id, review_id)
        links = [dict(r) for r in self.db.all("SELECT * FROM corroboration_link_390 WHERE review_id=? ORDER BY created_at,link_id", (review_id,))]
        latest = self.db.one("SELECT * FROM corroboration_assessment_390 WHERE review_id=? ORDER BY assessment_no DESC LIMIT 1", (review_id,))
        assessment = _j((latest or {}).get("assessment_json"), {}) if latest else None
        return {**review, "links": links, "latest_assessment": assessment, "truth_determined": False}

    def ai_review_feed(self, *, case_id: str, identity: Mapping[str, Any] | None = None, limit: int = 100) -> dict[str, Any]:
        if identity is not None:
            self._authorize(identity, case_id, "case.read", case_id)
        rows = self.db.all("SELECT review_id FROM corroboration_review_390 WHERE case_id=? ORDER BY updated_at DESC LIMIT ?", (case_id, max(1, min(int(limit), 500))))
        reviews = [self.review(case_id=case_id, review_id=str(r["review_id"])) for r in rows]
        return {
            "case_id": case_id,
            "build": BUILD,
            "reviews": reviews,
            "review_count": len(reviews),
            "candidate_review_only": True,
            "truth_determined": False,
            "probability_assigned": False,
            "automatic_evidence_promotion": False,
            "instruction": "Use independence-group counts as corroboration structure, not as truth probability. Exact duplicates, mirrors and unresolved origins must not be represented as additional independent confirmation.",
        }

    def verify_assessment(self, *, case_id: str, assessment_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM corroboration_assessment_390 WHERE assessment_id=? AND case_id=?", (assessment_id, case_id))
        if not row:
            raise KeyError(assessment_id)
        body = {k: row[k] for k in row if k != "record_hash"}
        return {"assessment_id": assessment_id, "valid": str(row.get("record_hash") or "") == _sha(body)}

    def status(self) -> dict[str, Any]:
        counts = self.db.one("SELECT COUNT(*) total,SUM(CASE WHEN status='finalized' THEN 1 ELSE 0 END) finalized FROM corroboration_review_390") or {}
        assessments = self.db.one("SELECT COUNT(*) total FROM corroboration_assessment_390") or {}
        overrides = self.db.one("SELECT COUNT(*) total FROM candidate_independence_review_390") or {}
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "source_independence_profiles": True,
            "candidate_independence_review": True,
            "corroboration_review": True,
            "duplicate_aware": True,
            "mirror_aware": True,
            "unknown_origin_fail_closed": True,
            "automatic_truth_acceptance": False,
            "truth_probability": False,
            "automatic_evidence_promotion": False,
            "automatic_identity_merge": False,
            "direct_network_fetch": False,
            "reviews": int(counts.get("total") or 0),
            "finalized_reviews": int(counts.get("finalized") or 0),
            "assessments": int(assessments.get("total") or 0),
            "candidate_independence_overrides": int(overrides.get("total") or 0),
        }
