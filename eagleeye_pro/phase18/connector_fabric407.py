from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, secrets
from typing import Any, Mapping

BUILD='407.0'
POLICY_ID='phase18.connector-data-fabric.v407'
ADAPTER_KINDS={'rest_api','registry','bulk_dataset','local_mirror','crawler','archive','internal_evidence'}
REMOTE_KINDS={'rest_api','registry','crawler','archive'}
LOCAL_KINDS={'bulk_dataset','local_mirror','internal_evidence'}
MAX_IMPORTED_BYTES=10_000_000

def _now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v):
    raw=v if isinstance(v,(bytes,bytearray)) else _canon(v).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()
def _id(prefix): return prefix+'_'+secrets.token_hex(12)

class ConnectorDataFabric407:
    """Governed connector/data-fabric control plane.

    Build 407 classifies registered sources into adapter kinds, creates review-first
    acquisition plans, and normalizes caller-supplied/imported results into immutable
    intake envelopes. It performs no network requests and grants no execution authority.
    """
    def __init__(self,db,audit,*,registry405,governance=None,actor='local-analyst'):
        self.db=db; self.audit=audit; self.registry405=registry405; self.governance=governance; self.actor=actor
        self._init_schema(); self.seed_from_registry()
    def _init_schema(self):
        self.db.conn.executescript('''
        CREATE TABLE IF NOT EXISTS connector_fabric_adapters_407(
          source_id TEXT PRIMARY KEY, adapter_kind TEXT NOT NULL, capability_json TEXT NOT NULL,
          remote INTEGER NOT NULL, requires_go INTEGER NOT NULL, provenance_required INTEGER NOT NULL,
          adapter_hash TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS connector_fabric_plan_407(
          plan_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL, adapter_kind TEXT NOT NULL,
          operation TEXT NOT NULL, params_json TEXT NOT NULL, source_metadata_hash TEXT NOT NULL,
          requires_go INTEGER NOT NULL, network_execution INTEGER NOT NULL, execution_authority INTEGER NOT NULL,
          created_by TEXT NOT NULL, created_at TEXT NOT NULL, plan_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS connector_fabric_intake_407(
          intake_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, source_id TEXT NOT NULL, adapter_kind TEXT NOT NULL,
          plan_id TEXT NOT NULL, media_type TEXT NOT NULL, payload_hash TEXT NOT NULL, payload_bytes INTEGER NOT NULL,
          provenance_json TEXT NOT NULL, imported_by TEXT NOT NULL, imported_at TEXT NOT NULL, record_hash TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_connector_plan_case_407 ON connector_fabric_plan_407(case_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_connector_intake_case_407 ON connector_fabric_intake_407(case_id,source_id,imported_at);
        '''); self.db.conn.commit()
    def _infer_kind(self,row:Mapping[str,Any])->str:
        caps={str(x).lower() for x in (row.get('capabilities') or [])}
        prov=str(row.get('provenance_class') or '')
        auth=str(row.get('auth_mode') or '')
        joined=' '.join(caps)
        if prov=='local_mirror' or 'local' in joined: return 'local_mirror'
        if 'archive' in joined or prov=='archive': return 'archive'
        if 'crawl' in joined or 'crawler' in joined or 'html' in joined: return 'crawler'
        if 'bulk' in joined or 'download' in joined or 'dataset' in joined: return 'bulk_dataset'
        if 'registry' in joined or 'register' in joined: return 'registry'
        if auth in {'api_key','oauth2'} or 'api' in joined or 'json' in joined: return 'rest_api'
        return 'registry'
    def seed_from_registry(self):
        changed=0
        for row in self.registry405.list_sources():
            kind=self._infer_kind(row); caps=sorted(set(row.get('capabilities') or [])); remote=1 if kind in REMOTE_KINDS else 0
            body={'source_id':row['source_id'],'adapter_kind':kind,'capabilities':caps,'remote':bool(remote),'requires_go':True,'provenance_required':True}
            h=_sha(body); old=self.db.one('SELECT adapter_hash FROM connector_fabric_adapters_407 WHERE source_id=?',(row['source_id'],))
            if old and str(old['adapter_hash'])==h: continue
            self.db.execute('''INSERT INTO connector_fabric_adapters_407 VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET adapter_kind=excluded.adapter_kind,capability_json=excluded.capability_json,remote=excluded.remote,requires_go=excluded.requires_go,provenance_required=excluded.provenance_required,adapter_hash=excluded.adapter_hash,updated_at=excluded.updated_at''',(row['source_id'],kind,_canon(caps),remote,1,1,h,_now())); changed+=1
        if changed:self.audit.log('connector_fabric_seeded','connector_fabric_adapters_407','fabric','',{'changed':changed,'network_requests':0,'execution_authority':False})
        return changed
    def adapters(self):
        out=[]
        for r in self.db.all('SELECT * FROM connector_fabric_adapters_407 ORDER BY source_id'):
            d=dict(r); d['capabilities']=json.loads(d.pop('capability_json')); d['remote']=bool(d['remote']); d['requires_go']=bool(d['requires_go']); d['provenance_required']=bool(d['provenance_required']); out.append(d)
        return out
    def adapter(self,source_id):
        r=self.db.one('SELECT * FROM connector_fabric_adapters_407 WHERE source_id=?',(source_id,))
        if not r: raise KeyError('source has no fabric adapter')
        d=dict(r); d['capabilities']=json.loads(d.pop('capability_json')); d['remote']=bool(d['remote']); d['requires_go']=bool(d['requires_go']); d['provenance_required']=bool(d['provenance_required']); return d
    def _authorize(self,identity,case_id,object_id=''):
        if not identity: raise PermissionError('active case identity required')
        if self.governance is None: raise PermissionError('governance unavailable')
        return self.governance.authorize(identity,case_id=case_id,capability='research.run',object_type='connector_fabric_407',object_id=object_id or case_id)
    def plan(self,*,case_id,source_id,operation,params:Mapping[str,Any]|None=None,identity:Mapping[str,Any]|None=None):
        case_id=str(case_id).strip(); operation=str(operation).strip(); params=dict(params or {})
        if not case_id: raise ValueError('case_id required')
        if not operation: raise ValueError('operation required')
        self._authorize(identity,case_id,source_id)
        src=self.registry405.get(source_id); ad=self.adapter(source_id)
        if src['health_state']=='disabled': raise PermissionError('source disabled')
        actor=str((identity or {}).get('user_id') or (identity or {}).get('username') or self.actor)
        metadata_hash=str(src['metadata_hash']); body={'case_id':case_id,'source_id':source_id,'adapter_kind':ad['adapter_kind'],'operation':operation,'params':params,'source_metadata_hash':metadata_hash,'requires_go':True,'network_execution':False,'execution_authority':False}
        ph=_sha(body); pid='cf407_'+ph[:24]; now=_now()
        self.db.execute('INSERT OR IGNORE INTO connector_fabric_plan_407 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,source_id,ad['adapter_kind'],operation,_canon(params),metadata_hash,1,0,0,actor,now,ph))
        self.audit.log('connector_fabric_plan_created','connector_fabric_plan_407',pid,case_id,{'source_id':source_id,'adapter_kind':ad['adapter_kind'],'requires_go':True,'network_requests':0,'execution_authority':False})
        return self.get_plan(pid)
    def get_plan(self,plan_id):
        r=self.db.one('SELECT * FROM connector_fabric_plan_407 WHERE plan_id=?',(plan_id,))
        if not r: raise KeyError('plan not found')
        d=dict(r); d['params']=json.loads(d.pop('params_json')); d['requires_go']=bool(d['requires_go']); d['network_execution']=bool(d['network_execution']); d['execution_authority']=bool(d['execution_authority']); return d
    def import_result(self,*,plan_id,payload:bytes|str,media_type,provenance:Mapping[str,Any],identity:Mapping[str,Any]|None=None):
        plan=self.get_plan(plan_id); self._authorize(identity,plan['case_id'],plan_id); raw=payload.encode('utf-8') if isinstance(payload,str) else bytes(payload)
        if not raw: raise ValueError('payload required')
        if len(raw)>MAX_IMPORTED_BYTES: raise ValueError('payload exceeds Build 407 intake limit')
        prov=dict(provenance or {})
        required=('retrieved_at','origin_ref','collector')
        missing=[k for k in required if not str(prov.get(k) or '').strip()]
        if missing: raise ValueError('provenance missing: '+','.join(missing))
        # Imported content is an intake artifact only; it is never evidence merely by import.
        prov.update({'source_id':plan['source_id'],'plan_id':plan_id,'promotion_status':'unreviewed_intake','network_execution_by_build407':False})
        actor=str((identity or {}).get('user_id') or (identity or {}).get('username') or self.actor); now=_now(); ih=_id('intake407'); ph=_sha(raw)
        record={'intake_id':ih,'case_id':plan['case_id'],'source_id':plan['source_id'],'adapter_kind':plan['adapter_kind'],'plan_id':plan_id,'media_type':str(media_type or 'application/octet-stream'),'payload_hash':ph,'payload_bytes':len(raw),'provenance':prov,'imported_by':actor,'imported_at':now}
        rh=_sha(record)
        self.db.execute('INSERT INTO connector_fabric_intake_407 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(ih,plan['case_id'],plan['source_id'],plan['adapter_kind'],plan_id,record['media_type'],ph,len(raw),_canon(prov),actor,now,rh))
        self.audit.log('connector_fabric_result_imported','connector_fabric_intake_407',ih,plan['case_id'],{'source_id':plan['source_id'],'adapter_kind':plan['adapter_kind'],'payload_hash':ph,'payload_bytes':len(raw),'evidence_promoted':False,'network_requests':0})
        return self.intake(ih)
    def intake(self,intake_id):
        r=self.db.one('SELECT * FROM connector_fabric_intake_407 WHERE intake_id=?',(intake_id,))
        if not r: raise KeyError('intake not found')
        d=dict(r); d['provenance']=json.loads(d.pop('provenance_json')); return d
    def verify_integrity(self):
        bad=[]
        for a in self.adapters():
            body={'source_id':a['source_id'],'adapter_kind':a['adapter_kind'],'capabilities':a['capabilities'],'remote':a['remote'],'requires_go':a['requires_go'],'provenance_required':a['provenance_required']}
            if _sha(body)!=a['adapter_hash']: bad.append({'table':'connector_fabric_adapters_407','id':a['source_id']})
        plan_ids=set()
        for r in self.db.all('SELECT * FROM connector_fabric_plan_407'):
            d=dict(r); body={'case_id':d['case_id'],'source_id':d['source_id'],'adapter_kind':d['adapter_kind'],'operation':d['operation'],'params':json.loads(d['params_json']),'source_metadata_hash':d['source_metadata_hash'],'requires_go':bool(d['requires_go']),'network_execution':bool(d['network_execution']),'execution_authority':bool(d['execution_authority'])}
            plan_ids.add(d['plan_id'])
            if _sha(body)!=d['plan_hash']: bad.append({'table':'connector_fabric_plan_407','id':d['plan_id'],'reason':'plan_hash_mismatch'})
        for r in self.db.all('SELECT * FROM connector_fabric_intake_407'):
            d=dict(r);
            if d['plan_id'] not in plan_ids: bad.append({'table':'connector_fabric_intake_407','id':d['intake_id'],'reason':'orphaned_plan'})
            rec={'intake_id':d['intake_id'],'case_id':d['case_id'],'source_id':d['source_id'],'adapter_kind':d['adapter_kind'],'plan_id':d['plan_id'],'media_type':d['media_type'],'payload_hash':d['payload_hash'],'payload_bytes':d['payload_bytes'],'provenance':json.loads(d['provenance_json']),'imported_by':d['imported_by'],'imported_at':d['imported_at']}
            if _sha(rec)!=d['record_hash']: bad.append({'table':'connector_fabric_intake_407','id':d['intake_id']})
        return {'valid':not bad,'violations':bad}
    def status(self):
        ads=self.adapters(); kinds={k:0 for k in sorted(ADAPTER_KINDS)}
        for a in ads:kinds[a['adapter_kind']]=kinds.get(a['adapter_kind'],0)+1
        plans=int((self.db.one('SELECT COUNT(*) c FROM connector_fabric_plan_407') or {}).get('c',0)); intake=int((self.db.one('SELECT COUNT(*) c FROM connector_fabric_intake_407') or {}).get('c',0))
        return {'build':BUILD,'policy':POLICY_ID,'connector_data_fabric':True,'adapters':len(ads),'adapter_kinds':kinds,'plans':plans,'intake_records':intake,'network_execution':False,'execution_authority':False,'automatic_go':False,'automatic_evidence_promotion':False,'provenance_required':True,'source_registry_integrity_required':True}
