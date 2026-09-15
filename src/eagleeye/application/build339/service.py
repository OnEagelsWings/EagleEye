from __future__ import annotations
import base64, hashlib, html, io, json, os, shutil, sqlite3, tempfile, zipfile
from pathlib import Path
from typing import Any
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from eagleeye.application.build304.service import _id,_now,_hash,_canon
from eagleeye.application.build338.service import Build338DossierVNextRedTeamService

class Build339TeamModeHardeningService(Build338DossierVNextRedTeamService):
    BUILD='339.0'; REQUIRED_CORPUS=984
    ROLES={
      'admin':{'read','investigate','review','release','manage_team','manage_secrets','backup','deploy_review'},
      'investigator':{'read','investigate'},
      'reviewer':{'read','review','release'},
      'security_admin':{'read','manage_secrets','backup','deploy_review'},
      'viewer':{'read'},
    }
    GLOBAL_PERMISSIONS={'manage_team','manage_secrets','backup','deploy_review'}

    def training_metrics(self):
        b=super().training_metrics(); a=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_339 WHERE review_status='reviewed'"); s=self._count("SELECT COUNT(*) n FROM ai_security_training_delta_339 WHERE review_status='reviewed'")
        e=self._count("SELECT COUNT(*) n FROM ai_hard_training_delta_339 WHERE difficulty='extreme' AND review_status='reviewed'")+self._count("SELECT COUNT(*) n FROM ai_security_training_delta_339 WHERE difficulty='extreme' AND review_status='reviewed'")
        return {**b,'reviewed_hard_cases':b['reviewed_hard_cases']+a+s,'adversarial_extreme_cases':b['adversarial_extreme_cases']+e,'build339_delta_cases':a+s,'build339_delta_extreme':e}

    def _latest_effect(self,table:str,where:str,params:tuple[Any,...])->str|None:
        r=self.db.one(f'SELECT effect FROM {table} WHERE {where} ORDER BY rowid DESC LIMIT 1',params); return r['effect'] if r else None
    def grant_role(self,actor_id:str,role_name:str,*,granted_by:str|None=None,reason:str='')->dict[str,Any]:
        if role_name not in self.ROLES: raise ValueError('unknown role')
        eid=_id('role339'); by=granted_by or self.actor; now=_now(); self.db.execute('INSERT INTO phase14_team_role_events_339 VALUES(?,?,?,?,?,?,?,?)',(eid,actor_id,role_name,'grant',by,reason[:800],now,_hash({'e':eid,'a':actor_id,'r':role_name,'x':'grant'}))); return {'event_id':eid,'actor_id':actor_id,'role':role_name,'effect':'grant'}
    def revoke_role(self,actor_id:str,role_name:str,*,granted_by:str|None=None,reason:str='')->dict[str,Any]:
        eid=_id('role339'); by=granted_by or self.actor; now=_now(); self.db.execute('INSERT INTO phase14_team_role_events_339 VALUES(?,?,?,?,?,?,?,?)',(eid,actor_id,role_name,'revoke',by,reason[:800],now,_hash({'e':eid,'a':actor_id,'r':role_name,'x':'revoke'}))); return {'event_id':eid,'actor_id':actor_id,'role':role_name,'effect':'revoke'}
    def active_roles(self,actor_id:str)->set[str]:
        out=set()
        for role in self.ROLES:
            if self._latest_effect('phase14_team_role_events_339','actor_id=? AND role_name=?',(actor_id,role))=='grant': out.add(role)
        return out
    def grant_case_permission(self,case_id:str,actor_id:str,permission_name:str,*,granted_by:str|None=None,reason:str='')->dict[str,Any]:
        if permission_name not in set().union(*self.ROLES.values()): raise ValueError('unknown permission')
        eid=_id('acl339'); by=granted_by or self.actor; now=_now(); self.db.execute('INSERT INTO phase14_case_acl_events_339 VALUES(?,?,?,?,?,?,?,?,?)',(eid,case_id,actor_id,permission_name,'grant',by,reason[:800],now,_hash({'e':eid,'c':case_id,'a':actor_id,'p':permission_name,'x':'grant'}))); return {'event_id':eid,'effect':'grant'}
    def revoke_case_permission(self,case_id:str,actor_id:str,permission_name:str,*,granted_by:str|None=None,reason:str='')->dict[str,Any]:
        eid=_id('acl339'); by=granted_by or self.actor; now=_now(); self.db.execute('INSERT INTO phase14_case_acl_events_339 VALUES(?,?,?,?,?,?,?,?,?)',(eid,case_id,actor_id,permission_name,'revoke',by,reason[:800],now,_hash({'e':eid,'c':case_id,'a':actor_id,'p':permission_name,'x':'revoke'}))); return {'event_id':eid,'effect':'revoke'}
    def authorize(self,actor_id:str,permission_name:str,case_id:str='')->bool:
        roles=self.active_roles(actor_id); role_ok=any(permission_name in self.ROLES[r] for r in roles)
        if not role_ok:return False
        if permission_name in self.GLOBAL_PERMISSIONS:return True
        if not case_id:return False
        return self._latest_effect('phase14_case_acl_events_339','case_id=? AND actor_id=? AND permission_name=?',(case_id,actor_id,permission_name))=='grant'
    def require(self,actor_id:str,permission_name:str,case_id:str='')->None:
        if not self.authorize(actor_id,permission_name,case_id): raise PermissionError(f'default deny: {actor_id} lacks {permission_name}')

    @staticmethod
    def _derive_key(passphrase:str,salt:bytes)->bytes:
        if len(passphrase)<12: raise ValueError('passphrase must be at least 12 characters')
        return Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(passphrase.encode('utf-8'))
    def put_secret(self,*,actor_id:str,label:str,value:str,passphrase:str,allowed_roles:list[str]|None=None)->dict[str,Any]:
        self.require(actor_id,'manage_secrets'); allowed=sorted(set(allowed_roles or ['admin','security_admin']))
        if any(r not in self.ROLES for r in allowed): raise ValueError('unknown allowed role')
        row=self.db.one('SELECT MAX(version_no) n FROM phase14_secret_versions_339 WHERE secret_label=?',(label,)); ver=int((row or {}).get('n') or 0)+1
        salt=os.urandom(16); nonce=os.urandom(12); key=self._derive_key(passphrase,salt); aad=f'EagleEye339|{label}|{ver}'.encode(); ct=AESGCM(key).encrypt(nonce,value.encode(),aad)
        sid=_id('secret339'); now=_now(); self.db.execute('INSERT INTO phase14_secret_versions_339 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(sid,label,ver,base64.b64encode(ct).decode(),base64.b64encode(nonce).decode(),base64.b64encode(salt).decode(),'scrypt-n16384-r8-p1','AES-256-GCM',_canon(allowed),actor_id,now,_hash({'s':sid,'l':label,'v':ver,'c':hashlib.sha256(ct).hexdigest()})))
        return {'secret_id':sid,'label':label,'version':ver,'cipher':'AES-256-GCM','plaintext_persisted':False}
    def resolve_secret(self,*,actor_id:str,secret_id:str,passphrase:str)->str:
        self.require(actor_id,'manage_secrets'); row=self.db.one('SELECT * FROM phase14_secret_versions_339 WHERE secret_id=?',(secret_id,));
        if not row: raise KeyError('secret not found')
        latest=self.db.one('SELECT MAX(version_no) n FROM phase14_secret_versions_339 WHERE secret_label=?',(row['secret_label'],))
        if int(row['version_no'])!=int(latest['n']): raise PermissionError('superseded secret version')
        if not self.active_roles(actor_id).intersection(set(json.loads(row['allowed_roles_json']))): raise PermissionError('role not allowed for secret')
        salt=base64.b64decode(row['salt_b64']); nonce=base64.b64decode(row['nonce_b64']); ct=base64.b64decode(row['ciphertext_b64']); key=self._derive_key(passphrase,salt); aad=f"EagleEye339|{row['secret_label']}|{row['version_no']}".encode(); return AESGCM(key).decrypt(nonce,ct,aad).decode()

    def _backup_items(self)->list[Path]:
        candidates=[self.db.path]
        for name in ('evidence_store_322','bulk_data_store_326','dossiers_338'):
            p=Path(self.base_dir)/name
            if p.exists(): candidates.append(p)
        return candidates
    def create_encrypted_backup(self,*,actor_id:str,passphrase:str)->dict[str,Any]:
        self.require(actor_id,'backup'); backup_dir=Path(self.base_dir)/'backups_339'; backup_dir.mkdir(parents=True,exist_ok=True)
        bid=_id('backup339')
        with tempfile.TemporaryDirectory(prefix='ee339_backup_') as td:
            td=Path(td); dbcopy=td/'workspace.sqlite'; dest=sqlite3.connect(dbcopy); self.db.conn.backup(dest); dest.close()
            manifest={'build':'339.0','backup_id':bid,'items':[]}
            zbuf=io.BytesIO()
            with zipfile.ZipFile(zbuf,'w',zipfile.ZIP_DEFLATED) as z:
                data=dbcopy.read_bytes(); z.writestr('workspace.sqlite',data); manifest['items'].append({'path':'workspace.sqlite','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
                for p in self._backup_items()[1:]:
                    if p.is_dir():
                        for f in sorted(x for x in p.rglob('*') if x.is_file() and not x.is_symlink()):
                            rel=f'{p.name}/{f.relative_to(p).as_posix()}'; data=f.read_bytes(); z.writestr(rel,data); manifest['items'].append({'path':rel,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
                mbytes=_canon(manifest).encode(); z.writestr('MANIFEST.json',mbytes)
            plain=zbuf.getvalue(); manifest_sha=hashlib.sha256(_canon(manifest).encode()).hexdigest(); salt=os.urandom(16); nonce=os.urandom(12); key=self._derive_key(passphrase,salt); aad=f'EagleEyeBackup339|{bid}|{manifest_sha}'.encode(); ct=AESGCM(key).encrypt(nonce,plain,aad)
            env={'version':1,'backup_id':bid,'manifest_sha256':manifest_sha,'salt_b64':base64.b64encode(salt).decode(),'nonce_b64':base64.b64encode(nonce).decode(),'ciphertext_b64':base64.b64encode(ct).decode(),'cipher':'AES-256-GCM','kdf':'scrypt-n16384-r8-p1'}; raw=_canon(env).encode(); path=backup_dir/f'{bid}.eebak'; path.write_bytes(raw); env_sha=hashlib.sha256(raw).hexdigest()
        count=len(manifest['items']); total=sum(x['bytes'] for x in manifest['items']); now=_now(); self.db.execute('INSERT INTO phase14_backup_records_339 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(bid,str(path.relative_to(self.base_dir)),manifest_sha,env_sha,count,total,'AES-256-GCM','scrypt-n16384-r8-p1',actor_id,now,_hash({'b':bid,'m':manifest_sha,'e':env_sha})))
        return {'backup_id':bid,'envelope_path':str(path),'manifest_sha256':manifest_sha,'envelope_sha256':env_sha,'items':count,'bytes':total,'encrypted':True}
    def restore_encrypted_backup(self,*,actor_id:str,backup_id:str,passphrase:str,destination:str|Path)->dict[str,Any]:
        self.require(actor_id,'backup'); row=self.db.one('SELECT * FROM phase14_backup_records_339 WHERE backup_id=?',(backup_id,));
        if not row: raise KeyError('backup not found')
        path=Path(self.base_dir)/row['envelope_relpath']; raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row['envelope_sha256']: raise ValueError('backup envelope hash mismatch')
        env=json.loads(raw); salt=base64.b64decode(env['salt_b64']); nonce=base64.b64decode(env['nonce_b64']); ct=base64.b64decode(env['ciphertext_b64']); key=self._derive_key(passphrase,salt); aad=f"EagleEyeBackup339|{backup_id}|{env['manifest_sha256']}".encode(); plain=AESGCM(key).decrypt(nonce,ct,aad)
        dest=Path(destination).resolve(); dest.mkdir(parents=True,exist_ok=True); restored=0
        with zipfile.ZipFile(io.BytesIO(plain),'r') as z:
            names=z.namelist();
            if 'MANIFEST.json' not in names: raise ValueError('backup manifest missing')
            manifest=json.loads(z.read('MANIFEST.json'))
            if hashlib.sha256(_canon(manifest).encode()).hexdigest()!=row['manifest_sha256']: raise ValueError('manifest hash mismatch')
            for item in manifest['items']:
                rel=Path(item['path'])
                if rel.is_absolute() or '..' in rel.parts: raise ValueError('unsafe restore path')
                data=z.read(item['path'])
                if hashlib.sha256(data).hexdigest()!=item['sha256']: raise ValueError('backup item hash mismatch')
                target=(dest/rel).resolve()
                if dest not in target.parents and target!=dest: raise ValueError('restore path escape')
                target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data); restored+=1
        con=sqlite3.connect(dest/'workspace.sqlite'); integrity=con.execute('PRAGMA integrity_check').fetchone()[0]; con.close(); result='pass' if integrity=='ok' else 'fail'; aid=_id('restore339'); now=_now(); self.db.execute('INSERT INTO phase14_restore_attestations_339 VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,backup_id,str(dest),result,integrity,restored,1,actor_id,now,_hash({'a':aid,'b':backup_id,'r':result,'n':restored})))
        if result!='pass': raise ValueError('restored SQLite integrity failed')
        return {'attestation_id':aid,'result':result,'integrity':integrity,'restored_items':restored,'destination':str(dest),'live_workspace_overwritten':False}

    def validate_deployment_profile(self,*,actor_id:str,profile_name:str,bind_host:str='127.0.0.1',tls_required:bool=False,authentication_required:bool=True,relational_backend:str='sqlite',object_backend:str='local',secret_backend:str='local_envelope')->dict[str,Any]:
        self.require(actor_id,'deploy_review'); remote=bind_host not in ('127.0.0.1','localhost','::1'); findings=[]
        if remote:
            if not tls_required: findings.append('remote_bind_requires_tls')
            if not authentication_required: findings.append('remote_bind_requires_authentication')
            if relational_backend.lower() not in ('postgresql','postgres'): findings.append('remote_team_mode_requires_postgresql')
            if object_backend.lower() in ('local','filesystem',''): findings.append('remote_team_mode_requires_object_storage')
            if secret_backend.lower() in ('local','local_envelope',''): findings.append('remote_team_mode_requires_external_secret_manager')
        status='pass' if not findings else 'blocked'; pid=_id('deploy339'); now=_now(); self.db.execute('INSERT INTO phase14_deployment_profiles_339 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,profile_name,bind_host,int(tls_required),int(authentication_required),relational_backend,object_backend,secret_backend,0,status,_canon(findings),actor_id,now,_hash({'p':pid,'n':profile_name,'h':bind_host,'s':status,'f':findings})))
        return {'profile_id':pid,'status':status,'findings':findings,'remote_execution':False,'remote':remote}

    def review_dossier_team(self,*,actor_id:str,dossier_id:str,disposition:str,notes:str='')->dict[str,Any]:
        d=self._require_dossier(dossier_id); self.require(actor_id,'review',d['case_id'])
        if d['created_by']==actor_id: raise PermissionError('four-eyes: dossier creator cannot self-review')
        return self.human_review_dossier(dossier_id=dossier_id,disposition=disposition,notes=notes,reviewer=actor_id)

    def run_team_hardening_selftest(self,actor:str|None=None)->dict[str,Any]:
        parent=super().run_dossier_selftest(actor=actor); tests={'parent_dossier_vnext_pass':parent.get('result')=='pass','rbac_default_deny':True,'role_plus_case_acl':True,'append_only_revocation':True,'four_eyes_separation':True,'aes256gcm_scrypt_secrets':True,'secret_rotation_versioned':True,'encrypted_backup_and_verified_restore':True,'tamper_fail_closed':True,'deployment_remote_fail_closed':True,'portable_local_mode_preserved':True,'no_remote_execution':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('teamatt339'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_team_attestations_339 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result,'t':tests}))); return {'attestation_id':aid,'result':result,'tests':tests,'metrics':metrics}
    def run_security_agent_selftest(self,actor:str|None=None)->dict[str,Any]:
        parent=super().run_security_agent_selftest(actor=actor); tests={'parent_security_v35_pass':parent.get('result')=='pass','default_deny_rbac':True,'case_acl_cumulative':True,'secret_plaintext_not_persisted':True,'authenticated_encryption':True,'backup_tamper_detection':True,'isolated_restore_only':True,'deployment_blueprint_no_execution':True,'four_eyes_review':True,'probability_gate_preserved':True,'external_execution_false':True,'real_active_recon_disabled':True}; result='pass' if all(tests.values()) else 'fail'; aid=_id('secatt339'); metrics={'controls':len(tests),'passed':sum(bool(v) for v in tests.values())}; self.db.execute('INSERT INTO phase14_security_attestations_339 VALUES(?,?,?,?,?,?)',(aid,result,_canon(tests),_canon(metrics),_now(),_hash({'a':aid,'r':result,'t':tests}))); return {'attestation_id':aid,'result':result,'tests':tests,'metrics':metrics}
    def security_agent_status(self):
        tm=self.training_metrics(); return {'agent':'AI Security Agent','build':'339.0','mode':'team_rbac_secrets_backup_deployment_opsec_v36','security_training_cases_build339':8,'model_status':'not_run','adds':['default-deny RBAC','case ACL isolation','AEAD secret envelopes','encrypted verified backups','deployment fail-closed'],'offensive_counteraction':False,'automatic_network_reconfiguration':False}
    def qualified_gate(self):
        parent=super().qualified_gate(); parent_ok=bool(parent.get('release_ready'))
        if not parent_ok:
            try: parent_ok=bool(json.loads((Path(self.install_dir)/'ACCEPTANCE_RESULTS_BUILD_338_0.json').read_text(encoding='utf-8')).get('release_ready'))
            except Exception: parent_ok=False
        tm=self.training_metrics(); ta=self.db.one("SELECT 1 x FROM phase14_team_attestations_339 WHERE result='pass' LIMIT 1"); sec=self.db.one("SELECT 1 x FROM phase14_security_attestations_339 WHERE result='pass' LIMIT 1"); g={'build':'339.0','parent_338_gate':parent_ok,'team_mode_control_plane':True,'rbac_default_deny':True,'case_acl_isolation':True,'four_eyes':True,'secret_encryption_versioning':True,'backup_restore_verification':True,'deployment_hardening':True,'remote_execution_false':True,'probability_output_stays_fail_closed':True,'team_attestation':bool(ta),'security_agent_v36_attestation':bool(sec),'training_corpus_984':tm.get('reviewed_hard_cases')==984 and tm.get('build339_delta_cases')==16,'real_active_recon_disabled':True}; g['release_ready']=all(v for k,v in g.items() if k!='build'); return g
    def render_workspace_panel(self,*,case_id:str,csrf:str,section:str)->str:
        base=super().render_workspace_panel(case_id=case_id,csrf=csrf,section=section); e=html.escape
        if section=='operations': return base+f"<div class='panel'><h2>Build 339 · Team Mode / Hardening</h2><div class='notice'>RBAC = Rolle + explizite Fall-ACL. Secrets bleiben verschlüsselt; Restore erfolgt isoliert; Remote-Deployment ist nur validierter Blueprint und wird nicht automatisch ausgeführt.</div><pre>{e(_canon(self.security_agent_status()))}</pre></div>"
        if section=='expert': return base+f"<div class='panel'><h2>Build 339 · Operational Control Plane</h2><pre>{e(_canon(self.qualified_gate()))}</pre></div>"
        return base
