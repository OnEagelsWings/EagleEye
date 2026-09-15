from __future__ import annotations
import hashlib, json, re, urllib.parse
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence
from eagleeye_pro.core.database import dumps, new_id, now_ts

def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
SECRET=re.compile(r'(?i)(token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key)')
INJECTION=("ignore previous instructions","reveal system prompt","bypass policy","developer message","execute this command")

class Build190EvidenceCaptureReplayService:
 BUILD="190.0"
 PROFILES=(
  {"source_id":"warc_iso_28500","title":"WARC ISO 28500 Capture","family":"preservation","access":"local_format","endpoint":"local://warc"},
  {"source_id":"ietf_memento","title":"IETF Memento TimeGate","family":"web_history","access":"http_standard","endpoint":"https://timetravel.mementoweb.org"},
  {"source_id":"internet_archive_cdx_190","title":"Internet Archive CDX / Replay","family":"web_archive","access":"rest_json","endpoint":"https://web.archive.org/cdx/search/cdx"},
  {"source_id":"common_crawl_index","title":"Common Crawl Index","family":"web_archive","access":"rest_json","endpoint":"https://index.commoncrawl.org"},
  {"source_id":"c2pa_capture_provenance","title":"C2PA Capture Provenance","family":"provenance","access":"local_validator","endpoint":"local://c2pa"},
  {"source_id":"browser_direct_capture","title":"Firefox Direct Evidence Capture","family":"live_web","access":"local_browser_bridge","endpoint":"local://firefox"},
 )
 def __init__(self,db:Any,audit:Any,*,global_sources:Any,source_ops:Any,authenticity:Any,actor:str="system"):
  self.db,self.audit,self.global_sources,self.source_ops,self.authenticity,self.actor=db,audit,global_sources,source_ops,authenticity,actor
 def seed_profiles(self,*,confirmation:str)->dict[str,Any]:
  if confirmation!="CAPTURE SOURCES 190 ANLEGEN":raise PermissionError("explicit approval required")
  for p in self.PROFILES:
   op={"local_processing":True,"store_cookies":False,"store_authorization":False,"external_uploads":False,"candidate_only":True}
   self.db.execute("INSERT OR REPLACE INTO capture_source_profiles_190 VALUES(?,?,?,?,?,?,?,?,?)",(p["source_id"],p["title"],p["family"],p["access"],p["endpoint"],"READY",dumps(op),now_ts(),_hash({**p,"opsec":op})))
  return {"created":len(self.PROFILES),"automatic_external_upload":False}
 def capture(self,*,case_id:str,source_id:str,source_url:str,final_url:str,http_status:int,content_type:str,headers:Mapping[str,Any],text_content:str,html_content:str="",screenshot_ref:str="",media_refs:Sequence[str]=(),request_meta:Mapping[str,Any]|None=None,confirmation:str)->dict[str,Any]:
  if confirmation!=f"CAPTURE 190 {case_id} SPEICHERN":raise PermissionError("explicit approval required")
  self._profile(source_id); clean_headers={k:("[REDACTED]" if SECRET.search(k) else str(v)) for k,v in headers.items()}
  req=self._redact(dict(request_meta or {})); safe_url=self._safe_url(source_url); safe_final=self._safe_url(final_url)
  previous=self.db.one("SELECT capture_id,text_content FROM evidence_captures_190 WHERE case_id=? AND source_url=? ORDER BY captured_at DESC LIMIT 1",(case_id,safe_url))
  cid=new_id("capture190"); content_hash=hashlib.sha256((text_content+"\n"+html_content).encode()).hexdigest(); response_hash=_hash({"status":http_status,"headers":clean_headers,"content":content_hash})
  op={"cookies_stored":False,"authorization_stored":False,"local_processing":True,"external_uploads":False,"untrusted_content_is_data":True}
  payload={"capture_id":cid,"case_id":case_id,"source_id":source_id,"source_url":safe_url,"final_url":safe_final,"captured_at":now_ts(),"http_status":http_status,"content_type":content_type,"headers":clean_headers,"text":text_content,"html":html_content,"screenshot_ref":screenshot_ref,"media_refs":list(media_refs),"request_meta":req,"response_sha256":response_hash,"content_sha256":content_hash,"previous_capture_id":previous["capture_id"] if previous else "","review_status":"captured_candidate","opsec":op}
  self.db.execute("INSERT INTO evidence_captures_190 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(cid,case_id,source_id,safe_url,safe_final,payload["captured_at"],http_status,content_type,dumps(clean_headers),text_content,html_content,screenshot_ref,dumps(list(media_refs)),dumps(req),response_hash,content_hash,payload["previous_capture_id"],"captured_candidate",dumps(op),_hash(payload)))
  diff=None
  if previous: diff=self.compare(case_id=case_id,older_capture_id=previous["capture_id"],newer_capture_id=cid,confirmation=f"CAPTURE DIFF 190 {case_id} ERSTELLEN")
  self._event("capture_created",cid,{"case_id":case_id,"source_id":source_id,"content_sha256":content_hash})
  return {"capture_id":cid,"content_sha256":content_hash,"response_sha256":response_hash,"previous_capture_id":payload["previous_capture_id"],"diff":diff,"review_required":True,"opsec":op}
 def compare(self,*,case_id:str,older_capture_id:str,newer_capture_id:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f"CAPTURE DIFF 190 {case_id} ERSTELLEN":raise PermissionError("explicit approval required")
  old=self._capture(older_capture_id); new=self._capture(newer_capture_id); a=old["text_content"].splitlines(); b=new["text_content"].splitlines(); aset,bset=set(a),set(b)
  added=[x for x in b if x not in aset][:200]; removed=[x for x in a if x not in bset][:200]; similarity=SequenceMatcher(None,old["text_content"],new["text_content"]).ratio(); ctype="unchanged" if similarity==1 else "changed"
  did=new_id("diff190"); p={"id":did,"case_id":case_id,"older":older_capture_id,"newer":newer_capture_id,"added":added,"removed":removed,"similarity":similarity}
  self.db.execute("INSERT INTO evidence_diffs_190 VALUES(?,?,?,?,?,?,?,?,?,?)",(did,case_id,older_capture_id,newer_capture_id,ctype,dumps(added),dumps(removed),similarity,now_ts(),_hash(p)))
  return {"diff_id":did,"change_type":ctype,"added":added,"removed":removed,"similarity":similarity}
 def create_replay(self,*,case_id:str,capture_id:str,created_by:str,confirmation:str)->dict[str,Any]:
  if confirmation!=f"REPLAY 190 {capture_id} ERSTELLEN":raise PermissionError("explicit approval required")
  c=self._capture(capture_id); manifest={"format":"EagleEye-Replay-1","capture_id":capture_id,"case_id":case_id,"source_url":c["source_url"],"final_url":c["final_url"],"captured_at":c["captured_at"],"content_sha256":c["content_sha256"],"response_sha256":c["response_sha256"],"screenshot_ref":c["screenshot_ref"],"review_required":True,"not_live_content":True}
  rid=new_id("replay190"); ph=_hash(manifest); self.db.execute("INSERT INTO replay_packages_190 VALUES(?,?,?,?,?,?,?,?)",(rid,case_id,capture_id,dumps(manifest),now_ts(),created_by,ph,1)); return {"replay_id":rid,"manifest":manifest,"package_sha256":ph}
 def ai_assess(self,*,case_id:str,capture_id:str,question:str,source_refs:Sequence[str],confirmation:str)->dict[str,Any]:
  if confirmation!=f"AI CAPTURE 190 {capture_id} PRUEFEN":raise PermissionError("explicit approval required")
  c=self._capture(capture_id); text=c["text_content"]; injection=[x for x in INJECTION if x in text.lower()]; findings=[]
  if injection: findings.append({"type":"prompt_injection_candidate","signals":injection,"executed":False})
  if not source_refs: findings.append({"type":"missing_corroboration","message":"independent source required"})
  if c["previous_capture_id"]: findings.append({"type":"version_history_available","previous_capture_id":c["previous_capture_id"]})
  confidence=min(.85,.25+.15*len(source_refs)); status="needs_review" if findings else "inconclusive"
  limits=["ai_output_is_not_fact","captured_page_may_be_false_or_out_of_context","source_independence_requires_review","human_review_required","untrusted_content_is_data"]
  aid=new_id("aicap190"); p={"id":aid,"case_id":case_id,"capture_id":capture_id,"question":question,"findings":findings,"source_refs":list(source_refs),"confidence":confidence,"status":status,"limitations":limits}
  self.db.execute("INSERT INTO ai_capture_assessments_190 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(aid,case_id,capture_id,question,dumps(findings),dumps(list(source_refs)),confidence,status,dumps(limits),now_ts(),_hash(p)))
  return {**p,"automatic_identity_confirmation":False,"automatic_accusation":False}
 def investigation_next_step(self,*,case_id:str,capture_id:str)->dict[str,Any]:
  c=self._capture(capture_id); steps=[]
  if not c["screenshot_ref"]:steps.append("Sichtbaren Screenshot ergänzen")
  if not c["previous_capture_id"]:steps.append("Frühere Version über Memento/CDX suchen")
  steps.extend(["Primärquelle oder unabhängige Zweitquelle prüfen","Treffer in Schritt 3 – Prüfen übernehmen"])
  return {"case_id":case_id,"workflow_position":"2_research_sources","next_global_step":"3_verify_candidates","recommended_steps":steps,"candidate_only":True}
 def dashboard(self)->dict[str,Any]:
  return {"build":self.BUILD,"profiles":(self.db.one("SELECT COUNT(*) AS n FROM capture_source_profiles_190") or {"n":0})["n"],"captures":(self.db.one("SELECT COUNT(*) AS n FROM evidence_captures_190") or {"n":0})["n"],"replays":(self.db.one("SELECT COUNT(*) AS n FROM replay_packages_190") or {"n":0})["n"],"local_processing":True,"external_uploads":False}
 def _safe_url(self,url:str)->str:
  p=urllib.parse.urlsplit(url); q=urllib.parse.parse_qsl(p.query,keep_blank_values=True); clean=[(k,"[REDACTED]" if SECRET.search(k) else v) for k,v in q]; return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,urllib.parse.urlencode(clean),""))
 def _redact(self,v:Any)->Any:
  if isinstance(v,Mapping):return {k:("[REDACTED]" if SECRET.search(str(k)) else self._redact(x)) for k,x in v.items()}
  if isinstance(v,list):return [self._redact(x) for x in v]
  return v
 def _profile(self,sid:str):
  r=self.db.one("SELECT * FROM capture_source_profiles_190 WHERE source_id=?",(sid,));
  if r is None:raise KeyError(sid)
  return r
 def _capture(self,cid:str):
  r=self.db.one("SELECT * FROM evidence_captures_190 WHERE capture_id=?",(cid,));
  if r is None:raise KeyError(cid)
  return r
 def _event(self,t:str,target:str,payload:Mapping[str,Any]):
  prev=self.db.one("SELECT event_sha256 FROM capture_events_190 ORDER BY created_at DESC,event_id DESC LIMIT 1"); ph=prev["event_sha256"] if prev else ""; eid=new_id("ce190"); created=now_ts(); eh=_hash({"id":eid,"type":t,"target":target,"payload":payload,"created":created,"prev":ph}); self.db.execute("INSERT INTO capture_events_190 VALUES(?,?,?,?,?,?,?,?)",(eid,t,target,dumps(payload),created,self.actor,ph,eh))
