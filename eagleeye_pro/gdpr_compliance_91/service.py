from __future__ import annotations
from typing import Any, Dict, List
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
SENSITIVE={'health','religion','political','union','sexual','biometric','minor','criminal','precise_address'}
class GDPRCompliance91Service:
    """Build 91.0 EU/DSGVO compliance layer: purpose binding, minimization, retention, export rationale."""
    def __init__(self, db: Database, audit: AuditService): self.db=db; self.audit=audit; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS gdpr_assessments_91(assessment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, purpose TEXT NOT NULL, lawful_basis TEXT NOT NULL, data_classes_json TEXT NOT NULL, minimization_json TEXT NOT NULL, retention_json TEXT NOT NULL, export_rationale TEXT DEFAULT '', decision TEXT NOT NULL, warnings_json TEXT NOT NULL, created_at TEXT NOT NULL); CREATE INDEX IF NOT EXISTS idx_gdpr91_case ON gdpr_assessments_91(case_id,created_at);"""); self.db.conn.commit()
    def assess(self, case_id: str, *, purpose: str, lawful_basis: str='legitimate_interest', data_classes: List[str]|None=None, export_mode: str='internal_redacted', retention_days: int=90, rationale: str='')->Dict[str,Any]:
        data_classes=data_classes or ['public_low','public_personal']; warnings=[]; decision='allowed_with_review'
        if not purpose or len(purpose.strip())<8: warnings.append({'level':'high','code':'weak_purpose','message':'Purpose binding is too vague.'})
        if lawful_basis not in {'legitimate_interest','consent','legal_obligation','public_task','contract','vital_interest'}: warnings.append({'level':'high','code':'unknown_lawful_basis','message':'Unknown lawful basis.'})
        if any(c in SENSITIVE for c in data_classes): warnings.append({'level':'high','code':'sensitive_data','message':'Sensitive/special category data requires manual legal review.'}); decision='review_required'
        if 'minor' in data_classes: warnings.append({'level':'critical','code':'minor_related','message':'Minor-related data is blocked until strict manual review.'}); decision='blocked_until_manual_review'
        if export_mode=='external_minimal' and any(c in {'precise_address','phone','email'} for c in data_classes): warnings.append({'level':'high','code':'external_pii_export','message':'External export requires redaction/minimization.'}); decision='review_required'
        minimization={'only_public_sources':True,'candidate_not_claim_until_review':True,'avoid_unnecessary_third_parties':True,'export_mode':export_mode}
        retention={'retention_days':retention_days,'review_required_after_days':min(retention_days,90),'delete_or_reassess':True}
        aid=new_id('gdpr91')
        self.db.execute('INSERT INTO gdpr_assessments_91 VALUES(?,?,?,?,?,?,?,?,?,?,?)',[aid,case_id,purpose,lawful_basis,dumps(data_classes),dumps(minimization),dumps(retention),rationale,decision,dumps(warnings),now_ts()])
        self.audit.log('assess','gdpr_compliance_91',aid,case_id,{'decision':decision,'warnings':warnings})
        return self.get(aid)
    def get(self,aid):
        r=self.db.one('SELECT * FROM gdpr_assessments_91 WHERE assessment_id=?',[aid])
        if not r: raise KeyError(aid)
        r['data_classes']=loads(r.pop('data_classes_json','[]'),[]); r['minimization']=loads(r.pop('minimization_json','{}'),{}); r['retention']=loads(r.pop('retention_json','{}'),{}); r['warnings']=loads(r.pop('warnings_json','[]'),[]); return r
    def latest(self,case_id):
        r=self.db.one('SELECT assessment_id FROM gdpr_assessments_91 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',[case_id]); return self.get(r['assessment_id']) if r else {}
