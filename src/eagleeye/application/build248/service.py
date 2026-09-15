from __future__ import annotations
import hashlib, html, json, os, shutil, subprocess, urllib.request, urllib.error, urllib.parse
from pathlib import Path
from typing import Any
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(v if isinstance(v,bytes) else _canon(v).encode('utf-8')).hexdigest()
def _text(v:Any,n:int=5000)->str:return str(v or '').replace('\x00','').strip()[:n]
def _loads(v:Any,d:Any)->Any:
    try:return json.loads(v) if v else d
    except Exception:return d

class Build248PrivateIntelligenceProductionHardeningService:
    BUILD='248.0'
    PREFERRED_MODEL='mistral:latest'
    PREFERRED_MODEL_ID='6577803aa9a0'
    REVIEW={'approved','rejected','needs_remediation'}
    def __init__(self,db,audit,*,runtime,recovery,governance,opsec,sentinel,training,conversation,base_dir,actor='local-analyst'):
        self.db,self.audit=db,audit; self.runtime,self.recovery=runtime,recovery; self.governance,self.opsec,self.sentinel=governance,opsec,sentinel; self.training,self.conversation,self.actor=training,conversation,actor; self.base_dir=Path(base_dir).resolve()
        conversation._production248=self; sentinel._production248=self
    def _case(self,cid):
        if not self.db.one('SELECT case_id FROM cases WHERE case_id=?',(cid,)):raise KeyError(cid)
    def _event(self,cid,typ,obj,oid,payload,actor):
        prev=self.db.one('SELECT event_hash FROM production_events_248 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(cid,)); ph=(prev or {}).get('event_hash',''); eid,now=new_id('prodevt248'),now_ts(); eh=_hash({'prev':ph,'event':eid,'type':typ,'object':oid,'payload':payload,'actor':actor,'at':now}); self.db.execute('INSERT INTO production_events_248 VALUES(?,?,?,?,?,?,?,?,?,?)',(eid,cid,typ,obj,oid,actor,dumps(payload),ph,eh,now))
        try:self.audit.log('build248_'+typ,obj,oid,cid,payload)
        except Exception:pass
    def _ollama_executable(self)->str:
        candidates=[]
        env=os.environ.get('OLLAMA_EXE','').strip()
        if env:candidates.append(env)
        found=shutil.which('ollama')
        if found:candidates.append(found)
        if os.name=='nt':
            local=os.environ.get('LOCALAPPDATA',''); prog=os.environ.get('ProgramFiles','');
            if local:candidates.append(str(Path(local)/'Programs'/'Ollama'/'ollama.exe'))
            if prog:candidates.append(str(Path(prog)/'Ollama'/'ollama.exe'))
        for c in candidates:
            p=Path(c)
            if p.exists() and p.is_file():return str(p.resolve())
        return ''
    def probe_ollama_mistral(self,*,case_id,actor,confirmation,endpoint='http://127.0.0.1:11434'):
        self._case(case_id)
        if confirmation!=f'PRODUCTION OLLAMA 248 {case_id} PRUEFEN':raise PermissionError('explicit approval required')
        host=(urllib.parse.urlparse(endpoint).hostname or '').casefold()
        if host not in {'127.0.0.1','localhost','::1'}:raise ValueError('Ollama endpoint must be loopback/local only')
        exe=self._ollama_executable(); version=''; cli_models=[]; cli_error=''
        if exe:
            try:
                r=subprocess.run([exe,'--version'],capture_output=True,text=True,timeout=5,check=False); version=_text((r.stdout or r.stderr).strip(),300)
                l=subprocess.run([exe,'list'],capture_output=True,text=True,timeout=8,check=False)
                if l.returncode==0:
                    for line in (l.stdout or '').splitlines()[1:]:
                        parts=line.split()
                        if len(parts)>=2:cli_models.append({'name':parts[0],'id':parts[1]})
                else:cli_error=_text(l.stderr,1000)
            except Exception as exc:cli_error=type(exc).__name__+': '+str(exc)
        api_models=[]; endpoint_healthy=False; api_error=''
        try:
            opener=urllib.request.build_opener(urllib.request.ProxyHandler())
            req=urllib.request.Request(endpoint.rstrip('/')+'/api/tags',method='GET')
            with opener.open(req,timeout=3) as resp:
                data=json.loads(resp.read(2_000_000).decode('utf-8'))
            endpoint_healthy=True
            for m in data.get('models') or []:api_models.append({'name':_text(m.get('name') or m.get('model'),200),'id':_text(m.get('digest'),200),'size':int(m.get('size') or 0)})
        except Exception as exc:api_error=type(exc).__name__+': '+str(exc)
        observed=api_models or cli_models
        preferred=[m for m in observed if m.get('name')==self.PREFERRED_MODEL]
        model_present=bool(preferred)
        id_match=False
        if preferred:
            pid=_text(preferred[0].get('id'),200).lower(); id_match=(pid.startswith(self.PREFERRED_MODEL_ID.lower()) or self.PREFERRED_MODEL_ID.lower().startswith(pid)) if pid else False
        status='ready_candidate' if endpoint_healthy and model_present and id_match else ('model_id_mismatch' if model_present and not id_match else ('model_missing' if endpoint_healthy else 'ollama_unavailable'))
        detail={'cli_error':cli_error,'api_error':api_error,'expected_model':self.PREFERRED_MODEL,'expected_id_prefix':self.PREFERRED_MODEL_ID,'id_match':id_match,'no_cloud_fallback':True,'uploaded_ollama_zip_note':'directory scaffold only; runtime/model remains local'}
        pid,now=new_id('prodprobe248'),now_ts(); payload={'probe_id':pid,'case_id':case_id,'ollama_found':bool(exe),'version':version,'endpoint_healthy':endpoint_healthy,'model_present':model_present,'status':status,'models':observed,'detail':detail}; self.db.execute('INSERT INTO production_runtime_probes_248 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,1 if exe else 0,version,endpoint,1 if endpoint_healthy else 0,self.PREFERRED_MODEL,self.PREFERRED_MODEL_ID,1 if model_present else 0,dumps(observed),exe,status,dumps(detail),actor,now,_hash(payload))); self._event(case_id,'runtime_probe','ollama',pid,{'status':status,'preferred_model':self.PREFERRED_MODEL,'external_egress':False},actor); return payload
    def register_preferred_mistral(self,*,case_id,actor,confirmation):
        self._case(case_id)
        if confirmation!=f'MISTRAL 248 {case_id} REGISTRIEREN':raise PermissionError('explicit approval required')
        p=self.db.one('SELECT * FROM production_runtime_probes_248 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,))
        if not p or p['status']!='ready_candidate':raise RuntimeError('successful local Mistral probe required')
        existing=self.db.one('SELECT model_id FROM ai_models_247 WHERE case_id=? AND model_name=? AND (model_digest LIKE ? OR version_ref LIKE ?)',(case_id,self.PREFERRED_MODEL,self.PREFERRED_MODEL_ID+'%',self.PREFERRED_MODEL_ID+'%'))
        if existing:return {'case_id':case_id,'model_id':existing['model_id'],'already_registered':True,'review_required':True}
        observed=_loads(p['observed_models_json'],[]); match=next((m for m in observed if m.get('name')==self.PREFERRED_MODEL),{}); digest=_text(match.get('id') or self.PREFERRED_MODEL_ID,200)
        m=self.runtime.register_model(case_id=case_id,model_name=self.PREFERRED_MODEL,model_digest=digest,version_ref=digest,backend='ollama_local',capabilities=['completion','investigation_dialogue','evidence_analysis','source_assessment','contradiction_analysis'],languages=['de','en'],context_window=32768,ram_mb=6144,vram_mb=0,actor='production-bootstrap-248',confirmation=f'AI MODEL 247 {case_id} REGISTRIEREN')
        self._event(case_id,'preferred_model_registered','ai_model',m['model_id'],{'model':self.PREFERRED_MODEL,'review_required':True,'automatic_activation':False},actor); return {'case_id':case_id,'model_id':m['model_id'],'already_registered':False,'review_required':True,'automatic_activation':False}
    def review_preferred_mistral(self,*,model_id,reviewer,rationale,confirmation):
        m=self.runtime.model(model_id)
        if m['model_name']!=self.PREFERRED_MODEL:raise ValueError('model is not the preferred Mistral candidate')
        if confirmation!=f'MISTRAL REVIEW 248 {model_id} PRUEFEN':raise PermissionError('explicit approval required')
        out=self.runtime.review_model(model_id=model_id,decision='approved',rationale=rationale,reviewer=reviewer,confirmation=f'AI MODEL 247 {model_id} PRUEFEN')
        self._event(m['case_id'],'preferred_model_reviewed','ai_model',model_id,{'decision':'approved','automatic_activation':False},reviewer); return out
    def activate_preferred_mistral(self,*,case_id,model_id,actor,confirmation):
        self._case(case_id); m=self.runtime.model(model_id)
        if confirmation!=f'MISTRAL 248 {model_id} AKTIVIEREN':raise PermissionError('explicit approval required')
        if m['case_id']!=case_id or m['model_name']!=self.PREFERRED_MODEL:raise ValueError('wrong model/case')
        if not m.get('review') or m['review']['decision']!='approved':raise PermissionError('independent model review required before activation')
        refreshed=self.runtime.local_ai.refresh_models(case_id=case_id,actor=actor,confirmation=f'OLLAMA MODELS 215 {case_id} AKTUALISIEREN')
        available={x['model_name'] for x in refreshed.get('models',[])}
        if self.PREFERRED_MODEL not in available:raise RuntimeError('reviewed Mistral is not available in the live local Ollama snapshot')
        cfg=self.runtime.local_ai.ensure_case_config(case_id=case_id,actor=actor)
        out=self.runtime.local_ai.select_model(case_id=case_id,model_name=self.PREFERRED_MODEL,context_window=max(8192,min(32768,int(m.get('context_window') or 8192))),temperature=float(cfg.get('temperature') or .15),actor=actor,confirmation=f'OLLAMA MODEL 215 {case_id} AUSWAEHLEN')
        self._event(case_id,'preferred_model_activated','ai_model',model_id,{'model':self.PREFERRED_MODEL,'local_only':True,'reviewed':True,'automatic_external_fallback':False},actor); return {**out,'build248_model_id':model_id,'reviewed':True,'local_only':True,'automatic_external_fallback':False}
    def secret_inventory_review(self,case_id):
        self._case(case_id); rows=[dict(x) for x in self.db.all('SELECT secret_id,secret_ref,scope,storage_class,exposure_status,rotation_status,recorded_at FROM opsec_secret_inventory_243 WHERE case_id=? ORDER BY recorded_at DESC',(case_id,))]
        flagged=[x for x in rows if x['exposure_status'] in {'suspected','confirmed'} or x['rotation_status'] in {'review_due','rotate_now'}]
        return {'count':len(rows),'flagged_count':len(flagged),'flagged_refs':[x['secret_ref'] for x in flagged],'secret_values_stored':False}
    def deployment_readiness(self):
        required=['START_EAGLEEYE_PRO.bat','EAGLEEYE_PRO_248_0.py','requirements-runtime.txt','pyproject.toml']
        files={name:(self.base_dir/name).exists() for name in required}
        return {'required_files':files,'all_present':all(files.values()),'loopback_default':True,'self_healing_venv_launcher':True,'model_binary_bundled':False,'model_data_bundled':False}
    def stage_restore(self,*,case_id,backup_id,actor,confirmation):
        self._case(case_id)
        if confirmation!=f'PRODUCTION RESTORE 248 {backup_id} VORBEREITEN':raise PermissionError('explicit approval required')
        row=self.db.one('SELECT case_id FROM production_backup_links_248 WHERE backup_id=?',(backup_id,))
        if not row or row['case_id']!=case_id:raise PermissionError('backup is not registered for this case')
        out=self.recovery.stage_restore(backup_id=backup_id,requested_by=actor,confirmation=f'RESTORE 1859 {backup_id} VORBEREITEN')
        self._event(case_id,'restore_staged','backup',backup_id,{'restore_id':out['restore_id'],'automatic_swap':False,'restart_required':True},actor); return out
    def access_review(self,case_id):
        self._case(case_id)
        assignments=[dict(x) for x in self.db.all('''SELECT a.assignment_id,a.role_key,a.active,u.username FROM governance_case_assignments_132 a JOIN governance_users_132 u ON u.user_id=a.user_id WHERE a.case_id=? ORDER BY u.username,a.role_key''',(case_id,))]
        active=[a for a in assignments if int(a.get('active') or 0)==1]; findings=[]
        if not active:findings.append('no_active_case_assignment')
        if sum(1 for a in active if a['role_key']=='administrator')>1:findings.append('multiple_case_administrators_review_least_privilege')
        return {'assignments':assignments,'active_count':len(active),'findings':findings,'least_privilege_review_required':bool(findings)}
    def production_preflight(self,*,case_id,actor,confirmation):
        self._case(case_id)
        if confirmation!=f'PRODUCTION HARDENING 248 {case_id} PRUEFEN':raise PermissionError('explicit approval required')
        integ=self.db.one('PRAGMA integrity_check'); integrity=next(iter(integ.values())) if integ else 'unknown'; schema=(self.db.one("SELECT value FROM meta WHERE key='schema_version'") or {}).get('value','unknown')
        access=self.access_review(case_id); backups=self.recovery.recovery_dashboard(); op=self.sentinel.opsec_state(case_id); secrets=self.secret_inventory_review(case_id); deployment=self.deployment_readiness(); probe=self.db.one('SELECT * FROM production_runtime_probes_248 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)); runtime_state={'status':probe['status'],'preferred_model':probe['preferred_model'],'model_present':bool(probe['model_present']),'endpoint_healthy':bool(probe['endpoint_healthy'])} if probe else {'status':'not_probed','preferred_model':self.PREFERRED_MODEL,'model_present':False,'endpoint_healthy':False}
        findings=[]
        if integrity!='ok':findings.append('database_integrity_failed')
        try:
            if float(schema) < 248.0: findings.append('schema_version_mismatch')
        except Exception:
            findings.append('schema_version_mismatch')
        findings.extend(access['findings'])
        if runtime_state['status']!='ready_candidate':findings.append('preferred_local_mistral_not_ready')
        if op.get('risk_level') in {'high','critical'}:findings.append('opsec_high_or_critical')
        if int(backups.get('backups') or 0)==0:findings.append('no_verified_backup_recorded')
        if secrets['flagged_count']:findings.append('secret_exposure_or_rotation_due')
        if not deployment['all_present']:findings.append('deployment_files_missing')
        score=max(0,100-15*len(findings)); status='ready_for_review' if score>=85 and not any(x in findings for x in ('database_integrity_failed','opsec_high_or_critical')) else 'remediation_required'
        sid,now=new_id('prodsnap248'),now_ts(); payload={'snapshot_id':sid,'case_id':case_id,'integrity':integrity,'schema':schema,'access':access,'backup':backups,'opsec':op,'runtime':runtime_state,'secrets':secrets,'deployment':deployment,'score':score,'status':status,'findings':findings}; self.db.execute('INSERT INTO production_hardening_snapshots_248 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,case_id,integrity,schema,dumps(access),dumps(backups),dumps(op),dumps(runtime_state),score,status,dumps(findings),actor,now,_hash(payload))); self._event(case_id,'production_preflight','hardening_snapshot',sid,{'status':status,'readiness_score':score,'findings':findings},actor); return payload
    def review_preflight(self,*,snapshot_id,decision,rationale,reviewer,confirmation):
        s=self.db.one('SELECT * FROM production_hardening_snapshots_248 WHERE snapshot_id=?',(snapshot_id,))
        if not s:raise KeyError(snapshot_id)
        if confirmation!=f'PRODUCTION REVIEW 248 {snapshot_id} PRUEFEN':raise PermissionError('explicit approval required')
        if reviewer==s['created_by']:raise PermissionError('independent reviewer required')
        if decision not in self.REVIEW or len(_text(rationale))<20:raise ValueError('invalid review')
        if decision=='approved' and s['status']!='ready_for_review':raise PermissionError('remediation required before approval')
        rid,now=new_id('prodrev248'),now_ts(); self.db.execute('INSERT INTO production_hardening_reviews_248 VALUES(?,?,?,?,?,?,?,?)',(rid,snapshot_id,s['case_id'],decision,_text(rationale,3000),reviewer,now,_hash({'review':rid,'snapshot':snapshot_id,'decision':decision}))); return dict(self.db.one('SELECT * FROM production_hardening_reviews_248 WHERE review_id=?',(rid,)))
    def create_verified_backup(self,*,case_id,actor,confirmation):
        self._case(case_id)
        if confirmation!=f'PRODUCTION BACKUP 248 {case_id} ERSTELLEN':raise PermissionError('explicit approval required')
        b=self.recovery.create_backup(backup_type='manual',created_by=actor,confirmation='BACKUP 1859 ERSTELLEN'); v=self.recovery.verify_backup(b['backup_id'])
        if not v['valid']:raise RuntimeError('backup verification failed')
        lid,now=new_id('prodbackup248'),now_ts(); self.db.execute('INSERT INTO production_backup_links_248 VALUES(?,?,?,?,?,?,?)',(lid,case_id,b['backup_id'],dumps(v),actor,now,_hash({'link':lid,'backup':b['backup_id'],'valid':True}))); self._event(case_id,'verified_backup','backup',b['backup_id'],{'verified':True,'automatic_restore':False},actor); return {**b,'verification':v,'automatic_restore':False}
    def stage_training(self,*,case_id,actor,confirmation,limit=20):
        self._case(case_id)
        if confirmation!=f'PRODUCTION TRAINING 248 {case_id} VORBEREITEN':raise PermissionError('explicit approval required')
        rows=self.db.all('''SELECT s.*,r.decision,r.rationale FROM production_hardening_snapshots_248 s JOIN production_hardening_reviews_248 r ON r.snapshot_id=s.snapshot_id WHERE s.case_id=? ORDER BY r.reviewed_at DESC LIMIT ?''',(case_id,max(1,min(100,int(limit))))); ids=[]
        for s in rows:
            for stream in ('production_hardening_248','opsec_production_hardening_248'):
                if self.db.one('SELECT link_id FROM production_training_links_248 WHERE snapshot_id=? AND stream=?',(s['snapshot_id'],stream)):continue
                ctx={'training_stream':stream,'readiness_score':s['readiness_score'],'status':s['status'],'findings':_loads(s['findings_json'],[]),'runtime':_loads(s['runtime_state_json'],{}),'opsec':_loads(s['opsec_state_json'],{}),'review_decision':s['decision'],'boundary':'defensive hardening; no stealth guarantee; no autonomous OS/network changes'}
                inst='Bewerte eine lokale Private-Intelligence-Plattform auf Produktionsreife. Beruecksichtige Datenbankintegritaet, least privilege, Backup/Recovery, lokale AI-Runtime und OPSEC. Ein niedriger Exposure-Wert beweist keine Untrackbarkeit.'
                ex=self.training.add_example(case_id=case_id,instruction=inst,response=f"Review: {s['decision']}. {s['rationale']}",context=ctx,source_type=stream,source_ref=s['snapshot_id'],created_by=actor,confirmation=f'TRAINING EXAMPLE 228 {case_id} ANLEGEN')
                lid,now=new_id('prodtrain248'),now_ts(); self.db.execute('INSERT INTO production_training_links_248 VALUES(?,?,?,?,?,?,?,?)',(lid,case_id,s['snapshot_id'],ex['example_id'],stream,actor,now,_hash({'link':lid,'example':ex['example_id'],'stream':stream}))); ids.append(ex['example_id'])
        return {'case_id':case_id,'created':len(ids),'training_example_ids':ids,'review_status':'pending','automatic_model_or_policy_activation':False}
    def context(self,case_id):
        self._case(case_id); p=self.db.one('SELECT * FROM production_runtime_probes_248 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)); s=self.db.one('SELECT * FROM production_hardening_snapshots_248 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)); return {'production_hardening_context_248':{'preferred_local_model':self.PREFERRED_MODEL,'runtime_status':(p or {}).get('status','not_probed'),'readiness_status':(s or {}).get('status','not_assessed'),'readiness_score':int((s or {}).get('readiness_score') or 0),'rules':['Production readiness is not investigative evidence.','Mistral remains local-only and review-gated.','No cloud fallback, no stealth guarantee, no autonomous OS/network reconfiguration.']}}
    def dashboard(self,case_id):
        self._case(case_id); p=self.db.one('SELECT * FROM production_runtime_probes_248 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)); s=self.db.one('SELECT * FROM production_hardening_snapshots_248 WHERE case_id=? ORDER BY rowid DESC LIMIT 1',(case_id,)); return {'build':self.BUILD,'runtime_status':(p or {}).get('status','not_probed'),'mistral':self.PREFERRED_MODEL,'readiness_status':(s or {}).get('status','not_assessed'),'readiness_score':int((s or {}).get('readiness_score') or 0),'backups':int((self.recovery.recovery_dashboard()).get('backups') or 0)}
    def render_workspace_panel(self,*,case_id,csrf):
        d=self.dashboard(case_id); e=lambda x:html.escape(str(x or ''),quote=True)
        return f"""<section class='card' id='build248'><h2>Private-Intelligence Production Hardening · Build 248</h2><p>Produktionshaertung, Backup/Recovery, Fallzugriffe und lokale Mistral/Ollama-Integration. Kein Cloud-Fallback und kein Unsichtbarkeitsversprechen.</p><div class='metrics'><div class='metric'><div class='label'>Runtime</div><div class='value'>{e(d['runtime_status'])}</div></div><div class='metric'><div class='label'>Preferred model</div><div class='value'>Mistral</div></div><div class='metric'><div class='label'>Readiness</div><div class='value'>{d['readiness_score']}</div></div><div class='metric'><div class='label'>Backups</div><div class='value'>{d['backups']}</div></div></div><div class='grid'><div class='card'><h3>Ollama + mistral:latest</h3><form method='post' action='/build248/probe'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Lokale Runtime pruefen</button></form><form method='post' action='/build248/register-mistral'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Mistral als Candidate registrieren</button></form><form method='post' action='/build248/mistral-review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='model_id' placeholder='Model-ID aus Registrierung' required><textarea name='rationale' placeholder='Review-Begründung' required></textarea><button>Mistral unabhängig freigeben</button></form><form method='post' action='/build248/mistral-activate'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='model_id' placeholder='Reviewte Model-ID' required><button>Reviewtes Mistral lokal aktivieren</button></form><p class='muted'>Erwartet: mistral:latest / ID-Prefix 6577803aa9a0. Registrierung aktiviert nichts; erst Review + explizite Aktivierung.</p></div><div class='card'><h3>Production Preflight</h3><form method='post' action='/build248/preflight'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Hardening-Preflight</button></form><form method='post' action='/build248/backup'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Verifiziertes Backup erstellen</button></form><form method='post' action='/build248/restore-stage'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='backup_id' placeholder='Backup-ID' required><button>Restore nur vorbereiten</button></form></div><div class='card'><h3>Training</h3><form method='post' action='/build248/training'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Reviewte Hardening-Daten vorbereiten</button></form><p class='muted'>Co-AI und OPSEC-Sentinel: pending → Redaction → Review → Qualification. Keine automatische Aktivierung.</p></div></div></section>"""
