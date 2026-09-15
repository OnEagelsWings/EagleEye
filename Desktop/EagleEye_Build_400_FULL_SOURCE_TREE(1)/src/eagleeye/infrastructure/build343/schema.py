from __future__ import annotations

from typing import Any


def ensure_build343_schema(db: Any) -> None:
    # Temporary Build-343 persistence. Build 344 migrates this into Schema Baseline v1.
    db.execute("""CREATE TABLE IF NOT EXISTS phase15_agent_tasks_343(
        task_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, agent_role TEXT NOT NULL, action_class TEXT NOT NULL,
        requested_gateway TEXT NOT NULL, approval_state TEXT NOT NULL, contract_version TEXT NOT NULL,
        task_json TEXT NOT NULL, record_hash TEXT NOT NULL, created_at TEXT NOT NULL
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_phase15_agent_tasks343_case ON phase15_agent_tasks_343(case_id, created_at)")
    db.execute("""CREATE TABLE IF NOT EXISTS phase15_agent_results_343(
        result_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, status TEXT NOT NULL, gateway_used TEXT NOT NULL,
        contract_version TEXT NOT NULL, result_json TEXT NOT NULL, record_hash TEXT NOT NULL, created_at TEXT NOT NULL,
        FOREIGN KEY(task_id) REFERENCES phase15_agent_tasks_343(task_id)
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_phase15_agent_results343_task ON phase15_agent_results_343(task_id, created_at)")
    for table in ("phase15_agent_tasks_343", "phase15_agent_results_343"):
        db.execute(f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_update BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT,'{table} immutable'); END")
        db.execute(f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'{table} immutable'); END")
