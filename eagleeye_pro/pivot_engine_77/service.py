from __future__ import annotations
from typing import Any, Dict
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.policy import PolicyGate
from eagleeye_pro.security.url_policy import URLPolicy

class PivotEngine77Service:
    def __init__(self, db: Database, audit: AuditService): self.db=db; self.audit=audit; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS pivot_results_77 (
          pivot_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, seed_type TEXT NOT NULL, seed_value TEXT NOT NULL,
          pivot_type TEXT NOT NULL, candidate TEXT NOT NULL, rationale TEXT NOT NULL, status TEXT DEFAULT 'candidate_not_claim', created_at TEXT NOT NULL, metadata_json TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_pivot77_case ON pivot_results_77(case_id,seed_type,seed_value);"""); self.db.conn.commit()
    def _store(self, case_id, seed_type, seed_value, pivot_type, candidate, rationale, metadata=None):
        gate=PolicyGate.evaluate_query(candidate)
        if not gate.get('ok'): return None
        pid=new_id('piv77'); self.db.execute('INSERT INTO pivot_results_77 VALUES(?,?,?,?,?,?,?,?,?,?)',[pid,case_id,seed_type,seed_value,pivot_type,candidate,rationale,'candidate_not_claim',now_ts(),dumps(metadata or {})]); return self.get(pid)
    def generate(self, case_id: str, seed_type: str, seed_value: str, metadata: Dict[str, Any]|None=None) -> Dict[str, Any]:
        val=(seed_value or '').strip(); out=[]
        if not val: raise ValueError('seed_value required')
        if seed_type=='email' and '@' in val:
            local,domain=val.split('@',1); out += [('domain',domain,'domain from email'),('username',local,'local part as username candidate'),('exact_search',f'"{val}"','exact public search candidate')]
        elif seed_type=='username':
            u=val.lstrip('@'); variants=sorted({u,u.replace('_','.'),u.replace('.','_'),u.replace('-','_'),u.lower()}); out += [('username_variant',x,'username spelling variant') for x in variants] + [('exact_search',f'"{u}"','exact username search')]
        elif seed_type=='name':
            parts=val.split(); out.append(('exact_search',f'"{val}"','exact name search'))
            if len(parts)>=2:
                rev=f'"{parts[-1]} {" ".join(parts[:-1])}"'; out.append(('name_variant',rev,'reversed name order'))
        elif seed_type=='domain':
            d=val.lower().replace('www.',''); out += [('rdap_lookup',d,'public RDAP candidate'),('dns_lookup',d,'public DNS candidate'),('mx_lookup',d,'public MX candidate'),('exact_search',f'"{d}"','domain exact search')]
        elif seed_type=='url':
            dec=URLPolicy.normalize_public_url(val)
            if not dec.get('ok'): raise ValueError(dec.get('blocked_reason'))
            host=dec.get('host',''); out += [('host',host,'host from URL'),('archive_lookup',dec.get('canonical_url'),'public web archive candidate')]
        else:
            out.append(('exact_search',f'"{val}"','generic exact public search candidate'))
        rows=[]
        for typ,cand,rat in out:
            r=self._store(case_id,seed_type,val,typ,cand,rat,metadata)
            if r: rows.append(r)
        self.audit.log('generate','pivot_results_77',case_id=case_id,details={'seed_type':seed_type,'count':len(rows)})
        return {'case_id':case_id,'seed_type':seed_type,'seed_value':val,'count':len(rows),'pivots':rows,'principle':'PivotResult != Claim'}
    def get(self,pivot_id):
        r=self.db.one('SELECT * FROM pivot_results_77 WHERE pivot_id=?',[pivot_id])
        if not r: raise KeyError(pivot_id)
        r['metadata']=loads(r.pop('metadata_json','{}'),{}); return r
    def list(self,case_id):
        rows=self.db.all('SELECT * FROM pivot_results_77 WHERE case_id=? ORDER BY created_at',[case_id])
        for r in rows: r['metadata']=loads(r.pop('metadata_json','{}'),{})
        return rows
