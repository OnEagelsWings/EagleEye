from __future__ import annotations
import re, hashlib
from eagleeye_pro.audit.service import AuditService
from eagleeye_pro.core.database import Database, dumps, loads, new_id, now_ts
from eagleeye_pro.security.url_policy import URLPolicy
DOMAIN_RE=re.compile(r'^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$')
class RDAPDNSIntel83Service:
    def __init__(self,db:Database,audit:AuditService): self.db=db; self.audit=audit; self.ensure_schema()
    def ensure_schema(self):
        self.db.conn.executescript("""CREATE TABLE IF NOT EXISTS domain_intel_83 (intel_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, domain TEXT NOT NULL, intel_type TEXT NOT NULL, status TEXT DEFAULT 'candidate_not_claim', payload_hash TEXT NOT NULL, signals_json TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);"""); self.db.conn.commit()
    def _domain(self,d):
        d=(d or '').strip().lower().replace('https://','').replace('http://','').split('/')[0].replace('www.','')
        if not DOMAIN_RE.match(d) or URLPolicy.is_private_or_local_host(d): raise ValueError('invalid_or_private_domain')
        return d
    def prepare_lookup(self,case_id,domain):
        d=self._domain(domain); return {'case_id':case_id,'domain':d,'allowed_lookup_types':['rdap','dns_a','dns_mx','dns_ns','whois_reference_manual'],'status':'prepared_manual_or_approved_provider','note':'Results are domain candidates; person attribution requires review.'}
    def import_payload(self,case_id,domain,intel_type,payload):
        d=self._domain(domain); txt=dumps(payload or {}); low=txt.lower(); signals=[]
        for key in ['registrant','organization','nameserver','mx','created','updated','country']:
            if key in low: signals.append(key)
        iid=new_id('di83'); self.db.execute('INSERT INTO domain_intel_83 VALUES(?,?,?,?,?,?,?,?,?)',[iid,case_id,d,intel_type,'candidate_not_claim',hashlib.sha256(txt.encode()).hexdigest(),dumps(sorted(set(signals))),txt,now_ts()]); self.audit.log('import','domain_intel_83',iid,case_id,{'domain':d,'intel_type':intel_type,'signals':signals}); return self.get(iid)
    def get(self,iid):
        r=self.db.one('SELECT * FROM domain_intel_83 WHERE intel_id=?',[iid])
        if not r: raise KeyError(iid)
        r['signals']=loads(r.pop('signals_json','[]'),[]); r['payload']=loads(r.pop('payload_json','{}'),{}); return r
    def list(self,case_id): return [self.get(r['intel_id']) for r in self.db.all('SELECT intel_id FROM domain_intel_83 WHERE case_id=? ORDER BY created_at',[case_id])]
