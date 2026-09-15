from __future__ import annotations
import hashlib, re
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.url_policy import URLPolicy
USER_RE=re.compile(r'^[A-Za-z0-9_.-]{1,80}$')
class PublicCodeProfile84Service:
    FORBIDDEN=('password','secret','token','credential','private key','api_key')
    def __init__(self,db:Database,audit:AuditService): self.db=db; self.audit=audit; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS public_code_profiles_84 (profile_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, platform TEXT NOT NULL, username TEXT NOT NULL, profile_url TEXT NOT NULL, status TEXT DEFAULT 'candidate_not_claim', signals_json TEXT NOT NULL, payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);"""); self.db.conn.commit()
    def prepare_profile(self,case_id,platform,username):
        u=username.strip().lstrip('@')
        if not USER_RE.match(u): raise ValueError('invalid_username')
        base={'github':'https://github.com/','gitlab':'https://gitlab.com/'}.get(platform.lower())
        if not base: raise ValueError('unsupported_platform')
        return {'case_id':case_id,'platform':platform.lower(),'username':u,'profile_url':base+u,'status':'prepared_manual_capture','warning':'Username match is not identity proof.'}
    def import_profile(self,case_id,platform,username,profile_url='',payload=None):
        prep=self.prepare_profile(case_id,platform,username); url=profile_url or prep['profile_url']; dec=URLPolicy.normalize_public_url(url)
        if not dec.get('ok'): raise ValueError(dec.get('blocked_reason'))
        p=payload or {}; txt=dumps(p).lower(); signals=[]
        for s in ['bio','location','organization','website','repository_count','created_at','public_email']:
            if s in txt: signals.append(s)
        if any(f in txt for f in self.FORBIDDEN): signals.append('sensitive_secret_like_marker_review_required')
        pid=new_id('cp84'); raw=dumps(p)
        self.db.execute('INSERT INTO public_code_profiles_84 VALUES(?,?,?,?,?,?,?,?,?,?)',[pid,case_id,platform.lower(),prep['username'],dec['canonical_url'],'candidate_not_claim',dumps(signals),hashlib.sha256(raw.encode()).hexdigest(),raw,now_ts()]); self.audit.log('import','public_code_profile_84',pid,case_id,{'platform':platform,'username':prep['username'],'signals':signals}); return self.get(pid)
    def get(self,pid):
        r=self.db.one('SELECT * FROM public_code_profiles_84 WHERE profile_id=?',[pid])
        if not r: raise KeyError(pid)
        r['signals']=loads(r.pop('signals_json','[]'),[]); r['payload']=loads(r.pop('payload_json','{}'),{}); return r
    def list(self,case_id): return [self.get(r['profile_id']) for r in self.db.all('SELECT profile_id FROM public_code_profiles_84 WHERE case_id=? ORDER BY created_at',[case_id])]
