from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, secrets
from typing import Any, Mapping

BUILD='399.0'
POLICY_ID='phase17.target-environment-soak-recovery.v399'
CONFIRM_FREEZE_PLAN='FREEZE 72H SOAK PLAN'
CONFIRM_IMPORT_EXTERNAL='IMPORT 72H TARGET EVIDENCE'
CONFIRM_REVIEW='REVIEW 72H TARGET SOAK'
CONFIRM_INTERNAL_SIM='RUN INTERNAL SOAK FRAMEWORK CHECK'

REQUIRED_DURATION_SECONDS=72*60*60
DEFAULT_SAMPLE_INTERVAL_SECONDS=15*60
MIN_EXTERNAL_SAMPLES=(REQUIRED_DURATION_SECONDS//DEFAULT_SAMPLE_INTERVAL_SECONDS)+1
REQUIRED_RECOVERY_TYPES=('application_restart','firefox_restart')

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v):
    b=v if isinstance(v,(bytes,bytearray)) else _canon(v).encode('utf-8'); return hashlib.sha256(b).hexdigest()
def _sid(p): return p+'_'+secrets.token_hex(12)
def _j(v,d):
    try:return json.loads(v) if isinstance(v,str) else (v if v is not None else d)
    except Exception:return d

def _dt(v:str)->datetime:
    s=str(v).strip().replace('Z','+00:00'); d=datetime.fromisoformat(s)
    if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

