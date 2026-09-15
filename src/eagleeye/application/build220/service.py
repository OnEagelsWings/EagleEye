from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _text(value: Any, limit: int = 20_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _shape(value: Any) -> str:
    paths: list[str] = []
    def walk(node: Any, prefix: str = "$") -> None:
        if isinstance(node, Mapping):
            paths.append(prefix + ":object")
            for key in sorted(str(k) for k in node.keys()):
                walk(node.get(key), f"{prefix}.{key}")
        elif isinstance(node, list):
            paths.append(prefix + ":array")
            for item in node[:3]:
                walk(item, prefix + "[]")
        elif node is None:
            paths.append(prefix + ":null")
        elif isinstance(node, bool):
            paths.append(prefix + ":bool")
        elif isinstance(node, (int, float)):
            paths.append(prefix + ":number")
        else:
            paths.append(prefix + ":string")
    walk(value)
    return _hash(sorted(set(paths)))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urllib.error.HTTPError(req.full_url, code, "redirect blocked", headers, fp)


class Build220ProductiveWebArchiveOrganizationDocumentsService:
    """Productive source pack II with four governed source paths.

    The service exposes public archive and organization APIs plus two local evidence
    paths. Every output is evidence-bound and candidate-only. It does not perform
    logins, browser automation, active contact, or autonomous identity resolution.
    """

    BUILD = "220.0"
    MAX_HTTP_BYTES = 3_000_000
    FAILURE_THRESHOLD = 3
    CIRCUIT_COOLDOWN_SECONDS = 900

    ADAPTERS: tuple[dict[str, Any], ...] = (
        {
            "adapter_key": "wayback_public", "title": "Internet Archive Wayback Availability",
            "source_class": "web_archive", "adapter_kind": "http_api", "target_types": ["url"],
            "allowed_hosts": ["archive.org"], "network_capable": True, "opsec_risk": "elevated",
            "active": True, "health_state": "degraded", "contract_version": "wayback-availability-v1",
            "required_fields": ["archived_snapshots"],
            "notes": "Returns the closest archived snapshot candidate. The original URL is never contacted by EagleEye.",
        },
        {
            "adapter_key": "gleif_public", "title": "GLEIF LEI Public API",
            "source_class": "organization_registry", "adapter_kind": "http_api", "target_types": ["organization", "name"],
            "allowed_hosts": ["api.gleif.org"], "network_capable": True, "opsec_risk": "elevated",
            "active": True, "health_state": "degraded", "contract_version": "gleif-lei-records-v1",
            "required_fields": ["data"],
            "notes": "Public legal-entity candidates and LEI records; names and ownership data require human interpretation.",
        },
        {
            "adapter_key": "exiftool_local", "title": "ExifTool Local Metadata",
            "source_class": "document_metadata", "adapter_kind": "local_tool", "target_types": ["document", "image"],
            "allowed_hosts": [], "network_capable": False, "opsec_risk": "low",
            "active": False, "health_state": "not_configured", "contract_version": "eagleeye-exiftool-211-v1",
            "required_fields": ["execution"],
            "notes": "Delegates to the approved offline Build-211 ExifTool adapter. Metadata is never treated as identity proof.",
        },
        {
            "adapter_key": "archivebox_import", "title": "ArchiveBox Controlled Import",
            "source_class": "capture_import", "adapter_kind": "controlled_import", "target_types": ["document", "url"],
            "allowed_hosts": [], "network_capable": False, "opsec_risk": "low",
            "active": False, "health_state": "not_configured", "contract_version": "archivebox-import-211-v1",
            "required_fields": ["source", "package"],
            "notes": "Imports investigator-created ArchiveBox outputs from the dedicated local import directory only.",
        },
    )

    def __init__(
        self, db: Any, audit: Any, *, reliability: Any, conversation: Any, evidence: Any,
        identity_ai: Any, planner: Any, base_dir: str | Path, actor: str = "local-analyst",
        http_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.reliability = reliability
        self.conversation = conversation
        self.evidence = evidence
        self.identity_ai = identity_ai
        self.planner = planner
        self.base_dir = Path(base_dir)
        self.actor = actor
        self.http_fetcher = http_fetcher
        self.seed()

    # ---------- catalog ----------
    def seed(self) -> dict[str, Any]:
        now = now_ts()
        if not self.db.one("SELECT project_id FROM upstream_projects_211 LIMIT 1"):
            self.evidence.seed_foundation(confirmation="EVIDENCE FOUNDATION 211 ANLEGEN")
        detected = self.evidence.detect_tools()
        projects = {x["project_id"]: {**x, **(self.db.one("SELECT enabled,review_status FROM upstream_projects_211 WHERE project_id=?", (x["project_id"],)) or {})} for x in detected.get("tools", [])}
        for item in self.ADAPTERS:
            existing = self.db.one("SELECT * FROM source_adapters_220 WHERE adapter_key=?", (item["adapter_key"],))
            active = bool(item["active"])
            health = item["health_state"]
            path = ""
            version = ""
            if item["adapter_key"] == "exiftool_local":
                p = projects.get("exiftool", {})
                path, version = p.get("detected_path", ""), p.get("detected_version", "")
                active = bool(p.get("enabled") and path)
                health = "healthy" if active else "not_configured"
            elif item["adapter_key"] == "archivebox_import":
                p = projects.get("archivebox", {})
                path, version = p.get("detected_path", ""), p.get("detected_version", "")
                active = bool(p.get("enabled"))
                health = "healthy" if active else "not_configured"
            if existing and existing["health_state"] == "quarantined":
                health = "quarantined"
            created = existing["created_at"] if existing else now
            payload = {**item, "active": active, "health_state": health, "detected_path": path, "detected_version": version}
            self.db.execute(
                """INSERT OR REPLACE INTO source_adapters_220(
                adapter_key,title,source_class,adapter_kind,target_types_json,allowed_hosts_json,network_capable,
                opsec_risk,active,health_state,circuit_state,circuit_open_until,quarantine_reason,contract_version,
                required_fields_json,detected_path,detected_version,notes,created_at,updated_at,payload_sha256)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (item["adapter_key"], item["title"], item["source_class"], item["adapter_kind"], dumps(item["target_types"]),
                 dumps(item["allowed_hosts"]), int(item["network_capable"]), item["opsec_risk"], int(active), health,
                 existing["circuit_state"] if existing else "closed", existing["circuit_open_until"] if existing else "",
                 existing["quarantine_reason"] if existing else "", item["contract_version"], dumps(item["required_fields"]),
                 path, version, item["notes"], created, now, _hash(payload)),
            )
        self._seed_router(now)
        return {"build": self.BUILD, "adapter_count": len(self.ADAPTERS), "automatic_execution": False}

    def _seed_router(self, now: str) -> None:
        entries = (
            ("wayback_pack_220", "Wayback Archive Research", "web_archive", "build220_wayback", ["url"], ["archived_snapshot_candidates", "evidence"], 1, "elevated", "approved_url", "public", "degraded"),
            ("gleif_pack_220", "GLEIF Organization Registry", "organization_registry", "build220_gleif", ["organization", "name"], ["organization_candidates", "lei_records", "evidence"], 1, "elevated", "organization_or_name", "public", "degraded"),
            ("exiftool_pack_220", "ExifTool Metadata", "document_metadata", "build220_exiftool", ["document", "image"], ["metadata_candidates", "parser_warnings"], 0, "low", "none", "local", "healthy" if self._adapter("exiftool_local")["active"] else "requires_local_tool"),
            ("archivebox_pack_220", "ArchiveBox Controlled Import", "web_archive", "build220_archivebox_import", ["url", "document"], ["archived_artifact", "capture_metadata", "evidence"], 0, "low", "none", "local-import", "healthy" if self._adapter("archivebox_import")["active"] else "requires_local_tool"),
        )
        for key, title, route, adapter, inputs, outputs, network, risk, exposure, cost, health in entries:
            active = 1 if (key in {"wayback_pack_220", "gleif_pack_220"} or health == "healthy") else 0
            existing = self.db.one("SELECT created_at FROM source_router_catalog_217 WHERE source_key=?", (key,))
            created = existing["created_at"] if existing else now
            payload = {"source_key": key, "title": title, "route_class": route, "adapter_type": adapter, "input_types": inputs, "expected_outputs": outputs, "network_capable": bool(network), "opsec_risk": risk, "data_exposure": exposure, "estimated_cost": cost, "active": bool(active), "health_status": health}
            self.db.execute(
                """INSERT OR REPLACE INTO source_router_catalog_217 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (key, title, route, adapter, dumps(inputs), dumps(outputs), 0, network, risk, exposure, cost, active, health,
                 "EagleEye Build 220", "Human-approved source pack II route.", created, now, _hash(payload)),
            )
        # Retire the placeholder organization bridge now that GLEIF exists.
        self.db.execute("UPDATE source_router_catalog_217 SET active=0,health_status='superseded',updated_at=? WHERE source_key='organization_registry_bridge'", (now,))

    def catalog(self) -> list[dict[str, Any]]:
        return [self._public_adapter(x) for x in self.db.all("SELECT * FROM source_adapters_220 ORDER BY adapter_key")]

    # ---------- execution ----------
    def preflight(self, *, adapter_key: str) -> dict[str, Any]:
        adapter = self._adapter(adapter_key)
        if adapter_key in {"exiftool_local", "archivebox_import"}:
            project_id = "exiftool" if adapter_key == "exiftool_local" else "archivebox"
            project = self.db.one("SELECT enabled,detected_path,detected_version FROM upstream_projects_211 WHERE project_id=?", (project_id,)) or {}
            ready = bool(project.get("enabled")) and (adapter_key == "archivebox_import" or bool(project.get("detected_path")))
            if ready and not bool(adapter["active"]):
                self.db.execute("UPDATE source_adapters_220 SET active=1,health_state='healthy',detected_path=?,detected_version=?,updated_at=? WHERE adapter_key=?", (project.get("detected_path", ""), project.get("detected_version", ""), now_ts(), adapter_key))
                adapter = self._adapter(adapter_key)
        if adapter["health_state"] == "quarantined":
            return {"allowed": False, "decision": "quarantined", "reason": adapter["quarantine_reason"]}
        until = adapter.get("circuit_open_until") or ""
        if adapter["circuit_state"] == "open" and until:
            try:
                parsed = datetime.fromisoformat(until.replace("Z", "+00:00"))
                if parsed > datetime.now(timezone.utc):
                    return {"allowed": False, "decision": "circuit_open", "until": until}
            except Exception:
                pass
        if not bool(adapter["active"]):
            return {"allowed": False, "decision": "not_configured"}
        return {"allowed": True, "decision": "closed"}

    def run_adapter(
        self, *, case_id: str, adapter_key: str, target_type: str, target_value: str, purpose: str,
        actor: str, confirmation: str, options: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if confirmation != f"SOURCE PACK 220 {case_id} {adapter_key} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        adapter = self._adapter(adapter_key)
        if target_type not in _loads(adapter["target_types_json"], []):
            raise ValueError("unsupported target type")
        if len(purpose.strip()) < 12:
            raise ValueError("substantive case purpose required")
        guard = self.preflight(adapter_key=adapter_key)
        if not guard["allowed"]:
            return {"build": self.BUILD, "adapter_key": adapter_key, "status": "blocked", "result_count": 0, "guard": guard}
        requested = {
            "direct_contact": False, "credential_login": False, "upload_local_file": False, "download": False,
            "active_engagement": False, "new_browser_window": False, "network_execution_from_core": bool(adapter["network_capable"]),
            "network_capable": bool(adapter["network_capable"]),
        }
        opsec = self.identity_ai.opsec_preflight(
            case_id=case_id, action_type="source_pack_220", source_id=adapter_key, created_by=actor,
            requested=requested, confirmation=f"OPSEC PREFLIGHT 212 {case_id} PRUEFEN",
        )
        if opsec["decision"] == "blocked":
            return {"build": self.BUILD, "adapter_key": adapter_key, "status": "blocked", "result_count": 0, "guard": opsec}
        target = self._validate_target(adapter_key, target_type, target_value)
        run_id, started = new_id("source220"), now_ts()
        stored_target = "sha256:" + _hash(target) if adapter_key in {"exiftool_local", "archivebox_import"} else target
        opts = dict(options or {})
        payload = {"run_id": run_id, "case_id": case_id, "adapter_key": adapter_key, "target_type": target_type, "target_value_redacted": stored_target, "purpose": purpose, "options": opts, "status": "running", "started_by": actor, "started_at": started}
        self.db.execute(
            """INSERT INTO source_runs_220(run_id,case_id,adapter_key,target_type,target_value_redacted,purpose,options_json,status,started_by,started_at,finished_at,result_count,evidence_source_id,error_class,error_message,raw_sha256,metrics_json,payload_sha256)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, case_id, adapter_key, target_type, stored_target, _text(purpose, 5000), dumps(opts), "running", actor, started, "", 0, "", "", "", "", "{}", _hash(payload)),
        )
        begun = datetime.now(timezone.utc)
        try:
            if adapter_key == "wayback_public":
                raw, results, source_url, evidence_ref = self._run_wayback(case_id, target, actor)
            elif adapter_key == "gleif_public":
                raw, results, source_url, evidence_ref = self._run_gleif(case_id, target, actor)
            elif adapter_key == "exiftool_local":
                raw, results, source_url, evidence_ref = self._run_exiftool(case_id, target, purpose, actor)
            elif adapter_key == "archivebox_import":
                raw, results, source_url, evidence_ref = self._run_archivebox_import(case_id, target, opts, actor)
            else:
                raise KeyError(adapter_key)
            inserted = self._store_results(run_id=run_id, case_id=case_id, adapter_key=adapter_key, results=results, evidence_ref=evidence_ref)
            status = "completed" if inserted else "not_found"
            latency = int((datetime.now(timezone.utc) - begun).total_seconds() * 1000)
            self._finish_run(run_id, status=status, results=inserted, raw=raw, evidence_ref=evidence_ref, latency_ms=latency)
            self._record_health(adapter_key, status="healthy", latency_ms=latency, http_status=int(raw.get("status") or 0) if isinstance(raw, Mapping) else 0, result_count=len(inserted), raw=raw, actor=actor)
        except Exception as exc:
            latency = int((datetime.now(timezone.utc) - begun).total_seconds() * 1000)
            raw = getattr(exc, "response", {})
            self._finish_run(run_id, status="failed", results=[], raw=raw, evidence_ref="", latency_ms=latency, error=exc)
            self._record_health(adapter_key, status="unavailable", latency_ms=latency, http_status=int(raw.get("status") or 0) if isinstance(raw, Mapping) else 0, result_count=0, raw=raw, actor=actor, error=exc)
        result = self.get_run(run_id)
        self._event(case_id, "source_pack_220_run_finished", "source_run", run_id, {"adapter_key": adapter_key, "status": result["status"], "result_count": result["result_count"]}, actor)
        return result

    # ---------- source paths ----------
    def _run_wayback(self, case_id: str, public_url: str, actor: str) -> tuple[dict[str, Any], list[dict[str, Any]], str, str]:
        endpoint = "https://archive.org/wayback/available?" + urllib.parse.urlencode({"url": public_url})
        response = self._http_json(endpoint, {"archive.org"}, {"User-Agent": "EagleEye-PersonOSINT/220"})
        if response["status"] != 200:
            raise RuntimeError(f"Wayback HTTP {response['status']}")
        closest = (((response.get("json") or {}).get("archived_snapshots") or {}).get("closest") or {})
        results: list[dict[str, Any]] = []
        if closest.get("available") and closest.get("url"):
            results.append({
                "result_type": "archived_snapshot_candidate", "title": f"Wayback snapshot {closest.get('timestamp','')}",
                "canonical_url": _text(closest.get("url"), 3000), "display_value": public_url, "language": "und",
                "confidence": 0.92, "independence_key": "wayback:" + _hash([public_url, closest.get("timestamp")]),
                "fields": {"original_url": public_url, "timestamp": closest.get("timestamp"), "http_status": closest.get("status"), "available": True},
                "limitations": ["archive availability does not prove authorship or identity", "snapshot content requires separate human review"],
            })
        ev = self.evidence.preserve_text_evidence(
            case_id=case_id, title="Build 220 · Wayback Availability", source_url=endpoint,
            text=json.dumps(response, ensure_ascii=False, indent=2), captured_by=actor,
            metadata={"build": self.BUILD, "adapter_key": "wayback_public", "queried_url": public_url, "candidate_only": True},
            confirmation=f"EVIDENCE 211 {case_id} TEXT SPEICHERN",
        )
        return response, results, endpoint, ev["source"]["source_id"]

    def _run_gleif(self, case_id: str, query: str, actor: str) -> tuple[dict[str, Any], list[dict[str, Any]], str, str]:
        params = urllib.parse.urlencode({"filter[fulltext]": query, "page[size]": 10})
        endpoint = "https://api.gleif.org/api/v1/lei-records?" + params
        response = self._http_json(endpoint, {"api.gleif.org"}, {"Accept": "application/vnd.api+json", "User-Agent": "EagleEye-PersonOSINT/220"})
        if response["status"] != 200:
            raise RuntimeError(f"GLEIF HTTP {response['status']}")
        results: list[dict[str, Any]] = []
        for item in ((response.get("json") or {}).get("data") or [])[:10]:
            attrs = item.get("attributes") or {}
            entity = attrs.get("entity") or {}
            legal_name = ((entity.get("legalName") or {}).get("name") or "")
            other = [x.get("name") for x in (entity.get("otherNames") or []) if isinstance(x, Mapping) and x.get("name")]
            address = entity.get("legalAddress") or {}
            lei = _text(item.get("id"), 80)
            if not lei:
                continue
            results.append({
                "result_type": "organization_candidate", "title": legal_name or lei,
                "canonical_url": f"https://search.gleif.org/#/record/{urllib.parse.quote(lei)}",
                "display_value": legal_name or lei, "language": _text((entity.get("legalName") or {}).get("language"), 20) or "und",
                "confidence": 0.86, "independence_key": "gleif:lei:" + lei,
                "fields": {"lei": lei, "legal_name": legal_name, "other_names": other, "entity_status": entity.get("status"), "country": address.get("country"), "city": address.get("city"), "registration": attrs.get("registration"), "relationships": item.get("relationships")},
                "limitations": ["LEI identifies a legal entity, not a natural person", "name similarity alone does not establish a relationship to the target person"],
            })
        ev = self.evidence.preserve_text_evidence(
            case_id=case_id, title="Build 220 · GLEIF LEI Search", source_url=endpoint,
            text=json.dumps(response, ensure_ascii=False, indent=2), captured_by=actor,
            metadata={"build": self.BUILD, "adapter_key": "gleif_public", "query": query, "candidate_only": True},
            confirmation=f"EVIDENCE 211 {case_id} TEXT SPEICHERN",
        )
        return response, results, endpoint, ev["source"]["source_id"]

    def _run_exiftool(self, case_id: str, package_id: str, purpose: str, actor: str) -> tuple[dict[str, Any], list[dict[str, Any]], str, str]:
        plan = self.evidence.plan_tool_run(
            case_id=case_id, project_id="exiftool", package_id=package_id, purpose=purpose,
            options={"build220": True}, created_by=actor, confirmation=f"TOOL RUN 211 {case_id} PLANEN",
        )
        executed = self.evidence.execute_exiftool(run_id=plan["run_id"], confirmation=f"TOOL RUN 211 {plan['run_id']} AUSFUEHREN")
        source = self.db.one("SELECT source_id FROM evidence_sources_211 WHERE case_id=? AND package_id=? ORDER BY created_at LIMIT 1", (case_id, package_id,))
        evidence_ref = source["source_id"] if source else ""
        result = {
            "result_type": "document_metadata_candidate", "title": "ExifTool metadata",
            "canonical_url": "", "display_value": executed.get("artifact_id", ""), "language": "und", "confidence": 0.66,
            "independence_key": "exiftool:" + package_id,
            "fields": {"package_id": package_id, "artifact_id": executed.get("artifact_id"), "tool_run_id": plan["run_id"]},
            "limitations": ["metadata can be edited", "absence of metadata is not evidence", "human review required"],
        }
        return {"status": 200, "plan": plan, "execution": executed}, [result], "local://exiftool", evidence_ref

    def _run_archivebox_import(self, case_id: str, artifact_path: str, options: Mapping[str, Any], actor: str) -> tuple[dict[str, Any], list[dict[str, Any]], str, str]:
        source_url = _text(options.get("source_url"), 3000)
        title = _text(options.get("title"), 500) or "ArchiveBox capture"
        media_type = _text(options.get("media_type"), 100) or "application/octet-stream"
        collector_version = _text(options.get("collector_version"), 200) or "unknown"
        imported = self.evidence.import_archivebox_capture(
            case_id=case_id, artifact_path=artifact_path, title=title, source_url=source_url,
            media_type=media_type, created_by=actor, collector_version=collector_version,
            confirmation=f"EVIDENCE 211 {case_id} TOOL IMPORT",
        )
        source_id = imported["source"]["source_id"]
        result = {
            "result_type": "archived_artifact_candidate", "title": title,
            "canonical_url": imported["source"].get("canonical_url", ""), "display_value": Path(artifact_path).name,
            "language": "und", "confidence": 0.94, "independence_key": "archivebox:" + imported["package"]["raw_sha256"],
            "fields": {"package_id": imported["package"]["package_id"], "source_id": source_id, "media_type": media_type, "collector_version": collector_version},
            "limitations": ["capture authenticity depends on the preserved hash and chain of custody", "content claims remain subject to human review"],
        }
        return {"status": 200, "source": imported["source"], "package": imported["package"]}, [result], source_url or "local://archivebox", source_id

    # ---------- review, training, dashboard ----------
    def review_result(self, *, result_id: str, decision: str, reason: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM source_results_220 WHERE result_id=?", (result_id,))
        if not row:
            raise KeyError(result_id)
        if confirmation != f"SOURCE RESULT 220 {result_id} PRUEFEN":
            raise PermissionError("explicit approval required")
        if decision not in {"accepted_candidate", "rejected", "duplicate", "needs_more_evidence"}:
            raise ValueError("invalid decision")
        if len(reason.strip()) < 20:
            raise ValueError("substantive review reason required")
        training = self.conversation.create_training_example(
            case_id=row["case_id"], task_type="source_assessment", language=row["language"], difficulty="real_source_review",
            input_payload={"adapter_key": row["adapter_key"], "result_type": row["result_type"], "fields": _loads(row["fields_json"], {}), "limitations": _loads(row["limitations_json"], [])},
            expected_output={"decision": decision, "reason": reason, "candidate_only": True}, evidence_refs=[row["evidence_ref"]] if row["evidence_ref"] else [],
            negative_constraints=["do not confirm identity", "do not treat metadata as immutable truth", "distinguish legal entity from natural person", "cite the archived or registry source"],
            label="build220_source_result_review", rationale=reason, created_by=reviewer,
            confirmation=f"TRAINING EXAMPLE 216 {row['case_id']} ANLEGEN",
        )
        rid, now = new_id("review220"), now_ts()
        payload = {"review_id": rid, "result_id": result_id, "case_id": row["case_id"], "decision": decision, "reason": reason, "reviewer": reviewer, "training_example_id": training["example_id"], "created_at": now}
        self.db.execute("INSERT INTO source_result_reviews_220 VALUES(?,?,?,?,?,?,?,?,?)", (rid, result_id, row["case_id"], decision, _text(reason, 5000), reviewer, training["example_id"], now, _hash(payload)))
        self.db.execute("UPDATE source_results_220 SET review_status=? WHERE result_id=?", (decision, result_id))
        self._event(row["case_id"], "source_result_220_reviewed", "source_result", result_id, {"decision": decision, "training_example_id": training["example_id"]}, reviewer)
        return payload

    def get_run(self, run_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM source_runs_220 WHERE run_id=?", (run_id,))
        if not row:
            raise KeyError(run_id)
        return {**row, "options": _loads(row["options_json"], {}), "metrics": _loads(row["metrics_json"], {}), "results": [self._public_result(x) for x in self.db.all("SELECT * FROM source_results_220 WHERE run_id=? ORDER BY created_at", (run_id,))]}

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        return {
            "build": self.BUILD, "case_id": case_id, "adapters": self.catalog(),
            "runs": self.db.all("SELECT * FROM source_runs_220 WHERE case_id=? ORDER BY started_at DESC LIMIT 40", (case_id,)),
            "results": [self._public_result(x) for x in self.db.all("SELECT * FROM source_results_220 WHERE case_id=? ORDER BY created_at DESC LIMIT 80", (case_id,))],
            "health": self.db.all("SELECT * FROM source_health_checks_220 ORDER BY checked_at DESC LIMIT 40"),
            "policy": {"candidate_only": True, "human_approval": True, "automatic_identity_confirmation": False, "automatic_browser_execution": False, "training_coupled": True},
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        base = self.reliability.render_workspace_panel(case_id=case_id, csrf=csrf).replace("Fallarbeitsraum 219", "Fallarbeitsraum 220", 1)
        data = self.dashboard(case_id=case_id)
        esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
        options = "".join(f"<option value='{esc(x['adapter_key'])}'>{esc(x['title'])} · {esc(x['health_state'])}</option>" for x in data["adapters"])
        rows = "".join(f"<tr><td>{esc(x['adapter_key'])}</td><td>{esc(x['result_type'])}</td><td>{esc(x['title'])}</td><td>{esc(x['review_status'])}</td><td><code>{esc(x['evidence_ref'])}</code></td></tr>" for x in data["results"][:30]) or "<tr><td colspan='5'>Noch keine Build-220-Ergebnisse.</td></tr>"
        panel = f"""
<section class='card' id='build220_sources'><h2>Productive Source Pack II · Build 220</h2>
<p>Kontrollierte Webarchiv-, Organisations- und Dokumentquellen. Alle Ergebnisse bleiben Kandidaten, werden als Evidence gebunden und fließen erst nach menschlichem Review in den Trainingsbestand ein.</p>
<div class='grid two'><div><form method='post' action='/build220/run'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>Quellenpfad ausführen</h3><select name='adapter_key'>{options}</select><select name='target_type'><option value='url'>url</option><option value='organization'>organization</option><option value='name'>name</option><option value='document'>document/package/path</option><option value='image'>image/package</option></select><input name='target_value' placeholder='URL, Organisation, Package-ID oder Importpfad' required><textarea name='purpose' rows='3' placeholder='Konkreter Fallzweck' required></textarea><textarea name='options_json' rows='5' placeholder='Optional für ArchiveBox: {{"title":"...","source_url":"https://...","media_type":"text/html","collector_version":"..."}}'></textarea><button>OPSEC prüfen und Quelle ausführen</button></form></div>
<div><form method='post' action='/build220/result-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>Ergebnis prüfen und AI trainieren</h3><input name='result_id' placeholder='Result-ID' required><select name='decision'><option value='accepted_candidate'>Kandidat akzeptieren</option><option value='needs_more_evidence'>Weitere Belege</option><option value='rejected'>Verwerfen</option><option value='duplicate'>Duplikat</option></select><textarea name='reason' rows='5' placeholder='Mindestens 20 Zeichen: fachliche Begründung' required></textarea><button>Review und Trainingsentwurf speichern</button></form></div></div>
<div class='table-wrap'><table><thead><tr><th>Adapter</th><th>Typ</th><th>Titel</th><th>Review</th><th>Evidence</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>
"""
        marker = "<section class='card' id='build219_reliability'>"
        return base.replace(marker, panel + marker, 1) if marker in base else base + panel

    # ---------- internals ----------
    def _http_json(self, url: str, allowed_hosts: set[str], headers: Mapping[str, str]) -> dict[str, Any]:
        if self.http_fetcher:
            return dict(self.http_fetcher(url=url, allowed_hosts=allowed_hosts, headers=headers))
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts or parsed.username or parsed.password:
            raise PermissionError("source endpoint rejected")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(), _NoRedirect())
        req = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            with opener.open(req, timeout=25) as response:
                raw = response.read(self.MAX_HTTP_BYTES + 1)
                if len(raw) > self.MAX_HTTP_BYTES:
                    raise ValueError("source response exceeds size limit")
                body = raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
                return {"status": int(response.status), "headers": {k: v for k, v in response.headers.items() if k.lower() in {"content-type", "etag", "last-modified", "retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"}}, "json": json.loads(body) if body.strip() else {}, "body_sha256": hashlib.sha256(raw).hexdigest(), "url": url}
        except urllib.error.HTTPError as exc:
            raw = exc.read(self.MAX_HTTP_BYTES + 1) if exc.fp else b""
            try:
                body: Any = json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
            except Exception:
                body = {"text": raw.decode("utf-8", errors="replace")[:2000]}
            return {"status": int(exc.code), "headers": dict(exc.headers.items()) if exc.headers else {}, "json": body, "body_sha256": hashlib.sha256(raw).hexdigest(), "url": url}

    def _validate_target(self, adapter_key: str, target_type: str, target: str) -> str:
        value = _text(target, 4000).strip()
        if adapter_key == "wayback_public":
            parsed = urllib.parse.urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("public HTTP(S) URL required")
            host = parsed.hostname.casefold()
            if host in {"localhost", "localhost.localdomain"}:
                raise ValueError("local URLs are not allowed")
            try:
                addr = ipaddress.ip_address(host)
                if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                    raise ValueError("private or local IP URLs are not allowed")
            except ValueError as exc:
                if "not allowed" in str(exc):
                    raise
            secret_keys = {"token", "access_token", "api_key", "apikey", "password", "session", "auth", "signature"}
            for key, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
                if key.casefold() in secret_keys:
                    raise ValueError("URL contains a sensitive query parameter")
            return value
        if adapter_key == "gleif_public":
            if len(value) < 2 or len(value) > 250:
                raise ValueError("organization query must be 2..250 characters")
            return value
        if adapter_key == "exiftool_local":
            package = self.evidence.evidence.get_package(value) if hasattr(self.evidence, "evidence") else None
            if not package or package.get("case_id") is None:
                raise ValueError("valid evidence package ID required")
            return value
        if adapter_key == "archivebox_import":
            path = Path(value).resolve()
            import_root = (self.evidence.import_root / "archivebox").resolve()
            try:
                path.relative_to(import_root)
            except ValueError as exc:
                raise ValueError("ArchiveBox import must be below the dedicated import directory") from exc
            if not path.is_file():
                raise FileNotFoundError(path)
            return str(path)
        raise ValueError("unknown adapter")

    def _store_results(self, *, run_id: str, case_id: str, adapter_key: str, results: Sequence[Mapping[str, Any]], evidence_ref: str) -> list[dict[str, Any]]:
        inserted: list[dict[str, Any]] = []
        for item in results[:100]:
            rid, now = new_id("result220"), now_ts()
            key = _text(item.get("independence_key"), 500) or _hash([adapter_key, item.get("canonical_url"), item.get("display_value")])
            if self.db.one("SELECT result_id FROM source_results_220 WHERE case_id=? AND adapter_key=? AND independence_key=?", (case_id, adapter_key, key)):
                continue
            payload = {"result_id": rid, "run_id": run_id, "case_id": case_id, "adapter_key": adapter_key, **dict(item), "evidence_ref": evidence_ref, "review_status": "unreviewed", "candidate_only": True, "created_at": now}
            self.db.execute(
                """INSERT INTO source_results_220(result_id,run_id,case_id,adapter_key,result_type,title,canonical_url,display_value,language,confidence,evidence_ref,independence_key,fields_json,limitations_json,review_status,candidate_only,created_at,payload_sha256)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rid, run_id, case_id, adapter_key, _text(item.get("result_type"), 100), _text(item.get("title"), 500), _text(item.get("canonical_url"), 3000), _text(item.get("display_value"), 3000), _text(item.get("language"), 20) or "und", max(0.0, min(1.0, float(item.get("confidence") or 0.0))), evidence_ref, key, dumps(dict(item.get("fields") or {})), dumps(list(item.get("limitations") or [])), "unreviewed", 1, now, _hash(payload)),
            )
            inserted.append(payload)
        return inserted

    def _finish_run(self, run_id: str, *, status: str, results: Sequence[Any], raw: Any, evidence_ref: str, latency_ms: int, error: Exception | None = None) -> None:
        finished = now_ts()
        metrics = {"result_count": len(results), "latency_ms": latency_ms, "candidate_only": True, "response_fingerprint": _shape(raw.get("json") if isinstance(raw, Mapping) and "json" in raw else raw)}
        self.db.execute(
            "UPDATE source_runs_220 SET status=?,finished_at=?,result_count=?,evidence_source_id=?,error_class=?,error_message=?,raw_sha256=?,metrics_json=?,payload_sha256=? WHERE run_id=?",
            (status, finished, len(results), evidence_ref, type(error).__name__ if error else "", _text(error, 2000) if error else "", _hash(raw), dumps(metrics), _hash({"run_id": run_id, "status": status, "finished_at": finished, "metrics": metrics}), run_id),
        )

    def _record_health(self, adapter_key: str, *, status: str, latency_ms: int, http_status: int, result_count: int, raw: Any, actor: str, error: Exception | None = None) -> str:
        adapter = self._adapter(adapter_key)
        required = _loads(adapter["required_fields_json"], [])
        sample = raw.get("json") if isinstance(raw, Mapping) and "json" in raw else raw
        missing = [field for field in required if not isinstance(sample, Mapping) or field not in sample]
        check_status = "contract_failed" if missing else status
        headers = {str(k).lower(): str(v) for k, v in (raw.get("headers") or {}).items()} if isinstance(raw, Mapping) else {}
        retry = headers.get("retry-after", "")
        retry_at = ""
        if retry.isdigit():
            retry_at = (datetime.now(timezone.utc) + timedelta(seconds=int(retry))).isoformat()
        cid, now = new_id("health220"), now_ts()
        payload = {"check_id": cid, "adapter_key": adapter_key, "check_type": "live_run", "status": check_status, "latency_ms": latency_ms, "http_status": http_status, "result_count": result_count, "observed_fingerprint": _shape(sample), "missing_fields": missing, "rate_limit": headers, "retry_after_at": retry_at, "error_class": type(error).__name__ if error else "", "error_message": _text(error, 1000) if error else "", "checked_by": actor, "checked_at": now}
        self.db.execute("INSERT INTO source_health_checks_220 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid, adapter_key, "live_run", check_status, latency_ms, http_status, result_count, payload["observed_fingerprint"], dumps(missing), dumps(headers), retry_at, payload["error_class"], payload["error_message"], actor, now, _hash(payload)))
        failures = self.db.one("SELECT COUNT(*) AS n FROM source_health_checks_220 WHERE adapter_key=? AND status IN ('unavailable','contract_failed') AND check_id IN (SELECT check_id FROM source_health_checks_220 WHERE adapter_key=? ORDER BY checked_at DESC LIMIT ?)", (adapter_key, adapter_key, self.FAILURE_THRESHOLD))
        if missing:
            self.db.execute("UPDATE source_adapters_220 SET health_state='quarantined',circuit_state='open',quarantine_reason=?,updated_at=? WHERE adapter_key=?", ("breaking parser contract: " + ",".join(missing), now, adapter_key))
        elif int((failures or {}).get("n", 0)) >= self.FAILURE_THRESHOLD:
            until = (datetime.now(timezone.utc) + timedelta(seconds=self.CIRCUIT_COOLDOWN_SECONDS)).isoformat()
            self.db.execute("UPDATE source_adapters_220 SET health_state='unavailable',circuit_state='open',circuit_open_until=?,updated_at=? WHERE adapter_key=?", (until, now, adapter_key))
        elif check_status == "healthy":
            self.db.execute("UPDATE source_adapters_220 SET health_state='healthy',circuit_state='closed',circuit_open_until='',updated_at=? WHERE adapter_key=?", (now, adapter_key))
        return cid

    def _adapter(self, adapter_key: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM source_adapters_220 WHERE adapter_key=?", (adapter_key,))
        if not row:
            raise KeyError(adapter_key)
        return row

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _public_adapter(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "target_types": _loads(row["target_types_json"], []), "allowed_hosts": _loads(row["allowed_hosts_json"], []), "required_fields": _loads(row["required_fields_json"], []), "network_capable": bool(row["network_capable"]), "active": bool(row["active"])}

    def _public_result(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "fields": _loads(row["fields_json"], {}), "limitations": _loads(row["limitations_json"], []), "candidate_only": True, "identity_confirmed": False}

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> str:
        prev = self.db.one("SELECT event_hash FROM build220_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "0" * 64
        eid, now = new_id("evt220"), now_ts()
        safe = {k: v for k, v in dict(payload).items() if k not in {"target_value", "token", "authorization", "raw", "stdout", "stderr"}}
        body = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": safe, "previous_hash": previous, "created_at": now}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build220_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, actor, dumps(safe), previous, event_hash, now))
        if self.audit is not None and hasattr(self.audit, "log"):
            self.audit.log(event_type, object_type, object_id, case_id, safe)
        return eid
