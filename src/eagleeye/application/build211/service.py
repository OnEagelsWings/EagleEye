from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts


SECRET_KEY = re.compile(r"(?i)(authorization|cookie|token|secret|password|api[_-]?key|session|private[_-]?key)")
TRACKING_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid", "mc_cid", "mc_eid"}
STATEMENT_KINDS = {"observation", "inference", "hypothesis"}
REVIEW_DECISIONS = {"accepted_as_observation", "rejected", "needs_more_evidence", "superseded"}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(value: Any) -> str:
    if isinstance(value, bytes):
        return _sha_bytes(value)
    return _sha_bytes(_canonical_json(value).encode("utf-8"))


def _loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _safe_text(value: Any, limit: int = 20000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _canonical_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("source_url must be a public HTTP(S) URL")
    if parts.username or parts.password:
        raise ValueError("URL credentials are prohibited")
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    clean_query: list[tuple[str, str]] = []
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        if key.casefold() in TRACKING_KEYS:
            continue
        clean_query.append((key, "[REDACTED]" if SECRET_KEY.search(key) else val))
    return urlunsplit((scheme, netloc, parts.path or "/", urlencode(sorted(clean_query)), ""))


def _safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())[:120]
    if not value or value in {".", ".."}:
        raise ValueError("invalid file name")
    return value


