from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POLICY_VERSION = "phase15.object-store.v1"
_DANGEROUS_MEDIA = {
    "application/x-msdownload", "application/x-dosexec", "application/x-executable",
    "application/vnd.microsoft.portable-executable", "application/x-sh", "application/x-bat",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha_json(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


class LocalCASObjectStore:
    backend_id = "local_cas_v1"

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for zone in ("objects", "quarantine"):
            (self.root / zone / "sha256").mkdir(parents=True, exist_ok=True)

    def _path(self, digest: str, zone: str) -> Path:
        if zone not in {"objects", "quarantine"}:
            raise ValueError("invalid object-store zone")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid sha256")
        return self.root / zone / "sha256" / digest[:2] / digest[2:4] / digest

    def put_bytes(self, data: bytes, *, quarantine: bool = False) -> dict[str, Any]:
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("object content must be bytes")
        content = bytes(data)
        digest = hashlib.sha256(content).hexdigest()
        zone = "quarantine" if quarantine else "objects"
        target = self._path(digest, zone)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            fd, tmp_name = tempfile.mkstemp(prefix=".ee-object-", dir=str(target.parent))
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                Path(tmp_name).replace(target)
            finally:
                try:
                    Path(tmp_name).unlink(missing_ok=True)
                except OSError:
                    pass
        try:
            target.chmod(0o600)
        except OSError:
            pass
        return {
            "backend_id": self.backend_id,
            "object_key": target.relative_to(self.root).as_posix(),
            "sha256": digest,
            "size_bytes": len(content),
            "quarantined": quarantine,
        }

    def read_bytes(self, object_key: str, expected_sha256: str) -> bytes:
        path = (self.root / str(object_key)).resolve()
        if self.root not in path.parents:
            raise PermissionError("object key escapes store root")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_sha256:
            raise IOError("object hash verification failed")
        return data


class S3CompatibleObjectStore:
    """S3-compatible adapter. No connection occurs until a method is called."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        prefix: str = "eagleeye/phase15",
        sse: str = "AES256",
        kms_key_id: str | None = None,
        client: Any | None = None,
    ) -> None:
        if sse not in {"AES256", "aws:kms"}:
            raise ValueError("S3 server-side encryption must be AES256 or aws:kms")
        if sse == "aws:kms" and not kms_key_id:
            raise ValueError("kms_key_id required for aws:kms")
        self.bucket = str(bucket).strip()
        self.endpoint_url = str(endpoint_url).strip()
        self.prefix = str(prefix).strip("/")
        self.sse = sse
        self.kms_key_id = kms_key_id
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3  # type: ignore
            self._client = boto3.client("s3", endpoint_url=self.endpoint_url)
        return self._client

    def put_bytes(self, data: bytes, *, quarantine: bool = False) -> dict[str, Any]:
        content = bytes(data)
        digest = hashlib.sha256(content).hexdigest()
        zone = "quarantine" if quarantine else "objects"
        key = f"{self.prefix}/{zone}/sha256/{digest[:2]}/{digest[2:4]}/{digest}"
        kwargs: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": content,
            "ServerSideEncryption": self.sse,
            "Metadata": {"sha256": digest, "eagleeye-policy": POLICY_VERSION},
        }
        if self.sse == "aws:kms":
            kwargs["SSEKMSKeyId"] = self.kms_key_id
        self._get_client().put_object(**kwargs)
        return {"backend_id": "s3_compatible_v1", "object_key": key, "sha256": digest, "size_bytes": len(content), "quarantined": quarantine}

    def read_bytes(self, object_key: str, expected_sha256: str) -> bytes:
        response = self._get_client().get_object(Bucket=self.bucket, Key=object_key)
        body = response["Body"].read()
        if hashlib.sha256(body).hexdigest() != expected_sha256:
            raise IOError("S3 object hash verification failed")
        return body


class ObjectStoreCoordinator:
    def __init__(self, db: Any, store: LocalCASObjectStore, *, actor: str = "local-analyst") -> None:
        self.db = db
        self.store = store
        self.actor = actor
        self._register_local_backend()

    def _register_local_backend(self) -> None:
        now = _now()
        config = {"content_addressed": True, "sha256_verify_on_read": True, "quarantine_zone": True, "network": False, "policy": POLICY_VERSION}
        body = {
            "backend_id": self.store.backend_id,
            "backend_kind": "local_cas",
            "role": "object_store",
            "status": "active",
            "config_json": _canon(config),
            "live_validated": 1,
            "last_checked_at": now,
            "created_at": now,
        }
        self.db.execute(
            "INSERT OR IGNORE INTO phase15_data_backends(backend_id,backend_kind,role,status,config_json,live_validated,last_checked_at,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?)",
            (*body.values(), _sha_json(body)),
        )

    def ingest(
        self,
        *,
        case_id: str,
        content: bytes,
        media_type: str,
        search_run_id: str | None = None,
        source_id: str | None = None,
        provenance: dict[str, Any] | None = None,
        security_state: str | None = None,
        actor: str | None = None,
    ) -> dict[str, Any]:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)
        mt = str(media_type or "application/octet-stream").strip().lower()[:160]
        search_kind = None
        if search_run_id:
            run = self.db.one("SELECT case_id,search_kind FROM phase15_search_runs WHERE search_run_id=?", (search_run_id,))
            if not run or run["case_id"] != case_id:
                raise PermissionError("search_run_id must belong to the case")
            search_kind = run["search_kind"]
        source = None
        if source_id:
            source = self.db.one("SELECT source_id,source_kind,review_status,locator FROM phase15_sources WHERE source_id=?", (source_id,))
            if not source:
                raise KeyError(source_id)
        if search_kind == "darknet":
            if not source or source["source_kind"] != "darknet_onion" or source["review_status"] != "approved_read_only":
                raise PermissionError("darknet artifacts require the reviewed source_id used for the research")
            if not search_run_id:
                raise PermissionError("darknet artifacts require search_run_id")
        danger = mt in _DANGEROUS_MEDIA or any(x in mt for x in ("executable", "x-msdownload", "x-dosexec"))
        state = security_state or ("quarantined" if search_kind == "darknet" or danger else "review_pending")
        if state not in {"quarantined", "review_pending", "safe_text", "reviewed_safe"}:
            raise ValueError("invalid security_state")
        # Darknet handoffs and executable-like content always enter the physical quarantine zone.
        # A later human review is an append-only event and never rewrites the original ingest state.
        quarantine = search_kind == "darknet" or state == "quarantined" or danger
        stored = self.store.put_bytes(content, quarantine=quarantine)
        oid = "obj_" + uuid.uuid4().hex[:24]
        now = _now()
        prov = {
            "policy": POLICY_VERSION,
            "case_id": case_id,
            "search_run_id": search_run_id,
            "source_id": source_id,
            "source_locator": source["locator"] if source else None,
            "ingest_mode": "gateway_or_local_handoff",
            "runtime_fetch_performed_by_build347": False,
            **(provenance or {}),
        }
        body = {
            "object_id": oid,
            "case_id": case_id,
            "search_run_id": search_run_id,
            "source_id": source_id,
            "backend_id": stored["backend_id"],
            "object_key": stored["object_key"],
            "sha256": stored["sha256"],
            "size_bytes": stored["size_bytes"],
            "media_type": mt,
            "security_state": "quarantined" if quarantine else state,
            "provenance_json": _canon(prov),
            "created_by": actor or self.actor,
            "created_at": now,
        }
        self.db.execute(
            """INSERT INTO phase15_objects(
               object_id,case_id,search_run_id,source_id,backend_id,object_key,sha256,size_bytes,media_type,security_state,provenance_json,created_by,created_at,record_hash
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (*body.values(), _sha_json(body)),
        )
        self._event(oid, "ingest", body["security_state"], actor or self.actor, {"sha256": stored["sha256"], "size_bytes": stored["size_bytes"]})
        return {**body, "provenance": prov, "quarantined": quarantine}

    def _event(self, object_id: str, event_type: str, decision: str, actor: str, details: dict[str, Any]) -> dict[str, Any]:
        event = {
            "event_id": "oev_" + uuid.uuid4().hex[:24],
            "object_id": object_id,
            "event_type": event_type,
            "decision": decision,
            "actor": actor,
            "details_json": _canon(details),
            "created_at": _now(),
        }
        self.db.execute(
            "INSERT INTO phase15_object_events(event_id,object_id,event_type,decision,actor,details_json,created_at,record_hash) VALUES(?,?,?,?,?,?,?,?)",
            (*event.values(), _sha_json(event)),
        )
        return event

    def review(self, object_id: str, *, decision: str, rationale: str, reviewer: str | None = None) -> dict[str, Any]:
        row = self.db.one("SELECT object_id,security_state FROM phase15_objects WHERE object_id=?", (object_id,))
        if not row:
            raise KeyError(object_id)
        if decision not in {"approve_safe", "keep_quarantined", "reject"}:
            raise ValueError("invalid object review decision")
        return self._event(object_id, "human_review", decision, reviewer or self.actor, {"rationale": str(rationale)[:4000], "original_security_state": row["security_state"]})

    def metadata(self, object_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase15_objects WHERE object_id=?", (object_id,))
        if not row:
            raise KeyError(object_id)
        row["provenance"] = json.loads(row.pop("provenance_json"))
        return row

    def read_verified(self, object_id: str) -> bytes:
        row = self.metadata(object_id)
        return self.store.read_bytes(row["object_key"], row["sha256"])

    def list_objects(self, *, case_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        n = max(1, min(int(limit), 500))
        if case_id:
            return self.db.all("SELECT object_id,case_id,search_run_id,source_id,backend_id,sha256,size_bytes,media_type,security_state,created_at FROM phase15_objects WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, n))
        return self.db.all("SELECT object_id,case_id,search_run_id,source_id,backend_id,sha256,size_bytes,media_type,security_state,created_at FROM phase15_objects ORDER BY created_at DESC LIMIT ?", (n,))

    def status(self) -> dict[str, Any]:
        row = self.db.one("SELECT COUNT(*) c,COALESCE(SUM(size_bytes),0) b FROM phase15_objects") or {"c": 0, "b": 0}
        q = self.db.one("SELECT COUNT(*) c FROM phase15_objects WHERE security_state='quarantined'") or {"c": 0}
        return {"policy": POLICY_VERSION, "backend_id": self.store.backend_id, "objects": int(row["c"]), "bytes": int(row["b"]), "quarantined": int(q["c"]), "network": False, "hash_verify_on_read": True}
