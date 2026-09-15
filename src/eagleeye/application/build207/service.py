from __future__ import annotations
import hashlib,json,re
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from typing import Any,Mapping,Sequence
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256((v if isinstance(v,bytes) else _canon(v).encode())).hexdigest()
def _tokens(s:str)->set[str]:return {x for x in re.findall(r"[\w\-]{2,}",str(s).lower(),re.UNICODE)}
def _redact(v:Any)->Any:
 if isinstance(v,dict):return {k:('[REDACTED]' if re.search(r'token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key',k,re.I) else _redact(x)) for k,x in v.items()}
 if isinstance(v,list):return [_redact(x) for x in v]
 return v

def _inj(t:str)->bool:return bool(re.search(r'ignore previous instructions|reveal (?:the )?system prompt|bypass policy|execute this command',str(t),re.I))

class Build207ControlledAIInvestigatorAgentsService:
 BUILD='207.0'
 AGENTS=(
  ('planner','Planner Agent','planning',['case.read','plan.write'],['case_context','source_catalog']),
  ('source','Source Agent','source_selection',['case.read','source.read','query.prepare'],['approved_sources']),
  ('extractor','Extraction Agent','extraction',['case.read','document.read','claim.propose'],['case_documents','social_posts','news_articles']),
  ('verifier','Verification Agent','verification',['case.read','evidence.read','conflict.mark'],['evidence_graph','temporal_identity','media_verification']),
  ('hypothesis','Hypothesis Agent','hypothesis',['case.read','hypothesis.propose'],['verified_candidates']),
  ('synthesis','Synthesis Agent','synthesis',['case.read','report.propose','chat.answer'],['approved_findings']))
 def __init__(self,db:Any,audit:Any,*,retrieval:Any,social:Any,news:Any,runtime:Any,graph:Any,identity:Any,verification:Any,workspace:Any,actor:str='system'):
  self.db,self.audit=db,audit;self.retrieval=retrieval;self.social=social;self.news=news;self.runtime=runtime;self.graph=graph;self.identity=identity;self.verification=verification;self.workspace=workspace;self.actor=actor
 def _event(self,case_id,event_type,payload,run_id=None,actor=None):
  prev=self.db.one('SELECT event_hash FROM ai_agent_events_207 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,));ph=prev['event_hash'] if prev else None;t=now_ts();eid=new_id('aevt207');body={'event_id':eid,'run_id':run_id,'case_id':case_id,'event_type':event_type,'actor':actor or self.actor,'payload':_redact(payload),'prev_hash':ph,'created_at':t};eh=_hash(body);self.db.execute('INSERT INTO ai_agent_events_207 VALUES(?,?,?,?,?,?,?,?,?)',(eid,run_id,case_id,event_type,actor or self.actor,dumps(body['payload']),ph,eh,t));return eh
 def seed_agents(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!='AI AGENTS 207 ANLEGEN':raise PermissionError('explicit approval required')
  t=now_ts()
  for aid,name,role,perms,scope in self.AGENTS:
   policy={'least_privilege':True,'citation_required':True,'automatic_action':False,'prompt_injection_isolation':True,'human_review_required':True}
   self.db.execute('INSERT OR REPLACE INTO ai_agent_profiles_207 VALUES(?,?,?,?,?,?,?,?)',(aid,name,role,dumps(perms),dumps(scope),'active',t,dumps(policy)))
  return {'agents':len(self.AGENTS),'least_privilege':True,'automatic_action':False}
 def create_run(self,*,case_id:str,question:str,created_by:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI RUN 207 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
  if not question.strip():raise ValueError('question required')
  rid=new_id('airun207');t=now_ts();policy={'sources_before_models':True,'citation_required':True,'automatic_action':False,'automatic_identity_confirmation':False,'case_isolation':True,'external_uploads':False}
  payload={'run_id':rid,'case_id':case_id,'question':question.strip(),'status':'draft','current_stage':'planning','created_by':created_by,'created_at':t,'policy':policy}
  self.db.execute('INSERT INTO ai_agent_runs_207 VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,case_id,question.strip(),'draft','planning',created_by,t,t,dumps(policy),_hash(payload)))
  self._event(case_id,'run_created',payload,rid,created_by);return payload
 def plan(self,*,run_id:str,countries:Sequence[str]=(),source_ids:Sequence[str]=(),confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI PLAN 207 {run_id} ERSTELLEN':raise PermissionError('explicit approval required')
  run=self.db.one('SELECT * FROM ai_agent_runs_207 WHERE run_id=?',(run_id,));
  if not run:raise KeyError(run_id)
  q=run['question'];intents=[]
  for pat,label in [(r'firma|unternehmen|company|organization','organization'),(r'account|social|profil|post','social'),(r'nachricht|zeitung|bericht|news','news'),(r'famil|eltern|kind|genealog','family'),(r'rolle|beruf|arbeit','role'),(r'bild|video|audio|fake','authenticity')]:
   if re.search(pat,q,re.I):intents.append(label)
  if not intents:intents=['identity','background']
  tasks=[];specs=[('planner',{'question':q,'intents':intents,'countries':list(countries)}),('source',{'question':q,'source_ids':list(source_ids),'countries':list(countries)}),('extractor',{'question':q,'case_id':run['case_id']}),('verifier',{'question':q,'checks':['source_independence','timeline','identity','provenance']}),('hypothesis',{'question':q,'rule':'working_hypotheses_only'}),('synthesis',{'question':q,'citation_required':True})]
  for i,(aid,inp) in enumerate(specs,1):
   tid=new_id('aitask207');req=1 if aid in {'source','synthesis'} else 0;t=now_ts();safe=_redact(inp)
   self.db.execute('INSERT INTO ai_agent_tasks_207 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(tid,run_id,aid,i,dumps(safe),None,'planned',req,None,t,t,_hash({'tid':tid,'input':safe})));tasks.append({'task_id':tid,'agent_id':aid,'sequence_no':i,'requires_approval':bool(req)})
  self.db.execute('UPDATE ai_agent_runs_207 SET status=?,current_stage=?,updated_at=? WHERE run_id=?',('planned','source_selection',now_ts(),run_id));self._event(run['case_id'],'plan_created',{'tasks':tasks,'intents':intents},run_id)
  return {'run_id':run_id,'intents':intents,'tasks':tasks,'automatic_execution':False}
 def approve_task(self,*,run_id:str,task_id:str,approved_by:str,scope:Mapping[str,Any],hours_valid:int=4,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI TASK 207 {task_id} FREIGEBEN':raise PermissionError('explicit approval required')
  task=self.db.one('SELECT * FROM ai_agent_tasks_207 WHERE task_id=? AND run_id=?',(task_id,run_id));
  if not task:raise KeyError(task_id)
  aid=new_id('approval207');exp=(datetime.now(timezone.utc)+timedelta(hours=max(1,min(hours_valid,24)))).isoformat();safe=_redact(dict(scope));payload={'approval_id':aid,'run_id':run_id,'task_id':task_id,'action':'execute_task','approved_by':approved_by,'scope':safe,'expires_at':exp}
  self.db.execute('INSERT INTO ai_agent_approvals_207 VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,run_id,task_id,'execute_task',approved_by,dumps(safe),0,exp,now_ts(),_hash(payload)))
  self.db.execute('UPDATE ai_agent_tasks_207 SET approved_by=?,updated_at=? WHERE task_id=?',(approved_by,now_ts(),task_id));return payload
 def _has_approval(self,task):
  if not task['requires_approval']:return True
  r=self.db.one('SELECT * FROM ai_agent_approvals_207 WHERE task_id=? AND used=0 ORDER BY created_at DESC LIMIT 1',(task['task_id'],));
  if not r:return False
  return not r['expires_at'] or datetime.fromisoformat(r['expires_at'])>=datetime.now(timezone.utc)
 def execute_task(self,*,run_id:str,task_id:str,context:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI TASK 207 {task_id} AUSFUEHREN':raise PermissionError('explicit approval required')
  task=self.db.one('SELECT * FROM ai_agent_tasks_207 WHERE task_id=? AND run_id=?',(task_id,run_id));run=self.db.one('SELECT * FROM ai_agent_runs_207 WHERE run_id=?',(run_id,));
  if not task or not run:raise KeyError(task_id)
  if not self._has_approval(task):raise PermissionError('task approval required')
  ctx=_redact(dict(context or {}));agent=task['agent_id'];out={'agent_id':agent,'status':'candidate','citations':[],'automatic_action':False}
  if agent=='planner':out.update({'plan':json.loads(task['input_json'])})
  elif agent=='source':out.update({'source_tasks':ctx.get('source_tasks',[]),'execution':'prepared_only'})
  elif agent=='extractor':
   docs=ctx.get('documents',[]);claims=[]
   for d in docs:
    text=str(d.get('text',''))
    for s in re.split(r'(?<=[.!?])\s+',text):
     if len(s)>25 and re.search(r'\b(?:ist|war|hat|leitete|arbeitete|is|was|has|led|served)\b',s,re.I):claims.append({'statement':s.strip(),'source_ref':d.get('source_ref'),'prompt_injection_candidate':_inj(text)})
   out.update({'claims':claims[:80],'citations':[{'source_ref':x.get('source_ref')} for x in docs if x.get('source_ref')]})
  elif agent=='verifier':
   claims=ctx.get('claims',[]);groups=defaultdict(list)
   for c in claims:groups[' '.join(sorted(_tokens(c.get('statement','')))[:12])].append(c)
   out.update({'verified_candidates':[{'statement':v[0]['statement'],'source_count':len({x.get('source_ref') for x in v}),'status':'corroborated_candidate' if len({x.get('source_ref') for x in v})>=2 else 'supported_candidate','citations':[{'source_ref':x.get('source_ref')} for x in v]} for v in groups.values()]})
  elif agent=='hypothesis':
   vc=ctx.get('verified_candidates',[]);out.update({'hypotheses':[{'statement':x['statement'],'status':'working_hypothesis','support_status':x.get('status'),'citations':x.get('citations',[]),'verification_plan':['Primärquelle prüfen','Zeitbezug prüfen','Identität abgleichen','Quellenunabhängigkeit prüfen']} for x in vc[:30]]})
  elif agent=='synthesis':
   hs=ctx.get('hypotheses',[]);out.update({'answer':' | '.join(x.get('statement','') for x in hs[:8]) or 'Keine ausreichend belegte Arbeitshypothese verfügbar.','hypotheses':hs[:20],'citations':[c for h in hs[:20] for c in h.get('citations',[])][:40],'human_review_required':True})
  self.db.execute('UPDATE ai_agent_tasks_207 SET output_json=?,status=?,updated_at=? WHERE task_id=?',(dumps(out),'completed',now_ts(),task_id));self.db.execute('UPDATE ai_agent_approvals_207 SET used=1 WHERE task_id=? AND used=0',(task_id,));self._event(run['case_id'],'task_completed',{'task_id':task_id,'agent_id':agent,'output':out},run_id)
  return out
 def social_deep_snapshot(self,*,case_id:str,account_ids:Sequence[str],confirmation:str)->dict[str,Any]:
  if confirmation!=f'SOCIAL DEEP 207 {case_id} ERSTELLEN':raise PermissionError('explicit approval required')
  accounts=[];posts=[]
  for aid in account_ids:
   a=self.db.one('SELECT * FROM social_accounts_204 WHERE account_id=? AND case_id=?',(aid,case_id));
   if a:accounts.append(dict(a));posts.extend(dict(x) for x in self.db.all('SELECT * FROM social_posts_204 WHERE account_id=? AND case_id=?',(aid,case_id)))
  interactions=Counter();activity=Counter();aliases=defaultdict(list);cit=[]
  for a in accounts:
   aliases[str(a.get('handle','')).lower()].append({'account_id':a['account_id'],'source_id':a['source_id'],'display_name':a.get('display_name')});cit.append({'source_ref':a.get('source_ref'),'account_id':a['account_id']})
  for p in posts:
   for fld in ('reply_to','repost_of','quote_of'):
    if p.get(fld):interactions[fld]+=1
   if p.get('published_at'):activity[str(p['published_at'])[:10]]+=1
   cit.append({'source_ref':p.get('source_ref'),'post_id':p['post_id']})
  alias_candidates=[{'handle':h,'accounts':vals,'status':'candidate'} for h,vals in aliases.items() if h and len(vals)>=2]
  sid=new_id('socialdeep207');payload={'snapshot_id':sid,'case_id':case_id,'platforms':sorted({a['source_id'] for a in accounts}),'interaction_counts':dict(interactions),'activity':dict(activity),'alias_candidates':alias_candidates,'citations':cit,'status':'candidate','created_at':now_ts()}
  self.db.execute('INSERT INTO social_research_snapshots_207 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,case_id,dumps(list(account_ids)),dumps(payload['platforms']),dumps(payload['interaction_counts']),dumps(payload['activity']),dumps(alias_candidates),dumps(cit),'candidate',payload['created_at'],_hash(payload)))
  return {**payload,'same_person_confirmed':False,'coordination_confirmed':False}
 def finalize(self,*,run_id:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI RUN 207 {run_id} ABSCHLIESSEN':raise PermissionError('explicit approval required')
  run=self.db.one('SELECT * FROM ai_agent_runs_207 WHERE run_id=?',(run_id,));tasks=[dict(x) for x in self.db.all('SELECT * FROM ai_agent_tasks_207 WHERE run_id=? ORDER BY sequence_no',(run_id,))]
  if not run:raise KeyError(run_id)
  if any(x['status']!='completed' for x in tasks):return {'run_id':run_id,'status':'blocked','reason':'incomplete_tasks'}
  synth=json.loads(tasks[-1]['output_json']);findings=[]
  for h in synth.get('hypotheses',[]):
   fid=new_id('finding207');payload={'finding_id':fid,'run_id':run_id,'case_id':run['case_id'],'finding_type':'working_hypothesis','statement':h.get('statement',''),'status':'candidate','confidence':0.5,'citations':h.get('citations',[]),'verification_plan':h.get('verification_plan',[]),'created_at':now_ts()};self.db.execute('INSERT INTO ai_agent_findings_207 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(fid,run_id,run['case_id'],'working_hypothesis',payload['statement'],'candidate',payload['confidence'],dumps(payload['citations']),dumps(payload['verification_plan']),payload['created_at'],_hash(payload)));findings.append(payload)
  self.db.execute('UPDATE ai_agent_runs_207 SET status=?,current_stage=?,updated_at=? WHERE run_id=?',('review_required','human_review',now_ts(),run_id));return {'run_id':run_id,'status':'review_required','findings':findings,'automatic_case_update':False}
 def feedback(self,*,case_id:str,item_ref:str,verdict:str,reason:str,analyst:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI AGENT FEEDBACK 207 {case_id} SPEICHERN':raise PermissionError('explicit approval required')
  if verdict not in {'confirmed','rejected','needs_more_evidence','partially_correct'}:raise ValueError('invalid verdict')
  fid=new_id('feedback207');payload={'feedback_id':fid,'case_id':case_id,'item_ref':item_ref,'verdict':verdict,'reason':reason,'analyst':analyst,'created_at':now_ts()};self.db.execute('INSERT INTO ai_agent_feedback_207 VALUES(?,?,?,?,?,?,?,?)',(fid,case_id,item_ref,verdict,reason,analyst,payload['created_at'],_hash(payload)));return {**payload,'used_for_local_calibration':True,'model_weights_changed_automatically':False}
