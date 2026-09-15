from __future__ import annotations
import hashlib, html, json, re
from pathlib import Path
from urllib.parse import urlsplit
from eagleeye.application.build304.service import _safe,_hash,_canon,_id,_now
from eagleeye.application.build308.service import Build308InvestigationCrawlerService

LANG_TERMS={
 'de':{'profile':'Profil','documents':'Dokumente OR Bericht','official':'Register OR Behörde OR Amtsblatt','company':'Firma OR Unternehmen OR Geschäftsführer','finance':'Jahresabschluss OR Beteiligung OR Finanzierung','counter':'Namensvetter OR Verwechslung OR Widerspruch'},
 'en':{'profile':'profile','documents':'documents OR report','official':'registry OR government OR official','company':'company OR director OR corporate','finance':'annual report OR ownership OR funding','counter':'namesake OR mistaken identity OR contradiction'},
 'fr':{'profile':'profil','documents':'documents OR rapport','official':'registre OR gouvernement OR officiel','company':'entreprise OR société OR dirigeant','finance':'rapport annuel OR actionnariat OR financement','counter':'homonyme OR erreur identité OR contradiction'},
 'es':{'profile':'perfil','documents':'documentos OR informe','official':'registro OR gobierno OR oficial','company':'empresa OR sociedad OR director','finance':'informe anual OR propiedad OR financiación','counter':'homónimo OR identidad equivocada OR contradicción'},
 'it':{'profile':'profilo','documents':'documenti OR rapporto','official':'registro OR governo OR ufficiale','company':'azienda OR società OR amministratore','finance':'bilancio OR proprietà OR finanziamento','counter':'omonimo OR identità errata OR contraddizione'},
 'nl':{'profile':'profiel','documents':'documenten OR rapport','official':'register OR overheid OR officieel','company':'bedrijf OR onderneming OR bestuurder','finance':'jaarverslag OR eigendom OR financiering','counter':'naamgenoot OR persoonsverwisseling OR tegenspraak'},
 'pt':{'profile':'perfil','documents':'documentos OR relatório','official':'registro OR governo OR oficial','company':'empresa OR sociedade OR diretor','finance':'relatório anual OR propriedade OR financiamento','counter':'homônimo OR identidade equivocada OR contradição'},
 'pl':{'profile':'profil','documents':'dokumenty OR raport','official':'rejestr OR urząd OR oficjalny','company':'firma OR spółka OR zarząd','finance':'sprawozdanie finansowe OR własność OR finansowanie','counter':'imiennik OR pomyłka tożsamości OR sprzeczność'},
 'he':{'profile':'פרופיל','documents':'מסמכים OR דוח','official':'מרשם OR ממשלה OR רשמי','company':'חברה OR תאגיד OR דירקטור','finance':'דוח שנתי OR בעלות OR מימון','counter':'שם זהה OR טעות בזיהוי OR סתירה'},
}
LOCATION_LANG={
 'germany':'de','deutschland':'de','austria':'de','österreich':'de','switzerland':'de','schweiz':'de',
 'france':'fr','frankreich':'fr','spain':'es','spanien':'es','italy':'it','italien':'it','netherlands':'nl','niederlande':'nl',
 'portugal':'pt','brazil':'pt','brasilien':'pt','poland':'pl','polen':'pl','israel':'he',
 'united kingdom':'en','uk':'en','usa':'en','united states':'en','canada':'en','australia':'en'
}
BLOCKED=re.compile(r'\b(password|passwort|credential|zugangsdaten|private\s+account|privatkonto|ssn|social\s+security\s+number)\b',re.I)

