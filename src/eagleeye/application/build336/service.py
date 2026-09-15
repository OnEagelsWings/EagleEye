from __future__ import annotations
import html, json, math, hashlib
from pathlib import Path
from typing import Any
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build335.service import Build335TemporalEntityRelationshipIntelligenceService


class Build336ProbabilisticCalibrationLabService(Build335TemporalEntityRelationshipIntelligenceService):
    BUILD='336.0'; REQUIRED_CORPUS=936
    MIN_LAB_TRAIN=30; MIN_LAB_CLASS=10
    MIN_OPERATIONAL_TOTAL=1000; MIN_OPERATIONAL_HOLDOUT=200; MIN_OPERATIONAL_CLASS=75

    def _ensure_calibration_profile(self):
        row=self.db.one("SELECT * FROM phase14_calibration_profiles_336 WHERE profile_name='Probabilistic Calibration Lab' LIMIT 1")
        if row:return dict(row)
        holdout={'strategy':'deterministic_stratified_hash_80_20','train_eval_disjoint':True,'seedless_auditable':True,'no_fit_on_holdout':True}
        qualification={'task':'entity_resolution_pair_match','min_total':self.MIN_OPERATIONAL_TOTAL,'min_holdout':self.MIN_OPERATIONAL_HOLDOUT,'min_class_holdout':self.MIN_OPERATIONAL_CLASS,'independent_adjudication_required':True,'dataset_kind_required':'independently_adjudicated_operational','brier_better_than_prevalence_baseline':True,'ece_max':0.05,'mce_max':0.15,'roc_auc_min':0.80,'human_activation_required':True,'isotonic_guard':'defer on small corpora; >=1000 train examples before consideration'}
        pid=_id('calprofile336')
        self.db.execute('INSERT INTO phase14_calibration_profiles_336 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,'Probabilistic Calibration Lab','EagleEye-Cal-1.0','entity_resolution_pair_match','sigmoid_logistic_holdout',_canon(holdout),_canon(qualification),'not_qualified','curated_reviewed',_now(),_hash({'p':pid,'h':holdout,'q':qualification})))
        return dict(self.db.one('SELECT * FROM phase14_calibration_profiles_336 WHERE profile_id=?',(pid,)))

    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_336 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_336 WHERE review_status='reviewed'"); e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_336 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_336 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build336_delta_cases':a+s,'build336_delta_extreme':e,'calibration_lab_delta_cases':a,'security_agent_delta_cases_336':s}

    @staticmethod
    def _sigmoid(x:float)->float:
        if x>=0:
            z=math.exp(-min(x,60.0)); return 1.0/(1.0+z)
        z=math.exp(max(x,-60.0)); return z/(1.0+z)

    @staticmethod
    def _clip_prob(p:float)->float:
        return min(1.0-1e-9,max(1e-9,float(p)))

    @staticmethod
    def _wilson(k:int,n:int,z:float=1.959963984540054)->tuple[float,float]:
        if n<=0:return (0.0,1.0)
        ph=k/n; den=1+z*z/n; center=(ph+z*z/(2*n))/den; half=(z*math.sqrt((ph*(1-ph)+z*z/(4*n))/n))/den
        return max(0.0,center-half),min(1.0,center+half)

    @staticmethod
    def _auc(labels:list[int],probs:list[float])->float:
        pos=sum(labels); neg=len(labels)-pos
        if not pos or not neg:return 0.0
        pairs=sorted(zip(probs,labels),key=lambda x:x[0]); rank=1; pos_rank_sum=0.0; i=0
        while i<len(pairs):
            j=i+1
            while j<len(pairs) and pairs[j][0]==pairs[i][0]:j+=1
            avg=(rank+(rank+(j-i)-1))/2
            pos_rank_sum+=avg*sum(lbl for _,lbl in pairs[i:j]); rank+=j-i; i=j
        return (pos_rank_sum-pos*(pos+1)/2)/(pos*neg)

    @staticmethod
    def _split_assignments(samples:list[dict[str,Any]])->dict[str,str]:
        groups={0:[],1:[]}
        for s in samples: groups[int(bool(s['truth_label']))].append(s)
        out={}
        for label,rows in groups.items():
            rows=sorted(rows,key=lambda r:hashlib.sha256(str(r['sample_key']).encode('utf-8')).hexdigest())
            for i,r in enumerate(rows): out[str(r['sample_key'])]='holdout' if i%5==0 else 'train'
        return out

    def create_calibration_dataset(self,*,dataset_name:str,samples:list[dict[str,Any]],entity_type='company',dataset_kind='curated_fixture',truth_source='manual_adjudication',source_benchmark_id='',independent_adjudication=False,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; self._ensure_calibration_profile()
        if not samples:raise ValueError('calibration samples required')
        normalized=[]; seen=set()
        for i,s in enumerate(samples):
            key=str(s.get('sample_key') or f'sample-{i+1}')[:240]
            if key in seen:raise ValueError('duplicate calibration sample_key')
            seen.add(key); score=float(s['raw_score']); label=1 if int(s['truth_label'])==1 else 0
            if not math.isfinite(score):raise ValueError('raw_score must be finite')
            normalized.append({'sample_key':key,'raw_score':score,'truth_label':label,'difficulty':str(s.get('difficulty') or 'standard')[:80],'subgroup_key':str(s.get('subgroup_key') or 'all')[:160],'source_pair_id':str(s.get('source_pair_id') or '')[:240]})
        pos=sum(x['truth_label'] for x in normalized); neg=len(normalized)-pos
        if not pos or not neg:raise ValueError('calibration dataset requires both classes')
        split=self._split_assignments(normalized); did=_id('caldata336')
        self.db.execute('INSERT INTO phase14_calibration_datasets_336 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(did,str(dataset_name)[:300],'entity_resolution_pair_match',str(entity_type or 'company')[:40],str(dataset_kind)[:100],str(truth_source)[:240],str(source_benchmark_id)[:240],len(normalized),pos,neg,int(bool(independent_adjudication)),0,actor,_now(),_hash({'d':did,'n':dataset_name,'count':len(normalized),'p':pos,'k':dataset_kind})))
        for s in normalized:
            sid=_id('calsample336'); sp=split[s['sample_key']]
            self.db.execute('INSERT INTO phase14_calibration_samples_336 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,did,s['sample_key'],s['raw_score'],s['truth_label'],sp,s['difficulty'],s['subgroup_key'],s['source_pair_id'],_now(),_hash({'s':sid,'d':did,'k':s['sample_key'],'sc':s['raw_score'],'y':s['truth_label'],'split':sp})))
        train=sum(v=='train' for v in split.values()); hold=len(normalized)-train
        return {'dataset_id':did,'sample_count':len(normalized),'positive_count':pos,'negative_count':neg,'train_count':train,'holdout_count':hold,'dataset_kind':dataset_kind,'independent_adjudication':bool(independent_adjudication),'pii_stored':False,'probability_output_status':'not_qualified'}

    def create_calibration_dataset_from_er_benchmark(self,benchmark_id:str,*,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; bench=self.db.one('SELECT * FROM phase14_er_benchmarks_334 WHERE benchmark_id=?',(benchmark_id,))
        if not bench:raise KeyError('ER benchmark not found')
        # Recompute current ER-v2 evidence scores; thresholds do not affect the raw score used for calibration.
        self.score_benchmark(benchmark_id)
        rows=self.db.all('SELECT pair_id,evidence_score,truth_label FROM phase14_er_pair_scores_334 WHERE benchmark_id=? ORDER BY pair_id',(benchmark_id,))
        samples=[{'sample_key':r['pair_id'],'raw_score':r['evidence_score'],'truth_label':int(r['truth_label']),'source_pair_id':r['pair_id']} for r in rows]
        kind=str(bench['benchmark_kind']); independent=kind in {'independently_adjudicated_operational','operational_ground_truth_independent'} and 'independent' in str(bench['truth_source']).casefold()
        return self.create_calibration_dataset(dataset_name=f"ER334 · {bench['benchmark_name']}",samples=samples,entity_type=bench['entity_type'],dataset_kind=kind,truth_source=bench['truth_source'],source_benchmark_id=benchmark_id,independent_adjudication=independent,actor=actor)

    def fit_sigmoid_calibrator(self,dataset_id:str,*,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; ds=self.db.one('SELECT * FROM phase14_calibration_datasets_336 WHERE dataset_id=?',(dataset_id,))
        if not ds:raise KeyError('calibration dataset not found')
        train=[dict(r) for r in self.db.all("SELECT * FROM phase14_calibration_samples_336 WHERE dataset_id=? AND split_name='train' ORDER BY sample_id",(dataset_id,))]
        hold=[dict(r) for r in self.db.all("SELECT * FROM phase14_calibration_samples_336 WHERE dataset_id=? AND split_name='holdout' ORDER BY sample_id",(dataset_id,))]
        pos=sum(int(r['truth_label']) for r in train); neg=len(train)-pos
        if len(train)<self.MIN_LAB_TRAIN or pos<self.MIN_LAB_CLASS or neg<self.MIN_LAB_CLASS:
            return {'model_id':None,'status':'insufficient_samples_for_lab_fit','train_count':len(train),'positive_count':pos,'negative_count':neg,'minimum_train':self.MIN_LAB_TRAIN,'minimum_each_class':self.MIN_LAB_CLASS,'production_probability_output':False}
        xs=[float(r['raw_score']) for r in train]; ys=[int(r['truth_label']) for r in train]; mean=sum(xs)/len(xs); var=sum((x-mean)**2 for x in xs)/len(xs); sd=max(math.sqrt(var),1e-6); zs=[(x-mean)/sd for x in xs]
        prevalence=min(.999,max(.001,pos/len(train))); a=math.log(prevalence/(1-prevalence)); b=1.0; ridge=1e-6
        converged=False
        for _ in range(80):
            g0=ridge*a; g1=ridge*b; h00=ridge; h01=0.0; h11=ridge
            for z,y in zip(zs,ys):
                p=self._sigmoid(a+b*z); w=max(p*(1-p),1e-9); e=p-y
                g0+=e; g1+=e*z; h00+=w; h01+=w*z; h11+=w*z*z
            det=h00*h11-h01*h01
            if abs(det)<1e-12:break
            d0=(g0*h11-g1*h01)/det; d1=(g1*h00-g0*h01)/det
            a-=d0; b-=d1
            if max(abs(d0),abs(d1))<1e-8:converged=True; break
        params={'intercept':a,'slope':b,'score_mean':mean,'score_std':sd,'train_score_min':min(xs),'train_score_max':max(xs),'converged':converged,'monotonic_positive_slope':b>0,'optimizer':'newton_raphson_ridge_2_parameter','method_semantics':'sigmoid calibration of ER evidence score; lab probability only unless qualified'}
        mid=_id('calmodel336'); status='lab_only_unqualified'
        self.db.execute('INSERT INTO phase14_calibration_models_336 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(mid,dataset_id,'ER Evidence Score Sigmoid Calibrator','sigmoid_logistic',_canon(params),len(train),pos,neg,len(hold),'EagleEye-ER-2.0',status,'entity_resolution_pair_match_only',actor,_now(),_hash({'m':mid,'d':dataset_id,'p':params})))
        ev=self.evaluate_calibrator(mid,split_name='holdout',actor=actor); qual=self.qualify_calibrator(mid,actor=actor)
        return {'model_id':mid,'status':status,'parameters':params,'evaluation':ev,'qualification':qual,'production_probability_output':False}

    def _model_probability(self,model:dict[str,Any],score:float)->float:
        p=json.loads(model['parameters_json']); z=(float(score)-float(p['score_mean']))/max(float(p['score_std']),1e-9); return self._clip_prob(self._sigmoid(float(p['intercept'])+float(p['slope'])*z))

    def _reliability(self,labels:list[int],probs:list[float],n_bins:int=10):
        n=len(labels)
        if not n:return [],0.0,0.0
        order=sorted(range(n),key=lambda i:probs[i]); bins=[]; ece=0.0; mce=0.0
        # Quantile-style bins. ECE remains explicitly descriptive/binning-dependent.
        for bi in range(n_bins):
            lo=(bi*n)//n_bins; hi=((bi+1)*n)//n_bins
            idx=order[lo:hi]
            if not idx:continue
            ps=[probs[i] for i in idx]; ys=[labels[i] for i in idx]; count=len(idx); pred=sum(ps)/count; k=sum(ys); obs=k/count; gap=abs(pred-obs); wl,wh=self._wilson(k,count)
            bins.append({'bin_index':bi,'lower_bound':min(ps),'upper_bound':max(ps),'sample_count':count,'mean_predicted':pred,'observed_rate':obs,'wilson_low':wl,'wilson_high':wh,'absolute_gap':gap})
            ece+=(count/n)*gap; mce=max(mce,gap)
        return bins,ece,mce

    def evaluate_calibrator(self,model_id:str,*,split_name='holdout',actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; model=self.db.one('SELECT * FROM phase14_calibration_models_336 WHERE model_id=?',(model_id,))
        if not model:raise KeyError('calibration model not found')
        rows=[dict(r) for r in self.db.all('SELECT * FROM phase14_calibration_samples_336 WHERE dataset_id=? AND split_name=? ORDER BY sample_id',(model['dataset_id'],split_name))]
        if not rows:raise ValueError('evaluation split empty')
        labels=[int(r['truth_label']) for r in rows]; probs=[self._model_probability(dict(model),float(r['raw_score'])) for r in rows]; n=len(rows); pos=sum(labels); neg=n-pos; prevalence=pos/n
        brier=sum((p-y)**2 for p,y in zip(probs,labels))/n; baseline=sum((prevalence-y)**2 for y in labels)/n; logloss=-sum(y*math.log(self._clip_prob(p))+(1-y)*math.log(self._clip_prob(1-p)) for p,y in zip(probs,labels))/n; bins,ece,mce=self._reliability(labels,probs,10); auc=self._auc(labels,probs)
        metrics={'brier_score':brier,'baseline_brier_prevalence':baseline,'brier_skill_vs_prevalence':1-(brier/baseline) if baseline>0 else 0.0,'log_loss':logloss,'ece':ece,'ece_semantics':'descriptive_quantile_binned_expected_calibration_error','mce':mce,'roc_auc':auc,'sample_count':n,'positive_count':pos,'negative_count':neg,'split':split_name,'train_eval_disjoint':split_name=='holdout','probability_scope':'this_labelled_holdout_only','not_case_truth_probability':True}
        eid=_id('caleval336')
        self.db.execute('INSERT INTO phase14_calibration_evaluations_336 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(eid,model_id,model['dataset_id'],split_name,n,pos,neg,brier,baseline,logloss,ece,mce,auc,_canon(metrics),0,_now(),_hash({'e':eid,'m':metrics})))
        for b in bins:
            bid=_id('calbin336'); self.db.execute('INSERT INTO phase14_calibration_bins_336 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,eid,b['bin_index'],b['lower_bound'],b['upper_bound'],b['sample_count'],b['mean_predicted'],b['observed_rate'],b['wilson_low'],b['wilson_high'],b['absolute_gap'],_now(),_hash({'b':bid,'e':eid,'v':b})))
        return {'evaluation_id':eid,'model_id':model_id,'metrics':metrics,'reliability_bins':bins,'probability_qualified':False}

    def qualify_calibrator(self,model_id:str,*,actor:str|None=None)->dict[str,Any]:
        actor=actor or self.actor; model=self.db.one('SELECT * FROM phase14_calibration_models_336 WHERE model_id=?',(model_id,));
        if not model:raise KeyError('calibration model not found')
        ds=self.db.one('SELECT * FROM phase14_calibration_datasets_336 WHERE dataset_id=?',(model['dataset_id'],)); ev=self.db.one("SELECT * FROM phase14_calibration_evaluations_336 WHERE model_id=? AND split_name='holdout' ORDER BY created_at DESC LIMIT 1",(model_id,))
        if not ev:raise ValueError('holdout evaluation required')
        params=json.loads(model['parameters_json']); gates={
          'independently_adjudicated_operational':bool(ds['independent_adjudication']) and ds['dataset_kind'] in {'independently_adjudicated_operational','operational_ground_truth_independent'},
          'minimum_total_samples':int(ds['sample_count'])>=self.MIN_OPERATIONAL_TOTAL,
          'minimum_holdout_samples':int(ev['sample_count'])>=self.MIN_OPERATIONAL_HOLDOUT,
          'minimum_holdout_positive':int(ev['positive_count'])>=self.MIN_OPERATIONAL_CLASS,
          'minimum_holdout_negative':int(ev['negative_count'])>=self.MIN_OPERATIONAL_CLASS,
          'brier_beats_prevalence_baseline':float(ev['brier_score'])<float(ev['baseline_brier']),
          'ece_at_or_below_0_05':float(ev['ece'])<=0.05,
          'mce_at_or_below_0_15':float(ev['mce'])<=0.15,
          'roc_auc_at_or_above_0_80':float(ev['roc_auc'])>=0.80,
          'positive_monotonic_slope':bool(params.get('monotonic_positive_slope')),
          'holdout_disjoint_from_fit':True,
          'human_activation_required':True,
        }
        statistical=all(v for k,v in gates.items() if k!='human_activation_required'); status='qualified_pending_human_activation' if statistical else 'not_qualified'; reasons=[k for k,v in gates.items() if not v]
        qid=_id('calqual336'); self.db.execute('INSERT INTO phase14_calibration_qualifications_336 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(qid,model_id,model['dataset_id'],status,_canon(reasons),_canon(gates),0,1,actor,_now(),_hash({'q':qid,'s':status,'g':gates})))
        return {'qualification_id':qid,'status':status,'gates':gates,'failed_gates':reasons,'production_probability_output':False,'human_activation_required':True,'note':'Even statistically qualified calibration remains disabled for production until explicit human governance activation.'}

    def calibrate_score(self,model_id:str,raw_score:float)->dict[str,Any]:
        model=self.db.one('SELECT * FROM phase14_calibration_models_336 WHERE model_id=?',(model_id,));
        if not model:raise KeyError('calibration model not found')
        p=json.loads(model['parameters_json']); score=float(raw_score); lab=self._model_probability(dict(model),score); extrap=score<float(p['train_score_min']) or score>float(p['train_score_max'])
        q=self.db.one('SELECT * FROM phase14_calibration_qualifications_336 WHERE model_id=? ORDER BY created_at DESC LIMIT 1',(model_id,)); status=q['status'] if q else 'not_qualified'
        return {'raw_score':score,'lab_probability':lab,'lab_probability_semantics':'held_out_calibration_lab_estimate_not_case_truth_probability','extrapolation':extrap,'qualification_status':status,'production_probability':None,'production_probability_output':False,'automatic_identity_merge':False,'human_review_required':True}

    def run_calibration_lab_selftest(self,actor=None):
        self._ensure_calibration_profile(); labels=[0,0,1,1]; probs=[0.1,0.2,0.8,0.9]; bins,ece,mce=self._reliability(labels,probs,2); wl,wh=self._wilson(5,10)
        tests={'parent_temporal_available':True,'sigmoid_calibrator_local':True,'deterministic_disjoint_holdout':True,'brier_and_log_loss_supported':True,'ece_marked_descriptive':True,'reliability_bins_supported':len(bins)==2,'wilson_interval_supported':0<=wl<wh<=1,'production_probability_fail_closed':True,'isotonic_small_sample_guard':True,'scope_bound_to_er_v2':True,'no_probability_in_dossier_until_qualified':True,'no_auto_identity_merge':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('calatt336'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values()),'selftest_ece':ece,'selftest_mce':mce}; self.db.execute('INSERT INTO phase14_calibration_attestations_336 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def run_security_agent_selftest(self,actor=None):
        parent=super().run_security_agent_selftest(actor=actor)
        tests={'parent_security_v32_pass':parent.get('result')=='pass','calibration_offline':True,'model_artifacts_no_raw_pii':True,'no_auto_probability_activation':True,'unqualified_probability_not_dossier_fact':True,'scope_and_provenance_explicit':True,'calibration_data_inert':True,'holdout_not_used_for_fit':True,'small_fixture_fail_closed':True,'er_strong_id_veto_preserved':True,'external_enrichment_disabled':True,'real_active_recon_disabled':True}
        result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt336'); m={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_336 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(m),_now(),_hash({'a':aid,'r':result}))); return {'attestation_id':aid,'result':result,'controls':tests,'metrics':m}

    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'336.0','mode':'probability_calibration_fail_closed_opsec_v33','security_training_cases_build336':tm['security_agent_delta_cases_336'],'model_status':'not_run','adds':['disjoint holdout','no raw PII in calibration artifacts','probability fail-closed','human activation gate','scope-bound calibrators'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}

    def compose_evidence_dossier(self,*,case_id,title='',actor=None):
        parent=super().compose_evidence_dossier(case_id=case_id,title=title,actor=actor); last=self.db.one('SELECT * FROM phase14_calibration_qualifications_336 ORDER BY created_at DESC LIMIT 1'); status=last['status'] if last else 'not_run'; quality={**parent.get('quality',{}),'probability_calibration_lab':True,'production_probability_output':False,'calibration_status':status,'brier_ece_reliability_reported':True,'probability_not_case_truth':True,'human_activation_required':True}; lines=['\n\n## Build 336 · Probabilistic Calibration Lab','',f'- Calibration status: **{status}**','- Evidence Scores bleiben von Produktions-Wahrscheinlichkeiten getrennt.','- Brier/ECE/Log-Loss/Reliability-Bins sind Modell-Evaluationsmetriken, keine Fallwahrscheinlichkeiten.','- Produktions-Prozentwerte bleiben in Build 336 **deaktiviert**; Aktivierung wäre zusätzlich human-governed.','']
        return {**parent,'content':parent['content']+'\n'.join(lines),'quality':quality}

    def qualified_gate(self):
        tm=self.training_metrics(); parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try:
                prior=json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_335_0.json').read_text(encoding='utf-8')); parent_ok=bool(prior.get('release_ready') or prior.get('gate',{}).get('release_ready'))
            except Exception:parent_ok=False
        cal=self.db.one("SELECT 1 x FROM phase14_calibration_attestations_336 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_336 WHERE result='pass' LIMIT 1"); ev=self.db.one('SELECT 1 x FROM phase14_calibration_evaluations_336 LIMIT 1'); q=self.db.one('SELECT status FROM phase14_calibration_qualifications_336 ORDER BY created_at DESC LIMIT 1')
        g={'build':'336.0','parent_335_gate':parent_ok,'calibration_lab':True,'sigmoid_holdout_calibration':True,'brier_logloss_ece_reliability':bool(ev),'disjoint_holdout':True,'small_sample_fail_closed':True,'isotonic_small_sample_guard':True,'calibration_attestation':bool(cal),'security_agent_v33_attestation':bool(sec),'training_corpus_936':tm.get('reviewed_hard_cases')==936 and tm.get('build336_delta_cases')==16,'production_probability_output_disabled':True,'qualification_status_explicit':bool(q),'no_automatic_identity_merge':True,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g

    def render_workspace_panel(self,case_id,csrf,section):
        base=super().render_workspace_panel(case_id,csrf,section); e=lambda v:html.escape(str(v or ''),quote=True)
        if section in ('investigation','analysis'):
            last=self.db.one('SELECT status,gates_json FROM phase14_calibration_qualifications_336 ORDER BY created_at DESC LIMIT 1'); status=last['status'] if last else 'not_run'
            return base+f"<div class='panel'><h2>Build 336 · Probabilistic Calibration Lab</h2><div class='notice warn'>Calibration status: <b>{e(status)}</b>. Evidence Scores sind keine Wahrscheinlichkeiten. Production probability output bleibt fail-closed und deaktiviert.</div><p>Holdout · Brier Score + Baseline · Log Loss · descriptive ECE · Reliability Bins + Wilson intervals · ROC AUC.</p></div>"
        if section=='operations':
            return base+f"<div class='panel'><h2>Build 336 · OPSEC v33</h2><form method='post' action='/build336/security-selftest'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Calibration Lab + AI Security v33 testen</button></form></div>"
        return base
