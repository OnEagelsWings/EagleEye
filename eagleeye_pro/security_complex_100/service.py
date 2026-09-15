from __future__ import annotations
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts

class SecurityComplex100Service:
    """Build 100.0: central security-complex for Spearhead Beta readiness."""
    BLOCKED_PATTERNS=['captcha bypass','login bypass','paywall bypass','private account','credential','password dump','home address doxx','live location','stalking']
    def __init__(self, db: Database, audit: AuditService, gdpr=None, guardrails=None, graph_analytics=None, reliability=None, enterprise=None):
        self.db=db; self.audit=audit; self.gdpr=gdpr; self.guardrails=guardrails; self.graph_analytics=graph_analytics; self.reliability=reliability; self.enterprise=enterprise; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS security_assessments_100 (
          assessment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, created_at TEXT NOT NULL,
          scope TEXT NOT NULL, risk_score INTEGER NOT NULL, decision TEXT NOT NULL,
          gates_json TEXT NOT NULL, findings_json TEXT NOT NULL, recommendations_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS security_events_100 (
          security_event_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, created_at TEXT NOT NULL,
          event_type TEXT NOT NULL, severity TEXT NOT NULL, object_ref TEXT DEFAULT '', details_json TEXT NOT NULL
        );"""); self.db.conn.commit()
    def log_event(self, case_id, event_type, severity='info', object_ref='', details=None):
        eid=new_id('se100'); self.db.execute('INSERT INTO security_events_100 VALUES(?,?,?,?,?,?,?)',[eid,case_id,now_ts(),event_type,severity,object_ref,dumps(details or {})]); self.audit.log('security_event','security_complex_100',eid,case_id,{'event_type':event_type,'severity':severity}); return self.event(eid)
    def event(self,eid):
        r=self.db.one('SELECT * FROM security_events_100 WHERE security_event_id=?',[eid])
        if not r: raise KeyError(eid)
        r['details']=loads(r.pop('details_json','{}'),{}); return r
    def assess_case_security(self, case_id, scope='full_case'):
        gates={}; rec=[]; risk=0; texts=[]
        for table,col in [('pasted_findings_91','content_excerpt'),('claims_v3_80','statement'),('search_plans_81','query'),('ai_assist_97','prompt')]:
            if self._table(table):
                try: texts += [str(r.get(col,'')) for r in self.db.all(f'SELECT {col} FROM {table} WHERE case_id=?',[case_id])]
                except Exception: pass
        if self._table('local_evidence_items_75'):
            try:
                for r in self.db.all('SELECT stored_path, artifact_type FROM local_evidence_items_75 WHERE case_id=? LIMIT 200',[case_id]):
                    if str(r.get('artifact_type','')).startswith(('pasted_','text')) or str(r.get('stored_path','')).lower().endswith('.txt'):
                        try:
                            with open(r['stored_path'], 'r', encoding='utf-8', errors='ignore') as fh:
                                texts.append(fh.read(5000))
                        except Exception:
                            pass
            except Exception:
                pass
        lowered='\n'.join(texts).lower(); hits=[p for p in self.BLOCKED_PATTERNS if p in lowered]
        gates['blocked_pattern_gate']={'pass': not hits, 'hits': hits}
        if hits: risk+=60; rec.append('Remove or reject blocked bypass/doxxing/private-access patterns.')
        gdpr=self.gdpr.latest(case_id) if self.gdpr else None; gdpr_decision=(gdpr or {}).get('decision','not_evaluated')
        gates['gdpr_gate']={'pass': gdpr_decision not in {'blocked_until_manual_review'}, 'decision': gdpr_decision}
        if gdpr_decision in {'review_required','blocked_until_manual_review'}: risk+=25; rec.append('Complete GDPR/legal basis review before export.')
        graph=self.graph_analytics.latest(case_id) if self.graph_analytics else None; graph_score=int((graph or {}).get('risk_score',0) or 0)
        gates['graph_risk_gate']={'pass': graph_score<70, 'risk_score': graph_score}; risk+=min(25, graph_score//4)
        if graph_score>=70: rec.append('Review high-risk graph edges and identity associations.')
        rel=self.reliability.latest_for_case(case_id) if self.reliability else []; low=[r for r in rel if r.get('score',0)<50]
        gates['source_reliability_gate']={'pass': not low, 'low_reliability_count': len(low)}
        if low: risk+=min(25, 8*len(low)); rec.append('Corroborate or downgrade low-reliability sources.')
        evidence_count=self._count('local_evidence_items_75',case_id); audit_count=len(self.db.all('SELECT event_id FROM audit_events WHERE case_id=? LIMIT 2',[case_id]))
        gates['evidence_gate']={'pass': evidence_count>0, 'evidence_count': evidence_count}; gates['audit_gate']={'pass': audit_count>0, 'audit_event_sample_count': audit_count}
        if evidence_count==0: risk+=20; rec.append('Add captured/hashable evidence before report export.')
        if audit_count==0: risk+=20; rec.append('Generate audit trail events through workspace actions.')
        risk=max(0,min(100,risk)); decision='pass'
        if hits: decision='blocked'
        elif risk>=75: decision='critical_review_required'
        elif risk>=40: decision='review_required'
        if not rec: rec.append('Security complex passed; maintain review-first export discipline.')
        findings={'blocked_hits':hits,'gdpr_decision':gdpr_decision,'graph_risk_score':graph_score,'low_reliability_count':len(low),'evidence_count':evidence_count,'audit_event_count_sample':audit_count}
        aid=new_id('sc100'); self.db.execute('INSERT INTO security_assessments_100 VALUES(?,?,?,?,?,?,?,?,?)',[aid,case_id,now_ts(),scope,risk,decision,dumps(gates),dumps(findings),dumps(rec)])
        self.audit.log('assess','security_complex_100',aid,case_id,{'decision':decision,'risk_score':risk})
        return self.get(aid)
    def spearhead_beta_readiness(self, case_id):
        sec=self.assess_case_security(case_id); claims=self._count('claims_v3_80',case_id); evidence=self._count('local_evidence_items_75',case_id); graph_nodes=self._count('investigation_graph_nodes_68',case_id)
        base=max(0, 70-sec['risk_score'])
        score=max(0, min(100, base + min(10,claims*3)+min(12,evidence*3)+min(8,graph_nodes*2)))
        missing=[]
        if evidence == 0: missing.append('evidence_vault_item')
        if graph_nodes == 0: missing.append('graph_node')
        if claims == 0: missing.append('reviewed_claim_or_claim_candidate')
        if sec['decision'] == 'blocked': missing.append('security_complex_pass')
        status='spearhead_beta_ready_with_review' if score>=75 and sec['decision'] in {'pass','review_required'} and not missing else 'not_beta_ready'
        return {'case_id':case_id,'build':'100.1','status':status,'readiness_score':score,'missing':missing,'security':sec,'metrics':{'claims':claims,'evidence_items':evidence,'graph_nodes':graph_nodes},'capabilities':['advanced_graph_analytics','controlled_ai_assist','source_reliability','authority_ready_package','security_complex','copy_paste_intake_fixed']}
    def get(self,aid):
        r=self.db.one('SELECT * FROM security_assessments_100 WHERE assessment_id=?',[aid])
        if not r: raise KeyError(aid)
        r['gates']=loads(r.pop('gates_json','{}'),{}); r['findings']=loads(r.pop('findings_json','{}'),{}); r['recommendations']=loads(r.pop('recommendations_json','[]'),[]); return r
    def latest(self,case_id):
        r=self.db.one('SELECT assessment_id FROM security_assessments_100 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',[case_id])
        return self.get(r['assessment_id']) if r else self.assess_case_security(case_id)
    def _table(self,name): return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?",[name]))
    def _count(self,table,case_id):
        if not self._table(table): return 0
        try: return int(self.db.one(f'SELECT COUNT(*) c FROM {table} WHERE case_id=?',[case_id])['c'])
        except Exception: return 0
