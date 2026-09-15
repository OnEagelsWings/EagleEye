from __future__ import annotations

import hashlib
import io
import math
import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

from eagleeye.application.build137.service import (
    IMAGE_HASH_VERSION,
    PHOTO_PROVIDERS,
    _average_hash,
    _difference_hash,
    _hamming_hex,
)
from eagleeye_pro.core.database import dumps, loads, new_id, now_ts


NODE_TYPES = {
    "person", "organization", "place", "email", "domain", "phone", "account",
    "document", "webpage", "photo", "photo_copy", "photo_variant", "photo_result",
    "research_run", "other",
}
REVIEW_STATES = {"candidate", "supported", "confirmed", "contradictory", "refuted"}
EPISTEMIC_STATES = {"confirmed", "supported", "hypothesis", "lead", "contradictory", "refuted"}
SOURCE_TYPES = {"primary", "official_register", "institutional", "press", "aggregator", "user_generated", "archive", "unknown"}
STANCES = {"supports", "contradicts", "context"}
WARNING_STATUSES = {"open", "acknowledged", "resolved", "dismissed"}
PHOTO_RESULT_KINDS = {"exact_copy", "cropped_variant", "edited_variant", "visually_similar", "context_only", "unknown"}
PHOTO_REVIEW_STATES = {"candidate", "reviewed", "linked", "rejected"}
PHOTO_RUN_STATUSES = {"prepared", "provider_opened", "uploaded_manually", "results_review", "completed", "cancelled"}
PHOTO_VARIANT_MODES = {"clean_full", "manual_crop", "center_square", "grayscale", "contrast", "detail_enhance"}
EXCLUSIVE_PREDICATES = {"birth_date", "date_of_birth", "life_status", "marital_status", "height", "primary_identity"}
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "msclkid", "ref", "ref_src"}
SENSITIVE_PARAMS = {"token", "access_token", "auth", "authorization", "apikey", "api_key", "key", "secret", "signature", "sig", "session", "password", "passwd"}
VARIANT_MAX_BYTES = 8 * 1024 * 1024
VARIANT_MAX_DIMENSION = 3000
VARIANT_MIN_DIMENSION = 256


