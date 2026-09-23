from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build433OrganizationIntelligenceService:
 BUILD='433.0'
 def __init__(self,db,audit,*,build432,organization433,actor='local-analyst'):self.db=db;self.audit=audit;self.build432=build432;self.organization433=organization433;self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build432,n,None)
  if v is None:raise AttributeError(n)
  return v
 def create_organization_subject(self,**kw):return self.organization433.create_subject(**kw)
 def record_organization_observation(self,**kw):return self.organization433.record_observation(**kw)
 def record_organization_relation(self,**kw):return self.organization433.record_relation(**kw)
 def case_organizations(self,case_id):return self.organization433.list_subjects(case_id)
 def organization_detail(self,case_id,subject_id):return self.organization433.subject_detail(case_id,subject_id)
 def case_organization_report(self,case_id):return self.organization433.case_report(case_id)
 def run_organization_case_selftest(self,**kw):return self.organization433.run_case_selftest(**kw)
 def organization_status(self):
  s=self.organization433.status();return {**s,'version_coherent':RUNTIME_BUILD==SCHEMA_VERSION==self.BUILD,'phase':19,'phase19_builds_completed':13,'production_release_ready':False}
