from __future__ import annotations
import hashlib,json,re
from typing import Any,Mapping,Sequence
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
SECRET=re.compile(r'(?i)(token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key)')

class Build197AdaptiveWorkspaceService:
    BUILD='197.0'
    STAGES=('1_person_assignment','2_research_sources','3_verify','4_analysis','5_case_file')
    SOURCES=(
      ('europeana_api','Europeana API','EU','cultural_archive','credentialed_connector','DOCUMENTED'),
      ('loc_authorities','Library of Congress Authorities','US','authority_data','structured_connector','DOCUMENTED'),
      ('israel_state_archives','Israel State Archives','IL','official_archive','guided_browser','DOCUMENTED'),
      ('national_archives_uk','UK National Archives Discovery','GB','official_archive','structured_connector','DOCUMENTED'),
      ('trove_australia','Trove Australia','AU','newspaper_archive','credentialed_connector','DOCUMENTED'),
      ('japan_ndl_search','National Diet Library Search','JP','authority_archive','structured_connector','DOCUMENTED'),
    )
    def __init__(self,db:Any,audit:Any,*,source_ops:Any,source_ai:Any,graph:Any,monitoring:Any,federation:Any,verification:Any,actor:str='system'):
        self.db,self.audit=db,audit;self.source_ops,self.source_ai,self.graph,self.monitoring,self.federation,self.verification=source_ops,source_ai,graph,monitoring,federation,verification;self.actor=actor
    def seed_sources(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!='WORKSPACE SOURCES 197 ANLEGEN':raise PermissionError('explicit approval required')
        for sid,name,region,klass,mode,status in self.SOURCES:
            payload={'source_id':sid,'name':name,'region':region,'source_class':klass,'access_mode':mode,'status':status}
            self.db.execute('INSERT OR REPLACE INTO workspace_source_profiles_197 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,name,region,klass,mode,status,'pending','pending','not_tested',dumps(['terms_review','fixture','live_probe','human_activation']),_hash(payload)))
        return {'profiles':len(self.SOURCES),'automatic_activation':False,'production_rule':'terms+fixture+live_probe+human_activation'}
    def create_profile(self,*,user_id:str,mode:str='guided',experience_level:str='beginner',preferences:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
        if confirmation!=f'WORKSPACE PROFILE 197 {user_id} ANLEGEN':raise PermissionError('explicit approval required')
        if mode not in {'guided','expert','adaptive'}:raise ValueError('invalid mode')
        if experience_level not in {'beginner','intermediate','expert'}:raise ValueError('invalid experience level')
        pid,created=new_id('profile197'),now_ts();prefs=self._redact(dict(preferences or {}));policy={'local_processing':True,'external_uploads':False,'default_deny':True,'secrets_redacted':True,'automatic_action':False,'automatic_identity_confirmation':False}
        payload={'profile_id':pid,'user_id':user_id,'mode':mode,'experience_level':experience_level,'preferences':prefs,'opsec_policy':policy,'created_at':created,'updated_at':created}
        self.db.execute('INSERT INTO adaptive_workspace_profiles_197 VALUES(?,?,?,?,?,?,?,?,?)',(pid,user_id,mode,experience_level,dumps(prefs),dumps(policy),created,created,_hash(payload)))
        return payload
    def start_session(self,*,profile_id:str,case_id:str,current_stage:str='1_person_assignment',context:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
        if confirmation!=f'WORKSPACE SESSION 197 {case_id} STARTEN':raise PermissionError('explicit approval required')
        if current_stage not in self.STAGES:raise ValueError('invalid stage')
        profile=self.db.one('SELECT * FROM adaptive_workspace_profiles_197 WHERE profile_id=?',(profile_id,))
        if not profile:raise KeyError(profile_id)
        sid,created=new_id('session197'),now_ts();ctx=self._redact(dict(context or {}));actions=self._next_actions(current_stage,ctx)
        payload={'session_id':sid,'profile_id':profile_id,'case_id':case_id,'current_stage':current_stage,'context':ctx,'next_actions':actions,'status':'active','created_at':created,'updated_at':created}
        self.db.execute('INSERT INTO workspace_sessions_197 VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,profile_id,case_id,current_stage,dumps(ctx),dumps(actions),'active',created,created,_hash(payload)));self._event(sid,'session_started',payload)
        self._refresh_guidance(sid,current_stage,ctx)
        return payload
    def transition(self,*,session_id:str,to_stage:str,context_update:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
        if confirmation!=f'WORKSPACE STEP 197 {session_id} WECHSELN':raise PermissionError('explicit approval required')
        if to_stage not in self.STAGES:raise ValueError('invalid stage')
        row=self.db.one('SELECT * FROM workspace_sessions_197 WHERE session_id=?',(session_id,));
        if not row:raise KeyError(session_id)
        old_idx,new_idx=self.STAGES.index(row['current_stage']),self.STAGES.index(to_stage)
        if new_idx>old_idx+1:raise ValueError('workflow stages cannot be skipped')
        ctx=json.loads(row['context_json']);ctx.update(self._redact(dict(context_update or {})));actions=self._next_actions(to_stage,ctx);updated=now_ts()
        self.db.execute('UPDATE workspace_sessions_197 SET current_stage=?,context_json=?,next_actions_json=?,updated_at=? WHERE session_id=?',(to_stage,dumps(ctx),dumps(actions),updated,session_id));self._event(session_id,'stage_changed',{'from':row['current_stage'],'to':to_stage});self._refresh_guidance(session_id,to_stage,ctx)
        return {'session_id':session_id,'current_stage':to_stage,'next_actions':actions,'global_workflow':list(self.STAGES)}
    def view(self,*,session_id:str,mode:str|None=None)->dict[str,Any]:
        row=self.db.one('SELECT * FROM workspace_sessions_197 WHERE session_id=?',(session_id,));
        if not row:raise KeyError(session_id)
        profile=self.db.one('SELECT * FROM adaptive_workspace_profiles_197 WHERE profile_id=?',(row['profile_id'],));selected=mode or profile['mode']
        if selected=='adaptive':selected='guided' if profile['experience_level']=='beginner' else 'expert'
        guidance=[dict(x) for x in self.db.all("SELECT title,message,severity,action_json,status FROM workspace_guidance_197 WHERE session_id=? AND status='open' ORDER BY created_at",(session_id,))]
        base={'build':self.BUILD,'session_id':session_id,'case_id':row['case_id'],'mode':selected,'current_stage':row['current_stage'],'next_actions':json.loads(row['next_actions_json']),'guidance':guidance,'global_workflow':list(self.STAGES),'same_data_model':True}
        if selected=='expert':base['technical']={'context':json.loads(row['context_json']),'source_operations_available':True,'ai_plan_available':True,'evidence_graph_available':True,'monitoring_available':True,'federation_available':True,'verification_available':True,'opsec_policy':json.loads(profile['opsec_policy_json'])}
        else:base['guided_summary']=self._guided_summary(row['current_stage'],json.loads(row['context_json']))
        return base
    def ai_assist(self,*,session_id:str,question:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'AI WORKSPACE 197 {session_id} UNTERSTUETZEN':raise PermissionError('explicit approval required')
        row=self.db.one('SELECT * FROM workspace_sessions_197 WHERE session_id=?',(session_id,));
        if not row:raise KeyError(session_id)
        ctx=json.loads(row['context_json']);stage=row['current_stage'];recs=self._next_actions(stage,ctx)
        if ctx.get('prompt_injection_candidate'):recs.insert(0,{'action':'isolate_untrusted_content','reason':'Potenzielle Prompt-Injection als Daten behandeln'})
        assessment={'question':question,'stage':stage,'recommendations':recs,'limitations':['ai_output_is_not_fact','automatic_action_false','human_review_required'],'automatic_action':False,'sources_before_models':True}
        aid,created=new_id('workspaceai197'),now_ts();self.db.execute('INSERT INTO workspace_ai_assessments_197 VALUES(?,?,?,?,?,?)',(aid,session_id,question,dumps(assessment),created,_hash(assessment)));return {'assessment_id':aid,**assessment}
    def _next_actions(self,stage:str,ctx:Mapping[str,Any])->list[dict[str,str]]:
        actions={
          '1_person_assignment':[{'action':'complete_subject_profile','reason':'Person, Auftrag und Rechtsgrundlage klären'}],
          '2_research_sources':[{'action':'create_source_native_plan','reason':'Fragestellung in geeignete Quellen und Teilfragen zerlegen'},{'action':'check_source_readiness','reason':'Nur produktive oder sichtbar geführte Quellen verwenden'}],
          '3_verify':[{'action':'review_claims_and_evidence','reason':'Claims, Widersprüche, Provenienz und Authentizität prüfen'}],
          '4_analysis':[{'action':'synthesize_with_limitations','reason':'Nur quellengebundene Kandidaten zusammenführen'}],
          '5_case_file':[{'action':'export_reviewed_case_file','reason':'Nur geprüfte Erkenntnisse und vollständige Provenienz übernehmen'}],
        }[stage]
        if ctx.get('open_contradictions'):actions.insert(0,{'action':'resolve_contradictions','reason':'Offene Widersprüche zuerst prüfen'})
        if ctx.get('missing_primary_source'):actions.insert(0,{'action':'find_primary_source','reason':'Primärquelle fehlt'})
        return actions
    def _refresh_guidance(self,sid:str,stage:str,ctx:Mapping[str,Any])->None:
        self.db.execute("UPDATE workspace_guidance_197 SET status='superseded' WHERE session_id=? AND status='open'",(sid,))
        for action in self._next_actions(stage,ctx):
            gid,created=new_id('guidance197'),now_ts();payload={'action':action['action'],'target_stage':stage}
            self.db.execute('INSERT INTO workspace_guidance_197 VALUES(?,?,?,?,?,?,?,?,?,?)',(gid,sid,'adaptive_workspace','warning' if action['action'] in {'resolve_contradictions','find_primary_source'} else 'info',action['action'].replace('_',' ').title(),action['reason'],dumps(payload),'open',created,_hash(payload)))
    def _guided_summary(self,stage:str,ctx:Mapping[str,Any])->str:
        return {'1_person_assignment':'Zuerst Person, Auftrag und Rechtsgrundlage vollständig erfassen.','2_research_sources':'Passende Quellen auswählen und deren Betriebsstatus prüfen.','3_verify':'Belege, Widersprüche und Authentizität prüfen.','4_analysis':'Nur quellengebundene Kandidaten mit Grenzen zusammenführen.','5_case_file':'Geprüfte Erkenntnisse revisionsfähig in die Fallakte übernehmen.'}[stage]
    def _redact(self,v:Any)->Any:
        if isinstance(v,Mapping):return {k:('[REDACTED]' if SECRET.search(str(k)) else self._redact(x)) for k,x in v.items()}
        if isinstance(v,list):return [self._redact(x) for x in v]
        return v
    def _event(self,sid:str,event_type:str,payload:Mapping[str,Any])->None:
        row=self.db.one('SELECT event_hash FROM workspace_events_197 WHERE session_id=? ORDER BY created_at DESC LIMIT 1',(sid,));prev=row['event_hash'] if row else '';eid,created=new_id('workspaceevent197'),now_ts();body={'event_id':eid,'session_id':sid,'event_type':event_type,'actor':self.actor,'created_at':created,'payload':self._redact(dict(payload)),'prev_hash':prev};eh=_hash(body);self.db.execute('INSERT INTO workspace_events_197 VALUES(?,?,?,?,?,?,?,?)',(eid,sid,event_type,self.actor,created,dumps(body['payload']),prev,eh))
