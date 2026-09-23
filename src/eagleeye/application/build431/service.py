from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build431NewsProvenanceService:
 BUILD='431.0'
 def __init__(self,db,audit,*,build430,provenance431,actor='local-analyst'):self.db=db;self.audit=audit;self.build430=build430;self.provenance431=provenance431;self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build430,n,None)
  if v is None:raise AttributeError(n)
  return v
 def analyze_news_provenance(self,**kw):return self.provenance431.analyze(**kw)
 def latest_news_provenance(self,case_id):return self.provenance431.latest(case_id)
 def provenance_status(self):
  s=self.provenance431.status();return {**s,'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION and int(RUNTIME_BUILD.split('.')[0])>=int(self.BUILD.split('.')[0]),'phase':19,'phase19_builds_completed':11,'production_release_ready':False}
