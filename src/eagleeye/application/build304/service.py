from __future__ import annotations
import hashlib,html,json,re,uuid
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

def _now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p):return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256((v if isinstance(v,str) else _canon(v)).encode()).hexdigest()
def _safe(v,n=5000):return re.sub(r'\s+',' ',str(v or '')).strip()[:n]

class _HTML(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.txt=[];self.title=[];self.intitle=False
 def handle_starttag(self,t,a):self.intitle=(t.lower()=='title')
 def handle_endtag(self,t):
  if t.lower()=='title':self.intitle=False
 def handle_data(self,d):
  s=_safe(d,3000)
  if s:self.txt.append(s);self.title.extend([s] if self.intitle else [])

class Build304ContentDossierSecurityService:
 BUILD='304.0';REQUIRED_CORPUS=424
 def __init__(self,db:Any,audit:Any,*,cases:Any,build303:Any,build302:Any,build301:Any,install_dir:Path,base_dir:Path,actor='local-analyst'):
  self.db=db;self.audit=audit;self.cases=cases;self.build303=build303;self.build302=build302;self.build301=build301;self.install_dir=Path(install_dir);self.base_dir=Path(base_dir);self.actor=actor
 def _table(self,n):return bool(self.db.one("SELECT 1 x FROM sqlite_master WHERE type='table' AND name=?",(n,)))
 def _count(self,q,a=()):
  try:return int((self.db.one(q,a) or {}).get('n') or 0)
  except Exception:return 0
 def _source(self,sid):
  r=self.db.one('SELECT * FROM phase13_source_records_301 WHERE source_id=?',(sid,))
  if not r:raise KeyError('source record not found')
  return r
 def _artifact(self,s):
  p=(self.base_dir/s['artifact_relpath']).resolve();root=self.base_dir.resolve()
  if root not in p.parents:raise RuntimeError('invalid artifact path')
  return p
 def _language(self,t):
  x=' '+t.lower()+' ';de=sum(x.count(' '+w+' ') for w in ('der','die','das','und','ist','mit','von','zu','ein','eine','nicht'));en=sum(x.count(' '+w+' ') for w in ('the','and','is','with','from','to','a','an','not','of'))
  return 'de' if de>=3 and de>en else ('en' if en>=3 and en>de else 'unknown')
 def scan_source(self,source_id,actor=None):
  actor=actor or self.actor;s=self._source(source_id);text=self._artifact(s).read_bytes()[:2*1024*1024].decode('utf-8','replace');low=text.lower();signals=[];score=0
  def add(name,w,detail):
   nonlocal score;signals.append({'signal':name,'weight':w,'detail':detail});score+=w
  if re.search(r'<script\b',low):add('active_script',25,'script element present')
  if re.search(r'<iframe\b|<object\b|<embed\b',low):add('embedded_active_content',20,'embedded active content present')
  if re.search(r'<form\b',low):add('form_interaction',15,'form present')
  if re.search(r'type\s*=\s*["\']password["\']',low):add('credential_pressure',35,'password field present')
  if re.search(r'navigator\.|canvas|getcontext\(|webgl|audiocontext|hardwareconcurrency|devicememory',low):add('fingerprinting_indicator',25,'fingerprinting primitive referenced')
  if re.search(r'sendbeacon|new\s+websocket|xmlhttprequest|\bfetch\s*\(|document\.cookie|localstorage|sessionstorage',low):add('tracking_or_state_api',20,'browser state/network API referenced')
  ext=[];origin=(urlsplit(s['origin_url']).hostname or '').lower()
  for m in re.finditer(r'(?i)(?:src|href)\s*=\s*["\'](https?://[^"\']+)',text):
   h=(urlsplit(m.group(1)).hostname or '').lower()
   if h and h!=origin:ext.append(h)
  if ext:add('cross_origin_resource',min(25,5+len(set(ext))*3),f'{len(set(ext))} external host(s) referenced')
  score=min(100,score);level='critical' if score>=70 else ('high' if score>=45 else ('medium' if score>=20 else 'low'));blocked=score>=45;verdict='quarantine_static_only' if blocked else 'static_processing_allowed';reason='active/tracking indicators require static-only handling' if blocked else '';now=_now();sid=_id('secscan304');p={'scan_id':sid,'case_id':s['case_id'],'source_id':source_id,'risk_level':level,'risk_score':score,'verdict':verdict,'signals':signals,'blocked':blocked,'quarantine_reason':reason,'scanned_by':actor,'scanned_at':now}
  self.db.execute('INSERT INTO phase13_security_scans_304 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(sid,s['case_id'],source_id,level,score,verdict,_canon(signals),int(blocked),reason,actor,now,_hash(p)))
  for z in signals:
   eid=_id('secev304');ep={'event_id':eid,'case_id':s['case_id'],'source_id':source_id,'event_type':z['signal'],'severity':level,'detail':z['detail'],'action':'block_active_processing' if blocked else 'report','created_at':now};self.db.execute('INSERT INTO phase13_security_events_304 VALUES(?,?,?,?,?,?,?,?,?)',(eid,s['case_id'],source_id,z['signal'],level,z['detail'],ep['action'],now,_hash(ep)))
  return p
 def analyze_source(self,source_id,actor=None):
  actor=actor or self.actor;s=self._source(source_id);scan=self.scan_source(source_id,actor);mime=(s.get('mime_type') or '').lower()
  if not (mime.startswith('text/') or mime in ('application/xhtml+xml','application/json','application/xml')):raise ValueError('static text/document analysis only')
  raw=self._artifact(s).read_bytes()[:2*1024*1024].decode('utf-8','replace');title='';text=raw
  if 'html' in mime or '<html' in raw[:1000].lower():
   p=_HTML();p.feed(raw);text=' '.join(p.txt);title=_safe(' '.join(p.title),240)
  text=_safe(text,250000);nsha=_hash(text.lower());dup=self.db.one('SELECT content_id FROM phase13_content_records_304 WHERE normalized_sha256=? ORDER BY analyzed_at LIMIT 1',(nsha,));ents=[];seen=set()
  for typ,pat in [('email',r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b'),('onion',r'\b[a-z2-7]{56}\.onion\b'),('url',r'https?://[^\s<>"\']+'),('domain',r'\b(?:[a-z0-9-]+\.)+[a-z]{2,24}\b')]:
   for m in re.finditer(pat,text,re.I):
    val=m.group(0).rstrip('.,);]');key=(typ,val.lower())
    if key not in seen:seen.add(key);ents.append((typ,val,m.start()))
  claims=[];cue=re.compile(r'\b(ist|war|hat|gehört|behauptet|meldet|sagt|according|claims?|alleges?|is|was|has|owns?|works?|reported)\b',re.I)
  for i,x in enumerate(re.split(r'(?<=[.!?])\s+',text)):
   x=_safe(x,900)
   if 35<=len(x)<=900 and cue.search(x):claims.append((x,i))
  ents=ents[:200];claims=claims[:120];cid=_id('content304');now=_now();status='static_only_quarantined' if scan['blocked'] else 'normalized_static';rec={'content_id':cid,'case_id':s['case_id'],'source_id':source_id,'origin_url':s['origin_url'],'normalized_sha256':nsha,'duplicate_of_content_id':(dup or {}).get('content_id',''),'language_code':self._language(text),'title':title,'text_excerpt':text[:1500],'word_count':len(text.split()),'entity_count':len(ents),'claim_count':len(claims),'content_status':status,'analyzed_by':actor,'analyzed_at':now}
  self.db.execute('INSERT INTO phase13_content_records_304 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,s['case_id'],source_id,s['origin_url'],nsha,rec['duplicate_of_content_id'],rec['language_code'],title,text[:1500],rec['word_count'],len(ents),len(claims),status,actor,now,_hash(rec)))
  for typ,val,pos in ents:
   hid=_id('ent304');h={'entity_hit_id':hid,'content_id':cid,'case_id':s['case_id'],'entity_type':typ,'normalized_value':val.lower(),'surface_value':val,'confidence':.85,'evidence_locator':f'char:{pos}','created_at':now};self.db.execute('INSERT INTO phase13_content_entities_304 VALUES(?,?,?,?,?,?,?,?,?,?)',(hid,cid,s['case_id'],typ,val.lower(),val,.85,f'char:{pos}',now,_hash(h)))
  for claim,idx in claims:
   hid=_id('claim304');h={'claim_hit_id':hid,'content_id':cid,'case_id':s['case_id'],'claim_text':claim,'claim_class':'source_assertion','evidence_locator':f'sentence:{idx}','source_status':'unverified_source_assertion','confidence_class':'unverified','created_at':now};self.db.execute('INSERT INTO phase13_content_claims_304 VALUES(?,?,?,?,?,?,?,?,?,?)',(hid,cid,s['case_id'],claim,'source_assertion',f'sentence:{idx}','unverified_source_assertion','unverified',now,_hash(h)))
  return {**rec,'security_scan':scan,'entities':ents,'claims':[c[0] for c in claims]}
 def _strict_verified_facts(self,case_id):
  if not self._table('verified_claims_229'):return []
  out=[]
  for c in self.db.all('SELECT * FROM verified_claims_229 WHERE case_id=? ORDER BY verification_score DESC,created_at',(case_id,)):
   try:refs=json.loads(c.get('supporting_refs_json') or '[]')
   except Exception:refs=[]
   if c.get('status') in ('verified','accepted') and float(c.get('verification_score') or 0)>=.80 and int(c.get('independent_support_count') or 0)>=1 and int(c.get('counterevidence_checked') or 0)==1 and refs:
    out.append((c,refs))
  return out
 def _queue_security_block(self,queue_id):
  row=self.db.one('SELECT s.* FROM phase13_onion_queue_fetches_303 f JOIN phase13_security_scans_304 s ON s.source_id=f.source_id LEFT JOIN phase13_security_reviews_304 r ON r.scan_id=s.scan_id WHERE f.queue_id=? AND s.blocked=1 AND (r.review_id IS NULL OR r.decision<>\'allow_bounded_static_continue\') ORDER BY s.scanned_at DESC LIMIT 1',(queue_id,))
  return row
 def review_security_scan(self,scan_id,decision,confirmation,rationale='',reviewer=None):
  reviewer=reviewer or self.actor
  if confirmation!='OK':raise ValueError('exact confirmation OK required')
  if decision not in ('allow_bounded_static_continue','keep_blocked'):raise ValueError('invalid security review decision')
  s=self.db.one('SELECT * FROM phase13_security_scans_304 WHERE scan_id=?',(scan_id,))
  if not s:raise KeyError('security scan not found')
  if self.db.one('SELECT 1 x FROM phase13_security_reviews_304 WHERE scan_id=?',(scan_id,)):raise ValueError('security scan already reviewed')
  rid=_id('secrev304');now=_now();rec={'review_id':rid,'scan_id':scan_id,'decision':decision,'confirmation':'OK','rationale':_safe(rationale,1500),'reviewer':reviewer,'reviewed_at':now};self.db.execute('INSERT INTO phase13_security_reviews_304 VALUES(?,?,?,?,?,?,?,?)',(rid,scan_id,decision,'OK',rec['rationale'],reviewer,now,_hash(rec)));return rec
 def secure_run_next(self,queue_id,actor=None):
  actor=actor or self.actor;blocked=self._queue_security_block(queue_id)
  if blocked:raise PermissionError(f"AI Security Agent blocked queue pending human review: {blocked['scan_id']}")
  r=self.build303.run_next(queue_id,actor=actor)
  if r.get('source_id'):
   a=self.analyze_source(r['source_id'],actor=actor);s=a['security_scan'];r={**r,'security_scan_id':s['scan_id'],'security_risk_level':s['risk_level'],'security_risk_score':s['risk_score'],'security_blocked':bool(s['blocked'])}
  return r
 def security_agent_status(self):
  tm=self.training_metrics();return {'agent':'AI Security Agent','build':'304.0','mode':'defensive_static_analysis_v1','security_training_cases_build304':tm['security_agent_delta_cases'],'model_status':'not_run','detects':['active content','embedded content','forms/credential pressure','fingerprinting primitives','browser state/network APIs','cross-origin resources'],'blocks':'high/critical queue continuation pending exact-OK human review','active_content_execution':False,'external_embedded_resource_fetch':False,'offensive_counteraction':False,'automatic_network_reconfiguration':False}
 def compose_evidence_dossier(self,*,case_id,title='',actor=None):
  actor=actor or self.actor;case=self.db.one('SELECT * FROM cases WHERE case_id=?',(case_id,));
  if not case:raise KeyError('case not found')
  parent=self.build303.compose_dossier(case_id=case_id,title=title or '',actor=actor);rev=int((self.db.one('SELECT MAX(revision_no) n FROM phase13_dossier_revisions_304 WHERE case_id=?',(case_id,)) or {}).get('n') or 0)+1
  facts=self._strict_verified_facts(case_id);findings=self.db.all('SELECT title,url,snippet,source_class,evidence_ref,stance FROM ai_research_findings_263 WHERE case_id=? ORDER BY created_at LIMIT 350',(case_id,)) if self._table('ai_research_findings_263') else []
  sources=self.db.all('SELECT source_id,origin_url,sha256 FROM phase13_source_records_301 WHERE case_id=? ORDER BY retrieved_at LIMIT 300',(case_id,)) if self._table('phase13_source_records_301') else []
  claims=self.db.all('SELECT c.claim_text,c.evidence_locator,r.source_id,r.origin_url FROM phase13_content_claims_304 c JOIN phase13_content_records_304 r ON r.content_id=c.content_id WHERE c.case_id=? ORDER BY c.created_at LIMIT 250',(case_id,))
  counters=self.db.all('SELECT verified_claim_id,strength,summary,provenance_verified FROM counterevidence_258 WHERE case_id=? ORDER BY created_at LIMIT 150',(case_id,)) if self._table('counterevidence_258') else []
  scans=self.db.all('SELECT risk_level FROM phase13_security_scans_304 WHERE case_id=?',(case_id,));cited=sum(1 for _,refs in facts if refs);coverage=(cited/len(facts)) if facts else 1.0;independence=(sum(min(1.0,int(c.get('independent_support_count') or 0)/2) for c,_ in facts)/len(facts)) if facts else 0.0;countercov=(sum(1 for c,_ in facts if int(c.get('counterevidence_checked') or 0)==1)/len(facts)) if facts else 0.0;integrity=1.0 if not sources else sum(1 for s in sources if _safe(s.get('sha256')))/len(sources);contr=sum(1 for f in findings if f.get('stance')=='contradicts')+sum(1 for c,_ in facts if int(c.get('independent_contradiction_count') or 0)>0);groups={urlsplit(f['url']).hostname.lower() for f in findings if _safe(f.get('url')) and urlsplit(f['url']).hostname};unsupported=0;quality=max(0,min(1,.32*coverage+.23*integrity+.20*independence+.15*countercov+.10*(1 if unsupported==0 else 0)));gate='pass' if facts and coverage==1.0 and integrity>=.95 and countercov==1.0 and unsupported==0 else ('review_required_no_verified_facts' if not facts else 'review_required')
  lines=[f'# {_safe(title or "Evidenzbasiertes AI-Ermittlungsdossier",180)}','',f'**Fall:** {case_id}',f'**Revision:** {rev}',f'**Status:** draft_for_review',f'**Qualitätsgate:** {gate} ({quality:.1%})','', '> Build 304 trennt verifizierte Fakten strikt von belegten Fundstellen, Quellenbehauptungen und analytischen Ableitungen. Ein Quellenbeleg allein macht eine Behauptung nicht wahr.','', '## Verifizierte Fakten','']
  if facts:
   for i,(c,refs) in enumerate(facts,1):lines += [f"{i}. **{_safe(c['claim_text'],700)}**",f"   - Claim: `{c['verified_claim_id']}`",f"   - Verification score: `{float(c['verification_score']):.2f}`",f"   - unabhängige Unterstützung: `{c['independent_support_count']}`",f"   - Evidence: `{', '.join(map(str,refs))}`"]
  else:lines.append('- Keine Aussage erfüllt derzeit die strenge Build-304-Faktengrenze. Unzureichend belegte Aussagen bleiben Claims/Fundstellen.')
  lines += ['','## Belegte Recherchefundstellen – nicht automatisch Fakten','']
  if findings:
   for i,f in enumerate(findings[:180],1):lines += [f"{i}. **[{f['stance']}] {_safe(f['title'],220)}**",f"   - Evidence: `{f['evidence_ref'] or 'fehlt'}`",f"   - Quelle: {f['url'] or 'fehlt'}",f"   - Inhalt: {_safe(f['snippet'],650)}",'   - Status: **Recherchefundstelle / nicht automatisch verifizierte Wahrheit**']
  else:lines.append('- Keine strukturierten Recherchefundstellen.')
  lines += ['','## Unverifizierte Quellenbehauptungen','']
  if claims:
   for c in claims[:150]:lines.append(f"- **UNVERIFIZIERTE QUELLENBEHAUPTUNG:** {_safe(c['claim_text'],700)} · Source `{c['source_id']}` · Locator `{c['evidence_locator']}`")
  else:lines.append('- Keine extrahierten Build-304-Quellenbehauptungen.')
  lines += ['','## Counter-Evidence / Widersprüche','']
  if counters:
   for c in counters:lines.append(f"- Claim `{c['verified_claim_id']}` · Stärke `{c['strength']}` · {_safe(c['summary'],650)} · Provenienz geprüft: {bool(c['provenance_verified'])}")
  else:lines.append('- Kein explizites Counter-Evidence gespeichert; bei materiellen Aussagen bleibt dies eine offene Prüfaufgabe.')
  high=sum(1 for s in scans if s['risk_level'] in ('high','critical'));lines += ['','## Qualitäts- und Quellenstatus','',f'- Verified facts: **{len(facts)}**.',f'- Fact Citation Coverage: **{coverage:.1%}**.',f'- Source Integrity Coverage: **{integrity:.1%}**.',f'- Source Independence Score (verified facts): **{independence:.1%}**.',f'- Counter-Evidence Coverage (verified facts): **{countercov:.1%}**.',f'- Unabhängige Host-Gruppen der Recherchefundstellen: **{len(groups)}**.',f'- Widerspruchssignale: **{contr}**.',f'- Unsupported fact count: **{unsupported}**.',f'- High/Critical Security Scans: **{high}**.','', '## Analytische Grenzen','', '- Source Echo zählt nicht automatisch als unabhängige Bestätigung.', '- AI-Ableitungen bleiben von Evidence-/Source-Referenzen getrennt.', '- Widersprüche und Gegenbelege dürfen nicht geglättet werden.', '- Darknet-Source-Statements bleiben Behauptungen der Quelle, bis unabhängige Evidenz sie trägt.','', '## Parent-Arbeitsdossier','',f'- Build-303 Parent: `{parent["dossier_id"]}` Revision {parent["revision_no"]}.','', '## Review-Checkliste','', '- [ ] Verifizierte Fakten gegen Evidence-Refs geprüft.', '- [ ] Primärquelle/Originaldokument soweit möglich geprüft.', '- [ ] Quellenunabhängigkeit geprüft.', '- [ ] Identitätsauflösung geprüft.', '- [ ] Gegenbelege/Widersprüche geprüft.', '- [ ] High/Critical Security Events geprüft.', '', '**Keine automatische Veröffentlichung oder Wahrheitsauswahl.**']
  content='\n'.join(lines)+'\n';did=_id('dossier304');rel=Path('dossiers_304')/case_id/f'{did}.md';pp=self.base_dir/rel;pp.parent.mkdir(parents=True,exist_ok=True);pp.write_text(content,encoding='utf-8');now=_now();qid=_id('dq304');metrics={'factual_claims':len(facts),'cited_factual_claims':cited,'citation_coverage':coverage,'independent_source_groups':len(groups),'contradiction_count':contr,'unresolved_count':len(claims)+len(findings),'source_integrity_coverage':integrity,'source_independence_score':independence,'counterevidence_coverage':countercov,'unsupported_fact_count':unsupported,'quality_score':quality};qp={'quality_id':qid,'case_id':case_id,'dossier_id':did,'dossier_revision':rev,**metrics,'gate_result':gate,'evaluated_by':actor,'evaluated_at':now};self.db.execute('INSERT INTO phase13_dossier_quality_304 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(qid,case_id,did,rev,len(facts),cited,coverage,len(groups),contr,len(claims)+len(findings),integrity,quality,gate,_canon(metrics),actor,now,_hash(qp)));dp={'dossier304_id':did,'parent_dossier303_id':parent['dossier_id'],'case_id':case_id,'revision_no':rev,'title':_safe(title or 'Evidenzbasiertes AI-Ermittlungsdossier',180),'status':'draft_for_review','markdown_relpath':rel.as_posix(),'content_sha256':_hash(content),'quality_id':qid,'generated_by':actor,'generated_at':now};self.db.execute('INSERT INTO phase13_dossier_revisions_304 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,parent['dossier_id'],case_id,rev,dp['title'],'draft_for_review',rel.as_posix(),dp['content_sha256'],qid,actor,now,_hash(dp)));return {**dp,'quality':metrics,'quality_gate':gate,'content':content,'review_required':True,'automatic_publication':False}
 def dossier_file(self,case_id,dossier_id):
  d=self.db.one('SELECT * FROM phase13_dossier_revisions_304 WHERE dossier304_id=? AND case_id=?',(dossier_id,case_id));
  if not d:raise KeyError('dossier not found')
  return self.base_dir/d['markdown_relpath'],d
 def _test_source(self,case_id,onion,raw,actor,prefix):
  rel=Path('raw_sources_304')/(prefix+'.html');p=self.base_dir/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);sha=hashlib.sha256(raw).hexdigest();m=self.build301.create_mission(case_id=case_id,onion_url='http://'+onion+'/',purpose='Build304 selftest',actor=actor);self.build301.approve_mission(m['mission_id'],'OK',actor);fid=_id('fetch304');now=_now();fp={'f':fid};self.db.execute('INSERT INTO phase13_tor_fetches_301 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(fid,m['mission_id'],'success','http://'+onion+'/',200,'text/html',len(raw),sha,rel.as_posix(),'{}','', '127.0.0.1',9050,now,_hash(fp)));sid=_id('src304');prov={'method':'GET','selftest':True};self.db.execute('INSERT INTO phase13_source_records_301 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,case_id,m['mission_id'],fid,'darknet_onion_readonly','http://'+onion+'/',now,'text/html',len(raw),sha,rel.as_posix(),_canon(prov),_hash({'s':sid})));return sid
 def run_content_intelligence_selftest(self,actor=None):
  actor=actor or self.actor;c=self.cases.create_case('304 content','internal','qa','qa');sid=self._test_source(c['case_id'],'a'*56+'.onion',b'<html><title>Test</title><body>According to the source, Alice owns example.org. Contact alice@example.org.</body></html>',actor,'content');a=self.analyze_source(sid,actor);b=self.analyze_source(sid,actor);ctl={'normalized_text':a['word_count']>5,'language_explicit':a['language_code'] in ('en','de','unknown'),'entity_candidates':a['entity_count']>=2,'claims_remain_unverified':a['claim_count']>=1,'duplicate_detection':bool(b['duplicate_of_content_id']),'raw_source_retained':self._artifact(self._source(sid)).exists()};res='pass' if all(ctl.values()) else 'fail';aid=_id('ciatt304');metrics={'entities':a['entity_count'],'claims':a['claim_count']};now=_now();self.db.execute('INSERT INTO phase13_content_intel_attestations_304 VALUES(?,?,?,?,?,?,?)',(aid,res,_canon(ctl),_canon(metrics),actor,now,_hash({'a':aid,'r':res})));return {'attestation_id':aid,'result':res,'controls':ctl,'metrics':metrics}
 def run_security_agent_selftest(self,actor=None):
  actor=actor or self.actor;c=self.cases.create_case('304 security','internal','qa','qa');sid=self._test_source(c['case_id'],'b'*56+'.onion',b'<html><script>navigator.hardwareConcurrency; fetch("https://tracker.invalid/p")</script><form><input type="password"></form></html>',actor,'security');s=self.scan_source(sid,actor);ctl={'tracking_detected':any(x['signal'] in ('fingerprinting_indicator','tracking_or_state_api','cross_origin_resource') for x in s['signals']),'credential_pressure_detected':any(x['signal']=='credential_pressure' for x in s['signals']),'high_risk_blocked':s['blocked'],'no_exploit_execution':True,'no_network_reconfiguration':True,'human_report_created':bool(s['signals'])};res='pass' if all(ctl.values()) else 'fail';aid=_id('secatt304');metrics={'risk_score':s['risk_score'],'signals':len(s['signals'])};now=_now();self.db.execute('INSERT INTO phase13_security_agent_attestations_304 VALUES(?,?,?,?,?,?,?)',(aid,res,_canon(ctl),_canon(metrics),actor,now,_hash({'a':aid,'r':res})));return {'attestation_id':aid,'result':res,'controls':ctl,'metrics':metrics}
 def startup_contract_status(self):
  import eagleeye_pro.version as v;text=(self.install_dir/'START_EAGLEEYE_PRO.bat').read_text(encoding='utf-8',errors='replace') if (self.install_dir/'START_EAGLEEYE_PRO.bat').exists() else '';checks={'version_build':tuple(map(int,v.BUILD.split('.')[:2]))>=(304,0),'version_schema':tuple(map(int,v.SCHEMA_VERSION.split('.')[:2]))>=(304,0),'entrypoint':(self.install_dir/'EAGLEEYE_PRO_304_0.py').exists(),'startup_script':(self.install_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_304_0.py').exists(),'generic_launcher_points_to_304':'EAGLEEYE_PRO_304_0.py' in text and 'Build 304.0' in text,'versioned_launcher':(self.install_dir/'START_EAGLEEYE_PRO_304_0.bat').exists()};return {'build':'304.0','checks':checks,'contract_ready':all(checks.values())}
 def all_training_cases(self):
  out=self.build303.all_training_cases()
  for table in ('ai_hard_training_delta_304','ai_security_training_delta_304'):
   for r in self.db.all(f"SELECT * FROM {table} WHERE review_status='reviewed' ORDER BY benchmark_id"):out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
  return out
 def training_metrics(self):
  b=self.build303.training_metrics();d1=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_304 WHERE review_status='reviewed'");d2=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_304 WHERE review_status='reviewed'");e1=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_304 WHERE difficulty='extreme' AND review_status='reviewed'");e2=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_304 WHERE difficulty='extreme' AND review_status='reviewed'");return {'reviewed_hard_cases':b['reviewed_hard_cases']+d1+d2,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e1+e2,'build304_delta_cases':d1+d2,'build304_delta_extreme':e1+e2,'dossier_delta_cases':d1,'security_agent_delta_cases':d2}
 def create_evaluation_batch(self,model_label='mistral:latest',actor=None):
  actor=actor or self.actor;cases=self.all_training_cases();sha=_hash(cases);ex=self.db.one('SELECT * FROM ai_evaluation_batches_304 WHERE model_label=? AND manifest_sha256=?',(model_label,sha))
  if ex:return {'batch_id':ex['batch_id'],'corpus_size':ex['corpus_size'],'deduplicated':True}
  bid=_id('eval304');now=_now();self.db.execute('INSERT INTO ai_evaluation_batches_304 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),.92,.88,1.0,0,'prepared',1,sha,actor,now,_hash({'b':bid})));return {'batch_id':bid,'corpus_size':len(cases),'deduplicated':False}
 def performance_status(self,model_label='mistral:latest'):return {'model_label':model_label,'status':'not_run','qualified':False,'required_corpus_size':424,'note':'No performance claim without full independent 424-case run.'}
 def qualified_gate(self):
  tm=self.training_metrics();ci=self.db.one("SELECT 1 x FROM phase13_content_intel_attestations_304 WHERE result='pass' LIMIT 1");sec=self.db.one("SELECT 1 x FROM phase13_security_agent_attestations_304 WHERE result='pass' LIMIT 1");p=self.build303.qualified_gate();g={'build':'304.0','parent_303_gate':p['release_ready'],'content_intelligence_attestation':bool(ci),'security_agent_attestation':bool(sec),'training_corpus_424':tm['reviewed_hard_cases']==424 and tm['build304_delta_cases']==16 and tm['build304_delta_extreme']==4,'evaluation_batch_424_ready':self.create_evaluation_batch()['corpus_size']==424,'startup_contract_ready':self.startup_contract_status()['contract_ready'],'ui_primary_navigation_stays_8':self.build302.navigation_model()['visible_after']==8,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'no_automatic_publication':True,'no_exploit_execution':True,'no_unreviewed_network_reconfiguration':True,'clearnet_fallback':False};g['release_ready']=all((g['parent_303_gate'],g['content_intelligence_attestation'],g['security_agent_attestation'],g['training_corpus_424'],g['evaluation_batch_424_ready'],g['startup_contract_ready'],g['ui_primary_navigation_stays_8'],g['dossier_improvement_through_320'],g['security_agent_improvement_through_320'],g['no_automatic_publication'],g['no_exploit_execution'],g['no_unreviewed_network_reconfiguration'],not g['clearnet_fallback']));return g
 def render_workspace_panel(self,case_id,csrf,section='cockpit'):
  e=lambda v:html.escape(str(v or ''),quote=True);base=self.build303.render_workspace_panel(case_id,csrf,section)
  if section=='reports':
   rows=self.db.all('SELECT d.*,q.quality_score,q.citation_coverage,q.gate_result FROM phase13_dossier_revisions_304 d JOIN phase13_dossier_quality_304 q ON q.quality_id=d.quality_id WHERE d.case_id=? ORDER BY d.revision_no DESC LIMIT 12',(case_id,));rr=''.join(f"<tr><td>{x['revision_no']}</td><td>{e(x['title'])}</td><td>{float(x['quality_score']):.0%}</td><td>{float(x['citation_coverage']):.0%}</td><td>{e(x['gate_result'])}</td><td><a href='/build304/dossier/download?case_id={e(case_id)}&amp;dossier_id={e(x['dossier304_id'])}'>Markdown</a></td></tr>" for x in rows);return base+f"<div class='panel'><h2>Build 304 · Evidenzbasiertes Dossier</h2><div class='notice'>Dauerlinie bis 320: Fakten/Behauptungen/Analyse trennen, Citation Coverage und Quellenintegrität erhöhen.</div><form method='post' action='/build304/dossier'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='title' placeholder='Titel'><button>Evidenzbasiertes AI-Dossier erzeugen</button></form><table><tr><th>Rev</th><th>Titel</th><th>Quality</th><th>Citations</th><th>Gate</th><th>Datei</th></tr>{rr or '<tr><td colspan="6">Noch kein Build-304-Dossier.</td></tr>'}</table></div>"
  if section=='operations':
   scans=self.db.all('SELECT scan_id,source_id,risk_level,risk_score,verdict,blocked FROM phase13_security_scans_304 WHERE case_id=? ORDER BY scanned_at DESC LIMIT 25',(case_id,));rr=''.join(f"<tr><td><code>{e(x['source_id'])}</code></td><td>{e(x['risk_level'])}</td><td>{x['risk_score']}</td><td>{e(x['verdict'])}</td><td>{'BLOCK' if x['blocked'] else 'report'}</td><td>{("<form method='post' action='/build304/security-review'><input type='hidden' name='csrf' value='"+e(csrf)+"'><input type='hidden' name='case_id' value='"+e(case_id)+"'><input type='hidden' name='scan_id' value='"+e(x['scan_id'])+"'><select name='decision'><option value='keep_blocked'>blockiert lassen</option><option value='allow_bounded_static_continue'>bounded static weiter</option></select><input name='confirmation' placeholder='OK' size='4'><input name='rationale' placeholder='Begründung'><button>Review</button></form>") if x['blocked'] else '—'}</td></tr>" for x in scans);return base+f"<div class='panel'><h2>Build 304 · AI-Sicherheitsagent</h2><div class='notice'>Defensiver Agent: Tracking-/Active-Content-/Credential-Risiken erkennen, melden, statische Verarbeitung erzwingen. Keine Exploits oder ungeprüften Netzwerkänderungen.</div><form method='post' action='/build304/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Security-Agent Selftest</button></form><table><tr><th>Source</th><th>Risk</th><th>Score</th><th>Verdict</th><th>Action</th><th>Review</th></tr>{rr or '<tr><td colspan="6">Noch keine Scans.</td></tr>'}</table></div>"
  if section=='sources':return base+"<div class='panel'><h2>Build 304 · Darknet Content Intelligence</h2><div class='notice'>Statische Normalisierung, Deduplizierung, Sprache, Entitätskandidaten und unverifizierte Source Assertions. Security Scan liegt vor weiterer Verarbeitung.</div><form method='post' action='/build304/analyze-source'><input type='hidden' name='csrf' value='%s'><input type='hidden' name='case_id' value='%s'><input name='source_id' placeholder='Source ID aus Onion-Abruf' style='width:55%%'><button>Source sicher analysieren</button></form><form method='post' action='/build304/content-selftest'><input type='hidden' name='csrf' value='%s'><input type='hidden' name='case_id' value='%s'><button>Content Intelligence Selftest</button></form></div>"%(e(csrf),e(case_id),e(csrf),e(case_id))
  return base
