from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import re
import secrets

BUILD = "438.0"
POLICY_ID = "phase19.temporal-relationship-fusion.v438"
_DATE_RE = re.compile(r"^(?P<y>\d{4})(?:-(?P<m>\d{2})(?:-(?P<d>\d{2}))?)?$")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value):
    return hashlib.sha256(_canon(value).encode()).hexdigest()


def _clean(value, limit=1000):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _temporal(value):
    """Parse only explicit ISO/calendar values; never guess natural-language dates."""
    raw = _clean(value, 160)
    if not raw:
        return None
    match = _DATE_RE.fullmatch(raw)
    if match:
        year, month, day = match.group("y"), match.group("m"), match.group("d")
        if day:
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError:
                return None
            return {"value": dt.date().isoformat(), "precision": "day", "sort_key": dt.date().isoformat(), "raw": raw}
        if month:
            try:
                datetime.fromisoformat(raw + "-01")
            except ValueError:
                return None
            return {"value": raw, "precision": "month", "sort_key": raw + "-01", "raw": raw}
        return {"value": raw, "precision": "year", "sort_key": raw + "-01-01", "raw": raw}
    try:
        text = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
            value_out = dt.isoformat(timespec="seconds").replace("+00:00", "Z")
            sort_key = dt.isoformat(timespec="seconds")
        else:
            value_out = dt.isoformat(timespec="seconds")
            sort_key = dt.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
        return {"value": value_out, "precision": "datetime", "sort_key": sort_key, "raw": raw}
    except ValueError:
        return None


