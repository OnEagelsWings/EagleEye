from __future__ import annotations

from typing import Mapping

from .contracts import AgentResult, AgentTask, GatewayKind, ResultStatus
from .policy import Phase15KernelPolicy
from .ports import AgentPort, GatewayPort, TaskRepositoryPort


class KernelDispatcher:
    """Single mediation point between agent contracts and side-effect gateways.

    The dispatcher owns no database, browser, shell or network client. Persistence is
    behind TaskRepositoryPort; external side effects are behind explicit GatewayPort.
    """

    def __init__(self, repository: TaskRepositoryPort, policy: Phase15KernelPolicy, gateways: Mapping[GatewayKind, GatewayPort] | None = None) -> None:
        self.repository = repository
        self.policy = policy
        self.gateways = dict(gateways or {})

    def submit(self, task: AgentTask) -> dict:
        return self.repository.create_task(task)

    def decision(self, task: AgentTask):
        return self.policy.evaluate(task)

    def dispatch(self, task_id: str, *, agent: AgentPort | None = None) -> AgentResult:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(task_id)
        decision = self.policy.evaluate(task)
        if decision.disposition == "block":
            result = AgentResult.create(task_id=task.task_id, status=ResultStatus.BLOCKED, output_payload={"executed": False}, policy_reason=decision.reason)
        elif decision.disposition == "defer":
            result = AgentResult.create(task_id=task.task_id, status=ResultStatus.DEFERRED, output_payload={"executed": False, "required_gateway": decision.gateway.value}, policy_reason=decision.reason)
        elif task.requested_gateway is GatewayKind.NONE:
            if agent is None:
                result = AgentResult.create(task_id=task.task_id, status=ResultStatus.PROPOSED, output_payload={"executed": False, "reason": "agent_adapter_not_supplied"}, policy_reason="local_contract_ready")
            else:
                result = agent.handle(task)
                if result.task_id != task.task_id:
                    raise ValueError("Agent result task_id mismatch")
                if result.gateway_used is not GatewayKind.NONE:
                    raise PermissionError("AgentPort cannot self-assert gateway execution")
        else:
            gateway = self.gateways.get(task.requested_gateway)
            if gateway is None:
                result = AgentResult.create(task_id=task.task_id, status=ResultStatus.DEFERRED, output_payload={"executed": False, "required_gateway": task.requested_gateway.value}, policy_reason="approved_gateway_adapter_missing")
            else:
                result = gateway.execute(task)
        self.repository.append_result(result)
        return result
