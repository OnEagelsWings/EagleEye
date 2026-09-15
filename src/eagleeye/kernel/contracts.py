from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

CONTRACT_VERSION = "phase15.agent-task-result.v1"
MAX_PAYLOAD_BYTES = 64 * 1024


class AgentRole(str, Enum):
    INVESTIGATION_SUPERVISOR = "investigation_supervisor"
    IMAGE_INTELLIGENCE = "image_intelligence"
    OPSEC_INTELLIGENCE = "opsec_intelligence"
    VOICE_GATEWAY = "voice_gateway"
    CRAWLER_WORKER = "crawler_worker"
    DATA_ADAPTER_WORKER = "data_adapter_worker"


class ActionClass(str, Enum):
    LOCAL_ANALYSIS = "local_analysis"
    EVIDENCE_QUERY = "evidence_query"
    EXTERNAL_RESEARCH = "external_research"
    DARKNET_RESEARCH = "darknet_research"
    IMAGE_ANALYSIS = "image_analysis"
    EXPORT = "export"
    MERGE = "merge"
    DELETE = "delete"
    RELEASE = "release"


class GatewayKind(str, Enum):
    NONE = "none"
    EVIDENCE_READ = "evidence_read"
    SEARCH = "search"
    DARKNET = "darknet"
    IMAGE = "image"
    EXPORT = "export"
    MUTATION = "mutation"


class ApprovalState(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class ResultStatus(str, Enum):
    PROPOSED = "proposed"
    COMPLETED = "completed"
    DEFERRED = "deferred"
    BLOCKED = "blocked"
    ERROR = "error"


_SECRET_KEY = re.compile(r"(^|_)(password|passwd|token|cookie|authorization|secret|api[_-]?key|private[_-]?key|bearer)($|_)", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8"))


def _validate_payload(value: Any, path: str = "payload") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_s = str(key)
            if _SECRET_KEY.search(key_s) and not key_s.lower().endswith(("_ref", "_reference", "_id")):
                raise ValueError(f"Raw secret material is forbidden in agent contracts: {path}.{key_s}")
            _validate_payload(child, f"{path}.{key_s}")
    elif isinstance(value, (list, tuple)):
        for idx, child in enumerate(value):
            _validate_payload(child, f"{path}[{idx}]")
    elif isinstance(value, (str, int, float, bool)) or value is None:
        return
    else:
        raise TypeError(f"Agent contract payload must be JSON-compatible: {path}")


def _enum_value(value: Any, enum_type: type[Enum]) -> str:
    if isinstance(value, enum_type):
        return str(value.value)
    return str(value)


@dataclass(frozen=True, slots=True)
class AgentTask:
    task_id: str
    case_id: str
    actor: str
    agent_role: AgentRole
    action_class: ActionClass
    requested_gateway: GatewayKind
    approval_state: ApprovalState
    input_payload: dict[str, Any] = field(default_factory=dict)
    search_run_id: str | None = None
    parent_task_id: str | None = None
    created_at: str = field(default_factory=_now)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(f"Unsupported agent contract: {self.contract_version}")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{6,120}", self.task_id):
            raise ValueError("Invalid task_id")
        if not str(self.case_id).strip() or len(str(self.case_id)) > 160:
            raise ValueError("case_id is required")
        if not str(self.actor).strip() or len(str(self.actor)) > 160:
            raise ValueError("actor is required")
        _validate_payload(self.input_payload)
        if _json_size(self.input_payload) > MAX_PAYLOAD_BYTES:
            raise ValueError("Agent task payload exceeds 64 KiB")
        if self.action_class is ActionClass.DARKNET_RESEARCH and self.requested_gateway is not GatewayKind.DARKNET:
            raise ValueError("Darknet research tasks must request the darknet gateway")
        if self.action_class in {ActionClass.EXPORT} and self.requested_gateway is not GatewayKind.EXPORT:
            raise ValueError("Export tasks must request the export gateway")
        if self.action_class in {ActionClass.MERGE, ActionClass.DELETE, ActionClass.RELEASE} and self.requested_gateway is not GatewayKind.MUTATION:
            raise ValueError("Mutating/release tasks must request the mutation gateway")

    @classmethod
    def create(
        cls,
        *,
        case_id: str,
        actor: str,
        agent_role: AgentRole,
        action_class: ActionClass,
        requested_gateway: GatewayKind = GatewayKind.NONE,
        approval_state: ApprovalState = ApprovalState.NOT_REQUIRED,
        input_payload: dict[str, Any] | None = None,
        search_run_id: str | None = None,
        parent_task_id: str | None = None,
        task_id: str | None = None,
    ) -> "AgentTask":
        return cls(
            task_id=task_id or "agt343_" + uuid.uuid4().hex[:20],
            case_id=str(case_id), actor=str(actor), agent_role=agent_role,
            action_class=action_class, requested_gateway=requested_gateway,
            approval_state=approval_state, input_payload=dict(input_payload or {}),
            search_run_id=search_run_id, parent_task_id=parent_task_id,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for name in ("agent_role", "action_class", "requested_gateway", "approval_state"):
            data[name] = _enum_value(getattr(self, name), type(getattr(self, name)))
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AgentTask":
        return cls(
            task_id=str(data["task_id"]), case_id=str(data["case_id"]), actor=str(data["actor"]),
            agent_role=AgentRole(str(data["agent_role"])), action_class=ActionClass(str(data["action_class"])),
            requested_gateway=GatewayKind(str(data["requested_gateway"])), approval_state=ApprovalState(str(data["approval_state"])),
            input_payload=dict(data.get("input_payload") or {}), search_run_id=data.get("search_run_id"),
            parent_task_id=data.get("parent_task_id"), created_at=str(data.get("created_at") or _now()),
            contract_version=str(data.get("contract_version") or ""),
        )


@dataclass(frozen=True, slots=True)
class AgentResult:
    result_id: str
    task_id: str
    status: ResultStatus
    output_payload: dict[str, Any]
    gateway_used: GatewayKind = GatewayKind.NONE
    policy_reason: str = ""
    created_at: str = field(default_factory=_now)
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CONTRACT_VERSION:
            raise ValueError(f"Unsupported result contract: {self.contract_version}")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{6,120}", self.result_id):
            raise ValueError("Invalid result_id")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{6,120}", self.task_id):
            raise ValueError("Invalid task_id")
        _validate_payload(self.output_payload, "output_payload")
        if _json_size(self.output_payload) > MAX_PAYLOAD_BYTES:
            raise ValueError("Agent result payload exceeds 64 KiB")

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        status: ResultStatus,
        output_payload: dict[str, Any] | None = None,
        gateway_used: GatewayKind = GatewayKind.NONE,
        policy_reason: str = "",
    ) -> "AgentResult":
        return cls(
            result_id="agr343_" + uuid.uuid4().hex[:20], task_id=task_id,
            status=status, output_payload=dict(output_payload or {}), gateway_used=gateway_used,
            policy_reason=str(policy_reason)[:1000],
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["gateway_used"] = self.gateway_used.value
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AgentResult":
        return cls(
            result_id=str(data["result_id"]), task_id=str(data["task_id"]),
            status=ResultStatus(str(data["status"])), output_payload=dict(data.get("output_payload") or {}),
            gateway_used=GatewayKind(str(data.get("gateway_used") or GatewayKind.NONE.value)),
            policy_reason=str(data.get("policy_reason") or ""), created_at=str(data.get("created_at") or _now()),
            contract_version=str(data.get("contract_version") or ""),
        )
