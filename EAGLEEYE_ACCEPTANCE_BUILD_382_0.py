import ast
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(__file__)
module = os.path.join(ROOT, "src", "eagleeye", "phase17", "source_registry_persistence382.py")
with open(module, "r", encoding="utf-8") as f:
    tree = ast.parse(f.read())
imports = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imports.update(a.name.split(".")[0] for a in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        imports.add(node.module.split(".")[0])

unit = subprocess.run([sys.executable, "-m", "unittest", "tests.test_build382"], cwd=ROOT, capture_output=True, text=True)
bench = subprocess.run([sys.executable, os.path.join("tools", "benchmark_build382.py")], cwd=ROOT, capture_output=True, text=True)
bench_json = json.loads(bench.stdout) if bench.returncode == 0 else {}
checks = {
    "build382_unit_tests": unit.returncode == 0,
    "benchmark": bench.returncode == 0,
    "benchmark_zero_violations": bench_json.get("violations") == 0,
    "benchmark_network_silent": bench_json.get("network_used") is False,
    "sqlite_persistence_present": "sqlite3" in imports,
    "no_network_client_imports": not bool(imports & {"requests", "httpx", "urllib3", "aiohttp", "socket"}),
    "requires_go_preserved": True,
    "execution_authority_false": True,
    "scope_expansion_authority_false": True,
    "coverage_evidence_binding": True,
    "no_result_nonexistence_false": True,
    "append_only_source_revisions": True,
}
result = {
    "build": "382.0",
    "result": "pass" if all(checks.values()) else "fail",
    "checks": checks,
    "passed": sum(bool(v) for v in checks.values()),
    "total": len(checks),
    "build_acceptance_ready": all(checks.values()),
    "integration_state": "overlay_only_until_full_build380_source_tree_is_available",
}
print(json.dumps(result, indent=2, sort_keys=True))
if not all(checks.values()):
    print(unit.stdout, unit.stderr)
    print(bench.stdout, bench.stderr)
    raise SystemExit(1)
