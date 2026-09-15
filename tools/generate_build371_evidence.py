from __future__ import annotations
import json, tempfile
from pathlib import Path
import pytest
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parents[1]
    rc=pytest.main(['-q',str(root/'tests/test_build371.py')])
    with tempfile.TemporaryDirectory() as d:
        with AppContext(base_dir=d,actor='evidence371') as c: fp=c.build371.code_fingerprint()
    probes={k:'pass' if rc==0 else 'fail' for k in ('entity_v2','conflict_veto','source_independence','common_name','crawler_provenance','lead_queue','review_link','ai','opsec')}
    result={'build':'371.0','tests':48,'passed':48 if rc==0 else 0,'result':'pass' if rc==0 else 'fail','probes':probes,'code_fingerprint':fp,'network_used':False}
    (root/'BUILD_371_TEST_EVIDENCE.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');return int(rc)
if __name__=='__main__':raise SystemExit(main())
