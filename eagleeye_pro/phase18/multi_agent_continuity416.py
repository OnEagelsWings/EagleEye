from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json
from typing import Any, Mapping
BUILD='416.0'; POLICY_ID='phase18.multi-agent-integrity-case-continuity.v416'
def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
class MultiAgentContinuity416:
    '''Fail-closed continuity guard for Build-415 multi-agent sessions. Revalidates case identity, immutable plan binding and optional Build-414 wave binding before every round.'''
    def __init__(self,db,audit,*,multi415,planner413,waves414,governance,actor='local-analyst'):
        self.db=db; self.audit=audit; self.multi415=multi415; self.planner413=planner413; self.waves414=waves414; self.governance=governance; self.actor=actor; self._init_schema()
    def _init_schema(self):
        self.db.conn.executescript('''CREATE TABLE IF NOT EXISTS multi_agent_hold_416(session_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,reason TEXT NOT NULL,detail_json TEXT NOT NULL,held_at TEXT NOT NULL,record_hash TEXT NOT NULL); CREATE TABLE IF NOT EXISTS multi_agent_continuity_check_416(check_id INTEGER PRIMARY KEY AUTOINCREMENT,session_id TEXT NOT NULL,case_id TEXT NOT NULL,result TEXT NOT NULL,detail_json TEXT NOT NULL,checked_at TEXT NOT NULL,record_hash TEXT NOT NULL); CREATE INDEX IF NOT EXISTS idx_cont416_session ON multi_agent_continuity_check_416(session_id,checked_at);'''); self.db.conn.commit()
    def _auth(self,identity,case_id,obj=''):
        if not identity: raise PermissionError('active case identity required')
        self.governance.authorize(dict(identity),case_id=case_id,capability='research.run',object_type='multi_agent_continuity_416',object_id=obj or case_id)
    def _hash(self,r): return _sha({k:r[k] for k in r if k not in ('record_hash','check_id')})
    def _hold(self,s,reason,detail):
        now=_now(); r={'session_id':s['session_id'],'case_id':s['case_id'],'reason':reason,'detail_json':_canon(detail),'held_at':now}; r['record_hash']=self._hash(r)
        self.db.execute('INSERT OR REPLACE INTO multi_agent_hold_416 VALUES(?,?,?,?,?,?)',tuple(r.values())); self.audit.log('multi_agent_session_held_416','multi_agent_hold_416',s['session_id'],s['case_id'],{'reason':reason}); return r
    def _check_record(self,s,result,detail):
        r={'session_id':s['session_id'],'case_id':s['case_id'],'result':result,'detail_json':_canon(detail),'checked_at':_now()}; r['record_hash']=self._hash(r)
        self.db.execute('INSERT INTO multi_agent_continuity_check_416(session_id,case_id,result,detail_json,checked_at,record_hash) VALUES(?,?,?,?,?,?)',tuple(r.values())); return r
    def validate(self,*,session_id,identity:Mapping[str,Any]|None=None):
        s=self.multi415.session(session_id); self._auth(identity,s['case_id'],session_id)
        if self.db.one('SELECT 1 FROM multi_agent_hold_416 WHERE session_id=?',(session_id,)): raise PermissionError('session is on integrity hold')
        problems=[]
        try:
            p=self.planner413.get_plan(s['plan_id'])
            if p['case_id']!=s['case_id']: problems.append('plan_case_mismatch')
            if p['plan_hash']!=s['plan_hash']: problems.append('plan_hash_mismatch')
        except KeyError: problems.append('orphaned_plan')
        if s.get('wave_run_id'):
            try:
                w=self.waves414.run(s['wave_run_id'])
                if w['case_id']!=s['case_id']: problems.append('wave_case_mismatch')
                if w['plan_id']!=s['plan_id']: problems.append('wave_plan_mismatch')
                if w['plan_hash']!=s['plan_hash']: problems.append('wave_plan_hash_mismatch')
                wi=self.waves414.verify_integrity()
                if not wi['valid'] and any(v.get('run_id')==s['wave_run_id'] for v in wi['violations']): problems.append('wave_integrity_violation')
            except KeyError: problems.append('orphaned_wave_run')
        mi=self.multi415.verify_integrity()
        if not mi['valid'] and any(v.get('session_id')==session_id or self._contribution_belongs(v.get('contribution_id'),session_id) for v in mi['violations']): problems.append('multi_agent_integrity_violation')
        if problems:
            self._check_record(s,'hold',{'problems':sorted(set(problems))}); self._hold(s,'continuity_validation_failed',{'problems':sorted(set(problems))}); raise PermissionError('multi-agent continuity validation failed: '+','.join(sorted(set(problems))))
        self._check_record(s,'pass',{'plan_bound':True,'wave_bound':bool(s.get('wave_run_id'))}); return {'build':BUILD,'session_id':session_id,'case_id':s['case_id'],'valid':True,'wave_bound':bool(s.get('wave_run_id'))}
    def _contribution_belongs(self,cid,sid):
        if not cid:return False
        r=self.db.one('SELECT session_id FROM multi_agent_contribution_415 WHERE contribution_id=?',(cid,)); return bool(r and r['session_id']==sid)
    def run_round(self,*,session_id,identity:Mapping[str,Any]|None=None):
        continuity=self.validate(session_id=session_id,identity=identity); out=self.multi415.run_round(session_id=session_id,identity=identity); out['continuity416']=continuity; return out
    def verify_integrity(self):
        bad=[]
        for r in self.db.all('SELECT * FROM multi_agent_hold_416'):
            d=dict(r)
            if self._hash(d)!=d['record_hash']: bad.append({'session_id':d['session_id'],'reason':'hold_hash_mismatch'})
        for r in self.db.all('SELECT * FROM multi_agent_continuity_check_416'):
            d=dict(r)
            if self._hash(d)!=d['record_hash']: bad.append({'check_id':d['check_id'],'reason':'continuity_check_hash_mismatch'})
        return {'build':BUILD,'valid':not bad,'violations':bad}
    def status(self):
        return {'build':BUILD,'policy':POLICY_ID,'revalidate_every_round':True,'case_identity_required':True,'immutable_plan_binding':True,'wave_binding_revalidated':True,'orphan_detection':True,'fail_closed_hold':True,'integrity_valid':self.verify_integrity()['valid'],'direct_network_authority':False,'automatic_go_issuance':False,'automatic_evidence_promotion':False,'autonomous_scope_expansion':False,'truth_determined':False}
