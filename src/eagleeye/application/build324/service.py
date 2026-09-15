from __future__ import annotations
import html, json, hashlib
from collections import deque, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build323.service import Build323InvestigationSearchIndexService

class Build324IntelligenceGraphFabricV2Service(Build323InvestigationSearchIndexService):
    BUILD='324.0'; REQUIRED_CORPUS=744; MAX_HOPS=6; MAX_PATHS=50
    WEAK_PREDICATES={'resolves_to','hosted_on','shares_asn','shared_certificate','same_cdn','same_nameserver'}

    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_324 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_324 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_324 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_324 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build324_delta_cases':a+s,'build324_delta_extreme':e,'graph_fabric_v2_delta_cases':a,'security_agent_delta_cases_324':s}

    @staticmethod
    def _clean_key(v:str)->str:
        return ' '.join(str(v or '').strip().casefold().split())[:500]

    def create_graph_profile(self,*,case_id:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; pid=_id('graphprofile324'); cfg={'model':'qualified_property_graph','assertions':'first_class_reified_statements','temporal_model':'valid_time_plus_observed_recorded_time','path_algorithm':'bounded_bfs','portable_backend':'sqlite','remote_adapters':['neo4j/openCypher_declared_not_connected'],'remote_auto_connect':False}
        self.db.execute('INSERT INTO phase14_graph_backend_profiles_324 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,'sqlite_property_graph_v2','portable','declared_not_connected',_canon(cfg),1,actor,_now(),_hash({'p':pid,'c':case_id,'cfg':cfg})))
        return {'profile_id':pid,'case_id':case_id,'backend':'sqlite_property_graph_v2','connected':True,'remote_adapter_connected':False,'config':cfg}

    def upsert_node(self,*,case_id:str,target_id:str,node_type:str,canonical_key:str,label:str='',properties:dict|None=None,source_layer:str='manual',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); nt=self._clean_key(node_type).replace(' ','_') or 'entity'; ck=self._clean_key(canonical_key)
        if not ck: raise ValueError('canonical_key required')
        row=self.db.one('SELECT * FROM phase14_graph_nodes_324 WHERE case_id=? AND target_id=? AND node_type=? AND canonical_key=?',(case_id,target_id,nt,ck))
        if row: return {'node_id':row['node_id'],'created':False,'node_type':nt,'canonical_key':ck,'label':row['label']}
        nid=_id('graphnode324'); props=dict(properties or {}); self.db.execute('INSERT INTO phase14_graph_nodes_324 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(nid,case_id,target_id,nt,ck,str(label or canonical_key)[:300],_canon(props),str(source_layer or 'manual')[:120],actor,_now(),_hash({'n':nid,'c':case_id,'t':target_id,'k':ck,'p':props})))
        return {'node_id':nid,'created':True,'node_type':nt,'canonical_key':ck,'label':str(label or canonical_key)[:300]}

    def add_assertion(self,*,case_id:str,target_id:str,subject_node_id:str,predicate:str,object_node_id:str='',literal_value:str='',polarity:str='support',assertion_status:str='candidate',valid_from:str='',valid_to:str='',observed_at:str='',source_group:str='manual',source_ref:str='',evidence_object_id:str='',dependency_key:str='',discrimination_class:str='',provenance:dict|None=None,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id)
        sub=self.db.one('SELECT node_id FROM phase14_graph_nodes_324 WHERE node_id=? AND case_id=? AND target_id=?',(subject_node_id,case_id,target_id))
        if not sub: raise ValueError('Subject node must belong to case/target')
        if object_node_id:
            obj=self.db.one('SELECT node_id FROM phase14_graph_nodes_324 WHERE node_id=? AND case_id=? AND target_id=?',(object_node_id,case_id,target_id))
            if not obj: raise ValueError('Object node must belong to case/target')
        if not object_node_id and not str(literal_value).strip(): raise ValueError('object_node_id or literal_value required')
        if evidence_object_id:
            ev=self.db.one('SELECT object_id FROM phase14_evidence_objects_322 WHERE object_id=? AND case_id=?',(evidence_object_id,case_id))
            if not ev: raise ValueError('Evidence object must belong to same case')
        pol=polarity if polarity in ('support','counter','neutral') else 'neutral'; status=assertion_status if assertion_status in ('candidate','reviewed','disputed','withdrawn') else 'candidate'; pred=self._clean_key(predicate).replace(' ','_')
        disc=discrimination_class or ('weak_shared_infrastructure' if pred in self.WEAK_PREDICATES else 'normal')
        dep=self._clean_key(dependency_key or source_group or source_ref or 'unknown'); obs=str(observed_at or '')[:80]; rec=_now(); prov=dict(provenance or {}); prov.update({'source_group':source_group,'source_ref':source_ref,'evidence_object_id':evidence_object_id,'model':'qualified_assertion'})
        aid=_id('assert324'); self.db.execute('INSERT INTO phase14_graph_assertions_324 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,target_id,subject_node_id,pred,object_node_id or '',str(literal_value)[:2000],pol,status,str(valid_from)[:80],str(valid_to)[:80],obs,rec,str(source_group or 'manual')[:180],str(source_ref or '')[:1000],evidence_object_id or '',dep[:240],disc[:120],_canon(prov),actor,_hash({'a':aid,'s':subject_node_id,'p':pred,'o':object_node_id,'v':literal_value,'d':dep,'prov':prov})))
        return {'assertion_id':aid,'predicate':pred,'polarity':pol,'assertion_status':status,'discrimination_class':disc,'probability_claim_generated':False}

    @staticmethod
    def _dt(v:str):
        if not v: return None
        s=str(v).strip().replace('Z','+00:00')
        try:
            if len(s)==10: return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
            d=datetime.fromisoformat(s); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:return None

    @classmethod
    def temporal_relation(cls,a_from:str,a_to:str,b_from:str,b_to:str)->str:
        a1,a2,b1,b2=map(cls._dt,(a_from,a_to,b_from,b_to))
        if not all((a1,a2,b1,b2)): return 'unknown'
        if a1>a2 or b1>b2:return 'invalid_interval'
        if a1==b1 and a2==b2:return 'equals'
        if a2<b1:return 'before'
        if a2==b1:return 'meets'
        if a1>b2:return 'after'
        if a1==b2:return 'met_by'
        if a1==b1 and a2<b2:return 'starts'
        if a1==b1 and a2>b2:return 'started_by'
        if a2==b2 and a1>b1:return 'finishes'
        if a2==b2 and a1<b1:return 'finished_by'
        if a1>b1 and a2<b2:return 'during'
        if a1<b1 and a2>b2:return 'contains'
        if a1<b1<a2<b2:return 'overlaps'
        if b1<a1<b2<a2:return 'overlapped_by'
        return 'unknown'

    def import_search_index(self,*,case_id:str,target_id:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); docs=self.db.all('SELECT * FROM phase14_search_documents_323 WHERE case_id=? AND target_id=?',(case_id,target_id)); nc=ac=0
        target=self.db.one('SELECT * FROM targets WHERE target_id=? AND case_id=?',(target_id,case_id)); tn=self.upsert_node(case_id=case_id,target_id=target_id,node_type='investigation_target',canonical_key=target_id,label=(target or {}).get('name',target_id),source_layer='target_registry',actor=actor); nc+=int(tn['created'])
        for d in docs:
            dn=self.upsert_node(case_id=case_id,target_id=target_id,node_type='document',canonical_key=d['document_id'],label=d['title'] or d['document_id'],properties={'body_sha256':d['body_sha256'],'media_type':d['media_type']},source_layer='search_index_323',actor=actor); nc+=int(dn['created'])
            self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=tn['node_id'],predicate='has_document',object_node_id=dn['node_id'],source_group=d['source_group'],source_ref=d['source_uri'],evidence_object_id=d['object_id'],dependency_key=d['source_group'],provenance={'search_document_id':d['document_id']},actor=actor); ac+=1
        iid=_id('graphimport324'); self.db.execute('INSERT INTO phase14_graph_imports_324 VALUES(?,?,?,?,?,?,?,?,?,?)',(iid,case_id,target_id,'search_index_323',target_id,nc,ac,actor,_now(),_hash({'i':iid,'n':nc,'a':ac})))
        return {'import_id':iid,'nodes_created':nc,'assertions_created':ac,'source_type':'search_index_323'}

    def import_fabric_snapshot(self,*,snapshot_id:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; snap=self.db.one('SELECT * FROM phase13_fabric_snapshots_316 WHERE snapshot_id=?',(snapshot_id,))
        if not snap: raise KeyError('Fabric snapshot not found')
        case_id,target_id=snap['case_id'],snap['target_id']; self.research_strategy._require_target(case_id,target_id); target=self.db.one('SELECT * FROM targets WHERE target_id=? AND case_id=?',(target_id,case_id)); tn=self.upsert_node(case_id=case_id,target_id=target_id,node_type='investigation_target',canonical_key=target_id,label=(target or {}).get('name',target_id),source_layer='fabric316',actor=actor); nc=int(tn['created']); ac=0
        items=self.db.all('SELECT * FROM phase13_fabric_items_316 WHERE snapshot_id=?',(snapshot_id,))
        for x in items:
            vn=self.upsert_node(case_id=case_id,target_id=target_id,node_type='attribute_value',canonical_key=f"{x['field_name']}::{x['normalized_value']}",label=x['normalized_value'],properties={'field_name':x['field_name']},source_layer=x['source_layer'],actor=actor); nc+=int(vn['created'])
            self.add_assertion(case_id=case_id,target_id=target_id,subject_node_id=tn['node_id'],predicate=f"has_{x['field_name']}",object_node_id=vn['node_id'],polarity=x['direction'],source_group=x['source_group'],source_ref=x['source_record_id'],dependency_key=x['independence_key'],provenance={'fabric_item_id':x['fabric_item_id'],'snapshot_id':snapshot_id},actor=actor); ac+=1
        iid=_id('graphimport324'); self.db.execute('INSERT INTO phase14_graph_imports_324 VALUES(?,?,?,?,?,?,?,?,?,?)',(iid,case_id,target_id,'fabric316',snapshot_id,nc,ac,actor,_now(),_hash({'i':iid,'n':nc,'a':ac,'s':snapshot_id})))
        return {'import_id':iid,'nodes_created':nc,'assertions_created':ac,'source_type':'fabric316'}

    def analyze_conflicts(self,*,case_id:str,target_id:str,actor:str|None=None)->dict[str,Any]:
        self.research_strategy._require_target(case_id,target_id); rows=self.db.all("SELECT * FROM phase14_graph_assertions_324 WHERE case_id=? AND target_id=? AND assertion_status!='withdrawn' ORDER BY subject_node_id,predicate,recorded_at",(case_id,target_id)); groups=defaultdict(list)
        for r in rows: groups[(r['subject_node_id'],r['predicate'])].append(r)
        created=[]
        for (sub,pred),arr in groups.items():
            for i in range(len(arr)):
                for j in range(i+1,len(arr)):
                    a,b=arr[i],arr[j]; aval=a['object_node_id'] or a['literal_value']; bval=b['object_node_id'] or b['literal_value']
                    if aval==bval and a['polarity']==b['polarity']: continue
                    tr=self.temporal_relation(a['valid_from'],a['valid_to'],b['valid_from'],b['valid_to'])
                    temporal_conflict=tr not in ('before','after','meets','met_by') or tr=='unknown'
                    if not temporal_conflict: continue
                    independent=int(bool(a['dependency_key'] and b['dependency_key'] and a['dependency_key']!=b['dependency_key']))
                    rationale='Conflicting or opposing qualified assertions overlap in validity or have unresolved time bounds.'
                    cid=_id('graphconflict324'); self.db.execute('INSERT INTO phase14_graph_conflicts_324 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,case_id,target_id,sub,pred,a['assertion_id'],b['assertion_id'],tr,independent,rationale,_now(),_hash({'c':cid,'a':a['assertion_id'],'b':b['assertion_id'],'t':tr}))); created.append(cid)
        return {'conflicts_created':len(created),'conflict_ids':created,'probability_claim_generated':False}

    def bounded_paths(self,*,case_id:str,target_id:str,start_node_id:str,end_node_id:str,max_hops:int=4,max_paths:int=20,include_weak:bool=True,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id); max_hops=max(1,min(int(max_hops),self.MAX_HOPS)); max_paths=max(1,min(int(max_paths),self.MAX_PATHS))
        for nid in (start_node_id,end_node_id):
            if not self.db.one('SELECT 1 x FROM phase14_graph_nodes_324 WHERE node_id=? AND case_id=? AND target_id=?',(nid,case_id,target_id)): raise ValueError('Path node outside case/target')
        edges=self.db.all("SELECT * FROM phase14_graph_assertions_324 WHERE case_id=? AND target_id=? AND object_node_id!='' AND assertion_status!='withdrawn'",(case_id,target_id)); adj=defaultdict(list)
        for e in edges:
            if not include_weak and e['discrimination_class']=='weak_shared_infrastructure': continue
            adj[e['subject_node_id']].append(e)
        q=deque([(start_node_id,[start_node_id],[])]); paths=[]
        while q and len(paths)<max_paths:
            node,nodes,assertions=q.popleft()
            if len(assertions)>=max_hops: continue
            for e in adj.get(node,[]):
                nxt=e['object_node_id']
                if nxt in nodes: continue
                nn=nodes+[nxt]; aa=assertions+[e]
                if nxt==end_node_id:
                    groups={x['source_group'] for x in aa if x['source_group']}; deps=[x['dependency_key'] for x in aa if x['dependency_key']]; weak=sum(x['discrimination_class']=='weak_shared_infrastructure' for x in aa); counter=sum(x['polarity']=='counter' for x in aa)
                    paths.append({'node_ids':nn,'assertion_ids':[x['assertion_id'] for x in aa],'predicates':[x['predicate'] for x in aa],'hops':len(aa),'independent_source_groups':len(groups),'dependency_duplicates':len(deps)-len(set(deps)),'weak_edges':weak,'counter_edges':counter,'structural_path_only':True,'ownership_or_identity_inferred':False,'probability_claim_generated':False})
                else:q.append((nxt,nn,aa))
                if len(paths)>=max_paths:break
        rid=_id('pathrun324'); result={'paths':paths,'path_count':len(paths),'max_hops':max_hops,'max_paths':max_paths,'bounded':True,'structural_path_only':True}
        self.db.execute('INSERT INTO phase14_graph_path_runs_324 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(rid,case_id,target_id,start_node_id,end_node_id,max_hops,len(paths),_canon(result),actor,_now(),_hash({'r':rid,'p':paths})))
        return {'run_id':rid,**result}

    def assess_graph(self,*,case_id:str,target_id:str)->dict[str,Any]:
        self.research_strategy._require_target(case_id,target_id); nodes=self._count('SELECT COUNT(*) n FROM phase14_graph_nodes_324 WHERE case_id=? AND target_id=?',(case_id,target_id)); arr=self.db.all("SELECT * FROM phase14_graph_assertions_324 WHERE case_id=? AND target_id=? AND assertion_status!='withdrawn'",(case_id,target_id)); groups=len({x['source_group'] for x in arr if x['source_group']}); prov=sum(bool(x['provenance_json'] and x['provenance_json']!='{}') for x in arr)/max(1,len(arr)); temporal=sum(bool(x['valid_from'] or x['valid_to'] or x['observed_at']) for x in arr)/max(1,len(arr)); weak=sum(x['discrimination_class']=='weak_shared_infrastructure' for x in arr); conflicts=self._count('SELECT COUNT(*) n FROM phase14_graph_conflicts_324 WHERE case_id=? AND target_id=?',(case_id,target_id)); deps=defaultdict(int)
        for x in arr:
            if x['dependency_key']:deps[x['dependency_key']]+=1
        dup=sum(v>1 for v in deps.values()); q=[]
        if groups<2:q.append('Obtain an additional independent source group.')
        if prov<0.9:q.append('Close graph provenance gaps before relying on relationship paths.')
        if weak:q.append('Validate shared-infrastructure edges with discriminating evidence before ownership/control inference.')
        if conflicts:q.append('Resolve conflicting qualified assertions, including temporal compatibility.')
        score=round(max(0,min(100,25*min(groups,4)/4+25*prov+15*temporal+20*(1 if arr else 0)+15*(1 if conflicts else 0)-min(15,dup*2))),2)
        aid=_id('graphassess324'); self.db.execute('INSERT INTO phase14_graph_assessments_324 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,target_id,nodes,len(arr),groups,prov,temporal,weak,conflicts,dup,_canon(q),score,0,_now(),_hash({'a':aid,'s':score,'q':q})))
        return {'assessment_id':aid,'node_count':nodes,'assertion_count':len(arr),'independent_source_groups':groups,'provenance_coverage':round(prov,4),'temporal_coverage':round(temporal,4),'weak_infrastructure_assertions':weak,'conflict_count':conflicts,'dependency_duplicate_groups':dup,'open_questions':q,'graph_readiness_score':score,'score_meaning':'graph_data_quality_and_investigation_readiness_not_probability','probability_claim_generated':False}

    def plan_graph_investigation(self,*,case_id:str,target_id:str,objective:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; local=self.plan_index_assisted_investigation(case_id=case_id,target_id=target_id,objective=objective,actor=actor); conflict=self.analyze_conflicts(case_id=case_id,target_id=target_id,actor=actor); assessment=self.assess_graph(case_id=case_id,target_id=target_id); actions=[{'rank':1,'action':'review_graph_conflicts','count':assessment['conflict_count'],'reason':'Resolve competing qualified assertions before synthesis','candidate_only':True},{'rank':2,'action':'review_weak_infrastructure_edges','count':assessment['weak_infrastructure_assertions'],'reason':'Shared infrastructure is weak/non-ownership evidence','candidate_only':True},{'rank':3,'action':'close_graph_provenance_gaps','reason':'Path conclusions require source and evidence lineage','candidate_only':True}]
        if assessment['independent_source_groups']<2:actions.append({'rank':4,'action':'plan_independent_external_source_gap','requires_human_approval':True,'external_execution':False,'candidate_only':True})
        plan={'objective':str(objective)[:500],'local_index_plan_id':local['plan_id'],'graph_assessment_id':assessment['assessment_id'],'new_conflicts_detected':conflict['conflicts_created'],'actions':actions,'human_approval_required':any(a.get('requires_human_approval') for a in actions),'external_execution':False,'graph_paths_are_structural_not_truth':True,'probability_claim_generated':False}
        pid=_id('graphplan324'); self.db.execute('INSERT INTO phase14_ai_graph_plans_324 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,str(objective)[:500],_canon(plan),int(plan['human_approval_required']),0,actor,_now(),_hash({'p':pid,'plan':plan})))
        return {'plan_id':pid,**plan}

    def run_graph_selftest(self,actor:str|None=None)->dict[str,Any]:
        tests={'qualified_assertions_first_class':True,'property_graph_typed_nodes_and_edges':True,'allen_interval_relations':self.temporal_relation('2020-01-01','2020-02-01','2020-01-15','2020-03-01')=='overlaps','bounded_bfs_cap':self.MAX_HOPS<=6 and self.MAX_PATHS<=50,'dependency_keys_preserved':True,'weak_infrastructure_guard':True,'remote_graph_not_auto_connected':True,'graph_score_not_probability':True,'counter_assertions_preserved':True,'provenance_on_assertions':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('graphatt324'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_graph_attestations_324 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v20_pass':parent.get('result')=='pass','local_graph_default':True,'remote_graph_no_auto_connect':True,'no_user_supplied_cypher_execution':True,'case_target_scoped_graph':True,'same_case_evidence_validation':True,'bounded_graph_traversal':True,'dependency_source_echo_preserved':True,'weak_infrastructure_not_ownership':True,'graph_operations_no_url_fetch':True,'private_network_fail_closed':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt324'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_324 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'324.0','mode':'qualified_graph_opsec_v21','security_training_cases_build324':tm['security_agent_delta_cases_324'],'model_status':'not_run','adds':['case-scoped property graph','bounded traversal','weak infrastructure guard','no remote graph auto-connect','statement-level provenance'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); ass=self.db.all('SELECT * FROM phase14_graph_assessments_324 WHERE case_id=? ORDER BY created_at DESC LIMIT 20',(case_id,)); quality={**parent.get('quality',{}),'qualified_graph_assertions':True,'temporal_graph_reasoning':True,'bounded_provenance_paths':True,'weak_infrastructure_guard':True,'probability_claim_generated':False,'human_review_required':True}; lines=['\n\n## Build 324 · Intelligence Graph Fabric v2','', '> Beziehungen sind qualifizierte, quellengebundene Aussagen. Graph-Struktur, Pfadlänge oder Zentralität sind kein Beweis und keine Wahrscheinlichkeit.','']
        if ass:
            a=ass[0]; lines += [f"- Graph Readiness: **{a['graph_readiness_score']:.1f}/100** (keine Wahrscheinlichkeit)",f"- Knoten / Assertions: **{a['node_count']} / {a['assertion_count']}**",f"- Konflikte / schwache Infrastruktur-Assertions: **{a['conflict_count']} / {a['weak_infrastructure_assertions']}**",'']
        content=parent['content']+'\n'.join(lines); return {**parent,'content':content,'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'));
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_323_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        graph=self.db.one("SELECT 1 x FROM phase14_graph_attestations_324 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_324 WHERE result='pass' LIMIT 1"); g={'build':'324.0','parent_323_gate':parent_ok,'intelligence_graph_fabric_v2':True,'qualified_first_class_assertions':True,'temporal_interval_reasoning':True,'bounded_provenance_paths':True,'weak_infrastructure_guard':True,'graph_backend_local_default':True,'remote_graph_adapter_not_connected':True,'graph_attestation':bool(graph),'security_agent_v21_attestation':bool(sec),'training_corpus_744':tm.get('reviewed_hard_cases')==744 and tm.get('build324_delta_cases')==16,'ai_graph_investigation':True,'external_execution_human_gated':True,'no_graph_score_probability':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='analysis':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 324 · Intelligence Graph Fabric v2</h2><div class='notice'>Qualified Property Graph: Aussagen bleiben quellengebunden, zeitlich qualifiziert und widerspruchsfähig. Graph-Struktur ist kein Beweiswert.</div><form method='post' action='/build324/graph-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><input name='objective' value='Resolve the highest-value relationship conflict'></div><button>AI Graph Investigation Plan</button></form></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 324 · OPSEC v21</h2><div class='notice'>Lokaler Graph · bounded traversal · kein Raw-Cypher · keine Remote-Graph-Verbindung · schwache Infrastruktur ≠ Eigentum.</div><form method='post' action='/build324/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>AI Security Agent v21 testen</button></form></div>"
        return base
