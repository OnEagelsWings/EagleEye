from __future__ import annotations

import hashlib, hmac, json, re, secrets, time, unicodedata, uuid
from dataclasses import dataclass
from typing import Any
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

USERNAME_RE=re.compile(r'^[a-z0-9._-]{3,32}$')
COMMON={'password','password123','passwort','passwort123','123456789012345','qwertzuiopasdfg','qwertyuiopasdfg','eagleeye123456789','adminadminadminadmin'}
GLOBAL_ROLES={'system_administrator','investigator','reviewer','read_only'}
CASE_ROLES={'case_lead','investigator','analyst','reviewer','report_author','read_only'}

def now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec='seconds')
def canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def sha(v): return hashlib.sha256(str(v).encode('utf-8')).hexdigest()
def new_id(prefix): return f"{prefix}_{uuid.uuid4().hex}"

@dataclass(frozen=True,slots=True)
class IssuedTeamSession:
    token:str; csrf_token:str; session_id:str; max_age:int; absolute_expires_epoch:int

class TeamIdentity359:
    POLICY_VERSION='phase15.team-identity.v359'
    MIN_PASSWORD=15; MAX_PASSWORD=128; IDLE_SECONDS=8*3600; ABSOLUTE_SECONDS=24*3600
    def __init__(self,db:Any,audit:Any,*,cases:Any,clock:Any|None=None):
        self.db=db; self.audit=audit; self.cases=cases; self.clock=clock or time.time
        self.hasher=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=4,hash_len=32,salt_len=16,type=Type.ID)
        self._dummy=self.hasher.hash(secrets.token_urlsafe(32))
    @staticmethod
    def normalize_username(username:str)->str:
        value=unicodedata.normalize('NFKC',str(username or '')).strip().casefold()
        if not USERNAME_RE.fullmatch(value): raise ValueError('Benutzername muss 3–32 Zeichen lang sein und darf nur a–z, 0–9, Punkt, Unterstrich und Bindestrich enthalten')
        return value
    def validate_password(self,password:str,*,username:str='',display_name:str='')->None:
        v=str(password or '')
        if len(v)<self.MIN_PASSWORD: raise ValueError(f'Passwort muss mindestens {self.MIN_PASSWORD} Zeichen lang sein')
        if len(v)>self.MAX_PASSWORD: raise ValueError(f'Passwort darf höchstens {self.MAX_PASSWORD} Zeichen lang sein')
        f=unicodedata.normalize('NFKC',v).casefold().strip(); c=re.sub(r'\s+','',f)
        if f in COMMON or c in COMMON: raise ValueError('Passwort ist zu häufig oder vorhersehbar')
        u=str(username or '').casefold(); d=re.sub(r'\s+','',str(display_name or '').casefold())
        if u and u in f: raise ValueError('Passwort darf den Benutzernamen nicht enthalten')
        if len(d)>=4 and d in c: raise ValueError('Passwort darf den Anzeigenamen nicht enthalten')
    def _safe_details(self,d):
        out=dict(d or {})
        for k in list(out):
            if any(m in k.casefold() for m in ('password','secret','token','csrf','credential','cookie','audio')): out[k]='[redacted]'
        return out
    def record_access(self,*,user_id='',username='',session_id='',case_id='',capability='',allowed:bool,event_type='authorization',reason='',object_type='',object_id='',details=None):
        prev=self.db.one('SELECT event_hash FROM phase15_access_events ORDER BY sequence DESC LIMIT 1') or {}
        created=now_iso(); safe=self._safe_details(details)
        payload={'event_type':event_type,'user_id':user_id,'username_hash':sha(username) if username else '','session_id':session_id,'case_id':case_id,'capability':capability,'allowed':bool(allowed),'reason':reason,'object_type':object_type,'object_id':object_id,'details':safe,'previous_hash':prev.get('event_hash') or 'GENESIS','created_at':created}
        event_hash=hashlib.sha256(canon(payload).encode()).hexdigest()
        eid=new_id('access359')
        self.db.execute('''INSERT INTO phase15_access_events(event_id,event_type,user_id,username_hash,session_id,case_id,capability,allowed,reason,object_type,object_id,details_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(eid,event_type,user_id or None,payload['username_hash'],session_id,case_id,capability,int(bool(allowed)),reason,object_type,object_id,canon(safe),payload['previous_hash'],event_hash,created))
        return {'event_id':eid,'event_hash':event_hash}
    def verify_access_chain(self):
        rows=self.db.all('SELECT * FROM phase15_access_events ORDER BY sequence ASC')
        prev='GENESIS'
        for row in rows:
            details=json.loads(row.get('details_json') or '{}')
            payload={'event_type':row['event_type'],'user_id':row.get('user_id') or '','username_hash':row.get('username_hash') or '','session_id':row.get('session_id') or '','case_id':row.get('case_id') or '','capability':row.get('capability') or '','allowed':bool(row.get('allowed')),'reason':row.get('reason') or '','object_type':row.get('object_type') or '','object_id':row.get('object_id') or '','details':details,'previous_hash':row.get('previous_hash') or '','created_at':row['created_at']}
            expected=hashlib.sha256(canon(payload).encode()).hexdigest()
            if row.get('previous_hash')!=prev or not hmac.compare_digest(expected,str(row.get('event_hash') or '')): return {'ok':False,'events':len(rows),'failed_event_id':row.get('event_id')}
            prev=row['event_hash']
        return {'ok':True,'events':len(rows),'head_hash':prev}
    def bootstrap_required(self):
        return int((self.db.one('SELECT COUNT(*) AS n FROM phase15_team_users WHERE active=1') or {}).get('n') or 0)==0
    def _public(self,row):
        return {'user_id':row['user_id'],'username':row['username'],'display_name':row['display_name'],'global_role':row['global_role'],'active':bool(row['active']),'must_change_password':bool(row['must_change_password']),'session_generation':int(row['session_generation'] or 0)}
    def public_user(self,username):
        u=self.normalize_username(username); row=self.db.one('SELECT * FROM phase15_team_users WHERE username=? COLLATE NOCASE',(u,))
        if not row: raise KeyError(username)
        return self._public(row)
    def status(self):
        now=int(self.clock()); users=int((self.db.one('SELECT COUNT(*) n FROM phase15_team_users WHERE active=1') or {}).get('n') or 0); sessions=int((self.db.one('SELECT COUNT(*) n FROM phase15_team_sessions WHERE revoked=0 AND idle_expires_epoch>? AND absolute_expires_epoch>?',(now,now)) or {}).get('n') or 0)
        return {'policy_version':self.POLICY_VERSION,'bootstrap_required':users==0,'users':users,'active_sessions':sessions,'password_algorithm':'argon2id','session_tokens_persisted_plaintext':False,'access_events_hash_chained':True}
    def create_initial_admin(self,*,username,display_name,password):
        if not self.bootstrap_required(): raise PermissionError('Bootstrap ist bereits abgeschlossen')
        return self._create_user(username=username,display_name=display_name,global_role='system_administrator',password=password,actor='bootstrap359')
    def _create_user(self,*,username,display_name,global_role,password,actor):
        u=self.normalize_username(username); d=str(display_name or '').strip()
        if global_role not in GLOBAL_ROLES: raise ValueError('Unbekannte globale Rolle')
        if len(d)<2 or len(d)>120: raise ValueError('Anzeigename muss 2–120 Zeichen lang sein')
        self.validate_password(password,username=u,display_name=d); uid=new_id('teamuser359'); stamp=now_iso()
        try:
            self.db.execute('''INSERT INTO phase15_team_users(user_id,username,display_name,password_hash,global_role,active,must_change_password,session_generation,failed_attempts,lock_until_epoch,created_by,created_at,updated_at) VALUES(?,?,?,?,?,1,0,0,0,0,?,?,?)''',(uid,u,d,self.hasher.hash(password),global_role,actor,stamp,stamp))
        except Exception as exc: raise ValueError('Benutzername ist bereits vergeben') from exc
        self.record_access(user_id=uid,username=u,event_type='user_created',capability='user.manage',allowed=True,reason='created',details={'global_role':global_role,'actor':actor})
        return self.public_user(u)
    def require_global(self,identity_or_username,permission='user.manage'):
        ident=identity_or_username if isinstance(identity_or_username,dict) else self.public_user(identity_or_username)
        role=ident.get('global_role')
        allowed=role=='system_administrator' or (permission=='case.create' and role=='investigator')
        self.record_access(user_id=ident.get('user_id',''),username=ident.get('username',''),session_id=ident.get('session_id',''),capability=permission,allowed=allowed,reason='global_role',details={'global_role':role})
        if not allowed: raise PermissionError(f'Globale Berechtigung verweigert: {permission}')
        return True
    def create_user(self,*,identity,username,display_name,global_role,password):
        self.require_global(identity,'user.manage'); actor=(identity if isinstance(identity,dict) else self.public_user(identity))['username']
        return self._create_user(username=username,display_name=display_name,global_role=global_role,password=password,actor=actor)
    def list_users(self): return [self._public(r) for r in self.db.all('SELECT * FROM phase15_team_users ORDER BY username')]
    def authenticate(self,*,username,password,client_fingerprint=''):
        raw=unicodedata.normalize('NFKC',str(username or '')).strip().casefold(); now=int(self.clock())
        row=self.db.one('SELECT * FROM phase15_team_users WHERE username=? COLLATE NOCASE',(raw,))
        encoded=(row or {}).get('password_hash') or self._dummy
        try: ok=bool(self.hasher.verify(encoded,str(password or '')))
        except (VerifyMismatchError,VerificationError,InvalidHashError): ok=False
        if not row or not row.get('active') or int(row.get('lock_until_epoch') or 0)>now or not ok:
            if row:
                failures=int(row.get('failed_attempts') or 0)+1; lock=now+300 if failures>=10 else 0
                self.db.execute('UPDATE phase15_team_users SET failed_attempts=?,lock_until_epoch=?,updated_at=? WHERE user_id=?',(failures,lock,now_iso(),row['user_id']))
            self.record_access(user_id=(row or {}).get('user_id',''),username=raw,event_type='login',allowed=False,reason='invalid_or_locked')
            return None
        self.db.execute('UPDATE phase15_team_users SET failed_attempts=0,lock_until_epoch=0,updated_at=? WHERE user_id=?',(now_iso(),row['user_id']))
        token=secrets.token_urlsafe(48); csrf=secrets.token_urlsafe(32); sid=new_id('teamsess359'); idle=now+self.IDLE_SECONDS; absolute=now+self.ABSOLUTE_SECONDS
        self.db.execute('''INSERT INTO phase15_team_sessions(session_id,token_hash,csrf_hash,user_id,client_fingerprint_hash,session_generation,created_epoch,last_seen_epoch,idle_expires_epoch,absolute_expires_epoch,revoked,revoked_reason,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,0,'',?,?)''',(sid,sha(token),sha(csrf),row['user_id'],sha(client_fingerprint or 'unknown'),int(row.get('session_generation') or 0),now,now,idle,absolute,now_iso(),now_iso()))
        self.record_access(user_id=row['user_id'],username=row['username'],session_id=sid,event_type='login',allowed=True,reason='password_verified')
        return IssuedTeamSession(token,csrf,sid,self.IDLE_SECONDS,absolute)
    def validate_session(self,token,*,client_fingerprint='',touch=True):
        if not token: return None
        now=int(self.clock()); row=self.db.one('''SELECT s.*,u.username,u.display_name,u.global_role,u.active,u.must_change_password,u.session_generation AS user_generation FROM phase15_team_sessions s JOIN phase15_team_users u ON u.user_id=s.user_id WHERE s.token_hash=?''',(sha(token),))
        if not row or not row.get('active') or row.get('revoked') or int(row['idle_expires_epoch'])<=now or int(row['absolute_expires_epoch'])<=now or int(row['session_generation'])!=int(row['user_generation']) or not hmac.compare_digest(str(row.get('client_fingerprint_hash') or ''),sha(client_fingerprint or 'unknown')): return None
        if touch:
            idle=min(now+self.IDLE_SECONDS,int(row['absolute_expires_epoch'])); self.db.execute('UPDATE phase15_team_sessions SET last_seen_epoch=?,idle_expires_epoch=?,updated_at=? WHERE session_id=?',(now,idle,now_iso(),row['session_id']))
        return {'user_id':row['user_id'],'username':row['username'],'display_name':row['display_name'],'global_role':row['global_role'],'session_id':row['session_id'],'must_change_password':bool(row['must_change_password'])}
    def csrf_token_valid(self,identity,csrf):
        if not identity or not csrf: return False
        row=self.db.one('SELECT csrf_hash FROM phase15_team_sessions WHERE session_id=? AND revoked=0',(identity.get('session_id'),))
        return bool(row and hmac.compare_digest(str(row['csrf_hash']),sha(csrf)))
    def revoke_session(self,token,*,reason='logout'):
        row=self.db.one('SELECT * FROM phase15_team_sessions WHERE token_hash=?',(sha(token),))
        if row: self.db.execute('UPDATE phase15_team_sessions SET revoked=1,revoked_reason=?,updated_at=? WHERE session_id=?',(reason,now_iso(),row['session_id']))
    def assign_case(self,*,identity,case_id,username,case_role,notes='',bootstrap=False):
        actor=identity if isinstance(identity,dict) else self.public_user(identity)
        if not bootstrap: self.require_global(actor,'user.manage') if actor.get('global_role')=='system_administrator' else self._require_case_lead(actor,case_id)
        if case_role not in CASE_ROLES: raise ValueError('Unbekannte Fallrolle')
        user=self.public_user(username); self.cases.get_case(case_id); stamp=now_iso(); mid=new_id('member359')
        existing=self.db.one('SELECT * FROM phase15_case_memberships WHERE case_id=? AND user_id=? AND case_role=?',(case_id,user['user_id'],case_role))
        if existing:
            self.db.execute('UPDATE phase15_case_memberships SET active=1,granted_by=?,granted_at=?,revoked_by=NULL,revoked_at=NULL,notes=? WHERE membership_id=?',(actor['username'],stamp,str(notes)[:1000],existing['membership_id'])); mid=existing['membership_id']
        else:
            self.db.execute('INSERT INTO phase15_case_memberships(membership_id,case_id,user_id,case_role,active,granted_by,granted_at,notes) VALUES(?,?,?,?,1,?,?,?)',(mid,case_id,user['user_id'],case_role,actor['username'],stamp,str(notes)[:1000]))
        self.record_access(user_id=actor['user_id'],username=actor['username'],session_id=actor.get('session_id',''),case_id=case_id,event_type='membership_granted',capability='case.manage',allowed=True,reason='role_assigned',details={'target_user_id':user['user_id'],'case_role':case_role})
        return self.db.one('SELECT * FROM phase15_case_memberships WHERE membership_id=?',(mid,))
    def _require_case_lead(self,identity,case_id):
        if identity.get('global_role')=='system_administrator': return True
        if 'case_lead' not in self.case_roles(identity,case_id): raise PermissionError('Fallleitung erforderlich')
        return True
    def revoke_case_membership(self,*,identity,case_id,username,case_role,reason):
        actor=identity if isinstance(identity,dict) else self.public_user(identity); self._require_case_lead(actor,case_id)
        if len(str(reason or '').strip())<8: raise ValueError('Entzugsgrund muss dokumentiert werden')
        user=self.public_user(username); row=self.db.one('SELECT * FROM phase15_case_memberships WHERE case_id=? AND user_id=? AND case_role=? AND active=1',(case_id,user['user_id'],case_role))
        if not row: raise KeyError('Aktive Fallmitgliedschaft nicht gefunden')
        self.db.execute('UPDATE phase15_case_memberships SET active=0,revoked_by=?,revoked_at=?,notes=? WHERE membership_id=?',(actor['username'],now_iso(),str(reason)[:1000],row['membership_id']))
        self.record_access(user_id=actor['user_id'],username=actor['username'],session_id=actor.get('session_id',''),case_id=case_id,event_type='membership_revoked',capability='case.manage',allowed=True,reason='role_revoked',details={'target_user_id':user['user_id'],'case_role':case_role})
        return self.db.one('SELECT * FROM phase15_case_memberships WHERE membership_id=?',(row['membership_id'],))
    def case_roles(self,identity_or_username,case_id):
        ident=identity_or_username if isinstance(identity_or_username,dict) else self.public_user(identity_or_username)
        if ident.get('global_role')=='system_administrator': return ['case_lead']
        return [r['case_role'] for r in self.db.all('SELECT case_role FROM phase15_case_memberships WHERE case_id=? AND user_id=? AND active=1 ORDER BY case_role',(case_id,ident['user_id']))]
    def visible_cases(self,identity_or_username):
        ident=identity_or_username if isinstance(identity_or_username,dict) else self.public_user(identity_or_username)
        if ident.get('global_role')=='system_administrator': return self.cases.list_cases()
        ids=[r['case_id'] for r in self.db.all('SELECT DISTINCT case_id FROM phase15_case_memberships WHERE user_id=? AND active=1',(ident['user_id'],))]
        out=[]
        for cid in ids:
            try: out.append(self.cases.get_case(cid))
            except KeyError: pass
        return out
    def list_case_memberships(self,case_id=''):
        sql='''SELECT m.membership_id,m.case_id,u.username,u.display_name,m.case_role,m.active,m.granted_by,m.granted_at,m.revoked_by,m.revoked_at,m.notes FROM phase15_case_memberships m JOIN phase15_team_users u ON u.user_id=m.user_id'''
        if case_id: return self.db.all(sql+' WHERE m.case_id=? ORDER BY m.active DESC,u.username,m.case_role',(case_id,))
        return self.db.all(sql+' ORDER BY m.active DESC,m.case_id,u.username,m.case_role LIMIT 500')
