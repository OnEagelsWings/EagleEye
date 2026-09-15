from __future__ import annotations
from typing import Any
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class ClaimEngineV380Service:
    GRADES=['unverified_hint','weakly_supported','partially_supported','strongly_supported','contradicted','rejected','needs_manual_review']
    def __init__(self,db:Database,audit:AuditService,counter_engine:Any=None): self.db=db; self.audit=audit; self.counter=counter_engine; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS claims_v3_80 (
          claim_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, statement TEXT NOT NULL, grade TEXT NOT NULL, review_status TEXT DEFAULT 'pending', identity_assessment_id TEXT DEFAULT '', support_refs_json TEXT NOT NULL, contra_refs_json TEXT NOT NULL, exportability TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, metadata_json TEXT NOT NULL);"""); self.db.conn.commit()
    def _grade(self,support,contra,identity_fit=0,doppler_risk='medium'):
        if contra: return 'contradicted'
        if doppler_risk=='high' or identity_fit<45: return 'needs_manual_review'
        if len(support)>=3 and identity_fit>=70: return 'strongly_supported'
        if len(support)>=2 and identity_fit>=55: return 'partially_supported'
        if support: return 'weakly_supported'
        return 'unverified_hint'
    def build(self,case_id,statement,support_refs=None,contra_refs=None,identity_assessment=None,metadata=None):
        support=support_refs or []; contra=contra_refs or []; ident=identity_assessment or {}; grade=self._grade(support,contra,int(ident.get('fit_score',0) or 0),ident.get('doppler_risk','medium'))
        export='exportable_with_uncertainty' if grade in {'partially_supported','strongly_supported'} else 'not_exportable_until_review'
        cid=new_id('cl80'); ts=now_ts(); self.db.execute('INSERT INTO claims_v3_80 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',[cid,case_id,statement,grade,'pending',ident.get('assessment_id',''),dumps(support),dumps(contra),export,ts,ts,dumps(metadata or {})])
        if self.counter: self.counter.evaluate(case_id,cid,statement,support,contra)
        self.audit.log('build','claim_v3_80',cid,case_id,{'grade':grade,'exportability':export}); return self.get(cid)
    def review(self,claim_id,status,reason='',actor='local-analyst'):
        self.db.execute('UPDATE claims_v3_80 SET review_status=?, updated_at=? WHERE claim_id=?',[status,now_ts(),claim_id]); self.audit.log('review','claim_v3_80',claim_id,details={'status':status,'reason':reason,'actor':actor}); return self.get(claim_id)
    def get(self,cid):
        r=self.db.one('SELECT * FROM claims_v3_80 WHERE claim_id=?',[cid])
        if not r: raise KeyError(cid)
        r['support_refs']=loads(r.pop('support_refs_json','[]'),[]); r['contra_refs']=loads(r.pop('contra_refs_json','[]'),[]); r['metadata']=loads(r.pop('metadata_json','{}'),{}); return r
    def list(self,case_id): return [self.get(r['claim_id']) for r in self.db.all('SELECT claim_id FROM claims_v3_80 WHERE case_id=? ORDER BY created_at',[case_id])]
    def matrix(self,case_id):
        claims=self.list(case_id); counts={g:0 for g in self.GRADES}
        for c in claims: counts[c['grade']]=counts.get(c['grade'],0)+1
        return {'case_id':case_id,'claim_count':len(claims),'grade_counts':counts,'claims':claims}
