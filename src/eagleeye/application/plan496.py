"""Build 496: case-scoped investigator plans, human approval, audit and no execution.

This is the planning half of a future AI/tool orchestrator, deliberately kept
inside EagleEye's existing canonical case DB. Plan approval does NOT authorize
network traffic: ProviderCollection120's independent search grants still apply.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
import unicodedata

MAX_PLANS_PER_CASE = 30
MAX_STEPS_PER_PLAN = 20
KINDS = frozenset({
    "manual_source", "provider_proposal", "web_capture_proposal",
    "document_review", "entity_review", "hypothesis_check",
})
DECISIONS = frozenset({"approved", "rejected"})
STEP_DECISIONS = frozenset({"done", "blocked"})


class PlanError(ValueError):
    pass


def _at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_text(value: object, *, field: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise PlanError(field + " must be text")
    # Validate raw input before whitespace normalization: split() would otherwise
    # silently erase newlines, tabs and other controls from the audit record.
    if any(unicodedata.category(ch) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for ch in value):
        raise PlanError(field + " contains forbidden Unicode controls")
    value = " ".join(value.split())
    if not minimum <= len(value) <= maximum:
        raise PlanError(field + " must contain " + str(minimum) + "–" + str(maximum) + " characters")
    return value


def _hash(row: dict) -> str:
    return hashlib.sha256(json.dumps(
        {k: v for k, v in row.items() if k != "record_hash"},
        sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


PLAN_SCHEMA = """CREATE TABLE IF NOT EXISTS case_plans_496(
    plan_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    objective TEXT NOT NULL,
    scope TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'draft',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reviewed_by TEXT NOT NULL DEFAULT '',
    reviewed_at TEXT NOT NULL DEFAULT '',
    review_note TEXT NOT NULL DEFAULT '',
    record_hash TEXT NOT NULL
)"""

STEP_SCHEMA = """CREATE TABLE IF NOT EXISTS case_plan_steps_496(
    step_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    instruction TEXT NOT NULL,
    provider_key TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'proposed',
    outcome TEXT NOT NULL DEFAULT '',
    acted_by TEXT NOT NULL DEFAULT '',
    acted_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    record_hash TEXT NOT NULL
)"""


def initialize(ctx) -> None:
    ctx.db.conn.execute(PLAN_SCHEMA)
    ctx.db.conn.execute(STEP_SCHEMA)
    ctx.db.conn.execute("CREATE INDEX IF NOT EXISTS case_plans_496_case ON case_plans_496(case_id,created_at)")
    ctx.db.conn.execute("CREATE INDEX IF NOT EXISTS case_plan_steps_496_plan ON case_plan_steps_496(case_id,plan_id)")
    ctx.db.conn.commit()


def _checked(value: object) -> dict:
    if value is None:
        raise KeyError("Investigation plan or step not found")
    row = dict(value)
    if row.get("record_hash") != _hash(row):
        raise PlanError("Investigation plan integrity verification failed")
    return row


def get_plan(ctx, case_id: str, plan_id: str) -> dict:
    return _checked(ctx.db.one(
        "SELECT * FROM case_plans_496 WHERE case_id=? AND plan_id=?", (case_id,plan_id)
    ))


def list_plans(ctx, case_id: str) -> list[dict]:
    rows = ctx.db.all(
        "SELECT * FROM case_plans_496 WHERE case_id=? ORDER BY created_at DESC,plan_id DESC LIMIT ?",
        (case_id,MAX_PLANS_PER_CASE)
    )
    return [_checked(row) for row in rows]


def list_steps(ctx, case_id: str, plan_id: str) -> list[dict]:
    get_plan(ctx, case_id, plan_id)
    rows = ctx.db.all(
        "SELECT * FROM case_plan_steps_496 WHERE case_id=? AND plan_id=? ORDER BY created_at,step_id",
        (case_id,plan_id)
    )
    return [_checked(row) for row in rows]


def _insert(ctx, table: str, row: dict) -> None:
    row["record_hash"] = _hash(row)
    columns = list(row)
    ctx.db.execute("INSERT INTO " + table + "(" + ",".join(columns) +
                   ") VALUES(" + ",".join("?" for _ in columns) + ")", tuple(row.values()))


def create_plan(ctx, user: dict, case_id: str, objective: str, scope: str) -> dict:
    ctx.team_governance_359.authorize(user, case_id=case_id, capability="research.run", object_type="operational_case", object_id=case_id)
    objective = _safe_text(objective, field="objective", minimum=15, maximum=350)
    scope = _safe_text(scope, field="scope", minimum=20, maximum=1200)
    with ctx.audit.actor_scope(user["username"]), ctx.db.transaction(immediate=True):
        count = ctx.db.one("SELECT count(*) AS n FROM case_plans_496 WHERE case_id=?", (case_id,))["n"]
        if count >= MAX_PLANS_PER_CASE:
            raise PlanError("At most 30 investigation plans per case")
        row = dict(
            plan_id="ip496_" + secrets.token_hex(12), case_id=case_id,
            objective=objective, scope=scope, state="draft",
            created_by=user["username"], created_at=_at(),
            reviewed_by="", reviewed_at="", review_note=""
        )
        _insert(ctx, "case_plans_496", row)
        ctx.audit.log("investigation_plan_created_496", "case_plan", row["plan_id"], case_id,
                      {"state": "draft", "network": False, "ai_tools": False})
    return row


def add_step(ctx, user: dict, case_id: str, plan_id: str, kind: str,
             instruction: str, provider_key: str = "") -> dict:
    ctx.team_governance_359.authorize(user, case_id=case_id, capability="research.run", object_type="operational_case", object_id=case_id)
    instruction = _safe_text(instruction, field="instruction", minimum=15, maximum=800)
    if kind not in KINDS:
        raise PlanError("Unsupported tool proposal kind")
    provider_key = _safe_text(provider_key, field="provider_key", minimum=0, maximum=110)
    if kind != "provider_proposal" and provider_key:
        raise PlanError("Only provider proposals can specify a provider key")
    if kind == "provider_proposal":
        if not provider_key or not provider_key.replace("_","").replace("-","").isalnum():
            raise PlanError("A valid, exact provider key is required")
        try:
            registered = ctx.provider_collection_120.provider(provider_key)
        except KeyError as exc:
            raise PlanError("Unknown provider; it must exist in the canonical catalog") from exc
        if not registered.get("enabled"):
            raise PlanError("Provider is disabled")
    with ctx.audit.actor_scope(user["username"]), ctx.db.transaction(immediate=True):
        plan = get_plan(ctx, case_id, plan_id)
        if plan["state"] != "draft":
            raise PlanError("Reviewed plans cannot be modified")
        n = ctx.db.one("SELECT count(*) AS n FROM case_plan_steps_496 WHERE case_id=? AND plan_id=?",
                       (case_id,plan_id))["n"]
        if n >= MAX_STEPS_PER_PLAN:
            raise PlanError("At most 20 steps per investigation plan")
        row = dict(step_id="ips496_" + secrets.token_hex(12), plan_id=plan_id, case_id=case_id,
                   kind=kind, instruction=instruction, provider_key=provider_key,
                   state="proposed", outcome="", acted_by="", acted_at="", created_at=_at())
        _insert(ctx, "case_plan_steps_496", row)
        ctx.audit.log("investigation_step_proposed_496", "case_plan_step", row["step_id"], case_id,
                      {"plan_id": plan_id, "kind": kind, "network": False,
                       "provider_key": provider_key, "executed": False})
    return row


def review_plan(ctx, user: dict, case_id: str, plan_id: str, decision: str,
                reason: str, expected_hash: str) -> dict:
    ctx.team_governance_359.authorize(user, case_id=case_id, capability="source.review", object_type="operational_case", object_id=case_id)
    if decision not in DECISIONS:
        raise PlanError("Unsupported plan review decision")
    reason = _safe_text(reason, field="review_note", minimum=20, maximum=1200)
    with ctx.audit.actor_scope(user["username"]), ctx.db.transaction(immediate=True):
        row = get_plan(ctx, case_id, plan_id)
        if row["record_hash"] != expected_hash:
            raise PlanError("Stale review form; reload the plan")
        if row["state"] != "draft":
            raise PlanError("Plan was already reviewed")
        if decision == "approved" and not list_steps(ctx, case_id, plan_id):
            raise PlanError("A plan needs at least one proposed step")
        row.update(state=decision, reviewed_by=user["username"], reviewed_at=_at(), review_note=reason)
        row["record_hash"] = _hash(row)
        ctx.db.execute(
            "UPDATE case_plans_496 SET state=?, reviewed_by=?, reviewed_at=?, review_note=?, record_hash=? "
            "WHERE case_id=? AND plan_id=? AND state='draft'",
            (row["state"],row["reviewed_by"],row["reviewed_at"],row["review_note"],
             row["record_hash"],case_id,plan_id)
        )
        ctx.audit.log("investigation_plan_reviewed_496", "case_plan", plan_id, case_id,
                      {"decision": decision, "network_approved": False,
                       "provider_execution_authorized": False, "ai_execution": False})
    return row


def annotate_step(ctx, user: dict, case_id: str, plan_id: str, step_id: str,
                  decision: str, note: str, expected_hash: str) -> dict:
    ctx.team_governance_359.authorize(user, case_id=case_id, capability="research.run", object_type="operational_case", object_id=case_id)
    if decision not in STEP_DECISIONS:
        raise PlanError("Unsupported step status")
    note = _safe_text(note, field="outcome", minimum=20, maximum=1400)
    with ctx.audit.actor_scope(user["username"]), ctx.db.transaction(immediate=True):
        plan = get_plan(ctx, case_id, plan_id)
        if plan["state"] != "approved":
            raise PlanError("Only approved plans can be annotated")
        row = _checked(ctx.db.one(
            "SELECT * FROM case_plan_steps_496 WHERE case_id=? AND plan_id=? AND step_id=?",
            (case_id,plan_id,step_id)
        ))
        if row["record_hash"] != expected_hash or row["state"] != "proposed":
            raise PlanError("Stale step or already annotated")
        row.update(state=decision, outcome=note, acted_by=user["username"], acted_at=_at())
        row["record_hash"] = _hash(row)
        ctx.db.execute(
            "UPDATE case_plan_steps_496 SET state=?,outcome=?,acted_by=?,acted_at=?,record_hash=? "
            "WHERE case_id=? AND plan_id=? AND step_id=? AND state='proposed'",
            (row["state"],row["outcome"],row["acted_by"],row["acted_at"],
             row["record_hash"],case_id,plan_id,step_id)
        )
        ctx.audit.log("investigation_step_annotated_496", "case_plan_step", step_id, case_id,
                      {"plan_id": plan_id, "decision": decision, "note_only": True,
                       "provider_run_performed": False, "truth_determined": False})
    return row
