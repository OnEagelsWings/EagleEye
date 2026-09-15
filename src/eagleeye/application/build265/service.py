from __future__ import annotations
import hashlib,json,re,time,uuid,shutil
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
import os

def _now():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def _id(p):return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _words(s):return set(re.sub(r'\W+',' ',str(s or '').casefold()).split())
def _date_value(s):
    try:
        if len(s)==10:return date.fromisoformat(s).toordinal()
        if len(s)==4:return date(int(s),7,1).toordinal()
    except:pass
    return None

class Build265TemporalContradictionService:
    BUILD='265.0'
    def __init__(self,db:Any,audit:Any,*,execution264:Any,research263:Any,compatibility:Any,training:Any,actor:str='local-analyst'):
        self.db=db;self.audit=audit;self.execution264=execution264;self.research263=research263;self.compatibility=compatibility;self.training=training;self.actor=actor
        self.base=Path(db.path).parent/'opsec_sessions_265';self.base.mkdir(parents=True,exist_ok=True);self.cleanup_orphans()

    def create_opsec_context(self,*,case_id,run_id,proxy_mode='direct',proxy_label='',mode='automated_provider'):
        if proxy_mode not in {'direct','user_configured_proxy'}:raise ValueError('only direct or user_configured_proxy modes are supported')
        sid=_id('opsec265');profile=self.base/sid/'firefox_profile';profile.mkdir(parents=True,exist_ok=False)
        for sub in ('cache','storage','downloads'): (profile/sub).mkdir()
        # Build 267 defensive browser privacy defaults. These reduce local/referrer leakage
        # but do not claim network anonymity or IP rotation.
        prefs = [
            'user_pref("browser.privatebrowsing.autostart", true);',
            'user_pref("network.http.sendRefererHeader", 0);',
            'user_pref("network.http.referer.XOriginPolicy", 2);',
            'user_pref("privacy.clearOnShutdown.cookies", true);',
            'user_pref("privacy.clearOnShutdown.cache", true);',
            'user_pref("privacy.clearOnShutdown.history", true);',
            'user_pref("privacy.sanitize.sanitizeOnShutdown", true);',
            'user_pref("media.peerconnection.enabled", false);',
            'user_pref("network.dns.disablePrefetch", true);',
            'user_pref("network.prefetch-next", false);',
            'user_pref("network.predictor.enabled", false);',
            'user_pref("network.http.speculative-parallel-limit", 0);',
            'user_pref("browser.urlbar.speculativeConnect.enabled", false);',
            'user_pref("privacy.resistFingerprinting", true);',
            'user_pref("toolkit.telemetry.enabled", false);',
            'user_pref("datareporting.healthreport.uploadEnabled", false);',
        ]
        if proxy_mode == 'user_configured_proxy':
            proxy_url=os.environ.get('EAGLEEYE_OUTBOUND_PROXY','').strip()
            pp=urlsplit(proxy_url) if proxy_url else None
            if not pp or pp.scheme not in {'http','https'} or not pp.hostname or pp.username or pp.password:
                raise RuntimeError('user_configured_proxy requires credential-free EAGLEEYE_OUTBOUND_PROXY http(s) endpoint')
            port=pp.port or (443 if pp.scheme=='https' else 80)
            prefs += [
                'user_pref("network.proxy.type", 1);',
                f'user_pref("network.proxy.http", "{pp.hostname}");',
                f'user_pref("network.proxy.http_port", {port});',
                f'user_pref("network.proxy.ssl", "{pp.hostname}");',
                f'user_pref("network.proxy.ssl_port", {port});',
                'user_pref("network.proxy.no_proxies_on", "localhost, 127.0.0.1");',
            ]
        (profile/'user.js').write_text('\n'.join(prefs)+'\n', encoding='utf-8')
        rel=str(profile.relative_to(Path(self.db.path).parent));ph=_hash(proxy_label) if proxy_label else ''
        payload={'run_id':run_id,'mode':mode,'proxy_mode':proxy_mode,'profile':rel,'email_identity_mode':'none'}
        self.db.execute('INSERT INTO opsec_sessions_265 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(sid,case_id,run_id,mode,rel,proxy_mode,ph,'none','active',_now(),'',_hash(payload)))
        self._event(case_id,'opsec_context_created','opsec_session',sid,self.actor,{'run_id':run_id,'proxy_mode':proxy_mode,'email_identity_mode':'none'})
        return {'session_id':sid,'profile_path':str(profile),'proxy_mode':proxy_mode,'email_identity_mode':'none','automatic_ip_rotation':False,'synthetic_email_creation':False}

    def cleanup_context(self,session_id,notes='run complete'):
        row=self.db.one('SELECT * FROM opsec_sessions_265 WHERE session_id=?',(session_id,))
        if not row:raise KeyError('opsec session')
        p=Path(self.db.path).parent/row['ephemeral_profile_relpath'];removed=True
        try:shutil.rmtree(p.parent if p.name=='firefox_profile' else p,ignore_errors=False)
        except FileNotFoundError:pass
        except Exception:removed=False
        self.db.execute("UPDATE opsec_sessions_265 SET status='cleaned',cleaned_at=? WHERE session_id=?",(_now(),session_id))
        cid=_id('cleanup265');payload={'session_id':session_id,'profile_removed':removed,'cookies_retained':0,'cache_retained':0,'history_retained':0}
        self.db.execute('INSERT INTO opsec_cleanup_265 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(cid,session_id,row['case_id'],row['run_id'],int(removed),0,0,0,notes,_now(),_hash(payload)))
        self._event(row['case_id'],'opsec_context_cleaned','opsec_session',session_id,self.actor,payload)
        return payload

    def cleanup_orphans(self):
        if not self.base.exists():return 0
        n=0
        for row in self.db.all("SELECT session_id FROM opsec_sessions_265 WHERE status IN ('active','cleanup_pending')"):
            try:self.cleanup_context(row['session_id'],notes='orphan cleanup on application start');n+=1
            except Exception:pass
        known={r['session_id'] for r in self.db.all('SELECT session_id FROM opsec_sessions_265')}
        for d in self.base.iterdir():
            if d.is_dir() and d.name not in known:shutil.rmtree(d,ignore_errors=True);n+=1
        return n

    def execute_enhanced(self,*,case_id,run_id,confirmation,approved_by=None,provider='',max_queries=8,max_results_per_query=8,proxy_mode='direct',proxy_label=''):
        if str(confirmation).strip().upper()!='OK':raise PermissionError('explicit OK required')
        ctx=self.create_opsec_context(case_id=case_id,run_id=run_id,proxy_mode=proxy_mode,proxy_label=proxy_label,mode='browser_queue' if provider=='browser_queue' else 'automated_provider')
        try:
            out=self.execution264.approve_and_execute(case_id=case_id,run_id=run_id,confirmation='OK',approved_by=approved_by or self.actor,provider=provider,max_queries=max_queries,max_results_per_query=max_results_per_query,browser_profile_path=ctx['profile_path'] if provider=='browser_queue' else '')
            analysis=self.analyze_run(case_id=case_id,run_id=run_id,actor=approved_by or self.actor)
            out['temporal_analysis_265']=analysis;out['opsec_context']={k:v for k,v in ctx.items() if k!='profile_path'}
            return out
        finally:
            if provider=='browser_queue':
                self.db.execute("UPDATE opsec_sessions_265 SET status='cleanup_pending' WHERE session_id=?",(ctx['session_id'],))
            else:
                self.cleanup_context(ctx['session_id'])

    def finalize_browser_context(self,*,case_id,run_id):
        row=self.db.one("SELECT session_id FROM opsec_sessions_265 WHERE case_id=? AND run_id=? AND status='cleanup_pending' ORDER BY created_at DESC LIMIT 1",(case_id,run_id))
        if not row:return {"status":"nothing_pending"}
        return {"status":"cleaned",**self.cleanup_context(row["session_id"],notes="browser research finalized")}

    def analyze_run(self,*,case_id,run_id,actor=None):
        actor=actor or self.actor
        rows=self.db.all('SELECT * FROM temporal_events_264 WHERE case_id=? AND run_id=? ORDER BY event_date,rowid',(case_id,run_id))
        assessments=[];conflict_refs=[]
        for i,a in enumerate(rows):
            for b in rows[i+1:]:
                overlap=len(_words(a['event_text']) & _words(b['event_text']))
                if overlap<6:continue
                av,bv=_date_value(a['event_date']),_date_value(b['event_date'])
                if av is None or bv is None or a['event_date']==b['event_date']:continue
                if a['date_precision']!=b['date_precision']:klass='precision_mismatch';sev='moderate';prec='different_precision'
                else:klass='hard_date_conflict';sev='high';prec='same_precision'
                delta=abs(av-bv) if av is not None and bv is not None else None
                bal={'a_evidence':json.loads(a['evidence_refs_json']),'b_evidence':json.loads(b['evidence_refs_json']),'auto_resolution':False}
                aid=_id('ta265');rat='Ähnliche Ereignisbeschreibung mit abweichenden Datumsangaben. Beide Evidenzpfade bleiben erhalten; keine automatische Wahrheitsentscheidung.'
                payload={'a':a['event_id'],'b':b['event_id'],'class':klass,'severity':sev,'delta':delta}
                self.db.execute('INSERT INTO temporal_assessments_265 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,run_id,a['event_id'],b['event_id'],klass,sev,delta,prec,_canon(bal),rat,'unresolved',_now(),_hash(payload)))
                assessments.append({'assessment_id':aid,**payload});conflict_refs.append(aid)
        brief=self._brief(case_id,run_id,rows,assessments,actor)
        self._event(case_id,'temporal_contradiction_analysis','research_run',run_id,actor,{'events':len(rows),'assessments':len(assessments),'brief_id':brief['brief_id']})
        return {'events_analyzed':len(rows),'conflicts':assessments,'brief':brief,'automatic_resolution':False,'automatic_causality':False}

    def _brief(self,case_id,run_id,events,assessments,actor):
        conflict_event_ids={x[k] for x in assessments for k in ('a','b')}
        consistent=[{'event_id':x['event_id'],'date':x['event_date'],'precision':x['date_precision'],'text':x['event_text'][:300],'evidence_refs':json.loads(x['evidence_refs_json'])} for x in events if x['event_id'] not in conflict_event_ids]
        unresolved=[{'assessment_id':x['assessment_id'],'class':x['class'],'severity':x['severity'],'event_a':x['a'],'event_b':x['b']} for x in assessments]
        follow=[]
        for x in unresolved[:6]:follow.append({'query':f'Prüfe Primärquellen und Originaldokumente zu den widersprüchlichen Datumsangaben {x["event_a"]} / {x["event_b"]}','reason':'temporal_conflict','requires_new_ok':True})
        summary=f'{len(events)} Timeline-Kandidaten analysiert; {len(assessments)} zeitliche Konfliktpaare; {len(consistent)} Kandidaten ohne erkannten Konflikt. Konflikte wurden nicht automatisch aufgelöst.'
        bid=_id('brief265');payload={'consistent':consistent,'conflicts':unresolved,'followup':follow,'summary':summary}
        self.db.execute('INSERT INTO timeline_briefs_265 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,case_id,run_id,_canon(consistent),_canon(unresolved),_canon(unresolved),_canon(follow),summary,'analysis_basis',actor,_now(),_hash(payload)))
        return {'brief_id':bid,'summary':summary,'consistent_events':consistent,'unresolved':unresolved,'followup_queries':follow}

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_temporal_benchmarks_265 WHERE review_status='reviewed'") or {'n':0})['n'];f=(self.db.one('SELECT COUNT(DISTINCT task_family) n FROM ai_temporal_benchmarks_265') or {'n':0})['n']
        return {'reviewed_benchmarks':n,'task_families':f,'timeline_conflict_reasoning':True,'followup_planning':True,'automatic_model_activation':False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_265 WHERE review_status='verified'") or {'n':0})['n']
        return {'verified_controls':n,'ephemeral_local_profile':1,'automatic_disposable_email_creation':0,'automatic_ip_creation_or_spoofing':0,'automatic_proxy_rotation':0,'user_configured_proxy_supported':1}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics();g={'build':'265.0','main_goal':bool(self.db.one("SELECT name FROM sqlite_master WHERE name='temporal_assessments_265'")),'ai_delta':a['reviewed_benchmarks']>=32 and a['task_families']>=15,'opsec_delta':o['verified_controls']>=28 and o['ephemeral_local_profile']==1,'capability_regression':'approved_ai_research_execution' in caps and 'advanced_timeline_reconstruction' in caps,'parent_build_gate':self.execution264.qualified_gate()['release_ready']};g['release_ready']=all(g[k] for k in ('main_goal','ai_delta','opsec_delta','capability_regression','parent_build_gate'));return g
    def render_workspace_panel(self,*,case_id,csrf):
        import html;e=lambda x:html.escape(str(x or ''),quote=True)
        briefs=self.db.all('SELECT * FROM timeline_briefs_265 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,));rows=''.join(f"<tr><td><code>{e(x['run_id'])}</code></td><td>{e(x['summary'])}</td><td>{e(x['created_at'])}</td></tr>" for x in briefs)
        pending=self.db.all("SELECT run_id,session_id FROM opsec_sessions_265 WHERE case_id=? AND status='cleanup_pending' ORDER BY created_at DESC",(case_id,))
        cleanup=''.join(f"<form method='post' action='/build265/finalize-browser'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='run_id' value='{e(x['run_id'])}'><button>Browser-Recherche {e(x['run_id'])} abschließen & temporäres Profil löschen</button></form>" for x in pending)
        return f"""<section class='card'><h2>Temporal Contradictions & OPSEC 265</h2><p><b>Timeline vergleichen → Konflikte erhalten → Follow-up priorisieren.</b></p><p>OPSEC: pro Run separater lokaler Session-Kontext, Cookie/Cache/History-Isolation und Cleanup. Optional kann ein bereits von dir konfigurierter Proxy genutzt werden. EagleEye erzeugt keine Wegwerf-E-Mail, keine neue/gespoofte IP und rotiert keine Proxy-Infrastruktur.</p>{cleanup}<table><tr><th>Run</th><th>Chronologie-Brief</th><th>Zeit</th></tr>{rows or '<tr><td colspan=3>Noch kein Brief.</td></tr>'}</table><pre>{e(_canon(self.qualified_gate()))}</pre></section>"""
    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one('SELECT event_hash FROM build265_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(cid,));ph=prev['event_hash'] if prev else 'GENESIS';eid=_id('evt265');now=_now();data={'event_id':eid,'case_id':cid,'event_type':etype,'object_type':otype,'object_id':oid,'actor':actor,'payload':payload,'previous_hash':ph,'created_at':now};self.db.execute('INSERT INTO build265_events VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
