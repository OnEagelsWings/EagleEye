from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.jurisdiction_intelligence384 import CONFIRM_WAVES
from eagleeye_pro.phase17.acquisition_orchestrator385 import CONFIRM_PREPARE
from eagleeye_pro.phase17.execution_authority386 import CONFIRM_GO
from eagleeye_pro.phase17.controlled_executor387 import CONFIRM_EXECUTE
from eagleeye_pro.phase17.research_wave_execution388 import CONFIRM_START,CONFIRM_ATTACH
from eagleeye_pro.phase17.result_intake389 import CONFIRM_PROMOTE
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'ACCEPTANCE_RESULTS_BUILD_389_0.json'; PW='Quartz-Orbit-Accept!389'

def main()->int:
    checks={}
    with tempfile.TemporaryDirectory(prefix='eagleeye389-accept-') as td:
        with AppContext(base_dir=Path(td),actor='accept389') as c:
            a=c.team_identity_359.create_initial_admin(username='accept389',display_name='Acceptance 389',password=PW); ident={**a,'session_id':'accept389-session'}
            cid=c.build380.team_create_case(identity=ident,title='Build389 acceptance',client='internal',purpose='authorized result intake qualification',legal_basis='public_data')['case_id']
            checks['version_coherent']=c.build389.version_status()['coherent']; checks['schema_gate']=c.build389.schema_metrics()['within_phase17_gate']; checks['predecessor_388']=c.build389.historical_build388_receipt()['valid']
            c.build382.set_source_scope(case_id=cid,source_id='gleif.lei',state='approved',reviewer='accept389',confirmation='APPROVE SOURCE')
            waves=c.build384.plan_research_waves(case_id=cid,mission='official corporate verification',jurisdictions=('global',),source_classes=('corporate',),wave_confirmation=CONFIRM_WAVES)
            packet=c.build385.compile_acquisition_packet(case_id=cid,wave_plan_id=waves['wave_plan_id'],identifiers={'gleif.lei':'5493001KJTIIGC8Y1R12'},actor='accept389')
            prep=c.build385.prepare_acquisition_packet(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_PREPARE); sid=next(x['canonical_source_id'] for x in prep['outcomes'] if x.get('canonical_source_id'))
            c.crawler_engine_349.review_source(sid,decision='approve_read_only',rationale='Build389 acceptance',reviewer='accept389')
            c.case_workflow_374.configure(case_id=cid,identity=ident,source_budgets={sid:20},case_request_budget=20,max_active_crawls=2,confirmation='WORKFLOW')
            grant=c.build386.issue_execution_grant(case_id=cid,packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_GO,source_ids=['gleif.lei']); dispatch=c.build387.execute_grant(case_id=cid,grant_id=grant['grant_id'],grant_token=grant['grant_token'],identity=ident,confirmation=CONFIRM_EXECUTE)
            sess=c.build388.start_wave_session(case_id=cid,wave_plan_id=waves['wave_plan_id'],packet_id=packet['packet_id'],identity=ident,confirmation=CONFIRM_START); c.build388.attach_wave_dispatch(case_id=cid,session_id=sess['session_id'],dispatch_id=dispatch['dispatch_id'],identity=ident,confirmation=CONFIRM_ATTACH)
            worker='accept-worker-389'; job=c.build348.claim_job(worker_id=worker); body={'data':[{'id':'5493001KJTIIGC8Y1R12','attributes':{'lei':'5493001KJTIIGC8Y1R12','entity':{'legalName':{'name':'Acceptance GmbH'},'status':'ACTIVE'}}}]}; obj=c.build348.ingest_artifact(case_id=cid,content=json.dumps(body),media_type='application/json',search_run_id=job['search_run_id'],source_id=sid,security_state='review_pending',provenance={'url':'https://example.invalid/accept389.json'}); c.build348.complete_job(job['job_id'],{'pages_fetched':1,'pages_stored':1,'errors':0},worker_id=worker); c.build388.reconcile_wave_session(case_id=cid,session_id=sess['session_id'],identity=ident)
            jobs_before=int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']); grants_before=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']); evidence_before=int((c.db.one('SELECT COUNT(*) n FROM evidence_items WHERE case_id=?',(cid,)) or {})['n'])
            intake=c.build389.normalize_wave_results(case_id=cid,session_id=sess['session_id'],identity=ident); cand=intake['candidates'][0]
            checks['normalized_candidate']=intake['candidate_count']==1 and cand['normalized'].get('lei')=='5493001KJTIIGC8Y1R12'; checks['raw_provenance_bound']=cand['object_id']==obj['object_id'] and bool(cand['provenance'].get('object_sha256')); checks['candidate_only']=cand['truth_assigned'] is False and cand['review_status']=='needs_review'; checks['candidate_hash_valid']=c.build389.verify_evidence_candidate(case_id=cid,candidate_id=cand['candidate_id'])['valid']; checks['ai_feed_candidate_only']=c.build389.ai_evidence_candidates(case_id=cid,identity=ident)['candidate_only'] is True
            checks['no_auto_jobs']=int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n'])==jobs_before; checks['no_auto_grants']=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n'])==grants_before; checks['no_auto_evidence']=int((c.db.one('SELECT COUNT(*) n FROM evidence_items WHERE case_id=?',(cid,)) or {})['n'])==evidence_before
            try: c.build389.promote_evidence_candidate(case_id=cid,candidate_id=cand['candidate_id'],identity=ident,confirmation='PROMOTE'); checks['exact_promotion_confirmation']=False
            except PermissionError: checks['exact_promotion_confirmation']=True
            promoted=c.build389.promote_evidence_candidate(case_id=cid,candidate_id=cand['candidate_id'],identity=ident,confirmation=CONFIRM_PROMOTE); checks['vault_needs_review']=promoted['vault_artifact']['review_status']=='needs_review' and promoted['evidence_review_required'] is True; checks['promotion_not_truth_acceptance']=promoted['automatic_truth_acceptance'] is False and int((c.db.one('SELECT COUNT(*) n FROM evidence_items WHERE case_id=?',(cid,)) or {})['n'])==evidence_before
            status=c.result_intake_389.status(); checks['no_direct_fetch']=not status['direct_network_fetch']; checks['no_auto_identity_merge']=not status['automatic_identity_merge']; checks['source_observations_preserved']=status['independent_source_observations_preserved']; fp=c.build389.code_fingerprint()
    result={'build':'389.0','code_fingerprint':fp,'checks':checks,'passed':sum(bool(v) for v in checks.values()),'total':len(checks),'result':'pass' if all(checks.values()) else 'fail'}; OUT.write_text(json.dumps(result,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(result,indent=2,sort_keys=True)); return 0 if result['result']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
