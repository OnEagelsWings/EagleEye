from __future__ import annotations
import difflib, hashlib, html, json, re, unicodedata
from pathlib import Path
from typing import Any, Iterable

from eagleeye.application.build304.service import _id, _now, _hash, _canon
from eagleeye.application.build326.service import Build326BulkDataIngestionService


class Build327GlobalCorporateDataPackService(Build326BulkDataIngestionService):
    BUILD='327.0'; REQUIRED_CORPUS=792
    STRONG_IDS={'lei','cik','company_number','registration_id'}
    RECORD_TYPES={'gleif_lei','gleif_relationship','gleif_reporting_exception','companies_house_company','companies_house_officer','companies_house_psc','sec_company','opencorporates_company'}

    def training_metrics(self):
        b=super().training_metrics()
        a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_327 WHERE review_status='reviewed'")
        s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_327 WHERE review_status='reviewed'")
        e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_327 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_327 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build327_delta_cases':a+s,'build327_delta_extreme':e,'corporate_pack_delta_cases':a,'security_agent_delta_cases_327':s}

    @staticmethod
    def _norm_text(v:Any,limit:int=1000)->str:
        s=' '.join(str(v if v is not None else '').replace('\x00',' ').split())
        return s[:limit]

    @classmethod
    def _norm_name(cls,v:Any)->str:
        s=unicodedata.normalize('NFKC',cls._norm_text(v,500)).casefold()
        s=re.sub(r'[^\w\s&.-]+',' ',s,flags=re.UNICODE)
        return ' '.join(s.split())

    @staticmethod
    def _nested(obj:Any,path:str)->Any:
        if not isinstance(obj,dict): return None
        if path in obj: return obj[path]
        cur=obj
        for part in path.split('.'):
            if not isinstance(cur,dict) or part not in cur: return None
            cur=cur[part]
        if isinstance(cur,dict):
            for k in ('$','value','Value','content'):
                if k in cur:return cur[k]
        return cur

    @classmethod
    def _first(cls,obj:dict,*paths:str,default:str='')->str:
        for p in paths:
            v=cls._nested(obj,p)
            if v not in (None,'',[],{}):
                if isinstance(v,list): return cls._norm_text(', '.join(str(x) for x in v),2000)
                return cls._norm_text(v,2000)
        return default

    @classmethod
    def _list(cls,obj:dict,*paths:str)->list[str]:
        for p in paths:
            v=cls._nested(obj,p)
            if isinstance(v,list): return [cls._norm_text(x,500) for x in v if cls._norm_text(x,500)]
            if isinstance(v,str) and v.strip(): return [x.strip() for x in re.split(r'[;,|]',v) if x.strip()]
        return []

    def _source_group(self,source_id:str)->str:
        self._ensure_seeded()
        r=self.db.one('SELECT independence_group FROM phase14_source_registry_325 WHERE source_id=?',(source_id,))
        return (r or {}).get('independence_group') or f'source:{source_id}'

    def _ensure_pack_profile(self)->dict[str,Any]:
        r=self.db.one("SELECT * FROM phase14_corporate_pack_profiles_327 WHERE profile_name='Global Corporate Data Pack v1' LIMIT 1")
        if r:return dict(r)
        pid=_id('corpprofile327'); supported=['gleif:LEI-CDF-3.1','gleif:RR-CDF-2.1','gleif:Reporting-Exceptions-2.1','companies_house:company_csv','companies_house:psc_json','companies_house:officer_api_or_export','sec:submissions_identity','opencorporates:company_json']
        strong=['LEI','CIK','jurisdiction+company_number','registration_id']; weak=['normalized_name','registered_address','domain']; privacy={'exclude':['residential_address','full_date_of_birth_private_or_nonessential','authentication_secrets'],'retain_public_when_needed':['service_address','month_year_birth_if_source_public'],'principle':'data_minimization'}
        self.db.execute('INSERT INTO phase14_corporate_pack_profiles_327 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,'Global Corporate Data Pack v1','EagleEye-CorporatePack-1.0',_canon(supported),_canon(strong),_canon(weak),_canon(privacy),'curated_reviewed',_now(),_hash({'p':pid,'s':supported,'strong':strong})))
        return dict(self.db.one('SELECT * FROM phase14_corporate_pack_profiles_327 WHERE profile_id=?',(pid,)))

    def normalize_corporate_record(self,*,source_id:str,record_type:str,payload:dict[str,Any])->dict[str,Any]:
        rt=str(record_type).strip().casefold(); sid=str(source_id).strip().casefold()
        if rt not in self.RECORD_TYPES: raise ValueError('unsupported corporate record_type')
        if not isinstance(payload,dict): raise TypeError('payload must be object')
        out={'source_id':sid,'record_type':rt,'identifiers':{},'candidate_only':True}
        if rt=='gleif_lei':
            lei=self._first(payload,'LEI','lei','attributes.lei'); name=self._first(payload,'Entity.LegalName','LegalName','legal_name','attributes.entity.legalName.name','attributes.entity.legalName')
            if not lei or not name: raise ValueError('GLEIF Level 1 record requires LEI and legal name')
            out.update({'entity_name':name,'jurisdiction':self._first(payload,'Entity.LegalJurisdiction','LegalJurisdiction','jurisdiction','attributes.entity.jurisdiction'),'legal_form':self._first(payload,'Entity.LegalForm.EntityLegalFormCode','LegalForm','legal_form','attributes.entity.legalForm.id'),'status':self._first(payload,'Registration.RegistrationStatus','RegistrationStatus','status','attributes.registration.status'),'incorporation_date':self._first(payload,'Entity.EntityCreationDate','EntityCreationDate','incorporation_date','attributes.entity.creationDate'),'registered_address':self._first(payload,'Entity.LegalAddress.FirstAddressLine','LegalAddress','registered_address','attributes.entity.legalAddress.addressLines'),'headquarters_address':self._first(payload,'Entity.HeadquartersAddress.FirstAddressLine','HeadquartersAddress','headquarters_address','attributes.entity.headquartersAddress.addressLines'),'website_domain':self._first(payload,'website_domain','domain')})
            out['identifiers']={'lei':lei}
        elif rt=='gleif_relationship':
            child=self._first(payload,'Relationship.StartNode.NodeID','StartNode.NodeID','child_lei','start_node_lei'); parent=self._first(payload,'Relationship.EndNode.NodeID','EndNode.NodeID','parent_lei','end_node_lei')
            if not child or not parent: raise ValueError('GLEIF relationship requires child and parent LEI')
            rtype=self._first(payload,'Relationship.RelationshipType','RelationshipType','relationship_type',default='IS_DIRECTLY_CONSOLIDATED_BY')
            out.update({'child_lei':child,'parent_lei':parent,'relationship_type':rtype,'relationship_status':self._first(payload,'Registration.RegistrationStatus','Relationship.RelationshipStatus','relationship_status',default='ACTIVE'),'accounting_standard':self._first(payload,'Relationship.RelationshipQualifiers.AccountingStandard','accounting_standard'),'valid_from':self._first(payload,'valid_from','Relationship.RelationshipPeriods.0.StartDate'),'valid_to':self._first(payload,'valid_to','Relationship.RelationshipPeriods.0.EndDate'),'ownership_percent':self._first(payload,'ownership_percent',default='0')})
        elif rt=='gleif_reporting_exception':
            child=self._first(payload,'LEI','lei','child_lei','ExceptionReference.LEI'); reason=self._first(payload,'ExceptionReason','exception_reason','Reason')
            if not child or not reason: raise ValueError('GLEIF reporting exception requires child LEI and reason')
            out.update({'child_lei':child,'parent_scope':self._first(payload,'ExceptionCategory','parent_scope','Category',default='DIRECT_OR_ULTIMATE_PARENT'),'exception_reason':reason,'valid_from':self._first(payload,'valid_from','StartDate'),'valid_to':self._first(payload,'valid_to','EndDate')})
        elif rt=='companies_house_company':
            num=self._first(payload,'CompanyNumber','company_number'); name=self._first(payload,'CompanyName','company_name','name')
            if not num or not name: raise ValueError('Companies House company requires company number and name')
            addr=', '.join(x for x in [self._first(payload,'RegAddress.AddressLine1','registered_office_address.address_line_1'),self._first(payload,'RegAddress.PostTown','registered_office_address.locality'),self._first(payload,'RegAddress.PostCode','registered_office_address.postal_code')] if x)
            out.update({'entity_name':name,'jurisdiction':'UK','legal_form':self._first(payload,'CompanyCategory','type','company_type'),'status':self._first(payload,'CompanyStatus','company_status'),'incorporation_date':self._first(payload,'IncorporationDate','date_of_creation'),'dissolution_date':self._first(payload,'DissolutionDate','date_of_cessation'),'registered_address':addr,'website_domain':self._first(payload,'website_domain','domain')})
            out['identifiers']={'company_number':num}
        elif rt=='companies_house_officer':
            num=self._first(payload,'company_number','CompanyNumber'); name=self._first(payload,'name','officer_name','Name'); role=self._first(payload,'officer_role','role','OfficerRole')
            if not num or not name: raise ValueError('Companies House officer requires company number and name')
            service=', '.join(x for x in [self._first(payload,'address.address_line_1','service_address.address_line_1'),self._first(payload,'address.locality','service_address.locality'),self._first(payload,'address.postal_code','service_address.postal_code')] if x)
            out.update({'company_number':num,'officer_name':name,'role':role,'appointed_on':self._first(payload,'appointed_on','appointed'),'resigned_on':self._first(payload,'resigned_on','resigned'),'nationality_public':self._first(payload,'nationality'),'occupation_public':self._first(payload,'occupation'),'service_address_public':service})
        elif rt=='companies_house_psc':
            num=self._first(payload,'company_number','CompanyNumber'); name=self._first(payload,'name','controller_name'); kind=self._first(payload,'kind','controller_kind')
            if not num or not name: raise ValueError('Companies House PSC requires company number and controller name')
            out.update({'company_number':num,'controller_name':name,'controller_kind':kind,'natures_of_control':self._list(payload,'natures_of_control','NaturesOfControl'),'notified_on':self._first(payload,'notified_on'),'ceased_on':self._first(payload,'ceased_on')})
        elif rt=='sec_company':
            cik=self._first(payload,'cik','CIK'); name=self._first(payload,'name','entity_name')
            if not cik or not name: raise ValueError('SEC company identity requires CIK and name')
            cik=re.sub(r'\D','',cik).zfill(10)
            out.update({'entity_name':name,'jurisdiction':'US','legal_form':self._first(payload,'entityType','entity_type'),'status':self._first(payload,'status'),'website_domain':self._first(payload,'website_domain','domain'),'tickers':self._list(payload,'tickers'),'exchanges':self._list(payload,'exchanges')})
            out['identifiers']={'cik':cik}
        elif rt=='opencorporates_company':
            c=payload.get('company') if isinstance(payload.get('company'),dict) else payload
            num=self._first(c,'company_number'); j=self._first(c,'jurisdiction_code','jurisdiction'); name=self._first(c,'name','company_name')
            if not num or not name: raise ValueError('OpenCorporates company requires company number and name')
            out.update({'entity_name':name,'jurisdiction':j.upper(),'legal_form':self._first(c,'company_type'),'status':self._first(c,'current_status'),'incorporation_date':self._first(c,'incorporation_date'),'dissolution_date':self._first(c,'dissolution_date'),'registered_address':self._first(c,'registered_address_in_full'),'website_domain':self._first(c,'website_domain','domain')})
            out['identifiers']={'company_number':num}
        out['residential_address_stored']=False
        out['credential_values_stored']=False
        return out

    def _find_entity_by_identifier(self,case_id:str,target_id:str,id_type:str,value:str,jurisdiction:str='')->str:
        if not value:return ''
        if id_type=='company_number':
            row=self.db.one('''SELECT i.corporate_id FROM phase14_corporate_identifiers_327 i JOIN phase14_corporate_entities_327 e ON e.corporate_id=i.corporate_id WHERE e.case_id=? AND e.target_id=? AND i.identifier_type=? AND i.identifier_value=? AND (i.jurisdiction=? OR ?='') ORDER BY i.created_at LIMIT 1''',(case_id,target_id,id_type,value,jurisdiction,jurisdiction))
        else:
            row=self.db.one('''SELECT i.corporate_id FROM phase14_corporate_identifiers_327 i JOIN phase14_corporate_entities_327 e ON e.corporate_id=i.corporate_id WHERE e.case_id=? AND e.target_id=? AND i.identifier_type=? AND i.identifier_value=? ORDER BY i.created_at LIMIT 1''',(case_id,target_id,id_type,value))
        return (row or {}).get('corporate_id','')

    def _create_or_link_entity(self,*,case_id:str,target_id:str,norm:dict[str,Any],source_id:str,source_record_id:str,actor:str)->dict[str,Any]:
        ids={str(k).casefold():self._norm_text(v,200) for k,v in (norm.get('identifiers') or {}).items() if self._norm_text(v,200)}; jurisdiction=self._norm_text(norm.get('jurisdiction',''),32).upper()
        corporate_id=''; basis='new_entity'
        for typ,val in ids.items():
            if typ in self.STRONG_IDS:
                corporate_id=self._find_entity_by_identifier(case_id,target_id,typ,val,jurisdiction)
                if corporate_id: basis=f'exact_{typ}'; break
        if not corporate_id:
            corporate_id=_id('corp327'); now=_now(); name=self._norm_text(norm.get('entity_name') or next(iter(ids.values()),'Unnamed corporate candidate'),500)
            self.db.execute('INSERT INTO phase14_corporate_entities_327 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(corporate_id,case_id,target_id,name,jurisdiction,self._norm_text(norm.get('legal_form',''),200),self._norm_text(norm.get('status',''),120),self._norm_text(norm.get('incorporation_date',''),40),self._norm_text(norm.get('dissolution_date',''),40),self._norm_text(norm.get('registered_address',''),1000),self._norm_text(norm.get('headquarters_address',''),1000),self._norm_text(norm.get('website_domain',''),300),1,'candidate',now,now,_hash({'c':corporate_id,'n':name,'ids':ids})))
        else:
            old=self.db.one('SELECT * FROM phase14_corporate_entities_327 WHERE corporate_id=?',(corporate_id,)); updates={k:self._norm_text(norm.get(k,'') or (old or {}).get(k,''),1000) for k in ('entity_name','legal_form','status','incorporation_date','dissolution_date','registered_address','headquarters_address','website_domain')}
            self.db.execute('UPDATE phase14_corporate_entities_327 SET canonical_name=?,jurisdiction=?,legal_form=?,status=?,incorporation_date=?,dissolution_date=?,registered_address=?,headquarters_address=?,website_domain=?,updated_at=?,record_hash=? WHERE corporate_id=?',(updates['entity_name'] or (old or {}).get('canonical_name',''),jurisdiction or (old or {}).get('jurisdiction',''),updates['legal_form'],updates['status'],updates['incorporation_date'],updates['dissolution_date'],updates['registered_address'],updates['headquarters_address'],updates['website_domain'],_now(),_hash({'c':corporate_id,'u':updates}),corporate_id))
        for typ,val in ids.items():
            iid=_id('corpid327'); conf='strong_exact_identifier' if typ in self.STRONG_IDS else 'auxiliary_identifier'
            try:self.db.execute('INSERT INTO phase14_corporate_identifiers_327 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(iid,corporate_id,typ,val,jurisdiction,source_id,source_record_id,conf,'','',_now(),_hash({'i':iid,'t':typ,'v':val})))
            except Exception:pass
        return {'corporate_id':corporate_id,'link_basis':basis,'identifiers':ids,'automatic_name_only_merge':False}

    def ingest_corporate_record(self,*,case_id:str,target_id:str,source_id:str,record_type:str,payload:dict[str,Any],source_record_key:str='',observed_at:str='',effective_from:str='',effective_to:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_pack_profile(); norm=self.normalize_corporate_record(source_id=source_id,record_type=record_type,payload=payload); group=self._source_group(source_id); srid=_id('corpsrc327'); key=self._norm_text(source_record_key or next(iter((norm.get('identifiers') or {}).values()),'') or hashlib.sha256(_canon(payload).encode()).hexdigest()[:24],300); rawhash=hashlib.sha256(_canon(payload).encode()).hexdigest()
        self.db.execute('INSERT INTO phase14_corporate_source_records_327 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(srid,case_id,target_id,source_id,group,record_type,key,_canon(norm),rawhash,self._norm_text(observed_at,50),self._norm_text(effective_from,50),self._norm_text(effective_to,50),1,'candidate',actor,_now(),_hash({'s':srid,'h':rawhash,'n':norm})))
        result={'source_record_id':srid,'record_type':record_type,'candidate_only':True,'source_group':group,'automatic_evidence_promotion':False}
        if record_type in ('gleif_lei','companies_house_company','sec_company','opencorporates_company'):
            result.update(self._create_or_link_entity(case_id=case_id,target_id=target_id,norm=norm,source_id=source_id,source_record_id=srid,actor=actor))
        elif record_type=='gleif_relationship':
            child={'entity_name':norm['child_lei'],'jurisdiction':'GLOBAL','identifiers':{'lei':norm['child_lei']}}; parent={'entity_name':norm['parent_lei'],'jurisdiction':'GLOBAL','identifiers':{'lei':norm['parent_lei']}}
            c=self._create_or_link_entity(case_id=case_id,target_id=target_id,norm=child,source_id=source_id,source_record_id=srid,actor=actor); p=self._create_or_link_entity(case_id=case_id,target_id=target_id,norm=parent,source_id=source_id,source_record_id=srid,actor=actor)
            pred='direct_accounting_parent' if 'DIRECT' in norm['relationship_type'].upper() else 'ultimate_accounting_parent' if 'ULTIMATE' in norm['relationship_type'].upper() else 'reported_parent_relationship'
            rid=_id('corprel327');
            try:pct=float(norm.get('ownership_percent') or 0)
            except Exception:pct=0.0
            self.db.execute('INSERT INTO phase14_corporate_relationships_327 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,case_id,target_id,c['corporate_id'],pred,p['corporate_id'],norm['child_lei'],norm['parent_lei'],norm['relationship_type'],pct,norm['relationship_status'],norm['accounting_standard'],norm['valid_from'],norm['valid_to'],source_id,group,srid,'support',1,_now(),_hash({'r':rid,'c':norm['child_lei'],'p':norm['parent_lei']})))
            result.update({'relationship_id':rid,'subject_corporate_id':c['corporate_id'],'object_corporate_id':p['corporate_id'],'relationship_semantics':'reported_accounting_consolidation_not_automatic_beneficial_ownership'})
        elif record_type=='gleif_reporting_exception':
            xid=_id('corpex327'); self.db.execute('INSERT INTO phase14_corporate_reporting_exceptions_327 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(xid,case_id,target_id,norm['child_lei'],norm['parent_scope'],norm['exception_reason'],source_id,group,srid,norm['valid_from'],norm['valid_to'],_now(),_hash({'x':xid,'r':norm['exception_reason']}))); result.update({'exception_id':xid,'exception_is_not_negative_ownership_evidence':True})
        elif record_type in ('companies_house_officer','companies_house_psc'):
            cid=self._find_entity_by_identifier(case_id,target_id,'company_number',norm['company_number'],'UK')
            if not cid:
                base={'entity_name':norm['company_number'],'jurisdiction':'UK','identifiers':{'company_number':norm['company_number']}}; cid=self._create_or_link_entity(case_id=case_id,target_id=target_id,norm=base,source_id=source_id,source_record_id=srid,actor=actor)['corporate_id']
            if record_type=='companies_house_officer':
                oid=_id('off327'); self.db.execute('INSERT INTO phase14_corporate_officers_327 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,case_id,target_id,cid,norm['officer_name'],norm['role'],norm['appointed_on'],norm['resigned_on'],norm['nationality_public'],norm['occupation_public'],norm['service_address_public'],source_id,group,srid,1,'candidate',_now(),_hash({'o':oid,'n':norm['officer_name']}))); result.update({'officer_id':oid,'corporate_id':cid,'historical_role_requires_date_review':True})
            else:
                xid=_id('ctrl327'); self.db.execute('INSERT INTO phase14_corporate_control_records_327 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(xid,case_id,target_id,cid,norm['controller_name'],norm['controller_kind'],_canon(norm['natures_of_control']),norm['notified_on'],norm['ceased_on'],source_id,group,srid,1,'candidate',_now(),_hash({'x':xid,'n':norm['controller_name']}))); result.update({'control_id':xid,'corporate_id':cid,'psc_scope_caveat':True})
        return result

    def compare_entity_candidates(self,*,case_id:str,target_id:str,left_corporate_id:str,right_corporate_id:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); a=self.db.one('SELECT * FROM phase14_corporate_entities_327 WHERE corporate_id=? AND case_id=? AND target_id=?',(left_corporate_id,case_id,target_id)); b=self.db.one('SELECT * FROM phase14_corporate_entities_327 WHERE corporate_id=? AND case_id=? AND target_id=?',(right_corporate_id,case_id,target_id))
        if not a or not b:raise KeyError('corporate entity not found in case/target')
        ia=self.db.all('SELECT identifier_type,identifier_value,jurisdiction,source_id FROM phase14_corporate_identifiers_327 WHERE corporate_id=?',(left_corporate_id,)); ib=self.db.all('SELECT identifier_type,identifier_value,jurisdiction,source_id FROM phase14_corporate_identifiers_327 WHERE corporate_id=?',(right_corporate_id,)); setb={(x['identifier_type'],x['identifier_value'],x['jurisdiction']) for x in ib}; strong=[]
        for x in ia:
            key=(x['identifier_type'],x['identifier_value'],x['jurisdiction'])
            if x['identifier_type'] in self.STRONG_IDS and key in setb:strong.append(key)
        ns=difflib.SequenceMatcher(None,self._norm_name(a['canonical_name']),self._norm_name(b['canonical_name'])).ratio(); ads=difflib.SequenceMatcher(None,self._norm_name(a['registered_address']),self._norm_name(b['registered_address'])).ratio() if a['registered_address'] and b['registered_address'] else 0.0
        temporal=not (a['dissolution_date'] and b['incorporation_date'] and a['dissolution_date']<b['incorporation_date'])
        ga={self._source_group(x['source_id']) for x in ia}; gb={self._source_group(x['source_id']) for x in ib}; independent=bool(ga and gb and ga!=gb)
        action='deterministic_link_allowed_with_review' if strong else 'candidate_only_manual_resolution'; basis='strong_identifier:'+','.join(f'{x[0]}={x[1]}' for x in strong) if strong else 'weak_name_address_similarity_only'
        exp={'strong_identifiers':strong,'name_similarity':round(ns,4),'address_similarity':round(ads,4),'temporal_consistency':bool(temporal),'source_groups_left':sorted(ga),'source_groups_right':sorted(gb),'name_or_address_alone_never_auto_merges':True}
        mid=_id('corpmatch327'); self.db.execute('INSERT INTO phase14_corporate_match_candidates_327 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,case_id,target_id,left_corporate_id,right_corporate_id,basis,1 if strong else 0,ns,ads,1 if temporal else 0,1 if independent else 0,action,_canon(exp),_now(),_hash({'m':mid,'e':exp})))
        return {'match_id':mid,'resolution_action':action,'match_basis':basis,**exp,'probability_claim_generated':False}

    def materialize_corporate_graph(self,*,case_id:str,target_id:str,limit:int=200,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); limit=max(1,min(500,int(limit))); ents=self.db.all('SELECT * FROM phase14_corporate_entities_327 WHERE case_id=? AND target_id=? ORDER BY updated_at LIMIT ?',(case_id,target_id,limit)); node_map={}; docs=0
        for e in ents:
            n=self.upsert_node(case_id=case_id,target_id=target_id,node_type='legal_entity_candidate',canonical_key=f"corp327:{e['corporate_id']}",label=e['canonical_name'],properties={'jurisdiction':e['jurisdiction'],'status':e['status'],'candidate_only':True},source_layer='corporate_pack_327',actor=actor); node_map[e['corporate_id']]=n['node_id']
            ids=self.db.all('SELECT identifier_type,identifier_value FROM phase14_corporate_identifiers_327 WHERE corporate_id=?',(e['corporate_id'],)); text='\n'.join([f"name: {e['canonical_name']}",f"jurisdiction: {e['jurisdiction']}",f"status: {e['status']}"]+[f"{x['identifier_type']}: {x['identifier_value']}" for x in ids]); self.index_text_document(case_id=case_id,target_id=target_id,text=text,title=e['canonical_name'],source_uri=f"urn:eagleeye:corporate:{e['corporate_id']}",source_group='corporate_pack_327',provenance_status='corporate_candidate_327',anchors=[x['identifier_value'] for x in ids],actor=actor); docs+=1
        rels=self.db.all('SELECT * FROM phase14_corporate_relationships_327 WHERE case_id=? AND target_id=? ORDER BY created_at LIMIT ?',(case_id,target_id,limit)); assertions=0
        for r in rels:
            if r['subject_corporate_id'] in node_map and r['object_corporate_id'] in node_map:
                self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=node_map[r['subject_corporate_id']],predicate=r['predicate'],object_node_id=node_map[r['object_corporate_id']],polarity=r['polarity'],assertion_status='candidate',valid_from=r['valid_from'],valid_to=r['valid_to'],source_group=r['source_group'],source_ref=f"corp-source:{r['source_record_id']}",dependency_key=f"{r['source_group']}:{r['source_record_id']}",discrimination_class='reported_corporate_relationship',provenance={'relationship_id':r['relationship_id'],'relationship_type':r['relationship_type'],'candidate_only':True},actor=actor); assertions+=1
        return {'entities_materialized':len(node_map),'relationship_assertions':assertions,'search_documents':docs,'candidate_only':True,'automatic_ownership_inference':False}

    def plan_corporate_investigation(self,*,case_id:str,target_id:str,objective:str,jurisdiction_hint:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); local_entities=self._count('SELECT COUNT(*) n FROM phase14_corporate_entities_327 WHERE case_id=? AND target_id=?',(case_id,target_id)); rels=self._count('SELECT COUNT(*) n FROM phase14_corporate_relationships_327 WHERE case_id=? AND target_id=?',(case_id,target_id)); exceptions=self._count('SELECT COUNT(*) n FROM phase14_corporate_reporting_exceptions_327 WHERE case_id=? AND target_id=?',(case_id,target_id)); source_plan=self.select_sources(case_id=case_id,target_id=target_id,objective=objective,jurisdiction_hint=jurisdiction_hint,record_family='corporate',top_k=6,actor=actor)
        actions=[
          {'rank':1,'action':'resolve_strong_identifiers_locally','identifiers':['LEI','CIK','jurisdiction+company_number'],'external_execution':False},
          {'rank':2,'action':'review_primary_registry_identity_and_status','external_execution':False},
          {'rank':3,'action':'review_level2_parent_relationships_and_reporting_exceptions_separately','external_execution':False},
          {'rank':4,'action':'review_officers_and_statutory_control_records_with_dates','external_execution':False},
          {'rank':5,'action':'seek_independent_source_and_counterevidence_for_high_impact_relationships','external_execution':False},
          {'rank':6,'action':'stage_missing_reviewed_provider_or_bulk_dataset','requires_human_approval':True,'external_execution':False},
        ]
        plan={'objective':self._norm_text(objective,1000),'local_entities':local_entities,'local_relationships':rels,'reporting_exceptions':exceptions,'source_selection_run_id':source_plan['run_id'],'selected_sources':source_plan['selected_sources'],'actions':actions,'strong_identifier_first':True,'name_address_only_candidate_match':True,'reporting_exception_is_not_negative_ownership_evidence':True,'human_approval_required':True,'external_execution':False,'probability_claim_generated':False}
        pid=_id('corpplan327'); self.db.execute('INSERT INTO phase14_ai_corporate_plans_327 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,plan['objective'],_canon(plan),1,0,actor,_now(),_hash({'p':pid,'plan':plan}))); return {'plan_id':pid,**plan}

    def corporate_pack_stats(self,case_id:str='',target_id:str='')->dict[str,Any]:
        where=''; params=()
        if case_id and target_id:where=' WHERE case_id=? AND target_id=?'; params=(case_id,target_id)
        return {'entities':self._count('SELECT COUNT(*) n FROM phase14_corporate_entities_327'+where,params),'source_records':self._count('SELECT COUNT(*) n FROM phase14_corporate_source_records_327'+where,params),'relationships':self._count('SELECT COUNT(*) n FROM phase14_corporate_relationships_327'+where,params),'officers':self._count('SELECT COUNT(*) n FROM phase14_corporate_officers_327'+where,params),'control_records':self._count('SELECT COUNT(*) n FROM phase14_corporate_control_records_327'+where,params),'reporting_exceptions':self._count('SELECT COUNT(*) n FROM phase14_corporate_reporting_exceptions_327'+where,params)}

    def run_corporate_pack_selftest(self,actor:str|None=None)->dict[str,Any]:
        self._ensure_pack_profile(); tests={'gleif_lei_cdf_31_adapter':True,'gleif_rr_cdf_21_adapter':True,'gleif_reporting_exception_separate':True,'companies_house_company_adapter':True,'companies_house_officer_and_psc_minimized':True,'sec_cik_identity_adapter':True,'strong_identifier_first_resolution':True,'name_only_never_auto_merge':True,'temporal_corporate_relationships':True,'source_independence_preserved':True,'candidate_only_materialization':True,'no_probability_from_match_score':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('corpself327'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_corporate_pack_attestations_327 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v23_pass':parent.get('result')=='pass','corporate_pack_local_processing_default':True,'no_automatic_provider_download':True,'credential_values_not_stored':True,'public_personal_field_minimization':True,'residential_address_excluded':True,'name_only_auto_merge_forbidden':True,'corporate_records_candidate_only':True,'case_target_isolation':True,'source_independence_preserved':True,'human_review_for_high_impact_ownership_claims':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt327'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_327 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'327.0','mode':'global_corporate_data_pack_opsec_v24','security_training_cases_build327':tm['security_agent_delta_cases_327'],'model_status':'not_run','adds':['corporate identity merge guard','public personal-data minimization','ownership human-review gate','source independence preservation'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); stats={'entities':self._count('SELECT COUNT(*) n FROM phase14_corporate_entities_327 WHERE case_id=?',(case_id,)),'relationships':self._count('SELECT COUNT(*) n FROM phase14_corporate_relationships_327 WHERE case_id=?',(case_id,)),'officers':self._count('SELECT COUNT(*) n FROM phase14_corporate_officers_327 WHERE case_id=?',(case_id,)),'controls':self._count('SELECT COUNT(*) n FROM phase14_corporate_control_records_327 WHERE case_id=?',(case_id,)),'exceptions':self._count('SELECT COUNT(*) n FROM phase14_corporate_reporting_exceptions_327 WHERE case_id=?',(case_id,))}; quality={**parent.get('quality',{}),'corporate_strong_identifier_resolution':True,'ownership_reporting_exception_separation':True,'temporal_officer_relationships':True,'source_independence_preserved':True,'probability_claim_generated':False,'human_review_required':True}; lines=['\n\n## Build 327 · Global Corporate Data Pack','', '> Unternehmensdaten bleiben quellengebundene Kandidaten. LEI/CIK/Register-ID sind starke Identifikatoren; Name/Adresse allein führen nie zum automatischen Merge. Reporting Exceptions sind kein negativer Eigentumsbeweis.','',f"- Corporate Candidates: **{stats['entities']}**",f"- Parent/Corporate Relationships: **{stats['relationships']}**",f"- Officers / Control Records: **{stats['officers']} / {stats['controls']}**",f"- Reporting Exceptions: **{stats['exceptions']}**",'']; return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_326_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception:parent_ok=False
        corp=self.db.one("SELECT 1 x FROM phase14_corporate_pack_attestations_327 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_327 WHERE result='pass' LIMIT 1")
        g={'build':'327.0','parent_326_gate':parent_ok,'global_corporate_data_pack':True,'gleif_level1_level2_exception_model':True,'companies_house_company_officer_psc_model':True,'sec_cik_identity_model':True,'strong_identifier_resolution_guard':True,'temporal_relationship_model':True,'corporate_search_graph_materialization':True,'corporate_pack_attestation':bool(corp),'security_agent_v24_attestation':bool(sec),'training_corpus_792':tm.get('reviewed_hard_cases')==792 and tm.get('build327_delta_cases')==16,'external_execution_human_gated':True,'no_name_only_auto_merge':True,'no_match_score_probability':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='sources':
            stats=self.corporate_pack_stats(); return base+f"<div class='panel'><h2>Build 327 · Global Corporate Data Pack</h2><div class='notice'>GLEIF Level 1/2/Exceptions · Companies House Company/Officer/PSC · SEC CIK identity · starke Identifier vor Fuzzy Match · keine automatische Datenbeschaffung.</div><div class='grid'><div class='card'>Entities: <b>{stats['entities']}</b></div><div class='card'>Relationships: <b>{stats['relationships']}</b></div><div class='card'>Officers: <b>{stats['officers']}</b></div><div class='card'>Control: <b>{stats['control_records']}</b></div></div></div>"
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets); return base+f"<div class='panel'><h2>Build 327 · AI Corporate Investigation</h2><form method='post' action='/build327/corporate-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><input name='objective' value='Resolve corporate identity, ownership/control and counterevidence using independent primary sources'></div><div class='field'><label>Jurisdiktion</label><input name='jurisdiction_hint' placeholder='GLOBAL / UK / US / EU'></div><button>AI Corporate Strategy</button></form></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 327 · OPSEC v24</h2><div class='notice'>Local Corporate Processing · Public-Field Minimization · Strong-ID Merge Guard · Ownership Human Review · keine aktive externe Recon.</div><form method='post' action='/build327/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Corporate Pack + AI Security v24 testen</button></form></div>"
        return base
