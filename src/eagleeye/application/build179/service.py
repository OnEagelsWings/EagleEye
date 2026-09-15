from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone, timedelta
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

def _canon(v: Any) -> str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v: Any) -> str: return hashlib.sha256(_canon(v).encode()).hexdigest()
def _clean(v: Any) -> Any:
    sensitive=('token','secret','password','authorization','cookie','session','api_key','private_key')
    if isinstance(v,Mapping): return {str(k):('[REDACTED]' if any(x in str(k).lower() for x in sensitive) else _clean(val)) for k,val in v.items()}
    if isinstance(v,list): return [_clean(x) for x in v]
    return v

class Build179AlertPatternEngineService:
    BUILD='179.0'
    RULE_TYPES={'new_alias','new_location','new_relationship','timeline_conflict','multi_source_confirmation','content_change','account_change','keyword_sequence'}
    SOURCE_PROFILES=[
      {'source_id':'eu_financial_sanctions_consolidated','title':'EU/UN/UK Consolidated Financial Sanctions dataset','jurisdiction':'EU','category':'sanctions','access_mode':'official_open_dataset','base_url':'https://data.europa.eu','docs_url':'https://data.europa.eu/data/datasets/financialsanctions','capabilities':['person_and_entity_designations','list_changes','identifiers'],'constraints':['screening_lead_only','false_positive_review','not_criminality_proof']},
      {'source_id':'un_sc_consolidated_sanctions','title':'UN Security Council Consolidated List','jurisdiction':'UN','category':'sanctions','access_mode':'official_xml_html_pdf','base_url':'https://main.un.org','docs_url':'https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list','capabilities':['individuals','entities','aliases','list_updates'],'constraints':['designation_context_only','identity_review','official_update_tracking']},
      {'source_id':'eu_safety_gate_alerts','title':'EU Safety Gate Alerts','jurisdiction':'EU','category':'product_safety','access_mode':'official_public_portal','base_url':'https://ec.europa.eu','docs_url':'https://ec.europa.eu/safety-gate-alerts/','capabilities':['dangerous_product_alerts','economic_operator_context','change_monitoring'],'constraints':['product_safety_context','not_person_culpability','terms_review']},
      {'source_id':'eu_rasff_window','title':'EU RASFF Window','jurisdiction':'EU','category':'food_feed_safety','access_mode':'official_public_portal','base_url':'https://webgate.ec.europa.eu','docs_url':'https://food.ec.europa.eu/food-safety/rasff_en','capabilities':['food_feed_notifications','country_product_risk_patterns'],'constraints':['commercial_details_limited','public_portal_limits','not_person_identity_evidence']},
      {'source_id':'eu_enisa_news_threats','title':'ENISA News and Cyber Threats','jurisdiction':'EU','category':'cybersecurity','access_mode':'official_web_monitor','base_url':'https://www.enisa.europa.eu','docs_url':'https://www.enisa.europa.eu/topics/cyber-threats','capabilities':['threat_context','publications','news_updates'],'constraints':['context_not_attribution','controlled_monitoring','terms_review']},
      {'source_id':'de_bsi_security_situation','title':'BSI Cyber-Sicherheitslage','jurisdiction':'DE','category':'cybersecurity','access_mode':'official_web_monitor','base_url':'https://www.bsi.bund.de','docs_url':'https://www.bsi.bund.de/DE/Themen/Verbraucherinnen-und-Verbraucher/Cyber-Sicherheitslage/cyber-sicherheitslage.html','capabilities':['warnings','situation_context','advisories'],'constraints':['technical_context_not_person_attribution','controlled_polling','terms_review']},
    ]
    POLICY={'public_only':True,'rule_based_explainable':True,'no_predictive_policing':True,'no_automatic_criminality_score':True,'no_automatic_accusation':True,'no_automatic_intervention':True,'human_review_required':True}
    def __init__(self,db:Any,audit:Any,*,monitor:Any,graph:Any,temporal_graph:Any,social_depth:Any,european_sources:Any,actor:str='system'):
        self.db,self.audit,self.monitor,self.graph,self.temporal_graph,self.social_depth,self.european_sources,self.actor=db,audit,monitor,graph,temporal_graph,social_depth,european_sources,actor
    def seed_sources(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!='PATTERN SOURCES 179 ERWEITERN': raise PermissionError('explicit source approval required')
        for p in self.SOURCE_PROFILES:
            payload={**p,'status':'DOCUMENTED'}
            self.db.execute('INSERT OR REPLACE INTO pattern_source_profiles_179 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(p['source_id'],p['title'],p['jurisdiction'],p['category'],p['access_mode'],p['base_url'],p['docs_url'],dumps(p['capabilities']),dumps(p['constraints']),'DOCUMENTED',now_ts(),_hash(payload)))
        return {'created':len(self.SOURCE_PROFILES),'production_active':0,'review_required':True}
    def create_rule(self,case_id:str,title:str,*,rule_type:str,condition:Mapping[str,Any],severity:str='medium',window_hours:int=168,minimum_sources:int=1,created_by:str|None=None,confirmation:str)->dict[str,Any]:
        if confirmation!=f'PATTERN 179 {case_id} REGEL ANLEGEN': raise PermissionError('explicit rule approval required')
        if rule_type not in self.RULE_TYPES: raise ValueError('unsupported rule type')
        if severity not in {'low','medium','high','critical'}: raise ValueError('invalid severity')
        if window_hours<1 or window_hours>8760 or minimum_sources<1 or minimum_sources>20: raise ValueError('rule limits exceeded')
        rid=new_id('rule179'); clean=_clean(dict(condition)); policy={**self.POLICY,'window_hours':window_hours,'minimum_sources':minimum_sources}
        payload={'rule_id':rid,'case_id':case_id,'title':title,'rule_type':rule_type,'condition':clean,'severity':severity,'window_hours':window_hours,'minimum_sources':minimum_sources,'status':'active','policy':policy}
        self.db.execute('INSERT INTO pattern_rules_179 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,case_id,title,rule_type,dumps(clean),severity,window_hours,minimum_sources,'active',dumps(policy),created_by or self.actor,now_ts(),now_ts(),_hash(payload)))
        self._event(case_id,rid,'rule_created',payload); return {**payload,'review_required':True}
    def evaluate(self,case_id:str,*,events:Sequence[Mapping[str,Any]],confirmation:str)->dict[str,Any]:
        if confirmation!=f'PATTERN 179 {case_id} AUSWERTEN': raise PermissionError('explicit evaluation approval required')
        rules=[dict(r) for r in self.db.all("SELECT * FROM pattern_rules_179 WHERE case_id=? AND status='active'",(case_id,))]
        clean_events=[_clean(dict(e)) for e in events[:10000]]; run_id=new_id('prun179'); findings=[]
        for r in rules:
            r['condition']=loads(r.pop('condition_json')); match=self._match(r,clean_events)
            if match:
                findings.append(self._finding(run_id,case_id,r,match))
        summary={'events_evaluated':len(clean_events),'rules_evaluated':len(rules),'findings':len(findings),'review_required':True,'automatic_action':False}
        self.db.execute('INSERT INTO pattern_runs_179 VALUES(?,?,?,?,?,?,?,?)',(run_id,case_id,now_ts(),now_ts(),'succeeded',dumps(summary),_hash({'run_id':run_id,**summary}),self.actor))
        self._event(case_id,None,'evaluation_completed',summary); return {'run_id':run_id,**summary,'finding_items':findings}
    def acknowledge(self,finding_id:str,*,reviewer:str,decision:str,note:str='',confirmation:str)->dict[str,Any]:
        if decision not in {'acknowledged','dismissed','needs_more_evidence'}: raise ValueError('invalid decision')
        if confirmation!=f'PATTERN 179 {finding_id} PRUEFEN': raise PermissionError('explicit review required')
        row=self.db.one('SELECT * FROM pattern_findings_179 WHERE finding_id=?',(finding_id,))
        if not row: raise KeyError('finding not found')
        self.db.execute('UPDATE pattern_findings_179 SET status=?,reviewed_by=?,reviewed_at=?,review_note=? WHERE finding_id=?',(decision,reviewer,now_ts(),note,finding_id))
        self._event(row['case_id'],row['rule_id'],'finding_reviewed',{'finding_id':finding_id,'decision':decision,'reviewer':reviewer}); return {'finding_id':finding_id,'status':decision}
    def case_patterns(self,case_id:str)->dict[str,Any]:
        findings=[dict(r) for r in self.db.all("SELECT * FROM pattern_findings_179 WHERE case_id=? ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC",(case_id,))]
        for f in findings: f['evidence']=loads(f.pop('evidence_json')); f['explanation']=loads(f.pop('explanation_json'))
        return {'case_id':case_id,'findings':findings,'limitations':['patterns_are_investigative_leads','correlation_is_not_causation','centrality_is_not_culpability','human_review_required'],'automatic_intervention':False}
    def source_coverage(self)->dict[str,Any]:
        tables=('european_source_profiles_172','extended_source_profiles_173','media_source_profiles_174','geo_source_profiles_175','multilingual_source_profiles_176','graph_source_profiles_177','monitor_source_profiles_178','pattern_source_profiles_179')
        counts=[]
        for t in tables:
            try: counts.append(int(self.db.one(f'SELECT COUNT(*) n FROM {t}')['n']))
            except Exception: counts.append(0)
        payload={'total_documented_sources':sum(counts),'pattern_sources':counts[-1],'production_active_new':0,'counts_by_layer':counts,'review_required':True}; return {**payload,'payload_sha256':_hash(payload)}
    def _match(self,r:Mapping[str,Any],events:Sequence[Mapping[str,Any]])->dict[str,Any]|None:
        typ=r['rule_type']; c=r['condition']; selected=[]
        def val(e,k): return e.get(k) if k in e else (e.get('details') or {}).get(k)
        if typ in {'new_alias','new_location','new_relationship','content_change','account_change'}:
            expected={'new_alias':'alias','new_location':'location','new_relationship':'relationship','content_change':'content_change','account_change':'account_change'}[typ]
            selected=[e for e in events if str(e.get('event_type'))==expected and all(str(val(e,k))==str(v) for k,v in c.items() if k not in {'keywords'})]
        elif typ=='timeline_conflict': selected=[e for e in events if e.get('event_type') in {'timeline_conflict','temporal_overlap'}]
        elif typ=='multi_source_confirmation':
            key=c.get('claim_key','claim'); groups={}
            for e in events:
                claim=str(val(e,key) or ''); source=str(e.get('source_id') or '')
                if claim and source: groups.setdefault(claim,set()).add(source)
            selected=[{'claim':k,'sources':sorted(v)} for k,v in groups.items() if len(v)>=int(r['minimum_sources'])]
        elif typ=='keyword_sequence':
            terms=[str(x).lower() for x in c.get('keywords',[])]; selected=[e for e in events if terms and all(t in _canon(e).lower() for t in terms)]
        if not selected: return None
        return {'matched_count':len(selected),'sample':selected[:20],'source_count':len({str(e.get('source_id')) for e in events if e.get('source_id')})}
    def _finding(self,run_id:str,case_id:str,r:Mapping[str,Any],match:Mapping[str,Any])->dict[str,Any]:
        fid=new_id('finding179'); explanation={'rule_type':r['rule_type'],'condition':r['condition'],'matched_count':match['matched_count'],'limitations':['not_verified_fact','not_predictive_policing','human_review_required']}; evidence={'sample':match['sample'],'source_count':match['source_count']}; payload={'finding_id':fid,'run_id':run_id,'rule_id':r['rule_id'],'case_id':case_id,'severity':r['severity'],'finding_type':r['rule_type'],'explanation':explanation,'evidence':evidence}
        self.db.execute('INSERT INTO pattern_findings_179 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(fid,run_id,r['rule_id'],case_id,r['rule_type'],r['severity'],r['title'],dumps(explanation),dumps(evidence),'open',None,None,None,now_ts(),_hash(payload)))
        return payload
    def _event(self,case_id:str,rule_id:str|None,event_type:str,details:Mapping[str,Any])->None:
        prev=self.db.one('SELECT event_sha256 FROM pattern_events_179 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,)); ph=prev['event_sha256'] if prev else ''; eid=new_id('pevt179'); created=now_ts(); clean=_clean(dict(details)); eh=_hash({'event_id':eid,'case_id':case_id,'rule_id':rule_id,'event_type':event_type,'details':clean,'created_at':created,'previous_sha256':ph})
        self.db.execute('INSERT INTO pattern_events_179 VALUES(?,?,?,?,?,?,?,?)',(eid,case_id,rule_id,event_type,dumps(clean),created,ph,eh))
