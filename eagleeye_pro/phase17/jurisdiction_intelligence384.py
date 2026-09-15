"""Build 384: Jurisdiction Intelligence and governed multi-wave research planning.

This module turns a Build-383 acquisition plan into jurisdiction-aware, bounded,
review-first research waves.  It remains network-silent and grants no connector,
crawler, credential, scope-expansion, identity-merge, or host-security authority.

The purpose is to make data acquisition systematic: identify which jurisdiction/source
classes should be covered, expose registry/validation/access gaps, and produce an
ordered plan for later human-authorized execution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import sqlite3
from typing import Any, Iterable, Mapping, Sequence

from .source_planner383 import (
    BUILD as BUILD_383,
    AcquisitionPlan383,
    PlannerGap383,
    SourcePlanner383,
    SourcePlannerRepository383,
)

BUILD = "384.0"
BASE_OVERLAY_BUILD = BUILD_383
POLICY_ID = "phase17.jurisdiction-intelligence-research-waves.v384"
CONFIRM_WAVES = "CONFIRM WAVES"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _norm(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip().casefold() for v in values if str(v).strip()}))


@dataclass(frozen=True, slots=True)
class JurisdictionProfile384:
    jurisdiction: str
    source_classes: tuple[str, ...]
    preferred_source_classes: tuple[str, ...] = ()
    required_review: bool = True
    execution_authority: bool = False


@dataclass(frozen=True, slots=True)
class WaveStep384:
    source_id: str
    source_class: str
    jurisdiction: str
    priority: int
    template_id: str
    rationale: tuple[str, ...]
    external_validation_state: str
    execution_mode: str
    requires_review: bool = True
    execution_authority: bool = False


@dataclass(frozen=True, slots=True)
class ResearchWave384:
    wave_number: int
    purpose: str
    source_classes: tuple[str, ...]
    jurisdictions: tuple[str, ...]
    steps: tuple[WaveStep384, ...]
    gap_types_addressed: tuple[str, ...]
    max_steps: int
    requires_go: bool = True
    execution_authority: bool = False


@dataclass(frozen=True, slots=True)
class CoverageObjective384:
    key: str
    source_class: str
    jurisdiction: str
    target: str
    currently_catalogued: int
    currently_planned: int
    gap_state: str


@dataclass(frozen=True, slots=True)
class WavePlan384:
    wave_plan_id: str
    case_id: str
    mission: str
    acquisition_plan_id: str
    jurisdictions: tuple[str, ...]
    entity_types: tuple[str, ...]
    waves: tuple[ResearchWave384, ...]
    coverage_objectives: tuple[CoverageObjective384, ...]
    gaps: tuple[PlannerGap383, ...]
    confirmation_state: str
    registry_fingerprint: str
    requires_go: bool = True
    requires_wave_confirmation: bool = True
    execution_authority: bool = False
    scope_expansion_authority: bool = False
    network_requests_created: int = 0
    policy_id: str = POLICY_ID

    @property
    def plan_hash(self) -> str:
        payload = asdict(self)
        payload.pop("wave_plan_id", None)
        return _stable_hash(payload)


class JurisdictionRepository384(SourcePlannerRepository383):
    def ensure_schema(self) -> None:
        super().ensure_schema()
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS jurisdiction_profile_384 (
                jurisdiction TEXT PRIMARY KEY,
                source_classes_json TEXT NOT NULL,
                preferred_source_classes_json TEXT NOT NULL,
                required_review INTEGER NOT NULL,
                execution_authority INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS research_wave_plan_384 (
                wave_plan_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                plan_hash TEXT NOT NULL UNIQUE,
                acquisition_plan_id TEXT NOT NULL,
                mission TEXT NOT NULL,
                jurisdictions_json TEXT NOT NULL,
                entity_types_json TEXT NOT NULL,
                confirmation_state TEXT NOT NULL,
                registry_fingerprint TEXT NOT NULL,
                requires_go INTEGER NOT NULL,
                requires_wave_confirmation INTEGER NOT NULL,
                execution_authority INTEGER NOT NULL,
                scope_expansion_authority INTEGER NOT NULL,
                network_requests_created INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS research_wave_384 (
                wave_plan_id TEXT NOT NULL,
                wave_number INTEGER NOT NULL,
                wave_json TEXT NOT NULL,
                PRIMARY KEY(wave_plan_id, wave_number),
                FOREIGN KEY(wave_plan_id) REFERENCES research_wave_plan_384(wave_plan_id)
            );
            CREATE TABLE IF NOT EXISTS coverage_objective_384 (
                wave_plan_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                objective_json TEXT NOT NULL,
                PRIMARY KEY(wave_plan_id, ordinal),
                FOREIGN KEY(wave_plan_id) REFERENCES research_wave_plan_384(wave_plan_id)
            );
            CREATE TABLE IF NOT EXISTS wave_gap_384 (
                wave_plan_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                gap_json TEXT NOT NULL,
                PRIMARY KEY(wave_plan_id, ordinal),
                FOREIGN KEY(wave_plan_id) REFERENCES research_wave_plan_384(wave_plan_id)
            );
            CREATE INDEX IF NOT EXISTS idx_research_wave_plan_384_case
                ON research_wave_plan_384(case_id, created_at);
            """
        )
        self.db.commit()
        self._schema_integrity_cache = None

    def upsert_jurisdiction_profile(self, profile: JurisdictionProfile384) -> None:
        if profile.execution_authority:
            raise ValueError("Build 384 jurisdiction profiles cannot grant execution authority")
        with self.db:
            self.db.execute(
                """INSERT INTO jurisdiction_profile_384(
                    jurisdiction,source_classes_json,preferred_source_classes_json,
                    required_review,execution_authority
                ) VALUES(?,?,?,?,?)
                ON CONFLICT(jurisdiction) DO UPDATE SET
                    source_classes_json=excluded.source_classes_json,
                    preferred_source_classes_json=excluded.preferred_source_classes_json,
                    required_review=excluded.required_review,
                    execution_authority=excluded.execution_authority""",
                (
                    profile.jurisdiction.casefold(),
                    _stable_json(_norm(profile.source_classes)),
                    _stable_json(_norm(profile.preferred_source_classes)),
                    int(profile.required_review),
                    0,
                ),
            )

    def load_jurisdiction_profiles(self) -> Mapping[str, JurisdictionProfile384]:
        rows = self.db.execute("SELECT * FROM jurisdiction_profile_384 ORDER BY jurisdiction").fetchall()
        out: dict[str, JurisdictionProfile384] = {}
        for row in rows:
            data = dict(row)
            out[data["jurisdiction"]] = JurisdictionProfile384(
                jurisdiction=data["jurisdiction"],
                source_classes=tuple(json.loads(data["source_classes_json"])),
                preferred_source_classes=tuple(json.loads(data["preferred_source_classes_json"])),
                required_review=bool(data["required_review"]),
                execution_authority=False,
            )
        return out

    def persist_wave_plan(self, plan: WavePlan384) -> None:
        if plan.execution_authority or plan.scope_expansion_authority or plan.network_requests_created:
            raise ValueError("Build 384 persists network-silent, non-executing plans only")
        with self.db:
            self.db.execute(
                """INSERT OR IGNORE INTO research_wave_plan_384(
                    wave_plan_id,case_id,plan_hash,acquisition_plan_id,mission,
                    jurisdictions_json,entity_types_json,confirmation_state,
                    registry_fingerprint,requires_go,requires_wave_confirmation,
                    execution_authority,scope_expansion_authority,network_requests_created
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    plan.wave_plan_id, plan.case_id, plan.plan_hash, plan.acquisition_plan_id,
                    plan.mission, _stable_json(plan.jurisdictions), _stable_json(plan.entity_types),
                    plan.confirmation_state, plan.registry_fingerprint, 1,
                    int(plan.requires_wave_confirmation), 0, 0, 0,
                ),
            )
            for wave in plan.waves:
                self.db.execute(
                    "INSERT OR IGNORE INTO research_wave_384(wave_plan_id,wave_number,wave_json) VALUES(?,?,?)",
                    (plan.wave_plan_id, wave.wave_number, _stable_json(asdict(wave))),
                )
            for idx, objective in enumerate(plan.coverage_objectives):
                self.db.execute(
                    "INSERT OR IGNORE INTO coverage_objective_384(wave_plan_id,ordinal,objective_json) VALUES(?,?,?)",
                    (plan.wave_plan_id, idx, _stable_json(asdict(objective))),
                )
            for idx, gap in enumerate(plan.gaps):
                self.db.execute(
                    "INSERT OR IGNORE INTO wave_gap_384(wave_plan_id,ordinal,gap_json) VALUES(?,?,?)",
                    (plan.wave_plan_id, idx, _stable_json(asdict(gap))),
                )

    def schema_integrity(self) -> Mapping[str, Any]:
        base = dict(super().schema_integrity())
        tables = {
            r[0] for r in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        required = {
            "jurisdiction_profile_384", "research_wave_plan_384", "research_wave_384",
            "coverage_objective_384", "wave_gap_384",
        }
        base.update({
            "build384_tables_present": required.issubset(tables),
            "build384_missing_tables": sorted(required - tables),
            "table_count": len(tables),
        })
        return base


_DEFAULT_JURISDICTION_PROFILES: tuple[JurisdictionProfile384, ...] = (
    JurisdictionProfile384("global", ("corporate", "reference", "archive", "sanctions", "regulatory"), ("reference", "corporate")),
    JurisdictionProfile384("us", ("corporate", "procurement", "public_money", "regulatory", "government", "legal", "archive", "reference", "sanctions"), ("corporate", "public_money", "regulatory")),
    JurisdictionProfile384("eu", ("corporate", "procurement", "regulatory", "government", "legal", "archive", "reference", "sanctions"), ("procurement", "corporate", "regulatory")),
    JurisdictionProfile384("de", ("corporate", "procurement", "government", "legal", "archive", "reference", "sanctions"), ("corporate", "procurement")),
)


class JurisdictionIntelligence384:
    def __init__(self, repository: JurisdictionRepository384, providers: Mapping[str, Any]) -> None:
        self.repository = repository
        self.providers = dict(providers)

    def seed_default_profiles(self) -> None:
        for profile in _DEFAULT_JURISDICTION_PROFILES:
            self.repository.upsert_jurisdiction_profile(profile)

    def _coverage_objectives(self, plan: AcquisitionPlan383) -> tuple[CoverageObjective384, ...]:
        registry = self.repository.load_registry().all()
        objectives: list[CoverageObjective384] = []
        jurisdictions = plan.jurisdictions or ("global",)
        for source_class in plan.active_source_classes:
            for jurisdiction in jurisdictions:
                catalogued = [
                    e for e in registry
                    if source_class in {c.casefold() for c in e.source_classes}
                    and (
                        jurisdiction in {j.casefold() for j in e.jurisdictions}
                        or "global" in {j.casefold() for j in e.jurisdictions}
                    )
                ]
                planned = [
                    s for s in plan.steps
                    if s.source_class == source_class and s.source_id in {e.source_id for e in catalogued}
                ]
                if not catalogued:
                    gap_state = "registry_gap"
                elif not planned:
                    gap_state = "planning_gap"
                elif all(s.external_validation_state in {"not_run", "plan_only", "failed"} for s in planned):
                    gap_state = "validation_gap"
                else:
                    gap_state = "planned"
                objectives.append(CoverageObjective384(
                    key=f"{jurisdiction}:{source_class}",
                    source_class=source_class,
                    jurisdiction=jurisdiction,
                    target="at_least_one_reviewable_source",
                    currently_catalogued=len(catalogued),
                    currently_planned=len(planned),
                    gap_state=gap_state,
                ))
        return tuple(objectives)

    @staticmethod
    def _wave_bucket(step: Any) -> int:
        if step.external_validation_state in {"externally_validated", "validated_local"}:
            return 1
        if step.execution_mode == "live_eligible":
            return 2
        return 3

    def plan_waves(
        self,
        *,
        case_id: str,
        mission: str,
        jurisdictions: Sequence[str] = (),
        entity_types: Sequence[str] = (),
        source_classes: Sequence[str] = (),
        selector_confirmation: str | None = None,
        wave_confirmation: str | None = None,
        max_steps_per_wave: int = 8,
    ) -> WavePlan384:
        if max_steps_per_wave < 1 or max_steps_per_wave > 20:
            raise ValueError("max_steps_per_wave must be between 1 and 20")
        if wave_confirmation is not None and wave_confirmation != CONFIRM_WAVES:
            raise ValueError("wave confirmation must be exact CONFIRM WAVES")

        planner = SourcePlanner383(self.repository, self.providers)
        acquisition = planner.plan(
            case_id=case_id,
            mission=mission,
            jurisdictions=jurisdictions,
            entity_types=entity_types,
            source_classes=source_classes,
            confirmation=selector_confirmation,
        )

        objectives = self._coverage_objectives(acquisition)
        gaps = list(acquisition.gaps)
        for objective in objectives:
            if objective.gap_state != "planned":
                gaps.append(PlannerGap383(
                    objective.gap_state,
                    objective.key,
                    "high" if objective.gap_state == "registry_gap" else "medium",
                    f"coverage objective {objective.key} is not yet fully planned",
                ))

        buckets: dict[int, list[WaveStep384]] = {1: [], 2: [], 3: []}
        plan_jurs = acquisition.jurisdictions or ("global",)
        for step in acquisition.steps:
            # A source can cover multiple jurisdictions; retain requested jurisdiction context without
            # pretending a source is jurisdiction-specific when only global coverage is known.
            jurisdiction = plan_jurs[0] if len(plan_jurs) == 1 else "multi"
            buckets[self._wave_bucket(step)].append(WaveStep384(
                source_id=step.source_id,
                source_class=step.source_class,
                jurisdiction=jurisdiction,
                priority=step.priority,
                template_id=step.template_id,
                rationale=step.reasons,
                external_validation_state=step.external_validation_state,
                execution_mode=step.execution_mode,
            ))

        purposes = {
            1: "Start with locally/externally validated high-confidence source paths",
            2: "Review live-eligible but not fully validated source paths",
            3: "Resolve plan-only and unresolved coverage gaps before any execution",
        }
        waves: list[ResearchWave384] = []
        number = 1
        for bucket in (1, 2, 3):
            steps = sorted(buckets[bucket], key=lambda s: (-s.priority, s.source_class, s.source_id))
            while steps:
                chunk, steps = steps[:max_steps_per_wave], steps[max_steps_per_wave:]
                waves.append(ResearchWave384(
                    wave_number=number,
                    purpose=purposes[bucket],
                    source_classes=tuple(sorted({s.source_class for s in chunk})),
                    jurisdictions=plan_jurs,
                    steps=tuple(chunk),
                    gap_types_addressed=tuple(sorted({g.gap_type for g in gaps})),
                    max_steps=max_steps_per_wave,
                ))
                number += 1

        confirmed = wave_confirmation == CONFIRM_WAVES
        payload = {
            "case_id": case_id,
            "mission": mission.strip(),
            "acquisition_plan_id": acquisition.plan_id,
            "jurisdictions": acquisition.jurisdictions,
            "entity_types": acquisition.entity_types,
            "waves": [asdict(w) for w in waves],
            "coverage": [asdict(o) for o in objectives],
            "gaps": [asdict(g) for g in gaps],
            "confirmation_state": "confirmed" if confirmed else "preview",
            "registry_fingerprint": acquisition.registry_fingerprint,
            "policy_id": POLICY_ID,
        }
        plan_hash = _stable_hash(payload)
        result = WavePlan384(
            wave_plan_id=f"wp384-{plan_hash[:24]}",
            case_id=case_id,
            mission=mission.strip(),
            acquisition_plan_id=acquisition.plan_id,
            jurisdictions=acquisition.jurisdictions,
            entity_types=acquisition.entity_types,
            waves=tuple(waves),
            coverage_objectives=objectives,
            gaps=tuple(gaps),
            confirmation_state="confirmed" if confirmed else "preview",
            registry_fingerprint=acquisition.registry_fingerprint,
            requires_wave_confirmation=not confirmed,
        )
        self.repository.persist_wave_plan(result)
        return result


def create_reference_repository384(connection: sqlite3.Connection | None = None) -> JurisdictionRepository384:
    connection = connection or sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    repo = JurisdictionRepository384(connection)
    from .investigation_control381 import default_registry
    repo.seed(default_registry().all())
    service = JurisdictionIntelligence384(repo, {})
    service.seed_default_profiles()
    return repo
