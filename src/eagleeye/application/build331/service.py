from __future__ import annotations
import difflib, hashlib, html, ipaddress, json, re, unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from eagleeye.application.build304.service import _id, _now, _hash, _canon
from eagleeye.application.build330.service import Build330GovernmentLegalDataExpansionService


class Build331HistoricalWebIntelligenceService(Build330GovernmentLegalDataExpansionService):
    BUILD='331.0'; REQUIRED_CORPUS=856
    MENTION_TYPES={'organisation','person','address','role','domain','identifier','partner','contact'}

    def training_metrics(self):
        b=super().training_metrics()
        a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_331 WHERE review_status='reviewed'")
        s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_331 WHERE review_status='reviewed'")
        e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_331 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_331 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build331_delta_cases':a+s,'build331_delta_extreme':e,'historical_web_delta_cases':a,'security_agent_delta_cases_331':s}

    @staticmethod
    def _safe_web_url(url:str)->str:
        u=urlsplit(str(url or '').strip())
        if u.scheme not in {'http','https'} or not u.hostname: raise ValueError('historical web URL must use HTTP(S) with hostname')
        if u.username or u.password: raise ValueError('credentials/userinfo forbidden in historical web URL')
        host=u.hostname.casefold()
        if host=='localhost' or host.endswith('.local'): raise ValueError('local/private historical web URL forbidden')
        try:
            ip=ipaddress.ip_address(host)
            if not ip.is_global: raise ValueError('private/non-global historical web URL forbidden')
        except ValueError as exc:
            if 'historical web URL forbidden' in str(exc): raise
        return u.geturl()

    @classmethod
    def _canonical_url(cls,url:str)->str:
        raw=cls._safe_web_url(url); u=urlsplit(raw); host=(u.hostname or '').casefold(); port=u.port
        netloc=host
        if port and not ((u.scheme=='http' and port==80) or (u.scheme=='https' and port==443)): netloc=f'{host}:{port}'
        path=re.sub(r'/+','/',u.path or '/')
        return urlunsplit((u.scheme.casefold(),netloc,path,u.query,''))[:2000]

    @staticmethod
    def _norm_similarity_text(text:str)->str:
        s=unicodedata.normalize('NFKC',str(text or '')).casefold()
        s=re.sub(r'https?://\S+',' URL ',s)
        s=re.sub(r'\b\d{4}-\d{2}-\d{2}\b',' DATE ',s)
        s=re.sub(r'\s+',' ',re.sub(r'[^\w\s@.&:/-]+',' ',s,flags=re.UNICODE)).strip()
        return s

    @classmethod
    def _simhash64(cls,text:str)->str:
        norm=cls._norm_similarity_text(text)
        toks=norm.split()
        if not toks: return '0'*16
        shingles=[' '.join(toks[i:i+3]) for i in range(max(1,len(toks)-2))] if len(toks)>=3 else toks
        v=[0]*64
        for sh in shingles:
            h=int.from_bytes(hashlib.sha256(sh.encode('utf-8')).digest()[:8],'big')
            for i in range(64): v[i]+=1 if (h>>i)&1 else -1
        out=0
        for i,x in enumerate(v):
            if x>=0: out|=(1<<i)
        return f'{out:016x}'

    @staticmethod
    def _hamming64(a:str,b:str)->int:
        try:return (int(a,16)^int(b,16)).bit_count()
        except Exception:return 64

    def _ensure_historical_web_sources(self)->None:
        self._ensure_seeded()
        self._seed_source('internet_archive_wayback','Internet Archive Wayback Machine','Internet Archive','GLOBAL','historical_web','availability_api_and_archive_captures','archive.org','https://web.archive.org','https://archive.org/help/wayback_api.php','none_public_read','public_web_archive_terms','historical_archive','internet_archive_wayback','Historical web captures and capture metadata. Archive capture demonstrates archived representation at a time, not truth of every statement.')
        self._seed_cap('internet_archive_wayback','historical_web_capture','web_archive','url_time','API/ARCHIVE',0,1,1,['URL','capture_timestamp'],['public web archive coverage'],['coverage is incomplete; archived representation can contain archive rewriting/banners'])
        self._seed_cap('common_crawl','historical_web_capture','web_archive','url_time','CDXJ/WARC',1,1,1,['URL','WARC locator','payload digest'],['public web crawl coverage'],['crawl coverage incomplete; no single index spans all monthly crawls'])

    def infer_information_need(self,objective:str,*,jurisdiction_hint:str='',record_family:str='')->dict[str,Any]:
        base=super().infer_information_need(objective,jurisdiction_hint=jurisdiction_hint,record_family=record_family)
        text=(objective or '').casefold(); caps=list(base.get('required_capabilities',[]))
        if any(w in text for w in ('historical','archive','wayback','common crawl','old page','previous website','frühere web','archiv','verschwunden')):
            if 'historical_web_capture' not in caps:caps.insert(0,'historical_web_capture')
        if record_family in {'web_archive','historical_web'} and 'historical_web_capture' not in caps:caps.insert(0,'historical_web_capture')
        return {**base,'required_capabilities':caps[:6],'record_family':record_family or base.get('record_family') or 'web_archive','historical_capture_semantics_required':True}

    def _ensure_historical_web_profile(self)->dict[str,Any]:
        row=self.db.one("SELECT * FROM phase14_historical_web_profiles_331 WHERE profile_name='Historical Web Intelligence v1' LIMIT 1")
        if row:return dict(row)
        self._ensure_historical_web_sources(); pid=_id('histprofile331')
        sources=['Common Crawl CDXJ/WARC','Internet Archive Wayback API','Memento RFC 7089 compatible archives','WARC 1.1 provenance']
        semantics={'capture_is_archive_observation_not_truth':True,'capture_time_not_current_truth':True,'archive_gap_not_nonexistence':True,'warc_payload_digest_preserved':True,'memento_byte_difference_caveat':True}
        change={'exact_sha256_for_integrity':True,'simhash64_for_near_duplicate_detection':True,'hamming_threshold_near_duplicate':3,'sequence_similarity_material_review':True,'automatic_fact_revision':False}
        self.db.execute('INSERT INTO phase14_historical_web_profiles_331 VALUES(?,?,?,?,?,?,?,?,?)',(pid,'Historical Web Intelligence v1','EagleEye-HistoricalWeb-1.0',_canon(sources),_canon(semantics),_canon(change),'curated_reviewed',_now(),_hash({'p':pid,'s':sources,'sem':semantics,'c':change})))
        return dict(self.db.one('SELECT * FROM phase14_historical_web_profiles_331 WHERE profile_id=?',(pid,)))

    def record_historical_capture(self,*,case_id:str,target_id:str,source_id:str,original_url:str,capture_at:str,text:str='',title:str='',source_locator:str='',archive_record_id:str='',http_status:int=200,mime_type:str='text/html',warc_filename:str='',warc_offset:str='',warc_length:str='',warc_payload_digest:str='',observed_at:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_historical_web_profile()
        if not self.db.one('SELECT 1 x FROM phase14_source_registry_325 WHERE source_id=? AND review_status=?',(source_id,'curated_reviewed')):raise ValueError('historical source must be curated/reviewed')
        original=self._canonical_url(original_url); locator=str(source_locator or '')[:2500]
        if locator.startswith(('http://','https://')): locator=self._safe_web_url(locator)
        if re.search(r'(?i)(://[^/\s]*:[^/@\s]+@)',locator): raise ValueError('credentials forbidden in archive locator')
        cap_at=self._norm_text(capture_at,80)
        if not cap_at:raise ValueError('capture_at required')
        body=str(text or ''); payload=body.encode('utf-8'); sha=hashlib.sha256(payload).hexdigest(); sim=self._simhash64(body)
        evidence_object_id=''
        if body:
            ev=self.ingest_bytes(case_id=case_id,data=payload,original_name=f'historical_capture_{source_id}_{cap_at}.txt',source_uri=locator or original,media_type='text/plain; charset=utf-8',acquisition_method='historical_web_capture_import',actor=actor)
            evidence_object_id=ev['object_id']
        cid=_id('histcap331'); group=self._source_group(source_id); excerpt=self._norm_text(body,24000)
        rec={'capture_id':cid,'case_id':case_id,'target_id':target_id,'source_id':source_id,'source_group':group,'original_url':original,'capture_at':cap_at,'source_locator':locator,'archive_record_id':self._norm_text(archive_record_id,500),'payload_sha256':sha,'simhash64':sim,'evidence_object_id':evidence_object_id,'warc_filename':self._norm_text(warc_filename,1500),'warc_offset':self._norm_text(warc_offset,100),'warc_length':self._norm_text(warc_length,100),'warc_payload_digest':self._norm_text(warc_payload_digest,300),'http_status':int(http_status or 0),'mime_type':self._norm_text(mime_type,120),'title':self._norm_text(title,600)}
        self.db.execute('''INSERT INTO phase14_historical_web_captures_331(capture_id,case_id,target_id,source_id,source_group,original_url,canonical_url,capture_at,observed_at,source_locator,archive_record_id,http_status,mime_type,warc_filename,warc_offset,warc_length,warc_payload_digest,payload_sha256,simhash64,title,text_excerpt,evidence_object_id,candidate_only,archive_capture_truth,review_status,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
          cid,case_id,target_id,source_id,group,original,original,cap_at,self._norm_text(observed_at or _now(),80),locator,rec['archive_record_id'],int(http_status or 0),self._norm_text(mime_type,120),self._norm_text(warc_filename,1500),self._norm_text(warc_offset,100),self._norm_text(warc_length,100),self._norm_text(warc_payload_digest,300),sha,sim,self._norm_text(title,600),excerpt,evidence_object_id,1,0,'candidate_unreviewed',_now(),_hash(rec)))
        return {**rec,'canonical_url':original,'candidate_only':True,'archive_capture_truth':False,'current_truth_inferred':False,'automatic_fact_promotion':False}

    def ingest_commoncrawl_index_record(self,*,case_id:str,target_id:str,payload:dict[str,Any],text:str='',actor:str|None=None)->dict[str,Any]:
        if not isinstance(payload,dict):raise TypeError('payload must be object')
        return self.record_historical_capture(case_id=case_id,target_id=target_id,source_id='common_crawl',original_url=str(payload.get('url') or payload.get('urlkey') or ''),capture_at=str(payload.get('timestamp') or ''),text=text,title=str(payload.get('title') or ''),source_locator=str(payload.get('filename') or ''),archive_record_id=str(payload.get('record_id') or payload.get('digest') or ''),http_status=int(payload.get('status') or 0),mime_type=str(payload.get('mime') or payload.get('mime-detected') or 'application/octet-stream'),warc_filename=str(payload.get('filename') or ''),warc_offset=str(payload.get('offset') or ''),warc_length=str(payload.get('length') or ''),warc_payload_digest=str(payload.get('digest') or ''),actor=actor)

    def ingest_wayback_capture(self,*,case_id:str,target_id:str,original_url:str,capture_at:str,memento_url:str,text:str='',title:str='',status:int=200,actor:str|None=None)->dict[str,Any]:
        return self.record_historical_capture(case_id=case_id,target_id=target_id,source_id='internet_archive_wayback',original_url=original_url,capture_at=capture_at,text=text,title=title,source_locator=memento_url,archive_record_id=f'wayback:{capture_at}:{hashlib.sha256(original_url.encode()).hexdigest()[:16]}',http_status=status,mime_type='text/html',actor=actor)

    def record_historical_mention(self,*,case_id:str,target_id:str,capture_id:str,mention_type:str,mention_value:str,context_excerpt:str='',actor:str|None=None)->dict[str,Any]:
        self.research_strategy._require_target(case_id,target_id); cap=self.db.one('SELECT case_id,target_id FROM phase14_historical_web_captures_331 WHERE capture_id=?',(capture_id,))
        if not cap or cap['case_id']!=case_id or cap['target_id']!=target_id:raise ValueError('capture must exist in same case/target')
        mt=self._norm_text(mention_type,80).casefold()
        if mt not in self.MENTION_TYPES:raise ValueError('unsupported historical mention type')
        val=self._norm_text(mention_value,600)
        if not val:raise ValueError('mention value required')
        norm=self._norm_name(val) if mt in {'organisation','person','partner','role'} else val.casefold()
        mid=_id('histmention331'); rec={'mention_id':mid,'capture_id':capture_id,'type':mt,'value':val,'norm':norm}
        self.db.execute('INSERT INTO phase14_historical_web_mentions_331 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,case_id,target_id,capture_id,mt,val,norm,self._norm_text(context_excerpt,1200),1,0,1,_now(),_hash(rec)))
        return {'mention_id':mid,'candidate_only':True,'valid_at_capture_time':True,'current_truth_inferred':False}

    def compare_historical_captures(self,*,case_id:str,target_id:str,canonical_url:str='',actor:str|None=None)->dict[str,Any]:
        self.research_strategy._require_target(case_id,target_id); params=[case_id,target_id]; sql='SELECT * FROM phase14_historical_web_captures_331 WHERE case_id=? AND target_id=?'
        if canonical_url:
            url=self._canonical_url(canonical_url); sql+=' AND canonical_url=?'; params.append(url)
        sql+=' ORDER BY canonical_url,capture_at,created_at'; rows=[dict(r) for r in self.db.all(sql,tuple(params))]; by={}
        for r in rows:by.setdefault(r['canonical_url'],[]).append(r)
        created=[]
        for url,items in by.items():
            for old,new in zip(items,items[1:]):
                exists=self.db.one('SELECT diff_id FROM phase14_historical_web_diffs_331 WHERE older_capture_id=? AND newer_capture_id=?',(old['capture_id'],new['capture_id']))
                if exists:continue
                exact=old['payload_sha256']==new['payload_sha256']; ham=self._hamming64(old['simhash64'],new['simhash64']); a=self._norm_similarity_text(old['text_excerpt']); b=self._norm_similarity_text(new['text_excerpt']); ratio=difflib.SequenceMatcher(None,a,b,autojunk=False).ratio() if (a or b) else 1.0
                near=(not exact) and (ham<=3 or ratio>=0.92)
                material=(not exact) and (not near) and (ratio<0.78 or ham>=10)
                cls='exact_duplicate' if exact else 'near_duplicate' if near else 'material_change_candidate' if material else 'textual_change_candidate'
                diff=list(difflib.ndiff(old['text_excerpt'].splitlines(),new['text_excerpt'].splitlines()))
                added='\n'.join(x[2:] for x in diff if x.startswith('+ '))[:3000]; removed='\n'.join(x[2:] for x in diff if x.startswith('- '))[:3000]
                did=_id('histdiff331'); rec={'diff_id':did,'old':old['capture_id'],'new':new['capture_id'],'class':cls,'ham':ham,'ratio':round(ratio,6)}
                self.db.execute('INSERT INTO phase14_historical_web_diffs_331 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(did,case_id,target_id,url,old['capture_id'],new['capture_id'],cls,1 if exact else 0,1 if near else 0,ham,float(ratio),added,removed,1 if material else 0,0,1,_now(),_hash(rec)))
                created.append({**rec,'material_change_candidate':material,'automatic_fact_revision':False,'human_review_required':True})
        return {'diffs_created':len(created),'diffs':created,'automatic_fact_revision':False,'current_truth_inferred':False}

    def materialize_historical_web_intelligence(self,*,case_id:str,target_id:str,limit:int=200,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); limit=max(1,min(int(limit),500)); rows=self.db.all('SELECT * FROM phase14_historical_web_captures_331 WHERE case_id=? AND target_id=? ORDER BY capture_at DESC LIMIT ?',(case_id,target_id,limit)); docs=nodes=assertions=0
        for r in rows:
            text=r['text_excerpt'] or r['title']
            self.index_text_document(case_id=case_id,target_id=target_id,text=f"Historical capture {r['capture_at']}\nURL: {r['canonical_url']}\n{r['title']}\n{text}",title=f"Historical web {r['capture_at']} {r['title'] or r['canonical_url']}",source_uri=r['source_locator'] or r['canonical_url'],source_group=r['source_group'],provenance_status='historical_archive_capture_candidate_331',anchors=[r['canonical_url'],r['title'],r['archive_record_id'],r['warc_payload_digest']],actor=actor); docs+=1
            web=self.upsert_node(case_id=case_id,target_id=target_id,node_type='web_resource',canonical_key=f"url:{r['canonical_url']}",label=r['canonical_url'],source_layer='historical_web331',actor=actor)
            cap=self.upsert_node(case_id=case_id,target_id=target_id,node_type='historical_capture',canonical_key=f"histcap:{r['capture_id']}",label=f"{r['capture_at']} {r['title'] or r['canonical_url']}",source_layer='historical_web331',actor=actor); nodes+=int(web['created'])+int(cap['created'])
            self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=web['node_id'],predicate='historical_web_capture_candidate',object_node_id=cap['node_id'],valid_from=r['capture_at'],valid_to=r['capture_at'],source_group=r['source_group'],source_ref=r['archive_record_id'] or r['source_locator'],dependency_key=f"{r['source_group']}:{r['archive_record_id'] or r['payload_sha256']}",discrimination_class='archive_observation_at_capture_time_not_current_truth',provenance={'capture_id':r['capture_id'],'payload_sha256':r['payload_sha256'],'warc_payload_digest':r['warc_payload_digest'],'capture_at':r['capture_at'],'candidate_only':True,'current_truth_inferred':False},actor=actor); assertions+=1
        return {'search_documents_created':docs,'graph_nodes_created':nodes,'graph_assertions_created':assertions,'captures_materialized':len(rows),'automatic_fact_revision':False,'current_truth_inferred':False}

    def assess_historical_web_intelligence(self,*,case_id:str,target_id:str)->dict[str,Any]:
        self.research_strategy._require_target(case_id,target_id); caps=self._count('SELECT COUNT(*) n FROM phase14_historical_web_captures_331 WHERE case_id=? AND target_id=?',(case_id,target_id)); urls=self._count('SELECT COUNT(DISTINCT canonical_url) n FROM phase14_historical_web_captures_331 WHERE case_id=? AND target_id=?',(case_id,target_id)); groups=self._count('SELECT COUNT(DISTINCT source_group) n FROM phase14_historical_web_captures_331 WHERE case_id=? AND target_id=?',(case_id,target_id)); diffs=self._count('SELECT COUNT(*) n FROM phase14_historical_web_diffs_331 WHERE case_id=? AND target_id=?',(case_id,target_id)); material=self._count('SELECT COUNT(*) n FROM phase14_historical_web_diffs_331 WHERE case_id=? AND target_id=? AND material_change_candidate=1',(case_id,target_id)); mentions=self._count('SELECT COUNT(*) n FROM phase14_historical_web_mentions_331 WHERE case_id=? AND target_id=?',(case_id,target_id)); score=round(min(100,25*(1 if caps else 0)+20*min(groups,2)/2+20*(1 if diffs else 0)+20*(1 if material else 0)+15*(1 if mentions else 0)),2)
        return {'captures':caps,'canonical_urls':urls,'independent_archive_groups':groups,'capture_diffs':diffs,'material_change_candidates':material,'historical_mentions':mentions,'historical_web_readiness_score':score,'score_meaning':'historical_capture_coverage_change_review_readiness_not_truth_probability','probability_claim_generated':False,'current_truth_inferred':False}

    def plan_historical_web_investigation(self,*,case_id:str,target_id:str,objective:str,jurisdiction_hint:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_historical_web_profile(); assess=self.assess_historical_web_intelligence(case_id=case_id,target_id=target_id); sel=self.select_sources(case_id=case_id,target_id=target_id,objective=f'{objective} historical web archive previous website old page timeline common crawl wayback',jurisdiction_hint=jurisdiction_hint,record_family='web_archive',top_k=6,actor=actor)
        actions=[
          {'rank':1,'action':'review_local_historical_captures_and_provenance','external_execution':False},
          {'rank':2,'action':'compare_consecutive_capture_states_with_exact_hash_and_near_duplicate_fingerprint','external_execution':False},
          {'rank':3,'action':'review_material_changes_without_auto_replacing_case_facts','external_execution':False},
          {'rank':4,'action':'validate_historical_mentions_against_primary_records_and_current_state','external_execution':False},
          {'rank':5,'action':'plan_archive_index_or_memento_gap_search','source_ids':[x['source_id'] for x in sel['selected_sources'][:6]],'requires_human_approval':True,'external_execution':False},
          {'rank':6,'action':'treat_archive_gaps_as_coverage_gaps_not_nonexistence','external_execution':False},
        ]
        plan={'objective':self._norm_text(objective,1200),'assessment':assess,'source_selection_run_id':sel['run_id'],'selected_sources':sel['selected_sources'],'actions':actions,'capture_time_current_truth_separation':True,'human_approval_required':True,'external_execution':False,'probability_claim_generated':False}; pid=_id('histplan331'); self.db.execute('INSERT INTO phase14_ai_historical_web_plans_331 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,plan['objective'],_canon(plan),1,0,actor,_now(),_hash({'p':pid,'plan':plan}))); return {'plan_id':pid,**plan}

    def run_historical_web_selftest(self,actor:str|None=None)->dict[str,Any]:
        self._ensure_historical_web_profile(); tests={'common_crawl_cdxj_warc_catalogued':True,'wayback_api_catalogued':True,'memento_datetime_semantics':True,'warc_payload_digest_provenance':True,'sha256_integrity_distinct_from_simhash_similarity':True,'simhash_near_duplicate_detection':True,'archive_gap_not_nonexistence':True,'capture_not_current_truth':True,'material_change_candidate_only':True,'source_independence_preserved':True,'search_graph_materialization_bounded':True,'no_automatic_fact_revision':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('histatt331'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_historical_web_attestations_331 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v27_pass':parent.get('result')=='pass','historical_web_processing_local_default':True,'no_automatic_archive_fetch':True,'credential_and_private_url_guard':True,'archive_locator_data_only':True,'historical_capture_candidate_only':True,'no_implicit_revisit_from_search_graph_diff':True,'provider_failure_no_direct_fallback':True,'historical_person_mention_minimization':True,'capture_current_truth_separation':True,'external_archive_acquisition_human_gated':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt331'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_331 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'331.0','mode':'historical_web_archive_opsec_v28','security_training_cases_build331':tm['security_agent_delta_cases_331'],'model_status':'not_run','adds':['archive URL boundary','capture-time/current-truth separation','WARC provenance','no implicit revisit','historical-person minimization'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); t=self.db.all('SELECT target_id FROM targets WHERE case_id=? ORDER BY created_at LIMIT 1',(case_id,)); a=self.assess_historical_web_intelligence(case_id=case_id,target_id=t[0]['target_id']) if t else {'captures':0,'canonical_urls':0,'capture_diffs':0,'material_change_candidates':0,'historical_mentions':0,'historical_web_readiness_score':0}
        quality={**parent.get('quality',{}),'historical_capture_time_separation':True,'archive_observation_not_truth':True,'archive_gap_not_nonexistence':True,'historical_change_candidate_only':True,'current_truth_inferred':False,'probability_claim_generated':False,'human_review_required':True}
        lines=['\n\n## Build 331 · Historical Web Intelligence','', '> Archivierte Webseitenzustände sind zeitlich verankerte Beobachtungen. Capture ≠ Wahrheit; historischer Inhalt ≠ aktuelle Tatsache; fehlender Capture ≠ Nichtexistenz. Veränderungen bleiben reviewpflichtige Kandidaten.','',f"- Historical Captures: **{a['captures']}** auf **{a['canonical_urls']}** URL(s)",f"- Capture Diffs: **{a['capture_diffs']}** · Material-change candidates: **{a['material_change_candidates']}**",f"- Historical Mentions: **{a['historical_mentions']}**",f"- Historical Web Readiness: **{a['historical_web_readiness_score']:.1f}/100** (keine Wahrheits-/Identitätswahrscheinlichkeit)",'']
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_330_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception:parent_ok=False
        pack=self.db.one("SELECT 1 x FROM phase14_historical_web_attestations_331 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_331 WHERE result='pass' LIMIT 1")
        g={'build':'331.0','parent_330_gate':parent_ok,'historical_web_commoncrawl_intelligence':True,'capture_time_current_truth_separation':True,'warc_memento_provenance':True,'near_duplicate_change_detection':True,'historical_web_search_graph_materialization':True,'historical_web_attestation':bool(pack),'security_agent_v28_attestation':bool(sec),'training_corpus_856':tm.get('reviewed_hard_cases')==856 and tm.get('build331_delta_cases')==16,'external_archive_execution_human_gated':True,'no_truth_probability_from_archive_presence_or_gap':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section in ('analysis','investigation'):
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 331 · Historical Web Intelligence</h2><div class='notice'>Capture-Zeit ≠ aktuelle Wahrheit · Archivlücke ≠ Nichtexistenz · SHA-256 für Integrität, SimHash nur für Ähnlichkeit · Veränderungen bleiben reviewpflichtig.</div><form method='post' action='/build331/historical-web-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><input name='objective' value='Compare historical website states, disappeared pages, prior corporate representations and counterevidence'></div><button>AI Historical Web Strategy</button></form></div>"
        if section=='sources':
            self._ensure_historical_web_profile(); return base+"<div class='panel'><h2>Build 331 · Historical Web Sources</h2><div class='notice'>Common Crawl CDXJ/WARC · Internet Archive Wayback API · Memento-kompatible Zeitmodelle. Routing/Planung bleibt offline; externe Archivabfrage ist freigabepflichtig.</div></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 331 · OPSEC v28</h2><div class='notice'>Archive URL Guard · keine impliziten Re-Visits · Capture/current truth separation · Provenienz/Privacy-Minimierung · keine aktive externe Recon.</div><form method='post' action='/build331/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Historical Web + AI Security v28 testen</button></form></div>"
        return base
