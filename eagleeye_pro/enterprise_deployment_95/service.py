from __future__ import annotations
from pathlib import Path
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
class EnterpriseDeployment95Service:
    """Build 95.0: local/enterprise deployment foundation: profiles, backup plan, offline/security checks."""
    def __init__(self,db:Database,audit:AuditService,base_dir:Path|str): self.db=db; self.audit=audit; self.base_dir=Path(base_dir); self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS deployment_profiles_95(profile_id TEXT PRIMARY KEY, name TEXT NOT NULL, mode TEXT NOT NULL, settings_json TEXT NOT NULL, readiness_json TEXT NOT NULL, created_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS backup_plans_95(plan_id TEXT PRIMARY KEY, case_id TEXT DEFAULT '', destination TEXT NOT NULL, include_evidence INTEGER DEFAULT 1, include_reports INTEGER DEFAULT 1, encryption_required INTEGER DEFAULT 1, status TEXT DEFAULT 'planned', created_at TEXT NOT NULL);"""); self.db.conn.commit()
    def create_profile(self,name:str,mode:str='local_single_user',settings:Dict[str,Any]|None=None)->Dict[str,Any]:
        settings=settings or {}; checks={'offline_capable':True,'public_only_default':True,'runtime_outside_install_dir':True,'encryption_recommended':True,'role_model_ready':mode in {'team','enterprise'},'backup_required':True}
        pid=new_id('deploy95'); self.db.execute('INSERT INTO deployment_profiles_95 VALUES(?,?,?,?,?,?)',[pid,name,mode,dumps(settings),dumps(checks),now_ts()]); self.audit.log('create','deployment_profile_95',pid,None,{'mode':mode}); return self.get_profile(pid)
    def get_profile(self,pid):
        r=self.db.one('SELECT * FROM deployment_profiles_95 WHERE profile_id=?',[pid])
        if not r: raise KeyError(pid)
        r['settings']=loads(r.pop('settings_json','{}'),{}); r['readiness']=loads(r.pop('readiness_json','{}'),{}); return r
    def plan_backup(self,case_id:str='',destination:str='local_backup',include_evidence:bool=True,include_reports:bool=True,encryption_required:bool=True)->Dict[str,Any]:
        bid=new_id('backup95'); self.db.execute('INSERT INTO backup_plans_95 VALUES(?,?,?,?,?,?,?,?)',[bid,case_id,destination,int(include_evidence),int(include_reports),int(encryption_required),'planned',now_ts()]); self.audit.log('plan','backup_plan_95',bid,case_id or None,{'destination':destination,'encryption_required':encryption_required}); return self.db.one('SELECT * FROM backup_plans_95 WHERE plan_id=?',[bid])
    def readiness(self)->Dict[str,Any]:
        issues=[]
        if str(self.base_dir).startswith(str(Path(__file__).resolve().parents[2])): issues.append({'level':'medium','code':'runtime_in_install_dir','message':'Runtime data should live outside the release folder.'})
        profiles=self.db.all('SELECT profile_id,name,mode,created_at FROM deployment_profiles_95 ORDER BY created_at DESC LIMIT 10')
        backups=self.db.all('SELECT * FROM backup_plans_95 ORDER BY created_at DESC LIMIT 10')
        return {'status':'enterprise_foundation_ready' if not issues else 'review_required','issues':issues,'profiles':profiles,'backup_plans':backups,'security_defaults':{'public_only':True,'review_first':True,'no_private_bypass':True,'local_storage_default':True}}
