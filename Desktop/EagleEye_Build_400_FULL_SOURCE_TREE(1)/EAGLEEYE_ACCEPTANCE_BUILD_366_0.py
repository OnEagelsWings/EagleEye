from __future__ import annotations

import json
import tempfile
from pathlib import Path

from eagleeye_pro.core.app_context import AppContext


def run() -> dict:
    root = Path(__file__).resolve().parent
    live = json.loads((root / "LIVE_VALIDATION_BUILD_366_CORPORATE.json").read_text(encoding="utf-8"))
    bench = json.loads((root / "BENCHMARK_BUILD_366_CORPORATE.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="ee366-accept-") as td:
        with AppContext(base_dir=Path(td), actor="accept366") as c:
            gate = c.build366.qualified_gate(); metrics = c.build366.schema_metrics(); status = c.build366.corporate_status()
            probes = {
                "schema": bool(metrics["within_gate"] and (metrics["table"],metrics["index"],metrics["trigger"]) == (141,128,8)),
                "version": c.build366.version_status()["coherent"],
                "catalog": c.build366._probe("catalog"), "gleif":c.build366._probe("gleif"), "sec":c.build366._probe("sec"),
                "review":c.build366._probe("review"), "confirmation":c.build366._probe("confirmation"), "receipt":c.build366._probe("receipt"),
                "replay":c.build366._probe("replay"), "ai":c.build366._probe("ai"), "opsec":c.build366._probe("opsec"), "crawler":c.build366._probe("crawler"),
                "benchmark": bench.get("result") == "pass" and bench.get("cases") == 2600 and bench.get("violations") == 0,
                "truthful_live_status": live.get("status") == "not_run" and live.get("network_used") is False and not status["gleif_externally_validated"] and not status["sec_externally_validated"],
                "gate": gate["build_acceptance_ready"], "production_false": gate["production_release_ready"] is False,
            }
            return {
                "build":"366.0", "result":"pass" if all(probes.values()) else "fail", "probes":probes,
                "gate":gate, "schema":metrics, "benchmark":{"cases":bench.get("cases"),"violations":bench.get("violations")},
                "corporate_live_validation":live, "external_network_used_by_acceptance":False,
            }

if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
