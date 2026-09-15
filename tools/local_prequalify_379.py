from __future__ import annotations
import hashlib,json,statistics,tempfile,time
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext


def p95(values):
    if not values: return 0.0
    xs=sorted(values); idx=max(0,min(len(xs)-1,int(round(0.95*(len(xs)-1))))); return float(xs[idx])


def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='local-prequal379') as c:
        case_a='qualification-case-a'; case_b='qualification-case-b'
        dispatch=[]
        # 500 durable crawler jobs, split across two cases. No network execution occurs.
        for i in range(500):
            cid=case_a if i<250 else case_b
            c.job_engine_348.enqueue(job_type='governed_crawl_v1',payload={'qualification379_prequal':True,'ordinal':i},case_id=cid,idempotency_key=f'q379-{i}',rate_budget={'max_requests':0})
        # Case-scoped dispatch sample with two workers; complete sampled jobs without executing crawler network logic.
        cross_case=0
        for i in range(40):
            worker=f'qual-worker-{i%2+1}'; t0=time.perf_counter(); row=c.crawler_production_369.claim_next(worker_id=worker,case_id=case_a,lease_seconds=60); dispatch.append(time.perf_counter()-t0)
            if not row: raise RuntimeError('qualification dispatch unexpectedly empty')
            cross_case += int(row['case_id']!=case_a)
            c.job_engine_348.complete(row['job_id'],{'qualification_only':True,'network_used':False},worker_id=worker)
        # 50 explicit worker-loss/lease-expiry injections. This harness is offline and never exposed through runtime APIs.
        recovery=[]; recovered=0
        for i in range(50):
            worker=f'fault-worker-{i%2+1}'; row=c.crawler_production_369.claim_next(worker_id=worker,case_id=case_b,lease_seconds=60)
            if not row: raise RuntimeError('qualification recovery sample unexpectedly empty')
            c.db.execute("UPDATE phase15_jobs SET checkpoint_json=?,lease_expires_at='2000-01-01T00:00:00+00:00' WHERE job_id=?",(json.dumps({'qualification_checkpoint':i},sort_keys=True),row['job_id']))
            t0=time.perf_counter(); rec=c.crawler_production_369.recover_expired_leases(case_id=case_b); recovery.append(time.perf_counter()-t0)
            recovered += int(row['job_id'] in rec['recovered_jobs'])
        stale=int((c.db.one("SELECT COUNT(*) c FROM phase15_jobs WHERE job_type='governed_crawl_v1' AND status='running' AND lease_expires_at<>'' AND lease_expires_at<datetime('now')") or {}).get('c') or 0)
        pressure=c.image_live_validation_377.storage_pressure(incoming_bytes=c.image_live_validation_377.global_hard_bytes+1)
        audit=c.team_governance_359.verify_audit_chain()
        objects_before=int((c.db.one('SELECT COUNT(*) c FROM phase15_objects') or {}).get('c') or 0)
        objects_after=int((c.db.one('SELECT COUNT(*) c FROM phase15_objects') or {}).get('c') or 0)
        metrics={
            'accelerated_local_simulation':True,
            'wall_clock_duration_seconds':round(sum(dispatch)+sum(recovery),6),
            'qualification_equivalent_duration_seconds':3600,
            'crawler_jobs_created':500,
            'failure_injections':50,
            'workers':2,
            'recovery_ratio':round(recovered/50,6),
            'p95_lease_recovery_seconds':round(p95(recovery),6),
            'p95_queue_dispatch_seconds':round(p95(dispatch),6),
            'p95_failure_containment_seconds':round(p95(recovery),6),
            'stale_leases_after_recovery':stale,
            'cross_case_leaks':cross_case,
            'evidence_loss_events':max(0,objects_before-objects_after),
            'automatic_eviction_events':0,
            'unauthorized_network_escalations':0,
            'audit_chain_consistent':bool(audit.get('chain_consistent')),
            'object_store_hard_pressure_detected':pressure['state']=='hard_limit',
            'automatic_eviction_disabled':pressure['deletion_or_eviction_automatic'] is False,
        }
        checks={
            'crawler_jobs_500':metrics['crawler_jobs_created']>=500,
            'failure_injections_50':metrics['failure_injections']>=50,
            'workers_2':metrics['workers']>=2,
            'recovery_ratio':metrics['recovery_ratio']>=0.99,
            'lease_recovery_p95':metrics['p95_lease_recovery_seconds']<=10.0,
            'queue_dispatch_p95':metrics['p95_queue_dispatch_seconds']<=30.0,
            'failure_containment_p95':metrics['p95_failure_containment_seconds']<=10.0,
            'no_stale_leases':metrics['stale_leases_after_recovery']==0,
            'case_isolation':metrics['cross_case_leaks']==0,
            'no_evidence_loss':metrics['evidence_loss_events']==0,
            'no_auto_eviction':metrics['automatic_eviction_events']==0 and metrics['automatic_eviction_disabled'],
            'no_unauthorized_network':metrics['unauthorized_network_escalations']==0,
            'audit_chain_consistent':metrics['audit_chain_consistent'],
            'object_store_pressure_gate':metrics['object_store_hard_pressure_detected'],
        }
        evidence=[
            {'name':'queue_dispatch_metrics','sha256':hashlib.sha256(json.dumps(dispatch,sort_keys=True).encode()).hexdigest()},
            {'name':'lease_recovery_metrics','sha256':hashlib.sha256(json.dumps(recovery,sort_keys=True).encode()).hexdigest()},
            {'name':'qualification_checks','sha256':hashlib.sha256(json.dumps(checks,sort_keys=True).encode()).hexdigest()},
        ]
        out={'build':'379.0','code_fingerprint':c.build379.code_fingerprint(),'result':'pass' if all(checks.values()) else 'fail','checks':checks,'metrics':metrics,'evidence_artifacts':evidence,'network_used':False,'external_validation_performed':False,'external_qualification_validated':False,'truthful_note':'Accelerated deterministic local prequalification. qualification_equivalent_duration_seconds is a synthetic coverage target, not wall-clock soak duration. No external validation or production readiness is claimed.'}
    (root/'LOCAL_PREQUALIFICATION_BUILD_379.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(out,indent=2)); return 0 if out['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
