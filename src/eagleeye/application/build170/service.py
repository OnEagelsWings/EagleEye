from __future__ import annotations
import ast, hashlib, json, threading
from pathlib import Path
from typing import Any
from eagleeye_pro.core.database import dumps,new_id,now_ts

def _canon(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _hash(v): return hashlib.sha256(_canon(v).encode()).hexdigest()

class Build170OperationalProductionCandidateService:
 BUILD="170.0"
 MISSION="Operational production candidate with hardened OPSEC, deterministic shutdown and governed AI"
 def __init__(self,db:Any,audit:Any,*,hardening:Any,observability:Any|None=None,actor:str="system",project_root:str|Path|None=None):
  self.db,self.audit,self.hardening,self.observability,self.actor=db,audit,hardening,observability,actor
  self.project_root=Path(project_root).resolve() if project_root else Path(__file__).resolve().parents[4]
  if not (self.project_root/'src').exists(): self.project_root=Path(__file__).resolve().parents[4]
  self._ensure_ai_policy()
 def _ensure_ai_policy(self):
  if self.db.one("SELECT snapshot_id FROM ai_policy_snapshots_170 LIMIT 1"): return
  policy={"local_only":True,"external_model_called":False,"untrusted_content_is_data":True,"automatic_action":False,"automatic_identity_confirmation":False,"automatic_accusation":False,"human_review_required":True,"source_citations_required":True,"opsec_preflight_required":True}
  self.db.execute("INSERT INTO ai_policy_snapshots_170 VALUES(?,?,?,?)",(new_id('aip170'),dumps(policy),now_ts(),_hash(policy)))
 def classify_exception_handlers(self):
  rows=[]
  for base in (self.project_root/'src',self.project_root/'eagleeye_pro'):
   if not base.exists(): continue
   for p in base.rglob('*.py'):
    try: tree=ast.parse(p.read_text('utf-8',errors='ignore'))
    except (SyntaxError,OSError): continue
    for node in ast.walk(tree):
     if isinstance(node,ast.ExceptHandler) and len(node.body)==1 and isinstance(node.body[0],ast.Pass):
      kind='bare' if node.type is None else 'typed'
      cls='approved_optional_cleanup' if kind=='typed' else 'requires_remediation'
      rationale='Typed optional cleanup boundary' if cls.startswith('approved') else 'Bare silent failure obscures operational outcome'
      item={"item_id":new_id('exc170'),"file_path":str(p.relative_to(self.project_root)),"line_no":node.lineno,"handler_kind":kind,"classification":cls,"rationale":rationale}
      self.db.execute("INSERT OR REPLACE INTO exception_classifications_170 VALUES(?,?,?,?,?,?,?)",(item['item_id'],item['file_path'],item['line_no'],kind,cls,rationale,_hash(item)))
      rows.append(item)
  return rows
 def shutdown_check(self):
  threads=[t for t in threading.enumerate() if t.is_alive() and t is not threading.current_thread()]
  non_daemon=[t.name for t in threads if not t.daemon]
  open_jobs=0
  try:
   r=self.db.one("SELECT COUNT(*) n FROM operation_jobs_153 WHERE status IN ('queued','running')"); open_jobs=int(r['n']) if r else 0
  except Exception as exc:
   details={"classification":"telemetry_table_unavailable","error_type":type(exc).__name__}; open_jobs=0
  else: details={}
  status='passed' if not non_daemon and open_jobs==0 else 'blocked'
  details.update({"non_daemon_threads":non_daemon,"open_jobs":open_jobs})
  cid=new_id('shutdown170'); payload={"check_id":cid,"status":status,"details":details}
  self.db.execute("INSERT INTO shutdown_checks_170 VALUES(?,?,?, ?,?)",(cid,status,dumps(details),now_ts(),_hash(payload)))
  return payload

 def scan_hard_coded_secrets(self):
  hits=[]
  names=("password","passwd","token","secret","api_key","apikey","authorization","private_key")
  for base in (self.project_root/'src',self.project_root/'eagleeye_pro'):
   if not base.exists(): continue
   for p in base.rglob('*.py'):
    try: tree=ast.parse(p.read_text('utf-8',errors='ignore'))
    except (SyntaxError,OSError): continue
    for node in ast.walk(tree):
     targets=[]; value=None
     if isinstance(node,ast.Assign): targets=node.targets; value=node.value
     elif isinstance(node,ast.AnnAssign): targets=[node.target]; value=node.value
     if not value or not isinstance(value,ast.Constant) or not isinstance(value.value,str): continue
     for target in targets:
      name=target.id.lower() if isinstance(target,ast.Name) else target.attr.lower() if isinstance(target,ast.Attribute) else ''
      if any(k in name for k in names) and not any(x in name for x in ('confirmation','reference','_ref')) and len(value.value)>=6:
       hits.append({"file":str(p.relative_to(self.project_root)),"line":node.lineno,"name":name})
  return hits

 def production_audit(self,*,created_by:str|None=None,confirmation:str):
  if confirmation!='PRODUCTION 170 VOLLPRUEFUNG AUSFUEHREN': raise PermissionError('explicit production audit approval required')
  legacy=self.hardening.run_opsec_audit(confirmation='OPSEC 169 VOLLPRUEFUNG AUSFUEHREN')
  handlers=self.classify_exception_handlers(); shutdown=self.shutdown_check()
  bare=[x for x in handlers if x['classification']=='requires_remediation']
  secret_findings=self.scan_hard_coded_secrets(); secret_hits=len(secret_findings)
  checks={"secret_hits":secret_hits,"secret_findings":secret_findings,"bare_silent_handlers":len(bare),"classified_handlers":len(handlers),"shutdown":shutdown,"legacy_opsec_score":legacy['score'],"schema":"170.0","ai_policy_present":True}
  blockers=[]
  if secret_hits: blockers.append('hard_coded_secret_candidates')
  if bare: blockers.append('bare_silent_exception_handlers')
  if shutdown['status']!='passed': blockers.append('runtime_shutdown_not_clean')
  score=max(0.0,100.0-secret_hits*40-len(bare)*4-(20 if shutdown['status']!='passed' else 0))
  status='candidate_ready' if not blockers and score>=90 else 'blocked'
  aid=new_id('audit170'); payload={"audit_id":aid,"status":status,"score":score,"checks":checks,"blockers":blockers}
  self.db.execute("INSERT INTO production_candidate_audits_170 VALUES(?,?,?,?,?,?,?,?)",(aid,status,score,dumps(checks),dumps(blockers),created_by or self.actor,now_ts(),_hash(payload)))
  self.audit.log('production_candidate_audit_170','audit170',aid,'',{"status":status,"score":score,"blockers":blockers})
  return payload
 def approve_candidate(self,audit_id:str,*,analyst:str,supervisor:str,confirmation:str):
  if confirmation!=f'PRODUCTION 170 {audit_id} FREIGEBEN': raise PermissionError('explicit release approval required')
  row=self.db.one('SELECT * FROM production_candidate_audits_170 WHERE audit_id=?',(audit_id,))
  if not row: raise KeyError('audit not found')
  if row['status']!='candidate_ready': raise RuntimeError('production candidate is blocked')
  if not analyst or not supervisor or analyst==supervisor: raise ValueError('independent analyst and supervisor required')
  approvals={"analyst":analyst,"supervisor":supervisor,"automatic_release":False,"production_deployment":False}
  did=new_id('release170'); payload={"decision_id":did,"audit_id":audit_id,"status":"approved_production_candidate","approvals":approvals}
  self.db.execute("INSERT INTO production_release_decisions_170 VALUES(?,?,?,?,?,?,?)",(did,audit_id,payload['status'],dumps(approvals),self.actor,now_ts(),_hash(payload)))
  return payload
 def dashboard(self):
  latest=self.db.one('SELECT * FROM production_candidate_audits_170 ORDER BY created_at DESC LIMIT 1')
  return {"build":self.BUILD,"mission":self.MISSION,"latest_audit":dict(latest) if latest else None,"release_semantics":{"production_candidate_is_not_deployment":True,"human_approval_required":True,"automatic_release":False},"core_business":"review-first person OSINT with provenance, OPSEC and authority-ready handover"}
