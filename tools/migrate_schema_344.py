from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for p in (ROOT,ROOT/'src'):
 if str(p) not in sys.path:sys.path.insert(0,str(p))
from eagleeye.infrastructure.schema_v1.migration import migrate_legacy_database,restore_backup
def main():
 ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest='cmd',required=True);m=sub.add_parser('migrate');m.add_argument('source',type=Path);m.add_argument('destination',type=Path);m.add_argument('--backup',type=Path);m.add_argument('--report',type=Path);r=sub.add_parser('restore');r.add_argument('backup',type=Path);r.add_argument('target',type=Path);ns=ap.parse_args();out=migrate_legacy_database(ns.source,ns.destination,backup_path=ns.backup,report_path=ns.report) if ns.cmd=='migrate' else restore_backup(ns.backup,ns.target);print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