def _safe_text(value: Any, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _slug(value: Any, limit: int = 80) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._")
    return (text or "item")[:limit]


def _clamp(value: Any, lower: float = 0.0, upper: float = 1.0) -> float:
    try:
        return max(lower, min(upper, float(value)))
    except (TypeError, ValueError):
        return lower


def _utc_after(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().strip()
    return re.sub(r"\s+", " ", text)[:1000]


def _periods_overlap(a_from: str, a_to: str, b_from: str, b_to: str) -> bool:
    low_a = a_from or "0000-00-00"
    high_a = a_to or "9999-99-99"
    low_b = b_from or "0000-00-00"
    high_b = b_to or "9999-99-99"
    return low_a <= high_b and low_b <= high_a


class Build138Service:
    """Evidence Graph and expanded, investigator-controlled photo research.

    The service records assertions, sources and derivation chains. It can compare
    image files as files, but never identifies a person, never performs face
    recognition and never uploads an image automatically.
    """

    BUILD = "138.0"

    def __init__(
        self,
        db: Any,
        audit: Any,
        base_dir: str | Path,
        install_dir: str | Path,
        *,
        build137: Any,
        build136: Any,
        build135: Any,
        protection: Any,
    ) -> None:
        self.db = db
        self.audit = audit
        self.base_dir = Path(base_dir).resolve()
        self.install_dir = Path(install_dir).resolve()
        self.build137 = build137
        self.build136 = build136
        self.build135 = build135
        self.protection = protection
        self.photo_root = self.build136.photo_root.resolve()
        Image.MAX_IMAGE_PIXELS = 100_000_000
        self.cleanup_expired_variants(actor="startup-cleanup-138")

    # ---------- validation, canonicalization, immutable event chain ----------
    def _case(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not row:
            raise KeyError("Fall nicht gefunden")
        return row

    def _target(self, case_id: str, target_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM targets WHERE case_id=? AND target_id=?", (case_id, target_id))
        if not row:
            raise KeyError("Zielperson nicht gefunden oder falscher Fall")
        return row

    @staticmethod
    def canonical_url(value: str, *, allow_empty: bool = False) -> str:
        text = str(value or "").strip()
        if not text and allow_empty:
            return ""
        parts = urlsplit(text)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            raise ValueError("Nur vollständige HTTP(S)-Quellenadressen sind erlaubt")
        if parts.username or parts.password:
            raise ValueError("Quellenadressen mit eingebetteten Zugangsdaten sind unzulässig")
        host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        port = parts.port
        netloc = host
        if port and not ((parts.scheme.lower() == "http" and port == 80) or (parts.scheme.lower() == "https" and port == 443)):
            netloc = f"{host}:{port}"
        query: list[tuple[str, str]] = []
        for key, val in parse_qsl(parts.query, keep_blank_values=True):
            folded = key.casefold()
            if folded in TRACKING_PARAMS:
                continue
            if folded in SENSITIVE_PARAMS or any(token in folded for token in ("token", "secret", "signature", "password", "session")):
                continue
            query.append((key[:120], val[:1000]))
        path = re.sub(r"/{2,}", "/", parts.path or "/")
        return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(query, doseq=True), ""))[:4000]

    def _event(self, *, case_id: str, event_type: str, object_type: str, object_id: str, actor: str, payload: Mapping[str, Any] | None = None) -> None:
        event_id = new_id("evt138")
        created_at = now_ts()
        previous = self.db.one("SELECT event_hash FROM build138_events WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous_hash = str((previous or {}).get("event_hash") or "GENESIS")
        body = dumps({
            "event_id": event_id,
            "case_id": case_id,
            "event_type": event_type,
            "object_type": object_type,
            "object_id": object_id,
            "payload": dict(payload or {}),
            "previous_hash": previous_hash,
            "created_by": _safe_text(actor, 120),
            "created_at": created_at,
        })
        event_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        self.db.execute(
            "INSERT INTO build138_events(event_id,case_id,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (event_id, case_id, event_type, object_type, object_id, dumps(dict(payload or {})), previous_hash, event_hash, _safe_text(actor, 120), created_at),
        )
        self.audit.log(event_type, object_type, object_id, case_id, dict(payload or {}))

    # ---------- Evidence Graph nodes, sources, assertions ----------
    def upsert_node(
        self,
        *,
        case_id: str,
        node_type: str,
        label: str,
        normalized_value: str = "",
        target_id: str = "",
        attributes: Mapping[str, Any] | None = None,
        review_state: str = "candidate",
        actor: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        if target_id:
            self._target(case_id, target_id)
        if node_type not in NODE_TYPES:
            raise ValueError("Unbekannter Evidence-Node-Typ")
        if review_state not in REVIEW_STATES:
            raise ValueError("Ungültiger Prüfstatus")
        label = _safe_text(label, 500)
        if not label:
            raise ValueError("Node-Bezeichnung fehlt")
        normalized = _normalize(normalized_value or label)
        existing = self.db.one("SELECT * FROM evidence_nodes_138 WHERE case_id=? AND node_type=? AND normalized_value=?", (case_id, node_type, normalized)) if normalized else None
        now = now_ts()
        if existing:
            merged = loads(existing.get("attributes_json"), {})
            merged.update(dict(attributes or {}))
            self.db.execute(
                "UPDATE evidence_nodes_138 SET label=?,target_id=COALESCE(NULLIF(?,''),target_id),attributes_json=?,review_state=?,candidate_only=?,updated_at=? WHERE node_id=?",
                (label, target_id, dumps(merged), review_state, 0 if review_state == "confirmed" else 1, now, existing["node_id"]),
            )
            row = self.db.one("SELECT * FROM evidence_nodes_138 WHERE node_id=?", (existing["node_id"],)) or {}
            row["attributes"] = loads(row.pop("attributes_json", "{}"), {})
            return {**row, "duplicate": True}
        node_id = new_id("node138")
        self.db.execute(
            "INSERT INTO evidence_nodes_138(node_id,case_id,target_id,node_type,label,normalized_value,attributes_json,review_state,candidate_only,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (node_id, case_id, target_id or None, node_type, label, normalized, dumps(dict(attributes or {})), review_state, 0 if review_state == "confirmed" else 1, _safe_text(actor, 120), now, now),
        )
        self._event(case_id=case_id, event_type="evidence_node_created", object_type="evidence_node_138", object_id=node_id, actor=actor, payload={"node_type": node_type, "review_state": review_state})
        row = self.db.one("SELECT * FROM evidence_nodes_138 WHERE node_id=?", (node_id,)) or {}
        row["attributes"] = loads(row.pop("attributes_json", "{}"), {})
        return {**row, "duplicate": False}

    def register_source(
        self,
        *,
        case_id: str,
        title: str,
        canonical_url: str,
        source_type: str,
        independence_group: str,
        actor: str,
        publisher: str = "",
        author: str = "",
        publication_at: str = "",
        retrieved_at: str = "",
        content_hash: str = "",
        parent_source_id: str = "",
        reliability: float = 0.5,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._case(case_id)
        if source_type not in SOURCE_TYPES:
            raise ValueError("Unbekannter Quellentyp")
        title = _safe_text(title, 1000)
        if not title:
            raise ValueError("Quellentitel fehlt")
        url = self.canonical_url(canonical_url, allow_empty=True)
        group = _safe_text(independence_group, 300)
        if not group:
            group = (urlsplit(url).hostname or "manual-source") if url else "manual-source"
        parent = None
        if parent_source_id:
            parent = self.db.one("SELECT * FROM evidence_sources_138 WHERE case_id=? AND source_id=?", (case_id, parent_source_id))
            if not parent:
                raise KeyError("Übergeordnete Quelle gehört nicht zum Fall")
        clean_hash = re.sub(r"[^a-fA-F0-9]", "", str(content_hash or ""))[:64].lower()
        if clean_hash and len(clean_hash) != 64:
            raise ValueError("Content-Hash muss ein SHA-256-Hexwert sein")
        origin_material = clean_hash or url or f"{group}|{title.casefold()}"
        origin_fingerprint = hashlib.sha256(origin_material.encode("utf-8")).hexdigest()
        duplicate = self.db.one(
            "SELECT * FROM evidence_sources_138 WHERE case_id=? AND origin_fingerprint=? AND canonical_url=?",
            (case_id, origin_fingerprint, url),
        )
        if duplicate:
            duplicate["metadata"] = loads(duplicate.pop("metadata_json", "{}"), {})
            return {**duplicate, "duplicate": True}
        source_id = new_id("src138")
        now = now_ts()
        self.db.execute(
            "INSERT INTO evidence_sources_138(source_id,case_id,canonical_url,title,publisher,author,source_type,publication_at,retrieved_at,content_hash,independence_group,origin_fingerprint,parent_source_id,reliability,metadata_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (source_id, case_id, url, title, _safe_text(publisher, 500), _safe_text(author, 500), source_type, _safe_text(publication_at, 40), _safe_text(retrieved_at, 40) or now, clean_hash, group, origin_fingerprint, parent_source_id or None, _clamp(reliability), dumps(dict(metadata or {})), _safe_text(actor, 120), now),
        )
        self._event(case_id=case_id, event_type="evidence_source_registered", object_type="evidence_source_138", object_id=source_id, actor=actor, payload={"source_type": source_type, "independence_group": group, "has_url": bool(url)})
        row = self.db.one("SELECT * FROM evidence_sources_138 WHERE source_id=?", (source_id,)) or {}
        row["metadata"] = loads(row.pop("metadata_json", "{}"), {})
        return {**row, "duplicate": False}

    def create_assertion(
        self,
        *,
        case_id: str,
        subject_node_id: str,
        predicate: str,
        object_node_id: str,
        assertion_text: str,
        epistemic_state: str,
        confidence: float,
        actor: str,
        target_id: str = "",
        valid_from: str = "",
        valid_to: str = "",
        observed_at: str = "",
        review_note: str = "",
    ) -> dict[str, Any]:
        self._case(case_id)
        if target_id:
            self._target(case_id, target_id)
        if epistemic_state not in EPISTEMIC_STATES:
            raise ValueError("Ungültiger epistemischer Status")
        if subject_node_id == object_node_id:
            raise ValueError("Selbstrelation ist nicht zulässig")
        subject = self.db.one("SELECT * FROM evidence_nodes_138 WHERE case_id=? AND node_id=?", (case_id, subject_node_id))
        obj = self.db.one("SELECT * FROM evidence_nodes_138 WHERE case_id=? AND node_id=?", (case_id, object_node_id))
        if not subject or not obj:
            raise KeyError("Subject oder Object gehört nicht zum Fall")
        predicate = re.sub(r"[^a-zA-Z0-9_.:-]+", "_", str(predicate or "").strip()).strip("_")[:120]
        if not predicate:
            raise ValueError("Prädikat fehlt")
        if valid_from and valid_to and valid_from > valid_to:
            raise ValueError("Gültigkeitszeitraum ist widersprüchlich")
        assertion_text = _safe_text(assertion_text, 4000)
        if len(assertion_text) < 5:
            raise ValueError("Aussagetext ist zu kurz")
        assertion_id = new_id("assert138")
        now = now_ts()
        self.db.execute(
            "INSERT INTO evidence_assertions_138(assertion_id,case_id,target_id,subject_node_id,predicate,object_node_id,assertion_text,epistemic_state,confidence,valid_from,valid_to,observed_at,candidate_only,source_count,independence_count,review_note,reviewed_by,reviewed_at,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,?,'','',?,?,?)",
            (assertion_id, case_id, target_id or None, subject_node_id, predicate, object_node_id, assertion_text, epistemic_state, _clamp(confidence), _safe_text(valid_from, 40), _safe_text(valid_to, 40), _safe_text(observed_at, 40) or now, 0 if epistemic_state == "confirmed" else 1, _safe_text(review_note, 4000), _safe_text(actor, 120), now, now),
        )
        self._event(case_id=case_id, event_type="evidence_assertion_created", object_type="evidence_assertion_138", object_id=assertion_id, actor=actor, payload={"predicate": predicate, "epistemic_state": epistemic_state, "candidate_only": epistemic_state != "confirmed"})
        return self.assertion(case_id=case_id, assertion_id=assertion_id)

    def assertion(self, *, case_id: str, assertion_id: str) -> dict[str, Any]:
        row = self.db.one(
            "SELECT a.*,s.label AS subject_label,o.label AS object_label FROM evidence_assertions_138 a JOIN evidence_nodes_138 s ON s.node_id=a.subject_node_id JOIN evidence_nodes_138 o ON o.node_id=a.object_node_id WHERE a.case_id=? AND a.assertion_id=?",
            (case_id, assertion_id),
        )
        if not row:
            raise KeyError("Evidence-Aussage nicht gefunden")
        row["sources"] = self.db.all(
            "SELECT l.*,s.title,s.canonical_url,s.source_type,s.independence_group,s.reliability FROM evidence_assertion_sources_138 l JOIN evidence_sources_138 s ON s.source_id=l.source_id WHERE l.assertion_id=? ORDER BY l.created_at",
            (assertion_id,),
        )
        return row

    def attach_source(
        self,
        *,
        case_id: str,
        assertion_id: str,
        source_id: str,
        stance: str,
        weight: float,
        excerpt: str,
        rationale: str,
        actor: str,
    ) -> dict[str, Any]:
        if stance not in STANCES:
            raise ValueError("Ungültige Quellenhaltung")
        self.assertion(case_id=case_id, assertion_id=assertion_id)
        source = self.db.one("SELECT * FROM evidence_sources_138 WHERE case_id=? AND source_id=?", (case_id, source_id))
        if not source:
            raise KeyError("Quelle gehört nicht zum Fall")
        link_id = new_id("asrc138")
        self.db.execute(
            "INSERT OR REPLACE INTO evidence_assertion_sources_138(link_id,assertion_id,case_id,source_id,stance,weight,excerpt,rationale,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (link_id, assertion_id, case_id, source_id, stance, _clamp(weight), _safe_text(excerpt, 2000), _safe_text(rationale, 2000), _safe_text(actor, 120), now_ts()),
        )
        self._refresh_assertion_counts(assertion_id)
        self._event(case_id=case_id, event_type="assertion_source_attached", object_type="evidence_assertion_138", object_id=assertion_id, actor=actor, payload={"source_id": source_id, "stance": stance})
        return self.assertion(case_id=case_id, assertion_id=assertion_id)

    def _refresh_assertion_counts(self, assertion_id: str) -> None:
        counts = self.db.one(
            "SELECT COUNT(DISTINCT l.source_id) AS sources,COUNT(DISTINCT s.independence_group) AS independent FROM evidence_assertion_sources_138 l JOIN evidence_sources_138 s ON s.source_id=l.source_id WHERE l.assertion_id=? AND l.stance='supports'",
            (assertion_id,),
        ) or {}
        self.db.execute("UPDATE evidence_assertions_138 SET source_count=?,independence_count=?,updated_at=? WHERE assertion_id=?", (int(counts.get("sources") or 0), int(counts.get("independent") or 0), now_ts(), assertion_id))

    def review_assertion(self, *, case_id: str, assertion_id: str, epistemic_state: str, confidence: float, review_note: str, actor: str) -> dict[str, Any]:
        if epistemic_state not in EPISTEMIC_STATES:
            raise ValueError("Ungültiger epistemischer Status")
        self.assertion(case_id=case_id, assertion_id=assertion_id)
        now = now_ts()
        self.db.execute(
            "UPDATE evidence_assertions_138 SET epistemic_state=?,confidence=?,candidate_only=?,review_note=?,reviewed_by=?,reviewed_at=?,updated_at=? WHERE case_id=? AND assertion_id=?",
            (epistemic_state, _clamp(confidence), 0 if epistemic_state == "confirmed" else 1, _safe_text(review_note, 4000), _safe_text(actor, 120), now, now, case_id, assertion_id),
        )
        self._event(case_id=case_id, event_type="evidence_assertion_reviewed", object_type="evidence_assertion_138", object_id=assertion_id, actor=actor, payload={"epistemic_state": epistemic_state, "confidence": _clamp(confidence)})
        return self.assertion(case_id=case_id, assertion_id=assertion_id)

    def add_provenance(
        self,
        *,
        case_id: str,
        from_object_type: str,
        from_object_id: str,
        relation_type: str,
        to_object_type: str,
        to_object_id: str,
        actor: str,
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._case(case_id)
        if from_object_type == to_object_type and from_object_id == to_object_id:
            raise ValueError("Provenienz-Selbstkante ist nicht zulässig")
        relation = re.sub(r"[^a-zA-Z0-9_.:-]+", "_", str(relation_type or "").strip()).strip("_")[:120]
        if not relation:
            raise ValueError("Provenienzrelation fehlt")
        existing = self.db.one(
            "SELECT * FROM evidence_provenance_edges_138 WHERE case_id=? AND from_object_type=? AND from_object_id=? AND relation_type=? AND to_object_type=? AND to_object_id=?",
            (case_id, from_object_type, from_object_id, relation, to_object_type, to_object_id),
        )
        if existing:
            return {**existing, "duplicate": True}
        edge_id = new_id("prov138")
        self.db.execute(
            "INSERT INTO evidence_provenance_edges_138(edge_id,case_id,from_object_type,from_object_id,relation_type,to_object_type,to_object_id,details_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (edge_id, case_id, _safe_text(from_object_type, 100), _safe_text(from_object_id, 200), relation, _safe_text(to_object_type, 100), _safe_text(to_object_id, 200), dumps(dict(details or {})), _safe_text(actor, 120), now_ts()),
        )
        self._event(case_id=case_id, event_type="provenance_edge_created", object_type="evidence_provenance_138", object_id=edge_id, actor=actor, payload={"relation_type": relation})
        return {**(self.db.one("SELECT * FROM evidence_provenance_edges_138 WHERE edge_id=?", (edge_id,)) or {}), "duplicate": False}

    # ---------- migration/synchronization into Evidence Graph ----------
    def sync_case_graph(self, *, case_id: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        created = defaultdict(int)
        target_nodes: dict[str, str] = {}
        for target in self.db.all("SELECT * FROM targets WHERE case_id=?", (case_id,)):
            node = self.upsert_node(case_id=case_id, node_type="person", label=target["name"], normalized_value=f"target:{target['target_id']}", target_id=target["target_id"], attributes={"source": "target", "target_id": target["target_id"]}, actor=actor)
            target_nodes[target["target_id"]] = node["node_id"]
            created["person"] += int(not node.get("duplicate"))
        for photo in self.db.all("SELECT * FROM photo_assets_136 WHERE case_id=?", (case_id,)):
            node = self.upsert_node(case_id=case_id, node_type="photo", label=photo.get("title") or photo.get("original_filename") or "Foto", normalized_value=f"photo:{photo['asset_id']}", target_id=photo.get("target_id") or "", attributes={"asset_id": photo["asset_id"], "sha256": photo.get("sha256"), "mime_type": photo.get("mime_type"), "review_status": photo.get("review_status")}, actor=actor)
            created["photo"] += int(not node.get("duplicate"))
            if photo.get("target_id") in target_nodes:
                self.add_provenance(case_id=case_id, from_object_type="target", from_object_id=photo["target_id"], relation_type="has_candidate_photo", to_object_type="photo_asset_136", to_object_id=photo["asset_id"], actor=actor, details={"identity_claim": False})
        for copy in self.db.all("SELECT * FROM photo_research_copies_137 WHERE case_id=?", (case_id,)):
            node = self.upsert_node(case_id=case_id, node_type="photo_copy", label=copy["filename"], normalized_value=f"photo_copy:{copy['copy_id']}", target_id=copy.get("target_id") or "", attributes={"copy_id": copy["copy_id"], "sha256": copy.get("sha256"), "metadata_removed": bool(copy.get("metadata_removed")), "status": copy.get("status")}, actor=actor)
            created["photo_copy"] += int(not node.get("duplicate"))
            self.add_provenance(case_id=case_id, from_object_type="photo_asset_136", from_object_id=copy["parent_asset_id"], relation_type="research_copy_of", to_object_type="photo_research_copy_137", to_object_id=copy["copy_id"], actor=actor, details={"sha256": copy.get("sha256")})
        for variant in self.db.all("SELECT * FROM photo_variants_138 WHERE case_id=?", (case_id,)):
            node = self.upsert_node(case_id=case_id, node_type="photo_variant", label=variant["label"], normalized_value=f"photo_variant:{variant['variant_id']}", target_id=variant.get("target_id") or "", attributes={"variant_id": variant["variant_id"], "mode": variant["variant_mode"], "sha256": variant["sha256"]}, actor=actor)
            created["photo_variant"] += int(not node.get("duplicate"))
            self.add_provenance(case_id=case_id, from_object_type="photo_asset_136", from_object_id=variant["parent_asset_id"], relation_type="derived_variant", to_object_type="photo_variant_138", to_object_id=variant["variant_id"], actor=actor, details=loads(variant.get("parameters_json"), {}))
        for run in self.db.all("SELECT * FROM photo_search_runs_138 WHERE case_id=?", (case_id,)):
            node = self.upsert_node(case_id=case_id, node_type="research_run", label=f"{run['provider_label']}: {run['purpose']}", normalized_value=f"photo_run:{run['run_id']}", target_id=run.get("target_id") or "", attributes={"run_id": run["run_id"], "provider": run["provider_key"], "status": run["status"], "automatic_upload": False}, actor=actor)
            created["research_run"] += int(not node.get("duplicate"))
            src_type, src_id = ("photo_variant_138", run["variant_id"]) if run.get("variant_id") else ("photo_research_copy_137", run["copy_id"])
            self.add_provenance(case_id=case_id, from_object_type=src_type, from_object_id=src_id, relation_type="searched_with", to_object_type="photo_search_run_138", to_object_id=run["run_id"], actor=actor, details={"provider": run["provider_key"], "automatic_upload": False})
        for result in self.db.all("SELECT * FROM photo_research_results_138 WHERE case_id=?", (case_id,)):
            node = self.upsert_node(case_id=case_id, node_type="photo_result", label=result.get("page_title") or result.get("page_url") or "Fototreffer", normalized_value=f"photo_result:{result['result_id']}", target_id=result.get("target_id") or "", attributes={"result_id": result["result_id"], "result_kind": result["result_kind"], "review_status": result["review_status"], "identity_claim": False}, actor=actor)
            created["photo_result"] += int(not node.get("duplicate"))
            self.add_provenance(case_id=case_id, from_object_type=result["research_run_type"], from_object_id=result["research_run_id"], relation_type="returned_hit", to_object_type="photo_result_138", to_object_id=result["result_id"], actor=actor, details={"source_id": result["source_id"]})
        self._event(case_id=case_id, event_type="case_graph_synchronized", object_type="case", object_id=case_id, actor=actor, payload={"created": dict(created)})
        return {"case_id": case_id, "created": dict(created), "identity_claims": 0}

    # ---------- integrity and contradiction analysis ----------
    def _new_warning(self, *, case_id: str, warning_type: str, severity: str, title: str, summary: str, refs: Iterable[Mapping[str, str]], details: Mapping[str, Any], actor: str) -> str:
        warning_id = new_id("warn138")
        now = now_ts()
        self.db.execute(
            "INSERT INTO evidence_warnings_138(warning_id,case_id,warning_type,severity,title,summary,object_refs_json,details_json,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?, 'open',?,?,?)",
            (warning_id, case_id, warning_type, severity, _safe_text(title, 500), _safe_text(summary, 2000), dumps(list(refs)), dumps(dict(details)), _safe_text(actor, 120), now, now),
        )
        return warning_id

    @staticmethod
    def _find_directed_cycles(edges: Iterable[tuple[str, str]], limit: int = 20) -> list[list[str]]:
        graph: dict[str, set[str]] = defaultdict(set)
        for left, right in edges:
            graph[left].add(right)
        cycles: list[list[str]] = []
        visiting: set[str] = set()
        visited: set[str] = set()
        stack: list[str] = []

        def visit(node: str) -> None:
            if len(cycles) >= limit:
                return
            if node in visiting:
                try:
                    idx = stack.index(node)
                    cycle = stack[idx:] + [node]
                    signature = tuple(cycle)
                    if not any(tuple(item) == signature for item in cycles):
                        cycles.append(cycle)
                except ValueError:
                    pass
                return
            if node in visited:
                return
            visiting.add(node); stack.append(node)
            for nxt in sorted(graph.get(node, set())):
                visit(nxt)
            stack.pop(); visiting.remove(node); visited.add(node)

        for node in sorted(graph):
            visit(node)
        return cycles

    def run_integrity_analysis(self, *, case_id: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        with self.db.transaction(immediate=True):
            self.db.execute("DELETE FROM evidence_warnings_138 WHERE case_id=? AND created_by='system-138' AND status='open'", (case_id,))
            warning_ids: list[str] = []
            assertions = self.db.all("SELECT * FROM evidence_assertions_138 WHERE case_id=?", (case_id,))
            for assertion in assertions:
                self._refresh_assertion_counts(assertion["assertion_id"])
                current = self.db.one("SELECT * FROM evidence_assertions_138 WHERE assertion_id=?", (assertion["assertion_id"],)) or assertion
                source_rows = self.db.all(
                    "SELECT s.* FROM evidence_assertion_sources_138 l JOIN evidence_sources_138 s ON s.source_id=l.source_id WHERE l.assertion_id=? AND l.stance='supports'",
                    (assertion["assertion_id"],),
                )
                if len(source_rows) > 1 and len({row["independence_group"] for row in source_rows}) == 1:
                    warning_ids.append(self._new_warning(case_id=case_id, warning_type="source_dependency", severity="high", title="Mehrere Belege stammen aus derselben Quellenfamilie", summary="Die Aussage wirkt mehrfach belegt, besitzt aber nur eine unabhängige Herkunft.", refs=[{"object_type": "assertion", "object_id": assertion["assertion_id"]}], details={"source_count": len(source_rows), "independence_count": 1}, actor="system-138"))
                if current["epistemic_state"] == "confirmed" and not any(row["source_type"] in {"primary", "official_register", "institutional"} for row in source_rows):
                    warning_ids.append(self._new_warning(case_id=case_id, warning_type="missing_primary_source", severity="medium", title="Bestätigte Aussage ohne Primär- oder institutionelle Quelle", summary="Der Status 'confirmed' sollte mit einer Primärquelle, einem amtlichen Register oder einer institutionellen Quelle abgesichert werden.", refs=[{"object_type": "assertion", "object_id": assertion["assertion_id"]}], details={"source_types": sorted({row["source_type"] for row in source_rows})}, actor="system-138"))
            # Same content/origin appearing as separate sources.
            groups = self.db.all("SELECT origin_fingerprint,COUNT(*) AS n,GROUP_CONCAT(source_id) AS ids FROM evidence_sources_138 WHERE case_id=? GROUP BY origin_fingerprint HAVING COUNT(*)>1", (case_id,))
            for group in groups:
                ids = [item for item in str(group["ids"] or "").split(",") if item]
                warning_ids.append(self._new_warning(case_id=case_id, warning_type="duplicate_origin", severity="medium", title="Mehrere Quellen verweisen auf denselben Ursprung", summary="Kopierte oder gespiegelt veröffentlichte Inhalte dürfen nicht als unabhängige Bestätigung gezählt werden.", refs=[{"object_type": "source", "object_id": source_id} for source_id in ids], details={"origin_fingerprint": group["origin_fingerprint"], "count": group["n"]}, actor="system-138"))
            # Circular parent-source chains.
            source_edges = [(row["source_id"], row["parent_source_id"]) for row in self.db.all("SELECT source_id,parent_source_id FROM evidence_sources_138 WHERE case_id=? AND parent_source_id IS NOT NULL", (case_id,))]
            for cycle in self._find_directed_cycles(source_edges):
                warning_ids.append(self._new_warning(case_id=case_id, warning_type="circular_evidence", severity="high", title="Zirkuläre Quellenkette erkannt", summary="Quellen verweisen in einem Kreis aufeinander und liefern dadurch keine unabhängige Ursprungsevidenz.", refs=[{"object_type": "source", "object_id": item} for item in cycle[:-1]], details={"cycle": cycle}, actor="system-138"))
            # General provenance cycles.
            prov_rows = self.db.all("SELECT * FROM evidence_provenance_edges_138 WHERE case_id=?", (case_id,))
            prov_edges = [(f"{r['from_object_type']}:{r['from_object_id']}", f"{r['to_object_type']}:{r['to_object_id']}") for r in prov_rows]
            for cycle in self._find_directed_cycles(prov_edges):
                warning_ids.append(self._new_warning(case_id=case_id, warning_type="provenance_cycle", severity="high", title="Zirkuläre Provenienz erkannt", summary="Die Ableitungskette eines Objekts führt auf sich selbst zurück.", refs=[{"object_type": "provenance_object", "object_id": item} for item in cycle[:-1]], details={"cycle": cycle}, actor="system-138"))
            # Conflicting exclusive assertions.
            by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
            for row in assertions:
                if row["predicate"] in EXCLUSIVE_PREDICATES and row["epistemic_state"] not in {"refuted"}:
                    by_key[(row["subject_node_id"], row["predicate"])].append(row)
            for (_subject, predicate), rows in by_key.items():
                for i, left in enumerate(rows):
                    for right in rows[i + 1:]:
                        if left["object_node_id"] != right["object_node_id"] and _periods_overlap(left["valid_from"], left["valid_to"], right["valid_from"], right["valid_to"]):
                            warning_ids.append(self._new_warning(case_id=case_id, warning_type="temporal_conflict", severity="high", title=f"Zeitlicher Konflikt bei {predicate}", summary="Zwei ausschließliche Angaben gelten im selben Zeitraum für unterschiedliche Werte.", refs=[{"object_type": "assertion", "object_id": left["assertion_id"]}, {"object_type": "assertion", "object_id": right["assertion_id"]}], details={"predicate": predicate}, actor="system-138"))
            # Photo result without image reference or local evidence.
            for result in self.db.all("SELECT * FROM photo_research_results_138 WHERE case_id=?", (case_id,)):
                if not result.get("image_url") and not result.get("local_result_asset_id") and result.get("result_kind") != "context_only":
                    warning_ids.append(self._new_warning(case_id=case_id, warning_type="photo_provenance_gap", severity="medium", title="Fototreffer ohne Bildreferenz", summary="Der Treffer besitzt weder eine gespeicherte Bildadresse noch ein lokal gesichertes Ergebnisbild.", refs=[{"object_type": "photo_result", "object_id": result["result_id"]}], details={"page_url": result["page_url"]}, actor="system-138"))
        self._event(case_id=case_id, event_type="integrity_analysis_completed", object_type="case", object_id=case_id, actor=actor, payload={"warning_count": len(warning_ids)})
        return {"case_id": case_id, "warning_count": len(warning_ids), "warnings": self.db.all("SELECT * FROM evidence_warnings_138 WHERE case_id=? AND status='open' ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,created_at DESC", (case_id,))}

    def update_warning(self, *, case_id: str, warning_id: str, status: str, actor: str) -> dict[str, Any]:
        if status not in WARNING_STATUSES:
            raise ValueError("Ungültiger Warnungsstatus")
        row = self.db.one("SELECT * FROM evidence_warnings_138 WHERE case_id=? AND warning_id=?", (case_id, warning_id))
        if not row:
            raise KeyError("Warnung nicht gefunden")
        self.db.execute("UPDATE evidence_warnings_138 SET status=?,updated_at=? WHERE warning_id=? AND case_id=?", (status, now_ts(), warning_id, case_id))
        self._event(case_id=case_id, event_type="evidence_warning_updated", object_type="evidence_warning_138", object_id=warning_id, actor=actor, payload={"status": status})
        return self.db.one("SELECT * FROM evidence_warnings_138 WHERE warning_id=?", (warning_id,)) or {}

    # ---------- expanded photo research variants ----------
    def _open_photo(self, *, case_id: str, asset_id: str) -> tuple[dict[str, Any], Path, Image.Image]:
        row, path = self.build136.photo_path(case_id=case_id, asset_id=asset_id)
        try:
            image = Image.open(path)
            image.verify()
            image = Image.open(path)
            image.load()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValueError(f"Bild konnte nicht sicher geöffnet werden: {exc}") from exc
        return row, path, image

    @staticmethod
    def _to_rgb(image: Image.Image) -> Image.Image:
        if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, (255, 255, 255))
            background.paste(rgba, mask=rgba.getchannel("A"))
            rgba.close()
            return background
        return image.convert("RGB") if image.mode != "RGB" else image.copy()

    @staticmethod
    def _quality_profile(image: Image.Image) -> dict[str, Any]:
        gray = image.convert("L")
        stat = ImageStat.Stat(gray)
        brightness = float(stat.mean[0])
        contrast = float(stat.stddev[0])
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_strength = float(ImageStat.Stat(edges).mean[0])
        entropy = float(gray.entropy())
        gray.close(); edges.close()
        return {
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
            "edge_strength": round(edge_strength, 2),
            "entropy": round(entropy, 3),
            "search_readiness": "good" if 35 <= brightness <= 220 and contrast >= 25 and edge_strength >= 8 else "limited",
        }

    def create_photo_variant(
        self,
        *,
        case_id: str,
        asset_id: str,
        variant_mode: str,
        label: str,
        parameters: Mapping[str, Any] | None,
        max_dimension: int,
        quality: int,
        actor: str,
    ) -> dict[str, Any]:
        if variant_mode not in PHOTO_VARIANT_MODES:
            raise ValueError("Unbekannter Foto-Variantenmodus")
        row, _path, source = self._open_photo(case_id=case_id, asset_id=asset_id)
        params = dict(parameters or {})
        max_dimension = max(VARIANT_MIN_DIMENSION, min(int(max_dimension or 1600), VARIANT_MAX_DIMENSION))
        quality = max(60, min(int(quality or 88), 95))
        working: Image.Image | None = None
        try:
            transposed = ImageOps.exif_transpose(source)
            working = transposed.copy() if transposed is source else transposed
            if variant_mode == "manual_crop":
                width, height = working.size
                left = int(params.get("left") or 0); top = int(params.get("top") or 0)
                right = int(params.get("right") or width); bottom = int(params.get("bottom") or height)
                if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                    raise ValueError("Ungültiger manueller Bildausschnitt")
                cropped = working.crop((left, top, right, bottom)); working.close(); working = cropped
                params = {"left": left, "top": top, "right": right, "bottom": bottom}
            elif variant_mode == "center_square":
                width, height = working.size
                side = min(width, height); left = (width - side) // 2; top = (height - side) // 2
                cropped = working.crop((left, top, left + side, top + side)); working.close(); working = cropped
                params = {"left": left, "top": top, "right": left + side, "bottom": top + side}
            elif variant_mode == "grayscale":
                converted = working.convert("L").convert("RGB"); working.close(); working = converted
                params = {"grayscale": True}
            elif variant_mode == "contrast":
                factor = max(0.5, min(float(params.get("factor") or 1.35), 2.5))
                enhanced = ImageEnhance.Contrast(self._to_rgb(working)).enhance(factor); working.close(); working = enhanced
                params = {"contrast_factor": factor}
            elif variant_mode == "detail_enhance":
                radius = max(0.5, min(float(params.get("radius") or 1.2), 3.0))
                percent = max(50, min(int(params.get("percent") or 130), 250))
                sharpened = self._to_rgb(working).filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=3)); working.close(); working = sharpened
                params = {"unsharp_radius": radius, "unsharp_percent": percent}
            else:
                params = {"clean_full": True}
            working.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            rgb = self._to_rgb(working); working.close(); working = rgb
            profile = self._quality_profile(working)
            buffer = io.BytesIO()
            working.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
            data = buffer.getvalue()
            if len(data) > VARIANT_MAX_BYTES:
                raise ValueError("Fotorecherche-Variante überschreitet 8 MB")
            digest = hashlib.sha256(data).hexdigest()
            existing = self.db.one("SELECT * FROM photo_variants_138 WHERE case_id=? AND parent_asset_id=? AND sha256=?", (case_id, asset_id, digest))
            if existing:
                existing["parameters"] = loads(existing.pop("parameters_json", "{}"), {})
                existing["download_url"] = f"/api/photo138/variant/{existing['variant_id']}?case_id={case_id}"
                return {**existing, "duplicate": True}
            variant_id = new_id("pvar138")
            case_root = (self.photo_root / case_id).resolve()
            variant_dir = (case_root / "research_138").resolve()
            if case_root.parent != self.photo_root or case_root not in variant_dir.parents:
                raise PermissionError("Ungültiger fallgebundener Variantenpfad")
            variant_dir.mkdir(parents=True, exist_ok=True)
            try:
                variant_dir.chmod(0o700)
            except OSError:
                pass
            filename = f"{_slug(label or row.get('title') or row.get('original_filename') or variant_mode)}_{variant_id}.jpg"
            final_path = variant_dir / filename
            temp_path = variant_dir / f".{variant_id}.tmp"
            temp_path.write_bytes(data)
            try:
                temp_path.chmod(0o600)
            except OSError:
                pass
            os.replace(temp_path, final_path)
            try:
                final_path.chmod(0o600)
            except OSError:
                pass
            parameter_record = {**params, "mode": variant_mode, "max_dimension": max_dimension, "quality": quality, "metadata_removed": True, "quality_profile": profile, "identity_claim": False}
            self.db.execute(
                "INSERT INTO photo_variants_138(variant_id,case_id,target_id,parent_asset_id,variant_mode,label,parameters_json,storage_relpath,filename,mime_type,byte_size,width_px,height_px,sha256,ahash64,dhash64,metadata_removed,status,expires_at,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,'image/jpeg',?,?,?,?,?,?,1,'ready',?,?,?)",
                (variant_id, case_id, row.get("target_id"), asset_id, variant_mode, _safe_text(label or variant_mode, 500), dumps(parameter_record), final_path.relative_to(self.base_dir).as_posix(), filename, len(data), working.width, working.height, digest, _average_hash(working), _difference_hash(working), _utc_after(24), _safe_text(actor, 120), now_ts()),
            )
            self.add_provenance(case_id=case_id, from_object_type="photo_asset_136", from_object_id=asset_id, relation_type="derived_variant", to_object_type="photo_variant_138", to_object_id=variant_id, actor=actor, details=parameter_record)
            self._event(case_id=case_id, event_type="photo_variant_created", object_type="photo_variant_138", object_id=variant_id, actor=actor, payload={"mode": variant_mode, "metadata_removed": True, "identity_claim": False})
            result = self.db.one("SELECT * FROM photo_variants_138 WHERE variant_id=?", (variant_id,)) or {}
            result["parameters"] = loads(result.pop("parameters_json", "{}"), {})
            result["download_url"] = f"/api/photo138/variant/{variant_id}?case_id={case_id}"
            return {**result, "duplicate": False}
        finally:
            if working is not None:
                try: working.close()
                except Exception: pass
            source.close()

    def variant_path(self, *, case_id: str, variant_id: str) -> tuple[dict[str, Any], Path]:
        row = self.db.one("SELECT * FROM photo_variants_138 WHERE case_id=? AND variant_id=?", (case_id, variant_id))
        if not row:
            raise KeyError("Fotorecherche-Variante nicht gefunden")
        if row["status"] != "ready":
            raise FileNotFoundError("Fotorecherche-Variante ist nicht verfügbar")
        candidate = (self.base_dir / row["storage_relpath"]).resolve()
        case_root = (self.photo_root / case_id).resolve()
        if case_root.parent != self.photo_root or case_root not in candidate.parents:
            raise PermissionError("Ungültiger Variantenpfad")
        if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
            raise FileNotFoundError("Fotorecherche-Variante fehlt")
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != row["sha256"]:
            raise PermissionError("Integritätsprüfung der Fotorecherche-Variante fehlgeschlagen")
        return row, candidate

    def cleanup_expired_variants(self, *, actor: str = "local-analyst") -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        removed: list[str] = []
        failed: list[dict[str, str]] = []
        for row in self.db.all("SELECT * FROM photo_variants_138 WHERE status='ready' AND expires_at!=''"):
            try:
                expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
            except ValueError:
                continue
            if expires > now:
                continue
            active = int((self.db.one("SELECT COUNT(*) AS n FROM photo_search_runs_138 WHERE variant_id=? AND status NOT IN ('completed','cancelled')", (row["variant_id"],)) or {}).get("n") or 0)
            if active:
                continue
            try:
                _record, path = self.variant_path(case_id=row["case_id"], variant_id=row["variant_id"])
                path.unlink(missing_ok=True)
                self.db.execute("UPDATE photo_variants_138 SET status='expired_removed' WHERE variant_id=?", (row["variant_id"],))
                removed.append(row["variant_id"])
            except FileNotFoundError:
                self.db.execute("UPDATE photo_variants_138 SET status='expired_removed' WHERE variant_id=?", (row["variant_id"],))
                removed.append(row["variant_id"])
            except Exception as exc:
                failed.append({"variant_id": row["variant_id"], "error": _safe_text(exc, 500)})
        if removed or failed:
            self.audit.log("cleanup", "photo_variant_138", "expired", None, {"removed": removed, "failed": failed, "actor": actor})
        return {"removed": removed, "failed": failed}

    # ---------- controlled reverse-image sweeps and result capture ----------
    def create_photo_search_runs(
        self,
        *,
        case_id: str,
        source_type: str,
        source_id: str,
        provider_keys: Iterable[str],
        purpose: str,
        confirmation: str,
        actor: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        if confirmation.strip() != "FOTORECHERCHE-SERIE FREIGEBEN":
            raise PermissionError("Freigabephrase FOTORECHERCHE-SERIE FREIGEBEN erforderlich")
        providers = []
        for key in provider_keys:
            clean = str(key or "").strip()
            if clean and clean not in providers:
                providers.append(clean)
        if not providers or len(providers) > 4 or any(key not in PHOTO_PROVIDERS for key in providers):
            raise ValueError("Ein bis vier bekannte Bildsuchanbieter auswählen")
        purpose = _safe_text(purpose, 1500)
        if len(purpose) < 8:
            raise ValueError("Dokumentierter Recherche-Zweck ist zu kurz")
        if source_type == "variant":
            source_row, _path = self.variant_path(case_id=case_id, variant_id=source_id)
            variant_id, copy_id = source_id, None
            parent_asset_id = source_row["parent_asset_id"]
            target_id = source_row.get("target_id")
            disclosure = {"filename": source_row["filename"], "sha256": source_row["sha256"], "metadata_removed": True, "variant_mode": source_row["variant_mode"], "automatic_upload": False, "original_not_disclosed": True}
        elif source_type == "copy137":
            source_row, _path = self.build137.copy_path(case_id=case_id, copy_id=source_id)
            variant_id, copy_id = None, source_id
            parent_asset_id = source_row["parent_asset_id"]
            target_id = source_row.get("target_id")
            disclosure = {"filename": source_row["filename"], "sha256": source_row["sha256"], "metadata_removed": True, "variant_mode": "build137_copy", "automatic_upload": False, "original_not_disclosed": True}
        else:
            raise ValueError("Recherchequelle muss eine Build-138-Variante oder Build-137-Kopie sein")
        runs: list[dict[str, Any]] = []
        now = now_ts()
        with self.db.transaction(immediate=True):
            for provider_key in providers:
                provider = PHOTO_PROVIDERS[provider_key]
                task_id = new_id("task")
                run_id = new_id("prun138")
                self.db.execute(
                    "INSERT INTO search_tasks(task_id,case_id,target_id,category,query,engine,url,status,created_at) VALUES(?,?,?,?,?,?,?,'planned',?)",
                    (task_id, case_id, target_id, "photo_reverse_search_138", f"Reverse image research 138: {disclosure['filename']}", provider["label"], provider["url"], now),
                )
                self.db.execute(
                    "INSERT INTO photo_search_runs_138(run_id,case_id,target_id,parent_asset_id,variant_id,copy_id,provider_key,provider_label,provider_url,purpose,status,search_task_id,manual_upload_required,external_upload_performed,result_note,disclosure_json,approved_by,approved_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,'prepared',?,1,0,'',?,?,?,?)",
                    (run_id, case_id, target_id, parent_asset_id, variant_id, copy_id, provider_key, provider["label"], provider["url"], purpose, task_id, dumps(disclosure), _safe_text(actor, 120), now, now),
                )
                runs.append(self.photo_search_run(case_id=case_id, run_id=run_id))
        for run in runs:
            src_type = "photo_variant_138" if variant_id else "photo_research_copy_137"
            self.add_provenance(case_id=case_id, from_object_type=src_type, from_object_id=source_id, relation_type="searched_with", to_object_type="photo_search_run_138", to_object_id=run["run_id"], actor=actor, details={"provider": run["provider_key"], "automatic_upload": False})
        self._event(case_id=case_id, event_type="photo_provider_sweep_prepared", object_type="photo_search_run_138", object_id=runs[0]["run_id"], actor=actor, payload={"run_ids": [row["run_id"] for row in runs], "provider_count": len(runs), "automatic_uploads": 0})
        return {"runs": runs, "run_count": len(runs), "automatic_uploads": 0, "identity_claims": 0}

    def photo_search_run(self, *, case_id: str, run_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM photo_search_runs_138 WHERE case_id=? AND run_id=?", (case_id, run_id))
        if not row:
            raise KeyError("Fotorecherche-Lauf nicht gefunden")
        row["disclosure"] = loads(row.pop("disclosure_json", "{}"), {})
        if row.get("variant_id"):
            row["download_url"] = f"/api/photo138/variant/{row['variant_id']}?case_id={case_id}"
        else:
            row["download_url"] = f"/api/photo137/copy/{row['copy_id']}?case_id={case_id}"
        return row

    def launch_photo_search_run(self, *, case_id: str, run_id: str, actor: str, local_redirect_origin: str) -> dict[str, Any]:
        row = self.photo_search_run(case_id=case_id, run_id=run_id)
        result = self.build136.launch_research_task(case_id=case_id, task_id=row["search_task_id"], actor=actor, local_redirect_origin=local_redirect_origin)
        self.db.execute("UPDATE photo_search_runs_138 SET status='provider_opened',updated_at=? WHERE case_id=? AND run_id=?", (now_ts(), case_id, run_id))
        self._event(case_id=case_id, event_type="photo_provider_opened_138", object_type="photo_search_run_138", object_id=run_id, actor=actor, payload={"provider": row["provider_key"], "manual_upload_required": True, "automatic_upload": False})
        result.update({"run_id": run_id, "download_url": row["download_url"], "manual_upload_required": True, "automatic_upload": False})
        return result

    def update_photo_search_run(self, *, case_id: str, run_id: str, status: str, result_note: str, actor: str) -> dict[str, Any]:
        if status not in PHOTO_RUN_STATUSES:
            raise ValueError("Ungültiger Fotorecherche-Status")
        row = self.photo_search_run(case_id=case_id, run_id=run_id)
        external = 1 if status in {"uploaded_manually", "results_review", "completed"} else int(row.get("external_upload_performed") or 0)
        self.db.execute("UPDATE photo_search_runs_138 SET status=?,external_upload_performed=?,result_note=?,updated_at=? WHERE case_id=? AND run_id=?", (status, external, _safe_text(result_note, 4000), now_ts(), case_id, run_id))
        self._event(case_id=case_id, event_type="photo_search_run_updated", object_type="photo_search_run_138", object_id=run_id, actor=actor, payload={"status": status, "external_upload_performed": bool(external)})
        return self.photo_search_run(case_id=case_id, run_id=run_id)

    def record_photo_result(
        self,
        *,
        case_id: str,
        research_run_type: str,
        research_run_id: str,
        page_url: str,
        image_url: str,
        page_title: str,
        result_kind: str,
        local_result_asset_id: str,
        notes: str,
        actor: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        if result_kind not in PHOTO_RESULT_KINDS:
            raise ValueError("Ungültige Fototreffer-Kategorie")
        if research_run_type == "build138":
            run = self.photo_search_run(case_id=case_id, run_id=research_run_id)
        elif research_run_type == "build137":
            run = self.build137.photo_job(case_id=case_id, job_id=research_run_id)
        else:
            raise ValueError("Unbekannter Fotorecherche-Lauftyp")
        page = self.canonical_url(page_url)
        image = self.canonical_url(image_url, allow_empty=True)
        local_asset = None
        if local_result_asset_id:
            local_asset = self.db.one("SELECT * FROM photo_assets_136 WHERE case_id=? AND asset_id=?", (case_id, local_result_asset_id))
            if not local_asset:
                raise KeyError("Lokales Ergebnisbild gehört nicht zu diesem Fall")
        source = self.register_source(case_id=case_id, title=page_title or page, canonical_url=page, source_type="unknown", independence_group=urlsplit(page).hostname or "photo-result", actor=actor, metadata={"photo_result": True, "provider": run.get("provider_key")})
        existing = self.db.one("SELECT * FROM photo_research_results_138 WHERE research_run_type=? AND research_run_id=? AND page_url=? AND image_url=?", (research_run_type, research_run_id, page, image))
        if existing:
            return {**existing, "duplicate": True, "comparison": self.db.one("SELECT * FROM photo_comparisons_138 WHERE result_id=?", (existing["result_id"],))}
        result_id = new_id("presult138")
        now = now_ts()
        target_id = run.get("target_id")
        parent_asset_id = run["parent_asset_id"]
        self.db.execute(
            "INSERT INTO photo_research_results_138(result_id,case_id,target_id,research_run_type,research_run_id,parent_asset_id,source_id,page_url,image_url,page_title,observed_at,result_kind,review_status,local_result_asset_id,notes,candidate_only,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'candidate',?,?,1,?,?,?)",
            (result_id, case_id, target_id, research_run_type, research_run_id, parent_asset_id, source["source_id"], page, image, _safe_text(page_title, 1000), now, result_kind, local_result_asset_id or None, _safe_text(notes, 4000), _safe_text(actor, 120), now, now),
        )
        self.add_provenance(case_id=case_id, from_object_type=research_run_type, from_object_id=research_run_id, relation_type="returned_hit", to_object_type="photo_result_138", to_object_id=result_id, actor=actor, details={"source_id": source["source_id"], "result_kind": result_kind})
        if local_result_asset_id:
            self.add_provenance(case_id=case_id, from_object_type="photo_result_138", from_object_id=result_id, relation_type="captured_as", to_object_type="photo_asset_136", to_object_id=local_result_asset_id, actor=actor, details={"identity_claim": False})
            comparison = self.compare_photo_result(case_id=case_id, result_id=result_id, actor=actor)
        else:
            comparison = None
        self._event(case_id=case_id, event_type="photo_result_recorded", object_type="photo_result_138", object_id=result_id, actor=actor, payload={"result_kind": result_kind, "local_result_asset": bool(local_result_asset_id), "identity_claim": False})
        row = self.db.one("SELECT * FROM photo_research_results_138 WHERE result_id=?", (result_id,)) or {}
        return {**row, "duplicate": False, "comparison": comparison}

    def compare_photo_result(self, *, case_id: str, result_id: str, actor: str) -> dict[str, Any]:
        result = self.db.one("SELECT * FROM photo_research_results_138 WHERE case_id=? AND result_id=?", (case_id, result_id))
        if not result:
            raise KeyError("Fototreffer nicht gefunden")
        compared_asset = result.get("local_result_asset_id")
        if not compared_asset:
            raise ValueError("Für einen lokalen Bildvergleich muss das Ergebnisbild in der Fotoakte liegen")
        reference_asset = result["parent_asset_id"]
        ref = self.build137.analyze_photo(case_id=case_id, asset_id=reference_asset, actor=actor)
        cmp = self.build137.analyze_photo(case_id=case_id, asset_id=compared_asset, actor=actor)
        ref_row = self.db.one("SELECT * FROM photo_assets_136 WHERE case_id=? AND asset_id=?", (case_id, reference_asset)) or {}
        cmp_row = self.db.one("SELECT * FROM photo_assets_136 WHERE case_id=? AND asset_id=?", (case_id, compared_asset)) or {}
        exact = int(bool(ref_row.get("sha256") and ref_row.get("sha256") == cmp_row.get("sha256")))
        ad = _hamming_hex(ref["fingerprint"]["ahash64"], cmp["fingerprint"]["ahash64"])
        dd = _hamming_hex(ref["fingerprint"]["dhash64"], cmp["fingerprint"]["dhash64"])
        if exact:
            band = "exact_file"
        elif ad <= 4 and dd <= 6:
            band = "near_duplicate_image"
        elif ad <= 10 and dd <= 12:
            band = "edited_or_cropped_candidate"
        elif ad <= 18 and dd <= 20:
            band = "weak_visual_similarity"
        else:
            band = "different_image"
        now = now_ts()
        existing = self.db.one("SELECT * FROM photo_comparisons_138 WHERE result_id=? AND reference_asset_id=? AND compared_asset_id=?", (result_id, reference_asset, compared_asset))
        comparison_id = existing["comparison_id"] if existing else new_id("pcmp138")
        if existing:
            self.db.execute("UPDATE photo_comparisons_138 SET exact_sha256=?,ahash_distance=?,dhash_distance=?,image_relation_band=?,identity_claim=0,updated_at=? WHERE comparison_id=?", (exact, ad, dd, band, now, comparison_id))
        else:
            self.db.execute(
                "INSERT INTO photo_comparisons_138(comparison_id,case_id,result_id,reference_asset_id,compared_asset_id,exact_sha256,ahash_distance,dhash_distance,image_relation_band,identity_claim,manual_observations_json,review_status,review_note,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,0,'{}','candidate','',?,?,?)",
                (comparison_id, case_id, result_id, reference_asset, compared_asset, exact, ad, dd, band, _safe_text(actor, 120), now, now),
            )
        self._event(case_id=case_id, event_type="photo_files_compared", object_type="photo_comparison_138", object_id=comparison_id, actor=actor, payload={"image_relation_band": band, "ahash_distance": ad, "dhash_distance": dd, "identity_claim": False})
        return self.db.one("SELECT * FROM photo_comparisons_138 WHERE comparison_id=?", (comparison_id,)) or {}

    def review_photo_result(self, *, case_id: str, result_id: str, review_status: str, result_kind: str, notes: str, actor: str) -> dict[str, Any]:
        if review_status not in PHOTO_REVIEW_STATES or result_kind not in PHOTO_RESULT_KINDS:
            raise ValueError("Ungültiger Fototreffer-Prüfstatus")
        row = self.db.one("SELECT * FROM photo_research_results_138 WHERE case_id=? AND result_id=?", (case_id, result_id))
        if not row:
            raise KeyError("Fototreffer nicht gefunden")
        self.db.execute("UPDATE photo_research_results_138 SET review_status=?,result_kind=?,notes=?,candidate_only=?,updated_at=? WHERE case_id=? AND result_id=?", (review_status, result_kind, _safe_text(notes, 4000), 1, now_ts(), case_id, result_id))
        self._event(case_id=case_id, event_type="photo_result_reviewed", object_type="photo_result_138", object_id=result_id, actor=actor, payload={"review_status": review_status, "result_kind": result_kind, "identity_claim": False})
        return self.db.one("SELECT * FROM photo_research_results_138 WHERE result_id=?", (result_id,)) or {}

    def build_photo_clusters(self, *, case_id: str, actor: str, ahash_threshold: int = 8, dhash_threshold: int = 10) -> dict[str, Any]:
        self._case(case_id)
        ahash_threshold = max(0, min(int(ahash_threshold), 20))
        dhash_threshold = max(0, min(int(dhash_threshold), 24))
        fingerprints = self.db.all("SELECT * FROM photo_fingerprints_137 WHERE case_id=? AND algorithm_version=?", (case_id, IMAGE_HASH_VERSION))
        parent = {row["asset_id"]: row["asset_id"] for row in fingerprints}

        def find(value: str) -> str:
            while parent[value] != value:
                parent[value] = parent[parent[value]]
                value = parent[value]
            return value

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for i, left in enumerate(fingerprints):
            for right in fingerprints[i + 1:]:
                if _hamming_hex(left["ahash64"], right["ahash64"]) <= ahash_threshold and _hamming_hex(left["dhash64"], right["dhash64"]) <= dhash_threshold:
                    union(left["asset_id"], right["asset_id"])
        groups: dict[str, list[str]] = defaultdict(list)
        for asset_id in parent:
            groups[find(asset_id)].append(asset_id)
        groups = {key: value for key, value in groups.items() if len(value) >= 2}
        with self.db.transaction(immediate=True):
            old = [row["cluster_id"] for row in self.db.all("SELECT cluster_id FROM photo_clusters_138 WHERE case_id=?", (case_id,))]
            for cluster_id in old:
                self.db.execute("DELETE FROM photo_clusters_138 WHERE cluster_id=?", (cluster_id,))
            created: list[dict[str, Any]] = []
            for idx, members in enumerate(sorted(groups.values(), key=lambda values: (-len(values), values[0])), 1):
                cluster_id = new_id("pcluster138")
                self.db.execute("INSERT INTO photo_clusters_138(cluster_id,case_id,label,algorithm_version,threshold_json,candidate_only,created_by,created_at) VALUES(?,?,?,?,?,1,?,?)", (cluster_id, case_id, f"Bildähnlichkeitscluster {idx}", IMAGE_HASH_VERSION, dumps({"ahash": ahash_threshold, "dhash": dhash_threshold}), _safe_text(actor, 120), now_ts()))
                for pos, asset_id in enumerate(sorted(members)):
                    self.db.execute("INSERT INTO photo_cluster_members_138(member_id,cluster_id,case_id,asset_id,role,created_at) VALUES(?,?,?,?,?,?)", (new_id("pcm138"), cluster_id, case_id, asset_id, "reference" if pos == 0 else "member", now_ts()))
                created.append({"cluster_id": cluster_id, "member_count": len(members), "asset_ids": sorted(members)})
        self._event(case_id=case_id, event_type="photo_clusters_rebuilt", object_type="case", object_id=case_id, actor=actor, payload={"cluster_count": len(created), "identity_claims": 0})
        return {"cluster_count": len(created), "clusters": created, "candidate_only": True, "identity_claims": 0}

    # ---------- dashboards ----------
    def evidence_dashboard(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        nodes = self.db.all("SELECT * FROM evidence_nodes_138 WHERE case_id=? ORDER BY updated_at DESC LIMIT 300", (case_id,))
        for row in nodes:
            row["attributes"] = loads(row.pop("attributes_json", "{}"), {})
        assertions = self.db.all("SELECT a.*,s.label AS subject_label,o.label AS object_label FROM evidence_assertions_138 a JOIN evidence_nodes_138 s ON s.node_id=a.subject_node_id JOIN evidence_nodes_138 o ON o.node_id=a.object_node_id WHERE a.case_id=? ORDER BY a.updated_at DESC LIMIT 300", (case_id,))
        sources = self.db.all("SELECT * FROM evidence_sources_138 WHERE case_id=? ORDER BY retrieved_at DESC LIMIT 300", (case_id,))
        warnings = self.db.all("SELECT * FROM evidence_warnings_138 WHERE case_id=? ORDER BY updated_at DESC LIMIT 200", (case_id,))
        provenance = self.db.all("SELECT * FROM evidence_provenance_edges_138 WHERE case_id=? ORDER BY created_at DESC LIMIT 300", (case_id,))
        return {
            "nodes": nodes,
            "assertions": assertions,
            "sources": sources,
            "warnings": warnings,
            "provenance": provenance,
            "node_count": len(nodes),
            "assertion_count": len(assertions),
            "source_count": len(sources),
            "open_warning_count": sum(1 for row in warnings if row["status"] == "open"),
            "confirmed_assertion_count": sum(1 for row in assertions if row["epistemic_state"] == "confirmed"),
        }

    def photo_dashboard(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        variants = self.db.all("SELECT * FROM photo_variants_138 WHERE case_id=? ORDER BY created_at DESC LIMIT 300", (case_id,))
        for row in variants:
            row["parameters"] = loads(row.pop("parameters_json", "{}"), {})
            row["download_url"] = f"/api/photo138/variant/{row['variant_id']}?case_id={case_id}"
        runs = self.db.all("SELECT * FROM photo_search_runs_138 WHERE case_id=? ORDER BY updated_at DESC LIMIT 300", (case_id,))
        for row in runs:
            row["disclosure"] = loads(row.pop("disclosure_json", "{}"), {})
            row["download_url"] = f"/api/photo138/variant/{row['variant_id']}?case_id={case_id}" if row.get("variant_id") else f"/api/photo137/copy/{row['copy_id']}?case_id={case_id}"
        results = self.db.all("SELECT r.*,s.title AS source_title,s.source_type,s.independence_group FROM photo_research_results_138 r JOIN evidence_sources_138 s ON s.source_id=r.source_id WHERE r.case_id=? ORDER BY r.updated_at DESC LIMIT 300", (case_id,))
        for row in results:
            row["comparison"] = self.db.one("SELECT * FROM photo_comparisons_138 WHERE result_id=?", (row["result_id"],))
        clusters = self.db.all("SELECT c.*,COUNT(m.member_id) AS member_count FROM photo_clusters_138 c LEFT JOIN photo_cluster_members_138 m ON m.cluster_id=c.cluster_id WHERE c.case_id=? GROUP BY c.cluster_id ORDER BY member_count DESC,c.created_at DESC", (case_id,))
        return {
            "variants": variants,
            "runs": runs,
            "results": results,
            "clusters": clusters,
            "variant_count": len(variants),
            "run_count": len(runs),
            "result_count": len(results),
            "cluster_count": len(clusters),
            "open_run_count": sum(1 for row in runs if row["status"] not in {"completed", "cancelled"}),
            "automatic_uploads": 0,
            "identity_claims": 0,
            "face_recognition": False,
        }

    def dashboard(self, case_id: str = "") -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "evidence": self.evidence_dashboard(case_id) if case_id else {
                "node_count": int((self.db.one("SELECT COUNT(*) AS n FROM evidence_nodes_138") or {}).get("n") or 0),
                "assertion_count": int((self.db.one("SELECT COUNT(*) AS n FROM evidence_assertions_138") or {}).get("n") or 0),
                "source_count": int((self.db.one("SELECT COUNT(*) AS n FROM evidence_sources_138") or {}).get("n") or 0),
            },
            "photos": self.photo_dashboard(case_id) if case_id else {
                "variant_count": int((self.db.one("SELECT COUNT(*) AS n FROM photo_variants_138") or {}).get("n") or 0),
                "result_count": int((self.db.one("SELECT COUNT(*) AS n FROM photo_research_results_138") or {}).get("n") or 0),
            },
            "safety": {
                "automatic_identity_claims": 0,
                "automatic_image_uploads": 0,
                "face_recognition": False,
                "manual_review_required": True,
                "candidate_only_photo_links": True,
            },
        }
