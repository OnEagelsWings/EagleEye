from __future__ import annotations
import hashlib,html,json,re,time,uuid
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit,parse_qsl,urlencode,urlunsplit

def _now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
TRACKING={'gclid','fbclid','mc_cid','mc_eid','ref','ref_src','yclid','dclid','msclkid'}
STOP={
 'der','die','das','den','dem','des','ein','eine','einer','eines','und','oder','aber','ist','war','sind','waren','wird','wurde','werden','zu','von','mit','für','fuer','im','in','am','an','auf','als','auch','dass','dies','diese','dieser','the','a','an','and','or','is','was','were','are','to','of','for','in','on','with','that','this','from'
}

def _canonical_url(url):
    try:
        p=urlsplit(str(url or '').strip())
        kept=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.casefold().startswith('utm_') and k.casefold() not in TRACKING]
        return urlunsplit((p.scheme.casefold() or 'https',(p.hostname or '').casefold(),re.sub(r'/+$','',p.path or '/') or '/',urlencode(sorted(kept)),''))
    except Exception:return str(url or '').strip()
def _tracking_count(url):
    try:return sum(1 for k,_ in parse_qsl(urlsplit(str(url or '')).query,keep_blank_values=True) if k.casefold().startswith('utm_') or k.casefold() in TRACKING)
    except Exception:return 0
def _host(url):
    try:return (urlsplit(str(url or '')).hostname or '').casefold()
    except Exception:return ''
def _norm(v): return re.sub(r'\s+',' ',re.sub(r'[^\wäöüÄÖÜß]+',' ',str(v or '').casefold())).strip()
def _tokens(v): return {x for x in _norm(v).split() if len(x)>=3 and x not in STOP}
def _similarity(a,b):
    aa,bb=_tokens(a),_tokens(b)
    if not aa or not bb:return 0.0
    return len(aa&bb)/len(aa|bb)
def _claim_text(f):
    title=str(f.get('title') or '').strip();snippet=str(f.get('snippet') or '').strip()
    return ((title+': '+snippet) if title and snippet else (snippet or title))[:1200]
def _explicit_date(text):
    m=re.search(r'(?i)\b(?:published|published on|veröffentlicht|veroeffentlicht|dated|vom)\s*(?:am\s*)?(\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})\b',text or '')
    if not m:return None
    d=m.group(1)
    if '.' in d:
        day,month,year=d.split('.');return f'{year}-{int(month):02d}-{int(day):02d}'
    return d

def _query_norm(text):
    def repl(m):return _canonical_url(m.group(0))
    x=re.sub(r'https?://[^\s\"\')]+',repl,str(text or ''))
    return re.sub(r'\s+',' ',x).strip().casefold()

class _UF:
    def __init__(self,ids):self.p={x:x for x in ids}
    def find(self,x):
        while self.p[x]!=x:
            self.p[x]=self.p[self.p[x]];x=self.p[x]
        return x
    def union(self,a,b):
        a,b=self.find(a),self.find(b)
        if a!=b:self.p[max(a,b)]=min(a,b)

