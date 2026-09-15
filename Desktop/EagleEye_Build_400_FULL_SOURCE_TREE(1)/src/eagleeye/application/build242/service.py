from __future__ import annotations
import hashlib, html, json
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256(v if isinstance(v,bytes) else _canon(v).encode()).hexdigest()
def _loads(v,default):
    try: return json.loads(v) if v else default
    except Exception: return default
def _text(v,n=8000): return str(v or '').replace('\x00','').strip()[:n]
def _clamp(v):
    try:return max(0.0,min(1.0,float(v)))
    except Exception:return 0.0

class Build242AgentOrchestrationOpsecSentinelService:
    BUILD='242.0'
    ROLES=('opsec_sentinel','planner','retriever','source_analyst','identity_analyst','verifier','critic','reporter')
    SEVERITY={'info':.10,'low':.25,'medium':.50,'high':.78,'critical':1.0}
    DEFAULT_WEIGHTS={'tracking_indicator':1.0,'unexpected_egress':.95,'credential_exposure':1.0,'personal_profile_reuse':.82,'telemetry_exposure':.68,'high_risk_source':.72,'source_opsec_incident':.84,'external_link_exposure':.38,'high_concurrency':.28,'cloud_policy_mismatch':.78,'other':.50}
    THRESHOLDS={'guarded':.30,'elevated':.50,'high':.70,'critical':.88}
    def __init__(self,db,audit,*,conversation,reasoning,source_fabric,adaptive,training,actor='local-analyst'):
        self.db,self.audit,self.conversation,self.reasoning,self.source_fabric,self.adaptive,self.training,self.actor=db,audit,conversation,reasoning,source_fabric,adaptive,training,actor
        conversation._opsec_sentinel_242=self
    def _case(self,case_id):
        if not self.db.one('SELECT case_id FROM cases WHERE case_id=?',(case_id,)): raise KeyError(case_id)
    def _event(self,case_id,event_type,object_type,object_id,payload,actor):
        prev=self.db.one('SELECT event_hash FROM build242_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)); ph=(prev or {}).get('event_hash',''); eid,now=new_id('evt242'),now_ts(); eh=_hash({'previous':ph,'event_id':eid,'case_id':case_id,'event_type':event_type,'object_type':object_type,'object_id':object_id,'actor':actor,'payload':dict(payload),'at':now}); self.db.execute('INSERT INTO build242_events VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,case_id,event_type,object_type,object_id,actor,dumps(dict(payload)),ph,eh,now));
        try:self.audit.log('build242_'+event_type,object_type,object_id,case_id,dict(payload))
        except Exception:pass
    # orchestration
    def create_run(self,*,case_id,objective,priority=50,max_tokens=20000,max_cost=0.0,max_seconds=1800,actor,confirmation):
        if confirmation!=f'AGENT RUN 242 {case_id} ANLEGEN': raise PermissionError('explicit approval required')
        self._case(case_id); objective=_text(objective,10000)
        if len(objective)<8: raise ValueError('objective too short')
        rid,now=new_id('agrun242'),now_ts(); vals=(rid,case_id,objective,'ready',max(0,min(100,int(priority))),max(0,int(max_tokens)),max(0.0,float(max_cost)),max(30,int(max_seconds)),0,0.0,0,'{}',actor,now,now,_hash({'run':rid,'objective':objective}))
        self.db.execute('INSERT INTO agent_runs_242 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals)
        dep_roles={'opsec_sentinel':[],'planner':['opsec_sentinel'],'retriever':['planner'],'source_analyst':['retriever'],'identity_analyst':['source_analyst'],'verifier':['source_analyst'],'critic':['identity_analyst','verifier'],'reporter':['critic']}; gates={'retriever':1,'source_analyst':1,'reporter':1}; ids={}
        for i,role in enumerate(self.ROLES,1): ids[role]=new_id('agtask242')
        for i,role in enumerate(self.ROLES,1):
            tid=ids[role]; deps=[ids[x] for x in dep_roles[role]]; status='ready' if not deps else 'planned'; self.db.execute('INSERT INTO agent_tasks_242 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(tid,rid,case_id,role,i,dumps(deps),status,gates.get(role,0),dumps({'objective':objective,'role':role}),'{}','{}',0,2,0,0.0,'','',now,now,_hash({'task':tid,'role':role,'run':rid})))
        ass=self.scan_case(case_id=case_id,run_id=rid,auto_contain=True); self._event(case_id,'agent_run_created','agent_run',rid,{'risk_level':ass['risk_level']},actor); return self.run(rid)
    def _task(self,row):
        d=dict(row); d['dependencies']=_loads(d.pop('dependencies_json',''),[]); d['input']=_loads(d.pop('input_json',''),{}); d['output']=_loads(d.pop('output_json',''),{}); d['checkpoint']=_loads(d.pop('checkpoint_json',''),{}); return d
    def run(self,run_id):
        r=self.db.one('SELECT * FROM agent_runs_242 WHERE run_id=?',(run_id,));
        if not r: raise KeyError(run_id)
        d=dict(r); d['checkpoint']=_loads(d.get('checkpoint_json'),{}); d['tasks']=[self._task(x) for x in self.db.all('SELECT * FROM agent_tasks_242 WHERE run_id=? ORDER BY sequence_no',(run_id,))]; return d
    def approve_task(self,*,task_id,decision,rationale,reviewer,confirmation):
        t=self.db.one('SELECT * FROM agent_tasks_242 WHERE task_id=?',(task_id,));
        if not t: raise KeyError(task_id)
        if confirmation!=f'AGENT TASK 242 {task_id} PRUEFEN': raise PermissionError('explicit approval required')
        if decision not in {'approved','rejected','deferred'}: raise ValueError('invalid decision')
        if len(_text(rationale,5000))<15: raise ValueError('rationale too short')
        aid,now=new_id('agapprove242'),now_ts(); self.db.execute('INSERT INTO agent_task_approvals_242 VALUES(?,?,?,?,?,?,?,?,?)',(aid,task_id,t['run_id'],t['case_id'],decision,_text(rationale,5000),reviewer,now,_hash({'approval':aid,'decision':decision})))
        if decision=='rejected': self.db.execute("UPDATE agent_tasks_242 SET status='cancelled',updated_at=? WHERE task_id=?",(now,task_id))
        return dict(self.db.one('SELECT * FROM agent_task_approvals_242 WHERE approval_id=?',(aid,)))
    def opsec_state(self,case_id):
        r=self.db.one('SELECT * FROM opsec_case_state_242 WHERE case_id=?',(case_id,)); return dict(r) if r else {'case_id':case_id,'mode':'normal','manual_gate_required':0,'last_risk_score':0,'last_risk_level':'low'}
    def ready_tasks(self,*,run_id):
        run=self.run(run_id)
        if run['status'] in {'paused','paused_opsec','cancelled','completed','failed'}: return []
        statuses={t['task_id']:t['status'] for t in run['tasks']}; gate=self.opsec_state(run['case_id'])['manual_gate_required']; out=[]
        for t in run['tasks']:
            if t['status'] not in {'planned','ready'} or any(statuses.get(x)!='completed' for x in t['dependencies']): continue
            need=t['human_gate'] or (gate and t['role']!='opsec_sentinel')
            if need:
                a=self.db.one('SELECT decision FROM agent_task_approvals_242 WHERE task_id=? ORDER BY reviewed_at DESC LIMIT 1',(t['task_id'],))
                if not a or a['decision']!='approved': continue
            out.append(t)
        return out
    def start_task(self,*,task_id,worker_id,actor,confirmation):
        t=self.db.one('SELECT * FROM agent_tasks_242 WHERE task_id=?',(task_id,));
        if not t: raise KeyError(task_id)
        if confirmation!=f'AGENT TASK 242 {task_id} STARTEN': raise PermissionError('explicit approval required')
        self.scan_case(case_id=t['case_id'],run_id=t['run_id'],auto_contain=True)
        if task_id not in {x['task_id'] for x in self.ready_tasks(run_id=t['run_id'])}: raise PermissionError('task not ready or gated')
        now=now_ts(); self.db.execute("UPDATE agent_tasks_242 SET status='running',worker_id=?,updated_at=? WHERE task_id=?",(_text(worker_id,200),now,task_id)); self.db.execute("UPDATE agent_runs_242 SET status='running',updated_at=? WHERE run_id=?",(now,t['run_id'])); return self._task(self.db.one('SELECT * FROM agent_tasks_242 WHERE task_id=?',(task_id,)))
    def checkpoint_task(self,*,task_id,checkpoint,tokens_used=0,cost_used=0.0):
        t=self.db.one('SELECT * FROM agent_tasks_242 WHERE task_id=?',(task_id,)); r=self.db.one('SELECT * FROM agent_runs_242 WHERE run_id=?',(t['run_id'],)) if t else None
        if not t or not r: raise KeyError(task_id)
        tt=max(0,int(tokens_used)); cc=max(0.0,float(cost_used)); now=now_ts(); self.db.execute('UPDATE agent_tasks_242 SET checkpoint_json=?,tokens_used=?,cost_used=?,updated_at=? WHERE task_id=?',(dumps(dict(checkpoint)),tt,cc,now,task_id)); total=int(r['tokens_used'])+tt; totalc=float(r['cost_used'])+cc; self.db.execute('UPDATE agent_runs_242 SET tokens_used=?,cost_used=?,checkpoint_json=?,updated_at=? WHERE run_id=?',(total,totalc,dumps({'last_task_id':task_id}),now,t['run_id']))
        if total>int(r['max_tokens']) or (float(r['max_cost'])>0 and totalc>float(r['max_cost'])): self.db.execute("UPDATE agent_runs_242 SET status='paused',updated_at=? WHERE run_id=?",(now,t['run_id']))
        return {'task_id':task_id,'tokens_used':tt,'cost_used':cc,'automatic_external_action':False}
    def complete_task(self,*,task_id,output,actor,confirmation):
        t=self.db.one('SELECT * FROM agent_tasks_242 WHERE task_id=?',(task_id,));
        if not t: raise KeyError(task_id)
        if confirmation!=f'AGENT TASK 242 {task_id} ABSCHLIESSEN': raise PermissionError('explicit approval required')
        if t['status']!='running': raise ValueError('task must be running')
        now=now_ts(); self.db.execute("UPDATE agent_tasks_242 SET status='completed',output_json=?,updated_at=? WHERE task_id=?",(dumps(dict(output)),now,task_id))
        tasks=self.db.all("SELECT task_id,dependencies_json FROM agent_tasks_242 WHERE run_id=? AND status='planned'",(t['run_id'],));
        for q in tasks:
            deps=_loads(q['dependencies_json'],[])
            if deps and all((self.db.one('SELECT status FROM agent_tasks_242 WHERE task_id=?',(d,)) or {}).get('status')=='completed' for d in deps): self.db.execute("UPDATE agent_tasks_242 SET status='ready',updated_at=? WHERE task_id=?",(now,q['task_id']))
        left=self.db.one("SELECT COUNT(*) n FROM agent_tasks_242 WHERE run_id=? AND status NOT IN ('completed','cancelled')",(t['run_id'],))['n']
        if not left:self.db.execute("UPDATE agent_runs_242 SET status='completed',updated_at=? WHERE run_id=?",(now,t['run_id']))
        return self._task(self.db.one('SELECT * FROM agent_tasks_242 WHERE task_id=?',(task_id,)))
    def pause_run(self,*,run_id,reason,actor,confirmation):
        if confirmation!=f'AGENT RUN 242 {run_id} PAUSIEREN': raise PermissionError('explicit approval required')
        r=self.run(run_id); now=now_ts(); self.db.execute("UPDATE agent_runs_242 SET status='paused',checkpoint_json=?,updated_at=? WHERE run_id=?",(dumps({'pause_reason':_text(reason,1000)}),now,run_id)); self.db.execute("UPDATE agent_tasks_242 SET status='paused',updated_at=? WHERE run_id=? AND status='running'",(now,run_id)); return self.run(run_id)
    def resume_run(self,*,run_id,actor,confirmation):
        if confirmation!=f'AGENT RUN 242 {run_id} FORTSETZEN': raise PermissionError('explicit approval required')
        r=self.run(run_id); a=self.scan_case(case_id=r['case_id'],run_id=run_id,auto_contain=True)
        if a['risk_level'] in {'high','critical'}: raise PermissionError('OPSEC risk blocks resume')
        now=now_ts(); self.db.execute("UPDATE agent_runs_242 SET status='ready',updated_at=? WHERE run_id=?",(now,run_id)); self.db.execute("UPDATE agent_tasks_242 SET status='ready',updated_at=? WHERE run_id=? AND status='paused'",(now,run_id)); return self.run(run_id)
    def recover_interrupted(self,*,actor='orchestrator-242'):
        rows=self.db.all("SELECT task_id,run_id FROM agent_tasks_242 WHERE status='running'"); now=now_ts()
        for x in rows:self.db.execute("UPDATE agent_tasks_242 SET status='ready',error_text='recovered_after_restart',updated_at=? WHERE task_id=?",(now,x['task_id'])); self.db.execute("UPDATE agent_runs_242 SET status='ready',updated_at=? WHERE run_id=?",(now,x['run_id']))
        return {'recovered_tasks':len(rows),'resumable':True,'automatic_external_action':False}
    # opsec observations / learning
    def record_observation(self,*,case_id,category,severity,confidence,source_type,details,detector,run_id='',source_ref='',confirmation):
        if confirmation!=f'OPSEC OBSERVATION 242 {case_id} SPEICHERN': raise PermissionError('explicit approval required')
        self._case(case_id); severity=severity if severity in self.SEVERITY else 'medium'; oid,now=new_id('opsecobs242'),now_ts(); data={'id':oid,'category':category,'severity':severity,'confidence':_clamp(confidence),'details':dict(details)}; self.db.execute('INSERT INTO opsec_observations_242 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(oid,case_id,_text(run_id,200),_text(category,120) or 'other',severity,_clamp(confidence),_text(source_type,120),_text(source_ref,500),dumps(dict(details)),detector,now,_hash(data))); return self.observation(oid)
    def observation(self,observation_id):
        r=self.db.one('SELECT * FROM opsec_observations_242 WHERE observation_id=?',(observation_id,));
        if not r: raise KeyError(observation_id)
        d=dict(r); d['details']=_loads(d['details_json'],{}); rv=self.db.one('SELECT * FROM opsec_observation_reviews_242 WHERE observation_id=?',(observation_id,)); d['review']=dict(rv) if rv else None; return d
    def review_observation(self,*,observation_id,decision,reviewed_severity,rationale,reviewer,confirmation):
        o=self.observation(observation_id)
        if confirmation!=f'OPSEC REVIEW 242 {observation_id} SPEICHERN': raise PermissionError('explicit approval required')
        if reviewer==o['detected_by']: raise PermissionError('independent reviewer required')
        if o['review']: raise ValueError('already reviewed')
        if decision not in {'confirmed','false_positive','needs_context'} or reviewed_severity not in self.SEVERITY: raise ValueError('invalid review')
        if len(_text(rationale,5000))<20: raise ValueError('rationale too short')
        rid,now=new_id('opsecrev242'),now_ts(); self.db.execute('INSERT INTO opsec_observation_reviews_242 VALUES(?,?,?,?,?,?,?,?,?)',(rid,observation_id,o['case_id'],decision,reviewed_severity,_text(rationale,5000),reviewer,now,_hash({'review':rid,'decision':decision}))); cand=self._maybe_auto_candidate(o['case_id']) if decision in {'confirmed','false_positive'} else None; d=dict(self.db.one('SELECT * FROM opsec_observation_reviews_242 WHERE review_id=?',(rid,))); d['auto_calibration_candidate_id']=(cand or {}).get('policy_id',''); return d
    def _active_policy(self,case_id):
        r=self.db.one('SELECT p.* FROM opsec_policy_activations_242 a JOIN opsec_policy_snapshots_242 p ON p.policy_id=a.policy_id WHERE a.case_id=? ORDER BY a.activated_at DESC LIMIT 1',(case_id,))
        if not r:return {'policy_id':'builtin-242','weights':dict(self.DEFAULT_WEIGHTS),'thresholds':dict(self.THRESHOLDS),'version':0}
        d=dict(r); d['weights']=_loads(d['weights_json'],self.DEFAULT_WEIGHTS); d['thresholds']=_loads(d['thresholds_json'],self.THRESHOLDS); return d
    def _reviewed_rows(self,case_id): return [dict(x) for x in self.db.all("SELECT o.category,o.confidence,o.detected_by,r.decision,r.reviewed_severity,r.reviewer FROM opsec_observations_242 o JOIN opsec_observation_reviews_242 r ON r.observation_id=o.observation_id WHERE o.case_id=? AND r.decision IN ('confirmed','false_positive') ORDER BY r.reviewed_at",(case_id,))]
    def _create_policy(self,case_id,actor,origin):
        rows=self._reviewed_rows(case_id)
        if len(rows)<3 or len({x['detected_by'] for x in rows})<2: raise ValueError('at least three reviewed observations from two detectors required')
        base=self._active_policy(case_id); w=dict(base['weights']); confirmed=[x for x in rows if x['decision']=='confirmed']; grouped={}
        for x in confirmed:grouped.setdefault(x['category'],[]).append(self.SEVERITY.get(x['reviewed_severity'],.5)*float(x['confidence']))
        for cat,vals in grouped.items():
            old=float(w.get(cat,w['other'])); empirical=sum(vals)/len(vals); w[cat]=round(max(.05,min(1.0,old+max(-.10,min(.10,(empirical-old)*.25)))),4)
        v=int((self.db.one('SELECT COALESCE(MAX(version),0) v FROM opsec_policy_snapshots_242 WHERE case_id=?',(case_id,)) or {'v':0})['v'])+1; pid,now=new_id('opsecpolicy242'),now_ts(); meta={'reviewed_incidents':len(rows),'detector_diversity':len({x['detected_by'] for x in rows}),'bounded_delta':.10,'automatic_activation':False}; self.db.execute('INSERT INTO opsec_policy_snapshots_242 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,v,origin,dumps(w),dumps(self.THRESHOLDS),len(rows),dumps(meta),actor,now,_hash({'policy':pid,'weights':w}))); return {'policy_id':pid,'case_id':case_id,'version':v,'origin':origin,'weights':w,'requires_independent_review':True}
    def calibrate_policy_candidate(self,*,case_id,actor,confirmation):
        if confirmation!=f'OPSEC CALIBRATION 242 {case_id} ERZEUGEN': raise PermissionError('explicit approval required')
        return self._create_policy(case_id,actor,'reviewed_local_calibration_candidate')
    def _maybe_auto_candidate(self,case_id):
        rows=self._reviewed_rows(case_id)
        if len(rows)<5 or len(rows)%5:return None
        last=self.db.one('SELECT evidence_count FROM opsec_policy_snapshots_242 WHERE case_id=? ORDER BY version DESC LIMIT 1',(case_id,))
        if last and int(last['evidence_count'])>=len(rows): return None
        try:return self._create_policy(case_id,'opsec-sentinel-242','automatic_reviewed_calibration_candidate')
        except ValueError:return None
    def review_policy(self,*,policy_id,decision,rationale,reviewer,confirmation):
        p=self.db.one('SELECT * FROM opsec_policy_snapshots_242 WHERE policy_id=?',(policy_id,));
        if not p: raise KeyError(policy_id)
        if confirmation!=f'OPSEC POLICY 242 {policy_id} PRUEFEN': raise PermissionError('explicit approval required')
        if reviewer==p['created_by']: raise PermissionError('independent reviewer required')
        if decision not in {'approved','rejected'}: raise ValueError('invalid decision')
        rid,now=new_id('polrev242'),now_ts(); self.db.execute('INSERT INTO opsec_policy_reviews_242 VALUES(?,?,?,?,?,?,?,?)',(rid,policy_id,p['case_id'],decision,_text(rationale,5000),reviewer,now,_hash({'review':rid,'decision':decision}))); return dict(self.db.one('SELECT * FROM opsec_policy_reviews_242 WHERE policy_review_id=?',(rid,)))
    def activate_policy(self,*,policy_id,actor,confirmation):
        p=self.db.one('SELECT * FROM opsec_policy_snapshots_242 WHERE policy_id=?',(policy_id,)); r=self.db.one('SELECT * FROM opsec_policy_reviews_242 WHERE policy_id=?',(policy_id,))
        if not p: raise KeyError(policy_id)
        if confirmation!=f'OPSEC POLICY 242 {policy_id} AKTIVIEREN': raise PermissionError('explicit approval required')
        if not r or r['decision']!='approved': raise PermissionError('approved review required')
        aid,now=new_id('polact242'),now_ts(); self.db.execute('INSERT INTO opsec_policy_activations_242 VALUES(?,?,?,?,?,?)',(aid,policy_id,p['case_id'],actor,now,_hash({'activation':aid,'policy':policy_id}))); return {'activation_id':aid,'policy_id':policy_id,'automatic_activation':False}
    def _source_factors(self,case_id):
        factors=[]
        try:
            rows=self.db.all("SELECT r.opsec_risk FROM source_fabric_case_bindings_236 b JOIN source_fabric_sources_236 s ON s.fabric_source_id=b.fabric_source_id JOIN source_fabric_revisions_236 r ON r.fabric_source_id=s.fabric_source_id WHERE b.case_id=? AND r.revision_no=(SELECT MAX(r2.revision_no) FROM source_fabric_revisions_236 r2 WHERE r2.fabric_source_id=r.fabric_source_id) AND r.opsec_risk IN ('high','critical')",(case_id,))
            if rows:factors.append({'category':'high_risk_source','score':min(1.0,.35+.12*len(rows)),'count':len(rows)})
        except Exception:pass
        try:
            q=self.db.one("SELECT COUNT(*) n FROM source_outcomes_231 o JOIN source_outcome_reviews_231 r ON r.outcome_id=o.outcome_id WHERE o.case_id=? AND o.opsec_incident=1 AND r.decision='accepted'",(case_id,))
            if q and int(q['n']):factors.append({'category':'source_opsec_incident','score':min(1.0,.45+.08*int(q['n'])),'count':int(q['n'])})
        except Exception:pass
        return factors
    def scan_case(self,*,case_id,run_id='',actor='opsec-sentinel-242',auto_contain=True):
        self._case(case_id); policy=self._active_policy(case_id); factors=[]
        for o in self.db.all('SELECT * FROM opsec_observations_242 WHERE case_id=? ORDER BY detected_at DESC LIMIT 100',(case_id,)):
            r=self.db.one('SELECT * FROM opsec_observation_reviews_242 WHERE observation_id=?',(o['observation_id'],));
            if r and r['decision']=='false_positive':continue
            sev=(r or {}).get('reviewed_severity',o['severity']); conf=float(o['confidence'])*(1.0 if r and r['decision']=='confirmed' else .5); factors.append({'category':o['category'],'score':_clamp(self.SEVERITY.get(sev,.5)*conf*float(policy['weights'].get(o['category'],policy['weights']['other']))),'reviewed':bool(r)})
        factors+=self._source_factors(case_id); active=self.db.one("SELECT COUNT(*) n FROM agent_runs_242 WHERE case_id=? AND status='running'",(case_id,));
        if active and int(active['n'])>3:factors.append({'category':'high_concurrency','score':min(.6,.15+.05*int(active['n'])),'count':int(active['n'])})
        try:
            op3=getattr(self,'_opsec3_243',None)
            if op3 is not None: factors.extend(op3.sentinel_factors(case_id))
        except Exception: pass
        try:
            rt247=getattr(self,'_runtime247',None)
            if rt247 is not None:
                rctx=rt247.context(case_id).get('production_ai_runtime_247',{})
                recent=rctx.get('recent_routes',[])
                external=[x for x in recent if x.get('backend') not in {'ollama_local','llama_cpp_local','sentence_transformers_local','rules_local'}]
                if external: factors.append({'category':'unexpected_egress','score':1.0,'count':len(external),'source':'ai_runtime_247'})
        except Exception: pass
        vals=[_clamp(x.get('score',0)) for x in factors]; score=0.0 if not vals else _clamp(max(vals)*.65+(sum(vals)/len(vals))*.35); th=policy['thresholds']; level='critical' if score>=th['critical'] else 'high' if score>=th['high'] else 'elevated' if score>=th['elevated'] else 'guarded' if score>=th['guarded'] else 'low'; rec=self._recommendations(factors,level); aid,now=new_id('opsecass242'),now_ts(); self.db.execute('INSERT INTO opsec_assessments_242 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,_text(run_id,200),policy['policy_id'],round(score,4),level,dumps(factors),dumps(rec),'[]',actor,now,_hash({'assessment':aid,'score':score,'level':level}))); containment=self._contain(case_id,aid,level,actor) if auto_contain else []; mode='paused_opsec' if level in {'high','critical'} else 'restricted' if level=='elevated' else 'guarded' if level=='guarded' else 'normal'; gate=1 if level in {'elevated','high','critical'} else 0; self.db.execute("INSERT INTO opsec_case_state_242 VALUES(?,?,?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET mode=excluded.mode,manual_gate_required=excluded.manual_gate_required,last_assessment_id=excluded.last_assessment_id,last_risk_score=excluded.last_risk_score,last_risk_level=excluded.last_risk_level,updated_at=excluded.updated_at",(case_id,mode,gate,aid,round(score,4),level,now)); return {'assessment_id':aid,'case_id':case_id,'risk_score':round(score,4),'risk_level':level,'factors':factors,'recommendations':rec,'containment':containment,'automatic_system_or_network_change':False}
    def _contain(self,case_id,assessment_id,level,actor):
        out=[]; now=now_ts()
        if level in {'elevated','high','critical'}: out.append('manual_gate_required')
        if level in {'high','critical'}:
            rows=self.db.all("SELECT run_id FROM agent_runs_242 WHERE case_id=? AND status IN ('ready','running')",(case_id,));
            for x in rows:
                self.db.execute("UPDATE agent_runs_242 SET status='paused_opsec',updated_at=? WHERE run_id=?",(now,x['run_id'])); self.db.execute("UPDATE agent_tasks_242 SET status='paused',updated_at=? WHERE run_id=? AND status='running'",(now,x['run_id'])); rid=new_id('opsecresp242'); self.db.execute('INSERT INTO opsec_responses_242 VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,case_id,assessment_id,'pause_eagleeye_agent_run',x['run_id'],'High defensive OPSEC risk; app-internal containment only',1,actor,now,_hash({'response':rid,'run':x['run_id']}))); out.append('paused:'+x['run_id'])
        return out
    def _recommendations(self,factors,level):
        cats={x.get('category') for x in factors}; r=[]
        if 'credential_exposure' in cats:r.append('Rotate exposed credentials and inspect secret handling before continuing.')
        if 'personal_profile_reuse' in cats:r.append('Separate personal and investigative browser/profile identities.')
        if 'high_risk_source' in cats or 'source_opsec_incident' in cats:r.append('Review source governance and access method before further use.')
        if level in {'elevated','high','critical'}:r.append('Reduce concurrent agent activity and require analyst approval for external steps.')
        return r or ['Maintain normal defensive monitoring; no external action is authorized by this assessment.']
    def stage_training(self,*,case_id,actor,limit=50,confirmation):
        if confirmation!=f'OPSEC TRAINING 242 {case_id} VORBEREITEN': raise PermissionError('explicit approval required')
        rows=self.db.all("SELECT o.*,r.decision,r.reviewed_severity,r.rationale,r.reviewer FROM opsec_observations_242 o JOIN opsec_observation_reviews_242 r ON r.observation_id=o.observation_id LEFT JOIN opsec_training_links_242 l ON l.observation_id=o.observation_id WHERE o.case_id=? AND r.decision IN ('confirmed','false_positive') AND l.observation_id IS NULL ORDER BY r.reviewed_at LIMIT ?",(case_id,max(1,min(200,int(limit))))); created=[]
        for x in rows:
            context={'category':x['category'],'observed_severity':x['severity'],'reviewed_severity':x['reviewed_severity'],'confidence':x['confidence'],'review_decision':x['decision'],'review_rationale':x['rationale'],'safe_boundary':'defensive_app_internal_only'}; instruction='Bewerte dieses OPSEC-Risikosignal. Trenne Beobachtung von Schlussfolgerung und schlage nur defensive, rechtmäßige, app-interne Maßnahmen oder Human-Gates vor.'; response=f"Review: {x['decision']}; severity: {x['reviewed_severity']}. {x['rationale']}"
            ex=self.training.add_example(case_id=case_id,instruction=instruction,response=response,context=context,source_type='opsec_sentinel_242',source_ref=x['observation_id'],created_by=actor,confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN'); lid,now=new_id('opsectrain242'),now_ts(); self.db.execute('INSERT INTO opsec_training_links_242 VALUES(?,?,?,?,?,?,?)',(lid,case_id,x['observation_id'],ex['example_id'],actor,now,_hash({'link':lid,'example':ex['example_id']}))); created.append(ex['example_id'])
        return {'case_id':case_id,'created':created,'count':len(created),'review_status':'pending','automatic_adapter_activation':False}
    def context(self,case_id):
        s=self.opsec_state(case_id); ass=self.db.one('SELECT * FROM opsec_assessments_242 WHERE case_id=? ORDER BY assessed_at DESC LIMIT 1',(case_id,)); op3=None
        try:
            svc=getattr(self,'_opsec3_243',None); op3=svc.context(case_id) if svc is not None else None
        except Exception: pass
        runtime247=None
        try:
            rt=getattr(self,'_runtime247',None); runtime247=rt.context(case_id).get('production_ai_runtime_247',{}) if rt is not None else None
        except Exception: pass
        production248=None
        try:
            pr=getattr(self,'_production248',None); production248=pr.context(case_id).get('production_hardening_context_248',{}) if pr is not None else None
        except Exception: pass
        return {'state':s,'latest_assessment':dict(ass) if ass else None,'investigative_opsec_243':op3,'production_ai_runtime_247':runtime247,'production_hardening_248':production248,'rules':['Risk indicators are signals, not proof of an attacker.','Use only defensive app-internal containment and human gates.','AI runtime must remain local-only with no silent external-provider fallback.','Production readiness and local Mistral availability are operational states, not evidence.','Do not bypass access controls, alter OS/network settings, perform anti-forensics, or claim untrackability.']}
    def dashboard(self,*,case_id):
        self._case(case_id); return {'build':self.BUILD,'runs':self.db.one('SELECT COUNT(*) n FROM agent_runs_242 WHERE case_id=?',(case_id,))['n'],'active_runs':self.db.one("SELECT COUNT(*) n FROM agent_runs_242 WHERE case_id=? AND status IN ('ready','running')",(case_id,))['n'],'observations':self.db.one('SELECT COUNT(*) n FROM opsec_observations_242 WHERE case_id=?',(case_id,))['n'],'training':self.db.one('SELECT COUNT(*) n FROM opsec_training_links_242 WHERE case_id=?',(case_id,))['n'],'state':self.opsec_state(case_id),'recent_runs':[dict(x) for x in self.db.all('SELECT run_id,status,priority,objective FROM agent_runs_242 WHERE case_id=? ORDER BY updated_at DESC LIMIT 8',(case_id,))]}
    def render_workspace_panel(self,*,case_id,csrf):
        d=self.dashboard(case_id=case_id); e=lambda x:html.escape(str(x or ''),quote=True); rows=''.join(f"<tr><td><code>{e(x['run_id'])}</code></td><td>{e(x['status'])}</td><td>{e(x['objective'][:100])}</td></tr>" for x in d['recent_runs']) or "<tr><td colspan='3'>Noch kein Agentenlauf.</td></tr>"
        return f"""<section class='card' id='build242'><h2>Agent Orchestration 3.0 + OPSEC Sentinel · Build 242</h2><p>Persistente, budgetierte Agentenrollen mit Human-Gates. Der defensive OPSEC Sentinel analysiert lokale App-Risikosignale, kann bei hohem Risiko nur EagleEye-Agentenaktivität pausieren und lernt kontrolliert aus unabhängig reviewten Vorfällen.</p><div class='metrics'><div class='metric'><div class='label'>Runs</div><div class='value'>{d['runs']}</div></div><div class='metric'><div class='label'>OPSEC</div><div class='value'>{e(d['state']['last_risk_level'])}</div></div><div class='metric'><div class='label'>Training</div><div class='value'>{d['training']}</div></div></div><div class='grid'><div class='card'><h3>Run</h3><form method='post' action='/build242/run-create'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><textarea name='objective' required></textarea><button>Run anlegen</button></form></div><div class='card'><h3>OPSEC Sentinel</h3><form method='post' action='/build242/opsec-scan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Lokalen OPSEC-Scan ausführen</button></form><form method='post' action='/build242/opsec-observe'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='category' value='tracking_indicator'><select name='severity'><option>low</option><option selected>medium</option><option>high</option><option>critical</option></select><input name='confidence' type='number' min='0' max='1' step='.05' value='.7'><textarea name='details'></textarea><button>Signal erfassen</button></form></div><div class='card'><h3>Review & Training</h3><form method='post' action='/build242/opsec-review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='observation_id' placeholder='Observation-ID'><select name='decision'><option>confirmed</option><option>false_positive</option><option>needs_context</option></select><select name='reviewed_severity'><option>low</option><option>medium</option><option>high</option><option>critical</option></select><textarea name='rationale'></textarea><button>Review</button></form><form method='post' action='/build242/opsec-train'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Reviewte Fälle fürs Training</button></form></div><div class='card'><h3>Adaptive Policy</h3><form method='post' action='/build242/opsec-calibrate'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Policy-Kandidat erzeugen</button></form><p class='muted'>Automatische Kalibrierung erzeugt nur Kandidaten; Aktivierung braucht unabhängiges Review.</p></div></div><table><thead><tr><th>Run</th><th>Status</th><th>Ziel</th></tr></thead><tbody>{rows}</tbody></table><p class='muted'>Keine autonomen OS-/Netzwerkänderungen, keine Anti-Forensik, keine Schutzumgehung.</p></section>"""
