from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json
from typing import Any, Mapping

BUILD='395.0'
POLICY_ID='phase17.case-state-version-graph-controlled-adoption.v395'
CONFIRM_REVIEW='REVIEW CASE STATE ADOPTION'
CONFIRM_ADOPT='ADOPT CASE STATE'
CONFIRM_ROLLBACK='ROLLBACK CASE STATE'
CONFIRM_BRANCH='CREATE CASE STATE BRANCH'
CONFIRM_STAGE='STAGE CASE STATE BRANCH'
_ALLOWED={'claim','hypothesis','reasoning_plan'}

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(v if isinstance(v,(bytes,bytearray)) else _canon(v).encode()).hexdigest()
def _sid(prefix,v,n=24): return f'{prefix}_{_sha(v)[:n]}'
def _j(v,d):
    if isinstance(v,(dict,list)): return v
    try: return json.loads(str(v or ''))
    except Exception: return d

class CaseStateVersionGraph395:
    def __init__(self,db:Any,audit:Any,*,discussion394:Any,synthesis391:Any,reasoning392:Any,governance:Any,actor='local-analyst'):
        self.db=db; self.audit=audit; self.discussion394=discussion394; self.synthesis391=synthesis391; self.reasoning392=reasoning392; self.governance=governance; self.actor=actor; self._init_schema()
    def _init_schema(self):
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS case_state_active_395(
          state_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,target_type TEXT NOT NULL,target_id TEXT NOT NULL,
          active_node_id TEXT NOT NULL,active_version_id TEXT NOT NULL DEFAULT '',active_payload_hash TEXT NOT NULL,
          generation INTEGER NOT NULL,previous_node_id TEXT NOT NULL DEFAULT '',adopted_by TEXT NOT NULL,adopted_at TEXT NOT NULL,record_hash TEXT NOT NULL,
          UNIQUE(case_id,target_type,target_id));
        CREATE INDEX IF NOT EXISTS idx_case_state_active_395_case ON case_state_active_395(case_id,target_type,target_id);
        CREATE TABLE IF NOT EXISTS case_state_branch_395(
          branch_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,target_type TEXT NOT NULL,target_id TEXT NOT NULL,branch_name TEXT NOT NULL,
          base_node_id TEXT NOT NULL,head_node_id TEXT NOT NULL,head_version_id TEXT NOT NULL DEFAULT '',generation INTEGER NOT NULL,state TEXT NOT NULL,
          created_by TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,record_hash TEXT NOT NULL,
          UNIQUE(case_id,target_type,target_id,branch_name));
        CREATE INDEX IF NOT EXISTS idx_case_state_branch_395_target ON case_state_branch_395(case_id,target_type,target_id,state);
        CREATE TABLE IF NOT EXISTS case_state_branch_transition_395(
          transition_id TEXT PRIMARY KEY,branch_id TEXT NOT NULL,case_id TEXT NOT NULL,from_node_id TEXT NOT NULL,to_node_id TEXT NOT NULL,
          from_generation INTEGER NOT NULL,to_generation INTEGER NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS case_state_adoption_proposal_395(
          proposal_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,target_type TEXT NOT NULL,target_id TEXT NOT NULL,candidate_node_id TEXT NOT NULL,
          candidate_version_id TEXT NOT NULL DEFAULT '',source_branch_id TEXT NOT NULL DEFAULT '',expected_active_node_id TEXT NOT NULL,
          expected_generation INTEGER NOT NULL,proposal_kind TEXT NOT NULL,rationale TEXT NOT NULL,status TEXT NOT NULL,execution_authority INTEGER NOT NULL,
          created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_case_state_adoption_proposal_395_case ON case_state_adoption_proposal_395(case_id,target_type,target_id,status);
        CREATE TABLE IF NOT EXISTS case_state_adoption_review_395(
          review_id TEXT PRIMARY KEY,proposal_id TEXT NOT NULL UNIQUE,case_id TEXT NOT NULL,disposition TEXT NOT NULL,rationale TEXT NOT NULL,
          reviewed_by TEXT NOT NULL,reviewed_at TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS case_state_transition_395(
          transition_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,target_type TEXT NOT NULL,target_id TEXT NOT NULL,proposal_id TEXT NOT NULL,
          action TEXT NOT NULL,from_node_id TEXT NOT NULL,to_node_id TEXT NOT NULL,from_generation INTEGER NOT NULL,to_generation INTEGER NOT NULL,
          from_payload_hash TEXT NOT NULL,to_payload_hash TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_case_state_transition_395_target ON case_state_transition_395(case_id,target_type,target_id,to_generation);
        CREATE TABLE IF NOT EXISTS case_state_kernel_bridge_395(
          bridge_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,transition_id TEXT NOT NULL UNIQUE,kernel_entry_id TEXT NOT NULL DEFAULT '',
          bridge_state TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);
        '''); self.db.conn.commit()
    def _auth(self,identity,case_id,cap,obj): self.governance.authorize(dict(identity),case_id=case_id,capability=cap,object_type='phase17_case_state_v395',object_id=obj)
    def _rehash(self,table,pkcol,pkval):
        row=self.db.one(f'SELECT * FROM {table} WHERE {pkcol}=?',(pkval,))
        if row:
            d=dict(row); body={k:d[k] for k in d if k!='record_hash'}; self.db.execute(f'UPDATE {table} SET record_hash=? WHERE {pkcol}=?',(_sha(body),pkval))
    def _origin_payload(self,case_id,t,id):
        if t=='claim': o=self.synthesis391.claim(case_id=case_id,claim_id=id); p={'proposition':o['proposition'],'epistemic_status':o.get('epistemic_status','candidate_claim_not_fact'),'corroboration_review_id':o.get('corroboration_review_id','')}; h=str(o.get('record_hash') or '')
        elif t=='hypothesis': o=self.synthesis391.hypothesis(case_id=case_id,hypothesis_id=id); p={'title':o['title'],'statement':o['statement'],'test_plan':o['test_plan'],'epistemic_status':o.get('epistemic_status','hypothesis_not_fact')}; h=str(o.get('record_hash') or '')
        elif t=='reasoning_plan': o=self.reasoning392.plan(case_id=case_id,plan_id=id); p={'workspace_id':o.get('workspace_id',''),'actions':o.get('actions',[]),'epistemic_status':'investigation_plan_not_authority'}; h=str(o.get('record_hash') or '')
        else: raise ValueError('unsupported target type')
        if not h: raise ValueError('origin object lacks integrity hash')
        return p,h
    def _node(self,case_id,t,id,node_id):
        origin=f'origin:{t}:{id}'
        if node_id==origin:
            p,h=self._origin_payload(case_id,t,id); return {'node_id':origin,'version_id':'','payload':p,'payload_hash':_sha(p),'source_hash':h,'node_kind':'origin'}
        v=self.discussion394.version(case_id=case_id,version_id=node_id)
        if v['target_type']!=t or v['target_id']!=id: raise ValueError('version target mismatch')
        if not self.discussion394.verify_version(case_id=case_id,version_id=node_id).get('valid'): raise ValueError('version integrity failed')
        return {'node_id':node_id,'version_id':node_id,'payload':v['payload'],'payload_hash':v['payload_hash'],'source_hash':v['record_hash'],'node_kind':'version'}
    def ensure_state(self,*,case_id,target_type,target_id,identity=None):
        t=str(target_type).casefold();
        if t not in _ALLOWED: raise ValueError('unsupported target type')
        if identity is not None: self._auth(identity,case_id,'case.read',target_id)
        r=self.db.one('SELECT * FROM case_state_active_395 WHERE case_id=? AND target_type=? AND target_id=?',(case_id,t,target_id))
        if not r:
            n=self._node(case_id,t,target_id,f'origin:{t}:{target_id}'); now=_now(); actor=str((identity or {}).get('username') or self.actor)[:120]
            b={'state_id':_sid('state395',{'case':case_id,'t':t,'id':target_id}),'case_id':case_id,'target_type':t,'target_id':target_id,'active_node_id':n['node_id'],'active_version_id':'','active_payload_hash':n['payload_hash'],'generation':0,'previous_node_id':'','adopted_by':actor,'adopted_at':now}
            self.db.execute('INSERT INTO case_state_active_395(state_id,case_id,target_type,target_id,active_node_id,active_version_id,active_payload_hash,generation,previous_node_id,adopted_by,adopted_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(*b.values(),_sha(b)))
            r=self.db.one('SELECT * FROM case_state_active_395 WHERE state_id=?',(b['state_id'],))
        return dict(r)
    def active_state(self,*,case_id,target_type,target_id,identity=None):
        r=self.ensure_state(case_id=case_id,target_type=target_type,target_id=target_id,identity=identity); n=self._node(case_id,r['target_type'],target_id,r['active_node_id'])
        if str(r.get('active_payload_hash') or '')!=str(n['payload_hash']): raise ValueError('active case-state payload binding is stale or tampered')
        return {**r,'payload':n['payload'],'execution_authority':False,'truth_determined':False}
    def create_branch(self,*,case_id,target_type,target_id,branch_name,identity,confirmation):
        if str(confirmation).strip().upper()!=CONFIRM_BRANCH: raise PermissionError(f'explicit confirmation {CONFIRM_BRANCH} required')
        self._auth(identity,case_id,'dossier.write',target_id); s=self.ensure_state(case_id=case_id,target_type=target_type,target_id=target_id); name=' '.join(str(branch_name).split())[:120]
        if len(name)<2: raise ValueError('branch name required')
        now=_now(); actor=str(identity.get('username') or self.actor)[:120]; b={'branch_id':_sid('branch395',{'case':case_id,'t':s['target_type'],'id':target_id,'name':name}),'case_id':case_id,'target_type':s['target_type'],'target_id':target_id,'branch_name':name,'base_node_id':s['active_node_id'],'head_node_id':s['active_node_id'],'head_version_id':s['active_version_id'],'generation':0,'state':'active','created_by':actor,'created_at':now,'updated_at':now}
        ex=self.db.one('SELECT * FROM case_state_branch_395 WHERE branch_id=?',(b['branch_id'],))
        if not ex: self.db.execute('INSERT INTO case_state_branch_395(branch_id,case_id,target_type,target_id,branch_name,base_node_id,head_node_id,head_version_id,generation,state,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(*b.values(),_sha(b))); ex=self.db.one('SELECT * FROM case_state_branch_395 WHERE branch_id=?',(b['branch_id'],))
        return dict(ex)|{'execution_authority':False}
    def stage_branch(self,*,case_id,branch_id,version_id,identity,confirmation):
        if str(confirmation).strip().upper()!=CONFIRM_STAGE: raise PermissionError(f'explicit confirmation {CONFIRM_STAGE} required')
        br=self.db.one('SELECT * FROM case_state_branch_395 WHERE case_id=? AND branch_id=?',(case_id,branch_id));
        if not br: raise KeyError(branch_id)
        br=dict(br); self._auth(identity,case_id,'dossier.write',br['target_id']); n=self._node(case_id,br['target_type'],br['target_id'],version_id); oldgen=int(br['generation']); newgen=oldgen+1; now=_now(); actor=str(identity.get('username') or self.actor)[:120]
        tr={'transition_id':_sid('btrans395',{'branch':branch_id,'from':br['head_node_id'],'to':version_id,'g':newgen}),'branch_id':branch_id,'case_id':case_id,'from_node_id':br['head_node_id'],'to_node_id':version_id,'from_generation':oldgen,'to_generation':newgen,'created_by':actor,'created_at':now}
        self.db.execute('INSERT INTO case_state_branch_transition_395(transition_id,branch_id,case_id,from_node_id,to_node_id,from_generation,to_generation,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?)',(*tr.values(),_sha(tr)))
        self.db.execute('UPDATE case_state_branch_395 SET head_node_id=?,head_version_id=?,generation=?,updated_at=?,record_hash=? WHERE branch_id=?',(version_id,version_id,newgen,now,_sha({**{k:br[k] for k in br if k!='record_hash'},'head_node_id':version_id,'head_version_id':version_id,'generation':newgen,'updated_at':now}),branch_id))
        return self.branch(case_id=case_id,branch_id=branch_id,identity=identity)
    def branch(self,*,case_id,branch_id,identity=None):
        r=self.db.one('SELECT * FROM case_state_branch_395 WHERE case_id=? AND branch_id=?',(case_id,branch_id));
        if not r: raise KeyError(branch_id)
        r=dict(r)
        if identity is not None:self._auth(identity,case_id,'case.read',r['target_id'])
        return r|{'execution_authority':False}
    def compare_nodes(self,*,case_id,target_type,target_id,left_node_id,right_node_id,identity=None):
        if identity is not None:self._auth(identity,case_id,'case.read',target_id)
        l=self._node(case_id,target_type,target_id,left_node_id); r=self._node(case_id,target_type,target_id,right_node_id); keys=sorted(set(l['payload'])|set(r['payload'])); changes=[{'field':k,'left':l['payload'].get(k),'right':r['payload'].get(k)} for k in keys if l['payload'].get(k)!=r['payload'].get(k)]
        return {'case_id':case_id,'target_type':target_type,'target_id':target_id,'left':l,'right':r,'changes':changes,'truth_determined':False,'execution_authority':False}
    def propose_adoption(self,*,case_id,target_type,target_id,candidate_version_id,identity,rationale,source_branch_id='',proposal_kind='adopt'):
        self._auth(identity,case_id,'dossier.write',target_id); s=self.ensure_state(case_id=case_id,target_type=target_type,target_id=target_id); kind=str(proposal_kind).casefold()
        if kind not in {'adopt','rollback'}: raise ValueError('proposal_kind must be adopt or rollback')
        candidate=f'origin:{s["target_type"]}:{target_id}' if not candidate_version_id else candidate_version_id
        if source_branch_id:
            br=self.branch(case_id=case_id,branch_id=source_branch_id); 
            if br['target_type']!=s['target_type'] or br['target_id']!=target_id: raise ValueError('branch target mismatch')
            if candidate_version_id and br['head_node_id']!=candidate_version_id: raise ValueError('candidate does not match branch head')
            candidate=br['head_node_id']
        n=self._node(case_id,s['target_type'],target_id,candidate); reason=' '.join(str(rationale).split())[:4000]
        if len(reason)<12: raise ValueError('substantive rationale required')
        now=_now(); actor=str(identity.get('username') or self.actor)[:120]; body={'proposal_id':_sid('adopt395',{'case':case_id,'t':s['target_type'],'id':target_id,'candidate':candidate,'gen':s['generation'],'kind':kind,'reason':reason}),'case_id':case_id,'target_type':s['target_type'],'target_id':target_id,'candidate_node_id':candidate,'candidate_version_id':n['version_id'],'source_branch_id':source_branch_id,'expected_active_node_id':s['active_node_id'],'expected_generation':int(s['generation']),'proposal_kind':kind,'rationale':reason,'status':'proposal_needs_review','execution_authority':0,'created_by':actor,'created_at':now}
        ex=self.db.one('SELECT proposal_id FROM case_state_adoption_proposal_395 WHERE proposal_id=?',(body['proposal_id'],))
        if not ex:self.db.execute('INSERT INTO case_state_adoption_proposal_395(proposal_id,case_id,target_type,target_id,candidate_node_id,candidate_version_id,source_branch_id,expected_active_node_id,expected_generation,proposal_kind,rationale,status,execution_authority,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(*body.values(),_sha(body)))
        return self.proposal(case_id=case_id,proposal_id=body['proposal_id'],identity=identity)
    def proposal(self,*,case_id,proposal_id,identity=None):
        r=self.db.one('SELECT * FROM case_state_adoption_proposal_395 WHERE case_id=? AND proposal_id=?',(case_id,proposal_id));
        if not r: raise KeyError(proposal_id)
        r=dict(r)
        if identity is not None:self._auth(identity,case_id,'case.read',r['target_id'])
        rv=self.db.one('SELECT * FROM case_state_adoption_review_395 WHERE proposal_id=?',(proposal_id,)); return r|{'review':dict(rv) if rv else None,'execution_authority':False}
    def review_adoption(self,*,case_id,proposal_id,identity,disposition,rationale,confirmation):
        if str(confirmation).strip().upper()!=CONFIRM_REVIEW: raise PermissionError(f'explicit confirmation {CONFIRM_REVIEW} required')
        p=self.proposal(case_id=case_id,proposal_id=proposal_id); self._auth(identity,case_id,'dossier.write',p['target_id']); disp=str(disposition).casefold()
        if disp not in {'approve','reject','defer'}: raise ValueError('unsupported disposition')
        reason=' '.join(str(rationale).split())[:4000]
        if len(reason)<12: raise ValueError('substantive review rationale required')
        if p['status']!='proposal_needs_review': raise PermissionError('proposal already reviewed')
        now=_now(); actor=str(identity.get('username') or self.actor)[:120]; b={'review_id':_sid('adoptreview395',{'p':proposal_id,'d':disp,'a':actor}),'proposal_id':proposal_id,'case_id':case_id,'disposition':disp,'rationale':reason,'reviewed_by':actor,'reviewed_at':now}
        self.db.execute('INSERT INTO case_state_adoption_review_395(review_id,proposal_id,case_id,disposition,rationale,reviewed_by,reviewed_at,record_hash) VALUES(?,?,?,?,?,?,?,?)',(*b.values(),_sha(b))); self.db.execute('UPDATE case_state_adoption_proposal_395 SET status=? WHERE proposal_id=?',('reviewed_for_adoption' if disp=='approve' else ('rejected' if disp=='reject' else 'deferred'),proposal_id)); self._rehash('case_state_adoption_proposal_395','proposal_id',proposal_id); return self.proposal(case_id=case_id,proposal_id=proposal_id,identity=identity)
    def apply_adoption(self,*,case_id,proposal_id,identity,confirmation):
        p=self.proposal(case_id=case_id,proposal_id=proposal_id); required=CONFIRM_ROLLBACK if p['proposal_kind']=='rollback' else CONFIRM_ADOPT
        if str(confirmation).strip().upper()!=required: raise PermissionError(f'explicit confirmation {required} required')
        self._auth(identity,case_id,'dossier.write',p['target_id']); rv=p.get('review') or {}
        if p['status']!='reviewed_for_adoption' or rv.get('disposition')!='approve': raise PermissionError('reviewed approval required')
        s=self.ensure_state(case_id=case_id,target_type=p['target_type'],target_id=p['target_id'])
        if int(s['generation'])!=int(p['expected_generation']) or s['active_node_id']!=p['expected_active_node_id']: raise PermissionError('case state changed since proposal; adoption is stale')
        n=self._node(case_id,p['target_type'],p['target_id'],p['candidate_node_id']); old=self._node(case_id,p['target_type'],p['target_id'],s['active_node_id']); newg=int(s['generation'])+1; now=_now(); actor=str(identity.get('username') or self.actor)[:120]
        tr={'transition_id':_sid('statex395',{'p':proposal_id,'from':s['active_node_id'],'to':n['node_id'],'g':newg}),'case_id':case_id,'target_type':p['target_type'],'target_id':p['target_id'],'proposal_id':proposal_id,'action':p['proposal_kind'],'from_node_id':s['active_node_id'],'to_node_id':n['node_id'],'from_generation':int(s['generation']),'to_generation':newg,'from_payload_hash':old['payload_hash'],'to_payload_hash':n['payload_hash'],'created_by':actor,'created_at':now}
        self.db.execute('INSERT INTO case_state_transition_395(transition_id,case_id,target_type,target_id,proposal_id,action,from_node_id,to_node_id,from_generation,to_generation,from_payload_hash,to_payload_hash,created_by,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(*tr.values(),_sha(tr)))
        body={'state_id':s['state_id'],'case_id':case_id,'target_type':p['target_type'],'target_id':p['target_id'],'active_node_id':n['node_id'],'active_version_id':n['version_id'],'active_payload_hash':n['payload_hash'],'generation':newg,'previous_node_id':s['active_node_id'],'adopted_by':actor,'adopted_at':now}
        self.db.execute('UPDATE case_state_active_395 SET active_node_id=?,active_version_id=?,active_payload_hash=?,generation=?,previous_node_id=?,adopted_by=?,adopted_at=?,record_hash=? WHERE state_id=?',(n['node_id'],n['version_id'],n['payload_hash'],newg,s['active_node_id'],actor,now,_sha(body),s['state_id']))
        self.db.execute('UPDATE case_state_adoption_proposal_395 SET status=? WHERE proposal_id=?',('applied',proposal_id)); self._rehash('case_state_adoption_proposal_395','proposal_id',proposal_id); self.audit.log('case_state_transition','case_state_transition_395',tr['transition_id'],case_id,{'action':p['proposal_kind'],'target_type':p['target_type'],'target_id':p['target_id'],'execution_authority':False})
        return self.active_state(case_id=case_id,target_type=p['target_type'],target_id=p['target_id'],identity=identity)|{'transition_id':tr['transition_id']}
    def history(self,*,case_id,target_type,target_id,identity=None):
        if identity is not None:self._auth(identity,case_id,'case.read',target_id)
        active=self.active_state(case_id=case_id,target_type=target_type,target_id=target_id); transitions=[dict(r) for r in self.db.all('SELECT * FROM case_state_transition_395 WHERE case_id=? AND target_type=? AND target_id=? ORDER BY to_generation',(case_id,target_type,target_id))]; branches=[dict(r) for r in self.db.all('SELECT * FROM case_state_branch_395 WHERE case_id=? AND target_type=? AND target_id=? ORDER BY created_at',(case_id,target_type,target_id))]
        seen={f'origin:{target_type}:{target_id}'}|{str(x['from_node_id']) for x in transitions}|{str(x['to_node_id']) for x in transitions}|{str(b['head_node_id']) for b in branches}; branch_heads={str(b['head_node_id']) for b in branches if b.get('state')=='active'}; statuses=[]
        for node in sorted(seen): statuses.append({'node_id':node,'status':'active' if node==active['active_node_id'] else ('branch_head' if node in branch_heads else 'superseded'),'is_active':node==active['active_node_id']})
        return {'active':active,'transitions':transitions,'branches':branches,'node_statuses':statuses,'execution_authority':False}
    def status(self):
        return {'build':BUILD,'policy':POLICY_ID,'case_state_version_graph':True,'controlled_adoption':True,'branch_pointers':True,'rollback_transitions':True,'superseded_state_tracking':True,'append_only_transition_history':True,'immutable_evidence_history':True,'truth_probability':False,'automatic_truth_acceptance':False,'automatic_upstream_mutation':False,'automatic_evidence_promotion':False,'automatic_go_issuance':False,'automatic_live_confirmation':False,'execution_authority':False,'direct_network_fetch':False,'automatic_identity_merge':False}