class Build272NarrativeDiffusionService:
    BUILD='272.0'
    def __init__(self,db:Any,audit:Any,*,source271:Any,collection270:Any,compatibility:Any,training:Any,actor:str='local-analyst'):
        self.db=db;self.audit=audit;self.source271=source271;self.collection270=collection270
        self.compatibility=compatibility;self.training=training;self.actor=actor

    def _run(self,case_id,run_id):
        r=self.db.one('SELECT * FROM ai_research_runs_263 WHERE case_id=? AND run_id=?',(case_id,run_id))
        if not r:raise KeyError('research run not found')
        return r

    def _source_map(self,case_id,parent_run_id):
        roll=self.source271.family_rollup(case_id,parent_run_id)
        out={}
        for c in roll['clusters']:
            key='family_'+_hash(c['evidence_refs'])[:20]
            for ev in c['evidence_refs']:out[ev]=key
        return out,roll

    def _ensure_observations(self,case_id,parent_run_id,ev_to_source):
        findings=self.source271._findings(case_id,parent_run_id)
        observations=[]
        for f in findings:
            ev=str(f['evidence_ref'])
            old=self.db.one('SELECT * FROM claim_observations_272 WHERE case_id=? AND parent_run_id=? AND evidence_ref=?',(case_id,parent_run_id,ev))
            if old:
                observations.append(dict(old));continue
            text=_claim_text(f);norm=_norm(text);explicit=_explicit_date(text)
            obs_time=explicit or str(f['created_at']);basis='explicit_source_date_candidate' if explicit else 'ingestion_time_only'
            oid=_id('claimobs272');payload={'ev':ev,'claim':norm,'time':obs_time,'basis':basis,'source_cluster':ev_to_source.get(ev,'unknown')}
            self.db.execute('INSERT INTO claim_observations_272 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (oid,case_id,parent_run_id,f['observed_run_id'],ev,ev_to_source.get(ev,'unknown'),text,norm,_hash(norm),str(f['stance']),obs_time,basis,_now(),_hash(payload)))
            observations.append(dict(self.db.one('SELECT * FROM claim_observations_272 WHERE observation_id=?',(oid,))))
        return observations

    def analyze_family(self,*,case_id,parent_run_id,actor=None):
        actor=actor or self.actor;self._run(case_id,parent_run_id)
        ev_to_source,source_rollup=self._source_map(case_id,parent_run_id)
        obs=self._ensure_observations(case_id,parent_run_id,ev_to_source)
        last=self.db.one('SELECT MAX(revision_no) n FROM narrative_evolution_briefs_272 WHERE case_id=? AND parent_run_id=?',(case_id,parent_run_id))
        rev=int((last or {'n':0})['n'] or 0)+1
        uf=_UF([o['observation_id'] for o in obs])
        for i,a in enumerate(obs):
            for b in obs[i+1:]:
                sim=_similarity(a['claim_text'],b['claim_text']);shared=len(_tokens(a['claim_text'])&_tokens(b['claim_text']))
                if a['normalized_claim']==b['normalized_claim'] or (sim>=0.45 and shared>=3):uf.union(a['observation_id'],b['observation_id'])
        comps=defaultdict(list)
        for o in obs:comps[uf.find(o['observation_id'])].append(o)
        clusters=[];obs_to_narrative={};edges=[];wording=0;cross_origin=0;dependent=0;signals=0
        explicit_count=sum(1 for o in obs if o['time_basis']=='explicit_source_date_candidate')
        ingestion_count=len(obs)-explicit_count
        for members in comps.values():
            members=sorted(members,key=lambda x:(x['observation_time'],x['created_at'],x['observation_id']))
            evs=sorted({m['evidence_ref'] for m in members});source_ids=sorted({ev_to_source.get(m['evidence_ref'],'unknown') for m in members})
            ck=_hash(sorted(m['claim_fingerprint'] for m in members))[:24];nid=_id('narr272')
            chrono='explicit_and_ingestion_mixed' if len({m['time_basis'] for m in members})>1 else (members[0]['time_basis'] if members else 'none')
            payload={'obs':[m['observation_id'] for m in members],'refs':evs,'sources':source_ids,'rev':rev}
            self.db.execute('INSERT INTO narrative_clusters_272 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (nid,case_id,parent_run_id,rev,ck,_canon([m['observation_id'] for m in members]),_canon(evs),_canon(source_ids),len(members),
                 len({x for x in source_ids if x!='unknown'}),members[0]['observation_time'] if members else '',members[-1]['observation_time'] if members else '',chrono,'analysis_basis',_now(),_hash(payload)))
            c={'narrative_id':nid,'observation_count':len(members),'evidence_refs':evs,'source_cluster_ids':source_ids,'chronology_basis':chrono,
               'earliest_observed_time':members[0]['observation_time'] if members else '','latest_observed_time':members[-1]['observation_time'] if members else ''}
            clusters.append(c)
            for m in members:obs_to_narrative[m['evidence_ref']]=nid
            for a,b in zip(members,members[1:]):
                sim=_similarity(a['claim_text'],b['claim_text']);ta,tb=_tokens(a['claim_text']),_tokens(b['claim_text'])
                added=sorted(tb-ta)[:40];removed=sorted(ta-tb)[:40]
                sa=ev_to_source.get(a['evidence_ref'],'unknown');sb=ev_to_source.get(b['evidence_ref'],'unknown')
                if sa!='unknown' and sa==sb:
                    dep='same_source_cluster';rel='dependent_republication_sequence_candidate';dependent+=1
                else:
                    dep='different_or_unknown_origin_candidates';rel='claim_evolution_sequence_candidate';cross_origin+=1
                sync=int(a['time_basis']=='explicit_source_date_candidate' and b['time_basis']=='explicit_source_date_candidate' and
                         a['observation_time']==b['observation_time'] and sa!='unknown' and sb!='unknown' and sa!=sb and sim>=0.85)
                if sync:rel='synchronized_cross_origin_similarity_signal';signals+=1
                if added or removed:wording+=1
                eid=_id('diff272');pl={'a':a['observation_id'],'b':b['observation_id'],'sim':round(sim,6),'added':added,'removed':removed,'dep':dep,'sync':sync}
                self.db.execute('INSERT INTO claim_diffusion_edges_272 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (eid,case_id,parent_run_id,rev,a['observation_id'],b['observation_id'],sim,rel,_canon(added),_canon(removed),dep,
                     'explicit_source_date_candidate' if a['time_basis']==b['time_basis']=='explicit_source_date_candidate' else 'mixed_or_ingestion_time',sync,'analysis_basis',_now(),_hash(pl)))
                edges.append({'edge_id':eid,'from':a['observation_id'],'to':b['observation_id'],'similarity':sim,'relation_type':rel,
                              'added_terms':added,'removed_terms':removed,'source_dependency_context':dep,'coordination_signal':bool(sync)})
        ach=self._ach_overlay(case_id,parent_run_id,rev,obs_to_narrative,ev_to_source)
        evolution=[]
        for c in sorted(clusters,key=lambda x:(-x['observation_count'],x['narrative_id']))[:20]:
            evolution.append({'narrative_id':c['narrative_id'],'observations':c['observation_count'],'source_origin_candidates':len([x for x in c['source_cluster_ids'] if x!='unknown']),
                              'chronology_basis':c['chronology_basis'],'earliest':c['earliest_observed_time'],'latest':c['latest_observed_time']})
        gaps=[];follow=[]
        if ingestion_count:gaps.append(f'{ingestion_count} claim observation(s) only have ingestion-time chronology; original publication chronology remains unresolved.')
        if dependent:gaps.append(f'{dependent} diffusion edge(s) remain inside the same source-origin cluster and should not be treated as independent spread.')
        if signals:gaps.append(f'{signals} synchronized cross-origin wording signal(s) require independent evidence before any coordination hypothesis can be assessed.')
        if source_rollup['dependent_source_count']:
            gaps.append('Source repetition remains material; seek the earliest original/primary source for dependent narrative clusters.')
        for g in gaps[:3]:
            if 'chronology' in g: q='Suche datierte Original- oder Primärquellen, um die tatsächliche Veröffentlichungsreihenfolge der relevanten Behauptung zu klären.'
            elif 'coordination' in g: q='Suche unabhängige Primärbelege für oder gegen eine koordinierte Verbreitung; bloße zeitgleiche Wortlautähnlichkeit reicht nicht aus.'
            else:q='Suche die früheste unabhängige Original- oder Primärquelle für den wiederholten Narrative-Cluster.'
            follow.append({'query':q,'requires_new_ok':True})
        coordination='not_established'
        summary=(f'{len(obs)} claim observation(s) collapse to {len(clusters)} narrative cluster(s) with {len(edges)} sequence edge(s). '
                 f'{dependent} edge(s) are source-dependent, {cross_origin} cross origin candidates; {signals} synchrony signal(s). '
                 'Observed diffusion and wording evolution do not establish coordination, influence, intent or truth.')
        bid=_id('nbrief272');payload={'rev':rev,'obs':len(obs),'clusters':len(clusters),'edges':len(edges),'signals':signals,'gaps':gaps}
        self.db.execute('INSERT INTO narrative_evolution_briefs_272 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (bid,case_id,parent_run_id,rev,len(obs),len(clusters),len(edges),wording,cross_origin,dependent,signals,explicit_count,ingestion_count,coordination,
             summary,_canon(evolution),_canon(gaps),_canon(follow),'analysis_basis',actor,_now(),_hash(payload)))
        corr=self.audit_cross_run_correlation(case_id=case_id,parent_run_id=parent_run_id,revision_no=rev,observations=obs)
        self._event(case_id,'narrative_evolution_analysis','research_run',parent_run_id,actor,{'revision':rev,'observations':len(obs),'clusters':len(clusters),'signals':signals})
        return {'brief_id':bid,'parent_run_id':parent_run_id,'revision_no':rev,'observation_count':len(obs),'narrative_cluster_count':len(clusters),
                'diffusion_edge_count':len(edges),'wording_change_edge_count':wording,'cross_origin_edge_count':cross_origin,'dependent_edge_count':dependent,
                'coordination_signal_count':signals,'coordination_assessment':coordination,'clusters':clusters,'edges':edges,'ach_diffusion_observations':ach,
                'research_gaps':gaps,'followup_queries':follow,'summary':summary,'cross_run_correlation_272':corr,
                'automatic_coordination_conclusion':False,'truth_probability':None,'influence_operation_conclusion':False}

    def _ach_overlay(self,case_id,parent_run_id,rev,ev_to_narrative,ev_to_source):
        matrix=self.db.one('SELECT matrix_id FROM ach_matrices_269 WHERE case_id=? AND run_id=?',(case_id,parent_run_id))
        if not matrix:return []
        hs=self.db.all('SELECT hypothesis_id,label FROM hypotheses_268 WHERE case_id=? AND run_id=? ORDER BY label',(case_id,parent_run_id));out=[]
        for h in hs:
            links=self.db.all('SELECT evidence_ref,role FROM hypothesis_evidence_links_268 WHERE hypothesis_id=?',(h['hypothesis_id'],))
            sup=[x['evidence_ref'] for x in links if str(x['role']).startswith('support')];con=[x['evidence_ref'] for x in links if str(x['role']).startswith('contradict')]
            sn={ev_to_narrative[x] for x in sup if x in ev_to_narrative};cn={ev_to_narrative[x] for x in con if x in ev_to_narrative}
            ss={ev_to_source[x] for x in sup if ev_to_source.get(x) not in {None,'unknown'}};cs={ev_to_source[x] for x in con if ev_to_source.get(x) not in {None,'unknown'}}
            note=(f'{len(sup)} raw support ref(s) → {len(sn)} narrative cluster(s) / {len(ss)} source-origin candidate cluster(s); '
                  f'{len(con)} contradict ref(s) → {len(cn)} narrative cluster(s) / {len(cs)} source-origin candidate cluster(s).')
            oid=_id('achdiff272');pl={'h':h['hypothesis_id'],'rev':rev,'sup':len(sup),'sn':len(sn),'ss':len(ss),'con':len(con),'cn':len(cn),'cs':len(cs)}
            self.db.execute('INSERT INTO ach_diffusion_observations_272 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (oid,case_id,parent_run_id,rev,matrix['matrix_id'],h['hypothesis_id'],h['label'],len(sup),len(sn),len(ss),len(con),len(cn),len(cs),note,'analysis_basis',_now(),_hash(pl)))
            out.append({'hypothesis_id':h['hypothesis_id'],'label':h['label'],'raw_support_refs':len(sup),'support_narrative_clusters':len(sn),
                        'support_source_clusters':len(ss),'raw_contradict_refs':len(con),'contradict_narrative_clusters':len(cn),'contradict_source_clusters':len(cs),'note':note})
        return out

    def audit_cross_run_correlation(self,*,case_id,parent_run_id,revision_no,observations=None):
        runs=self.source271._family_runs(case_id,parent_run_id);queries=[];hosts=defaultdict(set);tracking=0
        qmap=defaultdict(set);high=0
        for rid in runs:
            for q in self.db.all('SELECT query_text FROM ai_research_queries_263 WHERE case_id=? AND run_id=?',(case_id,rid)):
                qh=_hash(_query_norm(q['query_text']));qmap[qh].add(rid);queries.append(qh)
            row=self.db.one("SELECT COUNT(*) n FROM opsec_query_risk_267 WHERE case_id=? AND run_id=? AND risk_class='high'",(case_id,rid))
            high+=int((row or {'n':0})['n'])
            for f in self.db.all('SELECT url FROM ai_research_findings_263 WHERE case_id=? AND run_id=?',(case_id,rid)):
                h=_host(f['url']);
                if h:hosts[h].add(rid)
                tracking+=int(_tracking_count(f['url'])>0)
        repeated=sorted([h for h,rs in qmap.items() if len(rs)>1])
        host_overlap=sum(1 for rs in hosts.values() if len(rs)>1)
        observations=observations or self._ensure_observations(case_id,parent_run_id,self._source_map(case_id,parent_run_id)[0])
        fmap=defaultdict(set)
        for o in observations:fmap[o['claim_fingerprint']].add(o['observed_run_id'])
        narrative_repeat=sum(1 for rs in fmap.values() if len(rs)>1)
        points=min(10,len(repeated)*2)+min(6,high*2)+min(4,host_overlap)+min(4,narrative_repeat)
        risk='high' if points>=8 else 'moderate' if points>=4 else 'low'
        rec=[]
        if repeated:rec.append('Repeated exact query fingerprints cross run boundaries; review whether equally effective but less repetitive query formulations are possible.')
        if high:rec.append('High-correlation query patterns remain present; avoid combining unnecessary unique personal identifiers in one query.')
        if host_overlap:rec.append('Repeated host targeting across waves is visible; verify that this is analytically necessary and not accidental narrowing.')
        rec.append('Correlation risk is a local metadata assessment, not proof of anonymity or non-attribution.')
        aid=_id('corr272');summary=(f'{len(runs)} run(s), {len(queries)} query observations, {len(repeated)} repeated query fingerprint(s), '
                                   f'{host_overlap} host(s) repeated across runs and {narrative_repeat} narrative fingerprint(s) repeated across runs. Risk: {risk}.')
        pl={'runs':len(runs),'queries':len(queries),'repeated':len(repeated),'high':high,'hosts':host_overlap,'narrative':narrative_repeat,'points':points}
        self.db.execute('INSERT INTO opsec_cross_run_correlation_272 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (aid,case_id,parent_run_id,revision_no,len(runs),len(queries),len(repeated),high,len(hosts),host_overlap,tracking,narrative_repeat,points,risk,
             _canon(repeated),0,0,summary,_canon(rec),'defensive_opsec',_now(),_hash(pl)))
        return {'audit_id':aid,'risk_class':risk,'risk_points':points,'run_count':len(runs),'query_count':len(queries),'repeated_query_hash_count':len(repeated),
                'high_risk_query_count':high,'unique_host_count':len(hosts),'cross_run_host_overlap_count':host_overlap,'tracking_parameter_url_count':tracking,
                'cross_run_narrative_repeat_count':narrative_repeat,'raw_query_stored':False,'raw_tracking_values_stored':False,'recommendations':rec,
                'network_anonymity_verified':False}

    def augment_collection_plan(self,*,case_id,plan_id,brief_id):
        plan=self.collection270.plan(plan_id)
        if plan['case_id']!=case_id:raise ValueError('case mismatch')
        b=self.db.one('SELECT * FROM narrative_evolution_briefs_272 WHERE brief_id=? AND case_id=?',(brief_id,case_id))
        if not b:raise KeyError('brief')
        follow=json.loads(b['followup_queries_json']);existing={str(t['query_text']).strip().casefold() for t in plan['tasks']};added=[]
        for i,f in enumerate(follow[:3]):
            q=re.sub(r'\s+',' ',str(f.get('query','')).strip())
            if not q or q.casefold() in existing:continue
            existing.add(q.casefold());tid=_id('ctask272')
            self.db.execute('INSERT INTO collection_tasks_270 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (tid,plan_id,'narrativegap272_'+brief_id,case_id,plan['parent_run_id'],q,'Narrative evolution / claim diffusion gap','claim_diffusion_verification',17+i,5,1,'planned',_now(),_hash({'q':q,'brief':brief_id})))
            added.append(tid)
        self._event(case_id,'collection_plan_augmented','collection_plan',plan_id,self.actor,{'narrative_brief_id':brief_id,'added_tasks':len(added)})
        return {'plan_id':plan_id,'added_task_ids':added,'requires_new_ok':True,'automatic_execution':False}

    def execute_initial_run(self,*,case_id,run_id,confirmation,approved_by=None,provider='',max_queries=8,max_results_per_query=8,proxy_mode='direct',proxy_label='',opsec_mode='standard'):
        out=self.source271.execute_initial_run(case_id=case_id,run_id=run_id,confirmation=confirmation,approved_by=approved_by or self.actor,provider=provider,
            max_queries=max_queries,max_results_per_query=max_results_per_query,proxy_mode=proxy_mode,proxy_label=proxy_label,opsec_mode=opsec_mode)
        out['narrative_diffusion_272']=self.analyze_family(case_id=case_id,parent_run_id=run_id,actor=approved_by or self.actor)
        return out

    def approve_and_execute_wave(self,*,case_id,plan_id,confirmation,approved_by=None,provider='browser_queue',opsec_mode='standard',task_budget=None,result_budget=8):
        out=self.source271.approve_and_execute_wave(case_id=case_id,plan_id=plan_id,confirmation=confirmation,approved_by=approved_by or self.actor,
            provider=provider,opsec_mode=opsec_mode,task_budget=task_budget,result_budget=result_budget)
        plan=self.collection270.plan(plan_id);brief=self.analyze_family(case_id=case_id,parent_run_id=plan['parent_run_id'],actor=approved_by or self.actor)
        aug=self.augment_collection_plan(case_id=case_id,plan_id=plan_id,brief_id=brief['brief_id'])
        out['narrative_diffusion_272']=brief;out['narrative_gap_task_ids']=aug['added_task_ids'];out['requires_new_ok_for_next_wave']=True
        return out

    def review_brief(self,*,case_id,brief_id,decision,rationale,reviewer=None):
        b=self.db.one('SELECT * FROM narrative_evolution_briefs_272 WHERE brief_id=?',(brief_id,))
        if not b or b['case_id']!=case_id:raise KeyError('brief')
        reviewer=reviewer or self.actor
        if reviewer==b['created_by']:raise ValueError('independent reviewer required')
        if decision not in {'retain_analysis','needs_more_evidence','challenge_analysis','reject_analysis'}:raise ValueError('invalid decision')
        rid=_id('nrev272');self.db.execute('INSERT INTO narrative_evolution_reviews_272 VALUES(?,?,?,?,?,?,?,?)',
            (rid,brief_id,case_id,decision,rationale,reviewer,_now(),_hash({'d':decision,'r':rationale})))
        return {'review_id':rid,'decision':decision}

    def stage_training_candidate(self,*,case_id,brief_id,actor=None):
        b=self.db.one('SELECT * FROM narrative_evolution_briefs_272 WHERE brief_id=? AND case_id=?',(brief_id,case_id))
        rv=self.db.one('SELECT * FROM narrative_evolution_reviews_272 WHERE brief_id=?',(brief_id,))
        if not b or not rv or rv['decision']!='retain_analysis':raise PermissionError('independently retained narrative analysis required')
        return self.training.add_example(case_id=case_id,
            instruction='Separate observed claim diffusion and wording evolution from source dependence and unsupported coordination conclusions.',
            response=_canon({'observations':b['observation_count'],'narrative_clusters':b['narrative_cluster_count'],'diffusion_edges':b['diffusion_edge_count'],
                             'coordination_signals':b['coordination_signal_count'],'coordination_assessment':'not_established'}),
            context={'build':'272.0','diffusion_not_coordination':True,'popularity_not_truth':True,'human_review_required':True},
            evidence_refs=[],language='de',source_type='build272_reviewed_narrative_diffusion',source_ref=brief_id,created_by=actor or self.actor,
            confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN')

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_narrative_diffusion_benchmarks_272 WHERE review_status='reviewed'") or {'n':0})['n']
        fam=(self.db.one('SELECT COUNT(DISTINCT task_family) n FROM ai_narrative_diffusion_benchmarks_272') or {'n':0})['n']
        return {'reviewed_benchmarks':n,'task_families':fam,'narrative_evolution':True,'claim_diffusion':True,'ach_diffusion_overlay':True,
                'collection_feedback':True,'automatic_coordination_conclusion':False,'automatic_model_activation':False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_272 WHERE review_status='verified'") or {'n':0})['n']
        return {'verified_controls':n,'cross_run_correlation_audit':1,'raw_query_stored':0,'raw_tracking_values_stored':0,'gateway_context_preserved':1,
                'network_anonymity_claim':0,'automatic_ip_rotation':0,'disposable_email_generation':0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={'build':'272.0','main_goal':bool(self.db.one("SELECT name FROM sqlite_master WHERE name='narrative_evolution_briefs_272'")),
           'ai_delta':a['reviewed_benchmarks']>=54 and a['task_families']>=24,
           'opsec_delta':o['verified_controls']>=52 and o['cross_run_correlation_audit']==1,
           'capability_regression':'source_independence_graph_2_271' in caps and 'opsec_source_origin_audit_271' in caps,
           'parent_build_gate':self.source271.qualified_gate()['release_ready']}
        g['release_ready']=all(g[k] for k in ('main_goal','ai_delta','opsec_delta','capability_regression','parent_build_gate'));return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ''),quote=True)
        briefs=self.db.all('SELECT * FROM narrative_evolution_briefs_272 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,))
        rows=''.join(f"<tr><td><code>{e(b['parent_run_id'])}</code></td><td>{e(b['revision_no'])}</td><td>{e(b['observation_count'])}</td><td>{e(b['narrative_cluster_count'])}</td><td>{e(b['coordination_signal_count'])}</td><td>{e(b['summary'])}</td></tr>" for b in briefs)
        audits=self.db.all('SELECT * FROM opsec_cross_run_correlation_272 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,))
        arows=''.join(f"<tr><td>{e(a['parent_run_id'])}</td><td>{e(a['run_count'])}</td><td>{e(a['repeated_query_hash_count'])}</td><td>{e(a['cross_run_host_overlap_count'])}</td><td>{e(a['risk_class'])}</td><td>{e(a['summary'])}</td></tr>" for a in audits)
        return f"""<section class='card'><h2>Narrative Evolution & Claim Diffusion · Build 272</h2>
        <p><b>Claim observations → narrative clusters → wording changes → diffusion sequence candidates → ACH diffusion overlay → research gaps.</b></p>
        <p>Diffusion, Synchronität und Netzwerk-Nähe sind keine automatische Evidenz für Koordination oder eine Einflussoperation.</p>
        <h3>Narrative Briefs</h3><table><tr><th>Parent Run</th><th>Rev.</th><th>Observations</th><th>Narratives</th><th>Signals</th><th>Summary</th></tr>{rows or "<tr><td colspan='6'>Noch keine Narrative-Analyse.</td></tr>"}</table>
        <details><summary><b>Narrative Brief unabhängig reviewen</b></summary><form method='post' action='/build272/review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='brief_id' placeholder='Brief ID' required><select name='decision'><option>retain_analysis</option><option>needs_more_evidence</option><option>challenge_analysis</option><option>reject_analysis</option></select><textarea name='rationale' placeholder='Review-Begründung' required></textarea><button>Review speichern</button></form></details>
        <h3>Cross-Run Correlation Audit</h3><p>Der Audit speichert Query-Hashes und Zählwerte, nicht den sensitiven Querytext oder Trackingwerte. Er bewertet lokale Korrelationsmuster, nicht Anonymität.</p>
        <table><tr><th>Parent Run</th><th>Runs</th><th>Repeat Queries</th><th>Host Overlap</th><th>Risk</th><th>Summary</th></tr>{arows or "<tr><td colspan='6'>Noch kein Audit.</td></tr>"}</table>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one('SELECT event_hash FROM build272_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(cid,));ph=prev['event_hash'] if prev else 'GENESIS'
        eid=_id('evt272');now=_now();data={'event_id':eid,'case_id':cid,'event_type':etype,'object_type':otype,'object_id':oid,'actor':actor,'payload':payload,'previous_hash':ph,'created_at':now}
        self.db.execute('INSERT INTO build272_events VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
