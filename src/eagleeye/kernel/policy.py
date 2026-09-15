from __future__ import annotations

from dataclasses import dataclass

from .contracts import ActionClass, AgentTask, ApprovalState, GatewayKind


@dataclass(frozen=True, slots=True)
class KernelDecision:
    disposition: str
    reason: str
    gateway: GatewayKind

    @property
    def executable(self) -> bool:
        return self.disposition == "allow"


class Phase15KernelPolicy:
    """Fail-closed Phase-15 kernel policy for Build 343.

    External gateways are specified but intentionally unavailable in this build.
    This prevents an agent contract from silently turning into direct network, Tor,
    browser, export or mutation access before Search Session Capsules/OPSEC v2 exist.
    """

    BUILD = "343.0"
    HIGH_IMPACT = {ActionClass.EXTERNAL_RESEARCH, ActionClass.DARKNET_RESEARCH, ActionClass.EXPORT, ActionClass.MERGE, ActionClass.DELETE, ActionClass.RELEASE}

    def evaluate(self, task: AgentTask) -> KernelDecision:
        if task.approval_state is ApprovalState.DENIED:
            return KernelDecision("block", "human_approval_denied", task.requested_gateway)
        if task.action_class in self.HIGH_IMPACT and task.approval_state is not ApprovalState.APPROVED:
            return KernelDecision("block", "explicit_human_approval_required", task.requested_gateway)
        if task.requested_gateway in {GatewayKind.SEARCH, GatewayKind.DARKNET, GatewayKind.IMAGE, GatewayKind.EXPORT, GatewayKind.MUTATION}:
            return KernelDecision("defer", "runtime_gateway_not_enabled_before_search_capsule_opsec_v2", task.requested_gateway)
        if task.requested_gateway is GatewayKind.EVIDENCE_READ:
            return KernelDecision("defer", "evidence_gateway_contract_defined_runtime_adapter_not_enabled", task.requested_gateway)
        if task.requested_gateway is GatewayKind.NONE and task.action_class is ActionClass.LOCAL_ANALYSIS:
            return KernelDecision("allow", "local_contract_only", GatewayKind.NONE)
        return KernelDecision("block", "action_gateway_mismatch_or_not_allowed", task.requested_gateway)


KernelPolicy343 = Phase15KernelPolicy
