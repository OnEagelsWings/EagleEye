from __future__ import annotations
import hashlib,json,mimetypes,subprocess,threading,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Any,Callable,Mapping,Sequence
from eagleeye_pro.core.database import dumps,loads,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
def _sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for c in iter(lambda:f.read(1048576),b''):h.update(c)
 return h.hexdigest()
def _clean(v:Any)->Any:
 sensitive=('token','secret','password','authorization','cookie','session','api_key','private_key')
 if isinstance(v,Mapping):return {str(k):('[REDACTED]' if any(x in str(k).lower() for x in sensitive) else _clean(xv)) for k,xv in v.items()}
 if isinstance(v,list):return [_clean(x) for x in v]
 return v

class Build180ContentAuthenticityService:
 BUILD='180.0'
 SOURCE_PROFILES=[
 {'source_id':'c2pa_specification','title':'C2PA Content Credentials','category':'provenance_standard','access_mode':'official_spec','base_url':'https://spec.c2pa.org','docs_url':'https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html','constraints':['provenance_not_truth','absence_not_fake']},
 {'source_id':'c2pa_tool_local','title':'C2PA Tool Local Verification','category':'local_verifier','access_mode':'local_cli','base_url':'local://c2patool','docs_url':'https://opensource.contentauthenticity.org/docs/c2patool/','constraints':['local_only','tool_version_recorded']},
 {'source_id':'google_factcheck_api','title':'Google Fact Check Tools API','category':'claim_review','access_mode':'official_api_key','base_url':'https://factchecktools.googleapis.com','docs_url':'https://developers.google.com/fact-check/tools/api/reference/rest','constraints':['claim_review_not_ground_truth','credential_required']},
 {'source_id':'edmo_factchecks','title':'European Digital Media Observatory Fact Checks','category':'fact_check_network','access_mode':'guided_public','base_url':'https://edmo.eu','docs_url':'https://edmo.eu/areas-of-activities/fact-checking/','constraints':['publisher_independence_review','no_bulk_assumption']},
 {'source_id':'nist_genai_eval','title':'NIST GenAI Detector Evaluation','category':'detector_benchmark','access_mode':'official_reference','base_url':'https://ai-challenges.nist.gov','docs_url':'https://ai-challenges.nist.gov/genai','constraints':['benchmark_reference_only','detector_scores_not_verdicts']},
 {'source_id':'eu_disinfo_lab','title':'EU DisinfoLab Research','category':'disinformation_research','access_mode':'guided_public','base_url':'https://www.disinfo.eu','docs_url':'https://www.disinfo.eu/','constraints':['research_context_only','terms_review']},
 ]
 POLICY={'local_processing':True,'external_uploads':False,'automatic_verdict':False,'human_review_required':True,'automatic_identity_confirmation':False,'untrusted_content_is_data':True}
 def __init__(self,db:Any,audit:Any,*,base_dir:str|Path,media_forensics:Any,multilingual:Any,geospatial:Any,monitor:Any,pattern_engine:Any,actor:str='system'):
  self.db,self.audit,self.actor=db,audit,actor;self.base_dir=Path(base_dir);self.media=media_forensics;self.multilingual=multilingual;self.geo=geospatial;self.monitor=monitor;self.pattern=pattern_engine
  self._stop=threading.Event();self._thread=None;self._notifier:Callable[[dict[str,Any]],None]|None=None
 def seed_sources(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!='AUTH SOURCES 180 ERWEITERN':raise PermissionError('explicit source approval required')
  for p in self.SOURCE_PROFILES:
   payload={**p,'status':'DOCUMENTED'};self.db.execute('INSERT OR REPLACE INTO authenticity_source_profiles_180 VALUES(?,?,?,?,?,?,?,?,?,?)',(p['source_id'],p['title'],p['category'],p['access_mode'],p['base_url'],p['docs_url'],dumps(p['constraints']),'DOCUMENTED',now_ts(),_hash(payload)))
  return {'created':len(self.SOURCE_PROFILES),'production_active':0,'review_required':True}
 def create_policy(self,case_id:str,*,scope:Sequence[str],interval_minutes:int=60,alert_threshold:float=.65,active_days:int=30,approved_by:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AUTH 180 {case_id} AUTOMATIK AKTIVIEREN':raise PermissionError('explicit background approval required')
  allowed={'provenance','file_integrity','metadata','synthetic_media','context','source_corroboration'}
  if not scope or not set(scope)<=allowed:raise ValueError('invalid scope')
  if interval_minutes<5 or interval_minutes>1440:raise ValueError('interval out of range')
  if not 0<=alert_threshold<=1:raise ValueError('invalid threshold')
  pid=new_id('apol180');exp=(datetime.now(timezone.utc)+timedelta(days=max(1,min(active_days,365)))).isoformat();payload={'policy_id':pid,'case_id':case_id,'scope':list(scope),'interval_minutes':interval_minutes,'alert_threshold':alert_threshold,'status':'active','approved_by':approved_by,'expires_at':exp,'policy':self.POLICY}
  self.db.execute('INSERT INTO authenticity_policies_180 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,dumps(list(scope)),interval_minutes,alert_threshold,'active',approved_by,exp,now_ts(),_hash(payload)));self._event(case_id,'policy_created',payload);return payload
 def enqueue(self,case_id:str,*,policy_id:str,evidence_id:str|None=None,media_id:str|None=None,document_id:str|None=None,priority:str='normal',confirmation:str)->dict[str,Any]:
  if confirmation!=f'AUTH 180 {case_id} PRUEFEN':raise PermissionError('explicit verification approval required')
  if sum(bool(x) for x in (evidence_id,media_id,document_id))!=1:raise ValueError('exactly one target required')
  pol=self.db.one("SELECT * FROM authenticity_policies_180 WHERE policy_id=? AND case_id=? AND status='active'",(policy_id,case_id))
  if not pol or pol['expires_at']<=now_ts():raise PermissionError('active policy required')
  if priority not in {'low','normal','high','critical'}:raise ValueError('invalid priority')
  jid=new_id('ajob180');payload={'job_id':jid,'case_id':case_id,'evidence_id':evidence_id,'media_id':media_id,'document_id':document_id,'policy_id':policy_id,'status':'queued','priority':priority}
  self.db.execute('INSERT INTO authenticity_jobs_180 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(jid,case_id,evidence_id,media_id,document_id,policy_id,'queued',priority,now_ts(),None,None,None,None,_hash(payload)));self._event(case_id,'job_queued',payload);return payload
 def start_background(self,*,notifier:Callable[[dict[str,Any]],None]|None=None,poll_seconds:float=2.0)->dict[str,Any]:
  if self._thread and self._thread.is_alive():return {'status':'already_running'}
  self._notifier=notifier;self._stop.clear()
  def loop():
   while not self._stop.wait(max(.25,poll_seconds)):
    try:self.process_due(max_jobs=5)
    except Exception as exc:self._event('system','background_error',{'error':type(exc).__name__})
  self._thread=threading.Thread(target=loop,name='eagleeye-authenticity-180',daemon=True);self._thread.start();return {'status':'running','daemon':True}
 def stop_background(self)->dict[str,Any]:
  self._stop.set()
  if self._thread:self._thread.join(timeout=3)
  return {'status':'stopped','alive':bool(self._thread and self._thread.is_alive())}
 def process_due(self,*,max_jobs:int=10)->dict[str,Any]:
  rows=[dict(r) for r in self.db.all("SELECT * FROM authenticity_jobs_180 WHERE status='queued' ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, queued_at LIMIT ?",(max(1,min(max_jobs,100)),))]
  done=[]
  for row in rows:done.append(self._run_job(row))
  return {'processed':len(done),'jobs':done}
 def _run_job(self,row:Mapping[str,Any])->dict[str,Any]:
  jid=row['job_id'];self.db.execute("UPDATE authenticity_jobs_180 SET status='running',started_at=? WHERE job_id=?",(now_ts(),jid));checks=[]
  try:
   target=self._resolve_target(row);checks.extend(self._integrity_checks(jid,target));checks.extend(self._metadata_checks(jid,target));checks.extend(self._c2pa_check(jid,target));checks.extend(self._context_checks(jid,target))
   suspicious=[c for c in checks if c.get('status') in {'suspicious','contradicted'}];confidence=max([float(c.get('score') or 0) for c in suspicious] or [0]);result={'checks':len(checks),'suspicious':len(suspicious),'confidence':confidence,'verdict':'inconclusive' if suspicious else 'no_anomaly_detected','automatic_verdict':False,'review_required':True}
   self.db.execute("UPDATE authenticity_jobs_180 SET status='succeeded',finished_at=?,result_json=?,payload_sha256=? WHERE job_id=?",(now_ts(),dumps(result),_hash({'job_id':jid,**result}),jid))
   if suspicious:self._finding_and_alert(row,suspicious,confidence)
   self._event(row['case_id'],'job_completed',{'job_id':jid,**result});return {'job_id':jid,**result}
  except Exception as exc:
   self.db.execute("UPDATE authenticity_jobs_180 SET status='failed',finished_at=?,error_text=? WHERE job_id=?",(now_ts(),type(exc).__name__,jid));self._event(row['case_id'],'job_failed',{'job_id':jid,'error':type(exc).__name__});return {'job_id':jid,'status':'failed','error':type(exc).__name__}
 def _resolve_target(self,row:Mapping[str,Any])->dict[str,Any]:
  if row.get('media_id'):
   r=self.db.one('SELECT * FROM media_items_174 WHERE media_id=?',(row['media_id'],));
   if not r:raise KeyError('media not found')
   return {'kind':'media','path':r['file_path'],'sha256':r['exact_sha256'],'mime':r['mime_type'],'metadata':loads(r['metadata_json'])}
  if row.get('evidence_id'):
   r=self.db.one('SELECT * FROM evidence_registry_168 WHERE evidence_id=?',(row['evidence_id'],));
   if not r:raise KeyError('evidence not found')
   return {'kind':'evidence','path':r['original_path'],'sha256':r['sha256'],'mime':r['mime_type'],'metadata':{}}
  r=self.db.one('SELECT * FROM multilingual_documents_176 WHERE document_id=?',(row['document_id'],));
  if not r:raise KeyError('document not found')
  return {'kind':'document','text':r['original_text'],'sha256':r['content_sha256'],'mime':'text/plain','metadata':{'language':r['language_code']}}
 def _save_check(self,jid:str,typ:str,status:str,score:float|None,details:Mapping[str,Any],tool:str,version:str)->dict[str,Any]:
  cid=new_id('acheck180');clean=_clean(dict(details));payload={'check_id':cid,'job_id':jid,'check_type':typ,'status':status,'score':score,'details':clean,'tool_name':tool,'tool_version':version};self.db.execute('INSERT INTO authenticity_checks_180 VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,jid,typ,status,score,dumps(clean),tool,version,now_ts(),_hash(payload)));return payload
 def _integrity_checks(self,jid:str,t:Mapping[str,Any])->list[dict[str,Any]]:
  if 'path' not in t:return [self._save_check(jid,'file_integrity','supported',1.0,{'stored_sha256':t['sha256']},'eagleeye-sha256','1')]
  p=Path(t['path']);actual=_sha(p) if p.is_file() else None;status='supported' if actual==t['sha256'] else 'contradicted';return [self._save_check(jid,'file_integrity',status,1.0 if status=='supported' else .99,{'stored':t['sha256'],'actual':actual},'eagleeye-sha256','1')]
 def _metadata_checks(self,jid:str,t:Mapping[str,Any])->list[dict[str,Any]]:
  meta=t.get('metadata') or {};flags=[]
  if meta.get('GPSInfo')=='[PRESENT_REVIEW_REQUIRED]':flags.append('sensitive_gps_metadata_present')
  if t.get('mime','').startswith('image/') and not meta:flags.append('metadata_absent_or_stripped')
  status='suspicious' if len(flags)>1 else 'inconclusive' if flags else 'no_anomaly_detected';score=.55 if status=='suspicious' else .2 if flags else 0
  return [self._save_check(jid,'metadata',status,score,{'flags':flags,'note':'metadata absence is not proof of manipulation'},'eagleeye-metadata','1')]
 def _c2pa_check(self,jid:str,t:Mapping[str,Any])->list[dict[str,Any]]:
  if 'path' not in t:return [self._save_check(jid,'c2pa','inconclusive',0,{'reason':'not_media'},'c2patool','unavailable')]
  from shutil import which
  tool=which('c2patool')
  if not tool:return [self._save_check(jid,'c2pa','inconclusive',0,{'manifest_present':False,'reason':'tool_unavailable','absence_not_fake':True},'c2patool','unavailable')]
  cp=subprocess.run([tool,str(t['path'])],capture_output=True,text=True,timeout=30);ok=cp.returncode==0 and 'validation_status' not in cp.stderr.lower();return [self._save_check(jid,'c2pa','supported' if ok else 'inconclusive',.8 if ok else .1,{'returncode':cp.returncode,'output_sha256':_hash(cp.stdout),'absence_not_fake':True},'c2patool','local')]
 def _context_checks(self,jid:str,t:Mapping[str,Any])->list[dict[str,Any]]:
  indicators=[]
  text=str(t.get('text') or '')
  for phrase in ('ignore previous instructions','reveal system prompt','bypass policy'): 
   if phrase in text.lower():indicators.append('prompt_injection_indicator')
  status='suspicious' if indicators else 'inconclusive';return [self._save_check(jid,'context',status,.8 if indicators else 0,{'indicators':indicators,'source_content_is_data':True},'eagleeye-context','1')]
 def _finding_and_alert(self,row:Mapping[str,Any],checks:Sequence[Mapping[str,Any]],confidence:float)->None:
  severity='critical' if confidence>=.9 else 'high' if confidence>=.75 else 'medium';fid=new_id('afind180');summary='Mögliche Authentizitäts- oder Manipulationsauffälligkeit erkannt';evidence={'checks':[c['check_id'] for c in checks],'limitations':['detector_output_is_not_verdict','human_review_required','provenance_and_context_must_be_checked']};payload={'finding_id':fid,'job_id':row['job_id'],'case_id':row['case_id'],'finding_type':'authenticity_anomaly_candidate','severity':severity,'confidence':confidence,'summary':summary,'evidence':evidence}
  self.db.execute('INSERT INTO authenticity_findings_180 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(fid,row['job_id'],row['case_id'],payload['finding_type'],severity,confidence,summary,dumps(evidence),'open',now_ts(),_hash(payload)))
  aid=new_id('aalert180');title='Authentizitätsprüfung: mögliche Auffälligkeit';message=f'{summary}. Confidence-Signal {confidence:.2f}; keine automatische Fake-Feststellung.';ap={'alert_id':aid,'case_id':row['case_id'],'job_id':row['job_id'],'finding_id':fid,'severity':severity,'title':title,'message':message}
  self.db.execute('INSERT INTO authenticity_alerts_180 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(aid,row['case_id'],row['job_id'],fid,severity,title,message,'open',now_ts(),None,None,_hash(ap)));self._event(row['case_id'],'investigator_alert',ap)
  if self._notifier:
   try:self._notifier(ap)
   except Exception:self._event(row['case_id'],'notifier_failed',{'alert_id':aid})
 def alerts(self,case_id:str,*,status:str='open')->list[dict[str,Any]]:return [dict(r) for r in self.db.all('SELECT * FROM authenticity_alerts_180 WHERE case_id=? AND status=? ORDER BY created_at DESC',(case_id,status))]
 def acknowledge_alert(self,alert_id:str,*,reviewer:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AUTH ALERT 180 {alert_id} BESTAETIGEN':raise PermissionError('explicit alert review required')
  self.db.execute("UPDATE authenticity_alerts_180 SET status='acknowledged',acknowledged_by=?,acknowledged_at=? WHERE alert_id=?",(reviewer,now_ts(),alert_id));return {'alert_id':alert_id,'status':'acknowledged'}
 def source_coverage(self)->dict[str,Any]:
  tables=('european_source_profiles_172','extended_source_profiles_173','media_source_profiles_174','geo_source_profiles_175','multilingual_source_profiles_176','graph_source_profiles_177','monitor_source_profiles_178','pattern_source_profiles_179','authenticity_source_profiles_180');counts=[]
  for t in tables:
   try:counts.append(int(self.db.one(f'SELECT COUNT(*) n FROM {t}')['n']))
   except Exception:counts.append(0)
  return {'total_documented_sources':sum(counts),'authenticity_sources':counts[-1],'production_active_new':0,'review_required':True}
 def _event(self,case_id:str,event_type:str,details:Mapping[str,Any])->None:
  prev=self.db.one('SELECT event_sha256 FROM authenticity_events_180 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,));ph=prev['event_sha256'] if prev else '';eid=new_id('aevt180');created=now_ts();clean=_clean(dict(details));eh=_hash({'event_id':eid,'case_id':case_id,'event_type':event_type,'details':clean,'created_at':created,'previous_sha256':ph});self.db.execute('INSERT INTO authenticity_events_180 VALUES(?,?,?,?,?,?,?)',(eid,case_id,event_type,dumps(clean),created,ph,eh))
