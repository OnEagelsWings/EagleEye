from __future__ import annotations
import hashlib, json, re
from pathlib import Path


def _read(path):
    try:
        v=json.loads(Path(path).read_text(encoding='utf-8')); return v if isinstance(v,dict) else {}
    except Exception:return {}


class Build397ArgumentativeAnalystService:
    BUILD='397.0'; PACKAGE='397.0.0'; POLICY='phase17.argumentative-ai-analyst.v397'
    def __init__(self,db,audit,*,build396,analyst397,install_dir,actor='local-analyst'):
        self.db=db; self.audit=audit; self.build396=build396; self.analyst397=analyst397; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,n):
        if n.startswith('_'): raise AttributeError(n)
        v=getattr(self.build396,n,None)
        if v is None: raise AttributeError(n)
        return v
    def _fingerprint_paths(self):
        return ('eagleeye_pro/phase17/argumentative_analyst397.py','eagleeye_pro/phase17/__init__.py','eagleeye_pro/core/app_context.py','src/eagleeye/application/build397/service.py','src/eagleeye/interfaces/web/app397.py','src/eagleeye/interfaces/web/server.py','src/eagleeye/crawler/engine.py','src/eagleeye/crawler/frontier.py','EAGLEEYE_PRO_397_0.py','START_EAGLEEYE_PRO.bat','START_EAGLEEYE_PRO.sh','eagleeye_pro/version.py','pyproject.toml','tests/test_build397_integrated.py','EAGLEEYE_ACCEPTANCE_BUILD_397_0.py','tools/benchmark_build397.py')
    def code_fingerprint(self):
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel; h.update(rel.encode());h.update(b'\0');h.update(p.read_bytes() if p.is_file() else b'<missing>');h.update(b'\0')
        return h.hexdigest()
    def version_status(self):
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(); pt=(self.install_dir/'pyproject.toml').read_text(); g=lambda p,t:(re.search(p,t,re.M).group(1) if re.search(p,t,re.M) else 'unknown'); r=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt); s=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); p=g(r'^version\s*=\s*["\']([^"\']+)',pt); return {'runtime_build':r,'schema_version':s,'package_version':p,'coherent':r==s==self.BUILD and p==self.PACKAGE}
    def schema_metrics(self):
        _=self.analyst397.status(); rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type"); c={r['type']:int(r['c']) for r in rows}; integ=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown'); req={'analyst_assessment_397','analyst_citation_397','analyst_recommendation_397','analyst_recommendation_review_397'}; present={r['name'] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}; return {'tables':c.get('table',0),'indexes':c.get('index',0),'triggers':c.get('trigger',0),'views':c.get('view',0),'integrity_check':integ,'build397_tables_present':req.issubset(present),'within_phase17_gate':c.get('table',0)<330 and c.get('index',0)<540 and integ=='ok' and req.issubset(present)}
    def _evidence(self,filename):
        v=_read(self.install_dir/filename); return v if v.get('build')==self.BUILD and v.get('code_fingerprint')==self.code_fingerprint() and v.get('result')=='pass' else {}
    def historical_build396_receipt(self):
        r=_read(self.install_dir/'RELEASE_MANIFEST_BUILD_396_0.json'); valid=r.get('build')=='396.0' and r.get('production_release_ready') is False and int((r.get('regression') or {}).get('functional_regressions',-1))==0; return {'build':'396.0','valid':bool(valid),'code_fingerprint':r.get('code_fingerprint',''),'production_release_ready':False}
    def assess_argumentation(self,**k): return self.analyst397.assess(**k)
    def analyst_assessment(self,**k): return self.analyst397.assessment(**k)
    def propose_analyst_recommendation(self,**k): return self.analyst397.propose_recommendation(**k)
    def review_analyst_recommendation(self,**k): return self.analyst397.review_recommendation(**k)
    def analyst_recommendation(self,**k): return self.analyst397.recommendation(**k)
    def phase17_status(self,case_id=''):
        o=dict(self.build396.phase17_status(case_id)); o.update({'build':self.BUILD,'phase17_builds_completed':17,'argumentative_ai_analyst':True,'robots_parser_hardened':True,'robots_fail_closed':True,'precise_evidence_citations':True,'explicit_stop_decisions':True,'automatic_active_state_mutation':False,'automatic_go_issuance':False,'execution_authority':False,'truth_probability':False,'analyst':self.analyst397.status()}); return o
    def qualified_gate(self):
        v=self.version_status(); s=self.schema_metrics(); pred=self.historical_build396_receipt(); st=self.analyst397.status(); tests=self._evidence('BUILD_397_TEST_EVIDENCE.json'); bench=self._evidence('BENCHMARK_BUILD_397_ANALYST.json'); acc=self._evidence('ACCEPTANCE_RESULTS_BUILD_397_0.json'); checks={'version_coherent':v['coherent'],'schema_integrity':s['within_phase17_gate'],'phase17_predecessor_gate':pred['valid'],'build397_tests':bool(tests),'build397_benchmark':bool(bench) and int(bench.get('violations',-1))==0,'build397_acceptance':bool(acc),'precise_evidence_citations':st['precise_evidence_citations'],'source_independence_aware':st['source_independence_aware'],'support_counterevidence_separated':st['support_counterevidence_separated'],'explicit_stop_decisions':st['explicit_stop_decisions'],'review_required_recommendations':st['review_required_recommendations'],'no_active_state_auto_mutation':not st['automatic_upstream_mutation'],'no_auto_evidence_promotion':not st['automatic_evidence_promotion'],'no_auto_go':not st['automatic_go_issuance'],'no_live_confirmation':not st['automatic_live_confirmation'],'no_truth_probability':not st['truth_probability'],'no_auto_truth':not st['automatic_truth_acceptance'],'no_direct_fetch':not st['direct_network_fetch'],'no_execution_authority':not st['execution_authority']}; return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'phase17_builds_completed':17,'production_release_ready':False,'professional_pilot_line_preserved':pred['valid']}
