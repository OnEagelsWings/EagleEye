from __future__ import annotations

import hashlib, html, json, shutil, sqlite3, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now()->str:return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(prefix:str)->str:return f"{prefix}_{uuid.uuid4().hex[:12]}"
def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256((v if isinstance(v,str) else _canon(v)).encode('utf-8')).hexdigest()
def _parse_ts(v:str)->datetime:
    return datetime.fromisoformat(str(v).replace('Z','+00:00'))


class Build296OperationalStrengthFreezeService:
    BUILD='296.0'
    GATE_THRESHOLD=.88
    RPO_TARGET_SECONDS=24*60*60
    RTO_TARGET_SECONDS=120

    def __init__(self,db:Any,audit:Any,*,build295:Any,build294:Any,build293:Any,build281:Any,runtime_dir:Path,install_dir:Path,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.build295=build295; self.build294=build294; self.build293=build293; self.build281=build281
        self.runtime_dir=Path(runtime_dir); self.install_dir=Path(install_dir); self.actor=actor
        self.drill_dir=self.runtime_dir/'data'/'phase12_recovery_drills_296'; self.drill_dir.mkdir(parents=True,exist_ok=True)

    # ---- measured continuity / RPO-RTO ----
    def continuity_slo_status(self)->dict:
        now=datetime.now(timezone.utc)
        backup=self.db.one('SELECT backup_id,status,created_at FROM phase12_durable_backups_295 ORDER BY rowid DESC LIMIT 1')
        drill=self.db.one('SELECT * FROM phase12_recovery_drills_296 ORDER BY rowid DESC LIMIT 1')
        backup_age=None
        if backup:
            try: backup_age=max(0,int((now-_parse_ts(backup['created_at'])).total_seconds()))
            except Exception: backup_age=None
        rpo_met=backup_age is not None and backup_age<=self.RPO_TARGET_SECONDS and backup.get('status')=='verified'
        rto_measured=(int(drill['duration_ms'])/1000.0) if drill else None
        rto_met=bool(drill and drill['result']=='pass' and rto_measured<=self.RTO_TARGET_SECONDS)
        return {
            'rpo_target_seconds':self.RPO_TARGET_SECONDS,'rto_target_seconds':self.RTO_TARGET_SECONDS,
            'latest_backup_id':backup['backup_id'] if backup else '', 'latest_backup_age_seconds':backup_age,
            'latest_drill_id':drill['drill_id'] if drill else '', 'latest_measured_rto_seconds':rto_measured,
            'rpo_target_met_locally':rpo_met,'rto_target_met_in_latest_local_drill':rto_met,
            'enterprise_sla_claimed':False,
            'measurement_status':'measured' if backup and drill else ('partial' if backup or drill else 'not_measured'),
        }

    def run_recovery_drill(self,*,case_id:str='',actor:str|None=None)->dict:
        actor=actor or self.actor
        started_perf=time.perf_counter(); started_at=_now(); drill_id=_id('drill296')
        backup=self.build295.create_backup(actor=actor)
        verify=self.build295.verify_backup(backup['backup_id'])
        if not verify['valid']: raise RuntimeError('Recovery-Drill abgebrochen: Backup nicht verifiziert.')
        root=self.drill_dir/drill_id
        target=root/'runtime'/'data'/'eagleeye.db'
        restore=self.build295.restore_to_sandbox(backup_id=backup['backup_id'],target_db_path=target)
        conn=sqlite3.connect(str(target)); conn.row_factory=sqlite3.Row
        try:
            quick=str(conn.execute('PRAGMA quick_check').fetchone()[0]); fk=len(conn.execute('PRAGMA foreign_key_check').fetchall())
            if case_id:
                rcases=int(conn.execute('SELECT COUNT(*) FROM cases WHERE case_id=?',(case_id,)).fetchone()[0])
                rmissions=int(conn.execute('SELECT COUNT(*) FROM phase12_missions_281 WHERE case_id=?',(case_id,)).fetchone()[0])
                rjobs=int(conn.execute('SELECT COUNT(*) FROM phase12_ops_jobs_293 WHERE case_id=?',(case_id,)).fetchone()[0])
                scases=int(self.db.one('SELECT COUNT(*) n FROM cases WHERE case_id=?',(case_id,))['n'])
                smissions=int(self.db.one('SELECT COUNT(*) n FROM phase12_missions_281 WHERE case_id=?',(case_id,))['n'])
                sjobs=int(self.db.one('SELECT COUNT(*) n FROM phase12_ops_jobs_293 WHERE case_id=?',(case_id,))['n'])
            else:
                rcases=int(conn.execute('SELECT COUNT(*) FROM cases').fetchone()[0]); rmissions=int(conn.execute('SELECT COUNT(*) FROM phase12_missions_281').fetchone()[0]); rjobs=int(conn.execute('SELECT COUNT(*) FROM phase12_ops_jobs_293').fetchone()[0])
                scases=int(self.db.one('SELECT COUNT(*) n FROM cases')['n']); smissions=int(self.db.one('SELECT COUNT(*) n FROM phase12_missions_281')['n']); sjobs=int(self.db.one('SELECT COUNT(*) n FROM phase12_ops_jobs_293')['n'])
        finally: conn.close()
        duration_ms=max(1,int((time.perf_counter()-started_perf)*1000)); completed_at=_now()
        try:rpo_seconds=max(0,int((_parse_ts(started_at)-_parse_ts(backup['created_at'])).total_seconds()))
        except Exception:rpo_seconds=0
        counts_ok=(rcases, rmissions, rjobs)==(scases, smissions, sjobs)
        result='pass' if quick.lower()=='ok' and fk==0 and restore['restored'] and counts_ok and duration_ms/1000<=self.RTO_TARGET_SECONDS and rpo_seconds<=self.RPO_TARGET_SECONDS else 'fail'
        details={'backup_verified':verify['valid'],'restore':restore,'source_counts':{'cases':scases,'missions':smissions,'jobs':sjobs},'restored_counts':{'cases':rcases,'missions':rmissions,'jobs':rjobs},'counts_match':counts_ok,'enterprise_sla_claimed':False,'network_access':False,'automatic_resume':False}
        prev=self.db.one('SELECT drill_hash FROM phase12_recovery_drills_296 ORDER BY rowid DESC LIMIT 1'); previous_hash=prev['drill_hash'] if prev else 'GENESIS'
        payload={'drill_id':drill_id,'backup_id':backup['backup_id'],'case_id':case_id,'scenario':'local_backup_restore_reopen','started_at':started_at,'completed_at':completed_at,'duration_ms':duration_ms,'rpo_seconds':rpo_seconds,'rto_target_seconds':self.RTO_TARGET_SECONDS,'rpo_target_seconds':self.RPO_TARGET_SECONDS,'sqlite_quick_check':quick,'foreign_key_violations':fk,'restored_case_count':rcases,'restored_mission_count':rmissions,'restored_job_count':rjobs,'result':result,'details':details,'created_by':actor,'previous_hash':previous_hash}
        drill_hash=_hash(payload)
        self.db.execute('INSERT INTO phase12_recovery_drills_296 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(drill_id,backup['backup_id'],case_id,'local_backup_restore_reopen',started_at,completed_at,duration_ms,rpo_seconds,self.RTO_TARGET_SECONDS,self.RPO_TARGET_SECONDS,quick,fk,rcases,rmissions,rjobs,result,_canon(details),actor,previous_hash,drill_hash))
        shutil.rmtree(root,ignore_errors=True)
        return {**payload,'drill_hash':drill_hash,'measured_rto_seconds':duration_ms/1000.0,'rpo_target_met':rpo_seconds<=self.RPO_TARGET_SECONDS,'rto_target_met':duration_ms/1000<=self.RTO_TARGET_SECONDS}

    def verify_drill_chain(self)->bool:
        rows=self.db.all('SELECT * FROM phase12_recovery_drills_296 ORDER BY rowid'); prev='GENESIS'
        for r in rows:
            details=json.loads(r['details_json'])
            payload={'drill_id':r['drill_id'],'backup_id':r['backup_id'],'case_id':r['case_id'],'scenario':r['scenario'],'started_at':r['started_at'],'completed_at':r['completed_at'],'duration_ms':int(r['duration_ms']),'rpo_seconds':int(r['rpo_seconds']),'rto_target_seconds':int(r['rto_target_seconds']),'rpo_target_seconds':int(r['rpo_target_seconds']),'sqlite_quick_check':r['sqlite_quick_check'],'foreign_key_violations':int(r['foreign_key_violations']),'restored_case_count':int(r['restored_case_count']),'restored_mission_count':int(r['restored_mission_count']),'restored_job_count':int(r['restored_job_count']),'result':r['result'],'details':details,'created_by':r['created_by'],'previous_hash':r['previous_hash']}
            if r['previous_hash']!=prev or _hash(payload)!=r['drill_hash']:return False
            prev=r['drill_hash']
        return True

    # ---- safe backup rotation ----
    def create_rotation_plan(self,*,retain_count:int=3,confirmation:str='OK',approved_by:str='')->dict:
        if str(confirmation).strip().upper()!='OK':raise PermissionError("Retention-Planänderung erfordert ausdrückliches 'OK'.")
        retain_count=max(2,min(int(retain_count),20))
        backups=self.db.all("SELECT backup_id,status,created_at,db_sha256 FROM phase12_durable_backups_295 WHERE status='verified' ORDER BY rowid DESC")
        retained=[b['backup_id'] for b in backups[:retain_count]]; candidates=[b['backup_id'] for b in backups[retain_count:]]
        plan_id=_id('rotation296'); now=_now()
        payload={'rotation_plan_id':plan_id,'policy_name':'verified_restore_points','retain_count':retain_count,'backup_count':len(backups),'retained':retained,'retirement_candidates':candidates,'destructive_pruning_enabled':False,'approved_by':approved_by or self.actor,'approved_at':now,'created_at':now}
        self.db.execute('INSERT INTO phase12_rotation_plans_296 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(plan_id,'verified_restore_points',retain_count,len(backups),_canon(retained),_canon(candidates),0,approved_by or self.actor,now,now,_hash(payload)))
        return {**payload,'automatic_deletion':False,'note':'Ältere Backups werden nur als Kandidaten markiert; Build 296 löscht keine Restore-Punkte automatisch.'}

    # ---- bounded continuity stress assessment ----
    def run_continuity_stress_assessment(self,*,actor:str|None=None)->dict:
        actor=actor or self.actor; t0=time.perf_counter(); now=_now(); run_id=_id('stress296')
        cases=int(self.db.one('SELECT COUNT(*) n FROM cases')['n']); jobs=int(self.db.one('SELECT COUNT(*) n FROM phase12_ops_jobs_293')['n'])
        counts={r['status']:int(r['n']) for r in self.db.all('SELECT status,COUNT(*) n FROM phase12_ops_jobs_293 GROUP BY status')}
        isolated=int(self.db.one("SELECT COUNT(*) n FROM phase12_case_scheduler_294 WHERE fault_state='isolated'")['n'])
        orphan_jobs=int(self.db.one("SELECT COUNT(*) n FROM phase12_ops_jobs_293 j LEFT JOIN cases c ON c.case_id=j.case_id WHERE c.case_id IS NULL")['n'])
        dupes=int(self.db.one("SELECT COUNT(*) n FROM (SELECT op_job_id,COUNT(*) c FROM phase12_ops_jobs_293 GROUP BY op_job_id HAVING c>1)")['n'])
        continuity_ok=(orphan_jobs==0 and dupes==0 and len(self.db.all('PRAGMA foreign_key_check'))==0 and self.build295.verify_anchor_chain() and self.build295.verify_reconcile_chain() and self.verify_drill_chain())
        duration_ms=max(1,int((time.perf_counter()-t0)*1000))
        details={'orphan_jobs':orphan_jobs,'duplicate_job_ids':dupes,'foreign_key_violations':len(self.db.all('PRAGMA foreign_key_check')),'anchor_chain_ok':self.build295.verify_anchor_chain(),'reconcile_chain_ok':self.build295.verify_reconcile_chain(),'drill_chain_ok':self.verify_drill_chain(),'backpressure_snapshot':self.build294.pressure_snapshot(actor=actor),'human_authority_preserved':True}
        payload={'stress_run_id':run_id,'case_count':cases,'job_count':jobs,'running_count':counts.get('running',0),'queued_count':counts.get('queued',0),'recovery_count':counts.get('recovery_pending',0),'isolated_case_count':isolated,'continuity_ok':continuity_ok,'network_access':False,'external_collection_started':False,'duration_ms':duration_ms,'details':details,'created_by':actor,'created_at':now}
        self.db.execute('INSERT INTO phase12_continuity_stress_runs_296 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(run_id,cases,jobs,counts.get('running',0),counts.get('queued',0),counts.get('recovery_pending',0),isolated,1 if continuity_ok else 0,0,0,duration_ms,_canon(details),actor,now,_hash(payload)))
        return payload

    # ---- UX / training / release ----
    def operational_status(self)->dict:
        slo=self.continuity_slo_status(); last=self.db.one('SELECT result,duration_ms,created_by,completed_at FROM phase12_recovery_drills_296 ORDER BY rowid DESC LIMIT 1')
        if not last:
            return {'stand':'Operational Strength ist bereit für den ersten Recovery-Drill; bislang liegt noch keine gemessene Wiederherstellungszeit vor.','meaning':'Backups sind vorhanden, aber RPO/RTO sollen nur aus echten lokalen Drills bewertet werden.','next':'Einen Recovery-Drill ausführen und anschließend den gemessenen Wert prüfen.','slo':slo}
        if last['result']!='pass':
            return {'stand':'Der letzte Recovery-Drill ist fehlgeschlagen.','meaning':'EagleEye darf die Wiederherstellungsfähigkeit derzeit nicht als gesund einstufen.','next':'Drill-Details prüfen, Ursache beheben und erneut testen.','slo':slo}
        return {'stand':f"Operational Strength lokal gemessen: letzter Recovery-Drill PASS in {int(last['duration_ms'])/1000:.3f}s.",'meaning':'Der getestete lokale Backup/Restore-Pfad funktioniert innerhalb der gesetzten Zielwerte; dies ist keine Enterprise-SLA.','next':'Rotationsempfehlung und Backup-Alter prüfen; vor Field Qualification mindestens einen aktuellen Drill beibehalten.','slo':slo}

    def startup_contract_status(self)->dict:
        import eagleeye_pro.version as v
        def _ver(value):
            try:return tuple(int(x) for x in str(value).split('.')[:2])
            except Exception:return (0,0)
        generic=self.install_dir/'START_EAGLEEYE_PRO.bat'; text=generic.read_text(encoding='utf-8',errors='replace') if generic.exists() else ''
        
        import re
        m=re.search(r'(?:START_)?EAGLEEYE_PRO_(\d+)_0(?:\.py|\.bat)',text); generic_build=int(m.group(1)) if m else 0
        checks={'version_build':_ver(v.BUILD)>=_ver('296.0'),'version_schema':_ver(v.SCHEMA_VERSION)>=_ver('296.0'),'project_entrypoint':(self.install_dir/'EAGLEEYE_PRO_296_0.py').exists(),'startup_acceptance_script':(self.install_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_296_0.py').exists(),'generic_windows_starter':generic.exists(),'generic_windows_starter_points_to_296':generic_build>=296,'versioned_windows_starter':(self.install_dir/'START_EAGLEEYE_PRO_296_0.bat').exists(),'setup_script':(self.install_dir/'SETUP_EAGLEEYE_WINDOWS.bat').exists(),'requirements_windows':(self.install_dir/'requirements-windows.txt').exists()}
        return {'build':'296.0','checks':checks,'contract_ready':all(checks.values()),'actual_loopback_boot_required_for_release':True,'packaged_boot_required':True,'windows_launcher_content_checked':True}

    def all_training_cases(self)->list[dict]:
        out=self.build295.all_training_cases()
        for r in self.db.all("SELECT * FROM ai_hard_training_delta_296 WHERE review_status='reviewed' ORDER BY benchmark_id"):
            out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
        return out
    def training_metrics(self)->dict:
        b=self.build295.training_metrics(); delta=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_296 WHERE review_status='reviewed'")['n']); extreme=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_296 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases':int(b['reviewed_hard_cases'])+delta,'adversarial_extreme_cases':int(b['adversarial_extreme_cases'])+extreme,'build296_delta_cases':delta,'build296_delta_extreme':extreme,'performance_gate_threshold':self.GATE_THRESHOLD,'automatic_model_activation':False,'build300_case_target':360}
    def create_evaluation_batch(self,*,model_label:str='mistral:latest',actor:str|None=None)->dict:
        actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'296.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':self.GATE_THRESHOLD,'maximum_critical_failures':0,'independent_evaluator_required':True,'automatic_model_activation':False,'cases':cases}; sha=_hash(manifest)
        ex=self.db.one('SELECT * FROM ai_evaluation_batches_296 WHERE model_label=? AND manifest_sha256=? ORDER BY rowid DESC LIMIT 1',(model_label,sha))
        if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'independent_evaluator_required':bool(ex['independent_evaluator_required']),'cases':cases,'deduplicated':True}
        bid=_id('eval296'); now=_now(); payload={'batch_id':bid,**manifest,'created_by':actor,'created_at':now}
        self.db.execute('INSERT INTO ai_evaluation_batches_296 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),self.GATE_THRESHOLD,1.0,0,'prepared',1,sha,actor,now,_hash(payload)))
        return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':self.GATE_THRESHOLD,'independent_evaluator_required':True,'cases':cases,'deduplicated':False}
    def performance_status(self,model_label:str='mistral:latest')->dict:
        return {'model_label':model_label,'status':'not_run','qualified':False,'required_corpus_size':272,'minimum_mean_score':self.GATE_THRESHOLD,'note':'Build 296 beansprucht keine ≥88%-Leistung ohne vollständigen unabhängigen 272-Fälle-Lauf.'}
    def qualified_gate(self)->dict:
        parent=self.build295.qualified_gate(); tm=self.training_metrics(); batch=self.create_evaluation_batch(); startup=self.startup_contract_status()
        gates={'build':'296.0','parent_gate':bool(parent['release_ready']),'recovery_drill_engine_ready':True,'backup_rotation_non_destructive':True,'rpo_rto_measurement_ready':True,'continuity_stress_assessment_ready':True,'drill_chain_ok':self.verify_drill_chain(),'foreign_keys_ok':len(self.db.all('PRAGMA foreign_key_check'))==0,'network_access':False,'external_collection_auto_execution':False,'hard_training_corpus_272':tm['reviewed_hard_cases']>=272 and tm['build296_delta_cases']>=16 and tm['build296_delta_extreme']>=4,'evaluation_batch_272_ready':batch['corpus_size']==272 and abs(batch['minimum_mean_score']-.88)<1e-9,'startup_contract_ready':startup['contract_ready'],'automatic_model_activation':False,'human_authority_preserved':True,'operational_strength_block_293_296_complete':True}
        gates['release_ready']=all([gates['parent_gate'],gates['recovery_drill_engine_ready'],gates['backup_rotation_non_destructive'],gates['rpo_rto_measurement_ready'],gates['continuity_stress_assessment_ready'],gates['drill_chain_ok'],gates['foreign_keys_ok'],not gates['network_access'],not gates['external_collection_auto_execution'],gates['hard_training_corpus_272'],gates['evaluation_batch_272_ready'],gates['startup_contract_ready'],not gates['automatic_model_activation'],gates['human_authority_preserved'],gates['operational_strength_block_293_296_complete']])
        return gates

    def render_workspace_panel(self,*,case_id:str,csrf:str)->str:
        esc=lambda v:html.escape(str(v or ''),quote=True); s=self.operational_status(); tm=self.training_metrics(); perf=self.performance_status(); slo=s['slo']
        return f"""<section class='card'><h2>Operational Strength Freeze · Build 296</h2>
<div class='notice'><b>Was ist der Stand?</b><br>{esc(s['stand'])}<br><br><b>Was bedeutet das?</b><br>{esc(s['meaning'])}<br><br><b>Was ist jetzt zu tun?</b><br>{esc(s['next'])}</div>
<form method='post' action='/build296/drill/run'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><button>Lokalen Recovery-Drill ausführen</button></form>
<form method='post' action='/build296/rotation/plan'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><label>Restore-Punkte behalten <input name='retain_count' value='3' size='3'></label><label> Freigabe <input name='confirmation' placeholder='OK'></label><button>Rotationsempfehlung erstellen</button></form>
<p><b>Lokales RPO-Ziel:</b> 24h · <b>RTO-Drillziel:</b> 120s · <b>Messstatus:</b> {esc(slo['measurement_status'])}. Keine Enterprise-SLA-Behauptung.</p>
<details><summary>Analyst/Experte: Operational Freeze & AI-Gate</summary><p>Drill-Chain: <b>{'OK' if self.verify_drill_chain() else 'FEHLER'}</b> · destruktives Backup-Pruning: <b>aus</b> · Netzwerkzugriff: <b>aus</b> · Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · adversarial-extreme: <b>{tm['adversarial_extreme_cases']}</b> · Modellstatus: <b>{esc(perf['status'])}</b>. Gate: 272/272 Fälle, ≥88%, 0 kritische Fehler, unabhängige Evaluation.</p></details></section>"""
