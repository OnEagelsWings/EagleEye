from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _date(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc


class TimelineEngine117Service:
    """Review-gated temporal model derived from public-source candidate assertions.

    Events remain candidates until independently reviewed. Derivation from graph relations
    copies provenance links but never upgrades an assertion to fact automatically.
    """

    EVENT_TYPES = {
        "employment", "directorship", "membership", "publication", "appearance",
        "registration", "location", "organisation_event", "public_statement",
        "legal_public_record", "other",
    }
    PRECISIONS = {"day", "month", "year", "range", "unknown"}
    STATES = {"draft", "needs_review", "approved", "rejected", "retired"}
    STANCES = {"supports", "contradicts", "neutral"}

    def __init__(self, db, audit=None, kernel=None, graph=None):
        self.db = db
        self.audit = audit
        self.kernel = kernel
        self.graph = graph
        self._schema()

    def _schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS timeline_events_117(
                event_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                date_precision TEXT NOT NULL,
                location_entity_id TEXT,
                state TEXT NOT NULL,
                candidate_only INTEGER NOT NULL DEFAULT 1,
                confidence REAL NOT NULL,
                derived_from_relation_id TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_timeline117_case_date ON timeline_events_117(case_id,start_date,end_date,state);
            CREATE TABLE IF NOT EXISTS timeline_event_entities_117(
                link_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(event_id,entity_id,role)
            );
            CREATE TABLE IF NOT EXISTS timeline_event_sources_117(
                link_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                stance TEXT NOT NULL,
                weight REAL NOT NULL,
                rationale TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(event_id,source_id,stance)
            );
            CREATE TABLE IF NOT EXISTS timeline_reviews_117(
                review_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL UNIQUE,
                requested_by TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                state TEXT NOT NULL,
                reviewed_by TEXT,
                reviewed_at TEXT,
                decision_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS timeline_chains_117(
                chain_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                title TEXT NOT NULL,
                purpose TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS timeline_chain_members_117(
                chain_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                sequence_no INTEGER NOT NULL,
                transition_note TEXT NOT NULL,
                PRIMARY KEY(chain_id,event_id),
                UNIQUE(chain_id,sequence_no)
            );
            CREATE TABLE IF NOT EXISTS timeline_events_log_117(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_log_id TEXT UNIQUE NOT NULL,
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

    def _log(self, case_id: str, actor: str, event_type: str, object_type: str,
             object_id: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        event_log_id, ts = _id("tevt"), _now()
        row = self.db.one("SELECT event_hash FROM timeline_events_log_117 WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous = row["event_hash"] if row else "GENESIS"
        digest = hashlib.sha256(_json([event_log_id, case_id, actor, event_type, object_type, object_id, payload, previous, ts]).encode()).hexdigest()
        self.db.execute(
            "INSERT INTO timeline_events_log_117(event_log_id,case_id,actor,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (event_log_id, case_id, actor, event_type, object_type, object_id, _json(payload), previous, digest, ts),
        )
        if self.kernel:
            self.kernel.event(case_id, actor, event_type, object_type, object_id, payload)

    def _entity(self, case_id: str, entity_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM entities_109 WHERE case_id=? AND entity_id=?", (case_id, entity_id))
        if not row:
            raise ValueError("entity not found in case")
        return row

    def create_event(self, case_id: str, event_type: str, title: str, description: str,
                     created_by: str, start_date: str | None = None, end_date: str | None = None,
                     date_precision: str = "unknown", confidence: float = 0.5,
                     location_entity_id: str | None = None,
                     derived_from_relation_id: str | None = None) -> str:
        if event_type not in self.EVENT_TYPES:
            raise ValueError("unsupported event type")
        if date_precision not in self.PRECISIONS:
            raise ValueError("invalid date precision")
        start_date, end_date = _date(start_date), _date(end_date)
        if start_date and end_date and start_date > end_date:
            raise ValueError("invalid event interval")
        if len(title.strip()) < 3 or len(title) > 500 or len(description.strip()) < 8 or len(description) > 10000:
            raise ValueError("title and description required")
        if location_entity_id:
            self._entity(case_id, location_entity_id)
        if derived_from_relation_id:
            rel = self.db.one("SELECT * FROM graph_relations_116 WHERE relation_id=? AND case_id=?", (derived_from_relation_id, case_id))
            if not rel:
                raise ValueError("source relation not found in case")
        event_id, ts = _id("time"), _now()
        self.db.execute(
            "INSERT INTO timeline_events_117 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (event_id, case_id, event_type, title.strip(), description.strip(), start_date, end_date,
             date_precision, location_entity_id, "draft", 1, _clamp(confidence),
             derived_from_relation_id, created_by, ts, ts),
        )
        self._log(case_id, created_by, "TimelineEventCreated", "timeline_event", event_id,
                  {"event_type": event_type, "start_date": start_date, "end_date": end_date})
        return event_id

    def link_entity(self, event_id: str, entity_id: str, role: str, actor: str) -> str:
        event = self._event(event_id)
        self._entity(event["case_id"], entity_id)
        if not role.strip() or len(role) > 200:
            raise ValueError("role required")
        link_id = _id("tent")
        self.db.execute("INSERT INTO timeline_event_entities_117 VALUES(?,?,?,?,?)",
                        (link_id, event_id, entity_id, role.strip(), _now()))
        self._log(event["case_id"], actor, "TimelineEntityLinked", "timeline_event", event_id,
                  {"entity_id": entity_id, "role": role.strip()})
        return link_id

    def link_source(self, event_id: str, source_id: str, stance: str, weight: float,
                    rationale: str, actor: str) -> str:
        if stance not in self.STANCES:
            raise ValueError("invalid stance")
        event = self._event(event_id)
        source = self.db.one("SELECT * FROM graph_sources_116 WHERE source_id=? AND case_id=?", (source_id, event["case_id"]))
        if not source:
            raise ValueError("source not found in case")
        if len(rationale.strip()) < 6:
            raise ValueError("rationale required")
        link_id = _id("tsrc")
        self.db.execute("INSERT INTO timeline_event_sources_117 VALUES(?,?,?,?,?,?,?,?)",
                        (link_id, event_id, source_id, stance, _clamp(weight), rationale[:4000], actor, _now()))
        self._log(event["case_id"], actor, "TimelineSourceLinked", "timeline_event", event_id,
                  {"source_id": source_id, "stance": stance})
        return link_id

    def derive_from_relation(self, relation_id: str, actor: str) -> str:
        rel = self.db.one("SELECT * FROM graph_relations_116 WHERE relation_id=?", (relation_id,))
        if not rel:
            raise ValueError("relation not found")
        ver = self.db.one("SELECT * FROM graph_relation_versions_116 WHERE relation_id=? AND version_no=?",
                          (relation_id, rel["current_version"]))
        mapping = {
            "works_for": "employment", "formerly_worked_for": "employment", "director_of": "directorship",
            "member_of": "membership", "published": "publication", "spoke_at": "appearance",
            "registered_to": "registration", "located_at": "location",
        }
        event_type = mapping.get(rel["predicate"], "other")
        event_id = self.create_event(
            rel["case_id"], event_type, ver["assertion_text"][:500], ver["assertion_text"], actor,
            ver["valid_from"], ver["valid_to"], "range" if ver["valid_to"] else ("day" if ver["valid_from"] else "unknown"),
            confidence=(float(ver["confidence_identity"]) + float(ver["confidence_source"]) + float(ver["confidence_plausibility"])) / 3,
            derived_from_relation_id=relation_id,
        )
        self.link_entity(event_id, rel["subject_entity_id"], "subject", actor)
        self.link_entity(event_id, rel["object_entity_id"], "object", actor)
        rows = self.db.all("SELECT source_id,stance,weight,rationale FROM graph_relation_evidence_116 WHERE relation_id=? AND version_no=?",
                           (relation_id, rel["current_version"]))
        for row in rows:
            self.link_source(event_id, row["source_id"], row["stance"], row["weight"], row["rationale"], actor)
        self._log(rel["case_id"], actor, "TimelineDerivedFromRelation", "timeline_event", event_id,
                  {"relation_id": relation_id})
        return event_id

    def _event(self, event_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM timeline_events_117 WHERE event_id=?", (event_id,))
        if not row:
            raise ValueError("timeline event not found")
        return row

    def request_review(self, event_id: str, requested_by: str) -> str:
        event = self._event(event_id)
        support = self.db.one("SELECT COUNT(*) AS n FROM timeline_event_sources_117 WHERE event_id=? AND stance='supports'", (event_id,))["n"]
        if not support:
            raise ValueError("at least one supporting source required")
        review_id = _id("trev")
        self.db.execute("INSERT INTO timeline_reviews_117 VALUES(?,?,?,?,?,?,?,?)",
                        (review_id, event_id, requested_by, _now(), "pending", None, None, None))
        self.db.execute("UPDATE timeline_events_117 SET state='needs_review',updated_at=? WHERE event_id=?", (_now(), event_id))
        self._log(event["case_id"], requested_by, "TimelineReviewRequested", "timeline_event", event_id)
        return review_id

    def review(self, review_id: str, reviewer: str, approve: bool, reason: str) -> bool:
        review = self.db.one("SELECT * FROM timeline_reviews_117 WHERE review_id=?", (review_id,))
        if not review or review["state"] != "pending":
            raise ValueError("review unavailable")
        if review["requested_by"] == reviewer:
            raise PermissionError("independent reviewer required")
        if len(reason.strip()) < 12:
            raise ValueError("substantive review reason required")
        event = self._event(review["event_id"])
        decision = "approved" if approve else "rejected"
        with self.db.conn:
            cur = self.db.conn.execute(
                "UPDATE timeline_reviews_117 SET state=?,reviewed_by=?,reviewed_at=?,decision_reason=? WHERE review_id=? AND state='pending'",
                (decision, reviewer, _now(), reason[:4000], review_id),
            )
            if cur.rowcount != 1:
                raise ValueError("review already consumed")
            self.db.conn.execute("UPDATE timeline_events_117 SET state=?,candidate_only=?,updated_at=? WHERE event_id=?",
                                 (decision, 0 if approve else 1, _now(), review["event_id"]))
        self._log(event["case_id"], reviewer, "TimelineEventReviewed", "timeline_event", event["event_id"], {"decision": decision})
        return approve

    def event_record(self, event_id: str) -> dict[str, Any]:
        event = self._event(event_id)
        entities = self.db.all("SELECT * FROM timeline_event_entities_117 WHERE event_id=? ORDER BY role,entity_id", (event_id,))
        sources = self.db.all("SELECT l.*,s.title,s.independence_group,s.reliability FROM timeline_event_sources_117 l JOIN graph_sources_116 s ON s.source_id=l.source_id WHERE l.event_id=? ORDER BY l.created_at", (event_id,))
        return {"event": event, "entities": entities, "sources": sources, "epistemic_status": "reviewed_event_not_fact" if event["state"] == "approved" else "candidate_event"}

    def case_timeline(self, case_id: str, include_retired: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM timeline_events_117 WHERE case_id=?"
        params: list[Any] = [case_id]
        if not include_retired:
            sql += " AND state!='retired'"
        sql += " ORDER BY COALESCE(start_date,'9999-12-31'),COALESCE(end_date,start_date),created_at"
        return self.db.all(sql, params)

    def overlaps(self, case_id: str, entity_id: str | None = None) -> list[dict[str, Any]]:
        rows = self.case_timeline(case_id)
        if entity_id:
            allowed = {r["event_id"] for r in self.db.all("SELECT event_id FROM timeline_event_entities_117 WHERE entity_id=?", (entity_id,))}
            rows = [r for r in rows if r["event_id"] in allowed]
        conflicts = []
        for i, left in enumerate(rows):
            if not left["start_date"]:
                continue
            l_end = left["end_date"] or left["start_date"]
            for right in rows[i + 1:]:
                if not right["start_date"]:
                    continue
                r_end = right["end_date"] or right["start_date"]
                if left["start_date"] <= r_end and right["start_date"] <= l_end:
                    conflicts.append({"left_event_id": left["event_id"], "right_event_id": right["event_id"], "overlap_start": max(left["start_date"], right["start_date"]), "overlap_end": min(l_end, r_end), "status": "requires_context_review"})
        return conflicts

    def temporal_conflicts(self, case_id: str) -> list[dict[str, Any]]:
        conflicts = []
        for overlap in self.overlaps(case_id):
            left = self._event(overlap["left_event_id"]); right = self._event(overlap["right_event_id"])
            left_entities = {x["entity_id"] for x in self.db.all("SELECT entity_id FROM timeline_event_entities_117 WHERE event_id=?", (left["event_id"],))}
            right_entities = {x["entity_id"] for x in self.db.all("SELECT entity_id FROM timeline_event_entities_117 WHERE event_id=?", (right["event_id"],))}
            shared = sorted(left_entities & right_entities)
            if shared and left["event_type"] == right["event_type"] and (left["location_entity_id"] or right["location_entity_id"]) and left["location_entity_id"] != right["location_entity_id"]:
                conflicts.append({**overlap, "shared_entities": shared, "reason": "same event type overlaps at different locations", "classification": "possible_temporal_conflict"})
        return conflicts

    def create_chain(self, case_id: str, title: str, purpose: str, event_ids: list[str], actor: str) -> str:
        if len(event_ids) < 2:
            raise ValueError("event chain requires at least two events")
        events = [self._event(eid) for eid in event_ids]
        if any(event["case_id"] != case_id for event in events):
            raise ValueError("cross-case event chain blocked")
        ordered = sorted(events, key=lambda r: (r["start_date"] or "9999-12-31", r["created_at"]))
        chain_id = _id("tchain")
        self.db.execute("INSERT INTO timeline_chains_117 VALUES(?,?,?,?,?,?)", (chain_id, case_id, title[:500], purpose[:4000], actor, _now()))
        for index, event in enumerate(ordered, 1):
            self.db.execute("INSERT INTO timeline_chain_members_117 VALUES(?,?,?,?)", (chain_id, event["event_id"], index, "chronological candidate sequence"))
        self._log(case_id, actor, "TimelineChainCreated", "timeline_chain", chain_id, {"events": [e["event_id"] for e in ordered]})
        return chain_id

    def verify_chain(self, case_id: str) -> bool:
        previous = "GENESIS"
        rows = self.db.all("SELECT * FROM timeline_events_log_117 WHERE case_id=? ORDER BY sequence", (case_id,))
        for row in rows:
            if row["previous_hash"] != previous:
                return False
            material = _json([row["event_log_id"], row["case_id"], row["actor"], row["event_type"], row["object_type"], row["object_id"], json.loads(row["payload_json"]), row["previous_hash"], row["created_at"]])
            if hashlib.sha256(material.encode()).hexdigest() != row["event_hash"]:
                return False
            previous = row["event_hash"]
        return True
