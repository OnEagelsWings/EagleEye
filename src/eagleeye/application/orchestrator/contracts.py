from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ModelEnvelope:
    """Structured input boundary for future local or approved model adapters.

    External source text is always carried as untrusted data. It is never merged
    into system policy or treated as executable instructions.
    """

    case_id: str
    agent_key: str
    prompt_version: str
    policy: dict[str, Any]
    input_data: dict[str, Any]
    source_refs: tuple[dict[str, str], ...]


@dataclass(frozen=True, slots=True)
class ModelResult:
    content: dict[str, Any]
    model_key: str
    model_version: str
    prompt_version: str
    external_network_used: bool = False


@runtime_checkable
class AnalystModelAdapter(Protocol):
    model_key: str
    model_version: str

    def complete(self, envelope: ModelEnvelope) -> ModelResult:
        """Return a structured suggestions-only result without side effects."""


class DeterministicLocalAdapter:
    """Build-127 default adapter: local, deterministic and network-free."""

    model_key = "deterministic_local_127"
    model_version = "1.0"

    def complete(self, envelope: ModelEnvelope) -> ModelResult:
        content = dict(envelope.input_data)
        content["model_boundary"] = {
            "model_key": self.model_key,
            "model_version": self.model_version,
            "prompt_version": envelope.prompt_version,
            "external_network_used": False,
            "untrusted_sources_are_data_only": True,
        }
        return ModelResult(
            content=content,
            model_key=self.model_key,
            model_version=self.model_version,
            prompt_version=envelope.prompt_version,
            external_network_used=False,
        )
