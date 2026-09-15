from __future__ import annotations
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, new_id, now_ts
class TeamWorkflow94Service:
    """Build 94.0: roles, assignments, four-eyes review and case locks."""
    def __init__(self,db:Database,audit:AuditService): self.db=db; self.audit=audit; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS team_members_94(member_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, role TEXT NOT NULL, email TEXT DEFAULT '', active INTEGER DEFAULT 1, created_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS review_assignments_94(assignment_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT NOT NULL, assigned_to TEXT NOT NULL, required_role TEXT DEFAULT 'reviewer', status TEXT DEFAULT 'open', due_at TEXT DEFAULT '', notes TEXT DEFAULT '', created_at TEXT NOT NULL, decided_at TEXT DEFAULT '', decision TEXT DEFAULT ''); CREATE TABLE IF NOT EXISTS case_locks_94(lock_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, locked_by TEXT NOT NULL, reason TEXT NOT NULL, status TEXT DEFAULT 'active', created_at TEXT NOT NULL, released_at TEXT DEFAULT '');"""); self.db.conn.commit()
    def add_member(self,display_name:str,role:str,email:str='')->Dict[str,Any]:
        mid=new_id('member94'); self.db.execute('INSERT INTO team_members_94 VALUES(?,?,?,?,?,?)',[mid,display_name,role,email,1,now_ts()]); self.audit.log('create','team_member_94',mid,None,{'role':role}); return self.get_member(mid)
    def get_member(self,mid): return self.db.one('SELECT * FROM team_members_94 WHERE member_id=?',[mid]) or {}
    def assign_review(self,case_id:str,object_type:str,object_id:str,assigned_to:str,*,required_role:str='reviewer',due_at:str='',notes:str='')->Dict[str,Any]:
        aid=new_id('assign94'); self.db.execute('INSERT INTO review_assignments_94 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',[aid,case_id,object_type,object_id,assigned_to,required_role,'open',due_at,notes,now_ts(),'','']); self.audit.log('assign','review_assignment_94',aid,case_id,{'object_type':object_type,'object_id':object_id,'assigned_to':assigned_to}); return self.get_assignment(aid)
    def decide(self,assignment_id:str,decision:str,actor:str='local-analyst')->Dict[str,Any]:
        self.db.execute('UPDATE review_assignments_94 SET status=?, decision=?, decided_at=? WHERE assignment_id=?',['closed',decision,now_ts(),assignment_id]); self.audit.log('decide','review_assignment_94',assignment_id,None,{'decision':decision,'actor':actor}); return self.get_assignment(assignment_id)
    def lock_case(self,case_id:str,locked_by:str,reason:str)->Dict[str,Any]:
        active=self.db.one("SELECT * FROM case_locks_94 WHERE case_id=? AND status='active'",[case_id])
        if active: return active
        lid=new_id('lock94'); self.db.execute('INSERT INTO case_locks_94 VALUES(?,?,?,?,?,?,?)',[lid,case_id,locked_by,reason,'active',now_ts(),'']); self.audit.log('lock','case_lock_94',lid,case_id,{'locked_by':locked_by,'reason':reason}); return self.db.one('SELECT * FROM case_locks_94 WHERE lock_id=?',[lid])
    def release_lock(self,case_id:str,actor:str='local-analyst')->Dict[str,Any]:
        row=self.db.one("SELECT lock_id FROM case_locks_94 WHERE case_id=? AND status='active'",[case_id])
        if not row: return {'case_id':case_id,'status':'no_active_lock'}
        self.db.execute("UPDATE case_locks_94 SET status='released', released_at=? WHERE lock_id=?",[now_ts(),row['lock_id']]); self.audit.log('release','case_lock_94',row['lock_id'],case_id,{'actor':actor}); return {'case_id':case_id,'lock_id':row['lock_id'],'status':'released'}
    def get_assignment(self,aid): return self.db.one('SELECT * FROM review_assignments_94 WHERE assignment_id=?',[aid]) or {}
    def board(self,case_id): return {'case_id':case_id,'assignments':self.db.all('SELECT * FROM review_assignments_94 WHERE case_id=? ORDER BY created_at DESC',[case_id]),'locks':self.db.all('SELECT * FROM case_locks_94 WHERE case_id=? ORDER BY created_at DESC',[case_id])}