class Build211EvidenceProvenanceFoundationService:
    """Evidence-grade provenance and governed open-tool integration for PersonOSINT.

    Build 211 consolidates existing capture and evidence components instead of
    replacing them. Raw evidence remains owned by Build 121. Build 211 adds an
    append-only source/statement ledger, explainable human review and a narrow
    adapter boundary for independently installed open-source tools.
    """

    BUILD = "211.0"
    MAX_IMPORT_BYTES = 100 * 1024 * 1024
    MAX_TOOL_STDOUT = 5 * 1024 * 1024
    DEFAULT_PROJECTS = (
        {
            "project_id": "eagleeye_native",
            "title": "EagleEye Native Capture",
            "purpose": "Manual public-source capture and provenance without external tooling.",
            "homepage": "local://eagleeye/build211",
            "license_spdx": "EagleEye-internal",
            "integration_mode": "native",
            "executables": [],
            "capabilities": ["text_capture", "file_import", "sha256", "custody", "statements"],
            "distribution_allowed": True,
            "network_capable": False,
        },
        {
            "project_id": "exiftool",
            "title": "ExifTool",
            "purpose": "Local metadata extraction from preserved media and documents.",
            "homepage": "https://exiftool.org/",
            "license_spdx": "Artistic-1.0-Perl OR GPL-1.0-or-later",
            "integration_mode": "isolated_local_process",
            "executables": ["exiftool", "exiftool.exe"],
            "capabilities": ["metadata", "json_output", "offline", "version_args:-ver"],
            "distribution_allowed": False,
            "network_capable": False,
        },
        {
            "project_id": "singlefile",
            "title": "SingleFile",
            "purpose": "Faithful self-contained HTML capture in the existing Firefox workflow.",
            "homepage": "https://github.com/gildas-lormeau/SingleFile",
            "license_spdx": "AGPL-3.0-or-later",
            "integration_mode": "external_browser_or_cli",
            "executables": ["single-file", "single-file.exe"],
            "capabilities": ["self_contained_html", "firefox_extension", "manual_import"],
            "distribution_allowed": False,
            "network_capable": True,
        },
        {
            "project_id": "archivebox",
            "title": "ArchiveBox",
            "purpose": "Redundant local preservation as HTML, PNG, PDF, TXT, JSON, WARC and SQLite.",
            "homepage": "https://archivebox.io/",
            "license_spdx": "MIT",
            "integration_mode": "external_cli_or_api",
            "executables": ["archivebox", "archivebox.exe"],
            "capabilities": ["warc", "html", "screenshot", "pdf", "api", "webhooks"],
            "distribution_allowed": False,
            "network_capable": True,
        },
        {
            "project_id": "bellingcat_auto_archiver",
            "title": "Bellingcat Auto Archiver",
            "purpose": "Provider-oriented archival workflow for public social and media content.",
            "homepage": "https://github.com/bellingcat/auto-archiver",
            "license_spdx": "MIT",
            "integration_mode": "external_cli_or_api",
            "executables": ["auto-archiver", "auto-archiver.exe"],
            "capabilities": ["social_archiving", "provider_adapters", "manual_import"],
            "distribution_allowed": False,
            "network_capable": True,
        },
        {
            "project_id": "followthemoney",
            "title": "FollowTheMoney",
            "purpose": "Reference model for person, company, relationship and statement provenance.",
            "homepage": "https://followthemoney.tech/",
            "license_spdx": "MIT",
            "integration_mode": "schema_mapping_reference",
            "executables": ["ftm", "ftm.exe"],
            "capabilities": ["entity_schema", "statements", "dataset_provenance", "first_seen", "last_seen"],
            "distribution_allowed": False,
            "network_capable": False,
        },
    )

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        evidence: Any,
        capture: Any,
        monitoring: Any,
        ai_agents: Any,
        social: Any,
        base_dir: str | Path,
        actor: str = "system",
    ) -> None:
        self.db = db
        self.audit = audit
        self.evidence = evidence
        self.capture = capture
        self.monitoring = monitoring
        self.ai_agents = ai_agents
        self.social = social
        self.base_dir = Path(base_dir).resolve()
        self.actor = actor
        self.import_root = self.base_dir / "data" / "tool_outputs_211"
        self.bundle_root = self.base_dir / "reports" / "evidence_bundles_211"
        self.import_root.mkdir(parents=True, exist_ok=True)
        self.bundle_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Mission and open-source project registry
    # ------------------------------------------------------------------
    def seed_foundation(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "EVIDENCE FOUNDATION 211 ANLEGEN":
            raise PermissionError("explicit approval required")
        now = now_ts()
        mission = {
            "specialisation": "person_osint",
            "product_goal": "hidden_champion",
            "principles": ["efficient_search", "clear_research", "result_oriented", "open_methods"],
            "human_ai_model": "investigator_leads_ai_supports",
            "social_purpose": ["safety", "peace", "public_benefit"],
            "not_a_goal": ["feature_parity_for_its_own_sake", "opaque_mass_collection", "autonomous_accusation"],
        }
        safeguards = {
            "public_sources_only": True,
            "case_and_purpose_bound": True,
            "data_minimisation": True,
            "facts_inferences_hypotheses_separated": True,
            "automatic_identity_confirmation": False,
            "automatic_accusation": False,
            "automatic_external_action": False,
            "ai_claims_require_evidence": True,
            "human_review_required": True,
            "external_tools_write_to_core_db": False,
            "external_tool_code_bundled": False,
            "firefox_existing_browser_new_tabs": True,
        }
        payload = {"mission": mission, "safeguards": safeguards, "status": "active"}
        self.db.execute(
            "INSERT OR REPLACE INTO evidence_policies_211 VALUES(?,?,?,?,?,?,?)",
            ("default", dumps(mission), dumps(safeguards), "active", now, now, _sha(payload)),
        )
        for project in self.DEFAULT_PROJECTS:
            self._seed_project(project, now)
        self._ledger("system", "foundation_seeded", "policy", "default", payload)
        self._audit("seed", "evidence_foundation_211", "default", None, payload)
        return {
            "build": self.BUILD,
            "projects": len(self.DEFAULT_PROJECTS),
            "mission": mission,
            "safeguards": safeguards,
            "external_code_bundled": False,
        }

    def _seed_project(self, project: Mapping[str, Any], now: str) -> None:
        payload = {
            "project_id": project["project_id"],
            "title": project["title"],
            "purpose": project["purpose"],
            "homepage": project["homepage"],
            "license_spdx": project["license_spdx"],
            "integration_mode": project["integration_mode"],
            "executables": list(project["executables"]),
            "capabilities": list(project["capabilities"]),
            "distribution_allowed": bool(project["distribution_allowed"]),
            "network_capable": bool(project["network_capable"]),
        }
        existing = self.db.one("SELECT created_at FROM upstream_projects_211 WHERE project_id=?", (project["project_id"],))
        created = existing["created_at"] if existing else now
        self.db.execute(
            """INSERT OR REPLACE INTO upstream_projects_211
            (project_id,title,purpose,homepage,license_spdx,integration_mode,executable_names_json,capabilities_json,
             distribution_allowed,network_capable,enabled,review_status,detected_path,detected_version,last_checked_at,notes,created_at,updated_at,payload_sha256)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                project["project_id"], project["title"], project["purpose"], project["homepage"], project["license_spdx"],
                project["integration_mode"], dumps(list(project["executables"])), dumps(list(project["capabilities"])),
                int(bool(project["distribution_allowed"])), int(bool(project["network_capable"])),
                1 if project["project_id"] == "eagleeye_native" else 0, "approved_native" if project["project_id"] == "eagleeye_native" else "catalogued",
                "", "", "", "", created, now, _sha(payload),
            ),
        )

    def detect_tools(self) -> dict[str, Any]:
        projects = self.db.all("SELECT * FROM upstream_projects_211 ORDER BY title")
        results: list[dict[str, Any]] = []
        for project in projects:
            names = _loads(project["executable_names_json"], [])
            detected = ""
            for name in names:
                detected = shutil.which(name) or ""
                if detected:
                    break
            version = ""
            now = now_ts()
            payload = {
                "project_id": project["project_id"], "detected_path": detected,
                "detected_version": version, "last_checked_at": now,
            }
            self.db.execute(
                "UPDATE upstream_projects_211 SET detected_path=?,detected_version=?,last_checked_at=?,updated_at=? WHERE project_id=?",
                (detected, version, now, now, project["project_id"]),
            )
            results.append({**payload, "available": bool(detected) or project["project_id"] == "eagleeye_native"})
        return {"build": self.BUILD, "tools": results, "automatic_install": False, "automatic_network_execution": False}

    def enable_project(self, *, project_id: str, reviewer: str, reason: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"PROJECT 211 {project_id} FREIGEBEN":
            raise PermissionError("explicit approval required")
        project = self._project(project_id)
        if project_id != "eagleeye_native" and not project["detected_path"]:
            raise RuntimeError("project executable is not detected locally")
        if len(reason.strip()) < 10:
            raise ValueError("substantive reason required")
        now = now_ts()
        detected_version = self._detect_version(project_id, project["detected_path"]) if project["detected_path"] else "native"
        self.db.execute(
            "UPDATE upstream_projects_211 SET enabled=1,review_status='approved_local',notes=?,detected_version=?,updated_at=? WHERE project_id=?",
            (_safe_text(reason, 2000), detected_version, now, project_id),
        )
        result = {"project_id": project_id, "enabled": True, "reviewer": reviewer, "network_capable": bool(project["network_capable"]), "detected_version": detected_version}
        self._ledger("system", "upstream_project_enabled", "upstream_project", project_id, result, actor=reviewer)
        self._audit("approve", "upstream_project_211", project_id, None, result)
        return result

    # ------------------------------------------------------------------
    # Native evidence preservation and source provenance
    # ------------------------------------------------------------------
    def preserve_text_evidence(
        self,
        *,
        case_id: str,
        title: str,
        source_url: str,
        text: str,
        captured_by: str,
        published_at: str = "",
        legal_scope: str = "public_source_case_purpose",
        metadata: Mapping[str, Any] | None = None,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"EVIDENCE 211 {case_id} TEXT SPEICHERN":
            raise PermissionError("explicit approval required")
        self._require_case(case_id)
        if not title.strip() or not text.strip():
            raise ValueError("title and text are required")
        canonical = _canonical_url(source_url) if source_url else ""
        clean_metadata = self._sanitize(dict(metadata or {}))
        package = self.evidence.preserve_bytes(
            case_id=case_id,
            title=title.strip(),
            data=text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            captured_by=captured_by,
            source_url=canonical,
            source_kind="build211_manual_public_text",
            source_ref=canonical,
            metadata={
                "build": self.BUILD,
                "capture_mode": "manual_public_text",
                "content_is_untrusted": True,
                "candidate_only": True,
                **clean_metadata,
            },
            notes="Build 211 native evidence capture; review required.",
        )
        source = self._create_source(
            case_id=case_id,
            package_id=package["package_id"],
            source_kind="public_web_text",
            original_url=source_url,
            canonical_url=canonical,
            final_url=canonical,
            redirect_chain=[],
            response_headers={},
            observed_at=package["captured_at"],
            published_at=published_at,
            collector_id="eagleeye_native",
            collector_version=self.BUILD,
            upstream_project_id="eagleeye_native",
            capture_mode="manual_public_text",
            legal_scope=legal_scope,
            metadata=clean_metadata,
            created_by=captured_by,
        )
        return {"package": package, "source": source, "candidate_only": True, "ai_may_treat_as_instruction": False}

    def import_external_artifact(
        self,
        *,
        case_id: str,
        project_id: str,
        title: str,
        artifact_path: str,
        media_type: str,
        source_url: str,
        collector_version: str,
        created_by: str,
        metadata: Mapping[str, Any] | None = None,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"EVIDENCE 211 {case_id} TOOL IMPORT":
            raise PermissionError("explicit approval required")
        self._require_case(case_id)
        project = self._project(project_id)
        if project_id != "eagleeye_native" and not bool(project["enabled"]):
            raise PermissionError("project is not approved for local import")
        path = Path(artifact_path).resolve()
        try:
            path.relative_to(self.import_root)
        except ValueError as exc:
            raise ValueError(f"tool imports must be placed below {self.import_root}") from exc
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.stat().st_size <= 0 or path.stat().st_size > self.MAX_IMPORT_BYTES:
            raise ValueError("artifact is empty or exceeds the import limit")
        canonical = _canonical_url(source_url) if source_url else ""
        data = path.read_bytes()
        clean_metadata = self._sanitize({"original_file_name": path.name, **dict(metadata or {})})
        package = self.evidence.preserve_bytes(
            case_id=case_id, title=title.strip(), data=data, media_type=media_type,
            captured_by=created_by, source_url=canonical, source_kind=f"build211_external:{project_id}",
            source_ref=canonical or path.name,
            metadata={"upstream_project_id": project_id, "collector_version": collector_version, **clean_metadata},
            notes="Imported from independently installed external tool; original output preserved.",
        )
        source = self._create_source(
            case_id=case_id, package_id=package["package_id"], source_kind="external_tool_artifact",
            original_url=source_url, canonical_url=canonical, final_url=canonical, redirect_chain=[], response_headers={},
            observed_at=package["captured_at"], published_at="", collector_id=project_id,
            collector_version=collector_version, upstream_project_id=project_id, capture_mode="external_tool_import",
            legal_scope="public_source_case_purpose", metadata=clean_metadata, created_by=created_by,
        )
        result = {"package": package, "source": source, "project": project["title"], "external_tool_code_bundled": False}
        self._ledger(case_id, "external_artifact_imported", "evidence_source", source["source_id"], result, actor=created_by)
        return result

    def plan_external_capture(
        self, *, case_id: str, project_id: str, target_url: str, purpose: str,
        created_by: str, confirmation: str,
    ) -> dict[str, Any]:
        """Create a governed handoff without launching a browser, CLI or network request."""
        if confirmation != f"EXTERNAL CAPTURE 211 {case_id} PLANEN":
            raise PermissionError("explicit approval required")
        self._require_case(case_id)
        project = self._project(project_id)
        if project_id not in {"singlefile", "archivebox", "bellingcat_auto_archiver"}:
            raise ValueError("project does not expose a Build-211 capture handoff")
        if not bool(project["enabled"]):
            raise PermissionError("project is not approved for local use")
        canonical = _canonical_url(target_url)
        if len(purpose.strip()) < 12:
            raise ValueError("substantive case purpose required")
        run_id = new_id("toolrun211")
        now = now_ts()
        options = {
            "handoff_only": True,
            "manual_execution_required": True,
            "existing_firefox_required": project_id == "singlefile",
            "import_root": str((self.import_root / project_id).resolve()),
        }
        payload = {
            "run_id": run_id, "case_id": case_id, "project_id": project_id, "package_id": "",
            "purpose": _safe_text(purpose, 2000), "input_ref": canonical, "options": options,
            "status": "awaiting_manual_external_capture", "created_by": created_by, "created_at": now,
        }
        (self.import_root / project_id).mkdir(parents=True, exist_ok=True)
        self.db.execute(
            """INSERT INTO tool_runs_211 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, case_id, project_id, "", payload["purpose"], canonical, dumps(options),
             "awaiting_manual_external_capture", project["detected_path"], project["detected_version"],
             "", "", None, "", "", "", created_by, now, now, _sha(payload)),
        )
        self._ledger(case_id, "external_capture_handoff_planned", "tool_run", run_id, payload, actor=created_by)
        return {
            **payload, "automatic_execution": False, "automatic_network_request": False,
            "identity_confirmed": False, "external_tool_code_bundled": False,
        }

    def import_singlefile_capture(
        self, *, case_id: str, artifact_path: str, title: str, source_url: str,
        created_by: str, collector_version: str = "unknown", confirmation: str,
    ) -> dict[str, Any]:
        path = Path(artifact_path).resolve()
        try:
            path.relative_to((self.import_root / "singlefile").resolve())
        except ValueError as exc:
            raise ValueError("SingleFile imports must be placed in the dedicated project import directory") from exc
        if path.suffix.casefold() not in {".html", ".htm"}:
            raise ValueError("SingleFile import must be a self-contained HTML file")
        return self.import_external_artifact(
            case_id=case_id, project_id="singlefile", title=title, artifact_path=artifact_path,
            media_type="text/html", source_url=source_url, collector_version=collector_version,
            created_by=created_by, metadata={"adapter": "singlefile_211", "capture_contract": "self_contained_html"},
            confirmation=confirmation,
        )

    def import_archivebox_capture(
        self, *, case_id: str, artifact_path: str, title: str, source_url: str, media_type: str,
        created_by: str, collector_version: str = "unknown", confirmation: str,
    ) -> dict[str, Any]:
        path = Path(artifact_path).resolve()
        try:
            path.relative_to((self.import_root / "archivebox").resolve())
        except ValueError as exc:
            raise ValueError("ArchiveBox imports must be placed in the dedicated project import directory") from exc
        name = path.name.casefold()
        allowed = (".html", ".htm", ".pdf", ".png", ".json", ".warc", ".warc.gz")
        if not any(name.endswith(suffix) for suffix in allowed):
            raise ValueError("ArchiveBox import format is not supported by the Build-211 adapter")
        return self.import_external_artifact(
            case_id=case_id, project_id="archivebox", title=title, artifact_path=artifact_path,
            media_type=media_type, source_url=source_url, collector_version=collector_version,
            created_by=created_by, metadata={"adapter": "archivebox_211", "capture_contract": "redundant_open_format"},
            confirmation=confirmation,
        )

    def _create_source(
        self,
        *,
        case_id: str,
        package_id: str,
        source_kind: str,
        original_url: str,
        canonical_url: str,
        final_url: str,
        redirect_chain: Sequence[str],
        response_headers: Mapping[str, Any],
        observed_at: str,
        published_at: str,
        collector_id: str,
        collector_version: str,
        upstream_project_id: str,
        capture_mode: str,
        legal_scope: str,
        metadata: Mapping[str, Any],
        created_by: str,
    ) -> dict[str, Any]:
        source_id = new_id("source211")
        now = now_ts()
        clean_headers = self._sanitize(dict(response_headers))
        clean_meta = self._sanitize(dict(metadata))
        payload = {
            "source_id": source_id, "case_id": case_id, "package_id": package_id,
            "source_kind": source_kind, "original_url": (_canonical_url(original_url) if original_url else ""),
            "canonical_url": canonical_url, "final_url": final_url,
            "redirect_chain": list(redirect_chain), "response_headers": clean_headers,
            "observed_at": observed_at, "published_at": published_at, "collector_id": collector_id,
            "collector_version": collector_version, "upstream_project_id": upstream_project_id,
            "capture_mode": capture_mode, "legal_scope": legal_scope,
            "candidate_only": True, "content_is_untrusted": True, "metadata": clean_meta,
            "created_by": created_by, "created_at": now,
        }
        self.db.execute(
            """INSERT INTO evidence_sources_211
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                source_id, case_id, package_id, source_kind, (_canonical_url(original_url) if original_url else ""), canonical_url, final_url,
                dumps(list(redirect_chain)), dumps(clean_headers), observed_at, _safe_text(published_at, 64), collector_id,
                collector_version, upstream_project_id, capture_mode, legal_scope, 1, 1, dumps(clean_meta), created_by, now, _sha(payload),
            ),
        )
        self._ledger(case_id, "evidence_source_created", "evidence_source", source_id, payload, actor=created_by)
        self._audit("create", "evidence_source_211", source_id, case_id, {"package_id": package_id, "candidate_only": True})
        return self.get_source(source_id)

    # ------------------------------------------------------------------
    # Statement-level provenance: observation != inference != hypothesis
    # ------------------------------------------------------------------
    def create_statement(
        self,
        *,
        case_id: str,
        source_id: str,
        entity_ref: str,
        schema_name: str,
        predicate: str,
        value: Any,
        original_value: str,
        dataset_id: str,
        origin: str,
        statement_kind: str,
        confidence: float,
        created_by: str,
        value_language: str = "",
        first_seen: str = "",
        last_seen: str = "",
        limitations: Sequence[str] = (),
        link_object_type: str = "",
        link_object_id: str = "",
        link_relation: str = "supports",
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"STATEMENT 211 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        if statement_kind not in STATEMENT_KINDS:
            raise ValueError("invalid statement kind")
        if not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        source = self.get_source(source_id)
        if source["case_id"] != case_id:
            raise ValueError("cross-case statement rejected")
        if not entity_ref.strip() or not schema_name.strip() or not predicate.strip() or not dataset_id.strip() or not origin.strip():
            raise ValueError("entity_ref, schema_name, predicate, dataset_id and origin are required")
        now = now_ts()
        first = first_seen.strip() or source["observed_at"]
        last = last_seen.strip() or first
        limits = list(dict.fromkeys([_safe_text(v, 1000) for v in limitations if str(v).strip()]))
        mandatory = {
            "observation": ["source_may_be_inaccurate", "identity_link_not_automatically_confirmed"],
            "inference": ["inference_not_fact", "independent_verification_required"],
            "hypothesis": ["hypothesis_not_fact", "counter_evidence_required"],
        }[statement_kind]
        limits = list(dict.fromkeys(limits + mandatory))
        statement_id = new_id("stmt211")
        payload = {
            "statement_id": statement_id, "case_id": case_id, "source_id": source_id,
            "package_id": source["package_id"], "entity_ref": entity_ref.strip(), "schema_name": schema_name.strip(),
            "predicate": predicate.strip(), "value": value, "original_value": _safe_text(original_value),
            "value_language": value_language.strip(), "dataset_id": dataset_id.strip(), "origin": origin.strip(),
            "first_seen": first, "last_seen": last, "statement_kind": statement_kind,
            "confidence": round(float(confidence), 6), "review_status": "candidate", "limitations": limits,
            "created_by": created_by, "created_at": now,
        }
        self.db.execute(
            """INSERT INTO evidence_statements_211
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                statement_id, case_id, source_id, source["package_id"], entity_ref.strip(), schema_name.strip(), predicate.strip(),
                dumps(value), _safe_text(original_value), value_language.strip(), dataset_id.strip(), origin.strip(), first, last,
                statement_kind, round(float(confidence), 6), "candidate", dumps(limits), created_by, now, _sha(payload),
            ),
        )
        link = None
        if link_object_type.strip() and link_object_id.strip():
            link = self.link_statement(
                statement_id=statement_id, object_type=link_object_type, object_id=link_object_id,
                relation=link_relation, created_by=created_by,
                confirmation=f"STATEMENT LINK 211 {statement_id} ANLEGEN",
            )
        self._ledger(case_id, "statement_created", "evidence_statement", statement_id, payload, actor=created_by)
        self._audit("create", "evidence_statement_211", statement_id, case_id, {"kind": statement_kind, "source_id": source_id})
        return {"statement": self.get_statement(statement_id), "link": link, "identity_confirmed": False}

    def link_statement(
        self,
        *,
        statement_id: str,
        object_type: str,
        object_id: str,
        relation: str,
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"STATEMENT LINK 211 {statement_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        statement = self.get_statement(statement_id)
        link_id = new_id("slink211")
        now = now_ts()
        payload = {
            "link_id": link_id, "statement_id": statement_id, "case_id": statement["case_id"],
            "object_type": _safe_text(object_type, 100), "object_id": _safe_text(object_id, 300),
            "relation": _safe_text(relation, 100), "created_by": created_by, "created_at": now,
        }
        try:
            self.db.execute(
                "INSERT INTO evidence_statement_links_211 VALUES(?,?,?,?,?,?,?,?,?)",
                (link_id, statement_id, statement["case_id"], payload["object_type"], payload["object_id"], payload["relation"], created_by, now, _sha(payload)),
            )
        except Exception:
            existing = self.db.one(
                "SELECT * FROM evidence_statement_links_211 WHERE statement_id=? AND object_type=? AND object_id=? AND relation=?",
                (statement_id, payload["object_type"], payload["object_id"], payload["relation"]),
            )
            if existing:
                return existing
            raise
        self._ledger(statement["case_id"], "statement_linked", "statement_link", link_id, payload, actor=created_by)
        return payload

    def review_statement(
        self,
        *,
        statement_id: str,
        reviewer: str,
        decision: str,
        reason: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"STATEMENT REVIEW 211 {statement_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if decision not in REVIEW_DECISIONS:
            raise ValueError("invalid decision")
        if len(reason.strip()) < 12:
            raise ValueError("substantive review reason required")
        statement = self.get_statement(statement_id)
        if decision == "accepted_as_observation" and statement["statement_kind"] != "observation":
            raise ValueError("inferences and hypotheses cannot be accepted as observations")
        if decision == "accepted_as_observation":
            package_check = self.evidence.verify_package(statement["package_id"])
            if not package_check["ok"]:
                raise RuntimeError("supporting evidence failed integrity verification")
        if statement["origin"].casefold().startswith("ai_") and reviewer.strip() == statement["created_by"].strip():
            raise ValueError("AI-originated statements require an independent human reviewer")
        review_id = new_id("sreview211")
        now = now_ts()
        payload = {
            "review_id": review_id, "statement_id": statement_id, "case_id": statement["case_id"],
            "reviewer": reviewer, "decision": decision, "reason": _safe_text(reason, 4000), "created_at": now,
        }
        self.db.execute(
            "INSERT INTO evidence_statement_reviews_211 VALUES(?,?,?,?,?,?,?,?)",
            (review_id, statement_id, statement["case_id"], reviewer, decision, payload["reason"], now, _sha(payload)),
        )
        self._ledger(statement["case_id"], "statement_reviewed", "statement_review", review_id, payload, actor=reviewer)
        self._audit("review", "evidence_statement_211", statement_id, statement["case_id"], {"decision": decision, "review_id": review_id})
        return {**payload, "identity_confirmed": False, "statement_mutated": False}

    # ------------------------------------------------------------------
    # Governed local tool runs: Build 211 implements ExifTool only
    # ------------------------------------------------------------------
    def plan_tool_run(
        self,
        *,
        case_id: str,
        project_id: str,
        package_id: str,
        purpose: str,
        options: Mapping[str, Any] | None,
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"TOOL RUN 211 {case_id} PLANEN":
            raise PermissionError("explicit approval required")
        self._require_case(case_id)
        project = self._project(project_id)
        if not bool(project["enabled"]):
            raise PermissionError("project is not approved for local execution")
        package = self.evidence.get_package(package_id)
        if package["case_id"] != case_id:
            raise ValueError("cross-case tool run rejected")
        clean_options = self._sanitize(dict(options or {}))
        if self._contains_redaction(clean_options):
            raise ValueError("secrets are not allowed in tool options")
        run_id = new_id("toolrun211")
        now = now_ts()
        payload = {
            "run_id": run_id, "case_id": case_id, "project_id": project_id, "package_id": package_id,
            "purpose": _safe_text(purpose, 2000), "input_ref": package_id, "options": clean_options,
            "status": "planned", "created_by": created_by, "created_at": now,
        }
        self.db.execute(
            """INSERT INTO tool_runs_211
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id, case_id, project_id, package_id, payload["purpose"], package_id, dumps(clean_options), "planned",
                project["detected_path"], project["detected_version"], "", "", None, "", "", "", created_by, now, now, _sha(payload),
            ),
        )
        self._ledger(case_id, "tool_run_planned", "tool_run", run_id, payload, actor=created_by)
        return {**payload, "network_execution": False, "shell": False}

    def execute_exiftool(self, *, run_id: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"TOOL RUN 211 {run_id} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        run = self._tool_run(run_id)
        if run["project_id"] != "exiftool":
            raise ValueError("Build 211 only executes the offline ExifTool adapter")
        if run["status"] == "succeeded":
            return {"run_id": run_id, "status": "succeeded", "artifact_id": run["artifact_id"], "idempotent_replay": True}
        if run["status"] != "planned":
            raise RuntimeError(f"tool run is not executable from state {run['status']}")
        project = self._project("exiftool")
        executable = project["detected_path"] or shutil.which("exiftool") or shutil.which("exiftool.exe")
        if not executable:
            raise RuntimeError("ExifTool is not installed or detected")
        package = self.evidence.get_package(run["package_id"])
        raw = self.evidence.read_raw(run["package_id"])
        started = now_ts()
        self.db.execute("UPDATE tool_runs_211 SET status='running',started_at=?,updated_at=? WHERE run_id=?", (started, started, run_id))
        try:
            with tempfile.TemporaryDirectory(prefix="eagleeye-exiftool-211-") as temp_dir:
                temp_path = Path(temp_dir) / (Path(package["raw_relpath"]).name or "evidence.bin")
                temp_path.write_bytes(raw)
                env = {
                    key: os.environ[key]
                    for key in ("PATH", "SystemRoot", "WINDIR", "PATHEXT", "COMSPEC", "TEMP", "TMP")
                    if key in os.environ
                }
                env.update({"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
                proc = subprocess.run(
                    [str(executable), "-json", "-G1", "-a", "-s", str(temp_path)],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=30, check=False, shell=False, env=env,
                )
                stdout = proc.stdout[: self.MAX_TOOL_STDOUT]
                stderr = proc.stderr.decode("utf-8", errors="replace")[:4000]
                if proc.returncode != 0:
                    raise RuntimeError(f"ExifTool failed with exit code {proc.returncode}: {stderr}")
                parsed = json.loads(stdout.decode("utf-8", errors="strict"))
                clean = self._sanitize(parsed)
                for item in clean if isinstance(clean, list) else []:
                    if isinstance(item, dict) and "SourceFile" in item:
                        item["SourceFile"] = Path(str(item["SourceFile"])).name
                output = _canonical_json({
                    "format": "eagleeye-exiftool-211", "package_id": run["package_id"],
                    "project_version": project["detected_version"], "metadata": clean,
                    "limitations": ["metadata_can_be_modified", "absence_of_metadata_is_not_evidence", "human_review_required"],
                }).encode("utf-8")
                artifact = self.evidence.create_artifact(
                    package_id=run["package_id"], layer="derived", data=output, media_type="application/json",
                    created_by=run["created_by"], parser_name="ExifTool adapter 211",
                    parser_version=project["detected_version"] or "unknown", parser_config={"args": ["-json", "-G1", "-a", "-s"]},
                )
                finished = now_ts()
                result_payload = {
                    "run_id": run_id, "status": "succeeded", "exit_code": proc.returncode,
                    "stdout_sha256": _sha_bytes(stdout), "artifact_id": artifact["artifact_id"],
                    "finished_at": finished,
                }
                self.db.execute(
                    """UPDATE tool_runs_211 SET status='succeeded',finished_at=?,exit_code=?,stdout_sha256=?,stderr_redacted=?,artifact_id=?,updated_at=?,payload_sha256=? WHERE run_id=?""",
                    (finished, proc.returncode, result_payload["stdout_sha256"], self._redact_text(stderr), artifact["artifact_id"], finished, _sha(result_payload), run_id),
                )
                self._ledger(run["case_id"], "tool_run_succeeded", "tool_run", run_id, result_payload, actor=run["created_by"])
                self._audit("execute", "tool_run_211", run_id, run["case_id"], result_payload)
                return {**result_payload, "network_execution": False, "shell": False, "identity_confirmed": False}
        except Exception as exc:
            finished = now_ts()
            err = self._redact_text(str(exc))[:4000]
            payload = {"run_id": run_id, "status": "failed", "error": err, "finished_at": finished}
            self.db.execute(
                "UPDATE tool_runs_211 SET status='failed',finished_at=?,stderr_redacted=?,updated_at=?,payload_sha256=? WHERE run_id=?",
                (finished, err, finished, _sha(payload), run_id),
            )
            self._ledger(run["case_id"], "tool_run_failed", "tool_run", run_id, payload, actor=run["created_by"])
            raise

    # ------------------------------------------------------------------
    # Integrity, approval and reproducible bundle
    # ------------------------------------------------------------------
    def approve_package_export(self, *, package_id: str, reviewer: str, reason: str, confirmation: str, case_id: str = "") -> dict[str, Any]:
        if confirmation != f"EVIDENCE EXPORT 211 {package_id} FREIGEBEN":
            raise PermissionError("explicit approval required")
        package = self.evidence.get_package(package_id)
        if case_id and package["case_id"] != case_id:
            raise ValueError("cross-case export approval rejected")
        self.evidence.set_export_policy(
            package_id=package_id, export_allowed=True, redaction_required=True,
            actor=reviewer, reason=reason,
        )
        payload = {"package_id": package_id, "reviewer": reviewer, "reason": _safe_text(reason, 4000), "redaction_required": True}
        self._ledger(package["case_id"], "package_export_approved", "evidence_package", package_id, payload, actor=reviewer)
        return {"package_id": package_id, "export_allowed": True, "redaction_required": True}

    def verify_case(self, *, case_id: str) -> dict[str, Any]:
        self._require_case(case_id)
        sources = self.db.all("SELECT * FROM evidence_sources_211 WHERE case_id=? ORDER BY created_at,source_id", (case_id,))
        statements = self.db.all("SELECT * FROM evidence_statements_211 WHERE case_id=? ORDER BY rowid", (case_id,))
        links = self.db.all("SELECT * FROM evidence_statement_links_211 WHERE case_id=? ORDER BY rowid", (case_id,))
        reviews = self.db.all("SELECT * FROM evidence_statement_reviews_211 WHERE case_id=? ORDER BY rowid", (case_id,))
        errors: list[str] = []
        packages: dict[str, dict[str, Any]] = {}
        for source in sources:
            package_id = source["package_id"]
            if package_id not in packages:
                verification = self.evidence.verify_package(package_id)
                packages[package_id] = verification
                if not verification["ok"]:
                    errors.extend(f"package:{package_id}:{item}" for item in verification["errors"])
            expected = self._source_hash(source)
            if expected != source["payload_sha256"]:
                errors.append(f"source_hash_mismatch:{source['source_id']}")
        for statement in statements:
            expected = self._statement_hash(statement)
            if expected != statement["payload_sha256"]:
                errors.append(f"statement_hash_mismatch:{statement['statement_id']}")
        for link in links:
            if self._link_hash(link) != link["payload_sha256"]:
                errors.append(f"statement_link_hash_mismatch:{link['link_id']}")
        for review in reviews:
            if self._review_hash(review) != review["payload_sha256"]:
                errors.append(f"statement_review_hash_mismatch:{review['review_id']}")
        ledger = self._verify_ledger(case_id)
        errors.extend(ledger["errors"])
        result = {
            "case_id": case_id, "ok": not errors, "errors": errors,
            "packages": len(packages), "sources": len(sources), "statements": len(statements),
            "statement_links": len(links), "statement_reviews": len(reviews),
            "ledger_events": ledger["events"], "append_only": True,
        }
        self._audit("verify", "evidence_case_211", case_id, case_id, result)
        return result

    def export_case_bundle(
        self,
        *,
        case_id: str,
        package_ids: Sequence[str],
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"EVIDENCE BUNDLE 211 {case_id} ERSTELLEN":
            raise PermissionError("explicit approval required")
        package_ids = list(dict.fromkeys(x.strip() for x in package_ids if x and x.strip()))
        if not package_ids:
            raise ValueError("at least one package is required")
        verification = self.verify_case(case_id=case_id)
        if not verification["ok"]:
            raise RuntimeError("case evidence failed integrity verification")
        inner = self.evidence.export_packages(
            case_id=case_id, package_ids=package_ids, created_by=created_by, redaction_profile="investigator_review_211",
        )
        sources = self.db.all(
            f"SELECT * FROM evidence_sources_211 WHERE case_id=? AND package_id IN ({','.join('?' for _ in package_ids)}) ORDER BY created_at,source_id",
            (case_id, *package_ids),
        )
        source_ids = [s["source_id"] for s in sources]
        statements: list[dict[str, Any]] = []
        if source_ids:
            statements = self.db.all(
                f"SELECT * FROM evidence_statements_211 WHERE source_id IN ({','.join('?' for _ in source_ids)}) ORDER BY created_at,statement_id",
                source_ids,
            )
        statement_ids = [s["statement_id"] for s in statements]
        reviews: list[dict[str, Any]] = []
        if statement_ids:
            reviews = self.db.all(
                f"SELECT * FROM evidence_statement_reviews_211 WHERE statement_id IN ({','.join('?' for _ in statement_ids)}) ORDER BY rowid",
                statement_ids,
            )
        ledger = self.db.all("SELECT * FROM evidence_ledger_events_211 WHERE case_id=? ORDER BY rowid", (case_id,))
        bundle_id = new_id("bundle211")
        created_at = now_ts()
        manifest = {
            "format": "eagleeye-personosint-evidence-bundle-211",
            "bundle_id": bundle_id,
            "case_id": case_id,
            "created_at": created_at,
            "created_by": created_by,
            "mission": "clear, reviewable PersonOSINT for public benefit",
            "package_ids": package_ids,
            "statement_ids": statement_ids,
            "inner_export_sha256": _sha_bytes(Path(inner["path"]).read_bytes()),
            "guarantees": {
                "raw_evidence_hashed": True,
                "source_provenance_included": True,
                "statement_kinds_separated": True,
                "human_reviews_included": True,
                "automatic_identity_confirmation": False,
            },
        }
        bundle_path = self.bundle_root / f"{bundle_id}.zip"
        provenance = {
            "sources": [self._public_source_row(x) for x in sources],
            "statements": [self._public_statement_row(x) for x in statements],
            "reviews": reviews,
            "ledger": ledger,
        }
        provenance_bytes = _canonical_json(provenance).encode("utf-8")
        inner_bytes = Path(inner["path"]).read_bytes()
        manifest["provenance_sha256"] = _sha_bytes(provenance_bytes)
        manifest["inner_export_sha256"] = _sha_bytes(inner_bytes)
        manifest_bytes = _canonical_json(manifest).encode("utf-8")
        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr("manifest.json", manifest_bytes)
            archive.writestr("manifest.sha256", f"{_sha_bytes(manifest_bytes)}  manifest.json\n")
            archive.writestr("provenance.json", provenance_bytes)
            archive.writestr("provenance.sha256", f"{_sha_bytes(provenance_bytes)}  provenance.json\n")
            archive.writestr("evidence-121.zip", inner_bytes)
            archive.writestr("evidence-121.zip.sha256", f"{_sha_bytes(inner_bytes)}  evidence-121.zip\n")
        relpath = bundle_path.relative_to(self.bundle_root).as_posix()
        payload = {
            "bundle_id": bundle_id, "case_id": case_id, "package_ids": package_ids,
            "statement_ids": statement_ids, "bundle_relpath": relpath,
            "manifest_sha256": _sha_bytes(manifest_bytes), "byte_size": bundle_path.stat().st_size,
            "created_by": created_by, "created_at": created_at,
        }
        self.db.execute(
            "INSERT INTO evidence_bundles_211 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (bundle_id, case_id, dumps(package_ids), dumps(statement_ids), relpath, payload["manifest_sha256"], payload["byte_size"], created_by, created_at, _sha(payload)),
        )
        self._ledger(case_id, "evidence_bundle_created", "evidence_bundle", bundle_id, payload, actor=created_by)
        self._audit("export", "evidence_bundle_211", bundle_id, case_id, {"package_count": len(package_ids), "statement_count": len(statement_ids)})
        return {**payload, "path": str(bundle_path), "verification": self.verify_bundle(bundle_id)}

    def verify_bundle(self, bundle_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_bundles_211 WHERE bundle_id=?", (bundle_id,))
        if not row:
            raise KeyError(bundle_id)
        path = (self.bundle_root / row["bundle_relpath"]).resolve()
        try:
            path.relative_to(self.bundle_root)
        except ValueError as exc:
            raise RuntimeError("bundle path escaped storage root") from exc
        errors: list[str] = []
        if not path.is_file():
            errors.append("bundle_file_missing")
        elif path.stat().st_size != int(row["byte_size"]):
            errors.append("bundle_size_mismatch")
        try:
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None:
                    errors.append("zip_crc_failure")
                manifest = archive.read("manifest.json")
                manifest_data = json.loads(manifest.decode("utf-8"))
                provenance = archive.read("provenance.json")
                inner = archive.read("evidence-121.zip")
                if archive.read("manifest.sha256").decode().split()[0] != _sha_bytes(manifest):
                    errors.append("manifest_hash_file_mismatch")
                if row["manifest_sha256"] != _sha_bytes(manifest):
                    errors.append("manifest_database_hash_mismatch")
                if archive.read("provenance.sha256").decode().split()[0] != _sha_bytes(provenance):
                    errors.append("provenance_hash_mismatch")
                if manifest_data.get("provenance_sha256") != _sha_bytes(provenance):
                    errors.append("manifest_provenance_hash_mismatch")
                if archive.read("evidence-121.zip.sha256").decode().split()[0] != _sha_bytes(inner):
                    errors.append("inner_export_hash_mismatch")
                if manifest_data.get("inner_export_sha256") != _sha_bytes(inner):
                    errors.append("manifest_inner_export_hash_mismatch")
        except (OSError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
            errors.append(f"bundle_read_error:{type(exc).__name__}")
        return {"bundle_id": bundle_id, "ok": not errors, "errors": errors, "path": str(path)}

    # ------------------------------------------------------------------
    # Dashboard and UI
    # ------------------------------------------------------------------
    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._require_case(case_id)
        if not self.db.one("SELECT policy_id FROM evidence_policies_211 WHERE policy_id=\"default\""):
            self.seed_foundation(confirmation="EVIDENCE FOUNDATION 211 ANLEGEN")
        count = lambda sql, params=(): int((self.db.one(sql, params) or {"n": 0})["n"])
        tools = self.db.all("SELECT * FROM upstream_projects_211 ORDER BY title")
        sources = self.db.all("SELECT * FROM evidence_sources_211 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,))
        statements = self.db.all(
            """SELECT s.*, COALESCE((SELECT r.decision FROM evidence_statement_reviews_211 r
               WHERE r.statement_id=s.statement_id ORDER BY r.rowid DESC LIMIT 1), s.review_status) AS effective_review_status
               FROM evidence_statements_211 s WHERE s.case_id=? ORDER BY s.created_at DESC LIMIT 50""",
            (case_id,),
        )
        for statement in statements:
            statement["review_status"] = statement.pop("effective_review_status")
        runs = self.db.all("SELECT * FROM tool_runs_211 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,))
        bundles = self.db.all("SELECT * FROM evidence_bundles_211 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        return {
            "build": self.BUILD, "case_id": case_id,
            "counts": {
                "sources": count("SELECT COUNT(*) AS n FROM evidence_sources_211 WHERE case_id=?", (case_id,)),
                "statements": count("SELECT COUNT(*) AS n FROM evidence_statements_211 WHERE case_id=?", (case_id,)),
                "reviews": count("SELECT COUNT(*) AS n FROM evidence_statement_reviews_211 WHERE case_id=?", (case_id,)),
                "ledger_events": count("SELECT COUNT(*) AS n FROM evidence_ledger_events_211 WHERE case_id=?", (case_id,)),
                "bundles": count("SELECT COUNT(*) AS n FROM evidence_bundles_211 WHERE case_id=?", (case_id,)),
            },
            "tools": tools, "sources": sources, "statements": statements, "runs": runs, "bundles": bundles,
            "mission": "Effiziente, klare und ergebnisorientierte Personenrecherche – der Ermittler führt, die AI unterstützt.",
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        data = self.dashboard(case_id=case_id)
        esc = lambda v: html.escape(str(v or ""), quote=True)
        c = data["counts"]
        tools = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                esc(row["title"]), esc(row["license_spdx"]), esc(row["integration_mode"]),
                "ja" if row["detected_path"] or row["project_id"] == "eagleeye_native" else "nein",
                "freigegeben" if row["enabled"] else "nur katalogisiert",
            ) for row in data["tools"]
        ) or "<tr><td colspan='5'>Registry noch nicht angelegt.</td></tr>"
        sources = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td><code>{}</code></td></tr>".format(
                esc(row["created_at"]), esc(row["collector_id"]), esc(row["source_kind"]), esc(row["package_id"]),
            ) for row in data["sources"]
        ) or "<tr><td colspan='4'>Noch keine Build-211-Quelle.</td></tr>"
        statements = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{:.0f}%</td></tr>".format(
                esc(row["statement_kind"]), esc(row["entity_ref"]), esc(row["predicate"]), esc(row["review_status"]), float(row["confidence"]) * 100,
            ) for row in data["statements"]
        ) or "<tr><td colspan='5'>Noch keine quellengebundene Aussage.</td></tr>"
        return f"""
        <div class='notice'><b>Evidence &amp; Provenance Foundation 211</b><br>
        {esc(data['mission'])} Build 211 macht aus Fundstellen nachvollziehbare Belege und trennt Beobachtung, Schlussfolgerung und Hypothese technisch. Fremdwerkzeuge bleiben eigenständig installiert und schreiben niemals direkt in den EagleEye-Kern.</div>
        <div class='metrics'>
          <div class='metric'><div class='label'>Quellenartefakte</div><div class='value'>{c['sources']}</div></div>
          <div class='metric'><div class='label'>Aussagen</div><div class='value'>{c['statements']}</div></div>
          <div class='metric'><div class='label'>Reviews</div><div class='value'>{c['reviews']}</div></div>
          <div class='metric'><div class='label'>Ledger-Ereignisse</div><div class='value'>{c['ledger_events']}</div></div>
          <div class='metric'><div class='label'>Beweis-Bundles</div><div class='value'>{c['bundles']}</div></div>
        </div>
        <div class='panel'><h2>Öffentliche Fundstelle beweissicher übernehmen</h2>
          <form method='post' action='/evidence211/preserve-text'>
            <input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'>
            <div class='form-grid'>
              <div class='field'><label>Titel</label><input name='title' required></div>
              <div class='field'><label>Öffentliche Quell-URL</label><input name='source_url' type='url'></div>
              <div class='field'><label>Veröffentlichungszeit, falls bekannt</label><input name='published_at'></div>
              <div class='field'><label>Rechtlicher/Zweck-Scope</label><input name='legal_scope' value='public_source_case_purpose'></div>
            </div>
            <div class='field'><label>Unveränderter Textinhalt</label><textarea name='text' rows='8' required></textarea></div>
            <p><button>Als Kandidatenbeleg sichern</button></p>
          </form>
        </div>
        <div class='two-col'>
          <div class='panel'><h2>Quellen</h2><div class='table-wrap'><table><thead><tr><th>Zeit</th><th>Collector</th><th>Art</th><th>Package-ID</th></tr></thead><tbody>{sources}</tbody></table></div></div>
          <div class='panel'><h2>Integrationsregistry</h2><p><form method='post' action='/evidence211/detect-tools'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><button class='ghost'>Lokal installierte Werkzeuge prüfen</button></form></p><div class='table-wrap'><table><thead><tr><th>Projekt</th><th>Lizenz</th><th>Modus</th><th>Vorhanden</th><th>Status</th></tr></thead><tbody>{tools}</tbody></table></div></div>
        </div>
        <div class='panel'><h2>Kontrollierte Open-Source-Handoffs</h2>
          <div class='notice warn'>EagleEye installiert nichts automatisch und startet keine externen Netzrecherchen. Ein Tool wird zuerst lokal erkannt, dann begründet freigegeben. SingleFile/ArchiveBox-Captures werden außerhalb des Kerns erzeugt und anschließend aus <code>{esc(str(self.import_root))}</code> importiert.</div>
          <div class='actions'>
            <form class='action-card' method='post' action='/evidence211/enable-project'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><b>Lokales Projekt freigeben</b><select name='project_id'><option value='exiftool'>ExifTool</option><option value='singlefile'>SingleFile</option><option value='archivebox'>ArchiveBox</option><option value='bellingcat_auto_archiver'>Bellingcat Auto Archiver</option><option value='followthemoney'>FollowTheMoney</option></select><input name='reason' placeholder='Begründung, mindestens 10 Zeichen' required><button>Nach lokaler Erkennung freigeben</button></form>
            <form class='action-card' method='post' action='/evidence211/handoff'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><b>Manuellen Capture planen</b><select name='project_id'><option value='singlefile'>SingleFile im bestehenden Firefox</option><option value='archivebox'>ArchiveBox extern</option><option value='bellingcat_auto_archiver'>Bellingcat Auto Archiver extern</option></select><input type='url' name='target_url' placeholder='Öffentliche URL' required><input name='purpose' placeholder='Fallbezogener Zweck' required><button>Handoff anlegen</button></form>
            <form class='action-card' method='post' action='/evidence211/import-capture'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><b>Capture-Output importieren</b><select name='project_id'><option value='singlefile'>SingleFile</option><option value='archivebox'>ArchiveBox</option></select><input name='relative_path' placeholder='Dateiname relativ zum Projektordner' required><input name='title' placeholder='Belegtitel' required><input type='url' name='source_url' placeholder='Öffentliche Quell-URL'><input name='collector_version' placeholder='Tool-Version'><input name='media_type' value='text/html' placeholder='MIME-Type'><button>Als Kandidatenbeleg importieren</button></form>
            <form class='action-card' method='post' action='/evidence211/exiftool-plan'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><b>ExifTool offline planen</b><input name='package_id' placeholder='Gesicherte Package-ID' required><input name='purpose' value='Metadaten des gesicherten Artefakts lokal extrahieren.' required><button>Offline-Lauf planen</button></form>
            <form class='action-card' method='post' action='/evidence211/exiftool-run'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><b>Geplanten ExifTool-Lauf ausführen</b><input name='run_id' placeholder='Tool-Run-ID' required><button>Explizit offline ausführen</button></form>
          </div>
        </div>
        <div class='panel'><h2>Quellengebundene Aussage anlegen</h2>
          <form method='post' action='/evidence211/statement'>
            <input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'>
            <div class='form-grid'>
              <div class='field'><label>Source-ID</label><input name='source_id' required></div>
              <div class='field'><label>Entitätsreferenz</label><input name='entity_ref' placeholder='person:... oder Kandidat' required></div>
              <div class='field'><label>Schema</label><input name='schema_name' value='Person' required></div>
              <div class='field'><label>Prädikat</label><input name='predicate' placeholder='occupation, alias, affiliation ...' required></div>
              <div class='field'><label>Wert</label><input name='value' required></div>
              <div class='field'><label>Art</label><select name='statement_kind'><option>observation</option><option>inference</option><option>hypothesis</option></select></div>
              <div class='field'><label>Konfidenz 0–1</label><input name='confidence' type='number' step='0.01' min='0' max='1' value='0.5'></div>
              <div class='field'><label>Dataset</label><input name='dataset_id' value='case-local' required></div>
              <div class='field'><label>Origin</label><input name='origin' value='manual_analyst_extraction' required></div>
              <div class='field'><label>Originalformulierung</label><input name='original_value'></div>
            </div><p><button>Aussage als Kandidat anlegen</button></p>
          </form>
        </div>
        <div class='panel'><h2>Aussagen</h2><div class='table-wrap'><table><thead><tr><th>Art</th><th>Entität</th><th>Prädikat</th><th>Status</th><th>Konfidenz</th></tr></thead><tbody>{statements}</tbody></table></div></div>
        <div class='panel'><h2>Integrität und Bundle</h2>
          <div class='actions'>
            <form class='action-card' method='post' action='/evidence211/verify'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><b>Fallintegrität prüfen</b><p>Hashes, Rohartefakte, Aussagen und append-only Ledger kontrollieren.</p><button>Prüfung starten</button></form>
            <form class='action-card' method='post' action='/evidence211/approve-export'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><b>Package freigeben</b><input name='package_id' placeholder='Package-ID' required><input name='reason' placeholder='Begründung, mindestens 10 Zeichen' required><button>Redigierten Export freigeben</button></form>
            <form class='action-card' method='post' action='/evidence211/bundle'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><b>Reproduzierbares Bundle</b><input name='package_ids' placeholder='Package-IDs, kommagetrennt' required><button>Bundle erstellen</button></form>
          </div>
        </div>
        """

    # ------------------------------------------------------------------
    # Read helpers and verification internals
    # ------------------------------------------------------------------
    def get_source(self, source_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_sources_211 WHERE source_id=?", (source_id,))
        if not row:
            raise KeyError(source_id)
        for key in ("redirect_chain_json", "response_headers_json", "metadata_json"):
            row[key.removesuffix("_json")] = _loads(row.pop(key), [] if key == "redirect_chain_json" else {})
        row["candidate_only"] = bool(row["candidate_only"])
        row["content_is_untrusted"] = bool(row["content_is_untrusted"])
        return row

    def get_statement(self, statement_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_statements_211 WHERE statement_id=?", (statement_id,))
        if not row:
            raise KeyError(statement_id)
        row["value"] = _loads(row.pop("value_json"), None)
        row["limitations"] = _loads(row.pop("limitations_json"), [])
        row["reviews"] = self.db.all("SELECT * FROM evidence_statement_reviews_211 WHERE statement_id=? ORDER BY rowid", (statement_id,))
        return row

    def _project(self, project_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM upstream_projects_211 WHERE project_id=?", (project_id,))
        if not row:
            raise KeyError(project_id)
        row["executables"] = _loads(row["executable_names_json"], [])
        row["capabilities"] = _loads(row["capabilities_json"], [])
        return row

    def _tool_run(self, run_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM tool_runs_211 WHERE run_id=?", (run_id,))
        if not row:
            raise KeyError(run_id)
        row["options"] = _loads(row["options_json"], {})
        return row

    def _require_case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _ledger(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Any, actor: str | None = None) -> str:
        # System-wide events are anchored to a synthetic internal case only when no
        # real case exists. Foundation seeding therefore uses the first case or is
        # logged solely through the standard audit trail.
        if case_id == "system":
            first = self.db.one("SELECT case_id FROM cases ORDER BY created_at LIMIT 1")
            if not first:
                return ""
            case_id = first["case_id"]
        previous = self.db.one(
            "SELECT event_hash FROM evidence_ledger_events_211 WHERE case_id=? ORDER BY rowid DESC LIMIT 1",
            (case_id,),
        )
        prev = previous["event_hash"] if previous else "0" * 64
        event_id = new_id("ledger211")
        event_time = now_ts()
        clean_payload = self._sanitize(payload)
        record = {
            "event_id": event_id, "case_id": case_id, "event_type": event_type,
            "object_type": object_type, "object_id": object_id, "actor": actor or self.actor,
            "event_time": event_time, "payload": clean_payload, "previous_hash": prev,
        }
        event_hash = _sha(record)
        self.db.execute(
            "INSERT INTO evidence_ledger_events_211 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (event_id, case_id, event_type, object_type, object_id, actor or self.actor, event_time, dumps(clean_payload), prev, event_hash),
        )
        return event_id

    def _verify_ledger(self, case_id: str) -> dict[str, Any]:
        rows = self.db.all("SELECT * FROM evidence_ledger_events_211 WHERE case_id=? ORDER BY rowid", (case_id,))
        previous = "0" * 64
        errors: list[str] = []
        for row in rows:
            record = {
                "event_id": row["event_id"], "case_id": row["case_id"], "event_type": row["event_type"],
                "object_type": row["object_type"], "object_id": row["object_id"], "actor": row["actor"],
                "event_time": row["event_time"], "payload": _loads(row["payload_json"], {}), "previous_hash": previous,
            }
            expected = _sha(record)
            if row["previous_hash"] != previous or row["event_hash"] != expected:
                errors.append(f"ledger_chain_mismatch:{row['event_id']}")
            previous = row["event_hash"]
        return {"events": len(rows), "ok": not errors, "errors": errors}

    def _source_hash(self, row: Mapping[str, Any]) -> str:
        payload = {
            "source_id": row["source_id"], "case_id": row["case_id"], "package_id": row["package_id"],
            "source_kind": row["source_kind"], "original_url": row["original_url"], "canonical_url": row["canonical_url"],
            "final_url": row["final_url"], "redirect_chain": _loads(row["redirect_chain_json"], []),
            "response_headers": _loads(row["response_headers_json"], {}), "observed_at": row["observed_at"],
            "published_at": row["published_at"], "collector_id": row["collector_id"],
            "collector_version": row["collector_version"], "upstream_project_id": row["upstream_project_id"],
            "capture_mode": row["capture_mode"], "legal_scope": row["legal_scope"],
            "candidate_only": bool(row["candidate_only"]), "content_is_untrusted": bool(row["content_is_untrusted"]),
            "metadata": _loads(row["metadata_json"], {}), "created_by": row["created_by"], "created_at": row["created_at"],
        }
        return _sha(payload)

    def _statement_hash(self, row: Mapping[str, Any]) -> str:
        payload = {
            "statement_id": row["statement_id"], "case_id": row["case_id"], "source_id": row["source_id"],
            "package_id": row["package_id"], "entity_ref": row["entity_ref"], "schema_name": row["schema_name"],
            "predicate": row["predicate"], "value": _loads(row["value_json"], None), "original_value": row["original_value"],
            "value_language": row["value_language"], "dataset_id": row["dataset_id"], "origin": row["origin"],
            "first_seen": row["first_seen"], "last_seen": row["last_seen"], "statement_kind": row["statement_kind"],
            "confidence": round(float(row["confidence"]), 6), "review_status": row["review_status"],
            "limitations": _loads(row["limitations_json"], []), "created_by": row["created_by"], "created_at": row["created_at"],
        }
        return _sha(payload)

    def _link_hash(self, row: Mapping[str, Any]) -> str:
        return _sha({
            "link_id": row["link_id"], "statement_id": row["statement_id"], "case_id": row["case_id"],
            "object_type": row["object_type"], "object_id": row["object_id"], "relation": row["relation"],
            "created_by": row["created_by"], "created_at": row["created_at"],
        })

    def _review_hash(self, row: Mapping[str, Any]) -> str:
        return _sha({
            "review_id": row["review_id"], "statement_id": row["statement_id"], "case_id": row["case_id"],
            "reviewer": row["reviewer"], "decision": row["decision"], "reason": row["reason"],
            "created_at": row["created_at"],
        })

    def _public_source_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "source_id": row["source_id"], "package_id": row["package_id"], "source_kind": row["source_kind"],
            "canonical_url": row["canonical_url"], "observed_at": row["observed_at"], "published_at": row["published_at"],
            "collector_id": row["collector_id"], "collector_version": row["collector_version"],
            "capture_mode": row["capture_mode"], "legal_scope": row["legal_scope"],
            "candidate_only": bool(row["candidate_only"]), "payload_sha256": row["payload_sha256"],
        }

    def _public_statement_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "statement_id": row["statement_id"], "source_id": row["source_id"], "package_id": row["package_id"],
            "entity_ref": row["entity_ref"], "schema_name": row["schema_name"], "predicate": row["predicate"],
            "value": _loads(row["value_json"], None), "original_value": row["original_value"],
            "dataset_id": row["dataset_id"], "origin": row["origin"], "first_seen": row["first_seen"],
            "last_seen": row["last_seen"], "statement_kind": row["statement_kind"], "confidence": row["confidence"],
            "review_status": row["review_status"], "limitations": _loads(row["limitations_json"], []),
            "payload_sha256": row["payload_sha256"],
        }

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): ("[REDACTED]" if SECRET_KEY.search(str(k)) else self._sanitize(v)) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._sanitize(v) for v in value]
        if isinstance(value, str):
            return self._redact_text(value[:20000])
        return value

    @staticmethod
    def _contains_redaction(value: Any) -> bool:
        if isinstance(value, Mapping):
            return any(v == "[REDACTED]" or Build211EvidenceProvenanceFoundationService._contains_redaction(v) for v in value.values())
        if isinstance(value, list):
            return any(Build211EvidenceProvenanceFoundationService._contains_redaction(v) for v in value)
        return value == "[REDACTED]"

    @staticmethod
    def _redact_text(value: str) -> str:
        value = re.sub(r"(?i)(authorization|cookie|token|secret|password|api[_-]?key|session)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", value)
        return value

    @staticmethod
    def _detect_version(project_id: str, executable: str) -> str:
        args = [executable, "-ver"] if project_id == "exiftool" else [executable, "--version"]
        try:
            proc = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=5, check=False, shell=False)
            return proc.stdout.decode("utf-8", errors="replace").splitlines()[0][:200] if proc.stdout else ""
        except Exception:
            return ""

    def _audit(self, action: str, object_type: str, object_id: str, case_id: str | None, details: Mapping[str, Any]) -> None:
        if self.audit is not None and hasattr(self.audit, "log"):
            self.audit.log(action, object_type, object_id, case_id, dict(details))
