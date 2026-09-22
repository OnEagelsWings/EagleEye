from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build428ArchiveHistoryService:
 BUILD='428.0'
 def __init__(self,db,audit,*,build427,archive428,actor='local-analyst'):self.db=db;self.audit=audit;self.build427=build427;self.archive428=archive428;self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build427,n,None)
  if v is None:raise AttributeError(n)
  return v
 def register_archive_capture(self,**kw):return self.archive428.register_capture(**kw)
 def archive_timeline(self,case_id,original_url):return self.archive428.timeline(case_id,original_url)
 def archive_status(self):
  s=self.archive428.status();return {**s,'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION==self.BUILD,'phase':19,'phase19_builds_completed':8,'production_release_ready':False}
