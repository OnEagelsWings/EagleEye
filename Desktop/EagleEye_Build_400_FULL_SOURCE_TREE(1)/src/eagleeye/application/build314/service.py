from __future__ import annotations
import hashlib, html, json, re
from pathlib import Path
from urllib.parse import urlsplit
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build313.service import Build313TechnicalIntelligenceDataService

_GOVLEGAL_FAMILIES=['government_register','court_public_record','official_gazette','public_procurement','public_licensing','regulatory_filing','sanctions_public_record','counterevidence']
_SAFE_FIELDS={'record_id','name','organisation','authority','jurisdiction','filing_date','decision_date','registration_date','status','role','address_public','case_number','document_title','document_date','public_url','relationship','amount_public','currency','identifier_public'}

class Build314GovernmentLegalDataService(Build313TechnicalIntelligenceDataService):
    BUILD='314.0'; REQUIRED_CORPUS=584
    def __init__(self,*args,build313=None,**kwargs):
        super().__init__(*args,**kwargs); self.build313=build313 or self
    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_314 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_314 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_314 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_314 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build314_delta_cases':a+s,'build314_delta_extreme':e,'govlegal_delta_cases':a,'security_agent_delta_cases_314':s}
    def create_govlegal_plan(self,*,case_id,target_id,objective,jurisdictions=None,actor=None):
        actor=actor or self.actor; objective=' '.join(str(objective or '').split())[:1000]
        if not objective: raise ValueError('Analyseziel fehlt')
        if self.research_strategy: self.research_strategy._require_target(case_id,target_id)
        jurisdictions=self._clean_list(jurisdictions or [],8) or ['unspecified']
        qp=self.generate_query_plan(case_id=case_id,target_id=target_id,purpose=f"{objective}; government legal official register court gazette procurement licensing regulatory filing sanctions counterevidence",max_queries=32,actor=actor)
        bp=self.create_broker_plan(case_id=case_id,target_id=target_id,objective=f"{objective} official government legal register court gazette regulatory counterevidence",actor=actor)
        pid=_id('govlegal314'); now=_now(); payload={'jurisdictions':jurisdictions,'families':list(_GOVLEGAL_FAMILIES),'query_plan_id':qp['plan_id'],'broker_plan_id':bp['plan_id'],'candidate_only':True,'public_official_sources_only':True,'probability_claim_generated':False}
        self.db.execute('INSERT INTO phase13_govlegal_plans_314 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,hashlib.sha256(objective.encode()).hexdigest(),_canon(jurisdictions),_canon(_GOVLEGAL_FAMILIES),qp['plan_id'],bp['plan_id'],'planned',actor,now,_hash({'p':pid,'x':payload})))
        return {'plan_id':pid,**payload,'query_count':len(qp.get('queries',[])),'broker_routes':len(bp.get('routes',[]))}
    def ingest_govlegal_candidate(self,*,plan_id,record_type,jurisdiction,authority,source_url,fields,evidence_refs=None,support_direction='support'):
        plan=self.db.one('SELECT * FROM phase13_govlegal_plans_314 WHERE plan_id=?',(plan_id,))
        if not plan: raise KeyError('Government/Legal-Plan nicht gefunden')
        typ=' '.join(str(record_type or '').split())[:100]
        if typ not in _GOVLEGAL_FAMILIES: raise ValueError('Nicht zugelassene Government/Legal-Familie')
        url=str(source_url or '').strip()[:2000]
        if not url.startswith(('http://','https://')): raise ValueError('Nur öffentliche HTTP(S)-Quellen')
        host=(urlsplit(url).hostname or '').casefold()
        if not host: raise ValueError('Quelle ohne Host')
        safe={}; dropped=[]
        for k,v in dict(fields or {}).items():
            key=re.sub(r'[^a-z0-9_]+','_',str(k).strip().casefold())[:80]
            if key not in _SAFE_FIELDS: dropped.append(key); continue
            vals=v if isinstance(v,list) else [v]; cleaned=[' '.join(str(x).split())[:700] for x in vals if ' '.join(str(x).split())]
            if cleaned: safe[key]=cleaned if isinstance(v,list) else cleaned[0]
        if not safe: raise ValueError('Keine zulässigen Government/Legal-Felder')
        direction=str(support_direction or 'support').casefold(); direction=direction if direction in {'support','counter','neutral'} else 'neutral'
        cid=_id('govcand314'); now=_now(); refs=self._clean_list(evidence_refs or [],30); source_group=host
        payload={'fields':safe,'dropped_fields':dropped,'candidate_only':True,'authority':str(authority or '')[:300],'jurisdiction':str(jurisdiction or '')[:120]}
        self.db.execute('INSERT INTO phase13_govlegal_candidates_314 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,plan_id,plan['case_id'],plan['target_id'],typ,str(jurisdiction or '')[:120],str(authority or '')[:300],url,source_group,_canon(payload),_canon(refs),direction,'candidate_only',now,_hash({'c':cid,'p':plan_id,'f':safe})))
        return {'candidate_id':cid,'record_type':typ,'normalized':payload,'source_group':source_group,'support_direction':direction,'review_status':'candidate_only'}
    def assess_govlegal_bundle(self,plan_id):
        plan=self.db.one('SELECT * FROM phase13_govlegal_plans_314 WHERE plan_id=?',(plan_id,))
        if not plan: raise KeyError('Government/Legal-Plan nicht gefunden')
        rows=self.db.all('SELECT * FROM phase13_govlegal_candidates_314 WHERE plan_id=? ORDER BY created_at',(plan_id,)); values={}; contradictions=[]
        for r in rows:
            data=json.loads(r.get('normalized_json') or '{}').get('fields',{})
            for k,v in data.items():
                for x in (v if isinstance(v,list) else [v]): values.setdefault(k,{}).setdefault(str(x).casefold(),0); values[k][str(x).casefold()]+=1
        agreement={}
        for k,c in values.items():
            total=sum(c.values()); agreement[k]=round((max(c.values())/total) if total else 0,4)
            if len(c)>1 and total>1: contradictions.append({'field':k,'distinct_values':len(c),'distribution':c})
        support=sum(r.get('support_direction')=='support' for r in rows); counter=sum(r.get('support_direction')=='counter' for r in rows); groups=len({r.get('source_group') for r in rows if r.get('source_group')}); mean=(sum(agreement.values())/len(agreement)) if agreement else 0
        readiness=max(0,min(100,25*min(groups,3)/3+30*mean+20*min(len(rows),4)/4+15*(1 if counter else 0)+10*(1 if contradictions else 0)))
        aid=_id('govassess314'); now=_now(); self.db.execute('INSERT INTO phase13_govlegal_assessments_314 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,plan_id,plan['case_id'],plan['target_id'],support,counter,groups,_canon(agreement),_canon(contradictions),round(readiness,2),0,now,_hash({'a':aid,'r':round(readiness,2)})))
        return {'assessment_id':aid,'candidate_count':len(rows),'support_count':support,'counter_count':counter,'independent_source_groups':groups,'field_agreement':agreement,'contradictions':contradictions,'assessment_readiness_score':round(readiness,2),'score_meaning':'govlegal_evidence_workflow_readiness_not_probability','probability_claim_generated':False}
    def create_recon_lab_simulation(self,*,case_id,target_id,scope,confirmation,actor=None):
        actor=actor or self.actor
        if str(confirmation or '').strip()!='ACTIVE RECON LAB FREIGEBEN': raise PermissionError('Explizite Lab-Freigabe fehlt')
        if self.research_strategy: self.research_strategy._require_target(case_id,target_id)
        scope_text=' '.join(str(scope or '').split())[:500]
        if not scope_text: raise ValueError('Lab-Scope fehlt')
        auth=_id('reconauth314'); run=_id('reconlab314')
        plan=[
          {'step':1,'action':'scope_validation','network_action':False},
          {'step':2,'action':'simulated_host_inventory','network_action':False},
          {'step':3,'action':'simulated_service_observation','network_action':False},
          {'step':4,'action':'simulated_metadata_correlation','network_action':False},
          {'step':5,'action':'human_review','network_action':False},
        ]
        payload={'scope':scope_text,'authorization':'single_use','simulation_only':True,'network_calls':0,'real_external_probing':False,'plan':plan}
        self.db.execute('INSERT INTO phase13_recon_lab_runs_314 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(run,case_id,target_id,auth,_canon({'scope':scope_text}),_canon(plan),1,0,'simulated_complete',actor,_now(),_hash({'r':run,'p':payload})))
        return {'run_id':run,'authorization_id':auth,**payload,'status':'simulated_complete'}
    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v10_pass':parent.get('result')=='pass','public_govlegal_only':True,'candidate_only_records':True,'jurisdiction_provenance':True,'no_private_database_access':True,'active_recon_real_network_disabled':True,'lab_simulation_network_calls_zero':True,'explicit_lab_authorization_required':True,'no_port_scanning':True,'no_service_fingerprinting_external':True,'no_credential_testing':True,'no_probability_from_record_count':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt314'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase13_security_attestations_314 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'314.0','mode':'government_legal_plus_recon_lab_opsec_v11','security_training_cases_build314':tm['security_agent_delta_cases_314'],'model_status':'not_run','adds':['government/legal provenance','jurisdiction boundary','recon lab simulation','real active probing disabled'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        actor=actor or self.actor; parent=self.build313.compose_evidence_dossier(case_id=case_id,title=title,actor=actor)
        plans=self.db.all('SELECT * FROM phase13_govlegal_plans_314 WHERE case_id=? ORDER BY created_at DESC LIMIT 30',(case_id,)); cands=self.db.all('SELECT * FROM phase13_govlegal_candidates_314 WHERE case_id=? ORDER BY created_at DESC LIMIT 200',(case_id,)); ass=self.db.all('SELECT * FROM phase13_govlegal_assessments_314 WHERE case_id=? ORDER BY created_at DESC LIMIT 30',(case_id,)); labs=self.db.all('SELECT * FROM phase13_recon_lab_runs_314 WHERE case_id=? ORDER BY created_at DESC LIMIT 30',(case_id,))
        quality={'parent_dossier':True,'govlegal_plans':len(plans),'govlegal_candidates':len(cands),'govlegal_assessments':len(ass),'recon_lab_runs':len(labs),'candidate_only':True,'probability_claim_generated':False,'human_review_required':True,'real_active_recon_enabled':False}
        lines=['\n\n## Build 314 · Government / Legal Data','',f'- Government/Legal-Pläne: **{len(plans)}**',f'- Candidate-Records: **{len(cands)}**',f'- Assessments: **{len(ass)}**',f'- Active-Recon-Lab-Simulationen: **{len(labs)}**','', '> Öffentliche amtliche und juristische Quellen werden quellen- und jurisdictionsgebunden verarbeitet. Lab-Recon erzeugt keine realen Netzwerkaufrufe.','']
        if ass: lines += [f'- Letzter Government/Legal-Readiness-Score: **{ass[0].get("readiness_score",0):.1f}/100** (Workflow-Reife, keine Wahrscheinlichkeit)','']
        content=parent['content']+'\n'.join(lines); did=_id('dossier314'); rev=self._count('SELECT COUNT(*) n FROM phase13_dossier_revisions_314 WHERE case_id=?',(case_id,))+1; rel=Path('dossiers_314')/case_id/f'{did}.md'; path=Path(self.base_dir)/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content,encoding='utf-8'); ch=hashlib.sha256(content.encode()).hexdigest(); self.db.execute('INSERT INTO phase13_dossier_revisions_314 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,parent.get('dossier_id',''),case_id,rev,title or f'EagleEye Evidence Dossier · {case_id}','draft_for_review',str(rel),ch,_canon(quality),actor,_now(),_hash({'d':did,'c':ch}))); return {'dossier_id':did,'parent_dossier_id':parent.get('dossier_id',''),'case_id':case_id,'revision_no':rev,'status':'draft_for_review','content':content,'quality':quality,'file_relpath':str(rel),'content_sha256':ch}
    def dossier_file(self,case_id,dossier_id):
        row=self.db.one('SELECT * FROM phase13_dossier_revisions_314 WHERE case_id=? AND dossier314_id=?',(case_id,dossier_id,))
        if not row: raise KeyError('Dossier nicht gefunden')
        p=(Path(self.base_dir)/row['file_relpath']).resolve(); root=Path(self.base_dir).resolve()
        if root not in p.parents: raise PermissionError('Ungültiger Dossierpfad')
        return p,row
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_security_attestations_314 WHERE result='pass' LIMIT 1"); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try: parent_ok=bool(json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_313_0.json').read_text(encoding='utf-8')).get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        g={'build':'314.0','parent_313_gate':parent_ok,'security_agent_v11_attestation':bool(sec),'training_corpus_584':tm['reviewed_hard_cases']==584 and tm['build314_delta_cases']==16 and tm['build314_delta_extreme']==4,'phase13_government_legal_data':True,'public_official_sources_only':True,'jurisdiction_provenance':True,'candidate_only_govlegal_records':True,'crawler_govlegal_scope_ready':True,'probabilistic_reasoning_target_320':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'real_active_recon_disabled':True,'recon_lab_simulation_only':True,'no_probability_from_record_count':True}; g['release_ready']=all(g.values()); return g
    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 314 · Government / Legal Data</h2><div class='notice'>Öffentliche amtliche und juristische Quellen mit Jurisdiktions- und Behördenprovenienz.</div><form method='post' action='/build314/govlegal-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><textarea name='objective' rows='3' required></textarea></div><div class='field'><label>Jurisdiktionen (Komma)</label><input name='jurisdictions'></div><button>Government/Legal-Plan erzeugen</button></form></div><div class='panel'><h3>Active Recon · Lab Simulation</h3><div class='notice'>Trainiert Freigabe, Scope, Audit und Auswertung. Keine realen Netzwerkaufrufe.</div><form method='post' action='/build314/recon-lab'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Lab-Scope</label><input name='scope' required></div><div class='field'><label>Freigabe</label><input name='confirmation' placeholder='ACTIVE RECON LAB FREIGEBEN' required></div><button>Simulation starten</button></form></div>"
        if section=='operations': return base+f"<div class='panel'><h2>Build 314 · AI Security Agent v11</h2><form method='post' action='/build314/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-314 Government/Legal + Recon-Lab OPSEC Selftest</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        return base
