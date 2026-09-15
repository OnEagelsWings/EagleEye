from __future__ import annotations
import hashlib,json,re
from collections import Counter,defaultdict
from typing import Any,Mapping,Sequence
from urllib.parse import quote_plus,urlsplit,urlunsplit,parse_qsl,urlencode
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
def _tokens(s:str)->set[str]:return {x for x in re.findall(r"[\w\-]{3,}",str(s).lower(),re.UNICODE)}
def _clean(s:str)->str:
 s=re.sub(r'(?<!\d)\b(?:0[\.,]\d+|1[\.,]0+)\b',' ',str(s));return re.sub(r'\s+',' ',s.replace(';',' ')).strip()
def _redact_url(u:str)->str:
 p=urlsplit(str(u));sensitive={'token','api_key','apikey','key','secret','session','auth'}
 q=[(k,'[REDACTED]' if k.lower() in sensitive else v) for k,v in parse_qsl(p.query,keep_blank_values=True)]
 return urlunsplit((p.scheme,p.netloc,p.path,urlencode(q),p.fragment))
def _inj(t:str)->bool:return bool(re.search(r'ignore previous instructions|reveal (?:the )?system prompt|bypass policy|execute this command',str(t),re.I))
def _claim_sentences(text:str)->list[str]:
 out=[]
 for s in re.split(r'(?<=[.!?])\s+',str(text)):
  s=s.strip()
  if 25<=len(s)<=600 and re.search(r'\b(?:ist|war|wurde|hat|sagte|berichtete|arbeitet|leitete|gehörte|founded|served|said|reported|is|was|has)\b',s,re.I):out.append(s)
 return out[:40]
def _wire_fp(title:str,text:str)->str:
 toks=sorted(_tokens(title+' '+text[:1200]))
 return hashlib.sha256(' '.join(toks).encode()).hexdigest()[:24]

