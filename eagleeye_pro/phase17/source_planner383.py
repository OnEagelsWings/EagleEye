"""Build 383: governed Source Planner v1 for EagleEye Phase 17.

The planner translates an investigation mission into transparent *proposed* source-class
requirements, ranks already-catalogued sources, selects acquisition templates and records
coverage/data gaps. It remains network-silent and cannot execute connectors.

Governance invariants:
- mission inference is advisory only and cannot expand case scope by itself;
- inferred selectors require exact human ``CONFIRM SELECTORS`` before they are persisted
  as case source candidates;
- explicit source selectors may be planned directly, but still create candidate scope only;
- every persisted underlying Build-382 research plan requires GO and has no execution authority;
- only public, licensed, or explicitly authorized registry sources are considered;
- no authentication bypass, credential use, identity merge, network work, or host/security mutation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
import sqlite3
from typing import Any, Iterable, Mapping, Sequence

from .investigation_control381 import SourceExecutionMode, SourceRegistryEntry, default_registry
from .source_registry_persistence382 import (
    BUILD as BUILD_382,
    InvestigationControlPlane382,
    PersistentResearchPlan382,
    SourceRegistryRepository382,
)

BUILD = "383.0"
POLICY_ID = "phase17.source-planner-taxonomy-gap-analysis.v383"
BASE_OVERLAY_BUILD = BUILD_382
CONFIRM_INFERRED_SELECTORS = "CONFIRM SELECTORS"


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _norm(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip().casefold() for v in values if str(v).strip()}))


@dataclass(frozen=True, slots=True)
class AcquisitionTemplate383:
    template_id: str
    source_class: str
    purpose: str
    preferred_access_methods: tuple[str, ...]
    query_shapes: tuple[str, ...]
    normalization_targets: tuple[str, ...]
    provenance_requirements: tuple[str, ...] = ("source_id", "retrieved_at", "content_hash")
    review_required: bool = True
    execution_authority: bool = False


@dataclass(frozen=True, slots=True)
class SourceRequirement383:
    source_class: str
    origin: str
    reason: str
    weight: int


@dataclass(frozen=True, slots=True)
class PlannedSourceStep383:
    source_id: str
    source_name: str
    source_class: str
    template_id: str
    priority: int
    reasons: tuple[str, ...]
    access_methods: tuple[str, ...]
    execution_mode: str
    external_validation_state: str
    requires_human_review: bool = True
    execution_authority: bool = False


@dataclass(frozen=True, slots=True)
class PlannerGap383:
    gap_type: str
    key: str
    severity: str
    detail: str


@dataclass(frozen=True, slots=True)
class AcquisitionPlan383:
    plan_id: str
    case_id: str
    mission: str
    explicit_source_classes: tuple[str, ...]
    inferred_source_classes: tuple[str, ...]
    active_source_classes: tuple[str, ...]
    selector_state: str
    jurisdictions: tuple[str, ...]
    entity_types: tuple[str, ...]
    steps: tuple[PlannedSourceStep383, ...]
    gaps: tuple[PlannerGap383, ...]
    underlying_plan_id: str | None
    registry_fingerprint: str
    requires_go: bool = True
    requires_selector_review: bool = False
    execution_authority: bool = False
    scope_expansion_authority: bool = False
    network_requests_created: int = 0
    policy_id: str = POLICY_ID

    @property
    def plan_hash(self) -> str:
        payload = asdict(self)
        payload.pop("plan_id", None)
        return _stable_hash(payload)


TEMPLATES: tuple[AcquisitionTemplate383, ...] = (
    AcquisitionTemplate383(
        "corporate.identity.v1", "corporate", "Resolve legal entities, filings, officers and identifiers",
        ("LOCAL", "BULK", "GET", "POST"),
        ("exact_identifier", "exact_name", "name_plus_jurisdiction", "historical_name"),
        ("legal_entity", "identifier", "officer", "filing", "address"),
    ),
    AcquisitionTemplate383(
        "procurement.awards.v1", "procurement", "Identify awards, notices, buyers, suppliers and contract relationships",
        ("LOCAL", "BULK", "GET", "POST"),
        ("entity_identifier", "supplier_name", "buyer_name", "date_range", "award_identifier"),
        ("award", "supplier", "buyer", "amount", "currency", "date"),
    ),
    AcquisitionTemplate383(
        "public-money.flows.v1", "public_money", "Trace public spending and related organizational links",
        ("LOCAL", "BULK", "GET", "POST"),
        ("recipient_identifier", "recipient_name", "program", "date_range"),
        ("recipient", "agency", "amount", "program", "award"),
    ),
    AcquisitionTemplate383(
        "regulatory.documents.v1", "regulatory", "Collect regulatory filings, notices and official decisions",
        ("LOCAL", "BULK", "GET"),
        ("entity_identifier", "entity_name", "document_type", "date_range"),
        ("document", "issuer", "subject", "effective_date"),
    ),
    AcquisitionTemplate383(
        "government.records.v1", "government", "Collect official government records and publications",
        ("LOCAL", "BULK", "GET"),
        ("exact_name", "organization", "document_identifier", "date_range"),
        ("document", "organization", "person", "date"),
    ),
    AcquisitionTemplate383(
        "legal.records.v1", "legal", "Identify public or licensed legal records relevant to the case",
        ("LOCAL", "BULK", "GET", "POST"),
        ("party_name", "entity_identifier", "case_identifier", "date_range"),
        ("case", "party", "court", "date", "document"),
    ),
    AcquisitionTemplate383(
        "archive.history.v1", "archive", "Recover historical public snapshots and metadata",
        ("LOCAL", "BULK", "GET"),
        ("url", "domain", "identifier", "date_range"),
        ("web_resource", "snapshot", "document", "timestamp"),
    ),
    AcquisitionTemplate383(
        "reference.identifiers.v1", "reference", "Resolve identifiers and reference metadata across sources",
        ("LOCAL", "BULK", "GET"),
        ("exact_identifier", "exact_name"),
        ("identifier", "entity", "source_reference"),
    ),
    AcquisitionTemplate383(
        "sanctions.screening.v1", "sanctions", "Locate authoritative sanctions/watchlist records for analyst review",
        ("LOCAL", "BULK", "GET"),
        ("exact_identifier", "exact_name", "date_of_birth", "jurisdiction"),
        ("listed_entity", "list", "identifier", "listing_date"),
    ),
)

_TEMPLATE_BY_CLASS = {t.source_class: t for t in TEMPLATES}

# Transparent keyword taxonomy. Inference is advisory only until confirmed.
_MISSION_RULES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (r"\b(company|corporate|firma|unternehmen|gesellschaft|director|officer|shareholder|geschaeftsfuehrer|geschäftsführer)\b", ("corporate", "reference"), "mission mentions corporate/entity structure"),
    (r"\b(procurement|tender|award|contract|vergabe|ausschreibung|auftrag)\b", ("procurement", "public_money"), "mission mentions procurement/public awards"),
    (r"\b(spending|funding|grant|payment|public money|ausgabe|foerder|förder|zahlung)\b", ("public_money",), "mission mentions public-money flows"),
    (r"\b(regulator|filing|aufsicht|regulatorisch|regulatory)\b", ("regulatory",), "mission mentions regulatory records"),
    (r"\b(government|minister|agency|behoerde|behörde|regierung|amt)\b", ("government",), "mission mentions government records"),
    (r"\b(court|lawsuit|legal|insolv|gericht|klage|insolvenz|urteil)\b", ("legal",), "mission mentions legal/court records"),
    (r"\b(history|historical|archive|snapshot|historisch|archiv|frueher|früher)\b", ("archive",), "mission mentions historical/archive material"),
    (r"\b(sanction|watchlist|sanktions|sanktion)\b", ("sanctions",), "mission mentions sanctions/watchlists"),
)


class SourcePlannerRepository383(SourceRegistryRepository382):
    """Build-383 reference persistence layered on the Build-382 source ledger."""

    def ensure_schema(self) -> None:
        super().ensure_schema()
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS acquisition_plan_ledger (
                plan_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                plan_hash TEXT NOT NULL UNIQUE,
                mission TEXT NOT NULL,
                selector_state TEXT NOT NULL,
                explicit_source_classes_json TEXT NOT NULL,
                inferred_source_classes_json TEXT NOT NULL,
                active_source_classes_json TEXT NOT NULL,
                jurisdictions_json TEXT NOT NULL,
                entity_types_json TEXT NOT NULL,
                underlying_plan_id TEXT,
                registry_fingerprint TEXT NOT NULL,
                requires_selector_review INTEGER NOT NULL,
                requires_go INTEGER NOT NULL,
                execution_authority INTEGER NOT NULL,
                scope_expansion_authority INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS acquisition_plan_steps (
                plan_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                step_json TEXT NOT NULL,
                PRIMARY KEY(plan_id, ordinal),
                FOREIGN KEY(plan_id) REFERENCES acquisition_plan_ledger(plan_id)
            );
            CREATE TABLE IF NOT EXISTS acquisition_plan_gaps (
                plan_id TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                gap_json TEXT NOT NULL,
                PRIMARY KEY(plan_id, ordinal),
                FOREIGN KEY(plan_id) REFERENCES acquisition_plan_ledger(plan_id)
            );
            CREATE INDEX IF NOT EXISTS idx_acquisition_plan_case ON acquisition_plan_ledger(case_id, created_at);
            """
        )
        self.db.commit()
        self._schema_integrity_cache = None

    def schema_integrity(self) -> Mapping[str, Any]:
        base = dict(super().schema_integrity())
        tables = {
            r[0] for r in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        required383 = {"acquisition_plan_ledger", "acquisition_plan_steps", "acquisition_plan_gaps"}
        base.update({
            "build383_tables_present": required383.issubset(tables),
            "build383_missing_tables": sorted(required383 - tables),
            "table_count": len(tables),
        })
        return base

    def persist_acquisition_plan(self, plan: AcquisitionPlan383) -> None:
        if plan.execution_authority or plan.scope_expansion_authority or plan.network_requests_created:
            raise ValueError("Build 383 persists network-silent non-executing plans only")
        with self.db:
            self.db.execute(
                """INSERT OR IGNORE INTO acquisition_plan_ledger(
                    plan_id,case_id,plan_hash,mission,selector_state,
                    explicit_source_classes_json,inferred_source_classes_json,active_source_classes_json,
                    jurisdictions_json,entity_types_json,underlying_plan_id,registry_fingerprint,
                    requires_selector_review,requires_go,execution_authority,scope_expansion_authority
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    plan.plan_id, plan.case_id, plan.plan_hash, plan.mission, plan.selector_state,
                    _stable_json(plan.explicit_source_classes), _stable_json(plan.inferred_source_classes),
                    _stable_json(plan.active_source_classes), _stable_json(plan.jurisdictions),
                    _stable_json(plan.entity_types), plan.underlying_plan_id, plan.registry_fingerprint,
                    int(plan.requires_selector_review), 1, 0, 0,
                ),
            )
            for idx, step in enumerate(plan.steps):
                self.db.execute(
                    "INSERT OR IGNORE INTO acquisition_plan_steps(plan_id,ordinal,step_json) VALUES(?,?,?)",
                    (plan.plan_id, idx, _stable_json(asdict(step))),
                )
            for idx, gap in enumerate(plan.gaps):
                self.db.execute(
                    "INSERT OR IGNORE INTO acquisition_plan_gaps(plan_id,ordinal,gap_json) VALUES(?,?,?)",
                    (plan.plan_id, idx, _stable_json(asdict(gap))),
                )

    def load_acquisition_plan(self, plan_id: str) -> Mapping[str, Any] | None:
        row = self.db.execute("SELECT * FROM acquisition_plan_ledger WHERE plan_id=?", (plan_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["steps"] = [json.loads(r[0]) for r in self.db.execute(
            "SELECT step_json FROM acquisition_plan_steps WHERE plan_id=? ORDER BY ordinal", (plan_id,)
        )]
        result["gaps"] = [json.loads(r[0]) for r in self.db.execute(
            "SELECT gap_json FROM acquisition_plan_gaps WHERE plan_id=? ORDER BY ordinal", (plan_id,)
        )]
        return result


class SourcePlanner383:
    def __init__(self, repository: SourcePlannerRepository383, providers: Mapping[str, Any]) -> None:
        self.repository = repository
        self.providers = dict(providers)

    @staticmethod
    def infer_requirements(mission: str) -> tuple[SourceRequirement383, ...]:
        text = mission.strip().casefold()
        if not text:
            raise ValueError("mission is required")
        found: dict[str, SourceRequirement383] = {}
        for pattern, classes, reason in _MISSION_RULES:
            if re.search(pattern, text, flags=re.IGNORECASE):
                for source_class in classes:
                    existing = found.get(source_class)
                    candidate = SourceRequirement383(source_class, "mission_inference", reason, 60)
                    if existing is None or candidate.weight > existing.weight:
                        found[source_class] = candidate
        return tuple(found[k] for k in sorted(found))

    @staticmethod
    def _template_for(source_class: str) -> AcquisitionTemplate383:
        return _TEMPLATE_BY_CLASS.get(source_class, AcquisitionTemplate383(
            f"generic.{source_class}.v1", source_class,
            f"Collect governed evidence for source class {source_class}",
            ("LOCAL", "BULK", "GET", "POST"),
            ("exact_identifier", "exact_name", "date_range"),
            ("entity", "document", "identifier", "timestamp"),
        ))

    @staticmethod
    def _rank_entry(
        entry: SourceRegistryEntry,
        *,
        source_class: str,
        jurisdictions: tuple[str, ...],
        entity_types: tuple[str, ...],
        template: AcquisitionTemplate383,
    ) -> tuple[int, tuple[str, ...]]:
        score = 0
        reasons: list[str] = []
        entry_classes = {x.casefold() for x in entry.source_classes}
        if source_class in entry_classes:
            score += 50
            reasons.append("source_class_exact")
        entry_j = {x.casefold() for x in entry.jurisdictions}
        if jurisdictions:
            if set(jurisdictions) & entry_j:
                score += 25
                reasons.append("jurisdiction_exact")
            elif "global" in entry_j:
                score += 15
                reasons.append("jurisdiction_global")
        elif "global" in entry_j:
            score += 4
            reasons.append("global_scope")
        entry_e = {x.casefold() for x in entry.entity_types}
        overlap = set(entity_types) & entry_e
        if overlap:
            score += min(15, 5 * len(overlap))
            reasons.append("entity_type_overlap")
        access_overlap = set(template.preferred_access_methods) & set(entry.access_methods)
        if access_overlap:
            score += min(10, 2 * len(access_overlap))
            reasons.append("preferred_access_path")
        if entry.external_validation_state == "externally_validated":
            score += 8
            reasons.append("externally_validated")
        elif entry.external_validation_state == "validated_local":
            score += 4
            reasons.append("validated_local")
        elif entry.external_validation_state == "plan_only":
            score -= 3
            reasons.append("validation_plan_only")
        if entry.execution_mode == SourceExecutionMode.PLAN_ONLY:
            reasons.append("execution_plan_only")
        return max(score, 0), tuple(reasons)

    def plan(
        self,
        *,
        case_id: str,
        mission: str,
        jurisdictions: Sequence[str] = (),
        entity_types: Sequence[str] = (),
        source_classes: Sequence[str] = (),
        confirmation: str | None = None,
        per_class_limit: int = 4,
    ) -> AcquisitionPlan383:
        if per_class_limit < 1 or per_class_limit > 10:
            raise ValueError("per_class_limit must be between 1 and 10")
        cp382 = InvestigationControlPlane382(self.repository, self.providers)
        snapshot = cp382.snapshot(case_id)
        if not snapshot["research_ready"]:
            raise RuntimeError("source planning held by control-plane/persistence preflight")

        mission = mission.strip()
        if not mission:
            raise ValueError("mission is required")
        explicit = _norm(source_classes)
        inferred_requirements = self.infer_requirements(mission)
        inferred = tuple(r.source_class for r in inferred_requirements)
        confirmed = confirmation == CONFIRM_INFERRED_SELECTORS
        if confirmation is not None and not confirmed:
            raise ValueError("inferred selector confirmation must be exact CONFIRM SELECTORS")

        if explicit:
            active = explicit
            selector_state = "explicit"
            requires_selector_review = False
        elif inferred and confirmed:
            active = inferred
            selector_state = "confirmed_inferred"
            requires_selector_review = False
        elif inferred:
            active = inferred  # used to produce an advisory plan only; no case scope mutation below
            selector_state = "proposed_inferred"
            requires_selector_review = True
        else:
            active = ()
            selector_state = "no_selector_match"
            requires_selector_review = True

        jurs = _norm(jurisdictions)
        entities = _norm(entity_types)
        registry = self.repository.load_registry()
        entries = registry.all()
        steps: list[PlannedSourceStep383] = []
        gaps: list[PlannerGap383] = []

        if not active:
            gaps.append(PlannerGap383(
                "selector_gap", "source_classes", "high",
                "mission taxonomy produced no source-class selector; analyst must choose source classes",
            ))

        for source_class in active:
            template = self._template_for(source_class)
            matching = [e for e in entries if source_class in {c.casefold() for c in e.source_classes}]
            if not matching:
                gaps.append(PlannerGap383(
                    "registry_gap", source_class, "high",
                    "no catalogued source exists for this required source class",
                ))
                continue

            ranked: list[tuple[int, SourceRegistryEntry, tuple[str, ...]]] = []
            for entry in matching:
                score, reasons = self._rank_entry(
                    entry, source_class=source_class, jurisdictions=jurs, entity_types=entities, template=template
                )
                ranked.append((score, entry, reasons))
            ranked.sort(key=lambda x: (-x[0], x[1].source_id))

            if jurs and not any((set(jurs) & {x.casefold() for x in e.jurisdictions}) or "global" in {x.casefold() for x in e.jurisdictions} for e in matching):
                gaps.append(PlannerGap383(
                    "jurisdiction_gap", source_class, "high",
                    f"catalogued sources for {source_class} do not cover requested jurisdictions {jurs}",
                ))
            if entities and not any(set(entities) & {x.casefold() for x in e.entity_types} for e in matching):
                gaps.append(PlannerGap383(
                    "entity_type_gap", source_class, "medium",
                    f"catalogued sources for {source_class} do not advertise requested entity types {entities}",
                ))
            if all(e.external_validation_state in {"not_run", "plan_only", "failed"} for e in matching):
                gaps.append(PlannerGap383(
                    "validation_gap", source_class, "medium",
                    "no catalogued source for this class has external/local validation evidence",
                ))
            if not any(set(template.preferred_access_methods) & set(e.access_methods) for e in matching):
                gaps.append(PlannerGap383(
                    "access_path_gap", source_class, "medium",
                    "no catalogued source exposes a preferred acquisition method for this template",
                ))

            for score, entry, reasons in ranked[:per_class_limit]:
                steps.append(PlannedSourceStep383(
                    source_id=entry.source_id,
                    source_name=entry.name,
                    source_class=source_class,
                    template_id=template.template_id,
                    priority=score,
                    reasons=reasons,
                    access_methods=entry.access_methods,
                    execution_mode=entry.execution_mode.value,
                    external_validation_state=entry.external_validation_state,
                ))

        steps.sort(key=lambda x: (-x.priority, x.source_class, x.source_id))

        underlying: PersistentResearchPlan382 | None = None
        # Crucial governance boundary: inferred selectors do not mutate case scope until confirmed.
        if active and (explicit or confirmed):
            underlying = cp382.plan_research(
                case_id=case_id,
                mission=mission,
                jurisdictions=jurs,
                source_classes=active,
                entity_types=entities,
                limit=min(25, max(1, len({s.source_id for s in steps}) or 1)),
            )
        elif active:
            gaps.append(PlannerGap383(
                "selector_review_required", "inferred_source_classes", "high",
                "inferred source classes are advisory; exact CONFIRM SELECTORS is required before case scope changes",
            ))

        registry_fp = self.repository.registry_fingerprint()
        payload = {
            "case_id": case_id,
            "mission": mission,
            "explicit": explicit,
            "inferred": inferred,
            "active": active,
            "selector_state": selector_state,
            "jurisdictions": jurs,
            "entity_types": entities,
            "steps": [asdict(s) for s in steps],
            "gaps": [asdict(g) for g in gaps],
            "underlying_plan_id": underlying.plan_id if underlying else None,
            "registry_fingerprint": registry_fp,
            "requires_selector_review": requires_selector_review,
            "policy_id": POLICY_ID,
        }
        plan_hash = _stable_hash(payload)
        plan = AcquisitionPlan383(
            plan_id=f"ap383-{plan_hash[:24]}",
            case_id=case_id,
            mission=mission,
            explicit_source_classes=explicit,
            inferred_source_classes=inferred,
            active_source_classes=active,
            selector_state=selector_state,
            jurisdictions=jurs,
            entity_types=entities,
            steps=tuple(steps),
            gaps=tuple(gaps),
            underlying_plan_id=underlying.plan_id if underlying else None,
            registry_fingerprint=registry_fp,
            requires_selector_review=requires_selector_review,
        )
        self.repository.persist_acquisition_plan(plan)
        return plan


def create_reference_repository383(connection: sqlite3.Connection | None = None) -> SourcePlannerRepository383:
    connection = connection or sqlite3.connect(":memory:")
    repo = SourcePlannerRepository383(connection)
    repo.seed(default_registry().all())
    return repo
