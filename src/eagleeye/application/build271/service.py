from __future__ import annotations
import hashlib,html,json,re,time,uuid
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit,parse_qsl,urlencode,urlunsplit

def _now(): return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
def _norm_text(v): return re.sub(r'\s+',' ',re.sub(r'[^\wäöüÄÖÜß]+',' ',str(v or '').casefold())).strip()
TRACKING={'gclid','fbclid','mc_cid','mc_eid','ref','ref_src','yclid','dclid','msclkid'}
def _canonical_url(url):
    try:
        p=urlsplit(str(url or '').strip())
        kept=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.casefold().startswith('utm_') and k.casefold() not in TRACKING]
        host=(p.hostname or '').casefold()
        path=re.sub(r'/+$','',p.path or '/') or '/'
        return urlunsplit((p.scheme.casefold() or 'https',host,path,urlencode(sorted(kept)),''))
    except Exception:return str(url or '').strip()
def _tracking_count(url):
    try:
        return sum(1 for k,_ in parse_qsl(urlsplit(str(url or '')).query,keep_blank_values=True) if k.casefold().startswith('utm_') or k.casefold() in TRACKING)
    except Exception:return 0
def _host(url):
    try:return (urlsplit(str(url or '')).hostname or '').casefold()
    except Exception:return ''
def _source_priority(sc):
    s=(sc or '').casefold()
    if 'primary' in s or 'official' in s or 'archive' in s:return 0
    if 'document' in s:return 1
    if 'media' in s:return 2
    return 3

class _UF:
    def __init__(self,ids):self.p={x:x for x in ids}
    def find(self,x):
        while self.p[x]!=x:
            self.p[x]=self.p[self.p[x]];x=self.p[x]
        return x
    def union(self,a,b):
        a,b=self.find(a),self.find(b)
        if a!=b:self.p[max(a,b)]=min(a,b)

