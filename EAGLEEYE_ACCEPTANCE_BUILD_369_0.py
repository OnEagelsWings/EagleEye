from __future__ import annotations
import json, tempfile
from eagleeye_pro.core.app_context import AppContext

def run_acceptance():
    with tempfile.TemporaryDirectory(prefix='ee369_accept_') as d:
        with AppContext(base_dir=d,actor='accept369') as c:
            version=c.build369.version_status(); schema=c.build369.schema_metrics(); prod=c.build369.crawler_production_status(); crawler=c.build369.crawler_status(); gate=c.build369.qualified_gate(); live=c.build369._live_validation()
            checks={
                'version_coherent':bool(version['coherent']),
                'schema_gate':bool(schema['within_gate']),
                'schema_counts':(schema['table'],schema['index'],schema['trigger'])==(141,128,8),
                'test_evidence_current':bool(c.build369._test_evidence()),
                'benchmark_3200_current':bool(c.build369._benchmark()),
                'local_validation_current':bool(live) and live.get('status')=='pass',
                'scheduler_worker_replay_pass':prod['local_scheduler_worker_replay_validation']=='pass',
                'delta_resume_pass':prod['local_delta_resume_validation']=='pass',
                'lease_recovery_pass':prod['local_lease_recovery_validation']=='pass',
                'scheduler_explicit_only':crawler['operator_orchestrated_scheduler_tick'] and crawler['background_workers_started_on_boot']==0,
                'backpressure_enabled':crawler['queue_backpressure'],
                'source_health_circuit_enabled':crawler['source_health_circuit_breaker'],
                'provider_live_gates_preserved':crawler['provider_connector_live_gates_preserved'],
                'darknet_recurring_disabled':crawler['darknet_recurring_schedule_disabled'],
                'delta_enabled':crawler['delta_conditional_fetch'],
                'resume_enabled':crawler['frontier_checkpoint_resume'],
                'lease_recovery_crawler_only':crawler['crawler_only_expired_lease_recovery'],
                'qualified_gate':bool(gate['build_acceptance_ready']),
                'production_release_false':gate['production_release_ready'] is False,
            }
            result={'build':'369.0','checks':checks,'passed':sum(bool(v) for v in checks.values()),'total':len(checks),'result':'pass' if all(checks.values()) else 'fail','build_acceptance_ready':all(checks.values()),'production_release_ready':False,'schema':{'tables':schema['table'],'indexes':schema['index'],'triggers':schema['trigger'],'logical_bytes':schema.get('logical_bytes')},'code_fingerprint':c.build369.code_fingerprint(),'external_long_running_soak_validation':prod['external_long_running_soak_validation'],'external_load_validation':prod['external_load_validation'],'truthful_note':'Internal deterministic Crawler Production acceptance only; no external long-running soak/load validation is claimed.'}
    return result
if __name__=='__main__':
    r=run_acceptance(); print(json.dumps(r,indent=2,sort_keys=True)); raise SystemExit(0 if r['result']=='pass' else 1)
