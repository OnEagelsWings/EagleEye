from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Mapping, Protocol

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

LIFECYCLE_STATES = {"registered", "sandbox", "production", "degraded", "suspended", "retired"}
CONTRACT_STATES = {"unaccepted", "accepted", "expired", "revoked"}
RUN_STATUSES = {"succeeded", "partial_success", "failed", "blocked"}
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConnectorSpec:
    connector_id: str
    display_name: str
    version: str
    base_url: str
    allowed_hosts: tuple[str, ...]
    lifecycle_status: str = "sandbox"
    contract_state: str = "unaccepted"
    parser_kind: str = "json_records"
    records_path: str = ""
    timeout_seconds: float = 10.0
    max_attempts: int = 2
    max_response_bytes: int = 2_000_000
    allowed_content_types: tuple[str, ...] = ("application/json",)
    terms_reference: str = ""


@dataclass(frozen=True)
class ConnectorRequest:
    connector_id: str
    params: Mapping[str, Any]
    case_id: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True)
class ConnectorResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes
    final_url: str


class ConnectorTransport(Protocol):
    def __call__(self, url: str, *, timeout: float, headers: Mapping[str, str]) -> ConnectorResponse: ...


def urllib_transport(url: str, *, timeout: float, headers: Mapping[str, str]) -> ConnectorResponse:
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read()
            return ConnectorResponse(int(response.status), dict(response.headers.items()), body, response.geturl())
    except urllib.error.HTTPError as exc:
        return ConnectorResponse(int(exc.code), dict(exc.headers.items()), exc.read(), exc.geturl())


REFERENCE_CONNECTORS: tuple[ConnectorSpec, ...] = (
    ConnectorSpec("openalex_people", "OpenAlex Authors", "1.0", "https://api.openalex.org/authors", ("api.openalex.org",), records_path="results", terms_reference="https://docs.openalex.org/"),
    ConnectorSpec("crossref_works", "Crossref Works", "1.0", "https://api.crossref.org/works", ("api.crossref.org",), records_path="message.items", terms_reference="https://www.crossref.org/documentation/retrieve-metadata/rest-api/"),
    ConnectorSpec("orcid_public", "ORCID Public API", "1.0", "https://pub.orcid.org/v3.0/search", ("pub.orcid.org",), records_path="result", terms_reference="https://info.orcid.org/documentation/features/public-api/"),
    ConnectorSpec("wikidata_sparql", "Wikidata Query Service", "1.0", "https://query.wikidata.org/sparql", ("query.wikidata.org",), records_path="results.bindings", terms_reference="https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service"),
    ConnectorSpec("gdelt_doc", "GDELT DOC 2.0", "1.0", "https://api.gdeltproject.org/api/v2/doc/doc", ("api.gdeltproject.org",), records_path="articles", terms_reference="https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"),
)


