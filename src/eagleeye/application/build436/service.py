from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build436SurfaceOnionService:
 BUILD='436.0'
 def __init__(self,db,audit,*,build435,correlation436,actor='local-analyst'):self.db=db;self.audit=audit;self.build435=build435;self.correlation436=correlation436;self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build435,n,None)
  if v is None:raise AttributeError(n)
  return v
 def analyze_surface_onion(self,**kw):return self.correlation436.analyze(**kw)
 def latest_surface_onion(self,case_id):return self.correlation436.latest(case_id)
 def case_surface_onion_report(self,case_id):return self.correlation436.case_report(case_id)
 def run_surface_onion_case_selftest(self,**kw):return self.correlation436.run_case_selftest(**kw)
 def surface_onion_status(self):
  s=self.correlation436.status();return {**s,'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION and int(RUNTIME_BUILD.split('.')[0])>=int(self.BUILD.split('.')[0]),'phase':19,'phase19_builds_completed':16,'production_release_ready':False}
