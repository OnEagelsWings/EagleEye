from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Mapping, Sequence
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode('utf-8')).hexdigest()
def _clean(v: Any) -> Any:
    sensitive=('token','secret','password','authorization','cookie','session','api_key','private_key')
    if isinstance(v, Mapping):
        return {str(k):('[REDACTED]' if any(x in str(k).lower() for x in sensitive) else _clean(val)) for k,val in v.items()}
    if isinstance(v, list): return [_clean(x) for x in v]
    return v

def _dt(v: str) -> datetime:
    d=datetime.fromisoformat(v.replace('Z','+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

class Build178InvestigationMonitorService:
    BUILD='178.0'
    MIN_INTERVAL_MINUTES=60
    MAX_INTERVAL_MINUTES=43_200
    MAX_ACTIVE_DAYS=365
    SOURCE_PROFILES=[
      {'source_id':'de_bka_press_monitor','title':'BKA Pressemitteilungen','jurisdiction':'DE','category':'law_enforcement_news','access_mode':'official_web_monitor','base_url':'https://www.bka.de','docs_url':'https://www.bka.de/DE/AktuelleInformationen/AktuelleMeldungen/Pressemeldungen/pressemitteilungen_node.html','terms_url':'https://www.bka.de/DE/Service/Impressum/impressum_node.html','capabilities':['press_releases','public_case_updates','public_warnings'],'constraints':['public_information_only','not_complete_case_file','change_frequency_control']},
      {'source_id':'eu_europol_news_monitor','title':'Europol Newsroom','jurisdiction':'EU','category':'law_enforcement_news','access_mode':'official_web_monitor','base_url':'https://www.europol.europa.eu','docs_url':'https://www.europol.europa.eu/media-press/newsroom','terms_url':'https://www.europol.europa.eu/legal-notice','capabilities':['operation_updates','public_warnings','international_case_context'],'constraints':['public_information_only','no_operational_inference','terms_review']},
      {'source_id':'eu_commission_press_monitor','title':'European Commission Press Corner','jurisdiction':'EU','category':'official_news','access_mode':'official_feed_or_web','base_url':'https://ec.europa.eu','docs_url':'https://ec.europa.eu/commission/presscorner/home/en','terms_url':'https://commission.europa.eu/legal-notice_en','capabilities':['press_releases','statements','speeches','multilingual_updates'],'constraints':['official_context','feed_schema_monitoring','no_person_identity_confirmation']},
      {'source_id':'eu_eurostat_rss_monitor','title':'Eurostat RSS News Releases','jurisdiction':'EU','category':'official_statistics_news','access_mode':'official_rss','base_url':'https://ec.europa.eu','docs_url':'https://ec.europa.eu/eurostat/web/rss','terms_url':'https://ec.europa.eu/eurostat/about-us/policies/copyright','capabilities':['news_releases','statistical_updates','topic_feeds'],'constraints':['aggregate_context_only','rss_polling_frequency','not_person_evidence']},
      {'source_id':'de_certbund_advisories_monitor','title':'CERT-Bund Warn- und Informationsdienst','jurisdiction':'DE','category':'cybersecurity_advisories','access_mode':'official_web_or_feed','base_url':'https://wid.cert-bund.de','docs_url':'https://wid.cert-bund.de/portal/wid/start','terms_url':'https://www.bsi.bund.de/DE/Service-Navi/Impressum/impressum_node.html','capabilities':['security_advisories','vulnerability_updates','threat_context'],'constraints':['technical_context_not_person_attribution','terms_review','controlled_polling']},
      {'source_id':'de_servicebund_notices_monitor','title':'service.bund.de Bekanntmachungen','jurisdiction':'DE','category':'public_notices','access_mode':'official_guided_monitor','base_url':'https://www.service.bund.de','docs_url':'https://www.service.bund.de/Content/DE/Home/homepage_node.html','terms_url':'https://www.service.bund.de/Content/DE/Service/Impressum/impressum_node.html','capabilities':['public_tenders','public_notices','jobs'],'constraints':['publisher_responsible_for_content','guided_access','terms_review']},
    ]
    POLICY={'public_only':True,'explicit_activation':True,'minimum_interval_minutes':60,'expiry_required':True,'no_hidden_tracking':True,'no_automatic_identity_confirmation':True,'no_automatic_accusation':True,'human_review_required':True}

    def __init__(self, db: Any, audit: Any, *, collection: Any, crawler: Any, social: Any, graph: Any, european_sources: Any, actor: str='system'):
        self.db,self.audit,self.collection,self.crawler,self.social,self.graph,self.european_sources,self.actor=db,audit,collection,crawler,social,graph,european_sources,actor

    def seed_sources(self, *, confirmation: str) -> dict[str,Any]:
        if confirmation!='MONITOR SOURCES 178 ERWEITERN': raise PermissionError('explicit source approval required')
        for p in self.SOURCE_PROFILES:
            payload={**p,'status':'DOCUMENTED'}
            self.db.execute('INSERT OR REPLACE INTO monitor_source_profiles_178 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(p['source_id'],p['title'],p['jurisdiction'],p['category'],p['access_mode'],p['base_url'],p['docs_url'],p['terms_url'],dumps(p['capabilities']),dumps(p['constraints']),'DOCUMENTED',now_ts(),_hash(payload)))
        return {'created':len(self.SOURCE_PROFILES),'production_active':0,'review_required':True}

    def create_monitor(self, case_id: str, title: str, *, query: Mapping[str,Any], source_ids: Sequence[str], interval_minutes: int=1440, active_days: int=30, priority_rules: Mapping[str,Any]|None=None, created_by: str|None=None, confirmation: str) -> dict[str,Any]:
        if confirmation!=f'MONITOR 178 {case_id} ANLEGEN': raise PermissionError('explicit monitor approval required')
        if interval_minutes < self.MIN_INTERVAL_MINUTES or interval_minutes > self.MAX_INTERVAL_MINUTES: raise ValueError('interval outside controlled limits')
        if active_days<1 or active_days>self.MAX_ACTIVE_DAYS: raise ValueError('active_days outside controlled limits')
        if not source_ids or len(source_ids)>50: raise ValueError('1..50 sources required')
        q=_clean(dict(query)); rules={'keywords':[],'minimum_relevance':0.5,'alert_on_new':True,'alert_on_change':True,**_clean(dict(priority_rules or {}))}
        now=datetime.now(timezone.utc); expires=(now+timedelta(days=active_days)).isoformat(); mid=new_id('mon178')
        policy={**self.POLICY,'interval_minutes':interval_minutes,'active_days':active_days}
        payload={'monitor_id':mid,'case_id':case_id,'title':title,'query':q,'source_ids':list(source_ids),'interval_minutes':interval_minutes,'expires_at':expires,'priority_rules':rules,'policy':policy,'status':'active'}
        self.db.execute('INSERT INTO monitor_profiles_178 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,case_id,title,dumps(q),dumps(list(source_ids)),interval_minutes,expires,dumps(rules),dumps(policy),'active',created_by or self.actor,now_ts(),now_ts(),_hash(payload)))
        self._event(mid,case_id,'monitor_created',payload)
        return {**payload,'review_required':True}

    def due_monitors(self, *, at: str|None=None) -> list[dict[str,Any]]:
        now=_dt(at) if at else datetime.now(timezone.utc); out=[]
        for row in self.db.all("SELECT * FROM monitor_profiles_178 WHERE status='active'"):
            r=dict(row)
            if _dt(r['expires_at'])<=now: continue
            last=self.db.one('SELECT finished_at FROM monitor_runs_178 WHERE monitor_id=? AND finished_at IS NOT NULL ORDER BY finished_at DESC LIMIT 1',(r['monitor_id'],))
            due=not last or (_dt(last['finished_at'])+timedelta(minutes=int(r['interval_minutes']))<=now)
            if due:
                r['query']=loads(r.pop('query_json')); r['source_ids']=loads(r.pop('source_ids_json')); r['priority_rules']=loads(r.pop('priority_rules_json')); r['policy']=loads(r.pop('policy_json')); out.append(r)
        return out

    def run_monitor(self, monitor_id: str, *, provider: Callable[[str,Mapping[str,Any]],Sequence[Mapping[str,Any]]], confirmation: str) -> dict[str,Any]:
        if confirmation!=f'MONITOR 178 {monitor_id} AUSFUEHREN': raise PermissionError('explicit monitor run approval required')
        m=self._monitor(monitor_id)
        if m['status']!='active' or _dt(m['expires_at'])<=datetime.now(timezone.utc): raise PermissionError('monitor inactive or expired')
        rid=new_id('mrun178'); start=now_ts(); total=new=changed=errors=0; alerts=[]
        for source_id in m['source_ids']:
            try: records=list(provider(source_id,m['query']) or [])
            except Exception as exc:
                errors+=1; self._event(monitor_id,m['case_id'],'source_error',{'source_id':source_id,'error_type':type(exc).__name__}); continue
            for raw in records[:5000]:
                total+=1; rec=_clean(dict(raw)); source_record_id=str(rec.get('source_record_id') or rec.get('id') or rec.get('uri') or _hash(rec)[:24]); uri=rec.get('canonical_uri') or rec.get('url'); body=rec.get('content') if 'content' in rec else rec
                ch=_hash(body); previous=self.db.one('SELECT canonical_sha256,content_json FROM monitor_observations_178 WHERE monitor_id=? AND source_id=? AND source_record_id=? ORDER BY observed_at DESC LIMIT 1',(monitor_id,source_id,source_record_id))
                change='unchanged'
                if not previous: change='new'; new+=1
                elif previous['canonical_sha256']!=ch: change='changed'; changed+=1
                relevance=self._relevance(body,m['priority_rules']); oid=new_id('mobs178'); prov={'source_id':source_id,'monitor_id':monitor_id,'query_hash':_hash(m['query']),'public_only':True,'retrieved_at':now_ts()}
                if change!='unchanged':
                    self.db.execute('INSERT OR IGNORE INTO monitor_observations_178 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,monitor_id,rid,source_id,source_record_id,uri,now_ts(),rec.get('published_at'),dumps(body),ch,previous['canonical_sha256'] if previous else None,change,relevance,'needs_review',dumps(prov)))
                    if relevance>=float(m['priority_rules'].get('minimum_relevance',0.5)) and ((change=='new' and m['priority_rules'].get('alert_on_new')) or (change=='changed' and m['priority_rules'].get('alert_on_change'))):
                        alerts.append(self._alert(m,rid,change,relevance,source_id,source_record_id,oid))
        status='partial_success' if errors and total else ('failed' if errors and not total else 'succeeded')
        summary={'result_count':total,'new_count':new,'changed_count':changed,'error_count':errors,'alert_count':len(alerts),'review_required':True}
        self.db.execute('INSERT INTO monitor_runs_178 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(rid,monitor_id,m['case_id'],start,now_ts(),status,total,new,changed,errors,dumps(summary),_hash({'run_id':rid,**summary})))
        self.db.execute('UPDATE monitor_profiles_178 SET updated_at=? WHERE monitor_id=?',(now_ts(),monitor_id)); self._event(monitor_id,m['case_id'],'monitor_run_completed',summary)
        return {'run_id':rid,'status':status,**summary,'alerts':alerts}

    def pause(self, monitor_id: str, *, reason: str, confirmation: str) -> dict[str,Any]:
        if confirmation!=f'MONITOR 178 {monitor_id} PAUSIEREN': raise PermissionError('explicit pause approval required')
        m=self._monitor(monitor_id); self.db.execute("UPDATE monitor_profiles_178 SET status='paused',updated_at=? WHERE monitor_id=?",(now_ts(),monitor_id)); self._event(monitor_id,m['case_id'],'monitor_paused',{'reason':reason})
        return {'monitor_id':monitor_id,'status':'paused'}

    def situation(self, case_id: str) -> dict[str,Any]:
        active=int(self.db.one("SELECT COUNT(*) n FROM monitor_profiles_178 WHERE case_id=? AND status='active'",(case_id,))['n'])
        alerts=[dict(r) for r in self.db.all("SELECT * FROM monitor_alerts_178 WHERE case_id=? AND status='open' ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC",(case_id,))]
        for a in alerts: a['details']=loads(a.pop('details_json')); a['source_refs']=loads(a.pop('source_refs_json'))
        return {'case_id':case_id,'active_monitors':active,'open_alerts':alerts,'limitations':['public_sources_only','monitoring_scope_and_expiry_apply','alerts_are_intelligence_leads','human_review_required'],'automatic_action':False}

    def source_coverage(self) -> dict[str,Any]:
        tables=('european_source_profiles_172','extended_source_profiles_173','media_source_profiles_174','geo_source_profiles_175','multilingual_source_profiles_176','graph_source_profiles_177','monitor_source_profiles_178')
        counts=[]
        for table in tables:
            try: counts.append(int(self.db.one(f'SELECT COUNT(*) n FROM {table}')['n']))
            except Exception: counts.append(0)
        payload={'total_documented_sources':sum(counts),'monitor_sources':counts[-1],'production_active_new':0,'counts_by_layer':counts,'review_required':True}
        return {**payload,'payload_sha256':_hash(payload)}

    def _monitor(self, monitor_id: str) -> dict[str,Any]:
        row=self.db.one('SELECT * FROM monitor_profiles_178 WHERE monitor_id=?',(monitor_id,))
        if not row: raise KeyError('monitor not found')
        r=dict(row); r['query']=loads(r.pop('query_json')); r['source_ids']=loads(r.pop('source_ids_json')); r['priority_rules']=loads(r.pop('priority_rules_json')); r['policy']=loads(r.pop('policy_json')); return r
    def _relevance(self, body: Any, rules: Mapping[str,Any]) -> float:
        text=_canon(body).lower(); terms=[str(x).lower() for x in rules.get('keywords',[]) if str(x).strip()]
        if not terms: return 0.5
        hits=sum(1 for x in terms if x in text); return round(min(1.0,0.35+0.65*hits/max(1,len(terms))),4)
    def _alert(self,m:Mapping[str,Any],rid:str,change:str,relevance:float,source_id:str,record_id:str,obs_id:str)->dict[str,Any]:
        severity='high' if relevance>=0.85 else ('medium' if relevance>=0.65 else 'low'); aid=new_id('alert178'); details={'change_type':change,'relevance':relevance,'source_id':source_id,'source_record_id':record_id,'observation_id':obs_id,'limitations':['not_verified_fact','not_automatic_escalation']}; payload={'alert_id':aid,'monitor_id':m['monitor_id'],'case_id':m['case_id'],'alert_type':'source_change','severity':severity,'details':details}
        self.db.execute('INSERT INTO monitor_alerts_178 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(aid,m['monitor_id'],rid,m['case_id'],'source_change',severity,f'{change}: {source_id}',dumps(details),dumps([obs_id]),'open',now_ts(),_hash(payload)))
        return payload
    def _event(self,monitor_id:str|None,case_id:str|None,event_type:str,details:Mapping[str,Any])->None:
        prev=self.db.one('SELECT event_sha256 FROM monitor_events_178 WHERE monitor_id IS ? ORDER BY created_at DESC LIMIT 1',(monitor_id,)); ph=prev['event_sha256'] if prev else ''; created=now_ts(); eid=new_id('mevt178'); clean=_clean(dict(details)); eh=_hash({'event_id':eid,'monitor_id':monitor_id,'case_id':case_id,'event_type':event_type,'details':clean,'created_at':created,'previous_sha256':ph})
        self.db.execute('INSERT INTO monitor_events_178 VALUES(?,?,?,?,?,?,?,?)',(eid,monitor_id,case_id,event_type,dumps(clean),created,ph,eh))
