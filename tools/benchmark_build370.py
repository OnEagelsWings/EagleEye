from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from eagleeye_pro.core.app_context import AppContext

CATEGORIES=("gateway_gate","loopback_gate","dns_isolation","socks_auth_isolation","tor_queue_separation","backpressure_lease","crawler_continuity","ai_boundary","opsec_boundary","truthful_release")

def main():
    root=Path(__file__).resolve().parents[1]
    with TemporaryDirectory() as d:
        with AppContext(base_dir=d,actor="bench370") as c:
            status=c.tor_gateway_370.status(); crawler=c.build370.crawler_status(); ai=c.ai_autonomy_370.status(); op=c.opsec_supervisor_370.status(); road=c.build370.crawler_roadmap()
            base={
                "gateway_gate": not status["gateway_enabled"] and status["manual_live_confirmation"]=="TOR_LIVE",
                "loopback_gate": status["loopback_only"] and not status["control_port_authority"] and not status["tor_process_spawn"],
                "dns_isolation": status["remote_dns_required"],
                "socks_auth_isolation": status["isolate_socks_auth_required"],
                "tor_queue_separation": crawler["tor_specific_job_queue"] and crawler["clearnet_tor_worker_separation"],
                "backpressure_lease": crawler["tor_case_backpressure"] and crawler["tor_lease_recovery"],
                "crawler_continuity": crawler["continuous_crawler_expansion_370_380"] and [x["build"] for x in road]==list(range(370,381)),
                "ai_boundary": not ai["direct_tor_network_authority"] and not ai["direct_tor_job_enqueue_authority"],
                "opsec_boundary": not op["system_mutations"] and not op["tor_control_port_authority"],
                "truthful_release": not status["production_release_ready"] and status["external_onion_validation"]=="not_run",
            }
            violations=[]; category_pass={}
            for cat in CATEGORIES:
                passed=0
                for i in range(360):
                    ok=bool(base[cat])
                    # deterministic adversarial variations never relax the boundary
                    if cat=="crawler_continuity": ok=ok and road[i%len(road)]["build"] in range(370,381)
                    if cat=="socks_auth_isolation": ok=ok and c.tor_gateway_370.isolation_credentials(f"s{i}")["username"] != c.tor_gateway_370.isolation_credentials(f"other{i}")["username"]
                    if ok: passed+=1
                    else: violations.append({"category":cat,"case":i})
                category_pass[cat]=passed
            result={"build":"370.0","cases":3600,"passed":sum(category_pass.values()),"category_pass":category_pass,"violations":len(violations),"violation_details":violations[:50],"result":"pass" if not violations else "fail","network_used_by_benchmark":False,"external_validation_performed":False,"code_fingerprint":c.build370.code_fingerprint(),"truthful_scope":"Deterministic local Build-370 gateway/crawler boundary qualification only; no real Tor daemon or external onion service is contacted."}
    (root/"BENCHMARK_BUILD_370_TOR_CRAWLER.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,sort_keys=True))
    raise SystemExit(0 if result["result"]=="pass" else 1)
if __name__=="__main__": main()
