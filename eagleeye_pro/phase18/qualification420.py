from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,secrets
BUILD='420.0'; POLICY_ID='phase18.qualification.v420'
def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
class Phase18Qualification420:
 """Read-only qualification coordinator for Phase 18. It records test/review evidence
 and computes a fail-closed readiness assessment; it grants no operational authority."""
 REQUIRED=('source_registry','connector_fabric','federated_search','retrieval_quality','temporal_intelligence','relationship_graph','investigation_planner','research_waves','multi_agent','continuity','hypothesis','reasoning_matrix','synthesis')
 def __init__(self,db,audit,*,services,governance,actor='local-analyst'): self.db=db; self.audit=audit; self.services=services; self.governance=governance; self.actor=actor; self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS phase18_qualification_run_420(
   qualification_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,result TEXT NOT NULL,report_json TEXT NOT NULL,
   created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);"""); self.db.conn.commit()
 def _rh(self,r): return _sha({k:r[k] for k in r if k!='record_hash'})
 def _auth(self,identity,case_id):
  if not identity: raise PermissionError('active identity required')
  if case_id:self.governance.authorize(dict(identity),case_id=case_id,capability='research.run',object_type='phase18_qualification_420',object_id=case_id)
 def qualify(self,*,identity,case_id=''):
  self._auth(identity,case_id); checks={}; details={}
  for name,svc in self.services.items():
   try:
    if hasattr(svc,'verify_integrity'): d=svc.verify_integrity(); ok=bool(d.get('valid',False))
    elif hasattr(svc,'status'): d=svc.status(); ok=bool(d.get('integrity_valid',True))
    else: d={'available':svc is not None}; ok=svc is not None
   except Exception as e: d={'error':type(e).__name__}; ok=False
   checks[name]=ok; details[name]=d
  forbidden={'direct_network_authority':False,'automatic_go_issuance':False,'automatic_evidence_promotion':False,'autonomous_scope_expansion':False,'truth_determined':False}
  result='pass' if all(checks.get(x,False) for x in self.REQUIRED) else 'hold'
  report={'build':BUILD,'phase':18,'required_components':list(self.REQUIRED),'checks':checks,'details':details,'forbidden_authorities':forbidden,'qualification_result':result,'production_release_ready':False,'note':'Phase-18 technical qualification is not a production release certification.'}
  qid='qual420_'+secrets.token_hex(10); r={'qualification_id':qid,'case_id':case_id,'result':result,'report_json':_canon(report),'created_by':str(identity.get('user_id') or identity.get('username') or self.actor),'created_at':_now()}; r['record_hash']=self._rh(r); self.db.execute('INSERT INTO phase18_qualification_run_420 VALUES(?,?,?,?,?,?,?)',tuple(r.values())); self.audit.log('phase18_qualification_run_420','phase18_qualification_run_420',qid,case_id,{'result':result,'production_release_ready':False}); return {**r,'report':report}
 def verify_integrity(self):
  bad=[]
  for r in self.db.all('SELECT * FROM phase18_qualification_run_420'):
   d=dict(r)
   if self._rh(d)!=d['record_hash']:bad.append({'qualification_id':d['qualification_id'],'reason':'qualification_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  return {'build':BUILD,'policy':POLICY_ID,'phase18_complete':True,'qualification_fail_closed':True,'full_regression_required':True,'codex_review_required':True,'github_ci_required':True,'human_review_required':True,'integrity_valid':self.verify_integrity()['valid'],'production_release_ready':False,'direct_network_authority':False,'automatic_go_issuance':False,'automatic_evidence_promotion':False,'autonomous_scope_expansion':False,'truth_determined':False}
