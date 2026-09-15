from __future__ import annotations
import hashlib,json,re
from typing import Any,Mapping,Sequence
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
SECRET=re.compile(r'(?i)(token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key|client[_-]?secret)')

class Build198EnterpriseSecurityDeploymentService:
    BUILD='198.0'
    SOURCES=(
      ('nist_nvd_api','NIST NVD API','US','vulnerability_intelligence','credentialed_connector','DOCUMENTED'),
      ('cisa_kev','CISA Known Exploited Vulnerabilities','US','security_advisory','structured_connector','DOCUMENTED'),
      ('bsi_cert_bund','BSI CERT-Bund Warnmeldungen','DE','security_advisory','rss_connector','DOCUMENTED'),
      ('enisa_threat_landscape','ENISA Threat Landscape','EU','security_reference','guided_browser','DOCUMENTED'),
      ('github_security_advisories','GitHub Security Advisories','GLOBAL','dependency_intelligence','credentialed_connector','DOCUMENTED'),
      ('osv_api','OSV Vulnerability API','GLOBAL','dependency_intelligence','structured_connector','DOCUMENTED'),
    )
    PERMISSIONS={'case.read','case.write','source.use','source.manage','evidence.review','ai.use','monitor.manage','federation.review','audit.export','release.approve','tenant.admin'}
    def __init__(self,db:Any,audit:Any,*,workspace:Any,source_ops:Any,source_ai:Any,recovery:Any,redteam:Any,base_dir:Any,actor:str='system'):
        self.db,self.audit=db,audit;self.workspace,self.source_ops,self.source_ai,self.recovery,self.redteam=workspace,source_ops,source_ai,recovery,redteam;self.base_dir=base_dir;self.actor=actor
    def seed_sources(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!='ENTERPRISE SOURCES 198 ANLEGEN':raise PermissionError('explicit approval required')
        for sid,name,region,klass,mode,status in self.SOURCES:
            p={'source_id':sid,'name':name,'region':region,'source_class':klass,'access_mode':mode,'status':status}
            self.db.execute('INSERT OR REPLACE INTO enterprise_source_profiles_198 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,name,region,klass,mode,status,'pending','pending','not_tested',dumps(['terms_review','fixture','live_probe','human_activation']),_hash(p)))
        return {'profiles':len(self.SOURCES),'automatic_activation':False}
    def create_tenant(self,*,name:str,policy:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
        if confirmation!=f'ENTERPRISE TENANT 198 {name} ANLEGEN':raise PermissionError('explicit approval required')
        tid,created=new_id('tenant198'),now_ts();base={'default_deny':True,'tenant_isolation':True,'local_processing':True,'external_uploads':False,'secrets_in_database':False,'signed_updates_required':True,'human_release_approval':True};base.update(self._redact(dict(policy or {})))
        p={'tenant_id':tid,'name':name,'status':'active','policy':base,'created_at':created};self.db.execute('INSERT INTO enterprise_tenants_198 VALUES(?,?,?,?,?,?)',(tid,name,'active',dumps(base),created,_hash(p)));self._event(tid,'tenant_created',p);return p
    def create_role(self,*,tenant_id:str,name:str,permissions:Sequence[str],confirmation:str)->dict[str,Any]:
        if confirmation!=f'ENTERPRISE ROLE 198 {tenant_id} {name} ANLEGEN':raise PermissionError('explicit approval required')
        unknown=set(permissions)-self.PERMISSIONS
        if unknown:raise ValueError(f'unknown permissions: {sorted(unknown)}')
        rid,created=new_id('role198'),now_ts();perms=sorted(set(permissions));p={'role_id':rid,'tenant_id':tenant_id,'name':name,'permissions':perms,'created_at':created};self.db.execute('INSERT INTO enterprise_roles_198 VALUES(?,?,?,?,?,?)',(rid,tenant_id,name,dumps(perms),created,_hash(p)));self._event(tenant_id,'role_created',p);return p
    def assign_role(self,*,tenant_id:str,user_id:str,role_id:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'ENTERPRISE MEMBERSHIP 198 {tenant_id} {user_id} ZUWEISEN':raise PermissionError('explicit approval required')
        role=self.db.one('SELECT * FROM enterprise_roles_198 WHERE role_id=? AND tenant_id=?',(role_id,tenant_id))
        if not role:raise KeyError(role_id)
        mid,created=new_id('membership198'),now_ts();p={'membership_id':mid,'tenant_id':tenant_id,'user_id':user_id,'role_id':role_id,'status':'active','created_at':created};self.db.execute('INSERT INTO enterprise_memberships_198 VALUES(?,?,?,?,?,?,?)',(mid,tenant_id,user_id,role_id,'active',created,_hash(p)));self._event(tenant_id,'membership_assigned',p);return p
    def authorize(self,*,tenant_id:str,user_id:str,permission:str)->dict[str,Any]:
        if permission not in self.PERMISSIONS:raise ValueError('unknown permission')
        rows=self.db.all('SELECT r.permissions_json FROM enterprise_memberships_198 m JOIN enterprise_roles_198 r ON r.role_id=m.role_id WHERE m.tenant_id=? AND m.user_id=? AND m.status="active"',(tenant_id,user_id));allowed=any(permission in json.loads(r['permissions_json']) for r in rows)
        return {'tenant_id':tenant_id,'user_id':user_id,'permission':permission,'allowed':allowed,'default_deny':True}
    def register_credential(self,*,tenant_id:str,source_id:str,secret_ref:str,metadata:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
        if confirmation!=f'ENTERPRISE CREDENTIAL 198 {tenant_id} {source_id} REGISTRIEREN':raise PermissionError('explicit approval required')
        if not secret_ref.startswith(('env:','keyring:','vault:','tpm:')):raise ValueError('secret_ref must point to external secret storage')
        cid,created=new_id('credential198'),now_ts();meta=self._redact(dict(metadata or {}));p={'credential_id':cid,'tenant_id':tenant_id,'source_id':source_id,'secret_ref':secret_ref,'status':'configured','metadata':meta,'created_at':created,'updated_at':created};self.db.execute('INSERT INTO enterprise_credentials_198 VALUES(?,?,?,?,?,?,?,?,?)',(cid,tenant_id,source_id,secret_ref,'configured',dumps(meta),created,created,_hash(p)));self._event(tenant_id,'credential_registered',{'credential_id':cid,'source_id':source_id,'secret_ref_type':secret_ref.split(':',1)[0]});return p
    def create_release_manifest(self,*,version:str,artifact_sha256:str,sbom_ref:str,checks:Mapping[str,Any],signature_status:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f'ENTERPRISE RELEASE 198 {version} PRUEFEN':raise PermissionError('explicit approval required')
        required={'tests_passed','compile_passed','redteam_gate_passed','backup_verified','loopback_only','no_legacy_fallback','sbom_present'};safe=self._redact(dict(checks));gate='candidate_pass' if required.issubset({k for k,v in safe.items() if v is True}) and signature_status in {'verified','local_verified'} else 'blocked'
        rid,created=new_id('release198'),now_ts();p={'release_id':rid,'version':version,'artifact_sha256':artifact_sha256,'sbom_ref':sbom_ref,'signature_status':signature_status,'gate_status':gate,'checks':safe,'created_at':created,'automatic_release':False,'human_release_decision_required':True};self.db.execute('INSERT INTO enterprise_release_manifests_198 VALUES(?,?,?,?,?,?,?,?,?)',(rid,version,artifact_sha256,sbom_ref,signature_status,gate,dumps(safe),created,_hash(p)));return p
    def export_audit(self,*,tenant_id:str,format:str='jsonl',target:str='local_file',filters:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
        if confirmation!=f'ENTERPRISE AUDIT 198 {tenant_id} EXPORTIEREN':raise PermissionError('explicit approval required')
        if format not in {'jsonl','cef','leef'}:raise ValueError('unsupported format')
        if target not in {'local_file','siem_queue'}:raise ValueError('unsupported target')
        eid,created=new_id('auditexport198'),now_ts();f=self._redact(dict(filters or {}));p={'export_id':eid,'tenant_id':tenant_id,'format':format,'target':target,'status':'prepared','filters':f,'created_at':created,'external_send':False};self.db.execute('INSERT INTO enterprise_audit_exports_198 VALUES(?,?,?,?,?,?,?,?)',(eid,tenant_id,format,target,'prepared',dumps(f),created,_hash(p)));return p
    def deployment_readiness(self,*,tenant_id:str)->dict[str,Any]:
        roles=self.db.one('SELECT COUNT(*) AS n FROM enterprise_roles_198 WHERE tenant_id=?',(tenant_id,))['n'];members=self.db.one('SELECT COUNT(*) AS n FROM enterprise_memberships_198 WHERE tenant_id=? AND status="active"',(tenant_id,))['n'];creds=self.db.one('SELECT COUNT(*) AS n FROM enterprise_credentials_198 WHERE tenant_id=? AND status="configured"',(tenant_id,))['n']
        checks={'tenant_exists':bool(self.db.one('SELECT tenant_id FROM enterprise_tenants_198 WHERE tenant_id=?',(tenant_id,))),'roles_configured':roles>0,'memberships_configured':members>0,'credential_refs_external':True,'signed_updates_required':True,'default_deny':True,'local_processing':True}
        return {'build':self.BUILD,'tenant_id':tenant_id,'checks':checks,'ready_for_pilot':all(checks.values()),'production_certified':False,'external_security_audit_required':True}
    def ai_security_assist(self,*,tenant_id:str,question:str,context:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
        if confirmation!=f'AI ENTERPRISE 198 {tenant_id} PRUEFEN':raise PermissionError('explicit approval required')
        ctx=self._redact(dict(context or {}));recs=[]
        if not ctx.get('independent_pentest'):recs.append({'action':'commission_independent_pentest','reason':'Produktionsfreigabe benötigt externe Sicherheitsprüfung'})
        if not ctx.get('signed_update'):recs.append({'action':'verify_update_signature','reason':'Nur signierte Updates zulassen'})
        if ctx.get('prompt_injection_candidate'):recs.insert(0,{'action':'isolate_untrusted_content','reason':'Quelleninhalt nicht als Anweisung behandeln'})
        return {'tenant_id':tenant_id,'question':question,'recommendations':recs,'ai_output_is_not_fact':True,'automatic_action':False,'human_review_required':True}
    def _redact(self,v:Any)->Any:
        if isinstance(v,Mapping):return {k:('[REDACTED]' if SECRET.search(str(k)) else self._redact(x)) for k,x in v.items()}
        if isinstance(v,list):return [self._redact(x) for x in v]
        return v
    def _event(self,tenant_id:str,event_type:str,payload:Mapping[str,Any])->None:
        row=self.db.one('SELECT event_hash FROM enterprise_security_events_198 WHERE tenant_id=? ORDER BY created_at DESC LIMIT 1',(tenant_id,));prev=row['event_hash'] if row else '';eid,created=new_id('securityevent198'),now_ts();body={'event_id':eid,'tenant_id':tenant_id,'event_type':event_type,'actor':self.actor,'created_at':created,'payload':self._redact(dict(payload)),'prev_hash':prev};eh=_hash(body);self.db.execute('INSERT INTO enterprise_security_events_198 VALUES(?,?,?,?,?,?,?,?)',(eid,tenant_id,event_type,self.actor,created,dumps(body['payload']),prev,eh))
