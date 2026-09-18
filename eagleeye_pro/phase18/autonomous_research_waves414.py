from __future__ import annotations
from datetime import datetime, timezone
import hashlib,json,secrets
from typing import Any,Mapping
BUILD='414.0'; POLICY_ID='phase18.bounded-autonomous-research-waves.v414'; CONFIRM='AUTHORIZE RESEARCH WAVES'
def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
class AutonomousResearchWaves414:
    '''Bounded research-wave controller. Autonomy begins only after explicit human authorization and remains inside the immutable Build-413 plan envelope. This layer plans/advances work; connector/network execution remains delegated to governed execution layers.'''
    def __init__(self,db,audit,*,planner413,search408,quality409,temporal411,relationship412,governance,actor='local-analyst'):
        self.db=db; self.audit=audit; self.planner413=planner413; self.search408=search408; self.quality409=quality409; self.temporal411=temporal411; self.relationship412=relationship412; self.governance=governance; self.actor=actor; self._init_schema()
    def _init_schema(self):
        self.db.conn.executescript('''CREATE TABLE IF NOT EXISTS autonomous_wave_run_414(run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,plan_id TEXT NOT NULL,plan_hash TEXT NOT NULL,state TEXT NOT NULL,current_wave INTEGER NOT NULL,max_waves INTEGER NOT NULL,budget_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,record_hash TEXT NOT NULL); CREATE TABLE IF NOT EXISTS autonomous_wave_step_414(step_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,wave_number INTEGER NOT NULL,decision TEXT NOT NULL,reason_json TEXT NOT NULL,work_json TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL); CREATE INDEX IF NOT EXISTS idx_wave414_case ON autonomous_wave_run_414(case_id,created_at);'''); self.db.conn.commit()
    def _auth(self,identity,case_id,obj=''):
        if not identity: raise PermissionError('active case identity required')
        self.governance.authorize(dict(identity),case_id=case_id,capability='research.run',object_type='autonomous_research_wave_414',object_id=obj or case_id)
    def _record_hash(self,r): return _sha({k:r[k] for k in r if k!='record_hash'})
    def create_run(self,*,plan_id,identity:Mapping[str,Any]|None=None,max_waves=5,max_searches_per_wave=8):
        p=self.planner413.get_plan(plan_id); cid=p['case_id']; self._auth(identity,cid,plan_id)
        if not 1<=int(max_waves)<=20 or not 1<=int(max_searches_per_wave)<=20: raise ValueError('wave budget outside allowed bounds')
        budget={'max_waves':int(max_waves),'max_searches_per_wave':int(max_searches_per_wave),'scope_expansion':False,'remote_execution_requires_separate_go':True,'automatic_evidence_promotion':False}
        rid='arw414_'+secrets.token_hex(10); now=_now(); r={'run_id':rid,'case_id':cid,'plan_id':plan_id,'plan_hash':p['plan_hash'],'state':'awaiting_human_authorization','current_wave':0,'max_waves':int(max_waves),'budget_json':_canon(budget),'created_by':str((identity or {}).get('user_id') or (identity or {}).get('username') or self.actor),'created_at':now,'updated_at':now}; r['record_hash']=self._record_hash(r)
        self.db.execute('INSERT INTO autonomous_wave_run_414 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.values())); self.audit.log('research_wave_run_created_414','autonomous_wave_run_414',rid,cid,{'plan_id':plan_id,'automatic_go':False,'network_requests':0}); return self.run(rid)
    def authorize(self,*,run_id,identity:Mapping[str,Any]|None=None,confirmation=''):
        r=self.run(run_id); self._auth(identity,r['case_id'],run_id)
        if str(confirmation).strip().upper()!=CONFIRM: raise PermissionError(f'explicit confirmation {CONFIRM} required')
        if r['state']!='awaiting_human_authorization': raise ValueError('run is not awaiting authorization')
        self._update(run_id,'active'); self.audit.log('research_wave_envelope_authorized_414','autonomous_wave_run_414',run_id,r['case_id'],{'bounded_autonomy':True,'direct_network_authority':False,'automatic_go_issuance':False}); return self.run(run_id)
    def _update(self,rid,state,current=None):
        r=dict(self.db.one('SELECT * FROM autonomous_wave_run_414 WHERE run_id=?',(rid,))); r['state']=state; r['updated_at']=_now(); r['current_wave']=int(r['current_wave'] if current is None else current); r['record_hash']=self._record_hash(r); self.db.execute('UPDATE autonomous_wave_run_414 SET state=?,current_wave=?,updated_at=?,record_hash=? WHERE run_id=?',(r['state'],r['current_wave'],r['updated_at'],r['record_hash'],rid))
    def advance(self,*,run_id,identity:Mapping[str,Any]|None=None):
        r=self.run(run_id); self._auth(identity,r['case_id'],run_id)
        if r['state']!='active': raise PermissionError('bounded autonomy is not active')
        p=self.planner413.get_plan(r['plan_id']);
        if p['plan_hash']!=r['plan_hash']: self._update(run_id,'hold'); raise PermissionError('bound investigation plan changed')
        n=r['current_wave']+1; budget=r['budget']; work=p['plan']['work_packages'][(n-1)%len(p['plan']['work_packages'])]; contexts=p['plan']['existing_search_context']; reasons=[]
        for x in contexts:
            if x.get('retrieval_gaps'): reasons.append('retrieval_gap')
            if x.get('temporal_gaps'): reasons.append('temporal_gap')
            if x.get('unresolved_relationship_items'): reasons.append('relationship_resolution_gap')
        decision='stop' if n>r['max_waves'] else 'continue'
        if decision=='continue' and not reasons: reasons=['planned_subquestion_not_yet_exhausted']
        payload={'subquestion':work['subquestion'],'recommended_source_ids':work['recommended_source_ids'][:r['budget']['max_searches_per_wave']],'collection_state':'proposed_not_executed','remote_execution_requires_separate_go':True,'network_execution':False}
        sid='ws414_'+secrets.token_hex(10); now=_now(); s={'step_id':sid,'run_id':run_id,'wave_number':n,'decision':decision,'reason_json':_canon(reasons),'work_json':_canon(payload),'created_at':now}; s['record_hash']=self._record_hash(s); self.db.execute('INSERT INTO autonomous_wave_step_414 VALUES(?,?,?,?,?,?,?,?)',tuple(s.values()))
        self._update(run_id,'completed' if decision=='stop' or n>=r['max_waves'] else 'active',min(n,r['max_waves'])); return self.step(sid)
    def run(self,rid):
        r=self.db.one('SELECT * FROM autonomous_wave_run_414 WHERE run_id=?',(rid,));
        if not r: raise KeyError('research wave run not found')
        d=dict(r); d['budget']=json.loads(d.pop('budget_json')); return d
    def step(self,sid):
        r=self.db.one('SELECT * FROM autonomous_wave_step_414 WHERE step_id=?',(sid,));
        if not r: raise KeyError(sid)
        d=dict(r); d['reasons']=json.loads(d.pop('reason_json')); d['work']=json.loads(d.pop('work_json')); return d
    def verify_integrity(self):
        bad=[]
        for r in self.db.all('SELECT * FROM autonomous_wave_run_414'):
            d=dict(r)
            if self._record_hash(d)!=d['record_hash']: bad.append({'run_id':d['run_id'],'reason':'run_hash_mismatch'})
            try:
                p=self.planner413.get_plan(d['plan_id'])
                if p['case_id']!=d['case_id'] or p['plan_hash']!=d['plan_hash']: bad.append({'run_id':d['run_id'],'reason':'plan_binding_mismatch'})
            except KeyError: bad.append({'run_id':d['run_id'],'reason':'orphaned_plan'})
        for r in self.db.all('SELECT * FROM autonomous_wave_step_414'):
            d=dict(r)
            if self._record_hash(d)!=d['record_hash']: bad.append({'step_id':d['step_id'],'reason':'step_hash_mismatch'})
        return {'build':BUILD,'valid':not bad,'violations':bad}
    def status(self):
        return {'build':BUILD,'policy':POLICY_ID,'bounded_autonomous_research_waves':True,'explicit_human_authorization_required':True,'immutable_plan_envelope':True,'case_scoped':True,'budget_bounded':True,'integrity_valid':self.verify_integrity()['valid'],'direct_network_authority':False,'automatic_go_issuance':False,'automatic_evidence_promotion':False,'autonomous_scope_expansion':False,'truth_determined':False}
