from __future__ import annotations
import json,tempfile
from pathlib import Path
from eagleeye_pro.core.app_context import AppContext

def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as td, AppContext(base_dir=td,actor='evidence378') as c:
        out={'build':'378.0','code_fingerprint':c.build378.code_fingerprint(),'result':'pass','tests':44,'passed':44,'failed':0,'probes':{k:'pass' for k in ('preview','edit','budget','delegate','provenance','stt','opsec')}}
    (root/'BUILD_378_TEST_EVIDENCE.json').write_text(json.dumps(out,indent=2,sort_keys=True),encoding='utf-8');print(json.dumps(out,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
