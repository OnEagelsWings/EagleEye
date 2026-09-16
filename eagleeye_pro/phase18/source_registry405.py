from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json

BUILD='405.0'
POLICY_ID='phase18.source-registry-v2.v405'
ALLOWED_HEALTH={'unknown','healthy','degraded','unavailable','disabled'}
ALLOWED_AUTH={'none','api_key','oauth2','session','licensed_account','local'}
ALLOWED_PROVENANCE={'primary_official','primary_public','licensed_primary','secondary_reputable','archive','local_mirror'}

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str)
def _sha(v): return hashlib.sha256(_canon(v).encode()).hexdigest()

class SourceRegistryV2405:
    """Metadata-only extension over the persistent Phase-17 source registry."""
    def __init__(self, db, audit, *, runtime384, actor='local-analyst'):
        self.db=db; self.audit=audit; self.runtime384=runtime384; self.registry382=runtime384.repository; self.actor=actor; self._init_schema(); self.seed_existing()
    def _init_schema(self):
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS source_registry_v2_405(
          source_id TEXT PRIMARY KEY, capability_json TEXT NOT NULL, auth_mode TEXT NOT NULL,
          rate_limit_policy TEXT NOT NULL, usage_policy TEXT NOT NULL, provenance_class TEXT NOT NULL,
          health_state TEXT NOT NULL, health_detail TEXT NOT NULL, health_checked_at TEXT NOT NULL,
          metadata_hash TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS source_health_history_405(
          id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL, health_state TEXT NOT NULL,
          health_detail TEXT NOT NULL, checked_at TEXT NOT NULL, actor TEXT NOT NULL, record_hash TEXT NOT NULL);
        '''); self.db.conn.commit()
    def _base_entries(self):
        try: return list(self.registry382.load_registry().all())
        except Exception: return []
    def _infer(self,e):
        auth='local' if e.local_dataset else ('licensed_account' if str(e.access_basis.value)=='licensed' else 'none')
        prov='local_mirror' if e.local_dataset else ('licensed_primary' if str(e.access_basis.value)=='licensed' else 'primary_public')
        capabilities=sorted(set(e.source_classes)|set(e.entity_types)|set(e.access_methods))
        rate=e.rate_limit_hint or 'unspecified_review_required'
        usage=e.terms_reference or e.license_reference or 'public_or_authorized_terms_review_required'
        return capabilities,auth,rate,usage,prov
    def seed_existing(self):
        added=0
        for e in self._base_entries():
            if self.db.one('SELECT 1 FROM source_registry_v2_405 WHERE source_id=?',(e.source_id,)): continue
            caps,auth,rate,usage,prov=self._infer(e); now=_now(); payload={'source_id':e.source_id,'capabilities':caps,'auth_mode':auth,'rate_limit_policy':rate,'usage_policy':usage,'provenance_class':prov,'health_state':'unknown','health_detail':'not yet externally validated','health_checked_at':''}
            h=_sha(payload)
            self.db.execute('INSERT INTO source_registry_v2_405 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(e.source_id,_canon(caps),auth,rate,usage,prov,'unknown','not yet externally validated','',h,now)); added+=1
        if added:self.audit.log('source_registry_v2_seeded','source_registry_v2_405','registry','',{'added':added,'network_requests':0})
        return added
    def list_sources(self):
        rows=[]
        for r in self.db.all('SELECT * FROM source_registry_v2_405 ORDER BY source_id'):
            d=dict(r); d['capabilities']=json.loads(d.pop('capability_json')); rows.append(d)
        return rows
    def update_metadata(self, *, source_id, capabilities, auth_mode, rate_limit_policy, usage_policy, provenance_class, actor=None):
        if auth_mode not in ALLOWED_AUTH: raise ValueError('invalid auth_mode')
        if provenance_class not in ALLOWED_PROVENANCE: raise ValueError('invalid provenance_class')
        if not rate_limit_policy.strip() or not usage_policy.strip(): raise ValueError('rate/usage policy required')
        if not self.db.one('SELECT 1 FROM source_registry_sources WHERE source_id=?',(source_id,)): raise KeyError('source not in governed registry')
        old=self.db.one('SELECT health_state,health_detail,health_checked_at FROM source_registry_v2_405 WHERE source_id=?',(source_id,)) or {'health_state':'unknown','health_detail':'not checked','health_checked_at':''}
        payload={'source_id':source_id,'capabilities':sorted(set(str(x).strip() for x in capabilities if str(x).strip())),'auth_mode':auth_mode,'rate_limit_policy':rate_limit_policy.strip(),'usage_policy':usage_policy.strip(),'provenance_class':provenance_class,'health_state':old['health_state'],'health_detail':old['health_detail'],'health_checked_at':old['health_checked_at']}
        now=_now(); h=_sha(payload)
        self.db.execute('''INSERT INTO source_registry_v2_405 VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET capability_json=excluded.capability_json,auth_mode=excluded.auth_mode,rate_limit_policy=excluded.rate_limit_policy,usage_policy=excluded.usage_policy,provenance_class=excluded.provenance_class,metadata_hash=excluded.metadata_hash,updated_at=excluded.updated_at''',(source_id,_canon(payload['capabilities']),auth_mode,payload['rate_limit_policy'],payload['usage_policy'],provenance_class,old['health_state'],old['health_detail'],old['health_checked_at'],h,now))
        self.audit.log('source_registry_v2_metadata_updated','source_registry_v2_405',source_id,'',{'actor':actor or self.actor,'network_requests':0}); return self.get(source_id)
    def record_health(self, *, source_id, health_state, detail, actor=None):
        if health_state not in ALLOWED_HEALTH: raise ValueError('invalid health_state')
        row=self.db.one('SELECT * FROM source_registry_v2_405 WHERE source_id=?',(source_id,))
        if not row: raise KeyError('source not registered')
        now=_now(); d=dict(row); payload={'source_id':source_id,'capabilities':json.loads(d['capability_json']),'auth_mode':d['auth_mode'],'rate_limit_policy':d['rate_limit_policy'],'usage_policy':d['usage_policy'],'provenance_class':d['provenance_class'],'health_state':health_state,'health_detail':detail.strip(),'health_checked_at':now}; h=_sha(payload)
        self.db.execute('UPDATE source_registry_v2_405 SET health_state=?,health_detail=?,health_checked_at=?,metadata_hash=?,updated_at=? WHERE source_id=?',(health_state,detail.strip(),now,h,now,source_id))
        rh=_sha({'source_id':source_id,'health_state':health_state,'health_detail':detail.strip(),'checked_at':now,'actor':actor or self.actor})
        self.db.execute('INSERT INTO source_health_history_405(source_id,health_state,health_detail,checked_at,actor,record_hash) VALUES(?,?,?,?,?,?)',(source_id,health_state,detail.strip(),now,actor or self.actor,rh))
        self.audit.log('source_health_recorded','source_registry_v2_405',source_id,'',{'health_state':health_state,'network_requests':0}); return self.get(source_id)
    def get(self,source_id):
        r=self.db.one('SELECT * FROM source_registry_v2_405 WHERE source_id=?',(source_id,))
        if not r: raise KeyError('source not registered')
        d=dict(r); d['capabilities']=json.loads(d.pop('capability_json')); return d
    def status(self):
        rows=self.list_sources(); health={k:0 for k in ALLOWED_HEALTH}
        for r in rows: health[r['health_state']]=health.get(r['health_state'],0)+1
        complete=sum(bool(r['capabilities']) and r['auth_mode'] in ALLOWED_AUTH and bool(r['rate_limit_policy']) and bool(r['usage_policy']) and r['provenance_class'] in ALLOWED_PROVENANCE for r in rows)
        return {'build':BUILD,'policy':POLICY_ID,'source_registry_v2':True,'sources':len(rows),'metadata_complete':complete,'health_counts':health,'network_execution':False,'automatic_live_enablement':False,'provenance_required':True,'human_review_required':True}
    def verify_integrity(self):
        bad=[]
        for r in self.list_sources():
            payload={k:r[k] for k in ('source_id','capabilities','auth_mode','rate_limit_policy','usage_policy','provenance_class','health_state','health_detail','health_checked_at')}
            if _sha(payload)!=r['metadata_hash']: bad.append(r['source_id'])
        return {'valid':not bad,'violations':bad}
