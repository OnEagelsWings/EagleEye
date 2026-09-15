from __future__ import annotations

import json, os, platform, re, shutil, subprocess, sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts

class Build209OperationalCollectionOrchestratorService:
    BUILD = "209.0"
    LANGUAGES = ("de","en","he","ar","ru","zh","ja","es","pt","fr","it","hi")

    def __init__(self, db: Any, audit: Any, *, agent_runtime: Any, agents: Any, retrieval: Any, social: Any, runtime: Any, workspace: Any, base_dir: Path, actor: str="system"):
        self.db=db; self.audit=audit; self.agent_runtime=agent_runtime; self.agents=agents; self.retrieval=retrieval; self.social=social; self.runtime=runtime; self.workspace=workspace; self.base_dir=Path(base_dir); self.actor=actor

    def seed_orchestrator(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "ORCHESTRATOR 209 ANLEGEN": raise PermissionError("explicit approval required")
        now=now_ts()
        queues=[("critical",100,2),("interactive",80,6),("standard",50,8),("background",20,4)]
        for name,priority,max_parallel in queues:
            self.db.execute("INSERT OR REPLACE INTO collection_queues_209 VALUES(?,?,?,?,?,?)",(name,priority,max_parallel,"active",now,now))
        policies={"spawn_method":"spawn","network_default":"deny","filesystem_scope":"case_workspace","env_secrets":"redacted","kill_timeout_seconds":30}
        for agent_id in ("planner","source","extraction","verification","hypothesis","synthesis"):
            self.db.execute("INSERT OR REPLACE INTO process_isolation_profiles_209 VALUES(?,?,?,?,?,?,?)",(agent_id,"spawned_process",1,dumps(policies),"active",now,now))
        self._seed_models(now)
        return {"queues":len(queues),"isolated_agents":6,"persistent_service":True,"resume":True,"automatic_external_action":False}

    def _seed_models(self, now: str) -> None:
        # Production-capable routes; model files are installation assets and are never falsely marked bundled.
        routes=[
          ("de,en,fr,it,es,pt","general","local-open-weight-instruct","llama_cpp",8192,"configured_not_bundled"),
          ("he,ar","general","local-semitic-multilingual","llama_cpp",8192,"configured_not_bundled"),
          ("ru","general","local-cyrillic-multilingual","llama_cpp",8192,"configured_not_bundled"),
          ("zh,ja","general","local-cjk-multilingual","llama_cpp",8192,"configured_not_bundled"),
          ("hi","general","local-indic-multilingual","llama_cpp",8192,"configured_not_bundled"),
          ("*","embeddings","local-multilingual-embeddings","sentence_transformers",4096,"configured_not_bundled"),
          ("*","reranking","local-multilingual-reranker","sentence_transformers",4096,"configured_not_bundled"),
        ]
        for langs,task,model_ref,backend,ctx,status in routes:
            rid=f"{task}:{langs}"
            self.db.execute("INSERT OR REPLACE INTO production_model_routes_209 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(rid,langs,task,model_ref,backend,ctx,1,status,None,now,now))

    def detect_gpu(self) -> dict[str, Any]:
        result={"backend":"cpu","devices":[],"cuda_available":False,"rocm_available":False}
        exe=shutil.which("nvidia-smi")
        if exe:
            try:
                out=subprocess.check_output([exe,"--query-gpu=index,name,memory.total,memory.free","--format=csv,noheader,nounits"],text=True,timeout=5)
                for line in out.splitlines():
                    idx,name,total,free=[p.strip() for p in line.split(",",3)]
                    result["devices"].append({"index":int(idx),"name":name,"memory_total_mb":int(total),"memory_free_mb":int(free)})
                result["backend"]="cuda"; result["cuda_available"]=bool(result["devices"])
            except Exception: pass
        now=now_ts()
        self.db.execute("INSERT INTO gpu_inventory_209 VALUES(?,?,?,?,?,?)",(new_id("gpu209"),result["backend"],dumps(result["devices"]),1 if result["cuda_available"] else 0,1 if result["rocm_available"] else 0,now))
        return result

    def register_model(self, *, route_id: str, local_path: str, sha256: str, approved_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"MODEL 209 {route_id} REGISTRIEREN": raise PermissionError("explicit approval required")
        path=Path(local_path).expanduser().resolve()
        if not path.exists(): raise FileNotFoundError(path)
        import hashlib
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest.lower()!=sha256.lower(): raise ValueError("model hash mismatch")
        self.db.execute("UPDATE production_model_routes_209 SET local_path=?,status='validated_local',approved_by=?,updated_at=? WHERE route_id=?",(str(path),approved_by,now_ts(),route_id))
        return {"route_id":route_id,"status":"validated_local","local_path":str(path),"external_uploads":False}

    def route_model(self, *, language: str, task_type: str, required_context: int=4096, gpu_preferred: bool=True) -> dict[str, Any]:
        rows=self.db.all("SELECT * FROM production_model_routes_209 WHERE status IN ('validated_local','configured_not_bundled') ORDER BY CASE WHEN status='validated_local' THEN 0 ELSE 1 END")
        for row in rows:
            langs=set(str(row['languages']).split(','))
            if (language in langs or '*' in langs) and row['task_type'] in (task_type,'general') and int(row['max_context'])>=required_context:
                return {"route_id":row['route_id'],"model_ref":row['model_ref'],"backend":row['backend'],"status":row['status'],"ready":row['status']=='validated_local',"local_only":True,"gpu_preferred":gpu_preferred}
        return {"route_id":None,"model_ref":"rules-only-fallback","status":"fallback","ready":True,"local_only":True}

    def create_collection_run(self, *, case_id: str, question: str, source_ids: Sequence[str], languages: Sequence[str], max_tokens: int, max_cost: float, confirmation: str) -> dict[str, Any]:
        if confirmation != f"COLLECTION RUN 209 {case_id} ANLEGEN": raise PermissionError("explicit approval required")
        run_id=new_id("collect209"); now=now_ts()
        self.db.execute("INSERT INTO collection_runs_209 VALUES(?,?,?,?,?,?,?,?,?,?,?)",(run_id,case_id,question,dumps(list(source_ids)),dumps(list(languages)),"queued",max_tokens,max_cost,0,0.0,now))
        jobs=[]
        stages=[("planner",100),("source",90),("extraction",70),("verification",65),("hypothesis",55),("synthesis",40)]
        for agent,priority in stages:
            jid=new_id("collectjob209")
            self.db.execute("INSERT INTO collection_jobs_209 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(jid,run_id,case_id,agent,priority,"queued",0,3,None,dumps({}),0,0.0,None,now,now))
            jobs.append(jid)
        return {"run_id":run_id,"jobs":jobs,"persistent":True,"resumable":True,"parallel_stages":["source","extraction","verification"]}

    def claim_jobs(self, *, worker_id: str, capabilities: Sequence[str], limit: int=4) -> list[dict[str, Any]]:
        claimed=[]
        caps=set(capabilities)
        for row in self.db.all("SELECT * FROM collection_jobs_209 WHERE status IN ('queued','retry','interrupted') ORDER BY priority DESC,created_at LIMIT 100"):
            if row['agent_type'] not in caps: continue
            self.db.execute("UPDATE collection_jobs_209 SET status='running',worker_id=?,attempt=attempt+1,updated_at=? WHERE job_id=?",(worker_id,now_ts(),row['job_id']))
            claimed.append(dict(row)|{"status":"running","worker_id":worker_id,"attempt":int(row['attempt'])+1})
            if len(claimed)>=limit: break
        return claimed

    def checkpoint(self, *, job_id: str, checkpoint: Mapping[str,Any], tokens_used: int=0, cost: float=0.0) -> dict[str,Any]:
        self.db.execute("UPDATE collection_jobs_209 SET checkpoint_json=?,tokens_used=?,cost=?,updated_at=? WHERE job_id=?",(dumps(dict(checkpoint)),tokens_used,cost,now_ts(),job_id))
        return {"job_id":job_id,"checkpoint":dict(checkpoint)}

    def interrupt_and_resume(self, *, reason: str) -> dict[str,Any]:
        running=self.db.all("SELECT job_id FROM collection_jobs_209 WHERE status='running'")
        self.db.execute("UPDATE collection_jobs_209 SET status='interrupted',error_text=?,worker_id=NULL,updated_at=? WHERE status='running'",(reason[:500],now_ts()))
        return {"interrupted":len(running),"resumable":True}


    def allocate_gpu(self, *, job_id: str, required_memory_mb: int, confirmation: str) -> dict[str, Any]:
        if confirmation != f"GPU 209 {job_id} ZUWEISEN": raise PermissionError("explicit approval required")
        inventory=self.detect_gpu()
        candidates=[d for d in inventory["devices"] if int(d.get("memory_free_mb",0)) >= required_memory_mb]
        if not candidates:
            return {"job_id":job_id,"backend":"cpu","allocated":False,"reason":"no_suitable_gpu"}
        device=max(candidates,key=lambda d:int(d["memory_free_mb"]))
        allocation_id=new_id("gpualloc209")
        self.db.execute("INSERT INTO gpu_allocations_209 VALUES(?,?,?,?,?,?,?)",(allocation_id,job_id,int(device["index"]),required_memory_mb,"reserved",now_ts(),None))
        return {"allocation_id":allocation_id,"job_id":job_id,"backend":"cuda","device_index":int(device["index"]),"allocated":True}

    def execute_isolated(self, *, job_id: str, payload: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if confirmation != f"ISOLATED AGENT 209 {job_id} AUSFUEHREN": raise PermissionError("explicit approval required")
        script=self.base_dir/"tools"/"eagleeye_isolated_agent_209.py"
        if not script.exists(): script=Path(__file__).resolve().parents[4]/"tools"/"eagleeye_isolated_agent_209.py"
        env={k:v for k,v in os.environ.items() if k in {"PATH","SYSTEMROOT","TEMP","TMP","PYTHONUTF8"}}
        proc=subprocess.run([sys.executable,str(script)],input=json.dumps(dict(payload)),text=True,capture_output=True,timeout=30,env=env)
        if proc.returncode != 0: raise RuntimeError(proc.stderr[:500] or "isolated agent failed")
        result=json.loads(proc.stdout or "{}")
        self.db.execute("UPDATE collection_jobs_209 SET status=?,updated_at=? WHERE job_id=?",("blocked" if result.get("status")=='executor_required' else "completed",now_ts(),job_id))
        return result

    def benchmark_dataset(self, *, name: str, language: str, records: Sequence[Mapping[str,Any]], gold_labels: Sequence[Mapping[str,Any]], confirmation: str) -> dict[str,Any]:
        if confirmation != f"GOLD DATASET 209 {name} SPEICHERN": raise PermissionError("explicit approval required")
        if len(records)<10 or len(records)!=len(gold_labels): raise ValueError("gold dataset requires >=10 aligned records")
        did=new_id("gold209")
        self.db.execute("INSERT INTO gold_datasets_209 VALUES(?,?,?,?,?,?,?,?,?)",(did,name,language,len(records),dumps(list(records)),dumps(list(gold_labels)),"reviewed_candidate",now_ts(),None))
        return {"dataset_id":did,"records":len(records),"status":"reviewed_candidate"}

    def benchmark(self, *, dataset_id: str, predictions: Sequence[Mapping[str,Any]], confirmation: str) -> dict[str,Any]:
        if confirmation != f"GOLD BENCHMARK 209 {dataset_id} PRUEFEN": raise PermissionError("explicit approval required")
        ds=self.db.one("SELECT * FROM gold_datasets_209 WHERE dataset_id=?",(dataset_id,))
        if not ds: raise KeyError(dataset_id)
        gold=json.loads(ds['gold_json'])
        if len(predictions)!=len(gold): raise ValueError("prediction length mismatch")
        tp=fp=fn=0
        for p,g in zip(predictions,gold):
            pv=bool(p.get('match')); gv=bool(g.get('match'))
            tp+=int(pv and gv); fp+=int(pv and not gv); fn+=int((not pv) and gv)
        precision=tp/(tp+fp) if tp+fp else 1.0; recall=tp/(tp+fn) if tp+fn else 1.0
        status='passed' if precision>=0.90 and recall>=0.85 else 'failed'
        bid=new_id("goldbench209")
        self.db.execute("INSERT INTO gold_benchmarks_209 VALUES(?,?,?,?,?,?,?,?)",(bid,dataset_id,precision,recall,status,dumps(list(predictions)),now_ts(),None))
        return {"benchmark_id":bid,"precision":precision,"recall":recall,"status":status}

    def service_status(self) -> dict[str,Any]:
        return {"platform":platform.system(),"service_host":"windows_service" if platform.system()=='Windows' else 'portable_worker',"autostart_supported":platform.system()=='Windows',"process_isolation":"spawned_process","gpu":self.detect_gpu(),"runs":self.db.scalar("SELECT COUNT(*) FROM collection_runs_209") or 0,"queued":self.db.scalar("SELECT COUNT(*) FROM collection_jobs_209 WHERE status='queued'") or 0}

    def render_dashboard(self, *, case_id: str) -> str:
        jobs=self.db.all("SELECT * FROM collection_jobs_209 WHERE case_id=? ORDER BY created_at DESC LIMIT 50",(case_id,))
        models=self.db.all("SELECT * FROM production_model_routes_209 ORDER BY task_type,languages")
        rows=''.join(f"<tr><td>{j['agent_type']}</td><td>{j['status']}</td><td>{j['attempt']}</td><td>{j['tokens_used']}</td><td><form method='post' action='/agents209/job'><input type='hidden' name='job_id' value='{j['job_id']}'><button name='action' value='approve'>Freigeben</button><button name='action' value='interrupt'>Unterbrechen</button><button name='action' value='resume'>Fortsetzen</button></form></td></tr>" for j in jobs)
        model_rows=''.join(f"<tr><td>{m['languages']}</td><td>{m['task_type']}</td><td>{m['model_ref']}</td><td>{m['status']}</td></tr>" for m in models)
        return f"""<!doctype html><html><head><meta charset='utf-8'><title>EagleEye Agenten 209</title><style>body{{font-family:Arial;margin:24px}}table{{border-collapse:collapse;width:100%;margin-bottom:24px}}td,th{{border:1px solid #bbb;padding:7px}}.warn{{padding:10px;background:#fff3cd}}</style></head><body><h1>Operational Collection Orchestrator 209</h1><p>Fall: {case_id}</p><div class='warn'>Alle Agentenaktionen bleiben fallisoliert, zitierpflichtig und freigabepflichtig.</div><h2>Agentenjobs</h2><table><tr><th>Agent</th><th>Status</th><th>Versuch</th><th>Tokens</th><th>Steuerung</th></tr>{rows}</table><h2>Produktionsmodellrouten</h2><table><tr><th>Sprachen</th><th>Aufgabe</th><th>Modell</th><th>Status</th></tr>{model_rows}</table><h2>Neuer Lauf</h2><form method='post' action='/agents209/run'><input type='hidden' name='case_id' value='{case_id}'><label>Fragestellung <input name='question' size='80'></label><button>Kontrollierten Lauf anlegen</button></form></body></html>"""
