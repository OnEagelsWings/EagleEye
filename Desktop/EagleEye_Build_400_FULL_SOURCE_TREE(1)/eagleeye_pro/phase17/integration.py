from __future__ import annotations

from dataclasses import asdict
import threading
import time
from typing import Any, Mapping, Sequence

from .investigation_control381 import InvestigationControlPlane381, default_registry
from .source_registry_persistence382 import InvestigationControlPlane382
from .source_planner383 import SourcePlanner383
from .jurisdiction_intelligence384 import JurisdictionIntelligence384, JurisdictionRepository384


class _EvidenceStatus:
    def __init__(self, db: Any) -> None:
        self.db = db
    def status_for_case(self, case_id: str) -> Mapping[str, Any]:
        case = self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,))
        if not case:
            return {"state": "hold", "case_mismatch": True, "reason": "case_not_found"}
        count = self.db.one("SELECT COUNT(*) AS n FROM evidence_items WHERE case_id=?", (case_id,)) or {"n": 0}
        return {"state": "ready", "evidence_items": int(count.get("n") or 0), "read_only_status": True}


class _OperationsStatus:
    """Short-lived planning preflight cache.

    Phase-17 plans have no execution authority. A sub-second cache avoids repeatedly
    re-verifying the complete audit chain while a burst of advisory plans is built.
    Any later execution/GO remains governed by the existing live crawler/OPSEC gates.
    """
    def __init__(self, operations: Any, ttl_seconds: float = 0.5) -> None:
        self.operations = operations
        self.ttl_seconds = max(0.05, float(ttl_seconds))
        self._cache: dict[str, tuple[float, Mapping[str, Any]]] = {}
    def status_for_case(self, case_id: str) -> Mapping[str, Any]:
        now = time.monotonic(); cached = self._cache.get(case_id)
        if cached and now - cached[0] <= self.ttl_seconds:
            return cached[1]
        value = self.operations.readiness(case_id=case_id)
        hold = not bool(value.get("local_operational_ready")) or bool(self.operations.circuit_breaker_required(case_id=case_id))
        result = {"state": "hold" if hold else "ready", "circuit_open": hold, "detail": value, "planning_preflight_cache_seconds": self.ttl_seconds}
        self._cache[case_id] = (now, result)
        return result


class _CrawlerStatus:
    def __init__(self, crawler: Any, ttl_seconds: float = 0.5) -> None:
        self.crawler = crawler; self.ttl_seconds=max(0.05,float(ttl_seconds)); self._cache: dict[str, tuple[float, Mapping[str, Any]]] = {}
    def status_for_case(self, case_id: str) -> Mapping[str, Any]:
        now=time.monotonic(); cached=self._cache.get(case_id)
        if cached and now-cached[0] <= self.ttl_seconds: return cached[1]
        value = self.crawler.readiness(case_id=case_id)
        ready = bool(value.get("ready_for_more_bounded_work"))
        result={"state": "ready" if ready else "hold", "circuit_open": not ready, "detail": value, "planning_preflight_cache_seconds":self.ttl_seconds}
        self._cache[case_id]=(now,result); return result


class _OpsecStatus:
    def __init__(self, opsec: Any, operations_status: _OperationsStatus) -> None:
        self.opsec = opsec; self.operations_status = operations_status
    def status_for_case(self, case_id: str) -> Mapping[str, Any]:
        status = dict(self.opsec.status())
        operations = self.operations_status.status_for_case(case_id)
        circuit = bool(operations.get("circuit_open"))
        unsafe_mutation = any(bool(status.get(k)) for k in ("firewall_mutation", "os_mutation", "tor_configuration_mutation", "credential_mutation", "acl_mutation", "system_mutations"))
        return {"state": "hold" if circuit or unsafe_mutation else "ready", "circuit_open": circuit, "unsafe_mutation": unsafe_mutation}


class _SearchStatus:
    def __init__(self, build380: Any) -> None:
        self.build380 = build380
    def status_for_case(self, case_id: str) -> Mapping[str, Any]:
        return {"state": "ready", "case_id": case_id, "execution_authority": False}


class _GraphStatus(_SearchStatus):
    pass


