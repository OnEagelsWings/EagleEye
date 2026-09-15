from __future__ import annotations
import hashlib,json,secrets,tempfile,time
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS,CONFIRM_FINALIZE
PW='Benchmark391-Orbit!'
def cand(c,cid,source,i):
 raw=f'{source}|{i}'.encode(); oid='b391_'+secrets.token_hex(7); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T15:30:00+00:00'; c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','bench391',now,hashlib.sha256(raw+b'r').hexdigest())); obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}; rr={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}; out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='bench391',result_row=rr,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized={'entity':'Example','value':i},provenance={}); return out
def main():
 root=Path(__file__).resolve().parents[1]; N=1000
 with tempfile.TemporaryDirectory() as td:
  with AppContext(base_dir=td,actor='bench391') as c:
   a=c.team_identity_359.create_initial_admin(username='bench391',display_name='Benchmark Lead 391',password=PW); a={**a,'session_id':'bench391'}; cid=c.build380.team_create_case(identity=a,title='bench391',client='internal',purpose='qualification',legal_basis='public_data')['case_id']; _=c.execution_authority_386; g=cand(c,cid,'gleif.lei',1); s=cand(c,cid,'sec.edgar',1)
   before=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n']))
   start=time.perf_counter(); violations=0
   for i in range(N):
    r=c.build390.create_corroboration_review(case_id=cid,proposition=f'Benchmark proposition {i}',candidate_stances={g['candidate_id']:'supports',s['candidate_id']:'supports'},identity=a); c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS); c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='ready_for_evidence_review',confirmation=CONFIRM_FINALIZE); cl=c.build391.synthesize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a)
    if cl['support_groups']!=2 or cl['truth_determined'] or cl['probability_assigned'] or cl['epistemic_status']!='candidate_claim_not_fact': violations+=1
   elapsed=time.perf_counter()-start; after=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM hypotheses_112') or {})['n'])); violations+=int(before!=after); fp=c.build391.code_fingerprint(); payload={'build':'391.0','result':'pass' if violations==0 else 'fail','iterations':N,'violations':violations,'elapsed_seconds':elapsed,'syntheses_per_second':N/elapsed if elapsed else 0,'jobs_created':after[0]-before[0],'grants_created':after[1]-before[1],'evidence_promotions_created':after[2]-before[2],'legacy_kernel_hypotheses_created':after[3]-before[3],'code_fingerprint':fp}; (root/'BENCHMARK_BUILD_391_SYNTHESIS.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2)); raise SystemExit(0 if violations==0 else 1)
if __name__=='__main__': main()