class Build154ConnectorRuntimeService:
    BUILD = "154.0"
    MISSION = "Connector Runtime 2.0"

    def __init__(self, db: Any, audit: Any, *, observability: Any | None = None,
                 actor: str = "system", transport: ConnectorTransport | None = None,
                 sleeper: Callable[[float], None] = time.sleep) -> None:
        self.db = db
        self.audit = audit
        self.observability = observability
        self.actor = actor
        self.transport = transport or urllib_transport
        self.sleeper = sleeper
        self._seed_reference_connectors()

    def _seed_reference_connectors(self) -> None:
        for spec in REFERENCE_CONNECTORS:
            if not self.db.one("SELECT connector_id FROM connector_specs_154 WHERE connector_id=?", (spec.connector_id,)):
                self.register(spec)

    @staticmethod
    def _validate_spec(spec: ConnectorSpec) -> None:
        if not spec.connector_id or not spec.connector_id.replace("_", "").isalnum():
            raise ValueError("Ungültige Connector-ID")
        parsed = urllib.parse.urlsplit(spec.base_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("Connector-Basis-URL muss HTTPS verwenden")
        if parsed.hostname.casefold() not in {h.casefold() for h in spec.allowed_hosts}:
            raise ValueError("Basis-Host fehlt in der Allowlist")
        if spec.lifecycle_status not in LIFECYCLE_STATES or spec.contract_state not in CONTRACT_STATES:
            raise ValueError("Ungültiger Lifecycle- oder Contract-Status")
        if not 0.1 <= spec.timeout_seconds <= 60:
            raise ValueError("Timeout außerhalb des erlaubten Bereichs")
        if not 1 <= spec.max_attempts <= 5:
            raise ValueError("Maximalversuche außerhalb des erlaubten Bereichs")
        if not 1024 <= spec.max_response_bytes <= 20_000_000:
            raise ValueError("Antwortgrößenlimit außerhalb des erlaubten Bereichs")

    def register(self, spec: ConnectorSpec) -> dict[str, Any]:
        self._validate_spec(spec)
        existing = self.db.one("SELECT created_at FROM connector_specs_154 WHERE connector_id=?", (spec.connector_id,))
        created = (existing or {}).get("created_at") or now_ts()
        updated = now_ts()
        self.db.execute(
            "INSERT OR REPLACE INTO connector_specs_154(connector_id,display_name,version,base_url,allowed_hosts_json,lifecycle_status,contract_state,parser_kind,records_path,timeout_seconds,max_attempts,max_response_bytes,allowed_content_types_json,terms_reference,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (spec.connector_id, spec.display_name, spec.version, spec.base_url, dumps(spec.allowed_hosts),
             spec.lifecycle_status, spec.contract_state, spec.parser_kind, spec.records_path,
             spec.timeout_seconds, spec.max_attempts, spec.max_response_bytes, dumps(spec.allowed_content_types),
             spec.terms_reference, created, updated),
        )
        self.audit.log("connector_registered_154", "connector", spec.connector_id, None,
                       {"version": spec.version, "lifecycle": spec.lifecycle_status, "contract": spec.contract_state})
        return self.get_spec(spec.connector_id)

    def set_activation(self, connector_id: str, *, lifecycle_status: str, contract_state: str,
                       actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"CONNECTOR 154 {connector_id} AKTIVIEREN":
            raise PermissionError("Explizite Connector-Freigabe fehlt")
        if lifecycle_status not in LIFECYCLE_STATES or contract_state not in CONTRACT_STATES:
            raise ValueError("Ungültiger Status")
        if lifecycle_status == "production" and contract_state != "accepted":
            raise ValueError("Produktivbetrieb erfordert einen akzeptierten Quellenvertrag")
        if not self.db.one("SELECT connector_id FROM connector_specs_154 WHERE connector_id=?", (connector_id,)):
            raise KeyError("Connector nicht gefunden")
        self.db.execute("UPDATE connector_specs_154 SET lifecycle_status=?,contract_state=?,updated_at=? WHERE connector_id=?",
                        (lifecycle_status, contract_state, now_ts(), connector_id))
        self.audit.log("connector_activation_154", "connector", connector_id, None,
                       {"lifecycle": lifecycle_status, "contract": contract_state, "actor": actor})
        return self.get_spec(connector_id)

    def get_spec(self, connector_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM connector_specs_154 WHERE connector_id=?", (connector_id,))
        if not row:
            raise KeyError("Connector nicht gefunden")
        row["allowed_hosts"] = tuple(loads(row.pop("allowed_hosts_json"), []))
        row["allowed_content_types"] = tuple(loads(row.pop("allowed_content_types_json"), []))
        return row

    @staticmethod
    def _safe_url(spec: Mapping[str, Any], params: Mapping[str, Any]) -> str:
        parsed = urllib.parse.urlsplit(str(spec["base_url"]))
        if parsed.scheme != "https" or parsed.hostname.casefold() not in {h.casefold() for h in spec["allowed_hosts"]}:
            raise PermissionError("Connector-Ziel verletzt HTTPS- oder Host-Policy")
        clean: list[tuple[str, str]] = []
        for key, value in params.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                clean.extend((str(key), str(item)) for item in value)
            else:
                clean.append((str(key), str(value)))
        query = urllib.parse.urlencode(clean, doseq=True)
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))

    @staticmethod
    def _retry_after(headers: Mapping[str, str], *, cap: float = 30.0) -> float:
        value = next((v for k, v in headers.items() if k.casefold() == "retry-after"), "")
        if not value:
            return 0.0
        try:
            return min(cap, max(0.0, float(value)))
        except ValueError:
            try:
                seconds = parsedate_to_datetime(value).timestamp() - time.time()
                return min(cap, max(0.0, seconds))
            except Exception:
                return 0.0

    @staticmethod
    def _extract_path(payload: Any, path: str) -> Any:
        current = payload
        if not path:
            return current
        for part in path.split("."):
            if not isinstance(current, Mapping) or part not in current:
                raise ValueError(f"Records-Pfad nicht gefunden: {path}")
            current = current[part]
        return current

    @staticmethod
    def _shape(records: list[Any]) -> dict[str, Any]:
        keys: dict[str, set[str]] = {}
        for record in records[:100]:
            if isinstance(record, Mapping):
                for key, value in record.items():
                    keys.setdefault(str(key), set()).add(type(value).__name__)
            else:
                keys.setdefault("$item", set()).add(type(record).__name__)
        return {key: sorted(types) for key, types in sorted(keys.items())}

    def execute(self, request: ConnectorRequest) -> dict[str, Any]:
        spec = self.get_spec(request.connector_id)
        if spec["lifecycle_status"] != "production" or spec["contract_state"] != "accepted":
            raise PermissionError("Connector ist nicht produktiv und vertraglich freigegeben")
        correlation_id = request.correlation_id or f"corr154_{uuid.uuid4().hex}"
        run_id = new_id("connrun154")
        started_wall = time.monotonic()
        self.db.execute(
            "INSERT INTO connector_runs_154(run_id,connector_id,correlation_id,case_id,query_json,status,started_at) VALUES(?,?,?,?,?,?,?)",
            (run_id, request.connector_id, correlation_id, request.case_id, dumps(dict(request.params)), "running", now_ts()),
        )
        job = None
        if self.observability is not None:
            job = self.observability.start_job(operation=f"connector:{request.connector_id}", component="connector_runtime_154",
                                               case_id=request.case_id, correlation_id=correlation_id,
                                               input_summary={"parameter_names": sorted(map(str, request.params.keys()))})
        url = self._safe_url(spec, request.params)
        attempts = 0
        response: ConnectorResponse | None = None
        error: Exception | None = None
        try:
            for attempts in range(1, int(spec["max_attempts"]) + 1):
                try:
                    response = self.transport(url, timeout=float(spec["timeout_seconds"]), headers={
                        "Accept": ", ".join(spec["allowed_content_types"]),
                        "User-Agent": "EagleEye-PersonOSINT/154 public-only review-first",
                    })
                    if response.status_code not in RETRYABLE_STATUS or attempts >= int(spec["max_attempts"]):
                        break
                    delay = self._retry_after(response.headers) or min(8.0, 0.5 * (2 ** (attempts - 1)))
                    self.sleeper(delay)
                except (TimeoutError, urllib.error.URLError, OSError) as exc:
                    error = exc
                    if attempts >= int(spec["max_attempts"]):
                        break
                    self.sleeper(min(8.0, 0.5 * (2 ** (attempts - 1))))
            if response is None:
                raise TimeoutError(str(error or "Connector ohne Antwort"))
            if len(response.body) > int(spec["max_response_bytes"]):
                raise ValueError("Connector-Antwort überschreitet das Größenlimit")
            content_type = next((v for k, v in response.headers.items() if k.casefold() == "content-type"), "").split(";", 1)[0].strip().casefold()
            if content_type not in {str(v).casefold() for v in spec["allowed_content_types"]}:
                raise ValueError(f"Unerlaubter Content-Type: {content_type or 'fehlend'}")
            if not 200 <= response.status_code < 300:
                outcome = "RATE_LIMITED" if response.status_code == 429 else "AUTH_REQUIRED" if response.status_code in {401,403} else "SOURCE_UNAVAILABLE"
                raise RuntimeError(f"HTTP {response.status_code}:{outcome}")
            payload = json.loads(response.body.decode("utf-8"))
            extracted = self._extract_path(payload, str(spec["records_path"]))
            records = extracted if isinstance(extracted, list) else [extracted]
            shape = self._shape(records)
            fingerprint = _digest(shape)
            previous = self.db.one("SELECT schema_fingerprint FROM connector_schema_history_154 WHERE connector_id=? ORDER BY observed_at DESC LIMIT 1", (request.connector_id,))
            drift = bool(previous and previous["schema_fingerprint"] != fingerprint)
            provenance = {
                "connector_id": request.connector_id, "connector_version": spec["version"],
                "requested_url_sha256": hashlib.sha256(url.encode()).hexdigest(),
                "final_url_sha256": hashlib.sha256(response.final_url.encode()).hexdigest(),
                "retrieved_at": now_ts(), "http_status": response.status_code,
                "body_sha256": hashlib.sha256(response.body).hexdigest(), "content_type": content_type,
                "review_required": True, "automatic_identity_confirmation": False,
            }
            duration = int((time.monotonic() - started_wall) * 1000)
            self.db.execute("UPDATE connector_runs_154 SET status='succeeded',outcome_code='SUCCESS',attempts=?,http_status=?,records_count=?,response_bytes=?,schema_fingerprint=?,provenance_json=?,finished_at=?,duration_ms=? WHERE run_id=?",
                            (attempts, response.status_code, len(records), len(response.body), fingerprint, dumps(provenance), now_ts(), duration, run_id))
            self.db.execute("INSERT INTO connector_schema_history_154(schema_id,connector_id,observed_at,schema_fingerprint,schema_shape_json,run_id) VALUES(?,?,?,?,?,?)",
                            (new_id("schema154"), request.connector_id, now_ts(), fingerprint, dumps(shape), run_id))
            self._record_health(request.connector_id, "degraded" if drift else "healthy", duration, fingerprint, drift, {"records": len(records)})
            if job is not None:
                self.observability.finish_job(job.job_id, status="succeeded", outcome_code="SUCCESS", output_summary={"records": len(records), "schema_drift": drift})
            self.audit.log("connector_run_154", "connector_run", run_id, request.case_id,
                           {"connector": request.connector_id, "records": len(records), "schema_drift": drift, "correlation_id": correlation_id})
            return {"run_id": run_id, "correlation_id": correlation_id, "records": records,
                    "records_count": len(records), "schema_fingerprint": fingerprint,
                    "schema_drift": drift, "provenance": provenance, "attempts": attempts}
        except Exception as exc:
            duration = int((time.monotonic() - started_wall) * 1000)
            message = str(exc)[:4000]
            code = "PARSER_FAILED" if isinstance(exc, (json.JSONDecodeError, ValueError)) else "SOURCE_UNAVAILABLE"
            if "RATE_LIMITED" in message: code = "RATE_LIMITED"
            elif "AUTH_REQUIRED" in message: code = "AUTH_REQUIRED"
            self.db.execute("UPDATE connector_runs_154 SET status='failed',outcome_code=?,attempts=?,http_status=?,response_bytes=?,error_message=?,finished_at=?,duration_ms=? WHERE run_id=?",
                            (code, attempts, response.status_code if response else None, len(response.body) if response else 0, message, now_ts(), duration, run_id))
            self._record_health(request.connector_id, "degraded", duration, None, False, {"error": message, "outcome": code})
            if job is not None:
                self.observability.finish_job(job.job_id, status="failed", outcome_code=code,
                                              error_class="parser" if code == "PARSER_FAILED" else "source",
                                              error_message=message, retryable=code in {"RATE_LIMITED", "SOURCE_UNAVAILABLE"})
            raise

    def _record_health(self, connector_id: str, status: str, latency_ms: int,
                       fingerprint: str | None, drift: bool, details: Mapping[str, Any]) -> None:
        previous = self.db.one("SELECT consecutive_failures,last_success_at,last_failure_at FROM connector_health_154 WHERE connector_id=? ORDER BY checked_at DESC LIMIT 1", (connector_id,)) or {}
        success = status == "healthy" or (status == "degraded" and "records" in details)
        failures = 0 if success else int(previous.get("consecutive_failures") or 0) + 1
        self.db.execute("INSERT INTO connector_health_154(health_id,connector_id,checked_at,status,consecutive_failures,last_success_at,last_failure_at,latency_ms,schema_fingerprint,schema_drift,details_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (new_id("connhealth154"), connector_id, now_ts(), status, failures,
                         now_ts() if success else previous.get("last_success_at"),
                         previous.get("last_failure_at") if success else now_ts(), latency_ms, fingerprint, int(drift), dumps(dict(details))))

    def catalog(self) -> dict[str, Any]:
        rows = self.db.all("SELECT connector_id,display_name,version,lifecycle_status,contract_state,base_url,updated_at FROM connector_specs_154 ORDER BY connector_id")
        return {"build": self.BUILD, "mission": self.MISSION, "connectors": rows,
                "registered": len(rows), "production": sum(r["lifecycle_status"] == "production" and r["contract_state"] == "accepted" for r in rows),
                "review_first": True, "public_only": True, "automatic_identity_confirmation": False}

    def health_report(self) -> dict[str, Any]:
        rows = self.db.all("SELECT h.* FROM connector_health_154 h JOIN (SELECT connector_id,MAX(checked_at) AS m FROM connector_health_154 GROUP BY connector_id) x ON x.connector_id=h.connector_id AND x.m=h.checked_at ORDER BY h.connector_id")
        return {"build": self.BUILD, "connectors_checked": len(rows), "health": rows,
                "degraded": sum(r["status"] != "healthy" for r in rows)}
