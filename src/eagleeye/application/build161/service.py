from __future__ import annotations
import base64, hashlib, json, os, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v: Any) -> str: return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)
def _hash(v: Any) -> str: return hashlib.sha256(_canon(v).encode('utf-8')).hexdigest()
def _fingerprint(secret: str) -> str: return hashlib.sha256(secret.encode('utf-8')).hexdigest()[:16]
def _dt(v: str|None):
    if not v: return None
    d=datetime.fromisoformat(v.replace('Z','+00:00')); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

class LocalCredentialVault161:
    """Local encrypted credential store. Secret values never enter SQLite or audit logs."""
    def __init__(self, root: Path|str):
        self.root=Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.key_path=self.root/'credential_master_161.key'; self.data_path=self.root/'credentials_161.enc'
        self._key=self._load_key()
    def _load_key(self)->bytes:
        raw=os.environ.get('EAGLEEYE_CREDENTIAL_MASTER_KEY','').strip()
        if raw:
            try:key=base64.urlsafe_b64decode(raw.encode())
            except Exception as exc: raise ValueError('invalid EAGLEEYE_CREDENTIAL_MASTER_KEY') from exc
            if len(key)!=32: raise ValueError('credential master key must decode to 32 bytes')
            return key
        if self.key_path.exists(): return self.key_path.read_bytes()
        key=AESGCM.generate_key(bit_length=256); self.key_path.write_bytes(key)
        try: os.chmod(self.key_path,0o600)
        except OSError: pass
        return key
    def _read(self)->dict[str,str]:
        if not self.data_path.exists(): return {}
        blob=self.data_path.read_bytes(); nonce,ct=blob[:12],blob[12:]
        return json.loads(AESGCM(self._key).decrypt(nonce,ct,b'eagleeye-161').decode('utf-8'))
    def _write(self,data:Mapping[str,str])->None:
        nonce=os.urandom(12); ct=AESGCM(self._key).encrypt(nonce,_canon(dict(data)).encode('utf-8'),b'eagleeye-161')
        self.data_path.write_bytes(nonce+ct)
        try: os.chmod(self.data_path,0o600)
        except OSError: pass
    def put(self,ref:str,secret:str)->None:
        data=self._read(); data[ref]=secret; self._write(data)
    def get(self,ref:str)->str:
        data=self._read()
        if ref not in data: raise KeyError('credential secret unavailable')
        return data[ref]
    def delete(self,ref:str)->None:
        data=self._read(); data.pop(ref,None); self._write(data)

