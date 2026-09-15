from __future__ import annotations
import hashlib, json
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode()).hexdigest()

def _clamp(v: Any) -> float:
    return max(0.0, min(1.0, float(v)))

class Build184RealCaseValidationService:
    BUILD = "184.0"
    SOURCE_PROFILES = [
        {"source_id":"nist_openmfc","title":"NIST Open Media Forensics Challenge","category":"media_forensics_evaluation","access_mode":"official_evaluation","base_url":"https://mfc.nist.gov","docs_url":"https://www.nist.gov/itl/iad/mltg/open-media-forensics-challenge","constraints":["evaluation_dataset_terms","benchmark_not_case_verdict"]},
        {"source_id":"nist_genai_evaluations","title":"NIST GenAI Evaluations","category":"generative_ai_evaluation","access_mode":"official_evaluation","base_url":"https://ai-challenges.nist.gov","docs_url":"https://ai-challenges.nist.gov/genai","constraints":["task_specific_metrics","domain_shift_review"]},
        {"source_id":"nist_mediscore","title":"NIST MediScore Toolkit","category":"forensics_scoring","access_mode":"official_reference_implementation","base_url":"https://github.com/usnistgov/MediScore","docs_url":"https://data.nist.gov/pdr/lps/ark:/88434/mds2-2565","constraints":["version_pinned","metric_configuration_recorded"]},
        {"source_id":"c2pa_public_testfiles_184","title":"C2PA Public Test Files","category":"provenance_conformance","access_mode":"official_test_corpus","base_url":"https://spec.c2pa.org","docs_url":"https://spec.c2pa.org/public-testfiles/","constraints":["test_vectors_not_real_case_truth","validator_version_recorded"]},
        {"source_id":"w3c_prov_o","title":"W3C PROV-O","category":"provenance_model","access_mode":"official_standard","base_url":"https://www.w3.org","docs_url":"https://www.w3.org/TR/prov-o/","constraints":["provenance_not_truth","mapping_review_required"]},
        {"source_id":"ohchr_berkeley_protocol","title":"OHCHR Berkeley Protocol","category":"digital_open_source_validation","access_mode":"official_guidance","base_url":"https://www.ohchr.org","docs_url":"https://searchlibrary.ohchr.org/record/30334","constraints":["legal_context_review","do_no_harm","human_review_required"]},
    ]
    def __init__(self, db: Any, audit: Any, *, authenticity: Any, ai: Any, workspace: Any, repository: Any, actor: str = "system"):
        self.db, self.audit, self.authenticity, self.ai, self.workspace, self.repository, self.actor = db, audit, authenticity, ai, workspace, repository, actor
    def seed_sources(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "VALIDATION SOURCES 184 ERWEITERN": raise PermissionError("explicit source approval required")
        for p in self.SOURCE_PROFILES:
            q = {**p, "status":"DOCUMENTED"}
            self.db.execute("INSERT OR REPLACE INTO validation_source_profiles_184 VALUES(?,?,?,?,?,?,?,?,?,?)", (p["source_id"],p["title"],p["category"],p["access_mode"],p["base_url"],p["docs_url"],dumps(p["constraints"]),"DOCUMENTED",now_ts(),_hash(q)))
        return {"created":6,"production_active":0,"review_required":True}
    def create_case(self, title: str, *, case_type: str, ground_truth_policy: str = "adjudicated", dataset_ref: str = "", created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != "VALIDATION 184 FALL ANLEGEN": raise PermissionError("explicit validation approval required")
        if case_type not in {"media_authenticity","source_corroboration","entity_resolution","timeline","geolocation","multilingual","mixed"}: raise ValueError("unsupported validation case type")
        if ground_truth_policy not in {"adjudicated","synthetic_fixture","official_test_vector","consensus_reference"}: raise ValueError("invalid ground truth policy")
        cid = new_id("valcase184"); payload={"validation_case_id":cid,"title":str(title)[:240],"case_type":case_type,"ground_truth_policy":ground_truth_policy,"dataset_ref":dataset_ref,"status":"draft","created_by":created_by,"review_required":True}
        self.db.execute("INSERT INTO validation_cases_184 VALUES(?,?,?,?,?,?,?,?,?,?)",(cid,payload["title"],case_type,ground_truth_policy,dataset_ref,"draft",created_by,now_ts(),dumps(["no_live_subject_targeting","lawful_or_synthetic_data_only","human_review_required"]),_hash(payload)))
        self._event(cid,"validation_case_created",payload); return payload
    def add_item(self, validation_case_id: str, *, item_ref: str, label: str, expected: Mapping[str,Any], dimensions: Mapping[str,Any] | None = None, confirmation: str) -> dict[str,Any]:
        if confirmation != f"VALIDATION 184 {validation_case_id} ITEM HINZUFUEGEN": raise PermissionError("explicit item approval required")
        if label not in {"positive","negative","ambiguous","not_applicable"}: raise ValueError("invalid label")
        if not self.db.one("SELECT validation_case_id FROM validation_cases_184 WHERE validation_case_id=?",(validation_case_id,)): raise ValueError("validation case missing")
        iid=new_id("valitem184"); payload={"item_id":iid,"validation_case_id":validation_case_id,"item_ref":item_ref,"label":label,"expected":dict(expected),"dimensions":dict(dimensions or {}),"ground_truth_reviewed":False}
        self.db.execute("INSERT INTO validation_items_184 VALUES(?,?,?,?,?,?,?,?,?)",(iid,validation_case_id,item_ref,label,dumps(dict(expected)),dumps(dict(dimensions or {})),0,now_ts(),_hash(payload))); return payload
    def adjudicate_item(self, item_id: str, *, reviewers: Sequence[str], decision_note: str, confirmation: str) -> dict[str,Any]:
        if confirmation != f"VALIDATION 184 {item_id} ADJUDIZIEREN": raise PermissionError("explicit adjudication required")
        unique=sorted({str(x).strip() for x in reviewers if str(x).strip()})
        if len(unique)<2: raise ValueError("two independent reviewers required")
        self.db.execute("UPDATE validation_items_184 SET ground_truth_reviewed=1 WHERE item_id=?",(item_id,)); payload={"item_id":item_id,"reviewers":unique,"decision_note":decision_note[:2000],"status":"adjudicated"}; self._event("global","ground_truth_adjudicated",payload); return payload
    def record_predictions(self, validation_case_id: str, *, system_name: str, system_version: str, predictions: Sequence[Mapping[str,Any]], confirmation: str) -> dict[str,Any]:
        if confirmation != f"VALIDATION 184 {validation_case_id} AUSWERTEN": raise PermissionError("explicit validation run required")
        items={r["item_id"]:r for r in self.db.all("SELECT * FROM validation_items_184 WHERE validation_case_id=?",(validation_case_id,))}
        if not items: raise ValueError("validation items required")
        run_id=new_id("valrun184"); rows=[]
        for p in predictions:
            iid=str(p.get("item_id",""))
            if iid not in items: continue
            score=_clamp(p.get("score",0)); pred="positive" if score>=_clamp(p.get("threshold",0.5)) else "negative"; rows.append((iid,score,pred,dict(p)))
        if not rows: raise ValueError("matching predictions required")
        for iid,score,pred,raw in rows: self.db.execute("INSERT INTO validation_predictions_184 VALUES(?,?,?,?,?,?,?,?,?)",(new_id("pred184"),run_id,iid,score,pred,dumps(raw),system_name,system_version,now_ts()))
        metrics=self._metrics(items,rows); status=self._gate_status(metrics); limitations=["benchmark_performance_is_not_case_verdict","domain_shift_requires_review","false_positives_and_false_negatives_must_be_reported","human_review_required"]
        payload={"run_id":run_id,"validation_case_id":validation_case_id,"system_name":system_name,"system_version":system_version,"metrics":metrics,"gate_status":status,"limitations":limitations}
        self.db.execute("INSERT INTO validation_runs_184 VALUES(?,?,?,?,?,?,?,?,?,?)",(run_id,validation_case_id,system_name,system_version,dumps(metrics),status,dumps(limitations),now_ts(),self.actor,_hash(payload))); self._event(validation_case_id,"validation_run_completed",payload); return payload
    def _metrics(self, items: Mapping[str,Any], rows: Sequence[tuple[str,float,str,dict[str,Any]]]) -> dict[str,Any]:
        tp=tn=fp=fn=0; brier=0.0; usable=0; bins=[[] for _ in range(10)]; slices={}
        for iid,score,pred,_ in rows:
            label=items[iid]["label"]
            if label not in {"positive","negative"}: continue
            actual=1 if label=="positive" else 0; usable+=1; brier+=(score-actual)**2; bins[min(9,int(score*10))].append((score,actual))
            if actual and pred=="positive": tp+=1
            elif not actual and pred=="negative": tn+=1
            elif not actual and pred=="positive": fp+=1
            else: fn+=1
            for k,v in json.loads(items[iid]["dimensions_json"] or "{}").items():
                key=f"{k}={v}"; d=slices.setdefault(key,{"n":0,"errors":0}); d["n"]+=1; d["errors"]+=int(pred!=label)
        precision=tp/(tp+fp) if tp+fp else 0.0; recall=tp/(tp+fn) if tp+fn else 0.0; fpr=fp/(fp+tn) if fp+tn else 0.0; fnr=fn/(fn+tp) if fn+tp else 0.0; accuracy=(tp+tn)/usable if usable else 0.0
        ece=0.0
        if usable:
            for b in bins:
                if b: ece += len(b)/usable * abs(sum(x for x,_ in b)/len(b)-sum(y for _,y in b)/len(b))
        return {"n":usable,"tp":tp,"tn":tn,"fp":fp,"fn":fn,"precision":round(precision,6),"recall":round(recall,6),"false_positive_rate":round(fpr,6),"false_negative_rate":round(fnr,6),"accuracy":round(accuracy,6),"brier_score":round(brier/usable,6) if usable else None,"expected_calibration_error":round(ece,6),"dimension_slices":slices}
    def _gate_status(self, m: Mapping[str,Any]) -> str:
        if int(m.get("n",0))<4: return "insufficient_sample"
        return "candidate_pass" if float(m.get("false_positive_rate",1))<=0.15 and float(m.get("recall",0))>=0.70 and float(m.get("expected_calibration_error",1))<=0.20 else "blocked"
    def define_release_gate(self, name: str, *, requirements: Mapping[str,Any], approved_by: str, confirmation: str) -> dict[str,Any]:
        if confirmation != "VALIDATION GATE 184 ANLEGEN": raise PermissionError("explicit gate approval required")
        gid=new_id("gate184"); allowed={"min_n","min_precision","min_recall","max_false_positive_rate","max_false_negative_rate","max_brier_score","max_expected_calibration_error"}; req={k:v for k,v in requirements.items() if k in allowed}; payload={"gate_id":gid,"name":name[:160],"requirements":req,"approved_by":approved_by,"status":"active"}
        self.db.execute("INSERT INTO validation_gates_184 VALUES(?,?,?,?,?,?,?)",(gid,payload["name"],dumps(req),"active",approved_by,now_ts(),_hash(payload))); return payload
    def evaluate_gate(self, gate_id: str, run_id: str) -> dict[str,Any]:
        gate=self.db.one("SELECT * FROM validation_gates_184 WHERE gate_id=?",(gate_id,)); run=self.db.one("SELECT * FROM validation_runs_184 WHERE run_id=?",(run_id,))
        if not gate or not run: raise ValueError("gate and run required")
        req=json.loads(gate["requirements_json"]); m=json.loads(run["metrics_json"]); checks={}; mapping={"min_n":("n","min"),"min_precision":("precision","min"),"min_recall":("recall","min"),"max_false_positive_rate":("false_positive_rate","max"),"max_false_negative_rate":("false_negative_rate","max"),"max_brier_score":("brier_score","max"),"max_expected_calibration_error":("expected_calibration_error","max")}
        for key,val in req.items():
            metric,kind=mapping[key]; actual=m.get(metric); checks[key]=False if actual is None else (actual>=val if kind=="min" else actual<=val)
        status="passed" if checks and all(checks.values()) else "blocked"; payload={"gate_id":gate_id,"run_id":run_id,"status":status,"checks":checks,"automatic_production_activation":False,"human_release_decision_required":True}
        self.db.execute("INSERT INTO validation_gate_results_184 VALUES(?,?,?,?,?,?)",(new_id("gr184"),gate_id,run_id,status,dumps(checks),now_ts())); return payload
    def source_coverage(self) -> dict[str,Any]:
        tables=("european_source_profiles_172","extended_source_profiles_173","media_source_profiles_174","geo_source_profiles_175","multilingual_source_profiles_176","graph_source_profiles_177","monitor_source_profiles_178","pattern_source_profiles_179","authenticity_source_profiles_180","workspace_source_profiles_181","repository_source_profiles_182","plugin_source_profiles_183","validation_source_profiles_184"); counts=[]
        for t in tables:
            try: counts.append(int(self.db.one(f"SELECT COUNT(*) n FROM {t}")["n"]))
            except Exception: counts.append(0)
        return {"total_documented_sources":sum(counts),"validation_sources":counts[-1],"production_active_new":0,"review_required":True}
    def _event(self, case_id: str, event_type: str, details: Mapping[str,Any]) -> None:
        prev=self.db.one("SELECT event_sha256 FROM validation_events_184 WHERE case_id=? ORDER BY created_at DESC LIMIT 1",(case_id,)); ph=prev["event_sha256"] if prev else ""; eid=new_id("ve184"); ts=now_ts(); eh=_hash({"event_id":eid,"case_id":case_id,"event_type":event_type,"details":details,"created_at":ts,"previous_sha256":ph}); self.db.execute("INSERT INTO validation_events_184 VALUES(?,?,?,?,?,?,?)",(eid,case_id,event_type,dumps(dict(details)),ts,ph,eh))
