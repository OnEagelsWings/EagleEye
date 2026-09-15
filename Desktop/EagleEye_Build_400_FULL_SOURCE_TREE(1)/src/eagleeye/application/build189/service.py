from __future__ import annotations
import hashlib, json, time, urllib.parse, urllib.request
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v: Any)->str: return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v: Any)->str: return hashlib.sha256(_canon(v).encode()).hexdigest()

class Build189SocialGlobalSourceFabricService:
    """Public-source social fabric and country packs. No access-control bypass."""
    BUILD="189.0"
    PROFILES=(
      {"source_id":"bluesky_public_api","title":"Bluesky Public AppView","country":"GLOBAL","family":"social","access_mode":"rest_json","endpoint":"https://public.api.bsky.app/xrpc","query_template":"/app.bsky.feed.searchPosts?q={query}","auth":"none","rate_per_min":30,"wave":1,"required":["posts"]},
      {"source_id":"mastodon_public_api","title":"Mastodon Public API","country":"GLOBAL","family":"social","access_mode":"federated_rest","endpoint":"https://{instance}/api/v2","query_template":"/search?q={query}&type=statuses","auth":"instance_dependent","rate_per_min":20,"wave":1,"required":["statuses"]},
      {"source_id":"youtube_data_api","title":"YouTube Data API v3","country":"GLOBAL","family":"video_social","access_mode":"rest_json","endpoint":"https://www.googleapis.com/youtube/v3","query_template":"/search?part=snippet&type=video&q={query}","auth":"api_key","rate_per_min":20,"wave":1,"required":["items"]},
      {"source_id":"reddit_oauth_api","title":"Reddit Data API","country":"GLOBAL","family":"community","access_mode":"oauth_rest","endpoint":"https://oauth.reddit.com","query_template":"/search?q={query}&type=link","auth":"oauth2","rate_per_min":30,"wave":2,"required":["data"]},
      {"source_id":"github_public_api","title":"GitHub Public API","country":"GLOBAL","family":"developer","access_mode":"rest_json","endpoint":"https://api.github.com","query_template":"/search/users?q={query}","auth":"optional_token","rate_per_min":10,"wave":1,"required":["items"]},
      {"source_id":"internet_archive_cdx","title":"Internet Archive CDX","country":"GLOBAL","family":"web_archive","access_mode":"rest_json","endpoint":"https://web.archive.org/cdx/search/cdx","query_template":"?url={query}&output=json&filter=statuscode:200","auth":"none","rate_per_min":6,"wave":1,"required":["rows"]},
      {"source_id":"us_sec_edgar","title":"US SEC EDGAR APIs","country":"US","family":"corporate","access_mode":"rest_json","endpoint":"https://data.sec.gov","query_template":"/submissions/CIK{query}.json","auth":"none_user_agent_required","rate_per_min":300,"wave":1,"required":["name","cik"]},
      {"source_id":"us_data_gov","title":"US Data.gov CKAN","country":"US","family":"open_data","access_mode":"rest_json","endpoint":"https://catalog.data.gov/api/3/action","query_template":"/package_search?q={query}","auth":"none","rate_per_min":30,"wave":2,"required":["success","result"]},
      {"source_id":"il_data_gov_ckan","title":"Israel data.gov.il CKAN","country":"IL","family":"open_data","access_mode":"rest_json","endpoint":"https://data.gov.il/api/3/action","query_template":"/package_search?q={query}","auth":"none","rate_per_min":20,"wave":1,"required":["success","result"]},
      {"source_id":"il_corporations_registry","title":"Israel Corporations Authority","country":"IL","family":"corporate","access_mode":"guided_browser","endpoint":"https://www.gov.il/en/service/company_extract","query_template":"?query={query}","auth":"none_or_paid_extract","rate_per_min":4,"wave":2,"required":["records"]},
      {"source_id":"ae_open_data","title":"UAE Official Open Data Portal","country":"AE","family":"open_data","access_mode":"guided_browser","endpoint":"https://bayanat.ae","query_template":"/en/search?q={query}","auth":"none","rate_per_min":6,"wave":2,"required":["records"]},
      {"source_id":"ru_egrul_fns","title":"Russia FNS EGRUL/EGRIP","country":"RU","family":"corporate","access_mode":"guided_browser","endpoint":"https://egrul.nalog.ru","query_template":"/?query={query}","auth":"captcha_possible","rate_per_min":3,"wave":3,"required":["records"]},
      {"source_id":"ru_official_legal_information","title":"Russia Official Legal Information","country":"RU","family":"legal","access_mode":"guided_browser","endpoint":"http://pravo.gov.ru","query_template":"/search?query={query}","auth":"none","rate_per_min":4,"wave":3,"required":["records"]},
      {"source_id":"cn_gsxt","title":"China National Enterprise Credit System","country":"CN","family":"corporate","access_mode":"guided_browser","endpoint":"https://www.gsxt.gov.cn","query_template":"/index.html?query={query}","auth":"captcha_required","rate_per_min":2,"wave":3,"required":["records"]},
      {"source_id":"hk_companies_open_data","title":"Hong Kong Companies Registry Open Data","country":"HK","family":"corporate","access_mode":"open_data_files","endpoint":"https://data.gov.hk/en-datasets/provider/hk-cr","query_template":"?q={query}","auth":"none","rate_per_min":10,"wave":2,"required":["records"]},
    )
    def __init__(self,db:Any,audit:Any,*,records:Any,source_ops:Any,guided_router:Any,actor:str="system"):
        self.db,self.audit,self.records,self.source_ops,self.guided_router,self.actor=db,audit,records,source_ops,guided_router,actor
    def seed_profiles(self,*,confirmation:str)->dict[str,Any]:
        if confirmation!="GLOBAL SOURCES 189 ANLEGEN": raise PermissionError("explicit approval required")
        for p in self.PROFILES:
            status="CONTRACT_VALIDATED" if p["access_mode"] not in {"guided_browser","open_data_files"} else "GUIDED_READY"
            self.db.execute("INSERT OR REPLACE INTO global_source_profiles_189 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (p["source_id"],p["title"],p["country"],p["family"],p["access_mode"],p["endpoint"],p["query_template"],p["auth"],p["rate_per_min"],p["wave"],dumps(p["required"]),status,0,0,0,now_ts(),_hash(p)))
        self._event("profiles_seeded","*",{"count":len(self.PROFILES)})
        return {"created":len(self.PROFILES),"structured":sum(p["access_mode"] not in {"guided_browser","open_data_files"} for p in self.PROFILES),"automatic_activation":False}
    def validate_fixture(self,source_id:str,fixture:Mapping[str,Any],*,confirmation:str)->dict[str,Any]:
        if confirmation!=f"GLOBAL FIXTURE 189 {source_id} VALIDIEREN": raise PermissionError("explicit approval required")
        p=self._profile(source_id); missing=[x for x in json.loads(p["required_fields_json"]) if x not in fixture]
        if missing: raise ValueError("missing fixture fields: "+", ".join(missing))
        parsed=self._parse(source_id,fixture); fid=new_id("gfixture189")
        self.db.execute("INSERT INTO global_source_fixtures_189 VALUES(?,?,?,?,?,?,?)",(fid,source_id,dumps(fixture),1,len(parsed),now_ts(),_hash({"id":fid,"source":source_id,"count":len(parsed)})))
        self.db.execute("UPDATE global_source_profiles_189 SET status='FIXTURE_VALIDATED',fixture_validated=1,updated_at=? WHERE source_id=?",(now_ts(),source_id))
        return {"source_id":source_id,"normalized_count":len(parsed),"status":"FIXTURE_VALIDATED"}
    def record_live_probe(self,source_id:str,*,http_status:int,content_type:str,latency_ms:int,parser_ok:bool,terms_reviewed:bool,records_received:int,confirmation:str)->dict[str,Any]:
        if confirmation!=f"GLOBAL LIVE 189 {source_id} PRUEFEN": raise PermissionError("explicit approval required")
        self._profile(source_id); pid=new_id("gprobe189"); ok=200<=int(http_status)<300 and parser_ok and terms_reviewed
        payload={"id":pid,"source_id":source_id,"http_status":http_status,"content_type":content_type,"latency_ms":latency_ms,"parser_ok":parser_ok,"terms_reviewed":terms_reviewed,"records_received":records_received}
        self.db.execute("INSERT INTO global_source_probes_189 VALUES(?,?,?,?,?,?,?,?,?,?)",(pid,source_id,http_status,content_type,latency_ms,int(parser_ok),int(terms_reviewed),records_received,now_ts(),_hash(payload)))
        if ok: self.db.execute("UPDATE global_source_profiles_189 SET status='LIVE_VALIDATED',live_validated=1,updated_at=? WHERE source_id=?",(now_ts(),source_id))
        return {**payload,"healthy":ok,"automatic_activation":False}
    def promote(self,source_id:str,*,approved_by:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f"GLOBAL SOURCE 189 {source_id} AKTIVIEREN": raise PermissionError("explicit approval required")
        p=self._profile(source_id); blockers=[]
        if p["access_mode"] in {"guided_browser","open_data_files"}: blockers.append("guided_or_file_source_not_structured_connector")
        if not p["fixture_validated"]: blockers.append("fixture_not_validated")
        if not p["live_validated"]: blockers.append("live_probe_not_validated")
        if blockers: return {"promoted":False,"blockers":blockers,"status":p["status"]}
        self.db.execute("UPDATE global_source_profiles_189 SET status='PRODUCTION_ACTIVE',production_active=1,updated_at=? WHERE source_id=?",(now_ts(),source_id))
        self._event("source_activated",source_id,{"approved_by":approved_by})
        return {"promoted":True,"blockers":[],"status":"PRODUCTION_ACTIVE","automatic_activation":False}
    def route(self,*,case_id:str,question:str,person:Mapping[str,Any],countries:Sequence[str],lawful_basis:str,confirmation:str)->dict[str,Any]:
        if confirmation!="GLOBAL ROUTING 189 PLANEN": raise PermissionError("explicit approval required")
        if not lawful_basis.strip(): raise ValueError("lawful basis required")
        tokens=(question+" "+" ".join(str(v) for v in person.values())).lower(); wanted={c.upper() for c in countries}
        profiles=[dict(r) for r in self.db.all("SELECT * FROM global_source_profiles_189")]
        scored=[]
        for p in profiles:
            score=0
            if p["country_code"] in wanted or p["country_code"]=="GLOBAL": score+=30
            if any(x in tokens for x in ("firma","company","unternehmen","director","geschäft")) and p["source_family"]=="corporate": score+=35
            if any(x in tokens for x in ("social","account","profil","post","kommentar","video")) and p["source_family"] in {"social","community","video_social","developer"}: score+=35
            if any(x in tokens for x in ("archiv","alte webseite","history","historisch")) and p["source_family"]=="web_archive": score+=35
            if any(x in tokens for x in ("dataset","behörde","government","open data")) and p["source_family"]=="open_data": score+=35
            if score:
                query=" ".join(str(x).strip() for x in [person.get("given_name",""),person.get("family_name",""),person.get("organization",""),person.get("place","")] if str(x).strip())
                url=p["endpoint"].replace("{instance}","mastodon.social")+p["query_template"].replace("{query}",urllib.parse.quote_plus(query))
                scored.append({"source_id":p["source_id"],"title":p["title"],"country":p["country_code"],"score":score,"status":p["status"],"production_active":bool(p["production_active"]),"execution_mode":"structured_connector" if p["production_active"] else "guided_browser_tab","url":url,"candidate_only":True})
        scored.sort(key=lambda x:(not x["production_active"],-x["score"],x["title"]))
        return {"case_id":case_id,"question":question,"steps":scored,"next_global_step":"3_verify_candidates","automatic_identity_confirmation":False}
    def ingest(self,*,case_id:str,source_id:str,payload:Mapping[str,Any],source_ref:str,confirmation:str)->dict[str,Any]:
        if confirmation!=f"GLOBAL CANDIDATE 189 {case_id} SPEICHERN": raise PermissionError("explicit approval required")
        self._profile(source_id); items=self._parse(source_id,payload); saved=[]
        for item in items:
            cid=new_id("global189"); out={"candidate_id":cid,"case_id":case_id,"source_id":source_id,"source_record_id":str(item.get("id","")),"entity_type":item.get("type","record"),"names":item.get("names",[]),"identifiers":item.get("identifiers",{}),"relations":item.get("relations",[]),"source_ref":source_ref,"review_status":"candidate"}
            self.db.execute("INSERT INTO global_normalized_candidates_189 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(cid,case_id,source_id,out["source_record_id"],out["entity_type"],dumps(out["names"]),dumps(out["identifiers"]),dumps(out["relations"]),source_ref,now_ts(),"candidate",_hash(out))); saved.append(out)
        return {"saved":len(saved),"candidates":saved,"human_review_required":True,"automatic_identity_confirmation":False}
    def dashboard(self)->dict[str,Any]:
        rows=[dict(r) for r in self.db.all("SELECT * FROM global_source_profiles_189 ORDER BY activation_wave,country_code,title")]
        return {"build":self.BUILD,"total":len(rows),"active":sum(bool(r["production_active"]) for r in rows),"live_validated":sum(bool(r["live_validated"]) for r in rows),"countries":sorted({r["country_code"] for r in rows}),"sources":rows,"automatic_activation":False}
    def _parse(self,sid:str,p:Mapping[str,Any])->list[dict[str,Any]]:
        if sid=="bluesky_public_api": rows=p.get("posts",[])
        elif sid in {"youtube_data_api","github_public_api"}: rows=p.get("items",[])
        elif sid=="mastodon_public_api": rows=p.get("statuses",[])
        elif sid=="reddit_oauth_api": rows=((p.get("data") or {}).get("children",[])); rows=[r.get("data",{}) for r in rows]
        elif sid in {"us_data_gov","il_data_gov_ckan"}: rows=((p.get("result") or {}).get("results",[]))
        elif sid=="internet_archive_cdx": rows=p.get("rows",[])
        elif sid=="us_sec_edgar": rows=[p]
        else: rows=p.get("records",[])
        out=[]
        for r in rows if isinstance(rows,list) else []:
            if isinstance(r,list): out.append({"id":"|".join(map(str,r[:3])),"type":"web_snapshot","names":[str(r[2]) if len(r)>2 else ""],"identifiers":{},"relations":[]}); continue
            if not isinstance(r,Mapping): continue
            out.append({"id":r.get("id",r.get("cik",r.get("name",""))),"type":r.get("type","record"),"names":[x for x in [r.get("name"),r.get("title"),((r.get("snippet") or {}).get("title") if isinstance(r.get("snippet"),Mapping) else None)] if x],"identifiers":{"username":r.get("login"),"cik":r.get("cik")},"relations":[]})
        return out
    def _profile(self,sid:str):
        row=self.db.one("SELECT * FROM global_source_profiles_189 WHERE source_id=?",(sid,))
        if row is None: raise KeyError(sid)
        return row
    def _event(self,event_type:str,source_id:str,payload:Mapping[str,Any]):
        prev=self.db.one("SELECT event_sha256 FROM global_source_events_189 ORDER BY created_at DESC,event_id DESC LIMIT 1")
        ph=prev["event_sha256"] if prev else ""; eid=new_id("gse189"); created=now_ts(); eh=_hash({"id":eid,"type":event_type,"source":source_id,"payload":payload,"created":created,"prev":ph})
        self.db.execute("INSERT INTO global_source_events_189 VALUES(?,?,?,?,?,?,?,?)",(eid,event_type,source_id,dumps(payload),created,self.actor,ph,eh))
