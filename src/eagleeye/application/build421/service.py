from __future__ import annotations
import re
from importlib.metadata import version as package_version
from pathlib import Path
from eagleeye_pro.version import BUILD as RUNTIME_BUILD,SCHEMA_VERSION
class Build421AcquisitionSourceRegistryService:
 BUILD='421.0';PACKAGE='421.0.0'
 def __init__(self,db,audit,*,build420,registry421,install_dir,actor='local-analyst'):self.db=db;self.audit=audit;self.build420=build420;self.registry421=registry421;self.install_dir=Path(install_dir);self.actor=actor
 def __getattr__(self,n):
  if n.startswith('_'):raise AttributeError(n)
  v=getattr(self.build420,n,None)
  if v is None:raise AttributeError(n)
  return v
 def version_status(self):
  try:p=package_version('eagleeye-personosint-pro')
  except Exception:
   pt=self.install_dir/'pyproject.toml';txt=pt.read_text() if pt.exists() else '';m=re.search(r'^version\s*=\s*["\']([^"\']+)',txt,re.M);p=m.group(1) if m else 'unknown'
  return {'runtime_build':RUNTIME_BUILD,'schema_version':SCHEMA_VERSION,'package_version':p,'coherent':RUNTIME_BUILD==SCHEMA_VERSION==self.BUILD and p==self.PACKAGE}
 def register_source(self,**kw):return self.registry421.register(**kw)
 def sources(self,**kw):return self.registry421.list_sources(**kw)
 def acquisition_status(self):
  s=self.registry421.status();return {**s,'version_coherent':self.version_status()['coherent'],'phase':19,'phase19_builds_completed':1,'production_release_ready':False}
