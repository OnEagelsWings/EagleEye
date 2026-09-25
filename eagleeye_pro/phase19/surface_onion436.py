from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,secrets
BUILD='436.0';POLICY_ID='phase19.surface-onion-correlation-opsec.v436'
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
class SurfaceOnionCorrelation436:
 def __init__(self,db,audit,*,registry421,events422,content423,tor435,governance,actor='local-analyst'):self.db=db;self.audit=audit;self.registry421=registry421;self.events422=events422;self.content423=content423;self.tor435=tor435;self.governance=governance;self.actor=actor;self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS surface_onion_run_436(run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,min_jaccard REAL NOT NULL,candidate_count INTEGER NOT NULL,opsec_blocker_count INTEGER NOT NULL,result_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_sor436_case ON surface_onion_run_436(case_id,created_at);
CREATE TABLE IF NOT EXISTS surface_onion_candidate_436(candidate_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,case_id TEXT NOT NULL,surface_observation_id TEXT NOT NULL,surface_source_id TEXT NOT NULL,onion_task_id TEXT NOT NULL,onion_source_id TEXT NOT NULL,surface_content_id TEXT NOT NULL,onion_content_id TEXT NOT NULL,signals_json TEXT NOT NULL,score REAL NOT NULL,strength TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);CREATE INDEX IF NOT EXISTS idx_soc436_run ON surface_onion_candidate_436(run_id,score);CREATE INDEX IF NOT EXISTS idx_soc436_case ON surface_onion_candidate_436(case_id,surface_source_id,onion_source_id);""");self.db.conn.commit()
 def _rh(self,r):return _hash({k:r[k] for k in r if k!='record_hash'})
 def _identity(self,identity):
  if not isinstance(identity,dict) or not identity.get('username') or not identity.get('user_id'):raise PermissionError('canonical active identity required')
  try:u=self.governance.identity.public_user(str(identity['username']))
  except (KeyError,ValueError):raise PermissionError('canonical active identity required')
  if not u.get('active') or str(u.get('user_id'))!=str(identity.get('user_id')):raise PermissionError('canonical active identity required')
  return {**u,'session_id':str(identity.get('session_id') or 'surface436')}
 def _authorize(self,identity,case_id):
  ident=self._identity(identity);self.governance.authorize(ident,case_id=str(case_id),capability='research.run',object_type='surface_onion_correlation_436',object_id=str(case_id));return ident
 def _content(self,content_id):
  r=self.db.one('SELECT * FROM content_object_423 WHERE content_id=?',(str(content_id),))
  if not r:raise KeyError('content object not found')
  d=dict(r)
  try:d['tokens']=set(json.loads(d.get('token_json') or '[]'))
  except Exception:d['tokens']=set()
  return d
 def _surface_rows(self,case_id):
  rows=[]
  for r in self.db.all("""SELECT o.* FROM content_observation_423 o JOIN acquisition_source_421 s ON s.source_id=o.source_id WHERE o.case_id=? AND s.source_type!='tor_onion' ORDER BY o.created_at,o.observation_id""",(str(case_id),)):
   d=dict(r);d['content']=self._content(d['content_id']);rows.append(d)
  return rows
 def _onion_rows(self,case_id):
  out=[]
  for t in self.db.all("SELECT * FROM tor_research_task_435 WHERE case_id=? AND state='reviewed' AND content_id!='' ORDER BY created_at,task_id",(str(case_id),)):
   d=dict(t);d['content']=self._content(d['content_id']);d['event']=self.events422.get(d['event_id']);out.append(d)
  return out
 def _pair(self,surface,onion,min_jaccard):
  a=surface['content'];b=onion['content'];signals=[];score=0.0;strength=''
  if a['sha256']==b['sha256']:
   signals.append({'kind':'exact_sha256','value':a['sha256'],'meaning':'same captured bytes'});score=1.0;strength='exact'
  if a.get('text_fingerprint') and a['text_fingerprint']==b.get('text_fingerprint'):
   signals.append({'kind':'normalized_text_fingerprint','value':a['text_fingerprint'],'meaning':'same normalized textual fingerprint'});score=max(score,.98);strength='exact' if strength=='exact' else 'strong'
  ta=set(a.get('tokens') or ());tb=set(b.get('tokens') or ());jac=len(ta&tb)/len(ta|tb) if ta|tb else 0.0
  if jac>=float(min_jaccard):
   signals.append({'kind':'token_jaccard','value':round(jac,4),'meaning':'high lexical overlap candidate'});score=max(score,jac);strength=strength or ('strong' if jac>=.9 else 'moderate')
  if not signals:return None
  return {'signals':signals,'score':round(score,4),'strength':strength or 'moderate'}
 def _opsec(self,onion_rows):
  findings=[];blockers=0
  for t in onion_rows:
   ev=t['event'];usage=ev.get('usage') or {};src=self.registry421.get(t['source_id']);provenance=ev.get('provenance') or {}
   checks={'tor_source_contract':src.get('source_type')=='tor_onion' and src.get('access_mode')=='tor_public','tor_event_method':ev.get('method')=='tor_public','destination_credentials_absent':usage.get('no_auth') is True,'forms_absent':usage.get('no_forms') is True,'scope_expansion_absent':usage.get('no_scope_expansion') is True,'quarantine_provenance':ev.get('status')=='quarantined','public_onion_marked':provenance.get('public_onion_only') is True}
   failed=[k for k,v in checks.items() if not v]
   if failed:blockers+=1;findings.append({'task_id':t['task_id'],'severity':'blocker','failed_checks':failed,'action':'do not use this task for cross-surface operational follow-up'})
   else:findings.append({'task_id':t['task_id'],'severity':'clear','failed_checks':[]})
  return findings,blockers
 def analyze(self,*,identity,case_id,min_jaccard=.75):
  ident=self._authorize(identity,case_id);case_id=str(case_id or '').strip();threshold=float(min_jaccard)
  if not case_id:raise ValueError('case_id required')
  if not .5<=threshold<=1.0:raise ValueError('min_jaccard must be between 0.5 and 1.0')
  surface=self._surface_rows(case_id);onion=self._onion_rows(case_id);opsec,blockers=self._opsec(onion);run_id='sor436_'+secrets.token_hex(10);candidates=[]
  for s in surface:
   for o in onion:
    pair=self._pair(s,o,threshold)
    if not pair:continue
    cid='soc436_'+secrets.token_hex(10);r={'candidate_id':cid,'run_id':run_id,'case_id':case_id,'surface_observation_id':s['observation_id'],'surface_source_id':s['source_id'],'onion_task_id':o['task_id'],'onion_source_id':o['source_id'],'surface_content_id':s['content_id'],'onion_content_id':o['content_id'],'signals_json':_canon(pair['signals']),'score':pair['score'],'strength':pair['strength'],'created_at':_now()};r['record_hash']=self._rh(r);self.db.execute('INSERT INTO surface_onion_candidate_436 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));candidates.append({**r,'signals':pair['signals'],'candidate_only':True,'entity_identity_determined':False})
  result={'build':BUILD,'case_id':case_id,'surface_observations':len(surface),'reviewed_onion_tasks':len(onion),'candidate_count':len(candidates),'candidates':candidates,'opsec_findings':opsec,'opsec_blocker_count':blockers,'analysis_review_allowed':blockers==0,'operational_followup_allowed':False,'automatic_entity_resolution':False,'automatic_scope_expansion':False,'network_execution':False,'cross_surface_contact':False,'operational_followup_authority':False,'identity_determination':False,'truth_determination':False,'method_note':'Correlation scores describe content/provenance similarity only. They are not probabilities that surface and onion actors or entities are identical.'}
  row={'run_id':run_id,'case_id':case_id,'min_jaccard':threshold,'candidate_count':len(candidates),'opsec_blocker_count':blockers,'result_json':_canon(result),'created_by':str(ident['username']),'created_at':_now()};row['record_hash']=self._rh(row);self.db.execute('INSERT INTO surface_onion_run_436 VALUES(?,?,?,?,?,?,?,?,?)',tuple(row.values()));self.audit.log('surface_onion_correlation_run_436','case',case_id,case_id,{'run_id':run_id,'candidates':len(candidates),'opsec_blockers':blockers,'network_execution':False});return {**row,'result':result}
 def latest(self,case_id):
  r=self.db.one('SELECT * FROM surface_onion_run_436 WHERE case_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(str(case_id),))
  if not r:return None
  d=dict(r);d['result']=json.loads(d['result_json']);return d
 def case_report(self,case_id):
  runs=self.db.one('SELECT COUNT(*) n FROM surface_onion_run_436 WHERE case_id=?',(str(case_id),))['n'];cands=self.db.one('SELECT COUNT(*) n FROM surface_onion_candidate_436 WHERE case_id=?',(str(case_id),))['n'];latest=self.latest(case_id);return {'build':BUILD,'case_id':str(case_id),'runs':int(runs),'candidates':int(cands),'latest_opsec_blockers':int((latest or {}).get('opsec_blocker_count') or 0),'integrity_valid':self.verify_integrity()['valid'],'candidate_only':True,'case_scoped':True,'network_execution':False}
 def _ensure_surface_fixture_source(self):
  sid='src421_fixture_surface436';base='https://build436.example.invalid'
  with self.db.transaction(immediate=True):
   try:src=self.registry421.get(sid)
   except KeyError:
    caps=['case_fixture','public_pages'];coverage={'fixture_only':True,'network_execution_forbidden':True};r={'source_id':sid,'name':'Build 436 Synthetic Surface Fixture','source_type':'website','access_mode':'public','base_url':base,'capabilities_json':_canon(caps),'coverage_json':_canon(coverage),'terms_url':'','license_note':'Trusted internal synthetic surface fixture; no network retrieval.','enabled':1,'created_by':'system:build436_fixture','created_at':_now()};r['record_hash']=self.registry421._record_hash(r);self.db.execute('INSERT OR IGNORE INTO acquisition_source_421 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values()));src=self.registry421.get(sid);self.audit.log('surface436_fixture_source_seeded','acquisition_source_421',sid,'',{'fixture_only':True,'network_execution':False})
   if src['source_type']!='website' or src['base_url']!=base or not bool((src.get('coverage') or {}).get('fixture_only')):raise RuntimeError('reserved Build 436 fixture source has unexpected configuration')
   return src
 def run_case_selftest(self,*,identity,case_id):
  case_id=str(case_id or '').strip()
  if not case_id:raise ValueError('case_id required')
  tor=self.tor435.run_case_selftest(identity=identity,case_id=case_id);task=tor['task'];token=task['target'].rstrip('/').split('/')[-1];body=('Synthetic public onion page '+token).encode();src=self._ensure_surface_fixture_source();digest=hashlib.sha256(body).hexdigest();ev=self.events422.record(identity=identity,case_id=case_id,source_id=src['source_id'],target=src['base_url']+'/mirror/'+token,method='manual_import',status='retrieved',content_sha256=digest,media_type='text/plain',bytes_count=len(body),provenance={'build':'436.0','synthetic_surface_fixture':True},usage={'public_only':True,'network_execution':False});content=self.content423.ingest(identity=identity,event_id=ev['event_id'],content=body,media_type='text/plain',metadata={'build436_test_fixture':True});run=self.analyze(identity=identity,case_id=case_id,min_jaccard=.75);res=run['result'];exact=[c for c in res['candidates'] if any(s['kind']=='exact_sha256' for s in c['signals']) and c['onion_task_id']==task['task_id'] and c['surface_observation_id']==content['observation_id']];checks={'tor_selftest_passed':tor['result']=='PASS','surface_event_bound':ev['case_id']==case_id and ev['source_id']==src['source_id'],'exact_content_candidate_found':len(exact)==1,'candidate_only':bool(exact and exact[0]['candidate_only']),'identity_not_determined':bool(exact and exact[0]['entity_identity_determined'] is False),'opsec_clear':res['opsec_blocker_count']==0 and res['analysis_review_allowed'] is True and res['operational_followup_allowed'] is False,'no_network_execution':res['network_execution'] is False,'no_cross_surface_contact':res['cross_surface_contact'] is False,'integrity_valid':self.verify_integrity()['valid']}
  return {'build':BUILD,'case_id':case_id,'result':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'surface_event':ev,'surface_content':content,'correlation_run':run,'note':'Synthetic surface and onion fixtures use identical text to verify deterministic candidate correlation without any external network activity.'}
 def verify_integrity(self):
  bad=[]
  for table,key in [('surface_onion_run_436','run_id'),('surface_onion_candidate_436','candidate_id')]:
   for r in self.db.all('SELECT * FROM '+table):
    d=dict(r)
    if self._rh(d)!=d['record_hash']:bad.append({key:d[key],'table':table,'reason':'record_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  r=self.db.one('SELECT COUNT(*) n FROM surface_onion_run_436')['n'];c=self.db.one('SELECT COUNT(*) n FROM surface_onion_candidate_436')['n'];return {'build':BUILD,'policy':POLICY_ID,'runs':int(r),'candidates':int(c),'integrity_valid':self.verify_integrity()['valid'],'surface_onion_correlation':True,'opsec_gate':True,'reviewed_onion_only':True,'candidate_only':True,'automatic_entity_resolution':False,'automatic_scope_expansion':False,'network_execution':False,'cross_surface_contact':False,'identity_determination':False,'truth_determination':False,'case_specific_selftest':True,'production_release_ready':False}
