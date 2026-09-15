import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from eagleeye.phase17.source_planner383 import (  # noqa: E402
    CONFIRM_INFERRED_SELECTORS,
    SourcePlanner383,
    SourcePlannerRepository383,
)
from eagleeye.phase17.investigation_control381 import default_registry  # noqa: E402

READY = {
    "evidence": {"state": "ready"}, "crawler": {"state": "ready"},
    "operations": {"state": "ready"}, "opsec": {"state": "ready"},
    "graph": {"state": "ready"}, "search": {"state": "degraded"},
    "image": {"state": "not_validated"}, "ai": {"state": "ready"},
}

CASES = 4000
violations = 0
repo = SourcePlannerRepository383(sqlite3.connect(":memory:"))
repo.seed(default_registry().all())
planner = SourcePlanner383(repo, READY)
missions = [
    ("Map company directors", (), None),
    ("Review procurement awards", (), CONFIRM_INFERRED_SELECTORS),
    ("Find historical archive snapshots", (), CONFIRM_INFERRED_SELECTORS),
    ("Review government regulatory records", ("government", "regulatory"), None),
    ("Sanctions screening", ("sanctions",), None),
]
for i in range(CASES):
    mission, explicit, confirmation = missions[i % len(missions)]
    case_id = f"BENCH-383-{i:05d}"
    p = planner.plan(
        case_id=case_id,
        mission=mission,
        source_classes=explicit,
        confirmation=confirmation,
        jurisdictions=("US",) if i % 3 == 0 else (),
        entity_types=("company",) if i % 2 == 0 else (),
        per_class_limit=3,
    )
    if p.network_requests_created != 0 or p.execution_authority or p.scope_expansion_authority or not p.requires_go:
        violations += 1
    if p.selector_state == "proposed_inferred" and repo.case_scope(case_id):
        violations += 1
    if p.selector_state == "confirmed_inferred" and not repo.case_scope(case_id):
        violations += 1
    if any(not s.requires_human_review or s.execution_authority for s in p.steps):
        violations += 1
    if "sanctions" in p.active_source_classes and not any(g.gap_type == "registry_gap" for g in p.gaps):
        violations += 1

result = {
    "build": "383.0",
    "cases": CASES,
    "result": "pass" if violations == 0 else "fail",
    "violations": violations,
    "network_used": False,
    "system_mutations": 0,
    "selector_inference_is_advisory": True,
    "registry_fingerprint": repo.registry_fingerprint(),
    "truthful_scope": "Deterministic Source Planner/SQLite benchmark only; no connector execution or external validation claim.",
}
print(json.dumps(result, indent=2, sort_keys=True))
if violations:
    raise SystemExit(1)
