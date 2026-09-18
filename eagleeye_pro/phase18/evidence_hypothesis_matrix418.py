from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,secrets
from typing import Any,Mapping
BUILD='418.0'; POLICY_ID='phase18.evidence-hypothesis-reasoning-matrix.v418'
def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
class EvidenceHypothesisMatrix418:
 """Analytical matrix over Build-417 hypotheses. It exposes coverage, conflicts and gaps,
 but never decides truth or promotes evidence."""
 RELATIONS={'supports','contradicts','neutral','uncertain'}
 def __init__(self,db,audit,*,hypothesis417,continuity416,governance,actor='local-analyst'):
  self.db=db; self.audit=audit; self.hypothesis417=hypothesis417; self.continuity416=continuity416; self.governance=governance; self.actor=actor; self._init_schema()
 def _init_schema(self):
  self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS evidence_hypothesis_link_418(
   link_id TEXT PRIMARY KEY,hypothesis_id TEXT NOT NULL,session_id TEXT NOT NULL,case_id TEXT NOT NULL,
   evidence_ref TEXT NOT NULL,relation TEXT NOT NULL,rationale TEXT NOT NULL,confidence REAL,
   created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);
   CREATE INDEX IF NOT EXISTS idx_ehm418_hyp ON evidence_hypothesis_link_418(hypothesis_id,created_at);
   CREATE INDEX IF NOT EXISTS idx_ehm418_ev ON evidence_hypothesis_link_418(case_id,evidence_ref);"""); self.db.conn.commit()
 def _rh(self,r): return _sha({k:r[k] for k in r if k!='record_hash'})
 def _auth(self,identity,case_id,obj=''):
  if not identity: raise PermissionError('active case identity required')
  self.governance.authorize(dict(identity),case_id=case_id,capability='research.run',object_type='evidence_hypothesis_matrix_418',object_id=obj or case_id)
 def link(self,*,hypothesis_id,evidence_ref,relation,rationale='',confidence=None,identity:Mapping[str,Any]|None=None):
  h=self.hypothesis417.get(hypothesis_id); self.continuity416.validate(session_id=h['session_id'],identity=identity); self._auth(identity,h['case_id'],hypothesis_id)
  if not isinstance(evidence_ref,str) or not evidence_ref.strip(): raise ValueError('evidence_ref required')
  if relation not in self.RELATIONS: raise ValueError('invalid relation')
  if rationale is None: rationale=''
  if not isinstance(rationale,str): raise ValueError('rationale must be a string')
  if confidence is not None:
   if isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not 0<=float(confidence)<=1: raise ValueError('confidence must be between 0 and 1')
   confidence=float(confidence)
  lid='ehm418_'+secrets.token_hex(10); r={'link_id':lid,'hypothesis_id':hypothesis_id,'session_id':h['session_id'],'case_id':h['case_id'],'evidence_ref':evidence_ref.strip(),'relation':relation,'rationale':rationale.strip(),'confidence':confidence,'created_by':str((identity or {}).get('user_id') or (identity or {}).get('username') or self.actor),'created_at':_now()}; r['record_hash']=self._rh(r)
  self.db.execute('INSERT INTO evidence_hypothesis_link_418 VALUES(?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values())); self.audit.log('evidence_hypothesis_linked_418','evidence_hypothesis_link_418',lid,h['case_id'],{'hypothesis_id':hypothesis_id,'relation':relation,'evidence_promoted':False}); return dict(r)
 def matrix(self,*,session_id,identity:Mapping[str,Any]|None=None):
  continuity=self.continuity416.validate(session_id=session_id,identity=identity); rows=[dict(x) for x in self.db.all('SELECT * FROM hypothesis_417 WHERE session_id=? ORDER BY created_at,hypothesis_id',(session_id,))]
  if not rows: return {'build':BUILD,'session_id':session_id,'hypotheses':[],'evidence':{},'conflicts':[],'gaps':[],'continuity416':continuity,'truth_determined':False}
  self._auth(identity,rows[0]['case_id'],session_id); links=[dict(x) for x in self.db.all('SELECT * FROM evidence_hypothesis_link_418 WHERE session_id=? ORDER BY evidence_ref,created_at,link_id',(session_id,))]
  byh={h['hypothesis_id']:[] for h in rows}; bye={}
  for x in links: byh.setdefault(x['hypothesis_id'],[]).append(x); bye.setdefault(x['evidence_ref'],[]).append(x)
  conflicts=[]
  for ref,xs in bye.items():
   rel={x['relation'] for x in xs}
   if 'supports' in rel and 'contradicts' in rel: conflicts.append({'evidence_ref':ref,'reason':'cross_hypothesis_relation_conflict','links':xs})
  gaps=[]
  out=[]
  for h in rows:
   xs=byh.get(h['hypothesis_id'],[]); rel={x['relation'] for x in xs}
   if not xs: gaps.append({'hypothesis_id':h['hypothesis_id'],'reason':'no_evidence_links'})
   elif 'contradicts' not in rel: gaps.append({'hypothesis_id':h['hypothesis_id'],'reason':'no_counterevidence_link'})
   out.append({'hypothesis':h,'links':xs,'coverage':{'total':len(xs),'supports':sum(x['relation']=='supports' for x in xs),'contradicts':sum(x['relation']=='contradicts' for x in xs),'uncertain':sum(x['relation']=='uncertain' for x in xs)}})
  return {'build':BUILD,'session_id':session_id,'hypotheses':out,'evidence':bye,'conflicts':conflicts,'gaps':gaps,'continuity416':continuity,'assessment':'human_review_required','truth_determined':False,'automatic_evidence_promotion':False}
 def verify_integrity(self):
  bad=[]
  for r in self.db.all('SELECT * FROM evidence_hypothesis_link_418'):
   d=dict(r)
   if self._rh(d)!=d['record_hash']: bad.append({'link_id':d['link_id'],'reason':'link_hash_mismatch'})
   try:
    h=self.hypothesis417.get(d['hypothesis_id'])
    if h['case_id']!=d['case_id'] or h['session_id']!=d['session_id']: bad.append({'link_id':d['link_id'],'reason':'hypothesis_binding_mismatch'})
   except KeyError: bad.append({'link_id':d['link_id'],'reason':'orphaned_hypothesis'})
  return {'build':BUILD,'valid':not bad,'violations':bad}
 def status(self):
  return {'build':BUILD,'policy':POLICY_ID,'case_scoped':True,'session_bound':True,'continuity_guarded':True,'cross_hypothesis_matrix':True,'conflict_detection':True,'coverage_gap_detection':True,'counterevidence_required_for_complete_coverage':True,'human_review_required':True,'integrity_valid':self.verify_integrity()['valid'],'direct_network_authority':False,'automatic_go_issuance':False,'automatic_evidence_promotion':False,'autonomous_scope_expansion':False,'truth_determined':False}
