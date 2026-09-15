from __future__ import annotations
from dataclasses import asdict
from typing import Any
class Build383SourcePlannerService:
    BUILD="383.0"; POLICY="phase17.source-planner.v383"
    def __init__(self, db:Any, audit:Any, *, build382:Any, runtime:Any, actor:str="local-analyst") -> None:
        self.db=db; self.audit=audit; self.build382=build382; self.runtime=runtime; self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        v=getattr(self.build382,name,None)
        if v is None: raise AttributeError(name)
        return v
    def plan_acquisition(self, **kwargs:Any):
        p=self.runtime.plan383(**kwargs); return asdict(p)|{"plan_hash":p.plan_hash}
    def phase17_status(self,case_id:str=""):
        out=dict(self.build382.phase17_status(case_id)); out.update({"build":self.BUILD,"phase17_builds_completed":3,"source_planner_v1":True,"automatic_scope_expansion":False}); return out
