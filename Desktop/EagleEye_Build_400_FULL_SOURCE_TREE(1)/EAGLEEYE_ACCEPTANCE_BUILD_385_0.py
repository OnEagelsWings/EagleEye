from __future__ import annotations

import json
from pathlib import Path
import tempfile

from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "ACCEPTANCE_RESULTS_BUILD_385_0.json"
PW = "Acceptance-Orbit-Quartz-385!"


def main() -> int:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="eagleeye385-accept-") as td:
        with AppContext(base_dir=Path(td), actor="accept385") as c:
            admin = c.team_identity_359.create_initial_admin(username="accept385", display_name="Acceptance 385", password=PW)
            identity = {**admin, "session_id": "accept-session-385"}
            case = c.build380.team_create_case(identity=identity, title="Build385 acceptance", client="internal", purpose="authorized public-source acquisition qualification", legal_basis="public_data")
            cid = case["case_id"]

            checks["version_coherent"] = bool(c.build385.version_status().get("coherent"))
            checks["schema_within_phase17_gate"] = bool(c.build385.schema_metrics().get("within_phase17_gate"))
            checks["historical_build384_receipt"] = bool(c.build385.historical_build384_receipt().get("valid"))

            status = c.acquisition_orchestrator_385.status()
            checks["capability_matrix_seeded"] = int(status.get("capabilities", 0)) >= 6
            checks["network_execution_not_added"] = status.get("network_execution_added") is False
            checks["arbitrary_url_execution_blocked"] = status.get("arbitrary_url_execution") is False
            checks["credential_injection_blocked"] = status.get("credential_injection") is False
            checks["automatic_source_approval_blocked"] = status.get("automatic_source_approval") is False
            checks["automatic_crawl_enqueue_blocked"] = status.get("automatic_crawl_enqueue") is False
            checks["automatic_scope_expansion_blocked"] = status.get("automatic_scope_expansion") is False

            c.build382.set_source_scope(case_id=cid, source_id="gleif.lei", state="approved", reviewer="accept385", confirmation="APPROVE SOURCE")
            waves = c.build384.plan_research_waves(
                case_id=cid,
                mission="corporate official identifier verification",
                jurisdictions=("global",),
                source_classes=("corporate",),
                wave_confirmation=CONFIRM_WAVES,
            )
            packet = c.build385.compile_acquisition_packet(
                case_id=cid,
                wave_plan_id=waves["wave_plan_id"],
                identifiers={"gleif.lei": "5493001KJTIIGC8Y1R12"},
                actor="accept385",
            )
            item = next((x for x in packet.get("items", []) if x.get("source_id") == "gleif.lei"), {})
            checks["confirmed_wave_compiles_ready_source"] = bool(item.get("ready_for_preparation"))
            checks["packet_nonexecuting"] = packet.get("execution_authority") is False and packet.get("network_requests_created") == 0

            before_jobs = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs") or {}).get("n") or 0)
            wrong_confirmation_blocked = False
            try:
                c.build385.prepare_acquisition_packet(case_id=cid, packet_id=packet["packet_id"], identity=identity, confirmation="GO")
            except PermissionError:
                wrong_confirmation_blocked = True
            checks["prepare_exact_confirmation_required"] = wrong_confirmation_blocked

            prepared = c.build385.prepare_acquisition_packet(case_id=cid, packet_id=packet["packet_id"], identity=identity, confirmation=CONFIRM_PREPARE)
            after_jobs = int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs") or {}).get("n") or 0)
            source_ids = [x.get("canonical_source_id") for x in prepared.get("outcomes", []) if x.get("canonical_source_id")]
            checks["preparation_creates_pending_canonical_source"] = bool(source_ids) and all((c.db.one("SELECT review_status FROM phase15_sources WHERE source_id=?", (sid,)) or {}).get("review_status") == "pending_review" for sid in source_ids)
            checks["preparation_creates_no_jobs"] = before_jobs == after_jobs and prepared.get("jobs_created") == 0
            checks["preparation_creates_no_network_requests"] = prepared.get("network_requests_created") == 0

            readiness = c.build385.acquisition_execution_readiness(case_id=cid, packet_id=packet["packet_id"], identity=identity)
            checks["phase15_review_gate_preserved"] = readiness.get("ready_sources") == 0 and all("phase15_source_review_required" in x.get("blockers", []) for x in readiness.get("prepared_sources", []) if x.get("canonical_source_id"))
            checks["execution_authority_still_false"] = readiness.get("execution_authority") is False and readiness.get("automatic_enqueue") is False

            code_fingerprint = c.build385.code_fingerprint()

    passed = sum(1 for value in checks.values() if value)
    payload = {
        "build": "385.0",
        "code_fingerprint": code_fingerprint,
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "result": "pass" if passed == len(checks) else "fail",
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["result"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