class Phase17IntegratedRuntime384:
    """Integrated Phase-17 planning runtime on the canonical EagleEye database.

    Build 381-384 remain planning/governance layers. They never execute external
    requests and never grant crawler/provider/network authority. Repository writes
    are serialized through a runtime lock while the underlying SQLite connection
    remains owned by the canonical EagleEye Database lifecycle.
    """
    BUILD = "384.0"
    POLICY = "phase17.integrated-control-data-planning.v384"

    def __init__(self, db: Any, audit: Any, *, build380: Any, operations365: Any,
                 crawler369: Any, opsec380: Any, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build380 = build380
        self.actor = actor
        self._lock = threading.RLock()
        self.repository = JurisdictionRepository384(db.conn)
        self.repository.seed(default_registry().all(), actor="build384-integration", reason="phase17_integrated_seed")
        operations_status = _OperationsStatus(operations365)
        self.providers = {
            "evidence": _EvidenceStatus(db),
            "operations": operations_status,
            "crawler": _CrawlerStatus(crawler369),
            "opsec": _OpsecStatus(opsec380, operations_status),
            "search": _SearchStatus(build380),
            "graph": _GraphStatus(build380),
        }
        self.jurisdiction = JurisdictionIntelligence384(self.repository, self.providers)
        self.jurisdiction.seed_default_profiles()
        self.planner = SourcePlanner383(self.repository, self.providers)

    def snapshot381(self, case_id: str) -> Mapping[str, Any]:
        with self._lock:
            cp = InvestigationControlPlane381(self.repository.load_registry(), self.providers)
            snap = cp.snapshot(case_id)
            return asdict(snap) | {"snapshot_hash": snap.snapshot_hash}

    def plan381(self, *, case_id: str, mission: str, jurisdictions: Sequence[str] = (),
                source_classes: Sequence[str] = (), entity_types: Sequence[str] = (), limit: int = 12) -> Any:
        with self._lock:
            cp = InvestigationControlPlane381(self.repository.load_registry(), self.providers)
            plan = cp.plan_research(case_id=case_id, mission=mission, jurisdictions=jurisdictions,
                                    source_classes=source_classes, entity_types=entity_types, limit=limit)
            self.audit.log("PHASE17_381_RESEARCH_PLAN", "research_plan", plan.plan_hash, case_id=case_id,
                           details={"mission": mission, "source_count": len(plan.source_candidates), "requires_go": True, "execution_authority": False})
            return plan

    def coverage382(self, case_id: str) -> Any:
        with self._lock:
            return InvestigationControlPlane382(self.repository, self.providers).coverage_report(case_id)

    def set_source_scope382(self, *, case_id: str, source_id: str, state: str,
                            reviewer: str | None = None, note: str | None = None,
                            confirmation: str | None = None) -> None:
        with self._lock:
            self.repository.set_case_scope(case_id=case_id, source_id=source_id, state=state,
                                           reviewer=reviewer, note=note, confirmation=confirmation)
            self.audit.log("PHASE17_382_SOURCE_SCOPE", "source", source_id, case_id=case_id,
                           details={"state": state, "reviewer": reviewer or "", "execution_authority": False})

    def plan383(self, **kwargs: Any) -> Any:
        with self._lock:
            plan = self.planner.plan(**kwargs)
            self.audit.log("PHASE17_383_ACQUISITION_PLAN", "acquisition_plan", plan.plan_id,
                           case_id=plan.case_id, details={"plan_hash": plan.plan_hash, "selector_state": plan.selector_state,
                                                         "requires_go": True, "execution_authority": False})
            return plan

    def plan384(self, **kwargs: Any) -> Any:
        with self._lock:
            plan = self.jurisdiction.plan_waves(**kwargs)
            self.audit.log("PHASE17_384_RESEARCH_WAVES", "research_wave_plan", plan.wave_plan_id,
                           case_id=plan.case_id, details={"plan_hash": plan.plan_hash, "waves": len(plan.waves),
                                                         "requires_go": True, "execution_authority": False,
                                                         "network_requests_created": 0})
            return plan

    def status(self, case_id: str = "") -> Mapping[str, Any]:
        schema = self.repository.schema_integrity()
        registry = self.repository.load_registry().coverage()
        out: dict[str, Any] = {
            "build": self.BUILD,
            "policy": self.POLICY,
            "integrated_with_build380": True,
            "canonical_database": True,
            "registry": registry,
            "schema": schema,
            "network_execution_added": False,
            "automatic_scope_expansion": False,
            "automatic_identity_merge": False,
            "host_security_mutation": False,
        }
        if case_id:
            out["control_plane"] = self.snapshot381(case_id)
        return out
