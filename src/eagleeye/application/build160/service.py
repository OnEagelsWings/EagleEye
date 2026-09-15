from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode('utf-8')).hexdigest()
def _dt(v:str|None):
 if not v:return None
 d=datetime.fromisoformat(v.replace('Z','+00:00'));return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

class Build160InvestigatorDecisionCockpitService:
 BUILD='160.0';MISSION='Investigator Decision Cockpit + governed social OSINT'
 SOURCE_PROFILES=(
  {'source_id':'youtube_data_api','display_name':'YouTube Data API','access_mode':'official_api','official_docs':'https://developers.google.com/youtube/v3','auth_required':1,'public_only':1,'crawl_allowed':0,'capabilities':['video_search','channel_lookup','public_metadata']},
  {'source_id':'reddit_api','display_name':'Reddit Data API','access_mode':'official_api','official_docs':'https://developers.reddit.com/docs/api','auth_required':1,'public_only':1,'crawl_allowed':0,'capabilities':['public_posts','public_comments','subreddit_search']},
  {'source_id':'bluesky_public_api','display_name':'Bluesky Public API','access_mode':'public_api','official_docs':'https://docs.bsky.app','auth_required':0,'public_only':1,'crawl_allowed':0,'capabilities':['profile_lookup','public_posts','search']},
  {'source_id':'mastodon_public_api','display_name':'Mastodon Public API','access_mode':'instance_api','official_docs':'https://docs.joinmastodon.org/api','auth_required':0,'public_only':1,'crawl_allowed':0,'capabilities':['profile_lookup','public_statuses','instance_search']},
  {'source_id':'public_web_crawl','display_name':'Approved Public Web Crawl','access_mode':'investigator_approved_crawl','official_docs':'internal://crawl-policy-160','auth_required':0,'public_only':1,'crawl_allowed':1,'capabilities':['same_site_crawl','public_pages','evidence_capture']},
 )
 def __init__(self,db:Any,audit:Any,*,temporal:Any,collection:Any,source_gate:Any,evidence:Any|None=None,actor:str='system',export_dir:Path|str|None=None):
  self.db=db;self.audit=audit;self.temporal=temporal;self.collection=collection;self.source_gate=source_gate;self.evidence=evidence;self.actor=actor;self.export_dir=Path(export_dir or 'exports_build160');self.export_dir.mkdir(parents=True,exist_ok=True);self._seed_sources()
 def _seed_sources(self):
  for s in self.SOURCE_PROFILES:
   p={**s,'terms_review_required':True,'status':'registered'}
   self.db.execute('INSERT OR IGNORE INTO social_source_profiles_160 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(s['source_id'],s['display_name'],s['access_mode'],s['official_docs'],s['auth_required'],s['public_only'],s['crawl_allowed'],1,'registered',dumps(s['capabilities']),now_ts(),_hash(p)))
 def source_catalog(self)->list[dict[str,Any]]:
  return [dict(r) for r in self.db.all('SELECT * FROM social_source_profiles_160 ORDER BY display_name')]
 def authorize_crawl(self,case_id:str,source_id:str,scope:Mapping[str,Any],*,purpose:str,approved_by:str,confirmation:str,expires_at:str|None=None,budget:Mapping[str,Any]|None=None)->dict[str,Any]:
  if confirmation!=f'CRAWL 160 {case_id} AUTHORISIEREN':raise PermissionError('explicit investigator approval required')
  src=self.db.one('SELECT * FROM social_source_profiles_160 WHERE source_id=?',(source_id,))
  if not src or not src['crawl_allowed']:raise PermissionError('source does not permit governed crawl mode')
  allowed={'seed_urls','allowed_hosts','max_pages','max_depth','include_patterns','exclude_patterns'}
  if set(scope)-allowed:raise ValueError('unsupported crawl scope field')
  hosts=list(scope.get('allowed_hosts') or [])
  if not hosts:raise ValueError('allowed_hosts required')
  b={'max_pages':min(int((budget or {}).get('max_pages',50)),500),'max_depth':min(int((budget or {}).get('max_depth',2)),5),'max_runtime_seconds':min(int((budget or {}).get('max_runtime_seconds',900)),3600)}
  aid=new_id('crawl160');payload={'authorization_id':aid,'case_id':case_id,'source_id':source_id,'scope':dict(scope),'purpose':purpose,'approved_by':approved_by,'expires_at':expires_at,'budget':b,'status':'approved'}
  self.db.execute('INSERT INTO crawl_authorizations_160 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,source_id,dumps(scope),purpose,approved_by,now_ts(),expires_at,dumps(b),'approved',_hash(payload)))
  self.audit.log('crawl_authorized_160','crawl_authorization',aid,case_id,{'source_id':source_id,'budget':b,'public_only':True})
  return payload
 def validate_crawl(self,authorization_id:str)->dict[str,Any]:
  r=self.db.one('SELECT * FROM crawl_authorizations_160 WHERE authorization_id=?',(authorization_id,))
  if not r:raise KeyError('authorization not found')
  if r['status']!='approved':raise PermissionError('authorization inactive')
  if r['expires_at'] and _dt(r['expires_at'])<datetime.now(timezone.utc):raise PermissionError('authorization expired')
  return dict(r)
 def build_cockpit(self,case_id:str)->dict[str,Any]:
  entities=[dict(r) for r in self.db.all('SELECT * FROM temporal_entities_159 WHERE case_id=?',(case_id,))]
  relations=[dict(r) for r in self.db.all('SELECT * FROM temporal_relations_159 WHERE case_id=?',(case_id,))]
  conflicts=[dict(r) for r in self.db.all('SELECT * FROM temporal_conflicts_159 WHERE case_id=? AND review_status=?',(case_id,'open'))]
  candidates=[dict(r) for r in self.db.all('SELECT c.* FROM identity_candidates_156 c JOIN collection_plans_156 p ON p.plan_id=c.plan_id WHERE p.case_id=?',(case_id,))] if self._table('identity_candidates_156') else []
  accepted=sum(1 for c in candidates if c.get('review_status')=='accepted');pending=sum(1 for c in candidates if c.get('review_status') not in {'accepted','rejected'})
  corroborated=sum(1 for r in relations if r.get('status')=='corroborated')
  risks=[]
  if conflicts:risks.append({'severity':'high','type':'temporal_conflicts','count':len(conflicts)})
  if pending:risks.append({'severity':'medium','type':'unreviewed_identity_candidates','count':pending})
  next_steps=[]
  if conflicts:next_steps.append({'priority':1,'action':'review_temporal_conflicts','count':len(conflicts)})
  if pending:next_steps.append({'priority':2,'action':'review_identity_candidates','count':pending})
  if not relations:next_steps.append({'priority':3,'action':'collect_first_party_and_independent_sources'})
  summary={'entities':len(entities),'relations':len(relations),'corroborated_relations':corroborated,'identity_candidates':len(candidates),'accepted_candidates':accepted,'open_conflicts':len(conflicts)}
  sid=new_id('cockpit160');payload={'snapshot_id':sid,'case_id':case_id,'summary':summary,'risks':risks,'next_steps':next_steps,'review_required':True,'automatic_action':False}
  self.db.execute('INSERT INTO cockpit_snapshots_160 VALUES(?,?,?,?,?,?,?)',(sid,case_id,dumps(summary),dumps(risks),dumps(next_steps),now_ts(),_hash(payload)))
  return payload
 def fuse_profile(self,case_id:str,subject_label:str,source_records:Sequence[Mapping[str,Any]],*,confirmation:str)->dict[str,Any]:
  if confirmation!=f'PROFILE 160 {case_id} ZUSAMMENFUEHREN':raise PermissionError('analyst confirmation required')
  claims=[];by_field={}
  for rec in source_records:
   rid=str(rec.get('record_id') or rec.get('id') or new_id('src'))
   for k,v in dict(rec.get('data') or rec).items():
    if k in {'record_id','id','provenance'} or v in (None,''):continue
    by_field.setdefault(k,[]).append({'value':v,'record_id':rid,'provenance':rec.get('provenance',{})})
  conflicts=[]
  for field,vals in by_field.items():
   uniq={_canon(x['value']) for x in vals}
   claims.append({'field':field,'values':vals,'independent_sources':len({x['record_id'] for x in vals})})
   if len(uniq)>1:conflicts.append({'field':field,'values':[x['value'] for x in vals]})
  band='high' if claims and not conflicts and all(c['independent_sources']>=2 for c in claims) else ('medium' if claims else 'low')
  fid=new_id('fusion160');payload={'fusion_id':fid,'case_id':case_id,'subject_label':subject_label,'source_record_ids':[str(r.get('record_id') or r.get('id')) for r in source_records],'claims':claims,'conflicts':conflicts,'confidence_band':band,'review_status':'needs_review','automatic_identity_confirmation':False}
  self.db.execute('INSERT INTO profile_fusion_160 VALUES(?,?,?,?,?,?,?,?,?,?)',(fid,case_id,subject_label,dumps(payload['source_record_ids']),dumps(claims),dumps(conflicts),band,'needs_review',now_ts(),_hash(payload)))
  self.audit.log('profile_fusion_created_160','profile_fusion',fid,case_id,{'confidence_band':band,'conflicts':len(conflicts),'review_required':True})
  return payload
 def export_authority_dossier(self,case_id:str,title:str,*,created_by:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AKTE 160 {case_id} EXPORTIEREN':raise PermissionError('explicit export approval required')
  cockpit=self.build_cockpit(case_id);entities=[dict(r) for r in self.db.all('SELECT * FROM temporal_entities_159 WHERE case_id=?',(case_id,))];relations=[dict(r) for r in self.db.all('SELECT * FROM temporal_relations_159 WHERE case_id=?',(case_id,))];conflicts=[dict(r) for r in self.db.all('SELECT * FROM temporal_conflicts_159 WHERE case_id=?',(case_id,))];fusions=[dict(r) for r in self.db.all('SELECT * FROM profile_fusion_160 WHERE case_id=?',(case_id,))]
  manifest={'case_id':case_id,'title':title,'classification':'OSINT intelligence lead - analyst review required','generated_at':now_ts(),'generated_by':created_by,'methodology':['publicly accessible sources only','review-first identity resolution','provenance retained','no automatic guilt attribution'],'cockpit':cockpit,'entities':entities,'relations':relations,'conflicts':conflicts,'profile_fusions':fusions,'limitations':['This dossier is an intelligence lead, not proof of guilt.','Authorities must independently verify facts and apply lawful process.']}
  did=new_id('dossier160');case_dir=self.export_dir/case_id;case_dir.mkdir(parents=True,exist_ok=True);json_path=case_dir/f'{did}.json';html_path=case_dir/f'{did}.html';json_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
  html=f"<html><meta charset='utf-8'><body><h1>{escape(title)}</h1><p><b>Case:</b> {escape(case_id)}</p><p><b>Classification:</b> OSINT intelligence lead – analyst review required</p><h2>Executive summary</h2><pre>{escape(json.dumps(cockpit,ensure_ascii=False,indent=2))}</pre><h2>Entities</h2><pre>{escape(json.dumps(entities,ensure_ascii=False,indent=2,default=str))}</pre><h2>Relations and provenance</h2><pre>{escape(json.dumps(relations,ensure_ascii=False,indent=2,default=str))}</pre><h2>Conflicts</h2><pre>{escape(json.dumps(conflicts,ensure_ascii=False,indent=2,default=str))}</pre><h2>Limitations</h2><p>This dossier is an intelligence lead, not proof of guilt. Independent verification is required.</p></body></html>";html_path.write_text(html,encoding='utf-8')
  payload={'dossier_id':did,'case_id':case_id,'title':title,'classification':manifest['classification'],'export_path':str(case_dir),'files':[str(json_path),str(html_path)],'manifest_sha256':_hash(manifest)}
  self.db.execute('INSERT INTO authority_dossiers_160 VALUES(?,?,?,?,?,?,?,?,?)',(did,case_id,title,manifest['classification'],str(case_dir),dumps(manifest),created_by,now_ts(),_hash(payload)))
  self.audit.log('authority_dossier_exported_160','authority_dossier',did,case_id,{'files':2,'review_required':True})
  return payload
 def _table(self,name:str)->bool:
  return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(name,)))