class TargetEnvironmentSoak399:
    """Local/import-only qualification ledger for the planned 72h Windows/Firefox soak.

    This component does not launch Firefox, crawl, execute models, issue GO/LIVE, or mutate
    evidence. It validates and stores externally collected target-environment evidence.
    """
    def __init__(self,db:Any,audit:Any,*,governance:Any=None,actor:str='local-analyst'):
        self.db=db; self.audit=audit; self.governance=governance; self.actor=actor; self._init_schema()
    def _init_schema(self):
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS soak_plan_399(
          plan_id TEXT PRIMARY KEY,name TEXT NOT NULL,status TEXT NOT NULL,required_duration_seconds INTEGER NOT NULL,
          sample_interval_seconds INTEGER NOT NULL,min_samples INTEGER NOT NULL,max_sample_gap_seconds INTEGER NOT NULL,
          required_recoveries_json TEXT NOT NULL,requirements_json TEXT NOT NULL,frozen_by TEXT NOT NULL DEFAULT '',
          frozen_at TEXT NOT NULL DEFAULT '',plan_hash TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS soak_session_399(
          session_id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,run_origin TEXT NOT NULL,status TEXT NOT NULL,
          environment_json TEXT NOT NULL,collector_id TEXT NOT NULL,started_at TEXT NOT NULL,ended_at TEXT NOT NULL,
          duration_seconds REAL NOT NULL,execution_receipt TEXT NOT NULL,receipt_hash TEXT NOT NULL,
          evidence_bundle_hash TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_soak_session_399_plan ON soak_session_399(plan_id,run_origin,status);
        CREATE TABLE IF NOT EXISTS soak_sample_399(
          sample_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,ordinal INTEGER NOT NULL,observed_at TEXT NOT NULL,
          app_health TEXT NOT NULL,db_integrity TEXT NOT NULL,firefox_probe TEXT NOT NULL,firefox_profile_ok INTEGER NOT NULL,
          crawler_health TEXT NOT NULL,worker_health TEXT NOT NULL,recovery_state TEXT NOT NULL,critical_error INTEGER NOT NULL,
          details_json TEXT NOT NULL,evidence_ref TEXT NOT NULL,record_hash TEXT NOT NULL,
          UNIQUE(session_id,ordinal));
        CREATE INDEX IF NOT EXISTS idx_soak_sample_399_session ON soak_sample_399(session_id,observed_at);
        CREATE TABLE IF NOT EXISTS recovery_event_399(
          recovery_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,recovery_type TEXT NOT NULL,started_at TEXT NOT NULL,
          recovered_at TEXT NOT NULL,recovery_seconds REAL NOT NULL,before_state TEXT NOT NULL,after_state TEXT NOT NULL,
          successful INTEGER NOT NULL,evidence_ref TEXT NOT NULL,details_json TEXT NOT NULL,record_hash TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_recovery_event_399_session ON recovery_event_399(session_id,recovery_type);
        CREATE TABLE IF NOT EXISTS soak_review_399(
          review_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,reviewer_id TEXT NOT NULL,disposition TEXT NOT NULL,
          native_windows_verified INTEGER NOT NULL,native_firefox_e2e_verified INTEGER NOT NULL,recovery_verified INTEGER NOT NULL,
          notes TEXT NOT NULL,reviewed_at TEXT NOT NULL,record_hash TEXT NOT NULL,UNIQUE(session_id,reviewer_id));
        '''); self.db.conn.commit()
    def _rowhash(self,d,drop=('record_hash',)): return _sha({k:d[k] for k in sorted(d) if k not in drop})
    def create_reference_plan(self):
        pid='soak399_windows_firefox_72h_v1'; old=self.db.one('SELECT * FROM soak_plan_399 WHERE plan_id=?',(pid,))
        if old:return self.plan(pid)
        req={'native_windows':True,'native_firefox':True,'native_firefox_e2e':True,'db_integrity_required':'ok','protected_firefox_profile':True,'critical_unrecovered_errors_allowed':0,'external_receipt_required':True,'human_final_review_required':True}
        rec=list(REQUIRED_RECOVERY_TYPES)
        body={'plan_id':pid,'name':'Build399 72h native Windows + Firefox soak/recovery qualification','status':'draft','required_duration_seconds':REQUIRED_DURATION_SECONDS,'sample_interval_seconds':DEFAULT_SAMPLE_INTERVAL_SECONDS,'min_samples':MIN_EXTERNAL_SAMPLES,'max_sample_gap_seconds':DEFAULT_SAMPLE_INTERVAL_SECONDS*2,'required_recoveries_json':_canon(rec),'requirements_json':_canon(req),'frozen_by':'','frozen_at':'','plan_hash':_sha({'id':pid,'duration':REQUIRED_DURATION_SECONDS,'interval':DEFAULT_SAMPLE_INTERVAL_SECONDS,'recoveries':rec,'requirements':req})}; body['record_hash']=self._rowhash(body)
        self.db.execute('INSERT INTO soak_plan_399 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(body.values())); self.audit.log('soak_plan_created','soak_plan_399',pid,'',{'required_hours':72,'external_qualification':False}); return self.plan(pid)
    def plan(self,plan_id):
        r=self.db.one('SELECT * FROM soak_plan_399 WHERE plan_id=?',(plan_id,));
        if not r: raise KeyError('soak plan not found')
        d=dict(r); d['required_recoveries']=_j(d.pop('required_recoveries_json'),[]); d['requirements']=_j(d.pop('requirements_json'),{}); return d
    def freeze_plan(self,*,plan_id,identity:Mapping[str,Any],confirmation:str):
        if confirmation!=CONFIRM_FREEZE_PLAN: raise PermissionError(f'exact confirmation required: {CONFIRM_FREEZE_PLAN}')
        p=self.plan(plan_id); actor=str(identity.get('user_id') or identity.get('username') or self.actor); now=_now(); self.db.execute('UPDATE soak_plan_399 SET status=?,frozen_by=?,frozen_at=? WHERE plan_id=?',('frozen',actor,now,plan_id)); self._rehash_plan(plan_id); self.audit.log('soak_plan_frozen','soak_plan_399',plan_id,'',{'actor':actor}); return self.plan(plan_id)
    def _rehash_plan(self,pid):
        r=dict(self.db.one('SELECT * FROM soak_plan_399 WHERE plan_id=?',(pid,))); self.db.execute('UPDATE soak_plan_399 SET record_hash=? WHERE plan_id=?',(self._rowhash(r),pid))
    def _validate_bundle(self,plan,bundle):
        env=dict(bundle.get('environment') or {}); samples=list(bundle.get('samples') or []); recoveries=list(bundle.get('recoveries') or [])
        start=str(bundle.get('started_at') or ''); end=str(bundle.get('ended_at') or ''); receipt=str(bundle.get('execution_receipt') or ''); collector=str(bundle.get('collector_id') or '')
        if not start or not end or not receipt or not collector: raise ValueError('started_at, ended_at, execution_receipt and collector_id are required')
        dur=(_dt(end)-_dt(start)).total_seconds()
        if dur<0: raise ValueError('ended_at precedes started_at')
        for key in ('native_windows','native_firefox','native_firefox_e2e','protected_firefox_profile'):
            if key not in env: raise ValueError(f'environment.{key} must be explicitly supplied')
        return env,samples,recoveries,start,end,receipt,collector,dur
    def import_external_bundle(self,*,plan_id,bundle:Mapping[str,Any],identity:Mapping[str,Any],confirmation:str):
        if confirmation!=CONFIRM_IMPORT_EXTERNAL: raise PermissionError(f'exact confirmation required: {CONFIRM_IMPORT_EXTERNAL}')
        p=self.plan(plan_id)
        if p['status']!='frozen': raise ValueError('soak plan must be frozen before external evidence import')
        env,samples,recoveries,start,end,receipt,collector,dur=self._validate_bundle(p,bundle)
        sid=_sid('soak399'); actor=str(identity.get('user_id') or identity.get('username') or self.actor); created=_now(); bundle_hash=_sha(bundle)
        row={'session_id':sid,'plan_id':plan_id,'run_origin':'external_target_environment','status':'completed_imported','environment_json':_canon(env),'collector_id':collector,'started_at':start,'ended_at':end,'duration_seconds':dur,'execution_receipt':receipt,'receipt_hash':_sha(receipt),'evidence_bundle_hash':bundle_hash,'created_by':actor,'created_at':created}; row['record_hash']=self._rowhash(row)
        with self.db.conn:
            self.db.conn.execute('INSERT INTO soak_session_399 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(row.values()))
            for i,s in enumerate(samples,1): self._insert_sample(sid,i,s)
            for r in recoveries: self._insert_recovery(sid,r)
        self.audit.log('target_soak_bundle_imported','soak_session_399',sid,'',{'duration_seconds':dur,'samples':len(samples),'recoveries':len(recoveries),'bundle_hash':bundle_hash,'externally_asserted':True})
        return self.session(sid)
    def record_internal_framework_simulation(self,*,plan_id,identity:Mapping[str,Any],confirmation:str):
        if confirmation!=CONFIRM_INTERNAL_SIM: raise PermissionError(f'exact confirmation required: {CONFIRM_INTERNAL_SIM}')
        p=self.plan(plan_id)
        if p['status']!='frozen': raise ValueError('soak plan must be frozen')
        start='2026-01-01T00:00:00+00:00'; end='2026-01-01T02:00:00+00:00'; env={'native_windows':False,'native_firefox':False,'native_firefox_e2e':False,'protected_firefox_profile':False,'simulation':True}
        samples=[]
        for i in range(9):
            t=datetime(2026,1,1,0,0,tzinfo=timezone.utc).timestamp()+i*900
            samples.append({'observed_at':datetime.fromtimestamp(t,timezone.utc).isoformat(),'app_health':'healthy','db_integrity':'ok','firefox_probe':'not_run','firefox_profile_ok':False,'crawler_health':'idle','worker_health':'idle','recovery_state':'none','critical_error':False,'details':{'simulation':True},'evidence_ref':f'internal-sim-{i}'})
        bundle={'environment':env,'samples':samples,'recoveries':[],'started_at':start,'ended_at':end,'execution_receipt':'internal-framework-simulation-not-external-evidence','collector_id':'build399-internal-simulation'}
        env,samples,recoveries,start,end,receipt,collector,dur=self._validate_bundle(p,bundle)
        sid=_sid('soak399sim'); actor=str(identity.get('user_id') or identity.get('username') or self.actor); row={'session_id':sid,'plan_id':plan_id,'run_origin':'internal_framework_simulation','status':'completed_simulation','environment_json':_canon(env),'collector_id':collector,'started_at':start,'ended_at':end,'duration_seconds':dur,'execution_receipt':receipt,'receipt_hash':_sha(receipt),'evidence_bundle_hash':_sha(bundle),'created_by':actor,'created_at':_now()}; row['record_hash']=self._rowhash(row)
        with self.db.conn:
            self.db.conn.execute('INSERT INTO soak_session_399 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(row.values()))
            for i,s in enumerate(samples,1): self._insert_sample(sid,i,s)
        self.audit.log('target_soak_internal_simulation','soak_session_399',sid,'',{'external_qualification':False}); return self.session(sid)
    def _insert_sample(self,sid,ordinal,s):
        obs=str(s.get('observed_at') or ''); _dt(obs)
        row={'sample_id':_sid('sample399'),'session_id':sid,'ordinal':ordinal,'observed_at':obs,'app_health':str(s.get('app_health') or 'unknown'),'db_integrity':str(s.get('db_integrity') or 'unknown'),'firefox_probe':str(s.get('firefox_probe') or 'not_run'),'firefox_profile_ok':1 if s.get('firefox_profile_ok') else 0,'crawler_health':str(s.get('crawler_health') or 'unknown'),'worker_health':str(s.get('worker_health') or 'unknown'),'recovery_state':str(s.get('recovery_state') or 'none'),'critical_error':1 if s.get('critical_error') else 0,'details_json':_canon(s.get('details') or {}),'evidence_ref':str(s.get('evidence_ref') or '')}; row['record_hash']=self._rowhash(row); self.db.conn.execute('INSERT INTO soak_sample_399 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(row.values()))
    def _insert_recovery(self,sid,r):
        st=str(r.get('started_at') or ''); en=str(r.get('recovered_at') or ''); dur=(_dt(en)-_dt(st)).total_seconds()
        row={'recovery_id':_sid('recovery399'),'session_id':sid,'recovery_type':str(r.get('recovery_type') or ''),'started_at':st,'recovered_at':en,'recovery_seconds':dur,'before_state':str(r.get('before_state') or 'unknown'),'after_state':str(r.get('after_state') or 'unknown'),'successful':1 if r.get('successful') else 0,'evidence_ref':str(r.get('evidence_ref') or ''),'details_json':_canon(r.get('details') or {})}; row['record_hash']=self._rowhash(row); self.db.conn.execute('INSERT INTO recovery_event_399 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',tuple(row.values()))
    def session(self,session_id):
        r=self.db.one('SELECT * FROM soak_session_399 WHERE session_id=?',(session_id,));
        if not r: raise KeyError('soak session not found')
        d=dict(r); d['environment']=_j(d.pop('environment_json'),{}); return d
    def review_external_session(self,*,session_id,identity:Mapping[str,Any],disposition:str,native_windows_verified:bool,native_firefox_e2e_verified:bool,recovery_verified:bool,notes:str,confirmation:str):
        if confirmation!=CONFIRM_REVIEW: raise PermissionError(f'exact confirmation required: {CONFIRM_REVIEW}')
        s=self.session(session_id)
        if s['run_origin']!='external_target_environment': raise ValueError('only an external target-environment session can receive qualification review')
        reviewer=str(identity.get('user_id') or identity.get('username') or '')
        if not reviewer: raise ValueError('authenticated reviewer identity required')
        if disposition not in {'qualified','not_qualified','needs_followup'}: raise ValueError('invalid disposition')
        rid=_sid('review399'); row={'review_id':rid,'session_id':session_id,'reviewer_id':reviewer,'disposition':disposition,'native_windows_verified':1 if native_windows_verified else 0,'native_firefox_e2e_verified':1 if native_firefox_e2e_verified else 0,'recovery_verified':1 if recovery_verified else 0,'notes':notes,'reviewed_at':_now()}; row['record_hash']=self._rowhash(row); self.db.execute('INSERT INTO soak_review_399 VALUES(?,?,?,?,?,?,?,?,?,?)',tuple(row.values())); self.audit.log('target_soak_reviewed','soak_review_399',rid,'',{'session_id':session_id,'disposition':disposition,'reviewer':reviewer}); return dict(self.db.one('SELECT * FROM soak_review_399 WHERE review_id=?',(rid,)))
    def _session_metrics(self,sid):
        samples=[dict(r) for r in self.db.all('SELECT * FROM soak_sample_399 WHERE session_id=? ORDER BY observed_at',(sid,))]; rec=[dict(r) for r in self.db.all('SELECT * FROM recovery_event_399 WHERE session_id=?',(sid,))]
        gaps=[]
        for a,b in zip(samples,samples[1:]): gaps.append((_dt(b['observed_at'])-_dt(a['observed_at'])).total_seconds())
        return {'sample_count':len(samples),'first_sample_at':samples[0]['observed_at'] if samples else '', 'last_sample_at':samples[-1]['observed_at'] if samples else '', 'max_sample_gap_seconds':max(gaps) if gaps else None,'db_integrity_failures':sum(1 for x in samples if x['db_integrity']!='ok'),'app_health_failures':sum(1 for x in samples if x['app_health']!='healthy'),'crawler_health_failures':sum(1 for x in samples if x['crawler_health'] not in {'healthy','idle','governed'}),'worker_health_failures':sum(1 for x in samples if x['worker_health'] not in {'healthy','idle'}),'firefox_probe_failures':sum(1 for x in samples if x['firefox_probe']!='pass'),'firefox_profile_failures':sum(1 for x in samples if not x['firefox_profile_ok']),'critical_errors':sum(int(x['critical_error']) for x in samples),'recovery_types':sorted({x['recovery_type'] for x in rec if x['successful']}),'failed_recoveries':sum(1 for x in rec if not x['successful']),'recovery_times':[(x['started_at'],x['recovered_at']) for x in rec]}
    def qualification_status(self,plan_id='soak399_windows_firefox_72h_v1'):
        planrow=self.db.one('SELECT * FROM soak_plan_399 WHERE plan_id=?',(plan_id,))
        if not planrow:return {'build':BUILD,'plan_present':False,'external_72h_soak_qualified':False,'external_sessions':0}
        plan=self.plan(plan_id); sessions=[self.session(r['session_id']) for r in self.db.all("SELECT session_id FROM soak_session_399 WHERE plan_id=? AND run_origin='external_target_environment'",(plan_id,))]
        qualified_ids=[]; details=[]
        for s in sessions:
            m=self._session_metrics(s['session_id']); env=s['environment']; reviews=[dict(r) for r in self.db.all('SELECT * FROM soak_review_399 WHERE session_id=?',(s['session_id'],))]
            good_review=any(r['disposition']=='qualified' and r['native_windows_verified'] and r['native_firefox_e2e_verified'] and r['recovery_verified'] for r in reviews)
            required_rec=set(plan['required_recoveries']); got=set(m['recovery_types'])
            start_dt=_dt(s['started_at']); end_dt=_dt(s['ended_at'])
            first_dt=_dt(m['first_sample_at']) if m['first_sample_at'] else None; last_dt=_dt(m['last_sample_at']) if m['last_sample_at'] else None
            recovery_within=all(start_dt<=_dt(a)<=_dt(b)<=end_dt for a,b in m['recovery_times'])
            checks={
              'duration_72h':float(s['duration_seconds'])>=plan['required_duration_seconds'],
              'sample_coverage':m['sample_count']>=plan['min_samples'],
              'sample_gap':m['max_sample_gap_seconds'] is not None and m['max_sample_gap_seconds']<=plan['max_sample_gap_seconds'],
              'sample_start_coverage':first_dt is not None and 0 <= (first_dt-start_dt).total_seconds() <= plan['sample_interval_seconds'],
              'sample_end_coverage':last_dt is not None and 0 <= (end_dt-last_dt).total_seconds() <= plan['sample_interval_seconds'],
              'native_windows':env.get('native_windows') is True,
              'native_firefox':env.get('native_firefox') is True,
              'native_firefox_e2e':env.get('native_firefox_e2e') is True,
              'protected_firefox_profile':env.get('protected_firefox_profile') is True,
              'app_health':m['app_health_failures']==0,
              'db_integrity':m['db_integrity_failures']==0,
              'crawler_health':m['crawler_health_failures']==0,
              'worker_health':m['worker_health_failures']==0,
              'firefox_probe':m['firefox_probe_failures']==0,
              'firefox_profile':m['firefox_profile_failures']==0,
              'critical_errors':m['critical_errors']==0,
              'recovery_types':required_rec.issubset(got) and m['failed_recoveries']==0 and recovery_within,
              'execution_receipt':bool(s['execution_receipt'] and s['receipt_hash']),
              'human_review':good_review,
            }
            if all(checks.values()): qualified_ids.append(s['session_id'])
            details.append({'session_id':s['session_id'],'checks':checks,'metrics':m})
        return {'build':BUILD,'plan_present':True,'plan_status':plan['status'],'required_hours':72,'required_samples':plan['min_samples'],'external_sessions':len(sessions),'qualified_external_sessions':qualified_ids,'external_72h_soak_qualified':bool(qualified_ids),'details':details,'production_qualification':False,'direct_network_fetch_in_core':False,'execution_authority':False,'automatic_go':False,'automatic_live_confirmation':False,'automatic_evidence_promotion':False}
    def verify_session(self,session_id):
        row=self.db.one('SELECT * FROM soak_session_399 WHERE session_id=?',(session_id,))
        if not row:return {'valid':False,'violations':['missing_session']}
        s=dict(row); bad=[]
        if s['record_hash']!=self._rowhash(s): bad.append('session_hash')
        for table in ('soak_sample_399','recovery_event_399','soak_review_399'):
            for r in self.db.all(f'SELECT * FROM {table} WHERE session_id=?',(session_id,)):
                d=dict(r)
                if d['record_hash']!=self._rowhash(d): bad.append(f'{table}:{d.get(next(iter(d)))}')
        return {'valid':not bad,'violations':bad}
    def status(self):
        return {'build':BUILD,'policy':POLICY_ID,'required_soak_hours':72,'sample_interval_seconds':DEFAULT_SAMPLE_INTERVAL_SECONDS,'minimum_external_samples':MIN_EXTERNAL_SAMPLES,'required_recovery_types':list(REQUIRED_RECOVERY_TYPES),'native_windows_required':True,'native_firefox_e2e_required':True,'protected_firefox_profile_required':True,'external_evidence_import':True,'internal_framework_simulation':True,'simulation_can_qualify_external':False,'direct_network_fetch':False,'browser_launch_authority':False,'execution_authority':False,'automatic_go':False,'automatic_live_confirmation':False,'automatic_evidence_promotion':False}
