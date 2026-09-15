"""Build 382: persistent source registry, case source scope, research-plan ledger and coverage/gap tracking.

This module extends the network-silent Build-381 control plane. It intentionally does not
perform HTTP requests, crawl, authenticate to external systems, merge identities, or mutate
host/network security controls. It creates a durable planning/audit layer that can later be
bound to the canonical EagleEye database once the full Build-380 source tree is available.

Security / governance invariants:
- sources remain public, licensed, or explicitly authorized metadata only;
- source review is mandatory and source approval never grants execution authority;
- every research plan requires human GO and has execution_authority=False;
- coverage observations are evidence-linked where they represent an actual attempt/result;
- no-result observations never mean non-existence;
- source revisions are append-only; the current catalog is a projection of revisions;
- no automatic scope expansion and no autonomous OPSEC/system mutation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import sqlite3
from typing import Any, Iterable, Mapping, Sequence

from .investigation_control381 import (
    AccessBasis,
    BASE_BUILD_FINGERPRINT,
    BUILD as BUILD_381,
    GlobalSourceRegistry381,
    InvestigationControlPlane381,
    InvestigationPlan,
    SourceExecutionMode,
    SourceRegistryEntry,
    default_registry,
)

BUILD = "382.0"
POLICY_ID = "phase17.source-registry-persistence-coverage.v382"
BASE_OVERLAY_BUILD = BUILD_381
BASE_OVERLAY_FINGERPRINT = BASE_BUILD_FINGERPRINT

_CASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
_SOURCE_SCOPE_STATES = frozenset({"candidate", "approved", "excluded"})
_COVERAGE_STATES = frozenset({
    "planned",
    "reviewed",
    "attempted",
    "succeeded",
    "partial",
    "failed",
    "blocked",
    "stale",
    "no_result_observed",
    "not_applicable",
})
_EVIDENCE_REQUIRED_STATES = frozenset({
    "attempted", "succeeded", "partial", "failed", "blocked", "stale", "no_result_observed"
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _require_case(case_id: str) -> str:
    case_id = case_id.strip()
    if not _CASE_RE.fullmatch(case_id):
        raise ValueError("case_id must be machine-safe and <=160 characters")
    return case_id


def _entry_from_json(payload: Mapping[str, Any]) -> SourceRegistryEntry:
    return SourceRegistryEntry(
        source_id=str(payload["source_id"]),
        name=str(payload["name"]),
        access_basis=AccessBasis(str(payload["access_basis"])),
        execution_mode=SourceExecutionMode(str(payload.get("execution_mode", "plan_only"))),
        jurisdictions=tuple(payload.get("jurisdictions") or ()),
        source_classes=tuple(payload.get("source_classes") or ()),
        entity_types=tuple(payload.get("entity_types") or ()),
        access_methods=tuple(payload.get("access_methods") or ("GET",)),
        endpoint=payload.get("endpoint"),
        local_dataset=bool(payload.get("local_dataset", False)),
        license_reference=payload.get("license_reference"),
        terms_reference=payload.get("terms_reference"),
        freshness_seconds=payload.get("freshness_seconds"),
        historical_depth=payload.get("historical_depth"),
        rate_limit_hint=payload.get("rate_limit_hint"),
        provenance_required=bool(payload.get("provenance_required", True)),
        human_source_review_required=bool(payload.get("human_source_review_required", True)),
        external_validation_state=str(payload.get("external_validation_state", "not_run")),
        notes=payload.get("notes"),
    )


@dataclass(frozen=True, slots=True)
class PersistentResearchPlan382:
    plan_id: str
    case_id: str
    mission: str
    plan_hash: str
    registry_fingerprint: str
    source_ids: tuple[str, ...]
    requested_jurisdictions: tuple[str, ...]
    requested_source_classes: tuple[str, ...]
    requested_entity_types: tuple[str, ...]
    requires_go: bool = True
    execution_authority: bool = False
    scope_expansion_authority: bool = False
    network_requests_created: int = 0
    policy_id: str = POLICY_ID


@dataclass(frozen=True, slots=True)
class CoverageGap:
    gap_type: str
    key: str
    detail: str


@dataclass(frozen=True, slots=True)
class CoverageReport382:
    case_id: str
    registry_source_count: int
    case_candidate_count: int
    case_approved_count: int
    observed_source_count: int
    successful_or_partial_count: int
    stale_count: int
    failed_or_blocked_count: int
    requested_source_classes: tuple[str, ...]
    covered_source_classes: tuple[str, ...]
    gaps: tuple[CoverageGap, ...]
    no_result_is_nonexistence: bool = False
    network_requests_created: int = 0
    policy_id: str = POLICY_ID


class SourceRegistryRepository382:
    """SQLite reference implementation for the Phase-17 source/data planning ledger.

    The schema uses generic durable table names rather than per-build telemetry tables so the
    integration patch can map cleanly into the canonical EagleEye schema later.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.db = connection
        self.db.row_factory = sqlite3.Row
        self._schema_integrity_cache: Mapping[str, Any] | None = None
        self._registry_cache: GlobalSourceRegistry381 | None = None
        self._registry_fingerprint_cache: str | None = None
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS source_registry_sources (
                source_id TEXT PRIMARY KEY,
                current_revision INTEGER NOT NULL,
                current_hash TEXT NOT NULL,
                entry_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_registry_revisions (
                source_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                entry_hash TEXT NOT NULL,
                entry_json TEXT NOT NULL,
                actor TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(source_id, revision)
            );
            CREATE TABLE IF NOT EXISTS case_source_scope (
                case_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                state TEXT NOT NULL,
                reviewer TEXT,
                note TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(case_id, source_id),
                FOREIGN KEY(source_id) REFERENCES source_registry_sources(source_id)
            );
            CREATE TABLE IF NOT EXISTS research_plan_ledger (
                plan_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                plan_hash TEXT NOT NULL UNIQUE,
                registry_fingerprint TEXT NOT NULL,
                mission TEXT NOT NULL,
                selectors_json TEXT NOT NULL,
                source_ids_json TEXT NOT NULL,
                requires_go INTEGER NOT NULL,
                execution_authority INTEGER NOT NULL,
                scope_expansion_authority INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_coverage_ledger (
                observation_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                state TEXT NOT NULL,
                evidence_ref TEXT,
                detail TEXT,
                observed_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES source_registry_sources(source_id)
            );
            CREATE INDEX IF NOT EXISTS idx_case_source_scope_case ON case_source_scope(case_id, state);
            CREATE INDEX IF NOT EXISTS idx_research_plan_case ON research_plan_ledger(case_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_source_coverage_case ON source_coverage_ledger(case_id, source_id, observed_at);
            """
        )
        self.db.commit()
        self._schema_integrity_cache = None

    def schema_integrity(self) -> Mapping[str, Any]:
        if self._schema_integrity_cache is not None:
            return dict(self._schema_integrity_cache)
        result = self.db.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {
            r[0] for r in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        required = {
            "source_registry_sources", "source_registry_revisions", "case_source_scope",
            "research_plan_ledger", "source_coverage_ledger",
        }
        value = {
            "integrity_check": result,
            "required_tables_present": required.issubset(tables),
            "table_count": len(tables),
            "missing_tables": sorted(required - tables),
        }
        self._schema_integrity_cache = dict(value)
        return value

    def upsert_source(self, entry: SourceRegistryEntry, *, actor: str, reason: str) -> Mapping[str, Any]:
        actor = actor.strip()
        reason = reason.strip()
        if not actor or not reason:
            raise ValueError("actor and reason are required")
        # Reuse the strict Build-381 validation contract.
        validated_registry = GlobalSourceRegistry381([entry])
        normalized = validated_registry.get(entry.source_id)
        assert normalized is not None
        entry_json = _json(asdict(normalized))
        entry_hash = normalized.registry_hash
        current = self.db.execute(
            "SELECT current_revision,current_hash FROM source_registry_sources WHERE source_id=?",
            (normalized.source_id,),
        ).fetchone()
        if current and current["current_hash"] == entry_hash:
            return {"source_id": normalized.source_id, "revision": int(current["current_revision"]), "changed": False, "entry_hash": entry_hash}
        revision = 1 if current is None else int(current["current_revision"]) + 1
        now = _utc_now()
        with self.db:
            self.db.execute(
                "INSERT INTO source_registry_revisions(source_id,revision,entry_hash,entry_json,actor,reason,created_at) VALUES(?,?,?,?,?,?,?)",
                (normalized.source_id, revision, entry_hash, entry_json, actor, reason, now),
            )
            self.db.execute(
                """INSERT INTO source_registry_sources(source_id,current_revision,current_hash,entry_json,updated_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(source_id) DO UPDATE SET
                     current_revision=excluded.current_revision,
                     current_hash=excluded.current_hash,
                     entry_json=excluded.entry_json,
                     updated_at=excluded.updated_at""",
                (normalized.source_id, revision, entry_hash, entry_json, now),
            )
        self._registry_cache = None
        self._registry_fingerprint_cache = None
        return {"source_id": normalized.source_id, "revision": revision, "changed": True, "entry_hash": entry_hash}

    def seed(self, entries: Iterable[SourceRegistryEntry], *, actor: str = "build382", reason: str = "phase17_seed") -> int:
        changed = 0
        for entry in entries:
            changed += int(bool(self.upsert_source(entry, actor=actor, reason=reason)["changed"]))
        return changed

    def load_registry(self) -> GlobalSourceRegistry381:
        if self._registry_cache is not None:
            return self._registry_cache
        entries: list[SourceRegistryEntry] = []
        for row in self.db.execute("SELECT entry_json FROM source_registry_sources ORDER BY source_id"):
            entries.append(_entry_from_json(json.loads(row["entry_json"])))
        self._registry_cache = GlobalSourceRegistry381(entries)
        return self._registry_cache

    def revision_history(self, source_id: str) -> tuple[Mapping[str, Any], ...]:
        rows = self.db.execute(
            "SELECT source_id,revision,entry_hash,actor,reason,created_at FROM source_registry_revisions WHERE source_id=? ORDER BY revision",
            (source_id,),
        ).fetchall()
        return tuple(dict(r) for r in rows)

    def registry_fingerprint(self) -> str:
        if self._registry_fingerprint_cache is not None:
            return self._registry_fingerprint_cache
        values = {
            row["source_id"]: row["current_hash"]
            for row in self.db.execute("SELECT source_id,current_hash FROM source_registry_sources ORDER BY source_id")
        }
        self._registry_fingerprint_cache = _hash(values)
        return self._registry_fingerprint_cache

    def set_case_scope(
        self,
        *,
        case_id: str,
        source_id: str,
        state: str,
        reviewer: str | None = None,
        note: str | None = None,
        confirmation: str | None = None,
    ) -> None:
        case_id = _require_case(case_id)
        if state not in _SOURCE_SCOPE_STATES:
            raise ValueError("unsupported case source state")
        if self.db.execute("SELECT 1 FROM source_registry_sources WHERE source_id=?", (source_id,)).fetchone() is None:
            raise KeyError(source_id)
        if state == "approved":
            if not reviewer or not reviewer.strip():
                raise ValueError("human reviewer required for source approval")
            if confirmation != "APPROVE SOURCE":
                raise ValueError("exact APPROVE SOURCE confirmation required")
        with self.db:
            self.db.execute(
                """INSERT INTO case_source_scope(case_id,source_id,state,reviewer,note,updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(case_id,source_id) DO UPDATE SET
                     state=excluded.state, reviewer=excluded.reviewer, note=excluded.note, updated_at=excluded.updated_at""",
                (case_id, source_id, state, reviewer.strip() if reviewer else None, note, _utc_now()),
            )

    def case_scope(self, case_id: str) -> tuple[Mapping[str, Any], ...]:
        case_id = _require_case(case_id)
        rows = self.db.execute(
            "SELECT case_id,source_id,state,reviewer,note,updated_at FROM case_source_scope WHERE case_id=? ORDER BY source_id",
            (case_id,),
        ).fetchall()
        return tuple(dict(r) for r in rows)

    def persist_plan(
        self,
        plan: InvestigationPlan,
        *,
        jurisdictions: Sequence[str] = (),
        source_classes: Sequence[str] = (),
        entity_types: Sequence[str] = (),
    ) -> PersistentResearchPlan382:
        case_id = _require_case(plan.case_id)
        if plan.execution_authority or plan.scope_expansion_authority or not plan.requires_go or plan.network_requests_created:
            raise ValueError("Build 382 only persists review-first network-silent plans")
        registry_fp = self.registry_fingerprint()
        selectors = {
            "jurisdictions": sorted({x.strip() for x in jurisdictions if x.strip()}),
            "source_classes": sorted({x.strip() for x in source_classes if x.strip()}),
            "entity_types": sorted({x.strip() for x in entity_types if x.strip()}),
        }
        source_ids = tuple(c.source_id for c in plan.source_candidates)
        plan_id = f"rp382-{plan.plan_hash[:24]}"
        with self.db:
            self.db.execute(
                """INSERT OR IGNORE INTO research_plan_ledger(
                       plan_id,case_id,plan_hash,registry_fingerprint,mission,selectors_json,source_ids_json,
                       requires_go,execution_authority,scope_expansion_authority,created_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    plan_id, case_id, plan.plan_hash, registry_fp, plan.mission, _json(selectors), _json(source_ids),
                    1, 0, 0, _utc_now(),
                ),
            )
            for source_id in source_ids:
                self.db.execute(
                    """INSERT INTO case_source_scope(case_id,source_id,state,reviewer,note,updated_at)
                       VALUES(?,?, 'candidate',NULL,'research_plan_candidate',?)
                       ON CONFLICT(case_id,source_id) DO NOTHING""",
                    (case_id, source_id, _utc_now()),
                )
        return PersistentResearchPlan382(
            plan_id=plan_id,
            case_id=case_id,
            mission=plan.mission,
            plan_hash=plan.plan_hash,
            registry_fingerprint=registry_fp,
            source_ids=source_ids,
            requested_jurisdictions=tuple(selectors["jurisdictions"]),
            requested_source_classes=tuple(selectors["source_classes"]),
            requested_entity_types=tuple(selectors["entity_types"]),
        )

    def get_plan(self, plan_id: str) -> Mapping[str, Any] | None:
        row = self.db.execute("SELECT * FROM research_plan_ledger WHERE plan_id=?", (plan_id,)).fetchone()
        return dict(row) if row else None

    def record_coverage(
        self,
        *,
        case_id: str,
        source_id: str,
        state: str,
        evidence_ref: str | None = None,
        detail: str | None = None,
        observed_at: str | None = None,
    ) -> str:
        case_id = _require_case(case_id)
        if state not in _COVERAGE_STATES:
            raise ValueError("unsupported coverage state")
        if self.db.execute("SELECT 1 FROM source_registry_sources WHERE source_id=?", (source_id,)).fetchone() is None:
            raise KeyError(source_id)
        if state in _EVIDENCE_REQUIRED_STATES and (not evidence_ref or not evidence_ref.strip()):
            raise ValueError("evidence_ref required for attempted/result coverage states")
        if evidence_ref and len(evidence_ref) > 512:
            raise ValueError("evidence_ref too long")
        observed_at = observed_at or _utc_now()
        payload = {
            "case_id": case_id,
            "source_id": source_id,
            "state": state,
            "evidence_ref": evidence_ref,
            "detail": detail,
            "observed_at": observed_at,
        }
        observation_id = f"cov382-{_hash(payload)[:28]}"
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO source_coverage_ledger(observation_id,case_id,source_id,state,evidence_ref,detail,observed_at) VALUES(?,?,?,?,?,?,?)",
                (observation_id, case_id, source_id, state, evidence_ref, detail, observed_at),
            )
        return observation_id

    def coverage_report(self, case_id: str, *, requested_source_classes: Sequence[str] = ()) -> CoverageReport382:
        case_id = _require_case(case_id)
        registry = self.load_registry()
        entries = registry.all()
        entry_by_id = {e.source_id: e for e in entries}
        scope = self.case_scope(case_id)
        candidate_ids = {r["source_id"] for r in scope if r["state"] == "candidate"}
        approved_ids = {r["source_id"] for r in scope if r["state"] == "approved"}
        latest: dict[str, sqlite3.Row] = {}
        for row in self.db.execute(
            "SELECT * FROM source_coverage_ledger WHERE case_id=? ORDER BY observed_at, observation_id",
            (case_id,),
        ):
            latest[row["source_id"]] = row
        successful = {sid for sid, row in latest.items() if row["state"] in {"succeeded", "partial"}}
        stale = {sid for sid, row in latest.items() if row["state"] == "stale"}
        failed = {sid for sid, row in latest.items() if row["state"] in {"failed", "blocked"}}

        requested = tuple(sorted({x.strip() for x in requested_source_classes if x.strip()}))
        covered_classes: set[str] = set()
        for sid in successful:
            entry = entry_by_id.get(sid)
            if entry:
                covered_classes.update(entry.source_classes)

        gaps: list[CoverageGap] = []
        for source_class in requested:
            registry_sources = {e.source_id for e in entries if source_class.casefold() in {c.casefold() for c in e.source_classes}}
            if not registry_sources:
                gaps.append(CoverageGap("registry_gap", source_class, "no catalogued source for requested class"))
                continue
            scoped_sources = registry_sources & (candidate_ids | approved_ids)
            if not scoped_sources:
                gaps.append(CoverageGap("selection_gap", source_class, "catalogued sources exist but none are in case scope"))
                continue
            if not (registry_sources & successful):
                gaps.append(CoverageGap("coverage_gap", source_class, "case-scoped sources exist but no succeeded/partial evidence-linked observation is recorded"))
        for sid in sorted(stale):
            gaps.append(CoverageGap("stale_source", sid, "latest observation is stale"))
        for sid in sorted(failed):
            gaps.append(CoverageGap("failed_or_blocked", sid, "latest observation failed or was blocked"))

        return CoverageReport382(
            case_id=case_id,
            registry_source_count=len(entries),
            case_candidate_count=len(candidate_ids),
            case_approved_count=len(approved_ids),
            observed_source_count=len(latest),
            successful_or_partial_count=len(successful),
            stale_count=len(stale),
            failed_or_blocked_count=len(failed),
            requested_source_classes=requested,
            covered_source_classes=tuple(sorted(covered_classes)),
            gaps=tuple(gaps),
        )


class InvestigationControlPlane382:
    """Persistent facade over Build 381 planning; remains read-only with respect to networks."""

    def __init__(self, repository: SourceRegistryRepository382, providers: Mapping[str, Any]) -> None:
        self.repository = repository
        self.providers = dict(providers)

    def snapshot(self, case_id: str) -> Mapping[str, Any]:
        schema = self.repository.schema_integrity()
        registry = self.repository.load_registry()
        cp = InvestigationControlPlane381(registry, self.providers)
        base = cp.snapshot(case_id)
        return {
            "build": BUILD,
            "case_id": base.case_id,
            "research_ready": bool(base.research_ready and schema["integrity_check"] == "ok" and schema["required_tables_present"]),
            "base_control_plane_hash": base.snapshot_hash,
            "capability_states": dict(base.capability_states),
            "operations_hold": base.operations_hold,
            "opsec_hold": base.opsec_hold,
            "reasons": base.reasons,
            "registry_fingerprint": self.repository.registry_fingerprint(),
            "registry_source_count": registry.coverage()["source_count"],
            "persistence": dict(schema),
            "network_requests_created": 0,
            "mutations_performed": 0,
            "execution_authority": False,
            "scope_expansion_authority": False,
            "policy_id": POLICY_ID,
        }

    def plan_research(
        self,
        *,
        case_id: str,
        mission: str,
        jurisdictions: Sequence[str] = (),
        source_classes: Sequence[str] = (),
        entity_types: Sequence[str] = (),
        limit: int = 12,
    ) -> PersistentResearchPlan382:
        snap = self.snapshot(case_id)
        if not snap["research_ready"]:
            raise RuntimeError("research planning held by Build-382 control-plane/persistence preflight")
        registry = self.repository.load_registry()
        base_cp = InvestigationControlPlane381(registry, self.providers)
        plan = base_cp.plan_research(
            case_id=case_id,
            mission=mission,
            jurisdictions=jurisdictions,
            source_classes=source_classes,
            entity_types=entity_types,
            limit=limit,
        )
        return self.repository.persist_plan(
            plan,
            jurisdictions=jurisdictions,
            source_classes=source_classes,
            entity_types=entity_types,
        )


def create_reference_repository(connection: sqlite3.Connection | None = None) -> SourceRegistryRepository382:
    connection = connection or sqlite3.connect(":memory:")
    repo = SourceRegistryRepository382(connection)
    repo.seed(default_registry().all())
    return repo
