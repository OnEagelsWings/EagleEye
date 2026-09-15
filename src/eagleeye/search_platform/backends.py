from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

POLICY_VERSION = "phase15.search-backend.v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _fts_query(text: str) -> str:
    tokens = re.findall(r"[\w@.+-]+", str(text or ""), flags=re.UNICODE)
    if not tokens:
        raise ValueError("non-empty search terms required")
    # Phrase-safe tokens; no raw MATCH operators cross the contract boundary.
    return " AND ".join('"' + t.replace('"', '""') + '"' for t in tokens[:24])


class FTS5SearchBackend:
    """Portable local search backend.

    Only reviewed/indexable text is accepted. The backend never performs network I/O
    and never reads object-store bytes by itself; callers must hand it approved text.
    """

    kind = "sqlite_fts5"

    def __init__(self, db: Any) -> None:
        self.db = db

    def available(self) -> bool:
        try:
            row = self.db.one("SELECT sqlite_compileoption_used('ENABLE_FTS5') enabled") or {"enabled": 0}
            if int(row["enabled"]) == 1:
                return True
        except Exception:
            pass
        try:
            self.db.one("SELECT COUNT(*) c FROM phase15_search_fts")
            return True
        except Exception:
            return False

    def index_document(
        self,
        *,
        doc_id: str,
        case_id: str,
        title: str,
        body: str,
        object_id: str | None = None,
        source_id: str | None = None,
        security_state: str = "reviewed_safe",
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if security_state not in {"reviewed_safe", "public", "local_safe"}:
            raise PermissionError("document security state is not indexable")
        text = str(body or "")
        if not text.strip():
            raise ValueError("document body required")
        if len(text.encode("utf-8")) > 2 * 1024 * 1024:
            raise ValueError("document exceeds local indexing limit")
        now = _now()
        body_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        row = {
            "doc_id": str(doc_id)[:128],
            "case_id": str(case_id)[:128],
            "object_id": str(object_id or "")[:128],
            "source_id": str(source_id or "")[:128],
            "title": str(title or "")[:1000],
            "body_sha256": body_hash,
            "security_state": security_state,
            "provenance_json": _canon(provenance or {}),
            "created_at": now,
            "updated_at": now,
        }
        row["record_hash"] = _sha(row)
        with self.db.transaction(immediate=True):
            existing = self.db.one("SELECT doc_id FROM phase15_search_documents WHERE doc_id=?", (row["doc_id"],))
            if existing:
                self.db.execute(
                    "UPDATE phase15_search_documents SET case_id=?,object_id=?,source_id=?,title=?,body_sha256=?,security_state=?,provenance_json=?,updated_at=?,record_hash=? WHERE doc_id=?",
                    (row["case_id"], row["object_id"], row["source_id"], row["title"], row["body_sha256"], row["security_state"], row["provenance_json"], row["updated_at"], row["record_hash"], row["doc_id"]),
                )
                self.db.execute("DELETE FROM phase15_search_fts WHERE doc_id=?", (row["doc_id"],))
            else:
                self.db.execute(
                    "INSERT INTO phase15_search_documents(doc_id,case_id,object_id,source_id,title,body_sha256,security_state,provenance_json,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(row[k] for k in ("doc_id","case_id","object_id","source_id","title","body_sha256","security_state","provenance_json","created_at","updated_at","record_hash")),
                )
            self.db.execute("INSERT INTO phase15_search_fts(doc_id,case_id,title,body) VALUES(?,?,?,?)", (row["doc_id"], row["case_id"], row["title"], text))
        return {**row, "backend": self.kind, "body_bytes": len(text.encode("utf-8"))}

    def search(self, *, case_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        q = _fts_query(query)
        n = max(1, min(int(limit), 100))
        rows = self.db.all(
            """SELECT d.doc_id,d.case_id,d.object_id,d.source_id,d.title,d.body_sha256,d.security_state,d.provenance_json,
                      bm25(phase15_search_fts) AS score,
                      snippet(phase15_search_fts,3,'[',']','…',20) AS snippet
               FROM phase15_search_fts
               JOIN phase15_search_documents d ON d.doc_id=phase15_search_fts.doc_id
               WHERE phase15_search_fts MATCH ? AND phase15_search_fts.case_id=?
               ORDER BY score ASC LIMIT ?""",
            (q, str(case_id), n),
        )
        for row in rows:
            try:
                row["provenance"] = json.loads(row.pop("provenance_json") or "{}")
            except Exception:
                row["provenance"] = {}
        return rows

    def delete_document(self, doc_id: str) -> None:
        with self.db.transaction(immediate=True):
            self.db.execute("DELETE FROM phase15_search_fts WHERE doc_id=?", (str(doc_id),))
            self.db.execute("DELETE FROM phase15_search_documents WHERE doc_id=?", (str(doc_id),))

    def contract_probe(self) -> dict[str, Any]:
        return {
            "backend_kind": self.kind,
            "available": self.available(),
            "network_execution": False,
            "external_connection_opened": False,
            "policy": POLICY_VERSION,
        }


class PostgresSearchBackend:
    """Opt-in PostgreSQL FTS contract. Never auto-connects.

    `executor` exists only for deterministic contract tests or a future explicitly
    configured repository. Supplying configuration alone never counts as live validation.
    """

    kind = "postgresql_fts"

    def __init__(self, *, configured: bool = False, executor: Callable[[str, tuple[Any, ...]], list[dict[str, Any]]] | None = None, external_executor: bool = False) -> None:
        self.configured = bool(configured)
        self.executor = executor
        self.external_executor = bool(external_executor)

    @property
    def driver_available(self) -> bool:
        return self.executor is not None or importlib.util.find_spec("psycopg") is not None

    def contract_probe(self, *, live: bool = False) -> dict[str, Any]:
        base = {
            "backend_kind": self.kind,
            "configured": self.configured,
            "driver_available": self.driver_available,
            "live_validated": False,
            "external_connection_opened": False,
        }
        if not live:
            return base | {"status": "not_run", "reason": "live search validation requires explicit operator action"}
        if self.executor is None:
            raise RuntimeError("no explicitly configured PostgreSQL search executor")
        marker = "probe-" + uuid.uuid4().hex
        result = self.executor("SELECT %s AS probe", (marker,))
        if not result or result[0].get("probe") != marker:
            raise RuntimeError("PostgreSQL search contract mismatch")
        return base | {"status": "pass", "contract_validated": True, "live_validated": self.external_executor, "external_connection_opened": self.external_executor}


class SearchCoordinator:
    def __init__(self, db: Any, *, actor: str = "local-analyst") -> None:
        self.db = db
        self.actor = actor
        self.local = FTS5SearchBackend(db)
        self._register_local()

    def _register_local(self) -> None:
        now = _now()
        body = {
            "backend_id": "fts5_portable_v1",
            "backend_kind": "sqlite_fts5",
            "status": "active" if self.local.available() else "unavailable",
            "config_json": _canon({"network": False, "case_scoped": True, "policy": POLICY_VERSION}),
            "live_validated": 1 if self.local.available() else 0,
            "created_at": now,
            "updated_at": now,
        }
        self.db.execute(
            "INSERT OR REPLACE INTO phase15_search_backends(backend_id,backend_kind,status,config_json,live_validated,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?)",
            (*body.values(), _sha(body)),
        )

    def status(self) -> dict[str, Any]:
        rows = self.db.all("SELECT backend_id,backend_kind,status,live_validated,updated_at FROM phase15_search_backends ORDER BY backend_id")
        docs = self.db.one("SELECT COUNT(*) c FROM phase15_search_documents") or {"c": 0}
        return {
            "policy": POLICY_VERSION,
            "portable_backend": "fts5_portable_v1",
            "fts5_available": self.local.available(),
            "indexed_documents": int(docs["c"]),
            "backends": rows,
            "external_connections_opened_on_boot": 0,
        }
