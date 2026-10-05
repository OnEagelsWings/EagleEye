from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build437CrossSourceEntityResolutionService:
 BUILD='437.0'
 def __init__(self,db,audit,*,build436,resolution437,actor='local-analyst'):self.db=db;self.audit=audit;self.build436=build436;self.resolution437=resolution437;self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build436,n,None)
  if v is None:raise AttributeError(n)
  return v
 def sync_cross_source_entities(self,**kw):return self.resolution437.sync_case(**kw)
 def entity_resolution_bindings(self,case_id):return self.resolution437.bindings(case_id)
 def entity_resolution_review_queue(self,case_id):return self.resolution437.review_queue(case_id)
 def entity_resolution_packet(self,case_id,comparison_id):return self.resolution437.packet(case_id,comparison_id)
 def propose_same_entity_437(self,**kw):return self.resolution437.propose_same_entity(**kw)
 def review_same_entity_437(self,**kw):return self.resolution437.review_same_entity(**kw)
 def entity_resolution_report(self,case_id):return self.resolution437.case_report(case_id)
 def run_entity_resolution_case_selftest(self,**kw):return self.resolution437.run_case_selftest(**kw)
 def entity_resolution_status_437(self):
  s=self.resolution437.status();return {**s,'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION and int(RUNTIME_BUILD.split('.')[0])>=int(self.BUILD.split('.')[0]),'phase':19,'phase19_builds_completed':17,'production_release_ready':False}
