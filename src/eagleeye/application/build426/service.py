from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build426CrawlPrioritizationService:
 BUILD='426.0'
 def __init__(self,db,audit,*,build425,priority426,actor='local-analyst'):self.db=db;self.audit=audit;self.build425=build425;self.priority426=priority426;self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build425,n,None)
  if v is None:raise AttributeError(n)
  return v
 def prioritize_crawl(self,**kw):return self.priority426.prioritize(**kw)
 def ranked_case(self,case_id):return self.priority426.ranked_case(case_id)
 def prioritization_status(self):
  s=self.priority426.status();return {**s,'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION==self.BUILD,'phase':19,'phase19_builds_completed':6,'production_release_ready':False}
