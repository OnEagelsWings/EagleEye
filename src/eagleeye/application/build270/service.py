from __future__ import annotations
import hashlib,html,json,os,re,time,uuid
from typing import Any
from urllib.parse import urlsplit,urlencode
from urllib.request import Request,urlopen

def _now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
def _normq(v): return re.sub(r'\s+',' ',str(v or '').strip())
def _safe_query(q):
    return not re.search(r'(?i)\b(bypass|captcha|paywall\s*(?:umgehen|bypass)|login\s*(?:umgehen|bypass)|credential|password|passwort)\b',q or '')

class Build270IntelligenceGapsCollectionService:
    BUILD='270.0'
    def __init__(self,db:Any,audit:Any,*,analysis269:Any,research263:Any,execution264:Any,temporal265:Any,network266:Any,paths267:Any,
                 hypothesis268:Any,compatibility:Any,training:Any,actor:str='local-analyst'):
        self.db=db;self.audit=audit;self.analysis269=analysis269;self.research263=research263;self.execution264=execution264
        self.temporal265=temporal265;self.network266=network266;self.paths267=paths267;self.hypothesis268=hypothesis268
        self.compatibility=compatibility;self.training=training;self.actor=actor

    def _run(self,case_id,run_id):
        row=self.db.one('SELECT * FROM ai_research_runs_263 WHERE case_id=? AND run_id=?',(case_id,run_id))
        if not row: raise KeyError('research run not found')
        return row

    def _collect_gap_sources(self,case_id,run_id):
        out=[]
        def add(kind,ref,category,priority,title,question,evidence=None):
            q=_normq(question)
            if not q:return
            out.append({'origin_kind':kind,'origin_ref':ref or '', 'category':category,'priority':priority,'title':title,
                        'question':q,'evidence_refs':evidence or [],'discriminating_value':'high' if priority<=20 else 'moderate' if priority<=40 else 'low'})
        ach=self.db.one('SELECT * FROM ach_briefs_269 WHERE case_id=? AND run_id=? ORDER BY rowid DESC LIMIT 1',(case_id,run_id))
        if ach:
            for i,g in enumerate(json.loads(ach['research_gaps_json'])):add('ach269',ach['brief_id'],'discriminating_evidence',10+i,'ACH discrimination gap',g)
            for i,f in enumerate(json.loads(ach['followup_queries_json'])):add('ach269',ach['brief_id'],'discriminating_evidence',10+i,'ACH follow-up',f.get('query',''))
        hb=self.db.one('SELECT * FROM hypothesis_briefs_268 WHERE case_id=? AND run_id=? ORDER BY rowid DESC LIMIT 1',(case_id,run_id))
        if hb:
            for i,g in enumerate(json.loads(hb['research_gaps_json'])):add('hypothesis268',hb['brief_id'],'hypothesis_gap',20+i,'Hypothesis gap',g)
            for i,f in enumerate(json.loads(hb['followup_queries_json'])):add('hypothesis268',hb['brief_id'],'hypothesis_gap',20+i,'Hypothesis follow-up',f.get('query',''))
        tb=self.db.one('SELECT * FROM timeline_briefs_265 WHERE case_id=? AND run_id=? ORDER BY rowid DESC LIMIT 1',(case_id,run_id))
        if tb:
            for i,f in enumerate(json.loads(tb['followup_queries_json'])):add('timeline265',tb['brief_id'],'temporal_gap',25+i,'Temporal contradiction gap',f.get('query',''))
        pb=self.db.one('SELECT * FROM ai_path_briefs_267 WHERE case_id=? AND run_id=? ORDER BY rowid DESC LIMIT 1',(case_id,run_id))
        if pb:
            for i,g in enumerate(json.loads(pb['research_gaps_json'])):add('paths267',pb['brief_id'],'network_gap',30+i,'Network path gap',g)
            for i,f in enumerate(json.loads(pb['followup_queries_json'])):add('paths267',pb['brief_id'],'network_gap',30+i,'Network path follow-up',f.get('query',''))
        nb=self.db.one('SELECT * FROM ai_network_briefs_266 WHERE case_id=? AND run_id=? ORDER BY rowid DESC LIMIT 1',(case_id,run_id))
        if nb:
            for i,f in enumerate(json.loads(nb['followup_queries_json'])):add('network266',nb['brief_id'],'relationship_gap',35+i,'Relationship review gap',f.get('query',''))
        if not out:
            add('fallback',run_id,'source_gap',50,'Independent primary-source gap','Prüfe unabhängige Primärquellen und Gegenbelege zur zentralen Forschungsfrage des Falls.')
        return out

    def build_collection_plan(self,*,case_id,parent_run_id,actor=None,max_tasks_per_wave=3,max_waves=5):
        actor=actor or self.actor;run=self._run(case_id,parent_run_id)
        old=self.db.one('SELECT plan_id FROM collection_plans_270 WHERE case_id=? AND parent_run_id=?',(case_id,parent_run_id))
        if old:return self.plan(old['plan_id'])
        raw=self._collect_gap_sources(case_id,parent_run_id)
        seen=set();gaps=[]
        for g in sorted(raw,key=lambda x:(x['priority'],x['question'])):
            key=_normq(g['question']).casefold()
            if key in seen:continue
            seen.add(key)
            gid=_id('gap270');payload={**g,'parent_run_id':parent_run_id}
            self.db.execute('INSERT INTO intelligence_gaps_270 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (gid,case_id,parent_run_id,g['origin_kind'],g['origin_ref'],g['category'],g['title'],g['question'],int(g['priority']),g['discriminating_value'],
                 _canon(g['evidence_refs']),'open',actor,_now(),_hash(payload)))
            gaps.append({'gap_id':gid,**g})
        pid=_id('plan270');mt=max(1,min(int(max_tasks_per_wave),5));mw=max(1,min(int(max_waves),8))
        self.db.execute('INSERT INTO collection_plans_270 VALUES(?,?,?,?,?,?,?,?,?,?)',
            (pid,case_id,parent_run_id,f'Collection Plan: {run["user_request"][:120]}','planned',mt,mw,actor,_now(),_hash({'run':parent_run_id,'mt':mt,'mw':mw})))
        qseen=set();tasks=[]
        for g in gaps:
            q=g['question']
            if not q.lower().startswith(('suche ','recherchiere ','finde ','durchsuche ')):q='Suche '+q
            q=_normq(q)
            if not _safe_query(q):continue
            qk=q.casefold()
            if qk in qseen:continue
            qseen.add(qk);tid=_id('ctask270');priority=int(g['priority']);max_results=6 if priority<=20 else 5 if priority<=40 else 4
            self.db.execute('INSERT INTO collection_tasks_270 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (tid,pid,g['gap_id'],case_id,parent_run_id,q,g['title'],'public_primary_first',priority,max_results,1,'planned',_now(),_hash({'q':q,'p':priority})))
            tasks.append({'task_id':tid,'gap_id':g['gap_id'],'query_text':q,'objective':g['title'],'priority':priority,'max_results':max_results})
        self._event(case_id,'collection_plan_created','collection_plan',pid,actor,{'gaps':len(gaps),'tasks':len(tasks),'max_tasks_per_wave':mt})
        return self.plan(pid)

    def plan(self,plan_id):
        p=self.db.one('SELECT * FROM collection_plans_270 WHERE plan_id=?',(plan_id,))
        if not p:return None
        gaps=self.db.all('SELECT * FROM intelligence_gaps_270 WHERE case_id=? AND parent_run_id=? ORDER BY priority,gap_id',(p['case_id'],p['parent_run_id']))
        tasks=self.db.all('SELECT * FROM collection_tasks_270 WHERE plan_id=? ORDER BY priority,task_id',(plan_id,))
        executed={r['task_id'] for r in self.db.all('SELECT task_id FROM collection_wave_tasks_270 WHERE wave_id IN (SELECT wave_id FROM collection_waves_270 WHERE plan_id=?)',(plan_id,))}
        return {**p,'gaps':gaps,'tasks':tasks,'pending_tasks':[t for t in tasks if t['task_id'] not in executed],
                'external_wave_requires_ok':True,'automatic_continuous_collection':False}

    def review_plan(self,*,case_id,plan_id,decision,rationale,reviewer=None):
        p=self.db.one('SELECT * FROM collection_plans_270 WHERE plan_id=?',(plan_id,))
        if not p or p['case_id']!=case_id:raise KeyError('plan')
        reviewer=reviewer or self.actor
        if reviewer==p['created_by']:raise ValueError('independent reviewer required')
        if decision not in {'retain_plan','needs_revision','reject_plan'}:raise ValueError('invalid decision')
        rid=_id('cprev270');self.db.execute('INSERT INTO collection_plan_reviews_270 VALUES(?,?,?,?,?,?,?,?)',
            (rid,plan_id,case_id,decision,rationale,reviewer,_now(),_hash({'d':decision,'r':rationale})))
        return {'review_id':rid,'decision':decision}

    def stage_training_candidate(self,*,case_id,plan_id,actor=None):
        p=self.db.one('SELECT * FROM collection_plans_270 WHERE plan_id=? AND case_id=?',(plan_id,case_id))
        rv=self.db.one('SELECT * FROM collection_plan_reviews_270 WHERE plan_id=?',(plan_id,))
        if not p or not rv or rv['decision']!='retain_plan':raise PermissionError('independently retained plan required')
        tasks=self.db.all('SELECT query_text,objective,priority FROM collection_tasks_270 WHERE plan_id=? ORDER BY priority',(plan_id,))
        return self.training.add_example(case_id=case_id,instruction='Prioritize intelligence gaps into a bounded collection plan. New external waves require explicit user approval.',
            response=_canon({'tasks':tasks,'continuous_collection':False}),context={'build':'270.0','one_ok_one_wave':True,'human_review_required':True},
            evidence_refs=[],language='de',source_type='build270_reviewed_collection_plan',source_ref=plan_id,created_by=actor or self.actor,
            confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN')

    def preflight_gateway(self,*,case_id,parent_run_id,opsec_mode='standard',provider='browser_queue'):
        self._run(case_id,parent_run_id);mode=opsec_mode if opsec_mode in {'standard','high_risk'} else 'standard'
        raw=os.environ.get('EAGLEEYE_RESEARCH_GATEWAY','').strip();p=urlsplit(raw) if raw else None
        configured=bool(p and p.scheme in {'http','https'} and p.hostname)
        local=bool(configured and p.hostname in {'127.0.0.1','localhost','::1'})
        creds=bool(configured and (p.username or p.password));creds_absent=int(not creds)
        direct_blocked=int(mode=='high_risk' and provider!='local_gateway')
        local_checks=self.analysis269.preflight_leaks(case_id=case_id,run_id=parent_run_id,mode='standard',route_mode='direct')
        controls_ok=int(local_checks['profile_present'] and local_checks['profile_unique'] and local_checks['webrtc_disabled'] and
                        local_checks['dns_prefetch_disabled'] and local_checks['speculative_connections_disabled'] and local_checks['referrer_disabled'] and
                        not local_checks['cookie_residue'] and not local_checks['history_residue'])
        notes=[]
        if mode=='high_risk':
            if provider!='local_gateway':notes.append('high-risk collection requires provider=local_gateway')
            if not configured:notes.append('EAGLEEYE_RESEARCH_GATEWAY is not configured')
            elif not local:notes.append('research gateway must resolve to localhost/loopback only')
            if creds:notes.append('gateway URL must not embed credentials')
            if not controls_ok:notes.append('Build269 local browser/privacy controls failed')
        result='blocked' if mode=='high_risk' and (provider!='local_gateway' or not configured or not local or creds or not controls_ok) else 'pass'
        if mode=='high_risk' and result=='pass':
            result='pass_with_warning';notes.append('local gateway configured; gateway upstream route remains outside EagleEye visibility and is not claimed anonymous or leak-free')
        if mode=='standard' and provider!='local_gateway':notes.append('standard provider path; parent Build269 preflight remains authoritative')
        pid=_id('gwpf270');payload={'mode':mode,'provider':provider,'configured':configured,'local':local,'creds':creds,'controls_ok':controls_ok,'result':result}
        self.db.execute('INSERT INTO opsec_gateway_preflight_270 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (pid,case_id,parent_run_id,mode,provider,int(configured),int(local),creds_absent,direct_blocked,controls_ok,
             'local_gateway_upstream_unverified' if local else 'not_applicable',result,_canon(notes),_now(),_hash(payload)))
        self._event(case_id,'gateway_preflight','research_run',parent_run_id,self.actor,{'result':result,'mode':mode,'provider':provider})
        return {'preflight_id':pid,'result':result,'mode':mode,'provider':provider,'gateway_configured':configured,'gateway_local_only':local,
                'gateway_credentials_absent':bool(creds_absent),'local_profile_controls_ok':bool(controls_ok),
                'upstream_route_status':'local_gateway_upstream_unverified' if local else 'not_applicable','notes':notes,
                'network_anonymity_verified':False,'dns_leak_free_verified':False,'automatic_ip_rotation':False}

    def _gateway_search(self,query,limit):
        raw=os.environ.get('EAGLEEYE_RESEARCH_GATEWAY','').strip();p=urlsplit(raw)
        if not raw or p.hostname not in {'127.0.0.1','localhost','::1'} or p.username or p.password:raise RuntimeError('safe local research gateway is not configured')
        sep='&' if p.query else '?';url=raw+sep+urlencode({'q':query,'limit':int(limit)})
        req=Request(url,headers={'Accept':'application/json','User-Agent':'EagleEye-LocalGateway/270'})
        try:
            with urlopen(req,timeout=12) as r:data=json.loads(r.read(2_000_000).decode('utf-8','replace'))
        except Exception as exc:
            raise RuntimeError(f'local research gateway unavailable: {type(exc).__name__}') from exc
        rows=data.get('results',[]) if isinstance(data,dict) else data if isinstance(data,list) else []
        out=[];seen=set()
        for item in rows[:int(limit)]:
            if not isinstance(item,dict):continue
            url=str(item.get('url') or '').strip();title=str(item.get('title') or url)[:500];snippet=str(item.get('snippet') or item.get('description') or '')[:5000]
            if not url.startswith(('http://','https://')):continue
            key=url.split('#',1)[0]
            if key in seen:continue
            seen.add(key);out.append({'url':url,'title':title,'snippet':snippet})
        return out

    def _analyze_imported_child(self,case_id,child_run_id,actor):
        self.execution264.reconstruct_timeline(case_id=case_id,run_id=child_run_id,batch_id='collection_wave_270',actor=actor)
        temporal=self.temporal265.analyze_run(case_id=case_id,run_id=child_run_id,actor=actor)
        network=self.network266.analyze_run(case_id=case_id,run_id=child_run_id,actor=actor)
        risk=self.paths267.analyze_query_risk(case_id=case_id,run_id=child_run_id,route_mode='local_gateway')
        paths=self.paths267.analyze_paths(case_id=case_id,run_id=child_run_id,actor=actor)
        hyp=self.hypothesis268.build_hypothesis_set(case_id=case_id,run_id=child_run_id,actor=actor)
        ach=self.analysis269.build_ach(case_id=case_id,run_id=child_run_id,actor=actor)
        return {'temporal':temporal,'network':network,'query_risk':risk,'paths':paths,'hypothesis':hyp,'ach':ach}

    def approve_and_execute_wave(self,*,case_id,plan_id,confirmation,approved_by=None,provider='browser_queue',opsec_mode='standard',task_budget=3,result_budget=18):
        if str(confirmation).strip().upper()!='OK':raise PermissionError('explicit OK required')
        p=self.db.one('SELECT * FROM collection_plans_270 WHERE plan_id=?',(plan_id,))
        if not p or p['case_id']!=case_id:raise KeyError('plan')
        approved_by=approved_by or self.actor;tb=max(1,min(int(task_budget),p['max_tasks_per_wave'],5));rb=max(1,min(int(result_budget),40))
        prev=(self.db.one('SELECT COUNT(*) n FROM collection_waves_270 WHERE plan_id=?',(plan_id,)) or {'n':0})['n']
        if prev>=p['max_waves']:raise RuntimeError('collection plan wave limit reached')
        pre=self.preflight_gateway(case_id=case_id,parent_run_id=p['parent_run_id'],opsec_mode=opsec_mode,provider=provider)
        if pre['result']=='blocked':raise RuntimeError('Build270 gateway preflight blocked collection wave: '+'; '.join(pre['notes']))
        used={r['task_id'] for r in self.db.all('SELECT task_id FROM collection_wave_tasks_270 WHERE wave_id IN (SELECT wave_id FROM collection_waves_270 WHERE plan_id=?)',(plan_id,))}
        tasks=[t for t in self.db.all('SELECT * FROM collection_tasks_270 WHERE plan_id=? ORDER BY priority,task_id',(plan_id,)) if t['task_id'] not in used][:tb]
        if not tasks:raise ValueError('no pending collection tasks')
        wave_no=prev+1;wid=_id('wave270')
        self.db.execute('INSERT INTO collection_waves_270 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (wid,plan_id,case_id,p['parent_run_id'],wave_no,provider,opsec_mode,'local_gateway' if provider=='local_gateway' else 'parent_provider',tb,rb,
             'approved_once',approved_by,_now(),_hash({'plan':plan_id,'wave':wave_no,'provider':provider,'tb':tb,'rb':rb})))
        total=0;children=[];ach_count=0
        for task in tasks:
            remaining=max(0,rb-total)
            if remaining<=0:break
            child=self.research263.create_research_run(case_id=case_id,user_request=task['query_text'],auto_open=False,actor=approved_by)
            child_id=child['run_id'];imported=0;summary=''
            try:
                if opsec_mode=='high_risk':
                    if provider!='local_gateway':raise RuntimeError('high-risk wave requires local_gateway')
                    results=self._gateway_search(task['query_text'],min(task['max_results'],remaining))
                    qid=child['queries'][0]['query_id']
                    for item in results:
                        self.research263.add_finding(case_id=case_id,run_id=child_id,query_id=qid,title=item['title'],url=item['url'],snippet=item['snippet'],
                            source_class='local_gateway_public',evidence_ref='',stance='context_only',actor=approved_by)
                    imported=len(results);analysis=self._analyze_imported_child(case_id,child_id,approved_by);ach_count+=1;summary=analysis['ach']['summary']
                else:
                    out=self.analysis269.execute_enhanced(case_id=case_id,run_id=child_id,confirmation='OK',approved_by=approved_by,provider=provider,
                        max_queries=1,max_results_per_query=min(task['max_results'],remaining),opsec_mode='standard')
                    imported=int(out.get('deduplicated_count') or out.get('raw_result_count') or 0);ach_count+=1 if out.get('ach_269') else 0;summary=(out.get('ach_269') or {}).get('summary','')
                status='completed'
            except Exception as exc:
                status='failed';summary=f'{type(exc).__name__}: {str(exc)[:500]}'
                if opsec_mode=='high_risk':
                    # No direct-provider fallback is allowed after local-gateway failure.
                    imported=0
            total+=imported;wtid=_id('wtask270')
            self.db.execute('INSERT INTO collection_wave_tasks_270 VALUES(?,?,?,?,?,?,?,?,?)',
                (wtid,wid,task['task_id'],child_id,status,imported,summary,_now(),_hash({'wave':wid,'task':task['task_id'],'child':child_id,'status':status,'n':imported})))
            children.append({'task_id':task['task_id'],'child_run_id':child_id,'status':status,'imported_results':imported,'analysis_summary':summary})
            if status=='failed' and opsec_mode=='high_risk':break
        remaining_count=len([t for t in self.plan(plan_id)['pending_tasks'] if t['task_id'] not in {x['task_id'] for x in children}])
        next_rec=int(remaining_count>0);brief_id=_id('wavebrief270')
        status='completed' if all(x['status']=='completed' for x in children) else 'partial_or_failed'
        summary=f'Collection wave {wave_no}: {len(children)} child run(s), {total} imported result(s), {ach_count} ACH matrix/matrices. Remaining planned gaps/tasks: {remaining_count}. A further external wave requires a new explicit OK.'
        self.db.execute('INSERT INTO collection_wave_briefs_270 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (brief_id,wid,case_id,p['parent_run_id'],len(children),len(children),total,ach_count,summary,remaining_count,next_rec,status,_now(),_hash({'wave':wid,'n':total,'remaining':remaining_count})))
        self._event(case_id,'collection_wave_executed','collection_wave',wid,approved_by,{'wave_no':wave_no,'tasks':len(children),'results':total,'remaining':remaining_count,'status':status})
        return {'wave_id':wid,'wave_no':wave_no,'status':status,'children':children,'imported_result_count':total,'ach_matrix_count':ach_count,
                'remaining_gap_count':remaining_count,'next_wave_recommended':bool(next_rec),'requires_new_ok_for_next_wave':True,
                'gateway_preflight':pre,'continuous_background_collection':False,'automatic_truth_selection':False}

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_collection_benchmarks_270 WHERE review_status='reviewed'") or {'n':0})['n']
        fam=(self.db.one('SELECT COUNT(DISTINCT task_family) n FROM ai_collection_benchmarks_270') or {'n':0})['n']
        return {'reviewed_benchmarks':n,'task_families':fam,'intelligence_gap_planning':True,'bounded_collection_waves':True,
                'analysis_feedback_loop':True,'continuous_background_collection':False,'automatic_model_activation':False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_270 WHERE review_status='verified'") or {'n':0})['n']
        return {'verified_controls':n,'local_gateway_preflight':1,'high_risk_direct_provider_block':1,'gateway_fail_closed':1,
                'network_anonymity_claim':0,'dns_leak_free_claim':0,'automatic_ip_rotation':0,'disposable_email_generation':0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={'build':'270.0','main_goal':bool(self.db.one("SELECT name FROM sqlite_master WHERE name='intelligence_gaps_270'")),
           'ai_delta':a['reviewed_benchmarks']>=46 and a['task_families']>=20,
           'opsec_delta':o['verified_controls']>=44 and o['local_gateway_preflight']==1,
           'capability_regression':'ach_analysis_269' in caps and 'defensive_leak_preflight_269' in caps,
           'parent_build_gate':self.analysis269.qualified_gate()['release_ready']}
        g['release_ready']=all(g[k] for k in ('main_goal','ai_delta','opsec_delta','capability_regression','parent_build_gate'));return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ''),quote=True)
        plans=self.db.all('SELECT * FROM collection_plans_270 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,))
        rows=[]
        for p in plans:
            pending=len(self.plan(p['plan_id'])['pending_tasks'])
            rows.append(f"<tr><td><code>{e(p['plan_id'])}</code></td><td>{e(p['title'])}</td><td>{pending}</td><td><form method='post' action='/build270/wave'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='plan_id' value='{e(p['plan_id'])}'><input type='hidden' name='confirmation' value='OK'><button>OK · nächste begrenzte Welle</button></form></td></tr>")
        waves=self.db.all('SELECT * FROM collection_wave_briefs_270 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,))
        wrows=''.join(f"<tr><td>{e(w['wave_id'])}</td><td>{e(w['task_count'])}</td><td>{e(w['imported_result_count'])}</td><td>{e(w['remaining_gap_count'])}</td><td>{e(w['summary'])}</td></tr>" for w in waves)
        return f"""<section class='card'><h2>Intelligence Gaps & Collection Plan · Build 270</h2>
        <p><b>ACH/Timeline/Network/Hypothesis gaps → Priorisierung → Collection Plan → OK → eine begrenzte Wave → vollständige Analyse-Rückführung.</b></p>
        <p>Jede weitere externe Recherchewelle benötigt erneut OK. Kein kontinuierlicher Hintergrund-Crawler.</p>
        <h3>Collection Plans</h3><table><tr><th>Plan</th><th>Titel</th><th>Pending Tasks</th><th>Wave</th></tr>{''.join(rows) or "<tr><td colspan='4'>Noch kein Plan.</td></tr>"}</table>
        <h3>Wave Briefs</h3><table><tr><th>Wave</th><th>Tasks</th><th>Results</th><th>Remaining</th><th>Brief</th></tr>{wrows or "<tr><td colspan='5'>Noch keine Collection Wave.</td></tr>"}</table>
        <h3>High-Risk Gateway</h3><p>High-Risk Collection akzeptiert nur <code>provider=local_gateway</code> mit credential-freiem <code>EAGLEEYE_RESEARCH_GATEWAY</code> auf localhost/loopback. Gateway-Ausfall führt nicht zu Direct-Fallback. Upstream-Anonymität/DNS-Leakfreiheit werden nicht behauptet.</p>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one('SELECT event_hash FROM build270_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(cid,));ph=prev['event_hash'] if prev else 'GENESIS'
        eid=_id('evt270');now=_now();data={'event_id':eid,'case_id':cid,'event_type':etype,'object_type':otype,'object_id':oid,'actor':actor,'payload':payload,'previous_hash':ph,'created_at':now}
        self.db.execute('INSERT INTO build270_events VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
