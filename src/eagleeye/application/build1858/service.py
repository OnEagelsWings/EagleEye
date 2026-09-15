from __future__ import annotations
import hashlib, json, math
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
def _clamp(v:float)->float:return max(0.0,min(1.0,float(v)))

class Build1858AIAuthenticityCalibrationService:
    BUILD="185.8"
    SOURCES=(
      {"source_id":"c2pa_trust_list_live","title":"C2PA Trust List / Conformance","class":"provenance_primary","endpoint":"https://spec.c2pa.org/conformance-explorer/","intents":["provenance","signature","content_credentials"]},
      {"source_id":"c2pa_public_testfiles_live","title":"C2PA Public Test Files","class":"official_test_vectors","endpoint":"https://spec.c2pa.org/public-testfiles/","intents":["provenance","validator_test","signature"]},
      {"source_id":"nist_openmfc_live","title":"NIST OpenMFC","class":"official_benchmark","endpoint":"https://mfc.nist.gov/","intents":["image_manipulation","video_manipulation","deepfake","benchmark"]},
      {"source_id":"nist_genai_eval_live","title":"NIST GenAI Evaluations","class":"official_benchmark","endpoint":"https://ai-challenges.nist.gov/","intents":["synthetic_media","ai_text","audio","image","video"]},
      {"source_id":"google_factcheck_api","title":"Google Fact Check Tools API","class":"factcheck_index","endpoint":"https://factchecktools.googleapis.com/v1alpha1/claims:search","intents":["claim_check","context","source_corroboration"]},
      {"source_id":"edmo_factcheck_network","title":"European Digital Media Observatory","class":"factcheck_network","endpoint":"https://edmo.eu/","intents":["claim_check","disinformation","context"]},
      {"source_id":"invid_weverify_reference","title":"InVID-WeVerify Toolkit","class":"verification_tool_reference","endpoint":"https://weverify.eu/verification-plugin/","intents":["image_verification","video_verification","keyframes","context"]},
      {"source_id":"euvsdisinfo_database","title":"EUvsDisinfo Database","class":"official_context_database","endpoint":"https://euvsdisinfo.eu/disinformation-cases/","intents":["disinformation","narrative","claim_check","context"]},
    )
    def __init__(self,db:Any,audit:Any,*,sources:Any|None=None,authenticity:Any|None=None,validation:Any|None=None,actor:str="system"):
        self.db,self.audit,self.sources,self.authenticity,self.validation,self.actor=db,audit,sources,authenticity,validation,actor
    def seed_sources(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!="CALIBRATION SOURCES 1858 ANLEGEN":raise PermissionError("explicit approval required")
        for s in self.SOURCES:
            p={**s,"status":"DOCUMENTED","production_active":False}
            self.db.execute("INSERT OR REPLACE INTO calibration_source_profiles_1858 VALUES(?,?,?,?,?,?,?,?,?,?)",(s['source_id'],s['title'],s['class'],s['endpoint'],dumps(s['intents']),"DOCUMENTED",0,now_ts(),self.actor,_hash(p)))
        return {"created":len(self.SOURCES),"production_active":0,"review_required":True}
    def calibrate_detector(self,*,detector_name:str,detector_version:str,media_type:str,threshold:float,weight:float,precision:float,recall:float,false_positive_rate:float,false_negative_rate:float,expected_calibration_error:float,benchmark_ref:str,sample_size:int,approved_by:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f"CALIBRATION 1858 {detector_name} SPEICHERN":raise PermissionError("explicit approval required")
        vals=[threshold,weight,precision,recall,false_positive_rate,false_negative_rate,expected_calibration_error]
        if any(float(v)<0 or float(v)>1 for v in vals):raise ValueError("metrics must be between 0 and 1")
        if sample_size<100:status="sandbox_only"
        elif false_positive_rate<=0.10 and precision>=0.80 and recall>=0.70 and expected_calibration_error<=0.15:status="approved"
        else:status="sandbox_only"
        cid=new_id("cal1858"); p=locals().copy(); p.pop('self');p.pop('confirmation')
        self.db.execute("INSERT INTO detector_calibrations_1858 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(cid,detector_name,detector_version,media_type,float(threshold),float(weight),float(precision),float(recall),float(false_positive_rate),float(false_negative_rate),float(expected_calibration_error),benchmark_ref,int(sample_size),status,approved_by,now_ts(),_hash(p)))
        return {"calibration_id":cid,"status":status,"production_eligible":status=="approved","automatic_activation":False}
    def evaluate_ensemble(self,*,case_id:str,target_ref:str,media_type:str,results:Sequence[Mapping[str,Any]],confirmation:str)->dict[str,Any]:
        if confirmation!=f"ENSEMBLE 1858 {target_ref} AUSWERTEN":raise PermissionError("explicit approval required")
        accepted=[]
        for x in results:
            row=self.db.one("SELECT * FROM detector_calibrations_1858 WHERE detector_name=? AND detector_version=? AND media_type=? AND status='approved' ORDER BY created_at DESC LIMIT 1",(x.get('detector_name'),x.get('detector_version'),media_type))
            if row:
                score=_clamp(float(x.get('score',0))); positive=score>=float(row['threshold'])
                accepted.append({"detector_name":x.get('detector_name'),"score":score,"weight":float(row['weight']),"positive":positive,"false_positive_rate":float(row['false_positive_rate'])})
        denom=sum(x['weight'] for x in accepted) or 1.0
        weighted=sum(x['score']*x['weight'] for x in accepted)/denom
        positives=sum(1 for x in accepted if x['positive'])
        status="suspicious_candidate" if len(accepted)>=2 and positives>=2 and weighted>=0.65 else ("no_anomaly_detected" if len(accepted)>=2 and positives==0 else "inconclusive")
        eid=new_id("ens1858"); limitations=["detector_ensemble_is_not_verdict","domain_shift_requires_review","provenance_and_context_take_precedence","human_review_required"]
        payload={"ensemble_id":eid,"case_id":case_id,"target_ref":target_ref,"media_type":media_type,"accepted_detectors":accepted,"weighted_score":round(weighted,6),"positive_detectors":positives,"status":status,"limitations":limitations,"automatic_fake_verdict":False}
        self.db.execute("INSERT INTO authenticity_ensemble_runs_1858 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(eid,case_id,target_ref,media_type,dumps(accepted),weighted,positives,status,dumps(limitations),now_ts(),_hash(payload)))
        return payload
    def calibrate_ai_assessment(self,*,case_id:str,claim:str,evidence:Sequence[Mapping[str,Any]],model_outputs:Sequence[Mapping[str,Any]],confirmation:str)->dict[str,Any]:
        if confirmation!=f"AI CALIBRATION 1858 {case_id} AUSWERTEN":raise PermissionError("explicit approval required")
        independent={str(e.get('source_id')) for e in evidence if e.get('independent') and e.get('source_id')}
        support=sum(_clamp(e.get('score',0))*float(e.get('weight',1)) for e in evidence if e.get('direction')=='support')
        contradict=sum(_clamp(e.get('score',0))*float(e.get('weight',1)) for e in evidence if e.get('direction')=='contradict')
        calibrated=[m for m in model_outputs if m.get('calibrated') is True]
        model_score=sum(_clamp(m.get('confidence',0)) for m in calibrated)/len(calibrated) if calibrated else None
        if len(independent)>=2 and support>=1.2 and support>contradict:status="corroborated_candidate"
        elif len(independent)>=2 and contradict>=1.2 and contradict>support:status="contradicted_candidate"
        else:status="inconclusive"
        aid=new_id("aical1858"); limits=["ai_output_is_not_fact","models_do_not_replace_sources","source_independence_requires_review","human_review_required"]
        payload={"assessment_id":aid,"case_id":case_id,"claim":claim,"status":status,"independent_sources":len(independent),"evidence_support":support,"evidence_contradict":contradict,"calibrated_model_score":model_score,"limitations":limits}
        self.db.execute("INSERT INTO ai_calibration_assessments_1858 VALUES(?,?,?,?,?,?,?,?,?,?)",(aid,case_id,claim,status,len(independent),support,contradict,model_score,dumps(limits),_hash(payload)))
        return payload
    def route_verification(self,*,case_id:str,question:str,media_type:str,claim:str="",confirmation:str)->dict[str,Any]:
        if confirmation!=f"VERIFY ROUTING 1858 {case_id} PLANEN":raise PermissionError("explicit approval required")
        q=(question+" "+claim).lower(); intents=[]
        if any(x in q for x in ('fake','deepfake','manipul','synthet','ki-gener')):intents += ['deepfake','synthetic_media','image_manipulation','video_manipulation']
        if any(x in q for x in ('quelle','ursprung','herkunft','woher','content credential','signatur')):intents += ['provenance','content_credentials','signature']
        if any(x in q for x in ('behaupt','zitat','wahr','fact','kontext')):intents += ['claim_check','context','source_corroboration']
        intents=list(dict.fromkeys(intents or ['provenance','claim_check']))
        ranked=[]
        for s in self.SOURCES:
            overlap=len(set(intents)&set(s['intents']))
            if overlap:ranked.append({**s,"match_score":overlap,"execution_mode":"structured_connector" if s['source_id']=='google_factcheck_api' else "guided_browser_tab","result_status":"candidate_only","review_required":True})
        ranked.sort(key=lambda x:(-x['match_score'],0 if 'primary' in x['class'] or 'official' in x['class'] else 1,x['title']))
        return {"case_id":case_id,"build":self.BUILD,"intents":intents,"steps":ranked,"general_search_secondary":True,"automatic_verdict":False}
    def dashboard(self)->dict[str,Any]:
        return {"build":self.BUILD,"sources":len(self.SOURCES),"automatic_fake_verdict":False,"human_review_required":True,"approved_detectors":self.db.one("SELECT COUNT(*) AS n FROM detector_calibrations_1858 WHERE status='approved'")['n']}
