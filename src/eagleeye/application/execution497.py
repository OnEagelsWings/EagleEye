"""Build 497: audited plan-step execution through the EXISTING provider engine.

A plan approval never grants network access. ProviderCollection120 verifies the
separate, approved case-bound search intent/query for every live attempt.
Reservation is committed *before* calls, so retries or concurrent requests
cannot silently duplicate an uncertain external action.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from . import plan496
from eagleeye.infrastructure.providers.policy import validate_public_scope

class ExecutionError(ValueError):
    pass

APPROVAL_PHRASE = "PROVIDER RUN APPROVED"
MODES = {"replay", "live"}

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _hash(row):
    return hashlib.sha256(json.dumps(
        {k:v for k,v in row.items() if k != "record_hash"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()

def initialize(ctx):
    ctx.db.conn.execute("""CREATE TABLE IF NOT EXISTS case_plan_runs_497(
        step_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, plan_id TEXT NOT NULL,
        provider_key TEXT NOT NULL, query_sha256 TEXT NOT NULL,
        mode TEXT NOT NULL, search_intent_id TEXT NOT NULL, search_query_id TEXT NOT NULL,
        state TEXT NOT NULL, provider_run_id TEXT NOT NULL,
        error_type TEXT NOT NULL, actor TEXT NOT NULL,
        created_at TEXT NOT NULL, completed_at TEXT NOT NULL, record_hash TEXT NOT NULL
    )""")
    ctx.db.conn.execute("CREATE INDEX IF NOT EXISTS case_plan_runs_497_case ON case_plan_runs_497(case_id,plan_id)")
    ctx.db.conn.commit()

def get_execution(ctx, case_id, step_id):
    row = ctx.db.one("SELECT * FROM case_plan_runs_497 WHERE case_id=? AND step_id=?", (case_id,step_id))
    if not row: return None
    row = dict(row)
    if _hash(row) != row["record_hash"]:
        raise ExecutionError("Execution audit integrity verification failed")
    return row

def list_executions(ctx, case_id, plan_id):
    rows = ctx.db.all("SELECT step_id FROM case_plan_runs_497 WHERE case_id=? AND plan_id=? ORDER BY created_at",
                      (case_id,plan_id))
    return [get_execution(ctx,case_id,r["step_id"]) for r in rows]

def run_step(ctx, user, case_id, plan_id, step_id, *, query, purpose, mode,
             confirmation, search_intent_id="", search_query_id=""):
    # Check *service-level* permissions, not only the HTTP interface.
    ctx.team_governance_359.authorize(user,case_id=case_id,capability="research.run",
                                      object_type="operational_case",object_id=case_id)
    plan = plan496.get_plan(ctx,case_id,plan_id)
    if plan["state"] != "approved": raise ExecutionError("Research plan is not approved")
    steps = plan496.list_steps(ctx,case_id,plan_id)
    step = next((row for row in steps if row["step_id"] == step_id),None)
    if not step or step["kind"] != "provider_proposal" or step["state"] != "proposed":
        raise ExecutionError("Only an unchanged proposed provider step can run")
    if mode not in MODES: raise ExecutionError("Only replay or explicitly approved live mode")
    if confirmation != APPROVAL_PHRASE: raise ExecutionError("Explicit execution approval required")
    query = plan496._safe_text(query,field="query",minimum=2,maximum=230)
    purpose = plan496._safe_text(purpose,field="purpose",minimum=15,maximum=450)
    validate_public_scope(query,purpose)
    for value in (search_intent_id,search_query_id):
        plan496._safe_text(value,field="approval reference",minimum=0,maximum=110)
    if mode == "live" and (not search_intent_id or not search_query_id):
        raise ExecutionError("Live run requires approved intent and query references")
    provider = ctx.provider_collection_120.provider(step["provider_key"])
    if not provider["enabled"] or not provider["public_only"] or not provider["supports_"+mode]:
        raise ExecutionError("Provider not enabled for requested mode")
    if mode == "live":
        # Fail before inserting a reservation if the approval is invalid.
        ctx.provider_collection_120._validate_search_approval(
            case_id=case_id, provider_key=step["provider_key"], query=query,
            search_intent_id=search_intent_id, search_query_id=search_query_id)
    data={
        "step_id":step_id,"case_id":case_id,"plan_id":plan_id,
        "provider_key":step["provider_key"],
        "query_sha256":hashlib.sha256(query.encode()).hexdigest(),
        "mode":mode,"search_intent_id":search_intent_id,"search_query_id":search_query_id,
        "state":"reserved","provider_run_id":"","error_type":"","actor":user["username"],
        "created_at":_now(),"completed_at":""
    }
    data["record_hash"]=_hash(data)
    # Only a fresh step is eligible. UNIQUE step_id prevents simultaneous runs.
    with ctx.audit.actor_scope(user["username"]),ctx.db.transaction(immediate=True):
        if get_execution(ctx,case_id,step_id):
            raise ExecutionError("Plan step has already been reserved; no automatic retries")
        ctx.db.execute(
            "INSERT INTO case_plan_runs_497("+",".join(data)+") VALUES("+",".join("?" for _ in data)+")",
            tuple(data.values()))
        ctx.audit.log("case_plan_provider_reserved_497","case_plan_step",step_id,case_id,
                      {"plan_id":plan_id,"provider":step["provider_key"],"mode":mode,
                       "query_sha256":data["query_sha256"],"executed":False})
    # Execution is deliberately outside a database transaction. A crash leaves
    # 'reserved', requiring manual reconciliation; it must NOT auto-repeat.
    state="completed"; result=None; err=None
    try:
        result=ctx.provider_collection_120.execute(
            case_id=case_id,provider_key=step["provider_key"],query=query,
            purpose=purpose,approved_by=user["username"],
            confirmation=APPROVAL_PHRASE,mode=mode,
            search_intent_id=search_intent_id,search_query_id=search_query_id,
            max_results=20)
    except Exception as exc:
        state="failed";err=exc
    with ctx.audit.actor_scope(user["username"]),ctx.db.transaction(immediate=True):
        row=get_execution(ctx,case_id,step_id)
        row.update(state=state,provider_run_id=str((result or {}).get("run_id") or ""),
                   error_type=type(err).__name__ if err else "",completed_at=_now())
        row["record_hash"]=_hash(row)
        ctx.db.execute(
            "UPDATE case_plan_runs_497 SET state=?,provider_run_id=?,error_type=?,"
            "completed_at=?,record_hash=? WHERE step_id=? AND case_id=?",
            (row["state"],row["provider_run_id"],row["error_type"],
             row["completed_at"],row["record_hash"],step_id,case_id))
        ctx.audit.log("case_plan_provider_finished_497","case_plan_step",step_id,case_id,
                      {"plan_id":plan_id,"state":state,"provider_run_id":row["provider_run_id"],
                       "candidate_only":True,"error_type":row["error_type"]})
    if err: raise ExecutionError("Provider run failed; reserved step needs manual review") from err
    return row
