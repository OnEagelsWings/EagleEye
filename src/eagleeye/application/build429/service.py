from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build429NewsConnectorService:
 BUILD='429.0'
 def __init__(self,db,audit,*,build428,news429,actor='local-analyst'):self.db=db;self.audit=audit;self.build428=build428;self.news429=news429;self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build428,n,None)
  if v is None:raise AttributeError(n)
  return v
 def ingest_news_item(self,**kw):return self.news429.ingest_item(**kw)
 def case_news(self,case_id):return self.news429.case_items(case_id)
 def news_status(self):
  s=self.news429.status();return {**s,'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION and int(RUNTIME_BUILD.split('.')[0])>=int(self.BUILD.split('.')[0]),'phase':19,'phase19_builds_completed':9,'production_release_ready':False}
