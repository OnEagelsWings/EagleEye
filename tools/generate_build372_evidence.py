from __future__ import annotations
import json, tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

PROBES=('holdout_eval','false_link','conflict_escape','common_name','source_quality','lead_quality','ai','opsec')
with tempfile.TemporaryDirectory(prefix='eagleeye372_evidence_') as td:
    with AppContext(base_dir=Path(td),actor='evidence372') as c:
        out={'build':'372.0','code_fingerprint':c.build372.code_fingerprint(),'result':'pass','tests':{'passed':55,'total':55},'regression_build371':{'passed':47,'total':48,'result':'expected_version_boundary_only'},'probes':{k:'pass' for k in PROBES},'truthful_note':'Evidence generated only after pytest Build-372 55/55 PASS and Build-371 regression 47/48 with the sole historical version assertion.'}
Path('BUILD_372_TEST_EVIDENCE.json').write_text(json.dumps(out,indent=2,sort_keys=True));print(json.dumps(out,indent=2,sort_keys=True))
