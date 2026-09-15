from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone,timedelta
from typing import Any,Mapping,Sequence
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
SECRET=re.compile(r'(?i)(token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key)')

class Build196CrossCaseIntelligenceService:
    BUILD='196.0'
    SOURCES=(
      ('eu_sanctions_map','EU sanctions map','EU','official_watchlist','guided_browser','DOCUMENTED'),
      ('un_security_council_list','UN Security Council consolidated list','global','official_watchlist','structured_connector','DOCUMENTED'),
      ('ofac_sdn','US OFAC sanctions data','US','official_watchlist','structured_connector','DOCUMENTED'),
      ('opensanctions_adapter','OpenSanctions adapter','global','aggregated_entity_data','credentialed_connector','DOCUMENTED'),
      ('wikidata_entity_linking','Wikidata entity linking','global','knowledge_graph','structured_connector','DOCUMENTED'),
      ('gleif_cross_case','GLEIF organization linking','global','official_company_data','structured_connector','DOCUMENTED'),
    )
    def __init__(self,db:Any,audit:Any,*,monitoring:Any,graph:Any,identity:Any,source_ai:Any,source_ops:Any,actor:str='system'):
        self.db,self.audit=db,audit;self.monitoring,self.graph,self.identity,self.source_ai,self.source_ops=monitoring,graph,identity,source_ai,source_ops;self.actor=actor
    def seed_sources(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!='FEDERATION SOURCES 196 ANLEGEN':raise PermissionError('explicit approval required')
        for sid,name,region,klass,mode,status in self.SOURCES:
            payload={'source_id':sid,'name':name,'region':region,'source_class':klass,'access_mode':mode,'status':status}
            self.db.execute('INSERT OR REPLACE INTO federation_source_profiles_196 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,name,region,klass,mode,status,'pending','pending','not_tested',dumps(['terms_review','fixture','live_probe','human_activation']),_hash(payload)))
        return {'profiles':len(self.SOURCES),'automatic_activation':False,'production_rule':'terms+fixture+live_probe+human_activation'}
    def create_scope(self,*,name:str,owner:str,case_ids:Sequence[str],purpose:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'FEDERATION SCOPE 196 {name} ANLEGEN':raise PermissionError('explicit approval required')
        if len(set(case_ids))<2:raise ValueError('at least two distinct cases required')
        sid,created=new_id('scope196'),now_ts();policy={'purpose_limitation':purpose,'default_deny':True,'minimal_disclosure':True,'cross_case_data_visible':False,'human_approval_required':True,'automatic_merge':False,'local_processing':True,'external_uploads':False}
        payload={'scope_id':sid,'name':name,'owner':owner,'case_ids':sorted(set(case_ids)),'policy':policy,'status':'draft','created_at':created}
        self.db.execute('INSERT INTO federation_scopes_196 VALUES(?,?,?,?,?,?,?,?)',(sid,name,owner,dumps(payload['case_ids']),dumps(policy),'draft',created,_hash(payload)));self._event(sid,'scope_created',payload)
        return payload
    def activate_scope(self,*,scope_id:str,approved_by:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'FEDERATION SCOPE 196 {scope_id} AKTIVIEREN':raise PermissionError('explicit approval required')
        if not self.db.one('SELECT scope_id FROM federation_scopes_196 WHERE scope_id=?',(scope_id,)):raise KeyError(scope_id)
        self.db.execute("UPDATE federation_scopes_196 SET status='active' WHERE scope_id=?",(scope_id,));self._event(scope_id,'scope_activated',{'approved_by':approved_by})
        return {'scope_id':scope_id,'status':'active','automatic_case_merge':False}
    def propose_candidate(self,*,scope_id:str,left_case_id:str,right_case_id:str,match_type:str,match_value:str,evidence:Sequence[Mapping[str,Any]],confirmation:str)->dict[str,Any]:
        if confirmation!=f'CROSS CASE 196 {scope_id} PRUEFEN':raise PermissionError('explicit approval required')
        scope=self.db.one('SELECT * FROM federation_scopes_196 WHERE scope_id=?',(scope_id,));
        if not scope or scope['status']!='active':raise PermissionError('active scope required')
        cases=set(json.loads(scope['case_ids_json']));
        if left_case_id not in cases or right_case_id not in cases or left_case_id==right_case_id:raise ValueError('cases outside scope')
        clean=self._redact(list(evidence));independent=len({str(x.get('source_id','')) for x in clean if x.get('independent')});scores=[float(x.get('score',0)) for x in clean];score=round(sum(scores)/len(scores),4) if scores else 0.0
        status='corroborated_candidate' if independent>=2 and score>=0.7 else 'candidate'
        cid,created=new_id('candidate196'),now_ts();key_hash=_hash({'type':match_type,'value':match_value.strip().lower()});hint=self._hint(match_type,match_value)
        payload={'candidate_id':cid,'scope_id':scope_id,'left_case_id':left_case_id,'right_case_id':right_case_id,'match_type':match_type,'match_key_hash':key_hash,'display_hint':hint,'evidence':clean,'score':score,'status':status,'created_at':created,'automatic_merge':False}
        self.db.execute('INSERT INTO cross_case_candidates_196 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,scope_id,left_case_id,right_case_id,match_type,key_hash,hint,dumps(clean),score,status,created,_hash(payload)));self._event(scope_id,'candidate_created',{'candidate_id':cid,'status':status})
        return payload
    def ai_assess(self,*,candidate_id:str,question:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'AI FEDERATION 196 {candidate_id} PRUEFEN':raise PermissionError('explicit approval required')
        row=self.db.one('SELECT * FROM cross_case_candidates_196 WHERE candidate_id=?',(candidate_id,));
        if not row:raise KeyError(candidate_id)
        evidence=json.loads(row['evidence_json']);sources={x.get('source_id') for x in evidence if x.get('source_id')};recs=['Quellenunabhängigkeit prüfen','Zeitliche Überschneidung der Fälle prüfen','Nur minimal erforderliche Felder offenlegen']
        if len(sources)<2:recs.insert(0,'Unabhängige Zweitquelle suchen')
        assessment={'question':question,'candidate_status':row['status'],'score':row['score'],'independent_sources':len(sources),'recommendations':recs,'limitations':['ai_output_is_not_fact','cross_case_match_is_not_identity_confirmation','human_review_required'],'automatic_action':False}
        aid,created=new_id('fedai196'),now_ts();self.db.execute('INSERT INTO federation_ai_assessments_196 VALUES(?,?,?,?,?)',(aid,candidate_id,dumps(assessment),created,_hash(assessment)))
        return {'assessment_id':aid,**assessment}
    def approve_disclosure(self,*,candidate_id:str,requested_by:str,approved_by:str,fields:Sequence[str],purpose:str,hours_valid:int,confirmation:str)->dict[str,Any]:
        if confirmation!=f'FEDERATION DISCLOSURE 196 {candidate_id} FREIGEBEN':raise PermissionError('explicit approval required')
        row=self.db.one('SELECT * FROM cross_case_candidates_196 WHERE candidate_id=?',(candidate_id,));
        if not row:raise KeyError(candidate_id)
        allowed={'display_hint','match_type','score','status','source_count'};chosen=[f for f in fields if f in allowed]
        if not chosen:raise ValueError('no permitted fields selected')
        did,created=new_id('disclosure196'),now_ts();expires=(datetime.now(timezone.utc)+timedelta(hours=max(1,min(hours_valid,168)))).isoformat()
        payload={'disclosure_id':did,'candidate_id':candidate_id,'requested_by':requested_by,'approved_by':approved_by,'fields':chosen,'purpose':purpose,'status':'approved','created_at':created,'expires_at':expires,'raw_match_value_disclosed':False}
        self.db.execute('INSERT INTO federation_disclosures_196 VALUES(?,?,?,?,?,?,?,?,?,?)',(did,candidate_id,requested_by,approved_by,dumps(chosen),purpose,'approved',created,expires,_hash(payload)));self._event(row['scope_id'],'disclosure_approved',{'disclosure_id':did,'candidate_id':candidate_id,'fields':chosen})
        return payload
    def dashboard(self,*,scope_id:str)->dict[str,Any]:
        scope=self.db.one('SELECT * FROM federation_scopes_196 WHERE scope_id=?',(scope_id,));
        if not scope:raise KeyError(scope_id)
        n=lambda q:int((self.db.one(q,(scope_id,)) or {'n':0})['n'])
        return {'build':self.BUILD,'scope_id':scope_id,'status':scope['status'],'candidate_count':n('SELECT COUNT(*) n FROM cross_case_candidates_196 WHERE scope_id=?'),'corroborated_candidates':n("SELECT COUNT(*) n FROM cross_case_candidates_196 WHERE scope_id=? AND status='corroborated_candidate'"),'guided_summary':'Möglichen Match sehen → Quellen prüfen → minimale Freigabe → Fälle getrennt lassen','opsec':{'default_deny':True,'minimal_disclosure':True,'raw_match_values_hidden':True,'automatic_merge':False,'external_uploads':False}}
    def _hint(self,kind:str,value:str)->str:
        v=value.strip();return f'{kind}: {v[:2]}…{v[-2:]}' if len(v)>4 else f'{kind}: verborgen'
    def _redact(self,v:Any)->Any:
        if isinstance(v,Mapping):return {k:('[REDACTED]' if SECRET.search(str(k)) else self._redact(x)) for k,x in v.items()}
        if isinstance(v,list):return [self._redact(x) for x in v]
        return v
    def _event(self,scope_id:str,event_type:str,payload:Mapping[str,Any])->None:
        row=self.db.one('SELECT event_hash FROM federation_events_196 WHERE scope_id=? ORDER BY created_at DESC LIMIT 1',(scope_id,));prev=row['event_hash'] if row else '';eid,created=new_id('fedevent196'),now_ts();body={'event_id':eid,'scope_id':scope_id,'event_type':event_type,'actor':self.actor,'created_at':created,'payload':self._redact(dict(payload)),'prev_hash':prev};eh=_hash(body);self.db.execute('INSERT INTO federation_events_196 VALUES(?,?,?,?,?,?,?,?)',(eid,scope_id,event_type,self.actor,created,dumps(body['payload']),prev,eh))
