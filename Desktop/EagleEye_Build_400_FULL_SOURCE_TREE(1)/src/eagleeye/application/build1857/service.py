from __future__ import annotations
import hashlib, json, re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

def _canon(v: Any)->str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v: Any)->str: return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()

class Build1857ProductionSourceProcessingService:
    BUILD="185.7"
    CORE_SOURCES=(
      {"source_id":"de_bundestag_dip","title":"Deutscher Bundestag DIP","mode":"rest_api","authority":"official_primary","endpoint":"https://search.dip.bundestag.de/api/v1","auth":"api_key","rate_limit_per_minute":30,"intents":["person_role","parliament","publication","organization"]},
      {"source_id":"eu_data_portal","title":"data.europa.eu","mode":"rest_api","authority":"official_metadata","endpoint":"https://data.europa.eu/api/hub/search","auth":"none","rate_limit_per_minute":30,"intents":["official_dataset","organization","location"]},
      {"source_id":"eu_ted_procurement","title":"TED Search API","mode":"rest_api","authority":"official_primary","endpoint":"https://api.ted.europa.eu/v3/notices/search","auth":"none","rate_limit_per_minute":20,"intents":["organization","procurement","public_contract"]},
      {"source_id":"global_gleif_lei","title":"GLEIF LEI API","mode":"rest_api","authority":"official_registry","endpoint":"https://api.gleif.org/api/v1/lei-records","auth":"none","rate_limit_per_minute":30,"intents":["organization","ownership","address","identifier"]},
      {"source_id":"dnb_gnd","title":"DNB GND SRU","mode":"sru_api","authority":"curated_authority_file","endpoint":"https://services.dnb.de/sru/authorities","auth":"none","rate_limit_per_minute":20,"intents":["identity","name_variant","birth","death","occupation","publication"]},
      {"source_id":"govdata_source_discovery","title":"GovData","mode":"catalog_api","authority":"official_metadata","endpoint":"https://ckan.govdata.de/api/3/action/package_search","auth":"none","rate_limit_per_minute":20,"intents":["official_dataset","public_register","location","organization"]},
      {"source_id":"eu_parliament_open_data","title":"European Parliament Open Data","mode":"rest_api","authority":"official_primary","endpoint":"https://data.europarl.europa.eu/api/v2","auth":"none","rate_limit_per_minute":20,"intents":["person_role","parliament","organization","publication"]},
      {"source_id":"eu_cellar_multilingual","title":"EU Publications Office Cellar","mode":"sparql","authority":"official_primary","endpoint":"https://publications.europa.eu/webapi/rdf/sparql","auth":"none","rate_limit_per_minute":10,"intents":["publication","organization","law","multilingual"]},
      {"source_id":"familysearch_catalog","title":"FamilySearch Catalog","mode":"guided_authenticated","authority":"catalogue_and_index","endpoint":"https://www.familysearch.org/search/catalog","auth":"account","rate_limit_per_minute":6,"intents":["birth","death","marriage","family_history","residence"]},
      {"source_id":"matricula_online","title":"Matricula Online","mode":"guided_public","authority":"archival_primary","endpoint":"https://data.matricula-online.eu","auth":"none","rate_limit_per_minute":6,"intents":["birth","death","marriage","family_history"]},
      {"source_id":"archivportal_d","title":"Archivportal-D","mode":"guided_public","authority":"official_archive_discovery","endpoint":"https://www.archivportal-d.de","auth":"none","rate_limit_per_minute":6,"intents":["historical_record","family_history","occupation","residence"]},
      {"source_id":"arolsen_online_archive","title":"Arolsen Archives","mode":"guided_public","authority":"official_archive","endpoint":"https://collections.arolsen-archives.org","auth":"none","rate_limit_per_minute":6,"intents":["historical_record","migration","family_history","residence"]},
    )
    def __init__(self,db:Any,audit:Any,*,router:Any|None=None,actor:str="system"):
        self.db,self.audit,self.router,self.actor=db,audit,router,actor
    def seed_sources(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!="PRODUCTION SOURCES 1857 ANLEGEN": raise PermissionError("explicit approval required")
        for s in self.CORE_SOURCES:
            payload={**s,"status":"DOCUMENTED","production_active":False,"parser_status":"fixture_required"}
            self.db.execute("INSERT OR REPLACE INTO production_source_profiles_1857 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(s["source_id"],s["title"],s["mode"],s["authority"],s["endpoint"],s["auth"],s["rate_limit_per_minute"],dumps(s["intents"]),"DOCUMENTED","fixture_required",0,now_ts(),self.actor,_hash(payload)))
        return {"created":len(self.CORE_SOURCES),"production_active":0,"review_required":True}
    def register_fixture(self,source_id:str,fixture:Mapping[str,Any],*,schema_fields:Sequence[str],confirmation:str)->dict[str,Any]:
        if confirmation!=f"SOURCE FIXTURE 1857 {source_id} SPEICHERN": raise PermissionError("explicit fixture approval required")
        if source_id not in {s['source_id'] for s in self.CORE_SOURCES}: raise KeyError(source_id)
        missing=[x for x in schema_fields if x not in fixture]
        if missing: raise ValueError("fixture missing fields: "+", ".join(missing))
        fid=new_id("fixture1857"); payload={"fixture_id":fid,"source_id":source_id,"fixture":dict(fixture),"schema_fields":list(schema_fields)}
        self.db.execute("INSERT INTO production_source_fixtures_1857 VALUES(?,?,?,?,?,?,?)",(fid,source_id,dumps(fixture),dumps(list(schema_fields)),"VALID",now_ts(),_hash(payload)))
        self.db.execute("UPDATE production_source_profiles_1857 SET parser_status='FIXTURE_VALIDATED',status='FIXTURE_VALIDATED' WHERE source_id=?",(source_id,))
        return {**payload,"status":"FIXTURE_VALIDATED"}
    def record_live_probe(self,source_id:str,*,http_status:int,content_type:str,latency_ms:int,terms_reviewed:bool,parser_ok:bool,confirmation:str)->dict[str,Any]:
        if confirmation!=f"SOURCE LIVE 1857 {source_id} PRUEFEN": raise PermissionError("explicit live approval required")
        healthy=200<=int(http_status)<300 and bool(parser_ok)
        status="LIVE_VALIDATED" if healthy and terms_reviewed else ("LIVE_REVIEW_REQUIRED" if healthy else "DEGRADED")
        pid=new_id("probe1857"); payload={"probe_id":pid,"source_id":source_id,"http_status":int(http_status),"content_type":content_type,"latency_ms":int(latency_ms),"terms_reviewed":bool(terms_reviewed),"parser_ok":bool(parser_ok),"status":status}
        self.db.execute("INSERT INTO production_source_probes_1857 VALUES(?,?,?,?,?,?,?,?,?)",(pid,source_id,int(http_status),content_type,int(latency_ms),int(bool(terms_reviewed)),int(bool(parser_ok)),now_ts(),_hash(payload)))
        self.db.execute("UPDATE production_source_profiles_1857 SET status=? WHERE source_id=?",(status,source_id))
        return payload
    def source_gate(self,source_id:str,*,approved_by:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f"SOURCE GATE 1857 {source_id} FREIGEBEN": raise PermissionError("explicit gate approval required")
        row=self.db.one("SELECT status,parser_status FROM production_source_profiles_1857 WHERE source_id=?",(source_id,))
        if not row: raise KeyError(source_id)
        probe=self.db.one("SELECT terms_reviewed,parser_ok,http_status FROM production_source_probes_1857 WHERE source_id=? ORDER BY observed_at DESC LIMIT 1",(source_id,))
        blockers=[]
        if row['parser_status']!='FIXTURE_VALIDATED': blockers.append('fixture_not_validated')
        if not probe: blockers.append('live_probe_missing')
        elif not probe['terms_reviewed']: blockers.append('terms_not_reviewed')
        elif not probe['parser_ok'] or not (200<=probe['http_status']<300): blockers.append('live_parser_failed')
        active=not blockers
        status='PRODUCTION_READY' if active else 'BLOCKED'
        self.db.execute("UPDATE production_source_profiles_1857 SET status=?,production_active=? WHERE source_id=?",(status,int(active),source_id))
        return {"source_id":source_id,"status":status,"production_active":active,"blockers":blockers,"approved_by":approved_by,"automatic_activation":False}
    def normalize(self,source_id:str,record:Mapping[str,Any],*,source_ref:str)->dict[str,Any]:
        names=[]
        for k in ('name','title','person_name','organization_name','label'):
            v=record.get(k)
            if isinstance(v,str) and v.strip() and v.strip() not in names: names.append(v.strip())
        identifiers={k:str(v) for k,v in record.items() if k.lower() in {'id','lei','gnd_id','publication_number','record_id'} and v not in (None,'')}
        locations=[]
        for k in ('place','location','address','country'):
            v=record.get(k)
            if isinstance(v,str) and v.strip(): locations.append(v.strip())
        out={"source_id":source_id,"source_ref":source_ref,"names":names,"identifiers":identifiers,"locations":locations,"raw":dict(record),"observed_at":now_ts(),"review_required":True,"automatic_identity_confirmation":False}
        out['canonical_sha256']=_hash(out)
        rid=new_id('record1857')
        self.db.execute("INSERT INTO normalized_source_records_1857 VALUES(?,?,?,?,?,?,?,?,?)",(rid,source_id,source_ref,dumps(names),dumps(identifiers),dumps(locations),dumps(record),out['observed_at'],out['canonical_sha256']))
        return {"record_id":rid,**out}
    def route_with_readiness(self,*,case_id:str,question:str,person:Mapping[str,Any],lawful_basis:str,confirmation:str)->dict[str,Any]:
        if self.router is None: raise RuntimeError('guided router unavailable')
        route=self.router.route_question(case_id=case_id,question=question,person=person,lawful_basis=lawful_basis,max_sources=12,confirmation=f"SOURCE ROUTING 1856 {case_id} PLANEN")
        states={r['source_id']:r for r in self.db.all("SELECT source_id,status,production_active,parser_status FROM production_source_profiles_1857")}
        for step in route['steps']:
            state=states.get(step['source_id'])
            step['readiness']=dict(state) if state else {"status":"DOCUMENTED","production_active":0,"parser_status":"not_onboarded"}
            step['execution_mode']='structured_connector' if state and state['production_active'] else 'guided_browser_tab'
        route['routing_build']='185.7'; route['production_sources_first']=True
        return route
    def dashboard(self)->dict[str,Any]:
        rows=self.db.all("SELECT status,COUNT(*) AS n FROM production_source_profiles_1857 GROUP BY status")
        return {"build":self.BUILD,"sources":len(self.CORE_SOURCES),"by_status":{r['status']:r['n'] for r in rows},"automatic_activation":False,"general_search_secondary":True}
