from __future__ import annotations

import ast
import hashlib
import html
import json
import re
import uuid
from pathlib import Path
from typing import Any, Callable

from eagleeye.crawler.engine import CrawlTransport
from eagleeye.crawler.media import MediaCrawler353, POLICY_VERSION as MEDIA_CRAWLER_POLICY
from eagleeye.image_intelligence.agent import ImageIntelligenceAgent353, POLICY_VERSION as IMAGE_POLICY

DIMENSIONS = ("implemented", "integrated", "tested", "benchmarked", "externally_validated")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class Build353ImageIntelligenceService:
    BUILD = "353.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        build352: Any,
        image_agent: ImageIntelligenceAgent353,
        media_crawler: MediaCrawler353,
        install_dir: str | Path,
        base_dir: str | Path,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.build352 = build352
        self.image_agent = image_agent
        self.media_crawler = media_crawler
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._root = self.install_dir

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build352, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/infrastructure/schema_v1/schema.py",
            "src/eagleeye/image_intelligence/agent.py",
            "src/eagleeye/crawler/media.py",
            "src/eagleeye/application/build353/service.py",
            "src/eagleeye/interfaces/web/app353.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "EAGLEEYE_PRO_353_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_353_0.py",
            "tests/test_build353.py",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            p = self._root / rel
            h.update(rel.encode("utf-8")); h.update(b"\0")
            h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        value = _read_json(self._root / "BUILD_353_TEST_EVIDENCE.json")
        if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint():
            return value
        return {}

    def _probe(self, key: str) -> bool:
        return self._test_evidence().get("probes", {}).get(key) == "pass"

    def _benchmark(self) -> dict[str, Any]:
        value = _read_json(self._root / "BENCHMARK_BUILD_353_IMAGE_INTELLIGENCE.json")
        if value.get("build") == self.BUILD and value.get("code_fingerprint") == self.code_fingerprint() and int(value.get("cases", 0)) >= 500 and value.get("violations") == 0 and value.get("result") == "pass":
            return value
        return {}

    def schema_metrics(self) -> dict[str, Any]:
        return self.build352.schema_metrics()

    def version_status(self) -> dict[str, Any]:
        vt = (self._root / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        pt = (self._root / "pyproject.toml").read_text(encoding="utf-8")
        rb = re.search(r'^BUILD\s*=\s*["\']([^"\']+)', vt, re.M)
        rs = re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', vt, re.M)
        rp = re.search(r'^version\s*=\s*["\']([^"\']+)', pt, re.M)
        runtime = rb.group(1) if rb else "unknown"
        schema = rs.group(1) if rs else "unknown"
        package = rp.group(1) if rp else "unknown"
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == "353.0.0"}

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c, ast.Constant) and c.value is True and hasattr(c, "lineno")})
        return []

    def _agent_record(self, *, case_id: str, action_class: str, payload: dict[str, Any], result: dict[str, Any], status: str = "completed") -> dict[str, Any]:
        now = self.db.one("SELECT datetime('now') t")["t"]
        task_id = "task_" + uuid.uuid4().hex[:24]
        task = {
            "task_id": task_id,
            "case_id": case_id,
            "agent_role": "image_intelligence",
            "action_class": action_class,
            "requested_gateway": "local_image_analysis",
            "approval_state": "human_or_local_explicit",
            "contract_version": "phase15.agent-task-result.v1",
            "task_json": _canon(payload),
            "record_hash": "",
            "created_at": now,
        }
        task["record_hash"] = _sha({k: v for k, v in task.items() if k != "record_hash"})
        self.db.execute("INSERT INTO phase15_agent_tasks(task_id,case_id,agent_role,action_class,requested_gateway,approval_state,contract_version,task_json,record_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", tuple(task.values()))
        result_id = "res_" + uuid.uuid4().hex[:24]
        r = {
            "result_id": result_id,
            "task_id": task_id,
            "status": status,
            "gateway_used": "local_image_analysis",
            "contract_version": "phase15.agent-task-result.v1",
            "result_json": _canon(result),
            "record_hash": "",
            "created_at": now,
        }
        r["record_hash"] = _sha({k: v for k, v in r.items() if k != "record_hash"})
        self.db.execute("INSERT INTO phase15_agent_results(result_id,task_id,status,gateway_used,contract_version,result_json,record_hash,created_at) VALUES(?,?,?,?,?,?,?,?)", tuple(r.values()))
        return {"task_id": task_id, "result_id": result_id}

    def ingest_image(
        self,
        *,
        case_id: str,
        content: bytes,
        declared_media_type: str = "",
        filename: str = "",
        search_run_id: str | None = None,
        source_id: str | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        inspection = self.image_agent.inspect_bytes(content, declared_media_type=declared_media_type, filename=filename)
        security_state = "quarantined" if inspection["disposition"] == "quarantine" else "review_pending"
        if search_run_id:
            run = self.db.one("SELECT search_kind FROM phase15_search_runs WHERE search_run_id=?", (search_run_id,))
            if run and run["search_kind"] == "darknet":
                security_state = "quarantined"
        obj = self.build352.ingest_artifact(
            case_id=case_id,
            content=bytes(content),
            media_type=inspection["magic_media_type"],
            search_run_id=search_run_id,
            source_id=source_id,
            security_state=security_state,
            provenance={
                "image_policy": IMAGE_POLICY,
                "filename": filename,
                "declared_media_type": declared_media_type,
                "magic_media_type": inspection["magic_media_type"],
                "epistemic_boundaries": inspection["epistemic_boundaries"],
                **(provenance or {}),
            },
        )
        media_id = "media_" + uuid.uuid4().hex[:24]
        metadata = {
            "policy": IMAGE_POLICY,
            "inspection": inspection,
            "object_id": obj["object_id"],
            "security_state": obj["security_state"],
            "epistemic_contract": {
                "metadata_fact": "embedded_or_container_metadata_only",
                "deterministic_derivation": "derived_from_explicit_metadata_or_pixels",
                "visual_indication": "not_generated_in_build353",
                "geolocation_hypothesis": "not_generated_in_build353",
                "external_image_hit": "not_generated_in_build353",
                "identity_confirmation": False,
            },
        }
        self.db.execute(
            "INSERT INTO phase15_media_assets(media_id,case_id,evidence_id,media_kind,object_ref,sha256,metadata_json,review_status,created_at) VALUES(?,?,?,?,?,?,?,?,datetime('now'))",
            (media_id, case_id, "", "image", obj["object_id"], obj["sha256"], _canon(metadata), "quarantined" if obj["quarantined"] else "review_pending"),
        )
        agent_ref = self._agent_record(
            case_id=case_id,
            action_class="image_metadata_extract_v1",
            payload={"media_id": media_id, "object_id": obj["object_id"], "sha256": obj["sha256"], "raw_bytes_in_task": False},
            result={"media_id": media_id, "object_id": obj["object_id"], "inspection": inspection, "requires_human_review": True},
        )
        return {"media_id": media_id, "object": obj, "inspection": inspection, "agent": agent_ref}

    def image_asset(self, media_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase15_media_assets WHERE media_id=?", (media_id,))
        if not row:
            raise KeyError(media_id)
        row["metadata"] = json.loads(row.pop("metadata_json"))
        return row

    def image_assets(self, *, case_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        n = max(1, min(int(limit), 500))
        if case_id:
            rows = self.db.all("SELECT * FROM phase15_media_assets WHERE case_id=? AND media_kind='image' ORDER BY created_at DESC LIMIT ?", (case_id, n))
        else:
            rows = self.db.all("SELECT * FROM phase15_media_assets WHERE media_kind='image' ORDER BY created_at DESC LIMIT ?", (n,))
        for row in rows:
            try: row["metadata"] = json.loads(row.pop("metadata_json"))
            except Exception: row["metadata"] = {}
        return rows

    def run_ocr(self, media_id: str, *, backend: Callable[[Any], str] | None = None, language: str = "eng", human_approved: bool = False) -> dict[str, Any]:
        if not human_approved:
            raise PermissionError("explicit human approval required for OCR task")
        asset = self.image_asset(media_id)
        content = self.build352.artifact_bytes(asset["object_ref"])
        result = self.image_agent.ocr(content, backend=backend, language=language)
        agent_ref = self._agent_record(
            case_id=asset["case_id"],
            action_class="image_ocr_v1",
            payload={"media_id": media_id, "object_id": asset["object_ref"], "language": language, "raw_bytes_in_task": False},
            result={"media_id": media_id, "ocr": result, "requires_human_review": True},
            status="completed" if result.get("status") == "completed" else str(result.get("status") or "error"),
        )
        return {"media_id": media_id, "ocr": result, "agent": agent_ref}

    def discover_media_for_crawl(self, crawl_run_id: str) -> dict[str, Any]:
        return self.media_crawler.enqueue_for_crawl(crawl_run_id)

    def run_next_media_fetch(self, *, worker_id: str, transport: CrawlTransport, resolver: Callable[[str], list[str]] | None = None) -> dict[str, Any] | None:
        payload = self.media_crawler.fetch_next(worker_id=worker_id, transport=transport, resolver=resolver)
        if payload is None or "error" in payload:
            return payload
        response = payload["response"]
        stored = self.ingest_image(
            case_id=payload["case_id"],
            content=response.body,
            declared_media_type=str(response.headers.get("content-type") or ""),
            filename=payload["url"].rsplit("/", 1)[-1],
            search_run_id=payload["search_run_id"],
            source_id=payload["source_id"],
            provenance={"crawler_media_policy": MEDIA_CRAWLER_POLICY, "url": payload["url"], "transport_kind": getattr(transport, "transport_kind", "unknown")},
        )
        job = self.media_crawler.complete_fetch(payload, object_id=stored["object"]["object_id"], media_id=stored["media_id"], worker_id=worker_id)
        return {"job": job, "stored": stored, "url": payload["url"]}

    def run_next_crawl(self, **kwargs: Any) -> dict[str, Any] | None:
        result = self.build352.run_next_crawl(**kwargs)
        if result and result.get("status") == "succeeded":
            try:
                job_id = str(result.get("job_id") or "")
                row = self.db.one("SELECT payload_json FROM phase15_jobs WHERE job_id=?", (job_id,)) if job_id else None
                payload = json.loads(row["payload_json"]) if row else {}
                crawl_run_id = str(payload.get("crawl_run_id") or "")
                if crawl_run_id:
                    discovery = self.discover_media_for_crawl(crawl_run_id)
                    result = {**result, "build353_media_discovery": {"crawl_run_id": crawl_run_id, "urls": len(discovery["media_urls"]), "jobs_enqueued": discovery["jobs_enqueued"]}}
            except Exception as exc:
                result = {**result, "build353_media_discovery_error": f"{type(exc).__name__}:{exc}"[:500]}
        return result

    def image_status(self) -> dict[str, Any]:
        counts = self.db.one("SELECT COUNT(*) total,SUM(CASE WHEN review_status='quarantined' THEN 1 ELSE 0 END) quarantined FROM phase15_media_assets WHERE media_kind='image'") or {"total": 0, "quarantined": 0}
        return {
            **self.image_agent.status(),
            "assets": int(counts.get("total") or 0),
            "quarantined_assets": int(counts.get("quarantined") or 0),
            "crawler_media": self.media_crawler.status(),
            "agent_has_direct_network": False,
            "agent_has_direct_db": False,
            "autonomous_identity_confirmation": False,
            "autonomous_geolocation_fact": False,
        }

    def crawler_status(self) -> dict[str, Any]:
        base = dict(self.build352.crawler_status())
        base.update({
            "crawler_improvement_build": 353,
            "media_image_discovery": True,
            "media_fetch_job_type": "media_image_fetch_v1",
            "media_same_host_only": True,
            "media_redirect_auto_follow": False,
            "image_magic_verification": True,
            "image_quarantine_handoff": True,
        })
        return base

    def architecture_status(self) -> dict[str, Any]:
        return {
            **dict(self.build352.architecture_status()),
            "image_policy": IMAGE_POLICY,
            "media_crawler_policy": MEDIA_CRAWLER_POLICY,
            "image_agent_local_only": True,
            "image_agent_direct_network": False,
            "image_agent_direct_database": False,
            "image_raw_bytes_in_agent_task_contract": False,
            "metadata_vs_derivation_separated": True,
            "face_identity_confirmation": False,
            "visual_geolocation_in_build353": False,
            "reverse_image_search_in_build353": False,
            "ocr_explicit_human_action": True,
            "darknet_images_forced_quarantine": True,
            "built_in_live_tor_transport": False,
        }

    @staticmethod
    def _maturity(states: dict[str, bool]) -> str:
        last = "declared"
        for key in DIMENSIONS:
            if states[key]:
                last = key
            else:
                break
        return last

    def capabilities(self) -> list[dict[str, Any]]:
        bench = bool(self._benchmark())
        metrics = self.schema_metrics()
        version = self.version_status()
        specs = [
            ("schema_baseline_v1_353", "Schema Baseline retained", "schema", metrics["within_gate"], metrics["within_gate"], "schema", bench, False),
            ("image_secure_ingest_v1", "Secure image ingest + magic verification", "image", True, True, "secure_ingest", bench, False),
            ("image_metadata_extraction_v1", "EXIF/IPTC/XMP metadata extraction", "image", True, True, "metadata", bench, False),
            ("image_ocr_local_v1", "Explicit local OCR workflow", "image", True, True, "ocr", bench, False),
            ("image_epistemic_boundaries_v1", "Metadata/derivation/hypothesis boundaries", "image", True, True, "boundaries", bench, False),
            ("crawler_media_handoff_v1", "Governed crawler media handoff", "crawler", True, True, "media_crawler", bench, False),
            ("darknet_image_quarantine_v1", "Darknet image forced quarantine", "darknet", True, True, "darknet_image", bench, False),
            ("canonical_versioning_353", "Canonical Build 353 version contract", "packaging", version["coherent"], version["coherent"], "version", False, False),
        ]
        rows: list[dict[str, Any]] = []
        fp = self.code_fingerprint()
        for key, name, category, implemented, integrated, probe, benchmarked, externally_validated in specs:
            tested = bool(integrated and self._probe(probe))
            states = {
                "implemented": bool(implemented),
                "integrated": bool(implemented and integrated),
                "tested": tested,
                "benchmarked": bool(tested and benchmarked),
                "externally_validated": bool(tested and externally_validated),
            }
            rows.append({"capability_key": key, "display_name": name, "category": category, **states, "maturity": self._maturity(states), "required_for_baseline": True, "required_for_production": True, "code_fingerprint": fp})
        return rows

    def qualified_gate(self) -> dict[str, Any]:
        rows = self.capabilities()
        baseline = [r for r in rows if r["required_for_baseline"]]
        baseline_tested = bool(baseline) and all(r["tested"] for r in baseline)
        schema_gate = bool(self.schema_metrics()["within_gate"])
        build_acceptance = bool(baseline_tested and schema_gate)
        production = bool(rows) and all(r["externally_validated"] for r in rows if r["required_for_production"])
        return {
            "build": self.BUILD,
            "phase": "15",
            "gate_authority": "build353_image_intelligence_evidence_gate",
            "build_acceptance_ready": build_acceptance,
            "production_release_ready": production,
            "release_ready": production,
            "baseline_tested": baseline_tested,
            "schema_gate": schema_gate,
            "active_gate_literal_true_lines": self.active_gate_literal_true_lines(),
            "rule": "Build 353 validates secure local image handling and controlled crawler media handoff. It does not claim identity recognition, visual geolocation, reverse-image search, live Tor validation, or production readiness.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "phase": "15",
            "name": "Image Intelligence Agent v1 & Secure Media Crawler",
            "schema": self.schema_metrics(),
            "image": self.image_status(),
            "crawler": self.crawler_status(),
            "architecture": self.architecture_status(),
            "gate": self.qualified_gate(),
            "version": self.version_status(),
            "capabilities": self.capabilities(),
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        assets = self.image_assets(case_id=case_id, limit=20)
        rows = "".join(
            f"<tr><td><code>{html.escape(a['media_id'])}</code></td><td>{html.escape(a['sha256'][:16])}…</td><td>{html.escape(a['review_status'])}</td><td>{html.escape(str(a['metadata'].get('inspection',{}).get('format','')))}</td><td>{html.escape(str(a['metadata'].get('inspection',{}).get('width','')))}×{html.escape(str(a['metadata'].get('inspection',{}).get('height','')))}</td></tr>"
            for a in assets
        ) or "<tr><td colspan='5'>Noch keine Build-353-Bilder.</td></tr>"
        return (
            "<section class='card'><h2>Phase 15 · Build 353 · Image Intelligence Agent v1</h2>"
            "<p>Magic-Byte/MIME-Prüfung, SHA-256, EXIF/IPTC/XMP und explizites lokales OCR. Metadaten werden strikt von Ableitungen getrennt; keine automatische Identitätsbestätigung oder visuelle Geolokation.</p>"
            f"<form method='post' action='/cases/{html.escape(case_id)}/images' enctype='multipart/form-data'><input type='hidden' name='csrf' value='{html.escape(csrf)}'><label>Bilddatei</label><input type='file' name='image' accept='image/jpeg,image/png,image/webp,image/gif,image/tiff,image/bmp' required><label>Search Run ID (optional)</label><input name='search_run_id'><label>Source ID (bei Darknet erforderlich)</label><input name='source_id'><button>Prüfen & hashgebunden speichern</button></form>"
            f"<table><thead><tr><th>Media</th><th>SHA-256</th><th>Status</th><th>Format</th><th>Pixel</th></tr></thead><tbody>{rows}</tbody></table>"
            "<p><small>Status: <code>/api/build353</code></small></p></section>"
        )
