from __future__ import annotations
import argparse,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from eagleeye_pro.core.app_context import AppContext

def main():
    ap=argparse.ArgumentParser(description='Explicit Build-362 PostgreSQL live validation. DSN is read from EAGLEEYE_POSTGRES_DSN and never printed.')
    ap.add_argument('--base-dir',default=str(ROOT))
    args=ap.parse_args()
    if not os.getenv('EAGLEEYE_POSTGRES_DSN'):
        print(json.dumps({'build':'362.0','status':'not_run','reason':'EAGLEEYE_POSTGRES_DSN not configured','externally_validated':False},indent=2));return 2
    with AppContext(base_dir=Path(args.base_dir)) as c:
        result=c.build362.postgres_live_validation()
        safe={k:v for k,v in result.items() if 'dsn' not in k.casefold()}
        print(json.dumps(safe,indent=2,sort_keys=True,default=str));return 0 if result.get('status')=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
