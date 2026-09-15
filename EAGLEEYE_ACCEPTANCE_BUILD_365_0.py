from __future__ import annotations

import json
import tempfile
from pathlib import Path

from eagleeye_pro.core.app_context import AppContext


def run() -> dict:
    root = Path(__file__).resolve().parent
    live = json.loads((root / "LIVE_VALIDATION_BUILD_365_OPERATIONS.json").read_text(encoding="utf-8"))
    bench = json.loads((root / "BENCHMARK_BUILD_365_OPERATIONS.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="ee365-accept-") as td:
        with AppContext(base_dir=Path(td), actor="accept365") as c:
            gate = c.build365.qualified_gate()
            metrics = c.build365.schema_metrics()
            probes = {
                "schema": bool(metrics["within_gate"] and (metrics["table"], metrics["index"], metrics["trigger"]) == (141, 128, 8)),
                "version": c.build365.version_status()["coherent"],
                "operations": c.build365._probe("operations"),
                "metrics": c.build365._probe("metrics"),
                "trace": c.build365._probe("trace"),
                "incidents": c.build365._probe("incidents"),
                "workers": c.build365._probe("workers"),
                "ai": c.build365._probe("ai"),
                "opsec": c.build365._probe("opsec"),
                "crawler": c.build365._probe("crawler"),
                "local_live_operations": bool(live.get("status") == "pass" and live.get("local_sqlite_operations_live_validated") and live.get("queue_trace_incident_flow_live_validated")),
                "truthful_external": live.get("externally_validated") is False and live.get("external_multi_user_operations_validated") is False,
                "benchmark": bench.get("result") == "pass" and bench.get("cases") == 2400 and bench.get("violations") == 0,
                "gate": gate["build_acceptance_ready"],
                "production_false": gate["production_release_ready"] is False,
            }
            result = {
                "build": "365.0",
                "result": "pass" if all(probes.values()) else "fail",
                "probes": probes,
                "gate": gate,
                "schema": metrics,
                "benchmark": {"cases": bench.get("cases"), "violations": bench.get("violations")},
                "local_operations_validation": live,
                "external_network_used_by_acceptance": False,
            }
            return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
