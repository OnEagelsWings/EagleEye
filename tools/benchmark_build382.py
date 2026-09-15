import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from eagleeye.phase17.source_registry_persistence382 import (  # noqa: E402
    InvestigationControlPlane382,
    SourceRegistryRepository382,
)
from eagleeye.phase17.investigation_control381 import default_registry  # noqa: E402

READY = {
    "evidence": {"state": "ready"}, "crawler": {"state": "ready"},
    "operations": {"state": "ready"}, "opsec": {"state": "ready"},
    "graph": {"state": "ready"}, "search": {"state": "degraded"},
    "image": {"state": "not_validated"}, "ai": {"state": "ready"},
}

CASES = 3000
violations = 0
conn = sqlite3.connect(":memory:")
repo = SourceRegistryRepository382(conn)
repo.seed(default_registry().all())
cp = InvestigationControlPlane382(repo, READY)
classes = ["corporate", "procurement", "government", "archive", "regulatory"]
for i in range(CASES):
    case_id = f"BENCH-382-{i:04d}"
    source_class = classes[i % len(classes)]
    p = cp.plan_research(case_id=case_id, mission=f"benchmark mission {i}", source_classes=[source_class], limit=4)
    snap = cp.snapshot(case_id)
    if not p.requires_go or p.execution_authority or p.scope_expansion_authority or p.network_requests_created != 0:
        violations += 1
    if snap["network_requests_created"] != 0 or snap["mutations_performed"] != 0:
        violations += 1
    if p.source_ids:
        repo.record_coverage(case_id=case_id, source_id=p.source_ids[0], state="planned")
    report = repo.coverage_report(case_id, requested_source_classes=[source_class])
    if report.network_requests_created != 0 or report.no_result_is_nonexistence:
        violations += 1

result = {
    "build": "382.0",
    "cases": CASES,
    "result": "pass" if violations == 0 else "fail",
    "violations": violations,
    "network_used": False,
    "system_mutations": 0,
    "registry_fingerprint": repo.registry_fingerprint(),
    "truthful_scope": "Deterministic SQLite-backed planning/coverage benchmark only; no external connector or production claim.",
}
print(json.dumps(result, indent=2, sort_keys=True))
if violations:
    raise SystemExit(1)