class Build205NewsIntelligenceFabricService:
 BUILD='205.0'
 SOURCES=[
 ('gdelt_doc','GDELT DOC','GLOBAL','multi','public_api','https://api.gdeltproject.org/api/v2/doc/doc','aggregator'),
 ('mediacloud','Media Cloud','GLOBAL','multi','credentialed_api','https://api.mediacloud.org/api/v2','aggregator'),
 ('newsapi','NewsAPI','GLOBAL','multi','credentialed_api','https://newsapi.org/v2/everything','aggregator'),
 ('event_registry','Event Registry','GLOBAL','multi','credentialed_api','https://eventregistry.org/api/v1/article/getArticles','aggregator'),
 ('tagesschau','Tagesschau','DE','de','rss_or_browser','https://www.tagesschau.de/infoservices/alle-meldungen-100.html','public_service'),
 ('spiegel','Der Spiegel','DE','de','guided_browser','https://www.spiegel.de/suche/?suchbegriff=','publisher'),
 ('faz','Frankfurter Allgemeine','DE','de','guided_browser','https://www.faz.net/suche/','publisher'),
 ('bbc','BBC News','GB','en','rss_or_browser','https://www.bbc.co.uk/search?q=','public_service'),
 ('guardian','The Guardian','GB','en','public_api','https://content.guardianapis.com/search','publisher'),
 ('ap','Associated Press','US','en','guided_browser','https://apnews.com/search?q=','wire'),
 ('npr','NPR','US','en','rss_or_browser','https://www.npr.org/search?query=','public_service'),
 ('nyt','New York Times','US','en','credentialed_api','https://api.nytimes.com/svc/search/v2/articlesearch.json','publisher'),
 ('kan','KAN News','IL','he','rss_or_browser','https://www.kan.org.il/search/?q=','public_service'),
 ('haaretz','Haaretz','IL','he','guided_browser','https://www.haaretz.co.il/search?q=','publisher'),
 ('ynet','Ynet','IL','he','guided_browser','https://www.ynet.co.il/search?query=','publisher'),
 ('aljazeera','Al Jazeera','QA','ar','rss_or_browser','https://www.aljazeera.net/search/','publisher'),
 ('alarabiya','Al Arabiya','AE','ar','guided_browser','https://www.alarabiya.net/tools/search?query=','publisher'),
 ('tass','TASS','RU','ru','guided_browser','https://tass.ru/search?searchStr=','state_media'),
 ('meduza','Meduza','LV','ru','guided_browser','https://meduza.io/search?query=','independent_media'),
 ('xinhua','Xinhua','CN','zh','guided_browser','https://search.news.cn/','state_media'),
 ('scmp','South China Morning Post','HK','en','guided_browser','https://www.scmp.com/search/','publisher'),
 ('the_hindu','The Hindu','IN','en','guided_browser','https://www.thehindu.com/search/?q=','publisher'),
 ('nhk','NHK World','JP','en','guided_browser','https://www3.nhk.or.jp/nhkworld/en/search/?q=','public_service'),
 ('folha','Folha de S.Paulo','BR','pt','guided_browser','https://search.folha.uol.com.br/?q=','publisher')]
 def __init__(self,db:Any,audit:Any,*,runtime:Any,social:Any,source_ai:Any,media:Any,platform:Any,graph:Any,monitoring:Any,workspace:Any,actor:str='system'):
  self.db,self.audit=db,audit;self.runtime=runtime;self.social=social;self.source_ai=source_ai;self.media=media;self.platform=platform;self.graph=graph;self.monitoring=monitoring;self.workspace=workspace;self.actor=actor
 def seed(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!='NEWS SOURCES 205 ANLEGEN':raise PermissionError('explicit approval required')
  t=now_ts()
  for sid,name,country,lang,access,endpoint,cls in self.SOURCES:
   p={'source_id':sid,'name':name,'country':country,'language':lang,'access':access,'endpoint':endpoint,'source_class':cls}
   self.db.execute('INSERT OR REPLACE INTO news_source_profiles_205 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,name,country,lang,access,endpoint,cls,'documented',0,0,0,0,t,t,_hash(p),dumps({'copyright_safe':True,'full_text_export':False,'automatic_activation':False})))
  return {'sources':len(self.SOURCES),'countries':len({x[2] for x in self.SOURCES}),'automatic_activation':False}
 def create_plan(self,*,case_id:str,question:str,countries:Sequence[str],languages:Sequence[str],confirmation:str)->dict[str,Any]:
  if confirmation!=f'NEWS PLAN 205 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
  q=_clean(question);rows=[dict(r) for r in self.db.all('SELECT * FROM news_source_profiles_205')]
  cs={str(x).upper() for x in countries};ls={str(x).lower() for x in languages}
  def score(r):
   s=40
   if r['country'] in cs:s+=35
   if r['country']=='GLOBAL':s+=22
   if r['language'].lower() in ls or r['language']=='multi':s+=18
   if r['status']=='production_active':s+=40
   if r['source_class'] in ('wire','public_service','aggregator'):s+=10
   return -s,r['name']
  rows=sorted(rows,key=score);tabs=[];jobs=[]
  for r in rows:
   if r['source_id']=='gdelt_doc':url='https://api.gdeltproject.org/api/v2/doc/doc?query='+quote_plus(q)+'&mode=artlist&format=html'
   elif r['source_id']=='guardian':url='https://www.theguardian.com/search?q='+quote_plus(q)
   elif r['source_id']=='tagesschau':url='https://www.google.com/search?q='+quote_plus('site:tagesschau.de '+q)
   else:url=r['endpoint']+quote_plus(q)
   if len(tabs)<5:tabs.append({'source_id':r['source_id'],'title':r['name'],'url':url,'command':['firefox.exe','-new-tab',url],'existing_firefox_session':True})
   if 'api' in r['access']:jobs.append({'source_id':r['source_id'],'query':q,'mode':'fast_discovery','citation_required':True,'candidate_only':True})
  pid=new_id('newsplan205');payload={'plan_id':pid,'case_id':case_id,'question':q,'countries':list(cs),'languages':list(ls),'tabs':tabs,'jobs':jobs,'created_at':now_ts()}
  self.db.execute('INSERT INTO news_search_plans_205 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,q,dumps(list(cs)),dumps(list(ls)),dumps(tabs),dumps(jobs),payload['created_at'],_hash(payload),'candidate_only'))
  return {**payload,'parallel_tabs':len(tabs),'news_social_fusion':True,'automatic_action':False}
 def record_article(self,*,case_id:str,source_id:str,title:str,url:str,text:str,published_at:str|None=None,language:str='',country:str='',article_type:str='news_report',entities:Sequence[Mapping[str,Any]]|None=None,confirmation:str)->dict[str,Any]:
  if confirmation!=f'NEWS ARTICLE 205 {case_id} SPEICHERN':raise PermissionError('explicit approval required')
  if article_type not in {'news_report','analysis','opinion','editorial','interview','press_release','fact_check'}:raise ValueError('invalid article type')
  aid=new_id('article205');clean_text=str(text)[:50000];claims=_claim_sentences(clean_text);safe_url=_redact_url(url);fp=_wire_fp(title,clean_text);inj=_inj(clean_text)
  payload={'article_id':aid,'case_id':case_id,'source_id':source_id,'title':title,'url':safe_url,'published_at':published_at,'language':language,'country':country,'article_type':article_type,'claims':claims,'entities':list(entities or []),'wire_fingerprint':fp,'source_ref':safe_url,'status':'candidate','prompt_injection':inj}
  self.db.execute('INSERT INTO news_articles_205 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,source_id,title,safe_url,published_at,language,country,article_type,clean_text,dumps(claims),dumps(list(entities or [])),fp,safe_url,'candidate',int(inj),_hash(payload),now_ts()))
  return {**payload,'untrusted_content_is_data':True,'copyright_safe_summary_only':True}
 def cluster_events(self,*,case_id:str,article_ids:Sequence[str],label:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'NEWS CLUSTER 205 {case_id} ERSTELLEN':raise PermissionError('explicit approval required')
  rows=[dict(self.db.one('SELECT * FROM news_articles_205 WHERE article_id=? AND case_id=?',(x,case_id))) for x in article_ids];rows=[x for x in rows if x]
  if len(rows)<2:raise ValueError('at least two articles required')
  groups=defaultdict(list)
  for r in rows:groups[r['wire_fingerprint']].append(r)
  independent=sum(1 for g in groups.values() if g)
  claims=Counter()
  for r in rows:
   for c in json.loads(r['claims_json']):claims[c]+=1
  cid=new_id('cluster205');status='multi_source_candidate' if independent>=2 else 'syndicated_candidate';payload={'cluster_id':cid,'case_id':case_id,'label':label,'article_ids':list(article_ids),'claims':[{'claim':c,'mentions':n} for c,n in claims.most_common(30)],'countries':sorted({r['country'] for r in rows if r['country']}),'languages':sorted({r['language'] for r in rows if r['language']}),'independent_lines':independent,'wire_groups':len(groups),'status':status,'created_at':now_ts()}
  self.db.execute('INSERT INTO news_event_clusters_205 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,case_id,label,dumps(article_ids),dumps(payload['claims']),dumps(payload['countries']),dumps(payload['languages']),independent,len(groups),status,payload['created_at'],_hash(payload)))
  return {**payload,'shared_wire_copy_counted_once':True}
 def link_social(self,*,case_id:str,cluster_id:str,social_post_ids:Sequence[str],confirmation:str)->dict[str,Any]:
  if confirmation!=f'NEWS SOCIAL 205 {case_id} VERKNUEPFEN':raise PermissionError('explicit approval required')
  cluster=self.db.one('SELECT * FROM news_event_clusters_205 WHERE cluster_id=? AND case_id=?',(cluster_id,case_id));
  if not cluster:raise KeyError(cluster_id)
  posts=[dict(self.db.one('SELECT * FROM social_posts_204 WHERE post_id=? AND case_id=?',(x,case_id))) for x in social_post_ids];posts=[p for p in posts if p]
  article_claims=' '.join(x['claim'] for x in json.loads(cluster['claims_json']));signals=[]
  for p in posts:
   overlap=len(_tokens(article_claims)&_tokens(p['text']))/max(1,len(_tokens(article_claims)|_tokens(p['text'])))
   if overlap>.08:signals.append({'post_id':p['post_id'],'type':'content_overlap','score':round(overlap,3),'source_ref':p.get('source_ref')})
  status='propagation_candidate' if signals else 'unlinked_candidate';lid=new_id('newssocial205');payload={'link_id':lid,'case_id':case_id,'cluster_id':cluster_id,'social_post_ids':list(social_post_ids),'signals':signals,'status':status,'created_at':now_ts()}
  self.db.execute('INSERT INTO news_social_links_205 VALUES(?,?,?,?,?,?,?,?)',(lid,case_id,cluster_id,dumps(social_post_ids),dumps(signals),status,payload['created_at'],_hash(payload)))
  return {**payload,'coordination_confirmed':False,'human_review_required':True}
 def synthesize(self,*,case_id:str,question:str,cluster_ids:Sequence[str],confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI NEWS PROFILE 205 {case_id} ZUSAMMENFUEHREN':raise PermissionError('explicit approval required')
  clusters=[dict(self.db.one('SELECT * FROM news_event_clusters_205 WHERE cluster_id=? AND case_id=?',(x,case_id))) for x in cluster_ids];clusters=[c for c in clusters if c]
  if not clusters:raise ValueError('clusters required')
  hypotheses=[];conflicts=[];citations=[]
  claim_map=defaultdict(list)
  for c in clusters:
   for item in json.loads(c['claims_json']):claim_map[item['claim']].append(c)
   for aid in json.loads(c['article_ids_json']):
    r=self.db.one('SELECT source_ref,source_id,article_type FROM news_articles_205 WHERE article_id=?',(aid,));
    if r:citations.append({'article_id':aid,'source_ref':r['source_ref'],'source_id':r['source_id'],'article_type':r['article_type']})
  for claim,cs in list(claim_map.items())[:50]:
   independent=max(c['independent_lines'] for c in cs);hypotheses.append({'statement':claim,'status':'corroborated_candidate' if independent>=2 else 'supported_candidate','independent_lines':independent,'verification_plan':['Primärquelle prüfen','Agenturabhängigkeit prüfen','Zeitpunkt und Kontext vergleichen'],'source_cluster_ids':[c['cluster_id'] for c in cs]})
  neg=[h for h in hypotheses if re.search(r'\b(?:nicht|kein|denied|false)\b',h['statement'],re.I)]
  pos=[h for h in hypotheses if h not in neg]
  for a in pos:
   for b in neg:
    if len(_tokens(a['statement'])&_tokens(b['statement']))>=3:conflicts.append({'left':a['statement'],'right':b['statement'],'status':'needs_review'})
  sid=new_id('ainews205');profile={'cluster_count':len(clusters),'countries':sorted({x for c in clusters for x in json.loads(c['countries_json'])}),'languages':sorted({x for c in clusters for x in json.loads(c['languages_json'])}),'independent_source_lines':sum(c['independent_lines'] for c in clusters)};payload={'snapshot_id':sid,'case_id':case_id,'question':question,'profile':profile,'hypotheses':hypotheses,'conflicts':conflicts,'citations':citations,'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_news_profiles_205 VALUES(?,?,?,?,?,?,?,?,?)',(sid,case_id,question,dumps(profile),dumps(hypotheses),dumps(conflicts),dumps(citations),payload['created_at'],_hash(payload)))
  return {**payload,'co_investigator':True,'hypotheses_are_not_facts':True,'automatic_profile_update':False}
 def chat(self,*,case_id:str,snapshot_id:str,question:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI NEWS CHAT 205 {case_id} ANTWORTEN':raise PermissionError('explicit approval required')
  row=self.db.one('SELECT * FROM ai_news_profiles_205 WHERE snapshot_id=? AND case_id=?',(snapshot_id,case_id));
  if not row:raise KeyError(snapshot_id)
  hyps=json.loads(row['hypotheses_json']);conf=json.loads(row['conflicts_json']);cit=json.loads(row['citations_json']);qt=_tokens(question);ranked=sorted(hyps,key=lambda h:len(qt&_tokens(h['statement'])),reverse=True)[:6]
  answer='Quellengebundene Arbeitshypothesen: '+(' | '.join(h['statement'] for h in ranked) if ranked else 'keine passende Hypothese.')
  if conf:answer+=' Es bestehen widersprüchliche Darstellungen, die manuell geprüft werden müssen.'
  tid=new_id('ainewschat205');warnings=['Nachrichtenberichte sind nicht automatisch Primärbelege.','Geteilte Agenturtexte zählen nur als eine Quellenlinie.'];payload={'turn_id':tid,'case_id':case_id,'snapshot_id':snapshot_id,'question':question,'answer':answer,'citations':cit[:20],'warnings':warnings,'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_news_chat_turns_205 VALUES(?,?,?,?,?,?,?,?,?)',(tid,case_id,snapshot_id,question,answer,dumps(payload['citations']),dumps(warnings),payload['created_at'],_hash(payload)))
  return {**payload,'automatic_action':False,'human_review_required':True}
 def record_feedback(self,*,case_id:str,item_ref:str,verdict:str,reason:str,analyst:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI NEWS FEEDBACK 205 {case_id} SPEICHERN':raise PermissionError('explicit approval required')
  if verdict not in {'confirmed','rejected','needs_more_evidence','partially_correct'}:raise ValueError('invalid verdict')
  fid=new_id('ainewsfeedback205');payload={'feedback_id':fid,'case_id':case_id,'item_ref':item_ref,'verdict':verdict,'reason':reason,'analyst':analyst,'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_news_feedback_205 VALUES(?,?,?,?,?,?,?,?)',(fid,case_id,item_ref,verdict,reason,analyst,payload['created_at'],_hash(payload)))
  return {**payload,'used_for_local_calibration':True,'model_weights_changed_automatically':False}
 def validate_source(self,*,source_id:str,fixture_ok:bool,parser_ok:bool,live_ok:bool,terms_reviewed:bool,confirmation:str)->dict[str,Any]:
  if confirmation!=f'NEWS SOURCE 205 {source_id} VALIDIEREN':raise PermissionError('explicit approval required')
  r=self.db.one('SELECT * FROM news_source_profiles_205 WHERE source_id=?',(source_id,));
  if not r:raise KeyError(source_id)
  if 'api' in r['access'] and all((fixture_ok,parser_ok,live_ok,terms_reviewed)):status='production_ready'
  elif 'api' in r['access'] and fixture_ok and parser_ok and live_ok:status='live_validated'
  elif fixture_ok and parser_ok:status='fixture_validated'
  else:status='guided_ready' if 'browser' in r['access'] or 'rss' in r['access'] else 'contract_validated'
  self.db.execute('UPDATE news_source_profiles_205 SET status=?,fixture_ok=?,parser_ok=?,live_ok=?,terms_reviewed=?,updated_at=? WHERE source_id=?',(status,int(fixture_ok),int(parser_ok),int(live_ok),int(terms_reviewed),now_ts(),source_id))
  return {'source_id':source_id,'status':status,'automatic_activation':False}
