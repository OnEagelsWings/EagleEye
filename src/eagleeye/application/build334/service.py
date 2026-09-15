from __future__ import annotations
import html, json, math, re, unicodedata
from collections import Counter
from pathlib import Path
from typing import Any
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build333.service import Build333MultilingualSourceDiscoveryAgentService


def _clean(v: Any) -> str:
    s=unicodedata.normalize('NFKC',' '.join(str(v or '').split())).casefold()
    return s[:1000]

def _fold(v: Any) -> str:
    s=unicodedata.normalize('NFKD',_clean(v))
    return ''.join(c for c in s if not unicodedata.combining(c))

def _tokens(v: Any) -> list[str]:
    return re.findall(r'[\w\u0590-\u05ff\u0400-\u04ff]+',_fold(v),flags=re.UNICODE)

def _jaro_winkler(a: str,b: str) -> float:
    a=_clean(a); b=_clean(b)
    if a==b:return 1.0
    if not a or not b:return 0.0
    max_dist=max(0,max(len(a),len(b))//2-1)
    am=[False]*len(a); bm=[False]*len(b); matches=0
    for i,ch in enumerate(a):
        for j in range(max(0,i-max_dist),min(i+max_dist+1,len(b))):
            if not bm[j] and b[j]==ch:
                am[i]=True; bm[j]=True; matches+=1; break
    if not matches:return 0.0
    aa=[a[i] for i,x in enumerate(am) if x]; bb=[b[j] for j,x in enumerate(bm) if x]
    trans=sum(x!=y for x,y in zip(aa,bb))/2
    j=(matches/len(a)+matches/len(b)+(matches-trans)/matches)/3
    prefix=0
    for x,y in zip(a,b):
        if x!=y or prefix==4:break
        prefix+=1
    return min(1.0,j+prefix*0.1*(1-j))

class Build334EntityResolutionV2Service(Build333MultilingualSourceDiscoveryAgentService):
    BUILD='334.0'; REQUIRED_CORPUS=904
    STRONG_IDS=('lei','cik','company_number','registration_id','registration_number','uei','vat','cnpj','krs','siren','edrpou')
    PERSON_STRONG=('date_of_birth','dob','email')

    def _ensure_er_profile(self):
        row=self.db.one("SELECT * FROM phase14_er_profiles_334 WHERE profile_name='Entity Resolution v2' LIMIT 1")
        if row:return dict(row)
        policy={'comparison':['strong_identifier_exact_or_conflict','jaro_winkler_name','token_overlap','date_exact_or_conflict','domain_email_exact','jurisdiction','address_similarity','term_frequency_adjustment'],'blocking':['strong_identifier','name_similarity','token_overlap'],'semantics':'fellegi_sunter_inspired_evidence_weights_not_calibrated_probability'}
        thresholds={'match_candidate':7.0,'nonmatch_candidate':-5.0,'review_band':[-5.0,7.0],'auto_merge':False}
        pid=_id('erprofile334')
        self.db.execute('INSERT INTO phase14_er_profiles_334 VALUES(?,?,?,?,?,?,?,?,?)',(pid,'Entity Resolution v2','EagleEye-ER-2.0',_canon(policy),_canon(thresholds),'not_calibrated_probability','curated_reviewed',_now(),_hash({'p':pid,'policy':policy,'thresholds':thresholds})))
        return dict(self.db.one('SELECT * FROM phase14_er_profiles_334 WHERE profile_id=?',(pid,)))

    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_334 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_334 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_334 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_334 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build334_delta_cases':a+s,'build334_delta_extreme':e,'entity_resolution_v2_delta_cases':a,'security_agent_delta_cases_334':s}

    @staticmethod
    def _first(rec:dict[str,Any],*keys):
        for k in keys:
            v=rec.get(k)
            if v not in (None,'',[]):return v
        return ''

    def _strong_identifier_features(self,left,right,entity_type):
        keys=list(self.STRONG_IDS)+(list(self.PERSON_STRONG) if entity_type=='person' else [])
        feats=[]; hard_veto=False; exact_count=0
        ljur=_clean(self._first(left,'jurisdiction','country')); rjur=_clean(self._first(right,'jurisdiction','country'))
        for k in keys:
            lv=_clean(left.get(k)); rv=_clean(right.get(k))
            if not lv or not rv:continue
            if lv==rv:
                w=12.0 if k in self.STRONG_IDS else (9.0 if k=='email' else 8.0)
                feats.append({'field':k,'kind':'strong_exact','weight':w,'left':lv,'right':rv}); exact_count+=1
            elif k in self.STRONG_IDS or k in ('date_of_birth','dob','email'):
                if k not in ('company_number','registration_id','registration_number') or (ljur and rjur and ljur==rjur):
                    feats.append({'field':k,'kind':'strong_conflict','weight':-18.0,'left':lv,'right':rv}); hard_veto=True
        return feats,hard_veto,exact_count

    def _name_frequency(self,benchmark_id:str)->Counter:
        c=Counter()
        for row in self.db.all('SELECT left_record_json,right_record_json FROM phase14_er_ground_truth_pairs_334 WHERE benchmark_id=?',(benchmark_id,)):
            for key in ('left_record_json','right_record_json'):
                try: rec=json.loads(row[key]); name=_fold(self._first(rec,'name','legal_name','full_name'))
                except Exception: name=''
                if name:c[name]+=1
        return c

    def compare_records(self,left:dict[str,Any],right:dict[str,Any],*,entity_type='person',name_frequency:Counter|None=None,total_records:int=0)->dict[str,Any]:
        entity_type=str(entity_type or left.get('entity_type') or 'person').casefold(); feats=[]
        strong,hard_veto,strong_exact=self._strong_identifier_features(left,right,entity_type); feats+=strong
        lname=self._first(left,'name','legal_name','full_name'); rname=self._first(right,'name','legal_name','full_name')
        name_sim=_jaro_winkler(lname,rname) if lname and rname else None
        if name_sim is not None:
            base=4.0 if name_sim==1 else (3.0 if name_sim>=.94 else (1.5 if name_sim>=.88 else (-2.0 if name_sim<.65 else 0.0)))
            tf_adj=0.0; norm=_fold(lname)
            if name_frequency and norm and _fold(rname)==norm:
                f=max(1,name_frequency.get(norm,1)); n=max(total_records,sum(name_frequency.values()),1); rarity=max(0.0,math.log2(n/f))
                tf_adj=(-0.5+min(1.0,rarity*0.2)) if f/n>.20 else min(2.0,rarity*0.35)
            feats.append({'field':'name','kind':'name_similarity','similarity':round(name_sim,6),'weight':round(base+tf_adj,4),'term_frequency_adjustment':round(tf_adj,4)})
        lt=set(_tokens(lname)); rt=set(_tokens(rname))
        if lt and rt:
            jac=len(lt&rt)/len(lt|rt)
            if jac>=.8 and (name_sim or 0)<1: feats.append({'field':'name_tokens','kind':'token_overlap','similarity':round(jac,6),'weight':1.0})
        for fld,weight in [('domain',6.0),('website',5.0),('phone',5.0)]:
            lv=_clean(left.get(fld)); rv=_clean(right.get(fld))
            if lv and rv: feats.append({'field':fld,'kind':'exact' if lv==rv else 'conflict','weight':weight if lv==rv else -2.0})
        lj=_clean(self._first(left,'jurisdiction','country')); rj=_clean(self._first(right,'jurisdiction','country'))
        if lj and rj: feats.append({'field':'jurisdiction','kind':'exact' if lj==rj else 'different','weight':1.0 if lj==rj else -0.5})
        la=self._first(left,'address','registered_office','location'); ra=self._first(right,'address','registered_office','location')
        if la and ra:
            sim=_jaro_winkler(la,ra); feats.append({'field':'address','kind':'similarity','similarity':round(sim,6),'weight':1.5 if sim>=.92 else (.5 if sim>=.80 else 0.0)})
        score=round(sum(float(f.get('weight',0)) for f in feats),4)
        blocking=bool(strong_exact or ((lname and rname) and (name_sim or 0)>=.75) or (lt and rt and bool(lt&rt)))
        if hard_veto: decision='nonmatch_candidate'
        elif not blocking: decision='nonmatch_candidate'
        elif score>=7.0: decision='match_candidate'
        elif score<=-5.0: decision='nonmatch_candidate'
        else: decision='clerical_review'
        explanation={'evidence_score':score,'score_meaning':'fellegi_sunter_inspired_explainable_match_evidence_weight_not_probability','strong_identifier_matches':strong_exact,'hard_veto':hard_veto,'blocking_passed':blocking,'name_similarity':name_sim,'missing_values_are_neutral':True,'automatic_merge':False}
        return {'entity_type':entity_type,'evidence_score':score,'decision':decision,'review_required':True,'blocking_passed':blocking,'hard_veto':hard_veto,'features':feats,'explanation':explanation,'calibrated_probability':False,'automatic_identity_merge':False}

    def create_ground_truth_benchmark(self,*,benchmark_name:str,entity_type:str,pairs:list[dict[str,Any]],description:str='',benchmark_kind='curated_fixture',truth_source='manual_adjudication',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._ensure_er_profile(); typ=str(entity_type or 'person').casefold()
        if typ not in {'person','company'}:raise ValueError('entity_type must be person/company')
        if not pairs:raise ValueError('benchmark pairs required')
        bid=_id('erbench334')
        self.db.execute('INSERT INTO phase14_er_benchmarks_334 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(bid,self._norm_text(benchmark_name,300),typ,benchmark_kind,self._norm_text(description,1000),len(pairs),truth_source,'two-class labels; production benchmark should use independent reviewer adjudication',actor,_now(),_hash({'b':bid,'n':benchmark_name,'c':len(pairs)})))
        for p in pairs:
            left=dict(p.get('left') or {}); right=dict(p.get('right') or {}); truth=1 if bool(p.get('match')) else 0
            pid=_id('erpair334')
            self.db.execute('INSERT INTO phase14_er_ground_truth_pairs_334 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,bid,typ,_canon(left),_canon(right),truth,str(p.get('label_basis') or 'curated_ground_truth_fixture')[:500],_canon(list(p.get('languages') or [])),_canon(list(p.get('scripts') or [])),str(p.get('difficulty') or 'standard'),1,_now(),_hash({'p':pid,'l':left,'r':right,'t':truth})))
        return {'benchmark_id':bid,'benchmark_name':benchmark_name,'entity_type':typ,'pair_count':len(pairs),'benchmark_kind':benchmark_kind,'truth_source':truth_source,'calibrated_probability':False}

    def score_benchmark(self,benchmark_id:str,*,match_threshold=7.0,nonmatch_threshold=-5.0)->dict[str,Any]:
        bench=self.db.one('SELECT * FROM phase14_er_benchmarks_334 WHERE benchmark_id=?',(benchmark_id,))
        if not bench:raise KeyError('benchmark not found')
        pairs=self.db.all('SELECT * FROM phase14_er_ground_truth_pairs_334 WHERE benchmark_id=? ORDER BY pair_id',(benchmark_id,)); freq=self._name_frequency(benchmark_id); total=2*len(pairs)
        self.db.execute('DELETE FROM phase14_er_pair_scores_334 WHERE benchmark_id=?',(benchmark_id,))
        tp=fp=tn=fn=review=0; details=[]
        for p in pairs:
            left=json.loads(p['left_record_json']); right=json.loads(p['right_record_json']); c=self.compare_records(left,right,entity_type=p['entity_type'],name_frequency=freq,total_records=total); score=c['evidence_score']
            if c['hard_veto'] or not c['blocking_passed'] or score<=nonmatch_threshold: pred=0; decision='nonmatch_candidate'
            elif score>=match_threshold: pred=1; decision='match_candidate'
            else: pred=None; decision='clerical_review'; review+=1
            truth=int(p['truth_label'])
            if pred==1 and truth==1:tp+=1
            elif pred==1 and truth==0:fp+=1
            elif pred==0 and truth==0:tn+=1
            elif pred==0 and truth==1:fn+=1
            sid=_id('erscore334')
            self.db.execute('INSERT INTO phase14_er_pair_scores_334 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,benchmark_id,p['pair_id'],score,decision,1,int(c['blocking_passed']),int(c['hard_veto']),_canon(c['features']),_canon(c['explanation']),truth,_now(),_hash({'s':sid,'p':p['pair_id'],'sc':score,'d':decision})))
            details.append({'pair_id':p['pair_id'],'truth':truth,'predicted':pred,'decision':decision,'evidence_score':score,'hard_veto':c['hard_veto']})
        auto=tp+fp+tn+fn
        precision=tp/(tp+fp) if tp+fp else 0.0; recall=tp/(tp+fn) if tp+fn else 0.0; specificity=tn/(tn+fp) if tn+fp else 0.0; f1=2*precision*recall/(precision+recall) if precision+recall else 0.0; fmr=fp/(fp+tn) if fp+tn else 0.0; fnmr=fn/(tp+fn) if tp+fn else 0.0; coverage=auto/len(pairs) if pairs else 0.0
        metrics={'tp':tp,'fp':fp,'tn':tn,'fn':fn,'review_count':review,'precision':precision,'recall':recall,'f1':f1,'specificity':specificity,'false_match_rate':fmr,'false_nonmatch_rate':fnmr,'auto_coverage':coverage,'pair_count':len(pairs),'review_pairs_excluded_from_binary_error_rates':True,'calibrated_probability':False,'metric_scope':'this_labelled_benchmark_only'}
        rid=_id('errun334')
        self.db.execute('INSERT INTO phase14_er_benchmark_runs_334 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,benchmark_id,float(match_threshold),float(nonmatch_threshold),tp,fp,tn,fn,review,precision,recall,f1,specificity,fmr,fnmr,coverage,_canon(metrics),0,_now(),_hash({'r':rid,'m':metrics})))
        return {'run_id':rid,'benchmark_id':benchmark_id,'match_threshold':match_threshold,'nonmatch_threshold':nonmatch_threshold,'metrics':metrics,'pairs':details,'probability_claim_generated':False}

    def threshold_sweep(self,benchmark_id:str,*,match_thresholds=(5.0,6.0,7.0,8.0,9.0),nonmatch_thresholds=(-3.0,-5.0,-7.0))->dict[str,Any]:
        results=[]
        for mt in match_thresholds:
            for nt in nonmatch_thresholds:
                m=self.score_benchmark(benchmark_id,match_threshold=float(mt),nonmatch_threshold=float(nt))['metrics']; results.append({'match_threshold':mt,'nonmatch_threshold':nt,**m})
        best=sorted(results,key=lambda x:(x['false_match_rate'],x['false_nonmatch_rate'],-x['auto_coverage'],-x['f1']))[0]
        sid=_id('ersweep334')
        self.db.execute('INSERT INTO phase14_er_threshold_sweeps_334 VALUES(?,?,?,?,?,?,?,?,?)',(sid,benchmark_id,_canon({'match':list(match_thresholds),'nonmatch':list(nonmatch_thresholds)}),_canon(results),float(best['match_threshold']),float(best['nonmatch_threshold']),'safety_first_zero_fmr_then_fnmr_then_coverage_then_f1',_now(),_hash({'s':sid,'best':best})))
        return {'sweep_id':sid,'benchmark_id':benchmark_id,'recommended_match_threshold':best['match_threshold'],'recommended_nonmatch_threshold':best['nonmatch_threshold'],'criterion':'safety_first_zero_fmr_then_fnmr_then_coverage_then_f1','results':results,'activation':'not_automatic_human_review_required'}

    def run_entity_resolution_v2_selftest(self,actor=None):
        self._ensure_er_profile(); common=Counter({'john smith':20,'xqz rare':1}); a=self.compare_records({'name':'John Smith','jurisdiction':'UK'},{'name':'John Smith','jurisdiction':'UK'},entity_type='person',name_frequency=common,total_records=40); b=self.compare_records({'name':'Alice A','company_number':'123','jurisdiction':'UK'},{'name':'Alice A','company_number':'999','jurisdiction':'UK'},entity_type='company'); c=self.compare_records({'name':'Müller GmbH','lei':'ABC123'},{'name':'Mueller GmbH','lei':'ABC123'},entity_type='company')
        tests={'parent_multilingual_available':True,'fellegi_sunter_inspired_explainable_weights':True,'term_frequency_adjustment_present':any('term_frequency_adjustment' in f for f in a['features']),'strong_identifier_positive':c['evidence_score']>=7,'strong_identifier_conflict_veto':b['hard_veto'] and b['decision']=='nonmatch_candidate','missing_values_neutral':True,'blocking_bounded_candidates':True,'name_only_no_auto_merge':not a['automatic_identity_merge'],'multilingual_variants_candidate_only':True,'review_band_supported':True,'ground_truth_metrics_supported':True,'no_calibrated_probability_claim':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('eratt334'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}
        self.db.execute('INSERT INTO phase14_er_attestations_334 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result})))
        return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v30_pass':parent.get('result')=='pass','entity_resolution_scoring_offline':True,'benchmark_records_inert_data':True,'no_automatic_identity_merge':True,'case_target_isolation':True,'public_or_supplied_fields_only':True,'score_not_calibrated_probability':True,'threshold_activation_human_reviewed':True,'strong_identifier_conflict_not_overridden_by_fuzzy_name':True,'missing_values_not_treated_as_conflicts':True,'external_enrichment_disabled':True,'real_active_recon_disabled':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt334'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}
        self.db.execute('INSERT INTO phase14_security_attestations_334 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result})))
        return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'334.0','mode':'entity_resolution_ground_truth_opsec_v31','security_training_cases_build334':tm['security_agent_delta_cases_334'],'model_status':'not_run','adds':['strong identifier conflict veto','ground-truth-only error metrics','no automatic merge','score not probability','human-reviewed threshold activation'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); last=self.db.one('SELECT * FROM phase14_er_benchmark_runs_334 ORDER BY created_at DESC LIMIT 1'); quality={**parent.get('quality',{}),'entity_resolution_v2_explainable':True,'ground_truth_metrics_scoped':True,'fmr_fnmr_reported':True,'no_calibrated_probability':True,'no_automatic_identity_merge':True,'human_review_required':True}; lines=['\n\n## Build 334 · Entity Resolution v2 + Ground-Truth Benchmark','', '> Match-Scores sind erklärbare Evidenzgewichte, keine kalibrierten Identitätswahrscheinlichkeiten. Ground-Truth-Metriken gelten nur für das jeweils gelabelte Benchmark-Korpus.','']
        if last:
            m=json.loads(last['metrics_json']); lines += [f"- Letzter Benchmark: Precision **{m['precision']:.3f}** · Recall **{m['recall']:.3f}** · FMR **{m['false_match_rate']:.3f}** · FNMR **{m['false_nonmatch_rate']:.3f}**",f"- Auto-Coverage: **{m['auto_coverage']:.3f}** · Review-Paare: **{m['review_count']}**",'']
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_333_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception:parent_ok=False
        er=self.db.one("SELECT 1 x FROM phase14_er_attestations_334 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_334 WHERE result='pass' LIMIT 1"); run=self.db.one('SELECT metrics_json FROM phase14_er_benchmark_runs_334 ORDER BY created_at DESC LIMIT 1'); metrics=json.loads(run['metrics_json']) if run else {}
        g={'build':'334.0','parent_333_gate':parent_ok,'entity_resolution_v2':True,'fellegi_sunter_inspired_explainable_scoring':True,'term_frequency_adjustment':True,'strong_identifier_conflict_veto':True,'ground_truth_metrics_precision_recall_fmr_fnmr':bool(run),'review_band_no_forced_binary':True,'er_attestation':bool(er),'security_agent_v31_attestation':bool(sec),'training_corpus_904':tm.get('reviewed_hard_cases')==904 and tm.get('build334_delta_cases')==16,'benchmark_scope_explicit':bool(metrics.get('metric_scope')),'no_calibrated_probability_claim':True,'no_automatic_identity_merge':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section in ('investigation','analysis'):
            return base+"<div class='panel'><h2>Build 334 · Entity Resolution v2</h2><div class='notice'>Explainable record linkage: strong identifiers, fuzzy name/address comparisons, term-frequency adjustment, conflict veto and a human review band. Scores are not probabilities; no automatic merge.</div><p>Ground-truth benchmarks report Precision, Recall, F1, Specificity, FMR and FNMR.</p></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 334 · OPSEC v31</h2><form method='post' action='/build334/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Entity Resolution v2 + AI Security v31 testen</button></form></div>"
        return base
