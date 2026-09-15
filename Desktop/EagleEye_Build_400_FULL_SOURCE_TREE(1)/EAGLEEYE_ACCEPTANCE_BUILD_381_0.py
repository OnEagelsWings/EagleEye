#!/usr/bin/env python3
import json, os, subprocess, sys, tempfile
ROOT=os.path.dirname(os.path.abspath(__file__))
checks={}

def run(cmd):
    p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    return p.returncode==0,p.stdout,p.stderr

ok,out,err=run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_build381.py','-v'])
checks['build381_unit_tests']=ok
ok2,bout,berr=run([sys.executable,'tools/benchmark_build381.py'])
checks['benchmark']=ok2
if ok2:
    b=json.loads(bout)
    checks['benchmark_zero_violations']=b['violations']==0
    checks['benchmark_network_silent']=b['network_used'] is False
else:
    b={}
from pathlib import Path
text=Path('src/eagleeye/phase17/investigation_control381.py').read_text(encoding='utf-8')
checks['no_network_client_imports']=all(x not in text for x in ['import requests','import httpx','import urllib.request','import socket'])
checks['explicit_no_execution_authority']='execution_authority=False' in text
checks['explicit_no_scope_expansion']='scope_expansion_authority=False' in text
checks['source_review_required']='human_source_review_required' in text
checks['provenance_required']='provenance_required' in text
checks['base_fingerprint_bound']='0b367f97f28d33687ddbff6fb05b8652962a5f23aff1039145845c2cae32970d' in text
result={'build':'381.0','passed':sum(bool(v) for v in checks.values()),'total':len(checks),'checks':checks,
        'build_acceptance_ready':all(checks.values()),'result':'pass' if all(checks.values()) else 'fail',
        'integration_state':'overlay_only_until_full_build380_source_tree_is_available'}
print(json.dumps(result,indent=2,sort_keys=True))
sys.exit(0 if all(checks.values()) else 1)
