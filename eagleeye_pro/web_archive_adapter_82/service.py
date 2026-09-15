from __future__ import annotations
from typing import Any
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.url_policy import URLPolicy

class WebArchiveAdapter82Service:
    def __init__(self,db:Database,audit:AuditService,capture:Any=None): self.db=db; self.audit=audit; self.capture=capture; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS web_archive_candidates_82 (archive_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, original_url TEXT NOT NULL, canonical_url TEXT NOT NULL, archive_query_url TEXT NOT NULL, timestamp_hint TEXT DEFAULT '', status TEXT DEFAULT 'candidate_not_claim', created_at TEXT NOT NULL, metadata_json TEXT NOT NULL);"""); self.db.conn.commit()
    def prepare(self,case_id,url,timestamp_hint='',metadata=None):
        dec=URLPolicy.normalize_public_url(url)
        if not dec.get('ok'): raise ValueError(dec.get('blocked_reason'))
        q='https://web.archive.org/web/*/'+dec['canonical_url']; aid=new_id('wa82')
        self.db.execute('INSERT INTO web_archive_candidates_82 VALUES(?,?,?,?,?,?,?,?,?)',[aid,case_id,url,dec['canonical_url'],q,timestamp_hint,'candidate_not_claim',now_ts(),dumps(metadata or {})]); self.audit.log('prepare','web_archive_82',aid,case_id,{'url':dec['canonical_url']}); return self.get(aid)
    def get(self,aid):
        r=self.db.one('SELECT * FROM web_archive_candidates_82 WHERE archive_id=?',[aid])
        if not r: raise KeyError(aid)
        r['metadata']=loads(r.pop('metadata_json','{}'),{}); return r
    def list(self,case_id): return [self.get(r['archive_id']) for r in self.db.all('SELECT archive_id FROM web_archive_candidates_82 WHERE case_id=? ORDER BY created_at',[case_id])]
