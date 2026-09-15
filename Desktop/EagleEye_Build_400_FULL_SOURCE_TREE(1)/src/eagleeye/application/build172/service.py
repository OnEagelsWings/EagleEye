from __future__ import annotations
import hashlib,json
from typing import Any
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()

class Build172GermanEuropeanSourcesService:
 BUILD="172.0"
 def __init__(self,db:Any,audit:Any,*,sdk:Any,source_gate:Any,actor:str="system"):
  self.db,self.audit,self.sdk,self.source_gate,self.actor=db,audit,sdk,source_gate,actor
 def _catalog(self):
  return [
   {"source_id":"de_bundestag_dip","title":"Deutscher Bundestag DIP","jurisdiction":"DE","category":"parliamentary_people_documents","access_mode":"official_api","base_url":"https://search.dip.bundestag.de/api/v1","allowed_hosts":["search.dip.bundestag.de"],"auth":{"type":"api_key","location":"header"},"pagination":{"type":"cursor","response_path":"cursor"},"docs_url":"https://dip.bundestag.de/über-dip/hilfe/api","terms_url":"https://dip.bundestag.de/documents/nutzungsbedingungen_dip.pdf","terms_state":"review_required","entity_kinds":["person","organization","document","event"],"sdk_enabled":True},
   {"source_id":"eu_data_portal","title":"data.europa.eu Hub Search","jurisdiction":"EU","category":"open_data_catalogue","access_mode":"official_api","base_url":"https://data.europa.eu/api/hub/search","allowed_hosts":["data.europa.eu"],"auth":{"type":"none"},"pagination":{"type":"page","request_parameter":"page"},"docs_url":"https://data.europa.eu/api/hub/search/","terms_url":"https://data.europa.eu/en/legal-notice","terms_state":"review_required","entity_kinds":["dataset","organization","location"],"sdk_enabled":True},
   {"source_id":"eu_ted_procurement","title":"Tenders Electronic Daily Search API","jurisdiction":"EU","category":"procurement","access_mode":"official_api","base_url":"https://api.ted.europa.eu/v3/notices/search","allowed_hosts":["api.ted.europa.eu"],"auth":{"type":"none"},"pagination":{"type":"token","response_path":"iterationNextToken"},"docs_url":"https://ted.europa.eu/api/documentation/index.html","terms_url":"https://ted.europa.eu/en/legal-notice","terms_state":"review_required","entity_kinds":["organization","person","document","location"],"sdk_enabled":True},
   {"source_id":"eu_vies_vat","title":"VIES VAT Validation","jurisdiction":"EU","category":"business_identifier_validation","access_mode":"official_api","base_url":"https://ec.europa.eu/taxation_customs/vies/services/checkVatService","allowed_hosts":["ec.europa.eu"],"auth":{"type":"none"},"pagination":{"type":"none"},"docs_url":"https://ec.europa.eu/taxation_customs/vies/","terms_url":"https://ec.europa.eu/info/legal-notice_en","terms_state":"review_required","entity_kinds":["organization","identifier"],"sdk_enabled":False,"protocol":"SOAP"},
   {"source_id":"eu_eurlex","title":"EUR-Lex Webservice","jurisdiction":"EU","category":"law_and_official_documents","access_mode":"registered_api","base_url":"https://eur-lex.europa.eu/EURLexWebService","allowed_hosts":["eur-lex.europa.eu"],"auth":{"type":"api_key","registration_required":True},"pagination":{"type":"page"},"docs_url":"https://eur-lex.europa.eu/content/help/data-reuse/webservice.html","terms_url":"https://eur-lex.europa.eu/content/legal-notice/legal-notice.html","terms_state":"review_required","entity_kinds":["document","organization","person"],"sdk_enabled":False,"protocol":"SOAP"},
   {"source_id":"eu_sanctions_map","title":"EU Sanctions Map","jurisdiction":"EU","category":"sanctions","access_mode":"official_web","base_url":"https://www.sanctionsmap.eu","allowed_hosts":["www.sanctionsmap.eu","sanctionsmap.eu"],"auth":{"type":"none"},"pagination":{"type":"none"},"docs_url":"https://www.sanctionsmap.eu/","terms_url":"https://www.sanctionsmap.eu/","terms_state":"review_required","entity_kinds":["person","organization","location","regime"],"sdk_enabled":False},
   {"source_id":"de_handelsregister","title":"Gemeinsames Registerportal der Länder","jurisdiction":"DE","category":"company_register","access_mode":"guided_public","base_url":"https://www.handelsregister.de","allowed_hosts":["www.handelsregister.de","handelsregister.de"],"auth":{"type":"none"},"pagination":{"type":"none"},"docs_url":"https://www.handelsregister.de","terms_url":"https://www.handelsregister.de/rp_web/datenschutz.do","terms_state":"manual_review_required","entity_kinds":["organization","person","document"],"sdk_enabled":False},
   {"source_id":"de_unternehmensregister","title":"Unternehmensregister","jurisdiction":"DE","category":"company_disclosures","access_mode":"guided_public","base_url":"https://www.unternehmensregister.de","allowed_hosts":["www.unternehmensregister.de","unternehmensregister.de"],"auth":{"type":"none"},"pagination":{"type":"none"},"docs_url":"https://www.unternehmensregister.de","terms_url":"https://www.unternehmensregister.de/ureg/","terms_state":"manual_review_required","entity_kinds":["organization","person","document"],"sdk_enabled":False},
   {"source_id":"de_bundesanzeiger","title":"Bundesanzeiger","jurisdiction":"DE","category":"official_publications","access_mode":"guided_public","base_url":"https://www.bundesanzeiger.de","allowed_hosts":["www.bundesanzeiger.de","bundesanzeiger.de"],"auth":{"type":"none"},"pagination":{"type":"none"},"docs_url":"https://www.bundesanzeiger.de","terms_url":"https://www.bundesanzeiger.de/pub/de/agb","terms_state":"manual_review_required","entity_kinds":["organization","person","document"],"sdk_enabled":False},
   {"source_id":"de_transparency_register","title":"Transparenzregister","jurisdiction":"DE","category":"beneficial_ownership","access_mode":"auth_required","base_url":"https://www.transparenzregister.de","allowed_hosts":["www.transparenzregister.de","transparenzregister.de"],"auth":{"type":"oauth2_authorization_code","pkce":True,"account_required":True},"pagination":{"type":"none"},"docs_url":"https://www.transparenzregister.de","terms_url":"https://www.transparenzregister.de/connector/api/file/08b93c0a-85d0-4ff6-abeb-2a5daa276dab","terms_state":"legal_review_required","entity_kinds":["organization","person"],"sdk_enabled":False}
  ]
 def seed_catalog(self,*,created_by=None,confirmation:str):
  if confirmation!="EU SOURCES 172 KATALOG ANLEGEN":raise PermissionError("explicit catalogue approval required")
  created=[]
  sql="INSERT OR REPLACE INTO european_source_profiles_172 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
  for p in self._catalog():
   payload={**p,"status":"DOCUMENTED"}; sid=p["source_id"]
   self.db.execute(sql,(sid,p["title"],p["jurisdiction"],p["category"],p["access_mode"],p["base_url"],dumps(p["allowed_hosts"]),dumps(p["auth"]),dumps(p["pagination"]),p["docs_url"],p["terms_url"],p["terms_state"],dumps(p["entity_kinds"]),1 if p.get("sdk_enabled") else 0,p.get("protocol","REST"),"DOCUMENTED",now_ts(),_hash(payload)));created.append(sid)
  self.audit.log("european_source_catalog_seeded_172","source_catalog","phase6.1","",{"count":len(created)})
  return {"created":created,"count":len(created),"automatic_activation":False}
 def _sdk_spec(self,p):
  item={"type":"object","properties":{"id":{"type":"string"},"title":{"type":"string"},"name":{"type":"string"},"uri":{"type":"string"}},"required":["id"]}
  return {"connector_id":p["source_id"],"version":"1.0.0","title":p["title"],"base_url":p["base_url"],"allowed_hosts":p["allowed_hosts"],"auth":p["auth"],"pagination":p["pagination"],"input_schema":{"type":"object","properties":{"q":{"type":"string"}}},"output_schema":{"type":"object","properties":{"records":{"type":"array","items":item}},"required":["records"]},"normalization":{"entity_kinds":p["entity_kinds"],"review_required":True},"provenance":{"required":["connector_id","observed_at","body_sha256","source_record_id"]},"limits":{"timeout_seconds":45,"max_response_bytes":20000000,"max_pages":200}}
 def install_sdk_sources(self,*,created_by=None,confirmation:str):
  if confirmation!="EU SOURCES 172 SDK INSTALLIEREN":raise PermissionError("explicit SDK installation required")
  results=[]
  for p in self._catalog():
   if not p.get("sdk_enabled"):continue
   if not self.db.one("SELECT connector_id FROM connector_sdk_specs_171 WHERE connector_id=?",(p["source_id"],)):
    self.sdk.register_spec(self._sdk_spec(p),created_by=created_by or self.actor,confirmation=f"CONNECTOR SDK 171 {p['source_id']} REGISTRIEREN")
   if not self.db.one("SELECT fixture_id FROM connector_fixtures_171 WHERE connector_id=?",(p["source_id"],)):
    self.sdk.add_fixture(p["source_id"],fixture_kind="success",payload={"records":[{"id":p["source_id"]+"-fixture-1","title":"Official fixture record","uri":p["base_url"]}]},expected={"record_count":1},confirmation=f"FIXTURE 171 {p['source_id']} SPEICHERN")
   run=self.sdk.run_contract_tests(p["source_id"],created_by=created_by or self.actor,confirmation=f"CONTRACT 171 {p['source_id']} PRUEFEN")
   self.db.execute("UPDATE european_source_profiles_172 SET status=? WHERE source_id=?",("FIXTURE_VALIDATED" if run["status"]=="passed" else "DOCUMENTED",p["source_id"]));results.append({"source_id":p["source_id"],"status":run["status"]})
  return {"results":results,"fixture_validated":sum(x["status"]=="passed" for x in results)}
 def register_terms_review(self,source_id:str,*,decision:str,reviewer:str,evidence_ref:str,valid_until=None,confirmation:str):
  if confirmation!=f"EU SOURCE 172 {source_id} TERMS PRUEFEN":raise PermissionError("explicit terms review required")
  if decision not in {"accepted_for_sandbox","accepted_for_production","restricted","rejected"}:raise ValueError("invalid terms decision")
  if not self.db.one("SELECT source_id FROM european_source_profiles_172 WHERE source_id=?",(source_id,)):raise KeyError("source not found")
  rid=new_id("terms172");payload={"source_id":source_id,"decision":decision,"reviewer":reviewer,"evidence_ref":evidence_ref,"valid_until":valid_until}
  self.db.execute("INSERT INTO european_terms_reviews_172 VALUES(?,?,?,?,?,?,?,?)",(rid,source_id,decision,reviewer,evidence_ref,valid_until,now_ts(),_hash(payload)));return {"review_id":rid,"payload_sha256":_hash(payload)}
 def normalize(self,source_id:str,record:dict,*,observed_at=None):
  if not self.db.one("SELECT source_id FROM european_source_profiles_172 WHERE source_id=?",(source_id,)):raise KeyError("source not found")
  rid=str(record.get("id") or record.get("documentId") or record.get("publication-number") or record.get("vatNumber") or _hash(record)[:24]);names=[]
  for key in ("name","title","label","organisationName","organization_name"):
   v=record.get(key)
   if isinstance(v,str) and v.strip():names.append(v.strip())
  n={"source_id":source_id,"source_record_id":rid,"names":sorted(set(names)),"identifiers":{k:record[k] for k in ("vatNumber","celex","publication-number","documentId") if k in record},"locations":record.get("locations") or record.get("address") or [],"raw":record,"observed_at":observed_at or now_ts(),"review_required":True,"automatic_identity_confirmation":False};n["canonical_sha256"]=_hash(n);return n
 def readiness_matrix(self):
  out=[]
  for r in self.db.all("SELECT * FROM european_source_profiles_172 ORDER BY jurisdiction,source_id"):
   latest=self.db.one("SELECT * FROM european_terms_reviews_172 WHERE source_id=? ORDER BY reviewed_at DESC LIMIT 1",(r["source_id"],));sdk_status=None
   if r["sdk_enabled"]:
    sr=self.db.one("SELECT lifecycle_status FROM connector_sdk_specs_171 WHERE connector_id=?",(r["source_id"],));sdk_status=sr["lifecycle_status"] if sr else None
   blockers=[]
   if not latest or latest["decision"] not in {"accepted_for_sandbox","accepted_for_production"}:blockers.append("terms_review")
   if r["sdk_enabled"] and sdk_status!="FIXTURE_VALIDATED":blockers.append("fixture_contract")
   if r["access_mode"] in {"auth_required","registered_api"}:blockers.append("credential_or_registration")
   out.append({"source_id":r["source_id"],"title":r["title"],"jurisdiction":r["jurisdiction"],"access_mode":r["access_mode"],"status":r["status"],"sdk_status":sdk_status,"terms_decision":latest["decision"] if latest else None,"blockers":blockers,"production_active":False})
  return out
 def coverage_report(self):
  rows=self.readiness_matrix();cats={};jur={}
  for r in rows:
   jur[r["jurisdiction"]]=jur.get(r["jurisdiction"],0)+1;cat=self.db.one("SELECT category FROM european_source_profiles_172 WHERE source_id=?",(r["source_id"],))["category"];cats[cat]=cats.get(cat,0)+1
  report={"build":self.BUILD,"sources":len(rows),"jurisdictions":jur,"categories":cats,"fixture_validated":sum(r["sdk_status"]=="FIXTURE_VALIDATED" for r in rows),"production_active":0,"review_required":True,"gap_statement":"Official source depth improved; live production still requires current terms, credentials where applicable, probes and Source Gate approval."};report["payload_sha256"]=_hash(report);return report
 def dashboard(self):
  return {"build":self.BUILD,"catalogued_sources":self.db.one("SELECT COUNT(*) n FROM european_source_profiles_172")["n"],"core_business":"German and European public-source depth for review-first person OSINT","automatic_activation":False,"production_active":0}
