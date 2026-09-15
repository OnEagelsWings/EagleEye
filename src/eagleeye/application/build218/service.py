from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
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


def _text(value: Any, limit: int = 200_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _boolish(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "claimed", "found", "exists"}


def _shape_fingerprint(value: Any) -> str:
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
    return hashlib.sha256("\n".join(sorted(set(paths))).encode("utf-8")).hexdigest()


class SourceHTTPError(RuntimeError):
    def __init__(self, message: str, response: Mapping[str, Any]):
        super().__init__(message)
        self.response = dict(response)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urllib.error.HTTPError(req.full_url, code, "redirect blocked", headers, fp)


class Build218ProductiveDigitalIdentitySourcesService:
    """Five governed digital-identity adapters with evidence, review and training coupling.

    Network calls are limited to fixed public endpoints or to independently installed,
    explicitly approved username tools. Results are always candidates and never identity
    confirmations. Every accepted/rejected result can become a human-reviewed training signal.
    """

    BUILD = "218.0"
    MAX_HTTP_BYTES = 2_000_000
    MAX_CLI_BYTES = 5_000_000
    USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

    ADAPTERS: tuple[dict[str, Any], ...] = (
        {
            "adapter_key": "github_public", "title": "GitHub Public User API", "adapter_kind": "http_api",
            "target_types": ["username", "alias"], "allowed_hosts": ["api.github.com", "github.com"],
            "auth_mode": "optional_env:GITHUB_TOKEN", "executables": [], "network_capable": True,
            "opsec_risk": "elevated", "active": True, "health_status": "untested",
            "notes": "Public profile candidate; unauthenticated rate limit is lower. No repository cloning or login.",
        },
        {
            "adapter_key": "gravatar_public", "title": "Gravatar Public Profile", "adapter_kind": "http_api",
            "target_types": ["email"], "allowed_hosts": ["gravatar.com", "www.gravatar.com"],
            "auth_mode": "none_legacy_public_json", "executables": [], "network_capable": True,
            "opsec_risk": "elevated", "active": True, "health_status": "untested",
            "notes": "Email is locally SHA-256 hashed before the public profile request; candidate-only.",
        },
        {
            "adapter_key": "wikidata_public", "title": "Wikidata Entity Search", "adapter_kind": "http_api",
            "target_types": ["name", "alias", "organization"], "allowed_hosts": ["www.wikidata.org"],
            "auth_mode": "none", "executables": [], "network_capable": True,
            "opsec_risk": "elevated", "active": True, "health_status": "untested",
            "notes": "Public entity candidates with labels and descriptions; never resolves identity automatically.",
        },
        {
            "adapter_key": "sherlock_local", "title": "Sherlock Local CLI", "adapter_kind": "local_cli",
            "target_types": ["username", "alias"], "allowed_hosts": [], "auth_mode": "none",
            "executables": ["sherlock", "sherlock.exe"], "network_capable": True,
            "opsec_risk": "high", "active": False, "health_status": "not_configured",
            "notes": "Independently installed MIT tool. Execution is restricted to investigator-approved sites and no browse/proxy/Tor flags.",
        },
        {
            "adapter_key": "whatsmyname_local", "title": "WhatsMyName Local CLI", "adapter_kind": "local_cli",
            "target_types": ["username", "alias"], "allowed_hosts": [], "auth_mode": "none",
            "executables": ["whatsmyname", "wmn", "main.py"], "network_capable": True,
            "opsec_risk": "high", "active": False, "health_status": "not_configured",
            "notes": "Independently installed data/CLI; updates are disabled and only reviewed categories/sites may be used.",
        },
    )

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        planner: Any,
        conversation: Any,
        evidence: Any,
        identity_ai: Any,
        source_fabric: Any,
        base_dir: str | Path,
        actor: str = "local-analyst",
        http_fetcher: Callable[..., Mapping[str, Any]] | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.planner = planner
        self.conversation = conversation
        self.evidence = evidence
        self.identity_ai = identity_ai
        self.source_fabric = source_fabric
        self.base_dir = Path(base_dir)
        self.actor = actor
        self.http_fetcher = http_fetcher
        self.run_root = self.base_dir / "data" / "digital_sources_218" / "runs"
        self.run_root.mkdir(parents=True, exist_ok=True)
        self.seed()

    # ---------- catalog/configuration ----------
    def seed(self) -> dict[str, Any]:
        now = now_ts()
        for adapter in self.ADAPTERS:
            existing = self.db.one("SELECT created_at,detected_path,detected_version,dataset_path,allowed_sites_json,active,health_status FROM digital_source_adapters_218 WHERE adapter_key=?", (adapter["adapter_key"],))
            created = existing["created_at"] if existing else now
            detected_path = existing["detected_path"] if existing else ""
            detected_version = existing["detected_version"] if existing else ""
            dataset_path = existing["dataset_path"] if existing else ""
            allowed_sites = existing["allowed_sites_json"] if existing else "[]"
            active = int(existing["active"]) if existing and adapter["adapter_kind"] == "local_cli" else int(adapter["active"])
            health = existing["health_status"] if existing and adapter["adapter_kind"] == "local_cli" else adapter["health_status"]
            payload = {**adapter, "detected_path": detected_path, "detected_version": detected_version, "dataset_path": dataset_path, "allowed_sites": _loads(allowed_sites, []), "active": bool(active), "health_status": health}
            self.db.execute(
                "INSERT OR REPLACE INTO digital_source_adapters_218 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    adapter["adapter_key"], adapter["title"], adapter["adapter_kind"], dumps(adapter["target_types"]),
                    dumps(adapter["allowed_hosts"]), adapter["auth_mode"], dumps(adapter["executables"]), int(adapter["network_capable"]),
                    1, adapter["opsec_risk"], active, health, detected_path, detected_version, dataset_path, allowed_sites,
                    adapter["notes"], created, now, _hash(payload),
                ),
            )
        self._seed_router_pack(now)
        return {"build": self.BUILD, "adapter_count": len(self.ADAPTERS), "automatic_execution": False}

    def _seed_router_pack(self, now: str) -> None:
        source_key = "digital_identity_pack_218"
        existing = self.db.one("SELECT created_at FROM source_router_catalog_217 WHERE source_key=?", (source_key,))
        created = existing["created_at"] if existing else now
        payload = {
            "source_key": source_key, "title": "Produktives Digital-Identity-Pack", "route_class": "social_username",
            "adapter_type": "build218_governed_pack", "input_types": ["username", "alias", "email", "name", "organization"],
            "expected_outputs": ["public_account_candidates", "public_profile_candidates", "entity_candidates", "evidence"],
            "requires_auth": False, "network_capable": True, "opsec_risk": "elevated", "data_exposure": "approved_identifier",
            "estimated_cost": "public_or_local", "active": True, "health_status": "degraded", "upstream_ref": "EagleEye Build 218",
            "notes": "Five governed adapters; explicit human execution and result review required.",
        }
        self.db.execute(
            "INSERT OR REPLACE INTO source_router_catalog_217 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                source_key, payload["title"], payload["route_class"], payload["adapter_type"], dumps(payload["input_types"]),
                dumps(payload["expected_outputs"]), 0, 1, payload["opsec_risk"], payload["data_exposure"], payload["estimated_cost"],
                1, payload["health_status"], payload["upstream_ref"], payload["notes"], created, now, _hash(payload),
            ),
        )

    def catalog(self) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM digital_source_adapters_218 ORDER BY adapter_key")
        return [self._public_adapter(x) for x in rows]

    def detect_local_tools(self, *, actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation != "DIGITAL SOURCE TOOLS 218 ERKENNEN":
            raise PermissionError("explicit approval required")
        results = []
        for row in self.db.all("SELECT * FROM digital_source_adapters_218 WHERE adapter_kind='local_cli' ORDER BY adapter_key"):
            detected = row["detected_path"]
            if not detected:
                for name in _loads(row["executable_names_json"], []):
                    detected = shutil.which(name) or ""
                    if detected:
                        break
            version = self._cli_version(detected) if detected else ""
            health = "degraded" if detected else "not_configured"
            now = now_ts()
            self.db.execute("UPDATE digital_source_adapters_218 SET detected_path=?,detected_version=?,health_status=?,updated_at=? WHERE adapter_key=?", (detected, version, health, now, row["adapter_key"]))
            results.append({"adapter_key": row["adapter_key"], "detected_path": detected, "detected_version": version, "health_status": health})
        return {"build": self.BUILD, "tools": results, "automatic_install": False, "actor": actor}

    def configure_local_adapter(
        self, *, adapter_key: str, executable_path: str, dataset_path: str = "", allowed_sites: Sequence[str] = (),
        reviewer: str, reason: str, confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"DIGITAL SOURCE ADAPTER 218 {adapter_key} FREIGEBEN":
            raise PermissionError("explicit approval required")
        row = self._adapter(adapter_key)
        if row["adapter_kind"] != "local_cli":
            raise ValueError("only local CLI adapters require configuration")
        if len(reason.strip()) < 12:
            raise ValueError("substantive reason required")
        path = Path(executable_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        data_path = ""
        if dataset_path:
            dp = Path(dataset_path).expanduser().resolve()
            if not dp.is_file():
                raise FileNotFoundError(dp)
            data_path = str(dp)
        sites = sorted({_text(x, 120).strip() for x in allowed_sites if _text(x, 120).strip()})[:100]
        if adapter_key == "sherlock_local" and not sites:
            raise ValueError("Sherlock requires an investigator-approved site allowlist")
        version = self._cli_version(str(path))
        now = now_ts()
        payload = {"adapter_key": adapter_key, "path": str(path), "version": version, "dataset_path": data_path, "allowed_sites": sites, "reason": reason, "reviewer": reviewer}
        self.db.execute(
            "UPDATE digital_source_adapters_218 SET detected_path=?,detected_version=?,dataset_path=?,allowed_sites_json=?,active=1,health_status='degraded',notes=?,updated_at=?,payload_sha256=? WHERE adapter_key=?",
            (str(path), version, data_path, dumps(sites), _text(reason, 3000), now, _hash(payload), adapter_key),
        )
        self._event("system", "digital_adapter_configured", "digital_source_adapter", adapter_key, payload, reviewer)
        return {**payload, "active": True, "health_status": "degraded", "automatic_update": False}

    # ---------- execution ----------
    def execute_request(self, *, request_id: str, adapter_keys: Sequence[str], actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"DIGITAL SOURCE REQUEST 218 {request_id} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        request = self.db.one("SELECT * FROM source_execution_requests_217 WHERE request_id=?", (request_id,))
        if not request:
            raise KeyError(request_id)
        if request["source_key"] != "digital_identity_pack_218":
            raise ValueError("request is not assigned to Build 218 digital identity pack")
        data = _loads(request["request_json"], {})
        outputs = []
        for key in dict.fromkeys(adapter_keys):
            outputs.append(self.run_adapter(
                case_id=request["case_id"], adapter_key=key, target_type=data.get("target_type", "unknown"),
                target_value=data.get("target_value", ""), purpose=data.get("purpose", "Approved Build 217 source route"),
                actor=actor, request_id=request_id, route_id=request["route_id"],
                confirmation=f"DIGITAL SOURCE 218 {request['case_id']} {key} AUSFUEHREN",
            ))
        return {"request_id": request_id, "runs": outputs, "automatic_identity_confirmation": False, "human_review_required": True}

    def run_adapter(
        self, *, case_id: str, adapter_key: str, target_type: str, target_value: str, purpose: str, actor: str,
        confirmation: str, request_id: str = "", route_id: str = "",
    ) -> dict[str, Any]:
        if confirmation != f"DIGITAL SOURCE 218 {case_id} {adapter_key} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        adapter = self._adapter(adapter_key)
        if not bool(adapter["active"]):
            raise PermissionError("adapter is not active")
        if target_type not in _loads(adapter["target_types_json"], []):
            raise ValueError("adapter does not support target type")
        target = self._validate_target(target_type, target_value)
        if len(purpose.strip()) < 12:
            raise ValueError("substantive case purpose required")
        preflight = self.identity_ai.opsec_preflight(
            case_id=case_id, action_type="digital_source_execution", source_id=adapter_key, created_by=actor,
            requested={
                "direct_contact": False, "credential_login": False, "upload_local_file": False, "download": False,
                "active_engagement": False, "new_browser_window": False, "network_execution_from_core": bool(adapter["adapter_kind"] == "http_api"),
                "network_capable": bool(adapter["network_capable"]),
            },
            confirmation=f"OPSEC PREFLIGHT 212 {case_id} PRUEFEN",
        )
        run_id, started = new_id("source218"), now_ts()
        stored_target = "sha256:" + hashlib.sha256(target.encode("utf-8")).hexdigest() if target_type == "email" else target
        run_payload = {
            "run_id": run_id, "request_id": request_id, "route_id": route_id, "case_id": case_id, "adapter_key": adapter_key,
            "target_type": target_type, "target_value": stored_target, "purpose": purpose, "execution_mode": adapter["adapter_kind"],
            "status": "blocked" if preflight["decision"] == "blocked" else "running", "started_by": actor, "started_at": started,
        }
        self.db.execute(
            "INSERT INTO digital_source_runs_218 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, request_id, route_id, case_id, adapter_key, target_type, stored_target, _text(purpose, 5000), adapter["adapter_kind"], run_payload["status"], actor, started, "", 0, "", "", "", "", "{}", _hash(run_payload)),
        )
        if preflight["decision"] == "blocked":
            self._finish_run(run_id, status="blocked", error_class="opsec_block", error_message=", ".join(preflight["risks"]), results=[], raw={"preflight_id": preflight["preflight_id"]})
            return self.get_run(run_id)
        try:
            if adapter_key == "github_public":
                raw, results, source_url = self._run_github(target)
            elif adapter_key == "gravatar_public":
                raw, results, source_url = self._run_gravatar(target)
            elif adapter_key == "wikidata_public":
                raw, results, source_url = self._run_wikidata(target, language="de")
            elif adapter_key == "sherlock_local":
                raw, results, source_url = self._run_sherlock(adapter, target, run_id)
            elif adapter_key == "whatsmyname_local":
                raw, results, source_url = self._run_wmn(adapter, target, run_id)
            else:
                raise ValueError("unknown adapter")
            evidence = self.evidence.preserve_text_evidence(
                case_id=case_id, title=f"Build 218 · {adapter['title']} · {target_type}", source_url=source_url,
                text=json.dumps(raw, ensure_ascii=False, indent=2, default=str), captured_by=actor,
                metadata={"build": self.BUILD, "adapter_key": adapter_key, "run_id": run_id, "candidate_only": True, "target_type": target_type},
                confirmation=f"EVIDENCE 211 {case_id} TEXT SPEICHERN",
            )
            source_id = evidence["source"]["source_id"]
            inserted = self._store_results(run_id=run_id, case_id=case_id, adapter_key=adapter_key, results=results, evidence_ref=source_id)
            status = "completed" if inserted else "not_found"
            self._finish_run(run_id, status=status, results=inserted, raw=raw, evidence_source_id=source_id)
            self._record_health(adapter_key, "live_run", "healthy" if status in {"completed", "not_found"} else "degraded", 0, len(inserted), "", {"run_id": run_id}, actor)
        except Exception as exc:
            self._finish_run(run_id, status="failed", error_class=type(exc).__name__, error_message=_text(exc, 2000), results=[], raw=getattr(exc, "response", {}))
            self._record_health(adapter_key, "live_run", "unavailable", 0, 0, type(exc).__name__, {"message": _text(exc, 500)}, actor)
        result = self.get_run(run_id)
        self._event(case_id, "digital_source_run_finished", "digital_source_run", run_id, {"adapter_key": adapter_key, "status": result["status"], "result_count": result["result_count"]}, actor)
        return result

    # ---------- adapters ----------
    def _run_github(self, username: str) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
        url = f"https://api.github.com/users/{urllib.parse.quote(username, safe='')}"
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "EagleEye-PersonOSINT/219"}
        token = os.environ.get("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = self._http_json(url, allowed_hosts={"api.github.com"}, headers=headers)
        if response["status"] == 404:
            return response, [], url
        if response["status"] != 200:
            raise SourceHTTPError(f"GitHub HTTP {response['status']}", response)
        data = dict(response.get("json") or {})
        if not data.get("login"):
            return response, [], url
        result = {
            "result_type": "public_account_candidate", "existence_state": "found", "platform": "GitHub",
            "profile_url": _text(data.get("html_url"), 2000), "display_name": _text(data.get("name"), 500),
            "username": _text(data.get("login"), 200), "description": _text(data.get("bio"), 4000),
            "location": _text(data.get("location"), 500), "organization": _text(data.get("company"), 500),
            "language": "und", "confidence": 0.78, "independence_key": "github:user:" + str(data.get("id") or data.get("login")),
            "fields": {k: data.get(k) for k in ("id", "node_id", "blog", "twitter_username", "public_repos", "public_gists", "followers", "following", "created_at", "updated_at", "type")},
            "limitations": ["public profile only", "same username does not establish identity", "profile fields may be self-asserted"],
        }
        return response, [result], url

    def _run_gravatar(self, email: str) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
        digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
        url = f"https://www.gravatar.com/{digest}.json"
        response = self._http_json(url, allowed_hosts={"www.gravatar.com", "gravatar.com"}, headers={"User-Agent": "EagleEye-PersonOSINT/219"})
        if response["status"] == 404:
            return {**response, "email_sha256": digest}, [], url
        if response["status"] != 200:
            raise SourceHTTPError(f"Gravatar HTTP {response['status']}", response)
        body = response.get("json") or {}
        entry = (body.get("entry") or [body])[0] if isinstance(body, Mapping) else {}
        if not isinstance(entry, Mapping):
            return response, [], url
        accounts = entry.get("accounts") or entry.get("verified_accounts") or []
        result = {
            "result_type": "public_profile_candidate", "existence_state": "found", "platform": "Gravatar",
            "profile_url": _text(entry.get("profileUrl") or entry.get("profile_url"), 2000),
            "display_name": _text(entry.get("displayName") or entry.get("display_name"), 500),
            "username": _text(entry.get("preferredUsername") or entry.get("hash"), 200),
            "description": _text(entry.get("aboutMe") or entry.get("description"), 4000),
            "location": _text((entry.get("currentLocation") or entry.get("location")), 500),
            "organization": _text(entry.get("company") or entry.get("job_title"), 500), "language": "und", "confidence": 0.70,
            "independence_key": "gravatar:" + digest,
            "fields": {"email_sha256": digest, "thumbnail_url": entry.get("thumbnailUrl") or entry.get("avatar_url"), "accounts": accounts},
            "limitations": ["hash match is limited to the account primary email", "profile data may be self-asserted", "email-to-profile association needs human review"],
        }
        return {**response, "email_sha256": digest}, [result], url

    def _run_wikidata(self, query: str, language: str = "de") -> tuple[dict[str, Any], list[dict[str, Any]], str]:
        params = urllib.parse.urlencode({"action": "wbsearchentities", "search": query, "language": language, "uselang": language, "format": "json", "limit": 10, "type": "item", "origin": "*", "maxlag": 2})
        url = "https://www.wikidata.org/w/api.php?" + params
        response = self._http_json(url, allowed_hosts={"www.wikidata.org"}, headers={"User-Agent": "EagleEye-PersonOSINT/219"})
        if response["status"] != 200:
            raise SourceHTTPError(f"Wikidata HTTP {response['status']}", response)
        results = []
        for item in (response.get("json") or {}).get("search", [])[:10]:
            qid = _text(item.get("id"), 80)
            if not qid:
                continue
            results.append({
                "result_type": "public_entity_candidate", "existence_state": "possible", "platform": "Wikidata",
                "profile_url": _text(item.get("concepturi") or f"https://www.wikidata.org/wiki/{qid}", 2000),
                "display_name": _text(item.get("label"), 500), "username": "", "description": _text(item.get("description"), 4000),
                "location": "", "organization": "", "language": _text(item.get("match", {}).get("language") or language, 20),
                "confidence": 0.52, "independence_key": "wikidata:" + qid,
                "fields": {"entity_id": qid, "aliases": item.get("aliases") or [], "match": item.get("match") or {}},
                "limitations": ["name search candidate only", "Wikidata entity may refer to a namesake", "identity requires independent corroboration"],
            })
        return response, results, url

    def _run_sherlock(self, adapter: Mapping[str, Any], username: str, run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
        if not adapter["detected_path"]:
            raise RuntimeError("Sherlock executable is not configured")
        allowed = _loads(adapter["allowed_sites_json"], [])
        if not allowed:
            raise RuntimeError("Sherlock site allowlist is empty")
        work = self.run_root / run_id
        work.mkdir(parents=True, exist_ok=False)
        out = work / "sherlock.csv"
        cmd = [adapter["detected_path"], "--no-color", "--csv", "-o", str(out), "--timeout", "20"]
        for site in allowed[:25]:
            cmd.extend(["--site", site])
        if adapter["dataset_path"]:
            cmd.extend(["--json", adapter["dataset_path"]])
        cmd.append(username)
        proc = self._run_cli(cmd, cwd=work, timeout=180)
        text = out.read_text(encoding="utf-8", errors="replace") if out.is_file() else proc["stdout"]
        rows = list(csv.DictReader(io.StringIO(text))) if text.strip() else []
        results = []
        for row in rows:
            found = _boolish(row.get("exists") or row.get("status") or row.get("claimed"))
            url = _text(row.get("url_user") or row.get("url") or row.get("profile_url"), 2000)
            if not found and not url:
                continue
            if not found and str(row.get("http_status") or "") == "200":
                found = True
            if found:
                results.append({
                    "result_type": "public_account_candidate", "existence_state": "found", "platform": _text(row.get("name") or row.get("site") or "Sherlock site", 300),
                    "profile_url": url, "display_name": "", "username": username, "description": "", "location": "", "organization": "", "language": "und",
                    "confidence": 0.62, "independence_key": "sherlock:" + _hash([row.get("name"), url])[:24], "fields": dict(row),
                    "limitations": ["username existence signal only", "upstream site detection may drift", "same username does not establish identity"],
                })
        raw = {"command_contract": {"adapter": "sherlock", "allowed_sites": allowed[:25], "browse": False, "proxy": False, "tor": False}, "returncode": proc["returncode"], "stdout": proc["stdout"], "stderr": proc["stderr"], "csv": rows}
        return raw, results, "https://sherlockproject.xyz/sites"

    def _run_wmn(self, adapter: Mapping[str, Any], username: str, run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
        if not adapter["detected_path"]:
            raise RuntimeError("WhatsMyName executable is not configured")
        work = self.run_root / run_id
        work.mkdir(parents=True, exist_ok=False)
        cmd = [adapter["detected_path"], username, "--timeout", "20", "--threads", "10", "--export", "json"]
        proc = self._run_cli(cmd, cwd=work, timeout=180)
        candidates = sorted(work.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        body: Any = {}
        if candidates:
            body = json.loads(candidates[0].read_text(encoding="utf-8", errors="replace"))
        elif proc["stdout"].strip().startswith(("[", "{")):
            body = json.loads(proc["stdout"])
        items = body.get("results") or body.get("sites") or body if isinstance(body, Mapping) else body
        if isinstance(items, Mapping):
            items = [{"name": k, **(v if isinstance(v, Mapping) else {"value": v})} for k, v in items.items()]
        results = []
        for item in items or []:
            if not isinstance(item, Mapping):
                continue
            state = _text(item.get("status") or item.get("exists") or item.get("found"), 40).lower()
            found = _boolish(state) or state in {"claimed", "positive"}
            url = _text(item.get("url") or item.get("uri_pretty") or item.get("profile_url"), 2000)
            if found:
                results.append({
                    "result_type": "public_account_candidate", "existence_state": "found", "platform": _text(item.get("name") or item.get("site") or "WhatsMyName site", 300),
                    "profile_url": url, "display_name": "", "username": username, "description": "", "location": "", "organization": "", "language": "und",
                    "confidence": 0.60, "independence_key": "wmn:" + _hash([item.get("name"), url])[:24], "fields": dict(item),
                    "limitations": ["username existence signal only", "definition quality varies by site", "same username does not establish identity"],
                })
        raw = {"command_contract": {"adapter": "whatsmyname", "update": False, "threads": 10}, "returncode": proc["returncode"], "stdout": proc["stdout"], "stderr": proc["stderr"], "export": body}
        return raw, results, "https://github.com/Arcade-Project/WhatsMyName"

    # ---------- reviews/training/benchmark ----------
    def review_result(self, *, result_id: str, decision: str, reason: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"DIGITAL SOURCE RESULT 218 {result_id} PRUEFEN":
            raise PermissionError("explicit approval required")
        if decision not in {"accepted_candidate", "rejected", "duplicate", "needs_more_evidence"}:
            raise ValueError("invalid result decision")
        if len(reason.strip()) < 10:
            raise ValueError("substantive reason required")
        result = self.db.one("SELECT * FROM digital_source_results_218 WHERE result_id=?", (result_id,))
        if not result:
            raise KeyError(result_id)
        run = self.db.one("SELECT * FROM digital_source_runs_218 WHERE run_id=?", (result["run_id"],))
        training = self.conversation.create_training_example(
            case_id=result["case_id"], task_type="source_assessment", language=result["language"], difficulty="productive_source_review",
            input_payload={"adapter_key": result["adapter_key"], "target_type": run["target_type"], "candidate": self._public_result(result)},
            expected_output={"decision": decision, "reason": reason}, evidence_refs=[result["evidence_ref"]] if result["evidence_ref"] else [],
            negative_constraints=["candidate is not identity confirmation", "do not count copied sources as independent", "preserve uncertainty"],
            label="human_reviewed_productive_source_result", rationale=reason, created_by=reviewer,
            confirmation=f"TRAINING EXAMPLE 216 {result['case_id']} ANLEGEN",
        )
        review_id, now = new_id("review218"), now_ts()
        payload = {"review_id": review_id, "result_id": result_id, "run_id": result["run_id"], "case_id": result["case_id"], "decision": decision, "reason": reason, "reviewer": reviewer, "training_example_id": training["example_id"], "created_at": now}
        self.db.execute("INSERT INTO digital_source_result_reviews_218 VALUES(?,?,?,?,?,?,?,?,?,?)", (review_id, result_id, result["run_id"], result["case_id"], decision, _text(reason, 5000), reviewer, training["example_id"], now, _hash(payload)))
        self.db.execute("UPDATE digital_source_results_218 SET review_status=? WHERE result_id=?", (decision, result_id))
        self._event(result["case_id"], "digital_source_result_reviewed", "digital_source_result", result_id, {"decision": decision, "training_example_id": training["example_id"]}, reviewer)
        return payload

    def create_benchmark(self, *, adapter_key: str, title: str, target_type: str, target_value: str, expected_state: str, expected_min_results: int, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"DIGITAL SOURCE BENCHMARK 218 {adapter_key} ANLEGEN":
            raise PermissionError("explicit approval required")
        self._adapter(adapter_key)
        if expected_state not in {"completed", "not_found"}:
            raise ValueError("invalid expected state")
        bid, now = new_id("bench218"), now_ts()
        payload = {"benchmark_id": bid, "adapter_key": adapter_key, "title": title, "target_type": target_type, "target_value": target_value, "expected_state": expected_state, "expected_min_results": max(0, int(expected_min_results)), "status": "active", "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO digital_source_benchmarks_218 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (bid, adapter_key, _text(title, 500), target_type, _text(target_value, 1000), expected_state, payload["expected_min_results"], "active", created_by, now, _hash(payload)))
        return payload

    def evaluate_benchmark(self, *, benchmark_id: str, run_id: str, evaluator: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"DIGITAL SOURCE BENCHMARK 218 {benchmark_id} AUSWERTEN":
            raise PermissionError("explicit approval required")
        bench = self.db.one("SELECT * FROM digital_source_benchmarks_218 WHERE benchmark_id=?", (benchmark_id,))
        run = self.db.one("SELECT * FROM digital_source_runs_218 WHERE run_id=?", (run_id,))
        if not bench or not run:
            raise KeyError(benchmark_id if not bench else run_id)
        if bench["adapter_key"] != run["adapter_key"]:
            raise ValueError("benchmark and run adapter mismatch")
        passed = run["status"] == bench["expected_state"] and int(run["result_count"]) >= int(bench["expected_min_results"])
        rid, now = new_id("benchresult218"), now_ts()
        metrics = {"expected_state": bench["expected_state"], "observed_state": run["status"], "expected_min_results": bench["expected_min_results"], "observed_results": run["result_count"]}
        payload = {"result_id": rid, "benchmark_id": benchmark_id, "run_id": run_id, "adapter_key": run["adapter_key"], "passed": passed, "metrics": metrics, "evaluated_by": evaluator, "evaluated_at": now}
        self.db.execute("INSERT INTO digital_source_benchmark_results_218 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (rid, benchmark_id, run_id, run["adapter_key"], int(passed), run["status"], run["result_count"], dumps(metrics), evaluator, now, _hash(payload)))
        return payload

    # ---------- views ----------
    def get_run(self, run_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM digital_source_runs_218 WHERE run_id=?", (run_id,))
        if not row:
            raise KeyError(run_id)
        return {**row, "metrics": _loads(row["metrics_json"], {}), "results": [self._public_result(x) for x in self.db.all("SELECT * FROM digital_source_results_218 WHERE run_id=? ORDER BY result_id", (run_id,))], "candidate_only": True, "automatic_identity_confirmation": False}

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        return {
            "build": self.BUILD, "case_id": case_id, "adapters": self.catalog(),
            "runs": self.db.all("SELECT * FROM digital_source_runs_218 WHERE case_id=? ORDER BY started_at DESC LIMIT 30", (case_id,)),
            "results": [self._public_result(x) for x in self.db.all("SELECT * FROM digital_source_results_218 WHERE case_id=? ORDER BY created_at DESC LIMIT 60", (case_id,))],
            "reviews": self.db.all("SELECT * FROM digital_source_result_reviews_218 WHERE case_id=? ORDER BY created_at DESC LIMIT 40", (case_id,)),
            "health": self.db.all("SELECT h.* FROM digital_source_health_218 h JOIN (SELECT adapter_key,MAX(rowid) rid FROM digital_source_health_218 GROUP BY adapter_key) x ON x.rid=h.rowid ORDER BY h.adapter_key"),
            "policy": {"candidate_only": True, "explicit_execution": True, "evidence_required": True, "human_review": True, "training_coupled": True, "automatic_contact": False},
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        base = self.planner.render_workspace_panel(case_id=case_id, csrf=csrf).replace("Fallarbeitsraum 217", "Fallarbeitsraum 218", 1)
        data = self.dashboard(case_id=case_id)
        esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
        adapter_options = "".join(f"<option value='{esc(a['adapter_key'])}'>{esc(a['title'])} · {esc(a['health_status'])}</option>" for a in data["adapters"] if a["active"])
        adapters = "".join(f"<tr><td><code>{esc(a['adapter_key'])}</code></td><td>{esc(a['adapter_kind'])}</td><td>{'aktiv' if a['active'] else 'gesperrt'}</td><td>{esc(a['health_status'])}</td><td>{esc(a['opsec_risk'])}</td></tr>" for a in data["adapters"])
        runs = "".join(f"<tr><td><code>{esc(r['run_id'])}</code></td><td>{esc(r['adapter_key'])}</td><td>{esc(r['target_type'])}</td><td>{esc(r['status'])}</td><td>{esc(r['result_count'])}</td></tr>" for r in data["runs"]) or "<tr><td colspan='5'>Noch keine produktiven Quellenläufe.</td></tr>"
        results = "".join(f"<tr><td><code>{esc(r['result_id'])}</code></td><td>{esc(r['platform'])}</td><td>{esc(r['username'] or r['display_name'])}</td><td>{esc(r['existence_state'])}</td><td>{esc(r['review_status'])}</td><td><code>{esc(r['evidence_ref'])}</code></td></tr>" for r in data["results"]) or "<tr><td colspan='6'>Noch keine Kandidaten.</td></tr>"
        panel = f"""
<section class='card' id='build218_sources'><h2>Productive Source Pack I · Digital Identity · Build 218</h2>
<p>Fünf kontrollierte Quellenpfade: GitHub, Gravatar, Wikidata sowie lokal installierte Sherlock- und WhatsMyName-Adapter. Alle Treffer bleiben Kandidaten, werden als Evidence gespeichert und benötigen menschlichen Review.</p>
<div class='grid two'><div>
<form method='post' action='/build218/run'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>Produktiven Quellenlauf starten</h3><select name='adapter_key'>{adapter_options}</select><select name='target_type'><option>username</option><option>alias</option><option>email</option><option>name</option><option>organization</option></select><input name='target_value' placeholder='Geprüfter Suchwert' required><textarea name='purpose' rows='3' placeholder='Konkreter Fallzweck' required></textarea><button>OPSEC prüfen und Quelle ausführen</button></form>
<form method='post' action='/build218/tools-detect'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><button>Lokale Sherlock-/WMN-Tools erkennen</button></form></div>
<div><form method='post' action='/build218/result-review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>Kandidat prüfen und AI quellenbezogen trainieren</h3><input name='result_id' placeholder='Result-ID' required><select name='decision'><option value='accepted_candidate'>Kandidat akzeptieren</option><option value='rejected'>Verwerfen</option><option value='duplicate'>Duplikat</option><option value='needs_more_evidence'>Weitere Belege nötig</option></select><textarea name='reason' rows='4' placeholder='Begründung und Quellenkritik' required></textarea><button>Review und Trainingsentwurf speichern</button></form></div></div>
<div class='table-wrap'><table><thead><tr><th>Adapter</th><th>Typ</th><th>Status</th><th>Health</th><th>OPSEC</th></tr></thead><tbody>{adapters}</tbody></table></div>
<div class='table-wrap'><table><thead><tr><th>Lauf</th><th>Adapter</th><th>Zieltyp</th><th>Status</th><th>Ergebnisse</th></tr></thead><tbody>{runs}</tbody></table></div>
<div class='table-wrap'><table><thead><tr><th>Result</th><th>Plattform</th><th>Kandidat</th><th>Existenz</th><th>Review</th><th>Evidence</th></tr></thead><tbody>{results}</tbody></table></div>
</section>
"""
        marker = "<section class='card' id='build217_planner'>"
        return base.replace(marker, panel + marker, 1) if marker in base else base + panel

    # ---------- internals ----------
    def _http_json(self, url: str, *, allowed_hosts: set[str], headers: Mapping[str, str]) -> dict[str, Any]:
        if self.http_fetcher is not None:
            return dict(self.http_fetcher(url=url, allowed_hosts=allowed_hosts, headers=dict(headers)))
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or (parsed.hostname or "").lower() not in {x.lower() for x in allowed_hosts}:
            raise PermissionError("source endpoint is outside adapter allowlist")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(), _NoRedirect())
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            with opener.open(request, timeout=30) as response:
                status = int(response.status)
                raw = response.read(self.MAX_HTTP_BYTES + 1)
                if len(raw) > self.MAX_HTTP_BYTES:
                    raise ValueError("source response exceeds size limit")
                body = raw.decode(response.headers.get_content_charset() or "utf-8", errors="replace")
                return {"status": status, "headers": {k: v for k, v in response.headers.items() if k.lower() in {"content-type", "etag", "last-modified", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "retry-after"}}, "json": json.loads(body) if body.strip() else {}, "body_sha256": hashlib.sha256(raw).hexdigest(), "url": url}
        except urllib.error.HTTPError as exc:
            raw = exc.read(self.MAX_HTTP_BYTES + 1) if exc.fp else b""
            body = raw.decode("utf-8", errors="replace")
            parsed_body: Any = {}
            try:
                parsed_body = json.loads(body) if body.strip() else {}
            except Exception:
                parsed_body = {"text": body[:2000]}
            return {"status": int(exc.code), "headers": {k: v for k, v in (exc.headers.items() if exc.headers else []) if k.lower() in {"content-type", "etag", "last-modified", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "retry-after"}}, "json": parsed_body, "body_sha256": hashlib.sha256(raw).hexdigest(), "url": url}

    def _run_cli(self, command: Sequence[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
        blocked = {"--browse", "--proxy", "-p", "--tor", "-t", "--unique-tor", "--update", "-u", "--ignore-exclusions"}
        if any(arg in blocked for arg in command):
            raise PermissionError("unsafe CLI option blocked")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "NO_PROXY": "*", "no_proxy": "*"}
        proc = subprocess.run(list(command), cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False, shell=False)
        stdout = proc.stdout[: self.MAX_CLI_BYTES].decode("utf-8", errors="replace")
        stderr = proc.stderr[: self.MAX_CLI_BYTES].decode("utf-8", errors="replace")
        if proc.returncode not in {0, 1}:
            raise RuntimeError(f"CLI failed with return code {proc.returncode}: {stderr[:500]}")
        return {"returncode": proc.returncode, "stdout": stdout, "stderr": stderr}

    def _store_results(self, *, run_id: str, case_id: str, adapter_key: str, results: Sequence[Mapping[str, Any]], evidence_ref: str) -> list[dict[str, Any]]:
        inserted = []
        for item in results[:250]:
            rid, now = new_id("result218"), now_ts()
            profile_url = _text(item.get("profile_url"), 2000)
            username = _text(item.get("username"), 200)
            state = item.get("existence_state", "possible")
            independence_key = _text(item.get("independence_key"), 500) or _hash([adapter_key, profile_url, username])
            existing = self.db.one("SELECT result_id FROM digital_source_results_218 WHERE case_id=? AND adapter_key=? AND independence_key=? AND existence_state=?", (case_id, adapter_key, independence_key, state))
            if existing:
                continue
            payload = {"result_id": rid, "run_id": run_id, "case_id": case_id, "adapter_key": adapter_key, **dict(item), "evidence_ref": evidence_ref, "review_status": "unreviewed", "created_at": now}
            self.db.execute(
                "INSERT INTO digital_source_results_218 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rid, run_id, case_id, adapter_key, _text(item.get("result_type"), 100), state, _text(item.get("platform"), 300), profile_url,
                    _text(item.get("display_name"), 500), username, _text(item.get("description"), 5000), _text(item.get("location"), 500),
                    _text(item.get("organization"), 500), _text(item.get("language"), 20) or "und", max(0.0, min(1.0, float(item.get("confidence") or 0))),
                    evidence_ref, independence_key, dumps(dict(item.get("fields") or {})), dumps(list(item.get("limitations") or [])),
                    "unreviewed", now, _hash(payload),
                ),
            )
            inserted.append(payload)
        return inserted

    def _finish_run(self, run_id: str, *, status: str, results: Sequence[Any], raw: Any, error_class: str = "", error_message: str = "", evidence_source_id: str = "") -> None:
        finished = now_ts()
        raw_hash = _hash(raw)
        metrics = {"result_count": len(results), "finished_at": finished, "candidate_only": True, "http_status": int(raw.get("status") or 0) if isinstance(raw, Mapping) else 0, "response_headers": dict(raw.get("headers") or {}) if isinstance(raw, Mapping) else {}, "response_fingerprint": _shape_fingerprint(raw.get("json") if isinstance(raw, Mapping) and "json" in raw else raw)}
        payload = {"run_id": run_id, "status": status, "result_count": len(results), "error_class": error_class, "error_message": error_message, "evidence_source_id": evidence_source_id, "raw_sha256": raw_hash, "metrics": metrics, "finished_at": finished}
        self.db.execute("UPDATE digital_source_runs_218 SET status=?,finished_at=?,result_count=?,error_class=?,error_message=?,evidence_source_id=?,raw_sha256=?,metrics_json=?,payload_sha256=? WHERE run_id=?", (status, finished, len(results), error_class, _text(error_message, 2000), evidence_source_id, raw_hash, dumps(metrics), _hash(payload), run_id))

    def _record_health(self, adapter_key: str, check_type: str, status: str, latency_ms: int, result_count: int, error_class: str, details: Mapping[str, Any], actor: str) -> str:
        hid, now = new_id("health218"), now_ts()
        payload = {"health_id": hid, "adapter_key": adapter_key, "check_type": check_type, "status": status, "latency_ms": latency_ms, "result_count": result_count, "error_class": error_class, "details": dict(details), "checked_by": actor, "checked_at": now}
        self.db.execute("INSERT INTO digital_source_health_218 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (hid, adapter_key, check_type, status, int(latency_ms), int(result_count), error_class, dumps(dict(details)), actor, now, _hash(payload)))
        self.db.execute("UPDATE digital_source_adapters_218 SET health_status=?,updated_at=? WHERE adapter_key=?", (status, now, adapter_key))
        return hid

    def _validate_target(self, target_type: str, target_value: str) -> str:
        value = _text(target_value, 1000).strip()
        if target_type in {"username", "alias"}:
            value = value.lstrip("@")
            if not self.USERNAME_RE.fullmatch(value):
                raise ValueError("invalid username format")
        elif target_type == "email":
            value = value.lower()
            if not self.EMAIL_RE.fullmatch(value):
                raise ValueError("invalid email format")
        elif target_type in {"name", "organization"}:
            if len(value) < 2 or len(value) > 200:
                raise ValueError("invalid name or organization")
        else:
            raise ValueError("unsupported target type")
        return value

    def _cli_version(self, path: str) -> str:
        if not path:
            return ""
        try:
            proc = subprocess.run([path, "--version"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False, shell=False)
            return _text((proc.stdout or proc.stderr).decode("utf-8", errors="replace").strip(), 300)
        except Exception:
            return "unknown"

    def _adapter(self, adapter_key: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM digital_source_adapters_218 WHERE adapter_key=?", (adapter_key,))
        if not row:
            raise KeyError(adapter_key)
        return row

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _public_adapter(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "target_types": _loads(row["target_types_json"], []), "allowed_hosts": _loads(row["allowed_hosts_json"], []), "executables": _loads(row["executable_names_json"], []), "allowed_sites": _loads(row["allowed_sites_json"], []), "active": bool(row["active"]), "network_capable": bool(row["network_capable"]), "candidate_only": True}

    def _public_result(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "fields": _loads(row["fields_json"], {}), "limitations": _loads(row["limitations_json"], []), "candidate_only": True, "identity_confirmed": False}

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> str:
        ledger_case = case_id if self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)) else "system"
        if ledger_case == "system":
            return ""
        prev = self.db.one("SELECT event_hash FROM build218_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "0" * 64
        eid, now = new_id("evt218"), now_ts()
        safe = {k: v for k, v in dict(payload).items() if k not in {"target_value", "email", "token", "authorization", "raw", "stdout", "stderr"}}
        body = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": safe, "previous_hash": previous, "created_at": now}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build218_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, actor, dumps(safe), previous, event_hash, now))
        if self.audit is not None and hasattr(self.audit, "log"):
            self.audit.log(event_type, object_type, object_id, case_id, safe)
        return eid
