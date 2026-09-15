from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class IdentityResolutionV378Service:
    POS={'email_match':30,'username_match':18,'domain_match':12,'location_match':12,'occupation_match':12,'time_context_match':8,'source_corroboration':8}
    NEG={'name_only':25,'location_conflict':25,'occupation_conflict':20,'time_conflict':20,'multiple_same_name_candidates':20,'weak_source':10}
    def __init__(self,db:Database,audit:AuditService): self.db=db; self.audit=audit; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS identity_assessments_v3_78 (
          assessment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, subject_label TEXT NOT NULL, candidate_label TEXT NOT NULL,
          fit_score INTEGER DEFAULT 0, doppler_risk TEXT NOT NULL, decision TEXT NOT NULL, positive_signals_json TEXT NOT NULL, conflict_signals_json TEXT NOT NULL, created_at TEXT NOT NULL, notes TEXT DEFAULT '');"""); self.db.conn.commit()
    def assess(self, case_id:str, subject_label:str, candidate_label:str, positive_signals:List[str]|None=None, conflict_signals:List[str]|None=None, notes:str='')->Dict[str,Any]:
        pos=positive_signals or []; neg=conflict_signals or []
        score=max(0,min(100, sum(self.POS.get(x,0) for x in pos)-sum(self.NEG.get(x,0) for x in neg)))
        if neg and ('multiple_same_name_candidates' in neg or 'name_only' in neg): risk='high'
        elif score<45 or len(neg)>=2: risk='medium'
        else: risk='low'
        decision='claim_allowed_with_review' if score>=65 and risk!='high' else 'identity_review_required'
        aid=new_id('id78'); self.db.execute('INSERT INTO identity_assessments_v3_78 VALUES(?,?,?,?,?,?,?,?,?,?,?)',[aid,case_id,subject_label,candidate_label,score,risk,decision,dumps(pos),dumps(neg),now_ts(),notes])
        self.audit.log('assess','identity_v3_78',aid,case_id,{'fit_score':score,'doppler_risk':risk,'decision':decision})
        return self.get(aid)
    def get(self,aid):
        r=self.db.one('SELECT * FROM identity_assessments_v3_78 WHERE assessment_id=?',[aid])
        if not r: raise KeyError(aid)
        r['positive_signals']=loads(r.pop('positive_signals_json','[]'),[]); r['conflict_signals']=loads(r.pop('conflict_signals_json','[]'),[]); return r
    def list(self,case_id): return [self.get(r['assessment_id']) for r in self.db.all('SELECT assessment_id FROM identity_assessments_v3_78 WHERE case_id=? ORDER BY created_at',[case_id])]
