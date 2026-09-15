from __future__ import annotations
import hashlib,html,json,uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from eagleeye.infrastructure.build301.tor_gateway import TorReadOnlyGateway

def _now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p):return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256((v if isinstance(v,str) else _canon(v)).encode()).hexdigest()

class Build302TorHardeningSimplifiedUIService:
 BUILD='302.0'; REQUIRED_CORPUS=392; GATE_THRESHOLD=.92; CRITICAL_TRACK_THRESHOLD=.88
 PRIMARY_NAV=(
  ('cockpit302','Cockpit'),('investigation302','AI-Ermittlung'),('evidence302','Evidenz & Daten'),('sources302','Quellen & Darknet'),
  ('analysis302','Graph & Timeline'),('operations302','OPSEC & Betrieb'),('reports302','Dossiers & Reports'),('expert302','Expert Tools')
 )
 AI_MANAGED=(
  'Research Strategy','AI Research/Dossier','AI Execution/Timeline','Hypothesis/OPSEC','Gaps/Collection','Source Independence',
  'Reasoning Ledger','Co-Analyst Agents','Red-Team Analyst','AI Investigation Depth','Discriminating Evidence','Adaptive Orchestration','Cross-Surface Fusion'
 )
 def __init__(self,db:Any,audit:Any,*,cases:Any,build301:Any,install_dir:Path,base_dir:Path,actor='local-analyst'):
  self.db=db; self.audit=audit; self.cases=cases; self.build301=build301; self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor
 def navigation_model(self):
  groups={
   'AI-Ermittlung':['Workflow','Case Intelligence','Task Graph','AI Research/Dossier','AI Execution/Timeline','Hypothesis','ACH','Gaps/Collection','Source Independence','Reasoning','Co-Analyst Agents','Red-Team','AI Investigation Depth','Discriminating Evidence','Adaptive Orchestration','Cross-Surface Fusion'],
   'Evidenz & Daten':['People','Evidence','Documents','Entity Resolution','Claims/Sources','Cross-Case Knowledge'],
   'Quellen & Darknet':['German Sources','Global Sources','Direct Tor 301','Controlled Collection','Gateway/Capture/Replay'],
   'Graph & Timeline':['Graph','Timeline','Temporal','Network','Paths','Narrative Diffusion'],
   'OPSEC & Betrieb':['Monitoring','AI Runtime','Mission Queue','Mission Integrity','Failure Containment','Operational Strength/Resilience/Continuity','Field Qualification'],
   'Dossiers & Reports':['Publication/Legal','Intelligence Product','Reports','Release/Qualification'],
   'Expert Tools':['historical build panels','specialist diagnostics','release internals','manual compatibility modules']
  }
  return {'visible_before':65,'visible_after':len(self.PRIMARY_NAV),'reduction_pct':round((1-len(self.PRIMARY_NAV)/65)*100,1),'primary_nav':list(self.PRIMARY_NAV),'groups':groups,'ai_managed_modules':list(self.AI_MANAGED),'ai_managed_count':len(self.AI_MANAGED),'expert_only_count':65-len(self.PRIMARY_NAV)}
 def record_navigation_audit(self,actor=None):
  actor=actor or self.actor; m=self.navigation_model(); aid=_id('nav302'); now=_now(); payload={'audit_id':aid,**m,'actor':actor,'created_at':now}; self.db.execute('INSERT INTO phase13_navigation_audits_302 VALUES(?,?,?,?,?,?,?,?,?)',(aid,m['visible_before'],m['visible_after'],m['ai_managed_count'],m['expert_only_count'],_canon(m['groups']),actor,now,_hash(payload))); return payload
 def transport_policy(self):
  return {'proxy_loopback_only':True,'dns_resolution_via_socks_domain':True,'fresh_tcp_connection_per_request':True,'connection_pooling':False,'cookie_jar':False,'referrer':False,'credentials':False,'forms':False,'uploads':False,'contact':False,'binary_execution':False,'method':'GET','accept_encoding':'identity','same_onion_host_redirects_only':True,'max_redirects_cap':3,'max_response_bytes_cap':2*1024*1024,'clearnet_fallback':False,'fail_closed_on_proxy_error':True}
 def run_transport_hardening_selftest(self,actor=None):
  actor=actor or self.actor; parent=self.build301.run_protocol_selftest(actor=actor); loopback_rejected=False
  try:TorReadOnlyGateway('8.8.8.8',9050)
  except Exception:loopback_rejected=True
  policy=self.transport_policy(); controls={**policy,'non_loopback_proxy_rejected':loopback_rejected,'parent_socks5_domain_selftest':parent['result']=='pass'}
  ok=(controls['proxy_loopback_only'] and controls['dns_resolution_via_socks_domain'] and controls['fresh_tcp_connection_per_request'] and not controls['connection_pooling'] and not controls['cookie_jar'] and not controls['referrer'] and not controls['credentials'] and not controls['clearnet_fallback'] and controls['fail_closed_on_proxy_error'] and loopback_rejected and parent['result']=='pass')
  metrics={'parent_target_host':parent['metrics']['target_host'],'parent_http_status':parent['metrics']['http_status'],'primary_navigation_items':len(self.PRIMARY_NAV),'navigation_items_before':65}
  rid=_id('transport302'); now=_now(); result='pass' if ok else 'fail'; payload={'attestation_id':rid,'result':result,'controls':controls,'metrics':metrics,'actor':actor,'created_at':now}; self.db.execute('INSERT INTO phase13_transport_attestations_302 VALUES(?,?,?,?,?,?,?)',(rid,result,_canon(controls),_canon(metrics),actor,now,_hash(payload))); self.record_navigation_audit(actor); return payload
 def hardened_fetch_mission(self,mission_id,actor=None):
  actor=actor or self.actor; m=self.db.one('SELECT * FROM phase13_tor_missions_301 WHERE mission_id=?',(mission_id,));
  if not m:raise KeyError('mission not found')
  approval=self.db.one('SELECT * FROM phase13_tor_approvals_301 WHERE mission_id=?',(mission_id,))
  controls=self.transport_policy(); ok=bool(approval) and m['allowed_methods_json']==_canon(['GET']) and int(m['max_redirects'])<=3 and int(m['max_bytes'])<=2*1024*1024
  pid=_id('preflight302'); now=_now(); payload={'preflight_id':pid,'mission_id':mission_id,'result':'pass' if ok else 'blocked','controls':controls,'actor':actor,'created_at':now}; self.db.execute('INSERT INTO phase13_hardened_fetch_preflights_302 VALUES(?,?,?,?,?,?,?)',(pid,mission_id,payload['result'],_canon(controls),actor,now,_hash(payload)))
  if not approval:raise PermissionError('mission requires exact investigator OK before hardened Tor fetch')
  if not ok:raise PermissionError('Build 302 transport preflight blocked this mission')
  return self.build301.fetch_mission(mission_id,actor=actor)
 def startup_contract_status(self):
  import eagleeye_pro.version as v
  text=(self.install_dir/'START_EAGLEEYE_PRO.bat').read_text(encoding='utf-8',errors='replace') if (self.install_dir/'START_EAGLEEYE_PRO.bat').exists() else ''
  def _at_least(x):
   try:return tuple(int(p) for p in str(x).split('.')[:2]) >= (302,0)
   except Exception:return False
  checks={'version_build_at_least_302':_at_least(v.BUILD),'version_schema_at_least_302':_at_least(v.SCHEMA_VERSION),'historical_entrypoint':(self.install_dir/'EAGLEEYE_PRO_302_0.py').exists(),'startup_script':(self.install_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_302_0.py').exists(),'versioned_launcher':(self.install_dir/'START_EAGLEEYE_PRO_302_0.bat').exists()}; return {'build':'302.0','checks':checks,'contract_ready':all(checks.values()),'actual_packaged_boot_required':True}
 def all_training_cases(self):
  out=self.build301.all_training_cases()
  for r in self.db.all("SELECT * FROM ai_hard_training_delta_302 WHERE review_status='reviewed' ORDER BY benchmark_id"):out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
  return out
 def training_metrics(self):
  b=self.build301.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_302 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_302 WHERE review_status='reviewed' AND difficulty='extreme'")['n']); return {'reviewed_hard_cases':int(b['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(b['adversarial_extreme_cases'])+e,'build302_delta_cases':d,'build302_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'critical_track_threshold':self.CRITICAL_TRACK_THRESHOLD,'automatic_model_activation':False}
 def create_evaluation_batch(self,model_label='mistral:latest',actor=None):
  actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'302.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':.92,'critical_track_minimum':.88,'maximum_critical_failures':0,'independent_evaluator_required':True,'cases':cases}; sha=_hash(manifest); ex=self.db.one('SELECT * FROM ai_evaluation_batches_302 WHERE model_label=? AND manifest_sha256=?',(model_label,sha))
  if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'critical_track_minimum':float(ex['critical_threshold']),'deduplicated':True}
  bid=_id('eval302'); now=_now(); payload={'batch_id':bid,**manifest,'created_by':actor,'created_at':now}; self.db.execute('INSERT INTO ai_evaluation_batches_302 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),.92,.88,1.0,0,'prepared',1,sha,actor,now,_hash(payload))); return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':.92,'critical_track_minimum':.88,'deduplicated':False}
 def performance_status(self,model_label='mistral:latest'):return {'model_label':model_label,'status':'not_run','qualified':False,'required_corpus_size':392,'minimum_mean_score':.92,'critical_track_minimum':.88,'note':'No model-performance claim without full independent 392-case run.'}
 def qualified_gate(self):
  tm=self.training_metrics(); batch=self.create_evaluation_batch(); st=self.db.one("SELECT * FROM phase13_transport_attestations_302 WHERE result='pass' ORDER BY rowid DESC LIMIT 1"); nav=self.navigation_model(); startup=self.startup_contract_status(); parent=self.build301.qualified_gate()
  g={'build':'302.0','parent_301_gate':parent['release_ready'],'transport_hardening_selftest':bool(st),'navigation_primary_8':nav['visible_after']==8,'navigation_reduction_gt_80pct':nav['reduction_pct']>80,'ai_workflow_consolidated':nav['ai_managed_count']>=10,'training_corpus_392':tm['reviewed_hard_cases']==392 and tm['build302_delta_cases']==16 and tm['build302_delta_extreme']==4,'evaluation_batch_392_ready':batch['corpus_size']==392,'startup_contract_ready':startup['contract_ready'],'clearnet_fallback':False,'credential_automation':False,'automatic_external_interaction':False,'automatic_model_activation':False,'production_certification_claimed':False}
  g['release_ready']=all((g['parent_301_gate'],g['transport_hardening_selftest'],g['navigation_primary_8'],g['navigation_reduction_gt_80pct'],g['ai_workflow_consolidated'],g['training_corpus_392'],g['evaluation_batch_392_ready'],g['startup_contract_ready'],not g['clearnet_fallback'],not g['credential_automation'],not g['automatic_external_interaction'],not g['automatic_model_activation'],not g['production_certification_claimed'])); return g
 def _count(self,sql,args=()):
  try:return int((self.db.one(sql,args) or {}).get('n') or 0)
  except Exception:return 0
 def investigation_status(self,case_id):
  return {'assessments':self._count('SELECT COUNT(*) n FROM phase12_case_assessments_289 WHERE case_id=?',(case_id,)),'plans':self._count('SELECT COUNT(*) n FROM phase12_discriminating_plans_290 WHERE case_id=?',(case_id,)),'adaptive_rounds':self._count('SELECT COUNT(*) n FROM phase12_adaptive_rounds_291 WHERE case_id=?',(case_id,)),'fusions':self._count('SELECT COUNT(*) n FROM phase12_cross_surface_fusions_292 WHERE case_id=?',(case_id,)),'tor_sources':self._count('SELECT COUNT(*) n FROM phase13_source_records_301 WHERE case_id=?',(case_id,))}
 def _a(self,tab,case_id,label,desc=''):
  e=lambda v:html.escape(str(v or ''),quote=True); return f"<a class='action-card' href='/?tab={e(tab)}&amp;case_id={e(case_id)}'><b>{e(label)}</b>{('<br><span class=\"muted\">'+e(desc)+'</span>') if desc else ''}</a>"
 def render_workspace_panel(self,case_id,csrf,section='cockpit'):
  e=lambda v:html.escape(str(v or ''),quote=True); nav=self.navigation_model(); inv=self.investigation_status(case_id); tor=self.build301.gateway_status(); tm=self.training_metrics()
  if section=='cockpit':
   return f"<div class='notice'><b>Was ist der Stand?</b><br>Build 302 reduziert die Hauptnavigation von {nav['visible_before']} auf <b>{nav['visible_after']}</b> Arbeitsbereiche ({nav['reduction_pct']} % weniger sichtbare Punkte).<br><br><b>Was bedeutet das?</b><br>Routine-Schritte der AI-Ermittlung werden nicht mehr als eigene Menüfolge präsentiert. Der Ermittler arbeitet primär aus AI-Ermittlung, Evidenz/Daten, Quellen/Darknet, Analyse, Betrieb und Reports.<br><br><b>Was ist jetzt zu tun?</b><br>Fallziel in <b>AI-Ermittlung</b> bearbeiten; nur für Spezialdiagnostik zu Expert Tools wechseln.</div><div class='metrics'><div class='metric'><div class='label'>Primärnavigation</div><div class='value'>8</div></div><div class='metric'><div class='label'>AI-intern gebündelt</div><div class='value'>{nav['ai_managed_count']}</div></div><div class='metric'><div class='label'>Tor Gateway</div><div class='value'>{'READY' if tor['status']=='ready' else 'WAIT'}</div></div><div class='metric'><div class='label'>AI Hard-Cases</div><div class='value'>{tm['reviewed_hard_cases']}</div></div></div><div class='panel'><h2>Direkter Workflow</h2><div class='actions'>{self._a('investigation302',case_id,'1 · AI-Ermittlung','Ziel, nächste Evidenzfrage, Research Waves, Human Gate')}{self._a('sources302',case_id,'2 · Quellen & Darknet','Web/Register/Tor als Ermittlungsarme')}{self._a('evidence302',case_id,'3 · Evidenz & Daten','Dokumente, Claims, Entitäten, Provenienz')}{self._a('analysis302',case_id,'4 · Graph & Timeline','Beziehungen, Zeitachsen, Widersprüche')}{self._a('reports302',case_id,'5 · Dossier','Ergebnis und offene Punkte')}</div></div>"
  if section=='investigation':
   return f"<div class='notice'><b>AI-Ermittlung ist jetzt der zentrale Arbeitsbereich.</b><br>Die AI-interne Klickstrecke Research → Execution → Hypothesis → Collection Gaps → Source Independence → Reasoning → Adaptive/Fusion ist hier logisch zusammengeführt. Externe Sammlung und Autoritätsgrenzen bleiben freigabepflichtig.</div><div class='metrics'><div class='metric'><div class='label'>Assessments</div><div class='value'>{inv['assessments']}</div></div><div class='metric'><div class='label'>Evidenzpläne</div><div class='value'>{inv['plans']}</div></div><div class='metric'><div class='label'>Adaptive Runden</div><div class='value'>{inv['adaptive_rounds']}</div></div><div class='metric'><div class='label'>Fusionsstände</div><div class='value'>{inv['fusions']}</div></div></div><div class='panel'><h2>Schnellaktionen</h2><div class='actions'><form class='card' method='post' action='/build302/ai-assess'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><b>Fallstruktur aktualisieren</b><p class='muted'>AI erkennt Evidenzlücken und priorisiert offene Fragen.</p><button>AI-Strukturprüfung</button></form><form class='card' method='post' action='/build302/ai-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><b>Evidenzstrategie aktualisieren</b><p class='muted'>AI priorisiert diskriminierende Evidenz statt Quellenlisten manuell abzuarbeiten.</p><button>Evidenzplan erstellen</button></form><form class='card' method='post' action='/build302/ai-adapt'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><b>Adaptive Runde</b><p class='muted'>Neue Evidenz verändert automatisch die Reihenfolge der offenen Fragen.</p><button>Neu priorisieren</button></form><form class='card' method='post' action='/build302/ai-fuse'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><b>Cross-Surface Fusion</b><p class='muted'>Evidenzflächen zusammenführen, ohne Provenienz zu glätten.</p><button>Fusion aktualisieren</button></form></div></div><details><summary>Manuelle Spezialmodule</summary><div class='actions'>{self._a('research263',case_id,'Research/Dossier')}{self._a('execution264',case_id,'Execution/Timeline')}{self._a('hypothesis268',case_id,'Hypothesis')}{self._a('collection270',case_id,'Collection Gaps')}{self._a('source271',case_id,'Source Independence')}{self._a('reasoning275',case_id,'Reasoning Ledger')}{self._a('agents276',case_id,'Co-Analyst Agents')}{self._a('redteam277',case_id,'Red-Team')}</div></details>"
  if section=='evidence':return f"<div class='notice'>Alles, was die AI recherchiert, muss hier auf Evidenz, Entität, Claim und Provenienz zurückführbar bleiben.</div><div class='actions'>{self._a('evidence244',case_id,'Evidence Vault')}{self._a('documents255',case_id,'Dokumente')}{self._a('documents273',case_id,'Document Corpus')}{self._a('entities256',case_id,'Entity Resolution')}{self._a('claims258',case_id,'Claims & Sources')}{self._a('knowledge274',case_id,'Cross-Case Knowledge')}</div>"
  if section=='sources':
   return f"<div class='notice'><b>Tor/OPSEC:</b> {e(tor['status'])}. Build 302 erzwingt Loopback-SOCKS, SOCKS-Domainauflösung, frische Verbindungen, keine Cookies/Referrer/Auth und keinen Clearnet-Fallback.</div><div class='actions'>{self._a('phase13_301',case_id,'Darknet / Direct Tor','Onion-Missionen und Raw Source Records')}{self._a('sources253',case_id,'Deutsche Quellen')}{self._a('sources254',case_id,'Globale Quellen')}{self._a('documents273',case_id,'Dokumentkorpus')}</div><div class='panel'><h2>Build-302 Transport Attestation</h2><form method='post' action='/build302/selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Hardening-Selftest ausführen</button></form></div>"
  if section=='analysis':return f"<div class='actions'>{self._a('graph244',case_id,'Graph')}{self._a('timeline244',case_id,'Timeline')}{self._a('temporal265',case_id,'Temporal Intelligence')}{self._a('network266',case_id,'Network')}{self._a('paths267',case_id,'Paths')}{self._a('narrative272',case_id,'Narrative Diffusion')}</div>"
  if section=='operations':return f"<div class='notice'>Betriebstechnische Zwischenstufen sind aus dem normalen Recherchepfad entfernt. Sie bleiben für Recovery/OPSEC sichtbar, wenn ein Zustand Aufmerksamkeit verlangt.</div><div class='actions'>{self._a('opsec244',case_id,'OPSEC')}{self._a('phase12_293',case_id,'Queue & Worker')}{self._a('phase12_294',case_id,'Resilience')}{self._a('phase12_295',case_id,'Backup & Continuity')}{self._a('phase12_296',case_id,'Operational Freeze')}{self._a('monitor246',case_id,'Monitoring')}</div>"
  if section=='reports':return f"<div class='actions'>{self._a('reports244',case_id,'Reports')}{self._a('product278',case_id,'Intelligence Product')}{self._a('publication259',case_id,'Publication / Legal')}{self._a('qualification279',case_id,'Full Case Qualification')}</div>"
  # expert
  groups=[('Legacy/Phase 10','workflow245 monitor246 runtime247 production248 stress249 influence251 finance252 sources253 sources254 documents255 entities256 framing257 claims258 publication259 qualification260'.split()),('AI/Phase 11','caseintelligence261 taskgraph262 research263 execution264 temporal265 network266 paths267 hypothesis268 ach269 collection270 source271 narrative272 documents273 knowledge274 reasoning275 agents276 redteam277 product278 qualification279 release280'.split()),('Phase 12',' '.join(f'phase12_{n}' for n in range(281,301)).split()),('Phase 13','phase13_301'.split())]
  labels={}
  for key,label in [('phase13_301','Direct Tor 301')]:labels[key]=label
  blocks=[]
  for title,keys in groups:
   links=''.join(self._a(k,case_id,labels.get(k,k.replace('_',' '))) for k in keys); blocks.append(f"<details><summary>{e(title)}</summary><div class='actions'>{links}</div></details>")
  return f"<div class='notice warn'>Expert Tools sind absichtlich nicht Teil des normalen Recherchepfads. Sie bleiben für Diagnose, manuelle Spezialanalyse, Regression und historische Funktionen erreichbar.</div>{''.join(blocks)}<details><summary>Navigation Audit</summary><pre>{e(_canon(nav))}</pre></details>"
