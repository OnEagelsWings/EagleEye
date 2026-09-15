from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

ROOT=Path(__file__).resolve().parent

def run_acceptance():
    checks={}
    with tempfile.TemporaryDirectory(prefix="ee368_accept_") as d:
        with AppContext(base_dir=d,actor="accept368") as c:
            version=c.build368.version_status(); schema=c.build368.schema_metrics(); status=c.build368.reference_status(); crawler=c.build368.crawler_status(); gate=c.build368.qualified_gate()
            catalog={x["connector_key"]:x for x in c.build368.reference_connector_catalog()}
            checks={
                "version_coherent": bool(version["coherent"]),
                "schema_gate": bool(schema["within_gate"]),
                "schema_counts": (schema["table"],schema["index"],schema["trigger"])==(141,128,8),
                "two_live_reference_connectors": sum(bool(x["build368_live_eligible"]) for x in catalog.values())==2,
                "four_plan_only_reference_connectors": sum(bool(x["plan_only"]) for x in catalog.values())==4,
                "automatic_external_connections_zero": not status["automatic_external_connections"],
                "fuzzy_sanctions_screening_disabled": not status["sanctions_fuzzy_name_screening"],
                "archive_content_download_disabled": not status["archive_content_download"],
                "nara_execution_disabled": not status["nara_api_execution"],
                "govinfo_execution_disabled": not status["govinfo_api_execution"],
                "ofac_unsc_execution_disabled": not status["ofac_live_execution"] and not status["unsc_live_execution"],
                "crawler_reference_receipt": bool(crawler["canonical_reference_receipt"]),
                "replay_truthfulness": bool(crawler["replay_cannot_claim_reference_external_validation"]),
                "test_evidence_current": bool(c.build368._test_evidence()),
                "benchmark_current": bool(c.build368._benchmark()),
                "qualified_gate": bool(gate["build_acceptance_ready"]),
                "production_release_false": gate["production_release_ready"] is False,
            }
            out={"build":"368.0","checks":checks,"passed":sum(bool(v) for v in checks.values()),"total":len(checks),"result":"pass" if all(checks.values()) else "fail","build_acceptance_ready":all(checks.values()),"production_release_ready":False,"schema":{"tables":schema["table"],"indexes":schema["index"],"triggers":schema["trigger"],"logical_bytes":schema.get("logical_bytes")},"code_fingerprint":c.build368.code_fingerprint(),"truthful_note":"Internal deterministic acceptance only; no external reference-source validation is claimed."}
    return out

if __name__=="__main__":
    result=run_acceptance(); print(json.dumps(result,indent=2,sort_keys=True)); raise SystemExit(0 if result["result"]=="pass" else 1)
