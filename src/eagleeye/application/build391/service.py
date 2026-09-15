from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value=json.loads(path.read_text(encoding='utf-8')); return value if isinstance(value,dict) else {}
    except Exception: return {}


class Build391AIInvestigationSynthesisService:
    BUILD='391.0'; PACKAGE='391.0.0'; POLICY='phase17.ai-investigation-synthesis-build.v391'
    def __init__(self,db:Any,audit:Any,*,build390:Any,synthesis391:Any,install_dir:Any,actor:str='local-analyst')->None:
        self.db=db; self.audit=audit; self.build390=build390; self.synthesis391=synthesis391; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith('_'): raise AttributeError(name)
        value=getattr(self.build390,name,None)
        if value is None: raise AttributeError(name)
        return value
    def _fingerprint_paths(self)->tuple[str,...]:
        return ('eagleeye_pro/phase17/investigation_synthesis391.py','eagleeye_pro/phase17/evidence_review390.py','eagleeye_pro/core/app_context.py','src/eagleeye/application/build391/service.py','src/eagleeye/interfaces/web/app391.py','src/eagleeye/interfaces/web/server.py','eagleeye_pro/version.py','pyproject.toml','tests/test_build391_integrated.py','EAGLEEYE_ACCEPTANCE_BUILD_391_0.py','tools/benchmark_build391.py')
    def code_fingerprint(self)->str:
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel; h.update(rel.encode()); h.update(b'\0'); h.update(p.read_bytes() if p.is_file() else b'<missing>'); h.update(b'\0')
        return h.hexdigest()
    def version_status(self)->dict[str,Any]:
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(encoding='utf-8'); pt=(self.install_dir/'pyproject.toml').read_text(encoding='utf-8')
        def g(pattern,text):
            m=re.search(pattern,text,re.M); return m.group(1) if m else 'unknown'
        runtime=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=g(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}
    def schema_metrics(self)->dict[str,Any]:
        _=self.synthesis391.status(); rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type"); counts={r['type']:int(r['c']) for r in rows}; integrity=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown'); present={r['name'] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}; req={'investigation_claim_391','investigation_claim_candidate_391','investigation_claim_review_391','investigation_hypothesis_391','hypothesis_claim_link_391','investigation_hypothesis_review_391','kernel_synthesis_bridge_391','synthesis_snapshot_391'}
        return {'tables':counts.get('table',0),'indexes':counts.get('index',0),'triggers':counts.get('trigger',0),'views':counts.get('view',0),'integrity_check':integrity,'build391_tables_present':req.issubset(present),'within_phase17_gate':counts.get('table',0)<230 and counts.get('index',0)<400 and integrity=='ok' and req.issubset(present)}
    def _evidence(self,filename:str)->dict[str,Any]:
        value=_read_json(self.install_dir/filename); return value if value.get('build')==self.BUILD and value.get('code_fingerprint')==self.code_fingerprint() and value.get('result')=='pass' else {}
    def historical_build390_receipt(self)->dict[str,Any]:
        release=_read_json(self.install_dir/'RELEASE_MANIFEST_BUILD_390_0.json'); acceptance=_read_json(self.install_dir/'ACCEPTANCE_RESULTS_BUILD_390_0.json'); valid=(release.get('build')=='390.0' and release.get('production_release_ready') is False and int((release.get('regression') or {}).get('functional_regressions',-1))==0 and (release.get('acceptance') or {}).get('result')=='pass' and acceptance.get('build')=='390.0' and acceptance.get('result')=='pass' and acceptance.get('code_fingerprint')==release.get('code_fingerprint'))
        return {'build':'390.0','valid':bool(valid),'code_fingerprint':release.get('code_fingerprint',''),'production_release_ready':False}
    def synthesize_corroboration_review(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.synthesize_review(**kwargs)
    def synthesize_case(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.synthesize_case(**kwargs)
    def synthesis_claim(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.claim(**kwargs)
    def review_synthesis_claim(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.review_claim(**kwargs)
    def propose_hypothesis(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.propose_hypothesis(**kwargs)
    def synthesis_hypothesis(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.hypothesis(**kwargs)
    def review_synthesis_hypothesis(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.review_hypothesis(**kwargs)
    def admit_claim_to_kernel(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.admit_claim_to_kernel(**kwargs)
    def admit_hypothesis_to_kernel(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.admit_hypothesis_to_kernel(**kwargs)
    def ai_investigation_synthesis_feed(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.ai_synthesis_feed(**kwargs)
    def create_synthesis_snapshot(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.create_snapshot(**kwargs)
    def verify_synthesis_claim(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.verify_claim(**kwargs)
    def verify_synthesis_hypothesis(self,**kwargs:Any)->dict[str,Any]: return self.synthesis391.verify_hypothesis(**kwargs)
    def phase17_status(self,case_id:str='')->dict[str,Any]:
        out=dict(self.build390.phase17_status(case_id)); out.update({'build':self.BUILD,'phase17_builds_completed':11,'ai_investigation_synthesis':True,'candidate_claims':True,'counterevidence_preserved':True,'hypothesis_not_fact':True,'investigation_kernel_notebook_bridge':True,'legacy_kernel_probability_path_used':False,'automatic_truth_acceptance':False,'truth_probability':False,'synthesis':self.synthesis391.status()}); return out
    def qualified_gate(self)->dict[str,Any]:
        version=self.version_status(); schema=self.schema_metrics(); tests=self._evidence('BUILD_391_TEST_EVIDENCE.json'); bench=self._evidence('BENCHMARK_BUILD_391_SYNTHESIS.json'); acc=self._evidence('ACCEPTANCE_RESULTS_BUILD_391_0.json'); pred=self.historical_build390_receipt(); status=self.synthesis391.status()
        checks={'version_coherent':bool(version['coherent']),'schema_integrity':bool(schema['within_phase17_gate']),'phase17_predecessor_gate':bool(pred.get('valid')),'build391_tests':bool(tests),'build391_benchmark':bool(bench) and int(bench.get('violations',-1))==0,'build391_acceptance':bool(acc),'candidate_claim_synthesis':bool(status['candidate_claim_synthesis']),'counterevidence_preserved':bool(status['counterevidence_preserved']),'hypothesis_proposals':bool(status['hypothesis_proposals']),'kernel_notebook_bridge':bool(status['investigation_kernel_notebook_bridge']),'legacy_probability_path_unused':not bool(status['legacy_kernel_probability_path_used']),'no_auto_truth_acceptance':not bool(status['automatic_truth_acceptance']),'no_truth_probability':not bool(status['truth_probability']),'no_auto_claim_acceptance':not bool(status['automatic_claim_acceptance']),'no_auto_evidence_promotion':not bool(status['automatic_evidence_promotion']),'no_direct_fetch':not bool(status['direct_network_fetch'])}
        return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'phase17_builds_completed':11,'production_release_ready':False,'professional_pilot_line_preserved':bool(pred.get('valid')),'truthful_note':'Build 391 synthesizes finalized source-independent corroboration reviews into candidate claims, preserves counterevidence, supports review-only hypotheses and mirrors reviewed analytical objects into Investigation Kernel notebook entries. It does not declare facts, calculate truth probability, invoke the legacy kernel confidence path, promote evidence automatically, merge identities, or execute network research.'}
    def dashboard(self,case_id:str='')->dict[str,Any]: return {'build':self.BUILD,'phase17':self.phase17_status(case_id),'synthesis':self.synthesis391.status(),'schema':self.schema_metrics(),'gate':self.qualified_gate()}
