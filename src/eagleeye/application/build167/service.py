from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

def _canon(v: Any) -> str: return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
def _hash(v: Any) -> str: return hashlib.sha256(_canon(v).encode('utf-8')).hexdigest()
def _dt(v: str) -> datetime:
    d=datetime.fromisoformat(v.replace('Z','+00:00')); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

class Build167CrimeThreatWorkflowService:
    BUILD='167.0'
    MISSION='Review-first crime and threat intelligence workflow for lawful public-source investigations'
    SENSITIVE=re.compile(r'(password|token|secret|api[_-]?key|authorization|cookie|session)',re.I)
    RISK={'low','medium','high','critical'}
    VERIFY={'unverified','partially_verified','corroborated','disputed','rejected'}
    PRIORITY={'low','medium','high','critical'}
    ASSESS={'insufficient','plausible','supported','contradicted'}

    def __init__(self, db: Any, audit: Any, *, temporal: Any|None=None, social: Any|None=None,
                 correlation: Any|None=None, crawler: Any|None=None, cockpit: Any|None=None,
                 actor: str='system') -> None:
        self.db=db; self.audit=audit; self.temporal=temporal; self.social=social
        self.correlation=correlation; self.crawler=crawler; self.cockpit=cockpit; self.actor=actor
        self._ensure_ui_manifest()

    def open_workflow(self, *, case_id: str, title: str, scope: Mapping[str,Any], legal_basis: str,
                      risk_level: str='medium', opened_by: str|None=None, confirmation: str) -> dict[str,Any]:
        if confirmation != f'INVESTIGATION 167 {case_id} STARTEN':
            raise PermissionError('explicit crime/threat workflow approval required')
        if not case_id.strip() or not title.strip() or not legal_basis.strip(): raise ValueError('case, title and legal basis required')
        risk_level=risk_level.lower()
        if risk_level not in self.RISK: raise ValueError('invalid risk level')
        safe=dict(scope)
        if self.SENSITIVE.search(_canon(safe)): raise ValueError('credentials or session material prohibited')
        safe.update({'public_only':True,'no_contact_or_interaction':True,'no_intrusion':True,
                     'no_automated_accusation':True,'automatic_identity_confirmation':False,
                     'authority_verification_required':True})
        wid=new_id('investigation167'); now=now_ts(); payload={'case_id':case_id,'title':title,'scope':safe,'legal_basis':legal_basis,'risk_level':risk_level}
        self.db.execute('INSERT INTO crime_threat_cases_167 VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (wid,case_id,title[:500],dumps(safe),legal_basis.strip(),risk_level,'active',opened_by or self.actor,now,now,_hash(payload)))
        self.audit.log('crime_threat_workflow_opened_167','crime_threat_workflow',wid,case_id,{'risk_level':risk_level})
        return self.workflow(wid)

    def add_observation(self, workflow_id: str, *, observation_type: str, statement: Mapping[str,Any],
                        source_ref: str, confidence: float=.5, verification_status: str='unverified',
                        occurred_at: str|None=None, observed_at: str|None=None,
                        provenance: Mapping[str,Any]|None=None) -> dict[str,Any]:
        wf=self._workflow(workflow_id)
        if not source_ref.strip(): raise ValueError('source_ref required')
        if not 0<=confidence<=1: raise ValueError('confidence outside range')
        if verification_status not in self.VERIFY: raise ValueError('invalid verification status')
        if occurred_at: _dt(occurred_at)
        _dt(observed_at or now_ts())
        safe=dict(statement); prov=dict(provenance or {})
        if self.SENSITIVE.search(_canon({'statement':safe,'provenance':prov})): raise ValueError('sensitive material prohibited')
        oid=new_id('observation167'); payload={'workflow_id':workflow_id,'type':observation_type,'statement':safe,'source_ref':source_ref,'confidence':confidence,'verification':verification_status}
        self.db.execute('INSERT INTO crime_threat_observations_167 VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (oid,workflow_id,observation_type[:100],occurred_at,observed_at or now_ts(),source_ref,dumps(safe),confidence,verification_status,dumps(prov),_hash(payload)))
        self.audit.log('crime_threat_observation_added_167','crime_threat_observation',oid,wf['case_id'],{'verification_status':verification_status})
        return {'observation_id':oid,**payload,'review_required':True}

    def add_hypothesis(self, workflow_id: str, *, title: str, proposition: str,
                       supporting_refs: Iterable[str]=(), contradicting_refs: Iterable[str]=(),
                       assessment: str='insufficient') -> dict[str,Any]:
        self._workflow(workflow_id)
        if assessment not in self.ASSESS: raise ValueError('invalid assessment')
        if self.SENSITIVE.search(proposition): raise ValueError('sensitive material prohibited')
        support=list(dict.fromkeys(map(str,supporting_refs))); contra=list(dict.fromkeys(map(str,contradicting_refs)))
        hid=new_id('hypothesis167'); now=now_ts(); payload={'workflow_id':workflow_id,'title':title,'proposition':proposition,'supporting_refs':support,'contradicting_refs':contra,'assessment':assessment}
        self.db.execute('INSERT INTO crime_threat_hypotheses_167 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (hid,workflow_id,title[:500],proposition[:4000],dumps(support),dumps(contra),assessment,'open','needs_review',now,now,_hash(payload)))
        return {'hypothesis_id':hid,**payload,'status':'open','review_status':'needs_review'}

    def add_indicator(self, workflow_id: str, *, indicator_type: str, value: Mapping[str,Any], relevance: float,
                      source_refs: Iterable[str], temporal: Mapping[str,Any]|None=None) -> dict[str,Any]:
        self._workflow(workflow_id)
        if not 0<=relevance<=1: raise ValueError('relevance outside range')
        refs=list(dict.fromkeys(map(str,source_refs)))
        if not refs: raise ValueError('at least one source reference required')
        safe=dict(value); tmp=dict(temporal or {})
        if self.SENSITIVE.search(_canon(safe)): raise ValueError('sensitive material prohibited')
        for key in ('valid_from','valid_to','observed_at'):
            if tmp.get(key): _dt(str(tmp[key]))
        iid=new_id('indicator167'); payload={'workflow_id':workflow_id,'indicator_type':indicator_type,'value':safe,'relevance':relevance,'source_refs':refs,'temporal':tmp}
        self.db.execute('INSERT INTO crime_threat_indicators_167 VALUES(?,?,?,?,?,?,?,?,?)',
            (iid,workflow_id,indicator_type[:100],dumps(safe),relevance,dumps(refs),dumps(tmp),'needs_review',_hash(payload)))
        return {'indicator_id':iid,**payload,'review_status':'needs_review'}

    def link_entity(self, workflow_id: str, *, entity_ref: str, role_label: str, relevance: float,
                    basis_refs: Iterable[str], status: str='candidate') -> dict[str,Any]:
        self._workflow(workflow_id)
        if not 0<=relevance<=1: raise ValueError('relevance outside range')
        refs=list(dict.fromkeys(map(str,basis_refs)))
        if not refs: raise ValueError('basis references required')
        eid=new_id('entitylink167'); payload={'workflow_id':workflow_id,'entity_ref':entity_ref,'role_label':role_label,'relevance':relevance,'basis_refs':refs,'status':status}
        self.db.execute('INSERT INTO crime_threat_entities_167 VALUES(?,?,?,?,?,?,?,?,?)',
            (eid,workflow_id,entity_ref,role_label[:200],relevance,dumps(refs),status,'needs_review',_hash(payload)))
        return {'entity_link_id':eid,**payload,'review_status':'needs_review'}

    def create_lead(self, workflow_id: str, *, lead_type: str, title: str, detail: Mapping[str,Any],
                    priority: str='medium', source_refs: Iterable[str]=(), assigned_to: str|None=None) -> dict[str,Any]:
        wf=self._workflow(workflow_id)
        if priority not in self.PRIORITY: raise ValueError('invalid priority')
        if self.SENSITIVE.search(_canon(detail)): raise ValueError('sensitive material prohibited')
        refs=list(dict.fromkeys(map(str,source_refs))); lid=new_id('lead167'); now=now_ts(); payload={'workflow_id':workflow_id,'lead_type':lead_type,'title':title,'detail':dict(detail),'priority':priority,'source_refs':refs,'assigned_to':assigned_to}
        self.db.execute('INSERT INTO crime_threat_leads_167 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (lid,workflow_id,lead_type[:100],title[:500],dumps(dict(detail)),priority,dumps(refs),assigned_to,'open',now,now,_hash(payload)))
        self.audit.log('crime_threat_lead_created_167','crime_threat_lead',lid,wf['case_id'],{'priority':priority})
        return {'lead_id':lid,**payload,'status':'open'}

    def situation(self, workflow_id: str) -> dict[str,Any]:
        wf=self._workflow(workflow_id)
        obs=self.db.all('SELECT * FROM crime_threat_observations_167 WHERE workflow_id=? ORDER BY observed_at DESC',(workflow_id,))
        hypotheses=self.db.all('SELECT * FROM crime_threat_hypotheses_167 WHERE workflow_id=? ORDER BY updated_at DESC',(workflow_id,))
        indicators=self.db.all('SELECT * FROM crime_threat_indicators_167 WHERE workflow_id=? ORDER BY relevance DESC',(workflow_id,))
        entities=self.db.all('SELECT * FROM crime_threat_entities_167 WHERE workflow_id=? ORDER BY relevance DESC',(workflow_id,))
        leads=self.db.all("SELECT * FROM crime_threat_leads_167 WHERE workflow_id=? ORDER BY CASE priority WHEN 'critical' THEN 4 WHEN 'high' THEN 3 WHEN 'medium' THEN 2 ELSE 1 END DESC, created_at",(workflow_id,))
        corroborated=sum(r['verification_status']=='corroborated' for r in obs); disputed=sum(r['verification_status']=='disputed' for r in obs)
        gaps=[]
        if not obs: gaps.append('no_source_observations')
        if obs and not corroborated: gaps.append('no_corroborated_observation')
        if not hypotheses: gaps.append('no_explicit_hypotheses')
        if hypotheses and not any(loads(r['contradicting_refs_json'],[]) for r in hypotheses): gaps.append('hypotheses_without_counterevidence')
        if not entities: gaps.append('no_key_entities_mapped')
        if not indicators: gaps.append('no_reviewed_indicators')
        return {'workflow':wf,'counts':{'observations':len(obs),'corroborated_observations':corroborated,'disputed_observations':disputed,'hypotheses':len(hypotheses),'indicators':len(indicators),'entities':len(entities),'open_leads':sum(r['status']=='open' for r in leads)},'priority_entities':[dict(r) for r in entities[:10]],'priority_indicators':[dict(r) for r in indicators[:15]],'open_hypotheses':[dict(r) for r in hypotheses if r['status']=='open'][:15],'open_leads':[dict(r) for r in leads if r['status']=='open'][:20],'intelligence_gaps':gaps,'review_required':True}

    def ai_assist(self, workflow_id: str, *, task_type: str='next_steps', context: Mapping[str,Any]|None=None) -> dict[str,Any]:
        if task_type not in {'next_steps','threat_triage','hypothesis_review','source_gaps','key_person_review'}: raise ValueError('unsupported AI task')
        state=self.situation(workflow_id); context=dict(context or {})
        safe={k:('[REDACTED]' if self.SENSITIVE.search(str(k)) else v) for k,v in context.items()}
        suggestions=[]
        for gap in state['intelligence_gaps']:
            actions={'no_source_observations':'collect_lawful_public_source_observations','no_corroborated_observation':'seek_independent_corroboration','no_explicit_hypotheses':'formulate_testable_alternative_hypotheses','hypotheses_without_counterevidence':'actively_seek_disconfirming_evidence','no_key_entities_mapped':'map_relevant_entities_without_attributing_culpability','no_reviewed_indicators':'review_and_source_indicators'}
            suggestions.append({'priority':'high','action':actions[gap],'reason':gap})
        if state['counts']['disputed_observations']: suggestions.append({'priority':'high','action':'resolve_disputed_observations','reason':f"{state['counts']['disputed_observations']} disputed observations"})
        if state['workflow']['risk_level'] in {'high','critical'}: suggestions.append({'priority':'critical','action':'accelerate_preservation_and_authority_handover','reason':'high or critical assessed risk; independent authority decision required'})
        suggestions.append({'priority':'medium','action':'check_source_diversity_and_temporal_consistency','reason':'reduce confirmation bias and stale-context errors'})
        output={'task_type':task_type,'suggestions':suggestions,'intelligence_gaps':state['intelligence_gaps'],'limitations':['No prediction of criminality','Centrality is not culpability','No autonomous surveillance or intervention','All allegations remain unverified until independently established','Human review required'],'review_required':True}
        opsec={'local_only':True,'external_model_called':False,'automatic_action':False,'automatic_identity_confirmation':False,'automatic_accusation':False,'input_redacted':safe!=context,'public_only':True}
        aid=new_id('investigationai167'); payload={'assessment_id':aid,'workflow_id':workflow_id,'output':output,'opsec':opsec}
        self.db.execute('INSERT INTO crime_threat_ai_assessments_167 VALUES(?,?,?,?,?,?,?,?,?,?)',
            (aid,workflow_id,task_type,_hash(safe),dumps(output),dumps(opsec),'local_deterministic',1,now_ts(),_hash(payload)))
        return {**payload,'automatic_identity_confirmation':False}

    def generate_sitrep(self, workflow_id: str, *, generated_by: str, confirmation: str) -> dict[str,Any]:
        wf=self._workflow(workflow_id)
        if confirmation != f'SITREP 167 {workflow_id} ERSTELLEN': raise PermissionError('explicit SITREP approval required')
        state=self.situation(workflow_id); previous=self.db.one('SELECT sequence_no,payload_sha256 FROM crime_threat_sitreps_167 WHERE workflow_id=? ORDER BY sequence_no DESC LIMIT 1',(workflow_id,))
        seq=int(previous['sequence_no'])+1 if previous else 1; prev=previous['payload_sha256'] if previous else None
        summary={'case_id':wf['case_id'],'title':wf['title'],'risk_level':wf['risk_level'],'counts':state['counts'],'priority_entities':state['priority_entities'][:5],'priority_indicators':state['priority_indicators'][:8],'open_hypotheses':state['open_hypotheses'][:8],'open_leads':state['open_leads'][:10],'intelligence_gaps':state['intelligence_gaps'],'methodological_notice':'OSINT intelligence lead; allegations, identities, intent and culpability require independent authority verification'}
        sid=new_id('sitrep167'); payload={'sitrep_id':sid,'workflow_id':workflow_id,'sequence_no':seq,'summary':summary,'previous_sha256':prev}; digest=_hash(payload)
        self.db.execute('INSERT INTO crime_threat_sitreps_167 VALUES(?,?,?,?,?,?,?,?,?)',(sid,workflow_id,seq,generated_by,dumps(summary),'RESTRICTED - CRIME/THREAT OSINT',now_ts(),prev,digest))
        self.audit.log('crime_threat_sitrep_generated_167','crime_threat_sitrep',sid,wf['case_id'],{'sequence_no':seq})
        return {**payload,'payload_sha256':digest,'classification':'RESTRICTED - CRIME/THREAT OSINT'}

    def ui_manifest(self) -> dict[str,Any]:
        row=self.db.one('SELECT * FROM ui_workspace_manifest_167 ORDER BY created_at DESC LIMIT 1')
        return {'version':row['version'],'sections':loads(row['sections_json'],[]),'hidden_legacy_tabs':loads(row['hidden_legacy_tabs_json'],[]),'payload_sha256':row['payload_sha256']}

    def workflow(self, workflow_id: str) -> dict[str,Any]: return self._workflow(workflow_id)
    def _workflow(self, workflow_id: str) -> dict[str,Any]:
        row=self.db.one('SELECT * FROM crime_threat_cases_167 WHERE workflow_id=?',(workflow_id,))
        if not row: raise KeyError('crime/threat workflow not found')
        out=dict(row); out['scope']=loads(out.pop('scope_json'),{}); return out

    def _ensure_ui_manifest(self) -> None:
        if self.db.one('SELECT manifest_id FROM ui_workspace_manifest_167 LIMIT 1'): return
        sections=[
          {'tab':'overview','label':'Fallübersicht','contains':['cockpit','current risks','next steps']},
          {'tab':'investigation167','label':'Ermittlungszentrale','contains':['workflow','observations','hypotheses','indicators','leads','missing person']},
          {'tab':'research147','label':'Recherche & Quellen','contains':['research','connectors','social collection','controlled crawling']},
          {'tab':'capture150','label':'Beweise & Medien','contains':['capture','evidence','photos','replay']},
          {'tab':'graph_lab','label':'Analyse & Graph','contains':['identity','timeline','graph','contradictions','social correlation']},
          {'tab':'assistant140','label':'AI-Assistenz','contains':['local advisory AI','quality','benchmarks']},
          {'tab':'handover168','label':'Akte & Übergabe','contains':['authority dossier','chain of custody','export validation','handover receipt']},
          {'tab':'security143','label':'Sicherheit & Betrieb','contains':['OPSEC','access','governance','reliability','audit']},
        ]
        hidden=['entities','identity139','quality141','final145','auth146','connectors148','ecosystem149','research','workflow137','research_intelligence','intake','capture_identity','photos','evidence','evidence138','graph','timeline','contradictions','assistant','orchestrator','synthesis','governance','review','security','reliability','operations','release','export','audit']
        payload={'version':'167.0','sections':sections,'hidden_legacy_tabs':hidden}; self.db.execute('INSERT INTO ui_workspace_manifest_167 VALUES(?,?,?,?,?,?)',(new_id('uimanifest167'),'167.0',dumps(sections),dumps(hidden),now_ts(),_hash(payload)))
