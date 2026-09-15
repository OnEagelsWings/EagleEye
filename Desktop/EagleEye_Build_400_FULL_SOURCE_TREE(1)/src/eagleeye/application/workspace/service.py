from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any


class WorkspaceValidationError(ValueError):
    pass


class WorkspaceConflictError(WorkspaceValidationError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


class InvestigationWorkspace122Service:
    """Case-bound, review-first workspace service for Build 122.1.

    Stored records remain candidates unless a dedicated human review service changes
    their state. This service never promotes identity, graph or timeline assertions.
    """

    SECTIONS = (
        "overview", "mandate", "research", "intake", "entities", "evidence",
        "graph", "timeline", "contradictions", "hypotheses", "review", "export", "audit",
    )
    INTAKE_DECISIONS = {"deferred", "duplicate", "rejected", "accepted_for_evidence"}
    OBJECT_STORES = {
        "intake": ("provider_intake_120", "intake_id", "created_at"),
        "evidence": ("evidence_packages_121", "package_id", "captured_at"),
        "entity": ("resolution_entities_115", "resolution_entity_id", "created_at"),
        "relation": ("graph_relations_116", "relation_id", "created_at"),
        "timeline": ("timeline_events_117", "event_id", "created_at"),
        "contradiction": ("contradictions_118", "contradiction_id", "created_at"),
    }

    def __init__(self, db: Any, audit: Any, evidence: Any = None):
        self.db, self.audit, self.evidence = db, audit, evidence
        from eagleeye.infrastructure.workspace.schema import ensure_workspace_schema_122

        ensure_workspace_schema_122(db)

    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise WorkspaceValidationError("unknown case")
        return row

    def _table(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    def _count(self, table: str, where: str = "1=1", params: tuple[Any, ...] = ()) -> int:
        if not self._table(table):
            return 0
        return int(self.db.one(f"SELECT COUNT(*) AS n FROM {table} WHERE {where}", params)["n"])

    def _log(self, case_id: str, actor: str, action_type: str, object_type: str,
             object_id: str, details: dict[str, Any] | None = None) -> str:
        action_id = _id("wact1221")
        payload = details or {}
        self.db.execute(
            "INSERT INTO workspace_actions_122(action_id,case_id,actor,action_type,object_type,object_id,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (action_id, case_id, actor, action_type, object_type, object_id, _json(payload), _now()),
        )
        self.audit.log(action_type, object_type, object_id, case_id, payload)
        return action_id

    def _record_recovery(self, *, case_id: str, intake_id: str, operation: str,
                         exc: BaseException, cleanup_ok: bool, details: dict[str, Any] | None = None) -> None:
        try:
            self.db.execute(
                "INSERT INTO workspace_recovery_1221(recovery_id,case_id,intake_id,operation,state,error_type,error_text,cleanup_ok,details_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (_id("wrec1221"), case_id, intake_id, operation, "recovered" if cleanup_ok else "attention_required",
                 type(exc).__name__, str(exc)[:4000], int(cleanup_ok), _json(details or {}), _now()),
            )
        except Exception:
            # Recovery logging must never hide the primary failure.
            pass

    def case_snapshot(self, case_id: str) -> dict[str, Any]:
        case = self._case(case_id)
        metrics = {
            "open_search_tasks": self._count("search_tasks", "case_id=? AND status NOT IN ('done','closed')", (case_id,)),
            "new_intake": self._count("provider_intake_120", "case_id=? AND review_status='new'", (case_id,)),
            "evidence_packages": self._count("evidence_packages_121", "case_id=?", (case_id,)),
            "evidence_integrity_attention": self._count("evidence_packages_121", "case_id=? AND status NOT IN ('preserved','verified')", (case_id,)),
            "entities": self._count("resolution_entities_115", "case_id=?", (case_id,)),
            "merge_reviews": self._count("resolution_merge_proposals_115", "case_id=? AND state IN ('proposed','needs_review')", (case_id,)),
            "relations_review": self._count("graph_relations_116", "case_id=? AND state IN ('draft','needs_review')", (case_id,)),
            "timeline_review": self._count("timeline_events_117", "case_id=? AND state IN ('draft','needs_review')", (case_id,)),
            "open_contradictions": self._count("contradictions_118", "case_id=? AND state IN ('open','needs_review')", (case_id,)),
            "pending_reviews": self._count("review_items", "case_id=? AND status IN ('new','pending')", (case_id,)),
            "recovery_attention": self._count("workspace_recovery_1221", "case_id=? AND state='attention_required'", (case_id,)),
        }
        actions: list[dict[str, Any]] = []
        mapping = [
            ("new_intake", "Provider-Intake prüfen", "intake"),
            ("evidence_integrity_attention", "Evidence-Integrität prüfen", "evidence"),
            ("merge_reviews", "Entity-Matches prüfen", "entities"),
            ("relations_review", "Graphrelationen prüfen", "graph"),
            ("timeline_review", "Timeline-Ereignisse prüfen", "timeline"),
            ("open_contradictions", "Widersprüche bearbeiten", "contradictions"),
            ("pending_reviews", "Review-Warteschlange bearbeiten", "review"),
            ("recovery_attention", "Recovery-Hinweise bearbeiten", "audit"),
        ]
        for key, label, section in mapping:
            if metrics[key]:
                actions.append({
                    "section": section, "label": label, "count": metrics[key],
                    "priority": "high" if key in {"evidence_integrity_attention", "open_contradictions", "recovery_attention"} else "normal",
                })
        if not actions:
            actions.append({"section": "research", "label": "Recherche fortsetzen", "count": 0, "priority": "normal"})
        return {
            "case": case, "metrics": metrics, "next_actions": actions, "sections": list(self.SECTIONS),
            "epistemic_notice": "Workspace-Kennzahlen sind Workflow-Indikatoren, keine Tatsachen-, Identitäts- oder Risikobewertungen.",
        }

    def intake(self, case_id: str, status: str = "new", limit: int = 100) -> list[dict[str, Any]]:
        self._case(case_id)
        if not self._table("provider_intake_120"):
            return []
        limit = max(1, min(int(limit), 500))
        if status == "all":
            return self.db.all(
                "SELECT intake_id,provider_key,title,canonical_url,snippet,review_status,candidate_only,created_at,updated_at FROM provider_intake_120 WHERE case_id=? ORDER BY created_at DESC LIMIT ?",
                (case_id, limit),
            )
        if status not in {"new", *self.INTAKE_DECISIONS}:
            raise WorkspaceValidationError("unsupported intake status")
        return self.db.all(
            "SELECT intake_id,provider_key,title,canonical_url,snippet,review_status,candidate_only,created_at,updated_at FROM provider_intake_120 WHERE case_id=? AND review_status=? ORDER BY created_at DESC LIMIT ?",
            (case_id, status, limit),
        )

    def decide_intake(self, *, case_id: str, intake_id: str, decision: str, actor: str, reason: str) -> dict[str, Any]:
        self._case(case_id)
        if decision not in self.INTAKE_DECISIONS:
            raise WorkspaceValidationError("unsupported intake decision")
        if len(reason.strip()) < 8:
            raise WorkspaceValidationError("substantive reason required")
        if not actor.strip():
            raise WorkspaceValidationError("actor required")
        package: dict[str, Any] | None = None
        try:
            with self.db.transaction(immediate=True):
                row = self.db.one(
                    "SELECT intake_id,case_id,review_status FROM provider_intake_120 WHERE intake_id=? AND case_id=?",
                    (intake_id, case_id),
                )
                if not row:
                    raise WorkspaceValidationError("intake item not found in case")
                cursor = self.db.execute(
                    "UPDATE provider_intake_120 SET review_status=?,updated_at=? WHERE intake_id=? AND case_id=? AND review_status='new'",
                    (decision, _now(), intake_id, case_id),
                )
                if cursor.rowcount != 1:
                    raise WorkspaceConflictError("intake item already decided by another operation")
                if decision == "accepted_for_evidence":
                    if self.evidence is None:
                        raise WorkspaceValidationError("evidence service unavailable")
                    package = self.evidence.preserve_intake_item(intake_id=intake_id, captured_by=actor)
                    if package.get("case_id") != case_id or not package.get("candidate_only"):
                        raise WorkspaceValidationError("evidence preservation violated case or candidate boundary")
                self._log(
                    case_id, actor, "workspace_intake_decision", "provider_intake_120", intake_id,
                    {"decision": decision, "reason": reason.strip(), "evidence_package_id": package["package_id"] if package else ""},
                )
            return {"intake_id": intake_id, "decision": decision, "evidence_package": package}
        except BaseException as exc:
            cleanup_ok = True
            if package is not None and self.evidence is not None:
                cleanup_ok = bool(self.evidence.discard_uncommitted_package(package))
            self._record_recovery(
                case_id=case_id, intake_id=intake_id, operation="decide_intake",
                exc=exc, cleanup_ok=cleanup_ok,
                details={"decision": decision, "actor": actor, "package_id": package.get("package_id", "") if package else ""},
            )
            raise

    def list_objects(self, case_id: str, object_type: str, limit: int = 200) -> list[dict[str, Any]]:
        self._case(case_id)
        if object_type not in self.OBJECT_STORES:
            raise WorkspaceValidationError("unsupported object type")
        table, _key, order_column = self.OBJECT_STORES[object_type]
        if not self._table(table):
            return []
        limit = max(1, min(int(limit), 500))
        return self.db.all(
            f"SELECT * FROM {table} WHERE case_id=? ORDER BY {order_column} DESC LIMIT ?",
            (case_id, limit),
        )

    def detail(self, case_id: str, object_type: str, object_id: str, actor: str = "local-analyst") -> dict[str, Any]:
        self._case(case_id)
        if object_type not in self.OBJECT_STORES:
            raise WorkspaceValidationError("unsupported object type")
        table, key, _order = self.OBJECT_STORES[object_type]
        if not self._table(table):
            raise WorkspaceValidationError("object store unavailable")
        row = self.db.one(f"SELECT * FROM {table} WHERE {key}=? AND case_id=?", (object_id, case_id))
        if not row:
            raise WorkspaceValidationError("object not found in case")
        with self.db.transaction():
            self._log(case_id, actor, "workspace_object_viewed", table, object_id, {"object_type": object_type})
        return {
            "object_type": object_type,
            "record": row,
            "explainability": {
                "source_tables": [table], "automatic_confirmation": False, "human_review_required": True,
                "limitations": ["Die Ansicht zeigt gespeicherte Daten; sie führt keine unabhängige Wahrheitsprüfung durch."],
            },
        }

    def save_preference(self, case_id: str, actor: str, active_section: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        self._case(case_id)
        if active_section not in self.SECTIONS:
            raise WorkspaceValidationError("unknown section")
        if not actor.strip():
            raise WorkspaceValidationError("actor required")
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO workspace_preferences_122(case_id,actor,active_section,filters_json,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(case_id,actor) DO UPDATE SET active_section=excluded.active_section,filters_json=excluded.filters_json,updated_at=excluded.updated_at",
                (case_id, actor, active_section, _json(filters or {}), _now()),
            )
            self._log(case_id, actor, "workspace_preference_saved", "workspace_preferences_122", f"{case_id}:{actor}", {"active_section": active_section, "filters": filters or {}})
        return {"case_id": case_id, "actor": actor, "active_section": active_section, "filters": filters or {}}

    def preference(self, case_id: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        row = self.db.one("SELECT * FROM workspace_preferences_122 WHERE case_id=? AND actor=?", (case_id, actor))
        if not row:
            return {"case_id": case_id, "actor": actor, "active_section": "overview", "filters": {}}
        return {"case_id": case_id, "actor": actor, "active_section": row["active_section"], "filters": json.loads(row["filters_json"] or "{}")}

    def recent_actions(self, case_id: str, limit: int = 50) -> list[dict[str, Any]]:
        self._case(case_id)
        limit = max(1, min(int(limit), 200))
        return self.db.all("SELECT * FROM workspace_actions_122 WHERE case_id=? ORDER BY sequence DESC LIMIT ?", (case_id, limit))

    def recovery_events(self, case_id: str, limit: int = 50) -> list[dict[str, Any]]:
        self._case(case_id)
        limit = max(1, min(int(limit), 200))
        return self.db.all("SELECT * FROM workspace_recovery_1221 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, limit))
