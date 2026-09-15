from __future__ import annotations
import hashlib,json,re,html
from html.parser import HTMLParser
from typing import Any,Mapping,Sequence
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
SECRET=re.compile(r'(?i)(token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key|client[_-]?secret)')
INJECTION=re.compile(r'(?i)(ignore previous instructions|reveal (the )?system prompt|bypass policy|execute this command|developer message)')
SENTENCE=re.compile(r'(?<=[.!?])\s+')
class _TextExtractor(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','noscript','template'}:self.skip+=1
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript','template'} and self.skip:self.skip-=1
    def handle_data(self,data):
        if not self.skip and data.strip():self.parts.append(data.strip())

class Build199OperationalPilotCaseAIService:
    BUILD='199.0'
    SOURCES=(
      ('gleif_lei_live','GLEIF LEI API','GLOBAL','https://api.gleif.org/api/v1/lei-records','structured_connector','public'),
      ('crossref_rest_live','Crossref REST API','GLOBAL','https://api.crossref.org/works','structured_connector','public'),
      ('gdelt_doc_live','GDELT DOC 2.0','GLOBAL','https://api.gdeltproject.org/api/v2/doc/doc','structured_connector','public'),
      ('openalex_live','OpenAlex API','GLOBAL','https://api.openalex.org/works','credentialed_connector','api_key'),
      ('congress_live','Congress.gov API','US','https://api.congress.gov/v3','credentialed_connector','api_key'),
      ('knesset_odata_live','Knesset OData','IL','https://knesset.gov.il/Odata/ParliamentInfo.svc','structured_connector','public'),
      ('federal_register_live','Federal Register API','US','https://www.federalregister.gov/api/v1/documents.json','structured_connector','public'),
      ('world_bank_live','World Bank API','GLOBAL','https://api.worldbank.org/v2','structured_connector','public'),
    )
    def __init__(self,db:Any,audit:Any,*,enterprise:Any,workspace:Any,source_ai:Any,graph:Any,capture:Any,verification:Any,source_ops:Any,base_dir:Any,actor:str='system'):
        self.db,self.audit=db,audit;self.enterprise,self.workspace,self.source_ai,self.graph,self.capture,self.verification,self.source_ops=enterprise,workspace,source_ai,graph,capture,verification,source_ops;self.base_dir=base_dir;self.actor=actor
    def seed_sources(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!='PRODUCTIVE SOURCES 199 ANLEGEN':raise PermissionError('explicit approval required')
        for sid,name,region,endpoint,mode,auth in self.SOURCES:
            cfg={'auth':auth,'pagination':True,'rate_limit_respected':True,'request_timeout_seconds':30,'automatic_activation':False}
            self.db.execute('INSERT OR REPLACE INTO productive_source_profiles_199 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,name,region,endpoint,mode,'CONTRACT_VALIDATED','pending','not_tested','implemented','not_tested','inactive',dumps(cfg),_hash({'id':sid,'endpoint':endpoint,'cfg':cfg})))
        return {'profiles':len(self.SOURCES),'executable_contracts':len(self.SOURCES),'automatic_activation':False}
    def build_request(self,*,source_id:str,query:str,page:int=1,credential_ref:str|None=None)->dict[str,Any]:
        row=self.db.one('SELECT * FROM productive_source_profiles_199 WHERE source_id=?',(source_id,))
        if not row:raise KeyError(source_id)
        params={'query':query,'page':max(1,page)}
        if source_id=='gleif_lei_live':params={'filter[entity.legalName]':query,'page[number]':max(1,page),'page[size]':20}
        elif source_id=='crossref_rest_live':params={'query':query,'rows':20,'offset':(max(1,page)-1)*20,'mailto':'local-eagleeye@example.invalid'}
        elif source_id=='gdelt_doc_live':params={'query':query,'mode':'ArtList','format':'json','maxrecords':50}
        elif source_id=='openalex_live':params={'search':query,'page':max(1,page),'per-page':25}
        elif source_id=='federal_register_live':params={'conditions[term]':query,'page':max(1,page),'per_page':20}
        elif source_id=='world_bank_live':params={'format':'json','page':max(1,page),'per_page':50}
        headers={'Accept':'application/json','User-Agent':'EagleEye/199 local-review-first'}
        if credential_ref:headers['X-Credential-Reference']=credential_ref
        return {'source_id':source_id,'method':'GET','url':row['endpoint'],'params':params,'headers':headers,'execute_automatically':False}
    def validate_fixture(self,*,source_id:str,payload:Mapping[str,Any],confirmation:str)->dict[str,Any]:
        if confirmation!=f'PRODUCTIVE FIXTURE 199 {source_id} VALIDIEREN':raise PermissionError('explicit approval required')
        records=self._parse(source_id,payload)
        self.db.execute('UPDATE productive_source_profiles_199 SET fixture_status=?,parser_status=?,status=? WHERE source_id=?',('passed','passed','FIXTURE_VALIDATED',source_id))
        return {'source_id':source_id,'records':records,'count':len(records),'fixture_status':'passed','parser_status':'passed'}
    def record_live_probe(self,*,source_id:str,http_status:int,content_type:str,records_received:int,parser_ok:bool,terms_reviewed:bool,confirmation:str)->dict[str,Any]:
        if confirmation!=f'PRODUCTIVE LIVE 199 {source_id} PRUEFEN':raise PermissionError('explicit approval required')
        live='passed' if 200<=http_status<300 and 'json' in content_type.lower() and parser_ok else 'failed';terms='approved' if terms_reviewed else 'pending';status='LIVE_VALIDATED' if live=='passed' and terms=='approved' else 'FIXTURE_VALIDATED'
        self.db.execute('UPDATE productive_source_profiles_199 SET live_status=?,terms_status=?,status=? WHERE source_id=?',(live,terms,status,source_id))
        return {'source_id':source_id,'live_status':live,'terms_status':terms,'status':status,'records_received':records_received,'production_active':False}
    def activate_source(self,*,source_id:str,approved_by:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'PRODUCTIVE SOURCE 199 {source_id} AKTIVIEREN':raise PermissionError('explicit approval required')
        row=self.db.one('SELECT * FROM productive_source_profiles_199 WHERE source_id=?',(source_id,))
        if not row or row['fixture_status']!='passed' or row['parser_status']!='passed' or row['live_status']!='passed' or row['terms_status']!='approved':raise ValueError('source gates incomplete')
        self.db.execute('UPDATE productive_source_profiles_199 SET activation_status=?,status=? WHERE source_id=?',('active','PRODUCTION_ACTIVE',source_id));return {'source_id':source_id,'status':'PRODUCTION_ACTIVE','approved_by':approved_by,'automatic_activation':False}
    def extract_document(self,*,case_id:str,source_id:str,source_ref:str,content:Any,content_type:str,title:str='',language:str='und',confirmation:str)->dict[str,Any]:
        if confirmation!=f'AI EXTRACT 199 {case_id} AUSLESEN':raise PermissionError('explicit approval required')
        text=self._extract_text(content,content_type);text=re.sub(r'\s+',' ',text).strip()[:500000]
        entities=self._entities(text);claims=self._claims(text);inj=bool(INJECTION.search(text));did,created=new_id('document199'),now_ts();p={'document_id':did,'case_id':case_id,'source_id':source_id,'source_ref':source_ref,'content_type':content_type,'title':title,'language':language,'text':text,'claims':claims,'entities':entities,'prompt_injection_candidate':inj,'review_status':'candidate','created_at':created}
        self.db.execute('INSERT INTO extracted_documents_199 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(did,case_id,source_id,source_ref,content_type,title,language,text,dumps(claims),dumps(entities),int(inj),'candidate',created,_hash(p)));self._event(case_id,'document_extracted',{'document_id':did,'source_id':source_id,'prompt_injection_candidate':inj});return p
    def generate_hypotheses(self,*,case_id:str,question:str,document_ids:Sequence[str],max_hypotheses:int=5,confirmation:str)->dict[str,Any]:
        if confirmation!=f'AI HYPOTHESES 199 {case_id} ERSTELLEN':raise PermissionError('explicit approval required')
        docs=[]
        for did in document_ids:
            r=self.db.one('SELECT * FROM extracted_documents_199 WHERE document_id=? AND case_id=?',(did,case_id))
            if r:docs.append(r)
        candidates=[]
        for d in docs:
            for c in json.loads(d['claims_json']):
                statement=c['text'];refs=[d['source_ref']];score=min(.75,.35+.1*len(refs));test=[{'action':'find_independent_source','reason':'Hypothese benötigt unabhängige Korroboration'},{'action':'check_primary_source','reason':'Primärquelle priorisieren'},{'action':'check_timeline','reason':'zeitliche Plausibilität prüfen'}]
                hid,created=new_id('hypothesis199'),now_ts();p={'hypothesis_id':hid,'case_id':case_id,'statement':statement,'rationale':f'Aus quellengebundenem Text zur Frage: {question}','support_refs':refs,'contradiction_refs':[],'test_plan':test,'status':'working_hypothesis','confidence':score,'created_at':created}
                self.db.execute('INSERT INTO ai_hypotheses_199 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(hid,case_id,statement,p['rationale'],dumps(refs),dumps([]),dumps(test),'working_hypothesis',score,created,_hash(p)));candidates.append(p)
                if len(candidates)>=max_hypotheses:break
            if len(candidates)>=max_hypotheses:break
        return {'case_id':case_id,'question':question,'hypotheses':candidates,'hypotheses_are_not_facts':True,'automatic_case_update':False,'human_review_required':True}
    def create_chat(self,*,case_id:str,title:str,created_by:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'CASE CHAT 199 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
        sid,created=new_id('chat199'),now_ts();policy={'case_bound':True,'sources_before_models':True,'local_processing':True,'external_uploads':False,'automatic_actions':False,'secret_redaction':True,'prompt_injection_isolation':True};p={'session_id':sid,'case_id':case_id,'title':title,'created_by':created_by,'status':'active','policy':policy,'created_at':created};self.db.execute('INSERT INTO case_chat_sessions_199 VALUES(?,?,?,?,?,?,?,?)',(sid,case_id,title,created_by,'active',dumps(policy),created,_hash(p)));return p
    def chat(self,*,session_id:str,message:str,document_ids:Sequence[str]|None=None,confirmation:str)->dict[str,Any]:
        if confirmation!=f'CASE CHAT 199 {session_id} SENDEN':raise PermissionError('explicit approval required')
        s=self.db.one('SELECT * FROM case_chat_sessions_199 WHERE session_id=?',(session_id,));
        if not s:raise KeyError(session_id)
        safe=self._redact_text(message);docs=[]
        for did in document_ids or []:
            r=self.db.one('SELECT source_ref,title,text_content,prompt_injection_candidate FROM extracted_documents_199 WHERE document_id=? AND case_id=?',(did,s['case_id']))
            if r:docs.append(r)
        citations=[d['source_ref'] for d in docs];warnings=[]
        if any(d['prompt_injection_candidate'] for d in docs):warnings.append('Mindestens eine Quelle enthält mögliche Prompt-Injection und wird nur als Daten behandelt.')
        answer='Fallbezogene Auswertung: '
        if docs:
            snippets=[d['text_content'][:280] for d in docs]
            answer+=f'{len(docs)} Quellen wurden berücksichtigt. ' + ' '.join(snippets)[:1200]
        else:answer+='Es wurden keine Quellen übergeben; daher kann ich nur einen Rechercheplan liefern.'
        actions=[{'action':'review_sources','requires_approval':True},{'action':'generate_hypotheses','requires_approval':True}]
        if warnings:answer+=' '+warnings[0]
        created=now_ts();uid=new_id('chatmsg199');aid=new_id('chatmsg199');self.db.execute('INSERT INTO case_chat_messages_199 VALUES(?,?,?,?,?,?,?,?,?)',(uid,session_id,'user',safe,dumps([]),dumps([]),0,created,_hash({'id':uid,'content':safe})));self.db.execute('INSERT INTO case_chat_messages_199 VALUES(?,?,?,?,?,?,?,?,?)',(aid,session_id,'assistant',answer,dumps(citations),dumps(actions),1,created,_hash({'id':aid,'content':answer,'citations':citations})))
        return {'session_id':session_id,'answer':answer,'citations':citations,'warnings':warnings,'proposed_actions':actions,'automatic_action':False,'human_review_required':True}
    def record_pilot(self,*,case_id:str,scenario:str,user_level:str,metrics:Mapping[str,Any],findings:Sequence[Mapping[str,Any]],confirmation:str)->dict[str,Any]:
        if confirmation!=f'PILOT 199 {case_id} ABSCHLIESSEN':raise PermissionError('explicit approval required')
        required={'time_to_first_usable_result_minutes','time_to_case_file_minutes','false_attributions','completed_workflow'};m=dict(metrics);status='passed' if required.issubset(m) and bool(m.get('completed_workflow')) and int(m.get('false_attributions',1))==0 else 'needs_improvement';pid,created=new_id('pilot199'),now_ts();p={'pilot_id':pid,'case_id':case_id,'scenario':scenario,'user_level':user_level,'metrics':m,'findings':[dict(x) for x in findings],'status':status,'created_at':created};self.db.execute('INSERT INTO pilot_runs_199 VALUES(?,?,?,?,?,?,?,?,?)',(pid,case_id,scenario,user_level,dumps(m),dumps(p['findings']),status,created,_hash(p)));return p
    def _extract_text(self,content:Any,content_type:str)->str:
        if isinstance(content,Mapping):return self._json_text(content)
        if isinstance(content,(list,tuple)):return self._json_text(content)
        if isinstance(content,bytes):content=content.decode('utf-8','replace')
        text=str(content)
        if 'html' in content_type.lower():p=_TextExtractor();p.feed(text);return html.unescape(' '.join(p.parts))
        if 'json' in content_type.lower():
            try:return self._json_text(json.loads(text))
            except Exception:return text
        return text
    def _json_text(self,v:Any)->str:
        if isinstance(v,Mapping):return ' '.join(self._json_text(x) for k,x in v.items() if not SECRET.search(str(k)))
        if isinstance(v,(list,tuple)):return ' '.join(self._json_text(x) for x in v)
        return str(v)
    def _entities(self,text:str)->list[dict[str,Any]]:
        vals=[]
        for m in re.finditer(r'\b[A-ZÄÖÜ][\wÄÖÜäöüß-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß-]+){1,3}\b',text):
            val=m.group(0)
            if val not in [x['value'] for x in vals]:vals.append({'value':val,'type':'named_entity_candidate'})
            if len(vals)>=50:break
        return vals
    def _claims(self,text:str)->list[dict[str,Any]]:
        out=[]
        for s in SENTENCE.split(text):
            s=s.strip()
            if 25<=len(s)<=500 and re.search(r'\b(ist|war|wurde|hat|had|was|is|were|served|joined|born|died)\b',s,re.I):out.append({'text':s,'status':'candidate','requires_source_review':True})
            if len(out)>=40:break
        return out
    def _parse(self,source_id:str,payload:Mapping[str,Any])->list[dict[str,Any]]:
        if source_id=='gleif_lei_live':raw=payload.get('data',[])
        elif source_id=='crossref_rest_live':raw=payload.get('message',{}).get('items',[])
        elif source_id=='gdelt_doc_live':raw=payload.get('articles',[])
        elif source_id=='openalex_live':raw=payload.get('results',[])
        elif source_id=='federal_register_live':raw=payload.get('results',[])
        elif source_id=='world_bank_live':raw=payload[1] if isinstance(payload,list) and len(payload)>1 else payload.get('data',[])
        else:raw=payload.get('value',payload.get('results',payload.get('data',[])))
        if not isinstance(raw,list):raise ValueError('parser expected list records')
        return [{'source_record_id':str(x.get('id') or x.get('doi') or x.get('lei') or x.get('document_number') or i),'payload':self._redact(x),'review_status':'candidate'} for i,x in enumerate(raw)]
    def _redact(self,v:Any)->Any:
        if isinstance(v,Mapping):return {k:('[REDACTED]' if SECRET.search(str(k)) else self._redact(x)) for k,x in v.items()}
        if isinstance(v,list):return [self._redact(x) for x in v]
        return v
    def _redact_text(self,text:str)->str:return re.sub(r'(?i)(token|api[_-]?key|password|authorization|cookie|session)\s*[:=]\s*\S+',r'\1=[REDACTED]',text)
    def _event(self,case_id:str,event_type:str,payload:Mapping[str,Any])->None:
        row=self.db.one('SELECT event_hash FROM build199_events WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,));prev=row['event_hash'] if row else '';eid,created=new_id('event199'),now_ts();body={'event_id':eid,'case_id':case_id,'event_type':event_type,'actor':self.actor,'created_at':created,'payload':self._redact(dict(payload)),'prev_hash':prev};eh=_hash(body);self.db.execute('INSERT INTO build199_events VALUES(?,?,?,?,?,?,?,?)',(eid,case_id,event_type,self.actor,created,dumps(body['payload']),prev,eh))
