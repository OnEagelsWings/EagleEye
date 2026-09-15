from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value=json.loads(path.read_text(encoding='utf-8')); return value if isinstance(value,dict) else {}
    except Exception:
        return {}


class Build392CaseReasoningWorkspaceService:
    BUILD='392.0'; PACKAGE='392.0.0'; POLICY='phase17.case-reasoning-workspace-build.v392'
    def __init__(self,db:Any,audit:Any,*,build391:Any,reasoning392:Any,install_dir:Any,actor:str='local-analyst')->None:
        self.db=db; self.audit=audit; self.build391=build391; self.reasoning392=reasoning392; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith('_'): raise AttributeError(name)
        value=getattr(self.build391,name,None)
        if value is None: raise AttributeError(name)
        return value
    def _fingerprint_paths(self)->tuple[str,...]:
        return (
            'eagleeye_pro/phase17/case_reasoning392.py','eagleeye_pro/phase17/investigation_synthesis391.py',
            'eagleeye_pro/core/app_context.py','src/eagleeye/application/build392/service.py','src/eagleeye/interfaces/web/app392.py',
            'src/eagleeye/interfaces/web/server.py','EAGLEEYE_PRO_392_0.py','START_EAGLEEYE_PRO.bat','START_EAGLEEYE_PRO.sh','eagleeye_pro/version.py','pyproject.toml','tests/test_build392_integrated.py',
            'EAGLEEYE_ACCEPTANCE_BUILD_392_0.py','tools/benchmark_build392.py'
        )
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
        _=self.reasoning392.status(); rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type"); counts={r['type']:int(r['c']) for r in rows}; integrity=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown'); present={r['name'] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}; req={'case_reasoning_workspace_392','reasoning_issue_392','reasoning_argument_392','reasoning_plan_392','reasoning_plan_action_392','reasoning_plan_review_392','reasoning_kernel_bridge_392'}
        return {'tables':counts.get('table',0),'indexes':counts.get('index',0),'triggers':counts.get('trigger',0),'views':counts.get('view',0),'integrity_check':integrity,'build392_tables_present':req.issubset(present),'within_phase17_gate':counts.get('table',0)<250 and counts.get('index',0)<420 and integrity=='ok' and req.issubset(present)}
    def _evidence(self,filename:str)->dict[str,Any]:
        value=_read_json(self.install_dir/filename); return value if value.get('build')==self.BUILD and value.get('code_fingerprint')==self.code_fingerprint() and value.get('result')=='pass' else {}
    def historical_build391_receipt(self)->dict[str,Any]:
        release=_read_json(self.install_dir/'RELEASE_MANIFEST_BUILD_391_0.json'); acceptance=_read_json(self.install_dir/'ACCEPTANCE_RESULTS_BUILD_391_0.json'); valid=(release.get('build')=='391.0' and release.get('production_release_ready') is False and int((release.get('regression') or {}).get('functional_regressions',-1))==0 and (release.get('acceptance') or {}).get('result')=='pass' and acceptance.get('build')=='391.0' and acceptance.get('result')=='pass' and acceptance.get('code_fingerprint')==release.get('code_fingerprint'))
        return {'build':'391.0','valid':bool(valid),'code_fingerprint':release.get('code_fingerprint',''),'production_release_ready':False}
    def create_case_reasoning_workspace(self,**kwargs:Any)->dict[str,Any]: return self.reasoning392.create_workspace(**kwargs)
    def case_reasoning_workspace(self,**kwargs:Any)->dict[str,Any]: return self.reasoning392.workspace(**kwargs)
    def propose_next_investigation_plan(self,**kwargs:Any)->dict[str,Any]: return self.reasoning392.propose_plan(**kwargs)
    def reasoning_plan(self,**kwargs:Any)->dict[str,Any]: return self.reasoning392.plan(**kwargs)
    def review_reasoning_plan(self,**kwargs:Any)->dict[str,Any]: return self.reasoning392.review_plan(**kwargs)
    def admit_reasoning_plan_to_kernel(self,**kwargs:Any)->dict[str,Any]: return self.reasoning392.admit_plan_to_kernel(**kwargs)
    def ai_case_reasoning_feed(self,**kwargs:Any)->dict[str,Any]: return self.reasoning392.ai_reasoning_feed(**kwargs)
    def verify_case_reasoning_workspace(self,**kwargs:Any)->dict[str,Any]: return self.reasoning392.verify_workspace(**kwargs)
    def verify_reasoning_plan(self,**kwargs:Any)->dict[str,Any]: return self.reasoning392.verify_plan(**kwargs)
    def phase17_status(self,case_id:str='')->dict[str,Any]:
        out=dict(self.build391.phase17_status(case_id)); out.update({'build':self.BUILD,'phase17_builds_completed':12,'case_reasoning_workspace':True,'argument_graph':True,'research_gap_reasoning':True,'next_investigation_plan_proposals':True,'human_plan_review_required':True,'automatic_go_issuance':False,'execution_authority':False,'truth_probability':False,'reasoning':self.reasoning392.status()}); return out
    def qualified_gate(self)->dict[str,Any]:
        version=self.version_status(); schema=self.schema_metrics(); tests=self._evidence('BUILD_392_TEST_EVIDENCE.json'); bench=self._evidence('BENCHMARK_BUILD_392_REASONING.json'); acc=self._evidence('ACCEPTANCE_RESULTS_BUILD_392_0.json'); pred=self.historical_build391_receipt(); status=self.reasoning392.status()
        checks={
            'version_coherent':bool(version['coherent']),'schema_integrity':bool(schema['within_phase17_gate']),'phase17_predecessor_gate':bool(pred.get('valid')),
            'build392_tests':bool(tests),'build392_benchmark':bool(bench) and int(bench.get('violations',-1))==0,'build392_acceptance':bool(acc),
            'case_reasoning_workspace':bool(status['case_reasoning_workspace']),'argument_graph':bool(status['argument_graph']),'research_gap_reasoning':bool(status['research_gap_reasoning']),
            'next_plan_proposals':bool(status['next_investigation_plan_proposals']),'human_plan_review_required':bool(status['human_plan_review_required']),
            'kernel_notebook_plan_bridge':bool(status['kernel_notebook_plan_bridge']),'epistemic_layers_preserved':bool(status['epistemic_layers_preserved']),
            'no_truth_probability':not bool(status['truth_probability']),'no_auto_truth_acceptance':not bool(status['automatic_truth_acceptance']),
            'no_auto_evidence_promotion':not bool(status['automatic_evidence_promotion']),'no_auto_go':not bool(status['automatic_go_issuance']),
            'no_execution_authority':not bool(status['execution_authority']),'no_direct_fetch':not bool(status['direct_network_fetch']),
        }
        return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'phase17_builds_completed':12,'production_release_ready':False,'professional_pilot_line_preserved':bool(pred.get('valid')),'truthful_note':'Build 392 creates a deterministic case reasoning workspace over reviewed Phase-17 claims, counterevidence, hypotheses and research gaps. It can propose and human-review a next-investigation plan and mirror an approved plan into the Investigation Kernel notebook. It does not assign truth probability, grant GO, execute research, promote evidence, merge identities, or create network requests.'}
    def dashboard(self,case_id:str='')->dict[str,Any]: return {'build':self.BUILD,'phase17':self.phase17_status(case_id),'reasoning':self.reasoning392.status(),'schema':self.schema_metrics(),'gate':self.qualified_gate()}
