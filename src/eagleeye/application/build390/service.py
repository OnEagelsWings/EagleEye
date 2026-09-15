from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value=json.loads(path.read_text(encoding='utf-8')); return value if isinstance(value,dict) else {}
    except Exception: return {}


class Build390EvidenceReviewCorroborationService:
    BUILD='390.0'; PACKAGE='390.0.0'; POLICY='phase17.evidence-review-corroboration-build.v390'
    def __init__(self,db:Any,audit:Any,*,build389:Any,review390:Any,install_dir:Any,actor:str='local-analyst')->None:
        self.db=db; self.audit=audit; self.build389=build389; self.review390=review390; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith('_'): raise AttributeError(name)
        value=getattr(self.build389,name,None)
        if value is None: raise AttributeError(name)
        return value
    def _fingerprint_paths(self)->tuple[str,...]:
        return ('eagleeye_pro/phase17/evidence_review390.py','eagleeye_pro/phase17/result_intake389.py','eagleeye_pro/core/app_context.py','src/eagleeye/application/build390/service.py','src/eagleeye/interfaces/web/app390.py','src/eagleeye/interfaces/web/server.py','eagleeye_pro/version.py','pyproject.toml','tests/test_build390_integrated.py','EAGLEEYE_ACCEPTANCE_BUILD_390_0.py','tools/benchmark_build390.py')
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
        _=self.review390.status(); rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type"); counts={r['type']:int(r['c']) for r in rows}; integrity=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown'); present={r['name'] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}; req={'source_independence_profile_390','candidate_independence_review_390','corroboration_review_390','corroboration_link_390','corroboration_assessment_390'}
        return {'tables':counts.get('table',0),'indexes':counts.get('index',0),'triggers':counts.get('trigger',0),'views':counts.get('view',0),'integrity_check':integrity,'build390_tables_present':req.issubset(present),'within_phase17_gate':counts.get('table',0)<220 and counts.get('index',0)<380 and integrity=='ok' and req.issubset(present)}
    def _evidence(self,filename:str)->dict[str,Any]:
        value=_read_json(self.install_dir/filename); return value if value.get('build')==self.BUILD and value.get('code_fingerprint')==self.code_fingerprint() and value.get('result')=='pass' else {}
    def historical_build389_receipt(self)->dict[str,Any]:
        release=_read_json(self.install_dir/'RELEASE_MANIFEST_BUILD_389_0.json'); acceptance=_read_json(self.install_dir/'ACCEPTANCE_RESULTS_BUILD_389_0.json'); valid=(release.get('build')=='389.0' and release.get('production_release_ready') is False and int((release.get('regression') or {}).get('functional_regressions',-1))==0 and (release.get('acceptance') or {}).get('result')=='pass' and acceptance.get('build')=='389.0' and acceptance.get('result')=='pass' and acceptance.get('code_fingerprint')==release.get('code_fingerprint'))
        return {'build':'389.0','valid':bool(valid),'code_fingerprint':release.get('code_fingerprint',''),'production_release_ready':False}
    def source_independence_profiles(self)->list[dict[str,Any]]: return self.review390.source_profiles()
    def review_source_independence(self,**kwargs:Any)->dict[str,Any]: return self.review390.review_candidate_independence(**kwargs)
    def create_corroboration_review(self,**kwargs:Any)->dict[str,Any]: return self.review390.create_review(**kwargs)
    def assess_corroboration_review(self,**kwargs:Any)->dict[str,Any]: return self.review390.assess_review(**kwargs)
    def finalize_corroboration_review(self,**kwargs:Any)->dict[str,Any]: return self.review390.finalize_review(**kwargs)
    def corroboration_review(self,**kwargs:Any)->dict[str,Any]: return self.review390.review(**kwargs)
    def ai_corroboration_feed(self,**kwargs:Any)->dict[str,Any]: return self.review390.ai_review_feed(**kwargs)
    def verify_corroboration_assessment(self,**kwargs:Any)->dict[str,Any]: return self.review390.verify_assessment(**kwargs)
    def phase17_status(self,case_id:str='')->dict[str,Any]:
        out=dict(self.build389.phase17_status(case_id)); out.update({'build':self.BUILD,'phase17_builds_completed':10,'evidence_review_corroboration':True,'source_independence_grouping':True,'duplicate_mirror_aware':True,'automatic_truth_acceptance':False,'truth_probability':False,'automatic_evidence_promotion':False,'evidence_review':self.review390.status()}); return out
    def qualified_gate(self)->dict[str,Any]:
        version=self.version_status(); schema=self.schema_metrics(); tests=self._evidence('BUILD_390_TEST_EVIDENCE.json'); bench=self._evidence('BENCHMARK_BUILD_390_CORROBORATION.json'); acc=self._evidence('ACCEPTANCE_RESULTS_BUILD_390_0.json'); pred=self.historical_build389_receipt(); status=self.review390.status(); profiles=self.review390.source_profiles()
        archive=next((p for p in profiles if p.get('phase17_source_id')=='internet_archive.metadata'),{})
        checks={'version_coherent':bool(version['coherent']),'schema_integrity':bool(schema['within_phase17_gate']),'phase17_predecessor_gate':bool(pred.get('valid')),'build390_tests':bool(tests),'build390_benchmark':bool(bench) and int(bench.get('violations',-1))==0,'build390_acceptance':bool(acc),'source_independence_profiles':bool(status['source_independence_profiles']),'duplicate_aware':bool(status['duplicate_aware']),'mirror_aware':bool(status['mirror_aware']) and archive.get('countable_default') is False,'unknown_origin_fail_closed':bool(status['unknown_origin_fail_closed']),'no_auto_truth_acceptance':not bool(status['automatic_truth_acceptance']),'no_truth_probability':not bool(status['truth_probability']),'no_auto_evidence_promotion':not bool(status['automatic_evidence_promotion']),'no_auto_identity_merge':not bool(status['automatic_identity_merge']),'no_direct_fetch':not bool(status['direct_network_fetch'])}
        return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'phase17_builds_completed':10,'production_release_ready':False,'professional_pilot_line_preserved':bool(pred.get('valid')),'truthful_note':'Build 390 groups analyst-assigned candidate stances by reviewed/provisional source-independence origin. Raw hit counts, exact duplicates, mirrors and unresolved origins do not become extra independent support. Assessment states describe corroboration structure only; they never determine truth, assign truth probability, promote evidence automatically or merge identities.'}
    def dashboard(self,case_id:str='')->dict[str,Any]: return {'build':self.BUILD,'phase17':self.phase17_status(case_id),'evidence_review':self.review390.status(),'schema':self.schema_metrics(),'gate':self.qualified_gate()}
