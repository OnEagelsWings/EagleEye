from __future__ import annotations

import hashlib
import json
from typing import Any

from eagleeye.kernel.contracts import AgentResult, AgentTask


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class KernelTaskRepository343:
    """Persistence adapter. This is the only new Build-343 kernel component that knows the DB handle."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def create_task(self, task: AgentTask) -> dict:
        payload = task.to_dict(); digest = _sha(payload)
        self.db.execute("""INSERT INTO phase15_agent_tasks_343
            (task_id,case_id,agent_role,action_class,requested_gateway,approval_state,contract_version,task_json,record_hash,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""", (
            task.task_id, task.case_id, task.agent_role.value, task.action_class.value, task.requested_gateway.value,
            task.approval_state.value, task.contract_version, _canon(payload), digest, task.created_at,
        ))
        return payload | {"record_hash": digest}

    def get_task(self, task_id: str) -> AgentTask | None:
        row = self.db.one("SELECT task_json FROM phase15_agent_tasks_343 WHERE task_id=?", (task_id,))
        if not row: return None
        return AgentTask.from_dict(json.loads(row["task_json"]))

    def append_result(self, result: AgentResult) -> dict:
        payload = result.to_dict(); digest = _sha(payload)
        self.db.execute("""INSERT INTO phase15_agent_results_343
            (result_id,task_id,status,gateway_used,contract_version,result_json,record_hash,created_at) VALUES(?,?,?,?,?,?,?,?)""", (
            result.result_id, result.task_id, result.status.value, result.gateway_used.value, result.contract_version,
            _canon(payload), digest, result.created_at,
        ))
        return payload | {"record_hash": digest}

    def list_tasks(self, *, case_id: str | None = None, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        if case_id:
            rows = self.db.all("SELECT task_json,record_hash FROM phase15_agent_tasks_343 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, limit))
        else:
            rows = self.db.all("SELECT task_json,record_hash FROM phase15_agent_tasks_343 ORDER BY created_at DESC LIMIT ?", (limit,))
        return [json.loads(row["task_json"]) | {"record_hash": row["record_hash"]} for row in rows]

    def list_results(self, task_id: str) -> list[dict]:
        rows = self.db.all("SELECT result_json,record_hash FROM phase15_agent_results_343 WHERE task_id=? ORDER BY created_at,result_id", (task_id,))
        return [json.loads(row["result_json"]) | {"record_hash": row["record_hash"]} for row in rows]