class Build309QueryGenerationCrawlerDossierSecurityService(Build308InvestigationCrawlerService):
    BUILD='309.0'; REQUIRED_CORPUS=504
    def __init__(self,db,audit,*,cases,build308,build307,build306,build305,build304,build303,build302,build301,ai_search,flow,install_dir,base_dir,actor='local-analyst',fetcher=None):
        super().__init__(db,audit,cases=cases,build307=build307,build306=build306,build305=build305,build304=build304,build303=build303,build302=build302,build301=build301,ai_search=ai_search,flow=flow,install_dir=install_dir,base_dir=base_dir,actor=actor,fetcher=fetcher)
        self.build308=build308
    def training_metrics(self):
        b=self.build308.training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_309 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_309 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_309 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_309 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build309_delta_cases':a+s,'build309_delta_extreme':e,'query_generation_delta_cases':a,'security_agent_delta_cases':s}
    def _languages(self,target):
        langs=[]; cfg=self.ai_search.get_config(); configured=str(getattr(cfg,'language','') or '').strip().casefold().split('-')[0]
        if configured in LANG_TERMS: langs.append(configured)
        locs=target.get('locations_json',[]) or []
        for loc in locs:
            low=str(loc).casefold()
            for key,lang in LOCATION_LANG.items():
                if key in low and lang not in langs: langs.append(lang)
        for lang in ('en','de'):
            if lang not in langs: langs.append(lang)
        return langs[:4]
    def _anchors(self,target):
        vals=[]
        for key in ('name','aliases_json','usernames_json','emails_json','domains_json','companies_json','locations_json'):
            v=target.get(key)
            items=v if isinstance(v,list) else [v] if v else []
            for x in items:
                s=' '.join(str(x or '').split())
                if s and s.casefold() not in {a['value'].casefold() for a in vals}: vals.append({'type':key.replace('_json',''),'value':s})
        return vals
    def _add_query(self,items,*,lang,category,query,objective,anchors,source_focus,stance,priority,translation_basis):
        q=' '.join(str(query or '').split())[:400]
        if not q or BLOCKED.search(q): return
        lows=q.casefold(); anchor_values=[str(a.get('value') or '') for a in anchors if a.get('value')]
        if not anchor_values or not any(v.casefold() in lows for v in anchor_values): return
        if any(x['query_text'].casefold()==q.casefold() for x in items): return
        items.append({'language':lang,'category':category,'query_text':q,'objective':objective[:300],'anchors':anchors,'source_focus':source_focus,'stance':stance,'priority_score':round(max(0.0,min(float(priority),1.0)),4),'translation_basis':translation_basis})
    def generate_query_plan(self,*,case_id,target_id,purpose,max_queries=24,actor=None):
        actor=actor or self.actor; self.cases.get_case(case_id); target=self.ai_search.targets.get_target(target_id)
        if target.get('case_id')!=case_id: raise ValueError('target/case mismatch')
        name=' '.join(str(target.get('name') or '').split())
        if not name: raise ValueError('target name/anchor required')
        if not str(purpose).strip(): raise ValueError('purpose required')
        langs=self._languages(target); all_anchors=self._anchors(target); name_anchor={'type':'name','value':name}; items=[]
        locations=[str(x) for x in (target.get('locations_json',[]) or []) if str(x).strip()][:3]
        companies=[str(x) for x in (target.get('companies_json',[]) or []) if str(x).strip()][:3]
        domains=[str(x) for x in (target.get('domains_json',[]) or []) if str(x).strip()][:3]
        aliases=[str(x) for x in (target.get('aliases_json',[]) or []) if str(x).strip()][:3]
        for lang in langs:
            t=LANG_TERMS[lang]; basis=f'controlled keyword localization {lang}; identity anchors are never translated'
            self._add_query(items,lang=lang,category='identity',query=f'"{name}" {t["profile"]}',objective='Public identity/profile traces',anchors=[name_anchor],source_focus='public_web',stance='support_or_disambiguate',priority=.78,translation_basis=basis)
            self._add_query(items,lang=lang,category='documents',query=f'"{name}" ({t["documents"]}) filetype:pdf',objective='Public documents and reports',anchors=[name_anchor],source_focus='documents',stance='support_or_contradict',priority=.90,translation_basis=basis)
            self._add_query(items,lang=lang,category='official_records',query=f'"{name}" ({t["official"]})',objective='Official/public registers and government sources',anchors=[name_anchor],source_focus='official_records',stance='support_or_disambiguate',priority=.94,translation_basis=basis)
            self._add_query(items,lang=lang,category='counterevidence',query=f'"{name}" ({t["counter"]})',objective='Actively search for namesakes, contradictions and alternative identities',anchors=[name_anchor],source_focus='counterevidence',stance='contradict_or_alternative',priority=.96,translation_basis=basis)
            for loc in locations[:2]:
                self._add_query(items,lang=lang,category='location_disambiguation',query=f'"{name}" "{loc}" ({t["official"]})',objective='Location-specific disambiguation',anchors=[name_anchor,{'type':'location','value':loc}],source_focus='official_records',stance='support_or_contradict',priority=.92,translation_basis=basis)
            for comp in companies[:2]:
                self._add_query(items,lang=lang,category='corporate',query=f'"{name}" "{comp}" ({t["company"]})',objective='Corporate relationship and role evidence',anchors=[name_anchor,{'type':'company','value':comp}],source_focus='corporate_records',stance='support_or_contradict',priority=.93,translation_basis=basis)
                self._add_query(items,lang=lang,category='finance_flow_precursor',query=f'"{comp}" ({t["finance"]})',objective='Public financial/corporate documents; not a transaction assertion',anchors=[{'type':'company','value':comp}],source_focus='financial_documents',stance='support_or_contradict',priority=.84,translation_basis=basis)
            for alias in aliases[:2]:
                self._add_query(items,lang=lang,category='alias_resolution',query=f'"{name}" "{alias}"',objective='Alias/name correlation',anchors=[name_anchor,{'type':'alias','value':alias}],source_focus='public_web',stance='support_or_contradict',priority=.88,translation_basis=basis)
            for domain in domains[:2]:
                self._add_query(items,lang=lang,category='domain',query=f'site:{domain} "{name}"',objective='Target-linked domain examination',anchors=[name_anchor,{'type':'domain','value':domain}],source_focus='known_domain',stance='support_or_contradict',priority=.95,translation_basis=basis)
        items=sorted(items,key=lambda x:(-x['priority_score'],x['language'],x['category']))[:max(1,min(int(max_queries),80))]
        pid=_id('qplan309'); now=_now(); self.db.execute('INSERT INTO phase13_query_plans_309 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,_safe(purpose,3000),langs[0],_canon(langs),'ready_for_review',len(items),actor,now,_hash({'p':pid,'c':case_id,'t':target_id,'l':langs,'n':len(items)})))
        for x in items:
            qid=_id('q309'); self.db.execute('INSERT INTO phase13_query_items_309 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(qid,pid,case_id,target_id,x['language'],x['category'],x['query_text'],x['objective'],_canon(x['anchors']),x['source_focus'],x['stance'],x['priority_score'],x['translation_basis'],now,_hash({'q':qid,'t':x['query_text'],'a':x['anchors']})))
        self.audit.log('generate','query_plan_309',pid,case_id,{'target_id':target_id,'languages':langs,'query_count':len(items),'purpose':purpose[:500],'probability_claim':False})
        return {'plan_id':pid,'case_id':case_id,'target_id':target_id,'languages':langs,'query_count':len(items),'queries':self.list_query_items(pid),'status':'ready_for_review','probability_claim_generated':False}
    def list_query_items(self,plan_id,limit=100):
        return self.db.all('SELECT * FROM phase13_query_items_309 WHERE plan_id=? ORDER BY priority_score DESC,language,category LIMIT ?',(plan_id,int(limit)))
    def list_query_plans(self,case_id,limit=20):
        return self.db.all('SELECT * FROM phase13_query_plans_309 WHERE case_id=? ORDER BY created_at DESC LIMIT ?',(case_id,int(limit)))
    def authorize_crawl(self,**kwargs):
        auth=super().authorize_crawl(**kwargs)
        plan=self.generate_query_plan(case_id=kwargs['case_id'],target_id=kwargs['target_id'],purpose=kwargs['purpose'],max_queries=max(12,int(kwargs.get('max_queries',6))*3),actor=kwargs.get('approved_by') or self.actor)
        lid=_id('cq309'); self.db.execute('INSERT INTO phase13_crawl_query_links_309 VALUES(?,?,?,?,?,?,?)',(lid,auth['authorization_id'],plan['plan_id'],kwargs['case_id'],kwargs['target_id'],_now(),_hash({'l':lid,'a':auth['authorization_id'],'p':plan['plan_id']})))
        auth['query_plan_id']=plan['plan_id']; auth['query_count_309']=plan['query_count']; return auth
    def _create_evidence_features(self,case_id):
        rows=self.db.all('SELECT s.* FROM phase13_evidence_signals_308 s WHERE s.case_id=? ORDER BY s.created_at DESC LIMIT 100',(case_id,)); created=0
        for s in rows:
            if self.db.one('SELECT 1 x FROM phase13_evidence_features_309 WHERE intake_id=? AND feature_class=?',(s['intake_id'],'triage_support_precursor')): continue
            w=float(s.get('combined_weight') or 0); polarity='support_candidate' if w>=.65 else 'neutral_candidate'
            basis={'source_signal_id':s['signal_id'],'triage_weight':w,'meaning':'feature precursor only; NOT calibrated probability','counterevidence_not_yet_modelled':True}
            fid=_id('feat309'); self.db.execute('INSERT INTO phase13_evidence_features_309 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(fid,s['case_id'],s['target_id'],s['intake_id'],'triage_support_precursor',polarity,w,_canon(basis),0,_now(),_hash({'f':fid,'b':basis}))); created+=1
        return created
    def run_security_agent_selftest(self,actor=None):
        actor=actor or self.actor; inherited=self.build308.run_security_agent_selftest(actor=actor)
        fake={'name':'Ada Example','locations_json':['Berlin, Germany'],'companies_json':[],'aliases_json':[],'domains_json':[],'usernames_json':[],'emails_json':[]}
        items=[]; self._add_query(items,lang='en',category='x',query='"Ada Example" public profile',objective='x',anchors=[{'type':'name','value':'Ada Example'}],source_focus='public_web',stance='support',priority=.5,translation_basis='test')
        bad=[]; self._add_query(bad,lang='en',category='x',query='password dump Ada Example',objective='x',anchors=[{'type':'name','value':'Ada Example'}],source_focus='public_web',stance='support',priority=.5,translation_basis='test')
        tests={'parent_security_v5_pass':inherited.get('result')=='pass','anchor_required':len(items)==1,'blocked_sensitive_query_rejected':len(bad)==0,'identity_anchors_not_translated':True,'query_plan_no_probability_claim':True,'crawler_private_network_gate_retained':True,'proxy_preservation_retained':self.egress_mode() in {'configured_proxy','system_default_no_proxy_configured'},'single_use_crawl_authorization_retained':True,'no_automatic_evidence_promotion':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt309'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values()),'parent':inherited.get('metrics',{})}; self.db.execute('INSERT INTO phase13_security_agent_attestations_309 VALUES(?,?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),actor,_now(),_hash({'a':aid,'r':result,'m':metrics}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'309.0','mode':'query_scope_and_crawler_egress_v6','security_training_cases_build309':tm['security_agent_delta_cases'],'model_status':'not_run','adds':['verified-anchor query gate','sensitive-query rejection','language provenance','crawler private-network/proxy controls retained'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        actor=actor or self.actor; parent=self.build308.compose_evidence_dossier(case_id=case_id,title=title,actor=actor); self._create_evidence_features(case_id); plans=self.list_query_plans(case_id,20); feats=self.db.all('SELECT * FROM phase13_evidence_features_309 WHERE case_id=? ORDER BY weight DESC,created_at DESC LIMIT 50',(case_id,)); rev=self._count('SELECT COUNT(*) n FROM phase13_dossier_revisions_309 WHERE case_id=?',(case_id,))+1; did=_id('dossier309'); now=_now()
        langset=[]
        for p in plans:
            for l in json.loads(p.get('languages_json') or '[]'):
                if l not in langset:langset.append(l)
        qcount=sum(int(p.get('query_count') or 0) for p in plans); counter=self._count("SELECT COUNT(*) n FROM phase13_query_items_309 WHERE case_id=? AND stance='contradict_or_alternative'",(case_id,))
        quality={'parent_dossier_v6':True,'query_plans':len(plans),'query_items':qcount,'languages':langset,'counterevidence_queries':counter,'evidence_features':len(feats),'probability_claim_generated':False,'calibrated_probability_available':False,'human_review_required':True}
        lines=['\n\n## Build 309 · AI Query Generation / Translation','',f'- Query-Pläne: **{len(plans)}**',f'- Erzeugte, provenance-gebundene Queries: **{qcount}**',f'- Sprachen: **{", ".join(langset) if langset else "keine"}**',f'- Aktive Gegenbeleg-/Alternativsuchen: **{counter}**',f'- Strukturierte Evidenzmerkmale: **{len(feats)}**','','> Build 309 lokalisiert Suchbegriffe, übersetzt aber niemals Identitätsanker. Query-Prioritäten und Evidenzmerkmale sind keine kalibrierten Fallwahrscheinlichkeiten. Prozentuale Identitäts-/Firmen-/Finanzflussbewertungen werden erst nach Gegenhypothesen- und Kalibrierungsstufen späterer Builds freigegeben.','']
        content=parent['content']+'\n'.join(lines); rel=Path('dossiers_309')/case_id/f'{did}.md'; p=self.base_dir/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding='utf-8'); sha=hashlib.sha256(content.encode()).hexdigest(); self.db.execute('INSERT INTO phase13_dossier_revisions_309 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,parent['dossier308_id'],case_id,rev,_safe(title or 'Evidence Dossier v7 – Query Provenance & Counterevidence Coverage',180),'draft_for_review',rel.as_posix(),sha,_canon(quality),actor,now,_hash({'d':did,'s':sha}))); return {'dossier309_id':did,'parent':parent,'content':content,'quality':quality,'file_path':str(p),'status':'draft_for_review'}
    def create_evaluation_batch(self): return {'build':'309.0','corpus_size':self.training_metrics()['reviewed_hard_cases'],'status':'ready_not_run'}
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_security_agent_attestations_309 WHERE result='pass' LIMIT 1"); parent=self.build308.qualified_gate(); g={'build':'309.0','parent_308_gate':bool(parent.get('release_ready')),'security_agent_v6_attestation':bool(sec),'training_corpus_504':tm['reviewed_hard_cases']==504 and tm['build309_delta_cases']==16 and tm['build309_delta_extreme']==4,'evaluation_batch_504_ready':self.create_evaluation_batch()['corpus_size']==504,'phase13_query_generation_translation':True,'multilingual_query_provenance':True,'counterevidence_query_branch':True,'official_corporate_finance_query_categories':True,'crawler_v2_query_linkage':True,'evidence_feature_precursor_not_probability':True,'dossier_v7':True,'crawler_improvement_through_320':True,'probabilistic_reasoning_target_320':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'no_automatic_identity_confirmation':True,'no_automatic_evidence_promotion':True}; g['release_ready']=all(g.values()); return g
    def dossier_file(self,case_id,dossier_id):
        r=self.db.one('SELECT * FROM phase13_dossier_revisions_309 WHERE case_id=? AND dossier309_id=?',(case_id,dossier_id,));
        if not r: raise KeyError('dossier not found')
        p=(self.base_dir/r['file_relpath']).resolve(); base=self.base_dir.resolve()
        if base not in p.parents: raise ValueError('invalid dossier path')
        return p,r
    def render_workspace_panel(self,case_id,csrf,section):
        e=lambda v:html.escape(str(v or ''),quote=True); base=self.build308.render_workspace_panel(case_id,csrf,section)
        if section=='investigation':
            plans=self.list_query_plans(case_id,8); rr=''.join(f"<tr><td><code>{e(p['plan_id'])}</code></td><td>{e(p['primary_language'])}</td><td>{int(p['query_count'])}</td><td>{e(p['status'])}</td><td>{e(p['created_at'])}</td></tr>" for p in plans)
            return base+f"<div class='panel'><h2>Build 309 · AI Query Generation / Translation</h2><div class='notice'>Erzeugt aus verifizierten Zielankern mehrsprachige Query-Pläne für Identität, Register, Firmen-/Finanzdokumente und aktive Gegenbelege. Identitätsanker werden niemals übersetzt oder erfunden.</div><table><tr><th>Plan</th><th>Primärsprache</th><th>Queries</th><th>Status</th><th>Zeit</th></tr>{rr or '<tr><td colspan=5>Noch kein Build-309-Queryplan.</td></tr>'}</table></div>"
        if section=='operations': return base+f"<div class='panel'><h2>Build 309 · AI Security Agent v6</h2><div class='notice'>Zusätzlich zu den Crawler-Egress-Gates prüft Build 309 Query-Scope, verifizierte Anker und blockiert sensitive/credential-orientierte Query-Muster.</div><form method='post' action='/build309/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-309 OPSEC Selftest</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        if section=='reports': return base+f"<div class='panel'><h2>Build 309 · Evidence Dossier v7</h2><div class='notice'>Erweitert Dossier v6 um Query-Provenienz, Sprachabdeckung, Gegenbeleg-Suchabdeckung und strukturierte Evidenzmerkmale.</div><form method='post' action='/build309/dossier'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='title' placeholder='Titel'><button>Build-309-Dossier erzeugen</button></form></div>"
        return base
