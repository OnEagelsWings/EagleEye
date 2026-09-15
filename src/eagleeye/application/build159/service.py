from __future__ import annotations
import hashlib,json,re
from datetime import datetime,timezone
from typing import Any,Mapping
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
def _dt(v:str|None)->datetime|None:
 if not v:return None
 s=v.replace('Z','+00:00')
 d=datetime.fromisoformat(s)
 return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

class Build159TemporalPersonGraphService:
 BUILD='159.0'; MISSION='Temporal Person Graph + OPSEC-safe AI Assistance'
 SENSITIVE=re.compile(r'(?i)(password|token|secret|api[_ -]?key|cookie|authorization|street address|home address)')
 def __init__(self,db:Any,audit:Any,*,multilingual:Any,actor:str='system'):
  self.db=db;self.audit=audit;self.multilingual=multilingual;self.actor=actor
 def add_entity(self,entity_type:str,label:str,*,case_id:str|None=None,attributes:Mapping[str,Any]|None=None)->dict[str,Any]:
  if entity_type not in {'person','organization','location','event','document','account'}:raise ValueError('unsupported entity_type')
  eid=new_id('tent159');payload={'entity_id':eid,'case_id':case_id,'entity_type':entity_type,'label':label,'attributes':dict(attributes or {})}
  self.db.execute('INSERT INTO temporal_entities_159 VALUES(?,?,?,?,?,?,?)',(eid,case_id,entity_type,label,dumps(payload['attributes']),now_ts(),_hash(payload)))
  self.audit.log('temporal_entity_added_159','temporal_entity',eid,case_id,{'entity_type':entity_type})
  return payload
 def add_relation(self,subject_id:str,predicate:str,object_id:str,*,case_id:str|None=None,valid_from:str|None=None,valid_to:str|None=None,observed_at:str|None=None,source_time:str|None=None,source_ref:str|None=None,confidence:float=.5,status:str='candidate',provenance:Mapping[str,Any]|None=None)->dict[str,Any]:
  if status not in {'candidate','corroborated','disputed','rejected'}:raise ValueError('invalid status')
  if not 0<=confidence<=1:raise ValueError('confidence out of range')
  vf,vt=_dt(valid_from),_dt(valid_to)
  if vf and vt and vf>vt:raise ValueError('valid_from after valid_to')
  rid=new_id('trel159'); obs=observed_at or now_ts(); prov=dict(provenance or {})
  payload={'relation_id':rid,'case_id':case_id,'subject_id':subject_id,'predicate':predicate,'object_id':object_id,'valid_from':valid_from,'valid_to':valid_to,'observed_at':obs,'source_time':source_time,'source_ref':source_ref,'confidence':confidence,'status':status,'provenance':prov}
  self.db.execute('INSERT INTO temporal_relations_159 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,case_id,subject_id,predicate,object_id,valid_from,valid_to,obs,source_time,source_ref,confidence,status,dumps(prov),now_ts(),_hash(payload)))
  self.audit.log('temporal_relation_added_159','temporal_relation',rid,case_id,{'predicate':predicate,'status':status,'review_required':True})
  return payload
 def detect_conflicts(self,case_id:str)->list[dict[str,Any]]:
  rows=self.db.all('SELECT * FROM temporal_relations_159 WHERE case_id=? AND status<>? ORDER BY subject_id,predicate',(case_id,'rejected')); out=[]
  exclusive={'worked_at','lived_at','married_to','position_at'}
  for i,a in enumerate(rows):
   for b in rows[i+1:]:
    if a['subject_id']!=b['subject_id'] or a['predicate']!=b['predicate'] or a['predicate'] not in exclusive or a['object_id']==b['object_id']:continue
    af,at=_dt(a['valid_from']),_dt(a['valid_to']);bf,bt=_dt(b['valid_from']),_dt(b['valid_to'])
    overlap=(af is None or bt is None or af<=bt) and (bf is None or at is None or bf<=at)
    if not overlap:continue
    cid=new_id('tconf159'); exp={'reason':'overlapping_exclusive_relation','predicate':a['predicate'],'objects':[a['object_id'],b['object_id']]}; payload={'conflict_id':cid,'case_id':case_id,'relation_a_id':a['relation_id'],'relation_b_id':b['relation_id'],'conflict_type':'temporal_overlap','severity':'high','explanation':exp,'review_status':'open'}
    self.db.execute('INSERT OR IGNORE INTO temporal_conflicts_159 VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,case_id,a['relation_id'],b['relation_id'],'temporal_overlap','high',dumps(exp),'open',now_ts(),_hash(payload)));out.append(payload)
  return out
 def timeline(self,entity_id:str)->list[dict[str,Any]]:
  return [dict(r) for r in self.db.all('SELECT * FROM temporal_relations_159 WHERE subject_id=? OR object_id=? ORDER BY COALESCE(valid_from,observed_at),observed_at',(entity_id,entity_id))]
 def add_alias(self,canonical_name:str,alias_name:str,*,case_id:str|None=None,locale:str|None=None,alias_type:str='transliteration')->dict[str,Any]:
  if alias_type not in {'transliteration','former_name','nickname','spelling_variant','script_variant'}:raise ValueError('invalid alias_type')
  norm=self.multilingual.normalize_name(alias_name,locale=locale);aid=new_id('alias159');payload={'alias_id':aid,'case_id':case_id,'canonical_name':canonical_name,'alias_name':alias_name,'locale':locale,'alias_type':alias_type,'normalized':norm}
  self.db.execute('INSERT INTO multilingual_aliases_159 VALUES(?,?,?,?,?,?,?,?,?)',(aid,case_id,canonical_name,alias_name,locale,alias_type,dumps(norm),now_ts(),_hash(payload)));return payload
 def compare_identity(self,left:str,right:str,**kwargs:Any)->dict[str,Any]:
  result=self.multilingual.compare(left,right,**kwargs)
  # OPSEC risk lowers confidence and forces explicit review.
  penalty=.12*len(result.get('warnings',[]));result['risk_adjusted_score']=max(0.0,result['score']-penalty);result['review_required']=True;result['automatic_identity_confirmation']=False
  return result
 def assist(self,case_id:str,task_type:str,context:Mapping[str,Any])->dict[str,Any]:
  if task_type not in {'conflict_triage','next_steps','timeline_gap','hypothesis_check'}:raise ValueError('unsupported task_type')
  raw=_canon(context); findings=[]
  if self.SENSITIVE.search(raw): findings.append('sensitive_input_redacted')
  safe={k:('[REDACTED]' if self.SENSITIVE.search(str(k)) else v) for k,v in context.items()}
  conflicts=self.detect_conflicts(case_id) if task_type in {'conflict_triage','next_steps','hypothesis_check'} else []
  suggestions=[]
  if conflicts:suggestions.append({'priority':'high','action':'review_temporal_conflicts','reason':f'{len(conflicts)} overlapping exclusive relations'})
  if task_type=='timeline_gap':suggestions.append({'priority':'medium','action':'seek_independent_sources_for_open_intervals','reason':'temporal gaps require corroboration'})
  if not suggestions:suggestions.append({'priority':'low','action':'validate_provenance_and_collect_second_source','reason':'review-first baseline'})
  output={'task_type':task_type,'suggestions':suggestions,'conflict_ids':[c['conflict_id'] for c in conflicts],'limitations':['AI output is advisory','no automatic identity or relationship confirmation'],'review_required':True}
  opsec={'local_only':True,'external_model_called':False,'redactions':findings,'sensitive_content_persisted':False}
  aid=new_id('ai159');payload={'assistance_id':aid,'case_id':case_id,'task_type':task_type,'input_sha256':_hash(safe),'output':output,'opsec':opsec}
  self.db.execute('INSERT INTO ai_assistance_159 VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,case_id,task_type,_hash(safe),dumps(output),dumps(opsec),'local_deterministic',1,now_ts(),_hash(payload)))
  self.audit.log('ai_assistance_generated_159','ai_assistance',aid,case_id,{'task_type':task_type,'local_only':True,'review_required':True})
  return {**payload,'review_required':True,'automatic_action':False}
