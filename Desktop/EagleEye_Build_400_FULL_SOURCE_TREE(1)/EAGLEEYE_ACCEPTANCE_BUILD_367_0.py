from __future__ import annotations

import json
import tempfile
from pathlib import Path

from eagleeye_pro.core.app_context import AppContext


def run() -> dict:
    root=Path(__file__).resolve().parent
    live=json.loads((root/"LIVE_VALIDATION_BUILD_367_PUBLIC_MONEY.json").read_text(encoding="utf-8")); bench=json.loads((root/"BENCHMARK_BUILD_367_PUBLIC_MONEY.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="ee367-accept-") as td:
        with AppContext(base_dir=Path(td),actor="accept367") as c:
            gate=c.build367.qualified_gate(); metrics=c.build367.schema_metrics(); status=c.build367.public_money_status()
            probes={
                "schema":bool(metrics["within_gate"] and (metrics["table"],metrics["index"],metrics["trigger"])==(141,128,8)),
                "version":c.build367.version_status()["coherent"],
                "catalog":c.build367._probe("catalog"),"usaspending":c.build367._probe("usaspending"),"ted":c.build367._probe("ted"),"ted_plan":c.build367._probe("ted_plan"),
                "review":c.build367._probe("review"),"confirmation":c.build367._probe("confirmation"),"receipt":c.build367._probe("receipt"),"replay":c.build367._probe("replay"),"ai":c.build367._probe("ai"),"opsec":c.build367._probe("opsec"),"crawler":c.build367._probe("crawler"),
                "benchmark":bench.get("result")=="pass" and bench.get("cases")==2800 and bench.get("violations")==0,
                "truthful_live_status":live.get("status")=="not_run" and live.get("network_used") is False and not status["usaspending_externally_validated"] and not status["ted_externally_validated"],
                "gate":gate["build_acceptance_ready"],"production_false":gate["production_release_ready"] is False,
            }
            return {"build":"367.0","result":"pass" if all(probes.values()) else "fail","probes":probes,"gate":gate,"schema":metrics,"benchmark":{"cases":bench.get("cases"),"violations":bench.get("violations")},"public_money_live_validation":live,"external_network_used_by_acceptance":False}

if __name__=="__main__": print(json.dumps(run(),indent=2,sort_keys=True))
