from __future__ import annotations
from datetime import datetime, timezone
import hashlib,json,secrets
from typing import Any,Mapping
BUILD='415.0'; POLICY_ID='phase18.human-governed-multi-agent-investigation.v415'
def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()
class MultiAgentInvestigation415:
    '''Case-scoped analyst coordination. Agents produce reviewable proposals only; they cannot execute network actions, issue GO, promote evidence, expand scope, or determine truth.'''
    AGENTS={
      'lead':('Lead Investigator','coordinates questions and synthesis'),
      'source':('Source Analyst','maps provenance and source coverage'),
      'temporal':('Temporal Analyst','examines chronology and temporal gaps'),
      'relationship':('Relationship Analyst','examines explicit structured relationships'),
      'challenge':('Red-Team Analyst','challenges assumptions and identifies counterevidence needs'),
    }
    def __init__(self,db,audit,*,planner413,waves414,quality409,temporal411,relationship412,governance,actor='local-analyst'):
      self.db=db; self.audit=audit; self.planner413=planner413; self.waves414=waves414; self.quality409=quality409; self.temporal411=temporal411; self.relationship412=relationship412; self.governance=governance; self.actor=actor; self._init_schema()
    def _init_schema(self):
      self.db.conn.executescript('''CREATE TABLE IF NOT EXISTS multi_agent_session_415(session_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,plan_id TEXT NOT NULL,plan_hash TEXT NOT NULL,wave_run_id TEXT,state TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL); CREATE TABLE IF NOT EXISTS multi_agent_contribution_415(contribution_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,agent_id TEXT NOT NULL,kind TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL); CREATE INDEX IF NOT EXISTS idx_ma415_case ON multi_agent_session_415(case_id,created_at);'''); self.db.conn.commit()
    def _auth(self,identity,case_id,obj=''):
      if not identity: raise PermissionError('active case identity required')
      self.governance.authorize(dict(identity),case_id=case_id,capability='research.run',object_type='multi_agent_investigation_415',object_id=obj or case_id)
    def _rh(self,r): return _sha({k:r[k] for k in r if k!='record_hash'})
    def create_session(self,*,plan_id,wave_run_id='',identity:Mapping[str,Any]|None=None):
      p=self.planner413.get_plan(plan_id); cid=p['case_id']; self._auth(identity,cid,plan_id)
      if wave_run_id:
        w=self.waves414.run(wave_run_id)
        if w['case_id']!=cid or w['plan_id']!=plan_id or w['plan_hash']!=p['plan_hash']: raise PermissionError('research-wave binding mismatch')
      sid='mai415_'+secrets.token_hex(10); r={'session_id':sid,'case_id':cid,'plan_id':plan_id,'plan_hash':p['plan_hash'],'wave_run_id':wave_run_id,'state':'analysis_only','created_by':str((identity or {}).get('user_id') or (identity or {}).get('username') or self.actor),'created_at':_now()}; r['record_hash']=self._rh(r)
      self.db.execute('INSERT INTO multi_agent_session_415 VALUES(?,?,?,?,?,?,?,?,?)',tuple(r.values())); self.audit.log('multi_agent_session_created_415','multi_agent_session_415',sid,cid,{'plan_id':plan_id,'network_execution':False,'automatic_go':False}); return self.session(sid)
    def _context(self,p):
      xs=p['plan'].get('existing_search_context',[])
      return {'objective':p['plan'].get('objective',''),'subquestions':p['plan'].get('subquestions',[]),'search_context_count':len(xs),'retrieval_gaps':sum(len(x.get('retrieval_gaps') or []) for x in xs),'temporal_gaps':sum(len(x.get('temporal_gaps') or []) for x in xs),'unresolved_relationship_items':sum(int(x.get('unresolved_relationship_items') or 0) for x in xs)}
    def run_round(self,*,session_id,identity:Mapping[str,Any]|None=None):
      s=self.session(session_id); self._auth(identity,s['case_id'],session_id); p=self.planner413.get_plan(s['plan_id'])
      if p['plan_hash']!=s['plan_hash']: raise PermissionError('bound investigation plan changed')
      c=self._context(p); outputs={
       'lead':{'focus':'coordinate','questions':c['subquestions'],'recommendation':'route unresolved questions to specialist review'},
       'source':{'focus':'provenance','retrieval_gap_count':c['retrieval_gaps'],'recommendation':'review source coverage and provenance before collection'},
       'temporal':{'focus':'chronology','temporal_gap_count':c['temporal_gaps'],'recommendation':'review dated records and explicit chronology gaps'},
       'relationship':{'focus':'explicit_relationships','unresolved_item_count':c['unresolved_relationship_items'],'recommendation':'review unresolved endpoints without inferring hidden relationships'},
       'challenge':{'focus':'counteranalysis','recommendation':'seek disconfirming evidence and document alternative explanations','truth_determined':False},
      }
      ids=[]
      for aid,payload in outputs.items(): ids.append(self._add(session_id,aid,'analysis_proposal',payload))
      synthesis={'objective':c['objective'],'specialist_contributions':ids,'state':'human_review_required','network_execution':False,'remote_collection_authorized':False,'automatic_go':False,'automatic_evidence_promotion':False,'autonomous_scope_expansion':False,'truth_determined':False}
      synth=self._add(session_id,'lead','synthesis',synthesis); return {'session_id':session_id,'contributions':[self.contribution(x) for x in ids],'synthesis':self.contribution(synth)}
    def _add(self,sid,aid,kind,payload):
      cid='mac415_'+secrets.token_hex(10); r={'contribution_id':cid,'session_id':sid,'agent_id':aid,'kind':kind,'payload_json':_canon(payload),'created_at':_now()}; r['record_hash']=self._rh(r); self.db.execute('INSERT INTO multi_agent_contribution_415 VALUES(?,?,?,?,?,?,?)',tuple(r.values())); return cid
    def session(self,sid):
      r=self.db.one('SELECT * FROM multi_agent_session_415 WHERE session_id=?',(sid,));
      if not r: raise KeyError('multi-agent session not found')
      return dict(r)
    def contribution(self,cid):
      r=self.db.one('SELECT * FROM multi_agent_contribution_415 WHERE contribution_id=?',(cid,));
      if not r: raise KeyError(cid)
      d=dict(r); d['payload']=json.loads(d.pop('payload_json')); return d
    def verify_integrity(self):
      bad=[]; sessions={}
      for r in self.db.all('SELECT * FROM multi_agent_session_415'):
       d=dict(r); sessions[d['session_id']]=d
       if self._rh(d)!=d['record_hash']: bad.append({'session_id':d['session_id'],'reason':'session_hash_mismatch'})
       try:
        p=self.planner413.get_plan(d['plan_id'])
        if p['case_id']!=d['case_id'] or p['plan_hash']!=d['plan_hash']: bad.append({'session_id':d['session_id'],'reason':'plan_binding_mismatch'})
       except KeyError: bad.append({'session_id':d['session_id'],'reason':'orphaned_plan'})
      for r in self.db.all('SELECT * FROM multi_agent_contribution_415'):
       d=dict(r)
       if self._rh(d)!=d['record_hash']: bad.append({'contribution_id':d['contribution_id'],'reason':'contribution_hash_mismatch'})
       if d['session_id'] not in sessions: bad.append({'contribution_id':d['contribution_id'],'reason':'orphaned_session'})
      return {'build':BUILD,'valid':not bad,'violations':bad}
    def status(self): return {'build':BUILD,'policy':POLICY_ID,'agents':{k:v[0] for k,v in self.AGENTS.items()},'case_scoped':True,'plan_bound':True,'human_review_required':True,'integrity_valid':self.verify_integrity()['valid'],'direct_network_authority':False,'automatic_go_issuance':False,'automatic_evidence_promotion':False,'autonomous_scope_expansion':False,'truth_determined':False}
