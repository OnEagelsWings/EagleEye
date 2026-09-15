from __future__ import annotations
import base64, gzip, hashlib, json, os, re, urllib.parse
from pathlib import Path
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
SECRET=re.compile(r'(?i)(token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key)')

class Build191TemporalIdentityResolutionService:
 BUILD="191.0"
 def __init__(self,db:Any,audit:Any,*,capture:Any,source_ops:Any,global_sources:Any,ai:Any,base_dir:str|Path=".",actor:str="system"):
  self.db,self.audit,self.capture,self.source_ops,self.global_sources,self.ai,self.actor=db,audit,capture,source_ops,global_sources,ai,actor
  self.base_dir=Path(base_dir).resolve(); self.evidence_dir=self.base_dir/"data"/"evidence_191"; self.evidence_dir.mkdir(parents=True,exist_ok=True)
 def ingest_browser_bridge(self,*,case_id:str,source_id:str,page_url:str,title:str,visible_text:str,dom_html:str,resources:Sequence[Mapping[str,Any]],screenshot_base64:str="",headers:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
  if confirmation!=f"BROWSER BRIDGE 191 {case_id} SPEICHERN":raise PermissionError("explicit approval required")
  safe_resources=[]
  for r in resources[:2000]:
   url=self._safe_url(str(r.get("url",r.get("name",""))))
   safe_resources.append({"url":url,"type":str(r.get("type",r.get("initiatorType","")))[:80],"duration_ms":float(r.get("duration",0) or 0),"transfer_size":int(r.get("transferSize",0) or 0)})
  shot_ref=""; shot_hash=""
  if screenshot_base64:
   raw=base64.b64decode(screenshot_base64.split(",")[-1],validate=True)
   if len(raw)>25*1024*1024:raise ValueError("screenshot too large")
   shot_hash=hashlib.sha256(raw).hexdigest(); path=self.evidence_dir/f"{new_id('shot191')}.png"; path.write_bytes(raw); shot_ref=str(path.relative_to(self.base_dir))
  capture=self.capture.capture(case_id=case_id,source_id=source_id,source_url=page_url,final_url=page_url,http_status=200,content_type="text/html",headers=self._redact(dict(headers or {})),text_content=visible_text,html_content=dom_html,screenshot_ref=shot_ref,media_refs=[r["url"] for r in safe_resources if r["type"] in {"img","image","video","audio"}],request_meta={"bridge":"firefox191","resource_count":len(safe_resources)},confirmation=f"CAPTURE 190 {case_id} SPEICHERN")
  bid=new_id("bridge191"); created=now_ts(); p={"bridge_id":bid,"case_id":case_id,"capture_id":capture["capture_id"],"url":self._safe_url(page_url),"title":title,"dom":hashlib.sha256(dom_html.encode()).hexdigest(),"screenshot":shot_hash,"resources":safe_resources,"created":created}
  self.db.execute("INSERT INTO browser_bridge_captures_191 VALUES(?,?,?,?,?,?,?,?,?,?)",(bid,case_id,capture["capture_id"],p["url"],title,p["dom"],shot_hash,dumps(safe_resources),created,_hash(p)))
  self._event("browser_bridge_capture",bid,{"capture_id":capture["capture_id"],"resources":len(safe_resources)})
  return {"bridge_id":bid,"capture_id":capture["capture_id"],"screenshot_ref":shot_ref,"resource_count":len(safe_resources),"automatic_external_upload":False,"review_required":True}
 def export_warc(self,*,case_id:str,capture_id:str,created_by:str,include_resources:bool=True,confirmation:str)->dict[str,Any]:
  if confirmation!=f"WARC 191 {capture_id} EXPORTIEREN":raise PermissionError("explicit approval required")
  c=self.db.one("SELECT * FROM evidence_captures_190 WHERE capture_id=? AND case_id=?",(capture_id,case_id))
  if not c:raise KeyError(capture_id)
  records=[]
  metadata={"capture_id":capture_id,"case_id":case_id,"source_url":c["source_url"],"captured_at":c["captured_at"],"content_sha256":c["content_sha256"],"review_required":True}
  records.append(self._warc_record("metadata",f"urn:uuid:{new_id('warcinfo')}","application/json",_canon(metadata).encode(),target=c["source_url"]))
  payload=(c["html_content"] or c["text_content"]).encode("utf-8")
  records.append(self._warc_record("response",f"urn:uuid:{new_id('response')}",c["content_type"] or "text/html",payload,target=c["final_url"]))
  bridge=self.db.one("SELECT resources_json FROM browser_bridge_captures_191 WHERE capture_id=? ORDER BY created_at DESC LIMIT 1",(capture_id,))
  if include_resources and bridge:
   for r in json.loads(bridge["resources_json"] or "[]")[:1000]: records.append(self._warc_record("metadata",f"urn:uuid:{new_id('resource')}","application/json",_canon(r).encode(),target=r.get("url",c["final_url"])))
  raw=b"".join(records); wid=new_id("warc191"); path=self.evidence_dir/f"{wid}.warc.gz"
  with gzip.open(path,"wb",compresslevel=6) as f:f.write(raw)
  digest=hashlib.sha256(path.read_bytes()).hexdigest(); created=now_ts()
  self.db.execute("INSERT INTO warc_exports_191 VALUES(?,?,?,?,?,?,?,?,?)",(wid,case_id,capture_id,str(path.relative_to(self.base_dir)),len(records),digest,created,created_by,1))
  self._event("warc_exported",wid,{"capture_id":capture_id,"records":len(records),"sha256":digest})
  return {"warc_id":wid,"warc_path":str(path.relative_to(self.base_dir)),"record_count":len(records),"warc_sha256":digest,"format":"WARC/1.1 gzip","review_required":True}
 def create_identity(self,*,case_id:str,display_name:str,identity_type:str="person",attributes:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
  if confirmation!=f"IDENTITY 191 {case_id} ANLEGEN":raise PermissionError("explicit approval required")
  iid=new_id("identity191"); created=now_ts(); attrs=self._redact(dict(attributes or {})); p={"id":iid,"case":case_id,"name":display_name,"type":identity_type,"attrs":attrs,"created":created}
  self.db.execute("INSERT INTO temporal_identities_191 VALUES(?,?,?,?,?,?,?,?)",(iid,case_id,display_name,identity_type,dumps(attrs),"candidate",created,_hash(p)))
  return {"identity_id":iid,"review_status":"candidate"}
 def add_fact(self,*,identity_id:str,fact_type:str,fact_value:str,valid_from:str="",valid_to:str="",source_refs:Sequence[str]=(),confidence:float=.5,confirmation:str)->dict[str,Any]:
  if confirmation!=f"IDENTITY FACT 191 {identity_id} SPEICHERN":raise PermissionError("explicit approval required")
  if not 0<=confidence<=1:raise ValueError("confidence")
  fid=new_id("fact191"); observed=now_ts(); p={"id":fid,"identity":identity_id,"type":fact_type,"value":fact_value,"from":valid_from,"to":valid_to,"sources":list(source_refs),"confidence":confidence}
  self.db.execute("INSERT INTO temporal_identity_facts_191 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(fid,identity_id,fact_type,fact_value,valid_from,valid_to,observed,dumps(list(source_refs)),confidence,"candidate",_hash(p)))
  return {"fact_id":fid,"review_status":"candidate","valid_from":valid_from,"valid_to":valid_to}
 def assess_link(self,*,case_id:str,left_identity_id:str,right_identity_id:str,link_type:str,evidence:Sequence[Mapping[str,Any]],valid_from:str="",valid_to:str="",confirmation:str)->dict[str,Any]:
  if confirmation!=f"IDENTITY LINK 191 {case_id} PRUEFEN":raise PermissionError("explicit approval required")
  independent={str(x.get("source_id","")) for x in evidence if x.get("independent") and x.get("source_id")}; scores=[float(x.get("score",0)) for x in evidence]; score=sum(scores)/len(scores) if scores else 0.0
  contradictions=[x for x in evidence if x.get("direction")=="contradict"]
  status="corroborated_candidate" if len(independent)>=2 and score>=.7 and not contradictions else "conflicted_candidate" if contradictions else "candidate"
  limits=["identity_link_is_not_confirmation","temporal_overlap_requires_review","source_independence_requires_review","human_review_required"]
  lid=new_id("link191"); p={"id":lid,"case":case_id,"left":left_identity_id,"right":right_identity_id,"type":link_type,"from":valid_from,"to":valid_to,"evidence":list(evidence),"score":score,"status":status,"limitations":limits}
  self.db.execute("INSERT INTO temporal_identity_links_191 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(lid,case_id,left_identity_id,right_identity_id,link_type,valid_from,valid_to,dumps(list(evidence)),score,status,dumps(limits),_hash(p)))
  return {**p,"automatic_identity_confirmation":False}
 def timeline(self,*,identity_id:str)->dict[str,Any]:
  rows=self.db.all("SELECT * FROM temporal_identity_facts_191 WHERE identity_id=? ORDER BY valid_from,observed_at",(identity_id,))
  return {"identity_id":identity_id,"facts":[dict(r) for r in rows],"candidate_only":True}
 def ai_next_steps(self,*,identity_id:str,question:str)->dict[str,Any]:
  facts=self.db.all("SELECT * FROM temporal_identity_facts_191 WHERE identity_id=?",(identity_id,)); missing=[]
  types={r["fact_type"] for r in facts}
  for t in ("name","birth","location","organization"): 
   if t not in types:missing.append(t)
  return {"question":question,"known_fact_count":len(facts),"missing_high_value_facts":missing,"recommended_actions":["Primärquelle priorisieren","zeitliche Überschneidungen prüfen","unabhängige Zweitquelle beschaffen"],"ai_output_is_not_fact":True,"human_review_required":True}
 def dashboard(self)->dict[str,Any]:
  n=lambda table:(self.db.one(f"SELECT COUNT(*) AS n FROM {table}") or {"n":0})["n"]
  return {"build":self.BUILD,"browser_bridge_captures":n("browser_bridge_captures_191"),"warc_exports":n("warc_exports_191"),"identities":n("temporal_identities_191"),"facts":n("temporal_identity_facts_191"),"opsec":{"local_processing":True,"external_uploads":False,"cookies_stored":False}}
 def _warc_record(self,typ:str,record_id:str,content_type:str,payload:bytes,*,target:str)->bytes:
  headers=["WARC/1.1",f"WARC-Type: {typ}",f"WARC-Record-ID: <{record_id}>",f"WARC-Target-URI: {target}",f"WARC-Date: {now_ts()}",f"Content-Type: {content_type}",f"Content-Length: {len(payload)}","",""]
  return "\r\n".join(headers).encode()+payload+b"\r\n\r\n"
 def _safe_url(self,url:str)->str:
  p=urllib.parse.urlsplit(url); clean=[(k,"[REDACTED]" if SECRET.search(k) else v) for k,v in urllib.parse.parse_qsl(p.query,keep_blank_values=True)]; return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,urllib.parse.urlencode(clean),""))
 def _redact(self,v:Any)->Any:
  if isinstance(v,Mapping):return {k:("[REDACTED]" if SECRET.search(str(k)) else self._redact(x)) for k,x in v.items()}
  if isinstance(v,list):return [self._redact(x) for x in v]
  return v
 def _event(self,t:str,target:str,payload:Mapping[str,Any]):
  prev=self.db.one("SELECT event_sha256 FROM temporal_identity_events_191 ORDER BY created_at DESC,event_id DESC LIMIT 1"); ph=prev["event_sha256"] if prev else ""; eid=new_id("tie191"); created=now_ts(); eh=_hash({"id":eid,"type":t,"target":target,"payload":payload,"created":created,"prev":ph}); self.db.execute("INSERT INTO temporal_identity_events_191 VALUES(?,?,?,?,?,?,?,?)",(eid,t,target,dumps(payload),created,self.actor,ph,eh))
