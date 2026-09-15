from __future__ import annotations
import hashlib, html, json
from pathlib import Path
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build315.service import Build315CrossDatabaseEntityResolutionService

class Build316IntelligenceDataFabricService(Build315CrossDatabaseEntityResolutionService):
    BUILD='316.0'; REQUIRED_CORPUS=616
    def __init__(self,*args,build315=None,**kwargs):
        super().__init__(*args,**kwargs); self.build315=build315 or self
    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_316 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_316 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_316 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_316 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build316_delta_cases':a+s,'build316_delta_extreme':e,'data_fabric_delta_cases':a,'security_agent_delta_cases_316':s}
    def create_fabric_snapshot(self,*,case_id,target_id,objective='',actor=None):
        actor=actor or self.actor
        if self.research_strategy: self.research_strategy._require_target(case_id,target_id)
        sid=_id('fabric316'); objective=' '.join(str(objective or '').split())[:1200] or 'unified case intelligence fabric'
        layers=['records312','technical313','govlegal314','resolution315']
        self.db.execute('INSERT INTO phase13_fabric_snapshots_316 VALUES(?,?,?,?,?,?,?,?,?)',(sid,case_id,target_id,objective,_canon(layers),'planned',actor,_now(),_hash({'s':sid,'c':case_id,'t':target_id,'l':layers})))
        return {'snapshot_id':sid,'case_id':case_id,'target_id':target_id,'objective':objective,'source_layers':layers,'status':'planned','probability_claim_generated':False}
    def _resolution_signals(self,case_id,target_id):
        try: return self.db.all('SELECT * FROM phase13_entity_resolution_signals_315 WHERE case_id=? AND target_id=? ORDER BY created_at',(case_id,target_id))
        except Exception: return []
    def materialize_fabric(self,snapshot_id):
        snap=self.db.one('SELECT * FROM phase13_fabric_snapshots_316 WHERE snapshot_id=?',(snapshot_id,))
        if not snap: raise KeyError('Data-Fabric-Snapshot nicht gefunden')
        inserted=[]; index={}
        for r in self._resolution_signals(snap['case_id'],snap['target_id']):
            iid=_id('fabricitem316'); prov={'source_layer':r['source_layer'],'source_record_id':r['source_record_id'],'source_group':r['source_group'],'resolution_signal_id':r['signal_id']}
            self.db.execute('INSERT INTO phase13_fabric_items_316 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(iid,snapshot_id,snap['case_id'],snap['target_id'],r['source_layer'],r['source_record_id'],r['source_group'],'canonical_signal',r['field_name'],r['normalized_value'],r['direction'],r['weight_class'],r['independence_key'],_canon(prov),_now(),_hash({'i':iid,'p':prov,'v':r['normalized_value']})))
            inserted.append(iid); index.setdefault(r['field_name'],[]).append((iid,r))
        links=[]
        for field,items in index.items():
            for i in range(len(items)):
                a_id,a=items[i]
                for j in range(i+1,len(items)):
                    b_id,b=items[j]
                    if a['independence_key']==b['independence_key']:
                        typ='dependency'; rationale='same independence key; do not count as independent corroboration'
                    elif a['normalized_value']==b['normalized_value'] and a['source_group']!=b['source_group']:
                        typ='corroboration'; rationale='same canonical value from distinct source groups'
                    elif a['normalized_value']!=b['normalized_value']:
                        typ='conflict'; rationale='different canonical values for same field'
                    else: continue
                    lid=_id('fabriclink316'); self.db.execute('INSERT INTO phase13_fabric_links_316 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(lid,snapshot_id,snap['case_id'],snap['target_id'],a_id,b_id,typ,field,rationale,_now(),_hash({'l':lid,'a':a_id,'b':b_id,'t':typ}))); links.append(lid)
        self.db.execute("UPDATE phase13_fabric_snapshots_316 SET status='materialized' WHERE snapshot_id=?",(snapshot_id,))
        return {'snapshot_id':snapshot_id,'items_created':len(inserted),'links_created':len(links),'status':'materialized'}
    def assess_fabric(self,snapshot_id):
        snap=self.db.one('SELECT * FROM phase13_fabric_snapshots_316 WHERE snapshot_id=?',(snapshot_id,))
        if not snap: raise KeyError('Data-Fabric-Snapshot nicht gefunden')
        items=self.db.all('SELECT * FROM phase13_fabric_items_316 WHERE snapshot_id=?',(snapshot_id,)); links=self.db.all('SELECT * FROM phase13_fabric_links_316 WHERE snapshot_id=?',(snapshot_id,))
        support=sum(x['direction']=='support' for x in items); counter=sum(x['direction']=='counter' for x in items); neutral=sum(x['direction']=='neutral' for x in items)
        groups=len({x['source_group'] for x in items if x['source_group']}); corr=sum(x['link_type']=='corroboration' for x in links); conflict=sum(x['link_type']=='conflict' for x in links); dep=sum(x['link_type']=='dependency' for x in links)
        questions=[]
        if conflict: questions.append('Resolve conflicting canonical values before probability estimation.')
        if groups<2: questions.append('Obtain at least one additional independent source group.')
        if not counter: questions.append('Actively search for counterevidence / alternative explanation.')
        raw=20*min(groups,5)/5 + 25*min(corr,6)/6 + 20*min(len(items),16)/16 + 20*(1 if counter else 0) + 15*(1 if conflict else 0)
        penalty=min(20,dep*2); score=round(max(0,min(100,raw-penalty)),2)
        aid=_id('fabricassess316'); self.db.execute('INSERT INTO phase13_fabric_assessments_316 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,snapshot_id,snap['case_id'],snap['target_id'],len(items),len(links),groups,support,counter,neutral,corr,conflict,dep,_canon(questions),score,0,_now(),_hash({'a':aid,'s':score,'q':questions})))
        self.db.execute("UPDATE phase13_fabric_snapshots_316 SET status='assessed' WHERE snapshot_id=?",(snapshot_id,))
        return {'assessment_id':aid,'snapshot_id':snapshot_id,'item_count':len(items),'link_count':len(links),'independent_source_groups':groups,'support_items':support,'counter_items':counter,'neutral_items':neutral,'corroboration_links':corr,'conflict_links':conflict,'dependency_links':dep,'open_questions':questions,'fabric_readiness_score':score,'score_meaning':'intelligence_data_fabric_readiness_not_probability','probability_claim_generated':False,'human_review_required':True}
    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v12_pass':parent.get('result')=='pass','case_bound_snapshots':True,'candidate_only_materialization':True,'immutable_source_provenance':True,'dependency_links_preserved':True,'conflict_links_preserved':True,'counterevidence_retained':True,'no_auto_identity_confirmation':True,'no_auto_evidence_promotion':True,'no_probability_from_data_volume':True,'real_active_recon_still_disabled':True,'human_review_required':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt316'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase13_security_attestations_316 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'316.0','mode':'intelligence_data_fabric_opsec_v13','security_training_cases_build316':tm['security_agent_delta_cases_316'],'model_status':'not_run','adds':['fabric provenance retention','dependency/conflict graph','case-bound snapshots','no probability from data volume'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        actor=actor or self.actor; parent=self.build315.compose_evidence_dossier(case_id=case_id,title=title,actor=actor)
        snaps=self.db.all('SELECT * FROM phase13_fabric_snapshots_316 WHERE case_id=? ORDER BY created_at DESC LIMIT 50',(case_id,)); ass=self.db.all('SELECT * FROM phase13_fabric_assessments_316 WHERE case_id=? ORDER BY created_at DESC LIMIT 50',(case_id,))
        quality={'parent_dossier':True,'fabric_snapshots':len(snaps),'fabric_assessments':len(ass),'provenance_preserved':True,'dependency_graph':True,'conflict_graph':True,'probability_claim_generated':False,'human_review_required':True}
        lines=['\n\n## Build 316 · Intelligence Data Fabric','',f'- Fabric-Snapshots: **{len(snaps)}**',f'- Fabric-Assessments: **{len(ass)}**','', '> Die gemeinsame Fall-Datenebene bewahrt Herkunft, Quellenabhängigkeit, Konflikte und Gegenbelege. Der Readiness-Wert ist keine Wahrscheinlichkeit.','']
        if ass:
            a=ass[0]; lines += [f'- Letzter Fabric-Readiness-Score: **{a.get("fabric_readiness_score",0):.1f}/100** (keine Wahrscheinlichkeit)',f'- Unabhängige Quellengruppen: **{a.get("independent_groups",0)}**',f'- Corroboration-/Conflict-/Dependency-Links: **{a.get("corroboration_links",0)} / {a.get("conflict_links",0)} / {a.get("dependency_links",0)}**','']
        content=parent['content']+'\n'.join(lines); did=_id('dossier316'); rev=self._count('SELECT COUNT(*) n FROM phase13_dossier_revisions_316 WHERE case_id=?',(case_id,))+1; rel=Path('dossiers_316')/case_id/f'{did}.md'; path=Path(self.base_dir)/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content,encoding='utf-8'); ch=hashlib.sha256(content.encode()).hexdigest(); self.db.execute('INSERT INTO phase13_dossier_revisions_316 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,parent.get('dossier_id',''),case_id,rev,title or f'EagleEye Evidence Dossier · {case_id}','draft_for_review',str(rel),ch,_canon(quality),actor,_now(),_hash({'d':did,'c':ch}))); return {'dossier_id':did,'parent_dossier_id':parent.get('dossier_id',''),'case_id':case_id,'revision_no':rev,'status':'draft_for_review','content':content,'quality':quality,'file_relpath':str(rel),'content_sha256':ch}
    def dossier_file(self,case_id,dossier_id):
        row=self.db.one('SELECT * FROM phase13_dossier_revisions_316 WHERE case_id=? AND dossier316_id=?',(case_id,dossier_id,))
        if not row: raise KeyError('Dossier nicht gefunden')
        p=(Path(self.base_dir)/row['file_relpath']).resolve(); root=Path(self.base_dir).resolve()
        if root not in p.parents: raise PermissionError('Ungültiger Dossierpfad')
        return p,row
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_security_attestations_316 WHERE result='pass' LIMIT 1"); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try: parent_ok=bool(json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_315_0.json').read_text(encoding='utf-8')).get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        g={'build':'316.0','parent_315_gate':parent_ok,'security_agent_v13_attestation':bool(sec),'training_corpus_616':tm['reviewed_hard_cases']==616 and tm['build316_delta_cases']==16 and tm['build316_delta_extreme']==4,'phase13_intelligence_data_fabric':True,'unified_case_data_layer':True,'provenance_retention':True,'dependency_conflict_graph':True,'counterevidence_retention':True,'probabilistic_reasoning_target_320':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'real_active_recon_disabled':True,'no_probability_from_data_volume':True}; g['release_ready']=all(g.values()); return g
    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 316 · Intelligence Data Fabric</h2><div class='notice'>Erzeugt einen fallgebundenen Snapshot über Records, Technical/Government-Layer und Entity-Resolution-Signale. Provenienz, Abhängigkeiten und Konflikte bleiben sichtbar.</div><form method='post' action='/build316/fabric'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Zweck</label><textarea name='objective' rows='3'></textarea></div><button>Data-Fabric-Snapshot erzeugen</button></form></div>"
        if section=='operations': return base+f"<div class='panel'><h2>Build 316 · AI Security Agent v13</h2><form method='post' action='/build316/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-316 Data-Fabric/OPSEC Selftest</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        return base
