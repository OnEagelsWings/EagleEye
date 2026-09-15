from __future__ import annotations
import hashlib,json
from typing import Any
from eagleeye.kernel.contracts import AgentResult,AgentTask
def _canon(v:Any)->str:return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def _sha(v:Any)->str:return hashlib.sha256(_canon(v).encode()).hexdigest()
class KernelTaskRepository344:
    def __init__(self,db:Any): self.db=db
    def create_task(self,task:AgentTask)->dict:
        p=task.to_dict(); d=_sha(p); self.db.execute("INSERT INTO phase15_agent_tasks(task_id,case_id,agent_role,action_class,requested_gateway,approval_state,contract_version,task_json,record_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(task.task_id,task.case_id,task.agent_role.value,task.action_class.value,task.requested_gateway.value,task.approval_state.value,task.contract_version,_canon(p),d,task.created_at)); return p|{"record_hash":d}
    def get_task(self,task_id:str):
        r=self.db.one("SELECT task_json FROM phase15_agent_tasks WHERE task_id=?",(task_id,)); return AgentTask.from_dict(json.loads(r["task_json"])) if r else None
    def append_result(self,result:AgentResult)->dict:
        p=result.to_dict(); d=_sha(p); self.db.execute("INSERT INTO phase15_agent_results(result_id,task_id,status,gateway_used,contract_version,result_json,record_hash,created_at) VALUES(?,?,?,?,?,?,?,?)",(result.result_id,result.task_id,result.status.value,result.gateway_used.value,result.contract_version,_canon(p),d,result.created_at)); return p|{"record_hash":d}
    def list_tasks(self,*,case_id=None,limit=100):
        limit=max(1,min(int(limit),500)); rows=self.db.all("SELECT task_json,record_hash FROM phase15_agent_tasks WHERE case_id=? ORDER BY created_at DESC LIMIT ?",(case_id,limit)) if case_id else self.db.all("SELECT task_json,record_hash FROM phase15_agent_tasks ORDER BY created_at DESC LIMIT ?",(limit,)); return [json.loads(r["task_json"])|{"record_hash":r["record_hash"]} for r in rows]
    def list_results(self,task_id:str):
        rows=self.db.all("SELECT result_json,record_hash FROM phase15_agent_results WHERE task_id=? ORDER BY created_at,result_id",(task_id,)); return [json.loads(r["result_json"])|{"record_hash":r["record_hash"]} for r in rows]
