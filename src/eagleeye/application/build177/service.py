from __future__ import annotations
import hashlib, json, math, random, time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Mapping, Sequence
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

def _overlaps(start: str|None,end: str|None,from_: str|None,to: str|None) -> bool:
    lo=start or '0000-01-01T00:00:00+00:00'; hi=end or '9999-12-31T23:59:59+00:00'
    qlo=from_ or '0000-01-01T00:00:00+00:00'; qhi=to or '9999-12-31T23:59:59+00:00'
    return lo <= qhi and qlo <= hi

class Build177ScalableGraphEngineService:
    BUILD='177.0'
    TARGET_CONTRACT={'nodes':100_000,'edges':500_000,'interactive_filtering':True,'incremental_revisioning':True,'no_ui_blocking_contract':True}
    SOURCE_PROFILES=[
      {'source_id':'global_gleif_lei','title':'GLEIF LEI API','jurisdiction':'GLOBAL','category':'legal_entity_identity','access_mode':'official_rest_api','base_url':'https://api.gleif.org','docs_url':'https://www.gleif.org/en/lei-data/gleif-api','terms_url':'https://www.gleif.org/en/lei-data/access-and-use-lei-data','capabilities':['legal_entities','ownership_links','lei','bic_isin_mappings','fuzzy_name_search'],'constraints':['entity_subset_not_all_companies','source_attribution','schema_monitoring']},
      {'source_id':'de_bafin_companies','title':'BaFin Unternehmensdatenbank','jurisdiction':'DE','category':'regulated_entities','access_mode':'official_guided_public','base_url':'https://www.bafin.de','docs_url':'https://www.bafin.de/DE/die-bafin/publikationen-daten/datenbanken-uebersichten/unternehmenssuche/unternehmenssuche_node.html','terms_url':'https://www.bafin.de/DE/Service/Impressum/impressum_node.html','capabilities':['regulated_companies','authorisation_status','notifications','representatives'],'constraints':['guided_access','not_complete_company_registry','terms_review']},
      {'source_id':'de_destatis_genesis','title':'Destatis GENESIS-Online API','jurisdiction':'DE','category':'official_statistics','access_mode':'official_token_api','base_url':'https://www-genesis.destatis.de','docs_url':'https://www.destatis.de/DE/Service/OpenData/genesis-api-webservice-oberflaeche.html','terms_url':'https://www.destatis.de/DE/Service/Impressum/copyright.html','capabilities':['official_statistics','regional_context','economic_context','time_series'],'constraints':['token_required','aggregate_context_not_person_verification','licence_per_dataset']},
      {'source_id':'eu_dsa_transparency','title':'EU DSA Transparency Database','jurisdiction':'EU','category':'platform_transparency','access_mode':'official_research_api','base_url':'https://transparency.dsa.ec.europa.eu','docs_url':'https://transparency.dsa.ec.europa.eu/page/research-api','terms_url':'https://transparency.dsa.ec.europa.eu/page/documentation','capabilities':['content_moderation_statements','platform_patterns','recent_statistics'],'constraints':['research_api_not_bulk_collection','retention_window','no_person_guilt_inference']},
      {'source_id':'eu_whoiswho_search','title':'EU Whoiswho / Publications Office Search','jurisdiction':'EU','category':'official_directory','access_mode':'official_search_api_restricted','base_url':'https://op.europa.eu','docs_url':'https://op.europa.eu/en/web/webtools/search-api','terms_url':'https://op.europa.eu/en/web/about-us/legal-notices/accessibility-statement','capabilities':['eu_persons','organisations','roles','publications_linkage'],'constraints':['api_approval_may_be_required','official_role_context','terms_review']},
      {'source_id':'eu_state_aid_transparency','title':'EU State Aid Transparency Public Search','jurisdiction':'EU','category':'state_aid_awards','access_mode':'official_public_search','base_url':'https://webgate.ec.europa.eu','docs_url':'https://webgate.ec.europa.eu/competition/transparency/public','terms_url':'https://commission.europa.eu/legal-notice_en','capabilities':['aid_beneficiaries','awards','member_states','granting_authorities'],'constraints':['public_search','award_context_not_wrongdoing','parser_monitoring']},
    ]
    ANALYSIS_LIMITS={'exact_betweenness_nodes':2500,'default_sample_sources':128,'max_path_results':1000,'max_community_iterations':50}

    def __init__(self, db: Any, audit: Any, *, temporal_graph: Any, social_correlation: Any, multilingual: Any, european_sources: Any, actor: str='system'):
        self.db,self.audit,self.temporal_graph,self.social_correlation,self.multilingual,self.european_sources,self.actor=db,audit,temporal_graph,social_correlation,multilingual,european_sources,actor

    def seed_sources(self, *, confirmation: str) -> dict[str,Any]:
        if confirmation!='GRAPH SOURCES 177 ERWEITERN': raise PermissionError('explicit graph source approval required')
        for p in self.SOURCE_PROFILES:
            payload={**p,'status':'DOCUMENTED'}
            self.db.execute('INSERT OR REPLACE INTO graph_source_profiles_177 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(
                p['source_id'],p['title'],p['jurisdiction'],p['category'],p['access_mode'],p['base_url'],p['docs_url'],p['terms_url'],dumps(p['capabilities']),dumps(p['constraints']),'DOCUMENTED',now_ts(),_hash(payload)))
        return {'created':len(self.SOURCE_PROFILES),'production_active':0,'review_required':True}

    def create_graph(self, case_id: str, title: str, *, directed: bool=True, policy: Mapping[str,Any]|None=None, created_by: str|None=None, confirmation: str) -> dict[str,Any]:
        if confirmation!=f'GRAPH 177 {case_id} ANLEGEN': raise PermissionError('explicit graph approval required')
        graph_id=new_id('graph177'); created=now_ts(); pol={'review_first':True,'centrality_is_not_culpability':True,'source_filter_required':False,'automatic_identity_confirmation':False,**_clean(dict(policy or {}))}
        payload={'graph_id':graph_id,'case_id':case_id,'title':title,'directed':bool(directed),'policy':pol,'revision':0}
        self.db.execute('INSERT INTO scalable_graphs_177 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(graph_id,case_id,title,int(directed),dumps(pol),0,0,0,created_by or self.actor,created,created,_hash(payload)))
        self._event(graph_id,case_id,'graph_created',payload)
        return {**payload,'review_required':True}

    def upsert_nodes(self, graph_id: str, nodes: Sequence[Mapping[str,Any]], *, confirmation: str) -> dict[str,Any]:
        if confirmation!=f'GRAPH 177 {graph_id} KNOTEN IMPORTIEREN': raise PermissionError('explicit node import approval required')
        graph=self._graph(graph_id); created=updated=0
        for raw in nodes:
            node_id=str(raw.get('node_id') or raw.get('id') or '').strip()
            if not node_id: raise ValueError('node_id required')
            attrs=_clean(dict(raw.get('attributes') or {})); refs=[str(x) for x in raw.get('source_refs',[]) if str(x)]
            payload={'graph_id':graph_id,'node_id':node_id,'node_type':str(raw.get('node_type','entity')),'label':str(raw.get('label') or node_id),'attributes':attrs,'source_refs':refs,'confidence':float(raw.get('confidence',0.5)),'review_status':str(raw.get('review_status','needs_review')),'valid_from':raw.get('valid_from'),'valid_to':raw.get('valid_to'),'observed_at':raw.get('observed_at')}
            exists=self.db.one('SELECT 1 FROM scalable_graph_nodes_177 WHERE graph_id=? AND node_id=?',(graph_id,node_id))
            self.db.execute('INSERT OR REPLACE INTO scalable_graph_nodes_177 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(graph_id,node_id,payload['node_type'],payload['label'],dumps(attrs),dumps(refs),payload['confidence'],payload['review_status'],payload['valid_from'],payload['valid_to'],payload['observed_at'],_hash(payload),now_ts()))
            updated += int(bool(exists)); created += int(not exists)
        self._bump(graph_id); self._event(graph_id,graph['case_id'],'nodes_upserted',{'created':created,'updated':updated})
        return {'created':created,'updated':updated,'graph_id':graph_id,'review_required':True}

    def upsert_edges(self, graph_id: str, edges: Sequence[Mapping[str,Any]], *, confirmation: str) -> dict[str,Any]:
        if confirmation!=f'GRAPH 177 {graph_id} KANTEN IMPORTIEREN': raise PermissionError('explicit edge import approval required')
        graph=self._graph(graph_id); created=updated=0
        known={r['node_id'] for r in self.db.all('SELECT node_id FROM scalable_graph_nodes_177 WHERE graph_id=?',(graph_id,))}
        for raw in edges:
            src,tgt=str(raw.get('source_node','')),str(raw.get('target_node',''))
            if src not in known or tgt not in known: raise ValueError('edge endpoints must exist')
            edge_id=str(raw.get('edge_id') or _hash([src,tgt,raw.get('predicate','related_to'),raw.get('source_refs',[])])[:32])
            attrs=_clean(dict(raw.get('attributes') or {})); refs=[str(x) for x in raw.get('source_refs',[]) if str(x)]
            payload={'graph_id':graph_id,'edge_id':edge_id,'source_node':src,'target_node':tgt,'predicate':str(raw.get('predicate','related_to')),'directed':bool(raw.get('directed',graph['directed'])),'weight':max(0.0,float(raw.get('weight',1.0))),'attributes':attrs,'source_refs':refs,'confidence':float(raw.get('confidence',0.5)),'review_status':str(raw.get('review_status','needs_review')),'valid_from':raw.get('valid_from'),'valid_to':raw.get('valid_to'),'observed_at':raw.get('observed_at')}
            exists=self.db.one('SELECT 1 FROM scalable_graph_edges_177 WHERE graph_id=? AND edge_id=?',(graph_id,edge_id))
            self.db.execute('INSERT OR REPLACE INTO scalable_graph_edges_177 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(graph_id,edge_id,src,tgt,payload['predicate'],int(payload['directed']),payload['weight'],dumps(attrs),dumps(refs),payload['confidence'],payload['review_status'],payload['valid_from'],payload['valid_to'],payload['observed_at'],_hash(payload),now_ts()))
            updated += int(bool(exists)); created += int(not exists)
        self._bump(graph_id); self._event(graph_id,graph['case_id'],'edges_upserted',{'created':created,'updated':updated})
        return {'created':created,'updated':updated,'graph_id':graph_id,'review_required':True}

    def import_case_graph(self, graph_id: str, *, confirmation: str) -> dict[str,Any]:
        if confirmation!=f'GRAPH 177 {graph_id} FALLDATEN IMPORTIEREN': raise PermissionError('explicit case graph import approval required')
        graph=self._graph(graph_id); case_id=graph['case_id']; nodes=[]; edges=[]
        # Temporal graph entities/relations.
        try:
            for r in self.db.all('SELECT * FROM temporal_entities_159 WHERE case_id=?',(case_id,)):
                nodes.append({'node_id':r['entity_id'],'node_type':r['entity_type'],'label':r['label'],'attributes':loads(r['attributes_json'],{}),'source_refs':[],'confidence':1.0,'review_status':'needs_review'})
            for r in self.db.all('SELECT * FROM temporal_relations_159 WHERE case_id=?',(case_id,)):
                edges.append({'edge_id':r['relation_id'],'source_node':r['subject_id'],'target_node':r['object_id'],'predicate':r['predicate'],'confidence':r['confidence'],'review_status':r['status'],'valid_from':r['valid_from'],'valid_to':r['valid_to'],'observed_at':r['observed_at'],'source_refs':[r['source_ref']] if r['source_ref'] else []})
        except Exception: pass
        # Social accounts/interactions.
        try:
            for r in self.db.all('SELECT * FROM social_accounts_163 WHERE case_id=?',(case_id,)):
                nodes.append({'node_id':r['account_id'],'node_type':'account','label':r['display_name'] or r['handle'],'attributes':{'source_id':r['source_id'],'handle':r['handle']},'source_refs':[],'confidence':0.7,'review_status':r['review_status']})
            for r in self.db.all('SELECT * FROM social_interactions_163 WHERE case_id=?',(case_id,)):
                if r['actor_account_id'] and r['target_account_id']:
                    edges.append({'edge_id':r['interaction_id'],'source_node':r['actor_account_id'],'target_node':r['target_account_id'],'predicate':r['interaction_type'],'confidence':r['confidence'],'review_status':r['review_status'],'observed_at':r['observed_at'],'source_refs':[r['source_record_id']] if r['source_record_id'] else []})
        except Exception: pass
        # Ensure endpoints exist for observed social references.
        ids={n['node_id'] for n in nodes}
        for e in edges:
            for endpoint in (e['source_node'],e['target_node']):
                if endpoint not in ids:
                    nodes.append({'node_id':endpoint,'node_type':'reference','label':endpoint,'attributes':{},'source_refs':[],'confidence':0.4,'review_status':'needs_review'}); ids.add(endpoint)
        nr=self.upsert_nodes(graph_id,nodes,confirmation=f'GRAPH 177 {graph_id} KNOTEN IMPORTIEREN') if nodes else {'created':0,'updated':0}
        er=self.upsert_edges(graph_id,edges,confirmation=f'GRAPH 177 {graph_id} KANTEN IMPORTIEREN') if edges else {'created':0,'updated':0}
        return {'nodes':nr,'edges':er,'case_id':case_id,'review_required':True}

    def filter_graph(self, graph_id: str, *, node_types: Sequence[str]|None=None, predicates: Sequence[str]|None=None, min_confidence: float=0.0, review_statuses: Sequence[str]|None=None, valid_from: str|None=None, valid_to: str|None=None) -> dict[str,Any]:
        nodes=[dict(r) for r in self.db.all('SELECT * FROM scalable_graph_nodes_177 WHERE graph_id=?',(graph_id,))]
        if node_types: nodes=[n for n in nodes if n['node_type'] in set(node_types)]
        if review_statuses: nodes=[n for n in nodes if n['review_status'] in set(review_statuses)]
        nodes=[n for n in nodes if float(n['confidence'])>=min_confidence and _overlaps(n['valid_from'],n['valid_to'],valid_from,valid_to)]
        ids={n['node_id'] for n in nodes}
        edges=[dict(r) for r in self.db.all('SELECT * FROM scalable_graph_edges_177 WHERE graph_id=?',(graph_id,))]
        edges=[e for e in edges if e['source_node'] in ids and e['target_node'] in ids and float(e['confidence'])>=min_confidence and _overlaps(e['valid_from'],e['valid_to'],valid_from,valid_to)]
        if predicates: edges=[e for e in edges if e['predicate'] in set(predicates)]
        if review_statuses: edges=[e for e in edges if e['review_status'] in set(review_statuses)]
        return {'graph_id':graph_id,'nodes':nodes,'edges':edges,'node_count':len(nodes),'edge_count':len(edges),'filters':{'node_types':node_types,'predicates':predicates,'min_confidence':min_confidence,'review_statuses':review_statuses,'valid_from':valid_from,'valid_to':valid_to}}

    def analyze(self, graph_id: str, analysis_type: str, *, filters: Mapping[str,Any]|None=None, parameters: Mapping[str,Any]|None=None, confirmation: str) -> dict[str,Any]:
        if confirmation!=f'GRAPH ANALYSE 177 {graph_id} AUSFUEHREN': raise PermissionError('explicit graph analysis approval required')
        started=time.perf_counter(); graph=self._graph(graph_id); view=self.filter_graph(graph_id,**dict(filters or {})); params=dict(parameters or {})
        adj=self._adjacency(view,undirected=analysis_type in {'components','communities','bridges','key_nodes'})
        approximate=False
        if analysis_type=='components': result=self._components(adj)
        elif analysis_type=='degree': result=self._degree(adj)
        elif analysis_type=='shortest_path': result=self._shortest_path(adj,str(params.get('source')),str(params.get('target')))
        elif analysis_type=='bridges': result=self._bridges(adj)
        elif analysis_type=='communities': result=self._label_propagation(adj,max_iterations=min(self.ANALYSIS_LIMITS['max_community_iterations'],int(params.get('max_iterations',25))))
        elif analysis_type=='betweenness':
            sample=None
            if len(adj)>self.ANALYSIS_LIMITS['exact_betweenness_nodes']:
                sample=min(len(adj),int(params.get('sample_sources',self.ANALYSIS_LIMITS['default_sample_sources']))); approximate=True
            result=self._betweenness(adj,sample_sources=sample,seed=int(params.get('seed',177)))
        elif analysis_type=='key_nodes':
            degree=self._degree(adj)['scores']; between=self._betweenness(adj,sample_sources=min(len(adj),128) if len(adj)>2500 else None,seed=177)['scores']; approximate=len(adj)>2500
            scores={n:round(.45*degree.get(n,0)+.55*between.get(n,0),8) for n in adj}; result={'scores':dict(sorted(scores.items(),key=lambda x:x[1],reverse=True)),'limitations':['centrality_is_not_culpability','missing_private_or_unavailable_data','source_and_platform_bias','analyst_review_required']}
        else: raise ValueError('unsupported analysis type')
        duration=(time.perf_counter()-started)*1000; run_id=new_id('grun177'); payload={'run_id':run_id,'graph_id':graph_id,'analysis_type':analysis_type,'parameters':params,'filters':dict(filters or {}),'result':result,'graph_revision':graph['revision'],'node_count':view['node_count'],'edge_count':view['edge_count'],'duration_ms':duration,'approximation':approximate}
        self.db.execute('INSERT INTO graph_analysis_runs_177 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,graph_id,analysis_type,dumps({'parameters':params,'filters':dict(filters or {})}),dumps(result),graph['revision'],view['node_count'],view['edge_count'],duration,int(approximate),now_ts(),_hash(payload)))
        return {**payload,'review_required':True,'automatic_culpability_assessment':False}

    def benchmark(self, *, node_count: int=5000, edge_count: int=20000, confirmation: str) -> dict[str,Any]:
        if confirmation!='GRAPH BENCHMARK 177 AUSFUEHREN': raise PermissionError('explicit graph benchmark approval required')
        if node_count<10 or node_count>100_000 or edge_count<node_count-1 or edge_count>500_000: raise ValueError('benchmark outside contract')
        t0=time.perf_counter(); adj={str(i):set() for i in range(node_count)}
        for i in range(node_count-1): adj[str(i)].add(str(i+1)); adj[str(i+1)].add(str(i))
        rng=random.Random(177); remaining=edge_count-(node_count-1)
        for _ in range(remaining):
            a=str(rng.randrange(node_count)); b=str(rng.randrange(node_count))
            if a!=b: adj[a].add(b); adj[b].add(a)
        build_seconds=time.perf_counter()-t0; t1=time.perf_counter(); comps=self._components(adj); degree=self._degree(adj); analysis_seconds=time.perf_counter()-t1
        result={'components':comps['count'],'top_degree':list(degree['scores'].items())[:10],'contract_target':self.TARGET_CONTRACT,'executed_scale':{'nodes':node_count,'requested_edges':edge_count,'actual_edges':sum(map(len,adj.values()))//2},'method':'in_memory_adjacency_smoke_benchmark'}
        peak_est=sum(map(len,adj.values()))*72+node_count*256; bid=new_id('gbench177'); payload={'benchmark_id':bid,'node_count':node_count,'edge_count':result['executed_scale']['actual_edges'],'build_seconds':build_seconds,'analysis_seconds':analysis_seconds,'peak_memory_estimate_bytes':peak_est,'target_contract':self.TARGET_CONTRACT,'result':result}
        self.db.execute('INSERT INTO graph_benchmarks_177 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(bid,None,node_count,result['executed_scale']['actual_edges'],build_seconds,analysis_seconds,peak_est,dumps(self.TARGET_CONTRACT),dumps(result),now_ts(),_hash(payload)))
        return payload

    def source_coverage(self) -> dict[str,Any]:
        tables=('european_source_profiles_172','extended_source_profiles_173','media_source_profiles_174','geo_source_profiles_175','multilingual_source_profiles_176','graph_source_profiles_177')
        counts=[]
        for table in tables:
            try: counts.append(int(self.db.one(f'SELECT COUNT(*) n FROM {table}')['n']))
            except Exception: counts.append(0)
        payload={'total_documented_sources':sum(counts),'graph_sources':counts[-1],'production_active_new':0,'counts_by_layer':counts,'review_required':True}
        return {**payload,'payload_sha256':_hash(payload)}

    def _graph(self, graph_id: str) -> dict[str,Any]:
        r=self.db.one('SELECT * FROM scalable_graphs_177 WHERE graph_id=?',(graph_id,))
        if not r: raise KeyError('graph not found')
        return dict(r)

    def _bump(self,graph_id: str) -> None:
        n=int(self.db.one('SELECT COUNT(*) n FROM scalable_graph_nodes_177 WHERE graph_id=?',(graph_id,))['n']); e=int(self.db.one('SELECT COUNT(*) n FROM scalable_graph_edges_177 WHERE graph_id=?',(graph_id,))['n'])
        self.db.execute('UPDATE scalable_graphs_177 SET node_count=?,edge_count=?,revision=revision+1,updated_at=? WHERE graph_id=?',(n,e,now_ts(),graph_id)); self.db.execute('DELETE FROM graph_cache_177 WHERE graph_id=?',(graph_id,))

    def _adjacency(self,view: Mapping[str,Any],*,undirected: bool=False) -> dict[str,set[str]]:
        adj={n['node_id']:set() for n in view['nodes']}
        for e in view['edges']:
            adj[e['source_node']].add(e['target_node'])
            if undirected or not bool(e['directed']): adj[e['target_node']].add(e['source_node'])
        return adj

    def _components(self,adj: Mapping[str,set[str]]) -> dict[str,Any]:
        seen=set(); parts=[]
        for start in adj:
            if start in seen: continue
            q=[start]; seen.add(start); part=[]
            while q:
                n=q.pop(); part.append(n)
                for v in adj[n]:
                    if v not in seen: seen.add(v); q.append(v)
            parts.append(sorted(part))
        parts.sort(key=len,reverse=True); return {'count':len(parts),'components':parts,'largest_size':len(parts[0]) if parts else 0}

    def _degree(self,adj: Mapping[str,set[str]]) -> dict[str,Any]:
        den=max(1,len(adj)-1); scores={n:round(len(v)/den,8) for n,v in adj.items()}; return {'scores':dict(sorted(scores.items(),key=lambda x:x[1],reverse=True))}

    def _shortest_path(self,adj: Mapping[str,set[str]],source: str,target: str) -> dict[str,Any]:
        if source not in adj or target not in adj: return {'found':False,'path':[]}
        q=deque([source]); prev={source:None}
        while q:
            n=q.popleft()
            if n==target: break
            for v in adj[n]:
                if v not in prev: prev[v]=n; q.append(v)
        if target not in prev: return {'found':False,'path':[]}
        path=[]; cur=target
        while cur is not None: path.append(cur); cur=prev[cur]
        path.reverse(); return {'found':True,'path':path,'length':len(path)-1}

    def _bridges(self,adj: Mapping[str,set[str]]) -> dict[str,Any]:
        timer=0; tin={}; low={}; bridges=[]
        def dfs(v: str,p: str|None):
            nonlocal timer; timer+=1; tin[v]=low[v]=timer
            for to in adj[v]:
                if to==p: continue
                if to in tin: low[v]=min(low[v],tin[to])
                else:
                    dfs(to,v); low[v]=min(low[v],low[to])
                    if low[to]>tin[v]: bridges.append(sorted([v,to]))
        for n in adj:
            if n not in tin: dfs(n,None)
        bridges.sort(); return {'count':len(bridges),'bridges':bridges}

    def _label_propagation(self,adj: Mapping[str,set[str]],max_iterations: int=25) -> dict[str,Any]:
        labels={n:n for n in adj}; nodes=sorted(adj)
        for iteration in range(max_iterations):
            changed=0
            for n in nodes:
                if not adj[n]: continue
                counts=defaultdict(int)
                for v in adj[n]: counts[labels[v]]+=1
                best=min(((-c,l) for l,c in counts.items()))[1]
                if labels[n]!=best: labels[n]=best; changed+=1
            if not changed: break
        groups=defaultdict(list)
        for n,l in labels.items(): groups[l].append(n)
        communities=sorted((sorted(v) for v in groups.values()),key=len,reverse=True)
        return {'count':len(communities),'communities':communities,'iterations':iteration+1,'method':'deterministic_label_propagation'}

    def _betweenness(self,adj: Mapping[str,set[str]],sample_sources: int|None=None,seed: int=177) -> dict[str,Any]:
        nodes=list(adj); sources=nodes
        if sample_sources and sample_sources<len(nodes): sources=random.Random(seed).sample(nodes,sample_sources)
        cb={v:0.0 for v in nodes}
        for s in sources:
            stack=[]; pred={w:[] for w in nodes}; sigma=dict.fromkeys(nodes,0.0); sigma[s]=1.0; dist=dict.fromkeys(nodes,-1); dist[s]=0; q=deque([s])
            while q:
                v=q.popleft(); stack.append(v)
                for w in adj[v]:
                    if dist[w]<0: q.append(w); dist[w]=dist[v]+1
                    if dist[w]==dist[v]+1: sigma[w]+=sigma[v]; pred[w].append(v)
            delta=dict.fromkeys(nodes,0.0)
            while stack:
                w=stack.pop()
                for v in pred[w]: delta[v]+=(sigma[v]/sigma[w])*(1+delta[w]) if sigma[w] else 0
                if w!=s: cb[w]+=delta[w]
        scale=(len(nodes)/len(sources)) if sources else 1.0; den=max(1,(len(nodes)-1)*(len(nodes)-2))
        scores={n:round((cb[n]*scale)/den,8) for n in nodes}; return {'scores':dict(sorted(scores.items(),key=lambda x:x[1],reverse=True)),'sample_sources':len(sources),'approximate':len(sources)<len(nodes)}

    def _event(self,graph_id: str|None,case_id: str|None,event_type: str,details: Mapping[str,Any]) -> None:
        prev=self.db.one('SELECT event_sha256 FROM graph_events_177 WHERE graph_id=? ORDER BY created_at DESC LIMIT 1',(graph_id,)) if graph_id else None; previous=prev['event_sha256'] if prev else ''
        payload={'graph_id':graph_id,'case_id':case_id,'event_type':event_type,'details':_clean(dict(details)),'created_at':now_ts(),'previous_sha256':previous}; event_hash=_hash(payload)
        self.db.execute('INSERT INTO graph_events_177 VALUES(?,?,?,?,?,?,?,?)',(new_id('gev177'),graph_id,case_id,event_type,dumps(payload['details']),payload['created_at'],previous,event_hash))
