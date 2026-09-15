from __future__ import annotations
import hashlib, html, io, json, re, zipfile
from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256((v if isinstance(v,bytes) else _canon(v).encode())).hexdigest()
def _tokens(s:str)->set[str]:return {x for x in re.findall(r"[\w\-]{2,}",str(s).lower(),re.UNICODE)}
def _inj(t:str)->bool:return bool(re.search(r'ignore previous instructions|reveal (?:the )?system prompt|bypass policy|execute this command',str(t),re.I))
def _strip_html(t:str)->str:
 t=re.sub(r'(?is)<(script|style|template).*?>.*?</\1>',' ',str(t));t=re.sub(r'(?s)<[^>]+>',' ',t);return re.sub(r'\s+',' ',html.unescape(t)).strip()
def _sentences(t:str)->list[str]:return [x.strip() for x in re.split(r'(?<=[.!?])\s+',t) if 20<=len(x.strip())<=800]
def _claims(t:str)->list[str]:
 verbs=r'\b(?:ist|war|wurde|hat|leitete|arbeitete|gehörte|sagte|berichtete|is|was|has|served|led|founded|reported|said)\b'
 return [s for s in _sentences(t) if re.search(verbs,s,re.I)][:60]
def _extract_docx(data:bytes)->str:
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  raw=z.read('word/document.xml').decode('utf-8','ignore')
 return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',raw))).strip()
def _extract_pdf(data:bytes)->list[tuple[int,str]]:
 try:
  from pypdf import PdfReader
  r=PdfReader(io.BytesIO(data));return [(i+1,(p.extract_text() or '').strip()) for i,p in enumerate(r.pages)]
 except Exception:
  try:
   from PyPDF2 import PdfReader
   r=PdfReader(io.BytesIO(data));return [(i+1,(p.extract_text() or '').strip()) for i,p in enumerate(r.pages)]
  except Exception:return []

