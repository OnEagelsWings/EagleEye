from __future__ import annotations
import hashlib, html, json, os, re, shutil, time, uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

def _now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()

PROHIBITED=re.compile(r'(?i)\b(password|passwort|credential|login bypass|captcha bypass|exploit|malware deploy|purchase|buy drugs|weapon purchase|doxx|harass)\b')
INDICATORS=[
 ('email',re.compile(r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b')),
 ('btc',re.compile(r'\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}\b')),
 ('onion',re.compile(r'(?i)\b[a-z2-7]{56}\.onion\b')),
 ('sha256',re.compile(r'(?i)\b[a-f0-9]{64}\b')),
 ('ipv4',re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')),
]

class Build281Phase12MissionControllerService:
    BUILD='281.0'
    def __init__(self,db:Any,audit:Any,*,build280:Any,research263:Any,execution264:Any,install_dir:Path,base_dir:Path,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.build280=build280; self.research263=research263; self.execution264=execution264
        self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor

    def _case(self,case_id):
        row=self.db.one('SELECT case_id,title FROM cases WHERE case_id=?',(case_id,))
        if not row: raise KeyError('case not found')
        return row

    def _event(self,mission_id,event_type,actor,details):
        prev=self.db.one('SELECT event_hash FROM phase12_mission_events_281 WHERE mission_id=? ORDER BY rowid DESC LIMIT 1',(mission_id,))
        ph=prev['event_hash'] if prev else 'GENESIS'; eid=_id('p12evt281'); now=_now()
        payload={'event_id':eid,'mission_id':mission_id,'event_type':event_type,'actor':actor,'details':details,'created_at':now,'previous_hash':ph}
        eh=_hash(payload)
        self.db.execute('INSERT INTO phase12_mission_events_281 VALUES(?,?,?,?,?,?,?,?)',(eid,mission_id,event_type,actor,_canon(details),now,ph,eh))
        return eid

    def create_mission(self,*,case_id,objective,mission_type='hybrid_osint',max_cycles=3,max_queries=8,max_results=8,actor=None):
        self._case(case_id); actor=actor or self.actor; objective=' '.join((objective or '').split())
        if len(objective)<8: raise ValueError('objective too short')
        if PROHIBITED.search(objective): raise ValueError('mission contains prohibited access/contact/purchase instruction')
        max_cycles=max(1,min(int(max_cycles),5)); max_queries=max(1,min(int(max_queries),12)); max_results=max(1,min(int(max_results),12))
        if mission_type not in {'public_web','darkweb_analysis','hybrid_osint','local_analysis'}: raise ValueError('invalid mission type')
        mid=_id('mission281'); now=_now(); payload={'case_id':case_id,'objective':objective,'mission_type':mission_type,'max_cycles':max_cycles,'max_queries':max_queries,'max_results':max_results}
        self.db.execute('INSERT INTO phase12_missions_281 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,case_id,objective,mission_type,'bounded_after_ok',max_cycles,max_queries,max_results,'planned','','',actor,now,_hash(payload)))
        steps=self._plan_steps(mid,mission_type,objective)
        self._event(mid,'mission_planned',actor,{'steps':len(steps),'external_execution_authorized':False,'budget':{'cycles':max_cycles,'queries':max_queries,'results_per_query':max_results}})
        return {'mission_id':mid,'status':'planned','requires_ok':True,'steps':steps,'direct_darkweb_fetch_enabled':False,'automatic_contact':False}

    def _plan_steps(self,mission_id,mission_type,objective):
        specs=[('scope','local','Scope, known entities, evidence gaps and disconfirming questions establish.',0),
               ('research_plan','local','Generate bounded search plan and source classes from the mission objective.',0)]
        if mission_type in {'public_web','hybrid_osint'}:
            specs.append(('public_collection','public_web','Execute only the explicitly approved public-web research wave through existing governed providers.',1))
        if mission_type in {'darkweb_analysis','hybrid_osint'}:
            specs.append(('darkweb_intake','darkweb_import','Analyze investigator-supplied onion/dark-web artifacts; direct onion fetching remains disabled in Build 281.',0))
        specs += [('fusion','local','Fuse collected/imported evidence, preserve provenance and contradictions.',0),
                  ('red_team','local','Seek counterevidence and identify unsupported assertions.',0),
                  ('checkpoint','local','Stop at budget/uncertainty boundary and return control to the lead investigator.',0)]
        out=[]
        for no,(typ,surface,desc,external) in enumerate(specs,1):
            sid=_id('step281'); payload={'mission_id':mission_id,'step_no':no,'type':typ,'surface':surface,'description':desc,'external':external}
            self.db.execute('INSERT INTO phase12_mission_steps_281 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,mission_id,no,typ,surface,desc,external,'planned','',_now(),_hash(payload)))
            out.append({'step_id':sid,'step_no':no,'step_type':typ,'surface':surface,'description':desc,'requires_external_access':bool(external)})
        return out

    def approve_mission(self,*,mission_id,confirmation,approved_by=None):
        row=self.db.one('SELECT * FROM phase12_missions_281 WHERE mission_id=?',(mission_id,))
        if not row: raise KeyError('mission not found')
        if str(confirmation).strip().upper()!='OK': raise PermissionError('explicit OK of lead investigator required')
        approved_by=approved_by or self.actor
        if row['status'] not in {'planned','paused'}: raise ValueError('mission is not awaiting approval')
        self.db.execute("UPDATE phase12_missions_281 SET status='authorized',approved_by=?,approved_at=? WHERE mission_id=?",(approved_by,_now(),mission_id))
        self._event(mission_id,'lead_investigator_ok',approved_by,{'scope':row['mission_type'],'max_cycles':row['max_cycles'],'max_queries':row['max_queries'],'max_results':row['max_results']})
        return {'mission_id':mission_id,'status':'authorized','bounded_autonomy':True,'max_cycles':row['max_cycles'],'max_queries':row['max_queries'],'max_results':row['max_results'],'direct_darkweb_fetch_enabled':False}

    def run_authorized_cycle(self,*,mission_id,actor=None,execute_public_web=False,provider=''):
        actor=actor or self.actor; m=self.db.one('SELECT * FROM phase12_missions_281 WHERE mission_id=?',(mission_id,))
        if not m: raise KeyError('mission not found')
        if m['status']!='authorized': raise PermissionError('mission requires lead investigator OK')
        past=self.db.one("SELECT COUNT(*) n FROM phase12_mission_events_281 WHERE mission_id=? AND event_type='autonomous_cycle_completed'",(mission_id,))['n']
        if int(past)>=int(m['max_cycles']):
            self.db.execute("UPDATE phase12_missions_281 SET status='paused' WHERE mission_id=?",(mission_id,)); self._event(mission_id,'budget_stop',actor,{'cycles_used':past})
            return {'mission_id':mission_id,'status':'paused','reason':'cycle_budget_exhausted','new_ok_required':True}
        request=m['objective'] if re.match(r'(?i)^\\s*(suche|recherchiere|finde|durchsuche|search)\b',m['objective']) else 'Suche '+m['objective']
        run=self.research263.create_research_run(case_id=m['case_id'],user_request=request,auto_open=False,actor=actor)
        execution={'status':'planned_only','external_collection':False}
        if execute_public_web and m['mission_type'] in {'public_web','hybrid_osint'}:
            execution=self.execution264.approve_and_execute(case_id=m['case_id'],run_id=run['run_id'],confirmation='OK',approved_by=m['approved_by'] or actor,provider=provider,max_queries=int(m['max_queries']),max_results_per_query=int(m['max_results']))
        self._event(mission_id,'autonomous_cycle_completed',actor,{'cycle_no':int(past)+1,'research_run_id':run['run_id'],'external_collection':bool(execute_public_web),'execution_status':execution.get('status','')})
        return {'mission_id':mission_id,'cycle_no':int(past)+1,'research_run_id':run['run_id'],'research_plan':run,'execution':execution,'bounded':True,'new_external_scope_requires_new_ok':True if m['mission_type']=='darkweb_analysis' else False}

    def stop_mission(self,*,mission_id,actor=None,reason='lead investigator stop'):
        actor=actor or self.actor; m=self.db.one('SELECT * FROM phase12_missions_281 WHERE mission_id=?',(mission_id,))
        if not m: raise KeyError('mission not found')
        self.db.execute("UPDATE phase12_missions_281 SET status='stopped' WHERE mission_id=?",(mission_id,)); self._event(mission_id,'mission_stopped',actor,{'reason':reason})
        return {'mission_id':mission_id,'status':'stopped'}

    def ingest_darkweb_artifact(self,*,case_id,source_locator,title,observed_text,mission_id='',actor=None):
        self._case(case_id); actor=actor or self.actor; loc=' '.join((source_locator or '').split())
        text=(observed_text or '').strip()
        if not loc or not text: raise ValueError('source locator and observed text required')
        host=(urlsplit(loc if '://' in loc else 'http://'+loc).hostname or '').lower()
        locator_class='onion' if host.endswith('.onion') else 'darkweb_reference'
        aid=_id('dwart281'); ch=hashlib.sha256(text.encode('utf-8')).hexdigest(); risk='high' if PROHIBITED.search(text) else 'review_required'
        payload={'case_id':case_id,'mission_id':mission_id,'locator':loc,'class':locator_class,'title':title,'content_sha256':ch,'risk':risk}
        self.db.execute('INSERT INTO darkweb_artifacts_281 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,mission_id,loc,locator_class,title.strip(),text,'investigator_supplied_offline',ch,risk,'unreviewed',actor,_now(),_hash(payload)))
        if mission_id:self._event(mission_id,'darkweb_artifact_ingested',actor,{'artifact_id':aid,'locator_class':locator_class,'content_sha256':ch})
        return {'artifact_id':aid,'locator_class':locator_class,'content_sha256':ch,'risk_class':risk,'network_fetch_performed':False,'file_execution_performed':False}

    def analyze_darkweb_artifact(self,*,artifact_id,actor=None):
        a=self.db.one('SELECT * FROM darkweb_artifacts_281 WHERE artifact_id=?',(artifact_id,))
        if not a: raise KeyError('artifact not found')
        text=a['observed_text']; inds=[]
        for kind,pat in INDICATORS:
            for value in pat.findall(text):
                if len(inds)>=30: break
                inds.append({'type':kind,'value':value[:160]})
        prohibited=len(PROHIBITED.findall(text))
        caveats=['Offline analysis of investigator-supplied material; EagleEye did not fetch or authenticate the remote service.', 'Indicators are leads, not identity proof; corroborate with independent evidence.']
        summary=f"Offline dark-web artifact analysis: {len(inds)} structured indicator(s) detected; prohibited-action signal count={prohibited}. Provenance retained by SHA-256."
        xid=_id('dwan281'); payload={'artifact_id':artifact_id,'indicator_count':len(inds),'prohibited':prohibited,'summary':summary,'caveats':caveats}
        self.db.execute('INSERT INTO darkweb_analysis_281 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(xid,artifact_id,a['case_id'],summary,len(inds),_canon(inds),_canon(caveats),prohibited,'needs_human_review',_now(),_hash(payload)))
        if a['mission_id']:self._event(a['mission_id'],'darkweb_artifact_analyzed',actor or self.actor,{'artifact_id':artifact_id,'analysis_id':xid,'indicator_count':len(inds)})
        return {'analysis_id':xid,'artifact_id':artifact_id,'summary':summary,'indicators':inds,'caveats':caveats,'human_review_required':True,'network_fetch_performed':False}

    def infrastructure_snapshot(self):
        integrity=next(iter(self.db.one('PRAGMA integrity_check').values())); fk=len(self.db.all('PRAGMA foreign_key_check'))
        free=int(shutil.disk_usage(self.base_dir).free//(1024*1024)); write_ok=1
        try:
            p=self.base_dir/'.build281_write_test'; p.write_text('ok',encoding='utf-8'); p.unlink()
        except Exception: write_ok=0
        p11=bool(self.build280.qualified_gate()['release_ready']); ready=bool(integrity=='ok' and fk==0 and write_ok and free>=128 and p11)
        sid=_id('infra281'); payload={'integrity':integrity,'fk':fk,'write':write_ok,'free_mb':free,'p11':p11,'mission_controller':True,'direct_darkweb_fetch':False,'status':'ready' if ready else 'degraded'}
        self.db.execute('INSERT INTO infrastructure_snapshots_281 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,integrity,fk,write_ok,free,int(p11),1,0,payload['status'],_now(),_hash(payload)))
        return {'snapshot_id':sid,'sqlite_integrity':integrity,'foreign_key_violations':fk,'db_write_ok':bool(write_ok),'free_disk_mb':free,'phase11_gate':p11,'mission_controller_ready':True,'direct_darkweb_fetch_enabled':False,'status':payload['status']}

    def ai_metrics(self):
        n=self.db.one("SELECT COUNT(*) n FROM ai_phase12_benchmarks_281 WHERE review_status='reviewed'")['n']
        return {'reviewed_phase12_benchmarks':n,'explicit_ok_gate':True,'bounded_autonomy':True,'followup_planning':True,'automatic_model_activation':False}
    def opsec_metrics(self):
        n=self.db.one("SELECT COUNT(*) n FROM opsec_phase12_controls_281 WHERE review_status='verified'")['n']
        return {'verified_phase12_controls':n,'direct_darkweb_fetch_enabled':0,'automatic_tor_reconfiguration':0,'automatic_contact':0,'automatic_purchase':0,'automatic_publication':0}
    def qualified_gate(self):
        a=self.ai_metrics(); o=self.opsec_metrics(); p=self.build280.qualified_gate(); inf=self.infrastructure_snapshot()
        g={'build':'281.0','main_goal':True,'ai_delta':a['reviewed_phase12_benchmarks']>=16,'opsec_delta':o['verified_phase12_controls']>=16,'infrastructure_ready':inf['status']=='ready','parent_build_gate':p['release_ready'],'bounded_autonomy':a['bounded_autonomy'] and a['explicit_ok_gate'],'darkweb_boundary':o['direct_darkweb_fetch_enabled']==0}
        g['release_ready']=all(g[k] for k in ('main_goal','ai_delta','opsec_delta','infrastructure_ready','parent_build_gate','bounded_autonomy','darkweb_boundary'))
        return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ''),quote=True)
        missions=self.db.all('SELECT * FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,))
        rows=''.join(f"<tr><td><code>{e(m['mission_id'])}</code></td><td>{e(m['mission_type'])}</td><td>{e(m['status'])}</td><td>{e(m['objective'][:110])}</td><td><form method='post' action='/build281/approve'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(m['mission_id'])}'><input type='hidden' name='confirmation' value='OK'><button>OK · Mission freigeben</button></form></td></tr>" for m in missions)
        return f"""<section class='card'><h2>Phase 12 · Mission Controller 281</h2><p><b>Plan → Haupt­ermittler-OK → begrenzte autonome Zyklen → Checkpoint.</b> Dark-Web-Material wird in Build 281 offline importiert und analysiert; direkte Onion-Abfrage und automatische Tor-/Identitätsänderungen bleiben deaktiviert.</p><form method='post' action='/build281/mission'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><label>Ermittlungsziel <input name='objective' size='90' required></label><select name='mission_type'><option value='hybrid_osint'>Hybrid OSINT</option><option value='public_web'>Public Web</option><option value='darkweb_analysis'>Darkweb Analysis</option><option value='local_analysis'>Local Analysis</option></select><button>Mission planen</button></form><table><tr><th>Mission</th><th>Typ</th><th>Status</th><th>Ziel</th><th>Freigabe</th></tr>{rows or '<tr><td colspan="5">Noch keine Phase-12-Mission.</td></tr>'}</table><pre>{e(_canon(self.qualified_gate()))}</pre></section>"""
