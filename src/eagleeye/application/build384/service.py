from __future__ import annotations
from dataclasses import asdict
import hashlib, json, re
from pathlib import Path
from typing import Any

def _read_json(path:Path)->dict[str,Any]:
    try:
        v=json.loads(path.read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception: return {}

class Build384JurisdictionResearchWavesService:
    BUILD="384.0"; PACKAGE="384.0.0"; POLICY="phase17.jurisdiction-research-waves.v384"
    def __init__(self, db:Any, audit:Any, *, build383:Any, runtime:Any, install_dir:Any, actor:str="local-analyst") -> None:
        self.db=db; self.audit=audit; self.build383=build383; self.runtime=runtime; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith("_"): raise AttributeError(name)
        v=getattr(self.build383,name,None)
        if v is None: raise AttributeError(name)
        return v
    def _fingerprint_paths(self):
        return (
          'eagleeye_pro/phase17/investigation_control381.py','eagleeye_pro/phase17/source_registry_persistence382.py','eagleeye_pro/phase17/source_planner383.py','eagleeye_pro/phase17/jurisdiction_intelligence384.py','eagleeye_pro/phase17/integration.py','eagleeye_pro/core/app_context.py',
          'src/eagleeye/application/build381/service.py','src/eagleeye/application/build382/service.py','src/eagleeye/application/build383/service.py','src/eagleeye/application/build384/service.py','src/eagleeye/interfaces/web/app384.py','src/eagleeye/interfaces/web/server.py','eagleeye_pro/version.py','pyproject.toml','tests/test_build384_integrated.py'
        )
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel; h.update(rel.encode()); h.update(b'\0'); h.update(p.read_bytes() if p.is_file() else b'<missing>'); h.update(b'\0')
        return h.hexdigest()
    def plan_research_waves(self, **kwargs:Any):
        p=self.runtime.plan384(**kwargs); return asdict(p)|{"plan_hash":p.plan_hash}
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(encoding='utf-8'); pt=(self.install_dir/'pyproject.toml').read_text(encoding='utf-8')
        def g(p,t):
            m=re.search(p,t,re.M); return m.group(1) if m else 'unknown'
        runtime=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=g(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {"runtime_build":runtime,"schema_version":schema,"package_version":package,"coherent":runtime==schema==self.BUILD and package==self.PACKAGE}
    def schema_metrics(self):
        _=self.runtime.status()
        rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type")
        counts={r['type']:int(r['c']) for r in rows}; integrity=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown')
        return {"tables":counts.get('table',0),"indexes":counts.get('index',0),"triggers":counts.get('trigger',0),"views":counts.get('view',0),"integrity_check":integrity,"within_phase17_gate":counts.get('table',0)<190 and counts.get('index',0)<325 and integrity=='ok'}
    def _evidence(self,name):
        v=_read_json(self.install_dir/name); return v if v.get('build')==self.BUILD and v.get('code_fingerprint')==self.code_fingerprint() and v.get('result')=='pass' else {}
    def qualified_gate(self):
        version=self.version_status(); schema=self.schema_metrics(); tests=self._evidence('BUILD_384_TEST_EVIDENCE.json'); bench=self._evidence('BENCHMARK_BUILD_384_INTEGRATED.json'); acceptance=self._evidence('ACCEPTANCE_RESULTS_BUILD_384_0.json')
        pred=self.build383.build382.build381.historical_phase16_decision()
        checks={"version_coherent":bool(version['coherent']),"schema_integrity":bool(schema['within_phase17_gate']),"phase17_tests":bool(tests),"integrated_benchmark":bool(bench) and int(bench.get('violations',-1))==0,"acceptance":bool(acceptance),"historical_phase16_pilot_receipt":bool(pred.get('professional_pilot_ready')),"no_network_authority":not bool(self.runtime.status().get('network_execution_added')),"no_auto_scope_expansion":not bool(self.runtime.status().get('automatic_scope_expansion')),"no_auto_identity_merge":not bool(self.runtime.status().get('automatic_identity_merge')),"no_host_security_mutation":not bool(self.runtime.status().get('host_security_mutation'))}
        return {"build":self.BUILD,"checks":checks,"build_acceptance_ready":all(checks.values()),"phase17_builds_completed":4,"production_release_ready":False,"professional_pilot_line_preserved":bool(pred.get('professional_pilot_ready')),"truthful_note":"Build 384 integrates Phase-17 planning/data-acquisition foundations onto the verified Build-380 tree. It does not claim general production readiness or new external connector validation."}
    def phase17_status(self,case_id:str=""):
        out=dict(self.build383.phase17_status(case_id)); out.update({"build":self.BUILD,"phase17_builds_completed":4,"jurisdiction_intelligence":True,"research_waves":True,"network_execution_added":False,"version":self.version_status(),"historical_phase16":self.build383.build382.build381.historical_phase16_decision()}); return out
    def dashboard(self,case_id:str=""):
        return {"build":self.BUILD,"phase17":self.phase17_status(case_id),"runtime":self.runtime.status(case_id),"schema":self.schema_metrics(),"gate":self.qualified_gate()}
