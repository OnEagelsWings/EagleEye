from __future__ import annotations
import hashlib,json,secrets,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.phase17.evidence_review390 import CONFIRM_ASSESS,CONFIRM_FINALIZE,CONFIRM_INDEPENDENCE
PW='Acceptance390-Orbit!'

def cand(c,cid,source,norm):
 raw=json.dumps({'s':source,'n':norm},sort_keys=True).encode(); oid='a390_'+secrets.token_hex(7); sha=hashlib.sha256(raw).hexdigest(); now='2026-09-13T12:00:00+00:00'
 c.db.execute("INSERT INTO phase15_objects(object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,cid,'','canon_'+source,'local',oid,sha,len(raw),'application/json','review_pending','{}','accept390',now,hashlib.sha256(raw+b'r').hexdigest()))
 obj={'object_id':oid,'sha256':sha,'media_type':'application/json','security_state':'review_pending'}; result={'wave_number':1,'phase17_source_id':source,'canonical_source_id':'canon_'+source,'dispatch_id':'d'+oid,'job_id':'j'+oid,'crawl_run_id':'c'+oid,'search_run_id':'s'+oid}
 out,_=c.result_intake_389._insert_candidate(case_id=cid,session_id='accept390',result_row=result,obj=obj,parse_run_id='p'+oid,record_index=0,candidate_type='normalized_record',normalized=norm,provenance={}); return out

def main():
 root=Path(__file__).resolve().parent; checks={}
 with tempfile.TemporaryDirectory() as td:
  with AppContext(base_dir=td,actor='accept390') as c:
   a=c.team_identity_359.create_initial_admin(username='accept390',display_name='Accept 390',password=PW); a={**a,'session_id':'accept390'}; cid=c.build380.team_create_case(identity=a,title='accept390',client='internal',purpose='qualification',legal_basis='public_data')['case_id']
   g=cand(c,cid,'gleif.lei',{'name':'Example GmbH','status':'ACTIVE'}); s=cand(c,cid,'sec.edgar',{'name':'Example GmbH','status':'ACTIVE'}); arc=cand(c,cid,'internet_archive.metadata',{'name':'Example GmbH','status':'ACTIVE'})
   dup=cand(c,cid,'gleif.lei',{'name':'Example GmbH','status':'ACTIVE'}); unk=cand(c,cid,'custom.unknown',{'name':'X'})
   r=c.build390.create_corroboration_review(case_id=cid,proposition='Example GmbH is active',candidate_stances={g['candidate_id']:'supports',s['candidate_id']:'supports',arc['candidate_id']:'supports',dup['candidate_id']:'supports'},identity=a)
   ass=c.build390.assess_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,confirmation=CONFIRM_ASSESS)
   ru=c.build390.create_corroboration_review(case_id=cid,proposition='Unknown source claim',candidate_stances={unk['candidate_id']:'supports'},identity=a); au=c.build390.assess_corroboration_review(case_id=cid,review_id=ru['review_id'],identity=a,confirmation=CONFIRM_ASSESS)
   before=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']))
   fin=c.build390.finalize_corroboration_review(case_id=cid,review_id=r['review_id'],identity=a,disposition='ready_for_evidence_review',confirmation=CONFIRM_FINALIZE)
   after=(int((c.db.one('SELECT COUNT(*) n FROM phase15_jobs') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM execution_grant_386') or {})['n']),int((c.db.one('SELECT COUNT(*) n FROM evidence_candidate_promotion_389') or {})['n']))
   profiles=c.build390.source_independence_profiles(); ap=next(x for x in profiles if x['phase17_source_id']=='internet_archive.metadata')
   checks={'version_coherent':c.build390.version_status()['coherent'],'schema_integrity':c.build390.schema_metrics()['within_phase17_gate'],'predecessor_389':c.build390.historical_build389_receipt()['valid'],'two_independent_primary_groups':ass['support_groups']==2,'duplicate_not_double_counted':ass['exact_duplicate_links']>=1,'archive_not_counted':ass['non_countable_observations']>=1 and ap['countable_default'] is False,'unknown_fails_closed':au['support_groups']==0 and au['unresolved_observations']==1,'no_truth':ass['truth_determined'] is False and ass['probability_assigned'] is False,'no_auto_promotion':ass['automatic_evidence_promotion'] is False,'no_jobs_or_grants':before==after,'finalize_no_truth':fin['truth_determined'] is False,'assessment_hash_valid':c.build390.verify_corroboration_assessment(case_id=cid,assessment_id=ass['assessment_id'])['valid'],'ai_feed_review_only':c.build390.ai_corroboration_feed(case_id=cid,identity=a)['candidate_review_only'],'direct_network_fetch_false':c.evidence_review_390.status()['direct_network_fetch'] is False}
   fp=c.build390.code_fingerprint()
 result='pass' if all(checks.values()) else 'fail'; payload={'build':'390.0','result':result,'passed':sum(checks.values()),'total':len(checks),'checks':checks,'code_fingerprint':fp}
 (root/'ACCEPTANCE_RESULTS_BUILD_390_0.json').write_text(json.dumps(payload,indent=2,sort_keys=True)); print(json.dumps(payload,indent=2)); raise SystemExit(0 if result=='pass' else 1)
if __name__=='__main__': main()
