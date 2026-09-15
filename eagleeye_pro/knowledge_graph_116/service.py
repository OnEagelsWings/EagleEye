from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class KnowledgeGraph116Service:
    """Versioned semantic graph with provenance, counter-evidence and review gates.

    Relations are assertions, not facts. Original entities and prior relation versions are
    never overwritten. Approval creates a reviewed version; retirement is non-destructive.
    """

    PREDICATES = {
        "works_for", "formerly_worked_for", "director_of", "member_of", "owns_domain",
        "uses_account", "published", "mentioned_in", "spoke_at", "located_at",
        "participated_in", "registered_to", "alias_of", "associated_with", "other",
    }
    STANCES = {"supports", "contradicts", "neutral"}
    STATES = {"draft", "needs_review", "approved", "rejected", "retired"}
    CRITICAL_PREDICATES = {"alias_of", "registered_to", "owns_domain", "director_of"}

    def __init__(self, db, audit=None, kernel=None):
        self.db = db
        self.audit = audit
        self.kernel = kernel
        self._schema()

    def _schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS graph_predicates_116(
                predicate TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                inverse_label TEXT,
                allowed_subject_types_json TEXT NOT NULL,
                allowed_object_types_json TEXT NOT NULL,
                critical INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS graph_relations_116(
                relation_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                subject_entity_id TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object_entity_id TEXT NOT NULL,
                current_version INTEGER NOT NULL,
                state TEXT NOT NULL,
                candidate_only INTEGER NOT NULL DEFAULT 1,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(case_id,subject_entity_id,predicate,object_entity_id)
            );
            CREATE INDEX IF NOT EXISTS idx_graph_relations116_case ON graph_relations_116(case_id,state,predicate);
            CREATE TABLE IF NOT EXISTS graph_relation_versions_116(
                version_id TEXT PRIMARY KEY,
                relation_id TEXT NOT NULL,
                version_no INTEGER NOT NULL,
                valid_from TEXT,
                valid_to TEXT,
                observed_at TEXT,
                assertion_text TEXT NOT NULL,
                confidence_identity REAL NOT NULL,
                confidence_source REAL NOT NULL,
                confidence_recency REAL NOT NULL,
                confidence_independence REAL NOT NULL,
                confidence_completeness REAL NOT NULL,
                confidence_plausibility REAL NOT NULL,
                state TEXT NOT NULL,
                change_reason TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reviewed_by TEXT,
                reviewed_at TEXT,
                review_reason TEXT,
                previous_version_hash TEXT NOT NULL,
                version_hash TEXT UNIQUE NOT NULL,
                UNIQUE(relation_id,version_no)
            );
            CREATE TABLE IF NOT EXISTS graph_sources_116(
                source_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                canonical_url TEXT,
                title TEXT NOT NULL,
                publisher TEXT,
                author TEXT,
                published_at TEXT,
                retrieved_at TEXT NOT NULL,
                source_type TEXT NOT NULL,
                reliability REAL NOT NULL,
                independence_group TEXT NOT NULL,
                content_hash TEXT,
                archive_ref TEXT,
                metadata_json TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_graph_sources116_case ON graph_sources_116(case_id,independence_group);
            CREATE TABLE IF NOT EXISTS graph_relation_evidence_116(
                evidence_link_id TEXT PRIMARY KEY,
                relation_id TEXT NOT NULL,
                version_no INTEGER NOT NULL,
                source_id TEXT NOT NULL,
                stance TEXT NOT NULL,
                weight REAL NOT NULL,
                excerpt TEXT,
                rationale TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(relation_id,version_no,source_id,stance)
            );
            CREATE TABLE IF NOT EXISTS graph_relation_reviews_116(
                review_id TEXT PRIMARY KEY,
                relation_id TEXT NOT NULL,
                version_no INTEGER NOT NULL,
                requested_by TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                state TEXT NOT NULL,
                reviewed_by TEXT,
                reviewed_at TEXT,
                decision_reason TEXT,
                UNIQUE(relation_id,version_no)
            );
            CREATE TABLE IF NOT EXISTS graph_events_116(
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
        for predicate in sorted(self.PREDICATES):
            self.db.execute(
                "INSERT OR IGNORE INTO graph_predicates_116 VALUES(?,?,?,?,?,?,?)",
                (predicate, predicate.replace("_", " "), None, _json(["*"]), _json(["*"]),
                 1 if predicate in self.CRITICAL_PREDICATES else 0, _now()),
            )
        self.db.conn.commit()

    def _event(self, case_id: str, actor: str, event_type: str, object_type: str,
               object_id: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        event_id, ts = _id("gevt"), _now()
        row = self.db.one("SELECT event_hash FROM graph_events_116 WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous = row["event_hash"] if row else "GENESIS"
        material = _json([event_id, case_id, actor, event_type, object_type, object_id, payload, previous, ts])
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        self.db.execute(
            "INSERT INTO graph_events_116(event_id,case_id,actor,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (event_id, case_id, actor, event_type, object_type, object_id, _json(payload), previous, digest, ts),
        )
        if self.kernel:
            self.kernel.event(case_id, actor, event_type, object_type, object_id, payload)

    def _entity(self, case_id: str, entity_id: str):
        row = self.db.one("SELECT * FROM entities_109 WHERE case_id=? AND entity_id=?", (case_id, entity_id))
        if not row:
            raise ValueError("entity not found in case")
        return row

    def register_source(self, case_id: str, title: str, source_type: str, reliability: float,
                        independence_group: str, created_by: str, canonical_url: str | None = None,
                        publisher: str | None = None, author: str | None = None,
                        published_at: str | None = None, retrieved_at: str | None = None,
                        content_hash: str | None = None, archive_ref: str | None = None,
                        metadata: dict[str, Any] | None = None) -> str:
        if not title.strip() or len(title) > 1000:
            raise ValueError("invalid source title")
        if not independence_group.strip() or len(independence_group) > 300:
            raise ValueError("independence group required")
        source_id, ts = _id("gsrc"), _now()
        self.db.execute(
            "INSERT INTO graph_sources_116 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (source_id, case_id, canonical_url, title.strip(), publisher, author, published_at,
             retrieved_at or ts, source_type[:100], _clamp(reliability), independence_group[:300],
             content_hash, archive_ref, _json(metadata or {}), created_by, ts),
        )
        self._event(case_id, created_by, "GraphSourceRegistered", "source", source_id,
                    {"independence_group": independence_group})
        return source_id

    def create_relation(self, case_id: str, subject_entity_id: str, predicate: str,
                        object_entity_id: str, assertion_text: str, created_by: str,
                        valid_from: str | None = None, valid_to: str | None = None,
                        observed_at: str | None = None, quality: dict[str, float] | None = None,
                        change_reason: str = "initial assertion") -> str:
        if predicate not in self.PREDICATES:
            raise ValueError("unsupported predicate")
        if subject_entity_id == object_entity_id and predicate != "alias_of":
            raise ValueError("self relation not allowed")
        self._entity(case_id, subject_entity_id)
        self._entity(case_id, object_entity_id)
        if valid_from and valid_to and valid_from > valid_to:
            raise ValueError("invalid validity interval")
        if len(assertion_text.strip()) < 8 or len(assertion_text) > 10000:
            raise ValueError("assertion text required")
        relation_id, ts = _id("grel"), _now()
        q = quality or {}
        scores = [
            _clamp(q.get("identity", 0.5)), _clamp(q.get("source", 0.0)),
            _clamp(q.get("recency", 0.5)), _clamp(q.get("independence", 0.0)),
            _clamp(q.get("completeness", 0.25)), _clamp(q.get("plausibility", 0.5)),
        ]
        self.db.execute(
            "INSERT INTO graph_relations_116 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (relation_id, case_id, subject_entity_id, predicate, object_entity_id, 1, "draft", 1,
             created_by, ts, ts),
        )
        self._insert_version(relation_id, 1, valid_from, valid_to, observed_at, assertion_text,
                             scores, "draft", change_reason, created_by, "GENESIS")
        self._event(case_id, created_by, "GraphRelationCreated", "relation", relation_id,
                    {"predicate": predicate, "version": 1})
        return relation_id

    def _insert_version(self, relation_id: str, version_no: int, valid_from: str | None,
                        valid_to: str | None, observed_at: str | None, assertion_text: str,
                        scores: list[float], state: str, reason: str, actor: str,
                        previous_hash: str) -> str:
        version_id, ts = _id("gver"), _now()
        material = _json([relation_id, version_no, valid_from, valid_to, observed_at, assertion_text,
                          scores, state, reason, actor, previous_hash, ts])
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        self.db.execute(
            "INSERT INTO graph_relation_versions_116(version_id,relation_id,version_no,valid_from,valid_to,observed_at,assertion_text,confidence_identity,confidence_source,confidence_recency,confidence_independence,confidence_completeness,confidence_plausibility,state,change_reason,created_by,created_at,previous_version_hash,version_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (version_id, relation_id, version_no, valid_from, valid_to, observed_at, assertion_text,
             *scores, state, reason[:2000], actor, ts, previous_hash, digest),
        )
        return version_id

    def add_evidence(self, relation_id: str, source_id: str, stance: str, weight: float,
                     rationale: str, actor: str, excerpt: str | None = None,
                     version_no: int | None = None) -> str:
        if stance not in self.STANCES:
            raise ValueError("invalid stance")
        relation = self.db.one("SELECT * FROM graph_relations_116 WHERE relation_id=?", (relation_id,))
        source = self.db.one("SELECT * FROM graph_sources_116 WHERE source_id=?", (source_id,))
        if not relation or not source or source["case_id"] != relation["case_id"]:
            raise ValueError("relation/source mismatch")
        version_no = int(version_no or relation["current_version"])
        if not self.db.one("SELECT 1 FROM graph_relation_versions_116 WHERE relation_id=? AND version_no=?", (relation_id, version_no)):
            raise ValueError("relation version missing")
        link_id = _id("gev")
        self.db.execute(
            "INSERT INTO graph_relation_evidence_116 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (link_id, relation_id, version_no, source_id, stance, _clamp(weight),
             (excerpt or "")[:4000] or None, rationale[:4000], actor, _now()),
        )
        self._event(relation["case_id"], actor, "GraphEvidenceLinked", "relation", relation_id,
                    {"source_id": source_id, "stance": stance, "version": version_no})
        return link_id

    def quality_summary(self, relation_id: str, version_no: int | None = None) -> dict[str, Any]:
        rel = self.db.one("SELECT * FROM graph_relations_116 WHERE relation_id=?", (relation_id,))
        if not rel:
            raise ValueError("relation not found")
        version_no = int(version_no or rel["current_version"])
        v = self.db.one("SELECT * FROM graph_relation_versions_116 WHERE relation_id=? AND version_no=?", (relation_id, version_no))
        rows = self.db.all(
            "SELECT e.*,s.reliability,s.independence_group FROM graph_relation_evidence_116 e JOIN graph_sources_116 s ON s.source_id=e.source_id WHERE e.relation_id=? AND e.version_no=?",
            (relation_id, version_no),
        )
        groups: dict[tuple[str, str], float] = {}
        for row in rows:
            key = (row["independence_group"], row["stance"])
            groups[key] = max(groups.get(key, 0.0), float(row["weight"]) * float(row["reliability"]))
        support = sum(score for (group, stance), score in groups.items() if stance == "supports")
        contradict = sum(score for (group, stance), score in groups.items() if stance == "contradicts")
        return {
            "relation_id": relation_id, "version_no": version_no, "state": v["state"],
            "dimensions": {
                "identity": v["confidence_identity"], "source": v["confidence_source"],
                "recency": v["confidence_recency"], "independence": v["confidence_independence"],
                "completeness": v["confidence_completeness"], "plausibility": v["confidence_plausibility"],
            },
            "independent_support": round(support, 4),
            "independent_contradiction": round(contradict, 4),
            "supporting_sources": sum(1 for r in rows if r["stance"] == "supports"),
            "contradicting_sources": sum(1 for r in rows if r["stance"] == "contradicts"),
            "epistemic_status": "reviewed_assertion_not_fact" if v["state"] == "approved" else "candidate_assertion",
        }

    def revise_relation(self, relation_id: str, actor: str, assertion_text: str,
                        change_reason: str, valid_from: str | None = None,
                        valid_to: str | None = None, observed_at: str | None = None,
                        quality: dict[str, float] | None = None) -> int:
        rel = self.db.one("SELECT * FROM graph_relations_116 WHERE relation_id=?", (relation_id,))
        if not rel:
            raise ValueError("relation not found")
        prev = self.db.one("SELECT * FROM graph_relation_versions_116 WHERE relation_id=? AND version_no=?", (relation_id, rel["current_version"]))
        if valid_from and valid_to and valid_from > valid_to:
            raise ValueError("invalid validity interval")
        q = quality or {}
        scores = [
            _clamp(q.get("identity", prev["confidence_identity"])), _clamp(q.get("source", prev["confidence_source"])),
            _clamp(q.get("recency", prev["confidence_recency"])), _clamp(q.get("independence", prev["confidence_independence"])),
            _clamp(q.get("completeness", prev["confidence_completeness"])), _clamp(q.get("plausibility", prev["confidence_plausibility"])),
        ]
        new_no = int(rel["current_version"]) + 1
        self._insert_version(relation_id, new_no, valid_from, valid_to, observed_at,
                             assertion_text, scores, "draft", change_reason, actor, prev["version_hash"])
        self.db.execute("UPDATE graph_relations_116 SET current_version=?,state='draft',candidate_only=1,updated_at=? WHERE relation_id=?",
                        (new_no, _now(), relation_id))
        self._event(rel["case_id"], actor, "GraphRelationRevised", "relation", relation_id,
                    {"version": new_no, "reason": change_reason[:500]})
        return new_no

    def request_review(self, relation_id: str, requested_by: str) -> str:
        rel = self.db.one("SELECT * FROM graph_relations_116 WHERE relation_id=?", (relation_id,))
        if not rel:
            raise ValueError("relation not found")
        version_no = int(rel["current_version"])
        summary = self.quality_summary(relation_id, version_no)
        if summary["supporting_sources"] == 0:
            raise ValueError("at least one supporting source required")
        review_id = _id("grev")
        self.db.execute("INSERT INTO graph_relation_reviews_116 VALUES(?,?,?,?,?,?,?,?,?)",
                        (review_id, relation_id, version_no, requested_by, _now(), "pending", None, None, None))
        self.db.execute("UPDATE graph_relations_116 SET state='needs_review',updated_at=? WHERE relation_id=?", (_now(), relation_id))
        self.db.execute("UPDATE graph_relation_versions_116 SET state='needs_review' WHERE relation_id=? AND version_no=?", (relation_id, version_no))
        self._event(rel["case_id"], requested_by, "GraphReviewRequested", "relation", relation_id, {"version": version_no})
        return review_id

    def review(self, review_id: str, reviewer: str, approve: bool, reason: str) -> bool:
        review = self.db.one("SELECT * FROM graph_relation_reviews_116 WHERE review_id=?", (review_id,))
        if not review or review["state"] != "pending":
            raise ValueError("review unavailable")
        if review["requested_by"] == reviewer:
            raise PermissionError("independent reviewer required")
        if len(reason.strip()) < 12:
            raise ValueError("substantive review reason required")
        rel = self.db.one("SELECT * FROM graph_relations_116 WHERE relation_id=?", (review["relation_id"],))
        decision = "approved" if approve else "rejected"
        with self.db.conn:
            cur = self.db.conn.execute(
                "UPDATE graph_relation_reviews_116 SET state=?,reviewed_by=?,reviewed_at=?,decision_reason=? WHERE review_id=? AND state='pending'",
                (decision, reviewer, _now(), reason[:4000], review_id),
            )
            if cur.rowcount != 1:
                raise ValueError("review already consumed")
            self.db.conn.execute("UPDATE graph_relation_versions_116 SET state=?,reviewed_by=?,reviewed_at=?,review_reason=? WHERE relation_id=? AND version_no=?",
                                 (decision, reviewer, _now(), reason[:4000], review["relation_id"], review["version_no"]))
            self.db.conn.execute("UPDATE graph_relations_116 SET state=?,candidate_only=?,updated_at=? WHERE relation_id=?",
                                 (decision, 0 if approve else 1, _now(), review["relation_id"]))
        self._event(rel["case_id"], reviewer, "GraphRelationReviewed", "relation", rel["relation_id"],
                    {"version": review["version_no"], "decision": decision})
        return approve

    def retire_relation(self, relation_id: str, actor: str, reason: str) -> None:
        if len(reason.strip()) < 8:
            raise ValueError("retirement reason required")
        rel = self.db.one("SELECT * FROM graph_relations_116 WHERE relation_id=?", (relation_id,))
        if not rel:
            raise ValueError("relation not found")
        self.db.execute("UPDATE graph_relations_116 SET state='retired',candidate_only=1,updated_at=? WHERE relation_id=?", (_now(), relation_id))
        self._event(rel["case_id"], actor, "GraphRelationRetired", "relation", relation_id, {"reason": reason[:1000]})

    def relation_record(self, relation_id: str) -> dict[str, Any]:
        rel = self.db.one("SELECT * FROM graph_relations_116 WHERE relation_id=?", (relation_id,))
        if not rel:
            raise ValueError("relation not found")
        versions = self.db.all("SELECT * FROM graph_relation_versions_116 WHERE relation_id=? ORDER BY version_no", (relation_id,))
        evidence = self.db.all("SELECT e.*,s.title,s.canonical_url,s.independence_group,s.reliability FROM graph_relation_evidence_116 e JOIN graph_sources_116 s ON s.source_id=e.source_id WHERE e.relation_id=? ORDER BY e.version_no,e.created_at", (relation_id,))
        return {"relation": rel, "versions": versions, "evidence": evidence,
                "quality": self.quality_summary(relation_id)}

    def case_graph(self, case_id: str, state: str | None = None,
                   predicate: str | None = None, at_time: str | None = None) -> dict[str, Any]:
        sql = "SELECT * FROM graph_relations_116 WHERE case_id=?"
        params: list[Any] = [case_id]
        if state:
            if state not in self.STATES:
                raise ValueError("invalid state")
            sql += " AND state=?"; params.append(state)
        if predicate:
            if predicate not in self.PREDICATES:
                raise ValueError("invalid predicate")
            sql += " AND predicate=?"; params.append(predicate)
        relations = self.db.all(sql + " ORDER BY updated_at DESC", tuple(params))
        output = []
        entity_ids = set()
        for rel in relations:
            version = self.db.one("SELECT * FROM graph_relation_versions_116 WHERE relation_id=? AND version_no=?", (rel["relation_id"], rel["current_version"]))
            if at_time and ((version["valid_from"] and version["valid_from"] > at_time) or (version["valid_to"] and version["valid_to"] < at_time)):
                continue
            output.append({"relation": rel, "version": version, "quality": self.quality_summary(rel["relation_id"])})
            entity_ids.update([rel["subject_entity_id"], rel["object_entity_id"]])
        entities = [self.db.one("SELECT * FROM entities_109 WHERE entity_id=?", (eid,)) for eid in sorted(entity_ids)]
        return {"case_id": case_id, "entities": entities, "relations": output,
                "epistemic_notice": "Graph relations are reviewed assertions, not automatically established facts."}

    def verify_chain(self, case_id: str) -> bool:
        rows = self.db.all("SELECT * FROM graph_events_116 WHERE case_id=? ORDER BY sequence", (case_id,))
        previous = "GENESIS"
        for row in rows:
            material = _json([row["event_id"], row["case_id"], row["actor"], row["event_type"],
                              row["object_type"], row["object_id"], json.loads(row["payload_json"]),
                              previous, row["created_at"]])
            if row["previous_hash"] != previous or row["event_hash"] != hashlib.sha256(material.encode("utf-8")).hexdigest():
                return False
            previous = row["event_hash"]
        return True
