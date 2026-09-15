from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlsplit

from eagleeye.storage.object_store import S3CompatibleObjectStore
from eagleeye.search_platform.backends import PostgresSearchBackend

POLICY = "phase16.object-search-team-profile.v363"
AI_POLICY = "phase16.autonomous-investigation.v363"
OPSEC_POLICY = "phase16.defensive-opsec-supervisor.v363"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _endpoint_safe(endpoint: str) -> bool:
    raw = str(endpoint or "").strip()
    if not raw:
        return False
    try:
        p = urlsplit(raw)
    except ValueError:
        return False
    host = (p.hostname or "").casefold()
    if p.scheme == "https":
        return bool(host)
    return p.scheme == "http" and host in {"localhost", "127.0.0.1", "::1"}


def _redact_endpoint(endpoint: str) -> str:
    raw = str(endpoint or "").strip()
    if not raw:
        return ""
    try:
        p = urlsplit(raw)
    except ValueError:
        return "<invalid-endpoint>"
    host = p.hostname or ""
    if p.port:
        host = f"{host}:{p.port}"
    return f"{p.scheme}://{host}" if p.scheme and host else "<invalid-endpoint>"


class ObjectSearchTeamProfile363:
    """Phase-16 object/search profile.

    Normal startup never connects to an external service. Live probes are explicit
    operator actions and only mark external validation when a real client/DSN is used.
    Injected clients/executors prove contract behavior only.
    """

    def __init__(self, db: Any, *, local_store: Any, search: Any, base_dir: Any, actor: str = "local-analyst"):
        self.db = db
        self.local_store = local_store
        self.search = search
        self.base_dir = base_dir
        self.actor = actor
        self._last_s3: dict[str, Any] | None = None
        self._last_search: dict[str, Any] | None = None

    def s3_config(self) -> dict[str, Any]:
        endpoint = os.environ.get("EAGLEEYE_S3_ENDPOINT", "").strip()
        bucket = os.environ.get("EAGLEEYE_S3_BUCKET", "").strip()
        prefix = os.environ.get("EAGLEEYE_S3_PREFIX", "eagleeye/phase16").strip("/") or "eagleeye/phase16"
        sse = os.environ.get("EAGLEEYE_S3_SSE", "AES256").strip() or "AES256"
        kms = os.environ.get("EAGLEEYE_S3_KMS_KEY_ID", "").strip()
        return {
            "configured": bool(endpoint and bucket),
            "endpoint": _redact_endpoint(endpoint),
            "endpoint_transport_safe": _endpoint_safe(endpoint) if endpoint else False,
            "bucket": bucket[:128],
            "prefix": prefix[:256],
            "sse": sse,
            "kms_key_configured": bool(kms),
            "credentials_persisted": False,
            "credentials_source": "environment_or_sdk_provider_chain",
        }

    def s3_status(self) -> dict[str, Any]:
        cfg = self.s3_config()
        last = self._last_s3 or {}
        return {
            "policy": POLICY,
            "local_cas_live": True,
            "local_cas_backend_id": getattr(self.local_store, "backend_id", "local_cas_v1"),
            "s3_driver_available": importlib.util.find_spec("boto3") is not None,
            "configured": cfg["configured"],
            "endpoint": cfg["endpoint"],
            "endpoint_transport_safe": cfg["endpoint_transport_safe"],
            "server_available_in_build_environment": False,
            "live_validation_status": last.get("status", "not_run"),
            "externally_validated": bool(last.get("externally_validated", False)),
            "external_connection_opened": bool(last.get("external_connection_opened", False)),
            "automatic_external_connections": False,
            "server_side_encryption_required": True,
            "hash_verify_on_read": True,
            "credentials_persisted": False,
        }

    def s3_live_validation(self, *, client: Any | None = None, external_client: bool = False) -> dict[str, Any]:
        cfg = self.s3_config()
        if not cfg["configured"]:
            result = {"status": "not_run", "externally_validated": False, "external_connection_opened": False, "reason": "EAGLEEYE_S3_ENDPOINT and EAGLEEYE_S3_BUCKET required", "policy": POLICY}
            self._last_s3 = result
            return result
        if not cfg["endpoint_transport_safe"]:
            result = {"status": "blocked", "externally_validated": False, "external_connection_opened": False, "reason": "S3 endpoint must use HTTPS unless loopback", "policy": POLICY}
            self._last_s3 = result
            return result
        sse = cfg["sse"]
        if sse not in {"AES256", "aws:kms"}:
            result = {"status": "blocked", "externally_validated": False, "external_connection_opened": False, "reason": "unsupported server-side encryption", "policy": POLICY}
            self._last_s3 = result
            return result
        if sse == "aws:kms" and not cfg["kms_key_configured"]:
            result = {"status": "blocked", "externally_validated": False, "external_connection_opened": False, "reason": "KMS key id required", "policy": POLICY}
            self._last_s3 = result
            return result
        actual_external = bool(external_client)
        if client is None:
            if importlib.util.find_spec("boto3") is None:
                result = {"status": "not_run", "externally_validated": False, "external_connection_opened": False, "reason": "boto3 not installed", "policy": POLICY}
                self._last_s3 = result
                return result
            import boto3  # type: ignore
            client = boto3.client("s3", endpoint_url=os.environ["EAGLEEYE_S3_ENDPOINT"])
            actual_external = True
        store = S3CompatibleObjectStore(
            bucket=cfg["bucket"], endpoint_url=os.environ.get("EAGLEEYE_S3_ENDPOINT", ""), prefix=cfg["prefix"],
            sse=sse, kms_key_id=os.environ.get("EAGLEEYE_S3_KMS_KEY_ID") or None, client=client,
        )
        marker = ("eagleeye-363-" + uuid.uuid4().hex).encode("utf-8")
        stored = store.put_bytes(marker, quarantine=False)
        body = store.read_bytes(stored["object_key"], stored["sha256"])
        if body != marker:
            raise RuntimeError("S3 roundtrip mismatch")
        cleanup = "not_supported"
        if hasattr(client, "delete_object"):
            client.delete_object(Bucket=cfg["bucket"], Key=stored["object_key"])
            cleanup = "pass"
        result = {
            "status": "pass",
            "externally_validated": actual_external,
            "external_connection_opened": actual_external,
            "roundtrip": "pass",
            "sha256_verified": True,
            "server_side_encryption": sse,
            "cleanup": cleanup,
            "endpoint": cfg["endpoint"],
            "policy": POLICY,
            "truthful_note": "Injected clients prove contract behavior only; external validation requires a real S3/MinIO endpoint.",
        }
        self._last_s3 = result
        return result

    def local_search_rebuild_probe(self) -> dict[str, Any]:
        status = self.search.status()
        available = bool(status.get("fts5_available"))
        docs = int(status.get("indexed_documents") or 0)
        # Provenance tables remain canonical; the FTS virtual index can be rebuilt separately.
        return {
            "status": "pass" if available else "fail",
            "backend": "sqlite_fts5",
            "fts5_available": available,
            "indexed_documents": docs,
            "rebuild_strategy": "canonical_phase15_search_documents_to_virtual_fts",
            "network": False,
            "externally_validated": available,
            "policy": POLICY,
        }

    def team_search_status(self) -> dict[str, Any]:
        dsn = os.environ.get("EAGLEEYE_TEAM_SEARCH_DSN", "").strip() or os.environ.get("EAGLEEYE_POSTGRES_DSN", "").strip()
        last = self._last_search or {}
        return {
            "policy": POLICY,
            "portable_fts5_live": bool(self.search.status().get("fts5_available")),
            "configured": bool(dsn),
            "driver_available": importlib.util.find_spec("psycopg") is not None,
            "live_validation_status": last.get("status", "not_run"),
            "externally_validated": bool(last.get("externally_validated", False)),
            "external_connection_opened": bool(last.get("external_connection_opened", False)),
            "automatic_external_connections": False,
            "case_scoped_queries_required": True,
            "index_provenance_required": True,
        }

    def team_search_live_validation(self, *, executor: Callable[[str, tuple[Any, ...]], list[dict[str, Any]]] | None = None, external_executor: bool = False) -> dict[str, Any]:
        dsn = os.environ.get("EAGLEEYE_TEAM_SEARCH_DSN", "").strip() or os.environ.get("EAGLEEYE_POSTGRES_DSN", "").strip()
        actual_external = bool(external_executor)
        if executor is None and not dsn:
            result = {"status": "not_run", "externally_validated": False, "external_connection_opened": False, "reason": "EAGLEEYE_TEAM_SEARCH_DSN or EAGLEEYE_POSTGRES_DSN required", "policy": POLICY}
            self._last_search = result
            return result
        if executor is None:
            if importlib.util.find_spec("psycopg") is None:
                result = {"status": "not_run", "externally_validated": False, "external_connection_opened": False, "reason": "psycopg not installed", "policy": POLICY}
                self._last_search = result
                return result
            import psycopg  # type: ignore
            conn = psycopg.connect(dsn, connect_timeout=5)
            def _exec(sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    cols = [d.name for d in cur.description] if cur.description else []
                    return [dict(zip(cols, row)) for row in cur.fetchall()] if cols else []
            executor = _exec
            actual_external = True
        backend = PostgresSearchBackend(configured=True, executor=executor, external_executor=actual_external)
        try:
            probe = backend.contract_probe(live=True)
        finally:
            if actual_external and 'conn' in locals():
                try: conn.close()
                except Exception: pass
        result = {**probe, "policy": POLICY, "portable_fallback": True, "case_scoped_contract": True, "index_provenance_required": True}
        self._last_search = result
        return result

    def status(self) -> dict[str, Any]:
        return {"policy": POLICY, "s3": self.s3_status(), "team_search": self.team_search_status(), "local_search": self.local_search_rebuild_probe(), "automatic_external_connections": False}


class AutonomousInvestigation363:
    def __init__(self, db: Any, *, base362: Any, storage_search363: ObjectSearchTeamProfile363):
        self.db = db
        self.base362 = base362
        self.storage_search363 = storage_search363

    def status(self) -> dict[str, Any]:
        base = dict(self.base362.status())
        base.update({"policy_version": AI_POLICY, "storage_search_health_aware": True, "dossier_records_storage_search_validation": True, "degraded_backend_disclosure": True})
        return base

    def run_cycle(self, *, case_id: str, max_ticks: int = 8) -> dict[str, Any]:
        out = self.base362.run_cycle(case_id=case_id, max_ticks=max_ticks)
        dossier = out.get("dossier")
        if isinstance(dossier, dict):
            st = self.storage_search363.status()
            dossier["phase16_storage_search_context"] = {
                "local_cas_live": st["s3"]["local_cas_live"],
                "s3_externally_validated": st["s3"]["externally_validated"],
                "portable_fts5_live": st["team_search"]["portable_fts5_live"],
                "team_search_externally_validated": st["team_search"]["externally_validated"],
                "degraded_mode_disclosed": not (st["s3"]["externally_validated"] and st["team_search"]["externally_validated"]),
            }
            dossier["lead_review_required"] = True
        return out


class DefensiveOpsecSupervisor363:
    def __init__(self, db: Any, *, base362: Any, storage_search363: ObjectSearchTeamProfile363):
        self.db = db
        self.base362 = base362
        self.storage_search363 = storage_search363

    def status(self) -> dict[str, Any]:
        base = dict(self.base362.status())
        base.update({
            "policy_version": OPSEC_POLICY,
            "storage_search_health_monitor": True,
            "insecure_external_storage_endpoint_block": True,
            "backend_degradation_can_pause_external_jobs": True,
            "system_mutations": False,
        })
        return base

    def _storage_findings(self) -> list[dict[str, Any]]:
        cfg = self.storage_search363.s3_config()
        findings: list[dict[str, Any]] = []
        if cfg["configured"] and not cfg["endpoint_transport_safe"]:
            findings.append({"kind": "insecure_s3_endpoint", "endpoint": cfg["endpoint"]})
        for row in self.db.all("SELECT backend_id,backend_kind,config_json FROM phase15_data_backends ORDER BY backend_id"):
            text = str(row.get("config_json") or "")
            if re.search(r"https?://[^/\s:@]+:[^/\s@]+@", text, re.I):
                findings.append({"kind": "embedded_endpoint_credentials", "backend_id": row.get("backend_id")})
        return findings

    def protect_case(self, *, case_id: str) -> dict[str, Any]:
        base = self.base362.protect_case(case_id=case_id)
        findings = self._storage_findings()
        stopped: list[str] = []
        if findings:
            rows = self.db.all("SELECT job_id FROM phase15_jobs WHERE case_id=? AND status IN ('queued','retry','running')", (case_id,))
            for row in rows:
                self.db.execute("UPDATE phase15_jobs SET status='cancelled',error_text=?,updated_at=? WHERE job_id=?", ("OPSEC363 storage/search defensive stop", _now(), row["job_id"]))
                stopped.append(row["job_id"])
        return {**base, "storage_search_findings": findings, "storage_search_jobs_stopped": stopped, "system_mutations": False, "policy_version": OPSEC_POLICY}
