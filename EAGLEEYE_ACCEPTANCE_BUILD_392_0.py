from __future__ import annotations
import hashlib,json,secrets,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS,CONFIRM_FINALIZE
from eagleeye_pro.phase17.investigation_synthesis391 import CONFIRM_CLAIM_REVIEW,CONFIRM_HYPOTHESIS_REVIEW
from eagleeye_pro.phase17.case_reasoning392 import CONFIRM_PLAN_REVIEW,CONFIRM_KERNEL_ADMISSION

PW='Acceptance392-Secure-Z9!'

def cand(c,cid,source,norm):
    raw=json.dumps({'s':source,'n':norm},sort_keys=True).encode(); oid='a392_'+secrets.token_hex(7); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T16:45:00+00:00'
    c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','accept392',now,hashlib.sha256(raw+b'r').hexdigest()))
    obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}; rr={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
    out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='accept392',result_row=rr,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized=norm,provenance={}); return out

def main():
    root=Path(__file__).resolve().parent; checks={}
    with tempfile.TemporaryDirectory() as td:
        with AppContext(base_dir=td,actor='accept392') as c:
            a=c.team_identity_359.create_initial_admin(username='accept392',display_name='Reasoning Reviewer',password=PW); a={**a,'session_id':'accept392'}
            cid=c.build380.team_create_case(identity=a,title='accept392',client='internal',purpose='reasoning qualification',legal_basis='public_data')['case_id']; _=c.execution_authority_386
            g=cand(c,cid,'gleif.lei',{'name':'Example GmbH','status':'ACTIVE'}); s=cand(c,cid,'sec.edgar',{'name':'Example GmbH','status':'INACTIVE'})
            r=c.build390.create_corroboration_review(case_id=cid,proposition='Example GmbH is active',candidate_stances={g['candidate_id']:'supports',s['candidate_id']:'contradicts'},identity=a)
            c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS)
            c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='contested_requires_analysis',confirmation=CONFIRM_FINALIZE)
            cl=c.build391.synthesize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a)
            cl=c.build391.review_synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a,disposition='contested_requires_analysis',rationale='Contradiction preserved for structured analysis and further evidence work.',confirmation=CONFIRM_CLAIM_REVIEW)
            h=c.build391.propose_hypothesis(case_id=cid,title='Timing explanation',statement='The contradictory observations may reflect different effective dates.',test_plan='Compare dated filings, registry history and effective dates.',claim_relations={cl['claim_id']:'test_target'},identity=a)
            h=c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='The explanation is testable and remains explicitly hypothetical.',confirmation=CONFIRM_HYPOTHESIS_REVIEW)
            c.phase17_runtime_384.repository.record_coverage(case_id=cid,source_id='gleif.lei',state='failed',evidence_ref='worker:accept392',detail='simulated failed acquisition')
            before=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n']))
            ws=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a)
            plan=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
            plan=c.build392.review_reasoning_plan(case_id=cid,plan_id=plan['plan_id'],identity=a,disposition='approve_for_investigator_review',rationale='Reviewed contested evidence, test priorities and external authorization boundaries.',confirmation=CONFIRM_PLAN_REVIEW)
            kb=c.build392.admit_reasoning_plan_to_kernel(case_id=cid,plan_id=plan['plan_id'],identity=a,confirmation=CONFIRM_KERNEL_ADMISSION)
            feed=c.build392.ai_case_reasoning_feed(case_id=cid,identity=a)
            after=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n']))
            checks={
                'version_coherent':c.build392.version_status()['coherent'],
                'schema_integrity':c.build392.schema_metrics()['within_phase17_gate'],
                'predecessor_391':c.build392.historical_build391_receipt()['valid'],
                'workspace_contested':ws['reasoning_state']=='contested_analysis_required',
                'counterevidence_issue':any(x['issue_type']=='counterevidence_conflict' for x in ws['issues']),
                'coverage_gap_preserved':any(x['issue_type']=='research_gap' for x in ws['issues']),
                'argument_graph':any(x['from_type']=='evidence_candidate' and x['relation']=='contradicts' for x in ws['arguments']) and any(x['from_type']=='claim' and x['to_type']=='hypothesis' for x in ws['arguments']),
                'workspace_hash_valid':c.build392.verify_case_reasoning_workspace(case_id=cid,workspace_id=ws['workspace_id'])['valid'],
                'plan_reviewed':plan['plan_status']=='reviewed_plan' and plan['analyst_disposition']=='approve_for_investigator_review',
                'plan_hash_valid':c.build392.verify_reasoning_plan(case_id=cid,plan_id=plan['plan_id'])['valid'],
                'external_actions_require_go':all((not x['requires_external_execution']) or x['requires_go'] for x in plan['actions']),
                'no_execution_authority':not plan['execution_authority'] and all(not x['execution_authority'] for x in plan['actions']),
                'kernel_notebook_bridge':bool(kb.get('kernel_entry_id')) and kb['execution_authority'] is False,
                'no_jobs_grants_promotions_or_legacy_hypotheses':before==after,
                'feed_boundaries':feed['truth_determined'] is False and feed['probability_assigned'] is False and feed['execution_authority'] is False and feed['automatic_go_issuance'] is False,
                'epistemic_layers_preserved':feed['epistemic_layers_preserved'] is True,
                'no_direct_fetch':c.case_reasoning_392.status()['direct_network_fetch'] is False,
                'human_plan_review_required':c.case_reasoning_392.status()['human_plan_review_required'] is True,
            }
            fp=c.build392.code_fingerprint()
    result='pass' if all(checks.values()) else 'fail'; payload={'build':'392.0','result':result,'passed':sum(checks.values()),'total':len(checks),'checks':checks,'code_fingerprint':fp}; (root/'ACCEPTANCE_RESULTS_BUILD_392_0.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2)); raise SystemExit(0 if result=='pass' else 1)
if __name__=='__main__': main()