class Build206CaseAIRetrieval2Service:
 BUILD='206.0'
 SOURCES=[
 ('pdf_text','PDF Text Layer','document_parser'),('docx_xml','DOCX XML','document_parser'),('html_local','HTML Local','document_parser'),('json_structured','JSON/API','structured_parser'),('csv_table','CSV/Table','table_parser'),('evidence_graph','Evidence Graph','case_store'),('timeline','Temporal Timeline','case_store'),('social_news','Social & News Fabric','case_store')]
 def __init__(self,db:Any,audit:Any,*,platform:Any,pilot_ai:Any,social:Any,news:Any,graph:Any,identity:Any,monitoring:Any,capture:Any,runtime:Any,workspace:Any,actor:str='system'):
  self.db,self.audit=db,audit;self.platform=platform;self.pilot_ai=pilot_ai;self.social=social;self.news=news;self.graph=graph;self.identity=identity;self.monitoring=monitoring;self.capture=capture;self.runtime=runtime;self.workspace=workspace;self.actor=actor
 def seed(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!='RETRIEVAL SOURCES 206 ANLEGEN':raise PermissionError('explicit approval required')
  t=now_ts()
  for sid,name,kind in self.SOURCES:
   self.db.execute('INSERT OR REPLACE INTO retrieval_source_profiles_206 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,name,kind,'production_ready','2.0',1,1,1,t,t,dumps({'local_only':True,'citation_required':True,'automatic_activation':False})))
  return {'sources':len(self.SOURCES),'production_ready':len(self.SOURCES),'local_processing':True}
 def ingest(self,*,case_id:str,source_id:str,source_ref:str,title:str,content:bytes|str,content_type:str,language:str='',pages:Sequence[Mapping[str,Any]]|None=None,tables:Sequence[Mapping[str,Any]]|None=None,access_label:str='case',confirmation:str)->dict[str,Any]:
  if confirmation!=f'RETRIEVAL INGEST 206 {case_id} SPEICHERN':raise PermissionError('explicit approval required')
  raw=content.encode() if isinstance(content,str) else bytes(content);page_items=[]
  if pages:page_items=[(int(x.get('page',i+1)),str(x.get('text',''))) for i,x in enumerate(pages)]
  elif 'pdf' in content_type.lower():page_items=_extract_pdf(raw)
  elif 'word' in content_type.lower() or title.lower().endswith('.docx'):page_items=[(1,_extract_docx(raw))]
  elif 'html' in content_type.lower():page_items=[(1,_strip_html(raw.decode('utf-8','ignore')))]
  elif 'json' in content_type.lower():
   try:page_items=[(1,json.dumps(json.loads(raw.decode('utf-8')),ensure_ascii=False,indent=2))]
   except Exception:page_items=[(1,raw.decode('utf-8','ignore'))]
  else:page_items=[(1,raw.decode('utf-8','ignore'))]
  if not any(t.strip() for _,t in page_items):raise ValueError('no extractable text; provide pages or a text-layer document')
  did=new_id('doc206');text_all='\n'.join(t for _,t in page_items);meta={'pages':len(page_items),'bytes':len(raw),'parser':source_id,'access_label':access_label}
  self.db.execute('INSERT INTO case_documents_206 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,case_id,source_id,source_ref,title,content_type,language,_hash(raw),int(_inj(text_all)),'candidate',now_ts(),dumps(meta)))
  chunk_ids=[]
  for page,text in page_items:
   paragraphs=[x.strip() for x in re.split(r'\n\s*\n|(?<=\.)\s+(?=[A-ZÄÖÜ])',text) if x.strip()]
   bucket='';idx=1
   for p in paragraphs or [text]:
    if len(bucket)+len(p)>1800 and bucket:
     cid=self._chunk(did,case_id,f'page:{page}:chunk:{idx}',page,'text',bucket,source_ref,access_label);chunk_ids.append(cid);idx+=1;bucket=''
    bucket=(bucket+' '+p).strip()
   if bucket:chunk_ids.append(self._chunk(did,case_id,f'page:{page}:chunk:{idx}',page,'text',bucket,source_ref,access_label))
  table_ids=[]
  for i,tab in enumerate(tables or []):
   tid=new_id('table206');cells=tab.get('cells',[]);payload={'table_id':tid,'cells':cells,'caption':tab.get('caption'),'page':tab.get('page')}
   self.db.execute('INSERT INTO case_tables_206 VALUES(?,?,?,?,?,?,?,?,?)',(tid,did,case_id,tab.get('page'),tab.get('caption'),dumps(cells),source_ref,now_ts(),_hash(payload)));table_ids.append(tid)
   flat=' | '.join(' ; '.join(map(str,row)) if isinstance(row,list) else str(row) for row in cells)
   if flat:chunk_ids.append(self._chunk(did,case_id,f'table:{i+1}',tab.get('page'),'table',flat,source_ref,access_label))
  return {'document_id':did,'chunks':chunk_ids,'tables':table_ids,'pages':len(page_items),'prompt_injection_candidate':_inj(text_all),'status':'candidate','external_uploads':False}
 def _chunk(self,did,case_id,ref,page,kind,text,source_ref,access_label):
  cid=new_id('chunk206');self.db.execute('INSERT INTO case_chunks_206 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,did,case_id,ref,page,kind,text,len(_tokens(text)),_hash(text),source_ref,access_label,now_ts()));return cid
 def retrieve(self,*,case_id:str,question:str,top_k:int=12,access_labels:Sequence[str]=('case',),confirmation:str)->dict[str,Any]:
  if confirmation!=f'RETRIEVAL QUERY 206 {case_id} AUSFUEHREN':raise PermissionError('explicit approval required')
  q=_tokens(question);rows=[dict(r) for r in self.db.all('SELECT * FROM case_chunks_206 WHERE case_id=?',(case_id,)) if r['access_label'] in set(access_labels)]
  scored=[]
  for r in rows:
   toks=_tokens(r['text']);score=len(q&toks)/(max(1,len(q))**.5*max(1,len(toks))**.25)
   if score>0:scored.append((score,r))
  results=[]
  for score,r in sorted(scored,key=lambda x:x[0],reverse=True)[:max(1,min(top_k,50))]:
   results.append({'chunk_id':r['chunk_id'],'document_id':r['document_id'],'section_ref':r['section_ref'],'page_number':r['page_number'],'text':r['text'],'source_ref':r['source_ref'],'score':round(score,4)})
  qid=new_id('query206');payload={'query_id':qid,'case_id':case_id,'question':question,'results':results,'filters':{'access_labels':list(access_labels)},'created_at':now_ts()}
  self.db.execute('INSERT INTO retrieval_queries_206 VALUES(?,?,?,?,?,?,?)',(qid,case_id,question,dumps(payload['filters']),dumps(results),payload['created_at'],_hash(payload)))
  return {**payload,'citation_required':True,'case_isolation':True}
 def social_network(self,*,case_id:str,account_ids:Sequence[str],confirmation:str)->dict[str,Any]:
  if confirmation!=f'SOCIAL NETWORK 206 {case_id} ERSTELLEN':raise PermissionError('explicit approval required')
  accounts=[];posts=[]
  for aid in account_ids:
   r=self.db.one('SELECT * FROM social_accounts_204 WHERE account_id=? AND case_id=?',(aid,case_id,));
   if r:accounts.append(dict(r));posts.extend(dict(x) for x in self.db.all('SELECT * FROM social_posts_204 WHERE account_id=? AND case_id=?',(aid,case_id)))
  edges=[];topics=Counter();activity=Counter();cit=[]
  for p in posts:
   for field,rel in [('reply_to','reply'),('repost_of','repost'),('quote_of','quote')]:
    if p.get(field):edges.append({'from':p['post_id'],'to':p[field],'type':rel})
   for tok in _tokens(p.get('text','')):
    if len(tok)>4:topics[tok]+=1
   if p.get('published_at'):activity[str(p['published_at'])[:10]]+=1
   cit.append({'source_ref':p.get('source_ref'),'post_id':p['post_id'],'account_id':p['account_id']})
  sid=new_id('socialnet206');payload={'snapshot_id':sid,'case_id':case_id,'account_ids':list(account_ids),'node_count':len(accounts)+len(posts),'edge_count':len(edges),'activity':dict(activity),'topics':topics.most_common(20),'citations':cit,'status':'candidate','created_at':now_ts()}
  self.db.execute('INSERT INTO social_network_snapshots_206 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,case_id,dumps(list(account_ids)),payload['node_count'],payload['edge_count'],dumps(payload['activity']),dumps(payload['topics']),dumps(cit),'candidate',payload['created_at'],_hash(payload)))
  return {**payload,'edges':edges,'coordination_confirmed':False,'same_person_confirmed':False}
 def synthesize(self,*,case_id:str,question:str,top_k:int=18,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI CASE CONTEXT 206 {case_id} ZUSAMMENFUEHREN':raise PermissionError('explicit approval required')
  ret=self.retrieve(case_id=case_id,question=question,top_k=top_k,confirmation=f'RETRIEVAL QUERY 206 {case_id} AUSFUEHREN')
  claim_map=defaultdict(list);cit=[]
  for r in ret['results']:
   cit.append({k:r[k] for k in ('source_ref','document_id','section_ref','page_number')})
   for c in _claims(r['text']):claim_map[c].append(r)
  hypotheses=[]
  for claim,rs in list(claim_map.items())[:40]:
   refs={x['source_ref'] for x in rs};hypotheses.append({'statement':claim,'status':'corroborated_candidate' if len(refs)>=2 else 'supported_candidate','source_count':len(refs),'citations':[{k:x[k] for k in ('source_ref','document_id','section_ref','page_number')} for x in rs],'verification_plan':['Primärquelle prüfen','Zeitraum und Identität abgleichen','Quellenunabhängigkeit prüfen']})
  conflicts=[]
  for a in hypotheses:
   for b in hypotheses:
    if a is b:continue
    if len(_tokens(a['statement'])&_tokens(b['statement']))>=4 and bool(re.search(r'\b(?:nicht|kein|denied|false|never)\b',a['statement'],re.I)) != bool(re.search(r'\b(?:nicht|kein|denied|false|never)\b',b['statement'],re.I)):
     conflicts.append({'left':a['statement'],'right':b['statement'],'status':'needs_review'})
  cid=new_id('context206');profile={'documents':len({x['document_id'] for x in ret['results']}),'chunks':len(ret['results']),'sources':len({x['source_ref'] for x in ret['results']})};payload={'context_id':cid,'case_id':case_id,'question':question,'profile':profile,'hypotheses':hypotheses,'conflicts':conflicts[:20],'citations':cit,'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_case_contexts_206 VALUES(?,?,?,?,?,?,?,?,?)',(cid,case_id,question,dumps(profile),dumps(hypotheses),dumps(conflicts[:20]),dumps(cit),payload['created_at'],_hash(payload)))
  return {**payload,'hypotheses_are_not_facts':True,'automatic_case_update':False,'co_investigator':True}
 def chat(self,*,case_id:str,context_id:str,question:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI CASE CHAT 206 {case_id} ANTWORTEN':raise PermissionError('explicit approval required')
  row=self.db.one('SELECT * FROM ai_case_contexts_206 WHERE context_id=? AND case_id=?',(context_id,case_id));
  if not row:raise KeyError(context_id)
  hs=json.loads(row['hypotheses_json']);qt=_tokens(question);ranked=sorted(hs,key=lambda h:len(qt&_tokens(h['statement'])),reverse=True)[:6];cit=[]
  for h in ranked:cit.extend(h.get('citations',[]))
  seen=set();cit=[x for x in cit if not ((x['source_ref'],x['section_ref']) in seen or seen.add((x['source_ref'],x['section_ref'])))]
  answer='Quellengebundene Arbeitshypothesen: '+(' | '.join(h['statement'] for h in ranked) if ranked else 'Im Fallindex wurde keine hinreichend passende Aussage gefunden.')
  tid=new_id('chat206');warnings=['Arbeitshypothesen sind keine Tatsachen.','Jede Aussage muss am zitierten Abschnitt geprüft werden.'];payload={'turn_id':tid,'case_id':case_id,'context_id':context_id,'question':question,'answer':answer,'citations':cit[:20],'warnings':warnings,'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_case_chat_turns_206 VALUES(?,?,?,?,?,?,?,?,?)',(tid,case_id,context_id,question,answer,dumps(payload['citations']),dumps(warnings),payload['created_at'],_hash(payload)))
  return {**payload,'automatic_action':False,'human_review_required':True,'invented_sources':False}
 def feedback(self,*,case_id:str,item_ref:str,verdict:str,reason:str,analyst:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI RETRIEVAL FEEDBACK 206 {case_id} SPEICHERN':raise PermissionError('explicit approval required')
  if verdict not in {'confirmed','rejected','needs_more_evidence','partially_correct'}:raise ValueError('invalid verdict')
  fid=new_id('feedback206');payload={'feedback_id':fid,'case_id':case_id,'item_ref':item_ref,'verdict':verdict,'reason':reason,'analyst':analyst,'created_at':now_ts()}
  self.db.execute('INSERT INTO ai_retrieval_feedback_206 VALUES(?,?,?,?,?,?,?,?)',(fid,case_id,item_ref,verdict,reason,analyst,payload['created_at'],_hash(payload)))
  return {**payload,'used_for_local_calibration':True,'model_weights_changed_automatically':False}
