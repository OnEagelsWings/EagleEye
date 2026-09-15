from __future__ import annotations

from typing import Any

from eagleeye.kernel.contracts import ActionClass, AgentRole, AgentTask, ApprovalState, GatewayKind
from eagleeye.kernel.dispatcher import KernelDispatcher


class InvestigationKernelUseCases:
    """Build-independent application use cases over the Phase-15 kernel ports."""

    def __init__(self, dispatcher: KernelDispatcher) -> None:
        self.dispatcher = dispatcher

    def submit_local_analysis(self, *, case_id: str, actor: str, objective: str, context_refs: list[str] | None = None) -> dict[str, Any]:
        objective = str(objective or "").strip()
        if not objective: raise ValueError("objective is required")
        task = AgentTask.create(case_id=case_id, actor=actor, agent_role=AgentRole.INVESTIGATION_SUPERVISOR,
            action_class=ActionClass.LOCAL_ANALYSIS, requested_gateway=GatewayKind.NONE, approval_state=ApprovalState.NOT_REQUIRED,
            input_payload={"objective": objective, "context_refs": list(context_refs or [])})
        return self.dispatcher.submit(task)

    def submit_darknet_research(self, *, case_id: str, actor: str, query: str, source_ids: list[str], source_plan_id: str, human_approved: bool, search_run_id: str | None = None) -> dict[str, Any]:
        query = str(query or "").strip()
        source_ids = list(dict.fromkeys(str(x) for x in source_ids if str(x).strip()))
        if not query or not source_ids or not str(source_plan_id).strip():
            raise ValueError("query, source_ids and source_plan_id are required")
        task = AgentTask.create(case_id=case_id, actor=actor, agent_role=AgentRole.INVESTIGATION_SUPERVISOR,
            action_class=ActionClass.DARKNET_RESEARCH, requested_gateway=GatewayKind.DARKNET,
            approval_state=ApprovalState.APPROVED if human_approved else ApprovalState.PENDING,
            input_payload={"query": query, "source_ids": source_ids, "source_plan_id": str(source_plan_id),
                           "network_execution_requested": False, "opsec_gate_required": True,
                           "content_trust": "untrusted_until_quarantine_and_review"},
            search_run_id=search_run_id)
        return self.dispatcher.submit(task)

    def evaluate(self, task_id: str) -> dict[str, Any]:
        task = self.dispatcher.repository.get_task(task_id)
        if task is None: raise KeyError(task_id)
        decision = self.dispatcher.decision(task)
        return {"task_id": task_id, "disposition": decision.disposition, "reason": decision.reason, "gateway": decision.gateway.value}

    def dispatch(self, task_id: str) -> dict[str, Any]:
        return self.dispatcher.dispatch(task_id).to_dict()
