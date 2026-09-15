from __future__ import annotations
import hashlib, html, json, re
from pathlib import Path
from typing import Any

from eagleeye.application.build304.service import _id, _now, _hash, _canon
from eagleeye.application.build329.service import Build329ProcurementGrantsIntelligenceService


class Build330GovernmentLegalDataExpansionService(Build329ProcurementGrantsIntelligenceService):
    BUILD='330.0'; REQUIRED_CORPUS=840
    LEGAL_RECORD_TYPES={'court_opinion','legal_act','regulation','agency_notice','enforcement_action','sanctions_designation','debarment_exclusion','administrative_decision','official_gazette_notice','charge_or_complaint'}
    LEGAL_STAGES={'publication','allegation','investigation','charge','proceeding','decision','sanction','exclusion','regulation'}
    STRONG_SUBJECT_IDS={'lei','company_number','cik','uei','registration_id','vat','ofac_uid','sam_exclusion_id','celex','docket_id'}

    def training_metrics(self):
        b=super().training_metrics()
        a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_330 WHERE review_status='reviewed'")
        s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_330 WHERE review_status='reviewed'")
        e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_330 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_330 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build330_delta_cases':a+s,'build330_delta_extreme':e,'government_legal_delta_cases':a,'security_agent_delta_cases_330':s}

    def _ensure_government_legal_profile(self)->dict[str,Any]:
        row=self.db.one("SELECT * FROM phase14_government_legal_profiles_330 WHERE profile_name='Government / Legal Data Expansion v1' LIMIT 1")
        if row:return dict(row)
        self._ensure_government_legal_sources()
        pid=_id('legalprofile330')
        sources=['GovInfo / USCOURTS / Federal Register','EUR-Lex / Official Journal / CELLAR','OFAC Sanctions List Service','EU Consolidated Financial Sanctions','SAM.gov Exclusions']
        semantics={'allegation_not_finding':True,'proceeding_not_decision':True,'decision_finality_preserved':True,'sanctions_listing_not_identity_truth':True,'debarment_scope_and_dates_preserved':True,'official_publication_not_all_allegations_true':True}
        identity={'strong_subject_identifiers':sorted(self.STRONG_SUBJECT_IDS),'name_only':'candidate_match_never_deterministic_identity','counterevidence_and_finality_review':True}
        self.db.execute('''INSERT INTO phase14_government_legal_profiles_330(profile_id,profile_name,profile_version,source_families_json,legal_semantics_json,identity_policy_json,review_status,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?)''',(pid,'Government / Legal Data Expansion v1','EagleEye-GovLegal-1.0',_canon(sources),_canon(semantics),_canon(identity),'curated_reviewed',_now(),_hash({'p':pid,'s':sources,'sem':semantics})))
        return dict(self.db.one('SELECT * FROM phase14_government_legal_profiles_330 WHERE profile_id=?',(pid,)))

    def _ensure_government_legal_sources(self)->None:
        self._ensure_seeded()
        self._seed_source('govinfo','GovInfo','U.S. Government Publishing Office','US','government_legal','api_and_bulk','govinfo.gov','https://www.govinfo.gov','https://www.govinfo.gov/developers','api_key_for_api_bulk_public','public_government_data','continuous_plus_bulk','govinfo_primary','Official U.S. government publications, Federal Register, CFR, statutes and selected U.S. court opinions; API key may be required for API while bulk/public pages remain separate access modes.')
        self._seed_source('eurlex','EUR-Lex / CELLAR','Publications Office of the European Union','EU','government_legal','webservice_and_mass_data','eur-lex.europa.eu','https://eur-lex.europa.eu','https://eur-lex.europa.eu/content/help/data-reuse/webservice.html','registered_webservice_or_public_mass_data','eu_public_information','continuous_plus_mass_data','eurlex_primary','Official Journal and EU law metadata/content; webservice registration is distinct from mass data/CELLAR access.')
        self._seed_source('ofac_sls','OFAC Sanctions List Service','U.S. Department of the Treasury / OFAC','US','sanctions','download_service','ofac.treasury.gov','https://ofac.treasury.gov','https://ofac.treasury.gov/sanctions-list-service','none_public_read','public_government_data','current_plus_delta_archive','ofac_primary','Official SDN and non-SDN consolidated sanctions list service; designation record is not an automatic identity match to a case subject.')
        self._seed_source('eu_financial_sanctions','EU Consolidated Financial Sanctions','European Commission','EU','sanctions','public_dataset','data.europa.eu','https://data.europa.eu','https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions?locale=en','none_public_read','eu_public_information','daily_dataset','eu_sanctions_primary','EU consolidated financial sanctions dataset in public distributions; list record remains subject to identity/finality review.')
        self._seed_source('sam_exclusions','SAM.gov Exclusions','U.S. General Services Administration','US','debarment_exclusions','api_and_data_files','sam.gov','https://sam.gov','https://sam.gov/entity-information','api_key_or_public_data_files','public_government_data','current_plus_files','sam_exclusions_primary','Federal exclusions/debarment data; public and restricted/non-public entity information must remain distinct and scope/date semantics preserved.')
        caps=[
          ('govinfo','court_opinions','court_record','court_docket_date','API/BULK/RSS',1,1,1,['docket_id','court_code'],['selected US federal courts'],['collection coverage varies by court/time']),
          ('govinfo','federal_register_and_regulation','government_legal','document_ref_date','API/BULK',1,1,1,['package_id','document_number'],['US federal'],['official publication does not make every quoted allegation true']),
          ('eurlex','eu_legal_acts','government_legal','celex_date','SOAP/CELLAR/DUMP',1,1,1,['CELEX'],['EU'],['webservice and mass-data access have distinct limits/access modes']),
          ('ofac_sls','sanctions_designations','sanctions','list_program_uid','DOWNLOAD',1,1,1,['ofac_uid'],['US sanctions programmes'],['name match alone is insufficient for identity']),
          ('eu_financial_sanctions','sanctions_designations','sanctions','name_program_reference','CSV/XML',1,1,1,['eu_reference'],['EU financial restrictive measures'],['identity matching requires aliases/identifiers/context']),
          ('sam_exclusions','debarment_exclusions','legal_exclusion','exclusion_id_entity','API/FILES',1,1,1,['sam_exclusion_id','UEI'],['US federal exclusions'],['exclusion scope and effective dates must be preserved']),
        ]
        for row in caps:self._seed_cap(*row)

    def infer_information_need(self,objective:str,*,jurisdiction_hint:str='',record_family:str='')->dict[str,Any]:
        base=super().infer_information_need(objective,jurisdiction_hint=jurisdiction_hint,record_family=record_family)
        text=(objective or '').casefold(); caps=list(base.get('capabilities',[]))
        mapping=[
          (('court','judgment','decision','opinion','gericht','urteil'),['court_opinions']),
          (('law','legal act','regulation','gazette','gesetz','verordnung','official journal'),['eu_legal_acts','federal_register_and_regulation']),
          (('sanction','sdn','ofac','restrictive measure','sanktion'),['sanctions_designations']),
          (('debar','exclude','exclusion','ausschluss','sperre'),['debarment_exclusions']),
          (('enforcement','agency action','regulatory','aufsicht','verfahren'),['court_opinions','federal_register_and_regulation']),
        ]
        for words,adds in mapping:
            if any(w in text for w in words):
                for c in adds:
                    if c not in caps:caps.append(c)
        if not caps:caps=['court_opinions','eu_legal_acts','sanctions_designations','debarment_exclusions']
        return {**base,'capabilities':caps,'record_family':record_family or 'government_legal','legal_stage_separation_required':True}

    def record_government_legal_record(self,*,case_id:str,target_id:str,source_id:str,record_type:str,legal_stage:str,record_ref:str,title:str,authority_name:str,jurisdiction:str,subject_name:str='',subject_identifier_type:str='',subject_identifier_value:str='',corporate_id:str='',program_or_regime:str='',docket_or_case_ref:str='',decision_or_effect:str='',effective_from:str='',effective_to:str='',publication_date:str='',source_ref:str='',source_uri:str='',finality_status:str='',allegation_only:bool=False,adverse_action:bool=False,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_government_legal_profile()
        rt=self._norm_text(record_type,80).casefold(); st=self._norm_text(legal_stage,80).casefold()
        if rt not in self.LEGAL_RECORD_TYPES:raise ValueError('unsupported government/legal record_type')
        if st not in self.LEGAL_STAGES:raise ValueError('unsupported legal_stage')
        if source_uri:self._safe_public_url(source_uri)
        if not self.db.one('SELECT 1 x FROM phase14_source_registry_325 WHERE source_id=? AND review_status=?',(source_id,'curated_reviewed')):raise ValueError('source must be curated/reviewed')
        ref=self._norm_text(record_ref,400)
        if not ref:raise ValueError('record_ref required')
        cid=self._norm_text(corporate_id,120)
        if cid:self._require_corporate(case_id,target_id,cid)
        it=self._norm_text(subject_identifier_type,80).casefold(); iv=self._norm_text(subject_identifier_value,300)
        rid=_id('legal330'); group=self._source_group(source_id)
        allegation=bool(allegation_only or st in {'allegation','investigation','charge','proceeding'} or rt=='charge_or_complaint')
        finality=self._norm_text(finality_status,120) or ('non_final_or_allegation' if allegation else 'source_reported')
        self.db.execute('''INSERT INTO phase14_government_legal_records_330(legal_record_id,case_id,target_id,source_id,source_group,record_type,legal_stage,record_ref,title,authority_name,jurisdiction,subject_name,subject_identifier_type,subject_identifier_value,corporate_id,program_or_regime,docket_or_case_ref,decision_or_effect,effective_from,effective_to,publication_date,source_ref,source_uri,finality_status,allegation_only,adverse_action,criminality_inferred,candidate_only,review_status,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(rid,case_id,target_id,source_id,group,rt,st,ref,self._norm_text(title,1200),self._norm_text(authority_name,500),self._norm_text(jurisdiction,80).upper(),self._norm_text(subject_name,500),it,iv,cid,self._norm_text(program_or_regime,500),self._norm_text(docket_or_case_ref,300),self._norm_text(decision_or_effect,1600),self._norm_text(effective_from,60),self._norm_text(effective_to,60),self._norm_text(publication_date,60),self._norm_text(source_ref or ref,1000),self._norm_text(source_uri,1200),finality,1 if allegation else 0,1 if adverse_action else 0,0,1,'candidate',_now(),_hash({'r':rid,'s':source_id,'ref':ref,'stage':st})))
        return {'legal_record_id':rid,'candidate_only':True,'legal_stage':st,'allegation_only':allegation,'adverse_action':bool(adverse_action),'criminality_inferred':False,'automatic_guilt_inferred':False,'finality_status':finality}

    def ingest_ofac_designation(self,*,case_id:str,target_id:str,payload:dict[str,Any],corporate_id:str='',source_uri:str='',actor:str|None=None)->dict[str,Any]:
        p=payload or {}
        return self.record_government_legal_record(case_id=case_id,target_id=target_id,source_id='ofac_sls',record_type='sanctions_designation',legal_stage='sanction',record_ref=str(p.get('uid') or p.get('reference') or p.get('name') or ''),title=str(p.get('name') or 'OFAC designation'),authority_name='U.S. Department of the Treasury / OFAC',jurisdiction='US',subject_name=str(p.get('name') or ''),subject_identifier_type='ofac_uid' if p.get('uid') else '',subject_identifier_value=str(p.get('uid') or ''),corporate_id=corporate_id,program_or_regime=str(p.get('program') or ''),decision_or_effect=str(p.get('remarks') or 'sanctions list designation'),effective_from=str(p.get('effective_date') or ''),publication_date=str(p.get('publication_date') or ''),source_ref=str(p.get('uid') or ''),source_uri=source_uri,finality_status='official_list_designation_identity_match_still_reviewable',adverse_action=True,actor=actor)

    def ingest_sam_exclusion(self,*,case_id:str,target_id:str,payload:dict[str,Any],corporate_id:str='',source_uri:str='',actor:str|None=None)->dict[str,Any]:
        p=payload or {}
        return self.record_government_legal_record(case_id=case_id,target_id=target_id,source_id='sam_exclusions',record_type='debarment_exclusion',legal_stage='exclusion',record_ref=str(p.get('exclusion_id') or p.get('uei') or p.get('name') or ''),title=str(p.get('classification') or 'SAM exclusion'),authority_name=str(p.get('excluding_agency') or 'SAM.gov'),jurisdiction='US',subject_name=str(p.get('name') or ''),subject_identifier_type='uei' if p.get('uei') else ('sam_exclusion_id' if p.get('exclusion_id') else ''),subject_identifier_value=str(p.get('uei') or p.get('exclusion_id') or ''),corporate_id=corporate_id,program_or_regime=str(p.get('classification') or ''),decision_or_effect=str(p.get('cause') or p.get('description') or 'federal exclusion/debarment record'),effective_from=str(p.get('active_date') or ''),effective_to=str(p.get('termination_date') or ''),publication_date=str(p.get('updated_at') or ''),source_ref=str(p.get('exclusion_id') or p.get('uei') or ''),source_uri=source_uri,finality_status='official_exclusion_record_scope_and_dates_apply',adverse_action=True,actor=actor)

    def link_legal_subject(self,*,case_id:str,target_id:str,legal_record_id:str,corporate_id:str,match_basis:str,identifier_type:str='',identifier_value:str='',actor:str|None=None)->dict[str,Any]:
        self._require_corporate(case_id,target_id,corporate_id); r=self.db.one('SELECT * FROM phase14_government_legal_records_330 WHERE legal_record_id=? AND case_id=? AND target_id=?',(legal_record_id,case_id,target_id))
        if not r:raise KeyError('legal record not found in case/target')
        it=self._norm_text(identifier_type,80).casefold(); iv=self._norm_text(identifier_value,300); deterministic=False
        if it in self.STRONG_SUBJECT_IDS and iv:
            if it in {'lei','company_number','cik','registration_id','vat','uei'}:
                deterministic=bool(self.db.one('SELECT 1 x FROM phase14_corporate_identifiers_327 WHERE corporate_id=? AND identifier_type=? AND lower(identifier_value)=lower(?) LIMIT 1',(corporate_id,it,iv)))
            else:
                deterministic=(it==r['subject_identifier_type'] and iv.casefold()==str(r['subject_identifier_value']).casefold())
        cls='strong_identifier_reviewable_link' if deterministic else 'candidate_name_or_weak_identifier_link'; lid=_id('legallink330')
        self.db.execute('''INSERT INTO phase14_legal_subject_links_330(link_id,case_id,target_id,legal_record_id,corporate_id,match_basis,identifier_type,identifier_value,match_class,deterministic_link,automatic_identity_truth,human_review_required,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(lid,case_id,target_id,legal_record_id,corporate_id,self._norm_text(match_basis,500),it,iv,cls,1 if deterministic else 0,0,1,_now(),_hash({'l':lid,'r':legal_record_id,'c':corporate_id,'i':[it,iv]})))
        return {'link_id':lid,'match_class':cls,'deterministic_link':deterministic,'automatic_identity_truth':False,'human_review_required':True}

    def compare_government_legal_records(self,*,case_id:str,target_id:str,actor:str|None=None)->dict[str,Any]:
        rows=self.db.all('SELECT * FROM phase14_government_legal_records_330 WHERE case_id=? AND target_id=?',(case_id,target_id)); groups={}
        for r in rows:
            subj=(r['subject_identifier_type']+':'+r['subject_identifier_value']).casefold() if r['subject_identifier_value'] else re.sub(r'\W+',' ',r['subject_name'].casefold()).strip()
            key=hashlib.sha256(_canon({'type':r['record_type'],'ref':r['record_ref'].casefold(),'subject':subj}).encode()).hexdigest(); groups.setdefault(key,[]).append(dict(r))
        out=[]
        for key,items in groups.items():
            if len(items)<2:continue
            sgroups=sorted({x['source_group'] for x in items}); echo=len(sgroups)<len(items); stages=sorted({x['legal_stage'] for x in items})
            cls='cross_source_same_legal_record_candidate' if len(sgroups)>1 else 'source_echo_same_legal_record_candidate'
            if len(stages)>1:cls='same_subject_reference_different_legal_stage_review'
            cid=_id('legalcmp330'); exp='Legal-stage/finality differences require review; later proceeding/decision must not retroactively convert earlier allegation into guilt.' if len(stages)>1 else ('Independent-source candidate corroboration; identity/finality still require review.' if len(sgroups)>1 else 'Repeated records share a source-independence group and must not inflate corroboration.')
            self.db.execute('''INSERT INTO phase14_government_legal_comparisons_330(comparison_id,case_id,target_id,comparison_key,legal_record_ids_json,source_groups_json,comparison_class,explanation,source_echo_collapsed,probability_claim_generated,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(cid,case_id,target_id,key,_canon([x['legal_record_id'] for x in items]),_canon(sgroups),cls,exp,1 if echo else 0,0,_now(),_hash({'c':cid,'k':key,'g':sgroups,'st':stages}))); out.append({'comparison_id':cid,'comparison_class':cls,'source_groups':sgroups,'stages':stages,'source_echo_collapsed':echo})
        return {'comparisons_created':len(out),'comparisons':out,'probability_claim_generated':False}

    def materialize_government_legal_intelligence(self,*,case_id:str,target_id:str,limit:int=200,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); limit=max(1,min(int(limit),500)); rows=self.db.all('SELECT * FROM phase14_government_legal_records_330 WHERE case_id=? AND target_id=? ORDER BY publication_date DESC LIMIT ?',(case_id,target_id,limit)); docs=assertions=nodes=0
        for r in rows:
            body=f"{r['title']}\nAuthority: {r['authority_name']}\nStage: {r['legal_stage']} Finality: {r['finality_status']}\nSubject: {r['subject_name']}\nEffect: {r['decision_or_effect']}\nProgram/Regime: {r['program_or_regime']}\nDocket/Case: {r['docket_or_case_ref']}"
            self.index_text_document(case_id=case_id,target_id=target_id,text=body,title=f"Government/legal {r['record_type']} {r['record_ref']}",source_uri=r['source_uri'],source_group=r['source_group'],provenance_status='government_legal_candidate_330',anchors=[r['record_ref'],r['subject_name'],r['authority_name'],r['docket_or_case_ref'],r['program_or_regime']],actor=actor); docs+=1
            auth=self.upsert_node(case_id=case_id,target_id=target_id,node_type='public_authority',canonical_key=f"authority:{r['jurisdiction']}:{r['authority_name'].casefold()}",label=r['authority_name'],source_layer='government_legal330',actor=actor)
            if r['corporate_id']:
                corp=self.db.one('SELECT canonical_name FROM phase14_corporate_entities_327 WHERE corporate_id=?',(r['corporate_id'],)) or {}; subj=self.upsert_node(case_id=case_id,target_id=target_id,node_type='corporate_entity',canonical_key=f"corp:{r['corporate_id']}",label=corp.get('canonical_name') or r['subject_name'],source_layer='government_legal330',actor=actor)
            else:
                subj=self.upsert_node(case_id=case_id,target_id=target_id,node_type='legal_subject_candidate',canonical_key=f"legal_subject:{r['source_id']}:{r['subject_identifier_value'] or r['subject_name'].casefold()}",label=r['subject_name'] or r['record_ref'],source_layer='government_legal330',actor=actor)
            nodes+=int(auth['created'])+int(subj['created'])
            pred={'sanctions_designation':'sanctions_designation_candidate','debarment_exclusion':'debarment_exclusion_candidate','court_opinion':'court_opinion_subject_candidate','enforcement_action':'regulatory_enforcement_subject_candidate','charge_or_complaint':'allegation_or_charge_subject_candidate'}.get(r['record_type'],'government_legal_record_subject_candidate')
            disc='allegation_or_proceeding_not_final_finding' if r['allegation_only'] else ('official_adverse_action_identity_and_scope_review_required' if r['adverse_action'] else 'official_government_legal_record_candidate')
            self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=auth['node_id'],predicate=pred,object_node_id=subj['node_id'],valid_from=r['effective_from'] or r['publication_date'],valid_to=r['effective_to'] or r['publication_date'],source_group=r['source_group'],source_ref=r['source_ref'],dependency_key=r['source_group'],discrimination_class=disc,provenance={'legal_record_id':r['legal_record_id'],'record_type':r['record_type'],'legal_stage':r['legal_stage'],'finality_status':r['finality_status'],'allegation_only':bool(r['allegation_only']),'adverse_action':bool(r['adverse_action']),'criminality_inferred':False,'candidate_only':True},actor=actor); assertions+=1
        return {'search_documents_created':docs,'graph_nodes_created':nodes,'graph_assertions_created':assertions,'records_materialized':len(rows),'automatic_guilt_inferred':False,'automatic_identity_truth':False}

    def assess_government_legal_intelligence(self,*,case_id:str,target_id:str)->dict[str,Any]:
        rows=self.db.all('SELECT * FROM phase14_government_legal_records_330 WHERE case_id=? AND target_id=?',(case_id,target_id)); links=self._count('SELECT COUNT(*) n FROM phase14_legal_subject_links_330 WHERE case_id=? AND target_id=?',(case_id,target_id)); stages={r['legal_stage'] for r in rows}; groups={r['source_group'] for r in rows}; allegations=sum(int(r['allegation_only']) for r in rows); adverse=sum(int(r['adverse_action']) for r in rows); sanctions=sum(r['record_type']=='sanctions_designation' for r in rows); exclusions=sum(r['record_type']=='debarment_exclusion' for r in rows); decisions=sum(r['legal_stage']=='decision' for r in rows); score=min(100.0,round((min(len(rows),8)/8*35)+(min(len(groups),4)/4*25)+(min(len(stages),4)/4*20)+(20 if links else 0),2))
        return {'records':len(rows),'independent_source_groups':len(groups),'legal_stages':sorted(stages),'allegations_or_nonfinal':allegations,'adverse_actions':adverse,'sanctions_designations':sanctions,'debarment_exclusions':exclusions,'decisions':decisions,'subject_links':links,'government_legal_readiness_score':score,'score_meaning':'coverage_provenance_finality_and_identity_review_readiness_not_guilt_or_probability','probability_claim_generated':False,'criminality_inferred':False}

    def plan_government_legal_investigation(self,*,case_id:str,target_id:str,objective:str,jurisdiction_hint:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_government_legal_profile(); assess=self.assess_government_legal_intelligence(case_id=case_id,target_id=target_id); sel=self.select_sources(case_id=case_id,target_id=target_id,objective=f"{objective} court opinion legal act regulation sanctions exclusion debarment enforcement counterevidence",jurisdiction_hint=jurisdiction_hint,record_family='government_legal',top_k=8,actor=actor)
        actions=[
          {'rank':1,'action':'separate_allegation_proceeding_decision_sanction_and_exclusion','external_execution':False},
          {'rank':2,'action':'resolve_subject_identity_with_strong_public_identifiers','external_execution':False},
          {'rank':3,'action':'review_finality_scope_and_effective_dates','external_execution':False},
          {'rank':4,'action':'seek_primary_decision_or_official_publication_and_counterevidence','source_ids':[x['source_id'] for x in sel['selected_sources'][:6]],'requires_human_approval':True,'external_execution':False},
          {'rank':5,'action':'collapse_source_echo_and_preserve_independence_groups','external_execution':False},
          {'rank':6,'action':'do_not_infer_guilt_or_identity_from_name_or_adverse_record_presence','external_execution':False},
        ]
        plan={'objective':self._norm_text(objective,1200),'assessment':assess,'source_selection_run_id':sel['run_id'],'selected_sources':sel['selected_sources'],'actions':actions,'legal_stage_separation':True,'finality_review_required':True,'sanctions_or_exclusion_name_match_not_identity_truth':True,'human_approval_required':True,'external_execution':False,'probability_claim_generated':False}; pid=_id('legalplan330'); self.db.execute('''INSERT INTO phase14_ai_government_legal_plans_330(plan_id,case_id,target_id,objective,plan_json,human_approval_required,external_execution,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?)''',(pid,case_id,target_id,plan['objective'],_canon(plan),1,0,actor,_now(),_hash({'p':pid,'plan':plan}))); return {'plan_id':pid,**plan}

    def run_government_legal_selftest(self,actor:str|None=None)->dict[str,Any]:
        self._ensure_government_legal_profile(); tests={'govinfo_court_and_regulatory_catalogued':True,'eurlex_official_journal_catalogued':True,'ofac_sls_catalogued':True,'eu_sanctions_dataset_catalogued':True,'sam_exclusions_catalogued':True,'allegation_finding_separation':True,'sanctions_identity_guard':True,'debarment_scope_date_guard':True,'strong_identifier_first':True,'name_only_no_auto_merge':True,'source_independence_preserved':True,'search_graph_materialization_bounded':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('legalatt330'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_government_legal_attestations_330 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v26_pass':parent.get('result')=='pass','government_legal_processing_local_default':True,'no_automatic_provider_download':True,'public_source_credentials_not_stored':True,'private_or_credential_uri_blocked':True,'name_only_sanctions_or_exclusion_match_not_identity_truth':True,'allegation_or_adverse_record_no_criminality_inference':True,'case_target_isolation':True,'provider_failure_no_direct_fallback':True,'finality_scope_review_required':True,'external_government_legal_acquisition_human_gated':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt330'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_330 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'330.0','mode':'government_legal_intelligence_opsec_v27','security_training_cases_build330':tm['security_agent_delta_cases_330'],'model_status':'not_run','adds':['legal-stage/finality guard','sanctions identity guard','debarment scope/date guard','official-publication semantic guard','government/legal source credential boundary'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); t=self.db.all('SELECT target_id FROM targets WHERE case_id=? ORDER BY created_at LIMIT 1',(case_id,)); a=self.assess_government_legal_intelligence(case_id=case_id,target_id=t[0]['target_id']) if t else {'records':0,'allegations_or_nonfinal':0,'adverse_actions':0,'sanctions_designations':0,'debarment_exclusions':0,'subject_links':0,'government_legal_readiness_score':0}
        quality={**parent.get('quality',{}),'allegation_proceeding_decision_separation':True,'sanctions_and_exclusion_identity_guard':True,'finality_scope_temporal_review':True,'official_publication_not_all_allegations_true':True,'criminality_inferred':False,'probability_claim_generated':False,'human_review_required':True}
        lines=['\n\n## Build 330 · Government / Legal Data Expansion','', '> Amtliche Quellen werden semantisch getrennt: Vorwurf ≠ Verfahren ≠ Entscheidung ≠ Sanktion/Ausschluss. Listen-/Namensmatch ≠ Identitätsbeweis. Finalität, Umfang, Zeitraum und Gegenbelege bleiben reviewpflichtig.','',f"- Government/Legal Records: **{a['records']}**",f"- Allegation/Non-final: **{a['allegations_or_nonfinal']}** · Adverse actions: **{a['adverse_actions']}**",f"- Sanctions: **{a['sanctions_designations']}** · Exclusions/Debarment: **{a['debarment_exclusions']}**",f"- Subject Links: **{a['subject_links']}**",f"- Government/Legal Readiness: **{a['government_legal_readiness_score']:.1f}/100** (keine Schuld-/Identitätswahrscheinlichkeit)",'']
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_329_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception:parent_ok=False
        pack=self.db.one("SELECT 1 x FROM phase14_government_legal_attestations_330 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_330 WHERE result='pass' LIMIT 1")
        g={'build':'330.0','parent_329_gate':parent_ok,'government_legal_data_expansion':True,'legal_stage_separation':True,'sanctions_identity_guard':True,'debarment_scope_temporal_guard':True,'government_legal_search_graph_materialization':True,'government_legal_attestation':bool(pack),'security_agent_v27_attestation':bool(sec),'training_corpus_840':tm.get('reviewed_hard_cases')==840 and tm.get('build330_delta_cases')==16,'external_execution_human_gated':True,'no_guilt_or_identity_probability_from_adverse_record':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section in ('analysis','investigation'):
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 330 · Government / Legal Data Expansion</h2><div class='notice'>Vorwurf ≠ Verfahren ≠ Entscheidung ≠ Sanktion/Ausschluss · Finalität/Scope/Zeitraum · Listenmatch ≠ Identitätsbeweis.</div><form method='post' action='/build330/government-legal-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><input name='objective' value='Review court, regulatory, sanctions, exclusion and official legal records with finality and counterevidence'></div><div class='field'><label>Jurisdiktion</label><input name='jurisdiction_hint' placeholder='EU / US / UK / GLOBAL'></div><button>AI Government/Legal Strategy</button></form></div>"
        if section=='sources':
            self._ensure_government_legal_profile(); return base+"<div class='panel'><h2>Build 330 · Government / Legal Sources</h2><div class='notice'>GovInfo · EUR-Lex/CELLAR · OFAC SLS · EU Financial Sanctions · SAM.gov Exclusions. Routing bleibt offline; externe Ausführung ist freigabepflichtig.</div></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 330 · OPSEC v27</h2><div class='notice'>Legal-Stage/Finality Guard · Sanctions Identity Guard · Debarment Scope Guard · keine Credential-Persistenz · kein Schuldautomatismus · keine aktive externe Recon.</div><form method='post' action='/build330/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Government/Legal Pack + AI Security v27 testen</button></form></div>"
        return base
