from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, secrets
from pathlib import Path
from typing import Any, Mapping

BUILD='400.0'
POLICY_ID='phase17.final-end-to-end-acceptance.v400'
CONFIRM_RUN='RUN PHASE17 FINAL ACCEPTANCE'
CONFIRM_REVIEW='REVIEW PHASE17 FINAL ACCEPTANCE'


def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256((v if isinstance(v,(bytes,bytearray)) else _canon(v).encode('utf-8'))).hexdigest()
def _sid(p): return p+'_'+secrets.token_hex(12)
def _read(p:Path):
    try:
        v=json.loads(p.read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception:return {}

STAGES=(
(1,'control_plane_381','Investigation Control Plane','source_registry_sources','PHASE_17_PROGRESS_BUILD_384.md'),
(2,'source_registry_382','Persistent Source Registry','source_coverage_ledger','PHASE_17_PROGRESS_BUILD_384.md'),
(3,'source_planner_383','Source Planner','acquisition_plan_ledger','PHASE_17_PROGRESS_BUILD_384.md'),
(4,'jurisdiction_waves_384','Jurisdiction / Research Waves','research_wave_plan_384','RELEASE_MANIFEST_BUILD_384_0.json'),
(5,'acquisition_385','Acquisition Orchestration','acquisition_packet_385','RELEASE_MANIFEST_BUILD_385_0.json'),
(6,'go_authority_386','Capability-scoped GO','execution_grant_386','RELEASE_MANIFEST_BUILD_386_0.json'),
(7,'controlled_executor_387','Controlled Executor','execution_dispatch_387','RELEASE_MANIFEST_BUILD_387_0.json'),
(8,'research_waves_388','Governed Research Waves','research_wave_session_388','RELEASE_MANIFEST_BUILD_388_0.json'),
(9,'result_intake_389','Result Intake / Evidence Candidates','evidence_candidate_389','RELEASE_MANIFEST_BUILD_389_0.json'),
(10,'corroboration_390','Evidence Review / Corroboration','corroboration_review_390','RELEASE_MANIFEST_BUILD_390_0.json'),
(11,'synthesis_391','Investigation Synthesis','investigation_claim_391','RELEASE_MANIFEST_BUILD_391_0.json'),
(12,'reasoning_392','Case Reasoning Workspace','case_reasoning_workspace_392','RELEASE_MANIFEST_BUILD_392_0.json'),
(13,'dialogue_393','Investigator Dialogue / Challenge','investigator_dialogue_session_393','RELEASE_MANIFEST_BUILD_393_0.json'),
(14,'revision_394','Discussion / Versioned Revision','versioned_revision_394','RELEASE_MANIFEST_BUILD_394_0.json'),
(15,'case_state_395','Case State Version Graph','case_state_active_395','RELEASE_MANIFEST_BUILD_395_0.json'),
(16,'reconciliation_396','Incremental Re-analysis','reconciliation_scan_396','RELEASE_MANIFEST_BUILD_396_0.json'),
(17,'argumentative_analyst_397','Argumentative AI Analyst','analyst_assessment_397','RELEASE_MANIFEST_BUILD_397_0.json'),
(18,'model_holdout_398','Model/Human Holdout Framework','holdout_suite_398','RELEASE_MANIFEST_BUILD_398_0.json'),
(19,'target_soak_399','72h Target Soak Framework','soak_plan_399','RELEASE_MANIFEST_BUILD_399_0.json'),
)

class Phase17FinalAcceptance400:
    """Read-only Phase-17 end-to-end acceptance ledger.

    It validates the assembled local platform and historical qualified receipts. It does not
    execute research, issue GO/LIVE, launch browsers, call models, mutate evidence, or turn
    missing external qualification into a pass.
    """
    def __init__(self,db:Any,audit:Any,*,governance:Any,holdout398:Any,soak399:Any,install_dir:Any,base_dir:Any,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.governance=governance; self.holdout398=holdout398; self.soak399=soak399
        self.install_dir=Path(install_dir); self.base_dir=Path(base_dir); self.actor=actor; self._init_schema()
    def _init_schema(self):
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS phase17_acceptance_run_400(
          run_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,status TEXT NOT NULL,passed_steps INTEGER NOT NULL,total_steps INTEGER NOT NULL,
          internal_acceptance INTEGER NOT NULL,external_holdout_qualified INTEGER NOT NULL,external_soak_qualified INTEGER NOT NULL,
          professional_pilot_ready INTEGER NOT NULL,phase18_entry_ready INTEGER NOT NULL,production_release_ready INTEGER NOT NULL,
          blockers_json TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,run_hash TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_phase17_acceptance_run_400_case ON phase17_acceptance_run_400(case_id,created_at);
        CREATE TABLE IF NOT EXISTS phase17_acceptance_step_400(
          step_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,ordinal INTEGER NOT NULL,stage_key TEXT NOT NULL,stage_label TEXT NOT NULL,
          status TEXT NOT NULL,evidence_ref TEXT NOT NULL,details_json TEXT NOT NULL,record_hash TEXT NOT NULL,UNIQUE(run_id,ordinal));
        CREATE INDEX IF NOT EXISTS idx_phase17_acceptance_step_400_run ON phase17_acceptance_step_400(run_id,ordinal);
        CREATE TABLE IF NOT EXISTS phase17_acceptance_review_400(
          review_id TEXT PRIMARY KEY,run_id TEXT NOT NULL UNIQUE,disposition TEXT NOT NULL,rationale TEXT NOT NULL,
          reviewed_by TEXT NOT NULL,reviewed_at TEXT NOT NULL,record_hash TEXT NOT NULL);
        '''); self.db.conn.commit()
    def _rowhash(self,d): return _sha({k:v for k,v in d.items() if k not in {'record_hash'}})
    def _auth(self,identity:Mapping[str,Any],case_id:str):
        # Final Phase-17 acceptance is an approval action, not a read action.
        # Case-scoped runs require a lead/reviewer role; global runs are therefore
        # restricted to the system administrator because no case membership exists.
        self.governance.authorize(dict(identity),case_id=case_id,capability='dossier.review',object_type='phase17_final_acceptance_v400',object_id=case_id or 'global')
    def _table_present(self,name): return bool(self.db.one("SELECT 1 x FROM sqlite_master WHERE type='table' AND name=?",(name,)))
    def _manifest_ok(self,b:int,ref:str):
        if b<=383:
            p=self.install_dir/ref
            return p.is_file(), {'evidence':'integrated_by_build384','path':ref}
        d=_read(self.install_dir/ref)
        reg=d.get('regression') or {}
        ok=(d.get('build')==f'{b}.0' and d.get('production_release_ready') is False and int(reg.get('functional_regressions',0))==0)
        return ok, {'path':ref,'build':d.get('build'),'code_fingerprint':d.get('code_fingerprint',''),'functional_regressions':reg.get('functional_regressions',0),'decision':d.get('decision','')}
    def _external(self):
        h=self.holdout398.qualification_status(); s=self.soak399.qualification_status()
        return bool(h.get('external_holdout_qualified')),bool(s.get('external_72h_soak_qualified')),h,s
    def blockers(self):
        hold,soak,_,_=self._external(); out=[]
        if not hold: out.append('build398_real_model_human_holdout_pending')
        if not soak: out.append('build399_real_72h_windows_firefox_soak_pending')
        out += ['independent_build379_operational_qualification_pending','real_connector_chain_validation_pending','external_long_running_crawler_load_pending','postgres_object_store_team_backend_pending','real_case_entity_resolution_holdout_pending','external_dossier_domain_review_pending','tor_onion_end_to_end_pending']
        return out
    def run_acceptance(self,*,identity:Mapping[str,Any],case_id:str='',confirmation:str)->dict[str,Any]:
        if confirmation!=CONFIRM_RUN: raise PermissionError('Exact confirmation required')
        self._auth(identity,case_id); run_id=_sid('p17acc'); steps=[]
        for ordinal,key,label,table,ref in STAGES:
            table_ok=self._table_present(table); receipt_ok,receipt=self._manifest_ok(ordinal+380 if ordinal<=3 else int(key.rsplit('_',1)[-1]),ref)
            ok=table_ok and receipt_ok
            steps.append({'step_id':_sid('p17step'),'run_id':run_id,'ordinal':ordinal,'stage_key':key,'stage_label':label,'status':'pass' if ok else 'fail','evidence_ref':ref,'details_json':_canon({'runtime_table':table,'runtime_table_present':table_ok,'receipt':receipt}),'record_hash':''})
        hold,soak,h,s=self._external(); runtime_ok=all(x['status']=='pass' for x in steps)
        blockers=self.blockers(); internal=runtime_ok
        status='internal_phase17_complete_external_qualification_pending' if internal and blockers else ('internal_phase17_complete' if internal else 'internal_acceptance_failed')
        row={'run_id':run_id,'case_id':case_id,'status':status,'passed_steps':sum(x['status']=='pass' for x in steps),'total_steps':len(steps),'internal_acceptance':int(internal),'external_holdout_qualified':int(hold),'external_soak_qualified':int(soak),'professional_pilot_ready':int(internal),'phase18_entry_ready':int(internal),'production_release_ready':0,'blockers_json':_canon(blockers),'created_by':str(identity.get('username') or identity.get('user_id') or self.actor),'created_at':_now(),'run_hash':'','record_hash':''}
        row['run_hash']=_sha({'steps':[{k:v for k,v in x.items() if k!='record_hash'} for x in steps],'external_holdout':h,'external_soak':s,'blockers':blockers})
        row['record_hash']=self._rowhash(row)
        with self.db.conn:
            self.db.conn.execute('INSERT INTO phase17_acceptance_run_400 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(row.values()))
            for x in steps:
                x['record_hash']=self._rowhash(x); self.db.conn.execute('INSERT INTO phase17_acceptance_step_400 VALUES(?,?,?,?,?,?,?,?,?)',tuple(x.values()))
        try:self.audit.log('phase17_acceptance','run',run_id,case_id,{'status':status,'internal':internal,'production':False})
        except Exception:pass
        return self.acceptance(run_id)
    def acceptance(self,run_id):
        r=self.db.one('SELECT * FROM phase17_acceptance_run_400 WHERE run_id=?',(run_id,));
        if not r: raise KeyError('Acceptance run not found')
        d=dict(r); d['blockers']=json.loads(d.pop('blockers_json')); d['steps']=[]
        for x in self.db.all('SELECT * FROM phase17_acceptance_step_400 WHERE run_id=? ORDER BY ordinal',(run_id,)):
            s=dict(x); s['details']=json.loads(s.pop('details_json')); d['steps'].append(s)
        rv=self.db.one('SELECT * FROM phase17_acceptance_review_400 WHERE run_id=?',(run_id,)); d['review']=dict(rv) if rv else None
        for k in ('internal_acceptance','external_holdout_qualified','external_soak_qualified','professional_pilot_ready','phase18_entry_ready','production_release_ready'):d[k]=bool(d[k])
        return d
    def review(self,*,run_id:str,identity:Mapping[str,Any],disposition:str,rationale:str,confirmation:str):
        if confirmation!=CONFIRM_REVIEW: raise PermissionError('Exact confirmation required')
        run=self.acceptance(run_id); self._auth(identity,run['case_id'])
        if disposition not in {'accept_internal_phase17','needs_remediation'}: raise ValueError('Unsupported disposition')
        if disposition=='accept_internal_phase17' and not run['internal_acceptance']: raise ValueError('Internal acceptance has failures')
        row={'review_id':_sid('p17review'),'run_id':run_id,'disposition':disposition,'rationale':str(rationale),'reviewed_by':str(identity.get('username') or identity.get('user_id') or self.actor),'reviewed_at':_now(),'record_hash':''}; row['record_hash']=self._rowhash(row)
        with self.db.conn:self.db.conn.execute('INSERT INTO phase17_acceptance_review_400 VALUES(?,?,?,?,?,?,?)',tuple(row.values()))
        return self.acceptance(run_id)
    def verify(self,run_id):
        run=self.db.one('SELECT * FROM phase17_acceptance_run_400 WHERE run_id=?',(run_id,)); bad=[]
        if not run:return {'valid':False,'violations':['missing_run']}
        if dict(run)['record_hash']!=self._rowhash(dict(run)):bad.append('run_hash')
        for table in ('phase17_acceptance_step_400','phase17_acceptance_review_400'):
            for r in self.db.all(f'SELECT * FROM {table} WHERE run_id=?',(run_id,)):
                if dict(r)['record_hash']!=self._rowhash(dict(r)):bad.append(table)
        return {'valid':not bad,'violations':bad}
    def export_dossier(self,*,run_id:str,outdir:Any)->dict[str,str]:
        run=self.acceptance(run_id)
        if not run.get('review') or run['review'].get('disposition')!='accept_internal_phase17': raise PermissionError('Reviewed internal Phase-17 acceptance required')
        out=Path(outdir); out.mkdir(parents=True,exist_ok=True); base=out/f'EagleEye_Phase17_Acceptance_{run_id}'
        payload={'title':'EagleEye Phase 17 Final Acceptance','build':BUILD,'run':run,'truthful_scope':{'internal_phase17_complete':run['internal_acceptance'],'production_release_ready':False,'external_blockers':run['blockers']}}
        jp=base.with_suffix('.json'); jp.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
        md=['# EagleEye Phase 17 Final Acceptance',f"Build: {BUILD}",f"Internal acceptance: {run['internal_acceptance']}",f"Phase 18 entry ready: {run['phase18_entry_ready']}",f"Production release ready: {run['production_release_ready']}",'','## Stages']
        md += [f"- {x['ordinal']:02d}. {x['stage_label']}: {x['status']}" for x in run['steps']]
        md += ['','## External blockers']+[f'- {x}' for x in run['blockers']]
        mp=base.with_suffix('.md'); mp.write_text('\n'.join(md)+'\n',encoding='utf-8')
        try:
            from eagleeye_pro.reporting.docx_writer import write_docx
            dp=write_docx(base.with_suffix('.docx'),'EagleEye Phase 17 Final Acceptance',[("Abschlussstatus",[f"Internal Phase 17 complete: {run['internal_acceptance']}",f"Phase 18 entry ready: {run['phase18_entry_ready']}","Production release ready: False"]),("Phase-17-Schritte",[["#","Stage","Status","Evidence"]]+[[str(x['ordinal']),x['stage_label'],x['status'],x['evidence_ref']] for x in run['steps']]),('Offene externe Nachweise',run['blockers'])])
            docx=str(dp)
        except Exception: docx=''
        return {'json':str(jp),'markdown':str(mp),'docx':docx}
    def latest(self,case_id=''):
        r=self.db.one('SELECT run_id FROM phase17_acceptance_run_400 WHERE case_id=? ORDER BY created_at DESC,run_id DESC LIMIT 1',(case_id,)); return self.acceptance(r['run_id']) if r else None
    def status(self):
        hold,soak,_,_=self._external(); return {'build':BUILD,'policy':POLICY_ID,'phase17_builds_completed':20,'internal_end_to_end_acceptance_ledger':True,'historical_receipt_validation':True,'runtime_schema_stage_validation':True,'acceptance_dossier_export':True,'external_holdout_qualified':hold,'external_72h_soak_qualified':soak,'production_release_ready':False,'broad_live_research_release_ready':False,'direct_network_fetch':False,'browser_launch_authority':False,'model_execution_authority':False,'execution_authority':False,'automatic_go':False,'automatic_live_confirmation':False,'automatic_evidence_promotion':False,'automatic_truth_acceptance':False}
