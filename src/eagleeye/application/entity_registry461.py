"""Build 461: case-scoped, provenance-first entity and relationship registry.

No automatic identity resolution, guilt inference, or evidence verification.
This module is intentionally a local persistence layer, not a public API.
"""
from __future__ import annotations

from datetime import date
import sqlite3
from pathlib import Path
from uuid import uuid4

KINDS = frozenset({"person", "organization", "company", "place", "event", "document"})
RELATION_STATES = frozenset({"hypothesis", "supported", "disputed", "rejected"})
SOURCE_STATES = frozenset({"unreviewed", "reviewed"})


class EntityRegistry461:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.db_path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS entity461 (
                id TEXT PRIMARY KEY, case_id TEXT NOT NULL, kind TEXT NOT NULL,
                label TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS entity461_case ON entity461(case_id,kind);
            CREATE TABLE IF NOT EXISTS relation461 (
                id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
                source_id TEXT NOT NULL REFERENCES entity461(id),
                target_id TEXT NOT NULL REFERENCES entity461(id),
                predicate TEXT NOT NULL, state TEXT NOT NULL,
                valid_from TEXT, valid_until TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK(source_id != target_id)
            );
            CREATE INDEX IF NOT EXISTS relation461_case ON relation461(case_id,state);
            CREATE TABLE IF NOT EXISTS relation_source461 (
                relation_id TEXT NOT NULL REFERENCES relation461(id) ON DELETE CASCADE,
                source_ref TEXT NOT NULL,
                review_state TEXT NOT NULL DEFAULT 'unreviewed',
                PRIMARY KEY (relation_id,source_ref)
            );
        """)
        self.db.commit()

    @staticmethod
    def _required(value: str, field: str, maximum: int = 512) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(f"{field} must be nonempty and at most {maximum} characters")
        return value.strip()

    def create_entity(self, *, case_id: str, kind: str, label: str, notes: str = "") -> dict:
        case_id = self._required(case_id, "case_id", 128)
        if kind not in KINDS:
            raise ValueError("unsupported entity kind")
        label = self._required(label, "label")
        if not isinstance(notes, str) or len(notes) > 10000:
            raise ValueError("invalid notes")
        item_id = uuid4().hex
        with self.db:
            self.db.execute(
                "INSERT INTO entity461(id,case_id,kind,label,notes) VALUES(?,?,?,?,?)",
                (item_id, case_id, kind, label, notes),
            )
        return {"id": item_id, "case_id": case_id, "kind": kind, "label": label, "notes": notes}

    def create_relation(
        self, *, case_id: str, source_id: str, target_id: str,
        predicate: str, source_refs: list[str], state: str = "hypothesis",
        valid_from: str | None = None, valid_until: str | None = None
    ) -> dict:
        case_id = self._required(case_id, "case_id", 128)
        predicate = self._required(predicate, "predicate", 128)
        if state not in RELATION_STATES:
            raise ValueError("invalid relation state")
        if source_id == target_id:
            raise ValueError("self relation forbidden")
        if not isinstance(source_refs, list) or not source_refs or len(source_refs) > 50:
            raise ValueError("at least one source reference required (max 50)")
        refs = [self._required(ref, "source_ref", 256) for ref in source_refs]
        if len(set(refs)) != len(refs):
            raise ValueError("duplicate source reference")
        for bound_name, bound in (("valid_from", valid_from), ("valid_until", valid_until)):
            if bound is not None:
                if not isinstance(bound, str):
                    raise ValueError(f"{bound_name} must be ISO YYYY-MM-DD")
                try:
                    parsed = date.fromisoformat(bound)
                except ValueError as exc:
                    raise ValueError(f"{bound_name} must be ISO YYYY-MM-DD") from exc
                if bound != parsed.isoformat():
                    raise ValueError(f"{bound_name} must be canonical ISO YYYY-MM-DD")
        if valid_from is not None and valid_until is not None and valid_from > valid_until:
            raise ValueError("invalid date interval")
        with self.db:
            existing = self.db.execute(
                "SELECT id FROM entity461 WHERE case_id=? AND id IN (?,?)",
                (case_id, source_id, target_id),
            ).fetchall()
            if len(existing) != 2:
                raise ValueError("both entities must exist in the same case")
            relation_id = uuid4().hex
            self.db.execute(
                "INSERT INTO relation461(id,case_id,source_id,target_id,predicate,state,valid_from,valid_until) VALUES(?,?,?,?,?,?,?,?)",
                (relation_id, case_id, source_id, target_id, predicate, state, valid_from, valid_until),
            )
            self.db.executemany(
                "INSERT INTO relation_source461(relation_id,source_ref) VALUES(?,?)",
                [(relation_id, ref) for ref in refs],
            )
        return {"id": relation_id, "case_id": case_id, "state": state, "source_refs": refs,
                "source_verified": False}

    def graph(self, case_id: str) -> dict:
        case_id = self._required(case_id, "case_id", 128)
        self.db.row_factory = sqlite3.Row
        entities = [dict(r) for r in self.db.execute(
            "SELECT id,case_id,kind,label,notes FROM entity461 WHERE case_id=? ORDER BY id", (case_id,)
        )]
        relations = []
        for row in self.db.execute(
            "SELECT id,case_id,source_id,target_id,predicate,state,valid_from,valid_until "
            "FROM relation461 WHERE case_id=? ORDER BY id", (case_id,)
        ):
            relation = dict(row)
            relation["sources"] = [dict(x) for x in self.db.execute(
                "SELECT source_ref,review_state FROM relation_source461 WHERE relation_id=? ORDER BY source_ref",
                (relation["id"],),
            )]
            relation["source_verified"] = False
            relations.append(relation)
        return {"case_id": case_id, "entities": entities, "relations": relations,
                "source_verification": "external_review_required"}

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
