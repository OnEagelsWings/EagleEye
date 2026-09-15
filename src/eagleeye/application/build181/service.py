from __future__ import annotations
import hashlib,json
from typing import Any,Mapping,Sequence
from eagleeye_pro.core.database import dumps,loads,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
class Build181MultiAnalystWorkspaceService:
 BUILD='181.0'
 ROLES={'lead','analyst','reviewer','observer'}
 SOURCE_PROFILES=[
 {'source_id':'c2pa_conformance_explorer','title':'C2PA Conformance Explorer','category':'provenance_trust','access_mode':'official_public','base_url':'https://spec.c2pa.org','docs_url':'https://spec.c2pa.org/conformance-explorer/','constraints':['conformance_not_content_truth','trust_list_version_required']},
 {'source_id':'c2pa_public_testfiles','title':'C2PA Public Test Files','category':'verification_benchmark','access_mode':'official_public','base_url':'https://spec.c2pa.org','docs_url':'https://spec.c2pa.org/public-testfiles/','constraints':['test_material_only','license_review']},
 {'source_id':'cai_verify_reference','title':'Content Authenticity Initiative Verify','category':'provenance_validator','access_mode':'guided_public','base_url':'https://verify.contentauthenticity.org','docs_url':'https://opensource.contentauthenticity.org/docs/getting-started/inspect/','constraints':['no_external_upload_by_default','reference_validation_only']},
 {'source_id':'weverify_toolkit','title':'InVID-WeVerify Verification Toolkit','category':'verification_toolkit','access_mode':'guided_public','base_url':'https://weverify.eu','docs_url':'https://weverify.eu/verification-plugin/','constraints':['human_in_the_loop','tool_outputs_not_verdicts']},
 {'source_id':'weverify_deepfake_reference','title':'WeVerify Deepfake Detector','category':'detector_reference','access_mode':'research_reference','base_url':'https://weverify.eu','docs_url':'https://weverify.eu/tools/deepfake-detector/','constraints':['research_reference_only','independent_validation_required']},
 {'source_id':'c2pa_trust_list','title':'C2PA Official Trust List','category':'provenance_trust','access_mode':'official_public','base_url':'https://c2pa.org','docs_url':'https://c2pa.org/conformance/','constraints':['legacy_itl_distinguished','revocation_and_timestamp_checked']},
 ]
 def __init__(self,db:Any,audit:Any,*,authenticity:Any,pattern_engine:Any,graph:Any,actor:str='system'):
  self.db,self.audit,self.authenticity,self.pattern,self.graph,self.actor=db,audit,authenticity,pattern_engine,graph,actor
 def seed_sources(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!='WORKSPACE SOURCES 181 ERWEITERN':raise PermissionError('explicit source approval required')
  for p in self.SOURCE_PROFILES:
   payload={**p,'status':'DOCUMENTED'};self.db.execute('INSERT OR REPLACE INTO workspace_source_profiles_181 VALUES(?,?,?,?,?,?,?,?,?,?)',(p['source_id'],p['title'],p['category'],p['access_mode'],p['base_url'],p['docs_url'],dumps(p['constraints']),'DOCUMENTED',now_ts(),_hash(payload)))
  return {'created':len(self.SOURCE_PROFILES),'production_active':0,'review_required':True}
 def add_member(self,case_id:str,*,principal:str,role:str,added_by:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'WORKSPACE 181 {case_id} MITGLIED HINZUFUEGEN':raise PermissionError('explicit membership approval required')
  if role not in self.ROLES:raise ValueError('invalid role')
  mid=new_id('wm181');p={'member_id':mid,'case_id':case_id,'principal':principal,'role':role,'status':'active','added_by':added_by}
  self.db.execute('INSERT OR REPLACE INTO workspace_members_181 VALUES(?,?,?,?,?,?,?,?)',(mid,case_id,principal,role,'active',added_by,now_ts(),_hash(p)));self._event(case_id,'member_added',p);return p
 def create_task(self,case_id:str,*,title:str,task_type:str,created_by:str,assignee:str|None=None,priority:str='normal',due_at:str|None=None,evidence_refs:Sequence[str]=(),confirmation:str)->dict[str,Any]:
  if confirmation!=f'WORKSPACE 181 {case_id} AUFGABE ANLEGEN':raise PermissionError('explicit task approval required')
  if priority not in {'low','normal','high','critical'}:raise ValueError('invalid priority')
  if assignee and not self.db.one("SELECT 1 FROM workspace_members_181 WHERE case_id=? AND principal=? AND status='active'",(case_id,assignee)):raise PermissionError('assignee is not an active member')
  tid=new_id('wt181');p={'task_id':tid,'case_id':case_id,'title':title,'task_type':task_type,'assignee':assignee,'status':'open','priority':priority,'due_at':due_at,'evidence_refs':list(evidence_refs),'created_by':created_by}
  ts=now_ts();self.db.execute('INSERT INTO workspace_tasks_181 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,case_id,title,task_type,assignee,'open',priority,due_at,dumps(list(evidence_refs)),created_by,ts,ts,_hash(p)));self._event(case_id,'task_created',p);return p
 def review(self,case_id:str,*,target_type:str,target_id:str,reviewer:str,decision:str,note:str='',confidence:float|None=None,confirmation:str)->dict[str,Any]:
  if confirmation!=f'WORKSPACE 181 {target_id} PRUEFEN':raise PermissionError('explicit review required')
  if decision not in {'supported','rejected','inconclusive','needs_more_evidence'}:raise ValueError('invalid decision')
  member=self.db.one("SELECT role FROM workspace_members_181 WHERE case_id=? AND principal=? AND status='active'",(case_id,reviewer))
  if not member or member['role'] not in {'lead','reviewer'}:raise PermissionError('review role required')
  rid=new_id('wr181');p={'review_id':rid,'case_id':case_id,'target_type':target_type,'target_id':target_id,'reviewer':reviewer,'decision':decision,'confidence':confidence,'note':note}
  self.db.execute('INSERT OR REPLACE INTO workspace_reviews_181 VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,case_id,target_type,target_id,reviewer,decision,confidence,note,now_ts(),_hash(p)));state=self._review_state(case_id,target_type,target_id);self._event(case_id,'review_recorded',{**p,'state':state});return {'review':p,'state':state}
 def _review_state(self,case_id:str,target_type:str,target_id:str)->dict[str,Any]:
  rows=[dict(r) for r in self.db.all('SELECT reviewer,decision FROM workspace_reviews_181 WHERE case_id=? AND target_type=? AND target_id=?',(case_id,target_type,target_id))];dec={r['decision'] for r in rows}
  status='conflict' if 'supported' in dec and 'rejected' in dec else 'quorum_supported' if sum(r['decision']=='supported' for r in rows)>=2 else 'quorum_rejected' if sum(r['decision']=='rejected' for r in rows)>=2 else 'pending'
  if status=='conflict':self._open_conflict(case_id,target_type,target_id,rows)
  return {'status':status,'reviews':len(rows),'required_quorum':2}
 def _open_conflict(self,case_id:str,target_type:str,target_id:str,rows:Sequence[Mapping[str,Any]])->None:
  if self.db.one("SELECT 1 FROM workspace_conflicts_181 WHERE target_type=? AND target_id=? AND status='open'",(target_type,target_id)):return
  cid=new_id('wc181');p={'conflict_id':cid,'case_id':case_id,'target_type':target_type,'target_id':target_id,'decisions':list(rows)};self.db.execute('INSERT INTO workspace_conflicts_181 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,case_id,target_type,target_id,'open',dumps(list(rows)),None,None,now_ts(),None,_hash(p)))
 def calibrate_detector(self,*,detector_name:str,detector_version:str,media_type:str,threshold:float,weight:float,benchmark_ref:str,approved_by:str,false_positive_rate:float|None=None,false_negative_rate:float|None=None,confirmation:str)->dict[str,Any]:
  if confirmation!=f'DETECTOR 181 {detector_name} KALIBRIEREN':raise PermissionError('explicit detector approval required')
  if not 0<=threshold<=1 or not 0<weight<=1:raise ValueError('invalid calibration')
  if false_positive_rate is not None and not 0<=false_positive_rate<=1:raise ValueError('invalid false positive rate')
  cid=new_id('dc181');status='approved' if false_positive_rate is not None and false_positive_rate<=.15 else 'sandbox_only';p={'calibration_id':cid,'detector_name':detector_name,'detector_version':detector_version,'media_type':media_type,'threshold':threshold,'weight':weight,'false_positive_rate':false_positive_rate,'false_negative_rate':false_negative_rate,'benchmark_ref':benchmark_ref,'status':status,'approved_by':approved_by}
  self.db.execute('INSERT OR REPLACE INTO detector_calibrations_181 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,detector_name,detector_version,media_type,threshold,weight,false_positive_rate,false_negative_rate,benchmark_ref,status,approved_by,now_ts(),_hash(p)));return p
 def evaluate_ensemble(self,case_id:str,job_id:str,*,results:Sequence[Mapping[str,Any]],confirmation:str)->dict[str,Any]:
  if confirmation!=f'DETECTOR 181 {job_id} ENSEMBLE AUSWERTEN':raise PermissionError('explicit ensemble approval required')
  weighted=0.0;weights=0.0;positive=0;accepted=[]
  for r in results:
   cal=self.db.one("SELECT * FROM detector_calibrations_181 WHERE detector_name=? AND detector_version=? AND media_type=?",(r['detector_name'],r['detector_version'],r['media_type']))
   if not cal or cal['status']!='approved':continue
   score=float(r['score']);decision='positive' if score>=float(cal['threshold']) else 'negative';positive+=decision=='positive';weights+=float(cal['weight']);weighted+=score*float(cal['weight']);run=new_id('dr181');details={'media_type':r['media_type'],'raw':r.get('details',{})};self.db.execute('INSERT INTO detector_runs_181 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(run,case_id,job_id,r['detector_name'],r['detector_version'],score,cal['threshold'],cal['weight'],decision,dumps(details),now_ts(),_hash({'run':run,**details,'score':score})));accepted.append(decision)
  total=len(accepted);score=weighted/weights if weights else 0;agreement=max(positive,total-positive)/total if total else 0
  status='suspicious_candidate' if total>=2 and positive>=2 and score>=.65 else 'inconclusive' if total else 'no_approved_detectors'
  limitations=['detector_ensemble_is_not_verdict','calibration_domain_may_not_match_case_media','human_review_required','provenance_and_context_take_precedence']
  eid=new_id('ens181');p={'ensemble_id':eid,'case_id':case_id,'job_id':job_id,'weighted_score':score,'agreement':agreement,'positive_detectors':positive,'total_detectors':total,'status':status,'limitations':limitations}
  self.db.execute('INSERT INTO authenticity_ensembles_181 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(eid,case_id,job_id,score,agreement,positive,total,status,dumps(limitations),now_ts(),_hash(p)))
  if status=='suspicious_candidate':self._event(case_id,'ensemble_warning_candidate',p)
  return p
 def dashboard(self,case_id:str)->dict[str,Any]:
  q=lambda sql:int(self.db.one(sql,(case_id,))['n'])
  return {'case_id':case_id,'members':q('SELECT COUNT(*) n FROM workspace_members_181 WHERE case_id=? AND status="active"'),'open_tasks':q('SELECT COUNT(*) n FROM workspace_tasks_181 WHERE case_id=? AND status="open"'),'open_conflicts':q('SELECT COUNT(*) n FROM workspace_conflicts_181 WHERE case_id=? AND status="open"'),'open_authenticity_alerts':q('SELECT COUNT(*) n FROM authenticity_alerts_180 WHERE case_id=? AND status="open"'),'human_review_required':True}
 def source_coverage(self)->dict[str,Any]:
  tables=('european_source_profiles_172','extended_source_profiles_173','media_source_profiles_174','geo_source_profiles_175','multilingual_source_profiles_176','graph_source_profiles_177','monitor_source_profiles_178','pattern_source_profiles_179','authenticity_source_profiles_180','workspace_source_profiles_181');counts=[]
  for t in tables:
   try:counts.append(int(self.db.one(f'SELECT COUNT(*) n FROM {t}')['n']))
   except Exception:counts.append(0)
  return {'total_documented_sources':sum(counts),'workspace_and_verification_sources':counts[-1],'production_active_new':0,'review_required':True}
 def _event(self,case_id:str,event_type:str,details:Mapping[str,Any])->None:
  prev=self.db.one('SELECT event_sha256 FROM workspace_events_181 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,));ph=prev['event_sha256'] if prev else '';eid=new_id('we181');ts=now_ts();eh=_hash({'event_id':eid,'case_id':case_id,'event_type':event_type,'details':details,'created_at':ts,'previous_sha256':ph});self.db.execute('INSERT INTO workspace_events_181 VALUES(?,?,?,?,?,?,?)',(eid,case_id,event_type,dumps(dict(details)),ts,ph,eh))
