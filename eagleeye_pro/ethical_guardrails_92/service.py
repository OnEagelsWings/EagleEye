from __future__ import annotations
import re
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
BLOCK_PATTERNS=[('credential_or_secret','password|passwd|api[_-]?key|token|secret'),('bypass','captcha|paywall|login bypass|private account|scrape private'),('doxxing','home address|wohnadresse|private adresse|doxx'),('live_tracking','live location|standort in echtzeit|gps tracking')]
class EthicalGuardrails92Service:
    """Build 92.0: legal/ethical guardrail engine for action and export decisions."""
    def __init__(self,db:Database,audit:AuditService,gdpr:Any=None): self.db=db; self.audit=audit; self.gdpr=gdpr; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS guardrail_decisions_92(decision_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, action_type TEXT NOT NULL, subject TEXT DEFAULT '', context_json TEXT NOT NULL, decision TEXT NOT NULL, reasons_json TEXT NOT NULL, created_at TEXT NOT NULL); CREATE INDEX IF NOT EXISTS idx_guard92_case ON guardrail_decisions_92(case_id,created_at);"""); self.db.conn.commit()
    def evaluate(self,case_id:str,action_type:str,*,subject:str='',context:Dict[str,Any]|None=None)->Dict[str,Any]:
        context=context or {}; text=' '.join(str(x) for x in [action_type,subject,context.get('query',''),context.get('notes',''),context.get('export_mode','')]).lower(); reasons=[]; decision='allowed'
        for code,pat in BLOCK_PATTERNS:
            if re.search(pat,text,re.I): reasons.append({'level':'critical','code':code,'message':f'Blocked/risky pattern: {code}'}); decision='blocked'
        if context.get('data_class') in {'minor','health','religion','political','criminal'} and decision!='blocked': reasons.append({'level':'high','code':'sensitive_context','message':'Sensitive context requires manual review.'}); decision='review_required'
        if action_type in {'export','casefile_export'} and context.get('export_mode') in {'external_minimal','authority_redacted'} and decision=='allowed': decision='allowed_with_redaction'
        did=new_id('guard92'); self.db.execute('INSERT INTO guardrail_decisions_92 VALUES(?,?,?,?,?,?,?,?)',[did,case_id,action_type,subject,dumps(context),decision,dumps(reasons),now_ts()]); self.audit.log('evaluate','ethical_guardrails_92',did,case_id,{'decision':decision,'reasons':reasons}); return self.get(did)
    def get(self,did):
        r=self.db.one('SELECT * FROM guardrail_decisions_92 WHERE decision_id=?',[did])
        if not r: raise KeyError(did)
        r['context']=loads(r.pop('context_json','{}'),{}); r['reasons']=loads(r.pop('reasons_json','[]'),[]); return r
    def list(self,case_id): return [self.get(r['decision_id']) for r in self.db.all('SELECT decision_id FROM guardrail_decisions_92 WHERE case_id=? ORDER BY created_at DESC',[case_id])]
