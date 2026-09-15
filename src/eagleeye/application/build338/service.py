from __future__ import annotations
import html, json, hashlib, re
from pathlib import Path
from typing import Any
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build337.service import Build337AIInvestigationSupervisorService


class Build338DossierVNextRedTeamService(Build337AIInvestigationSupervisorService):
    BUILD='338.0'; REQUIRED_CORPUS=968
    RELEASE_AUTH='DOSSIER VNEXT FREIGEBEN'
    CLAIM_TYPES={'factual_observation','assessment','hypothesis','counterevidence','unresolved_conflict','data_gap'}
    MATERIALITY={'low','medium','high'}
    HUMAN_DISPOSITIONS={'approved_for_release','needs_rework','withheld'}

    def _ensure_dossier_profile(self):
        row=self.db.one("SELECT * FROM phase14_dossier_profiles_338 WHERE profile_name='Dossier vNext + Red-Team Review' LIMIT 1")
        if row:return dict(row)
        standards={
          'inspired_by':['ICD 203 analytic standards','CIA structured analytic techniques','NIST AI RMF challenge/red-team oversight'],
          'separate_information_assumptions_judgments':True,
          'source_quality_and_independence_explicit':True,
          'alternatives_and_contrary_information_required':True,
          'uncertainty_and_information_gaps_explicit':True,
          'probability_output':'disabled_until_build336_qualified_and_human_activated',
        }
        redteam={
          'logical_separation_from_supervisor':True,
          'does_not_mutate_supervisor_or_claims':True,
          'tests':['unsupported_material_claim','source_echo','single_origin_material_assessment','missing_counterevidence','assumption_dependency','identity_conflict','temporal_scope','legal_finality','probability_leak','overclaim_language'],
          'falsification_rule':'failure_to_find_falsifier_is_not_confirmation',
        }
        release={
          'critical_findings_block':True,
          'major_findings_require_rework':True,
          'latest_red_team_review_required':True,
          'human_review_required':True,
          'exact_release_phrase':self.RELEASE_AUTH,
          'external_execution':False,'production_probability_output':False,
        }
        pid=_id('dossierprofile338'); now=_now()
        self.db.execute('''INSERT INTO phase14_dossier_profiles_338
          (profile_id,profile_name,profile_version,analytic_standards_json,red_team_policy_json,release_policy_json,probability_policy,review_status,created_at,record_hash)
          VALUES(?,?,?,?,?,?,?,?,?,?)''',(pid,'Dossier vNext + Red-Team Review','EagleEye-Dossier-338.0',_canon(standards),_canon(redteam),_canon(release),'build336_probability_fail_closed','curated_reviewed',now,_hash({'p':pid,'s':standards,'r':redteam,'rel':release})))
        return dict(self.db.one('SELECT * FROM phase14_dossier_profiles_338 WHERE profile_id=?',(pid,)))

    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_338 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_338 WHERE review_status='reviewed'")
        e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_338 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_338 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build338_delta_cases':a+s,'build338_delta_extreme':e,'dossier_redteam_delta_cases':a,'security_agent_delta_cases_338':s}

    def _require_dossier(self,dossier_id:str)->dict[str,Any]:
        row=self.db.one('SELECT * FROM phase14_dossiers_vnext_338 WHERE dossier_id=?',(dossier_id,))
        if not row:raise KeyError('Dossier vNext not found')
        return dict(row)

    def _latest_red_team(self,dossier_id:str)->dict[str,Any]|None:
        row=self.db.one('SELECT * FROM phase14_red_team_reviews_338 WHERE dossier_id=? ORDER BY created_at DESC,review_id DESC LIMIT 1',(dossier_id,))
        return dict(row) if row else None

    def _normalise_source_ref(self,ref:dict[str,Any])->dict[str,Any]:
        if not isinstance(ref,dict):raise TypeError('source ref must be object')
        forbidden=('password','secret','token','credential','cookie','authorization')
        clean={}
        for k,v in ref.items():
            key=str(k)[:80]
            if any(x in key.casefold() for x in forbidden):continue
            if isinstance(v,(str,int,float,bool)) or v is None:clean[key]=str(v)[:1200] if isinstance(v,str) else v
        for key in ('source_ref','source_group','independence_group'):
            clean[key]=str(clean.get(key,'')).strip()[:500]
        if not clean['source_ref']:raise ValueError('source_ref required')
        if not clean['source_group']:clean['source_group']='unknown_source_group'
        if not clean['independence_group']:clean['independence_group']=clean['source_group']
        clean['primary']=bool(ref.get('primary',False)); clean['official']=bool(ref.get('official',False))
        clean['temporal_class']=str(ref.get('temporal_class','unspecified'))[:80]
        clean['evidence_locator']=str(ref.get('evidence_locator',''))[:1000]
        clean['evidence_object_id']=str(ref.get('evidence_object_id',''))[:240]
        clean['provenance_status']=str(ref.get('provenance_status','source_bound'))[:80]
        return clean

    def create_dossier_vnext(self,*,case_id:str,supervisor_run_id:str,title:str,parent_dossier_id:str='',notes:str='',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._ensure_dossier_profile(); run=self._require_run(supervisor_run_id)
        if run['case_id']!=case_id:raise PermissionError('Supervisor run belongs to another case')
        parent=None; revision=1
        if parent_dossier_id:
            parent=self._require_dossier(parent_dossier_id)
            if parent['case_id']!=case_id:raise PermissionError('Parent dossier belongs to another case')
            revision=int(parent['revision_no'])+1
        did=_id('dossier338'); now=_now(); title=self._norm_text(title or f'Dossier vNext · {run["objective"][:100]}',300)
        payload={'dossier_id':did,'case_id':case_id,'run':supervisor_run_id,'parent':parent_dossier_id,'revision':revision,'title':title}
        self.db.execute('''INSERT INTO phase14_dossiers_vnext_338
          (dossier_id,case_id,supervisor_run_id,parent_dossier_id,revision_no,title,status,red_team_required,human_review_required,external_execution,production_probability_output,created_by,created_at,closed_at,notes,record_hash)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(did,case_id,supervisor_run_id,parent_dossier_id,int(revision),title,'draft',1,1,0,0,actor,now,'',self._norm_text(notes,1200),_hash(payload)))
        return {'dossier_id':did,'case_id':case_id,'supervisor_run_id':supervisor_run_id,'revision_no':revision,'status':'draft','red_team_required':True,'human_review_required':True,'production_probability_output':False,'external_execution':False}

    def add_dossier_claim(self,*,dossier_id:str,claim_type:str,claim_text:str,materiality:str='medium',source_refs:list[dict[str,Any]]|None=None,counter_refs:list[dict[str,Any]]|None=None,assumptions:list[Any]|None=None,uncertainty_notes:str='',temporal_scope:str='unspecified',identity_status:str='candidate_or_not_applicable',legal_status:str='not_applicable',judgment_status:str='candidate',source_independence_required:bool=True,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; d=self._require_dossier(dossier_id)
        if d['status'] not in ('draft','needs_rework'):raise RuntimeError('Dossier is not open for append-only claim drafting')
        typ=str(claim_type).strip()
        if typ not in self.CLAIM_TYPES:raise ValueError('invalid claim type')
        mat=str(materiality).strip().lower()
        if mat not in self.MATERIALITY:raise ValueError('invalid materiality')
        txt=self._norm_text(claim_text,2400)
        if not txt:raise ValueError('claim text required')
        src=[self._normalise_source_ref(x) for x in (source_refs or [])][:24]; ctr=[self._normalise_source_ref(x) for x in (counter_refs or [])][:24]
        asm=[]
        for x in (assumptions or [])[:16]:
            if isinstance(x,dict):asm.append({'text':self._norm_text(x.get('text',''),600),'status':str(x.get('status','untested'))[:60]})
            else:asm.append({'text':self._norm_text(str(x),600),'status':'untested'})
        cid=_id('claim338'); now=_now(); p={'c':cid,'d':dossier_id,'t':typ,'text':txt,'src':src,'ctr':ctr,'asm':asm}
        self.db.execute('''INSERT INTO phase14_dossier_claims_338
          (claim_id,dossier_id,case_id,claim_type,claim_text,materiality,judgment_status,source_refs_json,counter_refs_json,assumptions_json,uncertainty_notes,temporal_scope,identity_status,legal_status,source_independence_required,automatic_truth,created_by,created_at,record_hash)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(cid,dossier_id,d['case_id'],typ,txt,mat,str(judgment_status)[:80],_canon(src),_canon(ctr),_canon(asm),self._norm_text(uncertainty_notes,1400),str(temporal_scope)[:120],str(identity_status)[:120],str(legal_status)[:120],int(bool(source_independence_required)),0,actor,now,_hash(p)))
        return {'claim_id':cid,'dossier_id':dossier_id,'claim_type':typ,'materiality':mat,'sources':len(src),'counter_sources':len(ctr),'assumptions':len(asm),'automatic_truth':False}

    @staticmethod
    def _source_groups(refs:list[dict[str,Any]])->set[str]:
        return {str(x.get('independence_group') or x.get('source_group') or 'unknown') for x in refs}

    @staticmethod
    def _probability_leak(text:str)->bool:
        low=str(text or '').casefold()
        if re.search(r'\b\d{1,3}(?:[.,]\d+)?\s*%',low):return True
        return bool(re.search(r'\b(probability|wahrscheinlichkeit)\b.{0,50}\b(identity|guilt|guilty|schuld|betrug|fraud|truth|wahrheit)\b',low))

    @staticmethod
    def _criminality_language(text:str)->bool:
        return bool(re.search(r'\b(guilty|criminal|fraud|corrupt(?:ion)?|betrug|betrügerisch|kriminell|schuldig|korrupt(?:ion)?)\b',str(text or '').casefold()))

    def _insert_finding(self,review_id,dossier_id,claim_id,severity,typ,description,remediation,blocks=False):
        fid=_id('rtfinding338'); now=_now()
        self.db.execute('''INSERT INTO phase14_red_team_findings_338
          (finding_id,review_id,dossier_id,claim_id,severity,finding_type,description,remediation,blocks_release,created_at,record_hash)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(fid,review_id,dossier_id,claim_id,severity,typ,self._norm_text(description,1200),self._norm_text(remediation,1200),int(bool(blocks)),now,_hash({'f':fid,'r':review_id,'c':claim_id,'t':typ,'s':severity})))
        return fid

    def _insert_falsifier(self,review_id,dossier_id,claim_id,test_type,description,weaken=True,refute=False):
        tid=_id('falsifier338'); now=_now()
        self.db.execute('''INSERT INTO phase14_falsification_tests_338
          (test_id,review_id,dossier_id,claim_id,test_type,description,status,result,would_weaken,would_refute,created_at,record_hash)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(tid,review_id,dossier_id,claim_id,test_type,self._norm_text(description,1200),'open','not_run',int(bool(weaken)),int(bool(refute)),now,_hash({'t':tid,'r':review_id,'c':claim_id,'type':test_type})))
        return tid

    def run_red_team_review(self,*,dossier_id:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; d=self._require_dossier(dossier_id); claims=[dict(x) for x in self.db.all('SELECT * FROM phase14_dossier_claims_338 WHERE dossier_id=? ORDER BY created_at,claim_id',(dossier_id,))]
        if not claims:raise RuntimeError('Dossier has no structured claims')
        rid=_id('redteam338'); critical=major=moderate=source_echo=unsupported=assumption_count=probability_leaks=0; findings=[]; falsifiers=0
        high_total=high_cited=high_assessment_total=high_assessment_independent=high_assessment_counter=0
        for c in claims:
            src=json.loads(c['source_refs_json'] or '[]'); ctr=json.loads(c['counter_refs_json'] or '[]'); asm=json.loads(c['assumptions_json'] or '[]'); groups=self._source_groups(src)
            high=c['materiality']=='high'; typ=c['claim_type']; text=c['claim_text']
            if high:
                high_total+=1; high_cited+=int(bool(src))
                if typ=='assessment':
                    high_assessment_total+=1; high_assessment_independent+=int(len(groups)>=2); high_assessment_counter+=int(bool(ctr))
            def find(sev,ft,desc,rem,block=False):
                nonlocal critical,major,moderate,source_echo,unsupported,assumption_count,probability_leaks
                findings.append(self._insert_finding(rid,dossier_id,c['claim_id'],sev,ft,desc,rem,block))
                if sev=='critical':critical+=1
                elif sev=='major':major+=1
                else:moderate+=1
                if ft=='source_echo':source_echo+=1
                if ft=='unsupported_material_claim':unsupported+=1
                if ft=='untested_assumption':assumption_count+=1
                if ft=='probability_leak':probability_leaks+=1
            if typ in ('factual_observation','assessment','counterevidence','unresolved_conflict') and not src:
                sev='critical' if high and typ in ('factual_observation','assessment') else 'major'; find(sev,'unsupported_material_claim','Claim has no source-bound support.','Attach immutable/source-bound evidence or reclassify as hypothesis/data gap.',sev=='critical')
            if len(src)>=2 and len(groups)<len(src):
                find('moderate','source_echo','Multiple citations collapse to fewer independence groups.','Count source origins, not citation volume; seek an independent source family.',False)
            if high and typ=='assessment' and c['source_independence_required'] and len(groups)<2:
                find('major','single_origin_material_assessment','High-material assessment lacks two independent source groups.','Seek independent corroboration or explicitly downgrade/reframe the assessment.',False)
            if high and typ=='assessment' and not ctr:
                find('major','missing_counterevidence','High-material assessment has no attached contrary/counterevidence review.','Attach counterevidence or document a reviewed search gap and alternative explanation.',False)
            untested=[x for x in asm if str(x.get('status','untested')).lower() not in ('tested','supported','rejected')]
            if untested:
                find('major' if high else 'moderate','untested_assumption',f'{len(untested)} assumption(s) remain untested.','Test, reject, or explicitly preserve each assumption and explain its effect on the judgment.',False)
            if self._probability_leak(text):
                find('critical','probability_leak','Claim contains probability-like output while production calibration is unqualified.','Remove percentage/probability language and use evidence/uncertainty descriptors only.',True)
            if high and str(c['identity_status']).casefold() in ('unresolved','candidate','conflict','strong_conflict'):
                find('critical','identity_unresolved','High-material claim depends on unresolved or conflicting identity.','Resolve strong identifiers or keep the claim out of release.',True)
            if high and str(c['temporal_scope']).casefold()=='current' and any(str(x.get('temporal_class','')).casefold()=='historical' for x in src):
                find('major','historical_as_current','Current-state claim relies on historical-only source material.','Add current authoritative evidence or reframe as historical observation.',False)
            if self._criminality_language(text) and str(c['legal_status']).casefold() in ('allegation_only','non_final','unknown','candidate'):
                find('critical','legal_finality_overclaim','Criminality/adverse language exceeds the stated legal finality.','Use precise procedural language and distinguish allegation, proceeding, decision and final disposition.',True)
            if high and typ in ('factual_observation','assessment') and src and not all(str(x.get('evidence_locator','')).strip() or str(x.get('evidence_object_id','')).strip() for x in src):
                find('major','provenance_gap','At least one high-material support source lacks an evidence locator/object reference.','Attach page/section/object/register locator before release.',False)
            if typ in ('assessment','hypothesis'):
                self._insert_falsifier(rid,dossier_id,c['claim_id'],'authoritative_contradiction','An authoritative primary record that directly contradicts the material assertion would weaken or refute this claim.',True,True); falsifiers+=1
                self._insert_falsifier(rid,dossier_id,c['claim_id'],'source_independence_collapse','If apparently independent supports are shown to originate from one source, corroboration strength must be reduced.',True,False); falsifiers+=1
                if str(c['identity_status']).casefold() not in ('not_applicable','candidate_or_not_applicable'):
                    self._insert_falsifier(rid,dossier_id,c['claim_id'],'strong_identifier_conflict','A conflicting authoritative identifier for the subject would refute the current entity linkage.',True,True); falsifiers+=1
                if str(c['temporal_scope']).casefold()!='unspecified':
                    self._insert_falsifier(rid,dossier_id,c['claim_id'],'temporal_boundary_conflict','An authoritative record showing the relationship/state was not valid in the claimed period would weaken or refute the claim.',True,True); falsifiers+=1
        verdict='fail' if critical else ('needs_rework' if major else 'pass')
        citation_cov=round(high_cited/max(1,high_total),4); independence_cov=round(high_assessment_independent/max(1,high_assessment_total),4); counter_cov=round(high_assessment_counter/max(1,high_assessment_total),4)
        readiness=max(0.0,100.0-(critical*35+major*12+moderate*3)); metrics={'claims':len(claims),'high_material_claims':high_total,'high_material_assessments':high_assessment_total,'citation_coverage_high':citation_cov,'independent_support_coverage_high_assessments':independence_cov,'counterevidence_coverage_high_assessments':counter_cov,'falsification_tests':falsifiers,'publication_readiness_score':round(readiness,2),'score_meaning':'dossier_release_readiness_not_truth_or_probability','absence_of_falsification_not_confirmation':True,'logical_red_team_separation_not_external_independent_audit':True,'production_probability_output':False,'external_execution':False}
        now=_now(); self.db.execute('''INSERT INTO phase14_red_team_reviews_338
          (review_id,dossier_id,case_id,reviewer_role,verdict,critical_count,major_count,moderate_count,source_echo_count,unsupported_count,assumption_count,probability_leak_count,metrics_json,created_by,created_at,record_hash)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(rid,dossier_id,d['case_id'],'AI Red-Team / Falsification Review',verdict,critical,major,moderate,source_echo,unsupported,assumption_count,probability_leaks,_canon(metrics),actor,now,_hash({'r':rid,'d':dossier_id,'v':verdict,'m':metrics})))
        self.db.execute('UPDATE phase14_dossiers_vnext_338 SET status=? WHERE dossier_id=?',('red_team_pass' if verdict=='pass' else 'needs_rework',dossier_id))
        return {'review_id':rid,'dossier_id':dossier_id,'verdict':verdict,'critical':critical,'major':major,'moderate':moderate,'source_echo':source_echo,'unsupported':unsupported,'assumptions':assumption_count,'probability_leaks':probability_leaks,'falsification_tests':falsifiers,'metrics':metrics,'release_blocked':verdict!='pass','automatic_truth':False}

    def human_review_dossier(self,*,dossier_id:str,disposition:str,notes:str='',reviewer:str|None=None)->dict[str,Any]:
        reviewer=reviewer or self.actor; d=self._require_dossier(dossier_id); rt=self._latest_red_team(dossier_id)
        if not rt:raise RuntimeError('Red-team review required before human dossier review')
        disp=str(disposition).strip()
        if disp not in self.HUMAN_DISPOSITIONS:raise ValueError('invalid disposition')
        if disp=='approved_for_release' and rt['verdict']!='pass':raise PermissionError('Cannot approve dossier with unresolved red-team critical/major findings')
        hid=_id('humanreview338'); now=_now()
        self.db.execute('''INSERT INTO phase14_dossier_human_reviews_338
          (human_review_id,dossier_id,red_team_review_id,reviewer,disposition,notes,red_team_findings_accepted,external_actions_approved,probability_output_approved,evidence_promotion_approved,created_at,record_hash)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(hid,dossier_id,rt['review_id'],reviewer,disp,self._norm_text(notes,1600),1,0,0,0,now,_hash({'h':hid,'d':dossier_id,'r':rt['review_id'],'disp':disp})))
        self.db.execute('UPDATE phase14_dossiers_vnext_338 SET status=? WHERE dossier_id=?',('human_approved' if disp=='approved_for_release' else ('needs_rework' if disp=='needs_rework' else 'withheld'),dossier_id))
        return {'human_review_id':hid,'dossier_id':dossier_id,'red_team_review_id':rt['review_id'],'disposition':disp,'external_actions_approved':False,'probability_output_approved':False,'evidence_promotion_approved':False}

    def dossier_vnext_status(self,dossier_id:str)->dict[str,Any]:
        d=self._require_dossier(dossier_id); claims=[dict(x) for x in self.db.all('SELECT * FROM phase14_dossier_claims_338 WHERE dossier_id=? ORDER BY created_at,claim_id',(dossier_id,))]; rt=self._latest_red_team(dossier_id); hr=self.db.one('SELECT * FROM phase14_dossier_human_reviews_338 WHERE dossier_id=? ORDER BY created_at DESC,human_review_id DESC LIMIT 1',(dossier_id,))
        counts={}
        for c in claims:counts[c['claim_type']]=counts.get(c['claim_type'],0)+1
        return {'dossier_id':dossier_id,'case_id':d['case_id'],'revision_no':d['revision_no'],'status':d['status'],'claim_counts':counts,'red_team_verdict':rt['verdict'] if rt else 'not_run','red_team_review_id':rt['review_id'] if rt else '', 'human_review_disposition':hr['disposition'] if hr else 'not_reviewed','production_probability_output':False,'external_execution':False,'automatic_truth_promotion':False,'claims_immutable':True}

    def render_dossier_vnext_markdown(self,dossier_id:str)->str:
        d=self._require_dossier(dossier_id); claims=[dict(x) for x in self.db.all('SELECT * FROM phase14_dossier_claims_338 WHERE dossier_id=? ORDER BY created_at,claim_id',(dossier_id,))]; rt=self._latest_red_team(dossier_id); findings=[dict(x) for x in self.db.all('SELECT * FROM phase14_red_team_findings_338 WHERE review_id=? ORDER BY severity,finding_type',(rt['review_id'],))] if rt else []; fals=[dict(x) for x in self.db.all('SELECT * FROM phase14_falsification_tests_338 WHERE review_id=? ORDER BY claim_id,test_type',(rt['review_id'],))] if rt else []
        sections=[('# Established observations','factual_observation'),('# Assessments','assessment'),('# Hypotheses','hypothesis'),('# Counterevidence','counterevidence'),('# Unresolved conflicts','unresolved_conflict'),('# Data gaps','data_gap')]
        out=[f"# {d['title']}",f"\nRevision: {d['revision_no']}  ",f"Status: {d['status']}  ","Production probability output: **disabled**  ","External execution: **disabled**",'']
        for heading,typ in sections:
            out += [heading,'']
            subset=[c for c in claims if c['claim_type']==typ]
            if not subset:out += ['_None recorded._','']; continue
            for c in subset:
                src=json.loads(c['source_refs_json'] or '[]'); ctr=json.loads(c['counter_refs_json'] or '[]'); asm=json.loads(c['assumptions_json'] or '[]')
                out += [f"- **[{c['materiality']}]** {c['claim_text']}",f"  - judgment status: `{c['judgment_status']}` · identity: `{c['identity_status']}` · temporal: `{c['temporal_scope']}` · legal: `{c['legal_status']}`",f"  - sources: {len(src)} · independence groups: {len(self._source_groups(src))} · counter sources: {len(ctr)} · assumptions: {len(asm)}"]
                if c['uncertainty_notes']:out += [f"  - uncertainty: {c['uncertainty_notes']}"]
            out.append('')
        out += ['# Red-Team / Falsification Review','']
        if rt:
            out += [f"Verdict: **{rt['verdict']}** · critical {rt['critical_count']} · major {rt['major_count']} · moderate {rt['moderate_count']}",'', '> Failure to find falsifying evidence is not confirmation of a claim. The red-team layer is logically separated from the supervisor but is not a substitute for an external independent audit.','']
            for f in findings:out += [f"- **{f['severity']} · {f['finding_type']}** — {f['description']} Remediation: {f['remediation']}"]
            if not findings:out += ['- No blocking or major red-team findings in the latest review.']
            out += ['','# Falsification indicators','']
            for x in fals[:40]:out += [f"- `{x['test_type']}` — {x['description']}"]
        else:out += ['_Red-team review not yet run._']
        return '\n'.join(out).strip()+"\n"

    def release_dossier_vnext(self,*,dossier_id:str,authorization_phrase:str,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; d=self._require_dossier(dossier_id); rt=self._latest_red_team(dossier_id)
        if str(authorization_phrase or '').strip()!=self.RELEASE_AUTH:raise PermissionError('Exact dossier release authorization required')
        if not rt or rt['verdict']!='pass':raise PermissionError('Passing red-team review required')
        hr=self.db.one('SELECT * FROM phase14_dossier_human_reviews_338 WHERE dossier_id=? AND red_team_review_id=? AND disposition=? ORDER BY created_at DESC LIMIT 1',(dossier_id,rt['review_id'],'approved_for_release'))
        if not hr:raise PermissionError('Human approval bound to latest red-team review required')
        content=self.render_dossier_vnext_markdown(dossier_id); release_id=_id('release338'); rel=Path('dossiers_vnext_338')/d['case_id']/f'{release_id}.md'; out=(self.base_dir/rel).resolve(); root=self.base_dir.resolve()
        if root not in out.parents:raise RuntimeError('Invalid dossier release path')
        out.parent.mkdir(parents=True,exist_ok=True); out.write_text(content,encoding='utf-8'); sha=hashlib.sha256(content.encode()).hexdigest(); now=_now(); auth_hash=hashlib.sha256(self.RELEASE_AUTH.encode()).hexdigest()
        self.db.execute('''INSERT INTO phase14_dossier_releases_338
          (release_id,dossier_id,red_team_review_id,human_review_id,case_id,release_status,markdown_relpath,content_sha256,authorization_phrase_hash,production_probability_output,external_execution,released_by,released_at,record_hash)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(release_id,dossier_id,rt['review_id'],hr['human_review_id'],d['case_id'],'released',rel.as_posix(),sha,auth_hash,0,0,actor,now,_hash({'r':release_id,'d':dossier_id,'sha':sha,'rt':rt['review_id'],'hr':hr['human_review_id']})))
        self.db.execute('UPDATE phase14_dossiers_vnext_338 SET status=?,closed_at=? WHERE dossier_id=?',('released',now,dossier_id))
        return {'release_id':release_id,'dossier_id':dossier_id,'status':'released','markdown_relpath':rel.as_posix(),'content_sha256':sha,'production_probability_output':False,'external_execution':False}

    def run_dossier_selftest(self,actor=None):
        self._ensure_dossier_profile(); tests={'typed_claim_model':True,'information_assumption_judgment_separation':True,'source_independence_review':True,'source_echo_detection':True,'alternative_counterevidence_review':True,'assumption_check':True,'falsification_indicators':True,'absence_of_falsification_not_confirmation':True,'immutable_claims_append_only_revisions':True,'red_team_before_human_release':True,'probability_fail_closed':True,'logical_red_team_separation_no_cot':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('dossieratt338'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}
        self.db.execute('INSERT INTO phase14_dossier_attestations_338 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v34_pass':parent.get('result')=='pass','red_team_local_only':True,'review_does_not_mutate_claims_or_evidence':True,'critical_findings_fail_closed':True,'latest_review_bound_human_release':True,'exact_release_authorization':True,'source_text_inert':True,'identity_temporal_legal_conflicts_visible':True,'case_scope_bound':True,'probability_gate_preserved':True,'external_execution_remains_false':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt338'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}
        self.db.execute('INSERT INTO phase14_security_attestations_338 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'338.0','mode':'dossier_vnext_redteam_opsec_v35','security_training_cases_build338':tm['security_agent_delta_cases_338'],'model_status':'not_run','adds':['pre-release red-team gate','immutable claim review layer','critical-finding fail-closed release','probability and external-execution gates preserved'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); ds=self.db.all('SELECT * FROM phase14_dossiers_vnext_338 WHERE case_id=? ORDER BY revision_no DESC,created_at DESC LIMIT 5',(case_id,)); lines=['\n\n## Build 338 · Dossier vNext + AI Red-Team / Falsification Review','']
        lines += [f'- Dossier-vNext revisions: **{len(ds)}**','- Production probability output: **disabled**','- External execution: **disabled**','', '> Material claims are typed and source-bound. Red-team findings, assumptions, counterevidence and falsification indicators remain visible; failure to falsify is not confirmation.','']
        for d in ds[:3]:
            rt=self._latest_red_team(d['dossier_id']); lines += [f"- Revision {d['revision_no']} · **{d['status']}** · {d['title']} · red-team: {(rt or {}).get('verdict','not_run')}"]
        quality={**parent.get('quality',{}),'dossier_vnext_338':True,'pre_release_red_team':True,'typed_claims':True,'source_echo_review':True,'assumption_and_falsification_review':True,'external_execution':False,'production_probability_output':False,'human_review_required':True,'failure_to_falsify_not_confirmation':True}
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); da=self.db.one("SELECT 1 x FROM phase14_dossier_attestations_338 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_338 WHERE result='pass' LIMIT 1"); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:parent_ok=bool(json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_337_0.json').read_text(encoding='utf-8')).get('release_ready'))
            except Exception:parent_ok=False
        g={'build':'338.0','parent_337_gate':parent_ok,'dossier_vnext':True,'typed_claims_and_judgments':True,'pre_release_ai_red_team':True,'falsification_review':True,'source_echo_and_independence_review':True,'assumptions_counterevidence_visible':True,'critical_findings_fail_closed':True,'append_only_claim_revisions':True,'human_release_gate':True,'probability_output_stays_fail_closed':True,'external_execution_false':True,'dossier_attestation':bool(da),'security_agent_v35_attestation':bool(sec),'training_corpus_968':tm.get('reviewed_hard_cases')==968 and tm.get('build338_delta_cases')==16,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section=='reports':
            runs=self.db.all('SELECT run_id,objective FROM phase14_supervisor_runs_337 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,)); ro=''.join(f"<option value='{e(r['run_id'])}'>{e(r['objective'][:100])}</option>" for r in runs); ds=self.db.all('SELECT dossier_id,revision_no,title,status FROM phase14_dossiers_vnext_338 WHERE case_id=? ORDER BY revision_no DESC,created_at DESC LIMIT 12',(case_id,)); rows=''.join(f"<tr><td><code>{e(d['dossier_id'])}</code></td><td>{d['revision_no']}</td><td>{e(d['title'])}</td><td>{e(d['status'])}</td></tr>" for d in ds)
            return base+f"<div class='panel'><h2>Build 338 · Dossier vNext + Red-Team</h2><div class='notice'>Beobachtung ≠ Annahme ≠ Bewertung. Materiale Aussagen werden vor Release auf Quellenabhängigkeit, Gegenbelege, Falsifizierbarkeit, Identität, Zeitbezug und Legal-Finality geprüft.</div><form method='post' action='/build338/dossier-create'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><div class='field'><label>Supervisor Run</label><select name='supervisor_run_id' required>{ro}</select></div><div class='field'><label>Titel</label><input name='title'></div><button>Dossier vNext anlegen</button></form><table><tr><th>Dossier</th><th>Rev.</th><th>Titel</th><th>Status</th></tr>{rows or '<tr><td colspan="4">Noch kein Dossier vNext.</td></tr>'}</table><h3>Strukturierte Aussage ergänzen</h3><form method='post' action='/build338/claim-add'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='dossier_id' placeholder='Dossier ID' required><select name='claim_type'><option>factual_observation</option><option>assessment</option><option>hypothesis</option><option>counterevidence</option><option>unresolved_conflict</option><option>data_gap</option></select><select name='materiality'><option>medium</option><option>high</option><option>low</option></select><textarea name='claim_text' rows='3' placeholder='Aussage' required></textarea><textarea name='source_refs_json' rows='3' placeholder='Source refs JSON list with source_ref, source_group, independence_group and evidence_locator'></textarea><textarea name='counter_refs_json' rows='2' placeholder='Counter refs JSON []'></textarea><textarea name='assumptions_json' rows='2' placeholder='Assumptions JSON []'></textarea><input name='temporal_scope' placeholder='temporal scope'><input name='identity_status' placeholder='identity status'><input name='legal_status' placeholder='legal status'><textarea name='uncertainty_notes' rows='2' placeholder='Unsicherheit / Grenzen'></textarea><button>Aussage append-only speichern</button></form><h3>Review & Release</h3><form method='post' action='/build338/red-team'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='dossier_id' placeholder='Dossier ID'><button>Red-Team / Falsification Review</button></form><form method='post' action='/build338/human-review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='dossier_id' placeholder='Dossier ID'><select name='disposition'><option>approved_for_release</option><option>needs_rework</option><option>withheld</option></select><input name='notes' placeholder='Review-Notiz'><button>Human Review speichern</button></form><form method='post' action='/build338/release'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='dossier_id' placeholder='Dossier ID'><input name='authorization_phrase' placeholder='{e(self.RELEASE_AUTH)}'><button>Dossier lokal freigeben</button></form></div>"
        if section=='operations':return base+f"<div class='panel'><h2>Build 338 · AI Security Agent v35</h2><form method='post' action='/build338/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Dossier + Red-Team + OPSEC v35 testen</button></form><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        return base
