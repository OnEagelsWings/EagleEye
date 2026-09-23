from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build425CrawlerCoreService:
 BUILD='425.0'
 def __init__(self,db,audit,*,build424,crawler425,actor='local-analyst'):self.db=db;self.audit=audit;self.build424=build424;self.crawler425=crawler425;self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build424,n,None)
  if v is None:raise AttributeError(n)
  return v
 def create_crawl_task(self,**kw):return self.crawler425.create_task(**kw)
 def accept_retrieval(self,**kw):return self.crawler425.accept_retrieval(**kw)
 def crawler_status(self):
  s=self.crawler425.status();return {**s,'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION and int(RUNTIME_BUILD.split('.')[0])>=int(self.BUILD.split('.')[0]),'phase':19,'phase19_builds_completed':5,'production_release_ready':False}
