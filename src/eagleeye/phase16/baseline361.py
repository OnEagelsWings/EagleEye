from __future__ import annotations
import hashlib,json,uuid
from datetime import datetime,timezone
from typing import Any
from eagleeye.kernel.contracts import AgentTask,AgentResult,AgentRole,ActionClass,GatewayKind,ApprovalState,ResultStatus

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()

class AutonomousInvestigation361:
    POLICY='phase16.autonomous-investigation.v361'
    def __init__(self,db,*,build360,task_repository,actor='local-analyst'):
        self.db=db; self.build360=build360; self.tasks=task_repository; self.actor=actor
    def status(self):
        return {'policy_version':self.POLICY,'explicit_go_required':True,'autonomous_after_go':True,'plans_and_delegates':True,'monitors_crawler':True,'refuses_unapproved_sources':True,'forms_hypotheses':True,'writes_review_dossier':True,'direct_network_client':False,'auto_release':False}
    def run_cycle(self,*,case_id:str,max_ticks:int=8)->dict[str,Any]:
        go=self.build360.active_investigation_go(case_id)
        if not go: return {'case_id':case_id,'state':'go_required','ticks':0,'network_executed_by_supervisor':False}
        history=[]
        for _ in range(max(1,min(int(max_ticks),8))):
            tick=self.build360.investigation_supervisor_tick(case_id=case_id); history.append(tick)
            state=str((tick.get('research_wave') or {}).get('state') or '')
            if state in {'waiting_for_wave_terminal','stopped_for_review','go_required'}: break
        dossier=self.build360.build_investigation_dossier(case_id=case_id,refresh_hypotheses=True)
        hypotheses=[]
        for h in dossier.get('hypotheses') or []:
            score=float(h.get('confidence') or h.get('plausibility') or 0.0)
            hypotheses.append({**h,'plausibility':max(0.0,min(1.0,score)),'requires_human_review':True})
        dossier['hypotheses']=hypotheses
        dossier['phase16_review_state']='ready_for_lead_review'
        dossier['release_authority']='human_case_lead_only'
        return {'case_id':case_id,'state':'review_ready' if dossier else 'in_progress','ticks':len(history),'history':history,'dossier':dossier,'network_executed_by_supervisor':False}

class DefensiveOpsecSupervisor361:
    POLICY='phase16.defensive-opsec-supervisor.v361'
    BLOCKING={'block','quarantine','deny','blocked'}
    def __init__(self,db,*,opsec,task_repository,actor='local-analyst'):
        self.db=db; self.opsec=opsec; self.tasks=task_repository; self.actor=actor
    def status(self):
        return {'policy_version':self.POLICY,'autonomous_defensive_supervision':True,'can_block_pause_quarantine':True,'can_change_firewall':False,'can_change_os':False,'can_change_tor_config':False,'can_change_credentials':False}
    def protect_case(self,*,case_id:str)->dict[str,Any]:
        events=self.db.all("SELECT * FROM phase15_security_events WHERE case_id=? ORDER BY created_at DESC LIMIT 500",(case_id,))
        blocked_runs={str(r.get('search_run_id') or '') for r in events if str(r.get('disposition') or '').lower() in self.BLOCKING and r.get('search_run_id')}
        paused=[]
        for sr in sorted(blocked_runs):
            jobs=self.db.all("SELECT job_id,status FROM phase15_jobs WHERE case_id=? AND search_run_id=? AND status IN ('queued','retry','running')",(case_id,sr))
            for j in jobs:
                self.db.execute("UPDATE phase15_jobs SET status='cancelled',error_text=?,updated_at=? WHERE job_id=?",('OPSEC361 autonomous defensive stop',_now(),j['job_id']))
                paused.append(j['job_id'])
        summary={'case_id':case_id,'security_events':len(events),'blocked_search_runs':len(blocked_runs),'jobs_defensively_stopped':paused,'system_mutations':False,'policy_version':self.POLICY}
        return summary

class Phase16Baseline361:
    POLICY='phase16.pilot-external-validation-baseline.v361'
    TARGETS=(
      ('postgresql_team','Build 362','blocking_for_production'),('s3_minio','Build 363','blocking_for_scale'),('team_search','Build 363','blocking_for_scale'),
      ('remote_multi_user','Build 364','blocking_for_production'),('gleif_live','Build 366','data_gap'),('sec_edgar_live','Build 366','data_gap'),('companies_house_live','Build 366','data_gap'),
      ('procurement_public_money','Build 367','data_gap'),('sanctions_legal_archive','Build 368','data_gap'),('tor_gateway_read_only','Build 370','special_validation'),
      ('external_pentest','Build 379','blocking_for_production'),('external_load_failure','Build 379','blocking_for_production'),('professional_pilot','Build 380','blocking_for_production'))
    def __init__(self,db,*,build360,task_repository,ai,opsec,actor='local-analyst'):
        self.db=db; self.build360=build360; self.tasks=task_repository; self.ai=ai; self.opsec=opsec; self.actor=actor
    def validation_matrix(self):
        return [{'key':k,'planned_build':b,'class':c,'status':'not_run','externally_validated':False} for k,b,c in self.TARGETS]
    def phase16_status(self):
        return {'phase':'16','build':'361.0','goal':'Live Operations, Entity Intelligence & External Validation','builds_completed':1,'builds_total':20,'production_release_ready':False,'controlled_local_pilot_candidate':True,'validation_matrix':self.validation_matrix(),'ai':self.ai.status(),'opsec':self.opsec.status(),'crawler_improvement_build':361,'live_osint_rule':'contract tests never equal external validation'}
    def record_validation_receipt(self,*,case_id:str,target_key:str,status:str,evidence:dict[str,Any],external:bool=False)->dict[str,Any]:
        if target_key not in {x[0] for x in self.TARGETS}: raise ValueError('unknown phase16 validation target')
        task=AgentTask.create(case_id=case_id,actor=self.actor,agent_role=AgentRole.INVESTIGATION_SUPERVISOR,action_class=ActionClass.LOCAL_ANALYSIS,input_payload={'kind':'phase16_validation_receipt_v361','target_key':target_key,'external':bool(external)})
        self.tasks.create_task(task)
        out={'target_key':target_key,'status':status,'external_validation':bool(external),'evidence_hash':_sha(evidence),'recorded_at':_now(),'truthful_note':'external=true only records an operator-supplied receipt; Build 361 does not independently claim the external test occurred.'}
        self.tasks.append_result(AgentResult.create(task_id=task.task_id,status=ResultStatus.COMPLETED,output_payload=out,policy_reason='phase16_validation_receipt'))
        return {'task_id':task.task_id,**out}
