from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build427IncrementalChangeService:
 BUILD='427.0'
 def __init__(self,db,audit,*,build426,change427,actor='local-analyst'):self.db=db;self.audit=audit;self.build426=build426;self.change427=change427;self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build426,n,None)
  if v is None:raise AttributeError(n)
  return v
 def capture_snapshot(self,**kw):return self.change427.capture(**kw)
 def change_history(self,case_id):return self.change427.changes(case_id)
 def change_status(self):
  s=self.change427.status();return {**s,'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION and int(RUNTIME_BUILD.split('.')[0])>=int(self.BUILD.split('.')[0]),'phase':19,'phase19_builds_completed':7,'production_release_ready':False}
