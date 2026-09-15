from __future__ import annotations
import hashlib,json,sqlite3,uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from eagleeye_pro.core.database import Database
from .schema import SCHEMA_BASELINE,ensure_phase15_schema_v1
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def sha256_file(path):
 h=hashlib.sha256(); f=open(path,'rb')
 try:
  for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
 finally:f.close()
 return h.hexdigest()
def _q(s):return '"'+str(s).replace('"','""')+'"'
def _objs(c,t,schema='main'):
 table='sqlite_master' if schema=='main' else f'{schema}.sqlite_master'; return [r[0] for r in c.execute(f"SELECT name FROM {table} WHERE type=? AND name NOT LIKE 'sqlite_%' ORDER BY name",(t,)).fetchall()]
def _cols(c,t,schema='main'):return [r[1] for r in c.execute(f"PRAGMA {schema}.table_info({_q(t)})").fetchall()]
def _count(c,t,schema='main'):
 try:return int(c.execute(f"SELECT COUNT(*) FROM {schema}.{_q(t)}").fetchone()[0])
 except sqlite3.DatabaseError:return -1
def database_metrics(path):
 p=Path(path); c=sqlite3.connect(str(p))
 try:
  d={t:len(_objs(c,t)) for t in ('table','index','trigger','view')}; d['page_count']=int(c.execute('PRAGMA page_count').fetchone()[0]); d['page_size']=int(c.execute('PRAGMA page_size').fetchone()[0]); d['logical_bytes']=d['page_count']*d['page_size']; d['file_bytes']=p.stat().st_size if p.exists() else 0; d['integrity_check']=str(c.execute('PRAGMA integrity_check').fetchone()[0]); return d
 finally:c.close()
def create_schema_baseline(path):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);db=Database(p)
 try:
  with db.bootstrap_lock():db.init_schema();ensure_phase15_schema_v1(db);db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
 finally:db.close()
 return database_metrics(p)
def consistent_backup(source_path,backup_path):
 s,b=Path(source_path),Path(backup_path);b.parent.mkdir(parents=True,exist_ok=True);b.unlink(missing_ok=True);src=sqlite3.connect(str(s));dst=sqlite3.connect(str(b))
 try:src.backup(dst);dst.commit()
 finally:dst.close();src.close()
 return {'path':str(b),'sha256':sha256_file(b),'metrics':database_metrics(b)}
def _copy_core(c):
 dst=set(_objs(c,'table'));src=set(_objs(c,'table','legacy'));special={'phase15_schema_meta','phase15_migration_runs','phase15_agent_tasks','phase15_agent_results','phase15_sources','phase15_source_review_events','phase15_search_runs','phase15_media_assets','phase15_object_links','phase15_security_events','phase15_dossier_releases'};copied=[];drops=[]
 for t in sorted(dst-special):
  if t not in src:continue
  dc=_cols(c,t);sc=_cols(c,t,'legacy');shared=[x for x in dc if x in sc]
  if not shared:continue
  cols=','.join(_q(x) for x in shared);before=_count(c,t);c.execute(f"INSERT OR IGNORE INTO main.{_q(t)} ({cols}) SELECT {cols} FROM legacy.{_q(t)}");after=_count(c,t);copied.append({'table':t,'source_rows':_count(c,t,'legacy'),'destination_rows':after,'rows_added':max(0,after-before),'columns':shared});lost=[x for x in sc if x not in dc]
  if lost:drops.append({'table':t,'legacy_only_columns':lost})
 return copied,drops
def _migrate_kernel(c):
 src=set(_objs(c,'table','legacy'));tasks=results=0
 if 'phase15_agent_tasks_343' in src:
  c.execute("INSERT OR IGNORE INTO phase15_agent_tasks(task_id,case_id,agent_role,action_class,requested_gateway,approval_state,contract_version,task_json,record_hash,created_at) SELECT task_id,case_id,agent_role,action_class,requested_gateway,approval_state,contract_version,task_json,record_hash,created_at FROM legacy.phase15_agent_tasks_343");tasks=_count(c,'phase15_agent_tasks')
 if 'phase15_agent_results_343' in src:
  c.execute("INSERT OR IGNORE INTO phase15_agent_results(result_id,task_id,status,gateway_used,contract_version,result_json,record_hash,created_at) SELECT result_id,task_id,status,gateway_used,contract_version,result_json,record_hash,created_at FROM legacy.phase15_agent_results_343");results=_count(c,'phase15_agent_results')
 return {'tasks':tasks,'results':results}
