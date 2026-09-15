from __future__ import annotations
import json, tempfile, time
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE
from eagleeye_pro.phase17.execution_authority386 import CONFIRM_GO
from eagleeye_pro.phase17.controlled_executor387 import CONFIRM_EXECUTE

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'BENCHMARK_BUILD_387_CONTROLLED_EXECUTOR.json'; CASES=100; PW='Bench-Orbit-Quartz-387!'

def main()->int:
    violations=0; started=time.perf_counter(); job_ids=[]; dispatch_ids=[]
    with tempfile.TemporaryDirectory(prefix='eagleeye387-bench-') as td:
        with AppContext(base_dir=Path(td),actor='bench387') as c:
            admin=c.team_identity_359.create_initial_admin(username='bench387',display_name='Bench 387',password=PW); ident={**admin,'session_id':'bench-session-387'}
            case=c.build380.team_create_case(identity=ident,title='Build387 benchmark',client='internal',purpose='deterministic controlled executor benchmark',legal_basis='public_data'); cid=case['case_id']
            c.build382.set_source_scope(case_id=cid,source_id='gleif.lei',state='approved',reviewer='bench387',confirmation='APPROVE SOURCE')
            waves=c.build384.plan_research_waves(case_id=cid,mission='official corporate identifier verification',jurisdictions=('global',),source_classes=('corporate',),wave_confirmation=CONFIRM_WAVES)
            packet=c.build385.compile_acquisition_packet(case_id=cid,wave_plan_id=waves['wave_plan_id'],identifiers={'gleif.lei':'5493001KJTIIGC8Y1R12'},actor='bench387')
            prepared=c.build385.prepare_acquisition_packet(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_PREPARE)
            sid=next(x['canonical_source_id'] for x in prepared['outcomes'] if x.get('canonical_source_id'))
            c.crawler_engine_349.review_source(sid,decision='approve_read_only',rationale='benchmark review',reviewer='bench387')
            c.case_workflow_374.configure(case_id=cid,identity=ident,source_budgets={sid:5000},case_request_budget=5000,max_active_crawls=2,confirmation='WORKFLOW')
            for _ in range(CASES):
                g=c.build386.issue_execution_grant(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_GO,ttl_minutes=5)
                out=c.build387.execute_grant(case_id=cid,grant_id=g['grant_id'],grant_token=g['grant_token'],identity=ident,confirmation=CONFIRM_EXECUTE)
                if out.get('jobs_enqueued')!=1 or out.get('network_fetches_executed')!=0 or out.get('grant_consumed') is not True: violations+=1
                if c.execution_authority_386.grant(case_id=cid,grant_id=g['grant_id']).get('state')!='consumed_387': violations+=1
                v=c.build387.verify_execution_dispatch(case_id=cid,dispatch_id=out['dispatch_id'])
                if not all(v.get(k) for k in ('record_hash_valid','jobs_present','all_jobs_workflow_tagged','all_jobs_unclaimed')): violations+=1
                jid=out['job_ids'][0]; job_ids.append(jid); dispatch_ids.append(out['dispatch_id'])
                # Benchmark executor throughput, not worker throughput. Cancel queued job so the next dispatch can reuse workflow capacity.
                c.job_engine_348.cancel(jid,actor='bench387')
            dispatch_count=int((c.db.one('SELECT COUNT(*) n FROM execution_dispatch_387') or {}).get('n') or 0)
            consumed_count=int((c.db.one("SELECT COUNT(*) n FROM execution_grant_386 WHERE state='consumed_387'") or {}).get('n') or 0)
            attempts=int((c.db.one("SELECT COALESCE(SUM(attempts),0) n FROM phase15_jobs WHERE job_id IN (%s)" % ','.join('?' for _ in job_ids),job_ids) or {}).get('n') or 0) if job_ids else 0
            if attempts!=0: violations+=1
            fp=c.build387.code_fingerprint()
    elapsed=max(time.perf_counter()-started,1e-6); payload={'build':'387.0','code_fingerprint':fp,'cases':CASES,'dispatches':dispatch_count,'consumed_grants':consumed_count,'unique_jobs':len(set(job_ids)),'unique_dispatches':len(set(dispatch_ids)),'worker_attempts':attempts,'network_fetches_executed_by_executor':0,'elapsed_seconds':round(elapsed,6),'cases_per_second':round(CASES/elapsed,3),'violations':violations,'result':'pass' if violations==0 and dispatch_count==CASES and consumed_count==CASES and len(set(job_ids))==CASES else 'fail','truthful_scope':'Controlled enqueue benchmark only. Jobs are never claimed or fetched by Build 387; external connector/network validation is not inferred.'}
    OUT.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); print(json.dumps(payload,indent=2,sort_keys=True)); return 0 if payload['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
