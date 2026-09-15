from __future__ import annotations

import ast
import hashlib
import html
import json
import re
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable

from eagleeye.crawler.engine import CrawlTransport
from eagleeye.crawler.visual_context import POLICY_VERSION as CONTEXT_POLICY, VisualContextCrawler355
from eagleeye.image_intelligence.geolocation import (
    MANIPULATION_POLICY_VERSION,
    POLICY_VERSION as GEO_POLICY,
    VisualGeoManipulation355,
)

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


class Build355VisualGeoService:
    BUILD = "355.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        build354: Any,
        visual_geo: VisualGeoManipulation355,
        visual_context: VisualContextCrawler355,
        install_dir: str | Path,
        base_dir: str | Path,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.build354 = build354
        self.visual_geo = visual_geo
        self.visual_context = visual_context
        self.install_dir = Path(install_dir)
        self.base_dir = Path(base_dir)
        self.actor = actor
        self._root = self.install_dir

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        value = getattr(self.build354, name, None)
        if value is None:
            raise AttributeError(name)
        return value

    def _fingerprint_paths(self) -> tuple[str, ...]:
        return (
            "src/eagleeye/infrastructure/schema_v1/schema.py",
            "src/eagleeye/image_intelligence/agent.py",
            "src/eagleeye/image_intelligence/similarity.py",
            "src/eagleeye/image_intelligence/geolocation.py",
            "src/eagleeye/crawler/media.py",
            "src/eagleeye/crawler/visual_context.py",
            "src/eagleeye/application/build355/service.py",
            "src/eagleeye/interfaces/web/app355.py",
            "eagleeye_pro/core/app_context.py",
            "src/eagleeye/interfaces/web/server.py",
            "eagleeye_pro/version.py",
            "pyproject.toml",
            "EAGLEEYE_PRO_355_0.py",
            "EAGLEEYE_ACCEPTANCE_BUILD_355_0.py",
            "tests/test_build355.py",
        )

    def code_fingerprint(self) -> str:
        h = hashlib.sha256()
        for rel in self._fingerprint_paths():
            p = self._root / rel
            h.update(rel.encode("utf-8")); h.update(b"\0")
            h.update(p.read_bytes() if p.is_file() else b"<missing>"); h.update(b"\0")
        return h.hexdigest()

    def _test_evidence(self) -> dict[str, Any]:
        value = _read_json(self._root / "BUILD_355_TEST_EVIDENCE.json")
        if value.get("build") == self.BUILD and value.get("result") == "pass" and value.get("code_fingerprint") == self.code_fingerprint():
            return value
        return {}

    def _probe(self, key: str) -> bool:
        return self._test_evidence().get("probes", {}).get(key) == "pass"

    def _benchmark(self) -> dict[str, Any]:
        value = _read_json(self._root / "BENCHMARK_BUILD_355_VISUAL_GEO.json")
        if value.get("build") == self.BUILD and value.get("code_fingerprint") == self.code_fingerprint() and int(value.get("cases", 0)) >= 600 and value.get("violations") == 0 and value.get("result") == "pass":
            return value
        return {}

    def schema_metrics(self) -> dict[str, Any]:
        return self.build354.schema_metrics()

    def version_status(self) -> dict[str, Any]:
        vt = (self._root / "eagleeye_pro/version.py").read_text(encoding="utf-8")
        pt = (self._root / "pyproject.toml").read_text(encoding="utf-8")
        rb = re.search(r'^BUILD\s*=\s*["\']([^"\']+)', vt, re.M)
        rs = re.search(r'^SCHEMA_VERSION\s*=\s*["\']([^"\']+)', vt, re.M)
        rp = re.search(r'^version\s*=\s*["\']([^"\']+)', pt, re.M)
        runtime = rb.group(1) if rb else "unknown"
        schema = rs.group(1) if rs else "unknown"
        package = rp.group(1) if rp else "unknown"
        return {"runtime_build": runtime, "schema_version": schema, "package_version": package, "coherent": runtime == schema == self.BUILD and package == "355.0.0"}

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

    def register_landmark_reference(
        self,
        *,
        media_id: str,
        label: str,
        city: str = "",
        country: str = "",
        latitude: float | None = None,
        longitude: float | None = None,
        human_approved: bool = False,
    ) -> dict[str, Any]:
        if not human_approved:
            raise PermissionError("explicit human approval required for landmark reference")
        row, _ = self._metadata_row(media_id)
        if row["review_status"] != "reviewed_safe":
            raise PermissionError("landmark reference image must be reviewed_safe")
        name = str(label or "").strip()[:240]
        if not name:
            raise ValueError("landmark label required")
        lat = float(latitude) if latitude is not None else None
        lon = float(longitude) if longitude is not None else None
        if lat is not None and not -90 <= lat <= 90:
            raise ValueError("invalid latitude")
        if lon is not None and not -180 <= lon <= 180:
            raise ValueError("invalid longitude")
        geo_id = "geo_ref_" + hashlib.sha256(f"{row['case_id']}|{media_id}|{name}|{city}|{country}|{lat}|{lon}".encode("utf-8")).hexdigest()[:24]
        existing = self.db.one("SELECT * FROM phase15_object_links WHERE case_id=? AND from_type='media' AND from_id=? AND relation='landmark_reference_v1' AND to_type='geo_reference' AND to_id=?", (row["case_id"], media_id, geo_id))
        if existing:
            existing["provenance"] = json.loads(existing.pop("provenance_json"))
            return existing
        provenance = {
            "policy": GEO_POLICY,
            "label": name,
            "city": str(city or "")[:160],
            "country": str(country or "")[:160],
            "latitude": lat,
            "longitude": lon,
            "human_approved": True,
            "reference_scope": "local_reviewed_reference_image",
            "general_landmark_recognition_claimed": False,
            "scene_location_confirmed": False,
        }
        link_id = "lnk_" + uuid.uuid4().hex[:24]
        self.db.execute("INSERT INTO phase15_object_links(link_id,case_id,from_type,from_id,relation,to_type,to_id,provenance_json,created_at) VALUES(?,?,?,?,?,?,?,?,datetime('now'))", (link_id, row["case_id"], "media", media_id, "landmark_reference_v1", "geo_reference", geo_id, _canon(provenance)))
        return {"link_id": link_id, "case_id": row["case_id"], "from_type": "media", "from_id": media_id, "relation": "landmark_reference_v1", "to_type": "geo_reference", "to_id": geo_id, "provenance": provenance}

    def landmark_references(self, *, case_id: str) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM phase15_object_links WHERE case_id=? AND from_type='media' AND relation='landmark_reference_v1' AND to_type='geo_reference' ORDER BY created_at ASC", (case_id,))
        for row in rows:
            try:
                row["provenance"] = json.loads(row.pop("provenance_json"))
            except Exception:
                row["provenance"] = {}
        return rows

    def _landmark_cues(self, media_id: str) -> list[dict[str, Any]]:
        row, _ = self._metadata_row(media_id)
        target_fp = self.build354.similarity_fingerprint(media_id)
        cues: list[dict[str, Any]] = []
        for ref in self.landmark_references(case_id=row["case_id"]):
            ref_media = ref["from_id"]
            if ref_media == media_id:
                continue
            try:
                ref_fp = self.build354.similarity_fingerprint(ref_media)
                cmp = self.build354.similarity.compare_fingerprints(target_fp, ref_fp)
            except Exception:
                continue
            relation = cmp.get("relation")
            if relation == "no_similarity_lead":
                continue
            conf = {"exact_duplicate_candidate": 0.72, "near_duplicate_candidate": 0.62, "visual_variant_candidate": 0.50}.get(str(relation), 0.0)
            p = ref.get("provenance") or {}
            cues.append({
                "kind": "local_landmark_reference",
                "label": str(p.get("label") or "local landmark reference"),
                "city": str(p.get("city") or ""),
                "country": str(p.get("country") or ""),
                "latitude": p.get("latitude"),
                "longitude": p.get("longitude"),
                "confidence": conf,
                "source_ref": ref["link_id"],
                "comparison": cmp,
                "general_landmark_recognition_claimed": False,
            })
        return cues

    def technical_manipulation_signals(self, media_id: str, *, persist: bool = True) -> dict[str, Any]:
        row, metadata = self._metadata_row(media_id)
        raw = self.build354.artifact_bytes(row["object_ref"])
        inspection = metadata.get("inspection") if isinstance(metadata.get("inspection"), dict) else {}
        result = self.visual_geo.technical_signals(raw, inspection=inspection)
        if persist:
            metadata["manipulation_signals_v1"] = result
            metadata.setdefault("epistemic_contract", {}).update({
                "manipulation_signal": "technical_signal_not_forgery_proof",
                "authenticity": "not_confirmed_by_build355",
            })
            self._save_metadata(media_id, metadata)
        return result

    def analyze_visual_geolocation(
        self,
        media_id: str,
        *,
        cues: Iterable[dict[str, Any]] = (),
        include_source_context: bool = True,
        include_landmark_references: bool = True,
        human_approved: bool = False,
    ) -> dict[str, Any]:
        if not human_approved:
            raise PermissionError("explicit human approval required for visual geolocation analysis")
        row, metadata = self._metadata_row(media_id)
        inspection = metadata.get("inspection") if isinstance(metadata.get("inspection"), dict) else {}
        all_cues = [dict(x) for x in list(cues)[:64] if isinstance(x, dict)]
        source_context: dict[str, Any] = {"contexts": [], "cues": [], "context_leads": []}
        if include_source_context:
            source_context = self.visual_context.context_for_media(media_id)
            all_cues.extend(source_context.get("cues") or [])
        landmark_cues: list[dict[str, Any]] = []
        if include_landmark_references:
            landmark_cues = self._landmark_cues(media_id)
            all_cues.extend(landmark_cues)
        geo = self.visual_geo.geolocation(inspection=inspection, cues=all_cues)
        technical = self.technical_manipulation_signals(media_id, persist=False)
        metadata["visual_geolocation_v1"] = geo
        metadata["manipulation_signals_v1"] = technical
        metadata["source_visual_context_v1"] = {
            "policy": CONTEXT_POLICY,
            "context_count": len(source_context.get("contexts") or []),
            "context_leads": list(source_context.get("context_leads") or [])[:40],
            "scene_location_confirmed": False,
        }
        metadata.setdefault("epistemic_contract", {}).update({
            "visual_indication": "candidate_only",
            "geolocation_hypothesis": "hypothesis_only_requires_human_review",
            "embedded_gps": "metadata_or_deterministic_metadata_derivation_not_scene_confirmation",
            "manipulation_signal": "technical_signal_not_authenticity_or_forgery_proof",
        })
        self._save_metadata(media_id, metadata)

        links: list[dict[str, Any]] = []
        for hyp in geo.get("hypotheses") or []:
            hid = "geo_hyp_" + hashlib.sha256(_canon({"media_id": media_id, "candidate": hyp.get("candidate_key"), "label": hyp.get("label")}).encode("utf-8")).hexdigest()[:24]
            existing = self.db.one("SELECT * FROM phase15_object_links WHERE case_id=? AND from_type='media' AND from_id=? AND relation='geolocation_hypothesis_v1' AND to_type='geo_hypothesis' AND to_id=?", (row["case_id"], media_id, hid))
            if existing:
                continue
            prov = {"policy": GEO_POLICY, "hypothesis": hyp, "candidate_only": True, "requires_human_review": True, "scene_location_confirmed": False}
            link_id = "lnk_" + uuid.uuid4().hex[:24]
            self.db.execute("INSERT INTO phase15_object_links(link_id,case_id,from_type,from_id,relation,to_type,to_id,provenance_json,created_at) VALUES(?,?,?,?,?,?,?,?,datetime('now'))", (link_id, row["case_id"], "media", media_id, "geolocation_hypothesis_v1", "geo_hypothesis", hid, _canon(prov)))
            links.append({"link_id": link_id, "to_id": hid, "provenance": prov})

        agent = self.build354.build353._agent_record(
            case_id=row["case_id"],
            action_class="visual_geolocation_and_manipulation_v1",
            payload={"media_id": media_id, "raw_image_bytes_in_task": False, "human_approved": True, "cue_count": len(all_cues)},
            result={
                "media_id": media_id,
                "geolocation": geo,
                "technical_signals": technical,
                "landmark_reference_candidates": landmark_cues,
                "source_context_summary": {"context_count": len(source_context.get("contexts") or []), "lead_count": len(source_context.get("context_leads") or [])},
                "requires_human_review": True,
                "scene_location_confirmed": False,
                "manipulation_confirmed": False,
            },
        )
        return {"media_id": media_id, "geolocation": geo, "technical_signals": technical, "source_context": source_context, "landmark_cues": landmark_cues, "links": links, "agent": agent}

    def geolocation_links(self, *, case_id: str, media_id: str | None = None) -> list[dict[str, Any]]:
        if media_id:
            rows = self.db.all("SELECT * FROM phase15_object_links WHERE case_id=? AND from_type='media' AND from_id=? AND relation='geolocation_hypothesis_v1' ORDER BY created_at DESC", (case_id, media_id))
        else:
            rows = self.db.all("SELECT * FROM phase15_object_links WHERE case_id=? AND from_type='media' AND relation='geolocation_hypothesis_v1' ORDER BY created_at DESC", (case_id,))
        for row in rows:
            try:
                row["provenance"] = json.loads(row.pop("provenance_json"))
            except Exception:
                row["provenance"] = {}
        return rows

    def run_next_media_fetch(self, *, worker_id: str, transport: CrawlTransport, resolver: Callable[[str], list[str]] | None = None) -> dict[str, Any] | None:
        payload = self.build354.build353.media_crawler.fetch_next(worker_id=worker_id, transport=transport, resolver=resolver)
        if payload is None or "error" in payload:
            return payload
        response = payload["response"]
        try:
            job_payload = json.loads(payload["job"].get("payload_json") or "{}")
        except Exception:
            job_payload = {}
        stored = self.build354.ingest_image(
            case_id=payload["case_id"], content=response.body,
            declared_media_type=str(response.headers.get("content-type") or ""), filename=payload["url"].rsplit("/", 1)[-1],
            search_run_id=payload["search_run_id"], source_id=payload["source_id"],
            provenance={
                "crawler_media_policy": "phase15.media-crawler.v1.secure-image-handoff",
                "visual_context_policy": CONTEXT_POLICY,
                "url": payload["url"],
                "crawl_run_id": str(job_payload.get("crawl_run_id") or ""),
                "transport_kind": getattr(transport, "transport_kind", "unknown"),
                "build355_visual_context": True,
            },
        )
        job = self.build354.build353.media_crawler.complete_fetch(payload, object_id=stored["object"]["object_id"], media_id=stored["media_id"], worker_id=worker_id)
        context = self.visual_context.context_for_media(stored["media_id"])
        row, metadata = self._metadata_row(stored["media_id"])
        metadata["source_visual_context_v1"] = {
            "policy": CONTEXT_POLICY,
            "context_count": len(context.get("contexts") or []),
            "context_leads": list(context.get("context_leads") or [])[:40],
            "cues": list(context.get("cues") or [])[:64],
            "scene_location_confirmed": False,
        }
        self._save_metadata(stored["media_id"], metadata)
        return {"job": job, "stored": stored, "url": payload["url"], "build355_visual_context": context}

    def run_next_crawl(self, **kwargs: Any) -> dict[str, Any] | None:
        result = self.build354.run_next_crawl(**kwargs)
        if result and "build354_media_discovery" in result:
            result = {**result, "build355_media_discovery": result["build354_media_discovery"]}
        return result

    def image_geo_status(self) -> dict[str, Any]:
        refs = self.db.one("SELECT COUNT(*) c FROM phase15_object_links WHERE relation='landmark_reference_v1'")
        hyps = self.db.one("SELECT COUNT(*) c FROM phase15_object_links WHERE relation='geolocation_hypothesis_v1'")
        return {
            **self.visual_geo.status(),
            "landmark_reference_records": int((refs or {}).get("c") or 0),
            "geolocation_hypothesis_records": int((hyps or {}).get("c") or 0),
            "external_landmark_provider_live_validation": "not_run",
            "visual_geolocation_requires_explicit_human_action": True,
            "scene_location_auto_confirmation": False,
        }

    def crawler_status(self) -> dict[str, Any]:
        base = dict(self.build354.crawler_status())
        base.update({
            "crawler_improvement_build": 355,
            "visual_context_from_stored_html": True,
            "same_host_source_neighborhood_leads": True,
            "source_neighborhood_auto_fetch": False,
            "page_geo_metadata_is_scene_fact": False,
            "visual_context_allowlist_broadening": False,
            "visual_context_policy": CONTEXT_POLICY,
        })
        return base

    def architecture_status(self) -> dict[str, Any]:
        return {
            **dict(self.build354.architecture_status()),
            "visual_geo_policy": GEO_POLICY,
            "manipulation_signal_policy": MANIPULATION_POLICY_VERSION,
            "visual_geolocation_in_build355": True,
            "visual_geolocation_output": "hypothesis_only",
            "embedded_gps_output": "metadata_or_deterministic_metadata_derivation_not_scene_confirmation",
            "local_landmark_reference_matching": "reference_image_similarity_candidate_only",
            "general_landmark_recognition_claimed": False,
            "manipulation_signals_are_forgery_proof": False,
            "authenticity_confirmation": False,
            "face_identity_confirmation": False,
            "external_visual_geo_provider_live_validation": "not_run",
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
            ("schema_baseline_v1_355", "Schema Baseline retained", "schema", metrics["within_gate"], metrics["within_gate"], "schema", bench, False),
            ("embedded_gps_epistemic_boundary_v1", "Embedded GPS remains metadata-derived evidence", "image", True, True, "gps", bench, False),
            ("visual_geolocation_hypothesis_v1", "Calibrated visual geolocation hypotheses", "image", True, True, "geo", bench, False),
            ("local_landmark_reference_v1", "Reviewed local landmark reference candidates", "image", True, True, "landmark", bench, False),
            ("technical_manipulation_signals_v1", "Non-conclusive technical manipulation signals", "image", True, True, "manipulation", bench, False),
            ("crawler_visual_context_v1", "Same-host visual source-context extraction", "crawler", True, True, "crawler", bench, False),
            ("darknet_image_quarantine_retained_355", "Darknet image quarantine retained", "darknet", True, True, "darknet", bench, False),
            ("canonical_versioning_355", "Canonical Build 355 version contract", "packaging", version["coherent"], version["coherent"], "version", False, False),
        ]
        rows: list[dict[str, Any]] = []
        fp = self.code_fingerprint()
        for key, name, category, implemented, integrated, probe, benchmarked, externally_validated in specs:
            tested = bool(integrated and self._probe(probe))
            states = {"implemented": bool(implemented), "integrated": bool(implemented and integrated), "tested": tested, "benchmarked": bool(tested and benchmarked), "externally_validated": bool(tested and externally_validated)}
            rows.append({"capability_key": key, "display_name": name, "category": category, **states, "maturity": self._maturity(states), "required_for_baseline": True, "required_for_production": True, "live_external_validation": "not_run" if key in {"visual_geolocation_hypothesis_v1", "local_landmark_reference_v1"} else "not_applicable_or_pending", "code_fingerprint": fp})
        return rows

    def qualified_gate(self) -> dict[str, Any]:
        rows = self.capabilities()
        baseline = [r for r in rows if r["required_for_baseline"]]
        baseline_tested = bool(baseline) and all(r["tested"] for r in baseline)
        schema_gate = self.schema_metrics()["within_gate"]
        production = bool(rows) and all(r["externally_validated"] for r in rows if r["required_for_production"])
        return {
            "build": self.BUILD,
            "phase": "15",
            "gate_authority": "build355_visual_geo_evidence_gate",
            "build_acceptance_ready": bool(baseline_tested and schema_gate),
            "production_release_ready": production,
            "release_ready": production,
            "baseline_tested": baseline_tested,
            "schema_gate": schema_gate,
            "external_visual_geo_validated": False,
            "active_gate_literal_true_lines": self.active_gate_literal_true_lines(),
            "rule": "Visual place outputs are hypotheses, embedded GPS is metadata-derived evidence only, and technical manipulation signals never prove forgery or authenticity.",
        }

    def dashboard(self) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "phase": "15",
            "name": "Visual Geolocation & Manipulation Signals",
            "schema": self.schema_metrics(),
            "image_geolocation": self.image_geo_status(),
            "image_similarity": self.build354.image_similarity_status(),
            "crawler": self.crawler_status(),
            "architecture": self.architecture_status(),
            "gate": self.qualified_gate(),
            "version": self.version_status(),
            "capabilities": self.capabilities(),
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        assets = self.image_assets(case_id=case_id, limit=30)
        hyps = self.geolocation_links(case_id=case_id)
        refs = self.landmark_references(case_id=case_id)
        rows = "".join(f"<tr><td><code>{html.escape(a['media_id'])}</code></td><td><code>{html.escape(a['sha256'][:16])}…</code></td><td>{html.escape(a['review_status'])}</td></tr>" for a in assets) or "<tr><td colspan='3'>Noch keine Bilder.</td></tr>"
        return (
            "<section class='card'><h2>Phase 15 · Build 355 · Visual Geolocation & Manipulation Signals</h2>"
            f"<p><b>Bilder:</b> {len(assets)} · <b>Landmark-Referenzen:</b> {len(refs)} · <b>Geo-Hypothesen:</b> {len(hyps)}</p>"
            "<p>EXIF-GPS bleibt Metadaten-/Ableitungsfakt. Visuelle Ortsannahmen bleiben reviewpflichtige Hypothesen. Technische Manipulationssignale beweisen weder Fälschung noch Authentizität.</p>"
            f"<table><thead><tr><th>Media</th><th>SHA-256</th><th>Review</th></tr></thead><tbody>{rows}</tbody></table>"
            "<p><small>Status: <code>/api/build355</code></small></p></section>"
        )
