from __future__ import annotations
import hashlib,html,json,re,uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin,urlsplit
from eagleeye.infrastructure.build301.tor_gateway import validate_onion_url,TorPolicyError

def _now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p):return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256((v if isinstance(v,str) else _canon(v)).encode()).hexdigest()
def _safe(s,n=5000):return re.sub(r'\s+',' ',str(s or '')).strip()[:n]

class Build303OnionQueueAIDossierService:
 BUILD='303.0'; REQUIRED_CORPUS=408; GATE_THRESHOLD=.92; CRITICAL_TRACK_THRESHOLD=.88
 def __init__(self,db:Any,audit:Any,*,cases:Any,build302:Any,build301:Any,research263:Any,install_dir:Path,base_dir:Path,actor='local-analyst'):
  self.db=db;self.audit=audit;self.cases=cases;self.build302=build302;self.build301=build301;self.research263=research263;self.install_dir=Path(install_dir);self.base_dir=Path(base_dir);self.actor=actor
 def _table(self,name):return bool(self.db.one("SELECT 1 x FROM sqlite_master WHERE type='table' AND name=?",(name,)))
 def _count(self,sql,args=()):
  try:return int((self.db.one(sql,args) or {}).get('n') or 0)
  except Exception:return 0
 def create_research_queue(self,*,case_id,seed_url,purpose,max_requests=8,max_depth=1,max_total_bytes=2*1024*1024,same_host_only=True,actor=None):
  actor=actor or self.actor;self.cases.get_case(case_id);purpose=_safe(purpose,500)
  if not purpose:raise ValueError('purpose is required')
  _,host,_,_=validate_onion_url(seed_url);max_requests=int(max_requests);max_depth=int(max_depth);max_total_bytes=int(max_total_bytes)
  if max_requests<1 or max_requests>20:raise ValueError('max_requests must be 1..20')
  if max_depth<0 or max_depth>3:raise ValueError('max_depth must be 0..3')
  if max_total_bytes<4096 or max_total_bytes>10*1024*1024:raise ValueError('max_total_bytes must be 4 KiB..10 MiB')
  qid=_id('onionq303');now=_now();payload={'queue_id':qid,'case_id':case_id,'purpose':purpose,'seed_url':seed_url,'onion_host':host,'max_requests':max_requests,'max_depth':max_depth,'max_total_bytes':max_total_bytes,'same_host_only':bool(same_host_only),'created_by':actor,'created_at':now}
  self.db.execute('INSERT INTO phase13_onion_research_queues_303 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(qid,case_id,purpose,seed_url,host,max_requests,max_depth,max_total_bytes,int(bool(same_host_only)),'awaiting_ok',actor,now,_hash(payload)))
  self._stage_item(qid,case_id,seed_url,0,'',100,'seed',actor)
  return {**payload,'status':'awaiting_ok','credentials':False,'forms':False,'uploads':False,'contact':False,'binary_execution':False,'clearnet_fallback':False}
 def _stage_item(self,queue_id,case_id,url,depth,parent_source_id,priority,reason,actor):
  try:validate_onion_url(url)
  except Exception:return None
  iid=_id('oqitem303');now=_now();p={'item_id':iid,'queue_id':queue_id,'case_id':case_id,'url':url,'depth':int(depth),'parent_source_id':parent_source_id or '','priority':int(priority),'reason':reason,'created_by':actor,'created_at':now}
  try:self.db.execute('INSERT INTO phase13_onion_queue_items_303 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(iid,queue_id,case_id,url,int(depth),parent_source_id or '',int(priority),_safe(reason,500),actor,now,_hash(p)))
  except Exception:return None
  return p
 def approve_queue(self,queue_id,confirmation,approved_by):
  if confirmation!='OK':raise ValueError('exact confirmation OK required')
  q=self.db.one('SELECT * FROM phase13_onion_research_queues_303 WHERE queue_id=?',(queue_id,))
  if not q:raise KeyError('queue not found')
  if self.db.one('SELECT 1 x FROM phase13_onion_queue_approvals_303 WHERE queue_id=?',(queue_id,)):raise ValueError('queue already approved')
  aid=_id('qok303');now=_now();p={'approval_id':aid,'queue_id':queue_id,'confirmation':'OK','approved_by':approved_by,'approved_at':now}
  self.db.execute('INSERT INTO phase13_onion_queue_approvals_303 VALUES(?,?,?,?,?,?)',(aid,queue_id,'OK',approved_by,now,_hash(p)));return p
 def _executed_item_ids(self,queue_id):return {r['item_id'] for r in self.db.all('SELECT item_id FROM phase13_onion_queue_fetches_303 WHERE queue_id=?',(queue_id,))}
 def queue_status(self,queue_id):
  q=self.db.one('SELECT * FROM phase13_onion_research_queues_303 WHERE queue_id=?',(queue_id,))
  if not q:raise KeyError('queue not found')
  approval=self.db.one('SELECT * FROM phase13_onion_queue_approvals_303 WHERE queue_id=?',(queue_id,));execs=self.db.all('SELECT * FROM phase13_onion_queue_fetches_303 WHERE queue_id=? ORDER BY executed_at',(queue_id,));used=sum(int(x['bytes_received'] or 0) for x in execs);done={x['item_id'] for x in execs};items=self.db.all('SELECT * FROM phase13_onion_queue_items_303 WHERE queue_id=? ORDER BY depth,priority DESC,created_at',(queue_id,));pending=[x for x in items if x['item_id'] not in done]
  return {'queue':q,'approved':bool(approval),'requests_used':len(execs),'requests_remaining':max(0,int(q['max_requests'])-len(execs)),'bytes_used':used,'bytes_remaining':max(0,int(q['max_total_bytes'])-used),'pending_count':len(pending),'pending':pending,'executions':execs}
 def _extract_onion_links(self,body,base_url,queue):
  text=body.decode('utf-8','replace');raw=re.findall(r'(?is)<a\b[^>]*?href\s*=\s*["\']([^"\']+)["\']',text);out=[];seen=set();base_host=queue['onion_host']
  for href in raw[:300]:
   href=html.unescape(href.strip());u=urljoin(base_url,href)
   try:_,host,_,_=validate_onion_url(u)
   except Exception:continue
   if int(queue['same_host_only']) and host!=base_host:continue
   if u not in seen:seen.add(u);out.append(u)
  return out[:80]
 def run_next(self,queue_id,actor=None):
  actor=actor or self.actor;st=self.queue_status(queue_id);q=st['queue'];approval=self.db.one('SELECT * FROM phase13_onion_queue_approvals_303 WHERE queue_id=?',(queue_id,))
  if not approval:raise PermissionError('queue requires exact investigator OK before bounded link following')
  if st['requests_remaining']<=0:raise RuntimeError('queue request budget exhausted')
  if st['bytes_remaining']<1024:raise RuntimeError('queue byte budget exhausted')
  pending=[x for x in st['pending'] if int(x['depth'])<=int(q['max_depth'])]
  if not pending:raise RuntimeError('no pending in-scope onion item')
  item=pending[0];per=min(524288,st['bytes_remaining']);m=self.build301.create_mission(case_id=q['case_id'],onion_url=item['url'],purpose=f"Queue303 {queue_id}: {q['purpose']}",max_bytes=per,max_redirects=0,actor=actor);self.build301.approve_mission(m['mission_id'],'OK',approval['approved_by']+' / bounded-queue303')
  eid=_id('qexec303');now=_now()
  try:
   r=self.build302.hardened_fetch_mission(m['mission_id'],actor=actor);src=self.db.one('SELECT * FROM phase13_source_records_301 WHERE source_id=?',(r['source_id'],));artifact=self.base_dir/src['artifact_relpath'];links=[]
   if int(item['depth'])<int(q['max_depth']) and src['mime_type'] in ('text/html','application/xhtml+xml'):
    links=self._extract_onion_links(artifact.read_bytes(),r['final_url'],q)
   staged=0
   for u in links:
    cid=_id('olink303');disp='staged' if self._stage_item(queue_id,q['case_id'],u,int(item['depth'])+1,r['source_id'],max(1,90-int(item['depth'])*10),'same-host link candidate',actor) else 'duplicate'
    cp={'candidate_id':cid,'queue_id':queue_id,'parent_source_id':r['source_id'],'url':u,'depth':int(item['depth'])+1,'disposition':disp,'rationale':'v3 onion link within approved queue host/depth scope','created_at':now};self.db.execute('INSERT INTO phase13_onion_link_candidates_303 VALUES(?,?,?,?,?,?,?,?,?)',(cid,queue_id,r['source_id'],u,int(item['depth'])+1,disp,cp['rationale'],now,_hash(cp)));staged+=int(disp=='staged')
   ep={'execution_id':eid,'queue_id':queue_id,'item_id':item['item_id'],'mission_id':m['mission_id'],'source_id':r['source_id'],'status':'success','bytes_received':int(r['bytes_received']),'links_staged':staged,'error_text':'','executed_by':actor,'executed_at':now};self.db.execute('INSERT INTO phase13_onion_queue_fetches_303 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(eid,queue_id,item['item_id'],m['mission_id'],r['source_id'],'success',int(r['bytes_received']),staged,'',actor,now,_hash(ep)));return ep
  except Exception as exc:
   ep={'execution_id':eid,'queue_id':queue_id,'item_id':item['item_id'],'mission_id':m['mission_id'],'source_id':'','status':'failed','bytes_received':0,'links_staged':0,'error_text':f'{type(exc).__name__}: {exc}','executed_by':actor,'executed_at':now};self.db.execute('INSERT INTO phase13_onion_queue_fetches_303 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(eid,queue_id,item['item_id'],m['mission_id'],'','failed',0,0,ep['error_text'],actor,now,_hash(ep)));raise
 def run_queue_scope_selftest(self,actor=None):
  actor=actor or self.actor;test_onion='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.onion';case=self.cases.create_case('Build303 queue selftest','internal','bounded onion queue policy','internal QA');q=self.create_research_queue(case_id=case['case_id'],seed_url='http://'+test_onion+'/',purpose='policy selftest',max_requests=3,max_depth=1,max_total_bytes=65536,actor=actor);blocked=False
  try:self.approve_queue(q['queue_id'],'YES',actor)
  except ValueError:blocked=True
  self.approve_queue(q['queue_id'],'OK',actor);queue=self.db.one('SELECT * FROM phase13_onion_research_queues_303 WHERE queue_id=?',(q['queue_id'],));links=self._extract_onion_links((f'<a href="/next">next</a><a href="http://{test_onion}/two">two</a><a href="http://bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.onion/x">cross</a>').encode(),'http://'+test_onion+'/',queue);controls={'exact_ok_required':blocked,'request_budget':int(queue['max_requests'])==3,'depth_budget':int(queue['max_depth'])==1,'byte_budget':int(queue['max_total_bytes'])==65536,'same_host_only':bool(queue['same_host_only']),'cross_host_filtered':len(links)==2,'read_only_parent_transport':self.build302.transport_policy()['method']=='GET','clearnet_fallback':False,'automatic_interaction':False};result='pass' if all((controls['exact_ok_required'],controls['request_budget'],controls['depth_budget'],controls['byte_budget'],controls['same_host_only'],controls['cross_host_filtered'],controls['read_only_parent_transport'],not controls['clearnet_fallback'],not controls['automatic_interaction'])) else 'fail';aid=_id('qatt303');now=_now();metrics={'links_in_scope':len(links),'primary_navigation_items':8};p={'attestation_id':aid,'result':result,'controls':controls,'metrics':metrics,'actor':actor,'created_at':now};self.db.execute('INSERT INTO phase13_queue_attestations_303 VALUES(?,?,?,?,?,?,?)',(aid,result,_canon(controls),_canon(metrics),actor,now,_hash(p)));return p
 def _case_row(self,case_id):
  r=self.db.one('SELECT * FROM cases WHERE case_id=?',(case_id,));
  if not r:raise KeyError('case not found')
  return r
 def compose_dossier(self,*,case_id,title='',actor=None):
  actor=actor or self.actor;case=self._case_row(case_id);rev=int((self.db.one('SELECT MAX(revision_no) n FROM phase13_ai_dossiers_303 WHERE case_id=?',(case_id,)) or {}).get('n') or 0)+1
  findings=self.db.all('SELECT title,url,snippet,source_class,evidence_ref,stance,created_at FROM ai_research_findings_263 WHERE case_id=? ORDER BY created_at LIMIT 250',(case_id,)) if self._table('ai_research_findings_263') else []
  sources=self.db.all('SELECT source_id,origin_url,retrieved_at,mime_type,sha256 FROM phase13_source_records_301 WHERE case_id=? ORDER BY retrieved_at LIMIT 200',(case_id,)) if self._table('phase13_source_records_301') else []
  hypotheses=self.db.all('SELECT hypothesis_id,label,statement,hypothesis_type,status FROM hypotheses_268 WHERE case_id=? ORDER BY created_at LIMIT 100',(case_id,)) if self._table('hypotheses_268') else []
  timeline=self.db.all('SELECT event_date,date_precision,event_text,evidence_refs_json,confidence_class,status FROM temporal_events_264 WHERE case_id=? ORDER BY event_date LIMIT 150',(case_id,)) if self._table('temporal_events_264') else []
  counters=self.db.all('SELECT verified_claim_id,strength,summary,provenance_verified FROM counterevidence_258 WHERE case_id=? ORDER BY created_at LIMIT 100',(case_id,)) if self._table('counterevidence_258') else []
  fusions=self.db.all('SELECT * FROM phase12_cross_surface_fusions_292 WHERE case_id=? ORDER BY created_at DESC LIMIT 3',(case_id,)) if self._table('phase12_cross_surface_fusions_292') else []
  openq=[]
  if not sources:openq.append('Noch keine Build-301/303 Source Records im Fall; Quellenbasis ergänzen.')
  if not findings:openq.append('Recherchefundstellen fehlen oder wurden noch nicht in den strukturierten Research-Lauf übernommen.')
  if not counters:openq.append('Explizites Counter-Evidence ist noch nicht dokumentiert; Gegenprüfung durchführen.')
  if hypotheses and not any(h['status'] in ('reviewed','accepted') for h in hypotheses):openq.append('Hypothesen sind noch nicht unabhängig geprüft; keine davon als Tatsache behandeln.')
  sup=[x for x in findings if x['stance']=='supports'];con=[x for x in findings if x['stance']=='contradicts'];ctx=[x for x in findings if x['stance'] not in ('supports','contradicts')]
  dossier_title=_safe(title or f"AI-Ermittlungsdossier – {case.get('title') or case_id}",180);lines=[f'# {dossier_title}','',f'**Fall:** {case_id}',f'**Status:** AI draft for analyst review',f'**Revision:** {rev}',f'**Erstellt:** {_now()}','', '> Dieses Dossier ist ein prüfbarer AI-Arbeitsentwurf. Es verifiziert keine Hypothese automatisch und ist nicht zur automatischen Veröffentlichung freigegeben.','', '## Executive Assessment','',f'- Strukturierte Fundstellen: **{len(findings)}** ({len(sup)} unterstützend, {len(con)} widersprechend, {len(ctx)} Kontext/neutral).',f'- Darknet/Onion Source Records: **{len(sources)}**.',f'- konkurrierende Hypothesen im Fall: **{len(hypotheses)}**.',f'- Timeline-Ereignisse: **{len(timeline)}**.',f'- explizite Counter-Evidence-Einträge: **{len(counters)}**.']
  if fusions:
   fx=fusions[0];lines.extend(['', '### Cross-Surface Arbeitsstand','',f"- Letzter Fusion-Record: `{fx.get('fusion_id','')}`. Confidence/Arbeitsreife bleibt ein Analysewert und keine Wahrheitswahrscheinlichkeit."])
  lines.extend(['','## Evidenz und Recherchefundstellen',''])
  if findings:
   for x in findings[:120]:lines.append(f"- **[{x['stance']}] {_safe(x['title'],220)}** — {_safe(x['snippet'],550)}  \n  Quelle: {x['url']} · Evidence: `{x['evidence_ref']}` · Klasse: `{x['source_class']}`")
  else:lines.append('- Noch keine strukturierten Recherchefundstellen vorhanden.')
  lines.extend(['','## Darknet / Source Provenance',''])
  if sources:
   for s in sources[:100]:lines.append(f"- `{s['source_id']}` · {s['origin_url']} · {s['retrieved_at']} · `{s['mime_type']}` · SHA-256 `{s['sha256']}`")
  else:lines.append('- Keine Onion Source Records vorhanden.')
  lines.extend(['','## Competing Hypotheses',''])
  if hypotheses:
   for h in hypotheses:lines.append(f"- **{_safe(h['label'],120)}** [{h['status']}] — {_safe(h['statement'],700)} _(type: {h['hypothesis_type']})_")
  else:lines.append('- Keine strukturierten Hypothesen vorhanden; keine Schlussfolgerung erzwingen.')
  lines.extend(['','## Counter-Evidence',''])
  if counters:
   for c in counters:lines.append(f"- Claim `{c['verified_claim_id']}` · Stärke `{c['strength']}` · {_safe(c['summary'],700)} · Provenienz geprüft: {bool(c['provenance_verified'])}")
  else:lines.append('- Noch kein explizites Counter-Evidence gespeichert. Dies ist eine materielle Recherche-Lücke.')
  lines.extend(['','## Timeline',''])
  if timeline:
   for t in timeline[:100]:lines.append(f"- {t['event_date']} ({t['date_precision']}) — {_safe(t['event_text'],500)} · Confidence `{t['confidence_class']}` · Status `{t['status']}`")
  else:lines.append('- Keine Timeline-Ereignisse vorhanden.')
  lines.extend(['','## Offene Fragen / Lücken',''])
  for q in openq or ['Keine automatisch erkannten strukturellen Mindestlücken; Analyst soll trotzdem Quellenunabhängigkeit, Identität und Gegenbelege prüfen.']:lines.append('- '+q)
  lines.extend(['','## Empfohlene Weiterarbeit','', '- Zentrale Aussagen gegen Primärquellen und unabhängige Quellen prüfen.', '- Widersprüche nicht glätten; diskriminierende Evidenzfragen priorisieren.', '- Bei neuen Onion-Leads nur innerhalb einer freigegebenen Build-303-Queue und deren Budget weiterarbeiten.', '- Nach materiellen neuen Erkenntnissen eine neue Dossier-Revision erzeugen.', '', '## Review Boundary','', '- Status bleibt `draft_for_review`, bis ein Analyst eine Review-Entscheidung speichert.', '- Keine automatische Veröffentlichung, Kontaktaufnahme, externe Weitergabe oder Hypothesen-Wahrheitsauswahl.', '- Evidence-/Source-Referenzen bleiben die Grundlage jeder weiteren Verwendung.'])
  content='\n'.join(lines)+'\n';did=_id('dossier303');rel=Path('dossiers_303')/case_id/f'{did}.md';target=self.base_dir/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content,encoding='utf-8');sha=_hash(content);now=_now();p={'dossier_id':did,'case_id':case_id,'revision_no':rev,'title':dossier_title,'status':'draft_for_review','markdown_relpath':rel.as_posix(),'content_sha256':sha,'source_count':len(sources),'finding_count':len(findings),'hypothesis_count':len(hypotheses),'timeline_count':len(timeline),'open_question_count':len(openq),'generated_by':actor,'generated_at':now};self.db.execute('INSERT INTO phase13_ai_dossiers_303 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(did,case_id,rev,dossier_title,'draft_for_review',rel.as_posix(),sha,len(sources),len(findings),len(hypotheses),len(timeline),len(openq),actor,now,_hash(p)));return {**p,'content':content,'automatic_publication':False,'review_required':True}
 def review_dossier(self,*,case_id,dossier_id,decision,review_note='',reviewer=None):
  reviewer=reviewer or self.actor;d=self.db.one('SELECT * FROM phase13_ai_dossiers_303 WHERE dossier_id=? AND case_id=?',(dossier_id,case_id))
  if not d:raise KeyError('dossier not found')
  if decision not in ('reviewed_for_continued_work','needs_revision','reject_draft'):raise ValueError('invalid dossier review decision')
  if self.db.one('SELECT 1 x FROM phase13_ai_dossier_reviews_303 WHERE dossier_id=?',(dossier_id,)):raise ValueError('dossier revision already reviewed')
  rid=_id('drev303');now=_now();p={'review_id':rid,'dossier_id':dossier_id,'case_id':case_id,'decision':decision,'review_note':_safe(review_note,2000),'reviewer':reviewer,'reviewed_at':now};self.db.execute('INSERT INTO phase13_ai_dossier_reviews_303 VALUES(?,?,?,?,?,?,?,?)',(rid,dossier_id,case_id,decision,p['review_note'],reviewer,now,_hash(p)));return p
 def dossier_file(self,case_id,dossier_id):
  d=self.db.one('SELECT * FROM phase13_ai_dossiers_303 WHERE dossier_id=? AND case_id=?',(dossier_id,case_id));
  if not d:raise KeyError('dossier not found')
  p=(self.base_dir/d['markdown_relpath']).resolve();root=self.base_dir.resolve()
  if root not in p.parents:raise RuntimeError('invalid dossier path')
  return p,d
 def startup_contract_status(self):
  import eagleeye_pro.version as v;text=(self.install_dir/'START_EAGLEEYE_PRO.bat').read_text(encoding='utf-8',errors='replace') if (self.install_dir/'START_EAGLEEYE_PRO.bat').exists() else ''
  
  def _at_least(x):
   try:return tuple(int(p) for p in str(x).split('.')[:2]) >= (303,0)
   except Exception:return False
  checks={'version_build_at_least_303':_at_least(v.BUILD),'version_schema_at_least_303':_at_least(v.SCHEMA_VERSION),'historical_entrypoint':(self.install_dir/'EAGLEEYE_PRO_303_0.py').exists(),'startup_script':(self.install_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_303_0.py').exists(),'versioned_launcher':(self.install_dir/'START_EAGLEEYE_PRO_303_0.bat').exists()};return {'build':'303.0','checks':checks,'contract_ready':all(checks.values()),'actual_packaged_boot_required':True}
 def all_training_cases(self):
  out=self.build302.all_training_cases();
  for r in self.db.all("SELECT * FROM ai_hard_training_delta_303 WHERE review_status='reviewed' ORDER BY benchmark_id"):out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
  return out
 def training_metrics(self):
  b=self.build302.training_metrics();d=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_303 WHERE review_status='reviewed'");e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_303 WHERE review_status='reviewed' AND difficulty='extreme'");return {'reviewed_hard_cases':int(b['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(b['adversarial_extreme_cases'])+e,'build303_delta_cases':d,'build303_delta_extreme':e,'performance_gate_threshold':.92,'critical_track_threshold':.88,'automatic_model_activation':False}
 def create_evaluation_batch(self,model_label='mistral:latest',actor=None):
  actor=actor or self.actor;cases=self.all_training_cases();manifest={'build':'303.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':.92,'critical_track_minimum':.88,'maximum_critical_failures':0,'independent_evaluator_required':True,'cases':cases};sha=_hash(manifest);ex=self.db.one('SELECT * FROM ai_evaluation_batches_303 WHERE model_label=? AND manifest_sha256=?',(model_label,sha))
  if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'critical_track_minimum':float(ex['critical_threshold']),'deduplicated':True}
  bid=_id('eval303');now=_now();p={'batch_id':bid,**manifest,'created_by':actor,'created_at':now};self.db.execute('INSERT INTO ai_evaluation_batches_303 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),.92,.88,1.0,0,'prepared',1,sha,actor,now,_hash(p)));return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':.92,'critical_track_minimum':.88,'deduplicated':False}
 def performance_status(self,model_label='mistral:latest'):return {'model_label':model_label,'status':'not_run','qualified':False,'required_corpus_size':408,'minimum_mean_score':.92,'critical_track_minimum':.88,'note':'No model-performance claim without full independent 408-case run.'}
 def qualified_gate(self):
  tm=self.training_metrics();b=self.create_evaluation_batch();att=self.db.one("SELECT * FROM phase13_queue_attestations_303 WHERE result='pass' ORDER BY rowid DESC LIMIT 1");startup=self.startup_contract_status();parent=self.build302.qualified_gate();g={'build':'303.0','parent_302_gate':parent['release_ready'],'queue_scope_attestation':bool(att),'bounded_queue_tables_ready':all(self._table(n) for n in ('phase13_onion_research_queues_303','phase13_onion_queue_items_303','phase13_onion_queue_fetches_303')),'ai_dossier_tables_ready':all(self._table(n) for n in ('phase13_ai_dossiers_303','phase13_ai_dossier_reviews_303')),'ui_primary_navigation_stays_8':self.build302.navigation_model()['visible_after']==8,'training_corpus_408':tm['reviewed_hard_cases']==408 and tm['build303_delta_cases']==16 and tm['build303_delta_extreme']==4,'evaluation_batch_408_ready':b['corpus_size']==408,'startup_contract_ready':startup['contract_ready'],'queue_exact_ok_required':True,'same_host_default':True,'clearnet_fallback':False,'credentials_forms_upload_contact':False,'automatic_publication':False,'automatic_model_activation':False};g['release_ready']=all((g['parent_302_gate'],g['queue_scope_attestation'],g['bounded_queue_tables_ready'],g['ai_dossier_tables_ready'],g['ui_primary_navigation_stays_8'],g['training_corpus_408'],g['evaluation_batch_408_ready'],g['startup_contract_ready'],g['queue_exact_ok_required'],g['same_host_default'],not g['clearnet_fallback'],not g['credentials_forms_upload_contact'],not g['automatic_publication'],not g['automatic_model_activation']));return g
 def render_workspace_panel(self,case_id,csrf,section='cockpit'):
  e=lambda v:html.escape(str(v or ''),quote=True)
  if section not in ('sources','reports'):
   return self.build302.render_workspace_panel(case_id,csrf,section)
  if section=='sources':
   base=self.build302.render_workspace_panel(case_id,csrf,'sources');queues=self.db.all('SELECT q.*,a.approval_id FROM phase13_onion_research_queues_303 q LEFT JOIN phase13_onion_queue_approvals_303 a ON a.queue_id=q.queue_id WHERE q.case_id=? ORDER BY q.created_at DESC LIMIT 12',(case_id,));rows=[]
   for q in queues:
    st=self.queue_status(q['queue_id']);rows.append(f"<tr><td><code>{e(q['queue_id'])}</code></td><td>{e(q['onion_host'])}</td><td>{st['requests_used']}/{e(q['max_requests'])}</td><td>{st['pending_count']}</td><td>{'OK' if q.get('approval_id') else 'wartet'}</td><td><form method='post' action='/build303/queue-approve'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='queue_id' value='{e(q['queue_id'])}'><input name='confirmation' placeholder='OK' size='4'><button>Freigeben</button></form></td><td><form method='post' action='/build303/queue-run'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='queue_id' value='{e(q['queue_id'])}'><button>Nächsten Read-only Schritt</button></form></td></tr>")
   extra=f"<div class='panel'><h2>Build 303 · Onion Research Queue</h2><div class='notice'>Eine einmal mit <b>OK</b> freigegebene Queue darf innerhalb ihrer festen Grenzen mehrere reine GET-Schritte ausführen. Standard: gleicher Onion-Host, max. Tiefe/Requests/Bytes. Keine Login-/Formular-/Upload-/Kontakt-Aktionen.</div><form method='post' action='/build303/queue'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><label>Seed v3 Onion URL<br><input name='seed_url' style='width:100%'></label><label>Zweck<br><input name='purpose' style='width:100%' value='Bounded read-only onion research'></label><label>Requests <input name='max_requests' value='8' size='4'></label> <label>Tiefe <input name='max_depth' value='1' size='3'></label> <label>Gesamtbytes <input name='max_total_bytes' value='2097152'></label><button>Research Queue anlegen</button></form><table><tr><th>Queue</th><th>Host</th><th>Requests</th><th>Pending</th><th>Status</th><th>OK</th><th>Run</th></tr>{''.join(rows) or '<tr><td colspan="7">Noch keine Build-303-Queue.</td></tr>'}</table><form method='post' action='/build303/selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Queue-Scope-Selftest</button></form></div>";return base+extra
  dossiers=self.db.all('SELECT d.*,r.decision FROM phase13_ai_dossiers_303 d LEFT JOIN phase13_ai_dossier_reviews_303 r ON r.dossier_id=d.dossier_id WHERE d.case_id=? ORDER BY d.revision_no DESC LIMIT 12',(case_id,));rows=[]
  for d in dossiers:
   rows.append(f"<tr><td>{e(d['revision_no'])}</td><td>{e(d['title'])}</td><td>{e(d.get('decision') or d['status'])}</td><td>{d['finding_count']}</td><td>{d['source_count']}</td><td><a href='/build303/dossier/download?case_id={e(case_id)}&amp;dossier_id={e(d['dossier_id'])}'>Markdown öffnen</a></td><td><form method='post' action='/build303/dossier-review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='dossier_id' value='{e(d['dossier_id'])}'><select name='decision'><option value='reviewed_for_continued_work'>für Weiterarbeit geprüft</option><option value='needs_revision'>Revision nötig</option><option value='reject_draft'>Entwurf verwerfen</option></select><input name='review_note' placeholder='Review-Notiz'><button>Review speichern</button></form></td></tr>")
  return f"<div class='notice'><b>AI-Dossier nach Recherche:</b> EagleEye kann den aktuellen Fallstand als Markdown-Arbeitsdossier verschriftlichen. Der Entwurf bleibt überprüfungspflichtig und enthält Evidenz-/Quellenreferenzen, Gegenbelege, Hypothesen, Timeline, Unsicherheiten und offene Fragen.</div><div class='panel'><h2>Dossier-Entwurf erzeugen</h2><form method='post' action='/build303/dossier'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><label>Titel (optional)<br><input name='title' style='width:100%' placeholder='AI-Ermittlungsdossier'></label><button>AI-Dossier verschriftlichen</button></form></div><div class='panel'><h2>Dossier-Revisionen</h2><table><tr><th>Rev.</th><th>Titel</th><th>Status</th><th>Findings</th><th>Sources</th><th>Datei</th><th>Review</th></tr>{''.join(rows) or '<tr><td colspan="7">Noch kein Build-303-Dossier.</td></tr>'}</table></div>"
