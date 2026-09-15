from __future__ import annotations
import hashlib,hmac,json,os,re
from pathlib import Path
from typing import Any,Mapping,Sequence
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
class Build183IntegrationPluginAIService:
 BUILD='183.0'
 ALLOWED_CAPABILITIES={'source.read','connector.http','analyzer.text','analyzer.media','export.write','repository.read','ai.suggest'}
 FORBIDDEN_CAPABILITIES={'credential.dump','browser.bypass','private_account.access','biometric.identify','external_media.upload','autonomous_intervention'}
 SOURCE_PROFILES=[
  {'source_id':'sigstore_cosign','title':'Sigstore Cosign','category':'plugin_signing','access_mode':'official_standard','base_url':'https://www.sigstore.dev','docs_url':'https://docs.sigstore.dev/cosign/','constraints':['signature_identity_review','transparency_log_availability']},
  {'source_id':'slsa_framework','title':'SLSA Supply-chain Levels','category':'software_supply_chain','access_mode':'official_standard','base_url':'https://slsa.dev','docs_url':'https://slsa.dev/spec/','constraints':['provenance_level_verified','builder_identity_review']},
  {'source_id':'cyclonedx_sbom','title':'CycloneDX SBOM','category':'dependency_transparency','access_mode':'official_standard','base_url':'https://cyclonedx.org','docs_url':'https://cyclonedx.org/specification/overview/','constraints':['sbom_not_vulnerability_verdict','version_pinned']},
  {'source_id':'spdx_specification','title':'SPDX Specification','category':'license_provenance','access_mode':'official_standard','base_url':'https://spdx.dev','docs_url':'https://spdx.github.io/spdx-spec/','constraints':['license_expression_review','document_namespace_unique']},
  {'source_id':'owasp_llm_top10','title':'OWASP Top 10 for LLM Applications','category':'ai_security','access_mode':'official_guidance','base_url':'https://owasp.org','docs_url':'https://owasp.org/www-project-top-10-for-large-language-model-applications/','constraints':['guidance_not_certification','prompt_injection_controls_required']},
  {'source_id':'nist_ai_rmf','title':'NIST AI Risk Management Framework','category':'ai_governance','access_mode':'official_guidance','base_url':'https://www.nist.gov','docs_url':'https://www.nist.gov/itl/ai-risk-management-framework','constraints':['context_specific_risk_review','human_oversight_required']},
 ]
 def __init__(self,db:Any,audit:Any,*,base_dir:Path,repository:Any,workspace:Any,authenticity:Any,actor:str='system'):
  self.db,self.audit,self.repository,self.workspace,self.authenticity,self.actor=db,audit,repository,workspace,authenticity,actor;self.root=Path(base_dir)/'plugins_183';self.root.mkdir(parents=True,exist_ok=True);self.key_path=self.root/'plugin_trust.key'
  if not self.key_path.exists():self.key_path.write_bytes(os.urandom(32))
 def seed_sources(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!='PLUGIN SOURCES 183 ERWEITERN':raise PermissionError('explicit source approval required')
  for p in self.SOURCE_PROFILES:
   q={**p,'status':'DOCUMENTED'};self.db.execute('INSERT OR REPLACE INTO plugin_source_profiles_183 VALUES(?,?,?,?,?,?,?,?,?,?)',(p['source_id'],p['title'],p['category'],p['access_mode'],p['base_url'],p['docs_url'],dumps(p['constraints']),'DOCUMENTED',now_ts(),_hash(q)))
  return {'created':6,'production_active':0,'review_required':True}
 def sign_manifest(self,manifest:Mapping[str,Any])->str:return hmac.new(self.key_path.read_bytes(),_canon(manifest).encode(),hashlib.sha256).hexdigest()
 def register_plugin(self,manifest:Mapping[str,Any],*,signature:str,approved_by:str,confirmation:str)->dict[str,Any]:
  pid=str(manifest.get('plugin_id','')).strip();version=str(manifest.get('version','')).strip();caps=set(manifest.get('capabilities',[]))
  if confirmation!=f'PLUGIN 183 {pid} REGISTRIEREN':raise PermissionError('explicit plugin approval required')
  if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,80}',pid) or not version:raise ValueError('invalid plugin identity')
  if signature!=self.sign_manifest(manifest):raise PermissionError('invalid plugin signature')
  if caps-self.ALLOWED_CAPABILITIES or caps&self.FORBIDDEN_CAPABILITIES:raise PermissionError('capability denied')
  if not manifest.get('entrypoint') or not manifest.get('sbom_sha256'):raise ValueError('entrypoint and SBOM required')
  status='sandbox_validated';payload={'plugin_id':pid,'version':version,'manifest':dict(manifest),'capabilities':sorted(caps),'status':status,'approved_by':approved_by}
  self.db.execute('INSERT OR REPLACE INTO plugins_183 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(pid,version,dumps(dict(manifest)),signature,dumps(sorted(caps)),manifest['entrypoint'],manifest['sbom_sha256'],status,approved_by,now_ts(),_hash(payload)));self._event('global','plugin_registered',payload);return payload
 def execute_plugin(self,plugin_id:str,*,case_id:str,capability:str,input_data:Mapping[str,Any],runner:Any,confirmation:str)->dict[str,Any]:
  if confirmation!=f'PLUGIN 183 {plugin_id} AUSFUEHREN':raise PermissionError('explicit plugin execution required')
  row=self.db.one("SELECT * FROM plugins_183 WHERE plugin_id=? AND status='sandbox_validated'",(plugin_id,));
  if not row:raise ValueError('validated plugin required')
  allowed=set(json.loads(row['capabilities_json']));
  if capability not in allowed:raise PermissionError('capability not granted')
  safe=self._sanitize(input_data);run_id=new_id('plugrun183')
  try:output=self._sanitize(runner(dict(safe)));status='succeeded'
  except Exception as exc:output={'error':type(exc).__name__};status='failed'
  payload={'run_id':run_id,'plugin_id':plugin_id,'case_id':case_id,'capability':capability,'input_sha256':_hash(safe),'output':output,'status':status,'external_uploads':False,'human_review_required':True}
  self.db.execute('INSERT INTO plugin_runs_183 VALUES(?,?,?,?,?,?,?,?,?,?)',(run_id,plugin_id,case_id,capability,payload['input_sha256'],dumps(output),status,0,now_ts(),_hash(payload)));self._event(case_id,'plugin_executed',payload);return payload
 def ai_assess(self,case_id:str,claim:str,*,evidence:Sequence[Mapping[str,Any]],model_outputs:Sequence[Mapping[str,Any]],confirmation:str)->dict[str,Any]:
  if confirmation!=f'AI 183 {case_id} BEWERTEN':raise PermissionError('explicit AI assessment required')
  clean_claim=self._sanitize_text(claim);trusted=[]
  for e in evidence:
   if not e.get('source_id') or not e.get('source_ref'):continue
   trusted.append({'source_id':e['source_id'],'source_ref':e['source_ref'],'direction':e.get('direction','neutral'),'score':max(0,min(1,float(e.get('score',0)))),'independent':bool(e.get('independent',False))})
  independent={e['source_id'] for e in trusted if e['independent']};support=sum(e['score'] for e in trusted if e['direction']=='support');contradict=sum(e['score'] for e in trusted if e['direction']=='contradict')
  calibrated=[m for m in model_outputs if m.get('calibrated') and 0<=float(m.get('confidence',0))<=1]
  consensus=sum(float(m['confidence']) for m in calibrated)/len(calibrated) if calibrated else 0.0
  status='corroborated_candidate' if len(independent)>=2 and support>=1.4 and support>contradict else 'contradicted_candidate' if len(independent)>=2 and contradict>=1.4 and contradict>support else 'inconclusive'
  warnings=[]
  if self._looks_like_injection(claim):warnings.append('prompt_injection_candidate')
  limitations=['ai_output_is_not_fact','models_do_not_replace_sources','source_independence_requires_review','human_review_required']
  aid=new_id('ai183');payload={'assessment_id':aid,'case_id':case_id,'claim':clean_claim,'status':status,'source_count':len(trusted),'independent_sources':len(independent),'model_consensus':consensus,'warnings':warnings,'limitations':limitations}
  self.db.execute('INSERT INTO ai_assessments_183 VALUES(?,?,?,?,?,?,?,?,?,?,?)',(aid,case_id,clean_claim,dumps(trusted),dumps(calibrated),consensus,status,dumps(warnings),dumps(limitations),now_ts(),_hash(payload)));self._event(case_id,'ai_assessment',payload);return payload
 def _sanitize_text(self,text:str)->str:
  text=re.sub(r'(?i)(api[_ -]?key|token|password|authorization)\s*[:=]\s*\S+',r'\1=[REDACTED]',str(text));return text[:20000]
 def _sanitize(self,v:Any)->Any:
  if isinstance(v,Mapping):return {str(k):('[REDACTED]' if any(x in str(k).lower() for x in ('token','secret','password','authorization','cookie','api_key','private_key')) else self._sanitize(x)) for k,x in v.items()}
  if isinstance(v,(list,tuple)):return [self._sanitize(x) for x in v]
  if isinstance(v,str):return self._sanitize_text(v)
  return v
 def _looks_like_injection(self,text:str)->bool:return bool(re.search(r'(?i)ignore\s+(all\s+)?previous|reveal\s+(the\s+)?system|bypass\s+(policy|rules)|developer\s+message',text))
 def source_coverage(self)->dict[str,Any]:
  tables=('european_source_profiles_172','extended_source_profiles_173','media_source_profiles_174','geo_source_profiles_175','multilingual_source_profiles_176','graph_source_profiles_177','monitor_source_profiles_178','pattern_source_profiles_179','authenticity_source_profiles_180','workspace_source_profiles_181','repository_source_profiles_182','plugin_source_profiles_183');counts=[]
  for t in tables:
   try:counts.append(int(self.db.one(f'SELECT COUNT(*) n FROM {t}')['n']))
   except Exception:counts.append(0)
  return {'total_documented_sources':sum(counts),'plugin_sources':counts[-1],'production_active_new':0,'review_required':True}
 def _event(self,case_id:str,event_type:str,details:Mapping[str,Any])->None:
  prev=self.db.one('SELECT event_sha256 FROM plugin_events_183 WHERE case_id=? ORDER BY created_at DESC LIMIT 1',(case_id,));ph=prev['event_sha256'] if prev else '';eid=new_id('pe183');ts=now_ts();eh=_hash({'event_id':eid,'case_id':case_id,'event_type':event_type,'details':details,'created_at':ts,'previous_sha256':ph});self.db.execute('INSERT INTO plugin_events_183 VALUES(?,?,?,?,?,?,?)',(eid,case_id,event_type,dumps(dict(details)),ts,ph,eh))
