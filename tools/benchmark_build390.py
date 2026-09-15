from __future__ import annotations
import hashlib,json,secrets,tempfile,time
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS
PW='Benchmark390-Orbit!'
def cand(c,cid,source,i):
 raw=f'{source}|{i}'.encode(); oid='b390_'+secrets.token_hex(7); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T12:00:00+00:00'
 c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','bench390',now,hashlib.sha256(raw+b'r').hexdigest()))
 obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}; result={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
 out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='bench390',result_row=result,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized={'entity':'Example','value':i%10},provenance={}); return out

def main():
 root=Path(__file__).resolve().parents[1]; N=1000
 with tempfile.TemporaryDirectory() as td:
  with AppContext(base_dir=td,actor='bench390') as c:
   a=c.team_identity_359.create_initial_admin(username='bench390',display_name='Bench 390',password=PW); a={**a,'session_id':'bench390'}; cid=c.build380.team_create_case(identity=a,title='bench390',client='internal',purpose='qualification',legal_basis='public_data')['case_id']
   g=cand(c,cid,'gleif.lei',1); s=cand(c,cid,'sec.edgar',1); arc=cand(c,cid,'internet_archive.metadata',1)
   jb=int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']); gb=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']); pb=int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n'])
   start=time.perf_counter(); violations=0
   for i in range(N):
    r=c.build390.create_corroboration_review(case_id=cid,proposition=f'Benchmark proposition {i}',candidate_stances={g['candidate_id']:'supports',s['candidate_id']:'supports',arc['candidate_id']:'supports'},identity=a)
    out=c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS)
    if out['support_groups']!=2 or out['truth_determined'] or out['automatic_evidence_promotion']: violations+=1
   elapsed=time.perf_counter()-start
   ja=int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']); ga=int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']); pa=int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n'])
   violations += int((jb,gb,pb)!=(ja,ga,pa)); fp=c.build390.code_fingerprint(); payload={'build':'390.0','result':'pass' if violations==0 else 'fail','iterations':N,'violations':violations,'elapsed_seconds':elapsed,'assessments_per_second':N/elapsed if elapsed else 0,'jobs_created':ja-jb,'grants_created':ga-gb,'evidence_promotions_created':pa-pb,'code_fingerprint':fp}
   (root/'BENCHMARK_BUILD_390_CORROBORATION.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2)); raise SystemExit(0 if violations==0 else 1)
if __name__=='__main__': main()
