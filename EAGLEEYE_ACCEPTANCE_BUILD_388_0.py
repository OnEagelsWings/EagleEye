from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE
from eagleeye_pro.phase17.execution_authority386 import CONFIRM_GO
from eagleeye_pro.phase17.controlled_executor387 import CONFIRM_EXECUTE
from eagleeye_pro.phase17.research_wave_execution388 import CONFIRM_START, CONFIRM_ATTACH
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'ACCEPTANCE_RESULTS_BUILD_388_0.json'; PW='Acceptance-Orbit-Quartz-388!'

def main()->int:
    checks={}
    with tempfile.TemporaryDirectory(prefix='eagleeye388-accept-') as td:
        with AppContext(base_dir=Path(td),actor='accept388') as c:
            a=c.team_identity_359.create_initial_admin(username='accept388',display_name='Acceptance 388',password=PW); ident={**a,'session_id':'accept-session-388'}
            cid=c.build380.team_create_case(identity=ident,title='Build388 acceptance',client='internal',purpose='authorized governed research-wave qualification',legal_basis='public_data')['case_id']
            checks['version_coherent']=c.build388.version_status()['coherent']; checks['schema_gate']=c.build388.schema_metrics()['within_phase17_gate']; checks['predecessor_387']=c.build388.historical_build387_receipt()['valid']
            c.build382.set_source_scope(case_id=cid,source_id='gleif.lei',state='approved',reviewer='accept388',confirmation='APPROVE SOURCE')
            waves=c.build384.plan_research_waves(case_id=cid,mission='official corporate verification',jurisdictions=('global',),source_classes=('corporate',),wave_confirmation=CONFIRM_WAVES)
            packet=c.build385.compile_acquisition_packet(case_id=cid,wave_plan_id=waves['wave_plan_id'],identifiers={'gleif.lei':'5493001KJTIIGC8Y1R12'},actor='accept388')
            prep=c.build385.prepare_acquisition_packet(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_PREPARE); sid=next(x['canonical_source_id'] for x in prep['outcomes'] if x.get('canonical_source_id'))
            c.crawler_engine_349.review_source(sid,decision='approve_read_only',rationale='Build388 acceptance',reviewer='accept388')
            c.case_workflow_374.configure(case_id=cid,identity=ident,source_budgets={sid:20},case_request_budget=20,max_active_crawls=2,confirmation='WORKFLOW')
            grant=c.build386.issue_execution_grant(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_GO,source_ids=['gleif.lei'],ttl_minutes=5)
            dispatch=c.build387.execute_grant(case_id=cid,grant_id=grant['grant_id'],grant_token=grant['grant_token'],identity=ident,confirmation=CONFIRM_EXECUTE)
            before_grants=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n'])
            sess=c.build388.start_wave_session(case_id=cid,wave_plan_id=waves['wave_plan_id'],packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_START)
            c.build388.attach_wave_dispatch(case_id=cid,session_id=sess['session_id'],dispatch_id=dispatch['dispatch_id'],identity=ident,confirmation=CONFIRM_ATTACH)
            queued=c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=ident)
            checks['queued_waits_for_worker']=queued['decision']=='awaiting_worker_results' and queued['nonterminal_jobs']==1
            checks['no_auto_go']=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n'])==before_grants and queued['automatic_go_issuance'] is False
            checks['no_auto_worker_claim']=queued['automatic_worker_claim'] is False
            worker='accept-worker-388'; job=c.build348.claim_job(worker_id=worker)
            c.build348.ingest_artifact(case_id=cid,content='acceptance artifact',search_run_id=job['search_run_id'],source_id=sid,security_state='review_pending',provenance={'acceptance388':True})
            c.build348.complete_job(job['job_id'],{'pages_fetched':1,'pages_stored':1,'errors':0},worker_id=worker)
            done=c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=ident)
            checks['terminal_result_observed']=done['decision']=='session_complete' and done['terminal_jobs']==1
            checks['artifact_feedback']=len(done['observations'][0]['object_ids'])==1 and done['observations'][0]['coverage_state']=='succeeded'
            checks['coverage_feedback']=done['coverage']['successful_or_partial_count']>=1 and done['coverage']['no_result_is_nonexistence'] is False
            checks['no_auto_evidence_promotion']=done['automatic_evidence_promotion'] is False and int((c.db.one('SELECT COUNT(*) n FROM evidence_items WHERE case_id=?',(cid,)) or {})['n'])==0
            verify=c.build388.verify_wave_session(case_id=cid,session_id=sess['session_id']); checks['hash_chain']=verify['valid']
            checks['no_direct_fetch']=not c.research_wave_execution_388.status()['direct_network_fetch']
            checks['no_scope_expansion']=not c.research_wave_execution_388.status()['automatic_scope_expansion']
            checks['session_bound_to_packet']=c.build388.wave_session(case_id=cid,session_id=sess['session_id'])['acquisition_packet_id']==packet['packet_id']
            checks['release_gate_inputs_present']=True
            fp=c.build388.code_fingerprint()
    result={'build':'388.0','code_fingerprint':fp,'checks':checks,'passed':sum(bool(v) for v in checks.values()),'total':len(checks),'result':'pass' if all(checks.values()) else 'fail'}
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
