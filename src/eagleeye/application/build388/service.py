from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class Build388GovernedResearchWavesService:
    BUILD = '388.0'
    PACKAGE = '388.0.0'
    POLICY = 'phase17.governed-research-wave-build.v388'

    def __init__(self, db: Any, audit: Any, *, build387: Any, waves388: Any, install_dir: Any, actor: str = 'local-analyst') -> None:
        self.db = db; self.audit = audit; self.build387 = build387; self.waves388 = waves388; self.install_dir = Path(install_dir); self.actor = actor

    def __getattr__(self, name: str):
        if name.startswith('_'): raise AttributeError(name)
        value = getattr(self.build387, name, None)
        if value is None: raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            'eagleeye_pro/phase17/research_wave_execution388.py','eagleeye_pro/phase17/controlled_executor387.py','eagleeye_pro/core/app_context.py',
            'src/eagleeye/application/build388/service.py','src/eagleeye/interfaces/web/app388.py','src/eagleeye/interfaces/web/server.py',
            'eagleeye_pro/version.py','pyproject.toml','tests/test_build388_integrated.py','EAGLEEYE_ACCEPTANCE_BUILD_388_0.py','tools/benchmark_build388.py',
        )

    def code_fingerprint(self) -> str:
        h=hashlib.sha256()
        for rel in self._fingerprint_paths():
            p=self.install_dir/rel; h.update(rel.encode()); h.update(b'\0'); h.update(p.read_bytes() if p.is_file() else b'<missing>'); h.update(b'\0')
        return h.hexdigest()

    def version_status(self) -> dict[str, Any]:
        vt=(self.install_dir/'eagleeye_pro/version.py').read_text(encoding='utf-8'); pt=(self.install_dir/'pyproject.toml').read_text(encoding='utf-8')
        def g(pattern,text):
            m=re.search(pattern,text,re.M); return m.group(1) if m else 'unknown'
        runtime=g(r'^BUILD\s*=\s*["\']([^"\']+)',vt); schema=g(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt); package=g(r'^version\s*=\s*["\']([^"\']+)',pt)
        return {'runtime_build':runtime,'schema_version':schema,'package_version':package,'coherent':runtime==schema==self.BUILD and package==self.PACKAGE}

    def schema_metrics(self) -> dict[str, Any]:
        _=self.waves388.status(); rows=self.db.all("SELECT type,COUNT(*) c FROM sqlite_master WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%' GROUP BY type"); counts={r['type']:int(r['c']) for r in rows}
        integrity=str((self.db.one('PRAGMA integrity_check') or {}).get('integrity_check') or 'unknown'); present={r['name'] for r in self.db.all("SELECT name FROM sqlite_master WHERE type='table'")}
        req={'research_wave_session_388','research_wave_binding_388','research_wave_result_388'}
        return {'tables':counts.get('table',0),'indexes':counts.get('index',0),'triggers':counts.get('trigger',0),'views':counts.get('view',0),'integrity_check':integrity,'build388_tables_present':req.issubset(present),'within_phase17_gate':counts.get('table',0)<205 and counts.get('index',0)<350 and integrity=='ok' and req.issubset(present)}

    def _evidence(self, filename: str) -> dict[str, Any]:
        value=_read_json(self.install_dir/filename)
        return value if value.get('build')==self.BUILD and value.get('code_fingerprint')==self.code_fingerprint() and value.get('result')=='pass' else {}

    def historical_build387_receipt(self) -> dict[str, Any]:
        release=_read_json(self.install_dir/'RELEASE_MANIFEST_BUILD_387_0.json'); acceptance=_read_json(self.install_dir/'ACCEPTANCE_RESULTS_BUILD_387_0.json')
        valid=(release.get('build')=='387.0' and release.get('production_release_ready') is False and int((release.get('regression') or {}).get('functional_regressions',-1))==0 and (release.get('acceptance') or {}).get('result')=='pass' and acceptance.get('build')=='387.0' and acceptance.get('result')=='pass' and acceptance.get('code_fingerprint')==release.get('code_fingerprint'))
        return {'build':'387.0','valid':bool(valid),'code_fingerprint':release.get('code_fingerprint',''),'production_release_ready':False}

    def start_wave_session(self, **kwargs: Any) -> dict[str, Any]: return self.waves388.start_session(**kwargs)
    def attach_wave_dispatch(self, **kwargs: Any) -> dict[str, Any]: return self.waves388.attach_dispatch(**kwargs)
    def reconcile_wave_session(self, **kwargs: Any) -> dict[str, Any]: return self.waves388.reconcile(**kwargs)
    def advance_wave_session(self, **kwargs: Any) -> dict[str, Any]: return self.waves388.advance(**kwargs)
    def wave_session(self, **kwargs: Any) -> dict[str, Any]: return self.waves388.session(**kwargs)
    def verify_wave_session(self, **kwargs: Any) -> dict[str, Any]: return self.waves388.verify_session(**kwargs)

    def phase17_status(self, case_id: str='') -> dict[str, Any]:
        out=dict(self.build387.phase17_status(case_id)); out.update({'build':self.BUILD,'phase17_builds_completed':8,'governed_research_waves':True,'coverage_feedback':True,'artifact_provenance_feedback':True,'automatic_go_issuance':False,'automatic_live_confirmation':False,'automatic_worker_claim':False,'automatic_evidence_promotion':False,'wave_execution':self.waves388.status()}); return out

    def qualified_gate(self) -> dict[str, Any]:
        version=self.version_status(); schema=self.schema_metrics(); tests=self._evidence('BUILD_388_TEST_EVIDENCE.json'); benchmark=self._evidence('BENCHMARK_BUILD_388_RESEARCH_WAVES.json'); acceptance=self._evidence('ACCEPTANCE_RESULTS_BUILD_388_0.json'); pred=self.historical_build387_receipt(); status=self.waves388.status()
        checks={'version_coherent':bool(version['coherent']),'schema_integrity':bool(schema['within_phase17_gate']),'phase17_predecessor_gate':bool(pred.get('valid')),'build388_tests':bool(tests),'build388_benchmark':bool(benchmark) and int(benchmark.get('violations',-1))==0,'build388_acceptance':bool(acceptance),'sequential_wave_governance':bool(status.get('sequential_wave_governance')),'coverage_feedback':bool(status.get('coverage_feedback')),'no_auto_go':not bool(status.get('automatic_go_issuance')),'no_auto_live':not bool(status.get('automatic_live_confirmation')),'no_auto_worker_claim':not bool(status.get('automatic_worker_claim')),'no_direct_fetch':not bool(status.get('direct_network_fetch')),'no_auto_evidence_promotion':not bool(status.get('automatic_evidence_promotion')),'no_auto_scope_expansion':not bool(status.get('automatic_scope_expansion'))}
        return {'build':self.BUILD,'checks':checks,'build_acceptance_ready':all(checks.values()),'phase17_builds_completed':8,'production_release_ready':False,'professional_pilot_line_preserved':bool(pred.get('valid')),'truthful_note':'Build 388 governs sequential research-wave continuation from completed Build-387 dispatches. It observes worker results and artifacts, feeds evidence-linked coverage, and requires explicit human advance before another GO/LIVE cycle. It does not auto-issue GO, auto-confirm LIVE, claim workers, fetch networks, or auto-promote raw artifacts to Evidence Vault evidence.'}

    def dashboard(self, case_id: str='') -> dict[str, Any]: return {'build':self.BUILD,'phase17':self.phase17_status(case_id),'wave_execution':self.waves388.status(),'schema':self.schema_metrics(),'gate':self.qualified_gate()}
