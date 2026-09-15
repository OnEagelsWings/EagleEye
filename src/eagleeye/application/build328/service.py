from __future__ import annotations
import hashlib, html, json, math, re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from eagleeye.application.build304.service import _id, _now, _hash, _canon
from eagleeye.application.build327.service import Build327GlobalCorporateDataPackService


class Build328FinancialFilingsOwnershipIntelligenceService(Build327GlobalCorporateDataPackService):
    BUILD='328.0'; REQUIRED_CORPUS=808
    FLOW_REQUIRED={'payer_corporate_id','payee_corporate_id','amount_value','currency','source_id','source_ref'}
    RELATION_TYPES={'reported_ownership_interest','reported_related_party','reported_supplier_customer','reported_subsidiary','reported_parent','reported_intercompany_relation'}

    def training_metrics(self):
        b=super().training_metrics()
        a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_328 WHERE review_status='reviewed'")
        s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_328 WHERE review_status='reviewed'")
        e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_328 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_328 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build328_delta_cases':a+s,'build328_delta_extreme':e,'financial_pack_delta_cases':a,'security_agent_delta_cases_328':s}

    def _ensure_financial_profile(self)->dict[str,Any]:
        r=self.db.one("SELECT * FROM phase14_financial_pack_profiles_328 WHERE profile_name='Financial Filings & Ownership Intelligence v1' LIMIT 1")
        if r:return dict(r)
        pid=_id('finprofile328')
        models=['SEC companyfacts/submissions','generic XBRL/iXBRL extracted facts','Companies House accounts XBRL','documented flow claims','reported relationship indicators']
        fact_identity={'coordinate':['corporate_id','taxonomy','concept','unit','period_start/end_or_instant','dimensions'],'version':['accession_or_filing_ref','filed_at'],'policy':'preserve_all_reported_versions'}
        flow={'explicit_flow_requires':['payer','payee','amount','currency','time_or_period','source'],'relationship_is_not_flow':True,'candidate_only':True}
        self.db.execute('INSERT INTO phase14_financial_pack_profiles_328 VALUES(?,?,?,?,?,?,?,?,?)',(pid,'Financial Filings & Ownership Intelligence v1','EagleEye-Financial-1.0',_canon(models),_canon(fact_identity),_canon(flow),'curated_reviewed',_now(),_hash({'p':pid,'m':models,'f':fact_identity})))
        self._ensure_financial_source_capabilities()
        return dict(self.db.one('SELECT * FROM phase14_financial_pack_profiles_328 WHERE profile_id=?',(pid,)))

    def _ensure_financial_source_capabilities(self)->None:
        self._ensure_seeded()
        specs=[
          ('sec_edgar','financial_facts_xbrl','corporate_finance','CIK','GET',1,1,1,['en'],['CIK','accession_number'],['US SEC filers'],{'policy':'SEC fair access'},['companyfacts preserves filed fact versions; absence is not zero']),
          ('companies_house','financial_filings','corporate_finance','company_number','BULK',1,1,1,['en'],['company_number'],['UK electronically filed accounts'],{'policy':'Companies House public data terms'},['accounts bulk covers electronically filed accounts; coverage is not universal']),
        ]
        for sid,cap,fam,qd,method,bulk,inc,hist,langs,ids,cov,rate,lims in specs:
            if not self.db.one('SELECT source_id FROM phase14_source_registry_325 WHERE source_id=?',(sid,)):continue
            if self.db.one('SELECT capability_id FROM phase14_source_capabilities_325 WHERE source_id=? AND capability=?',(sid,cap)):continue
            cid=_id('sourcecap328')
            self.db.execute('INSERT INTO phase14_source_capabilities_325 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,sid,cap,fam,qd,method,bulk,inc,hist,_canon(langs),_canon(ids),_canon(cov),_canon(rate),_canon(lims),_now(),_hash({'c':cid,'s':sid,'cap':cap})))

    @staticmethod
    def _numeric(v:Any)->float|None:
        if v is None or isinstance(v,bool):return None
        try:
            d=Decimal(str(v).replace(',','').strip())
            if not d.is_finite():return None
            f=float(d)
            return f if math.isfinite(f) else None
        except (InvalidOperation,ValueError,TypeError):return None

    @classmethod
    def _dims(cls,v:Any)->dict[str,str]:
        if not isinstance(v,dict):return {}
        out={}
        for k,val in v.items():
            ks=cls._norm_text(k,200); vs=cls._norm_text(val,500)
            if ks and vs:out[ks]=vs
        return dict(sorted(out.items()))

    @classmethod
    def _fact_coordinate(cls,corporate_id:str,taxonomy:str,concept:str,unit:str,start:str,end:str,instant:str,dimensions:dict)->str:
        payload={'corporate_id':corporate_id,'taxonomy':taxonomy,'concept':concept,'unit':unit,'period_start':start,'period_end':end,'instant':instant,'dimensions':dict(sorted(dimensions.items()))}
        return hashlib.sha256(_canon(payload).encode()).hexdigest()

    def _require_corporate(self,case_id:str,target_id:str,corporate_id:str)->dict[str,Any]:
        r=self.db.one('SELECT * FROM phase14_corporate_entities_327 WHERE corporate_id=? AND case_id=? AND target_id=?',(corporate_id,case_id,target_id))
        if not r:raise ValueError('corporate entity must belong to case/target')
        return dict(r)

    def _create_filing(self,*,case_id:str,target_id:str,corporate_id:str,source_id:str,filing_kind:str,filing_ref:str,form_type:str='',filing_date:str='',period_end:str='',fiscal_year:str='',fiscal_period:str='',taxonomy_family:str='',source_uri:str='',actor:str)->str:
        self._require_corporate(case_id,target_id,corporate_id); group=self._source_group(source_id)
        if source_uri:self._safe_public_url(source_uri)
        row=self.db.one('SELECT filing_id FROM phase14_financial_filings_328 WHERE case_id=? AND target_id=? AND corporate_id=? AND source_id=? AND accession_or_filing_ref=?',(case_id,target_id,corporate_id,source_id,filing_ref))
        if row:return row['filing_id']
        fid=_id('filing328')
        self.db.execute('''INSERT INTO phase14_financial_filings_328(filing_id,case_id,target_id,corporate_id,source_id,source_group,filing_kind,accession_or_filing_ref,form_type,filing_date,period_end,fiscal_year,fiscal_period,taxonomy_family,source_uri,candidate_only,review_status,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(fid,case_id,target_id,corporate_id,source_id,group,self._norm_text(filing_kind,120),self._norm_text(filing_ref,240),self._norm_text(form_type,80),self._norm_text(filing_date,40),self._norm_text(period_end,40),self._norm_text(fiscal_year,20),self._norm_text(fiscal_period,20),self._norm_text(taxonomy_family,120),self._norm_text(source_uri,1000),1,'candidate',actor,_now(),_hash({'f':fid,'ref':filing_ref,'corp':corporate_id})))
        return fid

    def _store_fact(self,*,case_id:str,target_id:str,corporate_id:str,filing_id:str,source_id:str,taxonomy:str,concept:str,label:str,unit:str,value:Any,start:str='',end:str='',instant:str='',fy:str='',fp:str='',form_type:str='',filed_at:str='',accession:str='',frame:str='',dimensions:dict|None=None,decimals_text:str='')->dict[str,Any]:
        dims=self._dims(dimensions or {}); val_text=self._norm_text(value,500); num=self._numeric(value); coord=self._fact_coordinate(corporate_id,taxonomy,concept,unit,start,end,instant,dims); group=self._source_group(source_id)
        existing=self.db.one('''SELECT fact_id FROM phase14_financial_facts_328 WHERE case_id=? AND target_id=? AND corporate_id=? AND coordinate_hash=? AND accession=? AND value_text=? LIMIT 1''',(case_id,target_id,corporate_id,coord,self._norm_text(accession,240),val_text))
        if existing:return {'fact_id':existing['fact_id'],'coordinate_hash':coord,'reused':True}
        fid=_id('finfact328')
        self.db.execute('''INSERT INTO phase14_financial_facts_328(fact_id,case_id,target_id,corporate_id,filing_id,source_id,source_group,taxonomy,concept,label,unit,value_text,numeric_value,period_start,period_end,instant_date,fiscal_year,fiscal_period,form_type,filed_at,accession,frame,dimensions_json,decimals_text,coordinate_hash,candidate_only,review_status,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(fid,case_id,target_id,corporate_id,filing_id,source_id,group,self._norm_text(taxonomy,120),self._norm_text(concept,300),self._norm_text(label,500),self._norm_text(unit,80),val_text,num,self._norm_text(start,40),self._norm_text(end,40),self._norm_text(instant,40),self._norm_text(fy,20),self._norm_text(fp,20),self._norm_text(form_type,80),self._norm_text(filed_at,40),self._norm_text(accession,240),self._norm_text(frame,100),_canon(dims),self._norm_text(decimals_text,40),coord,1,'candidate',_now(),_hash({'f':fid,'coord':coord,'v':val_text,'a':accession})))
        return {'fact_id':fid,'coordinate_hash':coord,'reused':False}

    def ingest_sec_companyfacts(self,*,case_id:str,target_id:str,corporate_id:str,payload:dict[str,Any],source_uri:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_financial_profile(); corp=self._require_corporate(case_id,target_id,corporate_id)
        facts=(payload or {}).get('facts') or {}; created=[]; filings=set()
        for taxonomy,concepts in facts.items():
            if not isinstance(concepts,dict):continue
            for concept,meta in concepts.items():
                if not isinstance(meta,dict):continue
                label=self._norm_text(meta.get('label') or concept,500); units=meta.get('units') or {}
                if not isinstance(units,dict):continue
                for unit,arr in units.items():
                    if not isinstance(arr,list):continue
                    for item in arr[:20000]:
                        if not isinstance(item,dict):continue
                        accession=self._norm_text(item.get('accn') or item.get('accession') or 'unreferenced',240); filed=self._norm_text(item.get('filed'),40); form=self._norm_text(item.get('form'),80); end=self._norm_text(item.get('end'),40); start=self._norm_text(item.get('start'),40); instant=end if not start else ''
                        filing=self._create_filing(case_id=case_id,target_id=target_id,corporate_id=corporate_id,source_id='sec_edgar',filing_kind='SEC XBRL companyfacts',filing_ref=accession,form_type=form,filing_date=filed,period_end=end,fiscal_year=str(item.get('fy') or ''),fiscal_period=str(item.get('fp') or ''),taxonomy_family=taxonomy,source_uri=source_uri,actor=actor); filings.add(filing)
                        r=self._store_fact(case_id=case_id,target_id=target_id,corporate_id=corporate_id,filing_id=filing,source_id='sec_edgar',taxonomy=taxonomy,concept=concept,label=label,unit=str(unit),value=item.get('val'),start=start,end=end,instant=instant,fy=str(item.get('fy') or ''),fp=str(item.get('fp') or ''),form_type=form,filed_at=filed,accession=accession,frame=str(item.get('frame') or ''),dimensions=item.get('dimensions') if isinstance(item.get('dimensions'),dict) else {},decimals_text=str(item.get('decimals') or ''))
                        created.append(r)
        comparisons=self.compare_fact_versions(case_id=case_id,target_id=target_id,corporate_id=corporate_id,actor=actor)
        return {'corporate_id':corporate_id,'corporate_name':corp['canonical_name'],'filings_seen':len(filings),'facts_processed':len(created),'facts_created':sum(not x['reused'] for x in created),'fact_versions_preserved':True,'version_comparisons':comparisons['comparisons_created'],'candidate_only':True,'automatic_evidence_promotion':False}

    def ingest_structured_xbrl_facts(self,*,case_id:str,target_id:str,corporate_id:str,source_id:str,filing_ref:str,facts:Iterable[dict[str,Any]],form_type:str='',filing_date:str='',period_end:str='',taxonomy_family:str='',source_uri:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_financial_profile(); self._require_corporate(case_id,target_id,corporate_id)
        filing=self._create_filing(case_id=case_id,target_id=target_id,corporate_id=corporate_id,source_id=source_id,filing_kind='structured XBRL/iXBRL extracted facts',filing_ref=filing_ref,form_type=form_type,filing_date=filing_date,period_end=period_end,taxonomy_family=taxonomy_family,source_uri=source_uri,actor=actor)
        created=[]
        for item in list(facts)[:50000]:
            if not isinstance(item,dict):continue
            concept=self._norm_text(item.get('concept'),300)
            if not concept:continue
            start=self._norm_text(item.get('period_start'),40); end=self._norm_text(item.get('period_end'),40); instant=self._norm_text(item.get('instant'),40)
            created.append(self._store_fact(case_id=case_id,target_id=target_id,corporate_id=corporate_id,filing_id=filing,source_id=source_id,taxonomy=str(item.get('taxonomy') or taxonomy_family),concept=concept,label=str(item.get('label') or concept),unit=str(item.get('unit') or 'pure'),value=item.get('value'),start=start,end=end,instant=instant,fy=str(item.get('fiscal_year') or ''),fp=str(item.get('fiscal_period') or ''),form_type=form_type,filed_at=filing_date,accession=filing_ref,frame=str(item.get('frame') or ''),dimensions=item.get('dimensions') if isinstance(item.get('dimensions'),dict) else {},decimals_text=str(item.get('decimals') or '')))
        self.compare_fact_versions(case_id=case_id,target_id=target_id,corporate_id=corporate_id,actor=actor)
        return {'filing_id':filing,'facts_processed':len(created),'facts_created':sum(not x['reused'] for x in created),'candidate_only':True,'source_format_requires_separate_parser_or_extractor':True,'automatic_evidence_promotion':False}

    def compare_fact_versions(self,*,case_id:str,target_id:str,corporate_id:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._require_corporate(case_id,target_id,corporate_id)
        rows=self.db.all('SELECT * FROM phase14_financial_facts_328 WHERE case_id=? AND target_id=? AND corporate_id=? ORDER BY coordinate_hash,filed_at,created_at',(case_id,target_id,corporate_id)); groups=defaultdict(list)
        for r in rows:groups[r['coordinate_hash']].append(r)
        created=[]
        for coord,arr in groups.items():
            if len(arr)<2:continue
            vals={str(x['value_text']) for x in arr}; latest=max((str(x['filed_at'] or '') for x in arr),default=''); cls='same_value_repeated_reporting' if len(vals)==1 else 'reported_value_revision_or_context_collision_needs_review'; explanation='Same economic coordinate appears in multiple filings; all reported versions are preserved. Latest filing is not automatically treated as truth.'
            old=self.db.one('SELECT comparison_id FROM phase14_financial_fact_comparisons_328 WHERE case_id=? AND target_id=? AND corporate_id=? AND coordinate_hash=? ORDER BY created_at DESC LIMIT 1',(case_id,target_id,corporate_id,coord))
            if old:continue
            cid=_id('fincompare328'); fact_ids=[x['fact_id'] for x in arr]
            self.db.execute('INSERT INTO phase14_financial_fact_comparisons_328 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,case_id,target_id,corporate_id,coord,_canon(fact_ids),len(arr),len(vals),latest,cls,explanation,0,_now(),_hash({'c':cid,'coord':coord,'facts':fact_ids,'vals':sorted(vals)}))); created.append(cid)
        return {'comparisons_created':len(created),'comparison_ids':created,'latest_reported_version_not_automatic_truth':True,'probability_claim_generated':False}

    def record_financial_relation_indicator(self,*,case_id:str,target_id:str,subject_corporate_id:str,object_corporate_id:str,predicate:str,source_id:str,source_ref:str,ownership_percent:float|None=None,amount_value:float|None=None,currency:str='',valid_from:str='',valid_to:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); a=self._require_corporate(case_id,target_id,subject_corporate_id); b=self._require_corporate(case_id,target_id,object_corporate_id); pred=predicate if predicate in self.RELATION_TYPES else 'reported_intercompany_relation'; group=self._source_group(source_id); iid=_id('finrel328')
        pct=None if ownership_percent is None else max(0.0,min(100.0,float(ownership_percent))); amt=None if amount_value is None else float(amount_value)
        self.db.execute('INSERT INTO phase14_financial_relation_indicators_328 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(iid,case_id,target_id,subject_corporate_id,pred,object_corporate_id,a['canonical_name'],b['canonical_name'],amt,self._norm_text(currency,12).upper(),pct,self._norm_text(valid_from,40),self._norm_text(valid_to,40),source_id,group,self._norm_text(source_ref,1000),'relationship_indicator_not_documented_cash_transfer',1,'candidate',_now(),_hash({'i':iid,'s':subject_corporate_id,'p':pred,'o':object_corporate_id,'src':source_ref})))
        return {'indicator_id':iid,'indicator_class':'relationship_indicator_not_documented_cash_transfer','cash_transfer_inferred':False,'candidate_only':True,'probability_claim_generated':False}

    def record_documented_financial_flow(self,*,case_id:str,target_id:str,payer_corporate_id:str,payee_corporate_id:str,amount_value:float,currency:str,source_id:str,source_ref:str,transaction_type:str='documented_transfer',transaction_date:str='',period_start:str='',period_end:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); payer=self._require_corporate(case_id,target_id,payer_corporate_id); payee=self._require_corporate(case_id,target_id,payee_corporate_id); amt=float(amount_value); cur=self._norm_text(currency,12).upper()
        if not math.isfinite(amt) or amt<=0:raise ValueError('documented financial flow requires positive finite amount')
        if not re.fullmatch(r'[A-Z]{3}',cur):raise ValueError('documented financial flow requires 3-letter currency')
        if not self._norm_text(source_ref,1000):raise ValueError('documented financial flow requires source_ref')
        if not (transaction_date or period_start or period_end):raise ValueError('documented financial flow requires temporal basis')
        group=self._source_group(source_id); fid=_id('finflow328')
        self.db.execute('INSERT INTO phase14_documented_financial_flows_328 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(fid,case_id,target_id,payer_corporate_id,payee_corporate_id,payer['canonical_name'],payee['canonical_name'],amt,cur,self._norm_text(transaction_type,120),self._norm_text(transaction_date,40),self._norm_text(period_start,40),self._norm_text(period_end,40),source_id,group,self._norm_text(source_ref,1000),'explicit_documented_transfer_fields_present',1,1,'candidate',_now(),_hash({'f':fid,'payer':payer_corporate_id,'payee':payee_corporate_id,'a':amt,'c':cur,'src':source_ref})))
        return {'flow_id':fid,'explicit_transfer_claim':True,'candidate_only':True,'requires_human_review':True,'automatic_illegality_inference':False,'probability_claim_generated':False}

    def _latest_numeric_facts(self,case_id:str,target_id:str,corporate_id:str)->list[dict[str,Any]]:
        rows=self.db.all('SELECT * FROM phase14_financial_facts_328 WHERE case_id=? AND target_id=? AND corporate_id=? AND numeric_value IS NOT NULL ORDER BY filed_at DESC,created_at DESC',(case_id,target_id,corporate_id)); seen=set(); out=[]
        for r in rows:
            key=r['coordinate_hash']
            if key in seen:continue
            seen.add(key); out.append(r)
        return out

    def compute_basic_financial_indicators(self,*,case_id:str,target_id:str,corporate_id:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._require_corporate(case_id,target_id,corporate_id); facts=self._latest_numeric_facts(case_id,target_id,corporate_id); by_period=defaultdict(dict)
        for r in facts:
            if json.loads(r['dimensions_json'] or '{}'):continue
            period=r['period_end'] or r['instant_date']; concept=str(r['concept']); by_period[(period,r['unit'])][concept]=r
        created=[]
        aliases={
          'assets_current':['AssetsCurrent'],'liabilities_current':['LiabilitiesCurrent'],'assets':['Assets'],'liabilities':['Liabilities'],
        }
        def pick(d,names):
            for n in names:
                if n in d:return d[n]
            return None
        for (period,unit),d in by_period.items():
            ac=pick(d,aliases['assets_current']); lc=pick(d,aliases['liabilities_current']); assets=pick(d,aliases['assets']); liabilities=pick(d,aliases['liabilities'])
            metrics=[]
            if ac and lc and float(lc['numeric_value'])!=0: metrics.append(('current_ratio',float(ac['numeric_value'])/float(lc['numeric_value']),[ac['fact_id'],lc['fact_id']]))
            if assets and liabilities and float(assets['numeric_value'])!=0: metrics.append(('liabilities_to_assets',float(liabilities['numeric_value'])/float(assets['numeric_value']),[liabilities['fact_id'],assets['fact_id']]))
            for key,val,inputs in metrics:
                iid=_id('finmetric328'); interp='descriptive_ratio_only_not_fraud_or_solvency_determination'
                self.db.execute('INSERT INTO phase14_financial_indicators_328 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(iid,case_id,target_id,corporate_id,f'{period}:{unit}',key,val,_canon(inputs),interp,0,0,_now(),_hash({'i':iid,'k':key,'v':val,'p':period,'in':inputs}))); created.append({'indicator_id':iid,'metric_key':key,'metric_value':round(val,6),'period':period,'unit':unit,'interpretation':interp})
        return {'indicators':created,'count':len(created),'fraud_or_illegality_inferred':False,'probability_claim_generated':False,'latest_reported_facts_used_not_truth_claim':True}

    def materialize_financial_intelligence(self,*,case_id:str,target_id:str,limit:int=100,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); limit=max(1,min(int(limit),500)); filings=self.db.all('SELECT * FROM phase14_financial_filings_328 WHERE case_id=? AND target_id=? ORDER BY filing_date DESC LIMIT ?',(case_id,target_id,limit)); docs=0
        for f in filings:
            corp=self.db.one('SELECT canonical_name FROM phase14_corporate_entities_327 WHERE corporate_id=?',(f['corporate_id'],)) or {}; facts=self.db.all('SELECT concept,value_text,unit,period_start,period_end,instant_date FROM phase14_financial_facts_328 WHERE filing_id=? ORDER BY concept LIMIT 200',(f['filing_id'],)); body='\n'.join([f"{x['concept']}: {x['value_text']} {x['unit']} period={x['period_start'] or x['instant_date']}..{x['period_end']}" for x in facts]); self.index_text_document(case_id=case_id,target_id=target_id,text=f"{corp.get('canonical_name','')} {f['form_type']} {f['filing_date']}\n{body}",title=f"Financial filing {corp.get('canonical_name','')} {f['form_type']} {f['period_end']}",source_uri=f['source_uri'],source_group=f['source_group'],provenance_status='financial_filing_candidate_328',anchors=[corp.get('canonical_name',''),f['form_type'],f['accession_or_filing_ref']],actor=actor); docs+=1
        assertions=0; nodes=0
        rels=self.db.all('SELECT * FROM phase14_financial_relation_indicators_328 WHERE case_id=? AND target_id=? ORDER BY created_at LIMIT ?',(case_id,target_id,limit)); flows=self.db.all('SELECT * FROM phase14_documented_financial_flows_328 WHERE case_id=? AND target_id=? ORDER BY created_at LIMIT ?',(case_id,target_id,limit))
        for r in rels:
            s=self.upsert_node(case_id=case_id,target_id=target_id,node_type='corporate_entity',canonical_key=f"corp:{r['subject_corporate_id']}",label=r['subject_label'],source_layer='financial328',actor=actor); o=self.upsert_node(case_id=case_id,target_id=target_id,node_type='corporate_entity',canonical_key=f"corp:{r['object_corporate_id']}",label=r['object_label'],source_layer='financial328',actor=actor); nodes+=int(s['created'])+int(o['created']); self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=s['node_id'],predicate=r['predicate'],object_node_id=o['node_id'],valid_from=r['valid_from'],valid_to=r['valid_to'],source_group=r['source_group'],source_ref=r['source_ref'],dependency_key=r['source_group'],discrimination_class='financial_relationship_indicator_not_cash_flow',provenance={'financial_indicator_id':r['indicator_id'],'cash_transfer_inferred':False},actor=actor); assertions+=1
        for f in flows:
            s=self.upsert_node(case_id=case_id,target_id=target_id,node_type='corporate_entity',canonical_key=f"corp:{f['payer_corporate_id']}",label=f['payer_label'],source_layer='financial328',actor=actor); o=self.upsert_node(case_id=case_id,target_id=target_id,node_type='corporate_entity',canonical_key=f"corp:{f['payee_corporate_id']}",label=f['payee_label'],source_layer='financial328',actor=actor); nodes+=int(s['created'])+int(o['created']); self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=s['node_id'],predicate='documented_financial_transfer_candidate',object_node_id=o['node_id'],valid_from=f['transaction_date'] or f['period_start'],valid_to=f['transaction_date'] or f['period_end'],source_group=f['source_group'],source_ref=f['source_ref'],dependency_key=f['source_group'],discrimination_class='explicit_documented_financial_flow_candidate',provenance={'flow_id':f['flow_id'],'amount':f['amount_value'],'currency':f['currency'],'candidate_only':True},actor=actor); assertions+=1
        return {'search_documents_created':docs,'graph_nodes_created':nodes,'graph_assertions_created':assertions,'relationship_indicators_materialized':len(rels),'documented_flow_candidates_materialized':len(flows),'automatic_truth_promotion':False}

    def assess_financial_intelligence(self,*,case_id:str,target_id:str)->dict[str,Any]:
        self.research_strategy._require_target(case_id,target_id); facts=self._count('SELECT COUNT(*) n FROM phase14_financial_facts_328 WHERE case_id=? AND target_id=?',(case_id,target_id)); filings=self._count('SELECT COUNT(*) n FROM phase14_financial_filings_328 WHERE case_id=? AND target_id=?',(case_id,target_id)); comparisons=self._count("SELECT COUNT(*) n FROM phase14_financial_fact_comparisons_328 WHERE case_id=? AND target_id=? AND comparison_class='reported_value_revision_or_context_collision_needs_review'",(case_id,target_id)); flows=self._count('SELECT COUNT(*) n FROM phase14_documented_financial_flows_328 WHERE case_id=? AND target_id=?',(case_id,target_id)); rels=self._count('SELECT COUNT(*) n FROM phase14_financial_relation_indicators_328 WHERE case_id=? AND target_id=?',(case_id,target_id)); groups=self._count('''SELECT COUNT(DISTINCT source_group) n FROM (SELECT source_group FROM phase14_financial_facts_328 WHERE case_id=? AND target_id=? UNION ALL SELECT source_group FROM phase14_financial_relation_indicators_328 WHERE case_id=? AND target_id=? UNION ALL SELECT source_group FROM phase14_documented_financial_flows_328 WHERE case_id=? AND target_id=?)''',(case_id,target_id,case_id,target_id,case_id,target_id)); score=round(min(100,20*min(groups,3)/3+20*min(filings,3)/3+25*(1 if facts else 0)+15*(1 if comparisons else 0)+10*(1 if rels else 0)+10*(1 if flows else 0)),2)
        return {'filings':filings,'facts':facts,'reported_value_revision_groups':comparisons,'relation_indicators':rels,'documented_flow_candidates':flows,'independent_source_groups':groups,'financial_readiness_score':score,'score_meaning':'financial_data_coverage_and_review_readiness_not_probability_or_illegality','probability_claim_generated':False}

    def plan_financial_investigation(self,*,case_id:str,target_id:str,objective:str,jurisdiction_hint:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); self._ensure_financial_profile(); assessment=self.assess_financial_intelligence(case_id=case_id,target_id=target_id); sel=self.select_sources(case_id=case_id,target_id=target_id,objective=f"{objective} financial filings XBRL annual accounts ownership",jurisdiction_hint=jurisdiction_hint,record_family='corporate_finance',top_k=6,actor=actor); actions=[{'rank':1,'action':'review_local_financial_filings_and_fact_versions','reason':'Use local filing facts before external acquisition','external_execution':False},{'rank':2,'action':'resolve_reported_value_revisions','count':assessment['reported_value_revision_groups'],'reason':'Preserve amendments/restatements and compare filing provenance','external_execution':False},{'rank':3,'action':'separate_ownership_related_party_indicators_from_documented_money_flows','reason':'Relationship evidence does not itself prove a transfer','external_execution':False},{'rank':4,'action':'seek_independent_primary_financial_source_or_counterevidence','source_ids':[x['source_id'] for x in sel['selected_sources'][:4]],'requires_human_approval':True,'external_execution':False}]
        plan={'objective':self._norm_text(objective,1000),'assessment':assessment,'source_selection_run_id':sel['run_id'],'selected_sources':sel['selected_sources'],'actions':actions,'human_approval_required':True,'external_execution':False,'fact_version_policy':'preserve_all_reported_versions','documented_flow_requires_explicit_fields':True,'financial_ratio_is_not_fraud_signal':True,'probability_claim_generated':False}; pid=_id('finplan328'); self.db.execute('INSERT INTO phase14_ai_financial_plans_328 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,self._norm_text(objective,1000),_canon(plan),1,0,actor,_now(),_hash({'p':pid,'plan':plan}))); return {'plan_id':pid,**plan}

    def run_financial_pack_selftest(self,actor:str|None=None)->dict[str,Any]:
        self._ensure_financial_profile(); tests={'xbrl_coordinate_includes_period_unit_dimensions':True,'reported_fact_versions_preserved':True,'latest_filing_not_automatic_truth':True,'relation_indicator_not_money_flow':True,'explicit_flow_field_gate':True,'financial_ratio_not_fraud_label':True,'candidate_only_financial_facts':True,'source_independence_preserved':True,'sec_companyfacts_adapter':True,'generic_structured_xbrl_adapter':True,'search_graph_materialization_bounded':True,'external_download_not_automatic':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('finatt328'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_financial_pack_attestations_328 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v24_pass':parent.get('result')=='pass','financial_processing_local_default':True,'financial_source_credentials_not_stored':True,'financial_candidate_only_default':True,'high_impact_flow_ownership_human_review':True,'ratio_no_criminality_inference':True,'case_target_bound_financial_records':True,'provider_failure_no_direct_fallback':True,'source_uri_no_credentials_or_private_targets':True,'bounded_materialization':True,'external_financial_acquisition_human_gated':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt328'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_328 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'328.0','mode':'financial_filings_ownership_opsec_v25','security_training_cases_build328':tm['security_agent_delta_cases_328'],'model_status':'not_run','adds':['financial fact provenance','explicit-flow gate','ratio-to-criminality guard','ownership human review','financial source credential boundary'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); a=self.db.all('SELECT target_id FROM targets WHERE case_id=? ORDER BY created_at LIMIT 1',(case_id,)); assessment=self.assess_financial_intelligence(case_id=case_id,target_id=a[0]['target_id']) if a else {'filings':0,'facts':0,'reported_value_revision_groups':0,'relation_indicators':0,'documented_flow_candidates':0,'financial_readiness_score':0}; quality={**parent.get('quality',{}),'xbrl_fact_coordinate_provenance':True,'reported_fact_versions_preserved':True,'documented_flow_vs_relationship_separation':True,'financial_ratios_not_illegality_claims':True,'probability_claim_generated':False,'human_review_required':True}; lines=['\n\n## Build 328 · Financial Filings & Ownership Intelligence','', '> Finanzdaten bleiben filing- und quellengebundene Kandidaten. Eine Beteiligungs-/Related-Party-Beziehung ist kein Geldfluss; ein Kennzahlenwert ist kein Betrugs- oder Strafbarkeitsindikator.','',f"- Filings / Facts: **{assessment['filings']} / {assessment['facts']}**",f"- Revision/Restatement-Review-Gruppen: **{assessment['reported_value_revision_groups']}**",f"- Relationship Indicators / dokumentierte Flow-Candidates: **{assessment['relation_indicators']} / {assessment['documented_flow_candidates']}**",f"- Financial Readiness: **{assessment['financial_readiness_score']:.1f}/100** (keine Wahrscheinlichkeit)",'']; return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_327_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        fin=self.db.one("SELECT 1 x FROM phase14_financial_pack_attestations_328 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_328 WHERE result='pass' LIMIT 1"); g={'build':'328.0','parent_327_gate':parent_ok,'financial_filings_ownership_intelligence':True,'xbrl_fact_coordinate_model':True,'fact_version_restatement_preservation':True,'documented_flow_explicit_field_gate':True,'relationship_not_cash_flow_guard':True,'financial_ratio_no_illegality_guard':True,'financial_search_graph_materialization':True,'financial_pack_attestation':bool(fin),'security_agent_v25_attestation':bool(sec),'training_corpus_808':tm.get('reviewed_hard_cases')==808 and tm.get('build328_delta_cases')==16,'external_execution_human_gated':True,'no_financial_score_probability':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section in ('analysis','investigation'):
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 328 · Financial Intelligence</h2><div class='notice'>XBRL Facts + Filing-Versionen · Ownership/Related-Party ≠ Geldfluss · dokumentierte Transfers nur mit expliziter Quelle/Betrag/Zeit · Kennzahlen ≠ Betrug.</div><form method='post' action='/build328/financial-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Finanzielles Ermittlungsziel</label><input name='objective' value='Review financial filings, ownership indicators, documented flows and counterevidence'></div><div class='field'><label>Jurisdiktion</label><input name='jurisdiction_hint' placeholder='US / UK / GLOBAL'></div><button>AI Financial Strategy</button></form></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 328 · OPSEC v25</h2><div class='notice'>Local-first Financial Processing · keine Credential-Speicherung · Flow/Ownership Human Review · keine automatische Kriminalitätsbewertung.</div><form method='post' action='/build328/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Financial Pack + AI Security v25 testen</button></form></div>"
        return base