class Build161OperationalConnectorAcceptanceService:
    BUILD='161.0'; MISSION='Operational Connector Acceptance and Credential Setup'
    POLICIES={
      'openalex_people':{'credential_required':True,'endpoint':'https://api.openalex.org/authors','auth':'query:api_key','credential_type':'api_key','probe_params':{'search':'Ada Lovelace','per-page':'1'},'official_docs':'https://developers.openalex.org/api-reference/authentication','rate_limit_source':'response_headers','public_only':True,'polling':'bounded'},
      'crossref_works':{'endpoint':'https://api.crossref.org/works','auth':'optional_mailto','credential_type':'mailto','credential_required':False,'probe_params':{'query.author':'Ada Lovelace','rows':'1'},'official_docs':'https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/','rate_limit_source':'response_headers','public_only':True,'polling':'bounded'},
      'orcid_public':{'credential_required':True,'endpoint':'https://pub.orcid.org/v3.0/search/','auth':'oauth_client_credentials','credential_type':'client_bundle','probe_params':{'q':'family-name:Lovelace'},'official_docs':'https://info.orcid.org/documentation/integration-guide/registering-a-public-api-client/','rate_limit_source':'documented_and_headers','public_only':True,'polling':'no_continuous_polling'},
      'bluesky_public':{'credential_required':False,'endpoint':'https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors','auth':'none','credential_type':'none','probe_params':{'q':'openai','limit':'1'},'official_docs':'https://docs.bsky.app/docs/advanced-guides/api-directory','rate_limit_source':'response_headers','public_only':True,'polling':'bounded'},
    }
    def __init__(self,db:Any,audit:Any,*,connector_runtime:Any,source_gate:Any,actor:str='system',vault_dir:Path|str='data/credential_vault_161'):
        self.db=db; self.audit=audit; self.connector_runtime=connector_runtime; self.source_gate=source_gate; self.actor=actor; self.vault=LocalCredentialVault161(vault_dir); self._seed()
    def _seed(self):
        from eagleeye.application.build154.service import ConnectorSpec
        for cid,p in self.POLICIES.items():
            try: self.connector_runtime.get_spec(cid)
            except KeyError:
                host=p['endpoint'].split('/')[2]
                records_path='actors' if cid=='bluesky_public' else ''
                self.connector_runtime.register(ConnectorSpec(cid,cid.replace('_',' ').title(),'1.0',p['endpoint'],(host,),records_path=records_path,terms_reference=p['official_docs']))
            self.db.execute('INSERT OR REPLACE INTO connector_runtime_policies_161 VALUES(?,?,?,?,?)',(cid,dumps(p),p['official_docs'],now_ts(),_hash({'connector_id':cid,'policy':p})))
    def policies(self)->list[dict[str,Any]]:
        return [dict(r) for r in self.db.all('SELECT * FROM connector_runtime_policies_161 ORDER BY connector_id')]
    def register_credential(self,connector_id:str,secret:str,*,credential_type:str,created_by:str,confirmation:str,expires_at:str|None=None,metadata:Mapping[str,Any]|None=None)->dict[str,Any]:
        if connector_id not in self.POLICIES: raise KeyError('unknown operational connector')
        if confirmation!=f'CREDENTIAL 161 {connector_id} SPEICHERN': raise PermissionError('explicit credential approval required')
        expected=self.POLICIES[connector_id]['credential_type']
        if expected=='none': raise ValueError('connector does not require credentials')
        if credential_type!=expected: raise ValueError(f'expected credential type {expected}')
        if not secret or len(secret)<4: raise ValueError('credential value too short')
        old=self.db.one('SELECT secret_ref FROM connector_credentials_161 WHERE connector_id=? AND credential_type=?',(connector_id,credential_type))
        ref=(old['secret_ref'] if old else new_id('secret161')); self.vault.put(ref,secret)
        cid=new_id('cred161'); payload={'connector_id':connector_id,'credential_type':credential_type,'secret_ref':ref,'fingerprint':_fingerprint(secret),'expires_at':expires_at,'metadata':dict(metadata or {})}
        self.db.execute('INSERT OR REPLACE INTO connector_credentials_161 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,connector_id,credential_type,ref,payload['fingerprint'],'stored',created_by,now_ts(),None,expires_at,dumps(metadata or {}),_hash(payload)))
        self.audit.log('credential_registered_161','connector_credential',cid,None,{'connector_id':connector_id,'credential_type':credential_type,'secret_fingerprint':payload['fingerprint']})
        return {**payload,'credential_id':cid,'secret_stored':True}
    def credential_status(self,connector_id:str)->dict[str,Any]:
        policy=self.POLICIES[connector_id]; required=bool(policy.get('credential_required', policy['credential_type']!='none'))
        row=self.db.one('SELECT * FROM connector_credentials_161 WHERE connector_id=? ORDER BY created_at DESC LIMIT 1',(connector_id,))
        valid=bool(row and row['status']=='stored' and (not row['expires_at'] or _dt(row['expires_at'])>datetime.now(timezone.utc)))
        return {'connector_id':connector_id,'required':required,'present':bool(row),'valid':valid,'credential_type':policy['credential_type'],'fingerprint':row['secret_fingerprint'] if row else None}
    def _auth(self,connector_id:str)->tuple[dict[str,str],dict[str,str]]:
        p=self.POLICIES[connector_id]; headers={'Accept':'application/json','User-Agent':'EagleEye-PersonOSINT/161 operational-acceptance'}; params=dict(p['probe_params'])
        if p['auth']=='none': return headers,params
        row=self.db.one('SELECT * FROM connector_credentials_161 WHERE connector_id=? ORDER BY created_at DESC LIMIT 1',(connector_id,))
        if not row:
            if not p.get('credential_required',True): return headers,params
            raise PermissionError('required credential missing')
        secret=self.vault.get(row['secret_ref'])
        if p['auth']=='query:api_key': params['api_key']=secret
        elif p['auth']=='optional_mailto': params['mailto']=secret
        elif p['auth']=='oauth_client_credentials':
            bundle=json.loads(secret); token=bundle.get('access_token')
            if not token: raise PermissionError('ORCID client bundle requires a current access_token')
            headers['Authorization']='Bearer '+token
        return headers,params
    def run_acceptance_probe(self,connector_id:str,*,environment:str='sandbox',checked_by:str,confirmation:str,transport:Callable[...,Mapping[str,Any]]|None=None)->dict[str,Any]:
        if connector_id not in self.POLICIES: raise KeyError('unknown operational connector')
        if environment not in {'sandbox','production'}: raise ValueError('invalid environment')
        if confirmation!=f'PROBE 161 {connector_id} AUSFUEHREN': raise PermissionError('explicit live probe approval required')
        headers,params=self._auth(connector_id); p=self.POLICIES[connector_id]; url=p['endpoint']+'?'+urlencode(params)
        started=time.perf_counter()
        try:
            if transport is None:
                import urllib.request
                req=urllib.request.Request(url,headers=headers,method='GET')
                with urllib.request.urlopen(req,timeout=15) as resp:
                    body=resp.read(2_000_000); status=resp.status; rh=dict(resp.headers.items())
            else:
                response=transport(url=url,headers=headers,timeout=15,max_bytes=2_000_000); status=int(response.get('status',0)); rh=dict(response.get('headers') or {}); body=response.get('body',b'')
                if isinstance(body,str): body=body.encode()
            latency=int((time.perf_counter()-started)*1000); parsed=json.loads(body.decode('utf-8'))
            schema=_hash(self._shape(parsed)); outcome='passed' if 200<=status<300 else 'failed'
            rate={k:v for k,v in rh.items() if k.lower() in {'retry-after','x-rate-limit-limit','x-rate-limit-remaining','x-ratelimit-limit','x-ratelimit-remaining'}}
            details={'endpoint_host':p['endpoint'].split('/')[2],'json_valid':True,'body_sha256':hashlib.sha256(body).hexdigest(),'credential_exposed':False}
        except Exception as exc:
            latency=int((time.perf_counter()-started)*1000); status=getattr(exc,'code',None); schema=None; rate={}; outcome='failed'; details={'error_type':type(exc).__name__,'error':str(exc)[:300],'credential_exposed':False}
        check_id=new_id('check161'); payload={'check_id':check_id,'connector_id':connector_id,'environment':environment,'check_type':'live_probe','outcome':outcome,'http_status':status,'latency_ms':latency,'rate_limit':rate,'schema_fingerprint':schema,'details':details}
        self.db.execute('INSERT INTO connector_acceptance_checks_161 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(check_id,connector_id,environment,'live_probe',outcome,status,latency,dumps(rate),schema,dumps(details),checked_by,now_ts(),_hash(payload)))
        self.audit.log('connector_probe_161','connector_acceptance_check',check_id,None,{'connector_id':connector_id,'outcome':outcome,'http_status':status,'latency_ms':latency})
        return payload
    def _shape(self,v:Any)->Any:
        if isinstance(v,dict): return {k:self._shape(v[k]) for k in sorted(v)[:100]}
        if isinstance(v,list): return [self._shape(v[0])] if v else []
        return type(v).__name__
    def readiness(self,connector_id:str,*,environment:str='production')->dict[str,Any]:
        p=self.POLICIES[connector_id]; cred=self.credential_status(connector_id); latest=self.db.one('SELECT * FROM connector_acceptance_checks_161 WHERE connector_id=? AND outcome=? ORDER BY checked_at DESC LIMIT 1',(connector_id,'passed'))
        gate=None
        try: gate=self.source_gate.evaluate(connector_id) if hasattr(self.source_gate,'evaluate') else None
        except Exception: gate=None
        requirements={'policy_registered':True,'credential_ready':(not cred['required'] or cred['valid']),'live_probe_passed':bool(latest),'source_gate_production':bool(gate and str(gate.get('gate_state','')).upper()=='PRODUCTION')}
        score=sum(1 for v in requirements.values() if v)/len(requirements); readiness='production_ready' if score==1 else ('sandbox_ready' if requirements['live_probe_passed'] and requirements['credential_ready'] else 'not_ready')
        findings=[k for k,v in requirements.items() if not v]; sid=new_id('ready161'); payload={'snapshot_id':sid,'connector_id':connector_id,'environment':environment,'readiness':readiness,'score':score,'requirements':requirements,'findings':findings}
        self.db.execute('INSERT INTO connector_readiness_snapshots_161 VALUES(?,?,?,?,?,?,?,?,?)',(sid,connector_id,environment,readiness,score,dumps(requirements),dumps(findings),now_ts(),_hash(payload)))
        return payload
    def accept(self,connector_id:str,*,environment:str,approved_by:str,reason:str,confirmation:str,expires_at:str|None=None)->dict[str,Any]:
        ready=self.readiness(connector_id,environment=environment)
        if environment=='production' and ready['readiness']!='production_ready': raise PermissionError('connector is not production ready')
        if confirmation!=f'CONNECTOR 161 {connector_id} {environment.upper()} ABNEHMEN': raise PermissionError('explicit operational acceptance required')
        did=new_id('accept161'); evidence={'readiness_snapshot_id':ready['snapshot_id'],'score':ready['score'],'requirements':ready['requirements']}; payload={'decision_id':did,'connector_id':connector_id,'environment':environment,'decision':'accepted','reason':reason,'evidence':evidence,'approved_by':approved_by,'expires_at':expires_at}
        self.db.execute('INSERT INTO connector_acceptance_decisions_161 VALUES(?,?,?,?,?,?,?,?,?,?)',(did,connector_id,environment,'accepted',reason,dumps(evidence),approved_by,now_ts(),expires_at,_hash(payload)))
        self.audit.log('connector_accepted_161','connector_acceptance',did,None,{'connector_id':connector_id,'environment':environment,'score':ready['score']})
        return payload
    def operational_matrix(self)->list[dict[str,Any]]:
        out=[]
        for cid,p in self.POLICIES.items():
            r=self.readiness(cid)
            out.append({'connector_id':cid,'endpoint':p['endpoint'],'auth':p['auth'],'credential':self.credential_status(cid),'readiness':r['readiness'],'score':r['score'],'findings':r['findings'],'public_only':True})
        return out
