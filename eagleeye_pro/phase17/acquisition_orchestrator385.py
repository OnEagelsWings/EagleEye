from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any, Mapping, Sequence

BUILD = "385.0"
POLICY_ID = "phase17.acquisition-orchestrator.v385"
CONFIRM_PREPARE = "PREPARE ACQUISITION"


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
class SourceCapability385:
    source_id: str
    bridge_kind: str
    connector_key: str
    identifier_kind: str
    prepare_supported: bool
    phase16_live_eligible: bool
    plan_only: bool
    required_phase17_scope_state: str = "approved"
    required_prepare_confirmation: str = CONFIRM_PREPARE
    execution_confirmation: str = "LIVE"
    automatic_execution: bool = False
    arbitrary_url_execution: bool = False
    credential_injection: bool = False
    notes: str = ""

    @property
    def capability_hash(self) -> str:
        return _sha(asdict(self))


@dataclass(frozen=True, slots=True)
class AcquisitionPacketItem385:
    source_id: str
    source_name: str
    source_class: str
    jurisdiction: str
    wave_number: int
    bridge_kind: str
    connector_key: str
    identifier_kind: str
    identifier_present: bool
    phase17_scope_state: str
    registry_execution_mode: str
    external_validation_state: str
    prepare_supported: bool
    phase16_live_eligible: bool
    plan_only: bool
    ready_for_preparation: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AcquisitionPacket385:
    packet_id: str
    case_id: str
    wave_plan_id: str
    mission: str
    items: tuple[AcquisitionPacketItem385, ...]
    coverage_summary: Mapping[str, Any]
    identifier_hashes: Mapping[str, str]
    requires_go: bool = True
    requires_source_review: bool = True
    requires_prepare_confirmation: bool = True
    execution_authority: bool = False
    network_requests_created: int = 0
    automatic_scope_expansion: bool = False
    policy_id: str = POLICY_ID

    @property
    def packet_hash(self) -> str:
        return _sha({
            "case_id": self.case_id,
            "wave_plan_id": self.wave_plan_id,
            "mission": self.mission,
            "items": [asdict(i) for i in self.items],
            "coverage_summary": dict(self.coverage_summary),
            "identifier_hashes": dict(sorted(self.identifier_hashes.items())),
            "requires_go": self.requires_go,
            "requires_source_review": self.requires_source_review,
            "requires_prepare_confirmation": self.requires_prepare_confirmation,
            "execution_authority": self.execution_authority,
            "network_requests_created": self.network_requests_created,
            "automatic_scope_expansion": self.automatic_scope_expansion,
            "policy_id": self.policy_id,
        })


DEFAULT_CAPABILITIES_385: tuple[SourceCapability385, ...] = (
    SourceCapability385(
        "gleif.lei", "corporate_connector", "gleif_lei_api_v1", "lei",
        True, True, False,
        notes="Exact LEI preparation through the existing Build-366 governed corporate connector.",
    ),
    SourceCapability385(
        "sec.edgar", "corporate_connector", "sec_edgar_submissions_v1", "cik",
        True, True, False,
        notes="Exact CIK preparation through the existing Build-366 governed corporate connector.",
    ),
    SourceCapability385(
        "usaspending.awards", "public_money_connector", "usaspending_award_v1", "generated_award_id",
        True, True, False,
        notes="Exact USAspending award preparation through Build 367.",
    ),
    SourceCapability385(
        "eu.ted", "public_money_connector", "ted_search_v3", "bounded_expert_query",
        True, False, True,
        notes="TED Search remains plan-only because the qualified crawler does not execute POST search in the current phase.",
    ),
    SourceCapability385(
        "us.federal_register", "reference_connector", "federal_register_document_v1", "document_number",
        True, True, False,
        notes="Exact Federal Register document preparation through Build 368.",
    ),
    SourceCapability385(
        "internet_archive.metadata", "reference_connector", "internet_archive_metadata_v1", "item_identifier",
        True, True, False,
        notes="Internet Archive metadata only; archive payload/content download remains outside this capability.",
    ),
)


