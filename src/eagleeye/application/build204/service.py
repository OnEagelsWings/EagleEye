from __future__ import annotations
import hashlib,json,re
from typing import Any,Mapping,Sequence
from urllib.parse import quote_plus
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
def _clean(q:str)->str:
 q=re.sub(r'(?<!\d)\b(?:0[\.,]\d+|1[\.,]0+)\b',' ',q)
 return re.sub(r'\s+',' ',q.replace(';',' ')).strip()
def _tokens(s:str)->set[str]:return {x for x in re.findall(r"[\w\-]{3,}",s.lower(),re.UNICODE)}
def _mask(v:str)->str:
 v=str(v or '')
 return v[:2]+'…'+v[-2:] if len(v)>5 else '…'

class Build204SocialIdentityOperationsService:
 BUILD='204.0'
 SOURCES=[
 ('bluesky_public','Bluesky Public AppView','global','public_api','https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts','posts_accounts','production_candidate'),
 ('mastodon_public','Mastodon Public API','instance','instance_api','/api/v2/search','posts_accounts','production_candidate'),
 ('github_public','GitHub REST API','global','credential_optional_api','https://api.github.com/search/users','accounts_events','production_candidate'),
 ('youtube_public','YouTube Data API','global','credentialed_api','https://www.googleapis.com/youtube/v3/search','videos_channels','contract_validated'),
 ('reddit_public','Reddit Data API','global','credentialed_or_guided','https://oauth.reddit.com/search','posts_accounts','restricted_review'),
 ('telegram_public_web','Telegram Public Web','global','guided_browser','https://t.me/s/','channels_posts','guided_ready'),
 ('mastodon_directory','Mastodon Instance Directory','global','guided_browser','https://instances.social/','instances','guided_ready'),
 ('internet_archive_social','Internet Archive Social History','global','structured_api','https://web.archive.org/cdx/search/cdx','history','production_candidate'),
 ('google_social_discovery','Google Social Discovery','global','guided_browser','https://www.google.com/search?q=','discovery','guided_ready'),
 ('bing_social_discovery','Bing Social Discovery','global','guided_browser','https://www.bing.com/search?q=','discovery','guided_ready')]
 def __init__(self,db:Any,audit:Any,*,runtime:Any,country_packs:Any,country_packs_ii:Any,pilot_ai:Any,platform:Any,graph:Any,identity:Any,monitoring:Any,workspace:Any,actor:str='system'):
  self.db,self.audit=db,audit;self.runtime=runtime;self.country_packs=country_packs;self.country_packs_ii=country_packs_ii;self.pilot_ai=pilot_ai;self.platform=platform;self.graph=graph;self.identity=identity;self.monitoring=monitoring;self.workspace=workspace;self.actor=actor
 def seed(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!='SOCIAL SOURCES 204 ANLEGEN':raise PermissionError('explicit approval required')
  created=now_ts()
  for sid,name,scope,access,endpoint,domain,status in self.SOURCES:
   p={'source_id':sid,'name':name,'scope':scope,'access':access,'endpoint':endpoint,'domain':domain,'status':status}
   self.db.execute('INSERT OR REPLACE INTO social_source_profiles_204 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,name,scope,access,endpoint,domain,status,0,0,0,0,created,created,_hash(p),dumps({'public_only':True,'no_private_access':True,'respect_terms':True})))
  return {'sources':len(self.SOURCES),'structured_candidates':sum(1 for x in self.SOURCES if 'api' in x[3]),'automatic_activation':False}
 def create_search_plan(self,*,case_id:str,question:str,person:Mapping[str,Any],platforms:Sequence[str]|None=None,confirmation:str)->dict[str,Any]:
  if confirmation!=f'SOCIAL PLAN 204 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
  clean=_clean(question);name=' '.join(str(person.get(k,'')).strip() for k in ('given_name','family_name') if person.get(k)).strip();handles=[str(x).lstrip('@') for x in person.get('handles',[])];query=_clean(' '.join([name,*handles,clean]));rows=[dict(r) for r in self.db.all('SELECT * FROM social_source_profiles_204')]
  if platforms: rows=[r for r in rows if r['source_id'] in set(platforms)]
  def rank(r):
   s=80 if r['status']=='production_active' else 60 if r['status']=='production_candidate' else 35
   if r['domain'] in ('posts_accounts','accounts_events'):s+=20
   if 'histor' in clean.lower() and r['domain']=='history':s+=40
   return (-s,r['name'])
  rows=sorted(rows,key=rank);tabs=[];jobs=[]
  for r in rows:
   if r['source_id']=='bluesky_public': url='https://bsky.app/search?q='+quote_plus(query)
   elif r['source_id']=='github_public': url='https://github.com/search?q='+quote_plus(query)+'&type=users'
   elif r['source_id']=='youtube_public': url='https://www.youtube.com/results?search_query='+quote_plus(query)
   elif r['source_id']=='reddit_public': url='https://www.reddit.com/search/?q='+quote_plus(query)
   elif r['source_id']=='telegram_public_web': url='https://www.google.com/search?q='+quote_plus('site:t.me '+query)
   elif r['source_id']=='mastodon_public': url='https://www.google.com/search?q='+quote_plus('site:mastodon.social '+query)
   elif r['source_id']=='internet_archive_social': url='https://web.archive.org/web/*/'+quote_plus(query)
   else:url=r['endpoint']+quote_plus(query)
   if len(tabs)<5:tabs.append({'source_id':r['source_id'],'title':r['name'],'url':url,'command':['firefox.exe','-new-tab',url],'existing_firefox_session':True})
   if r['access'] in ('public_api','instance_api','credential_optional_api','credentialed_api','structured_api'):
    jobs.append({'source_id':r['source_id'],'query':query,'mode':'fast_discovery','candidate_only':True,'citation_required':True,'public_only':True})
  pid=new_id('socialplan204');payload={'plan_id':pid,'case_id':case_id,'question':clean,'query':query,'tabs':tabs,'jobs':jobs,'created_at':now_ts()}
  self.db.execute('INSERT INTO social_search_plans_204 VALUES(?,?,?,?,?,?,?,?,?)',(pid,case_id,clean,dumps(person),dumps(tabs),dumps(jobs),payload['created_at'],_hash(payload),'candidate_only'))
  return {**payload,'parallel_tabs':len(tabs),'co_investigator_enabled':True,'automatic_identity_confirmation':False}
 def normalize_account(self,*,case_id:str,source_id:str,record:Mapping[str,Any],confirmation:str)->dict[str,Any]:
  if confirmation!=f'SOCIAL ACCOUNT 204 {case_id} SPEICHERN':raise PermissionError('explicit approval required')
  handle=str(record.get('handle') or record.get('username') or record.get('login') or '').strip();
  if not handle:raise ValueError('handle required')
  aid=new_id('socialacct204');profile={'display_name':record.get('display_name') or record.get('name'),'bio':record.get('bio') or record.get('description'),'url':record.get('url') or record.get('html_url'),'created_at':record.get('created_at'),'followers':record.get('followers_count') or record.get('followers'),'following':record.get('following_count') or record.get('following')}
  payload={'account_id':aid,'case_id':case_id,'source_id':source_id,'handle':handle,'profile':profile,'source_ref':record.get('source_ref') or profile['url'] or f'{source_id}:{handle}','observed_at':record.get('observed_at') or now_ts(),'status':'candidate'}
  self.db.execute('INSERT INTO social_accounts_204 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,source_id,handle,dumps(profile),payload['source_ref'],payload['observed_at'],'candidate',_hash(payload),0,now_ts()))
  return {**payload,'automatic_same_person':False,'human_review_required':True}
 def record_post(self,*,case_id:str,account_id:str,source_id:str,post:Mapping[str,Any],confirmation:str)->dict[str,Any]:
  if confirmation!=f'SOCIAL POST 204 {case_id} SPEICHERN':raise PermissionError('explicit approval required')
  text=str(post.get('text') or post.get('title') or '')[:10000];pid=new_id('socialpost204');relations={'reply_to':post.get('reply_to'),'repost_of':post.get('repost_of'),'quote_of':post.get('quote_of'),'thread_root':post.get('thread_root')}
  payload={'post_id':pid,'case_id':case_id,'account_id':account_id,'source_id':source_id,'text':text,'published_at':post.get('published_at'),'source_ref':post.get('source_ref'),'relations':relations,'status':'candidate'}
  self.db.execute('INSERT INTO social_posts_204 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,account_id,source_id,text,post.get('published_at'),post.get('source_ref'),dumps(relations),'candidate',_hash(payload),now_ts()))
  return {**payload,'untrusted_content_is_data':True}
 def assess_cross_platform(self,*,case_id:str,account_ids:Sequence[str],confirmation:str)->dict[str,Any]:
  if confirmation!=f'SOCIAL MATCH 204 {case_id} PRUEFEN':raise PermissionError('explicit approval required')
  rows=[dict(self.db.one('SELECT * FROM social_accounts_204 WHERE account_id=? AND case_id=?',(aid,case_id))) for aid in account_ids]
  rows=[r for r in rows if r]
  if len(rows)<2:raise ValueError('at least two accounts required')
  handles=[r['handle'].lower().lstrip('@') for r in rows];profiles=[json.loads(r['profile_json']) for r in rows];signals=[]
  if len(set(handles))==1:signals.append({'type':'same_handle','score':.55})
  names=[str(p.get('display_name') or '').strip().lower() for p in profiles if p.get('display_name')]
  if len(names)>=2 and len(set(names))==1:signals.append({'type':'same_display_name','score':.25})
  bios=[_tokens(str(p.get('bio') or '')) for p in profiles]
  if len(bios)>=2 and bios[0] and bios[1]:
   j=len(bios[0]&bios[1])/max(1,len(bios[0]|bios[1]));
   if j>=.35:signals.append({'type':'bio_similarity','score':min(.25,j*.3)})
  score=min(.85,sum(s['score'] for s in signals));status='corroborated_candidate' if score>=.7 and len({r['source_id'] for r in rows})>=2 else 'candidate'
  mid=new_id('socialmatch204');payload={'match_id':mid,'case_id':case_id,'account_ids':list(account_ids),'masked_handles':[_mask(x) for x in handles],'signals':signals,'score':score,'status':status,'created_at':now_ts()}
  self.db.execute('INSERT INTO social_identity_candidates_204 VALUES(?,?,?,?,?,?,?,?,?)',(mid,case_id,dumps(account_ids),dumps(payload['masked_handles']),dumps(signals),score,status,payload['created_at'],_hash(payload)))
  return {**payload,'same_person_confirmed':False,'human_review_required':True}
 def synthesize_social_profile(self,*,case_id:str,account_ids:Sequence[str],question:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI SOCIAL PROFILE 204 {case_id} ZUSAMMENFUEHREN':raise PermissionError('explicit approval required')
  accounts=[dict(self.db.one('SELECT * FROM social_accounts_204 WHERE account_id=? AND case_id=?',(x,case_id))) for x in account_ids];accounts=[x for x in accounts if x]
  posts=[]
  for a in accounts:posts.extend(dict(r) for r in self.db.all('SELECT * FROM social_posts_204 WHERE account_id=? ORDER BY published_at',(a['account_id'],)))
  claims=[];topics={};timeline=[]
  for p in posts:
   for sent in re.split(r'(?<=[.!?])\s+',p['text']):
    if len(sent.strip())>=25:claims.append({'text':sent.strip()[:600],'source_ref':p['source_ref'],'status':'candidate'})
   for tok in _tokens(p['text']):topics[tok]=topics.get(tok,0)+1
   if p['published_at']:timeline.append({'at':p['published_at'],'type':'post','source_ref':p['source_ref']})
  hypotheses=[]
  for c in claims[:40]:hypotheses.append({'statement':c['text'],'support_refs':[c['source_ref']] if c['source_ref'] else [],'status':'working_hypothesis','test_plan':['independent source','account ownership check','timeline consistency check']})
  sid=new_id('socialprofile204');profile={'accounts':[{'source_id':a['source_id'],'handle':a['handle'],'profile':json.loads(a['profile_json']),'source_ref':a['source_ref']} for a in accounts],'top_topics':sorted(topics.items(),key=lambda x:(-x[1],x[0]))[:20],'timeline':sorted(timeline,key=lambda x:x['at'])}
  payload={'snapshot_id':sid,'case_id':case_id,'question':question,'profile':profile,'claims':claims[:100],'hypotheses':hypotheses[:30],'source_refs':sorted({a['source_ref'] for a in accounts if a['source_ref']}|{p['source_ref'] for p in posts if p['source_ref']}),'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_social_profiles_204 VALUES(?,?,?,?,?,?,?,?,?)',(sid,case_id,dumps(profile),dumps(payload['claims']),dumps(payload['hypotheses']),dumps(payload['source_refs']),question,payload['created_at'],_hash(payload)))
  return {**payload,'profile_is_candidate':True,'automatic_profile_merge':False,'human_review_required':True}
 def chat(self,*,case_id:str,snapshot_id:str,question:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI SOCIAL CHAT 204 {case_id} ANTWORTEN':raise PermissionError('explicit approval required')
  row=self.db.one('SELECT * FROM ai_social_profiles_204 WHERE snapshot_id=? AND case_id=?',(snapshot_id,case_id));
  if not row:raise KeyError(snapshot_id)
  hyps=json.loads(row['hypotheses_json']);refs=json.loads(row['source_refs_json']);qt=_tokens(question);ranked=sorted(hyps,key=lambda h:len(qt&_tokens(h['statement'])),reverse=True)[:5]
  answer='Die Social-Quellen ergeben folgende prüfbare Arbeitshypothesen: '+(' | '.join(h['statement'] for h in ranked) if ranked else 'keine ausreichend passende Hypothese.')
  tid=new_id('socialchat204');payload={'turn_id':tid,'case_id':case_id,'question':question,'answer':answer,'citations':[{'source_ref':r} for r in refs[:15]],'hypotheses':ranked,'warnings':['Accountgleichheit ist nicht automatisch bestätigt.'],'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_social_chat_turns_204 VALUES(?,?,?,?,?,?,?,?,?)',(tid,case_id,question,answer,dumps(payload['citations']),dumps(ranked),dumps(payload['warnings']),payload['created_at'],_hash(payload)))
  return {**payload,'co_investigator':True,'automatic_action':False,'human_review_required':True}
 def record_feedback(self,*,case_id:str,item_ref:str,verdict:str,reason:str,analyst:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI SOCIAL FEEDBACK 204 {case_id} SPEICHERN':raise PermissionError('explicit approval required')
  if verdict not in {'confirmed','rejected','needs_more_evidence','partially_correct'}:raise ValueError('invalid verdict')
  fid=new_id('socialfeedback204');payload={'feedback_id':fid,'case_id':case_id,'item_ref':item_ref,'verdict':verdict,'reason':reason,'analyst':analyst,'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_social_feedback_204 VALUES(?,?,?,?,?,?,?,?)',(fid,case_id,item_ref,verdict,reason,analyst,payload['created_at'],_hash(payload)))
  return {**payload,'used_for_local_calibration':True,'model_weights_changed_automatically':False}
 def validate_source(self,*,source_id:str,fixture_ok:bool,parser_ok:bool,live_ok:bool,terms_reviewed:bool,confirmation:str)->dict[str,Any]:
  if confirmation!=f'SOCIAL SOURCE 204 {source_id} VALIDIEREN':raise PermissionError('explicit approval required')
  row=self.db.one('SELECT * FROM social_source_profiles_204 WHERE source_id=?',(source_id,));
  if not row:raise KeyError(source_id)
  if row['access'] in ('guided_browser','credentialed_or_guided'):status='guided_ready' if terms_reviewed else 'blocked_terms'
  elif fixture_ok and parser_ok and live_ok and terms_reviewed:status='production_ready'
  elif fixture_ok and parser_ok and live_ok:status='live_validated'
  elif fixture_ok and parser_ok:status='fixture_validated'
  else:status='contract_validated'
  self.db.execute('UPDATE social_source_profiles_204 SET status=?,fixture_ok=?,parser_ok=?,live_ok=?,terms_reviewed=?,updated_at=? WHERE source_id=?',(status,int(fixture_ok),int(parser_ok),int(live_ok),int(terms_reviewed),now_ts(),source_id))
  return {'source_id':source_id,'status':status,'automatic_activation':False}