class Build271SourceIndependenceService:
    BUILD='271.0'
    def __init__(self,db:Any,audit:Any,*,collection270:Any,analysis269:Any,compatibility:Any,training:Any,actor:str='local-analyst'):
        self.db=db;self.audit=audit;self.collection270=collection270;self.analysis269=analysis269
        self.compatibility=compatibility;self.training=training;self.actor=actor

    def _run(self,case_id,run_id):
        row=self.db.one('SELECT * FROM ai_research_runs_263 WHERE case_id=? AND run_id=?',(case_id,run_id))
        if not row:raise KeyError('research run not found')
        return row

    def _family_runs(self,case_id,parent_run_id):
        self._run(case_id,parent_run_id);ids=[parent_run_id]
        rows=self.db.all('''SELECT wt.child_run_id FROM collection_wave_tasks_270 wt
            JOIN collection_waves_270 w ON w.wave_id=wt.wave_id
            WHERE w.case_id=? AND w.parent_run_id=? AND wt.child_run_id<>'' ORDER BY wt.created_at''',(case_id,parent_run_id))
        for r in rows:
            if r['child_run_id'] not in ids:ids.append(r['child_run_id'])
        return ids

    def _findings(self,case_id,parent_run_id):
        ids=self._family_runs(case_id,parent_run_id)
        out=[]
        for rid in ids:
            for f in self.db.all('SELECT * FROM ai_research_findings_263 WHERE case_id=? AND run_id=? ORDER BY created_at,finding_id',(case_id,rid)):
                f=dict(f);f['observed_run_id']=rid;out.append(f)
        return out

    def _cycle_count(self,edges):
        adj=defaultdict(list)
        for a,b in edges:adj[a].append(b)
        state={};cycles=0
        def dfs(n):
            nonlocal cycles
            state[n]=1
            for x in adj[n]:
                if state.get(x)==1:cycles+=1
                elif state.get(x,0)==0:dfs(x)
            state[n]=2
        for n in list(adj):
            if state.get(n,0)==0:dfs(n)
        return cycles

    def analyze_family(self,*,case_id,parent_run_id,actor=None):
        actor=actor or self.actor;self._run(case_id,parent_run_id)
        old=self.db.one('SELECT brief_id FROM source_independence_briefs_271 WHERE case_id=? AND run_id=?',(case_id,parent_run_id))
        if old:return self.brief(old['brief_id'])
        findings=self._findings(case_id,parent_run_id)
        nodes=[];by_ev={};by_canon=defaultdict(list);by_fp=defaultdict(list)
        for f in findings:
            ev=str(f['evidence_ref']);url=str(f['url']);can=_canonical_url(url);host=_host(url)
            basis=_norm_text((f['title'] or '')+' '+(f['snippet'] or ''))
            fp=_hash(basis) if basis else _hash((can,ev))
            title=str(f['title'] or '')[:500]
            origin_kind='translation_candidate' if re.search(r'(?i)\b(translation|translated|übersetzung|uebersetzung)\b',title) else 'origin_candidate'
            sid=_id('src271');payload={'ev':ev,'can':can,'host':host,'fp':fp,'observed_run':f['observed_run_id']}
            self.db.execute('INSERT INTO source_nodes_271 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (sid,case_id,parent_run_id,f['observed_run_id'],ev,can,host,title,fp,str(f['source_class']),origin_kind,_now(),_hash(payload)))
            n={'source_id':sid,'evidence_ref':ev,'canonical_url':can,'host':host,'title':title,'content_fingerprint':fp,
               'source_class':str(f['source_class']),'origin_kind':origin_kind,'observed_run_id':f['observed_run_id']}
            nodes.append(n);by_ev[ev]=n;by_canon[can].append(n);by_fp[fp].append(n)
        edges=[];edgekeys=set()
        def edge(child,parent,relation,basis,confidence='candidate'):
            if child==parent:return
            key=(child,parent,relation)
            if key in edgekeys:return
            edgekeys.add(key);eid=_id('sedge271');p={'c':child,'p':parent,'r':relation,'b':basis}
            self.db.execute('INSERT INTO source_dependency_edges_271 VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (eid,case_id,parent_run_id,child,parent,relation,basis,confidence,'analysis_basis',_now(),_hash(p)))
            edges.append({'edge_id':eid,'child_source_id':child,'parent_source_id':parent,'relation_type':relation,'basis':basis})
        # Exact canonical URL repetitions: one candidate origin, remaining hits dependent.
        for can,arr in by_canon.items():
            if not can or len(arr)<2:continue
            origin=sorted(arr,key=lambda n:(_source_priority(n['source_class']),n['source_id']))[0]
            for n in arr:
                if n['source_id']!=origin['source_id']:edge(n['source_id'],origin['source_id'],'canonical_duplicate_or_mirror','same canonical URL after tracking-parameter normalization','high')
        # Identical captured content across distinct URLs/hosts: syndication/republication candidate.
        for fp,arr in by_fp.items():
            uniq={n['canonical_url'] for n in arr}
            if len(arr)<2 or len(uniq)<2:continue
            origin=sorted(arr,key=lambda n:(_source_priority(n['source_class']),n['source_id']))[0]
            for n in arr:
                if n['source_id']==origin['source_id']:continue
                rel='translation_candidate' if n['origin_kind']=='translation_candidate' else 'syndicated_or_republished_candidate'
                edge(n['source_id'],origin['source_id'],rel,'identical normalized captured title/snippet fingerprint across distinct URLs','candidate')
        # Explicit Build258 lineage, when evidence refs match this run family.
        lineages=self.db.all("SELECT source_ref,parent_source_ref,dependency_class FROM claim_source_lineage_258 WHERE case_id=? AND parent_source_ref<>''",(case_id,))
        for l in lineages:
            c=by_ev.get(l['source_ref']);p=by_ev.get(l['parent_source_ref'])
            if c and p:edge(c['source_id'],p['source_id'],'explicit_'+str(l['dependency_class']),'Build258 reviewed/manual lineage reference','explicit')
        # Build dependency components.
        uf=_UF([n['source_id'] for n in nodes])
        for e in edges:uf.union(e['child_source_id'],e['parent_source_id'])
        comps=defaultdict(list)
        for n in nodes:comps[uf.find(n['source_id'])].append(n)
        cycle_count=self._cycle_count([(e['child_source_id'],e['parent_source_id']) for e in edges])
        edge_by_comp=defaultdict(list)
        for e in edges:edge_by_comp[uf.find(e['child_source_id'])].append(e)
        cluster_out=[]
        for root,members in sorted(comps.items()):
            ed=edge_by_comp.get(root,[])
            origin=sorted(members,key=lambda n:(_source_priority(n['source_class']),n['source_id']))[0]
            rels=sorted({e['relation_type'] for e in ed})
            ck=_hash(sorted(n['source_id'] for n in members))[:24]
            independence='dependent_cluster' if len(members)>1 else ('unknown_origin' if not origin['host'] else 'origin_candidate_unverified')
            if cycle_count and any(e['child_source_id'] in {m['source_id'] for m in members} for e in ed):independence='circular_or_dependent_cluster'
            cid=_id('scluster271');refs=sorted({m['evidence_ref'] for m in members})
            payload={'members':[m['source_id'] for m in members],'refs':refs,'rels':rels,'independence':independence}
            self.db.execute('INSERT INTO source_clusters_271 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (cid,case_id,parent_run_id,ck,origin['source_id'],_canon([m['source_id'] for m in members]),_canon(refs),_canon(rels),len(members),independence,'analysis_basis',_now(),_hash(payload)))
            cluster_out.append({'cluster_id':cid,'origin_source_id':origin['source_id'],'member_count':len(members),'evidence_refs':refs,
                                'relation_types':rels,'independence_class':independence,'hosts':sorted({m['host'] for m in members if m['host']}),
                                'observed_runs':sorted({m['observed_run_id'] for m in members})})
        ev_to_cluster={ev:c['cluster_id'] for c in cluster_out for ev in c['evidence_refs']}
        ach_obs=self._ach_overlay(case_id,parent_run_id,ev_to_cluster)
        raw=len(nodes);clusters=len(cluster_out);dependent=max(0,raw-clusters)
        unknown=sum(1 for c in cluster_out if c['independence_class']=='unknown_origin')
        hosts=sorted({n['host'] for n in nodes if n['host']})
        gaps=[];follow=[]
        for c in sorted(cluster_out,key=lambda x:(-x['member_count'],x['cluster_id']))[:8]:
            if c['member_count']>=2:
                gaps.append(f"Source cluster {c['cluster_id']} contains {c['member_count']} dependent/repeated findings but only one origin candidate.")
                follow.append({'query':'Suche eine sachlich unabhängige Primär- oder Originalquelle für den Inhalt des abhängigen Quellenclusters '+c['cluster_id']+'.','requires_new_ok':True})
        if raw and clusters==1 and raw>1:gaps.append('All captured findings currently collapse to one source-origin candidate; independent corroboration is missing.')
        summary=(f'{raw} captured findings collapse to {clusters} source-origin candidate cluster(s); {dependent} repeated/dependent finding(s). '
                 f'{cycle_count} circular dependency signal(s). Origin candidates are not automatically verified as independent sources.')
        bid=_id('sbrief271');payload={'raw':raw,'clusters':clusters,'dependent':dependent,'cycles':cycle_count,'hosts':len(hosts),'gaps':gaps}
        self.db.execute('INSERT INTO source_independence_briefs_271 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (bid,case_id,parent_run_id,raw,clusters,clusters,dependent,unknown,cycle_count,len(hosts),summary,_canon(cluster_out),_canon(gaps),_canon(follow),
             'analysis_basis',actor,_now(),_hash(payload)))
        audit=self._opsec_origin_audit(case_id,parent_run_id,findings,cluster_out)
        self._event(case_id,'source_independence_analyzed','research_run',parent_run_id,actor,{'raw':raw,'clusters':clusters,'dependent':dependent,'cycles':cycle_count})
        return {**self.brief(bid),'ach_independence_observations':ach_obs,'opsec_source_origin_audit':audit}

    def _ach_overlay(self,case_id,run_id,ev_to_cluster):
        matrix=self.db.one('SELECT matrix_id FROM ach_matrices_269 WHERE case_id=? AND run_id=? ORDER BY rowid DESC LIMIT 1',(case_id,run_id))
        if not matrix:return []
        hs=self.db.all('SELECT hypothesis_id,label FROM hypotheses_268 WHERE case_id=? AND run_id=? ORDER BY label',(case_id,run_id));out=[]
        for h in hs:
            links=self.db.all('SELECT evidence_ref,role FROM hypothesis_evidence_links_268 WHERE hypothesis_id=?',(h['hypothesis_id'],))
            sr=[l['evidence_ref'] for l in links if str(l['role']).startswith('support')]
            cr=[l['evidence_ref'] for l in links if str(l['role']).startswith('contradict')]
            sc={ev_to_cluster[x] for x in sr if x in ev_to_cluster};cc={ev_to_cluster[x] for x in cr if x in ev_to_cluster}
            note=(f"{len(sr)} raw support ref(s) map to {len(sc)} source cluster(s); {len(cr)} raw contradict ref(s) map to {len(cc)} cluster(s). "
                  'This overlay adjusts source-count interpretation only and does not mutate ACH or assign truth probability.')
            oid=_id('achind271');payload={'h':h['hypothesis_id'],'sr':len(sr),'sc':len(sc),'cr':len(cr),'cc':len(cc)}
            self.db.execute('INSERT INTO ach_independence_observations_271 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (oid,case_id,run_id,matrix['matrix_id'],h['hypothesis_id'],h['label'],len(sr),len(sc),max(0,len(sr)-len(sc)),
                 len(cr),len(cc),max(0,len(cr)-len(cc)),note,'analysis_basis',_now(),_hash(payload)))
            out.append({'hypothesis_id':h['hypothesis_id'],'label':h['label'],'raw_support_refs':len(sr),'independent_support_cluster_candidates':len(sc),
                        'dependent_support_refs':max(0,len(sr)-len(sc)),
                        'raw_contradict_refs':len(cr),'independent_contradict_cluster_candidates':len(cc),'dependent_contradict_refs':max(0,len(cr)-len(cc))})
        return out

    def _opsec_origin_audit(self,case_id,run_id,findings,clusters):
        total=len(findings);hosts=defaultdict(int);tracking=0
        for f in findings:
            h=_host(f['url']);
            if h:hosts[h]+=1
            tracking+=int(_tracking_count(f['url'])>0)
        concentration=(max(hosts.values())/total) if total and hosts else 0.0
        cross_wave=sum(1 for c in clusters if len(c.get('observed_runs',[]))>1)
        pf=self.db.one("SELECT 1 x FROM opsec_gateway_preflight_270 WHERE case_id=? AND parent_run_id=? AND mode='high_risk' ORDER BY rowid DESC LIMIT 1",(case_id,run_id))
        points=(2 if concentration>=0.75 and total>=3 else 1 if concentration>=0.5 and total>=3 else 0)+(1 if tracking else 0)+(1 if cross_wave else 0)
        risk='high' if points>=3 else 'moderate' if points>=1 else 'low'
        summary=(f'{total} source URL(s), {len(hosts)} unique host(s), {tracking} URL(s) with tracking parameters, max host concentration {concentration:.0%}. '
                 'Tracking values are not copied into this audit. Source diversity does not imply network anonymity.')
        aid=_id('originaudit271');payload={'sources':total,'hosts':len(hosts),'tracking':tracking,'concentration':round(concentration,5),'crosswave':cross_wave,'risk':risk}
        self.db.execute('INSERT INTO opsec_source_origin_audits_271 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (aid,case_id,run_id,total,len(hosts),tracking,concentration,cross_wave,int(bool(pf)),0,risk,summary,'defensive_opsec',_now(),_hash(payload)))
        return {'audit_id':aid,'source_count':total,'unique_host_count':len(hosts),'tracking_parameter_url_count':tracking,
                'max_host_concentration':concentration,'cross_wave_repeated_origin_count':cross_wave,'high_risk_gateway_preflight_present':bool(pf),
                'raw_tracking_values_stored':False,'risk_class':risk,'summary':summary,'network_anonymity_verified':False}

    def brief(self,brief_id):
        b=self.db.one('SELECT * FROM source_independence_briefs_271 WHERE brief_id=?',(brief_id,))
        if not b:return None
        return {**b,'clusters':json.loads(b['cluster_summary_json']),'research_gaps':json.loads(b['research_gaps_json']),
                'followup_queries':json.loads(b['followup_queries_json']),'independence_verified':False,'truth_probability':None}

    def augment_collection_plan(self,*,case_id,plan_id,brief_id):
        plan=self.collection270.plan(plan_id);brief=self.brief(brief_id)
        if not plan or plan['case_id']!=case_id or not brief or brief['case_id']!=case_id:raise KeyError('plan/brief')
        existing={re.sub(r'\s+',' ',t['query_text'].strip()).casefold() for t in plan['tasks']};added=[]
        for i,f in enumerate(brief['followup_queries'][:3]):
            q=re.sub(r'\s+',' ',str(f.get('query','')).strip())
            if not q or q.casefold() in existing:continue
            existing.add(q.casefold());tid=_id('ctask271');priority=18+i
            self.db.execute('INSERT INTO collection_tasks_270 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (tid,plan_id,'sourcegap271_'+brief_id,case_id,plan['parent_run_id'],q,'Source independence gap','independent_primary_source',priority,5,1,'planned',_now(),_hash({'q':q,'brief':brief_id})))
            added.append(tid)
        self._event(case_id,'collection_plan_augmented','collection_plan',plan_id,self.actor,{'source_brief_id':brief_id,'added_tasks':len(added)})
        return {'plan_id':plan_id,'added_task_ids':added,'requires_new_ok':True,'automatic_execution':False}

    def execute_initial_run(self,*,case_id,run_id,confirmation,approved_by=None,provider='',max_queries=8,max_results_per_query=8,proxy_mode='direct',proxy_label='',opsec_mode='standard'):
        out=self.analysis269.execute_enhanced(case_id=case_id,run_id=run_id,confirmation=confirmation,approved_by=approved_by or self.actor,provider=provider,
            max_queries=max_queries,max_results_per_query=max_results_per_query,proxy_mode=proxy_mode,proxy_label=proxy_label,opsec_mode=opsec_mode)
        out['source_independence_271']=self.analyze_family(case_id=case_id,parent_run_id=run_id,actor=approved_by or self.actor)
        return out

    def approve_and_execute_wave(self,*,case_id,plan_id,confirmation,approved_by=None,provider='browser_queue',opsec_mode='standard',task_budget=None,result_budget=8):
        out=self.collection270.approve_and_execute_wave(case_id=case_id,plan_id=plan_id,confirmation=confirmation,approved_by=approved_by or self.actor,
            provider=provider,opsec_mode=opsec_mode,task_budget=task_budget,result_budget=result_budget)
        plan=self.collection270.plan(plan_id);parent=plan['parent_run_id']
        # A new family brief cannot overwrite the immutable previous brief. Create a revision by deleting only if this is the same-process stale analysis? No: preserve revisions by scope id.
        # Source-independence briefs are immutable, so if an earlier parent brief exists, analyze newly imported children under each child run and provide family roll-up from current DB separately.
        child_analyses=[]
        for c in out.get('children',[]):
            if c.get('status')=='completed':
                try:child_analyses.append(self.analyze_family(case_id=case_id,parent_run_id=c['child_run_id'],actor=approved_by or self.actor))
                except Exception as exc:child_analyses.append({'run_id':c['child_run_id'],'error':str(exc)})
        added=[]
        for b in child_analyses:
            if isinstance(b,dict) and b.get('brief_id'):
                try:added.extend(self.augment_collection_plan(case_id=case_id,plan_id=plan_id,brief_id=b['brief_id'])['added_task_ids'])
                except Exception:pass
        family=self.family_rollup(case_id,parent)
        out['source_independence_271']={'child_analyses':child_analyses,'family_rollup':family,'new_source_gap_task_ids':added}
        return out

    def family_rollup(self,case_id,parent_run_id):
        findings=self._findings(case_id,parent_run_id);runs=self._family_runs(case_id,parent_run_id)
        # Cluster across parent + all child runs, so a repeated URL/content in a later wave is not counted as a new origin candidate.
        uf=_UF([str(i) for i in range(len(findings))]);by_can=defaultdict(list);by_fp=defaultdict(list)
        meta=[]
        for i,f in enumerate(findings):
            can=_canonical_url(f['url']);fp=_hash(_norm_text((f['title'] or '')+' '+(f['snippet'] or '')))
            meta.append({'i':str(i),'evidence_ref':f['evidence_ref'],'canonical_url':can,'fingerprint':fp,'observed_run_id':f['observed_run_id'],'host':_host(f['url'])})
            by_can[can].append(str(i));by_fp[fp].append(str(i))
        for arr in list(by_can.values())+list(by_fp.values()):
            if len(arr)>1:
                for x in arr[1:]:uf.union(arr[0],x)
        comps=defaultdict(list)
        for m in meta:comps[uf.find(m['i'])].append(m)
        clusters=[];cross=0
        for members in comps.values():
            observed=sorted({m['observed_run_id'] for m in members})
            if len(observed)>1:cross+=max(0,len(members)-1)
            clusters.append({'member_count':len(members),'evidence_refs':sorted({m['evidence_ref'] for m in members}),
                             'observed_runs':observed,'hosts':sorted({m['host'] for m in members if m['host']})})
        raw=len(meta);count=len(clusters);last=self.db.one('SELECT MAX(revision_no) n FROM source_family_rollups_271 WHERE case_id=? AND parent_run_id=?',(case_id,parent_run_id))
        rev=int((last or {'n':0})['n'] or 0)+1;rid=_id('sfam271')
        summary=f'{raw} findings across {len(runs)} run(s) collapse to {count} cross-wave origin candidate cluster(s); {cross} repeated finding(s) cross run boundaries.'
        self.db.execute('INSERT INTO source_family_rollups_271 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (rid,case_id,parent_run_id,rev,len(runs),raw,count,cross,summary,_canon(clusters),'analysis_basis',_now(),_hash({'raw':raw,'count':count,'cross':cross,'rev':rev})))
        return {'rollup_id':rid,'parent_run_id':parent_run_id,'revision_no':rev,'run_count':len(runs),'raw_source_count':raw,'cluster_count':count,
                'dependent_source_count':max(0,raw-count),'cross_wave_dependency_count':cross,'clusters':clusters,'summary':summary,
                'automatic_external_followup':False,'new_external_wave_requires_ok':True}

    def review_brief(self,*,case_id,brief_id,decision,rationale,reviewer=None):
        b=self.db.one('SELECT * FROM source_independence_briefs_271 WHERE brief_id=?',(brief_id,))
        if not b or b['case_id']!=case_id:raise KeyError('brief')
        reviewer=reviewer or self.actor
        if reviewer==b['created_by']:raise ValueError('independent reviewer required')
        if decision not in {'retain_analysis','needs_more_evidence','challenge_analysis','reject_analysis'}:raise ValueError('invalid decision')
        rid=_id('srev271');self.db.execute('INSERT INTO source_independence_reviews_271 VALUES(?,?,?,?,?,?,?,?)',
            (rid,brief_id,case_id,decision,rationale,reviewer,_now(),_hash({'d':decision,'r':rationale})))
        return {'review_id':rid,'decision':decision}

    def stage_training_candidate(self,*,case_id,brief_id,actor=None):
        b=self.db.one('SELECT * FROM source_independence_briefs_271 WHERE brief_id=? AND case_id=?',(brief_id,case_id))
        rv=self.db.one('SELECT * FROM source_independence_reviews_271 WHERE brief_id=?',(brief_id,))
        if not b or not rv or rv['decision']!='retain_analysis':raise PermissionError('independently retained source-independence analysis required')
        return self.training.add_example(case_id=case_id,instruction='Separate raw source repetition from source-origin candidates and dependency clusters without converting origin count into truth.',
            response=_canon({'raw_sources':b['raw_source_count'],'origin_candidate_clusters':b['cluster_count'],'dependent_sources':b['dependent_source_count'],
                             'independence_verified':False}),context={'build':'271.0','source_independence':True,'human_review_required':True},
            evidence_refs=[],language='de',source_type='build271_reviewed_source_independence',source_ref=brief_id,created_by=actor or self.actor,
            confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN')

    def ai_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM ai_source_independence_benchmarks_271 WHERE review_status='reviewed'") or {'n':0})['n']
        fam=(self.db.one('SELECT COUNT(DISTINCT task_family) n FROM ai_source_independence_benchmarks_271') or {'n':0})['n']
        return {'reviewed_benchmarks':n,'task_families':fam,'source_dependency_graph':True,'ach_independence_overlay':True,
                'collection_feedback':True,'automatic_model_activation':False,'continuous_background_collection':False}
    def opsec_metrics(self):
        n=(self.db.one("SELECT COUNT(*) n FROM opsec_controls_271 WHERE review_status='verified'") or {'n':0})['n']
        return {'verified_controls':n,'source_origin_audit':1,'raw_tracking_values_stored':0,'gateway_context_preserved':1,
                'network_anonymity_claim':0,'automatic_ip_rotation':0,'disposable_email_generation':0}
    def qualified_gate(self):
        caps=self.compatibility.capabilities();a=self.ai_metrics();o=self.opsec_metrics()
        g={'build':'271.0','main_goal':bool(self.db.one("SELECT name FROM sqlite_master WHERE name='source_clusters_271'")),
           'ai_delta':a['reviewed_benchmarks']>=50 and a['task_families']>=22,'opsec_delta':o['verified_controls']>=48 and o['source_origin_audit']==1,
           'capability_regression':'intelligence_gaps_collection_plan_270' in caps and 'local_research_gateway_preflight_270' in caps,
           'parent_build_gate':self.collection270.qualified_gate()['release_ready']}
        g['release_ready']=all(g[k] for k in ('main_goal','ai_delta','opsec_delta','capability_regression','parent_build_gate'));return g

    def render_workspace_panel(self,*,case_id,csrf):
        e=lambda v:html.escape(str(v or ''),quote=True)
        briefs=self.db.all('SELECT * FROM source_independence_briefs_271 WHERE case_id=? ORDER BY created_at DESC LIMIT 14',(case_id,))
        rows=''.join(f"<tr><td><code>{e(b['run_id'])}</code></td><td>{e(b['raw_source_count'])}</td><td>{e(b['cluster_count'])}</td><td>{e(b['dependent_source_count'])}</td><td>{e(b['circular_dependency_count'])}</td><td>{e(b['summary'])}</td></tr>" for b in briefs)
        audits=self.db.all('SELECT * FROM opsec_source_origin_audits_271 WHERE case_id=? ORDER BY created_at DESC LIMIT 14',(case_id,))
        arows=''.join(f"<tr><td>{e(a['run_id'])}</td><td>{e(a['unique_host_count'])}</td><td>{e(a['tracking_parameter_url_count'])}</td><td>{e(round(a['max_host_concentration']*100))}%</td><td>{e(a['risk_class'])}</td></tr>" for a in audits)
        return f"""<section class='card'><h2>Source Independence Graph 2.0 · Build 271</h2>
        <p><b>Raw Findings → Source Nodes → Dependency Edges → Origin Candidate Clusters → ACH Independence Overlay → Source Gaps.</b></p>
        <p>Ein Origin-Kandidat ist keine verifizierte unabhängige Quelle. Wiederholung, Mirrors und Syndication werden nicht als zusätzliche Bestätigung gezählt.</p>
        <h3>Source Independence Briefs</h3><table><tr><th>Run</th><th>Raw</th><th>Cluster</th><th>Dependent</th><th>Cycles</th><th>Brief</th></tr>{rows or "<tr><td colspan='6'>Noch keine Analyse.</td></tr>"}</table>
        <details><summary><b>Analyse unabhängig reviewen</b></summary><form method='post' action='/build271/review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='brief_id' placeholder='Brief ID' required><select name='decision'><option>retain_analysis</option><option>needs_more_evidence</option><option>challenge_analysis</option><option>reject_analysis</option></select><textarea name='rationale' required></textarea><button>Review speichern</button></form></details>
        <h3>OPSEC Source-Origin Audit</h3><p>Trackingparameter werden nur gezählt/normalisiert; ihre Werte werden nicht in der 271-OPSEC-Tabelle dupliziert. Host-Diversität ist keine Aussage über Netzwerk-Anonymität.</p><table><tr><th>Run</th><th>Hosts</th><th>Tracking URLs</th><th>Max Host Share</th><th>Risk</th></tr>{arows or "<tr><td colspan='5'>Noch kein Audit.</td></tr>"}</table>
        <pre>{e(_canon(self.qualified_gate()))}</pre></section>"""

    def _event(self,cid,etype,otype,oid,actor,payload):
        prev=self.db.one('SELECT event_hash FROM build271_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(cid,));ph=prev['event_hash'] if prev else 'GENESIS'
        eid=_id('evt271');now=_now();data={'event_id':eid,'case_id':cid,'event_type':etype,'object_type':otype,'object_id':oid,'actor':actor,'payload':payload,'previous_hash':ph,'created_at':now}
        self.db.execute('INSERT INTO build271_events VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,cid,etype,otype,oid,actor,_canon(payload),ph,_hash(data),now))
