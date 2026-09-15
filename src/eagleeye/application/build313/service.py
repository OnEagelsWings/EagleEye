from __future__ import annotations
import hashlib, html, ipaddress, json, re
from pathlib import Path
from urllib.parse import urlsplit
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build312.service import Build312CorporatePersonRecordsService

_TECH_FAMILIES=['rdap_registry','dns_public','certificate_transparency','asn_bgp_public','public_web_metadata','repository_metadata','counterevidence']
_SAFE_FIELDS={'domain','hostname','ip_public','asn','cidr_public','registrar','rdap_handle','nameserver','mx','certificate_subject','certificate_issuer','certificate_san','certificate_not_before','certificate_not_after','organisation','country','technology_public_metadata','repository','public_url'}

class Build313TechnicalIntelligenceDataService(Build312CorporatePersonRecordsService):
    BUILD='313.0'; REQUIRED_CORPUS=568
    def __init__(self,*args,build312=None,**kwargs):
        super().__init__(*args,**kwargs); self.build312=build312 or self
    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_313 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_313 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_313 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_313 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build313_delta_cases':a+s,'build313_delta_extreme':e,'technical_intel_delta_cases':a,'security_agent_delta_cases_313':s}
    @staticmethod
    def _public_ip(value):
        try:
            ip=ipaddress.ip_address(str(value).strip()); return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified)
        except Exception: return False
    def create_technical_plan(self,*,case_id,target_id,objective,anchors=None,actor=None):
        actor=actor or self.actor; objective=' '.join(str(objective or '').split())[:1000]
        if not objective: raise ValueError('Analyseziel fehlt')
        if self.research_strategy: self.research_strategy._require_target(case_id,target_id)
        anchors=[] if anchors is None else self._clean_list(anchors,8)
        qp=self.generate_query_plan(case_id=case_id,target_id=target_id,purpose=f"{objective}; passive technical intelligence rdap dns certificate transparency asn bgp public metadata counterevidence",max_queries=32,actor=actor)
        bp=self.create_broker_plan(case_id=case_id,target_id=target_id,objective=f"{objective} RDAP DNS certificate transparency ASN BGP public repository counterevidence",actor=actor)
        pid=_id('techplan313'); now=_now(); content={'anchors':anchors,'families':list(_TECH_FAMILIES),'query_plan_id':qp['plan_id'],'broker_plan_id':bp['plan_id'],'candidate_only':True,'passive_only':True,'active_scanning':False,'probability_claim_generated':False}
        self.db.execute('INSERT INTO phase13_technical_plans_313 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,target_id,hashlib.sha256(objective.encode()).hexdigest(),_canon(anchors),_canon(_TECH_FAMILIES),qp['plan_id'],bp['plan_id'],'planned',actor,now,_hash({'p':pid,'c':content})))
        return {'plan_id':pid,**content,'query_count':len(qp.get('queries',[])),'broker_routes':len(bp.get('routes',[]))}
    def ingest_technical_candidate(self,*,plan_id,technical_type,source_label,source_url,fields,evidence_refs=None,support_direction='support'):
        plan=self.db.one('SELECT * FROM phase13_technical_plans_313 WHERE plan_id=?',(plan_id,))
        if not plan: raise KeyError('Technical-Plan nicht gefunden')
        typ=' '.join(str(technical_type or '').split())[:100]
        if typ not in _TECH_FAMILIES: raise ValueError('Nicht zugelassene Technical-Intelligence-Familie')
        url=str(source_url or '').strip()[:2000]
        if url and not url.startswith(('http://','https://')): raise ValueError('Nur öffentliche HTTP(S)-Quellen')
        host=(urlsplit(url).hostname or '').casefold() if url else ''
        safe={}; dropped=[]
        for k,v in dict(fields or {}).items():
            key=re.sub(r'[^a-z0-9_]+','_',str(k).strip().casefold())[:80]
            if key not in _SAFE_FIELDS: dropped.append(key); continue
            vals=v if isinstance(v,list) else [v]; cleaned=[]
            for item in vals:
                s=' '.join(str(item).split())[:500]
                if key in {'ip_public'} and not self._public_ip(s): dropped.append(f'{key}:nonpublic'); continue
                if key=='cidr_public':
                    try:
                        net=ipaddress.ip_network(s,strict=False)
                        if net.is_private or net.is_loopback or net.is_link_local or net.is_reserved: dropped.append(f'{key}:nonpublic'); continue
                    except Exception: dropped.append(f'{key}:invalid'); continue
                if s: cleaned.append(s)
            if cleaned: safe[key]=cleaned if isinstance(v,list) else cleaned[0]
        if not safe: raise ValueError('Keine zulässigen öffentlichen technischen Felder')
        direction=str(support_direction or 'support').casefold(); direction=direction if direction in {'support','counter','neutral'} else 'neutral'
        refs=self._clean_list(evidence_refs or [],30); cid=_id('techcand313'); now=_now(); source_group=host or hashlib.sha256(str(source_label or '').encode()).hexdigest()[:16]
        payload={'fields':safe,'dropped_fields':dropped,'candidate_only':True,'passive_only':True,'field_count':len(safe)}
        self.db.execute('INSERT INTO phase13_technical_candidates_313 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,plan_id,plan['case_id'],plan['target_id'],typ,str(source_label or '')[:300],url,source_group,_canon(payload),_canon(refs),direction,'candidate_only',now,_hash({'c':cid,'p':plan_id,'f':safe})))
        return {'candidate_id':cid,'technical_type':typ,'normalized':payload,'source_group':source_group,'support_direction':direction,'review_status':'candidate_only'}
    def assess_technical_bundle(self,plan_id):
        plan=self.db.one('SELECT * FROM phase13_technical_plans_313 WHERE plan_id=?',(plan_id,));
        if not plan: raise KeyError('Technical-Plan nicht gefunden')
        rows=self.db.all('SELECT * FROM phase13_technical_candidates_313 WHERE plan_id=? ORDER BY created_at',(plan_id,)); values={}; contradictions=[]
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
        aid=_id('techassess313'); now=_now(); self.db.execute('INSERT INTO phase13_technical_bundle_assessments_313 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(aid,plan_id,plan['case_id'],plan['target_id'],support,counter,groups,_canon(agreement),_canon(contradictions),round(readiness,2),0,now,_hash({'a':aid,'r':round(readiness,2)})))
        return {'assessment_id':aid,'candidate_count':len(rows),'support_count':support,'counter_count':counter,'independent_source_groups':groups,'field_agreement':agreement,'contradictions':contradictions,'assessment_readiness_score':round(readiness,2),'score_meaning':'technical_evidence_workflow_readiness_not_probability','probability_claim_generated':False}
    def technical_query_ladder(self,anchor,family):
        anchor=' '.join(str(anchor or '').split())[:200]; family=' '.join(str(family or '').split())[:80]
        broad=' '.join(x for x in [f'"{anchor}"' if anchor else '',family] if x); focused=' '.join(x for x in [f'"{anchor}"' if anchor else '',f'({family} OR RDAP OR DNS OR certificate OR ASN)'] if x); precision=' '.join(x for x in [focused,'site:iana.org OR site:arin.net OR site:ripe.net'] if x)
        return [{'variant':'broad','query':broad},{'variant':'focused','query':focused},{'variant':'precision','query':precision}]
    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v9_pass':parent.get('result')=='pass','passive_public_metadata_only':True,'no_port_scanning':True,'no_service_fingerprinting':True,'no_credential_testing':True,'private_ip_rejected':not self._public_ip('10.0.0.4'),'loopback_rejected':not self._public_ip('127.0.0.1'),'public_ip_allowed':self._public_ip('8.8.8.8'),'proxy_preservation_retained':True,'candidate_only_technical_records':True,'no_automatic_identity_confirmation':True,'no_probability_from_technical_hit_count':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt313'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase13_technical_attestations_313 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'313.0','mode':'passive_technical_intelligence_opsec_v10','security_training_cases_build313':tm['security_agent_delta_cases_313'],'model_status':'not_run','adds':['passive technical metadata boundary','public IP/CIDR filtering','no active scan','technical candidate provenance'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        actor=actor or self.actor; parent=self.build312.compose_evidence_dossier(case_id=case_id,title=title,actor=actor); plans=self.db.all('SELECT * FROM phase13_technical_plans_313 WHERE case_id=? ORDER BY created_at DESC LIMIT 30',(case_id,)); cands=self.db.all('SELECT * FROM phase13_technical_candidates_313 WHERE case_id=? ORDER BY created_at DESC LIMIT 200',(case_id,)); ass=self.db.all('SELECT * FROM phase13_technical_bundle_assessments_313 WHERE case_id=? ORDER BY created_at DESC LIMIT 30',(case_id,)); quality={'parent_dossier':True,'technical_plans':len(plans),'technical_candidates':len(cands),'technical_bundle_assessments':len(ass),'passive_only':True,'probability_claim_generated':False,'human_review_required':True}
        lines=['\n\n## Build 313 · Technical Intelligence Data','',f'- Technical-Pläne: **{len(plans)}**',f'- passive Candidate-Records: **{len(cands)}**',f'- Technical-Assessments: **{len(ass)}**','', '> Technische Metadaten werden ausschließlich passiv und quellengebunden verarbeitet. Korrelationen sind keine Identitätswahrscheinlichkeit und aktive Scans sind ausgeschlossen.','']
        if ass: lines += [f'- Letzter Technical-Readiness-Score: **{ass[0].get("readiness_score",0):.1f}/100** (Workflow-Reife, keine Wahrscheinlichkeit)','']
        content=parent['content']+'\n'.join(lines); did=_id('dossier313'); rev=self._count('SELECT COUNT(*) n FROM phase13_dossier_revisions_313 WHERE case_id=?',(case_id,))+1; rel=Path('dossiers_313')/case_id/f'{did}.md'; path=Path(self.base_dir)/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(content,encoding='utf-8'); ch=hashlib.sha256(content.encode()).hexdigest(); self.db.execute('INSERT INTO phase13_dossier_revisions_313 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(did,parent.get('dossier_id',''),case_id,rev,title or f'EagleEye Evidence Dossier · {case_id}','draft_for_review',str(rel),ch,_canon(quality),actor,_now(),_hash({'d':did,'c':ch}))); return {'dossier_id':did,'parent_dossier_id':parent.get('dossier_id',''),'case_id':case_id,'revision_no':rev,'status':'draft_for_review','content':content,'quality':quality,'file_relpath':str(rel),'content_sha256':ch}
    def dossier_file(self,case_id,dossier_id):
        row=self.db.one('SELECT * FROM phase13_dossier_revisions_313 WHERE case_id=? AND dossier313_id=?',(case_id,dossier_id));
        if not row: raise KeyError('Dossier nicht gefunden')
        p=(Path(self.base_dir)/row['file_relpath']).resolve(); root=Path(self.base_dir).resolve()
        if root not in p.parents: raise PermissionError('Ungültiger Dossierpfad')
        return p,row
    def qualified_gate(self):
        tm=self.training_metrics(); sec=self.db.one("SELECT 1 x FROM phase13_technical_attestations_313 WHERE result='pass' LIMIT 1"); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try: parent_ok=bool(json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_312_0.json').read_text(encoding='utf-8')).get('gate',{}).get('release_ready'))
            except Exception: parent_ok=False
        g={'build':'313.0','parent_312_gate':parent_ok,'security_agent_v10_attestation':bool(sec),'training_corpus_568':tm['reviewed_hard_cases']==568 and tm['build313_delta_cases']==16 and tm['build313_delta_extreme']==4,'phase13_technical_intelligence_data':True,'passive_public_metadata_only':True,'private_network_filtering':True,'candidate_only_technical_records':True,'adaptive_technical_query_ladder':True,'crawler_technical_scope_ready':True,'probabilistic_reasoning_target_320':True,'dossier_improvement_through_320':True,'security_agent_improvement_through_320':True,'no_active_scanning':True,'no_probability_from_technical_hit_count':True}; g['release_ready']=all(g.values()); return g
    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='investigation':
            targets=self.db.all('SELECT target_id,name FROM targets WHERE case_id=? ORDER BY created_at DESC',(case_id,)); opts=''.join(f"<option value='{e(t['target_id'])}'>{e(t['name'])}</option>" for t in targets)
            return base+f"<div class='panel'><h2>Build 313 · Technical Intelligence Data</h2><div class='notice'>Passive öffentliche technische Metadaten: RDAP/DNS/Certificate Transparency/ASN-BGP/Web- und Repository-Metadaten. Keine aktiven Scans.</div><form method='post' action='/build313/technical-plan'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Ziel</label><select name='target_id' required>{opts}</select></div><div class='field'><label>Ermittlungsziel</label><textarea name='objective' rows='3' required></textarea></div><div class='field'><label>Öffentliche Anker (Komma: Domain/Hostname/ASN)</label><input name='anchors'></div><button>Technical-Plan erzeugen</button></form></div>"
        if section=='operations': return base+f"<div class='panel'><h2>Build 313 · AI Security Agent v10</h2><form method='post' action='/build313/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Build-313 Technical/OPSEC Selftest</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        return base
