from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from eagleeye_pro.core.database import new_id

from .models import CollectionEventModel, EventType
from .repository import CoreRepository1041


class TypedEventBus1041:
    def __init__(self, repository: CoreRepository1041):
        self.repository = repository
        self._handlers: dict[EventType, list[Callable[[CollectionEventModel], Any]]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: Callable[[CollectionEventModel], Any]) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, *, case_id: str, event_type: EventType, producer: str, artifact_id: str | None = None, connector_run_id: str | None = None, payload: dict[str, Any] | None = None) -> CollectionEventModel:
        event = CollectionEventModel(
            event_id=new_id("evt1041"), case_id=case_id, event_type=event_type,
            producer=producer, artifact_id=artifact_id, connector_run_id=connector_run_id,
            payload=payload or {},
        )
        self.repository.emit_event(event)
        for handler in self._handlers[event_type]:
            handler(event)
        return event
