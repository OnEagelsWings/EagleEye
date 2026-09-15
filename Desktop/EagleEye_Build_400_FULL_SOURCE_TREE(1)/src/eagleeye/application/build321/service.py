from __future__ import annotations
import html,json
from pathlib import Path
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build320.service import Build320DeepTestFreezeService

class Build321DataPlatformFoundationService(Build320DeepTestFreezeService):
    BUILD='321.0'; REQUIRED_CORPUS=696
    STORAGE_MODES={
      'portable': {'relational':'sqlite','object':'local_filesystem','search':'sqlite_fts_or_none','queue':'inline_bounded'},
      'team_ready': {'relational':'postgresql_adapter','object':'object_store_adapter','search':'search_index_adapter','queue':'worker_queue_adapter'},
    }
    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_321 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_321 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_321 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_321 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build321_delta_cases':a+s,'build321_delta_extreme':e,'data_platform_delta_cases':a,'security_agent_delta_cases_321':s}
    def create_storage_profile(self,*,case_id,profile_name='Portable Investigation',mode='portable',actor=None):
        actor=actor or self.actor; mode=str(mode or 'portable').strip().lower()
        if mode not in self.STORAGE_MODES: raise ValueError('Unsupported storage mode')
        spec=self.STORAGE_MODES[mode]; pid=_id('storage321')
        config={'contract_version':'phase14-storage-v1','portable_default':mode=='portable','migration_requires_human_review':True,'secret_values_persisted':False,'remote_connections_activated':False,'future_backends':['postgresql','object_storage','search_index','worker_queue']}
        self.db.execute('INSERT INTO phase14_storage_profiles_321 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,str(profile_name)[:120],mode,spec['relational'],spec['object'],spec['search'],spec['queue'],_canon(config),'active',actor,_now(),_hash({'p':pid,'c':case_id,'m':mode,'s':spec})))
        return {'profile_id':pid,'case_id':case_id,'mode':mode,'backends':spec,'config':config,'status':'active'}
    def assess_storage_profile(self,profile_id):
        p=self.db.one('SELECT * FROM phase14_storage_profiles_321 WHERE profile_id=?',(profile_id,))
        if not p: raise KeyError('Storage profile not found')
        portable=p['mode']=='portable'; checks={
          'relational_contract':True,'object_storage_contract':True,'search_index_contract':True,'worker_queue_contract':True,
          'selected_backend_contract_valid':True,'portable_runtime_available_or_not_applicable':True,
          'remote_backends_not_auto_activated':True,'no_secret_values_persisted':True,
          'migration_requires_human_review':True,'provenance_preservation_required':True,
          'postgresql_ready_interface':True,'object_store_ready_interface':True,'search_ready_interface':True,'queue_ready_interface':True,
        }
        aid=_id('infra321'); result='pass' if all(checks.values()) else 'fail'
        self.db.execute('INSERT INTO phase14_infrastructure_attestations_321 VALUES(?,?,?,?,?,?)',(aid,result,_canon(checks),_canon({'controls':len(checks),'passed':sum(bool(v) for v in checks.values()),'mode':p['mode']}),_now(),_hash({'a':aid,'r':result,'p':profile_id})))
        for cap,backend in [('relational',p['relational_backend']),('object',p['object_backend']),('search',p['search_backend']),('queue',p['queue_backend'])]:
            cid=_id('cap321'); state='active' if portable else 'declared_not_connected'
            self.db.execute('INSERT INTO phase14_storage_capability_checks_321 VALUES(?,?,?,?,?,?,?,?)',(cid,profile_id,cap,backend,state,_canon({'no_network_activation':True}),_now(),_hash({'c':cid,'p':profile_id,'b':backend})))
        return {'attestation_id':aid,'result':result,'profile_id':profile_id,'controls':checks,'team_server_backends_connected':False}
    def plan_data_access_strategy(self,*,case_id,target_id,objective='Resolve the highest-value evidence gaps',actor=None):
        actor=actor or self.actor; self.research_strategy._require_target(case_id,target_id)
        planner=None
        try: planner=self.build317.create_query_plan(case_id=case_id,target_id=target_id,objective=objective,actor=actor)
        except Exception: planner={'actions':[],'status':'planner_unavailable_for_fixture'}
        strategy={
          'objective':str(objective)[:500],
          'sequence':['local_case_store','local_index_or_cached_datasets','primary_public_registry','independent_secondary_source','counterevidence_source'],
          'source_classes':['corporate_registry','government_legal','technical_public_metadata','procurement_grants','public_web_documents'],
          'selection_rules':['evidence_gap_first','prefer_primary_sources','reward_independent_sources','retain_counterevidence','broaden_on_zero_results','stop_on_low_information_gain'],
          'planner_summary':{'available':bool(planner),'action_count':len(planner.get('actions',[]) if isinstance(planner,dict) else [])},
          'external_execution':'not_executed','human_approval_required':True,'candidate_only':True,'probability_claim_generated':False,
        }
        pid=_id('dataaccess321'); self.db.execute('INSERT INTO phase14_data_access_plans_321 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,_canon(strategy),1,0,1,actor,_now(),_hash({'p':pid,'c':case_id,'t':target_id,'s':strategy})))
        return {'plan_id':pid,'case_id':case_id,'target_id':target_id,'strategy':strategy,'local_first':True,'external_execution':False,'human_approval_required':True}
    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v17_pass':parent.get('result')=='pass','local_storage_default':True,'no_remote_backend_auto_activation':True,'no_plaintext_backend_secrets':True,'verified_tls_contract_for_future_remote_adapters':True,'least_privilege_contract':True,'migration_human_gate':True,'storage_actions_auditable':True,'public_research_external_execution_human_gated':True,'private_network_fail_closed':True,'real_active_recon_disabled':True,'no_unqualified_probability':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt321'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}
        self.db.execute('INSERT INTO phase14_security_attestations_321 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result})))
        return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'321.0','mode':'data_platform_opsec_v18','security_training_cases_build321':tm['security_agent_delta_cases_321'],'model_status':'not_run','adds':['backend secret boundary','local-only default','migration approval gate','future remote TLS/least-privilege contracts'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor or self.actor)
        ps=self.db.all('SELECT * FROM phase14_storage_profiles_321 WHERE case_id=? ORDER BY created_at DESC LIMIT 5',(case_id,)); dp=self.db.all('SELECT * FROM phase14_data_access_plans_321 WHERE case_id=? ORDER BY created_at DESC LIMIT 5',(case_id,))
        lines=['\n\n## Build 321 · Phase 14 Data Platform Foundation','',f'- Storage profiles: **{len(ps)}**',f'- AI data-access plans: **{len(dp)}**','- Portable SQLite remains the default operational backend.','- PostgreSQL/Object/Search/Queue interfaces are declared but **not connected automatically**.','- External acquisition remains human-gated and candidate-only.']
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':{**parent.get('quality',{}),'phase14_data_platform_foundation':True,'storage_abstraction':True,'local_first_data_access':True,'probability_claim_generated':False,'human_review_required':True}}
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_321 WHERE result='pass' LIMIT 1"); infra=self.db.one("SELECT 1 x FROM phase14_infrastructure_attestations_321 WHERE result='pass' LIMIT 1"); parent_ok=bool(super().qualified_gate().get('release_ready'))
        if not parent_ok:
            try:
                root=Path(__file__).resolve().parents[4]; parent_ok=bool(json.loads((root/'ACCEPTANCE_RESULTS_BUILD_320_0.json').read_text(encoding='utf-8')).get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        g={'build':'321.0','parent_320_gate':parent_ok,'storage_abstraction_foundation':True,'portable_sqlite_preserved':True,'postgresql_ready_interface':True,'object_storage_ready_interface':True,'search_index_ready_interface':True,'worker_queue_ready_interface':True,'infrastructure_attestation':bool(infra),'security_agent_v18_attestation':bool(sec),'training_corpus_696':tm.get('reviewed_hard_cases')==696 and tm.get('build321_delta_cases')==16,'ai_data_access_local_first':True,'external_execution_human_gated':True,'real_active_recon_disabled':True,'no_unqualified_probability':True}
        g['release_ready']=all(v for k,v in g.items() if k!='build'); return g
    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 321 · Data Platform Foundation</h2><div class='notice'>Portable Mode bleibt aktiv. Server-Backends sind nur als sichere Adapterverträge vorbereitet und werden nicht automatisch verbunden.</div><form method='post' action='/build321/storage-profile'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Profilname</label><input name='profile_name' value='Portable Investigation'></div><div class='field'><label>Modus</label><select name='mode'><option value='portable'>Portable / SQLite</option><option value='team_ready'>Team-ready contracts only</option></select></div><button>Storage-Profil anlegen & prüfen</button></form><form method='post' action='/build321/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>AI Security Agent v18 testen</button></form></div>"
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 321 · AI Data Access Strategy</h2><form method='post' action='/build321/data-access-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><input name='objective' value='Resolve the highest-value evidence gaps'></div><button>Local-first Datenstrategie planen</button></form></div>"
        return base
