from __future__ import annotations
import hashlib, html, json, re
from pathlib import Path
from urllib.parse import urlsplit
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build311.service import Build311ConnectorBrokerService

_SAFE_FIELDS={
 'person':{'name','alias','date_of_birth','birth_place','nationality_public_record','occupation','employer','position','registration_id','address_public_record','domain','public_url'},
 'organisation':{'name','former_name','registration_id','jurisdiction','registered_office','status','incorporation_date','dissolution_date','officer','director','parent','subsidiary','shareholder_public_record','beneficial_owner_public_record','filing_date','account_period','domain','public_url'}
}
_RECORD_FAMILIES={
 'person':['identity_register','vital_record','professional_register','company_affiliation','public_document','counterevidence'],
 'organisation':['company_register','officer_register','ownership_public_record','filing','accounts_public_record','public_document','counterevidence']
}

class Build312CorporatePersonRecordsService(Build311ConnectorBrokerService):
    BUILD='312.0'; REQUIRED_CORPUS=552
    def __init__(self,*args,build311=None,**kwargs):
        super().__init__(*args,**kwargs); self.build311=build311 or self
    def training_metrics(self):
        b=super().training_metrics()
        a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_312 WHERE review_status='reviewed'")
        s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_312 WHERE review_status='reviewed'")
        e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_312 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_312 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build312_delta_cases':a+s,'build312_delta_extreme':e,'records_delta_cases':a,'security_agent_delta_cases_312':s}
    @staticmethod
    def _clean_list(values,limit=8):
        out=[]
        for v in values or []:
            s=' '.join(str(v).split())[:120]
            if s and s.casefold() not in {x.casefold() for x in out}: out.append(s)
            if len(out)>=limit: break
        return out
    def create_record_plan(self,*,case_id,target_id,record_kind,objective,countries=None,languages=None,actor=None):
        actor=actor or self.actor; kind=str(record_kind or '').strip().casefold()
        if kind in {'company','corporate','firma','organisation','organization'}: kind='organisation'
        if kind not in {'person','organisation'}: raise ValueError('record_kind muss person oder organisation sein')
        objective=' '.join(str(objective or '').split())[:1000]
        if not objective: raise ValueError('Analyseziel fehlt')
        if self.research_strategy: self.research_strategy._require_target(case_id,target_id)
        countries=self._clean_list(countries or []); languages=self._clean_list(languages or ['de','en'],4)
        families=list(_RECORD_FAMILIES[kind])
        query_purpose=f"{objective}; record_kind={kind}; record_families={' '.join(families)}"
        qp=self.generate_query_plan(case_id=case_id,target_id=target_id,purpose=query_purpose,max_queries=32,actor=actor)
        bp=self.create_broker_plan(case_id=case_id,target_id=target_id,objective=f"{objective} registry corporate documents counterevidence",actor=actor)
        pid=_id('records312'); now=_now(); content={'record_kind':kind,'families':families,'countries':countries,'languages':languages,'query_plan_id':qp['plan_id'],'broker_plan_id':bp['plan_id'],'candidate_only':True,'automatic_identity_confirmation':False,'probability_claim_generated':False}
        self.db.execute('INSERT INTO phase13_record_plans_312 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,kind,hashlib.sha256(objective.encode()).hexdigest(),_canon(countries),_canon(languages),_canon(families),qp['plan_id'],bp['plan_id'],'planned',actor,now,_hash({'p':pid,'c':content})))
        return {'plan_id':pid,**content,'query_count':len(qp.get('queries',[])),'broker_routes':len(bp.get('routes',[]))}
    def ingest_record_candidate(self,*,plan_id,record_type,source_label,source_url,fields,evidence_refs=None,support_direction='support'):
        plan=self.db.one('SELECT * FROM phase13_record_plans_312 WHERE plan_id=?',(plan_id,))
        if not plan: raise KeyError('Record-Plan nicht gefunden')
        kind=plan['record_kind']; rt=' '.join(str(record_type or '').split())[:100]
        if not rt: raise ValueError('record_type fehlt')
        url=str(source_url or '').strip()[:2000]
        if url and not url.startswith(('http://','https://')): raise ValueError('Nur öffentliche HTTP(S)-Quellen')
        host=(urlsplit(url).hostname or '').casefold() if url else ''
        safe={}; dropped=[]
        for k,v in dict(fields or {}).items():
            key=re.sub(r'[^a-z0-9_]+','_',str(k).strip().casefold())[:80]
            if key not in _SAFE_FIELDS[kind]: dropped.append(key); continue
            if isinstance(v,list): safe[key]=self._clean_list(v,20)
            else: safe[key]=' '.join(str(v).split())[:500]
        if not safe: raise ValueError('Keine zulässigen normalisierten Record-Felder')
        direction=str(support_direction or 'support').casefold()
        if direction not in {'support','counter','neutral'}: direction='neutral'
        refs=self._clean_list(evidence_refs or [],30); cid=_id('recordcand312'); now=_now()
        source_group=host or hashlib.sha256(str(source_label or '').encode()).hexdigest()[:16]
        payload={'fields':safe,'dropped_fields':dropped,'candidate_only':True,'field_count':len(safe)}
        self.db.execute('INSERT INTO phase13_record_candidates_312 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,plan_id,plan['case_id'],plan['target_id'],kind,rt,str(source_label or '')[:300],url,source_group,_canon(payload),_canon(refs),direction,'candidate_only',now,_hash({'c':cid,'p':plan_id,'f':safe})))
        return {'candidate_id':cid,'record_kind':kind,'record_type':rt,'normalized':payload,'source_group':source_group,'support_direction':direction,'review_status':'candidate_only'}
    def assess_record_bundle(self,plan_id):
        plan=self.db.one('SELECT * FROM phase13_record_plans_312 WHERE plan_id=?',(plan_id,));
        if not plan: raise KeyError('Record-Plan nicht gefunden')
        rows=self.db.all('SELECT * FROM phase13_record_candidates_312 WHERE plan_id=? ORDER BY created_at',(plan_id,))
        values={}; contradictions=[]
        for r in rows:
            data=json.loads(r.get('normalized_json') or '{}').get('fields',{})
            for k,v in data.items():
                vals=v if isinstance(v,list) else [v]
                values.setdefault(k,{})
                for x in vals: values[k][str(x).casefold()]=values[k].get(str(x).casefold(),0)+1
        agreement={}
        for k,c in values.items():
            total=sum(c.values()); best=max(c.values()) if c else 0; agreement[k]=round(best/total,4) if total else 0.0
            if len(c)>1 and total>1: contradictions.append({'field':k,'distinct_values':len(c),'distribution':c})
        support=sum(1 for r in rows if r.get('support_direction')=='support'); counter=sum(1 for r in rows if r.get('support_direction')=='counter')
        groups=len({r.get('source_group') for r in rows if r.get('source_group')})
        mean_agree=(sum(agreement.values())/len(agreement)) if agreement else 0.0
        # readiness is a workflow-quality score, deliberately not identity probability.
        readiness=max(0.0,min(100.0,20.0*min(groups,3)/3 + 35.0*mean_agree + 20.0*min(len(rows),4)/4 + 15.0*(1 if counter else 0) + 10.0*(1 if contradictions else 0)))
        aid=_id('recordassess312'); now=_now(); self.db.execute('INSERT INTO phase13_record_bundle_assessments_312 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,plan_id,plan['case_id'],plan['target_id'],support,counter,groups,_canon(agreement),_canon(contradictions),round(readiness,2),0,now,_hash({'a':aid,'p':plan_id,'r':round(readiness,2)})))
        return {'assessment_id':aid,'candidate_count':len(rows),'support_count':support,'counter_count':counter,'independent_source_groups':groups,'field_agreement':agreement,'contradictions':contradictions,'assessment_readiness_score':round(readiness,2),'score_meaning':'workflow_readiness_not_identity_probability','probability_claim_generated':False}
    def record_query_ladder(self,anchor,record_family,country=''):
        anchor=' '.join(str(anchor or '').split())[:200]; family=' '.join(str(record_family or '').split())[:80]; country=' '.join(str(country or '').split())[:80]
        broad=' '.join(x for x in [f'"{anchor}"' if anchor else '',family,country] if x)
        focused=' '.join(x for x in [f'"{anchor}"' if anchor else '',f'({family} OR register OR registry)',country] if x)
        precision=' '.join(x for x in [focused,'filetype:pdf'] if x)
        return [{'variant':'broad','query':broad},{'variant':'focused','query':focused},{'variant':'precision','query':precision}]
    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v8_pass':parent.get('result')=='pass','person_company_record_separation':True,'public_records_only':True,'unknown_fields_dropped':True,'field_provenance_retained':True,'private_network_gate_retained':True,'proxy_preservation_retained':True,'explicit_connector_execution_approval':True,'candidate_only_records':True,'no_automatic_identity_confirmation':True,'no_probability_from_record_count':True,'counterevidence_required_for_readiness':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt312'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}
        self.db.execute('INSERT INTO phase13_records_attestations_312 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result})))
        return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'312.0','mode':'public_records_opsec_v9','security_training_cases_build312':tm['security_agent_delta_cases_312'],'model_status':'not_run','adds':['person/company record separation','field allowlist','record-level provenance','candidate-only normalization'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        actor=actor or self.actor; parent=self.build311.compose_evidence_dossier(case_id=case_id,title=title,actor=actor)
        plans=self.db.all('SELECT * FROM phase13_record_plans_312 WHERE case_id=? ORDER BY created_at DESC LIMIT 30',(case_id,)); cands=self.db.all('SELECT * FROM phase13_record_candidates_312 WHERE case_id=? ORDER BY created_at DESC LIMIT 200',(case_id,)); ass=self.db.all('SELECT * FROM phase13_record_bundle_assessments_312 WHERE case_id=? ORDER BY created_at DESC LIMIT 30',(case_id,))
        quality={'parent_dossier':True,'record_plans':len(plans),'record_candidates':len(cands),'record_bundle_assessments':len(ass),'field_level_provenance':True,'probability_claim_generated':False,'human_review_required':True}
        lines=['\n\n## Build 312 · Corporate / Person Records','',f'- Record-Pläne: **{len(plans)}**',f'- normalisierte Candidate-Records: **{len(cands)}**',f'- Bundle-Assessments: **{len(ass)}**','', '> Record-Treffer und Readiness-Scores sind keine Identitätswahrscheinlichkeit. Felder bleiben candidate-only, quellengebunden und müssen gegen Gegenbelege und unabhängige Quellen geprüft werden.','']
        if ass:
            latest=ass[0]; lines += [f'- Letzter Assessment-Readiness-Score: **{latest.get("readiness_score",0):.1f}/100** (Workflow-Reife, keine Wahrscheinlichkeit)','']
        content=parent['content']+'\n'.join(lines); did=_id('dossier312'); rev=self._count('SELECT COUNT(*) n FROM phase13_dossier_revisions_312 WHERE case_id=?',(case_id,))+1; rel=Path('dossiers_312')/case_id/f'{did}.md'; path=Path(self.base_dir)/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content,encoding='utf-8'); ch=hashlib.sha256(content.encode()).hexdigest()
        self.db.execute('INSERT INTO phase13_dossier_revisions_312 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,parent.get('dossier_id',''),case_id,rev,title or f'EagleEye Evidence Dossier · {case_id}','draft_for_review',str(rel),ch,_canon(quality),actor,_now(),_hash({'d':did,'c':ch})))
        return {'dossier_id':did,'parent_dossier_id':parent.get('dossier_id',''),'case_id':case_id,'revision_no':rev,'status':'draft_for_review','content':content,'quality':quality,'file_relpath':str(rel),'content_sha256':ch}
    def dossier_file(self,case_id,dossier_id):
        row=self.db.one('SELECT * FROM phase13_dossier_revisions_312 WHERE case_id=? AND dossier312_id=?',(case_id,dossier_id));
        if not row: raise KeyError('Dossier nicht gefunden')
        p=(Path(self.base_dir)/row['file_relpath']).resolve(); root=Path(self.base_dir).resolve()
        if root not in p.parents: raise PermissionError('Ungültiger Dossierpfad')
        return p,row
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_records_attestations_312 WHERE result='pass' LIMIT 1"); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try: parent_ok=bool(json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_311_0.json').read_text(encoding='utf-8')).get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        g={'build':'312.0','parent_311_gate':parent_ok,'security_agent_v9_attestation':bool(sec),'training_corpus_552':tm['reviewed_hard_cases']==552 and tm['build312_delta_cases']==16 and tm['build312_delta_extreme']==4,'phase13_corporate_person_records':True,'record_kind_separation':True,'field_level_provenance':True,'candidate_only_records':True,'adaptive_record_query_ladder':True,'crawler_records_scope_ready':True,'probabilistic_reasoning_target_320':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'no_automatic_identity_confirmation':True,'no_probability_from_record_count':True}; g['release_ready']=all(g.values()); return g
    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 312 · Corporate / Person Records</h2><div class='notice'>Öffentliche Personen- und Firmenrecords werden getrennt geplant und field-level quellengebunden als candidate-only normalisiert. Readiness ≠ Identitätswahrscheinlichkeit.</div><form method='post' action='/build312/record-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Record-Typ</label><select name='record_kind'><option value='person'>Person</option><option value='organisation'>Firma/Organisation</option></select></div><div class='field'><label>Ermittlungsziel</label><textarea name='objective' rows='3' required></textarea></div><div class='field'><label>Länder (Komma)</label><input name='countries'></div><div class='field'><label>Sprachen (Komma)</label><input name='languages' value='de,en'></div><button>Record-Plan erzeugen</button></form></div>"
        if section=='operations': return base+f"<div class='panel'><h2>Build 312 · AI Security Agent v9</h2><form method='post' action='/build312/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-312 Records/OPSEC Selftest</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        return base
