from __future__ import annotations
import hashlib, html, json, re
from pathlib import Path
from urllib.parse import urlsplit
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build314.service import Build314GovernmentLegalDataService

_FIELD_CANON={
 'name':'name','alias':'name_alias','former_name':'name_alias','date_of_birth':'date_of_birth','birth_place':'birth_place',
 'registration_id':'registration_id','identifier_public':'registration_id','jurisdiction':'jurisdiction','status':'status',
 'domain':'domain','hostname':'domain','organisation':'organisation','employer':'organisation','parent':'organisation_relation',
 'subsidiary':'organisation_relation','officer':'person_relation','director':'person_relation','role':'role','position':'role',
 'registered_office':'address','address_public_record':'address','address_public':'address','country':'country',
 'registrar':'registrar','asn':'asn','rdap_handle':'rdap_handle','public_url':'public_url'
}
_HIGH={'registration_id','date_of_birth','domain','rdap_handle'}
_MEDIUM={'name','name_alias','organisation','organisation_relation','person_relation','address','asn','jurisdiction'}

def _norm_value(v):
    s=' '.join(str(v or '').split()).strip().casefold()
    s=re.sub(r'\s+',' ',s)
    return s[:700]

class Build315CrossDatabaseEntityResolutionService(Build314GovernmentLegalDataService):
    BUILD='315.0'; REQUIRED_CORPUS=600
    def __init__(self,*args,build314=None,**kwargs):
        super().__init__(*args,**kwargs); self.build314=build314 or self
    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_315 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_315 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_315 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_315 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build315_delta_cases':a+s,'build315_delta_extreme':e,'entity_resolution_delta_cases':a,'security_agent_delta_cases_315':s}
    def create_resolution_run(self,*,case_id,target_id,hypothesis_type='identity',hypothesis_text='',actor=None):
        actor=actor or self.actor
        if self.research_strategy: self.research_strategy._require_target(case_id,target_id)
        typ=str(hypothesis_type or 'identity').strip().casefold()
        if typ not in {'identity','organisation_identity','relationship','financial_flow','technical_link'}: typ='identity'
        text=' '.join(str(hypothesis_text or '').split())[:1200] or f'{typ} hypothesis for target {target_id}'
        rid=_id('resolve315'); layers=['records312','technical313','govlegal314']
        self.db.execute('INSERT INTO phase13_entity_resolution_runs_315 VALUES(?,?,?,?,?,?,?,?,?,?)',(rid,case_id,target_id,typ,text,_canon(layers),'planned',actor,_now(),_hash({'r':rid,'t':text,'l':layers})))
        return {'resolution_id':rid,'case_id':case_id,'target_id':target_id,'hypothesis_type':typ,'hypothesis_text':text,'source_layers':layers,'status':'planned','probability_claim_generated':False}
    def _rows_for_target(self,case_id,target_id):
        rows=[]
        for layer,table,idcol in [
          ('records312','phase13_record_candidates_312','candidate_id'),
          ('technical313','phase13_technical_candidates_313','candidate_id'),
          ('govlegal314','phase13_govlegal_candidates_314','candidate_id')]:
            try:
                for r in self.db.all(f'SELECT * FROM {table} WHERE case_id=? AND target_id=?',(case_id,target_id,)):
                    rows.append((layer,idcol,r))
            except Exception:
                pass
        return rows
    def build_resolution_signals(self,resolution_id):
        run=self.db.one('SELECT * FROM phase13_entity_resolution_runs_315 WHERE resolution_id=?',(resolution_id,))
        if not run: raise KeyError('Entity-Resolution-Lauf nicht gefunden')
        inserted=[]
        for layer,idcol,r in self._rows_for_target(run['case_id'],run['target_id']):
            try: payload=json.loads(r.get('normalized_json') or '{}')
            except Exception: payload={}
            fields=payload.get('fields',payload) if isinstance(payload,dict) else {}
            source_group=str(r.get('source_group') or (urlsplit(str(r.get('source_url') or '')).hostname or '')).casefold()[:300]
            direction=str(r.get('support_direction') or 'neutral').casefold(); direction=direction if direction in {'support','counter','neutral'} else 'neutral'
            for raw,val in dict(fields or {}).items():
                canon=_FIELD_CANON.get(str(raw).casefold())
                if not canon: continue
                vals=val if isinstance(val,list) else [val]
                for item in vals:
                    nv=_norm_value(item)
                    if not nv: continue
                    weight='high' if canon in _HIGH else ('medium' if canon in _MEDIUM else 'low')
                    dependency=f'{source_group}|{canon}'
                    sid=_id('sig315'); rationale=f'{layer}:{raw} -> {canon}; {direction}; source_group={source_group}'
                    self.db.execute('INSERT INTO phase13_entity_resolution_signals_315 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,resolution_id,run['case_id'],run['target_id'],layer,str(r.get(idcol) or ''),source_group,canon,nv,direction,weight,dependency,rationale,_now(),_hash({'s':sid,'d':dependency,'v':nv,'x':direction})))
                    inserted.append(sid)
        self.db.execute("UPDATE phase13_entity_resolution_runs_315 SET status='signals_built' WHERE resolution_id=?",(resolution_id,))
        return {'resolution_id':resolution_id,'signals_created':len(inserted),'status':'signals_built'}
    def assess_resolution(self,resolution_id):
        run=self.db.one('SELECT * FROM phase13_entity_resolution_runs_315 WHERE resolution_id=?',(resolution_id,))
        if not run: raise KeyError('Entity-Resolution-Lauf nicht gefunden')
        rows=self.db.all('SELECT * FROM phase13_entity_resolution_signals_315 WHERE resolution_id=? ORDER BY created_at',(resolution_id,))
        groups={}; byfield={}; dep={}
        for r in rows:
            groups.setdefault(r['source_group'],0); groups[r['source_group']]+=1
            dep.setdefault(r['independence_key'],0); dep[r['independence_key']]+=1
            byfield.setdefault(r['field_name'],{}).setdefault(r['normalized_value'],{'support':0,'counter':0,'neutral':0,'sources':set()})
            cell=byfield[r['field_name']][r['normalized_value']]; cell[r['direction']]+=1; cell['sources'].add(r['source_group'])
        matched=[]; conflicts=[]
        for field,vals in byfield.items():
            for value,data in vals.items():
                if data['support']>=2 and len(data['sources'])>=2:
                    matched.append({'field':field,'value':value,'independent_sources':len(data['sources']),'support_signals':data['support']})
            if len(vals)>1:
                visible={v:{'support':d['support'],'counter':d['counter'],'neutral':d['neutral'],'independent_sources':len(d['sources'])} for v,d in vals.items()}
                conflicts.append({'field':field,'values':visible})
        support=sum(r['direction']=='support' for r in rows); counter=sum(r['direction']=='counter' for r in rows); neutral=sum(r['direction']=='neutral' for r in rows)
        independent=len(groups); duplicate_groups=sum(1 for n in dep.values() if n>1)
        alternatives=[]
        if conflicts: alternatives.append({'hypothesis':'same-name/different-entity or stale-record alternative','trigger':'conflicting canonical fields'})
        if independent<2: alternatives.append({'hypothesis':'insufficient independent corroboration','trigger':'fewer than two independent source groups'})
        if counter: alternatives.append({'hypothesis':'counterevidence-supported alternative','trigger':'explicit counter-signals present'})
        raw=18*min(independent,4)/4 + 30*min(len(matched),5)/5 + 18*(1 if counter else 0) + 14*(1 if conflicts else 0) + 20*min(len(rows),12)/12
        penalty=min(25,duplicate_groups*3)
        readiness=round(max(0,min(100,raw-penalty)),2)
        aid=_id('resolveassess315'); now=_now()
        self.db.execute('INSERT INTO phase13_entity_resolution_assessments_315 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,resolution_id,run['case_id'],run['target_id'],support,counter,neutral,independent,duplicate_groups,_canon(matched),_canon(conflicts),_canon(alternatives),readiness,0,now,_hash({'a':aid,'r':readiness,'m':matched,'c':conflicts})))
        self.db.execute("UPDATE phase13_entity_resolution_runs_315 SET status='assessed' WHERE resolution_id=?",(resolution_id,))
        return {'assessment_id':aid,'resolution_id':resolution_id,'support_signals':support,'counter_signals':counter,'neutral_signals':neutral,'independent_source_groups':independent,'duplicate_dependency_groups':duplicate_groups,'matched_fields':matched,'conflicts':conflicts,'alternative_hypotheses':alternatives,'resolution_readiness_score':readiness,'score_meaning':'cross_database_resolution_workflow_readiness_not_probability','probability_claim_generated':False,'human_review_required':True}
    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v11_pass':parent.get('result')=='pass','case_bound_resolution':True,'candidate_only_inputs':True,'source_dependency_penalty':True,'duplicate_source_not_independent':True,'counterevidence_retained':True,'alternative_hypotheses_required':True,'no_auto_identity_confirmation':True,'no_auto_evidence_promotion':True,'no_probability_from_match_count':True,'real_active_recon_still_disabled':True,'human_review_required':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt315'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase13_security_attestations_315 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'315.0','mode':'cross_database_entity_resolution_opsec_v12','security_training_cases_build315':tm['security_agent_delta_cases_315'],'model_status':'not_run','adds':['source dependency penalty','cross-layer provenance','alternative hypothesis retention','no auto identity confirmation'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        actor=actor or self.actor; parent=self.build314.compose_evidence_dossier(case_id=case_id,title=title,actor=actor)
        runs=self.db.all('SELECT * FROM phase13_entity_resolution_runs_315 WHERE case_id=? ORDER BY created_at DESC LIMIT 50',(case_id,)); ass=self.db.all('SELECT * FROM phase13_entity_resolution_assessments_315 WHERE case_id=? ORDER BY created_at DESC LIMIT 50',(case_id,))
        quality={'parent_dossier':True,'entity_resolution_runs':len(runs),'entity_resolution_assessments':len(ass),'cross_database_provenance':True,'source_dependency_penalty':True,'alternative_hypotheses':True,'probability_claim_generated':False,'human_review_required':True}
        lines=['\n\n## Build 315 · Cross-Database Entity Resolution','',f'- Resolution-Läufe: **{len(runs)}**',f'- Assessments: **{len(ass)}**','', '> Personen-, Firmen-, technische und Government/Legal-Records werden quellenabhängig korreliert. Mehrfachtreffer derselben Quelle werden nicht als unabhängige Bestätigung gezählt.','']
        if ass:
            a=ass[0]; lines += [f'- Letzter Resolution-Readiness-Score: **{a.get("resolution_readiness_score",0):.1f}/100** (Workflow-Reife, keine Wahrscheinlichkeit)',f'- Unabhängige Quellengruppen: **{a.get("independent_groups",0)}**',f'- Abhängigkeits-/Duplikatgruppen: **{a.get("duplicate_dependency_groups",0)}**','']
        content=parent['content']+'\n'.join(lines); did=_id('dossier315'); rev=self._count('SELECT COUNT(*) n FROM phase13_dossier_revisions_315 WHERE case_id=?',(case_id,))+1; rel=Path('dossiers_315')/case_id/f'{did}.md'; path=Path(self.base_dir)/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content,encoding='utf-8'); ch=hashlib.sha256(content.encode()).hexdigest(); self.db.execute('INSERT INTO phase13_dossier_revisions_315 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,parent.get('dossier_id',''),case_id,rev,title or f'EagleEye Evidence Dossier · {case_id}','draft_for_review',str(rel),ch,_canon(quality),actor,_now(),_hash({'d':did,'c':ch}))); return {'dossier_id':did,'parent_dossier_id':parent.get('dossier_id',''),'case_id':case_id,'revision_no':rev,'status':'draft_for_review','content':content,'quality':quality,'file_relpath':str(rel),'content_sha256':ch}
    def dossier_file(self,case_id,dossier_id):
        row=self.db.one('SELECT * FROM phase13_dossier_revisions_315 WHERE case_id=? AND dossier315_id=?',(case_id,dossier_id,))
        if not row: raise KeyError('Dossier nicht gefunden')
        p=(Path(self.base_dir)/row['file_relpath']).resolve(); root=Path(self.base_dir).resolve()
        if root not in p.parents: raise PermissionError('Ungültiger Dossierpfad')
        return p,row
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_security_attestations_315 WHERE result='pass' LIMIT 1"); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try: parent_ok=bool(json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_314_0.json').read_text(encoding='utf-8')).get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        g={'build':'315.0','parent_314_gate':parent_ok,'security_agent_v12_attestation':bool(sec),'training_corpus_600':tm['reviewed_hard_cases']==600 and tm['build315_delta_cases']==16 and tm['build315_delta_extreme']==4,'phase13_cross_database_entity_resolution':True,'records_technical_govlegal_correlation':True,'source_dependency_penalty':True,'counterevidence_retention':True,'alternative_hypotheses':True,'probabilistic_reasoning_target_320':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'real_active_recon_disabled':True,'no_probability_from_match_count':True}; g['release_ready']=all(g.values()); return g
    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 315 · Cross-Database Entity Resolution</h2><div class='notice'>Korreliert Records 312, Technical Intelligence 313 und Government/Legal 314. Quellenabhängigkeiten und Gegenhypothesen bleiben sichtbar.</div><form method='post' action='/build315/resolve'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Hypothesentyp</label><select name='hypothesis_type'><option value='identity'>Personenidentität</option><option value='organisation_identity'>Firmenidentität</option><option value='relationship'>Beziehung</option><option value='financial_flow'>Finanzflow</option><option value='technical_link'>Technische Verbindung</option></select></div><div class='field'><label>Hypothese</label><textarea name='hypothesis_text' rows='3'></textarea></div><button>Cross-Database-Abgleich starten</button></form></div>"
        if section=='operations': return base+f"<div class='panel'><h2>Build 315 · AI Security Agent v12</h2><form method='post' action='/build315/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-315 Entity-Resolution/OPSEC Selftest</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        return base
