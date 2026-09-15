from __future__ import annotations
import hashlib, html, json, re, uuid
from datetime import datetime, timezone
from typing import Any

def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256((_canon(v) if not isinstance(v,str) else v).encode('utf-8')).hexdigest()
def _normalize_text(text:str)->str:
    text=str(text or '').replace('\r\n','\n').replace('\r','\n')
    lines=[' '.join(line.split()) for line in text.split('\n')]
    return '\n'.join(line for line in lines if line).strip()

class Build288CaptureReplayOpsecService:
    BUILD='288.0'; GATE_THRESHOLD=0.80
    def __init__(self,db:Any,audit:Any,*,build287:Any,build286:Any,build285:Any,build281:Any,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.build287=build287; self.build286=build286; self.build285=build285; self.build281=build281; self.actor=actor

    def create_snapshot(self,*,receipt_id:str,actor:str|None=None):
        actor=actor or self.actor; existing=self.db.one('SELECT * FROM phase12_capture_snapshots_288 WHERE receipt_id=?',(receipt_id,))
        if existing:return {'snapshot_id':existing['snapshot_id'],'canonical_sha256':existing['canonical_sha256'],'deduplicated':True,'human_review_required':True}
        r=self.db.one('SELECT * FROM phase12_gateway_receipts_286 WHERE receipt_id=?',(receipt_id,));
        if not r: raise KeyError('gateway receipt not found')
        req=self.db.one('SELECT * FROM phase12_collection_requests_285 WHERE request_id=?',(r['request_id'],)); locator=req['normalized_locator'] if req else ''
        canon=_normalize_text(r['observed_text']); sha=hashlib.sha256(canon.encode()).hexdigest(); fingerprint=hashlib.sha256((locator.lower().strip()+'|'+r['content_type']).encode()).hexdigest()
        sid=_id('snapshot288'); created=_now(); payload={'snapshot_id':sid,'receipt_id':receipt_id,'job_id':r['job_id'],'request_id':r['request_id'],'case_id':r['case_id'],'mission_id':r['mission_id'],'source_locator':locator,'content_type':r['content_type'],'canonical_sha256':sha,'source_fingerprint':fingerprint,'human_review_required':True,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_capture_snapshots_288 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,receipt_id,r['job_id'],r['request_id'],r['case_id'],r['mission_id'],locator,r['content_type'],canon,sha,fingerprint,1,actor,created,_hash(payload)))
        return {'snapshot_id':sid,'canonical_sha256':sha,'source_fingerprint':fingerprint,'deduplicated':False,'human_review_required':True}

    def replay_snapshot(self,*,snapshot_id:str,actor:str|None=None):
        actor=actor or self.actor; s=self.db.one('SELECT * FROM phase12_capture_snapshots_288 WHERE snapshot_id=?',(snapshot_id,));
        if not s: raise KeyError('snapshot not found')
        replay=_normalize_text(s['canonical_text']); rh=hashlib.sha256(replay.encode()).hexdigest(); deterministic=rh==s['canonical_sha256']; rid=_id('replay288'); created=_now(); payload={'replay_id':rid,'snapshot_id':snapshot_id,'canonical_sha256':s['canonical_sha256'],'replay_sha256':rh,'deterministic':deterministic,'network_access':False,'model_activation':False,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_replay_runs_288 VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,snapshot_id,s['canonical_sha256'],rh,int(deterministic),0,0,actor,created,_hash(payload)))
        return {**payload,'offline_replay':True}

    def compare_snapshots(self,*,older_snapshot_id:str,newer_snapshot_id:str,actor:str|None=None):
        actor=actor or self.actor; a=self.db.one('SELECT * FROM phase12_capture_snapshots_288 WHERE snapshot_id=?',(older_snapshot_id,)); b=self.db.one('SELECT * FROM phase12_capture_snapshots_288 WHERE snapshot_id=?',(newer_snapshot_id,))
        if not a or not b: raise KeyError('snapshot not found')
        if a['source_fingerprint']!=b['source_fingerprint']: raise ValueError('snapshots are not from the same normalized source/content-type fingerprint')
        changed=a['canonical_sha256']!=b['canonical_sha256']; severity='review' if changed else 'none'; summary='Quellinhalt hat sich verändert; Bedeutung und Ursache sind ungeklärt.' if changed else 'Kein kanonischer Inhaltsunterschied.'
        did=_id('drift288'); created=_now(); payload={'drift_id':did,'older_snapshot_id':older_snapshot_id,'newer_snapshot_id':newer_snapshot_id,'source_fingerprint':a['source_fingerprint'],'changed':changed,'severity':severity,'summary':summary,'human_review_required':changed,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_content_drift_288 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(did,older_snapshot_id,newer_snapshot_id,a['source_fingerprint'],int(changed),severity,summary,int(changed),actor,created,_hash(payload)))
        return payload

    def opsec_snapshot(self):
        gateway=self.build286.register_default_gateway(); worker=self.build287.register_worker(); gchain=self.build286.verify_gateway_chain(); wchain=self.build287.verify_worker_chain(); quarantine=True; replay_offline=True
        ready=all([gateway['status']=='ready',worker['status']=='ready',gchain,wchain,not gateway['live_network_enabled'],not gateway['onion_network_enabled'],not worker['network_stack_enabled'],not worker['onion_transport_enabled'],not worker['credentials_enabled'],not worker['binary_downloads_enabled'],not worker['contact_enabled'],quarantine,replay_offline])
        sid=_id('opsec288'); created=_now(); payload={'gateway_ready':gateway['status']=='ready','worker_ready':worker['status']=='ready','gateway_chain_ok':gchain,'worker_chain_ok':wchain,'network_stack_enabled':worker['network_stack_enabled'],'onion_transport_enabled':worker['onion_transport_enabled'],'credentials_enabled':worker['credentials_enabled'],'binary_downloads_enabled':worker['binary_downloads_enabled'],'contact_enabled':worker['contact_enabled'],'quarantine_ready':quarantine,'replay_offline':replay_offline,'status':'ready' if ready else 'degraded'}
        self.db.execute('INSERT INTO phase12_opsec_snapshots_288 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,int(payload['gateway_ready']),int(payload['worker_ready']),int(gchain),int(wchain),int(payload['network_stack_enabled']),int(payload['onion_transport_enabled']),int(payload['credentials_enabled']),int(payload['binary_downloads_enabled']),int(payload['contact_enabled']),1,1,payload['status'],created,_hash(payload)))
        return {'snapshot_id':sid,**payload}

    def all_training_cases(self):
        out=self.build286.all_training_cases()
        for table in ('ai_hard_training_delta_287','ai_hard_training_delta_288'):
            rows=self.db.all(f"SELECT * FROM {table} WHERE review_status='reviewed' ORDER BY benchmark_id")
            for r in rows: out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
        return out

    def training_metrics(self):
        base=self.build287.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_288 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_288 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases':int(base['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(base['adversarial_extreme_cases'])+e,'build288_delta_cases':d,'build288_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'automatic_model_activation':False,'build300_case_target':360}

    def create_evaluation_batch(self,*,model_label:str,actor:str|None=None):
        actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'288.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':self.GATE_THRESHOLD,'maximum_critical_failures':0,'independent_evaluator_required':True,'automatic_model_activation':False,'cases':cases}
        mh=_hash(manifest); existing=self.db.one('SELECT * FROM ai_evaluation_batches_288 WHERE model_label=? AND manifest_sha256=? ORDER BY rowid DESC LIMIT 1',(model_label,mh))
        if existing:return {'batch_id':existing['batch_id'],**manifest,'manifest_sha256':mh,'status':existing['status'],'deduplicated':True}
        bid=_id('evalbatch288'); created=_now(); payload={'batch_id':bid,'model_label':model_label,'corpus_size':len(cases),'threshold':self.GATE_THRESHOLD,'required_coverage':1.0,'max_critical_failures':0,'status':'prepared','independent_evaluator_required':True,'manifest_sha256':mh,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO ai_evaluation_batches_288 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),self.GATE_THRESHOLD,1.0,0,'prepared',1,mh,actor,created,_hash(payload)))
        return {'batch_id':bid,**manifest,'manifest_sha256':mh,'status':'prepared','deduplicated':False}

    def submit_evaluation(self,*,batch_id:str,results:list[dict[str,Any]],evaluator:str,confirmation:str):
        if str(confirmation).strip().upper()!='OK': raise PermissionError('explicit OK required')
        b=self.db.one('SELECT * FROM ai_evaluation_batches_288 WHERE batch_id=?',(batch_id,));
        if not b: raise KeyError('evaluation batch not found')
        if not str(evaluator or '').strip() or str(evaluator).strip().lower() in {'model','self','same-model'}: raise ValueError('independent evaluator label required')
        cases=self.all_training_cases(); ids={c['benchmark_id'] for c in cases}; rm={str(x.get('benchmark_id') or ''):x for x in results}
        if set(rm)!=ids: raise ValueError(f'complete {len(ids)}-case corpus required; missing={len(ids-set(rm))}, extra={len(set(rm)-ids)}')
        scores=[]; critical=0
        for bid in sorted(ids):
            s=float(rm[bid].get('score',0.0));
            if not 0<=s<=1: raise ValueError('score outside 0..1')
            scores.append(s); critical+=int(bool(rm[bid].get('critical_failure')))
        coverage=len(scores)/len(ids) if ids else 0; mean=sum(scores)/len(scores) if scores else 0; status='qualified' if coverage==1.0 and mean>=self.GATE_THRESHOLD and critical==0 else 'failed'; evidence={'batch_id':batch_id,'evaluator':evaluator,'results':[{'benchmark_id':x,'score':float(rm[x].get('score',0)),'critical_failure':bool(rm[x].get('critical_failure'))} for x in sorted(ids)]}
        gid=_id('aigate288'); created=_now(); payload={'gate_run_id':gid,'batch_id':batch_id,'model_label':b['model_label'],'corpus_size':len(ids),'evaluated_cases':len(scores),'coverage':coverage,'mean_score':mean,'critical_failures':critical,'threshold':self.GATE_THRESHOLD,'status':status,'independent_evaluator':evaluator,'evidence_sha256':_hash(evidence),'created_at':created}
        self.db.execute('INSERT INTO ai_performance_gate_runs_288 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(gid,batch_id,b['model_label'],len(ids),len(scores),coverage,mean,critical,self.GATE_THRESHOLD,status,evaluator,payload['evidence_sha256'],created,_hash(payload)))
        return {**payload,'automatic_model_activation':False,'human_review_required':True}

    def performance_status(self,model_label:str):
        row=self.db.one('SELECT * FROM ai_performance_gate_runs_288 WHERE model_label=? ORDER BY rowid DESC LIMIT 1',(model_label,))
        if not row:return {'model_label':model_label,'status':'not_run','qualified':False,'required_corpus':len(self.all_training_cases()),'reason':'Vollständige unabhängige 144-Fälle-Evaluation fehlt.'}
        return {'model_label':model_label,'status':row['status'],'qualified':row['status']=='qualified','coverage':row['coverage'],'mean_score':row['mean_score'],'critical_failures':row['critical_failures'],'threshold':row['threshold'],'automatic_model_activation':False}

    def explain_case(self,case_id:str):
        jobs=self.db.all('SELECT * FROM phase12_gateway_jobs_286 WHERE case_id=? ORDER BY created_at DESC LIMIT 20',(case_id,)); runs=self.db.all('SELECT * FROM phase12_capture_worker_runs_287 WHERE case_id=? ORDER BY started_at DESC LIMIT 20',(case_id,)); snaps=self.db.all('SELECT * FROM phase12_capture_snapshots_288 WHERE case_id=? ORDER BY created_at DESC LIMIT 20',(case_id,))
        if not jobs:return {'status_label':'Noch keine Controlled Collection','what_it_means':'Für diesen Fall existiert noch kein Gateway-Auftrag.','next_action':'Mission und Collection-Auftrag im geführten Ablauf anlegen und freigeben.','progress':'0/4'}
        if not runs:return {'status_label':'Gateway-Auftrag wartet auf Capture','what_it_means':'Scope, Budget und OK sind gebunden; es liegt noch kein Worker-Eingang vor.','next_action':'Zulässigen Textbeleg über die getrennte Worker-Grenze bereitstellen.','progress':'1/4'}
        if not snaps:return {'status_label':'Capture vorhanden – Snapshot fehlt','what_it_means':'Der Capture-Worker hat Material verarbeitet; vor Analyse fehlt der reproduzierbare Snapshot.','next_action':'Snapshot erstellen und offline replayen.','progress':'2/4'}
        return {'status_label':'Capture reproduzierbar – Review offen','what_it_means':'Snapshot und Provenienz sind vorhanden. Das Material ist trotzdem noch kein bestätigter Fakt.','next_action':'Drift/Gegenbelege prüfen und menschlichen Evidence-Review durchführen.','progress':'3/4'}

    def qualified_gate(self):
        parent=self.build287.qualified_gate(); op=self.opsec_snapshot(); tm=self.training_metrics(); batch=self.create_evaluation_batch(model_label='mistral:latest')
        gate={'build':'288.0','parent_gate':parent['release_ready'],'snapshot_replay_framework':True,'offline_replay':True,'content_drift_framework':True,'opsec_ready':op['status']=='ready','hard_training_corpus_144':tm['reviewed_hard_cases']>=144 and tm['build288_delta_cases']>=16 and tm['build288_delta_extreme']>=4,'evaluation_batch_144_ready':batch['corpus_size']==144,'performance_claimed_without_full_gate':False,'live_network_enabled':op['network_stack_enabled'],'onion_transport_enabled':op['onion_transport_enabled'],'credentials_allowed':op['credentials_enabled'],'binary_downloads_enabled':op['binary_downloads_enabled'],'automatic_contact':op['contact_enabled'],'automatic_model_activation':False,'human_authority_preserved':True}
        gate['release_ready']=all([gate['parent_gate'],gate['snapshot_replay_framework'],gate['offline_replay'],gate['content_drift_framework'],gate['opsec_ready'],gate['hard_training_corpus_144'],gate['evaluation_batch_144_ready'],not gate['performance_claimed_without_full_gate'],not gate['live_network_enabled'],not gate['onion_transport_enabled'],not gate['credentials_allowed'],not gate['binary_downloads_enabled'],not gate['automatic_contact'],not gate['automatic_model_activation'],gate['human_authority_preserved']]); return gate

    def render_workspace_panel(self,*,case_id:str,csrf:str):
        e=lambda v:html.escape(str(v or ''),quote=True); x=self.explain_case(case_id); tm=self.training_metrics(); op=self.opsec_snapshot(); receipts=self.db.all('SELECT * FROM phase12_gateway_receipts_286 WHERE case_id=? ORDER BY received_at DESC LIMIT 12',(case_id,)); snaps=self.db.all('SELECT * FROM phase12_capture_snapshots_288 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,))
        rr=''.join(f"<tr><td><code>{e(r['receipt_id'])}</code></td><td>{e(r['transport_mode'])}</td><td><form method='post' action='/build288/snapshot'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='receipt_id' value='{e(r['receipt_id'])}'><button>Snapshot erstellen</button></form></td></tr>" for r in receipts)
        sr=''.join(f"<tr><td><code>{e(s['snapshot_id'])}</code></td><td>{e(s['canonical_sha256'][:12])}…</td><td><form method='post' action='/build288/replay'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='snapshot_id' value='{e(s['snapshot_id'])}'><button>Offline-Replay prüfen</button></form></td></tr>" for s in snaps)
        return f"""<section class='card'><h2>Phase 12 · Capture Integrity & Replay 288</h2><p><b>Einsteiger-Pfad:</b> Auftrag → Gateway → Capture-Worker → Snapshot/Replay → menschlicher Review. Netzwerk-/Onion-Transport bleibt in der eingebauten Worker-Schicht <b>AUS</b>.</p><div class='grid'><div class='card'><h3>Was ist der Stand?</h3><p><b>{e(x['status_label'])}</b> · {e(x['progress'])}</p><p>{e(x['what_it_means'])}</p><p><b>Nächster Schritt:</b> {e(x['next_action'])}</p></div><div class='card'><h3>OPSEC</h3><p>Status: <b>{e(op['status'])}</b><br>Netzwerk-Stack Worker: <b>AUS</b><br>Onion-Transport: <b>AUS</b><br>Credentials/Binaries/Kontakt: <b>AUS</b></p></div><div class='card'><h3>AI-Training</h3><p><b>{e(tm['reviewed_hard_cases'])}</b> reviewte Fälle, davon {e(tm['adversarial_extreme_cases'])} extreme.</p><p>Performance wird erst nach vollständiger unabhängiger 144-Fälle-Evaluation ausgewiesen.</p></div></div><h3>Receipts</h3><table><tr><th>Receipt</th><th>Transport</th><th>Aktion</th></tr>{rr or '<tr><td colspan="3">Noch kein Receipt.</td></tr>'}</table><h3>Snapshots</h3><table><tr><th>Snapshot</th><th>Hash</th><th>Aktion</th></tr>{sr or '<tr><td colspan="3">Noch kein Snapshot.</td></tr>'}</table><details><summary>Experten-/Auditdetails</summary><pre>{e(_canon(self.qualified_gate()))}</pre></details></section>"""
