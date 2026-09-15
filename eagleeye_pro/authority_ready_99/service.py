from __future__ import annotations
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class AuthorityReadyPackage99Service:
    """Build 99.0: authority/court-ready readiness package, not a legal certification."""
    def __init__(self, db: Database, audit: AuditService, casefile=None, reliability=None, security=None):
        self.db=db; self.audit=audit; self.casefile=casefile; self.reliability=reliability; self.security=security; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS authority_packages_99 (
          authority_package_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, created_at TEXT NOT NULL,
          export_mode TEXT NOT NULL, readiness TEXT NOT NULL, checklist_json TEXT NOT NULL,
          warnings_json TEXT NOT NULL, references_json TEXT NOT NULL
        );"""); self.db.conn.commit()
    def build(self, case_id, export_mode='authority_redacted'):
        warnings=[]
        claims=self.db.all('SELECT * FROM claims_v3_80 WHERE case_id=?',[case_id]) if self._table('claims_v3_80') else []
        evidence=self.db.all('SELECT * FROM local_evidence_items_75 WHERE case_id=?',[case_id]) if self._table('local_evidence_items_75') else []
        audit_events=self.db.all('SELECT * FROM audit_events WHERE case_id=? ORDER BY timestamp DESC LIMIT 500',[case_id])
        reliability=self.reliability.latest_for_case(case_id) if self.reliability else []
        if not claims: warnings.append('No claims available for authority package.')
        if not evidence: warnings.append('No local evidence-vault items linked.')
        if any(c.get('review_status') not in {'accepted','reviewed','approved'} and c.get('grade') not in {'strongly_supported','partially_supported'} for c in claims):
            warnings.append('Some claims are unresolved or weak; keep them outside strong conclusions.')
        if reliability and any(r.get('score',0)<50 for r in reliability): warnings.append('Low-reliability source rating present.')
        sec = self.security.assess_case_security(case_id) if self.security else {'decision':'not_evaluated','risk_score':0}
        if sec.get('decision') in {'blocked','critical_review_required'}: warnings.append('Security complex requires review before authority export.')
        checklist={'public_only_scope': True, 'review_first': True, 'claims_have_source_refs': bool(claims), 'evidence_index_present': bool(evidence), 'audit_log_present': bool(audit_events), 'security_assessment': sec, 'source_reliability_count': len(reliability), 'method_note_required': True, 'redaction_required_for_external_use': export_mode!='internal_full'}
        readiness='ready_with_warnings' if warnings else 'ready'
        if 'No claims available for authority package.' in warnings or sec.get('decision')=='blocked': readiness='not_ready'
        pid=new_id('auth99'); refs={'claim_count':len(claims),'evidence_count':len(evidence),'audit_event_count':len(audit_events)}
        self.db.execute('INSERT INTO authority_packages_99 VALUES(?,?,?,?,?,?,?,?)',[pid,case_id,now_ts(),export_mode,readiness,dumps(checklist),dumps(warnings),dumps(refs)])
        self.audit.log('build','authority_package_99',pid,case_id,{'readiness':readiness,'warnings':warnings})
        return self.get(pid)
    def _table(self, name): return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", [name]))
    def get(self,pid):
        r=self.db.one('SELECT * FROM authority_packages_99 WHERE authority_package_id=?',[pid])
        if not r: raise KeyError(pid)
        r['checklist']=loads(r.pop('checklist_json','{}'),{}); r['warnings']=loads(r.pop('warnings_json','[]'),[]); r['references']=loads(r.pop('references_json','{}'),{}); return r
    def latest(self, case_id):
        r=self.db.one('SELECT authority_package_id FROM authority_packages_99 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',[case_id])
        return self.get(r['authority_package_id']) if r else self.build(case_id)
