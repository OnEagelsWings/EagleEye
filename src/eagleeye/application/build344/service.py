from __future__ import annotations
import ast,hashlib,html,json,re,uuid
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from eagleeye.application.kernel.use_cases import InvestigationKernelUseCases
from eagleeye.infrastructure.schema_v1.schema import SCHEMA_BASELINE
from eagleeye.kernel.contracts import CONTRACT_VERSION
DIMENSIONS=("implemented","integrated","tested","benchmarked","externally_validated")
_VALID_ONION=re.compile(r"^[a-z2-7]{56}\.onion$")
def _now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str)
def _sha(v):return hashlib.sha256(_canon(v).encode()).hexdigest()
def _read_json(p):
 try:
  d=json.loads(Path(p).read_text(encoding='utf-8'));return d if isinstance(d,dict) else {}
 except Exception:return {}
class Build344SchemaBaselineService:
 BUILD='344.0'
 def __init__(self,db,audit,*,use_cases:InvestigationKernelUseCases,repository,install_dir,base_dir,actor='local-analyst'):
  self.db=db;self.audit=audit;self.use_cases=use_cases;self.repository=repository;self.install_dir=Path(install_dir);self.base_dir=Path(base_dir);self.actor=actor;self._root=self.install_dir
 def _fingerprint_paths(self):return ('src/eagleeye/infrastructure/schema_v1/schema.py','src/eagleeye/infrastructure/schema_v1/migration.py','src/eagleeye/infrastructure/build344/repository.py','src/eagleeye/application/build344/service.py','src/eagleeye/interfaces/web/app344.py','eagleeye_pro/core/app_context.py','src/eagleeye/interfaces/web/server.py','eagleeye_pro/version.py','pyproject.toml','EAGLEEYE_PRO_344_0.py','EAGLEEYE_ACCEPTANCE_BUILD_344_0.py','tests/test_build344.py')
 def code_fingerprint(self):
  h=hashlib.sha256()
  for rel in self._fingerprint_paths():
   p=self._root/rel;h.update(rel.encode());h.update(b'\0');h.update(p.read_bytes() if p.is_file() else b'<missing>');h.update(b'\0')
  return h.hexdigest()
 def _test_evidence(self):
  d=_read_json(self._root/'BUILD_344_TEST_EVIDENCE.json');return d if d.get('build')==self.BUILD and d.get('result')=='pass' and d.get('code_fingerprint')==self.code_fingerprint() and isinstance(d.get('probes'),dict) else {}
 def _probe(self,n):return self._test_evidence().get('probes',{}).get(n)=='pass'
 def active_gate_literal_true_lines(self):
  tree=ast.parse(Path(__file__).read_text(encoding='utf-8'))
  for n in ast.walk(tree):
   if isinstance(n,ast.FunctionDef) and n.name=='qualified_gate':return sorted({int(c.lineno) for c in ast.walk(n) if isinstance(c,ast.Constant) and c.value is True and hasattr(c,'lineno')})
  return []
 def schema_metrics(self):
  o={}
  for k in ('table','index','trigger','view'):o[k]=int(self.db.one("SELECT COUNT(*) c FROM sqlite_master WHERE type=? AND name NOT LIKE 'sqlite_%'",(k,))['c'])
  pc=int(self.db.one('PRAGMA page_count')['page_count']);ps=int(self.db.one('PRAGMA page_size')['page_size']);ir=self.db.one('PRAGMA integrity_check') or {};integrity=next(iter(ir.values()),'unknown');logical=pc*ps
  return {**o,'logical_bytes':logical,'file_bytes':self.db.path.stat().st_size if self.db.path.exists() else 0,'integrity_check':integrity,'targets':{'tables_lt':150,'indexes_lt':300,'file_bytes_lt':5*1024*1024},'within_gate':o['table']<150 and o['index']<300 and logical<5*1024*1024}
 def schema_policy(self):
  r=self.db.one("SELECT value_json FROM phase15_schema_meta WHERE schema_key='baseline_policy'");return json.loads(r['value_json']) if r else {}
 def migration_runs(self,limit=20):return self.db.all("SELECT migration_id,source_build,target_schema,source_path,source_sha256,backup_path,backup_sha256,report_path,status,started_at,completed_at FROM phase15_migration_runs ORDER BY started_at DESC LIMIT ?",(max(1,min(int(limit),100)),))
 def register_darknet_source(self,*,onion_host,display_name,source_class='other',jurisdiction='unknown',allowed_use='public_or_authorized_read_only',risk_class='high',actor=None):
  host=str(onion_host or '').strip().lower()
  if host.startswith(('http://','https://')):host=host.split('//',1)[1].split('/',1)[0]
  if not _VALID_ONION.fullmatch(host):raise ValueError('Only syntactically valid v3 .onion hosts may be registered')
  if allowed_use!='public_or_authorized_read_only':raise ValueError('Build 344 permits only public/authorized read-only source governance')
  sid='dsrc_'+uuid.uuid4().hex[:20];now=_now();prov={'registered_in':'344.0','network_execution':False,'opsec_gate_required':True};body={'source_id':sid,'source_kind':'darknet_onion','locator':host,'display_name':str(display_name).strip()[:300],'source_class':str(source_class or 'other').strip().lower()[:80],'jurisdiction':str(jurisdiction or 'unknown')[:80],'allowed_use':allowed_use,'review_status':'pending','risk_class':str(risk_class or 'high')[:40],'provenance_json':_canon(prov),'created_by':actor or self.actor,'created_at':now,'updated_at':now};dig=_sha(body);self.db.execute("INSERT INTO phase15_sources(source_id,source_kind,locator,display_name,source_class,jurisdiction,allowed_use,review_status,risk_class,provenance_json,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(body['source_id'],body['source_kind'],body['locator'],body['display_name'],body['source_class'],body['jurisdiction'],body['allowed_use'],body['review_status'],body['risk_class'],body['provenance_json'],body['created_by'],body['created_at'],body['updated_at'],dig));return body|{'record_hash':dig}
 def review_darknet_source(self,source_id,*,decision,rationale,reviewer=None):
  row=self.db.one("SELECT * FROM phase15_sources WHERE source_id=? AND source_kind='darknet_onion'",(source_id,))
  if not row:raise KeyError(source_id)
  d=str(decision).strip().lower();mapping={'approve_read_only':'approved_read_only','quarantine':'quarantined','reject':'rejected'}
  if d not in mapping:raise ValueError('invalid decision')
  now=_now();eid='dsrev_'+uuid.uuid4().hex[:20];body={'event_id':eid,'source_id':source_id,'decision':d,'rationale':str(rationale).strip()[:2000],'reviewer':reviewer or self.actor,'created_at':now};dig=_sha(body)
  with self.db.transaction(immediate=True):self.db.execute("UPDATE phase15_sources SET review_status=?,updated_at=? WHERE source_id=?",(mapping[d],now,source_id));self.db.execute("INSERT INTO phase15_source_review_events(event_id,source_id,decision,rationale,reviewer,created_at,record_hash) VALUES(?,?,?,?,?,?,?)",(eid,source_id,d,body['rationale'],body['reviewer'],now,dig))
  return body|{'review_status':mapping[d],'record_hash':dig}
 def create_local_analysis_task(self,*,case_id,objective,context_refs=None,actor=None):return self.use_cases.submit_local_analysis(case_id=case_id,actor=actor or self.actor,objective=objective,context_refs=context_refs)
 def create_darknet_research_task(self,*,case_id,query,source_ids,human_approved,actor=None,search_run_id=None):
  ids=list(dict.fromkeys(str(x) for x in source_ids if str(x).strip()))
  if not ids:raise ValueError('source_ids required')
  ph=','.join('?' for _ in ids);rows=self.db.all(f"SELECT source_id,review_status FROM phase15_sources WHERE source_id IN ({ph}) AND source_kind='darknet_onion'",ids)
  if len(rows)!=len(ids) or any(r['review_status']!='approved_read_only' for r in rows):raise PermissionError('All darknet sources must be human-reviewed and approved_read_only')
  plan={'case_id':case_id,'query':str(query).strip(),'source_ids':sorted(ids),'network_execution':False,'schema':SCHEMA_BASELINE};pid='dplan_'+_sha(plan)[:20];task=self.use_cases.submit_darknet_research(case_id=case_id,actor=actor or self.actor,query=str(query).strip(),source_ids=ids,source_plan_id=pid,human_approved=human_approved,search_run_id=search_run_id);return task|{'source_plan_id':pid,'source_plan_hash':_sha(plan),'network_execution':False}
 def evaluate_task(self,task_id):return self.use_cases.evaluate(task_id)
 def dispatch_task(self,task_id):return self.use_cases.dispatch(task_id)
 def tasks(self,*,case_id=None,limit=100):return self.repository.list_tasks(case_id=case_id,limit=limit)
 def version_status(self):
  vt=(self._root/'eagleeye_pro/version.py').read_text();pt=(self._root/'pyproject.toml').read_text();rv=re.search(r'^BUILD\s*=\s*["\']([^"\']+)',vt,re.M);sv=re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)',vt,re.M);pv=re.search(r'^version\s*=\s*["\']([^"\']+)',pt,re.M);r=rv.group(1) if rv else 'unknown';s=sv.group(1) if sv else 'unknown';p=pv.group(1) if pv else 'unknown';return {'runtime_build':r,'schema_version':s,'package_version':p,'coherent':r==s==self.BUILD and p=='344.0.0'}
 @staticmethod
 def _maturity(st):
  last='declared'
  for k in DIMENSIONS:
   if st[k]:last=k
   else:break
  return last
 def capabilities(self):
  m=self.schema_metrics();v=self.version_status();specs=[('schema_baseline_v1','Consolidated Schema Baseline v1','schema',m['within_gate'],m['within_gate'],'schema_gate',True),('migration_backup_restore_344','Verified migration + backup/rollback tooling','migration',True,True,'migration',True),('kernel_repository_v1_344','Agent repository on build-independent schema','kernel',True,True,'repository',True),('darknet_governance_v1_344','Darknet source governance on consolidated schema','darknet',True,True,'darknet',True),('canonical_versioning_344','Canonical 344 version contract','packaging',v['coherent'],v['coherent'],'version',True),('search_session_capsule','Per-search Search Session Capsule','opsec',False,False,'future',False),('opsec_intelligence_v2','OPSEC Intelligence v2 runtime gate','opsec',False,False,'future',False)];rows=[];fp=self.code_fingerprint()
  for key,name,cat,impl,integ,probe,baseline in specs:
   tested=bool(integ and self._probe(probe));st={'implemented':bool(impl),'integrated':bool(impl and integ),'tested':tested,'benchmarked':False,'externally_validated':False};rows.append({'capability_key':key,'display_name':name,'category':cat,**st,'maturity':self._maturity(st),'required_for_baseline':baseline,'required_for_production':True,'code_fingerprint':fp})
  return rows
 def qualified_gate(self):
  rows=self.capabilities();base=[r for r in rows if r['required_for_baseline']];bt=bool(base) and all(r['tested'] for r in base);sg=self.schema_metrics()['within_gate'];ba=bt and sg;prod=[r for r in rows if r['required_for_production']];pr=bool(prod) and all(r['externally_validated'] for r in prod);return {'build':self.BUILD,'phase':'15','gate_authority':'build344_schema_baseline_evidence_gate','build_acceptance_ready':ba,'production_release_ready':pr,'release_ready':pr,'baseline_tested':bt,'schema_gate':sg,'active_gate_literal_true_lines':self.active_gate_literal_true_lines(),'rule':'Fresh installs use only the canonical core plus Schema Baseline v1; legacy build schemas never auto-bootstrap.'}
 def dashboard(self):return {'build':self.BUILD,'phase':'15','name':'Schema Baseline v1 + Safe Migration','schema':self.schema_metrics(),'policy':self.schema_policy(),'gate':self.qualified_gate(),'version':self.version_status(),'capabilities':self.capabilities(),'migration_runs':self.migration_runs(),'darknet_runtime_execution':False,'contract_version':CONTRACT_VERSION}
 def render_workspace_panel(self,*,case_id,csrf,section):
  m=self.schema_metrics();g=self.qualified_gate();return f'<section class="card" id="phase15-build344"><h2>Phase 15 · Build 344 · Schema Baseline v1</h2><p><b>Schema:</b> {m["table"]} Tabellen · {m["index"]} Indizes · {m["trigger"]} Trigger · {m["logical_bytes"]//1024} KiB</p><p><b>Build-Abnahme:</b> {"bereit" if g["build_acceptance_ready"] else "unvollständig"} · <b>Produktionsfreigabe:</b> nicht qualifiziert</p><p>Der aktive Phase-15-Kern verwendet keine per-Build-Schemata mehr. Legacy-Daten werden nur über verifizierte Migration mit vollständigem Rollback-Artefakt übernommen.</p><p>Darknet-Quellen bleiben read-only, reviewpflichtig und ohne Runtime-Netzwerkzugriff bis Search Session Capsule und OPSEC v2.</p><p><small>Maschinenlesbar: <code>/api/build344</code></small></p></section>'
