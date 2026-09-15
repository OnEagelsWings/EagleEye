from __future__ import annotations
import base64,hashlib,hmac,json,os,zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Any,Mapping,Sequence
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
def _future(days:int)->str:return (datetime.now(timezone.utc)+timedelta(days=days)).isoformat()
class Build182SecureRepositoryFederationService:
 BUILD='182.0'
 SOURCE_PROFILES=[
 {'source_id':'eu_eidas_trusted_lists','title':'EU eIDAS Trusted Lists','category':'trust_services','access_mode':'official_public','base_url':'https://eidas.ec.europa.eu','docs_url':'https://digital-strategy.ec.europa.eu/en/policies/eu-trusted-lists','constraints':['trust_status_time_bound','signature_validity_not_content_truth']},
 {'source_id':'bsi_tr_esor','title':'BSI TR-ESOR','category':'evidence_preservation','access_mode':'official_standard','base_url':'https://www.bsi.bund.de','docs_url':'https://www.bsi.bund.de/SharedDocs/Downloads/EN/BSI/Publications/TechGuidelines/TR03125/BSI_TR_03125_TR-ESOR.html','constraints':['implementation_requires_conformance_review','legal_effect_jurisdiction_specific']},
 {'source_id':'ietf_rfc3161','title':'RFC 3161 Time-Stamp Protocol','category':'trusted_timestamp','access_mode':'official_standard','base_url':'https://datatracker.ietf.org','docs_url':'https://datatracker.ietf.org/doc/html/rfc3161','constraints':['tsa_trust_required','timestamp_not_content_truth']},
 {'source_id':'ietf_bagit','title':'BagIt File Packaging Format','category':'repository_packaging','access_mode':'official_standard','base_url':'https://datatracker.ietf.org','docs_url':'https://datatracker.ietf.org/doc/html/rfc8493','constraints':['integrity_manifest_not_encryption','profile_validation_required']},
 {'source_id':'loc_digital_preservation','title':'Library of Congress Digital Preservation','category':'preservation_reference','access_mode':'official_public','base_url':'https://www.loc.gov','docs_url':'https://www.loc.gov/preservation/digital/','constraints':['reference_guidance_only','format_policy_review']},
 {'source_id':'etsi_signature_validation','title':'ETSI Signature Validation Standards','category':'signature_validation','access_mode':'standards_reference','base_url':'https://www.etsi.org','docs_url':'https://www.etsi.org/technologies/digital-signature','constraints':['standard_version_pinned','conformance_test_required']},
 ]
 def __init__(self,db:Any,audit:Any,*,base_dir:Path,workspace:Any,authenticity:Any,actor:str='system'):
  self.db,self.audit,self.workspace,self.authenticity,self.actor=db,audit,workspace,authenticity,actor;self.root=Path(base_dir)/'secure_repository_182';self.root.mkdir(parents=True,exist_ok=True)
 def seed_sources(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!='REPOSITORY SOURCES 182 ERWEITERN':raise PermissionError('explicit source approval required')
  for p in self.SOURCE_PROFILES:
   q={**p,'status':'DOCUMENTED'};self.db.execute('INSERT OR REPLACE INTO repository_source_profiles_182 VALUES(?,?,?,?,?,?,?,?,?,?)',(p['source_id'],p['title'],p['category'],p['access_mode'],p['base_url'],p['docs_url'],dumps(p['constraints']),'DOCUMENTED',now_ts(),_hash(q)))
  return {'created':len(self.SOURCE_PROFILES),'production_active':0,'review_required':True}
 def create_repository(self,*,title:str,created_by:str,confirmation:str)->dict[str,Any]:
  if confirmation!='REPOSITORY 182 ANLEGEN':raise PermissionError('explicit repository approval required')
  rid=new_id('repo182');key=os.urandom(32);kp=self.root/f'{rid}.key';kp.write_bytes(key)
  try:os.chmod(kp,0o600)
  except OSError:pass
  p={'repository_id':rid,'title':title,'key_ref':str(kp),'algorithm':'AES-256-GCM','status':'active','created_by':created_by}
  self.db.execute('INSERT INTO secure_repositories_182 VALUES(?,?,?,?,?,?,?,?)',(rid,title,str(kp),'AES-256-GCM','active',created_by,now_ts(),_hash(p)));return p
 def store_bytes(self,repository_id:str,case_id:str,*,logical_name:str,data:bytes,object_type:str='evidence',classification:str='restricted',source_refs:Sequence[str]=(),created_by:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'REPOSITORY 182 {case_id} SPEICHERN':raise PermissionError('explicit storage approval required')
  repo=self.db.one("SELECT * FROM secure_repositories_182 WHERE repository_id=? AND status='active'",(repository_id,));
  if not repo:raise ValueError('active repository required')
  key=Path(repo['key_ref']).read_bytes();oid=new_id('obj182');nonce=os.urandom(12);aad={'repository_id':repository_id,'case_id':case_id,'object_id':oid,'object_type':object_type,'logical_name':logical_name};cipher=AESGCM(key).encrypt(nonce,data,_canon(aad).encode());path=self.root/f'{oid}.bin';path.write_bytes(cipher)
  p={'object_id':oid,**aad,'plaintext_sha256':hashlib.sha256(data).hexdigest(),'ciphertext_sha256':hashlib.sha256(cipher).hexdigest(),'size_bytes':len(data),'classification':classification,'source_refs':list(source_refs)}
  self.db.execute('INSERT INTO repository_objects_182 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(oid,repository_id,case_id,object_type,logical_name,str(path),p['plaintext_sha256'],p['ciphertext_sha256'],base64.b64encode(nonce).decode(),_canon(aad),len(data),dumps(list(source_refs)),classification,created_by,now_ts(),_hash(p)));self._event(case_id,'object_stored',p);return p
 def retrieve_bytes(self,object_id:str,*,principal:str,confirmation:str)->bytes:
  if confirmation!=f'REPOSITORY 182 {object_id} LESEN':raise PermissionError('explicit read approval required')
  obj=self.db.one('SELECT * FROM repository_objects_182 WHERE object_id=?',(object_id,));
  if not obj:raise KeyError(object_id)
  grant=self.db.one("SELECT 1 FROM repository_access_grants_182 WHERE repository_id=? AND case_id=? AND principal=? AND permission IN ('read','admin') AND status='active' AND expires_at>?",(obj['repository_id'],obj['case_id'],principal,now_ts()))
  if not grant:raise PermissionError('active repository grant required')
  repo=self.db.one('SELECT key_ref FROM secure_repositories_182 WHERE repository_id=?',(obj['repository_id'],));key=Path(repo['key_ref']).read_bytes();cipher=Path(obj['ciphertext_path']).read_bytes()
  if hashlib.sha256(cipher).hexdigest()!=obj['ciphertext_sha256']:raise ValueError('ciphertext integrity failure')
  plain=AESGCM(key).decrypt(base64.b64decode(obj['nonce_b64']),cipher,obj['aad_json'].encode())
  if hashlib.sha256(plain).hexdigest()!=obj['plaintext_sha256']:raise ValueError('plaintext integrity failure')
  return plain
 def grant_access(self,repository_id:str,case_id:str,*,principal:str,permission:str,days:int,approved_by:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f'REPOSITORY 182 {case_id} ZUGRIFF FREIGEBEN':raise PermissionError('explicit access approval required')
  if permission not in {'read','write','federate','admin'} or not 1<=days<=90:raise ValueError('invalid access grant')
  gid=new_id('grant182');exp=_future(days);p={'grant_id':gid,'repository_id':repository_id,'case_id':case_id,'principal':principal,'permission':permission,'status':'active','expires_at':exp,'approved_by':approved_by}
  self.db.execute('INSERT OR REPLACE INTO repository_access_grants_182 VALUES(?,?,?,?,?,?,?,?,?,?)',(gid,repository_id,case_id,principal,permission,'active',exp,approved_by,now_ts(),_hash(p)));self._event(case_id,'access_granted',p);return p
 def export_case(self,repository_id:str,case_id:str,*,principal:str,object_ids:Sequence[str],redact_names:bool=True,confirmation:str)->dict[str,Any]:
  if confirmation!=f'FEDERATION 182 {case_id} EXPORTIEREN':raise PermissionError('explicit federation export required')
  grant=self.db.one("SELECT 1 FROM repository_access_grants_182 WHERE repository_id=? AND case_id=? AND principal=? AND permission IN ('federate','admin') AND status='active' AND expires_at>?",(repository_id,case_id,principal,now_ts()))
  if not grant:raise PermissionError('federation grant required')
  rows=[]
  for oid in object_ids:
   r=self.db.one('SELECT object_id,object_type,logical_name,plaintext_sha256,ciphertext_path,ciphertext_sha256,classification FROM repository_objects_182 WHERE object_id=? AND repository_id=? AND case_id=?',(oid,repository_id,case_id))
   if r:rows.append(dict(r))
  pid=new_id('fed182');manifest={'package_id':pid,'case_id':case_id,'objects':[{k:v for k,v in r.items() if k!='ciphertext_path'} for r in rows],'redaction':{'logical_names':redact_names},'automatic_identity_confirmation':False,'human_review_required':True};repo=self.db.one('SELECT key_ref FROM secure_repositories_182 WHERE repository_id=?',(repository_id,));key=Path(repo['key_ref']).read_bytes();sig=hmac.new(key,_canon(manifest).encode(),hashlib.sha256).digest();zp=self.root/f'{pid}.zip'
  with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
   z.writestr('manifest.json',_canon(manifest));z.writestr('manifest.sig',base64.b64encode(sig).decode())
   for r in rows:z.write(r['ciphertext_path'],f'objects/{r["object_id"]}.bin')
  sha=hashlib.sha256(zp.read_bytes()).hexdigest();p={'package_id':pid,'case_id':case_id,'direction':'export','package_sha256':sha,'objects':len(rows),'path':str(zp)}
  self.db.execute('INSERT INTO federation_packages_182 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(pid,case_id,'export',None,dumps(manifest),str(zp),sha,base64.b64encode(sig).decode(),'created',principal,now_ts(),_hash(p)));self._event(case_id,'federation_export_created',p);return p
 def authenticity_crosscheck(self,case_id:str,target_id:str,*,signals:Sequence[Mapping[str,Any]],confirmation:str)->dict[str,Any]:
  if confirmation!=f'AUTH CROSSCHECK 182 {target_id} AUSWERTEN':raise PermissionError('explicit crosscheck approval required')
  usable=[s for s in signals if s.get('independent',False) and 0<=float(s.get('score',0))<=1];score=sum(float(s['score'])*float(s.get('weight',1)) for s in usable)/sum(float(s.get('weight',1)) for s in usable) if usable else 0
  contradictions=sum(s.get('direction')=='contradict' for s in usable);supports=sum(s.get('direction')=='support' for s in usable);status='strongly_suspicious' if contradictions>=2 and score>=.7 else 'supported_candidate' if supports>=2 and score>=.7 else 'inconclusive';limitations=['crosscheck_is_not_verdict','source_independence_requires_review','repository_integrity_is_not_content_truth','human_review_required']
  cid=new_id('ac182');p={'crosscheck_id':cid,'case_id':case_id,'target_id':target_id,'score':score,'status':status,'signals':len(usable),'limitations':limitations};self.db.execute('INSERT INTO authenticity_crosschecks_182 VALUES(?,?,?,?,?,?,?,?,?)',(cid,case_id,target_id,dumps(usable),score,status,dumps(limitations),now_ts(),_hash(p)));self._event(case_id,'authenticity_crosscheck',p);return p
 def source_coverage(self)->dict[str,Any]:
  tables=('european_source_profiles_172','extended_source_profiles_173','media_source_profiles_174','geo_source_profiles_175','multilingual_source_profiles_176','graph_source_profiles_177','monitor_source_profiles_178','pattern_source_profiles_179','authenticity_source_profiles_180','workspace_source_profiles_181','repository_source_profiles_182');counts=[]
  for t in tables:
   try:counts.append(int(self.db.one(f'SELECT COUNT(*) n FROM {t}')['n']))
   except Exception:counts.append(0)
  return {'total_documented_sources':sum(counts),'repository_sources':counts[-1],'production_active_new':0,'review_required':True}
 def _event(self,case_id:str,event_type:str,details:Mapping[str,Any])->None:
  prev=self.db.one('SELECT event_sha256 FROM repository_events_182 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,));ph=prev['event_sha256'] if prev else '';eid=new_id('re182');ts=now_ts();eh=_hash({'event_id':eid,'case_id':case_id,'event_type':event_type,'details':details,'created_at':ts,'previous_sha256':ph});self.db.execute('INSERT INTO repository_events_182 VALUES(?,?,?,?,?,?,?)',(eid,case_id,event_type,dumps(dict(details)),ts,ph,eh))
