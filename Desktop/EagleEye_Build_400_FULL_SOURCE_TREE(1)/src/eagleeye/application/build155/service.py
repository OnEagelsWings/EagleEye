from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from typing import Any, Mapping
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

REVIEW_TYPES={'legal','technical'}
REVIEW_STATUSES={'approved','rejected','needs_changes','expired','revoked'}
GATE_STATES={'REGISTERED','LEGAL_REVIEW','TECHNICAL_REVIEW','SANDBOX','PRODUCTION','DEGRADED','SUSPENDED','RETIRED'}

def _canonical(v: Any)->str:
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _digest(v: Any)->str:
    return hashlib.sha256(_canonical(v).encode()).hexdigest()
def _parse(ts: str|None):
    if not ts: return None
    return datetime.fromisoformat(ts.replace('Z','+00:00'))

class Build155SourceContractGateService:
    BUILD='155.0'; MISSION='Source Contract Gate'
    def __init__(self, db: Any, audit: Any, *, runtime: Any, observability: Any|None=None, actor='system'):
        self.db=db; self.audit=audit; self.runtime=runtime; self.observability=observability; self.actor=actor

    def submit_review(self, connector_id: str, *, review_type: str, status: str, reviewer: str,
                      evidence_reference: str, findings: Mapping[str,Any]|None=None,
                      valid_until: str|None=None) -> dict[str,Any]:
        self.runtime.get_spec(connector_id)
        if review_type not in REVIEW_TYPES: raise ValueError('Ungültiger Review-Typ')
        if status not in REVIEW_STATUSES: raise ValueError('Ungültiger Review-Status')
        if status=='approved' and not evidence_reference.strip(): raise ValueError('Freigabe benötigt einen Prüfnachweis')
        if valid_until and _parse(valid_until) <= datetime.now(timezone.utc): raise ValueError('Review darf nicht bereits abgelaufen sein')
        prior=self.db.one('SELECT review_id FROM source_contract_reviews_155 WHERE connector_id=? AND review_type=? ORDER BY reviewed_at DESC LIMIT 1',(connector_id,review_type))
        payload={'connector_id':connector_id,'review_type':review_type,'status':status,'reviewer':reviewer,'evidence_reference':evidence_reference,'findings':dict(findings or {}),'valid_until':valid_until}
        rid=new_id('review155')
        self.db.execute('INSERT INTO source_contract_reviews_155(review_id,connector_id,review_type,status,reviewer,reviewed_at,valid_until,evidence_reference,findings_json,evidence_sha256,supersedes_review_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (rid,connector_id,review_type,status,reviewer,now_ts(),valid_until,evidence_reference,dumps(dict(findings or {})),_digest(payload),(prior or {}).get('review_id')))
        self.audit.log('source_review_155','connector',connector_id,None,{'review_id':rid,'type':review_type,'status':status,'reviewer':reviewer})
        return self.review(rid)

    def review(self, review_id: str)->dict[str,Any]:
        row=self.db.one('SELECT * FROM source_contract_reviews_155 WHERE review_id=?',(review_id,))
        if not row: raise KeyError('Review nicht gefunden')
        row['findings']=loads(row.pop('findings_json'),{})
        return row

    def _latest_valid(self, connector_id: str, review_type: str)->dict[str,Any]|None:
        row=self.db.one('SELECT * FROM source_contract_reviews_155 WHERE connector_id=? AND review_type=? ORDER BY reviewed_at DESC LIMIT 1',(connector_id,review_type))
        if not row or row['status']!='approved': return None
        expiry=_parse(row.get('valid_until'))
        if expiry and expiry <= datetime.now(timezone.utc): return None
        return row

    def evaluate(self, connector_id: str)->dict[str,Any]:
        spec=self.runtime.get_spec(connector_id); legal=self._latest_valid(connector_id,'legal'); technical=self._latest_valid(connector_id,'technical')
        health=self.db.one('SELECT status,schema_drift,consecutive_failures FROM connector_health_154 WHERE connector_id=? ORDER BY checked_at DESC LIMIT 1',(connector_id,)) or {}
        latest=self.db.one('SELECT decision,expires_at FROM source_gate_decisions_155 WHERE connector_id=? ORDER BY decided_at DESC LIMIT 1',(connector_id,)) or {}
        state='REGISTERED'
        if spec['lifecycle_status']=='retired' or latest.get('decision')=='RETIRED': state='RETIRED'
        elif spec['lifecycle_status']=='suspended' or latest.get('decision')=='SUSPENDED': state='SUSPENDED'
        elif not legal: state='LEGAL_REVIEW'
        elif not technical: state='TECHNICAL_REVIEW'
        elif health.get('schema_drift') or int(health.get('consecutive_failures') or 0)>=3: state='DEGRADED'
        elif spec['lifecycle_status']=='production' and spec['contract_state']=='accepted': state='PRODUCTION'
        else: state='SANDBOX'
        return {'connector_id':connector_id,'gate_state':state,'legal_review_id':legal and legal['review_id'],'technical_review_id':technical and technical['review_id'],'health':health,'executable':state=='PRODUCTION','review_first':True}

    def decide(self, connector_id: str, *, decision: str, reason: str, actor: str, confirmation: str, expires_at: str|None=None)->dict[str,Any]:
        decision=decision.upper()
        if decision not in {'PRODUCTION','SUSPENDED','RETIRED','SANDBOX'}: raise ValueError('Ungültige Gate-Entscheidung')
        if confirmation != f'SOURCE GATE 155 {connector_id} {decision}': raise PermissionError('Explizite Gate-Bestätigung fehlt')
        current=self.evaluate(connector_id)
        if decision=='PRODUCTION' and (not current['legal_review_id'] or not current['technical_review_id']): raise PermissionError('Produktivfreigabe erfordert gültige Legal- und Technical-Reviews')
        lifecycle={'PRODUCTION':'production','SUSPENDED':'suspended','RETIRED':'retired','SANDBOX':'sandbox'}[decision]
        contract='accepted' if decision=='PRODUCTION' else ('revoked' if decision in {'SUSPENDED','RETIRED'} else 'unaccepted')
        before=self.runtime.get_spec(connector_id)['lifecycle_status']
        self.db.execute('UPDATE connector_specs_154 SET lifecycle_status=?,contract_state=?,updated_at=? WHERE connector_id=?',(lifecycle,contract,now_ts(),connector_id))
        payload={'connector_id':connector_id,'decision':decision,'reason':reason,'actor':actor,'legal':current['legal_review_id'],'technical':current['technical_review_id'],'expires_at':expires_at}
        did=new_id('gate155')
        self.db.execute('INSERT INTO source_gate_decisions_155(decision_id,connector_id,decision,reason,actor,decided_at,legal_review_id,technical_review_id,expires_at,snapshot_sha256) VALUES(?,?,?,?,?,?,?,?,?,?)',(did,connector_id,decision,reason,actor,now_ts(),current['legal_review_id'],current['technical_review_id'],expires_at,_digest(payload)))
        self.db.execute('INSERT INTO source_status_events_155(event_id,connector_id,previous_status,new_status,reason,actor,occurred_at) VALUES(?,?,?,?,?,?,?)',(new_id('state155'),connector_id,before,lifecycle,reason,actor,now_ts()))
        self.audit.log('source_gate_decision_155','connector',connector_id,None,{'decision':decision,'decision_id':did,'actor':actor})
        return self.evaluate(connector_id)|{'decision_id':did}

    def execute(self, request: Any)->dict[str,Any]:
        gate=self.assert_executable(request.connector_id)
        result=self.runtime.execute(request)
        result["source_gate_155"]={"gate_state":gate["gate_state"],"legal_review_id":gate["legal_review_id"],"technical_review_id":gate["technical_review_id"]}
        return result

    def assert_executable(self, connector_id: str)->dict[str,Any]:
        result=self.evaluate(connector_id)
        if not result['executable']: raise PermissionError(f"Connector durch Source Contract Gate blockiert: {result['gate_state']}")
        return result

    def catalog(self)->dict[str,Any]:
        specs=self.runtime.catalog()['connectors']; rows=[self.evaluate(s['connector_id'])|{'display_name':s['display_name']} for s in specs]
        return {'build':self.BUILD,'mission':self.MISSION,'sources':rows,'counts':{state:sum(r['gate_state']==state for r in rows) for state in GATE_STATES},'automatic_identity_confirmation':False}
