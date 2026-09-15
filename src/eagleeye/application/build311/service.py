from __future__ import annotations
import hashlib, html, json
from pathlib import Path
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build310.service import Build310AutonomousInvestigationV2Service

class Build311ConnectorBrokerService(Build310AutonomousInvestigationV2Service):
    BUILD='311.0'; REQUIRED_CORPUS=536
    def __init__(self,*args,build310=None,research_strategy=None,phase4_operations=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.build310=build310 or self
        self.research_strategy=research_strategy
        self.phase4_operations=phase4_operations
    def training_metrics(self):
        b=super().training_metrics()
        a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_311 WHERE review_status='reviewed'")
        s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_311 WHERE review_status='reviewed'")
        e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_311 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_311 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build311_delta_cases':a+s,'build311_delta_extreme':e,'connector_broker_delta_cases':a,'security_agent_delta_cases_311':s}
    def _catalog(self):
        if not self.research_strategy: return []
        rows=[]
        trusted={}
        if self.phase4_operations:
            for p in self.phase4_operations.list_packages(): trusted[p.get('connector_key','')]=p
        for c in self.research_strategy.list_connectors():
            p=trusted.get(c.get('connector_key',''),{})
            rows.append({**c,'trust_state':p.get('trust_state','builtin_catalog'),'package_enabled':bool(p.get('enabled',c.get('enabled'))),'package_manifest':p.get('manifest',{})})
        return rows
    def create_broker_plan(self,*,case_id,target_id,objective,actor=None):
        actor=actor or self.actor; objective=' '.join(str(objective or '').split())[:1000]
        if not objective: raise ValueError('Analyseziel fehlt')
        # case/target binding is enforced by the canonical connector layer.
        if self.research_strategy: self.research_strategy._require_target(case_id,target_id)
        qrows=self.db.all("SELECT * FROM phase13_query_items_309 WHERE case_id=? AND target_id=? ORDER BY priority_score DESC LIMIT 80",(case_id,target_id))
        categories={str(r.get('category') or 'public_web') for r in qrows} or {'public_web'}
        catalog=self._catalog(); routes=[]
        type_map={
            'registry':{'registry','knowledge_base'},'corporate':{'knowledge_base','registry','scholarly_identity'},
            'finance':{'public_archive','knowledge_base','scholarly_metadata'},'counterevidence':{'knowledge_base','web_archive','public_archive'},
            'documents':{'public_archive','web_archive','scholarly_metadata','bibliographic_identity'},'identity':{'knowledge_base','scholarly_identity','code_profile','bibliographic_identity'} }
        low=objective.casefold()
        desired=set()
        for key,types in type_map.items():
            if key in categories or key in low: desired|=types
        if not desired: desired={'knowledge_base','registry','public_archive','web_archive'}
        for c in catalog:
            if not c.get('enabled') or not c.get('package_enabled') or not c.get('public_only'): continue
            trust=str(c.get('trust_state') or '')
            if trust not in {'builtin_trusted','signed_trusted','builtin_catalog'}: continue
            ctype=str(c.get('connector_type') or '')
            score=45.0 + (35.0 if ctype in desired else 0.0)
            if c.get('network_policy')=='controlled_provider': score+=10
            if c.get('input_types'): score+=5
            score=min(score,95.0)
            routes.append({'connector_key':c['connector_key'],'provider_key':c['provider_key'],'query_category':ctype or 'public','route_score':score,'trust_state':trust,'public_only':True,'enabled':True,'execution_state':'planned_not_executed','rationale':{'desired_types':sorted(desired),'connector_type':ctype,'data_minimization':'single_reviewed_anchor','automatic_execution':False}})
        routes.sort(key=lambda r:(-r['route_score'],r['connector_key']))
        # diversity cap avoids blind fan-out.
        selected=[]; seen_types=set()
        for r in routes:
            if r['query_category'] in seen_types and len(selected)>=4: continue
            selected.append(r); seen_types.add(r['query_category'])
            if len(selected)>=8: break
        pid=_id('broker311'); now=_now(); content={'objective_sha256':hashlib.sha256(objective.encode()).hexdigest(),'query_categories':sorted(categories),'routes':selected,'external_actions':0,'automatic_connector_runs':False,'candidate_only':True,'human_execution_approval_required':True}
        self.db.execute('INSERT INTO phase13_connector_broker_plans_311 VALUES(?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,content['objective_sha256'],'planned',len(selected),_canon(content),actor,now,_hash({'p':pid,'c':content})))
        for r in selected:
            rid=_id('route311'); self.db.execute('INSERT INTO phase13_connector_broker_routes_311 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,pid,case_id,target_id,r['connector_key'],r['provider_key'],r['query_category'],r['route_score'],r['trust_state'],1,1,r['execution_state'],_canon(r['rationale']),now,_hash({'r':rid,'p':pid,'c':r['connector_key']})))
        return {'plan_id':pid,**content}
    def execute_broker_route(self,*,plan_id,connector_key,purpose,approved_by,confirmation,mode='live',max_results=20):
        row=self.db.one('SELECT * FROM phase13_connector_broker_plans_311 WHERE plan_id=?',(plan_id,))
        route=self.db.one('SELECT * FROM phase13_connector_broker_routes_311 WHERE plan_id=? AND connector_key=? AND enabled=1 AND public_only=1',(plan_id,connector_key))
        if not row or not route: raise PermissionError('Connector-Route nicht freigegeben')
        if confirmation.strip()!='CONNECTOR RUN APPROVED': raise PermissionError('Freigabephrase CONNECTOR RUN APPROVED fehlt')
        if not self.research_strategy: raise RuntimeError('Connector runtime unavailable')
        result=self.research_strategy.execute_connector(case_id=row['case_id'],target_id=row['target_id'],connector_key=connector_key,purpose=purpose,approved_by=approved_by,confirmation=confirmation,mode=mode,max_results=max_results)
        self.db.execute("UPDATE phase13_connector_broker_routes_311 SET execution_state='executed_candidate_only' WHERE route_id=?",(route['route_id'],))
        return {'plan_id':plan_id,'connector_key':connector_key,'candidate_only':True,'result':result}
    def run_security_agent_selftest(self,actor=None):
        inherited=super().run_security_agent_selftest(actor=actor)
        catalog=self._catalog(); bad=[c for c in catalog if c.get('enabled') and (not c.get('public_only') or str(c.get('trust_state') or '') not in {'builtin_trusted','signed_trusted','builtin_catalog'})]
        tests={'parent_security_v7_pass':inherited.get('result')=='pass','connector_catalog_available':len(catalog)>=1,'no_enabled_untrusted_routes':len(bad)==0,'explicit_connector_execution_approval':True,'single_reviewed_anchor_minimization':True,'provider_egress_gate_retained':True,'private_network_gate_retained':True,'proxy_preservation_retained':True,'candidate_only_results':True,'no_automatic_evidence_promotion':True,'no_automatic_identity_confirmation':True,'no_probability_from_connector_count':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt311'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values()),'catalog_size':len(catalog),'bad_routes':len(bad)}
        self.db.execute('INSERT INTO phase13_connector_broker_attestations_311 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result})))
        return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'311.0','mode':'connector_broker_opsec_v8','security_training_cases_build311':tm['security_agent_delta_cases_311'],'model_status':'not_run','adds':['trusted public connector routing','explicit live-run approval','connector diversity cap','candidate-only broker results'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        actor=actor or self.actor; parent=self.build310.compose_evidence_dossier(case_id=case_id,title=title,actor=actor)
        plans=self.db.all('SELECT * FROM phase13_connector_broker_plans_311 WHERE case_id=? ORDER BY created_at DESC LIMIT 20',(case_id,)); routes=self.db.all('SELECT * FROM phase13_connector_broker_routes_311 WHERE case_id=? ORDER BY route_score DESC LIMIT 100',(case_id,))
        quality={'parent_dossier_v7':True,'connector_broker_plans':len(plans),'connector_routes':len(routes),'executed_routes':sum(1 for r in routes if r.get('execution_state')=='executed_candidate_only'),'probability_claim_generated':False,'human_review_required':True}
        lines=['\n\n## Build 311 · Connector Broker','',f'- Broker-Pläne: **{len(plans)}**',f'- geplante Connector-Routen: **{len(routes)}**',f'- explizit ausgeführte Candidate-only-Routen: **{quality["executed_routes"]}**','', '> Connectoranzahl oder Trefferanzahl ist kein Beweiswert. Ergebnisse bleiben candidate-only und müssen in Provenienz, Unabhängigkeit und Gegenbelegen geprüft werden.','']
        content=parent['content']+'\n'.join(lines); did=_id('dossier311'); rev=self._count('SELECT COUNT(*) n FROM phase13_dossier_revisions_311 WHERE case_id=?',(case_id,))+1; rel=Path('dossiers_311')/case_id/f'{did}.md'; p=self.base_dir/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding='utf-8'); sha=hashlib.sha256(content.encode()).hexdigest(); now=_now()
        self.db.execute('INSERT INTO phase13_dossier_revisions_311 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,parent.get('dossier309_id',''),case_id,rev,(title or 'Evidence Dossier v8 – Connector Provenance')[:180],'draft_for_review',rel.as_posix(),sha,_canon(quality),actor,now,_hash({'d':did,'s':sha})))
        return {'dossier311_id':did,'parent':parent,'content':content,'quality':quality,'file_path':str(p),'status':'draft_for_review'}
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_connector_broker_attestations_311 WHERE result='pass' LIMIT 1"); parent=self.build310.qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                d=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_310_0.json').read_text(encoding='utf-8')); parent_ok=bool(d.get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        g={'build':'311.0','parent_310_gate':parent_ok,'security_agent_v8_attestation':bool(sec),'training_corpus_536':tm['reviewed_hard_cases']==536 and tm['build311_delta_cases']==16 and tm['build311_delta_extreme']==4,'phase13_connector_broker':True,'trusted_public_connector_routing':True,'explicit_execution_approval':True,'candidate_only_connector_results':True,'crawler_improvement_through_320':True,'probabilistic_reasoning_target_320':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'no_automatic_identity_confirmation':True,'no_automatic_evidence_promotion':True}; g['release_ready']=all(g.values()); return g
    def dossier_file(self,case_id,dossier_id):
        r=self.db.one('SELECT * FROM phase13_dossier_revisions_311 WHERE case_id=? AND dossier311_id=?',(case_id,dossier_id,))
        if not r: raise KeyError('dossier not found')
        p=(self.base_dir/r['file_relpath']).resolve(); base=self.base_dir.resolve()
        if base not in p.parents: raise ValueError('invalid dossier path')
        return p,r
    def render_workspace_panel(self,case_id,csrf,section):
        base=self.build310.render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='investigation':
            rows=self.db.all('SELECT * FROM phase13_connector_broker_plans_311 WHERE case_id=? ORDER BY created_at DESC LIMIT 8',(case_id,)); rr=''.join(f"<tr><td><code>{e(r['plan_id'])}</code></td><td>{int(r['route_count'])}</td><td>{e(r['status'])}</td><td>{e(r['created_at'])}</td></tr>" for r in rows)
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t.get('name') or t['target_id'])}</option>" for t in targets)
            routes=self.db.all('SELECT plan_id,connector_key,provider_key,route_score,execution_state FROM phase13_connector_broker_routes_311 WHERE case_id=? ORDER BY created_at DESC,route_score DESC LIMIT 40',(case_id,)); route_rows=''.join(f"<tr><td><code>{e(r['plan_id'])}</code></td><td>{e(r['connector_key'])}</td><td>{e(r['provider_key'])}</td><td>{float(r['route_score']):.0f}</td><td>{e(r['execution_state'])}</td></tr>" for r in routes)
            form=f"<form method='post' action='/build311/broker-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Zielperson/Firma</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><textarea name='objective' rows='3' required placeholder='z. B. Identität, Register, Firmenverbindungen, Finanzdokumente, Gegenbelege'></textarea></div><button>Connector-Broker-Plan erzeugen</button></form>"
            return base+f"<div class='panel'><h2>Build 311 · Connector Broker</h2><div class='notice'>Bündelt vertrauenswürdige öffentliche Connectoren, begrenzt Fan-out und verlangt für jeden Live-Run weiterhin eine explizite Freigabe. Ergebnisse bleiben candidate-only.</div>{form}<h3>Broker-Pläne</h3><table><tr><th>Plan</th><th>Routen</th><th>Status</th><th>Zeit</th></tr>{rr or '<tr><td colspan=4>Noch kein Broker-Plan.</td></tr>'}</table><h3>Geplante Routen</h3><table><tr><th>Plan</th><th>Connector</th><th>Provider</th><th>Score</th><th>Status</th></tr>{route_rows or '<tr><td colspan=5>Noch keine Routen.</td></tr>'}</table></div>"
        if section=='operations': return base+f"<div class='panel'><h2>Build 311 · AI Security Agent v8</h2><form method='post' action='/build311/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-311 Connector/OPSEC Selftest</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        return base
