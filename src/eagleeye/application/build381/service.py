from __future__ import annotations
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any
class Build381InvestigationControlService:
    BUILD="381.0"; POLICY="phase17.investigation-control-source-registry.v381"
    def __init__(self, db:Any, audit:Any, *, build380:Any, runtime:Any, install_dir:Any, actor:str="local-analyst") -> None:
        self.db=db; self.audit=audit; self.build380=build380; self.runtime=runtime; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        v=getattr(self.build380,name,None)
        if v is None: raise AttributeError(name)
        return v
    def historical_phase16_decision(self):
        path=self.install_dir/'FINAL_PRODUCTION_DECISION_BUILD_380.json'
        try:
            value=json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            return {"build":"380.0","result":"missing","professional_pilot_ready":False,"production_release_ready":False}
        decision=value.get("decision") if isinstance(value.get("decision"),dict) else value
        return {"build":value.get('build','380.0'),"result":value.get('result','pass' if decision.get('professional_pilot_ready') else 'unknown'),"final_decision":decision.get('decision') or decision.get('final_decision') or decision.get('current_decision'),"professional_pilot_ready":bool(decision.get('professional_pilot_ready')),"production_candidate":bool(decision.get('production_candidate')),"production_release_ready":bool(decision.get('production_release_ready')),"external_qualification_validated":bool(decision.get('external_qualification_validated')),"historical_receipt":True,"base_code_fingerprint":value.get('code_fingerprint','')}
    def snapshot(self,case_id:str): return self.runtime.snapshot381(case_id)
    def plan_research(self, **kwargs:Any):
        p=self.runtime.plan381(**kwargs); return asdict(p)|{"plan_hash":p.plan_hash}
    def phase17_status(self,case_id:str=""):
        return {"build":self.BUILD,"phase17_builds_completed":1,"predecessor380":self.historical_phase16_decision(),"control_plane":self.runtime.status(case_id),"requires_go":True,"execution_authority":False}
    def dashboard(self,case_id:str=""): return {"build":self.BUILD,"phase16_predecessor":self.historical_phase16_decision(),"phase17":self.phase17_status(case_id)}
