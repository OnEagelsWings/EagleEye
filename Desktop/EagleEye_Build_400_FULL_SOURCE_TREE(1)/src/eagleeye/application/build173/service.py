from __future__ import annotations
import hashlib,json
from collections import defaultdict,deque
from typing import Any,Mapping
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
def _clean(v:Any)->Any:
 if isinstance(v,dict):return {k:('[REDACTED]' if any(x in k.lower() for x in ('token','secret','password','authorization','cookie','session')) else _clean(val)) for k,val in v.items()}
 if isinstance(v,list):return [_clean(x) for x in v]
 return v

class Build173SocialPlatformDepthService:
 BUILD='173.0'
 PROFILES={
  'bluesky_public':{'operations':['get_profile','author_feed','search_posts','post_thread','quotes','reposts'],'thread_model':'ancestor_root_descendants','history_model':'did_handle_profile_observations','access_notes':'Public AppView; cursor pagination; DID and AT-URI preserved.'},
  'mastodon_public':{'operations':['search','account_statuses','public_timeline','status_context','trends','directory'],'thread_model':'status_ancestors_descendants','history_model':'instance_account_profile_observations','access_notes':'Instance-specific capabilities; some endpoints or full-text search may require authentication.'},
  'youtube_data':{'operations':['search','channels','playlist_items','comment_threads','comment_replies'],'thread_model':'top_level_comment_replies','history_model':'channel_metadata_and_uploads_playlist','access_notes':'Official Data API; API key/quota; comment replies may require comments.list for completeness.'},
  'reddit_data':{'operations':['search_posts','user_about','user_submitted','thread_comments','subreddit_context'],'thread_model':'listing_comment_tree','history_model':'account_post_comment_observations','access_notes':'OAuth and current Data API terms required; removals and retention obligations apply.'}
 }
 EXTRA_SOURCES=[
  {'source_id':'eu_ejustice_business_registers','title':'European e-Justice Business Registers Interconnection','jurisdiction':'EU','category':'company_register_gateway','access_mode':'guided_public','base_url':'https://e-justice.europa.eu','docs_url':'https://e-justice.europa.eu/topics/registers-business-insolvency-land/business-registers-search-company-eu_en','terms_url':'https://e-justice.europa.eu/content_legal_notice-365-en.do','entity_kinds':['organization','person','document']},
  {'source_id':'europol_newsroom','title':'Europol Newsroom','jurisdiction':'EU','category':'law_enforcement_publications','access_mode':'official_web','base_url':'https://www.europol.europa.eu','docs_url':'https://www.europol.europa.eu/media-press/newsroom','terms_url':'https://www.europol.europa.eu/legal-notice','entity_kinds':['organization','person','event','document']},
  {'source_id':'de_bka_fahndung','title':'Bundeskriminalamt Fahndung','jurisdiction':'DE','category':'public_wanted_missing_notices','access_mode':'guided_public','base_url':'https://www.bka.de','docs_url':'https://www.bka.de/DE/IhreSicherheit/Fahndungen/fahndungen_node.html','terms_url':'https://www.bka.de/DE/Service/Datenschutz/datenschutz_node.html','entity_kinds':['person','event','location','document']},
  {'source_id':'de_polizei_presseportal','title':'Polizei-Presseportal','jurisdiction':'DE','category':'police_press_releases','access_mode':'guided_public','base_url':'https://www.presseportal.de','docs_url':'https://www.presseportal.de/blaulicht/','terms_url':'https://www.presseportal.de/agb','entity_kinds':['person','organization','event','location','document']},
  {'source_id':'eu_court_press','title':'Court of Justice of the European Union Press Releases','jurisdiction':'EU','category':'court_publications','access_mode':'official_web','base_url':'https://curia.europa.eu','docs_url':'https://curia.europa.eu/jcms/jcms/Jo2_7052/en/','terms_url':'https://curia.europa.eu/jcms/jcms/P_80908/en/','entity_kinds':['person','organization','document','event']}
 ]
 def __init__(self,db:Any,audit:Any,*,collection:Any,correlation:Any,european_sources:Any,actor:str='system'):
  self.db,self.audit,self.collection,self.correlation,self.european_sources,self.actor=db,audit,collection,correlation,european_sources,actor
 def seed_profiles(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!='SOCIAL DEPTH 173 PROFILE ANLEGEN':raise PermissionError('explicit profile approval required')
  for sid,p in self.PROFILES.items():
   payload={'source_id':sid,**p,'status':'DOCUMENTED'}
   self.db.execute('INSERT OR REPLACE INTO social_depth_profiles_173 VALUES(?,?,?,?,?,?,?,?)',(sid,dumps(p['operations']),p['thread_model'],p['history_model'],p['access_notes'],'DOCUMENTED',now_ts(),_hash(payload)))
  return {'profiles':len(self.PROFILES),'automatic_activation':False}
 def seed_extended_sources(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!='SOURCES 173 ERWEITERN':raise PermissionError('explicit source expansion approval required')
  for p in self.EXTRA_SOURCES:
   payload={**p,'status':'DOCUMENTED'}
   self.db.execute('INSERT OR REPLACE INTO extended_source_profiles_173 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(p['source_id'],p['title'],p['jurisdiction'],p['category'],p['access_mode'],p['base_url'],p['docs_url'],p['terms_url'],'DOCUMENTED',dumps(p['entity_kinds']),now_ts(),_hash(payload)))
  return {'created':len(self.EXTRA_SOURCES),'production_active':0,'review_required':True}
 def reconstruct_thread(self,case_id:str,source_id:str,root_record_id:str,nodes:list[Mapping[str,Any]],*,confirmation:str)->dict[str,Any]:
  if source_id not in self.PROFILES:raise KeyError('unsupported social source')
  if confirmation!=f'THREAD 173 {case_id} REKONSTRUIEREN':raise PermissionError('explicit thread reconstruction approval required')
  safe=[_clean(dict(n)) for n in nodes]
  index={str(n.get('id') or n.get('uri') or n.get('name') or i):n for i,n in enumerate(safe)}
  edges=[];children=defaultdict(list)
  for nid,n in index.items():
   parent=n.get('parent_id') or n.get('in_reply_to_id') or n.get('parent_uri') or n.get('reply_to')
   if parent is not None:
    parent=str(parent);edges.append({'type':'replied_to','source':nid,'target':parent,'evidence_class':'direct_public_api'});children[parent].append(nid)
  depth=0;q=deque([(str(root_record_id),0)]);seen=set()
  while q:
   nid,d=q.popleft()
   if nid in seen:continue
   seen.add(nid);depth=max(depth,d)
   for c in children.get(nid,[]):q.append((c,d+1))
  tid=new_id('thread173');payload={'thread_id':tid,'case_id':case_id,'source_id':source_id,'root_record_id':root_record_id,'nodes':list(index.values()),'edges':edges,'depth':depth,'node_count':len(index),'review_required':True}
  self.db.execute('INSERT INTO social_threads_173 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(tid,case_id,source_id,root_record_id,dumps(payload['nodes']),dumps(edges),depth,len(index),now_ts(),'needs_review',_hash(payload)))
  self._event(case_id,'thread_reconstructed',tid,{'source_id':source_id,'nodes':len(index),'depth':depth})
  return {**payload,'automatic_identity_confirmation':False}
 def record_account_history(self,case_id:str,source_id:str,account_ref:str,event_type:str,before:Mapping[str,Any],after:Mapping[str,Any],*,source_refs:list[str],confirmation:str)->dict[str,Any]:
  if confirmation!=f'ACCOUNT HISTORY 173 {case_id} ERFASSEN':raise PermissionError('explicit history approval required')
  if event_type not in {'handle_changed','display_name_changed','profile_changed','account_moved','account_deleted','account_restored'}:raise ValueError('invalid history event')
  hid=new_id('history173');payload={'history_id':hid,'case_id':case_id,'source_id':source_id,'account_ref':account_ref,'event_type':event_type,'before':_clean(dict(before)),'after':_clean(dict(after)),'source_refs':source_refs,'observed_at':now_ts()}
  self.db.execute('INSERT INTO social_account_history_173 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(hid,case_id,source_id,account_ref,event_type,dumps(payload['before']),dumps(payload['after']),payload['observed_at'],dumps(source_refs),'needs_review',_hash(payload)))
  return {**payload,'review_required':True}
 def record_content_event(self,case_id:str,source_id:str,record_ref:str,event_type:str,*,details:Mapping[str,Any],source_refs:list[str],event_time:str|None=None)->dict[str,Any]:
  if event_type not in {'created','edited','deleted','unavailable','restored','reposted','quoted'}:raise ValueError('invalid content event')
  eid=new_id('content173');payload={'event_id':eid,'case_id':case_id,'source_id':source_id,'record_ref':record_ref,'event_type':event_type,'event_time':event_time,'details':_clean(dict(details)),'source_refs':source_refs}
  self.db.execute('INSERT INTO social_content_events_173 VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,case_id,source_id,record_ref,event_type,event_time,dumps(payload['details']),dumps(source_refs),'needs_review',_hash(payload)))
  return {**payload,'review_required':True}
 def source_depth_matrix(self)->list[dict[str,Any]]:
  out=[]
  for sid,p in self.PROFILES.items():
   out.append({'source_id':sid,'operation_count':len(p['operations']),'thread_model':p['thread_model'],'history_model':p['history_model'],'production_active':False,'review_required':True})
  return out
 def source_coverage(self)->dict[str,Any]:
  base=int(self.db.one('SELECT COUNT(*) n FROM european_source_profiles_172')['n'])
  extra=int(self.db.one('SELECT COUNT(*) n FROM extended_source_profiles_173')['n'])
  report={'build':self.BUILD,'existing_european_sources':base,'new_sources':extra,'total_documented_sources':base+extra,'social_platforms_deepened':len(self.PROFILES),'production_active_new':0,'gap_statement':'Depth and official-source coverage increased; live activation still requires current terms, credentials, probes and source-gate approval.'};report['payload_sha256']=_hash(report);return report
 def case_summary(self,case_id:str)->dict[str,Any]:
  def c(t):return int(self.db.one(f'SELECT COUNT(*) n FROM {t} WHERE case_id=?',(case_id,))['n'])
  return {'case_id':case_id,'threads':c('social_threads_173'),'account_history_events':c('social_account_history_173'),'content_events':c('social_content_events_173'),'review_required':True,'automatic_identity_confirmation':False,'opsec':{'public_only':True,'no_interaction':True,'secrets_redacted':True}}
 def _event(self,case_id,event_type,entity_ref,details):
  eid=new_id('depth173');safe=_clean(details)
  self.db.execute('INSERT INTO social_depth_events_173 VALUES(?,?,?,?,?,?,?)',(eid,case_id,event_type,entity_ref,dumps(safe),now_ts(),_hash({'event_id':eid,'details':safe})))
  try:self.audit.log(f'social_depth_{event_type}_173','social_depth',entity_ref or case_id,case_id,safe)
  except Exception:pass
