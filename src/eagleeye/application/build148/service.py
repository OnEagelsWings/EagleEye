from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping
from urllib.parse import quote_plus, urlsplit

from eagleeye.infrastructure.providers.policy import sanitize_mapping, validate_public_scope
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts

REGISTER_CONFIRMATION = "CONNECTOR-MANIFEST 148 REGISTRIEREN"
CONTRACT_CONFIRMATION = "CONNECTOR-VERTRAG 148 AKZEPTIEREN"
RUN_CONFIRMATION = "CONNECTOR-RUN 148 FREIGEBEN"
QUARANTINE_CONFIRMATION = "CONNECTOR 148 QUARANTÄNE ÄNDERN"
SECRET_REF_CONFIRMATION = "CONNECTOR-SECRET 148 ZUORDNEN"

CONNECTOR_TYPES = {
    "LOOKUP", "IMPORT", "ENRICHMENT", "MONITOR",
    "GUIDED_BROWSER", "CAPTURE", "EXPORT", "STREAM",
}
EXECUTION_BACKENDS = {"provider_collection_120", "guided_browser_136", "internal_reference", "external_worker"}
LEGAL_STATES = {"approved_public", "approved_licensed", "terms_review_required", "disabled_legal"}
SIGNATURE_STATES = {"internal_trusted", "vendor_signed", "unsigned_local"}
LIFECYCLE_STATES = {"registered", "operational", "quarantined", "disabled", "changed_contract"}
HEALTH_STATES = {
    "operational", "degraded", "rate_limited", "authentication_required",
    "terms_review_required", "changed_contract", "quarantined", "offline",
}
REVIEW_STATES = {"new", "ready_for_review", "rejected", "accepted_candidate"}
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{2,95}$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _safe(value: Any, limit: int = 4000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _canonical_host(host: str) -> str:
    value = str(host or "").strip().casefold().strip(".")
    if not value or any(mark in value for mark in ("/", ":", "*", "@")) or value.endswith(".local") or value == "localhost":
        raise ValueError("Connector-Hosts müssen exakte öffentliche DNS-Namen ohne Wildcards sein")
    return value


def _schema_fingerprint(schema: Mapping[str, Any]) -> str:
    return _sha(dict(schema))


@dataclass(frozen=True, slots=True)
class ConnectorManifest148:
    connector_id: str
    label: str
    connector_version: str
    connector_type: str
    publisher: str
    execution_backend: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    source_key: str = ""
    entrypoint: str = ""
    entity_types: tuple[str, ...] = ()
    secret_names: tuple[str, ...] = ()
    allowed_hosts: tuple[str, ...] = ()
    rate_limit_per_minute: int = 30
    cost_model: str = "free_public"
    legal_status: str = "approved_public"
    terms_profile: str = "official_public_interface"
    retention_profile: str = "case_policy"
    data_classification: tuple[str, ...] = ("public_data",)
    health_probe: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    code_sha256: str = ""
    signature_status: str = "internal_trusted"
    enabled: bool = True

    def validate(self) -> None:
        if not SAFE_ID.fullmatch(self.connector_id):
            raise ValueError("connector_id muss ein sicherer Kleinbuchstaben-Identifier sein")
        if not _safe(self.label, 200) or not _safe(self.publisher, 200):
            raise ValueError("Connector-Label und Publisher sind erforderlich")
        if not SEMVER.fullmatch(self.connector_version):
            raise ValueError("Connector-Version muss SemVer entsprechen")
        if self.connector_type not in CONNECTOR_TYPES:
            raise ValueError("Unbekannter Connector-Typ")
        if self.execution_backend not in EXECUTION_BACKENDS:
            raise ValueError("Unbekanntes Ausführungsbackend")
        if self.legal_status not in LEGAL_STATES:
            raise ValueError("Ungültiger Rechts-/Nutzungsstatus")
        if self.signature_status not in SIGNATURE_STATES:
            raise ValueError("Ungültiger Signaturstatus")
        if not 1 <= int(self.rate_limit_per_minute) <= 600:
            raise ValueError("Rate Limit außerhalb sicherer Grenzen")
        for schema, label in ((self.input_schema, "input"), (self.output_schema, "output")):
            if not isinstance(schema, Mapping) or schema.get("type") != "object" or not isinstance(schema.get("properties", {}), Mapping):
                raise ValueError(f"{label}_schema muss ein JSON-Object-Schema sein")
        normalized_hosts = tuple(_canonical_host(host) for host in self.allowed_hosts)
        if len(set(normalized_hosts)) != len(normalized_hosts):
            raise ValueError("Doppelte Connector-Hosts")
        if self.execution_backend in {"provider_collection_120", "guided_browser_136", "external_worker"} and not normalized_hosts:
            raise ValueError("Extern ausführbare Connectoren benötigen eine Host-Allowlist")
        if any(not SAFE_ID.fullmatch(name) for name in self.secret_names):
            raise ValueError("Secret-Namen müssen sichere Identifier sein")
        if self.code_sha256 and not SHA256_RE.fullmatch(self.code_sha256):
            raise ValueError("code_sha256 muss ein SHA-256-Hexwert sein")

    def contract_payload(self) -> dict[str, Any]:
        self.validate()
        payload = asdict(self)
        payload["entity_types"] = sorted(set(self.entity_types))
        payload["secret_names"] = sorted(set(self.secret_names))
        payload["allowed_hosts"] = sorted({_canonical_host(host) for host in self.allowed_hosts})
        payload["data_classification"] = sorted(set(self.data_classification))
        payload["input_schema"] = dict(self.input_schema)
        payload["output_schema"] = dict(self.output_schema)
        payload["health_probe"] = sanitize_mapping(dict(self.health_probe))
        payload["metadata"] = sanitize_mapping(dict(self.metadata))
        payload["code_sha256"] = self.code_sha256 or _sha({"entrypoint": self.entrypoint, "connector_id": self.connector_id})
        return payload

    def fingerprint(self) -> str:
        return _sha(self.contract_payload())


class Build148ConnectorSDKService:
    """Connector SDK 2.0 and governance boundary.

    Connector output is always written to a candidate-only quarantine zone. A
    connector has no direct path to Evidence Graph, identity confirmation or
    reports. Secrets are referenced by vault key and may be leased once for a
    short period; raw values never enter manifests, runs, events or case data.
    """

    BUILD = "148.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        build147: Any,
        build136: Any,
        providers: Any,
        protection: Any,
        clock: Any | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.build147 = build147
        self.build136 = build136
        self.providers = providers
        self.protection = protection
        self.clock = clock or time.time
        self.seed_connectors()
        self.refresh_all_health()

    # ---------- safety and audit ----------
    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any] | None:
        if not target_id:
            return None
        row = self.db.one("SELECT * FROM targets WHERE case_id=? AND target_id=?", (case_id, target_id))
        if not row:
            raise KeyError("Zielperson nicht gefunden oder falscher Fall")
        return row

    def _event(self, *, event_type: str, actor: str, connector_id: str = "", case_id: str = "", run_id: str = "", payload: Mapping[str, Any] | None = None) -> str:
        safe = sanitize_mapping(dict(payload or {}))
        previous = self.db.one(
            "SELECT event_hash FROM connector_events_148 WHERE COALESCE(case_id,'')=? ORDER BY sequence DESC LIMIT 1",
            (case_id,),
        )
        previous_hash = str((previous or {}).get("event_hash") or "GENESIS")
        stamp = now_ts(); event_id = new_id("conn148")
        material = {
            "event_id": event_id, "case_id": case_id, "connector_id": connector_id,
            "run_id": run_id, "actor": _safe(actor, 120), "event_type": event_type,
            "payload": safe, "previous_hash": previous_hash, "created_at": stamp,
        }
        event_hash = _sha(material)
        self.db.execute(
            "INSERT INTO connector_events_148(event_id,case_id,connector_id,run_id,actor,event_type,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (event_id, case_id or None, connector_id, run_id, _safe(actor, 120), event_type, dumps(safe), previous_hash, event_hash, stamp),
        )
        self.audit.log("connector_sdk", "connector_148", connector_id or run_id or event_id, case_id or None, {"event_type": event_type, **safe})
        return event_id

    # ---------- manifests ----------
    @staticmethod
    def _default_input_schema(inputs: Iterable[str] = ("query",)) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "query": {"type": "string", "minLength": 1, "maxLength": 1000},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 500},
        }
        for key in inputs:
            clean = str(key).strip().casefold().replace("-", "_")
            if SAFE_ID.fullmatch(clean) and clean not in properties:
                properties[clean] = {"type": "string", "maxLength": 1000}
        return {"type": "object", "properties": properties, "required": ["query"], "additionalProperties": False}

    @staticmethod
    def _default_output_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "object"}},
                "result_count": {"type": "integer", "minimum": 0},
                "candidate_only": {"type": "boolean", "const": True},
            },
            "required": ["items", "candidate_only"],
            "additionalProperties": True,
        }

    def _source_manifest(self, source: Mapping[str, Any]) -> ConnectorManifest148:
        source_key = str(source["source_key"])
        native = bool(source.get("native_execution"))
        provider_key = str(source.get("provider_key") or "")
        connector_id = f"source147_{source_key}"
        hosts = tuple(str(item) for item in source.get("allowed_hosts") or [])
        metadata = dict(source.get("metadata") or {})
        metadata.update({
            "source_group": source.get("source_group"),
            "category": source.get("category"),
            "search_template": source.get("search_url_template"),
            "official_url": source.get("official_url"),
            "auth_requirement": source.get("auth_requirement"),
            "risk_level": source.get("risk_level"),
            "persona_recommended": bool(source.get("persona_recommended")),
            "provider_key": provider_key,
            "candidate_only": True,
        })
        secrets_required: tuple[str, ...] = ()
        required_secret_names: tuple[str, ...] = ()
        auth = str(source.get("auth_requirement") or "none").casefold()
        if "api_key" in auth:
            secrets_required = (f"{source_key}_api_key",)
        elif "token" in auth or "oauth" in auth:
            secrets_required = (f"{source_key}_access_token",)
        if any(mark in auth for mark in ("required_api", "authentication_required", "token_required", "oauth_required")):
            required_secret_names = secrets_required
        metadata["required_secret_names"] = list(required_secret_names)
        return ConnectorManifest148(
            connector_id=connector_id,
            source_key=source_key,
            label=str(source["label"]),
            connector_version="1.0.0",
            connector_type="LOOKUP" if native else "GUIDED_BROWSER",
            publisher="EagleEye built-in",
            entrypoint=provider_key if native else "eagleeye.guided_browser",
            execution_backend="provider_collection_120" if native else "guided_browser_136",
            input_schema=self._default_input_schema(source.get("input_types") or ("query",)),
            output_schema=self._default_output_schema(),
            entity_types=("person", "organisation", "public_profile", "document"),
            secret_names=secrets_required,
            allowed_hosts=hosts,
            rate_limit_per_minute=30 if native else 10,
            legal_status="approved_public" if str(source.get("terms_profile") or "").startswith("official") else "terms_review_required",
            terms_profile=str(source.get("terms_profile") or "official_public_interface"),
            retention_profile="case_policy_candidate_only",
            data_classification=("public_data", "personal_data_candidate"),
            health_probe={"kind": "provider_contract" if native else "official_url", "provider_key": provider_key},
            metadata=metadata,
            code_sha256=_sha({"provider": provider_key, "source": source_key, "version": "147"}),
            signature_status="internal_trusted",
        )

    def _reference_manifests(self) -> tuple[ConnectorManifest148, ...]:
        common_in = self._default_input_schema(("case_id", "object_id"))
        common_out = self._default_output_schema()
        specs = (
            ("eagleeye_case_import_148", "Controlled case import reference", "IMPORT"),
            ("eagleeye_evidence_enrichment_148", "Evidence enrichment reference", "ENRICHMENT"),
            ("eagleeye_source_monitor_148", "Source monitor reference", "MONITOR"),
            ("eagleeye_browser_capture_148", "Browser capture bridge reference", "CAPTURE"),
            ("eagleeye_case_export_148", "Portable case export reference", "EXPORT"),
            ("eagleeye_event_stream_148", "Event stream reference", "STREAM"),
        )
        return tuple(
            ConnectorManifest148(
                connector_id=cid, label=label, connector_version="1.0.0", connector_type=ctype,
                publisher="EagleEye SDK reference", execution_backend="internal_reference",
                entrypoint=f"eagleeye.connector148.{ctype.casefold()}", input_schema=common_in,
                output_schema=common_out, entity_types=("case_object",), allowed_hosts=(),
                rate_limit_per_minute=60, legal_status="approved_public",
                terms_profile="internal_reference_no_external_egress",
                retention_profile="case_policy", data_classification=("internal_case_data",),
                health_probe={"kind": "internal_contract"}, metadata={"reference_only": True, "candidate_only": True},
                code_sha256=_sha({"id": cid, "type": ctype, "build": self.BUILD}),
                signature_status="internal_trusted", enabled=True,
            ) for cid, label, ctype in specs
        )

    def seed_connectors(self) -> None:
        manifests = [self._source_manifest(row) for row in self.build147.list_sources()] + list(self._reference_manifests())
        for manifest in manifests:
            self._upsert_manifest(manifest, actor="build148-seed", preserve_governance=True)

    def _upsert_manifest(self, manifest: ConnectorManifest148, *, actor: str, preserve_governance: bool = False) -> dict[str, Any]:
        payload = manifest.contract_payload(); fingerprint = _sha(payload); stamp = now_ts()
        current = self.db.one("SELECT * FROM connector_manifests_148 WHERE connector_id=?", (manifest.connector_id,))
        lifecycle = str((current or {}).get("lifecycle_status") or "registered") if preserve_governance else "registered"
        quarantine_reason = str((current or {}).get("quarantine_reason") or "") if lifecycle == "quarantined" else ""
        accepted = self.db.one("SELECT accepted_fingerprint FROM connector_contracts_148 WHERE connector_id=? AND status='accepted' ORDER BY accepted_at DESC LIMIT 1", (manifest.connector_id,))
        if accepted and accepted["accepted_fingerprint"] != fingerprint and lifecycle != "quarantined":
            lifecycle = "changed_contract"
        values = (
            manifest.connector_id, manifest.source_key, manifest.label, manifest.connector_version,
            manifest.connector_type, manifest.publisher, manifest.entrypoint, manifest.execution_backend,
            dumps(payload["input_schema"]), dumps(payload["output_schema"]), dumps(payload["entity_types"]),
            dumps(payload["secret_names"]), dumps(payload["allowed_hosts"]), int(manifest.rate_limit_per_minute),
            manifest.cost_model, manifest.legal_status, manifest.terms_profile, manifest.retention_profile,
            dumps(payload["data_classification"]), dumps(payload["health_probe"]), dumps(payload["metadata"]),
            payload["code_sha256"], fingerprint, manifest.signature_status, int(manifest.enabled), lifecycle,
            quarantine_reason, _safe(actor, 120), stamp, stamp,
        )
        self.db.execute(
            """INSERT INTO connector_manifests_148(
            connector_id,source_key,label,connector_version,connector_type,publisher,entrypoint,execution_backend,
            input_schema_json,output_schema_json,entity_types_json,secret_names_json,allowed_hosts_json,
            rate_limit_per_minute,cost_model,legal_status,terms_profile,retention_profile,data_classification_json,
            health_probe_json,metadata_json,code_sha256,manifest_fingerprint,signature_status,enabled,lifecycle_status,
            quarantine_reason,registered_by,registered_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(connector_id) DO UPDATE SET source_key=excluded.source_key,label=excluded.label,
            connector_version=excluded.connector_version,connector_type=excluded.connector_type,publisher=excluded.publisher,
            entrypoint=excluded.entrypoint,execution_backend=excluded.execution_backend,input_schema_json=excluded.input_schema_json,
            output_schema_json=excluded.output_schema_json,entity_types_json=excluded.entity_types_json,
            secret_names_json=excluded.secret_names_json,allowed_hosts_json=excluded.allowed_hosts_json,
            rate_limit_per_minute=excluded.rate_limit_per_minute,cost_model=excluded.cost_model,
            legal_status=excluded.legal_status,terms_profile=excluded.terms_profile,retention_profile=excluded.retention_profile,
            data_classification_json=excluded.data_classification_json,health_probe_json=excluded.health_probe_json,
            metadata_json=excluded.metadata_json,code_sha256=excluded.code_sha256,
            manifest_fingerprint=excluded.manifest_fingerprint,signature_status=excluded.signature_status,
            enabled=excluded.enabled,lifecycle_status=excluded.lifecycle_status,quarantine_reason=excluded.quarantine_reason,
            updated_at=excluded.updated_at""",
            values,
        )
        self.db.execute("INSERT OR IGNORE INTO connector_health_148(connector_id,updated_at) VALUES(?,?)", (manifest.connector_id, stamp))
        return self.get_connector(manifest.connector_id)

    def register_manifest(self, manifest_data: Mapping[str, Any], *, confirmation: str, actor: str) -> dict[str, Any]:
        if confirmation.strip() != REGISTER_CONFIRMATION:
            raise PermissionError("Explizite Registrierung des Connector-Manifests erforderlich")
        manifest = ConnectorManifest148(
            connector_id=_safe(manifest_data.get("connector_id"), 96),
            source_key=_safe(manifest_data.get("source_key"), 96),
            label=_safe(manifest_data.get("label"), 200),
            connector_version=_safe(manifest_data.get("connector_version"), 40),
            connector_type=_safe(manifest_data.get("connector_type"), 40).upper(),
            publisher=_safe(manifest_data.get("publisher"), 200),
            entrypoint=_safe(manifest_data.get("entrypoint"), 500),
            execution_backend=_safe(manifest_data.get("execution_backend"), 80),
            input_schema=dict(manifest_data.get("input_schema") or {}),
            output_schema=dict(manifest_data.get("output_schema") or {}),
            entity_types=tuple(str(x) for x in manifest_data.get("entity_types") or ()),
            secret_names=tuple(str(x) for x in manifest_data.get("secret_names") or ()),
            allowed_hosts=tuple(str(x) for x in manifest_data.get("allowed_hosts") or ()),
            rate_limit_per_minute=int(manifest_data.get("rate_limit_per_minute") or 30),
            cost_model=_safe(manifest_data.get("cost_model") or "unknown", 120),
            legal_status=_safe(manifest_data.get("legal_status") or "terms_review_required", 80),
            terms_profile=_safe(manifest_data.get("terms_profile"), 1000),
            retention_profile=_safe(manifest_data.get("retention_profile") or "case_policy", 120),
            data_classification=tuple(str(x) for x in manifest_data.get("data_classification") or ("public_data",)),
            health_probe=dict(manifest_data.get("health_probe") or {}),
            metadata=dict(manifest_data.get("metadata") or {}),
            code_sha256=_safe(manifest_data.get("code_sha256"), 64),
            signature_status=_safe(manifest_data.get("signature_status") or "unsigned_local", 40),
            enabled=bool(manifest_data.get("enabled", True)),
        )
        self._upsert_manifest(manifest, actor=actor)
        self._event(event_type="connector_manifest_registered_148", connector_id=manifest.connector_id, actor=actor, payload={"version": manifest.connector_version, "type": manifest.connector_type, "signature_status": manifest.signature_status})
        self.refresh_health(manifest.connector_id)
        return self.get_connector(manifest.connector_id)

    @staticmethod
    def _decode_manifest(row: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(row)
        for old, new in (
            ("input_schema_json", "input_schema"), ("output_schema_json", "output_schema"),
            ("entity_types_json", "entity_types"), ("secret_names_json", "secret_names"),
            ("allowed_hosts_json", "allowed_hosts"), ("data_classification_json", "data_classification"),
            ("health_probe_json", "health_probe"), ("metadata_json", "metadata"),
        ):
            result[new] = loads(str(result.pop(old, "{}" if new in {"input_schema", "output_schema", "health_probe", "metadata"} else "[]")))
        result["enabled"] = bool(result.get("enabled"))
        return result

    def get_connector(self, connector_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT m.*,h.health_state,h.contract_state,h.last_test_at,h.test_summary_json FROM connector_manifests_148 m LEFT JOIN connector_health_148 h ON h.connector_id=m.connector_id WHERE m.connector_id=?", (connector_id,))
        if not row:
            raise KeyError("Connector nicht gefunden")
        result = self._decode_manifest(row)
        result["test_summary"] = loads(str(result.pop("test_summary_json", "{}")))
        result["secret_refs"] = self.db.all("SELECT secret_name,vault_key,required,created_at,updated_at FROM connector_secret_refs_148 WHERE connector_id=? ORDER BY secret_name", (connector_id,))
        return result

    def list_connectors(self, connector_type: str = "", lifecycle: str = "") -> list[dict[str, Any]]:
        clauses: list[str] = []; params: list[Any] = []
        if connector_type:
            clauses.append("m.connector_type=?"); params.append(connector_type.upper())
        if lifecycle:
            clauses.append("m.lifecycle_status=?"); params.append(lifecycle)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.db.all(f"SELECT m.*,h.health_state,h.contract_state,h.last_test_at,h.test_summary_json FROM connector_manifests_148 m LEFT JOIN connector_health_148 h ON h.connector_id=m.connector_id{where} ORDER BY m.connector_type,m.label", tuple(params))
        return [self._decode_manifest(row) | {"test_summary": loads(str(row.get("test_summary_json") or "{}"))} for row in rows]

    # ---------- contracts and health ----------
    def run_contract_tests(self, connector_id: str, *, actor: str) -> dict[str, Any]:
        connector = self.get_connector(connector_id)
        checks: list[dict[str, Any]] = []

        def check(name: str, ok: bool, detail: str) -> None:
            checks.append({"name": name, "ok": bool(ok), "detail": _safe(detail, 500)})

        check("safe_identifier", bool(SAFE_ID.fullmatch(connector_id)), connector_id)
        check("semver", bool(SEMVER.fullmatch(str(connector["connector_version"]))), str(connector["connector_version"]))
        check("connector_type", connector["connector_type"] in CONNECTOR_TYPES, str(connector["connector_type"]))
        check("execution_backend", connector["execution_backend"] in EXECUTION_BACKENDS, str(connector["execution_backend"]))
        check("exact_host_allowlist", all(_canonical_host(host) == host for host in connector["allowed_hosts"]), ", ".join(connector["allowed_hosts"]))
        check("input_schema", connector["input_schema"].get("type") == "object" and isinstance(connector["input_schema"].get("properties"), dict), "JSON object schema")
        check("output_schema", connector["output_schema"].get("type") == "object" and isinstance(connector["output_schema"].get("properties"), dict), "JSON object schema")
        output_text = _json(connector["output_schema"]).casefold()
        check("candidate_only_output", "candidate_only" in output_text, "Output must retain candidate-only state")
        check("no_direct_evidence_contract", not any(term in output_text for term in ("confirmed_identity", "automatic_merge", "write_evidence_graph")), "No direct evidence or identity promotion")
        check("code_fingerprint", bool(SHA256_RE.fullmatch(str(connector["code_sha256"]))), str(connector["code_sha256"])[:16])
        check("signature_status", connector["signature_status"] in SIGNATURE_STATES, str(connector["signature_status"]))
        check("legal_status", connector["legal_status"] in LEGAL_STATES, str(connector["legal_status"]))
        if connector["execution_backend"] == "provider_collection_120":
            provider_key = str(connector["metadata"].get("provider_key") or connector["entrypoint"])
            try:
                provider = self.providers.provider(provider_key)
                adapter_ok = True
                provider_hosts = set(provider.get("allowed_hosts") or [])
                host_alignment = provider_hosts.issubset(set(connector["allowed_hosts"]))
            except Exception:
                adapter_ok = False; host_alignment = False
            check("adapter_available", adapter_ok, provider_key)
            check("provider_host_alignment", host_alignment, "Provider hosts must be included in connector allowlist")
        else:
            check("adapter_available", True, "Not a native provider connector")
            check("provider_host_alignment", True, "Not applicable")
        passed = sum(1 for item in checks if item["ok"]); score = int(round(100 * passed / len(checks)))
        status = "passed" if passed == len(checks) else "failed"
        test_id = new_id("ctest148"); stamp = now_ts()
        self.db.execute("INSERT INTO connector_contract_tests_148(test_id,connector_id,manifest_fingerprint,status,score,checks_json,tested_by,created_at) VALUES(?,?,?,?,?,?,?,?)", (test_id, connector_id, connector["manifest_fingerprint"], status, score, dumps(checks), _safe(actor,120), stamp))
        self.db.execute("UPDATE connector_health_148 SET last_test_at=?,test_summary_json=?,updated_at=? WHERE connector_id=?", (stamp, dumps({"status": status, "score": score, "checks": checks}), stamp, connector_id))
        self._event(event_type="connector_contract_tested_148", connector_id=connector_id, actor=actor, payload={"status": status, "score": score, "failed": [item["name"] for item in checks if not item["ok"]]})
        self.refresh_health(connector_id)
        return {"test_id": test_id, "connector_id": connector_id, "status": status, "score": score, "checks": checks}

    def accept_contract(self, connector_id: str, *, confirmation: str, actor: str, notes: str = "") -> dict[str, Any]:
        if confirmation.strip() != CONTRACT_CONFIRMATION:
            raise PermissionError("Explizite Akzeptanz des Connector-Vertrags erforderlich")
        connector = self.get_connector(connector_id)
        test = self.db.one("SELECT * FROM connector_contract_tests_148 WHERE connector_id=? ORDER BY created_at DESC LIMIT 1", (connector_id,))
        if not test or test["status"] != "passed" or test["manifest_fingerprint"] != connector["manifest_fingerprint"]:
            raise ValueError("Der aktuelle Connector-Vertrag muss zuerst vollständig getestet werden")
        existing = self.db.one("SELECT * FROM connector_contracts_148 WHERE connector_id=? AND accepted_fingerprint=? AND status='accepted' ORDER BY accepted_at DESC LIMIT 1", (connector_id, connector["manifest_fingerprint"]))
        if existing:
            # Repeated approval of the unchanged, already accepted contract is idempotent.
            self.refresh_health(connector_id)
            return self.get_connector(connector_id)
        contract_id = new_id("contract148"); stamp = now_ts()
        with self.db.transaction(immediate=True):
            self.db.execute("UPDATE connector_contracts_148 SET status='superseded' WHERE connector_id=? AND status='accepted'", (connector_id,))
            self.db.execute("INSERT INTO connector_contracts_148(contract_id,connector_id,connector_version,accepted_fingerprint,input_schema_fingerprint,output_schema_fingerprint,accepted_by,accepted_at,status,notes) VALUES(?,?,?,?,?,?,?,?, 'accepted',?)", (contract_id, connector_id, connector["connector_version"], connector["manifest_fingerprint"], _schema_fingerprint(connector["input_schema"]), _schema_fingerprint(connector["output_schema"]), _safe(actor,120), stamp, _safe(notes,2000)))
        if connector["lifecycle_status"] != "quarantined":
            self.db.execute("UPDATE connector_manifests_148 SET lifecycle_status='operational',quarantine_reason='',updated_at=? WHERE connector_id=?", (stamp, connector_id))
        self._event(event_type="connector_contract_accepted_148", connector_id=connector_id, actor=actor, payload={"contract_id": contract_id, "fingerprint": connector["manifest_fingerprint"]})
        self.refresh_health(connector_id)
        return self.get_connector(connector_id)

    def set_quarantine(self, connector_id: str, *, quarantined: bool, reason: str, confirmation: str, actor: str) -> dict[str, Any]:
        if confirmation.strip() != QUARANTINE_CONFIRMATION:
            raise PermissionError("Explizite Quarantäneentscheidung erforderlich")
        connector = self.get_connector(connector_id)
        if quarantined and len(_safe(reason)) < 8:
            raise ValueError("Nachvollziehbarer Quarantänegrund erforderlich")
        next_state = "quarantined" if quarantined else "registered"
        self.db.execute("UPDATE connector_manifests_148 SET lifecycle_status=?,quarantine_reason=?,updated_at=? WHERE connector_id=?", (next_state, _safe(reason,1000) if quarantined else "", now_ts(), connector_id))
        self._event(event_type="connector_quarantine_changed_148", connector_id=connector_id, actor=actor, payload={"quarantined": quarantined, "reason": reason})
        self.refresh_health(connector_id)
        return self.get_connector(connector_id)

    def bind_secret_reference(self, connector_id: str, *, secret_name: str, vault_key: str, required: bool, confirmation: str, actor: str) -> dict[str, Any]:
        if confirmation.strip() != SECRET_REF_CONFIRMATION:
            raise PermissionError("Explizite Secret-Zuordnung erforderlich")
        connector = self.get_connector(connector_id)
        secret_name = _safe(secret_name, 96); vault_key = _safe(vault_key, 160)
        if not SAFE_ID.fullmatch(secret_name) or not re.fullmatch(r"[A-Za-z0-9._:-]{3,160}", vault_key):
            raise ValueError("Ungültiger Secret- oder Vault-Identifier")
        if connector["secret_names"] and secret_name not in connector["secret_names"]:
            raise ValueError("Secret ist im Connector-Manifest nicht deklariert")
        ref_id = new_id("secretref148"); stamp = now_ts()
        self.db.execute("INSERT INTO connector_secret_refs_148(ref_id,connector_id,secret_name,vault_key,required,configured_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(connector_id,secret_name) DO UPDATE SET vault_key=excluded.vault_key,required=excluded.required,configured_by=excluded.configured_by,updated_at=excluded.updated_at", (ref_id, connector_id, secret_name, vault_key, int(required), _safe(actor,120), stamp, stamp))
        self._event(event_type="connector_secret_reference_bound_148", connector_id=connector_id, actor=actor, payload={"secret_name": secret_name, "required": required, "vault_key_hash": hashlib.sha256(vault_key.encode()).hexdigest()})
        self.refresh_health(connector_id)
        return self.get_connector(connector_id)

    def issue_secret_lease(self, connector_id: str, *, case_id: str, secret_names: Iterable[str], issued_to: str, actor: str, ttl_seconds: int = 60) -> dict[str, Any]:
        self._case(case_id); connector = self.get_connector(connector_id)
        names = sorted({_safe(item,96) for item in secret_names if _safe(item,96)})
        if not names or any(name not in connector["secret_names"] for name in names):
            raise ValueError("Secret-Lease enthält nicht deklarierte Secret-Namen")
        refs = {row["secret_name"]: row for row in self.db.all("SELECT * FROM connector_secret_refs_148 WHERE connector_id=?", (connector_id,))}
        if any(name not in refs for name in names):
            raise ValueError("Nicht alle Secret-Referenzen sind konfiguriert")
        for name in names:
            if not self.protection.get_secret(str(refs[name]["vault_key"])):
                raise ValueError(f"Vault-Secret ist nicht konfiguriert: {name}")
        ttl = max(10, min(int(ttl_seconds), 120)); token = secrets.token_urlsafe(48); lease_id = new_id("lease148")
        self.db.execute("INSERT INTO connector_secret_leases_148(lease_id,connector_id,case_id,token_hash,secret_names_json,issued_to,issued_by,expires_epoch,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (lease_id, connector_id, case_id, hashlib.sha256(token.encode()).hexdigest(), dumps(names), _safe(issued_to,120), _safe(actor,120), int(self.clock()) + ttl, now_ts()))
        self._event(event_type="connector_secret_lease_issued_148", connector_id=connector_id, case_id=case_id, actor=actor, payload={"lease_id": lease_id, "secret_names": names, "issued_to": issued_to, "ttl_seconds": ttl})
        return {"lease_id": lease_id, "lease_token": token, "expires_in": ttl, "connector_id": connector_id, "secret_names": names}

    def redeem_secret_lease(self, connector_id: str, *, lease_token: str, issued_to: str) -> dict[str, str]:
        digest = hashlib.sha256(str(lease_token).encode()).hexdigest(); now = int(self.clock())
        row = self.db.one("SELECT * FROM connector_secret_leases_148 WHERE connector_id=? AND token_hash=? AND issued_to=?", (connector_id, digest, _safe(issued_to,120)))
        if not row or row["used_at"] or row["revoked_at"] or int(row["expires_epoch"]) < now:
            raise PermissionError("Secret-Lease ist ungültig, abgelaufen oder bereits verwendet")
        refs = {item["secret_name"]: item for item in self.db.all("SELECT * FROM connector_secret_refs_148 WHERE connector_id=?", (connector_id,))}
        names = loads(str(row["secret_names_json"])); values = {name: self.protection.get_secret(str(refs[name]["vault_key"])) for name in names}
        if any(not value for value in values.values()):
            raise ValueError("Vault-Secret fehlt")
        self.db.execute("UPDATE connector_secret_leases_148 SET used_at=? WHERE lease_id=?", (now_ts(), row["lease_id"]))
        self._event(event_type="connector_secret_lease_redeemed_148", connector_id=connector_id, case_id=str(row.get("case_id") or ""), actor=issued_to, payload={"lease_id": row["lease_id"], "secret_count": len(values)})
        return values

    def refresh_health(self, connector_id: str) -> dict[str, Any]:
        connector = self.get_connector(connector_id)
        accepted = self.db.one("SELECT accepted_fingerprint FROM connector_contracts_148 WHERE connector_id=? AND status='accepted' ORDER BY accepted_at DESC LIMIT 1", (connector_id,))
        contract_state = "accepted" if accepted and accepted["accepted_fingerprint"] == connector["manifest_fingerprint"] else ("changed" if accepted else "unaccepted")
        if connector["lifecycle_status"] == "quarantined":
            health = "quarantined"
        elif not connector["enabled"] or connector["lifecycle_status"] == "disabled" or connector["legal_status"] == "disabled_legal":
            health = "offline"
        elif contract_state == "changed" or connector["lifecycle_status"] == "changed_contract":
            health = "changed_contract"
        elif connector["legal_status"] == "terms_review_required" or contract_state == "unaccepted":
            health = "terms_review_required"
        else:
            required = set(connector["metadata"].get("required_secret_names") or [])
            required.update(row["secret_name"] for row in self.db.all("SELECT secret_name FROM connector_secret_refs_148 WHERE connector_id=? AND required=1", (connector_id,)))
            configured = {row["secret_name"] for row in self.db.all("SELECT secret_name FROM connector_secret_refs_148 WHERE connector_id=?", (connector_id,))}
            if required and not required.issubset(configured):
                health = "authentication_required"
            elif connector["execution_backend"] == "provider_collection_120":
                provider_key = str(connector["metadata"].get("provider_key") or connector["entrypoint"])
                state = self.db.one("SELECT * FROM provider_state_120 WHERE provider_key=?", (provider_key,)) or {}
                circuit = str(state.get("circuit_state") or "closed")
                if circuit == "open":
                    health = "degraded"
                elif float(state.get("next_allowed_epoch") or 0) > float(self.clock()):
                    health = "rate_limited"
                else:
                    health = "operational"
            else:
                health = "operational"
        stamp = now_ts()
        self.db.execute("UPDATE connector_health_148 SET health_state=?,contract_state=?,updated_at=? WHERE connector_id=?", (health, contract_state, stamp, connector_id))
        return {"connector_id": connector_id, "health_state": health, "contract_state": contract_state}

    def refresh_all_health(self) -> dict[str, int]:
        counts = {key: 0 for key in HEALTH_STATES}
        for row in self.db.all("SELECT connector_id FROM connector_manifests_148"):
            state = self.refresh_health(row["connector_id"])["health_state"]
            counts[state] = counts.get(state, 0) + 1
        return counts

    # ---------- run and quarantine ----------
    @staticmethod
    def _validate_input(schema: Mapping[str, Any], value: Mapping[str, Any]) -> dict[str, Any]:
        properties = dict(schema.get("properties") or {}); required = set(schema.get("required") or [])
        additional = bool(schema.get("additionalProperties", True)); clean: dict[str, Any] = {}
        missing = [key for key in required if key not in value or value.get(key) in (None, "")]
        if missing:
            raise ValueError("Pflichtfelder fehlen: " + ", ".join(sorted(missing)))
        for key, item in value.items():
            if key not in properties:
                if additional:
                    clean[key] = sanitize_mapping(item)
                    continue
                raise ValueError(f"Nicht erlaubtes Connector-Eingabefeld: {key}")
            spec = properties[key]; expected = spec.get("type")
            if expected == "integer":
                number = int(item)
                if number < int(spec.get("minimum", -10**9)) or number > int(spec.get("maximum", 10**9)):
                    raise ValueError(f"Connector-Eingabefeld außerhalb Grenzen: {key}")
                clean[key] = number
            elif expected == "boolean":
                clean[key] = bool(item)
            else:
                text = _safe(item, int(spec.get("maxLength") or 4000))
                if len(text) < int(spec.get("minLength") or 0):
                    raise ValueError(f"Connector-Eingabefeld ist zu kurz: {key}")
                clean[key] = text
        return clean

    def _assert_runnable(self, connector: Mapping[str, Any], *, mode: str) -> None:
        health = self.refresh_health(str(connector["connector_id"]))["health_state"]
        if health in {"quarantined", "offline", "changed_contract", "terms_review_required", "authentication_required"}:
            raise PermissionError(f"Connector ist nicht ausführbar: {health}")
        if mode not in {"dry_run", "replay", "live"}:
            raise ValueError("Ausführungsmodus muss dry_run, replay oder live sein")
        if mode == "live" and connector["execution_backend"] == "internal_reference":
            raise PermissionError("Interne Referenzconnectoren werden nicht als externe Live-Connectoren ausgeführt")
        if mode != "dry_run" and connector["execution_backend"] == "external_worker":
            raise PermissionError("Externe Worker bleiben bis zur signierten Sandbox-Freigabe auf Dry Run begrenzt")

    def execute_connector(
        self, *, case_id: str, connector_id: str, input_data: Mapping[str, Any], purpose: str,
        actor: str, confirmation: str, mode: str = "dry_run", target_id: str = "",
        local_redirect_origin: str = "http://127.0.0.1:8765",
    ) -> dict[str, Any]:
        if confirmation.strip() != RUN_CONFIRMATION:
            raise PermissionError("Explizite Connector-Run-Freigabe erforderlich")
        self._case(case_id); self._target(case_id, target_id)
        if len(_safe(purpose)) < 10:
            raise ValueError("Nachvollziehbarer Ermittlungszweck erforderlich")
        connector = self.get_connector(connector_id); self._assert_runnable(connector, mode=mode)
        clean_input = self._validate_input(connector["input_schema"], input_data)
        query = _safe(clean_input.get("query"), 1000)
        if query:
            validate_public_scope(query, purpose)
        run_id = new_id("crun148"); stamp = now_ts(); fingerprint = _sha(clean_input)
        self.db.execute("INSERT INTO connector_runs_148(run_id,case_id,target_id,connector_id,connector_type,execution_mode,status,purpose,input_json,input_fingerprint,output_contract_fingerprint,approved_by,started_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (run_id, case_id, target_id or None, connector_id, connector["connector_type"], mode, "running", _safe(purpose,2000), dumps(clean_input), fingerprint, _schema_fingerprint(connector["output_schema"]), _safe(actor,120), stamp, stamp, stamp))
        self._event(event_type="connector_run_started_148", connector_id=connector_id, case_id=case_id, run_id=run_id, actor=actor, payload={"mode": mode, "input_fields": sorted(clean_input), "input_fingerprint": fingerprint, "candidate_only": True})
        try:
            if mode == "dry_run":
                output = {"run_id": run_id, "status": "dry_run_completed", "connector_id": connector_id, "would_contact_hosts": connector["allowed_hosts"], "candidate_only": True, "automatic_evidence_write": False}
                self.db.execute("UPDATE connector_runs_148 SET status='dry_run_completed',completed_at=?,updated_at=? WHERE run_id=?", (now_ts(), now_ts(), run_id))
            elif connector["execution_backend"] == "provider_collection_120":
                provider_key = str(connector["metadata"].get("provider_key") or connector["entrypoint"])
                result = self.providers.execute(
                    case_id=case_id, provider_key=provider_key, query=query, purpose=purpose,
                    approved_by=actor, confirmation=self.providers.APPROVAL_PHRASE, mode=mode,
                    target_id=target_id, max_results=int(clean_input.get("max_results") or 50),
                )
                count = self._copy_provider_quarantine(case_id=case_id, target_id=target_id, connector_id=connector_id, run_id=run_id, provider_run_id=str(result.get("run_id") or ""))
                self.db.execute("UPDATE connector_runs_148 SET status='completed',provider_run_id=?,result_count=?,quarantine_count=?,completed_at=?,updated_at=? WHERE run_id=?", (str(result.get("run_id") or ""), int(result.get("result_count") or count), count, now_ts(), now_ts(), run_id))
                output = {"run_id": run_id, "status": "completed", "provider_run_id": result.get("run_id"), "result_count": int(result.get("result_count") or count), "quarantine_count": count, "candidate_only": True}
            elif connector["execution_backend"] == "guided_browser_136":
                source = self.build147.source(str(connector["source_key"])); template = str(source.get("search_url_template") or source.get("official_url"))
                destination = template.replace("{query}", quote_plus(query)) if "{query}" in template else template
                parts = urlsplit(destination); host = (parts.hostname or "").casefold()
                if parts.scheme != "https" or host not in set(connector["allowed_hosts"]):
                    raise PermissionError("Guided-Browser-Ziel liegt außerhalb der Connector-Allowlist")
                task_id = new_id("task148")
                self.db.execute("INSERT INTO search_tasks(task_id,case_id,target_id,category,query,engine,url,status,created_at) VALUES(?,?,?,?,?,?,?,'planned',?)", (task_id, case_id, target_id or None, "connector_guided_research_148", query, connector["label"], destination, now_ts()))
                launch = self.build136.launch_research_task(case_id=case_id, task_id=task_id, actor=actor, local_redirect_origin=local_redirect_origin)
                self.db.execute("UPDATE connector_runs_148 SET status='opened_manual_review',browser_task_id=?,completed_at=?,updated_at=? WHERE run_id=?", (task_id, now_ts(), now_ts(), run_id))
                output = {"run_id": run_id, "status": "opened_manual_review", "browser_task_id": task_id, "candidate_only": True, **launch}
            else:
                output = {"run_id": run_id, "status": "reference_completed", "connector_id": connector_id, "candidate_only": True, "automatic_external_action": False}
                self.db.execute("UPDATE connector_runs_148 SET status='reference_completed',completed_at=?,updated_at=? WHERE run_id=?", (now_ts(), now_ts(), run_id))
            self._event(event_type="connector_run_completed_148", connector_id=connector_id, case_id=case_id, run_id=run_id, actor=actor, payload={"status": output["status"], "result_count": output.get("result_count",0), "quarantine_count": output.get("quarantine_count",0), "candidate_only": True})
            return output
        except Exception as exc:
            self.db.execute("UPDATE connector_runs_148 SET status='failed',attempt_count=attempt_count+1,error_class=?,error_message=?,completed_at=?,updated_at=? WHERE run_id=?", (type(exc).__name__, _safe(exc,1000), now_ts(), now_ts(), run_id))
            self.db.execute("UPDATE connector_health_148 SET last_failure_at=?,consecutive_failures=consecutive_failures+1,updated_at=? WHERE connector_id=?", (now_ts(), now_ts(), connector_id))
            self._event(event_type="connector_run_failed_148", connector_id=connector_id, case_id=case_id, run_id=run_id, actor=actor, payload={"error_type": type(exc).__name__})
            raise

    def _copy_provider_quarantine(self, *, case_id: str, target_id: str, connector_id: str, run_id: str, provider_run_id: str) -> int:
        rows = self.db.all("SELECT * FROM provider_intake_120 WHERE case_id=? AND run_id=?", (case_id, provider_run_id))
        count = 0; stamp = now_ts()
        for row in rows:
            payload = sanitize_mapping(loads(str(row.get("raw_payload_json") or "{}")))
            normalized = {
                "title": row.get("title"), "url": row.get("canonical_url"), "snippet": row.get("snippet"),
                "source_type": row.get("source_type"), "published_at": row.get("published_at"), "payload": payload,
                "provider_intake_id": row.get("intake_id"), "candidate_only": True,
            }
            fingerprint = _sha(normalized); qid = new_id("quarantine148")
            try:
                self.db.execute("INSERT INTO connector_quarantine_148(quarantine_id,case_id,target_id,run_id,connector_id,item_type,title,canonical_url,source_host,snippet,normalized_payload_json,content_fingerprint,review_status,candidate_only,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'new',1,?,?)", (qid, case_id, target_id or None, run_id, connector_id, str(row.get("source_type") or "public_item")[:100], _safe(row.get("title"),500), _safe(row.get("canonical_url"),4000), _safe(row.get("source_host"),253), _safe(row.get("snippet"),10000), dumps(normalized), fingerprint, stamp, stamp))
                count += 1
            except Exception:
                existing = self.db.one("SELECT quarantine_id FROM connector_quarantine_148 WHERE case_id=? AND connector_id=? AND content_fingerprint=?", (case_id, connector_id, fingerprint))
                if not existing:
                    raise
        return count

    def record_guided_result(self, *, case_id: str, run_id: str, title: str, url: str, snippet: str, actor: str) -> dict[str, Any]:
        run = self.db.one("SELECT * FROM connector_runs_148 WHERE case_id=? AND run_id=?", (case_id, run_id))
        if not run:
            raise KeyError("Connector-Run nicht gefunden oder falscher Fall")
        if run["status"] != "opened_manual_review":
            raise ValueError("Nur ein geöffneter Guided-Browser-Run darf manuelle Ergebnisse aufnehmen")
        connector = self.get_connector(run["connector_id"]); parts = urlsplit(_safe(url,4000)); host = (parts.hostname or "").casefold()
        if parts.scheme != "https" or host not in set(connector["allowed_hosts"]):
            raise PermissionError("Ergebnis-URL liegt außerhalb der Connector-Allowlist")
        normalized = {"title": _safe(title,500), "url": _safe(url,4000), "snippet": _safe(snippet,10000), "candidate_only": True, "manual_guided_result": True}
        fingerprint = _sha(normalized); qid = new_id("quarantine148"); stamp = now_ts()
        existing = self.db.one("SELECT * FROM connector_quarantine_148 WHERE case_id=? AND connector_id=? AND content_fingerprint=?", (case_id, connector["connector_id"], fingerprint))
        if existing:
            return existing
        self.db.execute("INSERT INTO connector_quarantine_148(quarantine_id,case_id,target_id,run_id,connector_id,item_type,title,canonical_url,source_host,snippet,normalized_payload_json,content_fingerprint,review_status,candidate_only,created_at,updated_at) VALUES(?,?,?,?,?,'guided_public_result',?,?,?,?,?,?, 'new',1,?,?)", (qid, case_id, run.get("target_id"), run_id, connector["connector_id"], normalized["title"], normalized["url"], host, normalized["snippet"], dumps(normalized), fingerprint, stamp, stamp))
        self.db.execute("UPDATE connector_runs_148 SET result_count=result_count+1,quarantine_count=quarantine_count+1,updated_at=? WHERE run_id=?", (stamp, run_id))
        self._event(event_type="connector_guided_result_recorded_148", connector_id=connector["connector_id"], case_id=case_id, run_id=run_id, actor=actor, payload={"quarantine_id": qid, "source_host": host, "candidate_only": True})
        return self.db.one("SELECT * FROM connector_quarantine_148 WHERE quarantine_id=?", (qid,)) or {}

    def review_quarantine(self, *, case_id: str, quarantine_id: str, status: str, reason: str, actor: str) -> dict[str, Any]:
        if status not in REVIEW_STATES:
            raise ValueError("Ungültiger Quarantäne-Prüfstatus")
        if len(_safe(reason)) < 8:
            raise ValueError("Nachvollziehbare Prüfbegründung erforderlich")
        row = self.db.one("SELECT * FROM connector_quarantine_148 WHERE case_id=? AND quarantine_id=?", (case_id, quarantine_id))
        if not row:
            raise KeyError("Quarantäneobjekt nicht gefunden oder falscher Fall")
        self.db.execute("UPDATE connector_quarantine_148 SET review_status=?,reviewed_by=?,review_reason=?,updated_at=? WHERE quarantine_id=?", (status, _safe(actor,120), _safe(reason,2000), now_ts(), quarantine_id))
        self._event(event_type="connector_quarantine_item_reviewed_148", connector_id=row["connector_id"], case_id=case_id, run_id=row["run_id"], actor=actor, payload={"quarantine_id": quarantine_id, "status": status, "candidate_only": True, "automatic_evidence_write": False})
        return self.db.one("SELECT * FROM connector_quarantine_148 WHERE quarantine_id=?", (quarantine_id,)) or {}

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        self.refresh_all_health()
        types = {row["connector_type"]: int(row["n"]) for row in self.db.all("SELECT connector_type,COUNT(*) AS n FROM connector_manifests_148 GROUP BY connector_type")}
        health = {row["health_state"]: int(row["n"]) for row in self.db.all("SELECT health_state,COUNT(*) AS n FROM connector_health_148 GROUP BY health_state")}
        result: dict[str, Any] = {
            "build": self.BUILD, "connector_types": types, "health": health,
            "total_connectors": sum(types.values()),
            "accepted_contracts": int((self.db.one("SELECT COUNT(*) AS n FROM connector_contracts_148 WHERE status='accepted'") or {}).get("n") or 0),
            "quarantined_connectors": int((self.db.one("SELECT COUNT(*) AS n FROM connector_manifests_148 WHERE lifecycle_status='quarantined'") or {}).get("n") or 0),
            "automatic_evidence_writes": 0, "automatic_identity_claims": 0,
            "direct_database_access_for_connectors": 0, "raw_secrets_in_manifests": 0,
            "connectors": self.list_connectors(),
        }
        if case_id:
            result.update({
                "runs": self.db.all("SELECT r.*,m.label FROM connector_runs_148 r JOIN connector_manifests_148 m ON m.connector_id=r.connector_id WHERE r.case_id=? ORDER BY r.created_at DESC LIMIT 100", (case_id,)),
                "quarantine": self.db.all("SELECT q.*,m.label FROM connector_quarantine_148 q JOIN connector_manifests_148 m ON m.connector_id=q.connector_id WHERE q.case_id=? ORDER BY q.created_at DESC LIMIT 100", (case_id,)),
            })
        return result
