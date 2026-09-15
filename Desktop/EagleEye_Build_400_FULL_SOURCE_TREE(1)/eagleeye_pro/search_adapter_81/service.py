from __future__ import annotations
import hashlib
from urllib.parse import quote_plus
from typing import Any
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.policy import PolicyGate
from eagleeye_pro.security.url_policy import URLPolicy

SEARCH_ENGINES={'generic_web':'https://www.google.com/search?q={query}','bing_web':'https://www.bing.com/search?q={query}','duckduckgo_web':'https://duckduckgo.com/?q={query}','github_public':'https://github.com/search?q={query}&type=users'}
class SearchAdapter81Service:
    def __init__(self,db:Database,audit:AuditService,real_capture:Any=None,graph:Any=None): self.db=db; self.audit=audit; self.real_capture=real_capture; self.graph=graph; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS search_plans_81 (plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, target_ref TEXT DEFAULT '', query TEXT NOT NULL, engine TEXT NOT NULL, search_url TEXT NOT NULL, status TEXT DEFAULT 'planned_manual_execution', created_at TEXT NOT NULL, policy_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS search_results_81 (result_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, plan_id TEXT DEFAULT '', title TEXT NOT NULL, url TEXT NOT NULL, snippet TEXT DEFAULT '', normalized_url TEXT DEFAULT '', raw_hash TEXT NOT NULL, review_status TEXT DEFAULT 'candidate_not_claim', created_at TEXT NOT NULL, metadata_json TEXT NOT NULL);"""); self.db.conn.commit()
    def plan(self,case_id,query,engines=None,target_ref=''):
        gate=PolicyGate.evaluate_query(query)
        if not gate.get('ok'): return {'ok':False,'policy':gate,'plans':[]}
        rows=[]
        for eng in (engines or ['generic_web','bing_web','duckduckgo_web']):
            if eng not in SEARCH_ENGINES: raise ValueError(f'unsupported search engine: {eng}')
            sid=new_id('sp81'); url=SEARCH_ENGINES[eng].format(query=quote_plus(query)); self.db.execute('INSERT INTO search_plans_81 VALUES(?,?,?,?,?,?,?,?,?)',[sid,case_id,target_ref,query,eng,url,'planned_manual_execution',now_ts(),dumps(gate)]); rows.append(self.get_plan(sid))
        self.audit.log('plan','search_adapter_81',case_id=case_id,details={'query':query,'count':len(rows)})
        return {'ok':True,'policy':gate,'plans':rows,'execution_note':'Manual/browser execution only; imported results remain candidates, not claims.'}
    def get_plan(self,pid):
        r=self.db.one('SELECT * FROM search_plans_81 WHERE plan_id=?',[pid]); r['policy']=loads(r.pop('policy_json','{}'),{}); return r
    def import_result(self,case_id,title,url,snippet='',plan_id='',metadata=None):
        dec=URLPolicy.normalize_public_url(url)
        if not dec.get('ok'): raise ValueError(dec.get('blocked_reason'))
        raw=dumps({'title':title,'url':dec['canonical_url'],'snippet':snippet,'metadata':metadata or {}}); rid=new_id('sr81')
        self.db.execute('INSERT INTO search_results_81 VALUES(?,?,?,?,?,?,?,?,?,?,?)',[rid,case_id,plan_id,title,dec['canonical_url'],snippet,dec['canonical_url'],hashlib.sha256(raw.encode()).hexdigest(),'candidate_not_claim',now_ts(),dumps(metadata or {})])
        self.audit.log('import','search_result_81',rid,case_id,{'url':dec['canonical_url']})
        return self.get_result(rid)
    def get_result(self,rid):
        r=self.db.one('SELECT * FROM search_results_81 WHERE result_id=?',[rid])
        if not r: raise KeyError(rid)
        r['metadata']=loads(r.pop('metadata_json','{}'),{}); return r
    def list_results(self,case_id): return [self.get_result(r['result_id']) for r in self.db.all('SELECT result_id FROM search_results_81 WHERE case_id=? ORDER BY created_at',[case_id])]
