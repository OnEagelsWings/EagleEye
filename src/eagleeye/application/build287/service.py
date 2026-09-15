from __future__ import annotations
import hashlib, html, json, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED={'text/plain','text/html','application/json','application/xhtml+xml'}

def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v):
    raw=v if isinstance(v,bytes) else _canon(v).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

class Build287CaptureWorkerBoundaryService:
    BUILD='287.0'
    def __init__(self,db:Any,audit:Any,*,build286:Any,build285:Any,build284:Any,base_dir:str|Path,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.build286=build286; self.build285=build285; self.build284=build284; self.actor=actor
        self.root=Path(base_dir)/'phase12_capture_worker_287'; self.input_dir=self.root/'adapter_input'; self.receipt_dir=self.root/'worker_receipts'; self.quarantine_dir=self.root/'quarantine'
        for p in (self.input_dir,self.receipt_dir,self.quarantine_dir): p.mkdir(parents=True,exist_ok=True)

    def register_worker(self,*,actor:str|None=None):
        actor=actor or self.actor
        row=self.db.one("SELECT * FROM phase12_capture_workers_287 WHERE label='restricted-capture-worker' ORDER BY rowid DESC LIMIT 1")
        if not row:
            wid=_id('worker287'); created=_now(); payload={'worker_id':wid,'label':'restricted-capture-worker','execution_mode':'staged_adapter_only','process_boundary':'separate_worker_contract','network_stack_enabled':False,'onion_transport_enabled':False,'credentials_enabled':False,'binary_downloads_enabled':False,'contact_enabled':False,'upload_enabled':False,'status':'ready','created_by':actor,'created_at':created}
            self.db.execute('INSERT INTO phase12_capture_workers_287 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(wid,payload['label'],payload['execution_mode'],payload['process_boundary'],0,0,0,0,0,0,'ready',actor,created,_hash(payload)))
            row=self.db.one('SELECT * FROM phase12_capture_workers_287 WHERE worker_id=?',(wid,))
        return {'worker_id':row['worker_id'],'status':row['status'],'execution_mode':row['execution_mode'],'process_boundary':row['process_boundary'],'network_stack_enabled':bool(row['network_stack_enabled']),'onion_transport_enabled':bool(row['onion_transport_enabled']),'credentials_enabled':bool(row['credentials_enabled']),'binary_downloads_enabled':bool(row['binary_downloads_enabled']),'contact_enabled':bool(row['contact_enabled']),'upload_enabled':bool(row['upload_enabled']),'embedded_network_client':False}

    def _event(self,*,worker_id:str,run_id:str,job_id:str,action:str,details:dict[str,Any],actor:str|None=None):
        actor=actor or self.actor; prev=self.db.one('SELECT event_hash FROM phase12_capture_worker_events_287 WHERE worker_id=? ORDER BY rowid DESC LIMIT 1',(worker_id,)); ph=prev['event_hash'] if prev else ''
        eid=_id('workevt287'); created=_now(); payload={'event_id':eid,'worker_id':worker_id,'run_id':run_id,'job_id':job_id,'action':action,'details':details,'actor':actor,'created_at':created,'previous_hash':ph}; eh=_hash(payload)
        self.db.execute('INSERT INTO phase12_capture_worker_events_287 VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,worker_id,run_id,job_id,action,_canon(details),actor,created,ph,eh)); return {**payload,'event_hash':eh}

    def verify_worker_chain(self):
        rows=self.db.all('SELECT * FROM phase12_capture_worker_events_287 ORDER BY rowid'); last={}
        for r in rows:
            exp=last.get(r['worker_id'],'')
            if r['previous_hash']!=exp:return False
            payload={'event_id':r['event_id'],'worker_id':r['worker_id'],'run_id':r['run_id'],'job_id':r['job_id'],'action':r['action'],'details':json.loads(r['details_json']),'actor':r['actor'],'created_at':r['created_at'],'previous_hash':r['previous_hash']}
            if _hash(payload)!=r['event_hash']:return False
            last[r['worker_id']]=r['event_hash']
        return True

    def stage_adapter_capture(self,*,job_id:str,observed_text:str,content_type:str='text/plain',actor:str|None=None):
        actor=actor or self.actor; job=self.db.one('SELECT * FROM phase12_gateway_jobs_286 WHERE job_id=?',(job_id,))
        if not job: raise KeyError('gateway job not found')
        if job['state']!='dispatched': raise PermissionError('gateway job is not awaiting capture')
        ctype=str(content_type).split(';',1)[0].strip().lower()
        if ctype not in ALLOWED: raise PermissionError('text-only capture required')
        raw=str(observed_text or '').encode('utf-8')
        if not raw.strip(): raise ValueError('capture text required')
        if len(raw)>int(job['max_bytes']): raise ValueError('capture exceeds approved byte budget')
        existing=self.db.one('SELECT * FROM phase12_capture_worker_runs_287 WHERE job_id=?',(job_id,))
        if existing: return {'run_id':existing['run_id'],'job_id':job_id,'state':existing['state'],'deduplicated':True,'input_path':existing['input_path']}
        worker=self.register_worker(actor=actor); run=_id('workrun287'); path=self.input_dir/f'{run}.json'; created=_now()
        payload={'contract_version':'287.0','run_id':run,'worker_id':worker['worker_id'],'job_id':job_id,'request_id':job['request_id'],'job_token':job['job_token'],'envelope_sha256':job['envelope_sha256'],'content_type':ctype,'observed_text':raw.decode('utf-8'),'content_sha256':hashlib.sha256(raw).hexdigest(),'transport_attestation':'staged_adapter_input','network_fetch_performed':False,'file_execution_performed':False,'credentials_used':False,'contact_performed':False,'created_at':created}
        path.write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2),encoding='utf-8'); ish=hashlib.sha256(path.read_bytes()).hexdigest()
        row_payload={'run_id':run,'worker_id':worker['worker_id'],'job_id':job_id,'request_id':job['request_id'],'case_id':job['case_id'],'mission_id':job['mission_id'],'state':'staged','input_path':str(path),'input_sha256':ish,'receipt_path':'','network_fetch_performed':False,'file_execution_performed':False,'credentials_used':False,'contact_performed':False,'quarantined':False,'started_by':actor,'started_at':created,'completed_at':''}
        self.db.execute('INSERT INTO phase12_capture_worker_runs_287 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run,worker['worker_id'],job_id,job['request_id'],job['case_id'],job['mission_id'],'staged',str(path),ish,'',0,0,0,0,0,actor,created,'',_hash(row_payload)))
        self._event(worker_id=worker['worker_id'],run_id=run,job_id=job_id,action='adapter_capture_staged',details={'input_sha256':ish,'network_fetch_performed':False},actor=actor)
        return {'run_id':run,'job_id':job_id,'state':'staged','input_path':str(path),'input_sha256':ish,'deduplicated':False,'network_fetch_performed':False}

    def _quarantine(self,run:dict[str,Any],reason:str,details:dict[str,Any],actor:str):
        qid=_id('quarantine287'); created=_now(); payload={'quarantine_id':qid,'job_id':run['job_id'],'run_id':run['run_id'],'reason':reason,'input_sha256':run['input_sha256'],'details':details,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_capture_quarantine_287 VALUES(?,?,?,?,?,?,?,?,?)',(qid,run['job_id'],run['run_id'],reason,run['input_sha256'],_canon(details),actor,created,_hash(payload)))
        self.db.execute("UPDATE phase12_capture_worker_runs_287 SET state='quarantined',quarantined=1,completed_at=? WHERE run_id=?",(created,run['run_id']))
        self._event(worker_id=run['worker_id'],run_id=run['run_id'],job_id=run['job_id'],action='quarantined',details={'quarantine_id':qid,'reason':reason},actor=actor)
        return {'quarantine_id':qid,'reason':reason,'state':'quarantined'}

    def process_staged_capture(self,*,run_id:str,actor:str|None=None):
        actor=actor or self.actor; run=self.db.one('SELECT * FROM phase12_capture_worker_runs_287 WHERE run_id=?',(run_id,))
        if not run: raise KeyError('worker run not found')
        if run['state']=='completed':
            return {'run_id':run_id,'state':'completed','receipt_path':run['receipt_path'],'deduplicated':True}
        if run['state']!='staged': raise PermissionError('worker run is not staged')
        p=Path(run['input_path'])
        if not p.exists(): return self._quarantine(dict(run),'missing_input',{},actor)
        actual=hashlib.sha256(p.read_bytes()).hexdigest()
        if actual!=run['input_sha256']: return self._quarantine(dict(run),'input_hash_mismatch',{'actual':actual},actor)
        data=json.loads(p.read_text(encoding='utf-8'))
        prohibited=any(bool(data.get(k)) for k in ('network_fetch_performed','file_execution_performed','credentials_used','contact_performed'))
        if prohibited: return self._quarantine(dict(run),'prohibited_side_effect_reported',{},actor)
        job=self.db.one('SELECT * FROM phase12_gateway_jobs_286 WHERE job_id=?',(run['job_id'],))
        if not job or data.get('job_token')!=job['job_token'] or data.get('envelope_sha256')!=job['envelope_sha256']:
            return self._quarantine(dict(run),'manifest_binding_mismatch',{},actor)
        raw=str(data.get('observed_text') or '').encode('utf-8')
        if hashlib.sha256(raw).hexdigest()!=data.get('content_sha256'): return self._quarantine(dict(run),'content_hash_mismatch',{},actor)
        receipt=self.build286.build_synthetic_receipt(job_id=run['job_id'],observed_text=raw.decode('utf-8'),content_type=data.get('content_type','text/plain'))
        receipt['transport_mode']='restricted_capture_worker_287'
        outpath=self.receipt_dir/f"{run['run_id']}.receipt.json"; outpath.write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2),encoding='utf-8')
        ingested=self.build286.ingest_gateway_receipt(receipt=receipt,actor=actor); completed=_now()
        self.db.execute("UPDATE phase12_capture_worker_runs_287 SET state='completed',receipt_path=?,completed_at=? WHERE run_id=?",(str(outpath),completed,run_id))
        self._event(worker_id=run['worker_id'],run_id=run_id,job_id=run['job_id'],action='capture_processed',details={'receipt_id':ingested['receipt_id'],'receipt_path':str(outpath),'network_fetch_performed':False},actor=actor)
        return {'run_id':run_id,'state':'completed','receipt_path':str(outpath),**ingested,'deduplicated':False}

    def training_metrics(self):
        base=self.build286.training_metrics(); delta=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_287 WHERE review_status='reviewed'")['n']); ext=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_287 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases':int(base['reviewed_hard_cases'])+delta,'adversarial_extreme_cases':int(base['adversarial_extreme_cases'])+ext,'build287_delta_cases':delta,'build287_delta_extreme':ext,'automatic_model_activation':False}

    def infrastructure_snapshot(self):
        parent=bool(self.build286.qualified_gate()['release_ready']); w=self.register_worker(); chain=self.verify_worker_chain(); qready=True; ready=parent and w['status']=='ready' and chain and not w['network_stack_enabled'] and not w['onion_transport_enabled']
        sid=_id('infra287'); created=_now(); payload={'parent_ready':parent,'worker_ready':w['status']=='ready','worker_chain_ok':chain,'quarantine_ready':qready,'network_stack_enabled':w['network_stack_enabled'],'onion_transport_enabled':w['onion_transport_enabled'],'beginner_guidance_ready':True,'status':'ready' if ready else 'degraded'}
        self.db.execute('INSERT INTO infrastructure_snapshots_287 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,int(parent),int(payload['worker_ready']),int(chain),1,int(w['network_stack_enabled']),int(w['onion_transport_enabled']),1,payload['status'],created,_hash(payload)))
        return {'snapshot_id':sid,**payload}

    def qualified_gate(self):
        inf=self.infrastructure_snapshot(); tm=self.training_metrics(); gate={'build':'287.0','parent_gate':inf['parent_ready'],'capture_worker_boundary':inf['worker_ready'],'worker_chain':inf['worker_chain_ok'],'quarantine_ready':inf['quarantine_ready'],'beginner_guidance':inf['beginner_guidance_ready'],'hard_training_corpus_128':tm['reviewed_hard_cases']>=128 and tm['build287_delta_cases']>=16 and tm['build287_delta_extreme']>=4,'live_network_enabled':inf['network_stack_enabled'],'onion_transport_enabled':inf['onion_transport_enabled'],'credentials_allowed':False,'binary_downloads_enabled':False,'automatic_contact':False,'automatic_model_activation':False,'human_authority_preserved':True}
        gate['release_ready']=all([gate['parent_gate'],gate['capture_worker_boundary'],gate['worker_chain'],gate['quarantine_ready'],gate['beginner_guidance'],gate['hard_training_corpus_128'],not gate['live_network_enabled'],not gate['onion_transport_enabled'],not gate['credentials_allowed'],not gate['binary_downloads_enabled'],not gate['automatic_contact'],not gate['automatic_model_activation'],gate['human_authority_preserved']]); return gate

    def explain_run(self,run_id:str):
        r=self.db.one('SELECT * FROM phase12_capture_worker_runs_287 WHERE run_id=?',(run_id,));
        if not r: raise KeyError('worker run not found')
        if r['state']=='staged': return {'status_label':'Capture-Eingang bereit','what_it_means':'Ein Textbeleg wurde an der getrennten Worker-Grenze bereitgestellt. Noch wurde daraus keine Evidenz übernommen.','next_action':'Integrität prüfen und Worker-Verarbeitung starten.','risk':'kontrolliert'}
        if r['state']=='quarantined': return {'status_label':'In Quarantäne','what_it_means':'Eine Integritäts- oder Sicherheitsregel wurde verletzt. Das Original bleibt erhalten.','next_action':'Grund prüfen; nicht automatisch erneut ausführen.','risk':'stop'}
        return {'status_label':'Capture verarbeitet – Review offen','what_it_means':'Der Worker hat Vertrag, Hashes und Textgrenzen geprüft. Der Inhalt bleibt unbestätigte Evidenz.','next_action':'Snapshot/Replay in Build 288 prüfen und anschließend menschlich bewerten.','risk':'review_required'}

    def render_workspace_panel(self,*,case_id:str,csrf:str)->str:
        e=lambda v:html.escape(str(v or ''),quote=True); worker=self.register_worker(); tm=self.training_metrics()
        jobs=self.db.all("SELECT * FROM phase12_gateway_jobs_286 WHERE case_id=? AND state='dispatched' ORDER BY created_at DESC LIMIT 12",(case_id,))
        runs=self.db.all('SELECT * FROM phase12_capture_worker_runs_287 WHERE case_id=? ORDER BY started_at DESC LIMIT 12',(case_id,))
        jr=''.join(f"<tr><td><code>{e(j['job_id'])}</code></td><td>{e(j['request_id'])}</td><td><form method='post' action='/build287/stage'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='job_id' value='{e(j['job_id'])}'><textarea name='observed_text' rows='3' cols='44' placeholder='Kontrollierter Textbeleg aus zulässiger externer/Offline-Quelle' required></textarea><button>Text an Worker-Grenze bereitstellen</button></form></td></tr>" for j in jobs)
        rr=[]
        for r in runs:
            x=self.explain_run(r['run_id'])
            action=''
            if r['state']=='staged': action=f"<form method='post' action='/build287/process'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='run_id' value='{e(r['run_id'])}'><button>Integrität prüfen & verarbeiten</button></form>"
            rr.append(f"<tr><td><code>{e(r['run_id'])}</code></td><td><b>{e(x['status_label'])}</b><br><small>{e(x['what_it_means'])}</small></td><td>{e(x['next_action'])}</td><td>{action}</td></tr>")
        return f"""<section class='card'><h2>Phase 12 · Restricted Capture Worker 287</h2><p><b>Einsteiger-Pfad:</b> Gateway-Auftrag → Textbeleg bereitstellen → Worker prüft Hash/Scope/Sicherheitsflags → Receipt → Review. <b>Der eingebaute Worker hat keinen Netzwerk-/Onion-Client.</b></p><div class='grid'><div class='card'><h3>Worker</h3><p>Status: <b>{e(worker['status'])}</b><br>Prozessgrenze: {e(worker['process_boundary'])}<br>Netzwerk: <b>AUS</b><br>Onion: <b>AUS</b><br>Credentials/Binaries/Kontakt: <b>AUS</b></p></div><div class='card'><h3>AI-Training</h3><p><b>{e(tm['reviewed_hard_cases'])}</b> reviewte Fälle, davon {e(tm['adversarial_extreme_cases'])} extreme.</p></div></div><h3>Wartende Gateway-Aufträge</h3><table><tr><th>Job</th><th>Request</th><th>Nächster Schritt</th></tr>{jr or '<tr><td colspan="3">Kein wartender Gateway-Auftrag.</td></tr>'}</table><h3>Worker-Läufe</h3><table><tr><th>Run</th><th>Was ist der Stand?</th><th>Was bedeutet das / nächster Schritt?</th><th>Aktion</th></tr>{''.join(rr) or '<tr><td colspan="4">Noch kein Worker-Lauf.</td></tr>'}</table><details><summary>Experten-/Auditdetails</summary><pre>{e(_canon(self.qualified_gate()))}</pre></details></section>"""
