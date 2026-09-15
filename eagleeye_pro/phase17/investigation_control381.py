"""Build 381: Phase-17 Investigation Control Plane and Global Source Registry foundation.

This module is intentionally network-silent.  It provides a case-scoped, read-only
control plane over existing subsystem status providers and a governed registry of
public, licensed, or explicitly authorized sources.  It does *not* execute a source,
enqueue crawler work, expand investigation scope, merge identities, or mutate
host/network security controls.

The first Phase-17 build therefore improves orchestration and data-acquisition
planning without weakening the Build-380 professional-pilot boundary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable, Mapping, Protocol, Sequence
from urllib.parse import urlsplit


BUILD = "381.0"
POLICY_ID = "phase17.investigation-control-source-registry.v381"
BASE_BUILD_FINGERPRINT = "0b367f97f28d33687ddbff6fb05b8652962a5f23aff1039145845c2cae32970d"


class RegistryValidationError(ValueError):
    """Raised when a source violates Build-381 registry governance."""


class AccessBasis(str, Enum):
    PUBLIC = "public"
    LICENSED = "licensed"
    AUTHORIZED = "authorized"


class SourceExecutionMode(str, Enum):
    PLAN_ONLY = "plan_only"
    REVIEW_REQUIRED = "review_required"
    LIVE_ELIGIBLE = "live_eligible"


class CapabilityState(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"
    HOLD = "hold"
    NOT_VALIDATED = "not_validated"
    DISABLED = "disabled"


_ALLOWED_METHODS = frozenset({"GET", "HEAD", "POST", "BULK", "SQL", "LOCAL"})
_SENSITIVE_URL_RE = re.compile(r"(?i)(?:password|passwd|token|api[_-]?key|secret)=")


def _stable_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _tuple_text(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


@dataclass(frozen=True, slots=True)
class SourceRegistryEntry:
    source_id: str
    name: str
    access_basis: AccessBasis
    execution_mode: SourceExecutionMode = SourceExecutionMode.PLAN_ONLY
    jurisdictions: tuple[str, ...] = ()
    source_classes: tuple[str, ...] = ()
    entity_types: tuple[str, ...] = ()
    access_methods: tuple[str, ...] = ("GET",)
    endpoint: str | None = None
    local_dataset: bool = False
    license_reference: str | None = None
    terms_reference: str | None = None
    freshness_seconds: int | None = None
    historical_depth: str | None = None
    rate_limit_hint: str | None = None
    provenance_required: bool = True
    human_source_review_required: bool = True
    external_validation_state: str = "not_run"
    notes: str | None = None

    def normalized(self) -> "SourceRegistryEntry":
        return SourceRegistryEntry(
            source_id=self.source_id.strip(),
            name=self.name.strip(),
            access_basis=AccessBasis(self.access_basis),
            execution_mode=SourceExecutionMode(self.execution_mode),
            jurisdictions=_tuple_text(self.jurisdictions),
            source_classes=_tuple_text(self.source_classes),
            entity_types=_tuple_text(self.entity_types),
            access_methods=tuple(sorted({m.upper().strip() for m in self.access_methods if m.strip()})),
            endpoint=self.endpoint.strip() if self.endpoint else None,
            local_dataset=bool(self.local_dataset),
            license_reference=self.license_reference.strip() if self.license_reference else None,
            terms_reference=self.terms_reference.strip() if self.terms_reference else None,
            freshness_seconds=self.freshness_seconds,
            historical_depth=self.historical_depth.strip() if self.historical_depth else None,
            rate_limit_hint=self.rate_limit_hint.strip() if self.rate_limit_hint else None,
            provenance_required=bool(self.provenance_required),
            human_source_review_required=bool(self.human_source_review_required),
            external_validation_state=self.external_validation_state.strip(),
            notes=self.notes.strip() if self.notes else None,
        )

    @property
    def registry_hash(self) -> str:
        return _stable_hash(asdict(self.normalized()))


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    source_id: str
    name: str
    score: int
    reasons: tuple[str, ...]
    execution_mode: SourceExecutionMode
    requires_human_review: bool
    external_validation_state: str


@dataclass(frozen=True, slots=True)
class InvestigationPlan:
    case_id: str
    mission: str
    source_candidates: tuple[SourceCandidate, ...]
    requires_go: bool = True
    execution_authority: bool = False
    scope_expansion_authority: bool = False
    network_requests_created: int = 0
    policy_id: str = POLICY_ID

    @property
    def plan_hash(self) -> str:
        payload = {
            "case_id": self.case_id,
            "mission": self.mission,
            "source_candidates": [asdict(c) for c in self.source_candidates],
            "requires_go": self.requires_go,
            "execution_authority": self.execution_authority,
            "scope_expansion_authority": self.scope_expansion_authority,
            "network_requests_created": self.network_requests_created,
            "policy_id": self.policy_id,
        }
        return _stable_hash(payload)


@dataclass(frozen=True, slots=True)
class ControlPlaneSnapshot:
    case_id: str
    capability_states: Mapping[str, str]
    source_registry: Mapping[str, Any]
    operations_hold: bool
    opsec_hold: bool
    research_ready: bool
    reasons: tuple[str, ...]
    network_requests_created: int = 0
    mutations_performed: int = 0
    policy_id: str = POLICY_ID

    @property
    def snapshot_hash(self) -> str:
        return _stable_hash({
            "case_id": self.case_id,
            "capability_states": dict(sorted(self.capability_states.items())),
            "source_registry": self.source_registry,
            "operations_hold": self.operations_hold,
            "opsec_hold": self.opsec_hold,
            "research_ready": self.research_ready,
            "reasons": self.reasons,
            "network_requests_created": self.network_requests_created,
            "mutations_performed": self.mutations_performed,
            "policy_id": self.policy_id,
        })


class CapabilityStatusProvider(Protocol):
    def status_for_case(self, case_id: str) -> Mapping[str, Any]: ...


class GlobalSourceRegistry381:
    """Governed, network-silent registry used by Build 381 planning.

    A registry entry is metadata only.  Registering a source never validates it and
    never grants execution authority.  Live eligibility is a declared state that must
    still be enforced by the existing provider/crawler gates.
    """

    def __init__(self, entries: Iterable[SourceRegistryEntry] = ()) -> None:
        self._entries: dict[str, SourceRegistryEntry] = {}
        for entry in entries:
            self.register(entry)

    @staticmethod
    def _validate(entry: SourceRegistryEntry) -> SourceRegistryEntry:
        e = entry.normalized()
        if not e.source_id or len(e.source_id) > 128:
            raise RegistryValidationError("source_id must be non-empty and <=128 characters")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._:-]*", e.source_id):
            raise RegistryValidationError("source_id must be lowercase and machine-safe")
        if not e.name:
            raise RegistryValidationError("source name is required")
        if not e.provenance_required:
            raise RegistryValidationError("Build 381 requires provenance for every source")
        if not e.human_source_review_required:
            raise RegistryValidationError("Build 381 does not permit bypassing human source review")
        if not e.access_methods:
            raise RegistryValidationError("at least one access method is required")
        unsupported = set(e.access_methods) - _ALLOWED_METHODS
        if unsupported:
            raise RegistryValidationError(f"unsupported access methods: {sorted(unsupported)}")
        if e.local_dataset and e.endpoint:
            raise RegistryValidationError("local datasets must not embed an external endpoint")
        if not e.local_dataset and not e.endpoint:
            # Cataloguing a source before its endpoint is known is allowed only as plan-only.
            if e.execution_mode is not SourceExecutionMode.PLAN_ONLY:
                raise RegistryValidationError("non-local executable sources require an endpoint")
        if e.endpoint:
            if _SENSITIVE_URL_RE.search(e.endpoint) or "@" in urlsplit(e.endpoint).netloc:
                raise RegistryValidationError("credentials/secrets must never be embedded in source endpoints")
            parsed = urlsplit(e.endpoint)
            if parsed.scheme not in {"https", "http"}:
                raise RegistryValidationError("external source endpoint must use http/https metadata")
            if parsed.scheme == "http" and e.execution_mode is not SourceExecutionMode.PLAN_ONLY:
                raise RegistryValidationError("plain-http sources remain plan_only in Build 381")
        if e.access_basis is AccessBasis.LICENSED and not e.license_reference:
            raise RegistryValidationError("licensed sources require a license reference")
        if e.access_basis is AccessBasis.AUTHORIZED and not (e.terms_reference or e.license_reference):
            raise RegistryValidationError("authorized sources require an authorization/terms reference")
        if e.freshness_seconds is not None and e.freshness_seconds <= 0:
            raise RegistryValidationError("freshness_seconds must be positive")
        if e.external_validation_state not in {"not_run", "validated_local", "externally_validated", "failed", "plan_only"}:
            raise RegistryValidationError("unsupported external validation state")
        return e

    def register(self, entry: SourceRegistryEntry) -> str:
        e = self._validate(entry)
        existing = self._entries.get(e.source_id)
        if existing and existing.registry_hash != e.registry_hash:
            raise RegistryValidationError(f"source_id collision for {e.source_id}")
        self._entries[e.source_id] = e
        return e.registry_hash

    def get(self, source_id: str) -> SourceRegistryEntry | None:
        return self._entries.get(source_id)

    def all(self) -> tuple[SourceRegistryEntry, ...]:
        return tuple(self._entries[k] for k in sorted(self._entries))

    def candidate_sources(
        self,
        *,
        jurisdictions: Sequence[str] = (),
        source_classes: Sequence[str] = (),
        entity_types: Sequence[str] = (),
        limit: int = 25,
    ) -> tuple[SourceCandidate, ...]:
        wanted_j = {v.casefold() for v in jurisdictions}
        wanted_c = {v.casefold() for v in source_classes}
        wanted_e = {v.casefold() for v in entity_types}
        scored: list[SourceCandidate] = []
        for entry in self.all():
            ej = {v.casefold() for v in entry.jurisdictions}
            ec = {v.casefold() for v in entry.source_classes}
            ee = {v.casefold() for v in entry.entity_types}
            reasons: list[str] = []
            score = 0
            if wanted_j and (wanted_j & ej or "global" in ej):
                score += 4
                reasons.append("jurisdiction")
            if wanted_c and wanted_c & ec:
                score += 3
                reasons.append("source_class")
            if wanted_e and wanted_e & ee:
                score += 2
                reasons.append("entity_type")
            if not (wanted_j or wanted_c or wanted_e):
                score = 1
                reasons.append("registry_default")
            if score:
                scored.append(SourceCandidate(
                    source_id=entry.source_id,
                    name=entry.name,
                    score=score,
                    reasons=tuple(reasons),
                    execution_mode=entry.execution_mode,
                    requires_human_review=True,
                    external_validation_state=entry.external_validation_state,
                ))
        scored.sort(key=lambda x: (-x.score, x.source_id))
        return tuple(scored[: max(0, limit)])

    def coverage(self) -> Mapping[str, Any]:
        entries = self.all()
        by_access = {k.value: 0 for k in AccessBasis}
        by_mode = {k.value: 0 for k in SourceExecutionMode}
        external_validated = 0
        for e in entries:
            by_access[e.access_basis.value] += 1
            by_mode[e.execution_mode.value] += 1
            external_validated += int(e.external_validation_state == "externally_validated")
        return {
            "build": BUILD,
            "source_count": len(entries),
            "by_access_basis": by_access,
            "by_execution_mode": by_mode,
            "externally_validated": external_validated,
            "network_requests_created": 0,
            "registry_fingerprint": _stable_hash({e.source_id: e.registry_hash for e in entries}),
        }


class InvestigationControlPlane381:
    """Case-scoped read-only aggregation and governed research planning."""

    def __init__(
        self,
        registry: GlobalSourceRegistry381,
        providers: Mapping[str, CapabilityStatusProvider | Mapping[str, Any]],
    ) -> None:
        self.registry = registry
        self.providers = dict(providers)

    def _provider_status(self, name: str, provider: CapabilityStatusProvider | Mapping[str, Any], case_id: str) -> Mapping[str, Any]:
        if hasattr(provider, "status_for_case"):
            value = provider.status_for_case(case_id)  # type: ignore[attr-defined]
        else:
            value = provider
        if not isinstance(value, Mapping):
            raise TypeError(f"provider {name} returned non-mapping status")
        return value

    def snapshot(self, case_id: str) -> ControlPlaneSnapshot:
        if not case_id or len(case_id) > 160:
            raise ValueError("valid case_id required")
        states: dict[str, str] = {}
        reasons: list[str] = []
        operations_hold = False
        opsec_hold = False
        for name in sorted(self.providers):
            raw = self._provider_status(name, self.providers[name], case_id)
            state = str(raw.get("state", CapabilityState.NOT_VALIDATED.value))
            if state not in {v.value for v in CapabilityState}:
                state = CapabilityState.NOT_VALIDATED.value
            states[name] = state
            if bool(raw.get("case_mismatch")):
                states[name] = CapabilityState.HOLD.value
                reasons.append(f"{name}:case_mismatch")
            if name == "operations" and (state == CapabilityState.HOLD.value or bool(raw.get("circuit_open"))):
                operations_hold = True
                reasons.append("operations_hold")
            if name == "opsec" and (state == CapabilityState.HOLD.value or bool(raw.get("circuit_open"))):
                opsec_hold = True
                reasons.append("opsec_hold")
        critical = {"evidence", "crawler", "operations", "opsec"}
        missing_critical = sorted(critical - set(states))
        if missing_critical:
            reasons.extend(f"missing:{name}" for name in missing_critical)
        blocked = any(states.get(name) in {CapabilityState.HOLD.value, CapabilityState.DISABLED.value} for name in critical if name in states)
        research_ready = not operations_hold and not opsec_hold and not blocked and not missing_critical
        return ControlPlaneSnapshot(
            case_id=case_id,
            capability_states=states,
            source_registry=self.registry.coverage(),
            operations_hold=operations_hold,
            opsec_hold=opsec_hold,
            research_ready=research_ready,
            reasons=tuple(sorted(set(reasons))),
        )

    def plan_research(
        self,
        *,
        case_id: str,
        mission: str,
        jurisdictions: Sequence[str] = (),
        source_classes: Sequence[str] = (),
        entity_types: Sequence[str] = (),
        limit: int = 12,
    ) -> InvestigationPlan:
        snapshot = self.snapshot(case_id)
        if not snapshot.research_ready:
            raise RuntimeError("research planning held by control-plane preflight")
        mission = mission.strip()
        if not mission:
            raise ValueError("mission is required")
        candidates = self.registry.candidate_sources(
            jurisdictions=jurisdictions,
            source_classes=source_classes,
            entity_types=entity_types,
            limit=min(max(limit, 1), 25),
        )
        return InvestigationPlan(
            case_id=case_id,
            mission=mission,
            source_candidates=candidates,
            requires_go=True,
            execution_authority=False,
            scope_expansion_authority=False,
            network_requests_created=0,
        )


DEFAULT_PHASE17_SOURCE_SEEDS: tuple[SourceRegistryEntry, ...] = (
    SourceRegistryEntry(
        source_id="gleif.lei",
        name="GLEIF LEI public data",
        access_basis=AccessBasis.PUBLIC,
        execution_mode=SourceExecutionMode.REVIEW_REQUIRED,
        jurisdictions=("global",),
        source_classes=("corporate", "reference"),
        entity_types=("company", "legal_entity"),
        access_methods=("GET", "BULK"),
        endpoint="https://api.gleif.org/",
        terms_reference="GLEIF public data terms",
        external_validation_state="not_run",
    ),
    SourceRegistryEntry(
        source_id="sec.edgar",
        name="SEC EDGAR public filings",
        access_basis=AccessBasis.PUBLIC,
        execution_mode=SourceExecutionMode.REVIEW_REQUIRED,
        jurisdictions=("US",),
        source_classes=("corporate", "regulatory"),
        entity_types=("company", "filing"),
        access_methods=("GET",),
        endpoint="https://data.sec.gov/",
        terms_reference="SEC developer policy",
        external_validation_state="not_run",
    ),
    SourceRegistryEntry(
        source_id="usaspending.awards",
        name="USAspending public awards",
        access_basis=AccessBasis.PUBLIC,
        execution_mode=SourceExecutionMode.REVIEW_REQUIRED,
        jurisdictions=("US",),
        source_classes=("procurement", "public_money"),
        entity_types=("company", "organization", "award"),
        access_methods=("GET", "POST"),
        endpoint="https://api.usaspending.gov/",
        terms_reference="USAspending API documentation",
        external_validation_state="not_run",
    ),
    SourceRegistryEntry(
        source_id="eu.ted",
        name="TED public procurement notices",
        access_basis=AccessBasis.PUBLIC,
        execution_mode=SourceExecutionMode.PLAN_ONLY,
        jurisdictions=("EU",),
        source_classes=("procurement", "public_money"),
        entity_types=("company", "organization", "notice"),
        access_methods=("POST",),
        endpoint="https://api.ted.europa.eu/",
        terms_reference="TED Search API documentation",
        external_validation_state="plan_only",
    ),
    SourceRegistryEntry(
        source_id="us.federal_register",
        name="Federal Register public documents",
        access_basis=AccessBasis.PUBLIC,
        execution_mode=SourceExecutionMode.REVIEW_REQUIRED,
        jurisdictions=("US",),
        source_classes=("government", "legal", "regulatory"),
        entity_types=("document", "organization", "person"),
        access_methods=("GET",),
        endpoint="https://www.federalregister.gov/api/v1/",
        terms_reference="Federal Register API documentation",
        external_validation_state="not_run",
    ),
    SourceRegistryEntry(
        source_id="internet_archive.metadata",
        name="Internet Archive metadata",
        access_basis=AccessBasis.PUBLIC,
        execution_mode=SourceExecutionMode.REVIEW_REQUIRED,
        jurisdictions=("global",),
        source_classes=("archive", "reference"),
        entity_types=("document", "web_resource"),
        access_methods=("GET",),
        endpoint="https://archive.org/",
        terms_reference="Internet Archive terms",
        external_validation_state="not_run",
    ),
)


def default_registry() -> GlobalSourceRegistry381:
    return GlobalSourceRegistry381(DEFAULT_PHASE17_SOURCE_SEEDS)
