from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parent
    with TemporaryDirectory() as d:
        with AppContext(base_dir=d,actor="accept370") as c:
            m=c.build370.schema_metrics(); v=c.build370.version_status(); gate=c.build370.qualified_gate(); tor=c.tor_gateway_370.status(); crawl=c.build370.crawler_status(); ai=c.ai_autonomy_370.status(); op=c.opsec_supervisor_370.status(); road=c.build370.crawler_roadmap()
            checks={
                "version_coherent":v["coherent"],"schema_gate":m["within_gate"],"schema_counts":(m["table"],m["index"],m["trigger"])==(141,128,8),"test_evidence_current":bool(c.build370._test_evidence()),"benchmark_current":bool(c.build370._benchmark()),
                "local_socks_contract":c.build370._live_validation().get("local_socks_contract_validation")=="pass","local_tor_http_fixture":c.build370._live_validation().get("local_tor_transport_http_validation")=="pass","gateway_default_manual":tor["manual_live_confirmation"]=="TOR_LIVE","loopback_only":tor["loopback_only"],"remote_dns":tor["remote_dns_required"],"socks_auth_isolation":tor["isolate_socks_auth_required"],"no_control_port":not tor["control_port_authority"],"no_newnym":not tor["newnym_authority"],"no_tor_mutation":not tor["torrc_mutation"] and not tor["tor_process_spawn"],"queue_separation":crawl["clearnet_tor_worker_separation"],"tor_backpressure":crawl["tor_case_backpressure"],"tor_lease_recovery":crawl["tor_lease_recovery"],"crawler_roadmap":[x["build"] for x in road]==list(range(370,381)),"ai_boundary":not ai["direct_tor_network_authority"],"opsec_boundary":not op["system_mutations"],"zero_boot_network":tor["automatic_external_connections_on_boot"]==0,"truthful_release":gate["production_release_ready"] is False and not gate["external_onion_validated"]}
            result={"build":"370.0","checks":checks,"passed":sum(bool(v) for v in checks.values()),"total":len(checks),"result":"pass" if all(checks.values()) else "fail","build_acceptance_ready":gate["build_acceptance_ready"],"production_release_ready":False,"code_fingerprint":c.build370.code_fingerprint()}
    (root/"ACCEPTANCE_RESULTS_BUILD_370_0.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n"); print(json.dumps(result,sort_keys=True)); raise SystemExit(0 if result["result"]=="pass" and result["build_acceptance_ready"] else 1)
if __name__=="__main__": main()