class AcquisitionOrchestrator385:
    """Bridge Build-384 research waves to existing governed Phase-16 source preparation.

    Build 385 deliberately stops before external execution. It can compile a wave plan into
    concrete connector preparation requirements and, after explicit confirmation and case RBAC,
    create canonical *pending-review* Phase-15 source records through the existing Build-366/367/368
    preparation APIs. It never approves those sources, never queues a crawl, never performs an HTTP
    request, never accepts arbitrary URLs, and never injects credentials.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        build366: Any,
        build367: Any,
        build368: Any,
        workflow374: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.build366 = build366
        self.build367 = build367
        self.build368 = build368
        self.workflow374 = workflow374
        self.actor = actor
        self._init_schema()
        self._seed_capabilities()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS source_capability_385 (
                source_id TEXT PRIMARY KEY,
                capability_json TEXT NOT NULL,
                capability_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS acquisition_packet_385 (
                packet_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                wave_plan_id TEXT NOT NULL,
                packet_hash TEXT NOT NULL UNIQUE,
                packet_json TEXT NOT NULL,
                identifiers_json TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(wave_plan_id) REFERENCES research_wave_plan_384(wave_plan_id)
            );
            CREATE TABLE IF NOT EXISTS acquisition_preparation_385 (
                preparation_id TEXT PRIMARY KEY,
                packet_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                connector_key TEXT NOT NULL,
                identifier_hash TEXT NOT NULL,
                canonical_source_id TEXT,
                outcome_state TEXT NOT NULL,
                result_json TEXT NOT NULL,
                actor TEXT NOT NULL,
                created_at TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                UNIQUE(packet_id, source_id),
                FOREIGN KEY(packet_id) REFERENCES acquisition_packet_385(packet_id)
            );
            CREATE INDEX IF NOT EXISTS idx_acquisition_packet_385_case
                ON acquisition_packet_385(case_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_acquisition_preparation_385_case
                ON acquisition_preparation_385(case_id, created_at);
            """
        )
        self.db.conn.commit()

    def _seed_capabilities(self) -> None:
        now = _now()
        with self.db.conn:
            for capability in DEFAULT_CAPABILITIES_385:
                body = _canon(asdict(capability))
                self.db.conn.execute(
                    "INSERT INTO source_capability_385(source_id,capability_json,capability_hash,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(source_id) DO UPDATE SET capability_json=excluded.capability_json,capability_hash=excluded.capability_hash,updated_at=excluded.updated_at",
                    (capability.source_id, body, capability.capability_hash, now),
                )

    def capabilities(self) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT source_id,capability_json,capability_hash,updated_at FROM source_capability_385 ORDER BY source_id")
        return [dict(_j(r["capability_json"], {})) | {"capability_hash": r["capability_hash"], "updated_at": r["updated_at"]} for r in rows]

    def _capability(self, source_id: str) -> dict[str, Any] | None:
        row = self.db.one("SELECT capability_json FROM source_capability_385 WHERE source_id=?", (source_id,))
        return dict(_j(row["capability_json"], {})) if row else None

    def _validate_identifier(self, capability: Mapping[str, Any], identifier: str) -> tuple[bool, str]:
        bridge = str(capability.get("bridge_kind") or "")
        connector = str(capability.get("connector_key") or "")
        try:
            if bridge == "corporate_connector":
                self.build366.corporate_source_plan(connector, identifier)
            elif bridge == "public_money_connector":
                self.build367.public_money_source_plan(connector, identifier)
            elif bridge == "reference_connector":
                self.build368.reference_source_plan(connector, identifier)
            else:
                return False, "no_governed_acquisition_bridge"
            return True, ""
        except (ValueError, KeyError, PermissionError) as exc:
            return False, str(exc)[:240]

    def _wave_plan(self, case_id: str, wave_plan_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        plan = self.db.one("SELECT * FROM research_wave_plan_384 WHERE wave_plan_id=? AND case_id=?", (wave_plan_id, case_id))
        if not plan:
            raise KeyError(wave_plan_id)
        waves = self.db.all("SELECT wave_number,wave_json FROM research_wave_384 WHERE wave_plan_id=? ORDER BY wave_number", (wave_plan_id,))
        return plan, [dict(_j(w["wave_json"], {})) for w in waves]

    def _scope_state(self, case_id: str, source_id: str) -> str:
        row = self.db.one("SELECT state FROM case_source_scope WHERE case_id=? AND source_id=?", (case_id, source_id))
        return str(row.get("state") or "unselected") if row else "unselected"

    def _registry_entry(self, source_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT entry_json FROM source_registry_sources WHERE source_id=?", (source_id,))
        if not row:
            raise KeyError(source_id)
        return dict(_j(row["entry_json"], {}))

    def compile_packet(
        self,
        *,
        case_id: str,
        wave_plan_id: str,
        identifiers: Mapping[str, Any] | None = None,
        actor: str | None = None,
    ) -> AcquisitionPacket385:
        identifiers = {str(k): str(v).strip() for k, v in dict(identifiers or {}).items() if str(v).strip()}
        plan, waves = self._wave_plan(case_id, wave_plan_id)
        items: list[AcquisitionPacketItem385] = []
        seen: set[str] = set()
        class_counts: dict[str, int] = {}
        blockers_count: dict[str, int] = {}
        for wave in waves:
            number = int(wave.get("wave_number") or 0)
            for step in wave.get("steps") or []:
                sid = str(step.get("source_id") or "")
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                registry = self._registry_entry(sid)
                capability = self._capability(sid)
                scope_state = self._scope_state(case_id, sid)
                blockers: list[str] = []
                identifier_present = bool(identifiers.get(sid))
                if str(plan.get("confirmation_state") or "") != "confirmed":
                    blockers.append("wave_plan_not_confirmed")
                if scope_state != "approved":
                    blockers.append("phase17_source_scope_not_approved")
                if capability is None:
                    blockers.append("no_governed_acquisition_bridge")
                else:
                    if bool(capability.get("prepare_supported")) is not True:
                        blockers.append("preparation_not_supported")
                    if not identifier_present:
                        blockers.append("identifier_required")
                    else:
                        identifier_valid, _identifier_error = self._validate_identifier(capability, identifiers[sid])
                        if not identifier_valid:
                            blockers.append("identifier_invalid")
                    if bool(capability.get("arbitrary_url_execution")):
                        blockers.append("invalid_arbitrary_url_capability")
                    if bool(capability.get("credential_injection")):
                        blockers.append("invalid_credential_capability")
                for blocker in blockers:
                    blockers_count[blocker] = blockers_count.get(blocker, 0) + 1
                source_class = str(step.get("source_class") or "unknown")
                class_counts[source_class] = class_counts.get(source_class, 0) + 1
                items.append(AcquisitionPacketItem385(
                    source_id=sid,
                    source_name=str(registry.get("name") or sid),
                    source_class=source_class,
                    jurisdiction=str(step.get("jurisdiction") or "global"),
                    wave_number=number,
                    bridge_kind=str((capability or {}).get("bridge_kind") or "none"),
                    connector_key=str((capability or {}).get("connector_key") or ""),
                    identifier_kind=str((capability or {}).get("identifier_kind") or "unknown"),
                    identifier_present=identifier_present,
                    phase17_scope_state=scope_state,
                    registry_execution_mode=str(registry.get("execution_mode") or "plan_only"),
                    external_validation_state=str(registry.get("external_validation_state") or "not_run"),
                    prepare_supported=bool((capability or {}).get("prepare_supported")),
                    phase16_live_eligible=bool((capability or {}).get("phase16_live_eligible")),
                    plan_only=bool((capability or {}).get("plan_only")),
                    ready_for_preparation=not blockers,
                    blockers=tuple(sorted(set(blockers))),
                ))
        coverage = {
            "planned_sources": len(items),
            "ready_for_preparation": sum(1 for i in items if i.ready_for_preparation),
            "blocked_sources": sum(1 for i in items if not i.ready_for_preparation),
            "source_classes": dict(sorted(class_counts.items())),
            "blockers": dict(sorted(blockers_count.items())),
            "wave_confirmation_state": str(plan.get("confirmation_state") or "preview"),
        }
        packet_seed = {
            "case_id": case_id,
            "wave_plan_id": wave_plan_id,
            "mission": str(plan.get("mission") or ""),
            "items": [asdict(i) for i in items],
            "coverage": coverage,
            "identifiers_hashes": {k: _sha(v) for k, v in sorted(identifiers.items())},
            "policy": POLICY_ID,
        }
        identifier_hashes = {k: _sha(v) for k, v in sorted(identifiers.items())}
        packet_id = "acq385_" + _sha(packet_seed)[:24]
        packet = AcquisitionPacket385(packet_id, case_id, wave_plan_id, str(plan.get("mission") or ""), tuple(items), coverage, identifier_hashes)
        body = asdict(packet) | {"packet_hash": packet.packet_hash}
        who = str(actor or self.actor)[:120]
        with self.db.conn:
            self.db.conn.execute(
                "INSERT OR IGNORE INTO acquisition_packet_385(packet_id,case_id,wave_plan_id,packet_hash,packet_json,identifiers_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (packet.packet_id, case_id, wave_plan_id, packet.packet_hash, _canon(body), _canon(identifiers), who, _now()),
            )
        self.audit.log(
            "PHASE17_385_ACQUISITION_PACKET",
            "acquisition_packet",
            packet.packet_id,
            case_id=case_id,
            details={
                "wave_plan_id": wave_plan_id,
                "ready_for_preparation": coverage["ready_for_preparation"],
                "blocked_sources": coverage["blocked_sources"],
                "execution_authority": False,
                "network_requests_created": 0,
                "policy": POLICY_ID,
            },
        )
        return packet

    def packet(self, *, case_id: str, packet_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM acquisition_packet_385 WHERE packet_id=? AND case_id=?", (packet_id, case_id))
        if not row:
            raise KeyError(packet_id)
        body = dict(_j(row["packet_json"], {}))
        body["preparations"] = self.preparations(case_id=case_id, packet_id=packet_id)
        return body

    def preparations(self, *, case_id: str, packet_id: str) -> list[dict[str, Any]]:
        rows = self.db.all(
            "SELECT preparation_id,source_id,connector_key,identifier_hash,canonical_source_id,outcome_state,result_json,actor,created_at,record_hash "
            "FROM acquisition_preparation_385 WHERE case_id=? AND packet_id=? ORDER BY created_at,source_id",
            (case_id, packet_id),
        )
        out: list[dict[str, Any]] = []
        for row in rows:
            result = dict(_j(row["result_json"], {}))
            out.append({k: row[k] for k in row if k != "result_json"} | {"result": result})
        return out

    def _prepare_one(self, *, case_id: str, item: Mapping[str, Any], identifier: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        bridge = str(item.get("bridge_kind") or "")
        connector = str(item.get("connector_key") or "")
        kwargs = {"case_id": case_id, "connector_key": connector, "identifier": identifier, "identity": dict(identity)}
        if bridge == "corporate_connector":
            return dict(self.build366.prepare_corporate_source(**kwargs))
        if bridge == "public_money_connector":
            return dict(self.build367.prepare_public_money_source(**kwargs))
        if bridge == "reference_connector":
            return dict(self.build368.prepare_reference_source(**kwargs))
        raise PermissionError("no governed preparation bridge")

    def prepare_packet(
        self,
        *,
        case_id: str,
        packet_id: str,
        identity: Mapping[str, Any],
        confirmation: str,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_PREPARE:
            raise PermissionError(f"explicit confirmation {CONFIRM_PREPARE} required")
        row = self.db.one("SELECT * FROM acquisition_packet_385 WHERE packet_id=? AND case_id=?", (packet_id, case_id))
        if not row:
            raise KeyError(packet_id)
        packet = dict(_j(row["packet_json"], {}))
        identifiers = dict(_j(row["identifiers_json"], {}))
        actor = str(identity.get("username") or self.actor)[:120]
        outcomes: list[dict[str, Any]] = []
        for item in packet.get("items") or []:
            if not bool(item.get("ready_for_preparation")):
                outcomes.append({"source_id": item.get("source_id"), "state": "blocked", "blockers": list(item.get("blockers") or [])})
                continue
            sid = str(item.get("source_id") or "")
            existing = self.db.one("SELECT * FROM acquisition_preparation_385 WHERE packet_id=? AND source_id=?", (packet_id, sid))
            if existing:
                outcomes.append({"source_id": sid, "state": "already_prepared", "canonical_source_id": existing.get("canonical_source_id")})
                continue
            identifier = str(identifiers.get(sid) or "").strip()
            if not identifier:
                outcomes.append({"source_id": sid, "state": "blocked", "blockers": ["identifier_required"]})
                continue
            result = self._prepare_one(case_id=case_id, item=item, identifier=identifier, identity=identity)
            source = result.get("source") if isinstance(result.get("source"), Mapping) else None
            canonical_source_id = str((source or {}).get("source_id") or "") or None
            state = str(result.get("state") or "prepared")
            prep_body = {
                "packet_id": packet_id,
                "case_id": case_id,
                "source_id": sid,
                "connector_key": str(item.get("connector_key") or ""),
                "identifier_hash": _sha(identifier),
                "canonical_source_id": canonical_source_id,
                "outcome_state": state,
                "actor": actor,
                "policy": POLICY_ID,
            }
            preparation_id = "prep385_" + _sha(prep_body)[:24]
            record_hash = _sha(prep_body | {"result": result})
            with self.db.conn:
                self.db.conn.execute(
                    "INSERT INTO acquisition_preparation_385(preparation_id,packet_id,case_id,source_id,connector_key,identifier_hash,canonical_source_id,outcome_state,result_json,actor,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (preparation_id, packet_id, case_id, sid, prep_body["connector_key"], prep_body["identifier_hash"], canonical_source_id, state, _canon(result), actor, _now(), record_hash),
                )
            self.audit.log(
                "PHASE17_385_SOURCE_PREPARED",
                "source",
                canonical_source_id or sid,
                case_id=case_id,
                details={
                    "packet_id": packet_id,
                    "phase17_source_id": sid,
                    "connector_key": prep_body["connector_key"],
                    "outcome_state": state,
                    "canonical_source_id": canonical_source_id or "",
                    "network_requests_created": 0,
                    "automatic_source_approval": False,
                    "automatic_crawl_enqueue": False,
                    "policy": POLICY_ID,
                },
            )
            outcomes.append({"source_id": sid, "state": state, "canonical_source_id": canonical_source_id, "preparation_id": preparation_id})
        return {
            "build": BUILD,
            "packet_id": packet_id,
            "case_id": case_id,
            "outcomes": outcomes,
            "network_requests_created": 0,
            "jobs_created": 0,
            "automatic_source_approval": False,
            "automatic_crawl_enqueue": False,
            "execution_authority": False,
            "required_next_gates": ["phase15_source_review", "case_workflow_budget", "explicit_live_or_crawl_confirmation", "opsec_preflight"],
            "policy": POLICY_ID,
        }

    def execution_readiness(self, *, case_id: str, packet_id: str, identity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        packet = self.packet(case_id=case_id, packet_id=packet_id)
        preparations = packet.get("preparations") or []
        rows: list[dict[str, Any]] = []
        for prep in preparations:
            sid = str(prep.get("canonical_source_id") or "")
            source = self.db.one(
                "SELECT s.source_id,s.review_status,s.display_name,s.source_class,p.enabled,p.source_health FROM phase15_sources s JOIN phase15_crawler_policies p ON p.source_id=s.source_id WHERE s.source_id=?",
                (sid,),
            ) if sid else None
            blockers: list[str] = []
            if not sid:
                blockers.append("plan_only_or_no_canonical_source")
            elif not source:
                blockers.append("canonical_source_missing")
            else:
                if str(source.get("review_status")) != "approved_read_only":
                    blockers.append("phase15_source_review_required")
                if int(source.get("enabled") or 0) != 1:
                    blockers.append("phase15_source_not_enabled")
            rows.append({
                "phase17_source_id": prep.get("source_id"),
                "canonical_source_id": sid or None,
                "connector_key": prep.get("connector_key"),
                "review_status": source.get("review_status") if source else None,
                "source_health": source.get("source_health") if source else None,
                "ready_for_execution_gate": not blockers,
                "blockers": blockers,
            })
        workflow: dict[str, Any]
        if identity is None:
            workflow = {"state": "not_checked", "reason": "identity_required_for_workflow_status"}
        else:
            try:
                workflow = dict(self.workflow374.status(case_id=case_id, identity=dict(identity)))
            except KeyError:
                workflow = {"state": "not_configured"}
            except PermissionError as exc:
                workflow = {"state": "not_authorized", "reason": str(exc)}
        return {
            "build": BUILD,
            "case_id": case_id,
            "packet_id": packet_id,
            "prepared_sources": rows,
            "workflow": workflow,
            "ready_sources": sum(1 for r in rows if r["ready_for_execution_gate"]),
            "execution_authority": False,
            "network_requests_created": 0,
            "automatic_enqueue": False,
            "policy": POLICY_ID,
        }

    def status(self) -> dict[str, Any]:
        counts = {
            "capabilities": int((self.db.one("SELECT COUNT(*) n FROM source_capability_385") or {}).get("n") or 0),
            "packets": int((self.db.one("SELECT COUNT(*) n FROM acquisition_packet_385") or {}).get("n") or 0),
            "preparations": int((self.db.one("SELECT COUNT(*) n FROM acquisition_preparation_385") or {}).get("n") or 0),
        }
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            **counts,
            "bridges": ["corporate_connector", "public_money_connector", "reference_connector"],
            "network_execution_added": False,
            "arbitrary_url_execution": False,
            "credential_injection": False,
            "automatic_source_approval": False,
            "automatic_crawl_enqueue": False,
            "automatic_scope_expansion": False,
            "host_security_mutation": False,
        }
