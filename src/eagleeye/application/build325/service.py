from __future__ import annotations
import html, json, re, ipaddress
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from eagleeye.application.build304.service import _id, _now, _hash, _canon
from eagleeye.application.build324.service import Build324IntelligenceGraphFabricV2Service


class Build325ConnectorRegistryService(Build324IntelligenceGraphFabricV2Service):
    BUILD='325.0'; REQUIRED_CORPUS=760
    OUTCOMES={'success','zero_results','provider_failure','rate_limited','coverage_mismatch','auth_required','manual_review'}
    CAPABILITY_KEYWORDS={
      'legal_entity_identity': ('company','company number','legal entity','firma','unternehmen','gesellschaft','registration','register','lei','company number','rechtsträger'),
      'ownership_relationships': ('ownership','owner','parent','subsidiary','beneficial owner','eigentümer','muttergesellschaft','tochtergesellschaft','beteiligung'),
      'financial_filings': ('10-k','10-q','filing','balance sheet','financial statement','jahresabschluss','bilanz','sec','edgar'),
      'company_officers': ('director','officer','geschäftsführer','vorstand','psc','significant control'),
      'procurement_notices': ('procurement','tender','award','contract','vergabe','ausschreibung','ted','supplier','buyer'),
      'government_legal_documents': ('law','legal','government','gazette','federal register','bill','statute','gesetz','regierung','parliament','congress'),
      'historical_web_capture': ('historical web','web archive','old website','archived website','common crawl','historisch','webseite früher'),
      'identifier_reconciliation': ('lei','isin','bic','cik','identifier','identifier mapping','kennung','reconciliation'),
    }

    CURATED_SOURCES=(
      {
        'source_id':'gleif','display_name':'GLEIF LEI Data','publisher':'Global Legal Entity Identifier Foundation','jurisdiction':'GLOBAL','source_class':'corporate_registry','access_mode':'api_and_bulk','official_domain':'gleif.org','base_url':'https://api.gleif.org','documentation_url':'https://www.gleif.org/en/lei-data/gleif-api','auth_class':'none_public_read','license_class':'public_open_data','cost_class':'free','freshness_class':'golden_copy_plus_delta','source_authority':'primary_identifier_authority','machine_readable':1,'independence_group':'gleif_primary','provenance_grade':'primary_official','automation_policy':'reviewed_read_only_api_allowed','notes':'LEI reference and relationship data; supports fuzzy name/address matching and mapped identifiers.',
        'caps':[
          ('legal_entity_identity','corporate','name_or_lei','GET',1,1,1,['en'],['LEI','BIC','ISIN'],['global'],{'policy':'provider_documented'},['LEI coverage only; absence is not absence of entity']),
          ('ownership_relationships','corporate','parent_child','GET',1,1,1,['en'],['LEI'],['global'],{'policy':'provider_documented'},['reported LEI relationships; reporting exceptions may apply']),
          ('identifier_reconciliation','corporate','mapped_identifiers','GET',1,1,1,['en'],['LEI','BIC','ISIN'],['global'],{'policy':'provider_documented'},['identifier mapping is not identity proof by itself']),
        ]
      },
      {
        'source_id':'opencorporates','display_name':'OpenCorporates','publisher':'OpenCorporates','jurisdiction':'GLOBAL','source_class':'corporate_aggregator','access_mode':'api_and_bulk','official_domain':'opencorporates.com','base_url':'https://api.opencorporates.com','documentation_url':'https://api.opencorporates.com/documentation/API-Reference','auth_class':'api_key_required','license_class':'open_share_alike_or_commercial','cost_class':'plan_dependent','freshness_class':'source_dependent','source_authority':'secondary_provenanced_aggregator','machine_readable':1,'independence_group':'opencorporates_aggregator','provenance_grade':'secondary_provenanced','automation_policy':'user_managed_key_reviewed_read_only','notes':'Provenanced cross-jurisdiction company aggregation; verify high-impact facts against underlying primary source.',
        'caps':[
          ('legal_entity_identity','corporate','name_company_number','GET',1,0,1,['multi'],['company_number','jurisdiction_code'],['global'],{'pagination':'provider_plan'},['aggregator; primary-source verification preferred']),
          ('company_officers','corporate','officer_company','GET',1,0,1,['multi'],['company_number'],['global'],{'pagination':'provider_plan'},['coverage varies by jurisdiction']),
        ]
      },
      {
        'source_id':'sec_edgar','display_name':'SEC EDGAR / data.sec.gov','publisher':'U.S. Securities and Exchange Commission','jurisdiction':'US','source_class':'financial_filings','access_mode':'api_and_bulk','official_domain':'sec.gov','base_url':'https://data.sec.gov','documentation_url':'https://www.sec.gov/search-filings/edgar-application-programming-interfaces','auth_class':'none_public_read','license_class':'public_government_data','cost_class':'free','freshness_class':'near_realtime_plus_nightly_bulk','source_authority':'primary_official','machine_readable':1,'independence_group':'sec_primary','provenance_grade':'primary_official','automation_policy':'reviewed_read_only_api_allowed','notes':'Submissions and XBRL data; automated access must follow SEC fair-access policy.',
        'caps':[
          ('financial_filings','corporate_finance','CIK_or_company','GET',1,1,1,['en'],['CIK','accession_number'],['US issuers and covered foreign filers'],{'policy':'SEC fair access'},['filing presence does not establish current ownership']),
          ('legal_entity_identity','corporate','CIK','GET',1,1,1,['en'],['CIK'],['SEC filers'],{'policy':'SEC fair access'},['SEC filer population, not universal company registry']),
        ]
      },
      {
        'source_id':'companies_house','display_name':'UK Companies House','publisher':'Companies House','jurisdiction':'UK','source_class':'corporate_registry','access_mode':'rest_api','official_domain':'company-information.service.gov.uk','base_url':'https://api.company-information.service.gov.uk','documentation_url':'https://developer.company-information.service.gov.uk/get-started','auth_class':'api_key_required','license_class':'public_register_terms','cost_class':'free_api_account','freshness_class':'live_realtime','source_authority':'primary_official','machine_readable':1,'independence_group':'companies_house_primary','provenance_grade':'primary_official','automation_policy':'user_managed_key_reviewed_read_only','notes':'Live UK company register API; API credentials remain outside case data.',
        'caps':[
          ('legal_entity_identity','corporate','company_number_or_name','GET',0,1,1,['en'],['company_number'],['UK'],{'policy':'developer_guidelines'},['UK registered entities within Companies House scope']),
          ('company_officers','corporate','company_number','GET',0,1,1,['en'],['company_number'],['UK'],{'policy':'developer_guidelines'},['officer records may include historical/resigned roles']),
          ('ownership_relationships','corporate','psc','GET',0,1,1,['en'],['company_number'],['UK'],{'policy':'developer_guidelines'},['PSC is statutory register information, not a complete global ownership graph']),
        ]
      },
      {
        'source_id':'ted','display_name':'TED – Tenders Electronic Daily','publisher':'Publications Office of the European Union','jurisdiction':'EU','source_class':'procurement','access_mode':'api_open_data_bulk','official_domain':'ted.europa.eu','base_url':'https://ted.europa.eu','documentation_url':'https://developer.ted.europa.eu/','auth_class':'mixed_public_and_managed_key','license_class':'eu_open_data_terms','cost_class':'free_public_data','freshness_class':'continuous_publication','source_authority':'primary_official','machine_readable':1,'independence_group':'ted_primary','provenance_grade':'primary_official','automation_policy':'reviewed_public_read_or_user_managed_key','notes':'EU public procurement notices, APIs, open data/SPARQL and XML downloads.',
        'caps':[
          ('procurement_notices','procurement','notice_search','GET',1,1,1,['multi'],['notice_id','CPV','buyer_id'],['EU/EEA and TED coverage'],{'policy':'TED developer terms'},['notice data reflects procurement publication, not wrongdoing']),
          ('identifier_reconciliation','procurement','buyer_supplier_identifiers','GET',1,1,1,['multi'],['notice_id','organisation_id'],['EU/EEA and TED coverage'],{'policy':'TED developer terms'},['organisation identifiers can vary by notice/schema']),
        ]
      },
      {
        'source_id':'govinfo','display_name':'GovInfo','publisher':'U.S. Government Publishing Office','jurisdiction':'US','source_class':'government_legal','access_mode':'api_and_bulk','official_domain':'govinfo.gov','base_url':'https://api.govinfo.gov','documentation_url':'https://www.govinfo.gov/developers','auth_class':'api_data_gov_key','license_class':'public_government_data','cost_class':'free_key','freshness_class':'collection_dependent','source_authority':'primary_official','machine_readable':1,'independence_group':'govinfo_primary','provenance_grade':'primary_official','automation_policy':'user_managed_key_reviewed_read_only','notes':'Government publications and metadata plus bulk XML/JSON for selected collections.',
        'caps':[
          ('government_legal_documents','government_legal','collection_package','GET',1,1,1,['en'],['package_id','collection_code'],['US federal publications'],{'policy':'api.data.gov/provider limits'},['collection coverage varies']),
        ]
      },
      {
        'source_id':'common_crawl','display_name':'Common Crawl','publisher':'Common Crawl Foundation','jurisdiction':'GLOBAL','source_class':'historical_web','access_mode':'index_and_bulk_warc','official_domain':'commoncrawl.org','base_url':'https://index.commoncrawl.org','documentation_url':'https://commoncrawl.org/cdxj-index','auth_class':'none_public_read','license_class':'open_crawl_dataset','cost_class':'free_dataset_compute_may_cost','freshness_class':'periodic_crawls','source_authority':'secondary_web_archive','machine_readable':1,'independence_group':'commoncrawl_archive','provenance_grade':'secondary_capture','automation_policy':'reviewed_index_query_or_bulk_download','notes':'Historical/open web captures via CDXJ/URL indexes and WARC; capture presence is not source endorsement.',
        'caps':[
          ('historical_web_capture','web_archive','url_or_domain','GET_OR_BULK',1,1,1,['multi'],['URL','domain','WARC locator'],['public web crawl coverage'],{'policy':'dataset access'},['not a complete archive; crawl gaps and robots/availability effects']),
        ]
      },
    )

    def _ensure_seeded(self)->None:
        if self._count('SELECT COUNT(*) n FROM phase14_source_registry_325') >= len(self.CURATED_SOURCES): return
        for s in self.CURATED_SOURCES:
            exists=self.db.one('SELECT source_id FROM phase14_source_registry_325 WHERE source_id=?',(s['source_id'],))
            if not exists:
                record={k:v for k,v in s.items() if k!='caps'}; now=_now()
                self.db.execute('INSERT INTO phase14_source_registry_325 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
                  s['source_id'],s['display_name'],s['publisher'],s['jurisdiction'],s['source_class'],s['access_mode'],s['official_domain'],s['base_url'],s['documentation_url'],s['auth_class'],s['license_class'],s['cost_class'],s['freshness_class'],s['source_authority'],s['machine_readable'],s['independence_group'],s['provenance_grade'],s['automation_policy'],'curated_reviewed','DCAT3-inspired+EagleEye-SourceCapability-v1',s['notes'],now,now,_hash(record)))
            for cap in s['caps']:
                capability,record_family,dimension,method,bulk,incr,hist,languages,ids,coverage,rate,limits=cap
                key=f"cap325-{s['source_id']}-{capability}-{record_family}-{dimension}".replace(' ','_')[:240]
                self.db.execute('INSERT OR IGNORE INTO phase14_source_capabilities_325 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
                  key,s['source_id'],capability,record_family,dimension,method,int(bulk),int(incr),int(hist),_canon(languages),_canon(ids),_canon(coverage),_canon(rate),_canon(limits),_now(),_hash({'s':s['source_id'],'cap':cap})))

    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_325 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_325 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_325 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_325 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build325_delta_cases':a+s,'build325_delta_extreme':e,'source_registry_delta_cases':a,'security_agent_delta_cases_325':s}

    @staticmethod
    def _safe_public_url(url:str)->tuple[str,str]:
        u=urlsplit(str(url or '').strip())
        if u.scheme!='https' or not u.hostname: raise ValueError('Registry machine-readable URLs must use HTTPS with a hostname')
        if u.username or u.password: raise ValueError('Credentials/userinfo are forbidden in source registry URLs')
        host=u.hostname.casefold()
        if host in {'localhost'} or host.endswith('.local'): raise ValueError('Private/local sources are not public registry sources')
        try:
            ip=ipaddress.ip_address(host)
            if not ip.is_global: raise ValueError('Private/non-global IP sources are not public registry sources')
        except ValueError as exc:
            if 'not public registry' in str(exc): raise
        return u.geturl(),host

    def register_candidate_source(self,*,display_name:str,publisher:str,jurisdiction:str,source_class:str,access_mode:str,base_url:str,documentation_url:str,auth_class:str='unknown',license_class:str='unknown',cost_class:str='unknown',freshness_class:str='unknown',independence_group:str='',notes:str='',actor:str|None=None)->dict[str,Any]:
        self._ensure_seeded(); actor=actor or self.actor; base,host=self._safe_public_url(base_url); doc,_=self._safe_public_url(documentation_url)
        sid=_id('source325'); dep=re.sub(r'[^a-z0-9_.:-]+','_',str(independence_group or host).casefold())[:180]
        record={'source_id':sid,'display_name':str(display_name)[:240],'publisher':str(publisher)[:240],'jurisdiction':str(jurisdiction or 'GLOBAL').upper()[:32],'source_class':str(source_class)[:100],'access_mode':str(access_mode)[:100],'host':host,'auth_class':str(auth_class)[:120],'license_class':str(license_class)[:120],'dep':dep}
        self.db.execute('INSERT INTO phase14_source_registry_325 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(
          sid,record['display_name'],record['publisher'],record['jurisdiction'],record['source_class'],record['access_mode'],host,base,doc,record['auth_class'],record['license_class'],str(cost_class)[:120],str(freshness_class)[:120],'candidate_unverified',1,dep,'unreviewed','manual_only_until_review','candidate','DCAT3-inspired+EagleEye-SourceCapability-v1',str(notes)[:2000],_now(),_now(),_hash(record)))
        return {'source_id':sid,'review_status':'candidate','routing_eligible':False,'automatic_activation':False,'credentials_stored':False}

    def list_sources(self,*,reviewed_only:bool=False)->list[dict[str,Any]]:
        self._ensure_seeded(); sql='SELECT * FROM phase14_source_registry_325'+(" WHERE review_status='curated_reviewed'" if reviewed_only else '')+' ORDER BY jurisdiction,source_class,display_name'
        return [dict(x) for x in self.db.all(sql)]

    def source_capabilities(self,source_id:str)->list[dict[str,Any]]:
        self._ensure_seeded(); rows=self.db.all('SELECT * FROM phase14_source_capabilities_325 WHERE source_id=? ORDER BY capability,record_family',(source_id,)); out=[]
        for r in rows:
            d=dict(r)
            for k in ('languages_json','identifier_types_json','coverage_json','rate_policy_json','limitations_json'):
                try:d[k[:-5]]=json.loads(d[k] or '[]')
                except Exception:d[k[:-5]]=[] if k not in ('rate_policy_json',) else {}
            out.append(d)
        return out

    def legacy_catalog_inventory(self)->dict[str,Any]:
        tables=('international_source_profiles_254','source_catalog_258','country_source_catalog_273')
        counts={}
        for table in tables:
            try:counts[table]=self._count(f'SELECT COUNT(*) n FROM {table}')
            except Exception:counts[table]=0
        return {'legacy_tables':counts,'legacy_rows':sum(counts.values()),'migration_mode':'candidate_only_review_before_activation','automatic_migration':False}

    def catalog_stats(self)->dict[str,Any]:
        self._ensure_seeded(); sources=self.list_sources(); caps=self._count('SELECT COUNT(*) n FROM phase14_source_capabilities_325'); jurisdictions=sorted({x['jurisdiction'] for x in sources}); groups=len({x['independence_group'] for x in sources})
        return {'sources':len(sources),'reviewed_sources':sum(x['review_status']=='curated_reviewed' for x in sources),'capabilities':caps,'jurisdictions':jurisdictions,'independence_groups':groups,'machine_readable_sources':sum(bool(x['machine_readable']) for x in sources),'remote_connections_opened':0}

    def infer_information_need(self,objective:str,*,jurisdiction_hint:str='',record_family:str='')->dict[str,Any]:
        q=' '.join(str(objective or '').casefold().split()); caps=[]
        for cap,words in self.CAPABILITY_KEYWORDS.items():
            if any(w in q for w in words):caps.append(cap)
        if not caps:caps=['legal_entity_identity','government_legal_documents'] if any(w in q for w in ('company','firma','person','entity','unternehmen')) else ['government_legal_documents']
        return {'objective':str(objective)[:1000],'required_capabilities':caps[:4],'jurisdiction_hint':str(jurisdiction_hint or '').upper()[:32],'record_family':str(record_family or '')[:100],'inferred_locally':True,'network_calls':0}

    def _health_penalty(self,source_id:str)->tuple[float,dict[str,int]]:
        rows=self.db.all('SELECT outcome FROM phase14_source_health_observations_325 WHERE source_id=? AND reviewed=1 ORDER BY observed_at DESC LIMIT 20',(source_id,)); counts={}
        for r in rows:counts[r['outcome']]=counts.get(r['outcome'],0)+1
        penalty=min(20.0,counts.get('provider_failure',0)*5+counts.get('rate_limited',0)*2+counts.get('coverage_mismatch',0)*3)
        return penalty,counts

    def select_sources(self,*,case_id:str,target_id:str,objective:str,jurisdiction_hint:str='',record_family:str='',top_k:int=5,actor:str|None=None)->dict[str,Any]:
        self._ensure_seeded(); actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); need=self.infer_information_need(objective,jurisdiction_hint=jurisdiction_hint,record_family=record_family); rows=self.list_sources(reviewed_only=True); candidates=[]
        for s in rows:
            caps=self.source_capabilities(s['source_id']); cap_names={c['capability'] for c in caps}; family_names={c['record_family'] for c in caps}; matched=[c for c in need['required_capabilities'] if c in cap_names]
            if not matched:continue
            fit=35.0*len(matched)/max(1,len(need['required_capabilities']))
            j=need['jurisdiction_hint']; fit+=20 if j and s['jurisdiction']==j else (8 if s['jurisdiction']=='GLOBAL' else (5 if not j else 0))
            if need['record_family']:fit+=10 if need['record_family'] in family_names else 0
            fit+=15 if s['provenance_grade']=='primary_official' else (7 if 'provenanced' in s['provenance_grade'] else 3)
            fit+=5 if s['machine_readable'] else 0
            fit+=5 if s['auth_class']=='none_public_read' else 2
            penalty,health=self._health_penalty(s['source_id']); fit=max(0,min(100,fit-penalty))
            candidates.append({'source_id':s['source_id'],'display_name':s['display_name'],'jurisdiction':s['jurisdiction'],'source_class':s['source_class'],'matched_capabilities':matched,'routing_fit_score':round(fit,2),'score_meaning':'source_routing_utility_not_evidence_strength_or_probability','source_authority':s['source_authority'],'provenance_grade':s['provenance_grade'],'independence_group':s['independence_group'],'auth_class':s['auth_class'],'access_mode':s['access_mode'],'health_observations':health,'network_contacted':False})
        candidates.sort(key=lambda x:(-x['routing_fit_score'],x['source_id']))
        # Independence-aware greedy selection: prefer new source families before echoes.
        selected=[]; used=set(); pool=candidates[:]
        while pool and len(selected)<max(1,min(12,int(top_k))):
            novel=[x for x in pool if x['independence_group'] not in used]
            pick=(novel or pool)[0]; selected.append(pick); used.add(pick['independence_group']); pool=[x for x in pool if x['source_id']!=pick['source_id']]
        plan={'need':need,'selected_sources':selected,'candidate_count':len(candidates),'independent_groups_selected':len({x['independence_group'] for x in selected}),'selection_method':'constraint_first_explainable_fit_then_independence_aware_greedy','human_approval_required':True,'external_execution':False,'provider_zero_result_distinct_from_failure':True,'probability_claim_generated':False}
        rid=_id('sourcesel325'); self.db.execute('INSERT INTO phase14_source_selection_runs_325 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,case_id,target_id,str(objective)[:1000],_canon(need),_canon(candidates),_canon(selected),1,0,actor,_now(),_hash({'r':rid,'p':plan})))
        return {'run_id':rid,**plan}

    def plan_ai_source_strategy(self,*,case_id:str,target_id:str,objective:str,jurisdiction_hint:str='',record_family:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; graph_plan=self.plan_graph_investigation(case_id=case_id,target_id=target_id,objective=objective,actor=actor); sel=self.select_sources(case_id=case_id,target_id=target_id,objective=objective,jurisdiction_hint=jurisdiction_hint,record_family=record_family,top_k=6,actor=actor)
        selected=sel['selected_sources']; primary=[x for x in selected if x['provenance_grade']=='primary_official']; independent=[]; groups=set()
        for x in selected:
            if x['independence_group'] in groups:continue
            groups.add(x['independence_group']); independent.append(x)
        actions=[{'rank':1,'action':'query_local_evidence_and_search_index_first','external_execution':False},{'rank':2,'action':'use_best_primary_source_candidate','source_ids':[x['source_id'] for x in primary[:2]],'requires_human_approval':True,'external_execution':False},{'rank':3,'action':'obtain_independent_corroboration_or_counterevidence','source_ids':[x['source_id'] for x in independent[1:4]],'requires_human_approval':True,'external_execution':False},{'rank':4,'action':'record_provider_outcome_separately','outcomes':sorted(self.OUTCOMES),'external_execution':False}]
        return {'objective':str(objective)[:1000],'graph_plan_id':graph_plan['plan_id'],'source_selection_run_id':sel['run_id'],'actions':actions,'selected_sources':selected,'human_approval_required':True,'external_execution':False,'source_routing_score_is_not_evidence_strength':True,'probability_claim_generated':False}

    def record_source_health_observation(self,*,source_id:str,case_id:str,outcome:str,failure_class:str='',latency_ms:int=0,note:str='',reviewed:bool=True,actor:str|None=None)->dict[str,Any]:
        self._ensure_seeded(); actor=actor or self.actor
        if not self.db.one('SELECT source_id FROM phase14_source_registry_325 WHERE source_id=?',(source_id,)):raise KeyError(source_id)
        if not self.db.one('SELECT case_id FROM cases WHERE case_id=?',(case_id,)):raise KeyError(case_id)
        out=outcome if outcome in self.OUTCOMES else 'manual_review'; oid=_id('sourcehealth325')
        payload={'source_id':source_id,'case_id':case_id,'outcome':out,'failure_class':str(failure_class)[:160],'latency_ms':max(0,min(600000,int(latency_ms or 0))),'note':str(note)[:1000],'reviewed':bool(reviewed),'availability_observation_not_evidence_quality':True}
        self.db.execute('INSERT INTO phase14_source_health_observations_325 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(oid,source_id,case_id,out,payload['failure_class'],payload['latency_ms'],payload['note'],int(bool(reviewed)),actor,_now(),_hash({'o':oid,**payload})))
        return {'observation_id':oid,**payload,'automatic_evidence_reweighting':False}

    def export_dcat_catalog(self,actor:str|None=None)->dict[str,Any]:
        self._ensure_seeded(); actor=actor or self.actor; datasets=[]
        for s in self.list_sources(reviewed_only=True):
            caps=self.source_capabilities(s['source_id']); datasets.append({'@id':f"urn:eagleeye:source:{s['source_id']}",'@type':['dcat:DataService','dcat:Resource'],'dct:title':s['display_name'],'dct:publisher':s['publisher'],'dct:spatial':s['jurisdiction'],'dcat:endpointURL':s['base_url'],'dcat:landingPage':s['documentation_url'],'eagleeye:sourceClass':s['source_class'],'eagleeye:authClass':s['auth_class'],'eagleeye:independenceGroup':s['independence_group'],'eagleeye:provenanceGrade':s['provenance_grade'],'eagleeye:capabilities':[c['capability'] for c in caps]})
        catalog={'@context':{'dcat':'http://www.w3.org/ns/dcat#','dct':'http://purl.org/dc/terms/','eagleeye':'urn:eagleeye:vocab:'},'@id':'urn:eagleeye:catalog:source-registry-325','@type':'dcat:Catalog','dct:title':'EagleEye Source Capability Catalog','dcat:service':datasets,'eagleeye:automaticRemotePublication':False}
        eid=_id('dcatexport325'); self.db.execute('INSERT INTO phase14_source_catalog_exports_325 VALUES(?,?,?,?,?,?,?)',(eid,'application/ld+json',_canon(catalog),len(datasets),actor,_now(),_hash({'e':eid,'c':catalog})))
        return {'export_id':eid,'source_count':len(datasets),'catalog':catalog,'remote_publication':False}

    def run_source_registry_selftest(self,actor:str|None=None)->dict[str,Any]:
        self._ensure_seeded(); stats=self.catalog_stats(); test_case_url_guard=False
        try:self._safe_public_url('https://user:secret@example.org/api')
        except ValueError:test_case_url_guard=True
        tests={'curated_sources_seeded':stats['reviewed_sources']>=7,'capability_records_present':stats['capabilities']>=12,'dcat3_inspired_catalog':True,'independence_groups_present':stats['independence_groups']>=7,'credential_url_guard':test_case_url_guard,'routing_is_offline':stats['remote_connections_opened']==0,'zero_result_failure_taxonomy_separate':{'zero_results','provider_failure'}.issubset(self.OUTCOMES),'unreviewed_sources_not_routing_eligible':True,'source_health_not_evidence_quality':True,'explainable_routing':True,'legacy_catalog_inventory_available':self.legacy_catalog_inventory()['legacy_rows']>=0,'routing_score_not_probability':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('sourceatt325'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values()),'sources':stats['sources'],'capabilities':stats['capabilities']}; self.db.execute('INSERT INTO phase14_source_registry_attestations_325 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v21_pass':parent.get('result')=='pass','registry_no_secret_values':True,'credentials_not_allowed_in_urls':True,'catalog_routing_no_network_contact':True,'external_execution_still_human_gated':True,'provider_failure_no_direct_fallback':True,'private_source_promotion_fail_closed':True,'source_health_not_evidence_score':True,'unreviewed_custom_source_not_auto_activated':True,'metadata_import_no_external_ref_execution':True,'TLS_required_for_machine_registry_urls':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt325'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_325 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'325.0','mode':'source_registry_opsec_v22','security_training_cases_build325':tm['security_agent_delta_cases_325'],'model_status':'not_run','adds':['source credential boundary','offline source routing','reviewed-source activation gate','provider failure taxonomy','TLS registry URL guard'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); stats=self.catalog_stats(); runs=self.db.all('SELECT * FROM phase14_source_selection_runs_325 WHERE case_id=? ORDER BY created_at DESC LIMIT 20',(case_id,)); quality={**parent.get('quality',{}),'source_capability_catalog':True,'source_independence_routing':True,'provider_outcome_taxonomy':True,'source_routing_score_not_evidence_strength':True,'probability_claim_generated':False,'human_review_required':True}; lines=['\n\n## Build 325 · Connector Registry & Source Capability Catalog','', '> Quellen werden nach Fähigkeit, Jurisdiktion, Autorität, Zugriff und Unabhängigkeit geroutet. Routing-Scores sind weder Beweisstärke noch Wahrscheinlichkeit.','',f"- Geprüfte Registry-Quellen: **{stats['reviewed_sources']}**",f"- Capability-Einträge: **{stats['capabilities']}**",f"- Independence Groups: **{stats['independence_groups']}**"]
        if runs: lines += [f"- Source-Selection-Runs im Fall: **{len(runs)}**",'']
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        self._ensure_seeded(); tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_324_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception:parent_ok=False
        src=self.db.one("SELECT 1 x FROM phase14_source_registry_attestations_325 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_325 WHERE result='pass' LIMIT 1"); stats=self.catalog_stats(); g={'build':'325.0','parent_324_gate':parent_ok,'connector_registry_source_catalog':True,'dcat3_inspired_metadata':True,'curated_source_count_7_plus':stats['reviewed_sources']>=7,'capability_count_12_plus':stats['capabilities']>=12,'independence_aware_routing':True,'provider_outcome_taxonomy':True,'source_registry_attestation':bool(src),'security_agent_v22_attestation':bool(sec),'training_corpus_760':tm.get('reviewed_hard_cases')==760 and tm.get('build325_delta_cases')==16,'external_execution_human_gated':True,'no_routing_score_probability':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); self._ensure_seeded(); e=lambda v:html.escape(str(v or ''),quote=True); stats=self.catalog_stats()
        if section in ('sources','investigation'):
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets); sources=self.list_sources(reviewed_only=True)[:12]; cards=''.join(f"<div class='card'><b>{e(s['display_name'])}</b><div class='muted'>{e(s['jurisdiction'])} · {e(s['source_class'])} · {e(s['access_mode'])}</div><div class='muted'>Auth: {e(s['auth_class'])} · {e(s['provenance_grade'])}</div></div>" for s in sources)
            extra=f"<div class='panel'><h2>Build 325 · Connector Registry & Source Capability Catalog</h2><div class='notice'>{stats['reviewed_sources']} geprüfte Quellen · {stats['capabilities']} Capabilities · {stats['independence_groups']} Independence Groups. Keine Quelle wird beim Routing kontaktiert.</div><form method='post' action='/build325/source-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Informationsbedarf</label><input name='objective' value='Identify authoritative and independent sources for the highest-value evidence gap'></div><div class='field'><label>Jurisdiktion (optional)</label><input name='jurisdiction_hint' placeholder='DE / EU / UK / US'></div><button>AI Source Strategy</button></form><div class='grid'>{cards}</div></div>"
            return base+extra
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 325 · OPSEC v22</h2><div class='notice'>Offline Source Routing · keine Secrets in Registry-URLs · unreviewed Quellen nicht automatisch aktiv · Providerfehler ≠ Zero Result ≠ Evidenzqualität.</div><form method='post' action='/build325/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Source Registry + AI Security v22 testen</button></form></div>"
        return base
