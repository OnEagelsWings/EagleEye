from __future__ import annotations

import ast
import hashlib
import html
import json
import re
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from eagleeye.crawler.engine import CrawlTransport
from eagleeye.image_intelligence.similarity import ImageSimilarity354, POLICY_VERSION as SIMILARITY_POLICY

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


class Build354ImageSimilarityService:
    BUILD = "354.0"

    def __init__(self, db: Any, audit: Any, *, build353: Any, similarity: ImageSimilarity354, install_dir: str | Path, base_dir: str | Path, actor: str = "local-analyst") -> None:
        self.db = db
        self.audit = audit
        self.build353 = build353
        self.similarity = similarity
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._root = self.install_dir

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build353, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/infrastructure/schema_v1/schema.py",
            "src/eagleeye/image_intelligence/agent.py",
            "src/eagleeye/image_intelligence/similarity.py",
            "src/eagleeye/crawler/media.py",
            "src/eagleeye/application/build354/service.py",
            "src/eagleeye/interfaces/web/app354.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "EAGLEEYE_PRO_354_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_354_0.py",
            "tests/test_build354.py",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            p = self._root / rel
            h.update(rel.encode("utf-8")); h.update(b"\0")
            h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        value = _read_json(self._root / "BUILD_354_TEST_EVIDENCE.json")
        if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint():
            return value
        return {}

    def _probe(self, key: str) -> bool:
        return self._test_evidence().get("probes", {}).get(key) == "pass"

    def _benchmark(self) -> dict[str, Any]:
        value = _read_json(self._root / "BENCHMARK_BUILD_354_IMAGE_SIMILARITY.json")
        if value.get("build") == self.BUILD and value.get("code_fingerprint") == self.code_fingerprint() and int(value.get("cases", 0)) >= 550 and value.get("violations") == 0 and value.get("result") == "pass":
            return value
        return {}

    def schema_metrics(self) -> dict[str, Any]:
        return self.build353.schema_metrics()

    def version_status(self) -> dict[str, Any]:
        vt = (self._root / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        pt = (self._root / "pyproject.toml").read_text(encoding="utf-8")
        rb = re.search(r'^BUILD\s*=\s*["\']([^"\']+)', vt, re.M)
        rs = re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', vt, re.M)
        rp = re.search(r'^version\s*=\s*["\']([^"\']+)', pt, re.M)
        runtime = rb.group(1) if rb else "unknown"; schema = rs.group(1) if rs else "unknown"; package = rp.group(1) if rp else "unknown"
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == "354.0.0"}

    def active_gate_literal_true_lines(self) -> list[int]:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "qualified_gate":
                return sorted({int(c.lineno) for c in ast.walk(node) if isinstance(c, ast.Constant) and c.value is True and hasattr(c, "lineno")})
        return []

    def _metadata_row(self, media_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        row = self.db.one("SELECT * FROM phase15_media_assets WHERE media_id=?", (media_id,))
        if not row:
            raise KeyError(media_id)
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except Exception:
            metadata = {}
        return row, metadata

    def _save_metadata(self, media_id: str, metadata: dict[str, Any]) -> None:
        self.db.execute("UPDATE phase15_media_assets SET metadata_json=? WHERE media_id=?", (_canon(metadata), media_id))

    def similarity_fingerprint(self, media_id: str, *, persist: bool = True) -> dict[str, Any]:
        row, metadata = self._metadata_row(media_id)
        existing = metadata.get("similarity_v1")
        if isinstance(existing, dict) and existing.get("policy") == SIMILARITY_POLICY:
            return existing
        raw = self.build353.artifact_bytes(row["object_ref"])
        fp = self.similarity.fingerprint(raw)
        if persist:
            metadata["similarity_v1"] = fp
            metadata.setdefault("epistemic_contract", {}).update({
                "image_similarity": "candidate_only_not_identity",
                "local_embedding": "handcrafted_visual_descriptor_not_biometric_identity_embedding",
                "reverse_image_hit": "external_lead_only_requires_human_review",
            })
            self._save_metadata(media_id, metadata)
        return fp

    def _asset_dimensions(self, metadata: dict[str, Any]) -> tuple[int, int]:
        inspection = metadata.get("inspection") if isinstance(metadata, dict) else {}
        try:
            return int(inspection.get("width") or 0), int(inspection.get("height") or 0)
        except Exception:
            return 0, 0

    def _link_candidate(self, *, case_id: str, left_id: str, right_id: str, comparison: dict[str, Any], left_meta: dict[str, Any], right_meta: dict[str, Any]) -> dict[str, Any] | None:
        relation = str(comparison.get("relation") or "no_similarity_lead")
        if relation == "no_similarity_lead" or left_id == right_id:
            return None
        a, b = sorted((left_id, right_id))
        existing = self.db.one("SELECT * FROM phase15_object_links WHERE case_id=? AND from_type='media' AND from_id=? AND relation=? AND to_type='media' AND to_id=?", (case_id, a, relation, b))
        if existing:
            return existing
        lw, lh = self._asset_dimensions(left_meta); rw, rh = self._asset_dimensions(right_meta)
        scale_variant = False
        if lw and lh and rw and rh and (lw, lh) != (rw, rh):
            scale_variant = abs((lw / lh) - (rw / rh)) <= 0.02
        provenance = {
            "policy": SIMILARITY_POLICY,
            "comparison": comparison,
            "scale_variant_candidate": scale_variant,
            "candidate_only": True,
            "requires_human_review": True,
            "identity_confirmed": False,
            "same_source_confirmed": False,
        }
        link_id = "lnk_" + uuid.uuid4().hex[:24]
        self.db.execute(
            "INSERT INTO phase15_object_links(link_id,case_id,from_type,from_id,relation,to_type,to_id,provenance_json,created_at) VALUES(?,?,?,?,?,?,?,?,datetime('now'))",
            (link_id, case_id, "media", a, relation, "media", b, _canon(provenance)),
        )
        return {"link_id": link_id, "from_id": a, "to_id": b, "relation": relation, "provenance": provenance}

    def analyze_similarity(self, media_id: str, *, limit: int = 250) -> dict[str, Any]:
        row, metadata = self._metadata_row(media_id)
        fp = self.similarity_fingerprint(media_id)
        rows = self.db.all("SELECT * FROM phase15_media_assets WHERE case_id=? AND media_kind='image' AND media_id<>? ORDER BY created_at DESC LIMIT ?", (row["case_id"], media_id, max(1, min(int(limit), 500))))
        candidates: list[dict[str, Any]] = []
        for other in rows:
            try:
                ometa = json.loads(other["metadata_json"] or "{}")
            except Exception:
                ometa = {}
            ofp = ometa.get("similarity_v1") if isinstance(ometa.get("similarity_v1"), dict) else None
            if not ofp or ofp.get("policy") != SIMILARITY_POLICY:
                ofp = self.similarity_fingerprint(other["media_id"])
                _, ometa = self._metadata_row(other["media_id"])
            cmp = self.similarity.compare_fingerprints(fp, ofp)
            if cmp["relation"] != "no_similarity_lead":
                link = self._link_candidate(case_id=row["case_id"], left_id=media_id, right_id=other["media_id"], comparison=cmp, left_meta=metadata, right_meta=ometa)
                candidates.append({"media_id": other["media_id"], "comparison": cmp, "link": link})
        candidates.sort(key=lambda x: (0 if x["comparison"]["exact_sha256"] else 1, x["comparison"]["dhash_hamming"], -x["comparison"]["local_embedding_cosine"]))
        return {"media_id": media_id, "policy": SIMILARITY_POLICY, "fingerprint": fp, "candidates": candidates, "requires_human_review": bool(candidates), "identity_confirmed": False}

    def similarity_links(self, *, case_id: str, media_id: str | None = None) -> list[dict[str, Any]]:
        if media_id:
            rows = self.db.all("SELECT * FROM phase15_object_links WHERE case_id=? AND from_type='media' AND to_type='media' AND (from_id=? OR to_id=?) ORDER BY created_at DESC", (case_id, media_id, media_id))
        else:
            rows = self.db.all("SELECT * FROM phase15_object_links WHERE case_id=? AND from_type='media' AND to_type='media' ORDER BY created_at DESC", (case_id,))
        for row in rows:
            try: row["provenance"] = json.loads(row.pop("provenance_json"))
            except Exception: row["provenance"] = {}
        return rows

    def ingest_image(self, **kwargs: Any) -> dict[str, Any]:
        stored = self.build353.ingest_image(**kwargs)
        similarity = self.analyze_similarity(stored["media_id"])
        return {**stored, "similarity": similarity}

    def run_next_media_fetch(self, *, worker_id: str, transport: CrawlTransport, resolver: Callable[[str], list[str]] | None = None) -> dict[str, Any] | None:
        payload = self.build353.media_crawler.fetch_next(worker_id=worker_id, transport=transport, resolver=resolver)
        if payload is None or "error" in payload:
            return payload
        response = payload["response"]
        stored = self.ingest_image(
            case_id=payload["case_id"], content=response.body, declared_media_type=str(response.headers.get("content-type") or ""), filename=payload["url"].rsplit("/", 1)[-1],
            search_run_id=payload["search_run_id"], source_id=payload["source_id"], provenance={"crawler_media_policy": "phase15.media-crawler.v1.secure-image-handoff", "url": payload["url"], "transport_kind": getattr(transport, "transport_kind", "unknown"), "build354_asset_similarity": True},
        )
        job = self.build353.media_crawler.complete_fetch(payload, object_id=stored["object"]["object_id"], media_id=stored["media_id"], worker_id=worker_id)
        return {"job": job, "stored": stored, "url": payload["url"]}

    def run_next_crawl(self, **kwargs: Any) -> dict[str, Any] | None:
        result = self.build353.run_next_crawl(**kwargs)
        if result and "build353_media_discovery" in result:
            result = {**result, "build354_media_discovery": result["build353_media_discovery"]}
        return result

    def review_image(self, media_id: str, *, decision: str, rationale: str, reviewer: str | None = None) -> dict[str, Any]:
        if decision not in {"approve_safe", "keep_quarantined", "reject"}:
            raise ValueError("invalid image review decision")
        row, _ = self._metadata_row(media_id)
        event = self.build353.review_artifact(row["object_ref"], decision=decision, rationale=rationale, reviewer=reviewer or self.actor)
        status = {"approve_safe": "reviewed_safe", "keep_quarantined": "quarantined", "reject": "rejected"}[decision]
        self.db.execute("UPDATE phase15_media_assets SET review_status=? WHERE media_id=?", (status, media_id))
        return {"media_id": media_id, "review_status": status, "object_review_event": event}

    def register_image_search_provider(self, *, provider_key: str, display_name: str, endpoint_host: str, terms_ref: str) -> dict[str, Any]:
        key = re.sub(r"[^a-z0-9_.-]", "", str(provider_key).lower())[:80]
        host = str(endpoint_host).strip().lower().strip(".")
        if not key or not host or "." not in host or not terms_ref.strip():
            raise ValueError("provider key, endpoint host and terms reference required")
        locator = f"https://{host}/"
        existing = self.db.one("SELECT * FROM phase15_sources WHERE source_kind='external_image_search' AND locator=?", (locator,))
        if existing:
            return existing
        now = self.db.one("SELECT datetime('now') t")["t"]
        source_id = "src_" + uuid.uuid4().hex[:24]
        prov = {"policy": SIMILARITY_POLICY, "provider_key": key, "endpoint_host": host, "terms_ref": terms_ref.strip(), "network_execution_by_build354": False, "external_results_are_leads_only": True}
        body = {"source_id": source_id, "source_kind": "external_image_search", "locator": locator, "display_name": str(display_name)[:200], "source_class": "image_search_provider", "jurisdiction": "provider_dependent", "allowed_use": "public_or_authorized_read_only", "review_status": "pending", "risk_class": "medium", "provenance_json": _canon(prov), "created_by": self.actor, "created_at": now, "updated_at": now}
        self.db.execute("INSERT INTO phase15_sources(source_id,source_kind,locator,display_name,source_class,jurisdiction,allowed_use,review_status,risk_class,provenance_json,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (*body.values(), _sha(body)))
        return self.db.one("SELECT * FROM phase15_sources WHERE source_id=?", (source_id,))

    def review_image_search_provider(self, source_id: str, *, decision: str, rationale: str, reviewer: str | None = None) -> dict[str, Any]:
        if decision not in {"approve_read_only", "reject"}:
            raise ValueError("invalid provider review decision")
        source = self.db.one("SELECT * FROM phase15_sources WHERE source_id=? AND source_kind='external_image_search'", (source_id,))
        if not source:
            raise KeyError(source_id)
        now = self.db.one("SELECT datetime('now') t")["t"]
        event = {"event_id": "sre_" + uuid.uuid4().hex[:24], "source_id": source_id, "decision": decision, "rationale": str(rationale)[:4000], "reviewer": reviewer or self.actor, "created_at": now}
        self.db.execute("INSERT INTO phase15_source_review_events(event_id,source_id,decision,rationale,reviewer,created_at,record_hash) VALUES(?,?,?,?,?,?,?)", (*event.values(), _sha(event)))
        self.db.execute("UPDATE phase15_sources SET review_status=?,updated_at=? WHERE source_id=?", ("approved_read_only" if decision == "approve_read_only" else "rejected", now, source_id))
        return {**event, "review_status": "approved_read_only" if decision == "approve_read_only" else "rejected"}

    def enqueue_reverse_image_lead(self, *, media_id: str, provider_source_id: str, human_approved: bool = False) -> dict[str, Any]:
        if not human_approved:
            raise PermissionError("explicit human approval required for external image-search lead")
        asset = self.image_asset(media_id)
        if asset["review_status"] in {"quarantined", "rejected"}:
            raise PermissionError("image must be human-reviewed safe before external image-search handoff")
        provider = self.db.one("SELECT * FROM phase15_sources WHERE source_id=? AND source_kind='external_image_search'", (provider_source_id,))
        if not provider or provider["review_status"] != "approved_read_only":
            raise PermissionError("reviewed external image-search provider required")
        payload = {
            "policy": SIMILARITY_POLICY,
            "media_id": media_id,
            "object_ref": asset["object_ref"],
            "sha256": asset["sha256"],
            "provider_source_id": provider_source_id,
            "provider_locator": provider["locator"],
            "raw_image_bytes_in_job": False,
            "network_execution_by_build354": False,
            "requires_external_gateway": True,
            "external_hit_is_lead_only": True,
            "identity_confirmation_allowed": False,
        }
        return self.build353.enqueue_job(
            job_type="reverse_image_search_lead_v1", payload=payload, case_id=asset["case_id"], search_run_id=None,
            idempotency_key=f"reverse354:{media_id}:{provider_source_id}", max_attempts=1, priority=90,
            resource_budget={"max_runtime_seconds": 180, "max_memory_mb": 512, "max_output_bytes": 2_000_000}, rate_budget={"max_requests": 1, "requests_per_minute": 1},
        )

    def record_reverse_image_leads(self, *, media_id: str, provider_source_id: str, hits: list[dict[str, Any]], gateway_evidence: str) -> dict[str, Any]:
        asset = self.image_asset(media_id)
        provider = self.db.one("SELECT * FROM phase15_sources WHERE source_id=? AND source_kind='external_image_search'", (provider_source_id,))
        if not provider or provider["review_status"] != "approved_read_only":
            raise PermissionError("reviewed provider required")
        if not str(gateway_evidence).strip():
            raise ValueError("gateway evidence required")
        clean: list[dict[str, Any]] = []
        for hit in list(hits)[:50]:
            url = str(hit.get("url") or "").strip()
            p = urlsplit(url)
            if p.scheme not in {"http", "https"} or not p.hostname:
                continue
            clean.append({"url": url[:3000], "source_context": str(hit.get("source_context") or "")[:1000], "provider_score": hit.get("provider_score"), "classification": "external_image_hit_lead_only", "requires_human_review": True, "identity_confirmed": False, "location_confirmed": False})
        result = {"media_id": media_id, "provider_source_id": provider_source_id, "gateway_evidence": str(gateway_evidence)[:1000], "hits": clean, "lead_count": len(clean), "external_hits_are_leads_only": True, "requires_human_review": True, "identity_confirmed": False}
        return self.build353._agent_record(case_id=asset["case_id"], action_class="reverse_image_leads_v1", payload={"media_id": media_id, "provider_source_id": provider_source_id, "raw_bytes_in_task": False}, result=result) | {"result": result}

    def image_similarity_status(self) -> dict[str, Any]:
        links = self.db.one("SELECT COUNT(*) c FROM phase15_object_links WHERE from_type='media' AND to_type='media'")
        providers = self.db.one("SELECT COUNT(*) c FROM phase15_sources WHERE source_kind='external_image_search'")
        return {
            **self.similarity.status(),
            "candidate_links": int((links or {}).get("c") or 0),
            "external_provider_records": int((providers or {}).get("c") or 0),
            "external_provider_live_validation": "not_run",
            "reverse_image_network_execution_by_build354": False,
            "external_hits_are_leads_only": True,
        }

    def crawler_status(self) -> dict[str, Any]:
        base = dict(self.build353.crawler_status())
        base.update({
            "crawler_improvement_build": 354,
            "asset_exact_dedup": True,
            "asset_perceptual_hashing": True,
            "asset_local_embedding": True,
            "asset_variant_candidate_links": True,
            "variant_links_require_human_review": True,
            "cross_source_identity_promotion": False,
        })
        return base

    def architecture_status(self) -> dict[str, Any]:
        return {
            **dict(self.build353.architecture_status()),
            "similarity_policy": SIMILARITY_POLICY,
            "similarity_local_only": True,
            "perceptual_hashes": ["ahash64", "dhash64"],
            "local_embedding_kind": "handcrafted_visual_descriptor_not_identity_or_biometric_embedding",
            "similarity_is_identity_evidence": False,
            "reverse_image_gateway_deferred": True,
            "reverse_image_hits_are_leads_only": True,
            "external_image_provider_live_validation": "not_run",
            "visual_geolocation_in_build354": False,
            "face_identity_confirmation": False,
            "built_in_live_tor_transport": False,
        }

    @staticmethod
    def _maturity(states: dict[str, bool]) -> str:
        last = "declared"
        for key in DIMENSIONS:
            if states[key]: last = key
            else: break
        return last

    def capabilities(self) -> list[dict[str, Any]]:
        bench = bool(self._benchmark()); metrics = self.schema_metrics(); version = self.version_status()
        specs = [
            ("schema_baseline_v1_354", "Schema Baseline retained", "schema", metrics["within_gate"], metrics["within_gate"], "schema", bench, False),
            ("image_exact_duplicate_v1", "Exact image duplicate detection", "image", True, True, "exact", bench, False),
            ("image_perceptual_hash_v1", "aHash/dHash perceptual similarity", "image", True, True, "perceptual", bench, False),
            ("image_local_embedding_v1", "Local handcrafted visual descriptor", "image", True, True, "embedding", bench, False),
            ("image_variant_links_v1", "Review-first image variant candidate links", "image", True, True, "links", bench, False),
            ("crawler_asset_intelligence_v1", "Crawler asset dedup/variant handoff", "crawler", True, True, "crawler", bench, False),
            ("external_image_search_gateway_v1", "Approved external image-search gateway leads", "image", True, True, "external_gateway", False, False),
            ("darknet_image_quarantine_retained_354", "Darknet image quarantine retained", "darknet", True, True, "darknet", bench, False),
            ("canonical_versioning_354", "Canonical Build 354 version contract", "packaging", version["coherent"], version["coherent"], "version", False, False),
        ]
        rows: list[dict[str, Any]] = []
        fp = self.code_fingerprint()
        for key, name, category, implemented, integrated, probe, benchmarked, externally_validated in specs:
            tested = bool(integrated and self._probe(probe))
            states = {"implemented": bool(implemented), "integrated": bool(implemented and integrated), "tested": tested, "benchmarked": bool(tested and benchmarked), "externally_validated": bool(tested and externally_validated)}
            rows.append({"capability_key": key, "display_name": name, "category": category, **states, "maturity": self._maturity(states), "required_for_baseline": True, "required_for_production": True, "live_external_validation": "not_run" if key == "external_image_search_gateway_v1" else "not_applicable_or_pending", "code_fingerprint": fp})
        return rows

    def qualified_gate(self) -> dict[str, Any]:
        rows = self.capabilities(); baseline = [r for r in rows if r["required_for_baseline"]]
        baseline_tested = bool(baseline) and all(r["tested"] for r in baseline)
        schema_gate = self.schema_metrics()["within_gate"]
        production = bool(rows) and all(r["externally_validated"] for r in rows if r["required_for_production"])
        return {
            "build": self.BUILD, "phase": "15", "gate_authority": "build354_image_similarity_evidence_gate",
            "build_acceptance_ready": bool(baseline_tested and schema_gate), "production_release_ready": production, "release_ready": production,
            "baseline_tested": baseline_tested, "schema_gate": schema_gate, "external_image_provider_validated": False,
            "active_gate_literal_true_lines": self.active_gate_literal_true_lines(),
            "rule": "Image similarity is candidate-only. Local hashes/descriptors never confirm identity, location or source. External reverse-image services remain reviewed gateway leads until independently validated.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {"build": self.BUILD, "phase": "15", "name": "Image Similarity & Asset Intelligence", "schema": self.schema_metrics(), "image_similarity": self.image_similarity_status(), "crawler": self.crawler_status(), "architecture": self.architecture_status(), "gate": self.qualified_gate(), "version": self.version_status(), "capabilities": self.capabilities()}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        assets = self.image_assets(case_id=case_id, limit=30)
        links = self.similarity_links(case_id=case_id)
        rows = "".join(f"<tr><td><code>{html.escape(a['media_id'])}</code></td><td><code>{html.escape(a['sha256'][:16])}…</code></td><td>{html.escape(a['review_status'])}</td></tr>" for a in assets) or "<tr><td colspan='3'>Noch keine Bilder.</td></tr>"
        return (
            "<section class='card'><h2>Phase 15 · Build 354 · Image Similarity & Asset Intelligence</h2>"
            f"<p><b>Bilder:</b> {len(assets)} · <b>Ähnlichkeitslinks:</b> {len(links)} · Externe Reverse-Image-Treffer bleiben reviewpflichtige Leads.</p>"
            "<p>SHA-256, aHash/dHash und lokale visuelle Deskriptoren dienen ausschließlich zur Asset-Ähnlichkeit. Sie bestätigen weder Person, Ort noch gemeinsame Quelle.</p>"
            f"<table><thead><tr><th>Media</th><th>SHA-256</th><th>Review</th></tr></thead><tbody>{rows}</tbody></table>"
            "<p><small>Status: <code>/api/build354</code></small></p></section>"
        )
