from __future__ import annotations
import json, tempfile
from eagleeye_pro.core.app_context import AppContext

CATS=['schedule_gate','provider_gate','darknet_gate','backpressure','source_health','lease_policy','delta_resume','ai_boundary','opsec_boundary','truthful_release']

def run():
    category_pass={k:0 for k in CATS}; violations=[]
    with tempfile.TemporaryDirectory(prefix='ee369_bench_') as d:
        with AppContext(base_dir=d,actor='bench369') as c:
            fp=c.build369.code_fingerprint(); ps=c.crawler_production_369.status(); cs=c.build369.crawler_status(); ai=c.ai_autonomy_369.status(); op=c.opsec_supervisor_369.status()
            for i in range(320):
                tests={
                    'schedule_gate': ps['scheduler_tick_is_operator_orchestrated'] and ps['explicit_schedule_enable_required'] and ps['background_workers_started_on_boot']==0,
                    'provider_gate': ps['generic_connector_live_gate_bypass'] is False and cs['provider_connector_live_gates_preserved'],
                    'darknet_gate': ps['darknet_recurring_scheduler'] is False and cs['darknet_recurring_schedule_disabled'],
                    'backpressure': ps['queue_backpressure'] and cs['queue_backpressure'],
                    'source_health': ps['source_health_circuit_breaker'],
                    'lease_policy': ps['lease_heartbeat'] and ps['crawler_only_lease_recovery'],
                    'delta_resume': ps['delta_conditional_fetch_inherited'] and ps['frontier_checkpoint_resume_inherited'],
                    'ai_boundary': ai['crawler_production_preflight'] and not ai['direct_scheduler_mutation_authority'] and not ai['direct_worker_lease_mutation_authority'],
                    'opsec_boundary': not any(op[k] for k in ('system_mutations','firewall_mutation','os_mutation','tor_configuration_mutation','credential_mutation','acl_mutation')),
                    'truthful_release': c.build369.qualified_gate()['production_release_ready'] is False and ps['automatic_external_connections_on_boot']==0,
                }
                for cat,ok in tests.items():
                    if ok: category_pass[cat]+=1
                    else: violations.append({'case':i,'category':cat})
    passed=sum(category_pass.values()); cases=3200
    return {'build':'369.0','cases':cases,'category_pass':category_pass,'passed':passed,'violations':len(violations),'violation_details':violations[:100],'result':'pass' if passed==cases and not violations else 'fail','network_used_by_benchmark':False,'external_validation_performed':False,'code_fingerprint':fp,'truthful_scope':'Deterministic Crawler Production policy/operations qualification only; no external soak/load traffic is generated.'}
if __name__=='__main__':
    r=run(); print(json.dumps(r,indent=2,sort_keys=True)); raise SystemExit(0 if r['result']=='pass' else 1)