def _migrate_darknet(c):
 src=set(_objs(c,'table','legacy'));ns=nr=0
 if 'phase15_darknet_sources_342' in src:
  for r in c.execute("SELECT source_id,onion_host,display_name,source_class,jurisdiction,allowed_use,review_status,risk_class,created_by,created_at,updated_at,record_hash FROM legacy.phase15_darknet_sources_342").fetchall():
   prov=json.dumps({'migrated_from':'phase15_darknet_sources_342','original_source_id':r[0]},sort_keys=True,separators=(',',':'));c.execute("INSERT OR IGNORE INTO phase15_sources(source_id,source_kind,locator,display_name,source_class,jurisdiction,allowed_use,review_status,risk_class,provenance_json,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(r[0],'darknet_onion',r[1],r[2],r[3],r[4],r[5],r[6],r[7],prov,r[8],r[9],r[10],r[11]));ns=_count(c,'phase15_sources')
 if 'phase15_darknet_review_events_342' in src:c.execute("INSERT OR IGNORE INTO phase15_source_review_events(event_id,source_id,decision,rationale,reviewer,created_at,record_hash) SELECT event_id,source_id,decision,rationale,reviewer,created_at,record_hash FROM legacy.phase15_darknet_review_events_342");nr=_count(c,'phase15_source_review_events')
 return {'sources':ns,'review_events':nr}
def migrate_legacy_database(source_path,destination_path,*,source_build='343.0',backup_path=None,report_path=None):
 source,dest=Path(source_path),Path(destination_path)
 if not source.is_file():raise FileNotFoundError(source)
 if source.resolve()==dest.resolve():raise ValueError('source and destination must differ')
 backup=Path(backup_path) if backup_path else source.with_name(source.stem+'.pre344-backup.sqlite');report=Path(report_path) if report_path else dest.with_suffix(dest.suffix+'.migration-report.json');started=_now();mid='mig344_'+uuid.uuid4().hex[:16];sm=database_metrics(source);ss=sha256_file(source);bi=consistent_backup(source,backup);dest.unlink(missing_ok=True);create_schema_baseline(dest);c=sqlite3.connect(str(dest))
 try:
  c.execute('PRAGMA foreign_keys=OFF');c.execute('ATTACH DATABASE ? AS legacy',(str(backup),));c.execute('BEGIN IMMEDIATE');copied,drops=_copy_core(c);kernel=_migrate_kernel(c);dark=_migrate_darknet(c);src=set(_objs(c,'table','legacy'));dst=set(_objs(c,'table'));excluded={'phase15_agent_tasks_343','phase15_agent_results_343','phase15_darknet_sources_342','phase15_darknet_review_events_342','phase15_build342_state'};legacy=[{'table':t,'rows':_count(c,t,'legacy')} for t in sorted(src-dst-excluded)];details={'canonical_tables_copied':copied,'legacy_only_columns':drops,'phase15_kernel':kernel,'darknet':dark,'legacy_only_tables_retained_in_backup':legacy};c.execute("INSERT INTO phase15_migration_runs(migration_id,source_build,target_schema,source_path,source_sha256,backup_path,backup_sha256,report_path,status,started_at,completed_at,details_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(mid,source_build,SCHEMA_BASELINE,str(source),ss,str(backup),bi['sha256'],str(report),'completed',started,_now(),json.dumps(details,sort_keys=True,separators=(',',':'))));c.commit();c.execute('DETACH DATABASE legacy');c.execute('PRAGMA foreign_keys=ON');fk=c.execute('PRAGMA foreign_key_check').fetchall();integrity=str(c.execute('PRAGMA integrity_check').fetchone()[0]);c.commit()
 finally:c.close()
 dm=database_metrics(dest);out={'migration_id':mid,'source_build':source_build,'target_schema':SCHEMA_BASELINE,'source':{'path':str(source),'sha256':ss,'metrics':sm},'backup':bi,'destination':{'path':str(dest),'sha256':sha256_file(dest),'metrics':dm},'foreign_key_violations':len(fk),'integrity_check':integrity,'details':details,'rollback':{'available':True,'backup_path':str(backup),'strategy':'restore the verified pre-344 SQLite snapshot'},'completed_at':_now()};report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(out,indent=2,ensure_ascii=False,sort_keys=True),encoding='utf-8');return out
def restore_backup(backup_path,target_path):
 b,t=Path(backup_path),Path(target_path)
 if not b.is_file():raise FileNotFoundError(b)
 t.parent.mkdir(parents=True,exist_ok=True);t.unlink(missing_ok=True);s=sqlite3.connect(str(b));d=sqlite3.connect(str(t))
 try:s.backup(d);d.commit()
 finally:d.close();s.close()
 return {'path':str(t),'sha256':sha256_file(t),'metrics':database_metrics(t)}
