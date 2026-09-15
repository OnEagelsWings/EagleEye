from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time

from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "BENCHMARK_BUILD_385_ACQUISITION.json"
CASES = 1200


def main() -> int:
    violations = 0
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="eagleeye385-bench-") as td:
        with AppContext(base_dir=Path(td), actor="bench385") as c:
            case = c.cases.create_case(title="Build385 benchmark", client="internal", purpose="deterministic acquisition planning benchmark", legal_basis="public_data", jurisdiction="GLOBAL")
            cid = case["case_id"]
            c.build382.set_source_scope(case_id=cid, source_id="gleif.lei", state="approved", reviewer="bench385", confirmation="APPROVE SOURCE")
            waves = c.build384.plan_research_waves(case_id=cid, mission="corporate official identifier reference", jurisdictions=("global",), source_classes=("corporate",), wave_confirmation=CONFIRM_WAVES)
            wave_plan_id = waves["wave_plan_id"]
            before_jobs = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs") or {}).get("n") or 0)
            for i in range(CASES):
                # Connector parser accepts bounded 20-character uppercase alphanumeric LEI-shaped identifiers.
                lei = f"{i:020d}"
                packet = c.build385.compile_acquisition_packet(case_id=cid, wave_plan_id=wave_plan_id, identifiers={"gleif.lei": lei}, actor="bench385")
                item = next((x for x in packet.get("items", []) if x.get("source_id") == "gleif.lei"), None)
                if not item or not item.get("ready_for_preparation"):
                    violations += 1
                if packet.get("execution_authority") is not False or packet.get("network_requests_created") != 0:
                    violations += 1
            after_jobs = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs") or {}).get("n") or 0)
            if before_jobs != after_jobs:
                violations += 1
            status = c.acquisition_orchestrator_385.status()
            if status.get("network_execution_added") or status.get("automatic_crawl_enqueue") or status.get("automatic_source_approval"):
                violations += 1
            code_fingerprint = c.build385.code_fingerprint()
            packet_count = int((c.db.one("SELECT COUNT(*) n FROM acquisition_packet_385") or {}).get("n") or 0)
    elapsed = max(time.perf_counter() - started, 0.000001)
    payload = {
        "build": "385.0",
        "code_fingerprint": code_fingerprint,
        "cases": CASES,
        "packets_persisted": packet_count,
        "elapsed_seconds": round(elapsed, 6),
        "cases_per_second": round(CASES / elapsed, 3),
        "violations": violations,
        "network_requests": 0,
        "crawler_jobs_created": 0,
        "result": "pass" if violations == 0 and packet_count == CASES else "fail",
        "truthful_scope": "Local deterministic acquisition-packet compilation only; no external connector validation is inferred.",
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
