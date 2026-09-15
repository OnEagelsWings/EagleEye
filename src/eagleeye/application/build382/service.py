from __future__ import annotations
from dataclasses import asdict
from typing import Any
class Build382SourceRegistryPersistenceService:
    BUILD="382.0"; POLICY="phase17.source-registry-persistence-coverage.v382"
    def __init__(self, db:Any, audit:Any, *, build381:Any, runtime:Any, actor:str="local-analyst") -> None:
        self.db=db; self.audit=audit; self.build381=build381; self.runtime=runtime; self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        v=getattr(self.build381,name,None)
        if v is None: raise AttributeError(name)
        return v
    def coverage(self,case_id:str):
        c=self.runtime.coverage382(case_id); return asdict(c)
    def set_source_scope(self, **kwargs:Any): self.runtime.set_source_scope382(**kwargs); return {"ok":True,"execution_authority":False}
    def phase17_status(self,case_id:str=""):
        out=dict(self.build381.phase17_status(case_id)); out.update({"build":self.BUILD,"phase17_builds_completed":2,"persistent_source_registry":True,"coverage_gap_ledger":True}); return out
