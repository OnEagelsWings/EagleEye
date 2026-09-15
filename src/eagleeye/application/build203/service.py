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

class Build203GlobalCountryPacksIICoInvestigatorService:
 BUILD='203.0'
 PACKS={
 'MENA':[
 ('ae_open_data','AE Open Data','AE','structured_api','official','https://opendata.fcsc.gov.ae/api','open_data',['ar','en']),
 ('ae_national_economic_register','UAE National Economic Register','AE','guided_browser','official','https://ner.economy.ae/','company',['ar','en']),
 ('sa_open_data','Saudi Open Data','SA','structured_api','official','https://open.data.gov.sa/','open_data',['ar','en']),
 ('qa_open_data','Qatar Open Data','QA','guided_browser','official','https://www.data.gov.qa/','open_data',['ar','en']),
 ('jo_open_data','Jordan Open Data','JO','guided_browser','official','https://www.opendata.gov.jo/','open_data',['ar','en']),
 ('mena_aljazeera','Al Jazeera','QA','rss_or_browser','news','https://www.aljazeera.com/search/','news',['ar','en']),
 ('mena_alarabiya','Al Arabiya','AE','guided_browser','news','https://www.alarabiya.net/tools/search','news',['ar']),
 ('mena_the_national','The National','AE','guided_browser','news','https://www.thenationalnews.com/search/','news',['en'])],
 'RU':[
 ('ru_egrul','FNS EGRUL/EGRIP','RU','guided_browser','official','https://egrul.nalog.ru/','company',['ru']),
 ('ru_gov_publication','Official Legal Information','RU','guided_browser','official','http://publication.pravo.gov.ru/','law',['ru']),
 ('ru_duma','State Duma Open Data','RU','guided_browser','official','http://duma.gov.ru/','parliament',['ru']),
 ('ru_fedresurs','Fedresurs','RU','guided_browser','official','https://fedresurs.ru/','company',['ru']),
 ('ru_rsl','Russian State Library','RU','guided_browser','archive','https://search.rsl.ru/','archive',['ru']),
 ('ru_tass','TASS','RU','guided_browser','news','https://tass.com/search','news',['ru','en']),
 ('ru_meduza','Meduza','RU','guided_browser','news','https://meduza.io/search','news',['ru','en']),
 ('ru_novaya_europe','Novaya Gazeta Europe','RU','guided_browser','news','https://novayagazeta.eu/','news',['ru'])],
 'CNHK':[
 ('cn_gsxt','China GSXT','CN','guided_browser','official','https://www.gsxt.gov.cn/','company',['zh']),
 ('cn_credit_china','Credit China','CN','guided_browser','official','https://www.creditchina.gov.cn/','company',['zh']),
 ('cn_npc','National Peoples Congress','CN','guided_browser','official','http://www.npc.gov.cn/','parliament',['zh']),
 ('cn_court','China Judgments Online','CN','guided_browser','court','https://wenshu.court.gov.cn/','court',['zh']),
 ('hk_companies','Hong Kong Companies Registry','HK','guided_browser','official','https://www.cr.gov.hk/','company',['zh','en']),
 ('cn_xinhua','Xinhua','CN','guided_browser','news','https://english.news.cn/search.htm','news',['zh','en']),
 ('cn_globaltimes','Global Times','CN','guided_browser','news','https://www.globaltimes.cn/search','news',['zh','en']),
 ('hk_scmp','South China Morning Post','HK','guided_browser','news','https://www.scmp.com/search/','news',['en'])],
 'IN':[
 ('in_data_gov','data.gov.in','IN','credentialed_api','official','https://api.data.gov.in/','open_data',['en','hi']),
 ('in_mca','Ministry of Corporate Affairs','IN','guided_browser','official','https://www.mca.gov.in/','company',['en','hi']),
 ('in_parliament','Parliament of India','IN','guided_browser','official','https://sansad.in/','parliament',['en','hi']),
 ('in_ecourts','eCourts India','IN','guided_browser','court','https://services.ecourts.gov.in/','court',['en','hi']),
 ('in_national_archives','National Archives of India','IN','guided_browser','archive','https://www.abhilekh-patal.in/','archive',['en','hi']),
 ('in_the_hindu','The Hindu','IN','guided_browser','news','https://www.thehindu.com/search/','news',['en']),
 ('in_indianexpress','Indian Express','IN','guided_browser','news','https://indianexpress.com/?s=','news',['en']),
 ('in_ndtv','NDTV','IN','guided_browser','news','https://www.ndtv.com/search','news',['en','hi'])],
 'JP':[
 ('jp_e_stat','e-Stat Japan','JP','credentialed_api','official','https://api.e-stat.go.jp/rest/3.0/app/json','open_data',['ja','en']),
 ('jp_gbiz','gBizINFO','JP','structured_api','official','https://info.gbiz.go.jp/','company',['ja']),
 ('jp_diet','National Diet Library Search','JP','structured_api','authority','https://ndlsearch.ndl.go.jp/api','archive',['ja','en']),
 ('jp_courts','Courts in Japan','JP','guided_browser','court','https://www.courts.go.jp/','court',['ja']),
 ('jp_diet_parliament','National Diet','JP','guided_browser','official','https://www.shugiin.go.jp/','parliament',['ja']),
 ('jp_nhk','NHK','JP','guided_browser','news','https://www3.nhk.or.jp/news/','news',['ja']),
 ('jp_japantimes','Japan Times','JP','guided_browser','news','https://www.japantimes.co.jp/search/','news',['en']),
 ('jp_asahi','Asahi Shimbun','JP','guided_browser','news','https://www.asahi.com/ajw/search/','news',['ja','en'])],
 'LATAM':[
 ('br_dados','dados.gov.br','BR','structured_api','official','https://dados.gov.br/','open_data',['pt']),
 ('br_receita','Receita Federal CNPJ','BR','guided_browser','official','https://www.gov.br/receitafederal/','company',['pt']),
 ('mx_datos','datos.gob.mx','MX','structured_api','official','https://datos.gob.mx/','open_data',['es']),
 ('ar_datos','datos.gob.ar','AR','structured_api','official','https://datos.gob.ar/','open_data',['es']),
 ('cl_datos','datos.gob.cl','CL','guided_browser','official','https://datos.gob.cl/','open_data',['es']),
 ('latam_folha','Folha de S.Paulo','BR','guided_browser','news','https://search.folha.uol.com.br/','news',['pt']),
 ('latam_clarin','Clarín','AR','guided_browser','news','https://www.clarin.com/buscador/','news',['es']),
 ('latam_reforma','Reforma','MX','guided_browser','news','https://www.reforma.com/buscador/','news',['es'])]
 }
 def __init__(self,db:Any,audit:Any,*,runtime:Any,country_packs:Any,pilot_ai:Any,platform:Any,source_ai:Any,graph:Any,identity:Any,workspace:Any,actor:str='system'):
  self.db,self.audit=db,audit;self.runtime=runtime;self.country_packs=country_packs;self.pilot_ai=pilot_ai;self.platform=platform;self.source_ai=source_ai;self.graph=graph;self.identity=identity;self.workspace=workspace;self.actor=actor
 def seed(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!='COUNTRY PACKS 203 ANLEGEN':raise PermissionError('explicit approval required')
  created=now_ts();n=0
  for region,items in self.PACKS.items():
   for sid,name,country,access,klass,endpoint,domain,languages in items:
    status='guided_ready' if access in ('guided_browser','rss_or_browser') else 'contract_validated'
    p={'source_id':sid,'region':region,'country':country,'name':name,'access':access,'source_class':klass,'endpoint':endpoint,'domain':domain,'languages':languages,'status':status}
    self.db.execute('INSERT OR REPLACE INTO country_source_profiles_203 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,region,country,name,access,klass,endpoint,domain,dumps(languages),status,0,0,0,0,created,created,_hash(p)));n+=1
  return {'regions':len(self.PACKS),'sources':n,'structured_sources':sum(1 for xs in self.PACKS.values() for x in xs if x[3] in ('structured_api','credentialed_api')),'automatic_activation':False}
 def create_plan(self,*,case_id:str,question:str,regions:Sequence[str],person:Mapping[str,Any],mode:str='balanced',confirmation:str)->dict[str,Any]:
  if confirmation!=f'COUNTRY PLAN 203 {case_id} ANLEGEN':raise PermissionError('explicit approval required')
  clean=_clean(question);name=' '.join(str(person.get(k,'')).strip() for k in ('given_name','family_name') if person.get(k)).strip();query=_clean(f'{name} {clean}')
  rows=[]
  for region in regions:rows.extend(dict(r) for r in self.db.all('SELECT * FROM country_source_profiles_203 WHERE region=?',(region,)))
  ql=clean.lower()
  def rank(r:Mapping[str,Any]):
   s=50 if r['source_class'] in ('official','authority','court') else 20
   if r['domain']=='news' and any(w in ql for w in ('bericht','presse','medien','narrativ','news')):s+=45
   if r['domain']=='company' and any(w in ql for w in ('firma','unternehmen','organisation','geschäft')):s+=45
   if r['domain']=='parliament' and any(w in ql for w in ('politik','parlament','abgeordnet','regierung')):s+=45
   if r['domain']=='archive' and any(w in ql for w in ('histor','famil','geburt','archiv')):s+=45
   return (-s,r['region'],r['name'])
  rows=sorted({r['source_id']:r for r in rows}.values(),key=rank);tabs=[];jobs=[];ai_tasks=[]
  for r in rows:
   site=r['endpoint'].split('/')[2] if '//' in r['endpoint'] else r['endpoint']
   url=r['endpoint'] if r['access'] in ('guided_browser','rss_or_browser') else 'https://www.google.com/search?q='+quote_plus(f'site:{site} {query}')
   if len(tabs)<5:tabs.append({'source_id':r['source_id'],'title':r['name'],'url':url,'command':['firefox.exe','-new-tab',url],'existing_firefox_session':True})
   if r['access'] in ('structured_api','credentialed_api'):jobs.append({'source_id':r['source_id'],'query':query,'mode':mode,'candidate_only':True,'citation_required':True})
   ai_tasks.append({'source_id':r['source_id'],'task':'extract_compare_and_profile','question':clean,'language_hints':json.loads(r['languages_json']),'must_cite':True,'hypothesis_only':True})
  pid=new_id('countryplan203');payload={'plan_id':pid,'case_id':case_id,'question':clean,'regions':list(regions),'query':query,'tabs':tabs,'jobs':jobs,'ai_tasks':ai_tasks}
  self.db.execute('INSERT INTO country_search_plans_203 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,clean,dumps(list(regions)),dumps(dict(person)),mode,dumps(tabs),dumps(jobs),dumps(ai_tasks),now_ts(),_hash(payload)))
  return {**payload,'parallel_tabs':len(tabs),'tab_limit':5,'co_investigator_enabled':True,'sources_before_models':True,'automatic_identity_confirmation':False}
 def synthesize_profile(self,*,case_id:str,question:str,documents:Sequence[Mapping[str,Any]],confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI PROFILE 203 {case_id} ZUSAMMENFUEHREN':raise PermissionError('explicit approval required')
  claims=[];refs=[];conflicts=[];profile={'names':[],'organizations':[],'places':[],'roles':[],'dates':[],'accounts':[]}
  seen={k:set() for k in profile}
  for d in documents:
   ref=str(d.get('source_ref') or d.get('url') or d.get('document_id') or 'unknown');refs.append(ref);text=str(d.get('text') or d.get('summary') or '')
   for sent in re.split(r'(?<=[.!?])\s+',text):
    sent=sent.strip()
    if len(sent)>=20:claims.append({'text':sent[:600],'source_ref':ref,'status':'candidate'})
   for value in re.findall(r'\b[A-ZÄÖÜ][\wÄÖÜäöüß\-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß\-]+){1,3}\b',text):
    if value not in seen['names']:seen['names'].add(value);profile['names'].append({'value':value,'source_ref':ref,'status':'candidate'})
   for value in re.findall(r'\b(?:19|20)\d{2}\b',text):
    if value not in seen['dates']:seen['dates'].add(value);profile['dates'].append({'value':value,'source_ref':ref,'status':'candidate'})
  normalized={}
  for c in claims:
   key=' '.join(sorted(_tokens(c['text'])))[:220]
   normalized.setdefault(key,[]).append(c)
  hypotheses=[]
  for group in normalized.values():
   unique_refs=sorted({x['source_ref'] for x in group});statement=group[0]['text'];score=min(.88,.38+.15*len(unique_refs))
   hypotheses.append({'statement':statement,'support_refs':unique_refs,'confidence':score,'status':'working_hypothesis','test_plan':['independent primary source','timeline check','cross-script name check']})
  # crude contradiction marking for explicit negations around same tokens
  for i,a in enumerate(claims):
   for b in claims[i+1:]:
    overlap=len(_tokens(a['text'])&_tokens(b['text']))
    if overlap>=4 and ((' nicht ' in ' '+a['text'].lower()+' ') != (' nicht ' in ' '+b['text'].lower()+' ')):
     conflicts.append({'left':a,'right':b,'status':'needs_review'})
  sid=new_id('profile203');payload={'snapshot_id':sid,'case_id':case_id,'question':question,'profile':profile,'claims':claims[:100],'hypotheses':hypotheses[:20],'source_refs':sorted(set(refs)),'conflicts':conflicts[:20],'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_profile_snapshots_203 VALUES(?,?,?,?,?,?,?,?,?)',(sid,case_id,dumps(profile),dumps(payload['claims']),dumps(payload['hypotheses']),dumps(payload['source_refs']),dumps(payload['conflicts']),payload['created_at'],_hash(payload)))
  return {**payload,'hypotheses_are_not_facts':True,'human_review_required':True,'automatic_profile_update':False}
 def chat(self,*,case_id:str,question:str,snapshot_id:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI CHAT 203 {case_id} ANTWORTEN':raise PermissionError('explicit approval required')
  row=self.db.one('SELECT * FROM ai_profile_snapshots_203 WHERE snapshot_id=? AND case_id=?',(snapshot_id,case_id))
  if not row:raise KeyError(snapshot_id)
  hyps=json.loads(row['hypotheses_json']);claims=json.loads(row['claims_json']);refs=json.loads(row['source_refs_json']);warnings=[]
  qtok=_tokens(question);ranked=sorted(hyps,key=lambda h:len(qtok&_tokens(h['statement']))+h['confidence'],reverse=True)[:5]
  if not refs:warnings.append('Keine zitierfähige Quelle im Snapshot vorhanden.')
  answer='Auf Grundlage der fallbezogenen Quellen ergeben sich folgende prüfbare Arbeitshypothesen: '
  answer+=' | '.join(h['statement'] for h in ranked) if ranked else 'Der aktuelle Quellenstand reicht für keine belastbare Hypothese.'
  citations=[{'source_ref':r} for r in refs[:12]];tid=new_id('chat203');payload={'turn_id':tid,'case_id':case_id,'question':question,'answer':answer,'citations':citations,'hypotheses':ranked,'warnings':warnings,'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_chat_turns_203 VALUES(?,?,?,?,?,?,?,?,?)',(tid,case_id,question,answer,dumps(citations),dumps(ranked),dumps(warnings),payload['created_at'],_hash(payload)))
  return {**payload,'co_investigator':True,'citation_required':True,'automatic_action':False,'human_review_required':True}
 def record_feedback(self,*,case_id:str,item_type:str,item_ref:str,verdict:str,reason:str,analyst:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI FEEDBACK 203 {case_id} SPEICHERN':raise PermissionError('explicit approval required')
  if verdict not in {'confirmed','rejected','needs_more_evidence','partially_correct'}:raise ValueError('invalid verdict')
  fid=new_id('feedback203');p={'feedback_id':fid,'case_id':case_id,'item_type':item_type,'item_ref':item_ref,'verdict':verdict,'reason':reason,'analyst':analyst,'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_copilot_feedback_203 VALUES(?,?,?,?,?,?,?,?,?)',(fid,case_id,item_type,item_ref,verdict,reason,analyst,p['created_at'],_hash(p)))
  return {**p,'used_for_local_calibration':True,'model_weights_changed_automatically':False}
 def validate_source(self,*,source_id:str,fixture_ok:bool,parser_ok:bool,live_ok:bool,terms_reviewed:bool,confirmation:str)->dict[str,Any]:
  if confirmation!=f'COUNTRY SOURCE 203 {source_id} VALIDIEREN':raise PermissionError('explicit approval required')
  row=self.db.one('SELECT * FROM country_source_profiles_203 WHERE source_id=?',(source_id,));
  if not row:raise KeyError(source_id)
  if row['access'] in ('guided_browser','rss_or_browser'):status='guided_ready' if terms_reviewed else 'blocked_terms'
  elif fixture_ok and parser_ok and live_ok and terms_reviewed:status='production_ready'
  elif fixture_ok and parser_ok and live_ok:status='live_validated'
  elif fixture_ok and parser_ok:status='fixture_validated'
  else:status='contract_validated'
  self.db.execute('UPDATE country_source_profiles_203 SET status=?,fixture_ok=?,parser_ok=?,live_ok=?,terms_reviewed=?,updated_at=? WHERE source_id=?',(status,int(fixture_ok),int(parser_ok),int(live_ok),int(terms_reviewed),now_ts(),source_id))
  return {'source_id':source_id,'status':status,'automatic_activation':False}
