from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode('utf-8')).hexdigest()
def _dt(v: str) -> datetime:
    d=datetime.fromisoformat(v.replace('Z','+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

class Build166MissingPersonWorkflowService:
    BUILD='166.0'
    MISSION='Time-critical, review-first missing-person OSINT workflow'
    SENSITIVE=re.compile(r'(password|token|secret|api[_-]?key|authorization|cookie|session)',re.I)
    RISK_LEVELS={'low','medium','high','critical'}
    LEAD_PRIORITIES={'low','medium','high','critical'}
    VERIFICATION={'unverified','partially_verified','corroborated','disputed','rejected'}

    def __init__(self, db: Any, audit: Any, *, temporal: Any|None=None,
                 social: Any|None=None, correlation: Any|None=None,
                 cockpit: Any|None=None, actor: str='system') -> None:
        self.db=db; self.audit=audit; self.temporal=temporal
        self.social=social; self.correlation=correlation; self.cockpit=cockpit; self.actor=actor

    def open_workflow(self, *, case_id: str, subject: Mapping[str,Any],
                      risk_profile: Mapping[str,Any], legal_basis: str,
                      opened_by: str|None=None, confirmation: str) -> dict[str,Any]:
        if confirmation!=f'MISSING 166 {case_id} STARTEN':
            raise PermissionError('explicit missing-person workflow approval required')
        if not case_id.strip() or not legal_basis.strip(): raise ValueError('case_id and legal_basis required')
        safe_subject=dict(subject); safe_risk=dict(risk_profile)
        if self.SENSITIVE.search(_canon({'subject':safe_subject,'risk':safe_risk})):
            raise ValueError('credentials or session material are prohibited')
        level=str(safe_risk.get('risk_level','medium')).lower()
        if level not in self.RISK_LEVELS: raise ValueError('invalid risk level')
        safe_risk.update({'risk_level':level,'public_only':True,'no_contact_or_interaction':True,
                          'protect_vulnerable_person':True,'automatic_identity_confirmation':False})
        wid=new_id('missing166'); now=now_ts(); payload={'case_id':case_id,'subject':safe_subject,'risk':safe_risk,'legal_basis':legal_basis}
        self.db.execute('INSERT INTO missing_person_cases_166 VALUES(?,?,?,?,?,?,?,?,?,?)',(
            wid,case_id,dumps(safe_subject),dumps(safe_risk),legal_basis.strip(),'active',opened_by or self.actor,now,now,_hash(payload)))
        self.audit.log('missing_person_workflow_opened_166','missing_person_workflow',wid,case_id,{'risk_level':level})
        return self.workflow(wid)

    def add_sighting(self, workflow_id: str, *, observed_at: str, location: Mapping[str,Any],
                     source_ref: str, source_type: str='public_source', description: str='',
                     confidence: float=.5, verification_status: str='unverified',
                     provenance: Mapping[str,Any]|None=None, reported_at: str|None=None) -> dict[str,Any]:
        self._workflow(workflow_id)
        _dt(observed_at); _dt(reported_at or now_ts())
        if not source_ref.strip(): raise ValueError('source_ref required')
        if not 0<=confidence<=1: raise ValueError('confidence outside range')
        if verification_status not in self.VERIFICATION: raise ValueError('invalid verification status')
        loc=dict(location); prov=dict(provenance or {})
        if self.SENSITIVE.search(_canon({'location':loc,'provenance':prov})): raise ValueError('sensitive material prohibited')
        sid=new_id('sighting166'); payload={'workflow_id':workflow_id,'observed_at':observed_at,'location':loc,'source_ref':source_ref,'confidence':confidence,'verification':verification_status}
        self.db.execute('INSERT INTO missing_person_sightings_166 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(
            sid,workflow_id,observed_at,reported_at or now_ts(),dumps(loc),source_ref,source_type,description[:2000],confidence,verification_status,dumps(prov),_hash(payload)))
        self.audit.log('missing_person_sighting_added_166','missing_person_sighting',sid,self._workflow(workflow_id)['case_id'],{'verification_status':verification_status})
        return {'sighting_id':sid,**payload,'provenance':prov,'review_required':True}

    def add_contact(self, workflow_id: str, *, label: str, relationship_type: str,
                    relevance_score: float, person_ref: str|None=None, last_contact_at: str|None=None,
                    source_refs: Iterable[str]=(), risk_flags: Iterable[str]=()) -> dict[str,Any]:
        self._workflow(workflow_id)
        if not 0<=relevance_score<=1: raise ValueError('relevance score outside range')
        if last_contact_at: _dt(last_contact_at)
        cid=new_id('contact166'); refs=list(dict.fromkeys(map(str,source_refs))); flags=list(dict.fromkeys(map(str,risk_flags)))
        payload={'workflow_id':workflow_id,'label':label,'relationship_type':relationship_type,'relevance_score':relevance_score,'person_ref':person_ref,'last_contact_at':last_contact_at,'source_refs':refs,'risk_flags':flags}
        self.db.execute('INSERT INTO missing_person_contacts_166 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(
            cid,workflow_id,person_ref,label[:300],relationship_type[:100],relevance_score,last_contact_at,dumps(refs),dumps(flags),'needs_review',_hash(payload)))
        return {'contact_id':cid,**payload,'review_status':'needs_review'}

    def add_location(self, workflow_id: str, *, label: str, location: Mapping[str,Any],
                     location_type: str, relevance_score: float, temporal: Mapping[str,Any]|None=None,
                     source_refs: Iterable[str]=()) -> dict[str,Any]:
        self._workflow(workflow_id)
        if not 0<=relevance_score<=1: raise ValueError('relevance score outside range')
        lid=new_id('location166'); refs=list(dict.fromkeys(map(str,source_refs))); tmp=dict(temporal or {})
        for k in ('valid_from','valid_to','observed_at'):
            if tmp.get(k): _dt(str(tmp[k]))
        payload={'workflow_id':workflow_id,'label':label,'location':dict(location),'location_type':location_type,'relevance_score':relevance_score,'temporal':tmp,'source_refs':refs}
        self.db.execute('INSERT INTO missing_person_locations_166 VALUES(?,?,?,?,?,?,?,?,?,?)',(
            lid,workflow_id,label[:300],dumps(dict(location)),location_type[:100],relevance_score,dumps(tmp),dumps(refs),'needs_review',_hash(payload)))
        return {'location_id':lid,**payload,'review_status':'needs_review'}

    def create_lead(self, workflow_id: str, *, lead_type: str, title: str,
                    detail: Mapping[str,Any], priority: str='medium',
                    source_refs: Iterable[str]=(), assigned_to: str|None=None) -> dict[str,Any]:
        wf=self._workflow(workflow_id)
        if priority not in self.LEAD_PRIORITIES: raise ValueError('invalid priority')
        if self.SENSITIVE.search(_canon(detail)): raise ValueError('sensitive material prohibited')
        lid=new_id('lead166'); now=now_ts(); refs=list(dict.fromkeys(map(str,source_refs)))
        payload={'workflow_id':workflow_id,'lead_type':lead_type,'title':title,'detail':dict(detail),'priority':priority,'source_refs':refs,'assigned_to':assigned_to}
        self.db.execute('INSERT INTO missing_person_leads_166 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(
            lid,workflow_id,lead_type[:100],title[:500],dumps(dict(detail)),priority,dumps(refs),'open',assigned_to,now,now,_hash(payload)))
        self.audit.log('missing_person_lead_created_166','missing_person_lead',lid,wf['case_id'],{'priority':priority,'lead_type':lead_type})
        return {'lead_id':lid,**payload,'status':'open'}

    def last_seen(self, workflow_id: str) -> dict[str,Any]|None:
        row=self.db.one('''SELECT * FROM missing_person_sightings_166 WHERE workflow_id=?
          AND verification_status IN ('partially_verified','corroborated')
          ORDER BY observed_at DESC, confidence DESC LIMIT 1''',(workflow_id,))
        if not row: return None
        out=dict(row); out['location']=loads(out.pop('location_json'),{}); out['provenance']=loads(out.pop('provenance_json'),{}); return out

    def situation(self, workflow_id: str) -> dict[str,Any]:
        wf=self._workflow(workflow_id); sightings=self.db.all('SELECT * FROM missing_person_sightings_166 WHERE workflow_id=? ORDER BY observed_at DESC',(workflow_id,))
        contacts=self.db.all('SELECT * FROM missing_person_contacts_166 WHERE workflow_id=? ORDER BY relevance_score DESC',(workflow_id,))
        locations=self.db.all('SELECT * FROM missing_person_locations_166 WHERE workflow_id=? ORDER BY relevance_score DESC',(workflow_id,))
        leads=self.db.all('SELECT * FROM missing_person_leads_166 WHERE workflow_id=? ORDER BY CASE priority WHEN "critical" THEN 4 WHEN "high" THEN 3 WHEN "medium" THEN 2 ELSE 1 END DESC, created_at',(workflow_id,))
        verified=sum(r['verification_status']=='corroborated' for r in sightings); disputed=sum(r['verification_status']=='disputed' for r in sightings)
        last=self.last_seen(workflow_id)
        gaps=[]
        if not last: gaps.append('no_verified_last_seen')
        if not contacts: gaps.append('no_priority_contacts')
        if not locations: gaps.append('no_priority_locations')
        if not any(r['source_refs_json']!='[]' for r in leads): gaps.append('leads_without_source_support')
        return {'workflow':wf,'last_seen':last,'counts':{'sightings':len(sightings),'corroborated_sightings':verified,'disputed_sightings':disputed,'contacts':len(contacts),'locations':len(locations),'open_leads':sum(r['status']=='open' for r in leads)},'priority_contacts':[dict(r) for r in contacts[:10]],'priority_locations':[dict(r) for r in locations[:10]],'open_leads':[dict(r) for r in leads if r['status']=='open'][:20],'intelligence_gaps':gaps,'review_required':True}

    def ai_assist(self, workflow_id: str, *, task_type: str='next_steps', context: Mapping[str,Any]|None=None) -> dict[str,Any]:
        if task_type not in {'next_steps','risk_triage','source_gaps','timeline_review'}: raise ValueError('unsupported AI task')
        state=self.situation(workflow_id); context=dict(context or {})
        safe={k:('[REDACTED]' if self.SENSITIVE.search(str(k)) else v) for k,v in context.items()}
        suggestions=[]; risk=state['workflow']['risk_profile'].get('risk_level','medium')
        if state['last_seen'] is None: suggestions.append({'priority':'critical','action':'establish_last_verified_sighting','reason':'no corroborated or partially verified sighting'})
        if state['counts']['disputed_sightings']: suggestions.append({'priority':'high','action':'resolve_conflicting_sightings','reason':f"{state['counts']['disputed_sightings']} disputed sightings"})
        if not state['priority_contacts']: suggestions.append({'priority':'high','action':'identify_recent_public_contacts','reason':'contact network not yet mapped'})
        if not state['priority_locations']: suggestions.append({'priority':'high','action':'derive_location_pivots_from_verified_sources','reason':'no priority locations recorded'})
        if risk in {'high','critical'}: suggestions.append({'priority':'critical','action':'accelerate_authority_handover_and_preservation','reason':f'{risk} vulnerability/risk profile'})
        suggestions.append({'priority':'medium','action':'run_source_diversity_check','reason':'avoid single-source confirmation'})
        output={'task_type':task_type,'suggestions':suggestions,'intelligence_gaps':state['intelligence_gaps'],'limitations':['OSINT leads are not proof','no covert contact or tracking','location claims require independent verification','human review required'],'review_required':True}
        opsec={'local_only':True,'external_model_called':False,'automatic_action':False,'sensitive_content_persisted':False,'input_redacted':safe!=context,'public_only':True}
        aid=new_id('missingai166'); payload={'assessment_id':aid,'workflow_id':workflow_id,'output':output,'opsec':opsec}
        self.db.execute('INSERT INTO missing_person_ai_assessments_166 VALUES(?,?,?,?,?,?,?,?,?,?)',(
            aid,workflow_id,task_type,_hash(safe),dumps(output),dumps(opsec),'local_deterministic',1,now_ts(),_hash(payload)))
        return {**payload,'automatic_identity_confirmation':False}

    def generate_sitrep(self, workflow_id: str, *, generated_by: str,
                       confirmation: str) -> dict[str,Any]:
        wf=self._workflow(workflow_id)
        if confirmation!=f'SITREP 166 {workflow_id} ERSTELLEN': raise PermissionError('explicit SITREP approval required')
        state=self.situation(workflow_id)
        previous=self.db.one('SELECT sequence_no,payload_sha256 FROM missing_person_sitreps_166 WHERE workflow_id=? ORDER BY sequence_no DESC LIMIT 1',(workflow_id,))
        seq=(int(previous['sequence_no'])+1) if previous else 1; prev_hash=previous['payload_sha256'] if previous else None
        summary={'case_id':wf['case_id'],'subject':wf['subject'],'risk_profile':wf['risk_profile'],'last_seen':state['last_seen'],'counts':state['counts'],'intelligence_gaps':state['intelligence_gaps'],'priority_contacts':state['priority_contacts'][:5],'priority_locations':state['priority_locations'][:5],'open_leads':state['open_leads'][:10],'methodological_notice':'OSINT intelligence lead; independent authority verification required'}
        sid=new_id('sitrep166'); payload={'sitrep_id':sid,'workflow_id':workflow_id,'sequence_no':seq,'summary':summary,'previous_sha256':prev_hash}
        digest=_hash(payload)
        self.db.execute('INSERT INTO missing_person_sitreps_166 VALUES(?,?,?,?,?,?,?,?,?)',(
            sid,workflow_id,seq,generated_by,dumps(summary),'RESTRICTED - MISSING PERSON OSINT',now_ts(),prev_hash,digest))
        self.audit.log('missing_person_sitrep_generated_166','missing_person_sitrep',sid,wf['case_id'],{'sequence_no':seq})
        return {**payload,'payload_sha256':digest,'classification':'RESTRICTED - MISSING PERSON OSINT'}

    def workflow(self, workflow_id: str) -> dict[str,Any]: return self._workflow(workflow_id)
    def _workflow(self, workflow_id: str) -> dict[str,Any]:
        row=self.db.one('SELECT * FROM missing_person_cases_166 WHERE workflow_id=?',(workflow_id,))
        if not row: raise KeyError('missing-person workflow not found')
        out=dict(row); out['subject']=loads(out.pop('subject_json'),{}); out['risk_profile']=loads(out.pop('risk_profile_json'),{}); return out
