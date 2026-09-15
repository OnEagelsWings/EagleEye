from __future__ import annotations
import re
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class AIAssistedAnalyst97Service:
    """Build 97.0: controlled AI-assist layer. It suggests; it never asserts identity or fact."""
    FORBIDDEN_DECISIONS = {'confirm_identity','declare_guilt','assert_private_fact','bypass_access','doxxing_export'}
    def __init__(self, db: Database, audit: AuditService, guardrails=None):
        self.db=db; self.audit=audit; self.guardrails=guardrails; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS ai_assist_97 (
          assist_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, created_at TEXT NOT NULL,
          assist_type TEXT NOT NULL, prompt TEXT NOT NULL, decision TEXT NOT NULL,
          suggestions_json TEXT NOT NULL, warnings_json TEXT NOT NULL, metadata_json TEXT NOT NULL
        );"""); self.db.conn.commit()
    def suggest(self, case_id: str, assist_type='hypothesis_review', prompt='', context=None):
        context=context or {}; warnings=[]; suggestions=[]; lowered=(prompt+' '+dumps(context)).lower()
        if any(x in lowered for x in ['captcha bypass','login bypass','paywall bypass','private account','doxx','home address']):
            decision='blocked'; warnings.append('Request matches blocked or high-risk assistance pattern.')
        elif assist_type in self.FORBIDDEN_DECISIONS:
            decision='blocked'; warnings.append('AI layer cannot make final identity, guilt, bypass, or doxxing decisions.')
        else:
            decision='suggestions_only'
            suggestions=['Separate observed public finding from analyst claim.','Check identity fit before attaching this finding to a person.','Look for counter-evidence and same-name candidates.','Capture and hash the source before using it in a report.']
            if re.search(r'\b(is|ist|definitely|clearly|obviously|100%)\b', lowered): warnings.append('Potential overclaiming language detected.')
            if not context.get('source_refs'): warnings.append('No source references supplied; keep output as hypothesis only.')
        aid=new_id('ai97'); ts=now_ts()
        self.db.execute('INSERT INTO ai_assist_97 VALUES(?,?,?,?,?,?,?,?,?)',[aid,case_id,ts,assist_type,prompt,decision,dumps(suggestions),dumps(warnings),dumps(context)])
        self.audit.log('suggest','ai_assist_97',aid,case_id,{'decision':decision,'warning_count':len(warnings)})
        return self.get(aid)
    def get(self, aid):
        r=self.db.one('SELECT * FROM ai_assist_97 WHERE assist_id=?',[aid])
        if not r: raise KeyError(aid)
        r['suggestions']=loads(r.pop('suggestions_json','[]'),[]); r['warnings']=loads(r.pop('warnings_json','[]'),[]); r['metadata']=loads(r.pop('metadata_json','{}'),{})
        return r
    def list(self, case_id):
        return [self.get(r['assist_id']) for r in self.db.all('SELECT assist_id FROM ai_assist_97 WHERE case_id=? ORDER BY created_at DESC',[case_id])]