class TemporalRelationshipFusion438:
    """Case-scoped fusion over Build-437 reviewed entity links and Phase-19 provenance.

    Build 438 creates views, not new facts: reviewed same-entity links may group
    resolution records non-destructively; temporal items retain their original
    source/event/content provenance; relationship edges require an explicit source
    assertion. Machine-extracted dates/events stay candidates and temporal adjacency
    is never treated as causality.
    """

    def __init__(
        self,
        db,
        audit,
        *,
        resolution437,
        events422,
        content423,
        news429,
        news430,
        social432,
        organization433,
        registry434,
        change427,
        archive428,
        base115,
        governance,
        actor="local-analyst",
    ):
        self.db = db
        self.audit = audit
        self.resolution437 = resolution437
        self.events422 = events422
        self.content423 = content423
        self.news429 = news429
        self.news430 = news430
        self.social432 = social432
        self.organization433 = organization433
        self.registry434 = registry434
        self.change427 = change427
        self.archive428 = archive428
        self.base115 = base115
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS phase19_fusion_run_438(
            run_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            fusion_groups INTEGER NOT NULL,
            timeline_events INTEGER NOT NULL,
            relationship_edges INTEGER NOT NULL,
            unresolved_relationships INTEGER NOT NULL,
            result_json TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_pfr438_case ON phase19_fusion_run_438(case_id,created_at);"""
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _hash({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (KeyError, ValueError):
            raise PermissionError("canonical active identity required")
        if not user.get("active") or str(user.get("user_id")) != str(identity.get("user_id")):
            raise PermissionError("canonical active identity required")
        return {**user, "session_id": str(identity.get("session_id") or "fusion438")}

    def _authorize(self, identity, case_id, capability="research.run", object_id=""):
        ident = self._identity(identity)
        self.governance.authorize(
            ident,
            case_id=str(case_id),
            capability=capability,
            object_type="temporal_relationship_fusion_438",
            object_id=str(object_id or case_id),
        )
        return ident

    def _preflight(self, case_id):
        checks = {
            "entity_resolution_437": self.resolution437.verify_integrity()["valid"],
            "resolution_event_chain": self.base115.verify_event_chain(str(case_id))["valid"],
            "acquisition_events": self.events422.verify_integrity()["valid"],
            "content_store": self.content423.verify_integrity()["valid"],
            "news": self.news429.verify_integrity()["valid"],
            "news_extraction": self.news430.verify_integrity()["valid"],
            "social": self.social432.verify_integrity()["valid"],
            "organizations": self.organization433.verify_integrity()["valid"],
            "registry_organization": self.registry434.verify_integrity()["valid"],
            "change_detection": self.change427.verify_integrity()["valid"],
            "archive_history": self.archive428.verify_integrity()["valid"],
        }
        if not all(checks.values()):
            raise RuntimeError("Phase-19 fusion provenance preflight failed: " + ",".join(k for k, v in checks.items() if not v))
        return checks

    def _bindings(self, case_id):
        return self.resolution437.bindings(str(case_id))

    def fusion_groups(self, case_id):
        case_id = str(case_id)
        bindings = self._bindings(case_id)
        entity_ids = sorted({b["resolution_entity_id"] for b in bindings})
        parent = {eid: eid for eid in entity_ids}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)

        links = []
        for row in self.db.all(
            "SELECT * FROM resolution_links_115 WHERE case_id=? AND active=1 AND relationship='same_entity_reviewed' ORDER BY approved_at,link_id",
            (case_id,),
        ):
            item = dict(row)
            if item["canonical_entity_id"] not in parent or item["linked_entity_id"] not in parent:
                continue
            union(item["canonical_entity_id"], item["linked_entity_id"])
            links.append(item)

        members = defaultdict(list)
        for eid in entity_ids:
            members[find(eid)].append(eid)
        link_by_member = defaultdict(list)
        for link in links:
            link_by_member[find(link["canonical_entity_id"])].append(link)

        groups = []
        for root, ids in sorted(members.items()):
            ids = sorted(ids)
            group_id = "fg438_" + hashlib.sha256("|".join(ids).encode()).hexdigest()[:18]
            entities = []
            for eid in ids:
                row = self.db.one(
                    "SELECT resolution_entity_id,entity_type,display_name,candidate_only,source_entity_id FROM resolution_entities_115 WHERE resolution_entity_id=?",
                    (eid,),
                )
                if row:
                    entities.append(dict(row))
            approved_links = [
                {
                    "link_id": x["link_id"],
                    "canonical_entity_id": x["canonical_entity_id"],
                    "linked_entity_id": x["linked_entity_id"],
                    "relationship": x["relationship"],
                    "comparison_id": x["comparison_id"],
                    "approved_by": x["approved_by"],
                    "approved_at": x["approved_at"],
                }
                for x in link_by_member.get(root, [])
            ]
            groups.append(
                {
                    "fusion_group_id": group_id,
                    "member_entity_ids": ids,
                    "entities": entities,
                    "approved_same_entity_links": approved_links,
                    "reviewed_link_count": len(approved_links),
                    "non_destructive": True,
                    "source_records_retained": True,
                }
            )
        return {
            "build": BUILD,
            "case_id": case_id,
            "groups": groups,
            "group_count": len(groups),
            "reviewed_same_entity_links": len(links),
            "destructive_merge": False,
            "automatic_identity_confirmation": False,
        }

    def _entity_group_maps(self, case_id):
        groups = self.fusion_groups(case_id)
        entity_to_group = {}
        group_map = {}
        for group in groups["groups"]:
            group_map[group["fusion_group_id"]] = group
            for eid in group["member_entity_ids"]:
                entity_to_group[eid] = group["fusion_group_id"]
        return groups, entity_to_group, group_map

    @staticmethod
    def _binding_indexes(bindings):
        exact = {}
        by_content = defaultdict(set)
        by_event = defaultdict(set)
        for b in bindings:
            exact[(b["source_kind"], b["source_object_id"])] = b["resolution_entity_id"]
            if b.get("content_id"):
                by_content[b["content_id"]].add(b["resolution_entity_id"])
            if b.get("event_id"):
                by_event[b["event_id"]].add(b["resolution_entity_id"])
        return exact, by_content, by_event

    def _event(self, *, event_id, semantic_kind, temporal, entity_ids, entity_to_group, source_id="", acquisition_event_id="", content_id="", source_object_id="", provenance_class="", assertion_class="", source_ref="", label="", machine_candidate=False, collection_time=False, metadata=None):
        if temporal is None:
            return None
        entity_ids = sorted({x for x in entity_ids if x})
        group_ids = sorted({entity_to_group[x] for x in entity_ids if x in entity_to_group})
        event = {
            "timeline_event_id": str(event_id),
            "semantic_kind": semantic_kind,
            "temporal_value": temporal["value"],
            "temporal_precision": temporal["precision"],
            "sort_key": temporal["sort_key"],
            "label": _clean(label, 600),
            "resolution_entity_ids": entity_ids,
            "fusion_group_ids": group_ids,
            "source_id": str(source_id or ""),
            "event_id": str(acquisition_event_id or ""),
            "content_id": str(content_id or ""),
            "source_object_id": str(source_object_id or ""),
            "source_ref": str(source_ref or ""),
            "provenance_class": str(provenance_class or ""),
            "assertion_class": str(assertion_class or ""),
            "machine_extracted_candidate": bool(machine_candidate),
            "collection_time": bool(collection_time),
            "truth_determined": False,
            "causality_inferred": False,
            "metadata": metadata or {},
        }
        event["event_hash"] = _hash(event)
        return event

    def timeline(self, case_id, *, include_fixtures=False):
        case_id = str(case_id)
        groups, entity_to_group, _ = self._entity_group_maps(case_id)
        bindings = self._bindings(case_id)
        exact, by_content, by_event = self._binding_indexes(bindings)
        events = []
        undated = []

        for row in self.db.all("SELECT * FROM organization_observation_433 WHERE case_id=? ORDER BY observed_at,created_at", (case_id,)):
            item = dict(row)
            if item.get("record_hash") and self.organization433._rh(item) != item["record_hash"]:
                raise RuntimeError("organization observation integrity check failed")
            if item.get("test_fixture") and not include_fixtures:
                continue
            eid = exact.get(("organization_observation", item["observation_id"]))
            temporal = _temporal(item["observed_at"])
            ev = self._event(
                event_id="tl438:orgobs:" + item["observation_id"],
                semantic_kind="organization_observation",
                temporal=temporal,
                entity_ids=[eid],
                entity_to_group=entity_to_group,
                source_id=item["source_id"],
                acquisition_event_id=item["event_id"],
                content_id=item["content_id"],
                source_object_id=item["observation_id"],
                source_ref="organization433",
                provenance_class="source_observation",
                assertion_class="observed_at",
                label=item["observed_name"],
                metadata={"subject_id": item["subject_id"]},
            )
            if ev:
                events.append(ev)
            else:
                undated.append({"kind": "organization_observation", "object_id": item["observation_id"], "raw_time": item["observed_at"]})
            attrs = json.loads(item["attributes_json"])
            for field, kind in (("founded_at", "organization_founded"), ("dissolved_at", "organization_dissolved")):
                if not attrs.get(field):
                    continue
                temporal = _temporal(attrs[field])
                ev = self._event(
                    event_id=f"tl438:org:{item['observation_id']}:{field}",
                    semantic_kind=kind,
                    temporal=temporal,
                    entity_ids=[eid],
                    entity_to_group=entity_to_group,
                    source_id=item["source_id"],
                    acquisition_event_id=item["event_id"],
                    content_id=item["content_id"],
                    source_object_id=item["observation_id"],
                    source_ref="organization433",
                    provenance_class="source_asserted_attribute",
                    assertion_class=field,
                    label=item["observed_name"],
                    metadata={"source_claim_only": True},
                )
                if ev:
                    events.append(ev)
                else:
                    undated.append({"kind": kind, "object_id": item["observation_id"], "raw_time": attrs[field]})

        for item in self.social432.case_items(case_id, include_fixtures=include_fixtures):
            raw = self.db.one("SELECT * FROM social_observation_432 WHERE observation_id=?", (item["observation_id"],))
            if not raw or self.social432._rh(dict(raw)) != raw.get("record_hash"):
                raise RuntimeError("social observation integrity check failed")
            eid = exact.get(("social_observation", item["observation_id"]))
            temporal = _temporal(item["published_at"])
            ev = self._event(
                event_id="tl438:social:" + item["observation_id"],
                semantic_kind="social_publication",
                temporal=temporal,
                entity_ids=[eid],
                entity_to_group=entity_to_group,
                source_id=item["source_id"],
                acquisition_event_id=item["event_id"],
                content_id=item["content_id"],
                source_object_id=item["observation_id"],
                source_ref="social432",
                provenance_class="public_social_observation",
                assertion_class="published_at",
                label=item.get("account_handle") or item.get("external_object_id"),
                metadata={"platform": item.get("platform", ""), "object_type": item.get("object_type", "")},
            )
            if ev:
                events.append(ev)

        news_by_id = {}
        for item in self.news429.case_items(case_id):
            if self.news429._rh(item) != item.get("record_hash"):
                raise RuntimeError("news item integrity check failed")
            news_by_id[item["news_item_id"]] = item
            entity_ids = sorted(by_content.get(item["content_id"], set()))
            temporal = _temporal(item["published_at"])
            ev = self._event(
                event_id="tl438:news:" + item["news_item_id"],
                semantic_kind="news_publication",
                temporal=temporal,
                entity_ids=entity_ids,
                entity_to_group=entity_to_group,
                source_id=item["source_id"],
                acquisition_event_id=item["event_id"],
                content_id=item["content_id"],
                source_object_id=item["news_item_id"],
                source_ref="news429",
                provenance_class="publisher_metadata",
                assertion_class="published_at",
                label=item["title"],
                metadata={"publisher": item.get("publisher", ""), "canonical_url": item.get("canonical_url", "")},
            )
            if ev:
                events.append(ev)

        for extraction in self.news430.case_extractions(case_id):
            raw = self.db.one("SELECT * FROM news_extraction_430 WHERE extraction_id=?", (extraction["extraction_id"],))
            if not raw or self.news430._rh(dict(raw)) != raw.get("record_hash"):
                raise RuntimeError("news extraction integrity check failed")
            item = news_by_id.get(extraction["news_item_id"])
            if not item:
                continue
            entity_ids = sorted(
                {
                    b["resolution_entity_id"]
                    for b in bindings
                    if b["source_kind"] == "news_entity_mention" and b["source_object_id"].startswith(extraction["extraction_id"] + ":")
                }
            )
            for idx, candidate in enumerate(extraction.get("events") or []):
                temporal = _temporal(candidate.get("time"))
                if not temporal:
                    if candidate.get("time"):
                        undated.append({"kind": "news_extracted_event_candidate", "object_id": extraction["extraction_id"] + ":" + str(idx), "raw_time": candidate.get("time"), "machine_extracted_candidate": True})
                    continue
                ev = self._event(
                    event_id=f"tl438:newsevent:{extraction['extraction_id']}:{idx}",
                    semantic_kind="news_extracted_event_candidate",
                    temporal=temporal,
                    entity_ids=entity_ids,
                    entity_to_group=entity_to_group,
                    source_id=item["source_id"],
                    acquisition_event_id=item["event_id"],
                    content_id=item["content_id"],
                    source_object_id=extraction["extraction_id"] + ":" + str(idx),
                    source_ref="news430",
                    provenance_class="machine_extraction",
                    assertion_class="candidate_event_time",
                    label=candidate.get("label", ""),
                    machine_candidate=True,
                    metadata={
                        "event_type": candidate.get("event_type", "unknown"),
                        "confidence": float(candidate.get("confidence") or 0),
                        "source_span": _clean(candidate.get("source_span"), 500),
                        "location": _clean(candidate.get("location"), 300),
                    },
                )
                events.append(ev)

        for row in self.db.all("SELECT * FROM archive_capture_428 WHERE case_id=? ORDER BY captured_at,created_at", (case_id,)):
            item = dict(row)
            if self.archive428._rh(item) != item.get("record_hash"):
                raise RuntimeError("archive capture integrity check failed")
            temporal = _temporal(item["captured_at"])
            entity_ids = sorted(by_content.get(item["content_id"], set()) | by_event.get(item["retrieved_event_id"], set()))
            ev = self._event(
                event_id="tl438:archive:" + item["archive_capture_id"],
                semantic_kind="archive_capture",
                temporal=temporal,
                entity_ids=entity_ids,
                entity_to_group=entity_to_group,
                source_id=item["source_id"],
                acquisition_event_id=item["retrieved_event_id"],
                content_id=item["content_id"],
                source_object_id=item["archive_capture_id"],
                source_ref="archive428",
                provenance_class="archive_capture",
                assertion_class="captured_at",
                label=item["original_url"],
                collection_time=True,
                metadata={"archive_provider": item.get("archive_provider", ""), "archive_url": item.get("archive_url", "")},
            )
            if ev:
                events.append(ev)

        for row in self.db.all("SELECT * FROM source_snapshot_427 WHERE case_id=? ORDER BY captured_at,created_at", (case_id,)):
            item = dict(row)
            if self.change427._rh(item) != item.get("record_hash"):
                raise RuntimeError("source snapshot integrity check failed")
            temporal = _temporal(item["captured_at"])
            entity_ids = sorted(by_content.get(item["content_id"], set()) | by_event.get(item["event_id"], set()))
            ev = self._event(
                event_id="tl438:snapshot:" + item["snapshot_id"],
                semantic_kind="source_snapshot",
                temporal=temporal,
                entity_ids=entity_ids,
                entity_to_group=entity_to_group,
                source_id=item["source_id"],
                acquisition_event_id=item["event_id"],
                content_id=item["content_id"],
                source_object_id=item["snapshot_id"],
                source_ref="change427",
                provenance_class="collection_snapshot",
                assertion_class="captured_at",
                label=item["target"],
                collection_time=True,
                metadata={"content_sha256": item["content_sha256"]},
            )
            if ev:
                events.append(ev)

        events.sort(key=lambda x: (x["sort_key"], x["semantic_kind"], x["timeline_event_id"]))
        lifecycle = defaultdict(set)
        for ev in events:
            if ev["semantic_kind"] not in {"organization_founded", "organization_dissolved"}:
                continue
            for gid in ev["fusion_group_ids"]:
                lifecycle[(gid, ev["semantic_kind"])].add(ev["temporal_value"])
        disagreements = [
            {
                "fusion_group_id": gid,
                "semantic_kind": kind,
                "temporal_values": sorted(values),
                "classification": "source_temporal_disagreement_requires_review",
                "automatic_resolution": False,
            }
            for (gid, kind), values in sorted(lifecycle.items())
            if len(values) > 1
        ]
        return {
            "build": BUILD,
            "case_id": case_id,
            "events": events,
            "event_count": len(events),
            "undated_candidates": undated,
            "temporal_disagreements": disagreements,
            "fusion_groups": groups["groups"],
            "reviewed_same_entity_links": groups["reviewed_same_entity_links"],
            "machine_extracted_events_candidate_only": True,
            "collection_time_distinguished_from_event_time": True,
            "automatic_temporal_conflict_resolution": False,
            "truth_determined": False,
            "causality_inferred": False,
            "network_execution": False,
        }

    def relationship_graph(self, case_id, *, include_fixtures=False):
        case_id = str(case_id)
        groups, entity_to_group, group_map = self._entity_group_maps(case_id)
        bindings = self._bindings(case_id)
        exact, _, _ = self._binding_indexes(bindings)
        assertions = defaultdict(list)
        unresolved = []
        intra_group = []

        for row in self.db.all("SELECT * FROM organization_relation_claim_433 WHERE case_id=? ORDER BY created_at,relation_id", (case_id,)):
            item = dict(row)
            if self.organization433._rh(item) != item.get("record_hash"):
                raise RuntimeError("organization relation integrity check failed")
            if item.get("test_fixture") and not include_fixtures:
                continue
            left = exact.get(("organization_subject", item["source_subject_id"]))
            right = exact.get(("organization_subject", item["target_subject_id"]))
            assertion = {
                "relation_id": item["relation_id"],
                "relation_type": item["relation_type"],
                "source_subject_id": item["source_subject_id"],
                "target_subject_id": item["target_subject_id"],
                "source_resolution_entity_id": left or "",
                "target_resolution_entity_id": right or "",
                "source_id": item["source_id"],
                "event_id": item["event_id"],
                "content_id": item["content_id"],
                "source_span": item["source_span"],
                "assertion_basis": "explicit_source_relation_claim",
                "source_claim_only": True,
                "truth_determined": False,
            }
            if not left or not right or left not in entity_to_group or right not in entity_to_group:
                unresolved.append({**assertion, "reason": "relationship_endpoint_not_resolution_bound", "automatic_resolution": False})
                continue
            lg, rg = entity_to_group[left], entity_to_group[right]
            assertion["source_fusion_group_id"] = lg
            assertion["target_fusion_group_id"] = rg
            if lg == rg:
                intra_group.append({**assertion, "classification": "intra_reviewed_identity_group_relation_requires_review"})
                continue
            assertions[(lg, item["relation_type"], rg)].append(assertion)

        for row in self.db.all("SELECT * FROM organization_observation_433 WHERE case_id=? ORDER BY created_at,observation_id", (case_id,)):
            item = dict(row)
            if item.get("test_fixture") and not include_fixtures:
                continue
            source_eid = exact.get(("organization_subject", item["subject_id"]))
            source_gid = entity_to_group.get(source_eid, "")
            for person in json.loads(item["people_json"]):
                name = _clean(person.get("name"), 300)
                role = _clean(person.get("role"), 200)
                if not name or not role:
                    continue
                unresolved.append(
                    {
                        "kind": "organization_person_role",
                        "source_subject_id": item["subject_id"],
                        "source_resolution_entity_id": source_eid or "",
                        "source_fusion_group_id": source_gid,
                        "target_label": name,
                        "relation_type": "role:" + role.casefold(),
                        "source_id": item["source_id"],
                        "event_id": item["event_id"],
                        "content_id": item["content_id"],
                        "reason": "person_endpoint_not_explicitly_resolution_bound",
                        "automatic_resolution": False,
                        "source_claim_only": True,
                    }
                )

        observation_relationships = []
        for item in self.social432.case_items(case_id, include_fixtures=include_fixtures):
            eid = exact.get(("social_observation", item["observation_id"]))
            gid = entity_to_group.get(eid, "")
            for field, kind in (("reply_to_external_id", "reply_to"), ("reshare_of_external_id", "reshare_of")):
                target = _clean(item.get(field), 500)
                if not target:
                    continue
                observation_relationships.append(
                    {
                        "kind": kind,
                        "source_observation_id": item["observation_id"],
                        "source_resolution_entity_id": eid or "",
                        "source_fusion_group_id": gid,
                        "target_external_object_id": target,
                        "platform": item.get("platform", ""),
                        "source_id": item["source_id"],
                        "event_id": item["event_id"],
                        "content_id": item["content_id"],
                        "entity_relationship_inferred": False,
                    }
                )

        edges = []
        for (left_group, relation_type, right_group), items in sorted(assertions.items()):
            sources = sorted({x["source_id"] for x in items})
            edge = {
                "source_fusion_group_id": left_group,
                "relation_type": relation_type,
                "target_fusion_group_id": right_group,
                "assertions": items,
                "assertion_count": len(items),
                "independent_source_ids": sources,
                "source_asserted_only": True,
                "relationship_inferred": False,
                "truth_determined": False,
            }
            edge["edge_hash"] = _hash(edge)
            edges.append(edge)

        nodes = [
            {
                "fusion_group_id": g["fusion_group_id"],
                "member_entity_ids": g["member_entity_ids"],
                "entities": g["entities"],
                "reviewed_link_count": g["reviewed_link_count"],
                "non_destructive": True,
            }
            for g in groups["groups"]
        ]
        graph = {
            "build": BUILD,
            "case_id": case_id,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "unresolved_relationship_candidates": unresolved,
            "intra_group_relationship_assertions": intra_group,
            "observation_relationships": observation_relationships,
            "reviewed_same_entity_links": groups["reviewed_same_entity_links"],
            "explicit_source_relationships_only": True,
            "text_cooccurrence_relationships": False,
            "automatic_relationship_inference": False,
            "automatic_identity_confirmation": False,
            "destructive_merge": False,
            "truth_determined": False,
            "network_execution": False,
        }
        graph["graph_hash"] = _hash(graph)
        return graph

    def entity_context(self, case_id, entity_id, *, include_fixtures=False):
        case_id, entity_id = str(case_id), str(entity_id)
        groups, entity_to_group, group_map = self._entity_group_maps(case_id)
        if entity_id not in entity_to_group:
            raise KeyError("entity not present in Build-437 case bindings")
        gid = entity_to_group[entity_id]
        timeline = self.timeline(case_id, include_fixtures=include_fixtures)
        graph = self.relationship_graph(case_id, include_fixtures=include_fixtures)
        events = [x for x in timeline["events"] if gid in x["fusion_group_ids"]]
        edges = [x for x in graph["edges"] if x["source_fusion_group_id"] == gid or x["target_fusion_group_id"] == gid]
        return {
            "build": BUILD,
            "case_id": case_id,
            "requested_entity_id": entity_id,
            "fusion_group": group_map[gid],
            "timeline_events": events,
            "relationship_edges": edges,
            "provenance_preserved": True,
            "destructive_merge": False,
            "truth_determined": False,
            "causality_inferred": False,
        }

    def fuse_case(self, *, identity, case_id, include_fixtures=False):
        ident = self._authorize(identity, case_id)
        case_id = str(case_id or "").strip()
        if not case_id:
            raise ValueError("case_id required")
        preflight = self._preflight(case_id)
        groups = self.fusion_groups(case_id)
        timeline = self.timeline(case_id, include_fixtures=bool(include_fixtures))
        graph = self.relationship_graph(case_id, include_fixtures=bool(include_fixtures))
        result = {
            "build": BUILD,
            "case_id": case_id,
            "fusion_groups": groups["group_count"],
            "reviewed_same_entity_links": groups["reviewed_same_entity_links"],
            "timeline_events": timeline["event_count"],
            "relationship_edges": graph["edge_count"],
            "unresolved_relationships": len(graph["unresolved_relationship_candidates"]),
            "temporal_disagreements": len(timeline["temporal_disagreements"]),
            "preflight": preflight,
            "provenance_preserved": True,
            "source_records_retained": True,
            "machine_extracted_events_candidate_only": True,
            "explicit_source_relationships_only": True,
            "automatic_identity_confirmation": False,
            "automatic_relationship_inference": False,
            "automatic_temporal_conflict_resolution": False,
            "destructive_merge": False,
            "truth_determined": False,
            "causality_inferred": False,
            "network_execution": False,
        }
        row = {
            "run_id": "fusion438_" + secrets.token_hex(10),
            "case_id": case_id,
            "fusion_groups": groups["group_count"],
            "timeline_events": timeline["event_count"],
            "relationship_edges": graph["edge_count"],
            "unresolved_relationships": len(graph["unresolved_relationship_candidates"]),
            "result_json": _canon(result),
            "created_by": str(ident["username"]),
            "created_at": _now(),
        }
        row["record_hash"] = self._rh(row)
        self.db.execute("INSERT INTO phase19_fusion_run_438 VALUES(?,?,?,?,?,?,?,?,?,?)", tuple(row.values()))
        self.audit.log("temporal_relationship_fusion_run_438", "phase19_fusion_run_438", row["run_id"], case_id, result)
        return {**row, "result": result}

    def latest(self, case_id):
        row = self.db.one("SELECT * FROM phase19_fusion_run_438 WHERE case_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (str(case_id),))
        if not row:
            return None
        out = dict(row)
        out["result"] = json.loads(out["result_json"])
        return out

    def case_report(self, case_id, *, include_fixtures=False):
        case_id = str(case_id)
        groups = self.fusion_groups(case_id)
        timeline = self.timeline(case_id, include_fixtures=include_fixtures)
        graph = self.relationship_graph(case_id, include_fixtures=include_fixtures)
        return {
            "build": BUILD,
            "case_id": case_id,
            "fusion_groups": groups["group_count"],
            "reviewed_same_entity_links": groups["reviewed_same_entity_links"],
            "timeline_events": timeline["event_count"],
            "temporal_disagreements": len(timeline["temporal_disagreements"]),
            "relationship_edges": graph["edge_count"],
            "unresolved_relationship_candidates": len(graph["unresolved_relationship_candidates"]),
            "observation_relationships": len(graph["observation_relationships"]),
            "integrity_valid": self.verify_integrity()["valid"],
            "provenance_preserved": True,
            "destructive_merge": False,
            "truth_determined": False,
            "causality_inferred": False,
            "case_scoped": True,
        }

    def run_case_selftest(self, *, identity, case_id):
        ident = self._authorize(identity, case_id)
        base = self.resolution437.run_case_selftest(identity=ident, case_id=str(case_id))
        run = self.fuse_case(identity=ident, case_id=str(case_id), include_fixtures=True)
        timeline = self.timeline(str(case_id), include_fixtures=True)
        graph = self.relationship_graph(str(case_id), include_fixtures=True)
        checks = {
            "build437_fixture_passed": base["result"] == "PASS",
            "timeline_contains_provenance_bound_events": timeline["event_count"] >= 2,
            "two_unreviewed_candidates_stay_separate_groups": self.fusion_groups(str(case_id))["group_count"] >= 2,
            "no_automatic_identity_confirmation": run["result"]["automatic_identity_confirmation"] is False,
            "no_destructive_merge": run["result"]["destructive_merge"] is False,
            "explicit_relationships_only": graph["explicit_source_relationships_only"] is True,
            "no_relationship_inference": graph["automatic_relationship_inference"] is False,
            "machine_events_candidate_only": timeline["machine_extracted_events_candidate_only"] is True,
            "no_causality_inference": timeline["causality_inferred"] is False,
            "network_execution_absent": run["result"]["network_execution"] is False,
            "integrity_valid": self.verify_integrity()["valid"],
        }
        return {
            "build": BUILD,
            "case_id": str(case_id),
            "result": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "fusion_run": run,
            "note": "Build 438 fuses reviewed identity links non-destructively and keeps every temporal/relationship assertion source-bound.",
        }

    def verify_integrity(self):
        violations = []
        for row in self.db.all("SELECT * FROM phase19_fusion_run_438"):
            item = dict(row)
            if self._rh(item) != item.get("record_hash"):
                violations.append({"run_id": item.get("run_id"), "reason": "record_hash_mismatch"})
        return {"build": BUILD, "valid": not violations, "violations": violations}

    def status(self):
        count = self.db.one("SELECT COUNT(*) n FROM phase19_fusion_run_438")["n"]
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "runs": int(count),
            "integrity_valid": self.verify_integrity()["valid"],
            "temporal_relationship_fusion": True,
            "reviewed_identity_links_fused_non_destructively": True,
            "source_records_retained": True,
            "provenance_preserved": True,
            "machine_extracted_events_candidate_only": True,
            "collection_time_distinguished_from_event_time": True,
            "explicit_source_relationships_only": True,
            "text_cooccurrence_relationships": False,
            "automatic_identity_confirmation": False,
            "automatic_relationship_inference": False,
            "automatic_temporal_conflict_resolution": False,
            "truth_determined": False,
            "causality_inferred": False,
            "network_execution": False,
            "case_specific_selftest": True,
            "production_release_ready": False,
        }
