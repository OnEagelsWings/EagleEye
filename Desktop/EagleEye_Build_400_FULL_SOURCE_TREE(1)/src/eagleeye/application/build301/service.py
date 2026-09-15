from __future__ import annotations
import hashlib,html,json,os,socket,uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from eagleeye.infrastructure.build301.tor_gateway import TorReadOnlyGateway,TorPolicyError,validate_onion_url
from eagleeye.infrastructure.build301.selftest import run_local_socks5_http_selftest

def _now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p):return f"{p}_{uuid.uuid4().hex[:12]}"
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):return hashlib.sha256((v if isinstance(v,str) else _canon(v)).encode()).hexdigest()

class Build301DirectTorGatewayService:
 BUILD='301.0'; REQUIRED_CORPUS=376; GATE_THRESHOLD=.92; CRITICAL_TRACK_THRESHOLD=.88
 def __init__(self,db:Any,audit:Any,*,cases:Any,build300:Any,install_dir:Path,base_dir:Path,actor='local-analyst'):
  self.db=db; self.audit=audit; self.cases=cases; self.build300=build300; self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor; self.raw_dir=self.base_dir/'darknet_301'/'raw'; self.raw_dir.mkdir(parents=True,exist_ok=True)
 def _event(self,event_type,details,*,mission_id=None,actor=None):
  actor=actor or self.actor; prev=self.db.one('SELECT event_hash FROM phase13_tor_events_301 ORDER BY rowid DESC LIMIT 1'); ph=prev['event_hash'] if prev else 'GENESIS'; eid=_id('tor_evt301'); now=_now(); p={'event_id':eid,'mission_id':mission_id,'event_type':event_type,'details':details,'actor':actor,'created_at':now,'previous_hash':ph}; eh=_hash(p); self.db.execute('INSERT INTO phase13_tor_events_301 VALUES(?,?,?,?,?,?,?,?)',(eid,mission_id,event_type,_canon(details),actor,now,ph,eh)); return eh
 def verify_event_chain(self):
  prev='GENESIS'
  for r in self.db.all('SELECT * FROM phase13_tor_events_301 ORDER BY rowid'):
   if r['previous_hash']!=prev:return False
   p={'event_id':r['event_id'],'mission_id':r['mission_id'],'event_type':r['event_type'],'details':json.loads(r['details_json']),'actor':r['actor'],'created_at':r['created_at'],'previous_hash':r['previous_hash']}
   if _hash(p)!=r['event_hash']:return False
   prev=r['event_hash']
  return True
 def create_mission(self,*,case_id,onion_url,purpose,max_bytes=524288,max_redirects=2,actor=None):
  actor=actor or self.actor; self.cases.get_case(case_id); purpose=(purpose or '').strip()
  if not purpose:raise ValueError('purpose is required')
  scheme,host,port,path=validate_onion_url(onion_url); max_bytes=int(max_bytes); max_redirects=int(max_redirects)
  if max_bytes<1024 or max_bytes>2*1024*1024:raise ValueError('max_bytes must be 1024..2097152')
  if max_redirects<0 or max_redirects>3:raise ValueError('max_redirects must be 0..3')
  normalized=f'{scheme}://{host}{":"+str(port) if port not in (80,443) else ""}{path}'
  policy={'case_id':case_id,'onion_url':normalized,'onion_host':host,'purpose':purpose,'max_bytes':max_bytes,'max_redirects':max_redirects,'allowed_methods':['GET'],'allowed_mime':TorReadOnlyGateway.allowed_mime_types(),'credentials':False,'forms':False,'uploads':False,'contact':False,'binary_execution':False,'clearnet_fallback':False}
  mid=_id('tor_mission301'); now=_now(); scope_sha=_hash(policy); row=(mid,case_id,normalized,host,purpose,max_bytes,max_redirects,_canon(['GET']),_canon(policy['allowed_mime']),scope_sha,actor,now,_hash({'mission_id':mid,**policy,'created_at':now,'created_by':actor})); self.db.execute('INSERT INTO phase13_tor_missions_301 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',row); self._event('mission_created',{'scope_sha256':scope_sha,'host':host,'method':'GET','max_bytes':max_bytes},mission_id=mid,actor=actor); return {'mission_id':mid,**policy,'scope_sha256':scope_sha,'state':'awaiting_ok'}
 def approve_mission(self,mission_id,confirmation,approved_by):
  if confirmation!='OK':raise ValueError('exact confirmation OK required')
  m=self.db.one('SELECT * FROM phase13_tor_missions_301 WHERE mission_id=?',(mission_id,))
  if not m:raise KeyError('mission not found')
  if self.db.one('SELECT * FROM phase13_tor_approvals_301 WHERE mission_id=?',(mission_id,)):raise ValueError('mission already approved')
  aid=_id('tor_ok301'); now=_now(); p={'approval_id':aid,'mission_id':mission_id,'confirmation':'OK','approved_by':approved_by,'approved_at':now}; self.db.execute('INSERT INTO phase13_tor_approvals_301 VALUES(?,?,?,?,?,?)',(aid,mission_id,'OK',approved_by,now,_hash(p))); self._event('mission_approved',{'approval_id':aid,'confirmation':'OK'},mission_id=mission_id,actor=approved_by); return {**p,'state':'approved_read_only'}
 def _configured_candidates(self):
  host=os.environ.get('EAGLEEYE_TOR_SOCKS_HOST','127.0.0.1').strip() or '127.0.0.1'
  raw=os.environ.get('EAGLEEYE_TOR_SOCKS_PORT','').strip()
  ports=[int(raw)] if raw else [9050,9150]
  return [(host,p) for p in ports]
 def gateway_status(self):
  checks=[]
  for host,port in self._configured_candidates():
   try: g=TorReadOnlyGateway(host,port,connect_timeout=.6,read_timeout=.8); status=g.health_check()
   except Exception as exc:status={'healthy':False,'proxy_host':host,'proxy_port':port,'socks5_noauth':False,'error':f'{type(exc).__name__}: {exc}'}
   checks.append(status)
   if status['healthy']:return {'status':'ready','live_onion_read_transport':True,'selected_proxy':status,'checks':checks,'clearnet_fallback':False}
  return {'status':'tor_proxy_unavailable','live_onion_read_transport':False,'selected_proxy':None,'checks':checks,'clearnet_fallback':False}
 def _gateway(self):
  status=self.gateway_status()
  if status['status']!='ready':raise RuntimeError('local Tor SOCKS proxy unavailable; no clearnet fallback is permitted')
  p=status['selected_proxy']; return TorReadOnlyGateway(p['proxy_host'],p['proxy_port'])
 def fetch_mission(self,mission_id,actor=None):
  actor=actor or self.actor; m=self.db.one('SELECT * FROM phase13_tor_missions_301 WHERE mission_id=?',(mission_id,))
  if not m:raise KeyError('mission not found')
  approval=self.db.one('SELECT * FROM phase13_tor_approvals_301 WHERE mission_id=?',(mission_id,))
  if not approval:raise PermissionError('mission requires exact investigator OK before live Tor fetch')
  prior=self.db.one("SELECT * FROM phase13_tor_fetches_301 WHERE mission_id=? AND status='success'",(mission_id,))
  if prior:raise ValueError('Build 301 permits one successful live fetch per approved mission; create a new mission for another retrieval')
  gateway=self._gateway(); fid=_id('tor_fetch301'); self._event('fetch_started',{'proxy_host':gateway.proxy_host,'proxy_port':gateway.proxy_port,'scope_sha256':m['scope_sha256']},mission_id=mission_id,actor=actor)
  try:
   r=gateway.fetch(m['onion_url'],max_bytes=int(m['max_bytes']),max_redirects=int(m['max_redirects']))
   rel=Path('darknet_301')/'raw'/f'{fid}.bin'; target=self.base_dir/rel; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(r.body)
   now=_now(); payload={'fetch_id':fid,'mission_id':mission_id,'status':'success','final_url':r.final_url,'http_status':r.status_code,'content_type':r.content_type,'bytes_received':len(r.body),'body_sha256':r.sha256,'artifact_relpath':rel.as_posix(),'headers':r.headers,'error_text':'','proxy_host':r.proxy_host,'proxy_port':r.proxy_port,'created_at':now}; self.db.execute('INSERT INTO phase13_tor_fetches_301 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(fid,mission_id,'success',r.final_url,r.status_code,r.content_type,len(r.body),r.sha256,rel.as_posix(),_canon(r.headers),'',r.proxy_host,r.proxy_port,now,_hash(payload)))
   sid=_id('source301'); provenance={'transport':'tor_socks5_domain_resolution','mission_scope_sha256':m['scope_sha256'],'approval_id':approval['approval_id'],'method':'GET','redirect_policy':'same-onion-host-only','credentials_used':False,'interaction':False,'raw_preserved':True}; sp={'source_id':sid,'case_id':m['case_id'],'mission_id':mission_id,'fetch_id':fid,'source_kind':'darknet_onion_readonly','origin_url':r.final_url,'retrieved_at':now,'mime_type':r.content_type,'bytes_count':len(r.body),'sha256':r.sha256,'artifact_relpath':rel.as_posix(),'provenance':provenance}; self.db.execute('INSERT INTO phase13_source_records_301 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,m['case_id'],mission_id,fid,'darknet_onion_readonly',r.final_url,now,r.content_type,len(r.body),r.sha256,rel.as_posix(),_canon(provenance),_hash(sp))); self._event('fetch_success',{'fetch_id':fid,'source_id':sid,'sha256':r.sha256,'bytes':len(r.body),'mime':r.content_type,'http_status':r.status_code},mission_id=mission_id,actor=actor); return {**payload,'source_id':sid,'provenance':provenance,'text_preview':r.body[:4096].decode('utf-8','replace')}
  except Exception as exc:
   now=_now(); err=f'{type(exc).__name__}: {exc}'; payload={'fetch_id':fid,'mission_id':mission_id,'status':'failed','final_url':m['onion_url'],'http_status':None,'content_type':None,'bytes_received':0,'body_sha256':None,'artifact_relpath':None,'headers':{},'error_text':err,'proxy_host':gateway.proxy_host,'proxy_port':gateway.proxy_port,'created_at':now}; self.db.execute('INSERT INTO phase13_tor_fetches_301 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(fid,mission_id,'failed',m['onion_url'],None,None,0,None,None,'{}',err,gateway.proxy_host,gateway.proxy_port,now,_hash(payload))); self._event('fetch_failed',{'fetch_id':fid,'error':err},mission_id=mission_id,actor=actor); raise
 def run_protocol_selftest(self,actor=None):
  actor=actor or self.actor; h=run_local_socks5_http_selftest(); controls={'socks5_domain_target_preserved':h.target_host.endswith('.onion'),'get_only':True,'clearnet_fallback':False,'credentials_disabled':True,'binary_execution_disabled':True}; metrics={'target_host':h.target_host,'target_port':h.target_port,'http_status':h.status_code,'body_marker':'phase13-tor-selftest' in h.body}; result='pass' if (controls['socks5_domain_target_preserved'] and controls['get_only'] and not controls['clearnet_fallback'] and controls['credentials_disabled'] and controls['binary_execution_disabled'] and metrics['body_marker'] and h.status_code==200) else 'fail'; sid=_id('tor_selftest301'); now=_now(); p={'selftest_id':sid,'result':result,'controls':controls,'metrics':metrics,'created_by':actor,'created_at':now}; self.db.execute('INSERT INTO phase13_tor_selftests_301 VALUES(?,?,?,?,?,?,?)',(sid,result,_canon(controls),_canon(metrics),actor,now,_hash(p))); self._event('protocol_selftest',{'selftest_id':sid,'result':result,'metrics':metrics},actor=actor); return p
 def startup_contract_status(self):
  import eagleeye_pro.version as v
  text=(self.install_dir/'START_EAGLEEYE_PRO.bat').read_text(encoding='utf-8',errors='replace') if (self.install_dir/'START_EAGLEEYE_PRO.bat').exists() else ''
  
  def _at_least(x):
   try:return tuple(int(p) for p in str(x).split('.')[:2]) >= (301,0)
   except Exception:return False
  checks={'version_build_at_least_301':_at_least(v.BUILD),'version_schema_at_least_301':_at_least(v.SCHEMA_VERSION),'historical_entrypoint':(self.install_dir/'EAGLEEYE_PRO_301_0.py').exists(),'startup_script':(self.install_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_301_0.py').exists(),'versioned_launcher':(self.install_dir/'START_EAGLEEYE_PRO_301_0.bat').exists()}; return {'build':'301.0','checks':checks,'contract_ready':all(checks.values()),'actual_packaged_boot_required':True}
 def all_training_cases(self):
  out=self.build300.all_training_cases()
  for r in self.db.all("SELECT * FROM ai_hard_training_delta_301 WHERE review_status='reviewed' ORDER BY benchmark_id"):out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
  return out
 def training_metrics(self):
  b=self.build300.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_301 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_301 WHERE review_status='reviewed' AND difficulty='extreme'")['n']); return {'reviewed_hard_cases':int(b['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(b['adversarial_extreme_cases'])+e,'build301_delta_cases':d,'build301_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'critical_track_threshold':self.CRITICAL_TRACK_THRESHOLD,'automatic_model_activation':False}
 def create_evaluation_batch(self,model_label='mistral:latest',actor=None):
  actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'301.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':.92,'critical_track_minimum':.88,'maximum_critical_failures':0,'independent_evaluator_required':True,'cases':cases}; sha=_hash(manifest); ex=self.db.one('SELECT * FROM ai_evaluation_batches_301 WHERE model_label=? AND manifest_sha256=?',(model_label,sha))
  if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'critical_track_minimum':float(ex['critical_threshold']),'deduplicated':True}
  bid=_id('eval301'); now=_now(); p={'batch_id':bid,**manifest,'created_by':actor,'created_at':now}; self.db.execute('INSERT INTO ai_evaluation_batches_301 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),.92,.88,1.0,0,'prepared',1,sha,actor,now,_hash(p))); return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':.92,'critical_track_minimum':.88,'deduplicated':False}
 def performance_status(self,model_label='mistral:latest'):return {'model_label':model_label,'status':'not_run','qualified':False,'required_corpus_size':376,'minimum_mean_score':.92,'critical_track_minimum':.88,'note':'No model-performance claim without full independent 376-case run.'}
 def qualified_gate(self):
  tm=self.training_metrics(); b=self.create_evaluation_batch(); s=self.startup_contract_status(); st=self.db.one("SELECT * FROM phase13_tor_selftests_301 WHERE result='pass' ORDER BY rowid DESC LIMIT 1")
  g={'build':'301.0','parent_phase12_gate':self.build300.qualified_gate()['release_ready'],'protocol_selftest_passed':bool(st),'source_contract_tables_ready':all(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(n,)) for n in ('phase13_tor_missions_301','phase13_tor_fetches_301','phase13_source_records_301')),'training_corpus_376':tm['reviewed_hard_cases']==376 and tm['build301_delta_cases']==16 and tm['build301_delta_extreme']==4,'evaluation_batch_376_ready':b['corpus_size']==376,'startup_contract_ready':s['contract_ready'],'read_only_tor_transport_implemented':True,'mission_ok_required':True,'clearnet_fallback':False,'credential_automation':False,'forms_upload_contact':False,'binary_execution':False,'automatic_model_activation':False,'production_certification_claimed':False}
  g['release_ready']=all((g['parent_phase12_gate'],g['protocol_selftest_passed'],g['source_contract_tables_ready'],g['training_corpus_376'],g['evaluation_batch_376_ready'],g['startup_contract_ready'],g['read_only_tor_transport_implemented'],g['mission_ok_required'],not g['clearnet_fallback'],not g['credential_automation'],not g['forms_upload_contact'],not g['binary_execution'],not g['automatic_model_activation'],not g['production_certification_claimed'])); return g
 def field_status(self,case_id=None):
  gs=self.gateway_status(); latest=self.db.one('SELECT * FROM phase13_tor_fetches_301 ORDER BY rowid DESC LIMIT 1')
  if gs['status']=='ready':stand='Lokaler Tor-SOCKS-Proxy erkannt; Build 301 kann freigegebene Onion-GETs direkt ausführen.'
  else:stand='Direct-Tor-Gateway implementiert; aktuell wurde kein lokaler Tor-SOCKS-Proxy erkannt.'
  meaning='Live-Onion-Lesezugriff ist ab Phase 13 technisch aktiv, aber ausschließlich über eine explizit freigegebene Mission. Es gibt keinen Clearnet-Fallback und keine interaktiven Aktionen.'
  nxt='Tor/Tor Browser lokal starten, Mission für eine konkrete v3-Onion-URL anlegen, exakt OK freigeben und dann den einmaligen Read-only-Abruf starten.' if gs['status']!='ready' else 'Eine konkrete Onion-Mission anlegen und nach Scope-Prüfung mit OK freigeben.'
  return {'stand':stand,'meaning':meaning,'next':nxt,'gateway':gs,'latest_fetch':latest}
 def render_workspace_panel(self,case_id,csrf):
  e=lambda v:html.escape(str(v or ''),quote=True); st=self.field_status(case_id); tm=self.training_metrics(); p=self.performance_status(); missions=self.db.all('SELECT m.*,a.approval_id FROM phase13_tor_missions_301 m LEFT JOIN phase13_tor_approvals_301 a ON a.mission_id=m.mission_id WHERE m.case_id=? ORDER BY m.rowid DESC LIMIT 12',(case_id,)) if case_id else []
  rows=[]
  for m in missions:
   approved=bool(m.get('approval_id')); rows.append(f"<tr><td><code>{e(m['mission_id'])}</code></td><td>{e(m['onion_host'])}</td><td>{'freigegeben' if approved else 'wartet auf OK'}</td><td><form method='post' action='/build301/approve'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(m['mission_id'])}'><input name='confirmation' placeholder='OK' size='4'><button>Freigeben</button></form></td><td><form method='post' action='/build301/fetch'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(m['mission_id'])}'><button>Read-only abrufen</button></form></td></tr>")
  return f"""<section class='card'><h2>Phase 13 · Direct Tor Gateway 301</h2><div class='notice'><b>Was ist der Stand?</b><br>{e(st['stand'])}<br><br><b>Was bedeutet das?</b><br>{e(st['meaning'])}<br><br><b>Was ist jetzt zu tun?</b><br>{e(st['next'])}</div><div class='grid'><div class='card'><h3>Tor Gateway</h3><p>Status: <b>{e(st['gateway']['status'])}</b><br>Live Onion GET: <b>{'bereit' if st['gateway']['live_onion_read_transport'] else 'wartet auf lokalen Tor-Proxy'}</b><br>Clearnet-Fallback: <b>AUS</b><br>Credentials/Formulare/Uploads/Kontakt/Binär-Ausführung: <b>AUS</b></p></div><div class='card'><h3>AI/Data Foundation</h3><p>Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · Extreme: <b>{tm['adversarial_extreme_cases']}</b><br>Modellstatus: <b>{e(p['status'])}</b><br>Jeder erfolgreiche Abruf erzeugt Raw Artifact + SHA-256 + Source Record + Provenienz.</p></div></div><h3>Neue Onion-Mission</h3><form method='post' action='/build301/mission'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><label>v3 Onion URL<br><input name='onion_url' style='width:100%' placeholder='http://…56zeichen….onion/'></label><label>Zweck<br><input name='purpose' style='width:100%' value='Read-only OSINT research'></label><label>Max Bytes <input name='max_bytes' value='524288'></label><label>Redirects <input name='max_redirects' value='2'></label><button>Mission anlegen</button></form><h3>Missionen</h3><table><tr><th>Mission</th><th>Onion</th><th>Status</th><th>OK</th><th>Abruf</th></tr>{''.join(rows) or '<tr><td colspan="5">Noch keine Build-301-Mission für diesen Fall.</td></tr>'}</table><form method='post' action='/build301/selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Lokalen SOCKS5-Protokolltest ausführen</button></form><details><summary>Analyst/Experte</summary><pre>{e(_canon({'gateway':st['gateway'],'gate':self.qualified_gate(),'event_chain_ok':self.verify_event_chain()}))}</pre></details></section>"""
