from __future__ import annotations

from contextvars import ContextVar, Token
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List

from eagleeye_pro.core.database import Database, dumps, new_id, now_ts


_AUDIT_ACTOR: ContextVar[str] = ContextVar("eagleeye_audit_actor", default="")


class AuditService:
    def __init__(self, db: Database, actor: str = "local-analyst"):
        self.db = db
        self.actor = actor

    def current_actor(self) -> str:
        return _AUDIT_ACTOR.get() or self.actor

    def push_actor(self, actor: str) -> Token:
        return _AUDIT_ACTOR.set(str(actor or self.actor))

    def pop_actor(self, token: Token) -> None:
        _AUDIT_ACTOR.reset(token)

    @contextmanager
    def actor_scope(self, actor: str) -> Iterator[None]:
        token = self.push_actor(actor)
        try:
            yield
        finally:
            self.pop_actor(token)

    def log(self, action: str, object_type: str, object_id: str | None = None, case_id: str | None = None, details: Dict[str, Any] | None = None) -> str:
        event_id = new_id("audit")
        self.db.execute(
            "INSERT INTO audit_events(event_id,timestamp,actor,case_id,action,object_type,object_id,details_json) VALUES(?,?,?,?,?,?,?,?)",
            [event_id, now_ts(), self.current_actor(), case_id, action, object_type, object_id, dumps(details or {})],
        )
        return event_id

    def list_for_case(self, case_id: str | None = None, limit: int = 200) -> List[Dict[str, Any]]:
        if case_id:
            return self.db.all("SELECT * FROM audit_events WHERE case_id=? ORDER BY timestamp DESC LIMIT ?", [case_id, limit])
        return self.db.all("SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?", [limit])
