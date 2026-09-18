from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, secrets
from typing import Any, Mapping

BUILD='417.0'
POLICY_ID='phase18.hypothesis-counterevidence-coordination.v417'

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()

class HypothesisCoordination417:
    """Case/session-bound hypothesis ledger. Hypotheses remain analyst proposals:
    no truth determination, evidence promotion, scope expansion, GO issuance or network execution.
    """
    STATES={'working','challenged','supported','insufficient','rejected_by_human','accepted_by_human'}
    def __init__(self,db,audit,*,continuity416,multi415,governance,actor='local-analyst'):
        self.db=db; self.audit=audit; self.continuity416=continuity416; self.multi415=multi415; self.governance=governance; self.actor=actor; self._init_schema()
    def _init_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS hypothesis_417(
          hypothesis_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,case_id TEXT NOT NULL,statement TEXT NOT NULL,
          alternative_to TEXT NOT NULL,state TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS hypothesis_item_417(
          item_id TEXT PRIMARY KEY,hypothesis_id TEXT NOT NULL,case_id TEXT NOT NULL,item_type TEXT NOT NULL,
          reference TEXT NOT NULL,note TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_h417_session ON hypothesis_417(session_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_h417_items ON hypothesis_item_417(hypothesis_id,created_at);"""); self.db.conn.commit()
    def _auth(self,identity,case_id,obj=''):
        if not identity: raise PermissionError('active case identity required')
        self.governance.authorize(dict(identity),case_id=case_id,capability='research.run',object_type='hypothesis_coordination_417',object_id=obj or case_id)
    def _rh(self,r): return _sha({k:r[k] for k in r if k!='record_hash'})
    def create(self,*,session_id,statement,identity:Mapping[str,Any]|None=None,alternative_to=''):
        self.continuity416.validate(session_id=session_id,identity=identity)
        s=self.multi415.session(session_id); self._auth(identity,s['case_id'],session_id)
        statement=' '.join(str(statement).split())
        if len(statement)<3: raise ValueError('hypothesis statement required')
        if alternative_to:
            parent=self.get(alternative_to)
            if parent['case_id']!=s['case_id'] or parent['session_id']!=session_id: raise PermissionError('alternative hypothesis binding mismatch')
        hid='hyp417_'+secrets.token_hex(10)
        r={'hypothesis_id':hid,'session_id':session_id,'case_id':s['case_id'],'statement':statement,'alternative_to':alternative_to,'state':'working','created_by':str((identity or {}).get('user_id') or (identity or {}).get('username') or self.actor),'created_at':_now()}
        r['record_hash']=self._rh(r); self.db.execute('INSERT INTO hypothesis_417 VALUES(?,?,?,?,?,?,?,?,?)',tuple(r.values()))
        self.audit.log('hypothesis_created_417','hypothesis_417',hid,s['case_id'],{'session_id':session_id,'truth_determined':False})
        return self.get(hid)
    def add_item(self,*,hypothesis_id,item_type,reference='',note='',identity:Mapping[str,Any]|None=None):
        h=self.get(hypothesis_id); self.continuity416.validate(session_id=h['session_id'],identity=identity); self._auth(identity,h['case_id'],hypothesis_id)
        if item_type not in {'support','counterevidence','uncertainty','open_question'}: raise ValueError('invalid hypothesis item type')
        if not str(reference).strip() and not str(note).strip(): raise ValueError('reference or note required')
        iid='hitem417_'+secrets.token_hex(10); r={'item_id':iid,'hypothesis_id':hypothesis_id,'case_id':h['case_id'],'item_type':item_type,'reference':str(reference).strip(),'note':str(note).strip(),'created_by':str((identity or {}).get('user_id') or (identity or {}).get('username') or self.actor),'created_at':_now()}; r['record_hash']=self._rh(r)
        self.db.execute('INSERT INTO hypothesis_item_417 VALUES(?,?,?,?,?,?,?,?,?)',tuple(r.values())); self.audit.log('hypothesis_item_added_417','hypothesis_item_417',iid,h['case_id'],{'hypothesis_id':hypothesis_id,'item_type':item_type,'evidence_promoted':False}); return dict(r)
    def set_human_state(self,*,hypothesis_id,state,identity:Mapping[str,Any]|None=None):
        h=self.get(hypothesis_id); self.continuity416.validate(session_id=h['session_id'],identity=identity); self._auth(identity,h['case_id'],hypothesis_id)
        if state not in self.STATES: raise ValueError('invalid hypothesis state')
        if state in {'accepted_by_human','rejected_by_human'} and not identity: raise PermissionError('human identity required')
        r={k:h[k] for k in ('hypothesis_id','session_id','case_id','statement','alternative_to','created_by','created_at')}; r['state']=state
        ordered={'hypothesis_id':r['hypothesis_id'],'session_id':r['session_id'],'case_id':r['case_id'],'statement':r['statement'],'alternative_to':r['alternative_to'],'state':r['state'],'created_by':r['created_by'],'created_at':r['created_at']}; ordered['record_hash']=self._rh(ordered)
        self.db.execute('UPDATE hypothesis_417 SET state=?,record_hash=? WHERE hypothesis_id=?',(state,ordered['record_hash'],hypothesis_id)); self.audit.log('hypothesis_state_set_by_human_417','hypothesis_417',hypothesis_id,h['case_id'],{'state':state}); return self.get(hypothesis_id)
    def get(self,hypothesis_id):
        r=self.db.one('SELECT * FROM hypothesis_417 WHERE hypothesis_id=?',(hypothesis_id,))
        if not r: raise KeyError('hypothesis not found')
        return dict(r)
    def review(self,*,hypothesis_id,identity:Mapping[str,Any]|None=None):
        h=self.get(hypothesis_id); continuity=self.continuity416.validate(session_id=h['session_id'],identity=identity); self._auth(identity,h['case_id'],hypothesis_id)
        items=[dict(x) for x in self.db.all('SELECT * FROM hypothesis_item_417 WHERE hypothesis_id=? ORDER BY created_at,item_id',(hypothesis_id,))]
        counts={k:sum(1 for x in items if x['item_type']==k) for k in ('support','counterevidence','uncertainty','open_question')}
        alternatives=[dict(x) for x in self.db.all('SELECT * FROM hypothesis_417 WHERE alternative_to=? ORDER BY created_at,hypothesis_id',(hypothesis_id,))]
        return {'build':BUILD,'hypothesis':h,'items':items,'counts':counts,'alternatives':alternatives,'continuity416':continuity,'assessment':'human_review_required','truth_determined':False,'automatic_evidence_promotion':False}
    def verify_integrity(self):
        bad=[]; hs={}
        for r in self.db.all('SELECT * FROM hypothesis_417'):
            d=dict(r); hs[d['hypothesis_id']]=d
            if self._rh(d)!=d['record_hash']: bad.append({'hypothesis_id':d['hypothesis_id'],'reason':'hypothesis_hash_mismatch'})
            try:
                s=self.multi415.session(d['session_id'])
                if s['case_id']!=d['case_id']: bad.append({'hypothesis_id':d['hypothesis_id'],'reason':'session_case_mismatch'})
            except KeyError: bad.append({'hypothesis_id':d['hypothesis_id'],'reason':'orphaned_session'})
        for r in self.db.all('SELECT * FROM hypothesis_item_417'):
            d=dict(r)
            if self._rh(d)!=d['record_hash']: bad.append({'item_id':d['item_id'],'reason':'item_hash_mismatch'})
            if d['hypothesis_id'] not in hs: bad.append({'item_id':d['item_id'],'reason':'orphaned_hypothesis'})
            elif hs[d['hypothesis_id']]['case_id']!=d['case_id']: bad.append({'item_id':d['item_id'],'reason':'item_case_mismatch'})
        return {'build':BUILD,'valid':not bad,'violations':bad}
    def status(self):
        return {'build':BUILD,'policy':POLICY_ID,'case_scoped':True,'session_bound':True,'continuity_guarded':True,'counterevidence_first_class':True,'alternatives_supported':True,'uncertainty_explicit':True,'open_questions_explicit':True,'human_review_required':True,'integrity_valid':self.verify_integrity()['valid'],'direct_network_authority':False,'automatic_go_issuance':False,'automatic_evidence_promotion':False,'autonomous_scope_expansion':False,'truth_determined':False}
