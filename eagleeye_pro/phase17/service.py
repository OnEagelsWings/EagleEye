"""Phase-17 service facade for Builds 381-384."""
from __future__ import annotations
import sqlite3
from typing import Any, Mapping

from .investigation_control381 import default_registry
from .jurisdiction_intelligence384 import JurisdictionIntelligence384, JurisdictionRepository384
from .source_planner383 import SourcePlanner383
from .integration import Phase17IntegratedRuntime384


def create_phase17_repository(connection: sqlite3.Connection | None = None) -> JurisdictionRepository384:
    db = connection or sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    repo = JurisdictionRepository384(db)
    repo.seed(default_registry().all())
    JurisdictionIntelligence384(repo, {}).seed_default_profiles()
    return repo


def create_phase17_services(providers: Mapping[str, Any], connection: sqlite3.Connection | None = None) -> Mapping[str, Any]:
    repo = create_phase17_repository(connection)
    return {"repository": repo, "source_planner": SourcePlanner383(repo, providers), "jurisdiction_intelligence": JurisdictionIntelligence384(repo, providers)}

__all__ = ["Phase17IntegratedRuntime384", "create_phase17_repository", "create_phase17_services"]
