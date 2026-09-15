from __future__ import annotations
import hashlib, html, json, math, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _id(p): return f'{p}_{uuid.uuid4().hex[:12]}'
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v): return hashlib.sha256((_canon(v) if not isinstance(v,str) else v).encode('utf-8')).hexdigest()
def _safe(v,d):
    try:return json.loads(v) if isinstance(v,str) else (v if v is not None else d)
    except Exception:return d

def _clip(v,n=280):
    s=' '.join(str(v or '').split())
    return s[:n] + ('…' if len(s)>n else '')

def _ver(s:str):
    try:return tuple(int(x) for x in str(s).split('.')[:2])
    except Exception:return (0,0)

class Build292CrossSurfaceFusionService:
    BUILD='292.0'; GATE_THRESHOLD=0.85
    SURFACE_TARGET=6
    def __init__(self,db:Any,audit:Any,*,build291:Any,build290:Any,build289:Any,build288:Any,build281:Any,base_dir:Path,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.build291=build291; self.build290=build290; self.build289=build289; self.build288=build288; self.build281=build281; self.base_dir=Path(base_dir); self.actor=actor

    def _table(self,name:str)->bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?",(name,)))
    def _mission(self,case_id:str,mission_id:str=''):
        if mission_id: row=self.db.one('SELECT * FROM phase12_missions_281 WHERE case_id=? AND mission_id=?',(case_id,mission_id))
        else: row=self.db.one('SELECT * FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        if not row: raise ValueError('Für den Fall existiert noch keine Phase-12-Mission.')
        return row
    def _round(self,case_id:str,mission_id:str,round_id:str='',actor:str=''):
        if round_id: r=self.db.one('SELECT * FROM phase12_adaptive_rounds_291 WHERE case_id=? AND round_id=?',(case_id,round_id))
        else: r=self.db.one('SELECT * FROM phase12_adaptive_rounds_291 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        if not r:
            self.build291.create_adaptive_round(case_id=case_id,mission_id=mission_id,actor=actor or self.actor)
            r=self.db.one('SELECT * FROM phase12_adaptive_rounds_291 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        return r

    def _item(self,surface,source_ref,item_class,excerpt,prov,review,stance,uncertainty,ind=1.0):
        prov=max(0.0,min(1.0,float(prov))); review=max(0.0,min(1.0,float(review))); ind=max(0.1,min(1.0,float(ind)))
        contribution=round(prov*review*ind,4)
        return {'surface':surface,'source_ref':str(source_ref or ''),'item_class':item_class,'excerpt':_clip(excerpt),'provenance_quality':round(prov,4),'review_quality':round(review,4),'independence_weight':round(ind,4),'stance':stance,'contribution':contribution,'uncertainty':uncertainty}

    def collect_case_surfaces(self,case_id:str,round_id:str=''):
        items=[]
        # Evidence Vault: accepted/reviewed material only; decision is about evidence usability, not truth.
        if self._table('evidence_vault_items_239'):
            rows=self.db.all("SELECT v.vault_item_id,v.source_key,v.source_url,v.original_filename,v.acquisition_method,r.decision,r.evidence_quality,r.rationale FROM evidence_vault_items_239 v LEFT JOIN evidence_reviews_239 r ON r.vault_item_id=v.vault_item_id WHERE v.case_id=? ORDER BY v.created_at DESC LIMIT 12",(case_id,))
            for r in rows:
                reviewed=r['decision'] or 'unreviewed'; q=float(r['evidence_quality'] or 0.35) if r['decision'] else 0.35
                stance='corroborative' if reviewed=='accepted' else 'unresolved'
                items.append(self._item('evidence_vault',r['vault_item_id'],'vault_evidence',r['original_filename'] or r['source_url'] or r['source_key'],0.9,q,stance,'Evidence acceptance does not by itself prove a claim.'))
        # Verified claims: only this surface can contribute direct hypothesis-support/contradiction signals.
        if self._table('verified_claims_229'):
            for r in self.db.all('SELECT * FROM verified_claims_229 WHERE case_id=? ORDER BY updated_at DESC LIMIT 12',(case_id,)):
                sup=int(r['independent_support_count'] or 0); con=int(r['independent_contradiction_count'] or 0); score=float(r['verification_score'] or r['confidence'] or 0.0)
                if con>sup and con>0: stance='contradictory'
                elif sup>con and sup>0 and score>=0.55: stance='corroborative'
                else: stance='unresolved'
                ind=min(1.0,0.45+0.12*(sup+con))
                items.append(self._item('claims',r['verified_claim_id'],r['claim_kind'] or 'claim',r['claim_text'],0.85,max(0.25,score),stance,'Claim remains provisional unless human-reviewed and independently corroborated.',ind))
        # Documents: document existence/provenance is useful, content remains unresolved unless separately reviewed.
        if self._table('document_candidates_273'):
            for r in self.db.all('SELECT document_id,title,url,document_type,source_class,status,translated_summary_de FROM document_candidates_273 WHERE case_id=? ORDER BY created_at DESC LIMIT 12',(case_id,)):
                review=0.65 if str(r['status']).lower() in ('reviewed','accepted','verified') else 0.45
                items.append(self._item('documents',r['document_id'],r['document_type'] or 'document',r['translated_summary_de'] or r['title'] or r['url'],0.82,review,'unresolved','Document metadata/content must be tied to a specific claim before it becomes corroborative evidence.'))
        # Timeline: explicit conflicts reduce synthesis readiness; consistent events are not causality proof.
        if self._table('timeline_briefs_265'):
            for r in self.db.all('SELECT * FROM timeline_briefs_265 WHERE case_id=? ORDER BY created_at DESC LIMIT 6',(case_id,)):
                conflicts=_safe(r['conflicts_json'],[]); consistent=_safe(r['consistent_events_json'],[]); unresolved=_safe(r['unresolved_json'],[])
                stance='contradictory' if conflicts else ('corroborative' if consistent and not unresolved else 'unresolved')
                review=0.72 if str(r['status']).lower() in ('reviewed','accepted','qualified') else 0.55
                items.append(self._item('timeline',r['brief_id'],'timeline_brief',r['summary'],0.78,review,stance,'Temporal consistency is not causality; unresolved date precision remains explicit.'))
        # Identity resolution: comparisons carry uncertainty; no automatic merge.
        if self._table('identity_comparisons_212'):
            for r in self.db.all('SELECT * FROM identity_comparisons_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 8',(case_id,)):
                hard=_safe(r['hard_conflicts_json'],[]); prob=float(r['probability'] or 0.0); state=str(r['candidate_state'] or '')
                stance='contradictory' if hard else ('corroborative' if prob>=0.85 and state in ('match_candidate','same_candidate','reviewed_match') else 'unresolved')
                items.append(self._item('identity',r['comparison_id'],'identity_comparison',f"Identity comparison: state={state}; probability={prob:.2f}; hard_conflicts={len(hard)}",0.82,min(0.85,max(0.35,prob)),stance,'Identity scores are candidate assessments; automatic merge remains disabled.'))
        elif self._table('identity_records_212'):
            for r in self.db.all('SELECT * FROM identity_records_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 8',(case_id,)):
                items.append(self._item('identity',r['record_id'],'identity_record',r['record_ref'] or r['source_ref'],float(r['source_reliability'] or 0.5),0.45,'unresolved','Single identity records do not establish that two records refer to the same person.'))
        # Controlled capture: strong provenance, but content is still an observation pending claim linkage/review.
        if self._table('phase12_capture_snapshots_288'):
            for r in self.db.all('SELECT * FROM phase12_capture_snapshots_288 WHERE case_id=? ORDER BY created_at DESC LIMIT 10',(case_id,)):
                items.append(self._item('capture',r['snapshot_id'],'capture_snapshot',r['canonical_text'],0.92,0.50,'unresolved','Capture proves what was observed in the snapshot, not the truth of the observed statement.'))
        # Dark-web intake: deliberately lower default review weight and never auto-promoted.
        if self._table('darkweb_artifacts_281'):
            for r in self.db.all('SELECT * FROM darkweb_artifacts_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 10',(case_id,)):
                rq=0.42 if str(r['review_status']).lower() in ('reviewed','accepted') else 0.25
                items.append(self._item('darkweb_intake',r['artifact_id'],r['locator_class'],r['title']+': '+r['observed_text'],0.70,rq,'unresolved','Investigator-supplied dark-web material is a lead, not identity or factual proof.'))
        # Adaptive AI outcomes: AI analysis is never counted as independent factual evidence.
        if self._table('phase12_adaptive_outcomes_291'):
            q='SELECT o.*,t.question FROM phase12_adaptive_outcomes_291 o JOIN phase12_adaptive_tasks_291 t ON t.adaptive_task_id=o.adaptive_task_id WHERE t.case_id=?'
            args=[case_id]
            if round_id: q+=' AND o.round_id=?'; args.append(round_id)
            q+=' ORDER BY o.created_at DESC LIMIT 12'
            for r in self.db.all(q,tuple(args)):
                items.append(self._item('ai_analysis',r['outcome_id'],r['outcome_class'],r['question'],0.55,0.35,'unresolved','AI-generated analysis is a review candidate and is not independent evidence.',0.35))
        # Deduplicate by (surface, source_ref); repeated references do not multiply independence.
        seen=set(); out=[]
        for x in items:
            key=(x['surface'],x['source_ref'])
            if key in seen: continue
            seen.add(key); out.append(x)
        return out[:64]

    def _calibrate(self,items:list[dict]):
        surfaces=sorted({x['surface'] for x in items}); counts={s:sum(1 for x in items if x['surface']==s) for s in surfaces}
        # Downweight repeated items within a surface to prevent volume from impersonating independence.
        by_surface={}
        adjusted=[]
        for x in items:
            n=by_surface.get(x['surface'],0); by_surface[x['surface']]=n+1
            y=dict(x); y['independence_weight']=round(max(0.25,x['independence_weight']*(0.78**n)),4); y['contribution']=round(y['provenance_quality']*y['review_quality']*y['independence_weight'],4); adjusted.append(y)
        support=sum(x['contribution'] for x in adjusted if x['stance']=='corroborative')
        contradict=sum(x['contribution'] for x in adjusted if x['stance']=='contradictory')
        unresolved=sum(x['contribution'] for x in adjusted if x['stance']=='unresolved')
        total=support+contradict+unresolved
        coverage=min(1.0,len(surfaces)/self.SURFACE_TARGET)
        independent_refs=len({(x['surface'],x['source_ref']) for x in adjusted})
        independence=min(1.0,(len(surfaces)/max(1,self.SURFACE_TARGET))*0.65 + min(1.0,independent_refs/max(4,len(adjusted)))*0.35)
        reviewed=sum(1 for x in adjusted if x['review_quality']>=0.6)/max(1,len(adjusted))
        contradiction_ratio=contradict/max(total,1e-9); unresolved_ratio=unresolved/max(total,1e-9)
        raw=0.18 + 0.24*coverage + 0.22*independence + 0.18*reviewed + 0.18*(support/max(total,1e-9)) - 0.32*contradiction_ratio - 0.16*unresolved_ratio
        calibrated=max(0.05,min(0.82,raw))
        if len(surfaces)<2: calibrated=min(calibrated,0.34)
        if contradiction_ratio>=0.25: calibrated=min(calibrated,0.49)
        if calibrated<0.35: band='insufficient'
        elif calibrated<0.50: band='low'
        elif calibrated<0.65: band='moderate'
        else: band='guarded_high'
        notes=[
          'This is working confidence in the current cross-surface synthesis, not probability that a hypothesis is true.',
          f'{len(surfaces)} distinct evidence surfaces contributed; repeated items within a surface were downweighted.',
          'Dark-web intake and AI analysis are never auto-promoted to independent verified evidence.',
          'Contradictions and unresolved items reduce the calibrated score and remain visible for review.',
        ]
        return adjusted,counts,{'support':support,'contradict':contradict,'unresolved':unresolved,'coverage':coverage,'independence':independence,'reviewed_fraction':reviewed,'contradiction_ratio':contradiction_ratio,'unresolved_ratio':unresolved_ratio,'raw':raw,'calibrated':calibrated,'band':band,'notes':notes}

    def create_fusion(self,*,case_id:str,mission_id:str='',round_id:str='',actor:str|None=None):
        actor=actor or self.actor; m=self._mission(case_id,mission_id); r=self._round(case_id,m['mission_id'],round_id,actor)
        raw=self.collect_case_surfaces(case_id,r['round_id']); items,counts,cal=self._calibrate(raw); surfaces=sorted(counts)
        fid=_id('fusion292'); created=_now(); state={'case_id':case_id,'mission_id':m['mission_id'],'round_id':r['round_id'],'items':[{k:x[k] for k in ('surface','source_ref','stance','contribution')} for x in items]}; state_hash=_hash(state)
        payload={'fusion_id':fid,'case_id':case_id,'mission_id':m['mission_id'],'source_round_id':r['round_id'],'surfaces':surfaces,'surface_counts':counts,'support_score':cal['support'],'contradict_score':cal['contradict'],'unresolved_score':cal['unresolved'],'independence_score':cal['independence'],'coverage_score':cal['coverage'],'confidence_score':cal['calibrated'],'confidence_band':cal['band'],'contradiction_count':sum(1 for x in items if x['stance']=='contradictory'),'human_review_required':True,'status':'checkpoint_required','created_by':actor,'created_at':created,'state_sha256':state_hash}
        self.db.execute('INSERT INTO phase12_fusion_runs_292 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(fid,case_id,m['mission_id'],r['round_id'],_canon(surfaces),_canon(counts),_canon(items),cal['support'],cal['contradict'],cal['unresolved'],cal['independence'],cal['coverage'],cal['calibrated'],cal['band'],payload['contradiction_count'],1,'checkpoint_required',actor,created,state_hash,_hash(payload)))
        for x in items:
            iid=_id('fitem292'); ip={'item_id':iid,'fusion_id':fid,'case_id':case_id,**x,'created_at':created}
            self.db.execute('INSERT INTO phase12_fusion_items_292 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(iid,fid,case_id,x['surface'],x['source_ref'],x['item_class'],x['excerpt'],x['provenance_quality'],x['review_quality'],x['independence_weight'],x['stance'],x['contribution'],x['uncertainty'],created,_hash(ip)))
        cid=_id('cal292'); cp={'calibration_id':cid,'fusion_id':fid,'case_id':case_id,'raw_confidence':cal['raw'],'calibrated_confidence':cal['calibrated'],'confidence_band':cal['band'],'coverage_score':cal['coverage'],'independence_score':cal['independence'],'contradiction_penalty':cal['contradiction_ratio'],'notes':cal['notes'],'automatic_truth_selection':False,'human_review_required':True,'created_at':created}
        self.db.execute('INSERT INTO phase12_confidence_calibrations_292 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,fid,case_id,cal['raw'],cal['calibrated'],cal['band'],cal['coverage'],cal['independence'],cal['contradiction_ratio'],_canon(cal['notes']),0,1,created,_hash(cp)))
        checkpoint=self._create_checkpoint(fid,case_id,m['mission_id'],1,'surface_review',f'{len(items)} Beiträge aus {len(surfaces)} Datenoberflächen wurden provenance-erhaltend zusammengeführt.',"Quellenmix, Herkunft und Widersprüche prüfen; anschließend mit 'OK' zum Confidence-Checkpoint wechseln.",actor)
        return {**payload,'items':items,'calibration':cal,'checkpoint':checkpoint,'automatic_truth_selection':False,'network_access':False,'external_collection_started':False}

    def _create_checkpoint(self,fusion_id,case_id,mission_id,stage_no,stage,summary,next_action,actor):
        ex=self.db.one('SELECT * FROM phase12_investigator_checkpoints_292 WHERE fusion_id=? AND stage_no=?',(fusion_id,stage_no))
        if ex:return dict(ex)
        cid=_id('checkpoint292'); created=_now(); payload={'checkpoint_id':cid,'fusion_id':fusion_id,'case_id':case_id,'mission_id':mission_id,'stage_no':stage_no,'stage':stage,'status':'awaiting_ok','summary':summary,'next_action':next_action,'requires_ok':True,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO phase12_investigator_checkpoints_292 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(cid,fusion_id,case_id,mission_id,stage_no,stage,'awaiting_ok',summary,next_action,1,actor,created,_hash(payload)))
        return payload

    def approve_checkpoint(self,*,checkpoint_id:str,confirmation:str,approved_by:str):
        if confirmation.strip().upper()!='OK': raise PermissionError("Checkpoint-Freigabe benötigt ausdrücklich 'OK'.")
        cp=self.db.one('SELECT * FROM phase12_investigator_checkpoints_292 WHERE checkpoint_id=?',(checkpoint_id,))
        if not cp: raise KeyError('checkpoint not found')
        ex=self.db.one("SELECT * FROM phase12_checkpoint_approvals_292 WHERE checkpoint_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(checkpoint_id,))
        if ex:return {'checkpoint_id':checkpoint_id,'approved':True,'deduplicated':True,'approval_id':ex['approval_id']}
        aid=_id('cpapprove292'); created=_now(); payload={'approval_id':aid,'checkpoint_id':checkpoint_id,'fusion_id':cp['fusion_id'],'case_id':cp['case_id'],'mission_id':cp['mission_id'],'decision':'approved','approved_by':approved_by,'approved_at':created,'checkpoint_sha256':cp['payload_sha256']}
        self.db.execute('INSERT INTO phase12_checkpoint_approvals_292 VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,checkpoint_id,cp['fusion_id'],cp['case_id'],cp['mission_id'],'approved',approved_by,created,cp['payload_sha256'],_hash(payload)))
        return {**payload,'approved':True,'deduplicated':False}

    def advance_checkpoint(self,*,checkpoint_id:str,actor:str|None=None):
        actor=actor or self.actor; cp=self.db.one('SELECT * FROM phase12_investigator_checkpoints_292 WHERE checkpoint_id=?',(checkpoint_id,))
        if not cp: raise KeyError('checkpoint not found')
        ap=self.db.one("SELECT * FROM phase12_checkpoint_approvals_292 WHERE checkpoint_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(checkpoint_id,))
        if not ap: raise PermissionError("Checkpoint benötigt zuerst das 'OK' des Hauptermittlers.")
        f=self.db.one('SELECT * FROM phase12_fusion_runs_292 WHERE fusion_id=?',(cp['fusion_id'],)); stage=int(cp['stage_no'])
        if stage==1:
            return self._create_checkpoint(f['fusion_id'],f['case_id'],f['mission_id'],2,'confidence_review',f"Arbeits-Confidence: {float(f['confidence_score']):.2f} ({f['confidence_band']}); Widersprüche: {int(f['contradiction_count'])}.","Kalibrierung, Widerspruchspenalty und Unsicherheiten prüfen; dann mit 'OK' zum Investigator-Decision-Checkpoint wechseln.",actor)
        if stage==2:
            return self._create_checkpoint(f['fusion_id'],f['case_id'],f['mission_id'],3,'investigator_decision','Fusion und Kalibrierung sind geprüft; konkurrierende Erklärungen bleiben offen.','Hauptermittler entscheidet, ob eine neue Research Wave, zusätzliche Review-Arbeit oder ein Stopp sinnvoll ist. Externe Collection startet nicht automatisch.',actor)
        return {'fusion_id':f['fusion_id'],'stage_no':3,'stage':'investigator_decision','complete':True,'automatic_truth_selection':False,'external_collection_started':False,'next_action':'Hauptermittler trifft die nächste Ermittlungsentscheidung; neue externe Erhebung benötigt weiterhin separate Freigabe.'}

    def explain_case(self,case_id:str):
        f=self.db.one('SELECT * FROM phase12_fusion_runs_292 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        if not f:return {'stand':'Noch keine Cross-Surface-Fusion für diesen Fall.','meaning':'Build 292 kann vorhandene Claims, Dokumente, Timeline-, Identity-, Capture-, Darkweb- und AI-Analyseoberflächen zusammenführen, ohne ihre Qualitätsunterschiede zu verwischen.','next':'Mit „Cross-Surface-Fusion erstellen“ beginnen.'}
        cp=self.db.one('SELECT * FROM phase12_investigator_checkpoints_292 WHERE fusion_id=? ORDER BY stage_no DESC LIMIT 1',(f['fusion_id'],))
        approved=self.db.one("SELECT * FROM phase12_checkpoint_approvals_292 WHERE checkpoint_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(cp['checkpoint_id'],)) if cp else None
        surfaces=_safe(f['surfaces_json'],[])
        stand=f"{len(surfaces)} Datenoberflächen wurden zusammengeführt. Arbeits-Confidence: {float(f['confidence_score']):.2f} ({f['confidence_band']}); Widersprüche: {int(f['contradiction_count'])}."
        meaning='Der Wert beschreibt, wie tragfähig die aktuelle Synthese ist – nicht, wie wahrscheinlich eine Hypothese wahr ist. Schwache, abhängige oder widersprüchliche Quellen werden heruntergewichtet.'
        if cp and not approved: nxt=f"Checkpoint {cp['stage_no']}/3 ({cp['stage']}) prüfen und nur mit 'OK' freigeben."
        elif cp and int(cp['stage_no'])<3: nxt='Freigegebenen Checkpoint weiterführen; die nächste Stufe wird separat sichtbar.'
        else: nxt='Hauptermittler entscheidet über nächste Research Wave, zusätzliche Prüfung oder Stopp. Externe Collection bleibt separat freigabepflichtig.'
        return {'stand':stand,'meaning':meaning,'next':nxt,'fusion_id':f['fusion_id'],'checkpoint_id':cp['checkpoint_id'] if cp else '','checkpoint_stage':int(cp['stage_no']) if cp else 0}

    def startup_contract_status(self):
        import eagleeye_pro.version as v
        checks={'version_build':_ver(v.BUILD)>=_ver('292.0'),'version_schema':_ver(v.SCHEMA_VERSION)>=_ver('292.0'),'project_entrypoint':(self.base_dir/'EAGLEEYE_PRO_292_0.py').exists(),'startup_acceptance_script':(self.base_dir/'EAGLEEYE_STARTUP_ACCEPTANCE_BUILD_292_0.py').exists(),'generic_windows_starter':(self.base_dir/'START_EAGLEEYE_PRO.bat').exists(),'versioned_windows_starter':(self.base_dir/'START_EAGLEEYE_PRO_292_0.bat').exists(),'setup_script':(self.base_dir/'SETUP_EAGLEEYE_WINDOWS.bat').exists(),'requirements_windows':(self.base_dir/'requirements-windows.txt').exists()}
        return {'build':'292.0','checks':checks,'contract_ready':all(checks.values()),'actual_loopback_boot_required_for_release':True,'packaged_boot_required':True}

    def all_training_cases(self):
        out=self.build291.all_training_cases(); rows=self.db.all("SELECT * FROM ai_hard_training_delta_292 WHERE review_status='reviewed' ORDER BY benchmark_id")
        for r in rows:out.append({'benchmark_id':r['benchmark_id'],'track':r['track'],'difficulty':r['difficulty'],'prompt':r['prompt'],'expected_controls':json.loads(r['expected_controls_json'])})
        return out
    def training_metrics(self):
        base=self.build291.training_metrics(); d=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_292 WHERE review_status='reviewed'")['n']); e=int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_292 WHERE review_status='reviewed' AND difficulty='extreme'")['n'])
        return {'reviewed_hard_cases':int(base['reviewed_hard_cases'])+d,'adversarial_extreme_cases':int(base['adversarial_extreme_cases'])+e,'build292_delta_cases':d,'build292_delta_extreme':e,'performance_gate_threshold':self.GATE_THRESHOLD,'automatic_model_activation':False,'build300_case_target':360}
    def create_evaluation_batch(self,*,model_label:str='mistral:latest',actor:str|None=None):
        actor=actor or self.actor; cases=self.all_training_cases(); manifest={'build':'292.0','model_label':model_label,'corpus_size':len(cases),'required_coverage':1.0,'minimum_mean_score':self.GATE_THRESHOLD,'maximum_critical_failures':0,'independent_evaluator_required':True,'automatic_model_activation':False,'cases':cases}; mh=_hash(manifest)
        ex=self.db.one('SELECT * FROM ai_evaluation_batches_292 WHERE model_label=? AND manifest_sha256=? ORDER BY rowid DESC LIMIT 1',(model_label,mh))
        if ex:return {'batch_id':ex['batch_id'],'corpus_size':int(ex['corpus_size']),'minimum_mean_score':float(ex['threshold']),'independent_evaluator_required':bool(ex['independent_evaluator_required']),'cases':cases,'deduplicated':True}
        bid=_id('eval292'); created=_now(); payload={'batch_id':bid,**manifest,'created_by':actor,'created_at':created}
        self.db.execute('INSERT INTO ai_evaluation_batches_292 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(bid,model_label,len(cases),self.GATE_THRESHOLD,1.0,0,'prepared',1,mh,actor,created,_hash(payload)))
        return {'batch_id':bid,'corpus_size':len(cases),'minimum_mean_score':self.GATE_THRESHOLD,'independent_evaluator_required':True,'cases':cases,'deduplicated':False}
    def performance_status(self,model_label:str='mistral:latest'):
        p=self.build291.performance_status(model_label)
        return {'model_label':model_label,'status':p.get('status','not_run'),'qualified':False,'required_corpus_size':208,'minimum_mean_score':self.GATE_THRESHOLD,'note':'Build 292 beansprucht keine ≥85%-Leistung ohne vollständigen unabhängigen 208-Fälle-Lauf.'}
    def qualified_gate(self):
        parent=self.build291.qualified_gate(); tm=self.training_metrics(); batch=self.create_evaluation_batch(); sc=self.startup_contract_status()
        g={'build':'292.0','parent_gate':bool(parent['release_ready']),'cross_surface_fusion':True,'source_quality_preserved':True,'confidence_calibration':True,'confidence_not_truth':True,'three_stage_checkpoint':True,'explicit_ok_required':True,'external_collection_auto_execution':False,'network_access':False,'beginner_guidance':True,'hard_training_corpus_208':tm['reviewed_hard_cases']>=208 and tm['build292_delta_cases']>=16 and tm['build292_delta_extreme']>=4,'evaluation_batch_208_ready':batch['corpus_size']==208 and abs(batch['minimum_mean_score']-0.85)<1e-9,'startup_contract_ready':sc['contract_ready'],'actual_startup_release_test_required':True,'automatic_model_activation':False,'human_authority_preserved':True}
        g['release_ready']=all([g['parent_gate'],g['cross_surface_fusion'],g['source_quality_preserved'],g['confidence_calibration'],g['confidence_not_truth'],g['three_stage_checkpoint'],g['explicit_ok_required'],not g['external_collection_auto_execution'],not g['network_access'],g['beginner_guidance'],g['hard_training_corpus_208'],g['evaluation_batch_208_ready'],g['startup_contract_ready'],not g['automatic_model_activation'],g['human_authority_preserved']])
        return g

    def render_workspace_panel(self,*,case_id:str,csrf:str):
        e=lambda v:html.escape(str(v or ''),quote=True); x=self.explain_case(case_id); tm=self.training_metrics(); perf=self.performance_status(); sc=self.startup_contract_status(); f=self.db.one('SELECT * FROM phase12_fusion_runs_292 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,))
        rows='<li>Noch keine Fusion.</li>'
        action=f"<form method='post' action='/build292/fusion'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Cross-Surface-Fusion erstellen</button></form>"
        if f:
            items=_safe(f['evidence_items_json'],[]); rows=''.join(f"<li><b>{e(i['surface'])}</b> · {e(i['stance'])} · Beitrag {e(i['contribution'])}<br>{e(i['excerpt'])}<br><small>{e(i['uncertainty'])}</small></li>" for i in items[:8]) or '<li>Keine Beiträge.</li>'
            cp=self.db.one('SELECT * FROM phase12_investigator_checkpoints_292 WHERE fusion_id=? ORDER BY stage_no DESC LIMIT 1',(f['fusion_id'],)); approval=self.db.one("SELECT * FROM phase12_checkpoint_approvals_292 WHERE checkpoint_id=? AND decision='approved' ORDER BY rowid DESC LIMIT 1",(cp['checkpoint_id'],)) if cp else None
            if cp and not approval: action=f"<form method='post' action='/build292/checkpoint/approve'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='checkpoint_id' value='{e(cp['checkpoint_id'])}'><label>Freigabe <input name='confirmation' placeholder='OK'></label> <button>Checkpoint {e(cp['stage_no'])}/3 mit OK freigeben</button></form>"
            elif cp: action=f"<form method='post' action='/build292/checkpoint/advance'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='checkpoint_id' value='{e(cp['checkpoint_id'])}'><button>Freigegebenen Checkpoint weiterführen</button></form>"
        return f"""
<section class='card'><h2>Cross-Surface Evidence Fusion · Build 292</h2>
<div class='notice'><b>Was ist der Stand?</b><br>{e(x['stand'])}<br><br><b>Was bedeutet das?</b><br>{e(x['meaning'])}<br><br><b>Was ist jetzt zu tun?</b><br>{e(x['next'])}</div>
<h3>Fusionierte Beiträge</h3><ol>{rows}</ol>{action}
<details><summary>Analyst/Experte: Kalibrierung, Checkpoints, Startup und Training</summary><p>Hard-Cases: <b>{tm['reviewed_hard_cases']}</b> · adversarial-extreme: <b>{tm['adversarial_extreme_cases']}</b> · Modellstatus: <b>{e(perf['status'])}</b>. Startup-Vertrag: <b>{'ready' if sc['contract_ready'] else 'not ready'}</b>. Build-292 AI-Gate: 208/208 Fälle, ≥85%, 0 kritische Fehler, unabhängige Evaluation. Confidence ist kein Wahrheitswert; Darkweb-/AI-Material wird nicht automatisch aufgewertet. Netzwerkzugriff und automatische externe Collection bleiben aus.</p></details>
</section>"""
