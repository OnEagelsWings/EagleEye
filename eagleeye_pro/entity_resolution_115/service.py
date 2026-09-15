from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Iterable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class EntityResolution115Service:
    """Review-gated entity resolution for candidate identities.

    The service never destructively merges records and never confirms an identity
    automatically. It records comparisons, conflicts and human-reviewed resolution links.
    """

    ENTITY_TYPES = {"person", "organisation", "account", "domain", "email", "phone", "place", "document", "other"}
    ANCHOR_TYPES = {"email", "username", "phone", "domain", "organisation", "location", "birth_year", "external_id", "url"}
    STRONG_ANCHORS = {"email", "phone", "external_id"}
    STATES = {"candidate", "needs_review", "rejected", "approved_same", "approved_distinct"}

    def __init__(self, db, audit=None, kernel=None):
        self.db = db
        self.audit = audit
        self.kernel = kernel
        self._schema()

    def _schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS resolution_entities_115(
                resolution_entity_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                source_entity_id TEXT,
                entity_type TEXT NOT NULL,
                display_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                attributes_json TEXT NOT NULL,
                candidate_only INTEGER NOT NULL DEFAULT 1,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(case_id, source_entity_id)
            );
            CREATE INDEX IF NOT EXISTS idx_resolution_entities115_name
                ON resolution_entities_115(case_id, entity_type, normalized_name);
            CREATE TABLE IF NOT EXISTS resolution_aliases_115(
                alias_id TEXT PRIMARY KEY,
                resolution_entity_id TEXT NOT NULL,
                alias TEXT NOT NULL,
                normalized_alias TEXT NOT NULL,
                alias_kind TEXT NOT NULL,
                source_ref TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(resolution_entity_id, normalized_alias)
            );
            CREATE INDEX IF NOT EXISTS idx_resolution_aliases115_norm
                ON resolution_aliases_115(normalized_alias);
            CREATE TABLE IF NOT EXISTS resolution_anchors_115(
                anchor_id TEXT PRIMARY KEY,
                resolution_entity_id TEXT NOT NULL,
                anchor_type TEXT NOT NULL,
                anchor_value TEXT NOT NULL,
                normalized_value TEXT NOT NULL,
                value_hash TEXT NOT NULL,
                reliability REAL NOT NULL,
                source_ref TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(resolution_entity_id, anchor_type, value_hash)
            );
            CREATE INDEX IF NOT EXISTS idx_resolution_anchors115_lookup
                ON resolution_anchors_115(anchor_type, value_hash);
            CREATE TABLE IF NOT EXISTS resolution_comparisons_115(
                comparison_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                left_entity_id TEXT NOT NULL,
                right_entity_id TEXT NOT NULL,
                name_similarity REAL NOT NULL,
                alias_similarity REAL NOT NULL,
                anchor_score REAL NOT NULL,
                conflict_penalty REAL NOT NULL,
                total_score REAL NOT NULL,
                classification TEXT NOT NULL,
                explanation_json TEXT NOT NULL,
                state TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reviewed_by TEXT,
                reviewed_at TEXT,
                review_reason TEXT,
                UNIQUE(case_id,left_entity_id,right_entity_id)
            );
            CREATE TABLE IF NOT EXISTS resolution_conflicts_115(
                conflict_id TEXT PRIMARY KEY,
                comparison_id TEXT NOT NULL,
                conflict_type TEXT NOT NULL,
                left_value TEXT NOT NULL,
                right_value TEXT NOT NULL,
                severity REAL NOT NULL,
                explanation TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS resolution_clusters_115(
                cluster_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                label TEXT NOT NULL,
                state TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS resolution_cluster_members_115(
                cluster_id TEXT NOT NULL,
                resolution_entity_id TEXT NOT NULL,
                membership_score REAL NOT NULL,
                status TEXT NOT NULL,
                PRIMARY KEY(cluster_id,resolution_entity_id)
            );
            CREATE TABLE IF NOT EXISTS resolution_merge_proposals_115(
                proposal_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                comparison_id TEXT NOT NULL,
                canonical_entity_id TEXT NOT NULL,
                candidate_entity_id TEXT NOT NULL,
                state TEXT NOT NULL,
                requested_by TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                reviewed_by TEXT,
                reviewed_at TEXT,
                decision_reason TEXT,
                UNIQUE(comparison_id)
            );
            CREATE TABLE IF NOT EXISTS resolution_links_115(
                link_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                canonical_entity_id TEXT NOT NULL,
                linked_entity_id TEXT NOT NULL,
                relationship TEXT NOT NULL,
                comparison_id TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                approved_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(case_id,canonical_entity_id,linked_entity_id)
            );
            CREATE TABLE IF NOT EXISTS resolution_events_115(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                case_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.db.conn.commit()

    @staticmethod
    def normalize_text(value: str) -> str:
        text = unicodedata.normalize("NFKD", str(value or ""))
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        text = text.casefold().replace("ß", "ss")
        text = re.sub(r"[^\w@.+-]+", " ", text, flags=re.UNICODE)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def normalize_anchor(cls, anchor_type: str, value: str) -> str:
        value = str(value or "").strip()
        if anchor_type == "email":
            return value.casefold()
        if anchor_type == "phone":
            return re.sub(r"\D", "", value)
        if anchor_type in {"domain", "url"}:
            return value.casefold().rstrip("/")
        return cls.normalize_text(value)

    def _event(self, case_id: str, actor: str, event_type: str, object_type: str, object_id: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        event_id, ts = _id("revt"), _now()
        row = self.db.one("SELECT event_hash FROM resolution_events_115 WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous = row["event_hash"] if row else "GENESIS"
        material = _json([event_id, case_id, actor, event_type, object_type, object_id, payload, previous, ts])
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        self.db.execute(
            "INSERT INTO resolution_events_115(event_id,case_id,actor,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (event_id, case_id, actor, event_type, object_type, object_id, _json(payload), previous, digest, ts),
        )
        if self.kernel:
            self.kernel.event(case_id, actor, event_type, object_type, object_id, payload)

    def register_entity(self, case_id: str, entity_type: str, display_name: str, created_by: str,
                        source_entity_id: str | None = None, attributes: dict[str, Any] | None = None,
                        aliases: Iterable[str] | None = None, anchors: Iterable[dict[str, Any]] | None = None) -> str:
        if entity_type not in self.ENTITY_TYPES:
            raise ValueError("unsupported entity type")
        normalized = self.normalize_text(display_name)
        if len(normalized) < 2 or len(display_name) > 500:
            raise ValueError("invalid display name")
        entity_id, ts = _id("rent"), _now()
        self.db.execute(
            "INSERT INTO resolution_entities_115(resolution_entity_id,case_id,source_entity_id,entity_type,display_name,normalized_name,attributes_json,candidate_only,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (entity_id, case_id, source_entity_id, entity_type, display_name.strip(), normalized, _json(attributes or {}), 1, created_by, ts, ts),
        )
        self.add_alias(entity_id, display_name, "primary", created_by)
        for alias in aliases or []:
            self.add_alias(entity_id, alias, "alias", created_by)
        for anchor in anchors or []:
            self.add_anchor(entity_id, anchor["type"], anchor["value"], created_by, anchor.get("reliability", .7), anchor.get("source_ref"))
        self._event(case_id, created_by, "ResolutionEntityRegistered", "resolution_entity", entity_id, {"entity_type": entity_type})
        return entity_id

    def add_alias(self, entity_id: str, alias: str, alias_kind: str, actor: str, source_ref: str | None = None) -> str:
        entity = self._entity(entity_id)
        normalized = self.normalize_text(alias)
        if len(normalized) < 2 or len(alias) > 500:
            raise ValueError("invalid alias")
        alias_id = _id("ralias")
        self.db.execute(
            "INSERT OR IGNORE INTO resolution_aliases_115(alias_id,resolution_entity_id,alias,normalized_alias,alias_kind,source_ref,created_at) VALUES(?,?,?,?,?,?,?)",
            (alias_id, entity_id, alias.strip(), normalized, alias_kind[:40], source_ref, _now()),
        )
        self._event(entity["case_id"], actor, "ResolutionAliasAdded", "resolution_entity", entity_id, {"alias_kind": alias_kind})
        return alias_id

    def add_anchor(self, entity_id: str, anchor_type: str, value: str, actor: str,
                   reliability: float = .7, source_ref: str | None = None) -> str:
        entity = self._entity(entity_id)
        if anchor_type not in self.ANCHOR_TYPES:
            raise ValueError("unsupported anchor type")
        normalized = self.normalize_anchor(anchor_type, value)
        if not normalized or len(normalized) > 1000:
            raise ValueError("invalid anchor")
        digest = hashlib.sha256(f"{anchor_type}:{normalized}".encode("utf-8")).hexdigest()
        anchor_id = _id("ranc")
        self.db.execute(
            "INSERT OR IGNORE INTO resolution_anchors_115(anchor_id,resolution_entity_id,anchor_type,anchor_value,normalized_value,value_hash,reliability,source_ref,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (anchor_id, entity_id, anchor_type, value[:1000], normalized, digest, _clamp(reliability), source_ref, _now()),
        )
        self._event(entity["case_id"], actor, "ResolutionAnchorAdded", "resolution_entity", entity_id, {"anchor_type": anchor_type})
        return anchor_id

    def _entity(self, entity_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM resolution_entities_115 WHERE resolution_entity_id=?", (entity_id,))
        if not row:
            raise ValueError("resolution entity not found")
        return row

    def _aliases(self, entity_id: str) -> list[str]:
        return [r["normalized_alias"] for r in self.db.all("SELECT normalized_alias FROM resolution_aliases_115 WHERE resolution_entity_id=?", (entity_id,))]

    def _anchors(self, entity_id: str) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM resolution_anchors_115 WHERE resolution_entity_id=?", (entity_id,))

    @staticmethod
    def _best_similarity(left: Iterable[str], right: Iterable[str]) -> float:
        scores = [SequenceMatcher(None, a, b).ratio() for a in left for b in right if a and b]
        return max(scores, default=0.0)

    def compare(self, left_entity_id: str, right_entity_id: str, created_by: str) -> dict[str, Any]:
        if left_entity_id == right_entity_id:
            raise ValueError("cannot compare entity with itself")
        left, right = self._entity(left_entity_id), self._entity(right_entity_id)
        if left["case_id"] != right["case_id"]:
            raise ValueError("cross-case identity comparison prohibited")
        if left["entity_type"] != right["entity_type"]:
            raise ValueError("different entity types cannot be identity-resolved")
        a_id, b_id = sorted([left_entity_id, right_entity_id])
        left, right = self._entity(a_id), self._entity(b_id)
        left_aliases, right_aliases = self._aliases(a_id), self._aliases(b_id)
        name_similarity = SequenceMatcher(None, left["normalized_name"], right["normalized_name"]).ratio()
        alias_similarity = self._best_similarity(left_aliases, right_aliases)
        la, ra = self._anchors(a_id), self._anchors(b_id)
        matched, conflicts = [], []
        for x in la:
            for y in ra:
                if x["anchor_type"] != y["anchor_type"]:
                    continue
                if x["value_hash"] == y["value_hash"]:
                    strength = min(float(x["reliability"]), float(y["reliability"]))
                    matched.append({"type": x["anchor_type"], "strength": strength, "strong": x["anchor_type"] in self.STRONG_ANCHORS})
                elif x["anchor_type"] in self.STRONG_ANCHORS | {"birth_year"}:
                    severity = .9 if x["anchor_type"] in self.STRONG_ANCHORS else .55
                    conflicts.append((x["anchor_type"], x["anchor_value"], y["anchor_value"], severity))
        anchor_score = min(1.0, sum((.55 if m["strong"] else .22) * m["strength"] for m in matched))
        conflict_penalty = min(.85, sum(c[3] for c in conflicts) / max(1, len(conflicts))) if conflicts else 0.0
        total = _clamp(.35 * name_similarity + .20 * alias_similarity + .55 * anchor_score - .60 * conflict_penalty)
        if conflict_penalty >= .75:
            classification = "likely_distinct"
        elif total >= .82 and any(m["strong"] for m in matched):
            classification = "strong_candidate"
        elif total >= .62:
            classification = "possible_match"
        elif total >= .40:
            classification = "weak_candidate"
        else:
            classification = "insufficient"
        explanation = {
            "matched_anchors": matched,
            "conflict_count": len(conflicts),
            "warning": "Similarity is not identity proof; human review is mandatory.",
            "automatic_merge": False,
        }
        comparison_id = _id("rcmp")
        existing = self.db.one("SELECT comparison_id FROM resolution_comparisons_115 WHERE case_id=? AND left_entity_id=? AND right_entity_id=?", (left["case_id"], a_id, b_id))
        if existing:
            comparison_id = existing["comparison_id"]
            self.db.execute("DELETE FROM resolution_conflicts_115 WHERE comparison_id=?", (comparison_id,))
            self.db.execute(
                "UPDATE resolution_comparisons_115 SET name_similarity=?,alias_similarity=?,anchor_score=?,conflict_penalty=?,total_score=?,classification=?,explanation_json=?,state='needs_review',created_by=?,created_at=?,reviewed_by=NULL,reviewed_at=NULL,review_reason=NULL WHERE comparison_id=?",
                (name_similarity, alias_similarity, anchor_score, conflict_penalty, total, classification, _json(explanation), created_by, _now(), comparison_id),
            )
        else:
            self.db.execute(
                "INSERT INTO resolution_comparisons_115(comparison_id,case_id,left_entity_id,right_entity_id,name_similarity,alias_similarity,anchor_score,conflict_penalty,total_score,classification,explanation_json,state,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (comparison_id, left["case_id"], a_id, b_id, name_similarity, alias_similarity, anchor_score, conflict_penalty, total, classification, _json(explanation), "needs_review", created_by, _now()),
            )
        for typ, lv, rv, severity in conflicts:
            self.db.execute(
                "INSERT INTO resolution_conflicts_115 VALUES(?,?,?,?,?,?,?,?)",
                (_id("rcnf"), comparison_id, typ, lv[:1000], rv[:1000], severity, f"Conflicting {typ} anchors require human review.", _now()),
            )
        self._event(left["case_id"], created_by, "EntitiesCompared", "resolution_comparison", comparison_id, {"classification": classification, "score": round(total, 4)})
        return self.comparison(comparison_id)

    def comparison(self, comparison_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM resolution_comparisons_115 WHERE comparison_id=?", (comparison_id,))
        if not row:
            raise ValueError("comparison not found")
        row["explanation"] = json.loads(row.pop("explanation_json"))
        row["conflicts"] = self.db.all("SELECT conflict_type,left_value,right_value,severity,explanation FROM resolution_conflicts_115 WHERE comparison_id=?", (comparison_id,))
        return row

    def candidate_matches(self, entity_id: str, minimum_score: float = .40) -> list[dict[str, Any]]:
        entity = self._entity(entity_id)
        rows = self.db.all(
            "SELECT comparison_id,total_score,classification,state,left_entity_id,right_entity_id FROM resolution_comparisons_115 WHERE case_id=? AND (left_entity_id=? OR right_entity_id=?) AND total_score>=? ORDER BY total_score DESC",
            (entity["case_id"], entity_id, entity_id, _clamp(minimum_score)),
        )
        return rows

    def create_cluster(self, case_id: str, label: str, members: Iterable[tuple[str, float]], created_by: str) -> str:
        cluster_id = _id("rclu")
        self.db.execute("INSERT INTO resolution_clusters_115 VALUES(?,?,?,?,?,?)", (cluster_id, case_id, label[:300], "candidate", created_by, _now()))
        count = 0
        for entity_id, score in members:
            entity = self._entity(entity_id)
            if entity["case_id"] != case_id:
                raise ValueError("cross-case cluster member prohibited")
            self.db.execute("INSERT INTO resolution_cluster_members_115 VALUES(?,?,?,?)", (cluster_id, entity_id, _clamp(score), "candidate"))
            count += 1
        if count < 2:
            raise ValueError("cluster requires at least two entities")
        self._event(case_id, created_by, "ResolutionClusterCreated", "resolution_cluster", cluster_id, {"members": count})
        return cluster_id

    def propose_merge(self, comparison_id: str, canonical_entity_id: str, requested_by: str) -> str:
        cmp = self.comparison(comparison_id)
        if canonical_entity_id not in {cmp["left_entity_id"], cmp["right_entity_id"]}:
            raise ValueError("canonical entity is not part of comparison")
        if cmp["classification"] in {"insufficient", "likely_distinct"}:
            raise ValueError("comparison does not support a merge proposal")
        candidate = cmp["right_entity_id"] if canonical_entity_id == cmp["left_entity_id"] else cmp["left_entity_id"]
        proposal_id = _id("rmrg")
        self.db.execute(
            "INSERT INTO resolution_merge_proposals_115 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (proposal_id, cmp["case_id"], comparison_id, canonical_entity_id, candidate, "pending", requested_by, _now(), None, None, None),
        )
        self._event(cmp["case_id"], requested_by, "ResolutionMergeProposed", "merge_proposal", proposal_id, {"comparison_id": comparison_id})
        return proposal_id

    def review_merge(self, proposal_id: str, reviewer: str, approve: bool, reason: str) -> dict[str, Any]:
        proposal = self.db.one("SELECT * FROM resolution_merge_proposals_115 WHERE proposal_id=?", (proposal_id,))
        if not proposal or proposal["state"] != "pending":
            raise ValueError("merge proposal unavailable")
        if reviewer == proposal["requested_by"]:
            raise PermissionError("independent reviewer required")
        if len(reason.strip()) < 8:
            raise ValueError("substantive review reason required")
        state = "approved" if approve else "rejected"
        self.db.execute(
            "UPDATE resolution_merge_proposals_115 SET state=?,reviewed_by=?,reviewed_at=?,decision_reason=? WHERE proposal_id=? AND state='pending'",
            (state, reviewer, _now(), reason[:4000], proposal_id),
        )
        relationship = "same_entity_reviewed" if approve else "distinct_entity_reviewed"
        if approve:
            self.db.execute(
                "INSERT INTO resolution_links_115 VALUES(?,?,?,?,?,?,?,?,?)",
                (_id("rlnk"), proposal["case_id"], proposal["canonical_entity_id"], proposal["candidate_entity_id"], relationship, proposal["comparison_id"], reviewer, _now(), 1),
            )
        self.db.execute(
            "UPDATE resolution_comparisons_115 SET state=?,reviewed_by=?,reviewed_at=?,review_reason=? WHERE comparison_id=?",
            ("approved_same" if approve else "approved_distinct", reviewer, _now(), reason[:4000], proposal["comparison_id"]),
        )
        self._event(proposal["case_id"], reviewer, "ResolutionMergeReviewed", "merge_proposal", proposal_id, {"decision": state, "destructive_merge": False})
        return {"proposal_id": proposal_id, "state": state, "relationship": relationship, "destructive_merge": False}

    def verify_event_chain(self, case_id: str) -> dict[str, Any]:
        previous, errors = "GENESIS", []
        rows = self.db.all("SELECT * FROM resolution_events_115 WHERE case_id=? ORDER BY sequence", (case_id,))
        for row in rows:
            payload = json.loads(row["payload_json"])
            material = _json([row["event_id"], row["case_id"], row["actor"], row["event_type"], row["object_type"], row["object_id"], payload, previous, row["created_at"]])
            expected = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous or row["event_hash"] != expected:
                errors.append(row["event_id"])
            previous = row["event_hash"]
        return {"valid": not errors, "errors": errors, "events": len(rows)}

    def dashboard(self, case_id: str) -> dict[str, Any]:
        return {
            "entities": self.db.all("SELECT * FROM resolution_entities_115 WHERE case_id=? ORDER BY created_at", (case_id,)),
            "comparisons": self.db.all("SELECT comparison_id,left_entity_id,right_entity_id,total_score,classification,state FROM resolution_comparisons_115 WHERE case_id=? ORDER BY total_score DESC", (case_id,)),
            "proposals": self.db.all("SELECT * FROM resolution_merge_proposals_115 WHERE case_id=? ORDER BY requested_at DESC", (case_id,)),
            "links": self.db.all("SELECT * FROM resolution_links_115 WHERE case_id=? AND active=1", (case_id,)),
            "human_control": {
                "automatic_identity_confirmation": False,
                "automatic_destructive_merge": False,
                "independent_review_required": True,
                "status": "candidate_until_reviewed",
            },
        }
