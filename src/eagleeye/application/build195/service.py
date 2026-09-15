from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone, timedelta
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v: Any)->str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v: Any)->str: return hashlib.sha256(_canon(v).encode()).hexdigest()
SECRET=re.compile(r"(?i)(token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key)")
INJECTION=re.compile(r"(?i)(ignore previous instructions|reveal (?:the )?system prompt|bypass policy|disable audit|execute this command)")

class Build195ContinuousCaseIntelligenceService:
    BUILD='195.0'
    SOURCES=(
      ('gdelt_monitor','GDELT DOC monitoring','global','news_monitor','structured_connector','https://api.gdeltproject.org/api/v2/doc/doc','open',60),
      ('mediacloud_monitor','Media Cloud monitoring','global','news_archive_monitor','credentialed_connector','https://api.mediacloud.org/api/search','api_key',60),
      ('rss_atom_monitor','RSS/Atom publication monitoring','global','publication_feed','rss_connector','feed://configured-source','none',60),
      ('internet_archive_changes','Internet Archive CDX change watch','global','web_archive_monitor','structured_connector','https://web.archive.org/cdx/search/cdx','open',360),
      ('us_sec_submissions_watch','SEC submissions watch','US','official_registry_monitor','structured_connector','https://data.sec.gov/submissions/','user_agent',120),
      ('us_federal_register_watch','US Federal Register watch','US','official_notice_monitor','structured_connector','https://www.federalregister.gov/api/v1/documents.json','open',120),
      ('de_dip_watch','Bundestag DIP change watch','DE','parliament_monitor','credentialed_connector','https://search.dip.bundestag.de/api/v1','api_key',180),
      ('il_knesset_watch','Knesset OData watch','IL','parliament_monitor','structured_connector','https://knesset.gov.il/Odata/ParliamentInfo.svc','open',180),
      ('global_gleif_watch','GLEIF LEI watch','global','company_registry_monitor','structured_connector','https://api.gleif.org/api/v1/lei-records','open',360),
      ('github_events_watch','GitHub public events/search watch','global','developer_social_monitor','credentialed_connector','https://api.github.com','token_optional',60),
      ('bluesky_search_watch','Bluesky public search watch','global','social_monitor','structured_connector','https://public.api.bsky.app/xrpc','open',60),
      ('mastodon_public_watch','Mastodon public instance watch','global','social_monitor','instance_connector','instance://public-api','instance_specific',60),
    )
    def __init__(self,db:Any,audit:Any,*,media:Any,source_ai:Any,graph:Any,identity:Any,capture:Any,source_ops:Any,global_sources:Any,actor:str='system'):
        self.db,self.audit=db,audit; self.media,self.source_ai,self.graph,self.identity,self.capture,self.source_ops,self.global_sources=media,source_ai,graph,identity,capture,source_ops,global_sources; self.actor=actor
    def seed_sources(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!='MONITOR SOURCES 195 ANLEGEN': raise PermissionError('explicit approval required')
        for sid,name,region,klass,mode,endpoint,auth,floor in self.SOURCES:
            p={'source_id':sid,'name':name,'region':region,'source_class':klass,'access_mode':mode,'endpoint':endpoint,'auth_type':auth,'polling_floor_minutes':floor,'status':'DOCUMENTED'}
            self.db.execute('INSERT OR REPLACE INTO monitoring_source_profiles_195 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,name,region,klass,mode,endpoint,auth,'DOCUMENTED',floor,'pending','pending','not_tested',now_ts(),dumps(['terms_review','fixture','live_probe','human_activation']),_hash(p)))
        return {'profiles':len(self.SOURCES),'automatic_activation':False,'minimum_polling_minutes':60,'production_rule':'terms+fixture+live_probe+human_activation'}
    def create_monitor(self,*,case_id:str,name:str,question:str,subjects:Sequence[Mapping[str,Any]],source_ids:Sequence[str],interval_minutes:int,confirmation:str)->dict[str,Any]:
        if confirmation!=f'MONITOR 195 {case_id} ANLEGEN': raise PermissionError('explicit approval required')
        known={x[0]:x for x in self.SOURCES}; missing=[s for s in source_ids if s not in known]
        if missing: raise ValueError(f'unknown sources: {missing}')
        floor=max([known[s][7] for s in source_ids] or [60]); interval=max(interval_minutes,floor)
        mid,created=new_id('monitor195'),now_ts(); nxt=(datetime.now(timezone.utc)+timedelta(minutes=interval)).isoformat()
        policy={'local_processing':True,'external_uploads':False,'human_review_required':True,'automatic_identity_confirmation':False,'automatic_contact':False,'respect_rate_limits':True,'content_is_untrusted_data':True}
        payload={'monitor_id':mid,'case_id':case_id,'name':name,'question':question,'subjects':self._redact(list(subjects)),'source_ids':list(source_ids),'interval_minutes':interval,'status':'draft','last_run_at':'','next_run_at':nxt,'created_at':created,'policy':policy,'next_global_step':'3_verify_candidates'}
        self.db.execute('INSERT INTO case_monitors_195 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,case_id,name,question,dumps(payload['subjects']),dumps(list(source_ids)),interval,'draft','',nxt,created,dumps(policy),_hash(payload)))
        self._event(mid,'monitor_created',payload)
        return payload
    def activate_monitor(self,*,monitor_id:str,approved_by:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'MONITOR 195 {monitor_id} AKTIVIEREN': raise PermissionError('explicit approval required')
        row=self.db.one('SELECT * FROM case_monitors_195 WHERE monitor_id=?',(monitor_id,));
        if not row: raise KeyError(monitor_id)
        self.db.execute("UPDATE case_monitors_195 SET status='active' WHERE monitor_id=?",(monitor_id,)); self._event(monitor_id,'monitor_activated',{'approved_by':approved_by})
        return {'monitor_id':monitor_id,'status':'active','automatic_external_actions':False}
    def record_observation(self,*,monitor_id:str,source_id:str,source_ref:str,published_at:str,content_type:str,title:str,summary:str,claims:Sequence[Mapping[str,Any]],entities:Sequence[Mapping[str,Any]],provenance:Mapping[str,Any],confirmation:str)->dict[str,Any]:
        if confirmation!=f'OBSERVATION 195 {monitor_id} SPEICHERN': raise PermissionError('explicit approval required')
        if not self.db.one('SELECT monitor_id FROM case_monitors_195 WHERE monitor_id=?',(monitor_id,)): raise KeyError(monitor_id)
        oid,obs=new_id('obs195'),now_ts(); clean_summary=str(self._redact(summary))[:4000]; clean_claims=self._redact(list(claims)); clean_entities=self._redact(list(entities)); clean_prov=self._redact(dict(provenance)); inj=bool(INJECTION.search(title+' '+summary)); content_hash=_hash({'title':title,'summary':clean_summary,'claims':clean_claims,'entities':clean_entities})
        payload={'observation_id':oid,'monitor_id':monitor_id,'source_id':source_id,'source_ref':self._redact_url(source_ref),'observed_at':obs,'published_at':published_at,'content_type':content_type,'title':title,'summary':clean_summary,'claims':clean_claims,'entities':clean_entities,'content_sha256':content_hash,'provenance':clean_prov,'prompt_injection_candidate':inj,'review_status':'candidate'}
        duplicate=self.db.one('SELECT observation_id FROM monitor_observations_195 WHERE monitor_id=? AND content_sha256=?',(monitor_id,content_hash))
        if duplicate: return {'duplicate':True,'existing_observation_id':duplicate['observation_id'],'content_sha256':content_hash}
        self.db.execute('INSERT INTO monitor_observations_195 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,monitor_id,source_id,payload['source_ref'],obs,published_at,content_type,title,clean_summary,dumps(clean_claims),dumps(clean_entities),content_hash,dumps(clean_prov),1 if inj else 0,'candidate',_hash(payload)))
        self._event(monitor_id,'observation_recorded',{'observation_id':oid,'source_id':source_id,'prompt_injection_candidate':inj})
        return payload
    def assess_impact(self,*,monitor_id:str,observation_id:str,graph_id:str,claim_id:str,old_state:Mapping[str,Any],new_state:Mapping[str,Any],confirmation:str)->dict[str,Any]:
        if confirmation!=f'IMPACT 195 {observation_id} PRUEFEN': raise PermissionError('explicit approval required')
        obs=self.db.one('SELECT * FROM monitor_observations_195 WHERE observation_id=? AND monitor_id=?',(observation_id,monitor_id));
        if not obs: raise KeyError(observation_id)
        old,new=dict(old_state),dict(new_state); old_status=str(old.get('status','unreviewed')); new_status=str(new.get('status','unreviewed'))
        if new_status in {'contested','contested_candidate','contradicted_candidate'} and old_status not in {'contested','contested_candidate','contradicted_candidate'}: impact,severity,reason='claim_contradicted','high','Neue Quelle widerspricht einem bisher nicht widersprochenen Claim.'
        elif old.get('value')!=new.get('value'): impact,severity,reason='claim_changed','medium','Eine bestehende Angabe hat sich geändert.'
        elif old_status!=new_status: impact,severity,reason='claim_status_changed','medium','Der Prüfstatus eines Claims hat sich verändert.'
        else: impact,severity,reason='corroboration_added','low','Neue Quelle ergänzt die bestehende Beleglage.'
        iid,created=new_id('impact195'),now_ts(); payload={'impact_id':iid,'monitor_id':monitor_id,'observation_id':observation_id,'graph_id':graph_id,'claim_id':claim_id,'impact_type':impact,'severity':severity,'reason':reason,'old_state':old,'new_state':new,'created_at':created,'review_status':'candidate'}
        self.db.execute('INSERT INTO case_change_impacts_195 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(iid,monitor_id,observation_id,graph_id,claim_id,impact,severity,reason,dumps(old),dumps(new),created,'candidate',_hash(payload)))
        return payload
    def ai_triage(self,*,monitor_id:str,observation_id:str,impact_id:str,question:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'AI MONITOR 195 {impact_id} AUSWERTEN': raise PermissionError('explicit approval required')
        impact=self.db.one('SELECT * FROM case_change_impacts_195 WHERE impact_id=?',(impact_id,)); obs=self.db.one('SELECT * FROM monitor_observations_195 WHERE observation_id=?',(observation_id,))
        if not impact or not obs: raise KeyError('impact or observation missing')
        recommendations=['Originalquelle und Erfassungszeit prüfen','Quellenunabhängigkeit bewerten','Claim in Schritt 3 – Prüfen öffnen']
        if impact['severity']=='high': recommendations.insert(0,'Bestehende Fallbewertung bis zum Review nicht fortschreiben')
        if obs['prompt_injection_candidate']: recommendations.insert(0,'Quelleninhalt als potenzielle Prompt-Injection isoliert behandeln')
        assessment={'question':question,'impact_type':impact['impact_type'],'severity':impact['severity'],'reason':impact['reason'],'recommendations':recommendations,'limitations':['ai_output_is_not_fact','news_and_social_updates_require_primary_source_review','human_review_required'],'automatic_action':False}
        aid,created=new_id('monai195'),now_ts(); self.db.execute('INSERT INTO monitoring_ai_assessments_195 VALUES(?,?,?,?,?,?,?)',(aid,monitor_id,observation_id,impact_id,dumps(assessment),created,_hash(assessment)))
        return {'assessment_id':aid,**assessment}
    def create_alert(self,*,monitor_id:str,impact_id:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'ALERT 195 {impact_id} ERSTELLEN': raise PermissionError('explicit approval required')
        impact=self.db.one('SELECT i.*,m.case_id FROM case_change_impacts_195 i JOIN case_monitors_195 m ON m.monitor_id=i.monitor_id WHERE i.impact_id=?',(impact_id,));
        if not impact: raise KeyError(impact_id)
        title={'high':'Wesentlicher Widerspruch im Fall','medium':'Relevante Falländerung','low':'Neue Korroboration'}[impact['severity']]
        action='Sofort in Schritt 3 prüfen' if impact['severity']=='high' else 'Bei nächster Fallprüfung bewerten'
        aid,created=new_id('alert195'),now_ts(); payload={'alert_id':aid,'monitor_id':monitor_id,'impact_id':impact_id,'case_id':impact['case_id'],'severity':impact['severity'],'title':title,'explanation':impact['reason'],'recommended_action':action,'status':'open','created_at':created,'automatic_notification':False}
        self.db.execute('INSERT INTO case_alerts_195 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(aid,monitor_id,impact_id,impact['case_id'],impact['severity'],title,impact['reason'],action,'open',created,'',_hash(payload)))
        return payload
    def dashboard(self,*,case_id:str='')->dict[str,Any]:
        where=' WHERE case_id=?' if case_id else ''; args=(case_id,) if case_id else ()
        n=lambda q,a=(): int((self.db.one(q,a) or {'n':0})['n'])
        return {'build':self.BUILD,'monitors':n('SELECT COUNT(*) AS n FROM case_monitors_195'+where,args),'active_monitors':n("SELECT COUNT(*) AS n FROM case_monitors_195"+where+(" AND" if where else " WHERE")+" status='active'",args),'open_alerts':n("SELECT COUNT(*) AS n FROM case_alerts_195"+(" WHERE case_id=? AND" if case_id else " WHERE")+" status='open'",args),'guided_summary':'Änderung erkennen → betroffenen Claim erklären → Quelle prüfen → Fallakte aktualisieren','opsec':{'local_processing':True,'external_uploads':False,'automatic_contact':False,'automatic_identity_confirmation':False,'minimum_polling_minutes':60}}
    def _event(self,mid:str,event_type:str,payload:Mapping[str,Any])->None:
        row=self.db.one('SELECT event_hash FROM monitoring_events_195 WHERE monitor_id=? ORDER BY created_at DESC LIMIT 1',(mid,)); prev=row['event_hash'] if row else ''; eid,created=new_id('monevent195'),now_ts(); body={'event_id':eid,'monitor_id':mid,'event_type':event_type,'actor':self.actor,'created_at':created,'payload':self._redact(dict(payload)),'prev_hash':prev}; eh=_hash(body); self.db.execute('INSERT INTO monitoring_events_195 VALUES(?,?,?,?,?,?,?,?)',(eid,mid,event_type,self.actor,created,dumps(body['payload']),prev,eh))
    def _redact(self,v:Any)->Any:
        if isinstance(v,Mapping): return {k:('[REDACTED]' if SECRET.search(str(k)) else self._redact(x)) for k,x in v.items()}
        if isinstance(v,list): return [self._redact(x) for x in v]
        return v
    def _redact_url(self,url:str)->str:
        p=urlsplit(url); q=[(k,'[REDACTED]' if SECRET.search(k) else v) for k,v in parse_qsl(p.query,keep_blank_values=True)]; return urlunsplit((p.scheme,p.netloc,p.path,urlencode(q),p.fragment))
