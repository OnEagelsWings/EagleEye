from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value=json.loads(path.read_text(encoding='utf-8')); return value if isinstance(value,dict) else {}
    except Exception: return {}


class Build389ResultIntakeEvidenceNormalizationService:
    BUILD='389.0'; PACKAGE='389.0.0'; POLICY='phase17.result-intake-evidence-normalization-build.v389'
    def __init__(self,db:Any,audit:Any,*,build388:Any,intake389:Any,install_dir:Any,actor:str='local-analyst')->None:
        self.db=db; self.audit=audit; self.build388=build388; self.intake389=intake389; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith('_'): raise AttributeError(name)
        value=getattr(self.build388,name,None)
        if value is None: raise AttributeError(name)
        return value
    def _fingerprint_paths(self)->tuple[str,...]:
        return ('eagleeye_pro/phase17/result_intake389.py','eagleeye_pro/phase17/research_wave_execution388.py','eagleeye_pro/core/app_context.py','src/eagleeye/application/build389/service.py','src/eagleeye/interfaces/web/app389.py','src/eagleeye/interfaces/web/server.py','eagleeye_pro/version.py','pyproject.toml','tests/test_build389_integrated.py','EAGLEEYE_ACCEPTANCE_BUILD_389_0.py','tools/benchmark_build389.py')
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
        _=self.intake389.status(); rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type"); counts={r['type']:int(r['c']) for r in rows}; integrity=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown'); present={r['name'] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}; req={'result_intake_batch_389','evidence_candidate_389','evidence_candidate_promotion_389'}
        return {'tables':counts.get('table',0),'indexes':counts.get('index',0),'triggers':counts.get('trigger',0),'views':counts.get('view',0),'integrity_check':integrity,'build389_tables_present':req.issubset(present),'within_phase17_gate':counts.get('table',0)<210 and counts.get('index',0)<360 and integrity=='ok' and req.issubset(present)}
    def _evidence(self,filename:str)->dict[str,Any]:
        value=_read_json(self.install_dir/filename); return value if value.get('build')==self.BUILD and value.get('code_fingerprint')==self.code_fingerprint() and value.get('result')=='pass' else {}
    def historical_build388_receipt(self)->dict[str,Any]:
        release=_read_json(self.install_dir/'RELEASE_MANIFEST_BUILD_388_0.json'); acceptance=_read_json(self.install_dir/'ACCEPTANCE_RESULTS_BUILD_388_0.json'); valid=(release.get('build')=='388.0' and release.get('production_release_ready') is False and int((release.get('regression') or {}).get('functional_regressions',-1))==0 and (release.get('acceptance') or {}).get('result')=='pass' and acceptance.get('build')=='388.0' and acceptance.get('result')=='pass' and acceptance.get('code_fingerprint')==release.get('code_fingerprint'))
        return {'build':'388.0','valid':bool(valid),'code_fingerprint':release.get('code_fingerprint',''),'production_release_ready':False}
    def normalize_wave_results(self,**kwargs:Any)->dict[str,Any]: return self.intake389.normalize_session(**kwargs)
    def evidence_candidates(self,**kwargs:Any)->list[dict[str,Any]]: return self.intake389.candidates(**kwargs)
    def ai_evidence_candidates(self,**kwargs:Any)->dict[str,Any]: return self.intake389.ai_candidate_feed(**kwargs)
    def promote_evidence_candidate(self,**kwargs:Any)->dict[str,Any]: return self.intake389.promote_candidate(**kwargs)
    def verify_evidence_candidate(self,**kwargs:Any)->dict[str,Any]: return self.intake389.verify_candidate(**kwargs)
    def phase17_status(self,case_id:str='')->dict[str,Any]:
        out=dict(self.build388.phase17_status(case_id)); out.update({'build':self.BUILD,'phase17_builds_completed':9,'result_intake_normalization':True,'evidence_candidate_pipeline':True,'ai_candidate_feed':True,'automatic_evidence_promotion':False,'automatic_truth_acceptance':False,'automatic_identity_merge':False,'result_intake':self.intake389.status()}); return out
    def qualified_gate(self)->dict[str,Any]:
        version=self.version_status(); schema=self.schema_metrics(); tests=self._evidence('BUILD_389_TEST_EVIDENCE.json'); bench=self._evidence('BENCHMARK_BUILD_389_RESULT_INTAKE.json'); acc=self._evidence('ACCEPTANCE_RESULTS_BUILD_389_0.json'); pred=self.historical_build388_receipt(); status=self.intake389.status(); checks={'version_coherent':bool(version['coherent']),'schema_integrity':bool(schema['within_phase17_gate']),'phase17_predecessor_gate':bool(pred.get('valid')),'build389_tests':bool(tests),'build389_benchmark':bool(bench) and int(bench.get('violations',-1))==0,'build389_acceptance':bool(acc),'normalization_active':bool(status['result_normalization']),'provenance_preserved':bool(status['raw_object_provenance_preserved']),'dedupe_without_source_collapse':bool(status['independent_source_observations_preserved']),'ai_candidate_feed':bool(status['ai_candidate_feed']),'no_auto_evidence_promotion':not bool(status['automatic_evidence_promotion']),'no_auto_truth_acceptance':not bool(status['automatic_truth_acceptance']),'no_auto_identity_merge':not bool(status['automatic_identity_merge']),'no_direct_fetch':not bool(status['direct_network_fetch'])}
        return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'phase17_builds_completed':9,'production_release_ready':False,'professional_pilot_line_preserved':bool(pred.get('valid')),'truthful_note':'Build 389 normalizes terminal crawler artifacts into provenance-bound review candidates using the existing Build-350 parser layer. Exact logical duplicates are linked without collapsing independent-source observations. AI receives candidate-only context. Explicit PROMOTE EVIDENCE copies a candidate into Evidence Vault with needs_review status; it does not create a verified fact or automatic evidence acceptance.'}
    def dashboard(self,case_id:str='')->dict[str,Any]: return {'build':self.BUILD,'phase17':self.phase17_status(case_id),'result_intake':self.intake389.status(),'schema':self.schema_metrics(),'gate':self.qualified_gate()}
