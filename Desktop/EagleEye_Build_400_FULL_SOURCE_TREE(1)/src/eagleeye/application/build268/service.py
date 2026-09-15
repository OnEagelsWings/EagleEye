from __future__ import annotations
import hashlib,html,json,os,re,time,uuid
from typing import Any
from urllib.parse import urlsplit

def _now():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def _id(p):return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256(_canon(v).encode()).hexdigest()

class Build268HypothesisLabService:
    BUILD='268.0'
    def __init__(self,db:Any,audit:Any,*,paths267:Any,research263:Any,compatibility:Any,training:Any,actor:str='local-analyst'):
        self.db=db;self.audit=audit;self.paths267=paths267;self.research263=research263;self.compatibility=compatibility;self.training=training;self.actor=actor

    def preflight_egress(self,*,case_id,run_id,provider='',opsec_mode='standard',route_mode='direct'):
        provider=(provider or 'browser_queue').strip();mode=opsec_mode if opsec_mode in {'standard','strict'} else 'standard'
        proxy=os.environ.get('EAGLEEYE_OUTBOUND_PROXY','').strip();p=urlsplit(proxy) if proxy else None
        route_ok=bool(p and p.scheme in {'http','https'} and p.hostname and not p.username and not p.password)
        verifiable=provider in {'brave','ollama_web'}
        browser_proxy=(provider=='browser_queue' and route_ok)
        direct=(route_mode=='direct')
        notes=[];result='pass'
        if mode=='strict':
            if provider=='searxng':result='blocked';notes.append('local SearXNG upstream egress is outside EagleEye and cannot be verified in strict mode')
            elif provider in {'brave','ollama_web'} and (direct or not route_ok):result='blocked';notes.append('strict external API egress requires credential-free EAGLEEYE_OUTBOUND_PROXY')
            elif provider=='browser_queue' and (route_mode!='user_configured_proxy' or not browser_proxy):result='blocked';notes.append('strict browser egress requires configured proxy route in ephemeral Firefox profile')
        else:
            if direct:notes.append('standard mode direct route: public IP visible')
        pid=_id('egpol268');payload={'mode':mode,'provider':provider,'route_mode':route_mode,'route_ok':route_ok,'result':result}
        self.db.execute('INSERT INTO opsec_egress_policies_268 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (pid,case_id,run_id,mode,provider,route_mode,int(mode=='strict'),int(mode!='strict'),int(provider=='browser_queue' and mode=='strict'),result,_now(),_hash(payload)))
        pf=_id('egpf268');pp={'route':route_ok,'verifiable':verifiable,'browser_proxy':browser_proxy,'direct':direct,'result':result}
        self.db.execute('INSERT INTO opsec_egress_preflight_268 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (pf,pid,case_id,run_id,provider,int(route_ok),int(verifiable),int(browser_proxy),int(direct),result,'; '.join(notes),_now(),_hash(pp)))
        self._event(case_id,'egress_preflight','research_run',run_id,self.actor,{'result':result,'mode':mode,'provider':provider,'route_mode':route_mode})
        return {'policy_id':pid,'preflight_id':pf,'result':result,'mode':mode,'provider':provider,'route_mode':route_mode,
                'route_configured':route_ok,'provider_route_verifiable':verifiable,'browser_proxy_configurable':browser_proxy,
                'direct_route_detected':direct,'notes':notes,'network_anonymity_verified':False}

    def build_hypothesis_set(self,*,case_id,run_id,research_question='',actor=None):
        actor=actor or self.actor
        old=self.db.one('SELECT set_id FROM hypothesis_sets_268 WHERE case_id=? AND run_id=?',(case_id,run_id))
        if old:return self.hypothesis_brief(old['set_id'])
        run=self.db.one('SELECT * FROM ai_research_runs_263 WHERE case_id=? AND run_id=?',(case_id,run_id))
        if not run:raise KeyError('research run')
        question=(research_question or run['user_request']).strip();sid=_id('hset268')
        self.db.execute('INSERT INTO hypothesis_sets_268 VALUES(?,?,?,?,?,?,?,?)',(sid,case_id,run_id,question,'analysis_basis',actor,_now(),_hash({'q':question})))
        specs=[
            ('H1','Direkte dokumentierte Beziehung/Erklärung',f'Die beobachteten Daten könnten eine direkte, durch unabhängige Quellen belegbare Beziehung oder Erklärung zur Forschungsfrage stützen.','working'),
            ('H2','Alternative Kontext-/Quellenabhängigkeits-Erklärung',f'Die beobachteten Muster könnten durch gemeinsame Quellen, administrative Routine, Kontextnähe oder andere nicht-kausale Erklärungen entstehen.','alternative'),
            ('H3','Unzureichende Evidenz / ungelöst',f'Die verfügbare Evidenz reicht derzeit nicht aus, um zwischen direkten und alternativen Erklärungen belastbar zu unterscheiden.','null_insufficient'),
        ]
        hyps=[]
        for label,title,statement,ht in specs:
            hid=_id('hyp268');self.db.execute('INSERT INTO hypotheses_268 VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (hid,sid,case_id,run_id,label,f'{title}: {statement}',ht,'unreviewed',actor,_now(),_hash({'label':label,'statement':statement})))
            hyps.append((label,hid))
        h=dict(hyps)
        findings=self.db.all('SELECT * FROM ai_research_findings_263 WHERE case_id=? AND run_id=? ORDER BY created_at',(case_id,run_id))
        for f in findings:
            if f['stance']=='supports':self._link(h['H1'],case_id,f['evidence_ref'],'supporting_candidate','finding','Finding was tagged supportive; this does not verify H1.')
            elif f['stance']=='contradicts':
                self._link(h['H1'],case_id,f['evidence_ref'],'contradicting_candidate','finding','Finding contradicts the working explanation.')
                self._link(h['H2'],case_id,f['evidence_ref'],'supporting_alternative','finding','Contradiction may support an alternative explanation.')
            else:self._link(h['H3'],case_id,f['evidence_ref'],'context','finding','Context evidence does not discriminate hypotheses.')
        paths=self.db.all('SELECT * FROM network_paths_267 WHERE case_id=? AND run_id=? ORDER BY hop_count LIMIT 20',(case_id,run_id))
        for p in paths:
            for ev in json.loads(p['evidence_refs_json']):self._link(h['H1'],case_id,ev,'context_path','network_path','Observed path is context only; topology is not coordination.')
        self._obs(h['H1'],case_id,'expected','Independent primary evidence should explicitly document the asserted relationship or event.')
        self._obs(h['H1'],case_id,'falsifying','Independent primary evidence explicitly contradicts the asserted relationship or chronology.')
        self._obs(h['H2'],case_id,'expected','Multiple apparently independent reports resolve to one origin, routine process, or non-causal shared context.')
        self._obs(h['H2'],case_id,'falsifying','Independent direct records establish a specific relationship that the context explanation cannot account for.')
        self._obs(h['H3'],case_id,'expected','Key claims remain unsupported by independent primary evidence after targeted review.')
        self._obs(h['H3'],case_id,'falsifying','Discriminating independent evidence clearly favors one explanation and withstands counterevidence review.')
        brief=self._brief(sid,case_id,run_id,actor)
        self._event(case_id,'hypothesis_set_created','hypothesis_set',sid,actor,{'hypotheses':3,'findings':len(findings),'paths':len(paths)})
        return brief

    def _link(self,hid,cid,ev,role,kind,rationale):
        if not ev:return
        if self.db.one('SELECT link_id FROM hypothesis_evidence_links_268 WHERE hypothesis_id=? AND evidence_ref=? AND role=?',(hid,ev,role)):return
        lid=_id('hlink268');self.db.execute('INSERT INTO hypothesis_evidence_links_268 VALUES(?,?,?,?,?,?,?,?,?)',
            (lid,hid,cid,ev,role,kind,rationale,_now(),_hash({'h':hid,'ev':ev,'role':role})))
    def _obs(self,hid,cid,typ,text):
        oid=_id('hobs268');self.db.execute('INSERT INTO hypothesis_observations_268 VALUES(?,?,?,?,?,?,?,?)',(oid,hid,cid,typ,text,'open',_now(),_hash({'h':hid,'t':typ,'s':text})))

    def review_hypothesis(self,*,case_id,hypothesis_id,decision,rationale,reviewer=None):
        h=self.db.one('SELECT * FROM hypotheses_268 WHERE hypothesis_id=?',(hypothesis_id,))
        if not h or h['case_id']!=case_id:raise KeyError('hypothesis')
        reviewer=reviewer or self.actor
        if reviewer==h['created_by']:raise ValueError('independent reviewer required')
        if decision not in {'retain','challenge','reject','needs_more_evidence'}:raise ValueError('invalid decision')
        rid=_id('hrev268');self.db.execute('INSERT INTO hypothesis_reviews_268 VALUES(?,?,?,?,?,?,?,?)',(rid,hypothesis_id,case_id,decision,rationale,reviewer,_now(),_hash({'d':decision,'r':rationale})))
        return {'review_id':rid,'decision':decision}

    def _brief(self,sid,cid,run_id,actor):
        hs=self.db.all('SELECT * FROM hypotheses_268 WHERE set_id=? ORDER BY label',(sid,));comparison=[];gaps=[];follow=[];sup=con=0
        for h in hs:
            links=self.db.all('SELECT * FROM hypothesis_evidence_links_268 WHERE hypothesis_id=?',(h['hypothesis_id'],))
            s=sum(1 for x in links if x['role'].startswith('support'));c=sum(1 for x in links if x['role'].startswith('contradict'))
            sup+=s;con+=c;comparison.append({'label':h['label'],'support_links':s,'contradict_links':c,'context_links':len(links)-s-c,'truth_probability':None})
            if h['label']=='H1' and s==0:gaps.append('H1 lacks explicit supporting evidence links from the current run.')
            if h['label']=='H3':gaps.append('Identify discriminating evidence that can separate H1 from H2 rather than merely adding more context.')
        follow=[{'query':'Prüfe unabhängige Primärquellen, die zwischen der direkten und der alternativen Erklärung unterscheiden können.','requires_new_ok':True}]
        summary=(f'{len(hs)} konkurrierende Hypothesen werden parallel geführt. Link-Anzahlen sind keine Wahrscheinlichkeiten oder Wahrheits-Scores. '
                 f'Supporting={sup}, contradicting={con}; Gegenbelege und die Null-/Insufficient-Hypothese bleiben sichtbar.')
        bid=_id('hbrief268');self.db.execute('INSERT INTO hypothesis_briefs_268 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (bid,sid,cid,run_id,len(hs),sup,con,summary,_canon(comparison),_canon(gaps),_canon(follow),'analysis_basis',actor,_now(),_hash({'c':comparison,'g':gaps})))
        return {'brief_id':bid,'set_id':sid,'summary':summary,'comparison':comparison,'research_gaps':gaps,'followup_queries':follow,
                'automatic_winner_selection':False,'numeric_truth_score':None}

    def hypothesis_brief(self,set_id):
        b=self.db.one('SELECT * FROM hypothesis_briefs_268 WHERE set_id=? ORDER BY rowid DESC LIMIT 1',(set_id,))
        if not b:return None
        return {**b,'comparison':json.loads(b['comparison_json']),'research_gaps':json.loads(b['research_gaps_json']),'followup_queries':json.loads(b['followup_queries_json']),
                'automatic_winner_selection':False,'numeric_truth_score':None}

    def execute_enhanced(self,*,case_id,run_id,confirmation,approved_by=None,provider='',max_queries=8,max_results_per_query=8,proxy_mode='direct',proxy_label='',opsec_mode='standard'):
        pf=self.preflight_egress(case_id=case_id,run_id=run_id,provider=provider or 'browser_queue',opsec_mode=opsec_mode,route_mode=proxy_mode)
        if pf['result']=='blocked':raise RuntimeError('OPSEC egress preflight blocked this run: '+'; '.join(pf['notes']))
        out=self.paths267.execute_enhanced(case_id=case_id,run_id=run_id,confirmation=confirmation,approved_by=approved_by or self.actor,
            provider=provider,max_queries=max_queries,max_results_per_query=max_results_per_query,proxy_mode=proxy_mode,proxy_label=proxy_label)
        hyp=self.build_hypothesis_set(case_id=case_id,run_id=run_id,actor=approved_by or self.actor)
        out['hypothesis_lab_268']=hyp;out['egress_preflight_268']=pf
        return out

    def stage_training_candidate(self,*,case_id,hypothesis_id,actor=None):
        h=self.db.one('SELECT * FROM hypotheses_268 WHERE hypothesis_id=? AND case_id=?',(hypothesis_id,case_id));rv=self.db.one('SELECT * FROM hypothesis_reviews_268 WHERE hypothesis_id=?',(hypothesis_id,))
        if not h or not rv or rv['decision']!='retain':raise PermissionError('independently retained hypothesis required')
        links=self.db.all('SELECT evidence_ref,role FROM hypothesis_evidence_links_268 WHERE hypothesis_id=?',(hypothesis_id,))
        return self.training.add_example(case_id=case_id,instruction='Maintain a reviewable competing hypothesis with supporting and contradicting evidence and falsification tests; do not select truth automatically.',
            response=_canon({'label':h['label'],'type':h['hypothesis_type'],'evidence_roles':[x['role'] for x in links],'truth_score':None}),
            context={'build':'268.0','competing_hypotheses':True,'automatic_winner_selection':False},evidence_refs=[x['evidence_ref'] for x in links],
            language='de',source_type='build268_reviewed_hypothesis',source_ref=hypothesis_id,created_by=actor or self.actor,confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN')

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_hypothesis_benchmarks_268 WHERE review_status='reviewed'") or {'n':0})['n'];fam=(self.db.one('SELECT COUNT(DISTINCT task_family) n FROM ai_hypothesis_benchmarks_268') or {'n':0})['n']
        return {'reviewed_benchmarks':n,'task_families':fam,'competing_hypothesis_synthesis':True,'automatic_winner_selection':False,'numeric_truth_score':False,'automatic_model_activation':False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_268 WHERE review_status='verified'") or {'n':0})['n']
        return {'verified_controls':n,'strict_egress_policy':1,'fail_closed_external_route':1,'network_anonymity_claim':0,'automatic_ip_rotation':0,'disposable_email_generation':0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics();g={'build':'268.0','main_goal':bool(self.db.one("SELECT name FROM sqlite_master WHERE name='hypotheses_268'")),'ai_delta':a['reviewed_benchmarks']>=40 and a['task_families']>=20,'opsec_delta':o['verified_controls']>=36 and o['strict_egress_policy']==1,'capability_regression':'network_path_brokerage_analysis' in caps and 'opsec_query_correlation_risk' in caps,'parent_build_gate':self.paths267.qualified_gate()['release_ready']};g['release_ready']=all(g[k] for k in ('main_goal','ai_delta','opsec_delta','capability_regression','parent_build_gate'));return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ''),quote=True)
        briefs=self.db.all('SELECT * FROM hypothesis_briefs_268 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,));rows=''.join(f"<tr><td><code>{e(b['run_id'])}</code></td><td>{e(b['hypothesis_count'])}</td><td>{e(b['supporting_link_count'])}</td><td>{e(b['contradicting_link_count'])}</td><td>{e(b['summary'])}</td></tr>" for b in briefs)
        pfs=self.db.all('SELECT * FROM opsec_egress_preflight_268 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,));prows=''.join(f"<tr><td>{e(p['run_id'])}</td><td>{e(p['provider'])}</td><td>{e(p['result'])}</td><td>{e(p['notes'])}</td></tr>" for p in pfs)
        return f"""<section class='card'><h2>Hypothesis Lab 2.0 · Build 268</h2><p><b>Datenfusion → konkurrierende Hypothesen → Supporting/Contradicting Evidence → Expected/Falsifying Observations → Research Gaps.</b></p><p>Kein automatischer Gewinner und kein Wahrheits-Score.</p><h3>Hypothesis Briefs</h3><table><tr><th>Run</th><th>Hypothesen</th><th>Support</th><th>Contradict</th><th>Brief</th></tr>{rows or '<tr><td colspan=5>Noch kein Hypothesis Set.</td></tr>'}</table><h3>OPSEC Egress Preflight</h3><p>Strict Mode blockiert direkte externe Provider-/Browser-Routen. Ein vorhandener Proxy wird nur als Routingpfad gewertet, nicht als Anonymitätsbeweis.</p><table><tr><th>Run</th><th>Provider</th><th>Result</th><th>Notes</th></tr>{prows or '<tr><td colspan=4>Noch kein Preflight.</td></tr>'}</table><pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one('SELECT event_hash FROM build268_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(cid,));ph=prev['event_hash'] if prev else 'GENESIS';eid=_id('evt268');now=_now();data={'event_id':eid,'case_id':cid,'event_type':etype,'object_type':otype,'object_id':oid,'actor':actor,'payload':payload,'previous_hash':ph,'created_at':now};self.db.execute('INSERT INTO build268_events VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
