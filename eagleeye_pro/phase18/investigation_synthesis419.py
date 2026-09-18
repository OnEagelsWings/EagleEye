from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,secrets
from typing import Any,Mapping
BUILD='419.0'; POLICY_ID='phase18.investigation-synthesis.v419'
def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
class InvestigationSynthesis419:
 """Creates reviewable analytical syntheses from the 417/418 hypothesis matrix.
 Syntheses are snapshots, not findings of fact."""
 def __init__(self,db,audit,*,matrix418,hypothesis417,continuity416,governance,actor='local-analyst'):
  self.db=db; self.audit=audit; self.matrix418=matrix418; self.hypothesis417=hypothesis417; self.continuity416=continuity416; self.governance=governance; self.actor=actor; self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS investigation_synthesis_419(
   synthesis_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,case_id TEXT NOT NULL,title TEXT NOT NULL,
   summary_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);
   CREATE INDEX IF NOT EXISTS idx_syn419_session ON investigation_synthesis_419(session_id,created_at);"""); self.db.conn.commit()
 def _rh(self,r): return _sha({k:r[k] for k in r if k!='record_hash'})
 def _auth(self,identity,case_id,obj=''):
  if not identity: raise PermissionError('active case identity required')
  self.governance.authorize(dict(identity),case_id=case_id,capability='research.run',object_type='investigation_synthesis_419',object_id=obj or case_id)
 def synthesize(self,*,session_id,title='Investigation synthesis',identity:Mapping[str,Any]|None=None):
  continuity=self.continuity416.validate(session_id=session_id,identity=identity)
  hi=self.hypothesis417.verify_integrity(); mi=self.matrix418.verify_integrity()
  if not hi['valid'] or not mi['valid']: raise PermissionError('source ledger integrity violation')
  matrix=self.matrix418.matrix(session_id=session_id,identity=identity)
  if not matrix['hypotheses']: raise ValueError('at least one hypothesis required')
  case_id=matrix['hypotheses'][0]['hypothesis']['case_id']; self._auth(identity,case_id,session_id)
  if not isinstance(title,str) or not title.strip(): raise ValueError('title required')
  competing=[]; unresolved=[]
  for row in matrix['hypotheses']:
   h=row['hypothesis']; c=row['coverage']; items=[dict(x) for x in self.db.all('SELECT * FROM hypothesis_item_417 WHERE hypothesis_id=? ORDER BY created_at,item_id',(h['hypothesis_id'],))]; links=[{k:v for k,v in x.items() if k!='record_hash'} for x in row['links']]; safe_items=[{k:v for k,v in x.items() if k!='record_hash'} for x in items]; counter_count=c['contradicts']+sum(x['item_type']=='counterevidence' for x in items); competing.append({'hypothesis_id':h['hypothesis_id'],'statement':h['statement'],'human_state':h['state'],'support_count':c['supports']+sum(x['item_type']=='support' for x in items),'counterevidence_count':counter_count,'uncertain_count':c['uncertain']+sum(x['item_type']=='uncertainty' for x in items),'hypothesis_items':safe_items,'evidence_links':links,'analytical_note':'insufficient_counterevidence_review' if counter_count==0 else 'support_and_counterevidence_present'})
  unresolved.extend(matrix['gaps']); unresolved.extend({'evidence_ref':x['evidence_ref'],'reason':x['reason']} for x in matrix['conflicts'])
  summary={'competing_hypotheses':competing,'unresolved':unresolved,'matrix_conflicts':len(matrix['conflicts']),'matrix_gaps':len(matrix['gaps']),'continuity_valid':bool(continuity),'assessment':'human_review_required','truth_determined':False,'recommended_next_step':'review unresolved gaps and conflicts before human conclusion' if unresolved else 'human comparative review'}
  sid='syn419_'+secrets.token_hex(10); r={'synthesis_id':sid,'session_id':session_id,'case_id':case_id,'title':title.strip(),'summary_json':_canon(summary),'created_by':str((identity or {}).get('user_id') or (identity or {}).get('username') or self.actor),'created_at':_now()}; r['record_hash']=self._rh(r); self.db.execute('INSERT INTO investigation_synthesis_419 VALUES(?,?,?,?,?,?,?,?)',tuple(r.values())); self.audit.log('investigation_synthesis_created_419','investigation_synthesis_419',sid,case_id,{'session_id':session_id,'truth_determined':False}); return {**r,'summary':summary}
 def get(self,synthesis_id,identity=None):
  r=self.db.one('SELECT * FROM investigation_synthesis_419 WHERE synthesis_id=?',(synthesis_id,))
  if not r: raise KeyError(synthesis_id)
  d=dict(r); self._auth(identity,d['case_id'],synthesis_id); self.continuity416.validate(session_id=d['session_id'],identity=identity); d['summary']=json.loads(d['summary_json']); return d
 def verify_integrity(self):
  bad=[]
  for r in self.db.all('SELECT * FROM investigation_synthesis_419'):
   d=dict(r)
   if self._rh(d)!=d['record_hash']: bad.append({'synthesis_id':d['synthesis_id'],'reason':'synthesis_hash_mismatch'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  return {'build':BUILD,'policy':POLICY_ID,'matrix_grounded':True,'competing_hypotheses_preserved':True,'unresolved_conflicts_exposed':True,'counterevidence_visible':True,'human_review_required':True,'integrity_valid':self.verify_integrity()['valid'],'direct_network_authority':False,'automatic_go_issuance':False,'automatic_evidence_promotion':False,'autonomous_scope_expansion':False,'truth_determined':False}
