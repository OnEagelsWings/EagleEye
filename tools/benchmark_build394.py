from __future__ import annotations
import hashlib,json,secrets,tempfile,time
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS,CONFIRM_FINALIZE
from eagleeye_pro.phase17.investigation_synthesis391 import CONFIRM_CLAIM_REVIEW,CONFIRM_HYPOTHESIS_REVIEW
from eagleeye_pro.phase17.discussion_revision394 import CONFIRM_REVISION_REVIEW,CONFIRM_APPLY_REVISION

PW='Benchmark394-Secure-Vector-Z9!'

def cand(c,cid,source,norm):
    raw=json.dumps({'s':source,'n':norm},sort_keys=True).encode(); oid='b394_'+secrets.token_hex(7); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T22:15:00+00:00'
    c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','bench394',now,hashlib.sha256(raw+b'r').hexdigest()))
    obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}; rr={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
    out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='bench394',result_row=rr,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized=norm,provenance={}); return out

def side_counts(c):
    names=['phase15_jobs','execution_grant_386','evidence_candidate_promotion_389','hypotheses_112','investigation_claim_391','investigation_hypothesis_391','reasoning_plan_392']
    return tuple(int((c.db.one(f'SELECT COUNT(*) n FROM {n}') or {})['n']) for n in names)

def main():
    root=Path(__file__).resolve().parents[1]; TURNS=500; REVISIONS=50
    with tempfile.TemporaryDirectory() as td:
        with AppContext(base_dir=td,actor='bench394') as c:
            a=c.team_identity_359.create_initial_admin(username='bench394',display_name='Discussion Benchmark',password=PW); a={**a,'session_id':'bench394'}
            cid=c.build380.team_create_case(identity=a,title='bench394',client='internal',purpose='discussion revision benchmark',legal_basis='public_data')['case_id']; _=c.execution_authority_386
            g=cand(c,cid,'gleif.lei',{'entity':'Example','value':1}); s=cand(c,cid,'sec.edgar',{'entity':'Example','value':2})
            r=c.build390.create_corroboration_review(case_id=cid,proposition='Benchmark proposition',candidate_stances={g['candidate_id']:'supports',s['candidate_id']:'contradicts'},identity=a); c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS); c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='contested_requires_analysis',confirmation=CONFIRM_FINALIZE)
            cl=c.build391.synthesize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a); cl=c.build391.review_synthesis_claim(case_id=cid,claim_id=cl['claim_id'],identity=a,disposition='contested_requires_analysis',rationale='Benchmark claim preserves contradiction and uncertainty.',confirmation=CONFIRM_CLAIM_REVIEW)
            h1=c.build391.propose_hypothesis(case_id=cid,title='Benchmark timing',statement='Observations may be time-dependent.',test_plan='Compare dated source records.',claim_relations={cl['claim_id']:'test_target'},identity=a); h1=c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h1['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='Benchmark hypothesis remains testable and non-factual.',confirmation=CONFIRM_HYPOTHESIS_REVIEW)
            h2=c.build391.propose_hypothesis(case_id=cid,title='Benchmark scope',statement='Observations may use different entity scope.',test_plan='Resolve identifiers and compare scope.',claim_relations={cl['claim_id']:'test_target'},identity=a); h2=c.build391.review_synthesis_hypothesis(case_id=cid,hypothesis_id=h2['hypothesis_id'],identity=a,disposition='retain_for_testing',rationale='Competing benchmark hypothesis remains testable.',confirmation=CONFIRM_HYPOTHESIS_REVIEW)
            ws=c.build392.create_case_reasoning_workspace(case_id=cid,identity=a); d393=c.build393.create_investigator_dialogue(case_id=cid,workspace_id=ws['workspace_id'],identity=a); d=c.build394.create_investigator_discussion(case_id=cid,dialogue_session_id=d393['session_id'],identity=a)
            before=side_counts(c); violations=0
            start=time.perf_counter(); parent=''
            types=['argument','counterargument','clarification','synthesis']
            for i in range(TURNS):
                t=c.build394.discuss_case(case_id=cid,discussion_id=d['discussion_id'],prompt=f'benchmark discussion turn {i}',turn_type=types[i%len(types)],parent_turn_id=parent,identity=a)
                parent=t['turn_id']
                if t['response']['truth_determined'] or t['response']['probability_assigned'] or t['response']['automatic_upstream_mutation'] or t['response']['execution_authority'] or not c.build394.verify_discussion_turn(case_id=cid,turn_id=t['turn_id'])['valid']:
                    violations+=1
            turn_elapsed=time.perf_counter()-start
            comp=c.build394.compare_discussion_hypotheses(case_id=cid,discussion_id=d['discussion_id'],hypothesis_ids=[h1['hypothesis_id'],h2['hypothesis_id']],identity=a)
            violations+=int(comp['comparison']['winner_selected'] or comp['comparison']['probability_assigned'])
            rev_start=time.perf_counter(); last_version=None
            for i in range(REVISIONS):
                p=c.build394.create_versioned_revision_proposal(case_id=cid,discussion_id=d['discussion_id'],target_type='claim',target_id=cl['claim_id'],patch={'analyst_note':f'benchmark append-only revision {i}'},rationale='Benchmark append-only version lineage without changing evidence-derived metrics.',source_turn_id=parent,identity=a)
                c.build394.review_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,disposition='approve_versioned_revision',rationale='Benchmark review approves only an append-only working-copy note.',confirmation=CONFIRM_REVISION_REVIEW)
                v=c.build394.apply_versioned_revision(case_id=cid,proposal_id=p['proposal_id'],identity=a,confirmation=CONFIRM_APPLY_REVISION)
                if v['version_number']!=i+1 or v['execution_authority'] or not c.build394.verify_versioned_revision(case_id=cid,version_id=v['version_id'])['valid']:
                    violations+=1
                if last_version and v['parent_version_id']!=last_version: violations+=1
                last_version=v['version_id']
            rev_elapsed=time.perf_counter()-rev_start
            after=side_counts(c); violations+=int(before!=after)
            fp=c.build394.code_fingerprint(); payload={
                'build':'394.0','result':'pass' if violations==0 else 'fail','discussion_turns':TURNS,'versioned_revisions':REVISIONS,'violations':violations,
                'discussion_elapsed_seconds':turn_elapsed,'discussion_turns_per_second':TURNS/turn_elapsed if turn_elapsed else 0,
                'revision_elapsed_seconds':rev_elapsed,'versioned_revisions_per_second':REVISIONS/rev_elapsed if rev_elapsed else 0,
                'jobs_created':after[0]-before[0],'grants_created':after[1]-before[1],'evidence_promotions_created':after[2]-before[2],
                'legacy_kernel_hypotheses_created':after[3]-before[3],'claims_created':after[4]-before[4],'hypotheses_created':after[5]-before[5],'reasoning_plans_created':after[6]-before[6],
                'code_fingerprint':fp,
            }
            (root/'BENCHMARK_BUILD_394_DISCUSSION.json').write_text(json.dumps(payload,indent=2,sort_keys=True),encoding='utf-8'); print(json.dumps(payload,indent=2)); raise SystemExit(0 if violations==0 else 1)
if __name__=='__main__': main()
