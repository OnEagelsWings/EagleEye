from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, secrets
from typing import Any, Mapping, Iterable

BUILD='413.0'
POLICY_ID='phase18.investigation-planner.v413'
MAX_SUBQUESTIONS=32
MAX_SEARCH_CONTEXT=20

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
def _norm(v): return ' '.join(str(v or '').split())

class InvestigationPlanner413:
    """Immutable, human-governed investigation planning over Phase-18 intelligence layers.

    Plans are decision support only. They do not execute searches, grant GO, stop work,
    determine truth, infer relationships/causality, or promote evidence.
    """
    def __init__(self,db,audit,*,registry405,fabric407,search408,quality409,temporal411,relationship412,governance,actor='local-analyst'):
        self.db=db; self.audit=audit; self.registry405=registry405; self.fabric407=fabric407; self.search408=search408; self.quality409=quality409; self.temporal411=temporal411; self.relationship412=relationship412; self.governance=governance; self.actor=actor; self._init_schema()
    def _init_schema(self):
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS investigation_plan_413(
          plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, objective TEXT NOT NULL,
          plan_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
          plan_hash TEXT NOT NULL, network_execution INTEGER NOT NULL,
          execution_authority INTEGER NOT NULL, automatic_go INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_investigation_plan_413_case ON investigation_plan_413(case_id,created_at);
        '''); self.db.conn.commit()
    def _authorize(self,identity,case_id,object_id=''):
        if not identity: raise PermissionError('active case identity required')
        return self.governance.authorize(identity,case_id=case_id,capability='research.run',object_type='investigation_plan_413',object_id=object_id or case_id)
    def _source_strategy(self):
        out=[]
        adapters={a['source_id']:a for a in self.fabric407.adapters()}
        for src in self.registry405.list_sources():
            ad=adapters.get(src['source_id'])
            if not ad or src.get('health_state')=='disabled': continue
            out.append({'source_id':src['source_id'],'adapter_kind':ad['adapter_kind'],'remote':ad['remote'],'requires_go':ad['requires_go'],'provenance_class':src.get('provenance_class',''),'health_state':src.get('health_state','unknown'),'network_execution':False})
        return sorted(out,key=lambda x:(x['remote'],x['adapter_kind'],x['source_id']))
    def _context(self,case_id,search_ids:Iterable[str]):
        context=[]
        for sid in list(search_ids or [])[:MAX_SEARCH_CONTEXT]:
            sess=self.search408.session(sid)
            if sess['case_id']!=case_id: raise PermissionError('search context belongs to another case')
            quality=self.quality409.assess(sid); temporal=self.temporal411.coverage(sid); graph=self.relationship412.graph(sid)
            context.append({'search_id':sid,'query':sess['query_text'],'retrieval_gaps':quality['gaps'],'source_coverage_ratio':quality['coverage']['source_coverage_ratio'],'temporal_gaps':temporal['temporal_gaps'],'explicit_temporal_coverage_ratio':temporal['explicit_temporal_coverage_ratio'],'explicit_graph_nodes':graph['node_count'],'explicit_graph_edges':graph['edge_count'],'unresolved_relationship_items':len(graph['malformed_or_unresolved'])})
        return context
    def create_plan(self,*,case_id,objective,subquestions,search_ids=None,identity:Mapping[str,Any]|None=None,risk_constraints=None,stop_conditions=None):
        case_id=_norm(case_id); objective=_norm(objective)
        if not case_id: raise ValueError('case_id required')
        if not objective: raise ValueError('objective required')
        self._authorize(identity,case_id)
        qs=[]
        for q in list(subquestions or []):
            q=_norm(q)
            if q and q not in qs: qs.append(q)
        if not qs: raise ValueError('at least one subquestion required')
        if len(qs)>MAX_SUBQUESTIONS: raise ValueError('too many subquestions')
        context=self._context(case_id,search_ids or [])
        source_strategy=self._source_strategy()
        default_stops=['objective_answered_with_reviewable_provenance','material_subquestions_exhausted_or_explicitly_deferred','new_collection_requires_scope_or_GO_not_yet_approved','risk_constraint_reached','diminishing_retrieval_yield_requires_human_review']
        stops=[_norm(x) for x in (stop_conditions or default_stops) if _norm(x)]
        default_risks=['case_scope_only','provenance_required','remote_collection_requires_separate_governed_execution','no_access_control_bypass','no_automatic_evidence_promotion','no_truth_determination','no_autonomous_scope_expansion']
        risks=[_norm(x) for x in (risk_constraints or default_risks) if _norm(x)]
        work=[]
        for i,q in enumerate(qs,1):
            work.append({'sequence':i,'subquestion':q,'recommended_source_ids':[s['source_id'] for s in source_strategy[:8]],'collection_state':'planned_not_executed','requires_human_go_for_remote_execution':any(s['remote'] for s in source_strategy[:8]),'success_criterion':'reviewable provenance-bearing information sufficient for analyst assessment'})
        plan={'build':BUILD,'case_id':case_id,'objective':objective,'subquestions':qs,'work_packages':work,'source_strategy':source_strategy,'existing_search_context':context,'stop_conditions':stops,'risk_constraints':risks,'planner_assumptions':['plan_is_decision_support_not_execution','coverage_gaps_are_not_proof_of_absence','relationship_graph_contains_explicit_structured_assertions_only','temporal_analysis_does_not_infer_causality'],'network_execution':False,'execution_authority':False,'automatic_go':False,'automatic_stop':False,'truth_determined':False,'automatic_evidence_promotion':False,'autonomous_scope_expansion':False}
        actor=str((identity or {}).get('user_id') or (identity or {}).get('username') or self.actor); now=_now(); body_hash=_sha(plan); pid='ip413_'+body_hash[:20]+'_'+secrets.token_hex(2); record_hash=_sha({'plan_id':pid,'plan':plan,'created_by':actor,'created_at':now})
        self.db.execute('INSERT INTO investigation_plan_413 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,objective,_canon(plan),actor,now,record_hash,0,0,0))
        self.audit.log('investigation_plan_created_413','investigation_plan_413',pid,case_id,{'objective_hash':_sha(objective),'subquestions':len(qs),'search_contexts':len(context),'network_requests':0,'execution_authority':False,'automatic_go':False})
        return self.get_plan(pid)
    def get_plan(self,plan_id):
        r=self.db.one('SELECT * FROM investigation_plan_413 WHERE plan_id=?',(plan_id,))
        if not r: raise KeyError('investigation plan not found')
        d=dict(r); d['plan']=json.loads(d.pop('plan_json')); d['network_execution']=bool(d['network_execution']); d['execution_authority']=bool(d['execution_authority']); d['automatic_go']=bool(d['automatic_go']); return d
    def list_plans(self,case_id): return [self.get_plan(r['plan_id']) for r in self.db.all('SELECT plan_id FROM investigation_plan_413 WHERE case_id=? ORDER BY created_at,plan_id',(case_id,))]
    def verify_integrity(self):
        bad=[]
        for r in self.db.all('SELECT * FROM investigation_plan_413'):
            d=dict(r)
            try: plan=json.loads(d['plan_json'])
            except Exception: bad.append({'plan_id':d['plan_id'],'reason':'invalid_plan_json'}); continue
            expected=_sha({'plan_id':d['plan_id'],'plan':plan,'created_by':d['created_by'],'created_at':d['created_at']})
            if expected!=d['plan_hash']: bad.append({'plan_id':d['plan_id'],'reason':'plan_hash_mismatch'})
            if bool(d['network_execution']) or bool(d['execution_authority']) or bool(d['automatic_go']): bad.append({'plan_id':d['plan_id'],'reason':'forbidden_authority_flag'})
        return {'build':BUILD,'valid':not bad,'violations':bad,'immutable_plan_records':True}
    def status(self):
        n=int((self.db.one('SELECT COUNT(*) c FROM investigation_plan_413') or {}).get('c',0)); integ=self.verify_integrity()
        return {'build':BUILD,'policy':POLICY_ID,'investigation_planner':True,'plans':n,'integrity_valid':integ['valid'],'case_scoped_authorization':True,'objective_and_subquestions':True,'source_strategy':True,'stop_conditions':True,'risk_constraints':True,'phase18_context_aware':True,'immutable_plan_records':True,'network_execution':False,'execution_authority':False,'automatic_go':False,'automatic_stop':False,'truth_determined':False,'automatic_evidence_promotion':False,'autonomous_scope_expansion':False}
