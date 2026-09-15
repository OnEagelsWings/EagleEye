from __future__ import annotations
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class CounterEvidence79Service:
    OVERCLAIM=('definitely','certainly','zweifelsfrei','bewiesen','garantiert','is the same person','ist dieselbe person')
    def __init__(self,db:Database,audit:AuditService): self.db=db; self.audit=audit; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS counter_evidence_79 (
          counter_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, claim_ref TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, severity TEXT DEFAULT 'medium', source_ref TEXT DEFAULT '', created_at TEXT NOT NULL, metadata_json TEXT NOT NULL);"""); self.db.conn.commit()
    def add(self,case_id,claim_ref,title,description,severity='medium',source_ref='',metadata=None):
        cid=new_id('ctr79'); self.db.execute('INSERT INTO counter_evidence_79 VALUES(?,?,?,?,?,?,?,?,?)',[cid,case_id,claim_ref,title,description,severity,source_ref,now_ts(),dumps(metadata or {})]); self.audit.log('add','counter_evidence_79',cid,case_id,{'claim_ref':claim_ref,'severity':severity}); return self.get(cid)
    def get(self,cid):
        r=self.db.one('SELECT * FROM counter_evidence_79 WHERE counter_id=?',[cid])
        if not r: raise KeyError(cid)
        r['metadata']=loads(r.pop('metadata_json','{}'),{}); return r
    def list(self,case_id): return [self.get(r['counter_id']) for r in self.db.all('SELECT counter_id FROM counter_evidence_79 WHERE case_id=? ORDER BY created_at',[case_id])]
    def evaluate(self,case_id,claim_ref,statement='',support_refs=None,contra_refs=None):
        rows=[self.get(r['counter_id']) for r in self.db.all('SELECT counter_id FROM counter_evidence_79 WHERE case_id=? AND claim_ref=?',[case_id,claim_ref])]
        warnings=[]; txt=(statement or '').lower()
        if any(w in txt for w in self.OVERCLAIM): warnings.append('overclaiming_language')
        if not support_refs: warnings.append('missing_support_refs')
        if contra_refs or rows: warnings.append('contra_evidence_present')
        decision='counter_review_required' if warnings else 'no_counter_issue_detected'
        return {'case_id':case_id,'claim_ref':claim_ref,'decision':decision,'warnings':warnings,'counter_items':rows}
