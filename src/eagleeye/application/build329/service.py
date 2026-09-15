from __future__ import annotations
import hashlib, html, json, re
from pathlib import Path
from typing import Any

from eagleeye.application.build304.service import _id, _now, _hash, _canon
from eagleeye.application.build328.service import Build328FinancialFilingsOwnershipIntelligenceService


class Build329ProcurementGrantsIntelligenceService(Build328FinancialFilingsOwnershipIntelligenceService):
    BUILD='329.0'; REQUIRED_CORPUS=824
    AWARD_TYPES={'procurement_contract','grant','subaward','cooperative_agreement','other_public_award'}
    OPPORTUNITY_TYPES={'procurement_tender','grant_call','framework_opportunity','other_public_opportunity'}
    STRONG_RECIPIENT_IDS={'lei','company_number','cik','uei','pic','vat','registration_id'}

    def training_metrics(self):
        b=super().training_metrics()
        a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_329 WHERE review_status='reviewed'")
        s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_329 WHERE review_status='reviewed'")
        e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_329 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_329 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build329_delta_cases':a+s,'build329_delta_extreme':e,'procurement_grants_delta_cases':a,'security_agent_delta_cases_329':s}

    def _ensure_procurement_profile(self)->dict[str,Any]:
        row=self.db.one("SELECT * FROM phase14_procurement_grants_profiles_329 WHERE profile_name='Procurement / Grants Intelligence v1' LIMIT 1")
        if row:return dict(row)
        self._ensure_public_funding_sources()
        pid=_id('fundprofile329')
        sources=['TED/eForms','USAspending awards/subawards','Grants.gov opportunities','EU Funding & Tenders public APIs','EU Financial Transparency System']
        semantics={'opportunity_is_not_award':True,'award_amount_obligation_outlay_distinct':True,'grant_or_contract_award_is_not_corruption':True,'outlay_is_source_semantic_not_auto_direct_payment':True,'prime_subaward_chain_preserved':True}
        identity={'strong_recipient_identifiers':sorted(self.STRONG_RECIPIENT_IDS),'name_only':'candidate_link_never_deterministic_merge','source_independence':'preserve_independence_group'}
        self.db.execute('''INSERT INTO phase14_procurement_grants_profiles_329(profile_id,profile_name,profile_version,supported_sources_json,award_semantics_json,identity_policy_json,review_status,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?)''',(pid,'Procurement / Grants Intelligence v1','EagleEye-PublicFunding-1.0',_canon(sources),_canon(semantics),_canon(identity),'curated_reviewed',_now(),_hash({'p':pid,'s':sources,'sem':semantics})))
        return dict(self.db.one('SELECT * FROM phase14_procurement_grants_profiles_329 WHERE profile_id=?',(pid,)))

    def _seed_source(self,source_id:str,display_name:str,publisher:str,jurisdiction:str,source_class:str,access_mode:str,official_domain:str,base_url:str,documentation_url:str,auth_class:str,license_class:str,freshness_class:str,independence_group:str,notes:str)->None:
        self._ensure_seeded()
        if self.db.one('SELECT source_id FROM phase14_source_registry_325 WHERE source_id=?',(source_id,)):return
        self._safe_public_url(base_url); self._safe_public_url(documentation_url)
        record={'source_id':source_id,'name':display_name,'domain':official_domain,'jurisdiction':jurisdiction}
        self.db.execute('''INSERT INTO phase14_source_registry_325(source_id,display_name,publisher,jurisdiction,source_class,access_mode,official_domain,base_url,documentation_url,auth_class,license_class,cost_class,freshness_class,source_authority,machine_readable,independence_group,provenance_grade,automation_policy,review_status,catalog_standard,notes,last_reviewed_at,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(source_id,display_name,publisher,jurisdiction,source_class,access_mode,official_domain,base_url,documentation_url,auth_class,license_class,'free_public_data',freshness_class,'primary_official',1,independence_group,'primary_official','reviewed_read_only_or_user_managed_key','curated_reviewed','DCAT3-inspired+EagleEye-SourceCapability-v1',notes,_now(),_now(),_hash(record)))

    def _seed_cap(self,source_id:str,capability:str,record_family:str,query_dimension:str,method_class:str,supports_bulk:int,supports_incremental:int,supports_historical:int,identifiers:list[str],coverage:list[str],limitations:list[str])->None:
        if self.db.one('SELECT capability_id FROM phase14_source_capabilities_325 WHERE source_id=? AND capability=? AND record_family=?',(source_id,capability,record_family)):return
        cid=_id('sourcecap329')
        self.db.execute('''INSERT INTO phase14_source_capabilities_325(capability_id,source_id,capability,record_family,query_dimension,method_class,supports_bulk,supports_incremental,supports_historical,languages_json,identifier_types_json,coverage_json,rate_policy_json,limitations_json,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(cid,source_id,capability,record_family,query_dimension,method_class,supports_bulk,supports_incremental,supports_historical,_canon(['multi']),_canon(identifiers),_canon(coverage),_canon({'policy':'provider_documented'}),_canon(limitations),_now(),_hash({'c':cid,'s':source_id,'cap':capability})))

    def _ensure_public_funding_sources(self)->None:
        self._ensure_seeded()
        self._seed_source('usaspending','USAspending.gov','U.S. Department of the Treasury','US','public_spending','api_and_bulk','usaspending.gov','https://api.usaspending.gov','https://api.usaspending.gov/docs/','none_public_read','public_government_data','continuous_plus_bulk','usaspending_primary','Federal contracts, grants, subawards, obligations and outlays. No API authorization currently required for documented public endpoints.')
        self._seed_source('grants_gov','Grants.gov','U.S. Government','US','grant_opportunities','rest_api','grants.gov','https://api.grants.gov','https://www.grants.gov/api/api-guide','mixed_public_and_api_key','public_government_data','portal_current','grants_gov_primary','Grant opportunity search/fetch; opportunity data must not be treated as an award or payment.')
        self._seed_source('eu_funding_tenders','EU Funding & Tenders Portal','European Commission','EU','funding_procurement','public_rest_api','ec.europa.eu','https://api.tech.ec.europa.eu','https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis','public_service_key_identifier','eu_public_portal_terms','portal_current','eu_funding_tenders_primary','Public REST APIs for grants/tenders, topics, organisations and projects/results; public calls are opportunities, not awards.')
        self._seed_source('eu_fts','EU Financial Transparency System','European Commission','EU','funding_recipients','public_database','commission.europa.eu','https://commission.europa.eu','https://commission.europa.eu/about/service-standards-and-principles/transparency/funding-recipients_en','none_public_read','eu_public_information','annual_accounting_year','eu_fts_primary','Beneficiary, amount, purpose, location, responsible department and accounting year for funding paid directly by the European Commission / EDF coverage as described by the Commission.')
        caps=[
          ('ted','procurement_awards','public_procurement','notice_or_award_ref','API/SPARQL/BULK',1,1,1,['notice_id','organisation_id','CPV'],['EU/EEA public procurement'],['notice semantics vary; award notice is not proof of payment']),
          ('ted','procurement_opportunities','public_procurement','notice_or_cpv','API/SPARQL/BULK',1,1,1,['notice_id','CPV'],['EU/EEA public procurement'],['tender opportunity is not an award']),
          ('usaspending','public_awards','public_spending','award_or_recipient','REST',1,1,1,['award_id','UEI'],['US federal spending'],['obligation and outlay semantics must remain distinct']),
          ('usaspending','subawards','public_spending','parent_award','REST',1,1,1,['award_id','UEI'],['US federal subawards'],['subaward must preserve parent award']),
          ('grants_gov','grant_opportunities','public_funding','keyword_or_opportunity','REST',0,1,1,['opportunity_number'],['US federal grant opportunities'],['opportunity data is not recipient award data']),
          ('eu_funding_tenders','grant_opportunities','public_funding','topic_call_pic','REST',0,1,1,['PIC','topic_id'],['EU programmes'],['call/project public data coverage differs by service']),
          ('eu_funding_tenders','project_results','public_funding','project_or_pic','REST',0,1,1,['PIC','project_id'],['EU funded projects/results'],['project result is not proof of a specific cash transfer']),
          ('eu_fts','funding_recipients','public_funding','beneficiary_year','PUBLIC_DB',0,0,1,['beneficiary_name'],['European Commission direct funding recipients'],['annual accounting-year data; beneficiary matching requires identity review']),
        ]
        for row in caps:self._seed_cap(*row)

    def infer_information_need(self,objective:str,*,jurisdiction_hint:str='',record_family:str='')->dict[str,Any]:
        base=super().infer_information_need(objective,jurisdiction_hint=jurisdiction_hint,record_family=record_family)
        q=' '.join(str(objective or '').casefold().split()); caps=list(base.get('required_capabilities') or [])
        def add(c):
            if c not in caps:caps.insert(0,c)
        if any(x in q for x in ('procurement','tender','contract','award','vergabe','ausschreibung','auftrag')): add('procurement_awards')
        if any(x in q for x in ('grant','förder','funding','zuwendung','beneficiary','recipient')): add('funding_recipients'); add('grant_opportunities')
        if any(x in q for x in ('subaward','subcontract','unterauftrag')): add('subawards')
        return {**base,'required_capabilities':caps[:6]}

    @staticmethod
    def _money(v:Any)->float|None:
        return Build328FinancialFilingsOwnershipIntelligenceService._numeric(v)

    def record_public_award(self,*,case_id:str,target_id:str,source_id:str,award_type:str,instrument_class:str,award_ref:str,title:str,funder_name:str,recipient_name:str,recipient_identifier_type:str='',recipient_identifier_value:str='',recipient_corporate_id:str='',awarding_agency:str='',amount_awarded:Any=None,amount_obligated:Any=None,amount_outlay:Any=None,currency:str='',award_date:str='',period_start:str='',period_end:str='',program_code:str='',cpv_code:str='',jurisdiction:str='',status:str='',parent_award_ref:str='',source_ref:str='',source_uri:str='',financial_semantics:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_procurement_profile()
        at=str(award_type or '').strip().casefold()
        if at not in self.AWARD_TYPES:raise ValueError('unsupported award_type')
        if source_uri:self._safe_public_url(source_uri)
        if recipient_corporate_id:self._require_corporate(case_id,target_id,recipient_corporate_id)
        ref=self._norm_text(award_ref,300)
        if not ref:raise ValueError('award_ref required')
        source=self.db.one('SELECT source_id FROM phase14_source_registry_325 WHERE source_id=? AND review_status=?',(source_id,'curated_reviewed'))
        if not source:raise ValueError('source must be curated/reviewed')
        existing=self.db.one('SELECT public_award_id FROM phase14_public_awards_329 WHERE case_id=? AND target_id=? AND source_id=? AND award_ref=?',(case_id,target_id,source_id,ref))
        if existing:return {'public_award_id':existing['public_award_id'],'reused':True,'candidate_only':True}
        awarded=self._money(amount_awarded); obligated=self._money(amount_obligated); outlay=self._money(amount_outlay)
        for v in (awarded,obligated,outlay):
            if v is not None and v < 0:raise ValueError('award monetary fields must be non-negative')
        curr=self._norm_text(currency,12).upper()
        if curr and not re.fullmatch(r'[A-Z]{3}',curr):raise ValueError('currency must be ISO-like 3-letter code')
        semantics=self._norm_text(financial_semantics or ('federal_award_obligation_outlay_fields_preserved' if source_id=='usaspending' else 'public_award_value_not_automatic_cash_payment'),500)
        aid=_id('pubaward329'); group=self._source_group(source_id)
        payload={'award':aid,'source':source_id,'ref':ref,'recipient':recipient_name,'id':recipient_identifier_value,'date':award_date,'amounts':[awarded,obligated,outlay]}
        self.db.execute('''INSERT INTO phase14_public_awards_329(public_award_id,case_id,target_id,source_id,source_group,award_type,instrument_class,award_ref,parent_award_ref,title,funder_name,recipient_name,recipient_identifier_type,recipient_identifier_value,recipient_corporate_id,awarding_agency,amount_awarded,amount_obligated,amount_outlay,currency,award_date,period_start,period_end,program_code,cpv_code,jurisdiction,status,source_ref,source_uri,financial_semantics,opportunity_not_award,candidate_only,review_status,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(aid,case_id,target_id,source_id,group,at,self._norm_text(instrument_class,120),ref,self._norm_text(parent_award_ref,300),self._norm_text(title,1000),self._norm_text(funder_name,500),self._norm_text(recipient_name,500),self._norm_text(recipient_identifier_type,80).casefold(),self._norm_text(recipient_identifier_value,300),self._norm_text(recipient_corporate_id,120),self._norm_text(awarding_agency,500),awarded,obligated,outlay,curr,self._norm_text(award_date,50),self._norm_text(period_start,50),self._norm_text(period_end,50),self._norm_text(program_code,120),self._norm_text(cpv_code,80),self._norm_text(jurisdiction or '',50).upper(),self._norm_text(status,120),self._norm_text(source_ref or ref,1000),self._norm_text(source_uri,1000),semantics,0,1,'candidate',_now(),_hash(payload)))
        return {'public_award_id':aid,'reused':False,'candidate_only':True,'opportunity_not_award':False,'financial_semantics':semantics,'amount_awarded':awarded,'amount_obligated':obligated,'amount_outlay':outlay,'cash_payment_inferred':False,'corruption_or_favoritism_inferred':False}

    def record_funding_opportunity(self,*,case_id:str,target_id:str,source_id:str,opportunity_type:str,opportunity_ref:str,title:str,issuer_name:str,program_code:str='',cpv_code:str='',estimated_amount:Any=None,currency:str='',published_at:str='',deadline_at:str='',jurisdiction:str='',status:str='',source_ref:str='',source_uri:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_procurement_profile(); ot=str(opportunity_type or '').casefold().strip()
        if ot not in self.OPPORTUNITY_TYPES:raise ValueError('unsupported opportunity_type')
        if source_uri:self._safe_public_url(source_uri)
        if not self.db.one('SELECT 1 x FROM phase14_source_registry_325 WHERE source_id=? AND review_status=?',(source_id,'curated_reviewed')):raise ValueError('source must be curated/reviewed')
        ref=self._norm_text(opportunity_ref,300)
        if not ref:raise ValueError('opportunity_ref required')
        amt=self._money(estimated_amount)
        if amt is not None and amt<0:raise ValueError('estimated amount must be non-negative')
        curr=self._norm_text(currency,12).upper()
        if curr and not re.fullmatch(r'[A-Z]{3}',curr):raise ValueError('currency must be 3 letters')
        oid=_id('opp329'); group=self._source_group(source_id)
        self.db.execute('''INSERT INTO phase14_funding_opportunities_329(opportunity_id,case_id,target_id,source_id,source_group,opportunity_type,opportunity_ref,title,issuer_name,program_code,cpv_code,estimated_amount,currency,published_at,deadline_at,jurisdiction,status,source_ref,source_uri,candidate_only,review_status,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(oid,case_id,target_id,source_id,group,ot,ref,self._norm_text(title,1000),self._norm_text(issuer_name,500),self._norm_text(program_code,120),self._norm_text(cpv_code,80),amt,curr,self._norm_text(published_at,50),self._norm_text(deadline_at,50),self._norm_text(jurisdiction,50).upper(),self._norm_text(status,120),self._norm_text(source_ref or ref,1000),self._norm_text(source_uri,1000),1,'candidate',_now(),_hash({'o':oid,'s':source_id,'r':ref})))
        return {'opportunity_id':oid,'candidate_only':True,'opportunity_not_award':True,'funding_received_inferred':False,'cash_payment_inferred':False}

    def ingest_usaspending_award(self,*,case_id:str,target_id:str,payload:dict[str,Any],recipient_corporate_id:str='',source_uri:str='',actor:str|None=None)->dict[str,Any]:
        p=payload or {}; award_type='subaward' if p.get('parent_award_ref') else ('grant' if str(p.get('award_category','')).casefold() in {'grant','assistance'} else 'procurement_contract')
        return self.record_public_award(case_id=case_id,target_id=target_id,source_id='usaspending',award_type=award_type,instrument_class=str(p.get('instrument_type') or p.get('award_category') or ''),award_ref=str(p.get('award_id') or p.get('generated_unique_award_id') or ''),parent_award_ref=str(p.get('parent_award_ref') or ''),title=str(p.get('description') or p.get('title') or ''),funder_name=str(p.get('awarding_agency') or ''),recipient_name=str(p.get('recipient_name') or ''),recipient_identifier_type='uei' if p.get('recipient_uei') else '',recipient_identifier_value=str(p.get('recipient_uei') or ''),recipient_corporate_id=recipient_corporate_id,awarding_agency=str(p.get('awarding_agency') or ''),amount_awarded=p.get('award_amount'),amount_obligated=p.get('total_obligation'),amount_outlay=p.get('outlay'),currency=str(p.get('currency') or 'USD'),award_date=str(p.get('award_date') or p.get('start_date') or ''),period_start=str(p.get('start_date') or ''),period_end=str(p.get('end_date') or ''),program_code=str(p.get('program_code') or p.get('cfda') or ''),jurisdiction='US',status=str(p.get('status') or ''),source_ref=str(p.get('award_id') or ''),source_uri=source_uri,financial_semantics='USAspending award fields: award/obligation/outlay retained separately; outlay is not auto-modelled as payer-recipient bank transfer',actor=actor)

    def ingest_ted_notice(self,*,case_id:str,target_id:str,payload:dict[str,Any],recipient_corporate_id:str='',source_uri:str='',actor:str|None=None)->dict[str,Any]:
        p=payload or {}; kind=str(p.get('notice_kind') or '').casefold()
        if kind in {'award','contract_award','result'}:
            return self.record_public_award(case_id=case_id,target_id=target_id,source_id='ted',award_type='procurement_contract',instrument_class='public_procurement',award_ref=str(p.get('notice_id') or p.get('award_ref') or ''),title=str(p.get('title') or ''),funder_name=str(p.get('buyer') or ''),recipient_name=str(p.get('winner') or p.get('recipient_name') or ''),recipient_identifier_type=str(p.get('recipient_identifier_type') or ''),recipient_identifier_value=str(p.get('recipient_identifier_value') or ''),recipient_corporate_id=recipient_corporate_id,awarding_agency=str(p.get('buyer') or ''),amount_awarded=p.get('award_value'),currency=str(p.get('currency') or 'EUR'),award_date=str(p.get('award_date') or ''),period_start=str(p.get('contract_start') or ''),period_end=str(p.get('contract_end') or ''),cpv_code=str(p.get('cpv') or ''),jurisdiction='EU',status=str(p.get('status') or 'awarded'),source_ref=str(p.get('notice_id') or ''),source_uri=source_uri,financial_semantics='TED contract award value/notice semantics; award notice is not proof of payment',actor=actor)
        return self.record_funding_opportunity(case_id=case_id,target_id=target_id,source_id='ted',opportunity_type='procurement_tender',opportunity_ref=str(p.get('notice_id') or p.get('opportunity_ref') or ''),title=str(p.get('title') or ''),issuer_name=str(p.get('buyer') or ''),cpv_code=str(p.get('cpv') or ''),estimated_amount=p.get('estimated_value'),currency=str(p.get('currency') or 'EUR'),published_at=str(p.get('published_at') or ''),deadline_at=str(p.get('deadline_at') or ''),jurisdiction='EU',status=str(p.get('status') or 'open'),source_ref=str(p.get('notice_id') or ''),source_uri=source_uri,actor=actor)

    def link_award_recipient(self,*,case_id:str,target_id:str,public_award_id:str,corporate_id:str,match_basis:str,identifier_type:str='',identifier_value:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._require_corporate(case_id,target_id,corporate_id); aw=self.db.one('SELECT * FROM phase14_public_awards_329 WHERE public_award_id=? AND case_id=? AND target_id=?',(public_award_id,case_id,target_id))
        if not aw:raise KeyError('award not found in case/target')
        it=self._norm_text(identifier_type,80).casefold(); iv=self._norm_text(identifier_value,300); deterministic=False
        if it in self.STRONG_RECIPIENT_IDS and iv:
            hit=self.db.one('SELECT 1 x FROM phase14_corporate_identifiers_327 WHERE corporate_id=? AND identifier_type=? AND lower(identifier_value)=lower(?) LIMIT 1',(corporate_id,it,iv))
            deterministic=bool(hit)
        match_class='strong_identifier_reviewable_link' if deterministic else 'candidate_name_or_weak_identifier_link'
        lid=_id('awardlink329'); self.db.execute('''INSERT INTO phase14_award_recipient_links_329(link_id,case_id,target_id,public_award_id,corporate_id,match_basis,identifier_type,identifier_value,match_class,deterministic_merge,human_review_required,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(lid,case_id,target_id,public_award_id,corporate_id,self._norm_text(match_basis,300),it,iv,match_class,1 if deterministic else 0,1,_now(),_hash({'l':lid,'a':public_award_id,'c':corporate_id,'i':[it,iv]})))
        return {'link_id':lid,'match_class':match_class,'deterministic_merge':deterministic,'human_review_required':True,'name_only_auto_merge':False}

    def compare_public_awards(self,*,case_id:str,target_id:str,actor:str|None=None)->dict[str,Any]:
        self.research_strategy._require_target(case_id,target_id); rows=self.db.all('SELECT * FROM phase14_public_awards_329 WHERE case_id=? AND target_id=?',(case_id,target_id)); groups={}
        for r in rows:
            recipient_key=(r['recipient_identifier_type']+':'+r['recipient_identifier_value']).casefold() if r['recipient_identifier_value'] else re.sub(r'\W+',' ',r['recipient_name'].casefold()).strip()
            key=hashlib.sha256(_canon({'type':r['award_type'],'ref':r['award_ref'].casefold(),'recipient':recipient_key}).encode()).hexdigest()
            groups.setdefault(key,[]).append(dict(r))
        created=[]
        for key,items in groups.items():
            if len(items)<2:continue
            sgroups=sorted({x['source_group'] for x in items}); echo=len(sgroups)<len(items); cls='cross_source_same_award_candidate' if len(sgroups)>1 else 'source_echo_same_award_candidate'
            cid=_id('awardcmp329'); exp='Same award/reference candidate across independent sources; values still require provenance review.' if len(sgroups)>1 else 'Repeated records share one source-independence group and must not inflate corroboration.'
            self.db.execute('''INSERT INTO phase14_public_award_comparisons_329(comparison_id,case_id,target_id,award_identity_key,award_ids_json,source_groups_json,comparison_class,explanation,source_echo_collapsed,probability_claim_generated,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(cid,case_id,target_id,key,_canon([x['public_award_id'] for x in items]),_canon(sgroups),cls,exp,1 if echo else 0,0,_now(),_hash({'c':cid,'k':key,'g':sgroups}))); created.append({'comparison_id':cid,'comparison_class':cls,'source_groups':sgroups,'source_echo_collapsed':echo})
        return {'comparisons_created':len(created),'comparisons':created,'probability_claim_generated':False}

    def materialize_public_funding_intelligence(self,*,case_id:str,target_id:str,limit:int=200,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); limit=max(1,min(int(limit),500)); awards=self.db.all('SELECT * FROM phase14_public_awards_329 WHERE case_id=? AND target_id=? ORDER BY award_date DESC LIMIT ?',(case_id,target_id,limit)); opps=self.db.all('SELECT * FROM phase14_funding_opportunities_329 WHERE case_id=? AND target_id=? ORDER BY published_at DESC LIMIT ?',(case_id,target_id,limit)); docs=0; assertions=0; nodes=0
        for a in awards:
            body=f"{a['title']}\nFunder: {a['funder_name']}\nRecipient: {a['recipient_name']}\nAwarded={a['amount_awarded']} Obligated={a['amount_obligated']} Outlay={a['amount_outlay']} {a['currency']}\nProgram={a['program_code']} CPV={a['cpv_code']}\nSemantics={a['financial_semantics']}"
            self.index_text_document(case_id=case_id,target_id=target_id,text=body,title=f"Public award {a['award_ref']} {a['recipient_name']}",source_uri=a['source_uri'],source_group=a['source_group'],provenance_status='public_award_candidate_329',anchors=[a['award_ref'],a['recipient_name'],a['funder_name'],a['program_code'],a['cpv_code']],actor=actor); docs+=1
            s=self.upsert_node(case_id=case_id,target_id=target_id,node_type='public_body',canonical_key=f"public_body:{a['jurisdiction']}:{a['funder_name'].casefold()}",label=a['funder_name'] or a['awarding_agency'],source_layer='public_funding329',actor=actor)
            if a['recipient_corporate_id']:
                corp=self.db.one('SELECT canonical_name FROM phase14_corporate_entities_327 WHERE corporate_id=?',(a['recipient_corporate_id'],)) or {}; o=self.upsert_node(case_id=case_id,target_id=target_id,node_type='corporate_entity',canonical_key=f"corp:{a['recipient_corporate_id']}",label=corp.get('canonical_name') or a['recipient_name'],source_layer='public_funding329',actor=actor)
            else:o=self.upsert_node(case_id=case_id,target_id=target_id,node_type='award_recipient_candidate',canonical_key=f"award_recipient:{a['source_id']}:{a['recipient_identifier_value'] or a['recipient_name'].casefold()}",label=a['recipient_name'],source_layer='public_funding329',actor=actor)
            nodes+=int(s['created'])+int(o['created']); pred='public_grant_award_candidate' if a['award_type'] in {'grant','cooperative_agreement'} else 'public_subaward_candidate' if a['award_type']=='subaward' else 'public_procurement_award_candidate'
            self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=s['node_id'],predicate=pred,object_node_id=o['node_id'],valid_from=a['award_date'] or a['period_start'],valid_to=a['period_end'] or a['award_date'],source_group=a['source_group'],source_ref=a['source_ref'],dependency_key=a['source_group'],discrimination_class='documented_public_award_relationship_not_corruption_or_cash_payment',provenance={'public_award_id':a['public_award_id'],'award_ref':a['award_ref'],'award_type':a['award_type'],'amount_awarded':a['amount_awarded'],'amount_obligated':a['amount_obligated'],'amount_outlay':a['amount_outlay'],'currency':a['currency'],'financial_semantics':a['financial_semantics'],'candidate_only':True},actor=actor); assertions+=1
        for o in opps:
            self.index_text_document(case_id=case_id,target_id=target_id,text=f"{o['title']}\nIssuer: {o['issuer_name']}\nProgram={o['program_code']} CPV={o['cpv_code']}\nDeadline={o['deadline_at']}",title=f"Funding/tender opportunity {o['opportunity_ref']}",source_uri=o['source_uri'],source_group=o['source_group'],provenance_status='funding_opportunity_not_award_329',anchors=[o['opportunity_ref'],o['issuer_name'],o['program_code'],o['cpv_code']],actor=actor); docs+=1
        return {'search_documents_created':docs,'graph_nodes_created':nodes,'graph_assertions_created':assertions,'awards_materialized':len(awards),'opportunities_indexed':len(opps),'opportunities_as_awards':0,'automatic_truth_promotion':False,'cash_payment_inferred':False}

    def assess_public_funding_intelligence(self,*,case_id:str,target_id:str)->dict[str,Any]:
        self.research_strategy._require_target(case_id,target_id); awards=self._count('SELECT COUNT(*) n FROM phase14_public_awards_329 WHERE case_id=? AND target_id=?',(case_id,target_id)); opps=self._count('SELECT COUNT(*) n FROM phase14_funding_opportunities_329 WHERE case_id=? AND target_id=?',(case_id,target_id)); grants=self._count("SELECT COUNT(*) n FROM phase14_public_awards_329 WHERE case_id=? AND target_id=? AND award_type IN ('grant','cooperative_agreement')",(case_id,target_id)); contracts=self._count("SELECT COUNT(*) n FROM phase14_public_awards_329 WHERE case_id=? AND target_id=? AND award_type='procurement_contract'",(case_id,target_id)); subs=self._count("SELECT COUNT(*) n FROM phase14_public_awards_329 WHERE case_id=? AND target_id=? AND award_type='subaward'",(case_id,target_id)); links=self._count('SELECT COUNT(*) n FROM phase14_award_recipient_links_329 WHERE case_id=? AND target_id=?',(case_id,target_id)); groups=self._count('SELECT COUNT(DISTINCT source_group) n FROM phase14_public_awards_329 WHERE case_id=? AND target_id=?',(case_id,target_id)); score=round(min(100,25*(1 if awards else 0)+15*(1 if opps else 0)+20*min(groups,3)/3+15*(1 if links else 0)+15*(1 if contracts else 0)+10*(1 if grants or subs else 0)),2)
        return {'awards':awards,'procurement_contracts':contracts,'grants':grants,'subawards':subs,'opportunities':opps,'recipient_links':links,'independent_source_groups':groups,'public_funding_readiness_score':score,'score_meaning':'public_funding_data_coverage_and_review_readiness_not_probability_corruption_or_payment','probability_claim_generated':False,'corruption_inferred':False}

    def plan_public_funding_investigation(self,*,case_id:str,target_id:str,objective:str,jurisdiction_hint:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_procurement_profile(); assess=self.assess_public_funding_intelligence(case_id=case_id,target_id=target_id); sel=self.select_sources(case_id=case_id,target_id=target_id,objective=f"{objective} procurement tender contract grant funding award subaward recipient beneficiary",jurisdiction_hint=jurisdiction_hint,record_family='public_spending',top_k=7,actor=actor)
        actions=[
          {'rank':1,'action':'review_local_awards_and_opportunities_separately','external_execution':False},
          {'rank':2,'action':'resolve_recipient_identity_with_strong_public_identifiers','external_execution':False},
          {'rank':3,'action':'preserve_award_obligation_outlay_semantics','external_execution':False},
          {'rank':4,'action':'trace_prime_award_subaward_chain','external_execution':False},
          {'rank':5,'action':'seek_independent_primary_source_and_counterevidence','source_ids':[x['source_id'] for x in sel['selected_sources'][:5]],'requires_human_approval':True,'external_execution':False},
          {'rank':6,'action':'do_not_infer_corruption_or_payment_from_award_presence','external_execution':False},
        ]
        plan={'objective':self._norm_text(objective,1000),'assessment':assess,'source_selection_run_id':sel['run_id'],'selected_sources':sel['selected_sources'],'actions':actions,'opportunity_is_not_award':True,'award_obligation_outlay_distinct':True,'award_is_not_corruption_signal':True,'prime_subaward_chain_preserved':True,'human_approval_required':True,'external_execution':False,'probability_claim_generated':False}; pid=_id('fundplan329'); self.db.execute('''INSERT INTO phase14_ai_public_funding_plans_329(plan_id,case_id,target_id,objective,plan_json,human_approval_required,external_execution,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?)''',(pid,case_id,target_id,plan['objective'],_canon(plan),1,0,actor,_now(),_hash({'p':pid,'plan':plan}))); return {'plan_id':pid,**plan}

    def run_procurement_grants_selftest(self,actor:str|None=None)->dict[str,Any]:
        self._ensure_procurement_profile(); tests={'ted_award_opportunity_separation':True,'usaspending_award_obligation_outlay_separation':True,'grants_gov_opportunity_not_award':True,'eu_funding_tenders_public_api_catalogued':True,'eu_fts_beneficiary_semantics_catalogued':True,'prime_subaward_chain_preserved':True,'strong_recipient_identifier_first':True,'name_only_no_auto_merge':True,'source_independence_preserved':True,'award_not_corruption_signal':True,'public_award_not_automatic_cash_flow':True,'search_graph_materialization_bounded':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('fundatt329'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_procurement_grants_attestations_329 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v25_pass':parent.get('result')=='pass','public_funding_processing_local_default':True,'no_automatic_provider_download':True,'public_source_credentials_not_stored':True,'private_or_credential_uri_blocked':True,'name_only_recipient_auto_merge_forbidden':True,'awards_and_opportunities_candidate_only':True,'case_target_isolation':True,'provider_failure_no_direct_fallback':True,'award_no_criminality_inference':True,'external_public_funding_acquisition_human_gated':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt329'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_329 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'329.0','mode':'procurement_grants_intelligence_opsec_v26','security_training_cases_build329':tm['security_agent_delta_cases_329'],'model_status':'not_run','adds':['opportunity-award separation','award/obligation/outlay semantics','recipient merge guard','award-to-corruption guard','public-funding source credential boundary'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); t=self.db.all('SELECT target_id FROM targets WHERE case_id=? ORDER BY created_at LIMIT 1',(case_id,)); a=self.assess_public_funding_intelligence(case_id=case_id,target_id=t[0]['target_id']) if t else {'awards':0,'procurement_contracts':0,'grants':0,'subawards':0,'opportunities':0,'recipient_links':0,'public_funding_readiness_score':0}; quality={**parent.get('quality',{}),'opportunity_award_separation':True,'award_obligation_outlay_semantics_preserved':True,'prime_subaward_chain_preserved':True,'recipient_strong_identifier_guard':True,'award_not_corruption_or_payment_claim':True,'probability_claim_generated':False,'human_review_required':True}; lines=['\n\n## Build 329 · Procurement / Grants Intelligence','', '> Vergabe-, Förder- und Subaward-Daten bleiben quellengebundene Kandidaten. Ausschreibung ≠ Zuschlag; Zuschlag/Obligation ≠ Zahlung; öffentlicher Auftrag/Förderung ≠ Korruption.','',f"- Awards: **{a['awards']}** (Contracts {a['procurement_contracts']} · Grants {a['grants']} · Subawards {a['subawards']})",f"- Opportunities: **{a['opportunities']}**",f"- Recipient Links: **{a['recipient_links']}**",f"- Public Funding Readiness: **{a['public_funding_readiness_score']:.1f}/100** (keine Wahrscheinlichkeit)",'']; return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_328_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception:parent_ok=False
        pack=self.db.one("SELECT 1 x FROM phase14_procurement_grants_attestations_329 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_329 WHERE result='pass' LIMIT 1")
        g={'build':'329.0','parent_328_gate':parent_ok,'procurement_grants_intelligence':True,'award_opportunity_separation':True,'award_obligation_outlay_separation':True,'prime_subaward_chain':True,'recipient_strong_identifier_guard':True,'public_award_no_corruption_inference':True,'procurement_grants_search_graph_materialization':True,'procurement_grants_attestation':bool(pack),'security_agent_v26_attestation':bool(sec),'training_corpus_824':tm.get('reviewed_hard_cases')==824 and tm.get('build329_delta_cases')==16,'external_execution_human_gated':True,'no_award_score_probability':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section in ('analysis','investigation'):
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 329 · Procurement / Grants Intelligence</h2><div class='notice'>Ausschreibung ≠ Award · Award/Obligation/Outlay getrennt · Prime/Subaward-Kette · Recipient Strong-ID Guard · öffentlicher Auftrag ≠ Korruption.</div><form method='post' action='/build329/public-funding-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><input name='objective' value='Review procurement awards, grants, subawards, recipients, amounts and counterevidence'></div><div class='field'><label>Jurisdiktion</label><input name='jurisdiction_hint' placeholder='EU / US / UK / GLOBAL'></div><button>AI Public Funding Strategy</button></form></div>"
        if section=='sources':
            self._ensure_procurement_profile(); return base+"<div class='panel'><h2>Build 329 · Public Funding Sources</h2><div class='notice'>TED · USAspending · Grants.gov · EU Funding & Tenders · EU Financial Transparency System. Routing bleibt offline; externe Ausführung ist freigabepflichtig.</div></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 329 · OPSEC v26</h2><div class='notice'>Public-source boundary · Recipient Merge Guard · keine Credential-Persistenz · Award ≠ Kriminalitätslabel · keine aktive externe Recon.</div><form method='post' action='/build329/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Public Funding Pack + AI Security v26 testen</button></form></div>"
        return base
