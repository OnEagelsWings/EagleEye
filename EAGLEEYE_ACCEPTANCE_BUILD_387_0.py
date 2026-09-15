from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE
from eagleeye_pro.phase17.execution_authority386 import CONFIRM_GO
from eagleeye_pro.phase17.controlled_executor387 import CONFIRM_EXECUTE

ROOT=Path(__file__).resolve().parent; OUT=ROOT/'ACCEPTANCE_RESULTS_BUILD_387_0.json'; PW='Acceptance-Orbit-Quartz-387!'

def main()->int:
    checks={}
    with tempfile.TemporaryDirectory(prefix='eagleeye387-accept-') as td:
        with AppContext(base_dir=Path(td), actor='accept387') as c:
            admin=c.team_identity_359.create_initial_admin(username='accept387',display_name='Acceptance 387',password=PW); ident={**admin,'session_id':'accept-session-387'}
            case=c.build380.team_create_case(identity=ident,title='Build387 acceptance',client='internal',purpose='authorized public-source controlled execution qualification',legal_basis='public_data'); cid=case['case_id']
            checks['version_coherent']=bool(c.build387.version_status().get('coherent'))
            checks['schema_gate']=bool(c.build387.schema_metrics().get('within_phase17_gate'))
            checks['historical_build386_receipt']=bool(c.build387.historical_build386_receipt().get('valid'))
            c.build382.set_source_scope(case_id=cid,source_id='gleif.lei',state='approved',reviewer='accept387',confirmation='APPROVE SOURCE')
            waves=c.build384.plan_research_waves(case_id=cid,mission='official corporate identifier verification',jurisdictions=('global',),source_classes=('corporate',),wave_confirmation=CONFIRM_WAVES)
            packet=c.build385.compile_acquisition_packet(case_id=cid,wave_plan_id=waves['wave_plan_id'],identifiers={'gleif.lei':'5493001KJTIIGC8Y1R12'},actor='accept387')
            prepared=c.build385.prepare_acquisition_packet(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_PREPARE)
            sid=next(x['canonical_source_id'] for x in prepared['outcomes'] if x.get('canonical_source_id'))
            c.crawler_engine_349.review_source(sid,decision='approve_read_only',rationale='acceptance controlled read-only source',reviewer='accept387')
            c.case_workflow_374.configure(case_id=cid,identity=ident,source_budgets={sid:20},case_request_budget=20,max_active_crawls=2,confirmation='WORKFLOW')
            grant=c.build386.issue_execution_grant(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_GO,ttl_minutes=5)
            before=int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs WHERE job_type='governed_crawl_v1'") or {}).get('n') or 0)
            wrong=False
            try:c.build387.execute_grant(case_id=cid,grant_id=grant['grant_id'],grant_token=grant['grant_token'],identity=ident,confirmation='EXECUTE')
            except PermissionError:wrong=True
            checks['exact_live_required']=wrong
            checks['wrong_confirmation_no_job']=int((c.db.one("SELECT COUNT(*) n FROM phase15_jobs WHERE job_type='governed_crawl_v1'") or {}).get('n') or 0)==before
            out=c.build387.execute_grant(case_id=cid,grant_id=grant['grant_id'],grant_token=grant['grant_token'],identity=ident,confirmation=CONFIRM_EXECUTE)
            checks['one_job_enqueued']=out.get('jobs_enqueued')==1 and len(out.get('job_ids') or [])==1
            checks['executor_performs_no_fetch']=out.get('network_fetches_executed')==0 and out.get('direct_network_fetch_by_executor') is False
            checks['grant_consumed']=c.execution_authority_386.grant(case_id=cid,grant_id=grant['grant_id']).get('state')=='consumed_387'
            job=c.db.one('SELECT * FROM phase15_jobs WHERE job_id=?',(out['job_ids'][0],)) or {}; payload=json.loads(job.get('payload_json') or '{}')
            checks['job_queued_unclaimed']=job.get('status')=='queued' and int(job.get('attempts') or 0)==0 and not job.get('lease_owner')
            checks['workflow_provenance']=payload.get('phase16_case_workflow_v374') is True and payload.get('phase17_executor_v387') is True
            checks['scope_expansion_false']=payload.get('automatic_scope_expansion') is False
            verify=c.build387.verify_execution_dispatch(case_id=cid,dispatch_id=out['dispatch_id'])
            checks['dispatch_record_hash']=verify.get('record_hash_valid') is True
            checks['dispatch_jobs_present']=verify.get('jobs_present') is True and verify.get('all_jobs_workflow_tagged') is True
            replay=False
            try:c.build387.execute_grant(case_id=cid,grant_id=grant['grant_id'],grant_token=grant['grant_token'],identity=ident,confirmation=CONFIRM_EXECUTE)
            except PermissionError:replay=True
            checks['replay_blocked']=replay
            checks['one_dispatch_per_grant']=int((c.db.one('SELECT COUNT(*) n FROM execution_dispatch_387 WHERE grant_id=?',(grant['grant_id'],)) or {}).get('n') or 0)==1
            checks['token_not_in_dispatch']=grant['grant_token'] not in str(c.db.one('SELECT dispatch_json FROM execution_dispatch_387 WHERE dispatch_id=?',(out['dispatch_id'],)) or {})
            status=c.controlled_executor_387.status()
            checks['post_reservation_revalidation']=status.get('post_reservation_revalidation') is True
            checks['workflow_budget_recheck']=status.get('workflow_budget_recheck') is True
            checks['no_worker_claim_by_executor']=status.get('worker_claim_by_executor') is False
            checks['no_host_security_mutation']=status.get('host_security_mutation') is False
            code_fingerprint=c.build387.code_fingerprint()
    passed=sum(bool(v) for v in checks.values()); payload={'build':'387.0','code_fingerprint':code_fingerprint,'checks':checks,'passed':passed,'total':len(checks),'result':'pass' if passed==len(checks) else 'fail'}
    OUT.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n'); print(json.dumps(payload,indent=2,sort_keys=True)); return 0 if payload['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
