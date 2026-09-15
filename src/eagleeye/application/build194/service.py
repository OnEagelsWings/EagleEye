from __future__ import annotations
import hashlib, json, re
from collections import defaultdict
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
def _hash(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode()).hexdigest()
SECRET = re.compile(r"(?i)(token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key)")
INJECTION = re.compile(r"(?i)(ignore previous instructions|reveal (?:the )?system prompt|bypass policy|disable audit|execute this command)")

class Build194MultimodalVerificationLabService:
    BUILD = "194.0"
    NEWS_AGGREGATORS = (
        ("gdelt_doc_api","GDELT DOC 2.0","global","multilingual_news_api","structured_connector","https://api.gdeltproject.org/api/v2/doc/doc","open"),
        ("mediacloud_search_api","Media Cloud Search","global","news_archive_api","credentialed_connector","https://api.mediacloud.org/api/search","api_key"),
        ("newsapi_org","NewsAPI","global","news_search_api","credentialed_connector","https://newsapi.org/v2/everything","api_key"),
        ("event_registry_api","Event Registry / NewsAPI.ai","global","event_news_api","credentialed_connector","https://eventregistry.org/api/v1/article/getArticles","api_key"),
        ("world_news_api","World News API","global","news_search_api","credentialed_connector","https://api.worldnewsapi.com/search-news","api_key"),
    )
    PUBLICATIONS = (
        ("de_tagesschau","Tagesschau","DE","de","public_broadcaster","https://www.tagesschau.de/xml/rss2/"),
        ("de_spiegel","Der Spiegel","DE","de","newspaper_magazine","https://www.spiegel.de/schlagzeilen/index.rss"),
        ("de_zeit","Die Zeit","DE","de","newspaper","https://newsfeed.zeit.de/index"),
        ("de_faz","Frankfurter Allgemeine Zeitung","DE","de","newspaper","https://www.faz.net/rss/aktuell/"),
        ("de_sueddeutsche","Süddeutsche Zeitung","DE","de","newspaper","https://rss.sueddeutsche.de/rss/Topthemen"),
        ("uk_bbc","BBC News","GB","en","public_broadcaster","https://feeds.bbci.co.uk/news/rss.xml"),
        ("uk_guardian","The Guardian","GB","en","newspaper","https://www.theguardian.com/world/rss"),
        ("us_npr","NPR","US","en","public_broadcaster","https://feeds.npr.org/1001/rss.xml"),
        ("us_ap","Associated Press","US","en","news_agency","https://apnews.com/"),
        ("us_nyt","The New York Times","US","en","newspaper","https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
        ("us_wapo","The Washington Post","US","en","newspaper","https://www.washingtonpost.com/"),
        ("il_kan","KAN News","IL","he","public_broadcaster","https://www.kan.org.il/"),
        ("il_haaretz","Haaretz","IL","he,en","newspaper","https://www.haaretz.com/"),
        ("il_timesofisrael","Times of Israel","IL","en","newspaper","https://www.timesofisrael.com/feed/"),
        ("il_ynet","Ynet","IL","he","newspaper","https://www.ynet.co.il/"),
        ("qa_aljazeera","Al Jazeera","QA","ar,en","broadcaster","https://www.aljazeera.com/xml/rss/all.xml"),
        ("sa_alarabiya","Al Arabiya","SA","ar,en","broadcaster","https://english.alarabiya.net/tools/rss"),
        ("ae_thenational","The National","AE","en","newspaper","https://www.thenationalnews.com/arc/outboundfeeds/rss/"),
        ("eg_ahram","Al-Ahram","EG","ar,en","newspaper","https://english.ahram.org.eg/"),
        ("ru_tass","TASS","RU","ru,en","state_news_agency","https://tass.com/rss/v2.xml"),
        ("ru_meduzа","Meduza","RU","ru,en","independent_news","https://meduza.io/rss/en/all"),
        ("ru_novaya","Novaya Gazeta Europe","RU","ru,en","independent_news","https://novayagazeta.eu/"),
        ("cn_xinhua","Xinhua","CN","zh,en","state_news_agency","https://english.news.cn/"),
        ("cn_globaltimes","Global Times","CN","zh,en","state_newspaper","https://www.globaltimes.cn/rss/outbrain.xml"),
        ("hk_scmp","South China Morning Post","HK","en","newspaper","https://www.scmp.com/rss/91/feed"),
        ("fr_france24","France 24","FR","fr,en,ar","public_broadcaster","https://www.france24.com/en/rss"),
        ("fr_lemonde","Le Monde","FR","fr","newspaper","https://www.lemonde.fr/rss/une.xml"),
        ("es_elpais","El País","ES","es","newspaper","https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"),
        ("it_ansа","ANSA","IT","it,en","news_agency","https://www.ansa.it/sito/ansait_rss.xml"),
        ("in_thehindu","The Hindu","IN","en","newspaper","https://www.thehindu.com/feeder/default.rss"),
        ("jp_nhk","NHK World","JP","ja,en","public_broadcaster","https://www3.nhk.or.jp/nhkworld/en/news/feeds/"),
        ("br_folha","Folha de S.Paulo","BR","pt","newspaper","https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"),
    )
    def __init__(self, db: Any, audit: Any, *, source_ai: Any, graph: Any, capture: Any, authenticity: Any, calibration: Any, source_ops: Any, actor: str="system"):
        self.db,self.audit=db,audit
        self.source_ai,self.graph,self.capture,self.authenticity,self.calibration,self.source_ops=source_ai,graph,capture,authenticity,calibration,source_ops
        self.actor=actor

    def seed_sources(self, *, confirmation: str) -> dict[str,Any]:
        if confirmation != "MEDIA SOURCES 194 ANLEGEN": raise PermissionError("explicit approval required")
        count=0
        for sid,name,country,klass,mode,endpoint,auth in self.NEWS_AGGREGATORS:
            p={"source_id":sid,"name":name,"country":country,"language":"multi","source_class":klass,"access_mode":mode,"endpoint":endpoint,"auth":auth,"status":"DOCUMENTED"}
            self.db.execute("INSERT OR REPLACE INTO media_source_profiles_194 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,name,country,"multi",klass,mode,endpoint,auth,"DOCUMENTED",1,now_ts(),dumps(["terms_review","fixture","live_probe"]),_hash(p))); count+=1
        for sid,name,country,lang,klass,url in self.PUBLICATIONS:
            p={"source_id":sid,"name":name,"country":country,"language":lang,"source_class":klass,"access_mode":"rss_or_guided_browser","endpoint":url,"auth":"none","status":"GUIDED_READY"}
            self.db.execute("INSERT OR REPLACE INTO media_source_profiles_194 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,name,country,lang,klass,"rss_or_guided_browser",url,"none","GUIDED_READY",1,now_ts(),dumps(["terms_review","feed_probe"]),_hash(p))); count+=1
        return {"profiles":count,"aggregators":len(self.NEWS_AGGREGATORS),"publications":len(self.PUBLICATIONS),"automatic_activation":False}

    def create_verification(self, *, case_id: str, target_ref: str, media_type: str, question: str, source_refs: Sequence[str]=(), confirmation: str) -> dict[str,Any]:
        if confirmation != f"VERIFY LAB 194 {case_id} ANLEGEN": raise PermissionError("explicit approval required")
        if media_type not in {"image","video","audio","document","text","web"}: raise ValueError("unsupported media_type")
        vid,created=new_id("verify194"),now_ts(); q=self._redact(question)
        policy={"local_processing":True,"external_uploads":False,"automatic_verdict":False,"biometric_identification":False,"human_review_required":True}
        payload={"verification_id":vid,"case_id":case_id,"target_ref":target_ref,"media_type":media_type,"question":q,"source_refs":list(source_refs),"status":"planned","created_at":created,"policy":policy}
        self.db.execute("INSERT INTO multimodal_verifications_194 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(vid,case_id,target_ref,media_type,q,dumps(list(source_refs)),"planned",created,dumps(policy),"candidate",_hash(payload)))
        return payload|{"routes":self.route_verification(question=question,media_type=media_type,countries=[],confirmation="VERIFY ROUTE 194 PLANEN")}

    def add_signal(self, *, verification_id: str, signal_type: str, direction: str, score: float, method: str, details: Mapping[str,Any], source_ref: str="", confirmation: str) -> dict[str,Any]:
        if confirmation != f"VERIFY SIGNAL 194 {verification_id} SPEICHERN": raise PermissionError("explicit approval required")
        if direction not in {"support","contradict","neutral"}: raise ValueError("invalid direction")
        if not 0 <= float(score) <= 1: raise ValueError("score out of range")
        sid,created=new_id("vsig194"),now_ts(); clean=self._redact(dict(details))
        payload={"signal_id":sid,"verification_id":verification_id,"signal_type":signal_type,"direction":direction,"score":float(score),"method":method,"details":clean,"source_ref":source_ref,"created_at":created}
        self.db.execute("INSERT INTO verification_signals_194 VALUES(?,?,?,?,?,?,?,?,?,?)",(sid,verification_id,signal_type,direction,float(score),method,dumps(clean),source_ref,created,_hash(payload)))
        return payload

    def evaluate(self, *, verification_id: str, confirmation: str) -> dict[str,Any]:
        if confirmation != f"VERIFY LAB 194 {verification_id} AUSWERTEN": raise PermissionError("explicit approval required")
        row=self.db.one("SELECT * FROM multimodal_verifications_194 WHERE verification_id=?",(verification_id,))
        if not row: raise KeyError(verification_id)
        signals=[dict(x) for x in self.db.all("SELECT * FROM verification_signals_194 WHERE verification_id=?",(verification_id,))]
        pos=[x for x in signals if x["direction"]=="support"]; neg=[x for x in signals if x["direction"]=="contradict"]
        ps=sum(float(x["score"]) for x in pos)/len(pos) if pos else 0.0; ns=sum(float(x["score"]) for x in neg)/len(neg) if neg else 0.0
        if len(neg)>=2 and ns>=.7: status="strongly_suspicious_candidate"
        elif neg and pos: status="contested_candidate"
        elif neg: status="suspicious_candidate"
        elif len(pos)>=2 and ps>=.7: status="supported_candidate"
        else: status="inconclusive"
        limitations=["detector_signals_are_not_verdict","provenance_does_not_prove_context","human_review_required"]
        if not signals: limitations.append("no_signals_available")
        eid,created=new_id("veval194"),now_ts(); payload={"evaluation_id":eid,"verification_id":verification_id,"status":status,"support_score":round(ps,4),"contradiction_score":round(ns,4),"signals":len(signals),"limitations":limitations,"created_at":created}
        self.db.execute("INSERT INTO verification_evaluations_194 VALUES(?,?,?,?,?,?,?,?,?)",(eid,verification_id,status,ps,ns,len(signals),dumps(limitations),created,_hash(payload)))
        self.db.execute("UPDATE multimodal_verifications_194 SET status=? WHERE verification_id=?",(status,verification_id))
        return payload

    def route_verification(self, *, question: str, media_type: str, countries: Sequence[str], confirmation: str) -> dict[str,Any]:
        if confirmation != "VERIFY ROUTE 194 PLANEN": raise PermissionError("explicit approval required")
        q=question.lower(); intents=[]
        if any(x in q for x in ("fake","deepfake","manipul","synthet")): intents.append("manipulation")
        if any(x in q for x in ("woher","quelle","provenienz","origin","erstmals")): intents.append("provenance")
        if any(x in q for x in ("behaupt","bericht","zeitung","presse","news","darstellung")): intents.append("news_context")
        if any(x in q for x in ("ort","location","datum","zeit","weather")): intents.append("context")
        if not intents: intents=["provenance","news_context"]
        sources=[]
        if "manipulation" in intents: sources += ["nist_openmfc_live","c2pa_trust_list_live","invid_weverify_reference"]
        if "provenance" in intents: sources += ["c2pa_capture_provenance","internet_archive_cdx_190","browser_direct_capture"]
        if "news_context" in intents or "manipulation" in intents or "provenance" in intents:
            sources += ["gdelt_doc_api","mediacloud_search_api","newsapi_org","event_registry_api"]
        country_set={c.upper() for c in countries}
        for sid,_,country,_,_,_ in self.PUBLICATIONS:
            if not country_set or country.upper() in country_set: sources.append(sid)
        seen=[]
        for s in sources:
            if s not in seen: seen.append(s)
        return {"intents":intents,"sources":seen,"execution":"structured_connector_or_guided_firefox","automatic_external_upload":False}

    def create_news_analysis(self, *, case_id: str, question: str, countries: Sequence[str], languages: Sequence[str], date_from: str="", date_to: str="", confirmation: str) -> dict[str,Any]:
        if confirmation != f"NEWS ANALYSIS 194 {case_id} ANLEGEN": raise PermissionError("explicit approval required")
        aid,created=new_id("news194"),now_ts(); route=self.route_verification(question=question,media_type="text",countries=countries,confirmation="VERIFY ROUTE 194 PLANEN")
        payload={"analysis_id":aid,"case_id":case_id,"question":question,"countries":list(countries),"languages":list(languages),"date_from":date_from,"date_to":date_to,"sources":route["sources"],"status":"planned","created_at":created,"policy":{"copyright_safe":True,"fulltext_export":False,"source_citations_required":True,"human_review_required":True}}
        self.db.execute("INSERT INTO news_analyses_194 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(aid,case_id,question,dumps(list(countries)),dumps(list(languages)),date_from,date_to,dumps(route["sources"]),"planned",created,dumps(payload["policy"]),_hash(payload)))
        return payload

    def record_article(self, *, analysis_id: str, source_id: str, title: str, url: str, published_at: str, language: str, country: str, article_type: str, claims: Sequence[Mapping[str,Any]], summary: str, provenance: Mapping[str,Any], confirmation: str) -> dict[str,Any]:
        if confirmation != f"NEWS ARTICLE 194 {analysis_id} SPEICHERN": raise PermissionError("explicit approval required")
        if article_type not in {"news_report","analysis","opinion","editorial","interview","press_release","fact_check"}: raise ValueError("invalid article_type")
        rid,created=new_id("article194"),now_ts(); clean_claims=self._redact(list(claims)); clean_prov=self._redact(dict(provenance)); clean_summary=str(self._redact(summary))[:4000]
        injection=bool(INJECTION.search(title+" "+summary))
        payload={"article_id":rid,"analysis_id":analysis_id,"source_id":source_id,"title":title,"url":self._redact_url(url),"published_at":published_at,"language":language,"country":country,"article_type":article_type,"claims":clean_claims,"summary":clean_summary,"provenance":clean_prov,"prompt_injection_candidate":injection,"review_status":"candidate","created_at":created}
        self.db.execute("INSERT INTO news_articles_194 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(rid,analysis_id,source_id,title,payload["url"],published_at,language,country,article_type,dumps(clean_claims),clean_summary,dumps(clean_prov),1 if injection else 0,"candidate",created,_hash(payload)))
        return payload

    def synthesize_news(self, *, analysis_id: str, confirmation: str) -> dict[str,Any]:
        if confirmation != f"NEWS SYNTHESIS 194 {analysis_id} ERSTELLEN": raise PermissionError("explicit approval required")
        rows=[dict(x) for x in self.db.all("SELECT * FROM news_articles_194 WHERE analysis_id=?",(analysis_id,))]
        by_claim=defaultdict(list); perspectives=defaultdict(int); countries=set(); sources=set()
        for r in rows:
            countries.add(r["country"]); sources.add(r["source_id"]); perspectives[r["article_type"]]+=1
            for c in json.loads(r["claims_json"] or "[]"):
                text=str(c.get("claim") or c.get("text") or "").strip()
                if text: by_claim[text].append({"source_id":r["source_id"],"direction":c.get("direction","support"),"article_type":r["article_type"],"url":r["url"]})
        findings=[]
        for claim,items in by_claim.items():
            support={x["source_id"] for x in items if x["direction"]=="support"}; contra={x["source_id"] for x in items if x["direction"]=="contradict"}
            status="contested_candidate" if support and contra else "corroborated_candidate" if len(support)>=2 else "supported_candidate" if support else "contradicted_candidate" if contra else "inconclusive"
            findings.append({"claim":claim,"status":status,"source_count":len(support|contra),"evidence":items})
        sid,created=new_id("newssyn194"),now_ts(); limits=["news_reporting_is_not_primary_evidence","shared_wire_copy_may_not_be_independent","opinion_must_not_be_treated_as_fact","copyright_safe_summaries_only","human_review_required"]
        payload={"synthesis_id":sid,"analysis_id":analysis_id,"article_count":len(rows),"source_count":len(sources),"countries":sorted(countries),"perspectives":dict(perspectives),"findings":findings,"limitations":limits,"created_at":created,"next_step":"3_verify_candidates"}
        self.db.execute("INSERT INTO news_syntheses_194 VALUES(?,?,?,?,?,?,?,?,?,?)",(sid,analysis_id,len(rows),len(sources),dumps(sorted(countries)),dumps(dict(perspectives)),dumps(findings),dumps(limits),created,_hash(payload)))
        return payload

    def dashboard(self, *, case_id: str="") -> dict[str,Any]:
        n=lambda q,a=(): int((self.db.one(q,a) or {"n":0})["n"])
        return {"build":self.BUILD,"source_profiles":n("SELECT COUNT(*) AS n FROM media_source_profiles_194"),"verifications":n("SELECT COUNT(*) AS n FROM multimodal_verifications_194"),"news_analyses":n("SELECT COUNT(*) AS n FROM news_analyses_194"),"guided_summary":"Medium prüfen → internationale Berichte vergleichen → Primärquelle bestätigen → Fallakte","opsec":{"local_processing":True,"external_uploads":False,"automatic_verdict":False,"automatic_identity_confirmation":False}}

    def _redact(self,v: Any)->Any:
        if isinstance(v,Mapping): return {k:("[REDACTED]" if SECRET.search(str(k)) else self._redact(x)) for k,x in v.items()}
        if isinstance(v,list): return [self._redact(x) for x in v]
        return v
    def _redact_url(self,url: str)->str:
        return re.sub(r"(?i)(token|api[_-]?key|key|auth|session)=([^&]+)",r"\1=%5BREDACTED%5D",url)
