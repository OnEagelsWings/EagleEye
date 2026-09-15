from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value=json.loads(path.read_text(encoding='utf-8')); return value if isinstance(value,dict) else {}
    except Exception:
        return {}


class Build393InvestigatorDialogueChallengeService:
    BUILD='393.0'; PACKAGE='393.0.0'; POLICY='phase17.investigator-dialogue-challenge-build.v393'
    def __init__(self,db:Any,audit:Any,*,build392:Any,dialogue393:Any,install_dir:Any,actor:str='local-analyst')->None:
        self.db=db; self.audit=audit; self.build392=build392; self.dialogue393=dialogue393; self.install_dir=Path(install_dir); self.actor=actor
    def __getattr__(self,name:str):
        if name.startswith('_'): raise AttributeError(name)
        value=getattr(self.build392,name,None)
        if value is None: raise AttributeError(name)
        return value
    def _fingerprint_paths(self)->tuple[str,...]:
        return (
            'eagleeye_pro/phase17/investigator_dialogue393.py','eagleeye_pro/phase17/case_reasoning392.py',
            'eagleeye_pro/core/app_context.py','src/eagleeye/application/build393/service.py','src/eagleeye/interfaces/web/app393.py',
            'src/eagleeye/interfaces/web/server.py','EAGLEEYE_PRO_393_0.py','START_EAGLEEYE_PRO.bat','START_EAGLEEYE_PRO.sh','eagleeye_pro/version.py','pyproject.toml','tests/test_build393_integrated.py',
            'EAGLEEYE_ACCEPTANCE_BUILD_393_0.py','tools/benchmark_build393.py'
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
        _=self.dialogue393.status(); rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type"); counts={r['type']:int(r['c']) for r in rows}; integrity=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown'); present={r['name'] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}; req={'investigator_dialogue_session_393','investigator_dialogue_turn_393','challenge_revision_proposal_393','challenge_revision_review_393','dialogue_kernel_bridge_393'}
        return {'tables':counts.get('table',0),'indexes':counts.get('index',0),'triggers':counts.get('trigger',0),'views':counts.get('view',0),'integrity_check':integrity,'build393_tables_present':req.issubset(present),'within_phase17_gate':counts.get('table',0)<270 and counts.get('index',0)<450 and integrity=='ok' and req.issubset(present)}
    def _evidence(self,filename:str)->dict[str,Any]:
        value=_read_json(self.install_dir/filename); return value if value.get('build')==self.BUILD and value.get('code_fingerprint')==self.code_fingerprint() and value.get('result')=='pass' else {}
    def historical_build392_receipt(self)->dict[str,Any]:
        release=_read_json(self.install_dir/'RELEASE_MANIFEST_BUILD_392_0.json'); acceptance=_read_json(self.install_dir/'ACCEPTANCE_RESULTS_BUILD_392_0.json'); valid=(release.get('build')=='392.0' and release.get('production_release_ready') is False and int((release.get('regression') or {}).get('functional_regressions',-1))==0 and (release.get('acceptance') or {}).get('result')=='pass' and acceptance.get('build')=='392.0' and acceptance.get('result')=='pass' and acceptance.get('code_fingerprint')==release.get('code_fingerprint'))
        return {'build':'392.0','valid':bool(valid),'code_fingerprint':release.get('code_fingerprint',''),'production_release_ready':False}
    def create_investigator_dialogue(self,**kwargs:Any)->dict[str,Any]: return self.dialogue393.create_session(**kwargs)
    def investigator_dialogue(self,**kwargs:Any)->dict[str,Any]: return self.dialogue393.session(**kwargs)
    def challenge_reasoning(self,**kwargs:Any)->dict[str,Any]: return self.dialogue393.challenge(**kwargs)
    def challenge_turn(self,**kwargs:Any)->dict[str,Any]: return self.dialogue393.turn(**kwargs)
    def review_challenge_proposal(self,**kwargs:Any)->dict[str,Any]: return self.dialogue393.review_proposal(**kwargs)
    def challenge_proposal(self,**kwargs:Any)->dict[str,Any]: return self.dialogue393.proposal(**kwargs)
    def admit_challenge_to_kernel(self,**kwargs:Any)->dict[str,Any]: return self.dialogue393.admit_turn_to_kernel(**kwargs)
    def ai_investigator_dialogue_feed(self,**kwargs:Any)->dict[str,Any]: return self.dialogue393.ai_dialogue_feed(**kwargs)
    def verify_investigator_dialogue(self,**kwargs:Any)->dict[str,Any]: return self.dialogue393.verify_session(**kwargs)
    def verify_challenge_turn(self,**kwargs:Any)->dict[str,Any]: return self.dialogue393.verify_turn(**kwargs)
    def verify_challenge_proposal(self,**kwargs:Any)->dict[str,Any]: return self.dialogue393.verify_proposal(**kwargs)
    def phase17_status(self,case_id:str='')->dict[str,Any]:
        out=dict(self.build392.phase17_status(case_id)); out.update({'build':self.BUILD,'phase17_builds_completed':13,'investigator_dialogue':True,'challenge_engine':True,'revision_proposals':True,'human_revision_review_required':True,'automatic_upstream_mutation':False,'automatic_go_issuance':False,'execution_authority':False,'truth_probability':False,'dialogue':self.dialogue393.status()}); return out
    def qualified_gate(self)->dict[str,Any]:
        version=self.version_status(); schema=self.schema_metrics(); tests=self._evidence('BUILD_393_TEST_EVIDENCE.json'); bench=self._evidence('BENCHMARK_BUILD_393_DIALOGUE.json'); acc=self._evidence('ACCEPTANCE_RESULTS_BUILD_393_0.json'); pred=self.historical_build392_receipt(); status=self.dialogue393.status()
        checks={
            'version_coherent':bool(version['coherent']),'schema_integrity':bool(schema['within_phase17_gate']),'phase17_predecessor_gate':bool(pred.get('valid')),
            'build393_tests':bool(tests),'build393_benchmark':bool(bench) and int(bench.get('violations',-1))==0,'build393_acceptance':bool(acc),
            'investigator_dialogue':bool(status['investigator_dialogue']),'challenge_engine':bool(status['challenge_engine']),'weakest_assumption':bool(status['weakest_assumption_challenge']),
            'counter_argument':bool(status['counter_argument_challenge']),'falsification':bool(status['falsification_challenge']),'blind_spot':bool(status['blind_spot_challenge']),
            'source_independence':bool(status['source_independence_challenge']),'plan_red_team':bool(status['plan_red_team']),'revision_proposals':bool(status['revision_proposals']),
            'human_revision_review_required':bool(status['human_revision_review_required']),'kernel_challenge_bridge':bool(status['kernel_notebook_challenge_bridge']),
            'no_truth_probability':not bool(status['truth_probability']),'no_auto_truth_acceptance':not bool(status['automatic_truth_acceptance']),
            'no_auto_upstream_mutation':not bool(status['automatic_upstream_mutation']),'no_auto_evidence_promotion':not bool(status['automatic_evidence_promotion']),
            'no_auto_go':not bool(status['automatic_go_issuance']),'no_execution_authority':not bool(status['execution_authority']),'no_direct_fetch':not bool(status['direct_network_fetch']),
        }
        return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'phase17_builds_completed':13,'production_release_ready':False,'professional_pilot_line_preserved':bool(pred.get('valid')),'truthful_note':'Build 393 adds a provenance-bound investigator dialogue and challenge layer over the Build-392 reasoning workspace. It can challenge weak assumptions, counterarguments, falsification needs, blind spots, source independence and plan sequencing, and can persist review-required revision proposals. It does not determine truth, assign probability, mutate claims/hypotheses/plans automatically, grant GO/LIVE authority, promote evidence, merge identities, or create network requests.'}
    def dashboard(self,case_id:str='')->dict[str,Any]: return {'build':self.BUILD,'phase17':self.phase17_status(case_id),'dialogue':self.dialogue393.status(),'schema':self.schema_metrics(),'gate':self.qualified_gate()}
