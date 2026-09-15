from __future__ import annotations
import hashlib,json,secrets,tempfile,time
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS,CONFIRM_FINALIZE
from eagleeye_pro.phase17.investigation_synthesis391 import CONFIRM_CLAIM_REVIEW,CONFIRM_HYPOTHESIS_REVIEW

PW='Benchmark392-Secure-Z9!'
def cand(c,cid,source,norm):
    raw=json.dumps({'s':source,'n':norm},sort_keys=True).encode(); oid='b392_'+secrets.token_hex(7); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T16:45:00+00:00'
    c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','bench392',now,hashlib.sha256(raw+b'r').hexdigest()))
    obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}; rr={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
    out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='bench392',result_row=rr,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized=norm,provenance={}); return out

def main():
    root=Path(__file__).resolve().parents[1]; N=1000
    with tempfile.TemporaryDirectory() as td:
        with AppContext(base_dir=td,actor='bench392') as c:
            a=c.team_identity_359.create_initial_admin(username='bench392',display_name='Reasoning Benchmark',password=PW); a={**a,'session_id':'bench392'}; cid=c.build380.team_create_case(identity=a,title='bench392',client='internal',purpose='qualification',legal_basis='public_data')['case_id']; _=c.execution_authority_386
            g=cand(c,cid,'gleif.lei',{'entity':'Example','value':1}); s=cand(c,cid,'sec.edgar',{'entity':'Example','value':2})
            r=c.build390.create_corroboration_review(case_id=cid,proposition='Benchmark proposition',candidate_stances={g['candidate_id']:'supports',s['candidate_id']:'contradicts'},identity=a); c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS); c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='contested_requires_analysis',confirmation=CONFIRM_FINALIZE)
            cl=c.build391.synthesize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a); cl=c.build391.review_synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a,disposition='contested_requires_analysis',rationale='Benchmark claim review preserves contradiction and analytical uncertainty.',confirmation=CONFIRM_CLAIM_REVIEW)
            h=c.build391.propose_hypothesis(case_id=cid,title='Benchmark hypothesis',statement='The differing observations may be time-dependent.',test_plan='Compare dated source records.',claim_relations={cl['claim_id']:'test_target'},identity=a); c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='Benchmark hypothesis remains testable and non-factual.',confirmation=CONFIRM_HYPOTHESIS_REVIEW)
            before=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n']))
            ws=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a); plan=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=ws['workspace_id'],identity=a)
            start=time.perf_counter(); violations=0
            for _ in range(N):
                w=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a); p=c.build392.propose_next_investigation_plan(case_id=cid,workspace_id=w['workspace_id'],identity=a); v=c.build392.verify_case_reasoning_workspace(case_id=cid,workspace_id=w['workspace_id'])
                if w['workspace_id']!=ws['workspace_id'] or p['plan_id']!=plan['plan_id'] or not v['valid'] or w['truth_determined'] or w['probability_assigned'] or p['execution_authority']:
                    violations+=1
            elapsed=time.perf_counter()-start
            after=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n']))
            violations+=int(before!=after); fp=c.build392.code_fingerprint(); payload={'build':'392.0','result':'pass' if violations==0 else 'fail','iterations':N,'violations':violations,'elapsed_seconds':elapsed,'reasoning_cycles_per_second':N/elapsed if elapsed else 0,'jobs_created':after[0]-before[0],'grants_created':after[1]-before[1],'evidence_promotions_created':after[2]-before[2],'legacy_kernel_hypotheses_created':after[3]-before[3],'workspace_id':ws['workspace_id'],'plan_id':plan['plan_id'],'code_fingerprint':fp}
            (root/'BENCHMARK_BUILD_392_REASONING.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2)); raise SystemExit(0 if violations==0 else 1)
if __name__=='__main__': main()
