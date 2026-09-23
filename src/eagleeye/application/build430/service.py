from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build430NewsExtractionService:
 BUILD='430.0'
 def __init__(self,db,audit,*,build429,extraction430,actor='local-analyst'):self.db=db;self.audit=audit;self.build429=build429;self.extraction430=extraction430;self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build429,n,None)
  if v is None:raise AttributeError(n)
  return v
 def record_news_extraction(self,**kw):return self.extraction430.record(**kw)
 def case_news_extractions(self,case_id):return self.extraction430.case_extractions(case_id)
 def extraction_status(self):
  s=self.extraction430.status();return {**s,'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION and int(RUNTIME_BUILD.split('.')[0])>=int(self.BUILD.split('.')[0]),'phase':19,'phase19_builds_completed':10,'hard_checkpoint':True,'production_release_ready':False}
