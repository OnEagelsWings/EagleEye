from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict

@dataclass(frozen=True)
class Command:
    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    actor: str = "local-analyst"
