from __future__ import annotations
import hashlib,json,re
from typing import Any,Mapping,Sequence
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
SECRET=re.compile(r'(?i)(token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key|client[_-]?secret)')
INJECTION=re.compile(r'(?i)(ignore previous instructions|reveal (the )?system prompt|bypass policy|execute this command|developer message)')

class Build200EvidenceIntelligencePlatformService:
    BUILD='200.0'
    PRODUCT_NAME='EagleEye Evidence Intelligence Platform 2.0'
    COHORT=('gleif_lei_live','crossref_rest_live','gdelt_doc_live','openalex_live','congress_live','knesset_odata_live','federal_register_live','world_bank_live','internet_archive_cdx_190','github_events_watch')
    def __init__(self,db:Any,audit:Any,*,pilot_ai:Any,enterprise:Any,workspace:Any,source_ops:Any,graph:Any,identity:Any,monitoring:Any,verification:Any,capture:Any,redteam:Any,recovery:Any,base_dir:Any,actor:str='system'):
        self.db,self.audit=db,audit;self.pilot_ai=pilot_ai;self.enterprise=enterprise;self.workspace=workspace;self.source_ops=source_ops;self.graph=graph;self.identity=identity;self.monitoring=monitoring;self.verification=verification;self.capture=capture;self.redteam=redteam;self.recovery=recovery;self.base_dir=base_dir;self.actor=actor
    def seed_release_cohort(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!='PLATFORM SOURCES 200 ANLEGEN':raise PermissionError('explicit approval required')
        created=now_ts()
        for sid in self.COHORT:
            p={'source_id':sid,'cohort':'phase6_release','required':True,'fixture_ok':False,'parser_ok':False,'live_ok':False,'terms_ok':False,'active':False,'checked_at':created}
            self.db.execute('INSERT OR REPLACE INTO platform_source_cohort_200 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,'phase6_release',1,0,0,0,0,0,'',created,_hash(p)))
        return {'cohort':'phase6_release','sources':len(self.COHORT),'automatic_activation':False}
    def record_source_gate(self,*,source_id:str,fixture_ok:bool,parser_ok:bool,live_ok:bool,terms_ok:bool,active:bool,last_error:str='',confirmation:str)->dict[str,Any]:
        if confirmation!=f'PLATFORM SOURCE 200 {source_id} PRUEFEN':raise PermissionError('explicit approval required')
        if source_id not in self.COHORT:raise KeyError(source_id)
        if active and not all((fixture_ok,parser_ok,live_ok,terms_ok)):raise ValueError('source gates incomplete')
        created=now_ts();p={'source_id':source_id,'fixture_ok':fixture_ok,'parser_ok':parser_ok,'live_ok':live_ok,'terms_ok':terms_ok,'active':active,'last_error':last_error,'checked_at':created}
        self.db.execute('UPDATE platform_source_cohort_200 SET fixture_ok=?,parser_ok=?,live_ok=?,terms_ok=?,active=?,last_error=?,checked_at=?,payload_sha256=? WHERE source_id=?',(int(fixture_ok),int(parser_ok),int(live_ok),int(terms_ok),int(active),last_error[:500],created,_hash(p),source_id))
        return {**p,'production_ready':all((fixture_ok,parser_ok,live_ok,terms_ok,active)),'automatic_activation':False}
    def index_case_documents(self,*,case_id:str,document_ids:Sequence[str],confirmation:str)->dict[str,Any]:
        if confirmation!=f'CASE INDEX 200 {case_id} AUFBAUEN':raise PermissionError('explicit approval required')
        chunks=[]
        for did in document_ids:
            row=self.db.one('SELECT document_id,source_ref,text_content FROM extracted_documents_199 WHERE document_id=? AND case_id=?',(did,case_id))
            if not row:continue
            text=row['text_content'];parts=[text[i:i+1800] for i in range(0,len(text),1600)] or ['']
            for n,part in enumerate(parts,1):
                cid,created=new_id('chunk200'),now_ts();section=f'chunk:{n}';p={'chunk_id':cid,'case_id':case_id,'document_id':did,'source_ref':row['source_ref'],'section_ref':section,'text':part,'embedding_ref':'local-hash:'+_hash(part)[:24]}
                self.db.execute('INSERT INTO case_index_chunks_200 VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,case_id,did,row['source_ref'],section,part,max(1,len(part)//4),p['embedding_ref'],created,_hash(p)));chunks.append(p)
        return {'case_id':case_id,'documents_indexed':len(set(x['document_id'] for x in chunks)),'chunks':len(chunks),'local_index':True,'external_uploads':False}
    def create_case_chat(self,*,case_id:str,title:str,created_by:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'CASE INVESTIGATOR 200 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
        sid,created=new_id('casechat200'),now_ts();policy={'case_bound':True,'sources_before_models':True,'citation_required':True,'automatic_action':False,'human_review_required':True,'prompt_injection_isolation':True,'local_retrieval':True};p={'session_id':sid,'case_id':case_id,'title':title,'created_by':created_by,'status':'active','policy':policy,'created_at':created}
        self.db.execute('INSERT INTO case_chat_sessions_200 VALUES(?,?,?,?,?,?,?,?)',(sid,case_id,title,created_by,'active',dumps(policy),created,_hash(p)));return p
    def chat(self,*,session_id:str,message:str,max_sources:int=6,confirmation:str)->dict[str,Any]:
        if confirmation!=f'CASE INVESTIGATOR 200 {session_id} SENDEN':raise PermissionError('explicit approval required')
        s=self.db.one('SELECT * FROM case_chat_sessions_200 WHERE session_id=?',(session_id,));
        if not s:raise KeyError(session_id)
        safe=self._redact_text(message);terms={x.lower() for x in re.findall(r'[\wÄÖÜäöüß-]{4,}',safe)}
        rows=self.db.all('SELECT * FROM case_index_chunks_200 WHERE case_id=?',(s['case_id'],))
        ranked=[]
        for r in rows:
            score=sum(1 for t in terms if t in r['text_content'].lower());ranked.append((score,r))
        selected=[r for score,r in sorted(ranked,key=lambda x:x[0],reverse=True) if score>0][:max_sources]
        if not selected:selected=[r for _,r in ranked[:max_sources]]
        citations=[{'source_ref':r['source_ref'],'section_ref':r['section_ref'],'document_id':r['document_id']} for r in selected]
        inj=any(INJECTION.search(r['text_content']) for r in selected);warnings=[]
        if inj:warnings.append('Mindestens ein Quellenabschnitt enthält mögliche Prompt-Injection und wurde nur als Daten behandelt.')
        if selected:
            evidence=' '.join(r['text_content'][:420] for r in selected)
            answer=f'Quellengebundene Fallauswertung auf Basis von {len(selected)} Abschnitten: {evidence[:2200]}'
        else:answer='Im Fallindex wurden keine passenden Quellen gefunden. Zuerst Quellen erfassen und indexieren.'
        actions=[{'action':'review_citations','requires_approval':True},{'action':'test_hypothesis','requires_approval':True},{'action':'open_evidence_graph','requires_approval':True}]
        created=now_ts();uid,aid=new_id('chatmsg200'),new_id('chatmsg200')
        self.db.execute('INSERT INTO case_chat_messages_200 VALUES(?,?,?,?,?,?,?,?,?,?)',(uid,session_id,'user',safe,dumps([]),dumps({}),dumps([]),0,created,_hash({'id':uid,'content':safe})))
        self.db.execute('INSERT INTO case_chat_messages_200 VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,session_id,'assistant',answer,dumps(citations),dumps({'chunks':len(selected),'prompt_injection_candidate':inj}),dumps(actions),1,created,_hash({'id':aid,'answer':answer,'citations':citations})))
        return {'session_id':session_id,'answer':answer,'citations':citations,'warnings':warnings,'proposed_actions':actions,'automatic_action':False,'human_review_required':True,'sources_before_models':True}
    def run_reference_case(self,*,case_id:str,scenario:str,user_level:str,checks:Mapping[str,bool],metrics:Mapping[str,Any],confirmation:str)->dict[str,Any]:
        if confirmation!=f'REFERENCE CASE 200 {case_id} ABSCHLIESSEN':raise PermissionError('explicit approval required')
        required=('intake','source_plan','source_execution','document_extraction','hypotheses','verification','graph','chat','case_file')
        blockers=[x for x in required if not checks.get(x,False)]
        if int(metrics.get('false_attributions',1))>0:blockers.append('false_attributions')
        status='passed' if not blockers else 'blocked';rid,created=new_id('reference200'),now_ts();p={'run_id':rid,'case_id':case_id,'scenario':scenario,'user_level':user_level,'checks':dict(checks),'metrics':dict(metrics),'status':status,'blockers':blockers,'created_at':created}
        self.db.execute('INSERT INTO reference_cases_200 VALUES(?,?,?,?,?,?,?,?,?)',(rid,case_id,scenario,user_level,dumps(dict(checks)),dumps(dict(metrics)),status,created,_hash(p)));return p
    def benchmark(self,*,name:str,metrics:Mapping[str,float],thresholds:Mapping[str,float],confirmation:str)->dict[str,Any]:
        if confirmation!=f'QUALITY BENCHMARK 200 {name} PRUEFEN':raise PermissionError('explicit approval required')
        failed=[]
        for k,v in thresholds.items():
            actual=float(metrics.get(k,-1));
            if k.endswith('_max'):
                base=k[:-4];actual=float(metrics.get(base,-1));
                if actual<0 or actual>v:failed.append(base)
            elif actual<v:failed.append(k)
        status='passed' if not failed else 'blocked';bid,created=new_id('benchmark200'),now_ts();p={'benchmark_id':bid,'name':name,'metrics':dict(metrics),'thresholds':dict(thresholds),'failed':failed,'status':status,'created_at':created}
        self.db.execute('INSERT INTO quality_benchmarks_200 VALUES(?,?,?,?,?,?,?)',(bid,name,dumps(dict(metrics)),dumps(dict(thresholds)),status,created,_hash(p)));return p
    def release_gate(self,*,checks:Mapping[str,bool],confirmation:str)->dict[str,Any]:
        if confirmation!='PLATFORM RELEASE 200 PRUEFEN':raise PermissionError('explicit approval required')
        required=('tests_passed','compile_passed','startup_passed','backup_restore_passed','redteam_passed','no_critical_findings','source_cohort_validated','reference_cases_passed','chat_citations_validated','no_legacy_fallback','loopback_only','sbom_present','signature_verified')
        blockers=[x for x in required if not checks.get(x,False)]
        status='candidate_pass' if not blockers else 'blocked';gid,created=new_id('release200'),now_ts();p={'gate_id':gid,'version':'200.0','checks':dict(checks),'blockers':blockers,'status':status,'human_approval_required':True,'automatic_release':False,'created_at':created}
        self.db.execute('INSERT INTO release_gates_200 VALUES(?,?,?,?,?,?,?,?)',(gid,'200.0',dumps(dict(checks)),dumps(blockers),status,1,created,_hash(p)));return p
    def phase6_status(self)->dict[str,Any]:
        cohort=self.db.all('SELECT * FROM platform_source_cohort_200');active=sum(int(r['active']) for r in cohort);refs=self.db.all('SELECT * FROM reference_cases_200');passed=sum(1 for r in refs if r['status']=='passed')
        return {'build':'200.0','product':self.PRODUCT_NAME,'phase6':'complete_candidate','source_cohort_total':len(cohort),'source_cohort_active':active,'reference_cases':len(refs),'reference_cases_passed':passed,'production_certified':False,'external_audit_required':True}
    def _redact_text(self,text:str)->str:return re.sub(r'(?i)(token|api[_-]?key|password|authorization|cookie|session|secret)\s*[:=]\s*\S+',r'\1=[REDACTED]',text)
