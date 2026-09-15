from __future__ import annotations

import hashlib
import html
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(v: Any) -> str:
    if isinstance(v, bytes):
        return hashlib.sha256(v).hexdigest()
    return hashlib.sha256(_canon(v).encode("utf-8")).hexdigest()


def _loads(v: str | None, default: Any) -> Any:
    try:
        return json.loads(v) if v else default
    except Exception:
        return default


def _text(v: Any, n: int = 20000) -> str:
    return str(v or "").replace("\x00", "").strip()[:n]


def _clamp(v: Any) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except Exception:
        return 0.0


class Build239EvidenceVaultProvenanceService:
    """Content-addressed, case-local evidence vault with explicit provenance.

    Build 239 performs no network acquisition. It stores bytes/text supplied by a
    controlled capture/import path, records immutable provenance, supports derived
    evidence without overwriting originals, detects source changes across captures,
    and stages only independently reviewed evidence decisions for Build-228 training.
    """

    BUILD = "239.0"
    REVIEW_DECISIONS = {"accepted", "rejected", "needs_context"}
    DERIVATIONS = {"text_extract", "translation", "summary", "redaction", "transcode", "manual_annotation", "other"}

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        kernel: Any,
        source_fabric: Any,
        training: Any,
        conversation: Any,
        base_dir: str | Path,
        actor: str = "local-analyst",
    ) -> None:
        self.db, self.audit, self.kernel, self.source_fabric, self.training, self.conversation = db, audit, kernel, source_fabric, training, conversation
        self.actor = actor
        self.base_dir = Path(base_dir)
        self.vault_dir = self.base_dir / "evidence_vault_239"
        self.blob_dir = self.vault_dir / "sha256"
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        self.conversation._evidence_vault_239 = self

    # ------------------------------------------------------------------
    # Capture and storage
    # ------------------------------------------------------------------
    def capture_text(
        self,
        *,
        case_id: str,
        text: str,
        media_type: str = "text/plain; charset=utf-8",
        original_filename: str = "",
        source_key: str = "",
        source_url: str = "",
        captured_at: str = "",
        acquisition_method: str = "manual_capture",
        metadata: Mapping[str, Any] | None = None,
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        raw = str(text or "").encode("utf-8")
        return self.capture_bytes(case_id=case_id, content=raw, media_type=media_type, original_filename=original_filename,
                                  source_key=source_key, source_url=source_url, captured_at=captured_at,
                                  acquisition_method=acquisition_method, metadata=metadata, created_by=created_by,
                                  confirmation=confirmation)

    def capture_bytes(
        self,
        *,
        case_id: str,
        content: bytes,
        media_type: str,
        original_filename: str = "",
        source_key: str = "",
        source_url: str = "",
        captured_at: str = "",
        acquisition_method: str = "controlled_import",
        metadata: Mapping[str, Any] | None = None,
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        self.kernel.cases.get_case(case_id)
        if confirmation != f"EVIDENCE VAULT 239 {case_id} CAPTURE":
            raise PermissionError("explicit approval required")
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise ValueError("non-empty bytes required")
        raw = bytes(content)
        if len(raw) > 100 * 1024 * 1024:
            raise ValueError("single evidence item exceeds 100 MiB safety limit")
        skey = _text(source_key, 200)
        if skey:
            constraint = self.source_fabric.ranking_constraint(source_key=skey)
            if constraint.get("managed") and not constraint.get("eligible"):
                raise PermissionError("source is not governance/health eligible")
        url = _text(source_url, 4000)
        if url and urlparse(url).scheme not in {"http", "https", "file", "urn"}:
            raise ValueError("unsupported provenance URL scheme")
        method = _text(acquisition_method, 120).lower() or "controlled_import"
        digest = hashlib.sha256(raw).hexdigest()
        captured = _text(captured_at, 100) or now_ts()
        existing = self.db.one(
            "SELECT * FROM evidence_vault_items_239 WHERE case_id=? AND content_sha256=? AND source_key=? AND source_url=? AND acquisition_method=? AND captured_at=?",
            (case_id, digest, skey, url, method, captured),
        )
        if existing:
            return {**self._item_payload(existing), "idempotent": True}
        rel = self._blob_relpath(digest)
        self._write_blob(rel, raw, digest)
        vid, now = new_id("vault239"), now_ts()
        meta = dict(metadata or {})
        payload = {
            "vault_item_id": vid, "case_id": case_id, "content_sha256": digest, "media_type": _text(media_type, 300) or "application/octet-stream",
            "byte_size": len(raw), "storage_relpath": rel, "original_filename": Path(_text(original_filename, 500)).name,
            "source_key": skey, "source_url": url, "captured_at": captured, "acquisition_method": method,
            "capture_metadata": meta, "created_by": created_by, "created_at": now,
        }
        self.db.execute(
            "INSERT INTO evidence_vault_items_239 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (vid, case_id, digest, payload["media_type"], len(raw), rel, payload["original_filename"], skey, url, captured, method, dumps(meta), created_by, now, _hash(payload)),
        )
        self._event(case_id, "evidence_captured", "vault_item", vid, {"sha256": digest, "byte_size": len(raw), "source_key": skey, "network_by_build239": False}, created_by)
        change = {"origin_key": "", "change_kind": "derived_not_source_change"} if method.startswith("derived:") else self._detect_change_for_new_item(vid, actor=created_by)
        return {**payload, "review_status": "pending", "idempotent": False, "change_detection": change, "network_acquisition_by_build239": False}

    def create_derived(
        self,
        *,
        parent_vault_item_id: str,
        content: bytes | str,
        media_type: str,
        transformation_type: str,
        transformation_params: Mapping[str, Any] | None,
        original_filename: str,
        created_by: str,
        confirmation: str,
    ) -> dict[str, Any]:
        parent = self.item(parent_vault_item_id)
        if confirmation != f"EVIDENCE DERIVATION 239 {parent_vault_item_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        typ = _text(transformation_type, 80).lower()
        if typ not in self.DERIVATIONS:
            raise ValueError("unsupported derivation type")
        raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        child = self.capture_bytes(
            case_id=parent["case_id"], content=raw, media_type=media_type, original_filename=original_filename,
            source_key=parent["source_key"], source_url=parent["source_url"], captured_at=now_ts(),
            acquisition_method=f"derived:{typ}", metadata={"derived_from": parent_vault_item_id, "transformation": dict(transformation_params or {})},
            created_by=created_by, confirmation=f"EVIDENCE VAULT 239 {parent['case_id']} CAPTURE",
        )
        if child["vault_item_id"] == parent_vault_item_id:
            raise ValueError("derived evidence must not equal parent")
        existing = self.db.one("SELECT * FROM evidence_derivations_239 WHERE child_vault_item_id=?", (child["vault_item_id"],))
        if existing:
            return {"derivation": existing, "child": child, "idempotent": True}
        did, now = new_id("deriv239"), now_ts()
        params = dict(transformation_params or {})
        payload = {"derivation_id": did, "case_id": parent["case_id"], "parent_vault_item_id": parent_vault_item_id,
                   "child_vault_item_id": child["vault_item_id"], "transformation_type": typ, "transformation_params": params,
                   "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO evidence_derivations_239 VALUES(?,?,?,?,?,?,?,?,?)",
                        (did, parent["case_id"], parent_vault_item_id, child["vault_item_id"], typ, dumps(params), created_by, now, _hash(payload)))
        self._event(parent["case_id"], "evidence_derived", "vault_item", child["vault_item_id"], {"parent": parent_vault_item_id, "transformation_type": typ}, created_by)
        return {"derivation": payload, "child": child, "idempotent": False}

    # ------------------------------------------------------------------
    # Review, integrity, change detection
    # ------------------------------------------------------------------
    def review_item(self, *, vault_item_id: str, decision: str, evidence_quality: float, rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        item = self.item(vault_item_id)
        if confirmation != f"EVIDENCE REVIEW 239 {vault_item_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if reviewer == item["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in self.REVIEW_DECISIONS:
            raise ValueError("invalid review decision")
        note = _text(rationale, 6000)
        if len(note) < 15:
            raise ValueError("substantive rationale required")
        if self.db.one("SELECT review_id FROM evidence_reviews_239 WHERE vault_item_id=?", (vault_item_id,)):
            raise ValueError("evidence already reviewed")
        check = self.verify_item(vault_item_id=vault_item_id, checked_by=reviewer)
        if decision == "accepted" and check["status"] != "ok":
            raise PermissionError("integrity gate blocks evidence acceptance")
        rid, now = new_id("evreview239"), now_ts()
        payload = {"review_id": rid, "vault_item_id": vault_item_id, "case_id": item["case_id"], "decision": decision,
                   "evidence_quality": _clamp(evidence_quality), "rationale": note, "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO evidence_reviews_239 VALUES(?,?,?,?,?,?,?,?,?)",
                        (rid, vault_item_id, item["case_id"], decision, payload["evidence_quality"], note, reviewer, now, _hash(payload)))
        self._event(item["case_id"], "evidence_reviewed", "vault_item", vault_item_id, {"decision": decision, "quality": payload["evidence_quality"], "integrity": check["status"]}, reviewer)
        return payload

    def verify_item(self, *, vault_item_id: str, checked_by: str) -> dict[str, Any]:
        item = self.item(vault_item_id)
        path = self.base_dir / item["storage_relpath"]
        present = path.is_file()
        observed = hashlib.sha256(path.read_bytes()).hexdigest() if present else ""
        status = "ok" if present and observed == item["content_sha256"] else ("missing" if not present else "hash_mismatch")
        cid, now = new_id("integrity239"), now_ts()
        payload = {"integrity_check_id": cid, "case_id": item["case_id"], "vault_item_id": vault_item_id,
                   "expected_sha256": item["content_sha256"], "observed_sha256": observed, "status": status,
                   "file_present": present, "checked_by": checked_by, "checked_at": now}
        self.db.execute("INSERT INTO evidence_integrity_checks_239 VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (cid, item["case_id"], vault_item_id, item["content_sha256"], observed, status, 1 if present else 0, checked_by, now, _hash(payload)))
        self._event(item["case_id"], "evidence_integrity_checked", "vault_item", vault_item_id, {"status": status}, checked_by)
        return payload

    def case_integrity(self, *, case_id: str, checked_by: str, limit: int = 1000) -> dict[str, Any]:
        self.kernel.cases.get_case(case_id)
        rows = self.db.all("SELECT vault_item_id FROM evidence_vault_items_239 WHERE case_id=? ORDER BY created_at,vault_item_id LIMIT ?", (case_id, max(1, min(int(limit), 5000))))
        checks = [self.verify_item(vault_item_id=r["vault_item_id"], checked_by=checked_by) for r in rows]
        counts = {s: sum(1 for c in checks if c["status"] == s) for s in ("ok", "missing", "hash_mismatch")}
        return {"case_id": case_id, "checked": len(checks), "counts": counts, "passed": counts["missing"] == 0 and counts["hash_mismatch"] == 0}

    # ------------------------------------------------------------------
    # Canonical kernel and AI context
    # ------------------------------------------------------------------
    def bind_to_kernel(self, *, vault_item_id: str, title: str, statement: str, confidence: float, actor: str, confirmation: str) -> dict[str, Any]:
        item = self.item(vault_item_id)
        if confirmation != f"EVIDENCE KERNEL 239 {vault_item_id} BINDEN":
            raise PermissionError("explicit approval required")
        review = self.db.one("SELECT * FROM evidence_reviews_239 WHERE vault_item_id=?", (vault_item_id,))
        if not review or review["decision"] != "accepted":
            raise PermissionError("accepted independent evidence review required")
        integrity = self.verify_item(vault_item_id=vault_item_id, checked_by=actor)
        if integrity["status"] != "ok":
            raise PermissionError("integrity gate failed")
        existing = self.db.one("SELECT * FROM evidence_kernel_bindings_239 WHERE vault_item_id=?", (vault_item_id,))
        if existing:
            return {**existing, "idempotent": True}
        if item["source_key"]:
            source_binding = self.source_fabric.bind_source_to_case(case_id=item["case_id"], source_key=item["source_key"], actor=actor,
                                                                    confirmation=f"SOURCE FABRIC BIND 236 {item['case_id']} {item['source_key']}")
            source_id = source_binding["canonical_source_object_id"]
        else:
            source_obj = self.kernel.create_source(case_id=item["case_id"], label=item["source_url"] or item["original_filename"] or "Vault source",
                                                   url=item["source_url"], source_class="evidence_vault_239", actor=actor,
                                                   confirmation=f"KERNEL OBJECT 235 {item['case_id']} ANLEGEN")
            source_id = source_obj["object_id"]
        evidence = self.kernel.create_object(
            case_id=item["case_id"], object_type="evidence", subtype="vault_item_239", label=_text(title, 1200),
            canonical_key=_hash({"vault_item_id": vault_item_id, "content_sha256": item["content_sha256"]}), state="reviewed",
            confidence=_clamp(confidence), payload={"statement": _text(statement, 20000), "vault_item_id": vault_item_id, "content_sha256": item["content_sha256"]},
            provenance={"origin": "build239_evidence_vault", "vault_item_id": vault_item_id, "sha256": item["content_sha256"], "captured_at": item["captured_at"]},
            actor=actor, confirmation=f"KERNEL OBJECT 235 {item['case_id']} ANLEGEN",
        )
        self.kernel.create_link(case_id=item["case_id"], source_object_id=evidence["object_id"], relation_type="sourced_from", target_object_id=source_id,
                                confidence=_clamp(confidence), evidence_refs=[vault_item_id], actor=actor,
                                confirmation=f"KERNEL LINK 235 {item['case_id']} ANLEGEN")
        deriv = self.db.one("SELECT * FROM evidence_derivations_239 WHERE child_vault_item_id=?", (vault_item_id,))
        if deriv:
            parent_binding = self.db.one("SELECT canonical_evidence_object_id FROM evidence_kernel_bindings_239 WHERE vault_item_id=?", (deriv["parent_vault_item_id"],))
            if parent_binding:
                self.kernel.create_link(case_id=item["case_id"], source_object_id=evidence["object_id"], relation_type="derived_from",
                                        target_object_id=parent_binding["canonical_evidence_object_id"], confidence=1.0, evidence_refs=[vault_item_id], actor=actor,
                                        confirmation=f"KERNEL LINK 235 {item['case_id']} ANLEGEN")
        bid, now = new_id("evbind239"), now_ts()
        payload = {"binding_id": bid, "case_id": item["case_id"], "vault_item_id": vault_item_id, "canonical_source_object_id": source_id,
                   "canonical_evidence_object_id": evidence["object_id"], "bound_by": actor, "bound_at": now}
        self.db.execute("INSERT INTO evidence_kernel_bindings_239 VALUES(?,?,?,?,?,?,?,?)",
                        (bid, item["case_id"], vault_item_id, source_id, evidence["object_id"], actor, now, _hash(payload)))
        self._event(item["case_id"], "evidence_bound_to_kernel", "vault_item", vault_item_id, {"canonical_evidence_object_id": evidence["object_id"]}, actor)
        return payload

    def conversation_context(self, *, case_id: str, limit: int = 80) -> dict[str, Any]:
        rows = self.db.all("""
            SELECT v.*,r.decision,r.evidence_quality,r.rationale review_rationale,k.canonical_evidence_object_id
            FROM evidence_vault_items_239 v
            LEFT JOIN evidence_reviews_239 r ON r.vault_item_id=v.vault_item_id
            LEFT JOIN evidence_kernel_bindings_239 k ON k.vault_item_id=v.vault_item_id
            WHERE v.case_id=? ORDER BY v.captured_at DESC,v.vault_item_id DESC LIMIT ?
        """, (case_id, max(1, min(int(limit), 300))))
        accepted=[]; pending=[]
        for r in rows:
            item = {"vault_item_id": r["vault_item_id"], "sha256": r["content_sha256"], "media_type": r["media_type"], "source_key": r["source_key"],
                    "source_url": r["source_url"], "captured_at": r["captured_at"], "decision": r.get("decision") or "pending",
                    "quality": r.get("evidence_quality"), "canonical_evidence_object_id": r.get("canonical_evidence_object_id") or ""}
            (accepted if item["decision"] == "accepted" else pending).append(item)
        return {
            "build": self.BUILD, "case_id": case_id, "accepted_evidence": accepted, "pending_or_rejected_not_facts": pending,
            "reasoning_rules": [
                "Only independently accepted evidence with intact content hash may ground factual claims.",
                "Derived evidence must retain its parent provenance; a summary or translation is not the original.",
                "A source change must be surfaced explicitly instead of silently replacing the earlier capture.",
            ],
        }

    # ------------------------------------------------------------------
    # Continuous training
    # ------------------------------------------------------------------
    def stage_training(self, *, case_id: str, actor: str, limit: int, confirmation: str) -> dict[str, Any]:
        self.kernel.cases.get_case(case_id)
        if confirmation != f"EVIDENCE TRAINING 239 {case_id} VORBEREITEN":
            raise PermissionError("explicit approval required")
        rows = self.db.all("""
            SELECT v.*,r.review_id,r.decision,r.evidence_quality,r.rationale,r.reviewer
            FROM evidence_vault_items_239 v JOIN evidence_reviews_239 r ON r.vault_item_id=v.vault_item_id
            LEFT JOIN evidence_training_links_239 t ON t.vault_item_id=v.vault_item_id
            WHERE v.case_id=? AND t.training_link_id IS NULL
            ORDER BY r.reviewed_at,v.vault_item_id LIMIT ?
        """, (case_id, max(1, min(int(limit or 50), 200))))
        staged=[]
        for r in rows:
            instruction = "Bewerte einen OSINT-Beleg hinsichtlich Integrität, Grounding und Evidenzqualität. Trenne Originalbeleg, abgeleitete Evidenz und Quellenänderungen sauber."
            response = f"Review decision: {r['decision']}. Evidence quality: {float(r['evidence_quality']):.2f}. Begründung: {r['rationale']}"
            context = {"sha256": r["content_sha256"], "media_type": r["media_type"], "byte_size": r["byte_size"], "source_key": r["source_key"],
                       "source_url": r["source_url"], "captured_at": r["captured_at"], "acquisition_method": r["acquisition_method"],
                       "reviewer": r["reviewer"], "network_acquisition_by_build239": False}
            try:
                ex = self.training.add_example(case_id=case_id, instruction=instruction, response=response, context=context,
                                               evidence_refs=[r["vault_item_id"]], language="de", source_type="evidence_vault_239",
                                               source_ref=r["vault_item_id"], created_by=actor,
                                               confirmation=f"TRAINING EXAMPLE 228 {case_id} ANLEGEN")
            except ValueError as exc:
                if "duplicate training example" in str(exc):
                    continue
                raise
            tid, now = new_id("evtrain239"), now_ts()
            payload = {"training_link_id": tid, "case_id": case_id, "vault_item_id": r["vault_item_id"], "review_id": r["review_id"],
                       "training_example_id": ex["example_id"], "created_by": actor, "created_at": now}
            self.db.execute("INSERT INTO evidence_training_links_239 VALUES(?,?,?,?,?,?,?,?)",
                            (tid, case_id, r["vault_item_id"], r["review_id"], ex["example_id"], actor, now, _hash(payload)))
            staged.append(payload)
        self._event(case_id, "evidence_training_staged", "case", case_id, {"count": len(staged), "automatic_training_execution": False, "automatic_model_activation": False}, actor)
        return {"case_id": case_id, "staged": staged, "automatic_training_execution": False, "automatic_model_activation": False}

    # ------------------------------------------------------------------
    # Snapshot, dashboard, UI
    # ------------------------------------------------------------------
    def create_snapshot(self, *, case_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        self.kernel.cases.get_case(case_id)
        if confirmation != f"EVIDENCE SNAPSHOT 239 {case_id} ERSTELLEN":
            raise PermissionError("explicit approval required")
        rows = self.db.all("SELECT vault_item_id,content_sha256,source_key,source_url,captured_at FROM evidence_vault_items_239 WHERE case_id=? ORDER BY vault_item_id", (case_id,))
        manifest = [{k: r[k] for k in ("vault_item_id", "content_sha256", "source_key", "source_url", "captured_at")} for r in rows]
        accepted = self.db.one("SELECT COUNT(*) AS n FROM evidence_reviews_239 WHERE case_id=? AND decision='accepted'", (case_id,))["n"]
        derived = self.db.one("SELECT COUNT(*) AS n FROM evidence_derivations_239 WHERE case_id=?", (case_id,))["n"]
        changed = self.db.one("SELECT COUNT(DISTINCT origin_key) AS n FROM evidence_change_events_239 WHERE case_id=? AND change_kind='content_changed'", (case_id,))["n"]
        sid, now = new_id("evsnap239"), now_ts(); digest = _hash(manifest)
        payload = {"snapshot_id": sid, "case_id": case_id, "item_count": len(rows), "accepted_count": accepted, "derived_count": derived,
                   "changed_origin_count": changed, "manifest_sha256": digest, "created_by": actor, "created_at": now}
        self.db.execute("INSERT INTO evidence_vault_snapshots_239 VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (sid, case_id, len(rows), accepted, derived, changed, digest, actor, now, _hash(payload)))
        self._event(case_id, "evidence_snapshot_created", "case", case_id, {"manifest_sha256": digest, "item_count": len(rows)}, actor)
        return payload

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self.kernel.cases.get_case(case_id)
        scalar = lambda sql, args=(case_id,): self.db.one(sql, args)["n"]
        return {"build": self.BUILD,
                "items": scalar("SELECT COUNT(*) AS n FROM evidence_vault_items_239 WHERE case_id=?"),
                "accepted": scalar("SELECT COUNT(*) AS n FROM evidence_reviews_239 WHERE case_id=? AND decision='accepted'"),
                "derived": scalar("SELECT COUNT(*) AS n FROM evidence_derivations_239 WHERE case_id=?"),
                "changes": scalar("SELECT COUNT(*) AS n FROM evidence_change_events_239 WHERE case_id=? AND change_kind='content_changed'"),
                "kernel_bindings": scalar("SELECT COUNT(*) AS n FROM evidence_kernel_bindings_239 WHERE case_id=?"),
                "training_examples": scalar("SELECT COUNT(*) AS n FROM evidence_training_links_239 WHERE case_id=?"),
                "network_acquisition": False}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        e=html.escape; d=self.dashboard(case_id=case_id)
        return f"""<section class='card' id='build239_evidence_vault'><h2>Evidence Vault &amp; Provenance + AI Training · Build 239</h2>
<p>Content-addressed Evidence Vault: Originale werden nicht überschrieben; Derived Evidence bleibt auf das Original rückführbar. Build 239 führt keinen Netzwerkabruf aus.</p>
<div class='metrics'><div class='metric'><div class='label'>Items</div><div class='value'>{d['items']}</div></div><div class='metric'><div class='label'>Akzeptiert</div><div class='value'>{d['accepted']}</div></div><div class='metric'><div class='label'>Derived</div><div class='value'>{d['derived']}</div></div><div class='metric'><div class='label'>Changes</div><div class='value'>{d['changes']}</div></div><div class='metric'><div class='label'>Training</div><div class='value'>{d['training_examples']}</div></div></div>
<div class='grid'>
<div class='card'><h3>Textbeleg einfrieren</h3><form method='post' action='/build239/capture-text'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='source_key' placeholder='Source key optional'><input name='source_url' placeholder='Quell-URL optional'><input name='original_filename' placeholder='Dateiname optional'><textarea name='text' placeholder='Bereits kontrolliert erfasster Originaltext' required></textarea><button>Originalbeleg speichern</button></form></div>
<div class='card'><h3>Beleg unabhängig prüfen</h3><form method='post' action='/build239/review'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='vault_item_id' placeholder='Vault Item-ID' required><select name='decision'><option>accepted</option><option>needs_context</option><option>rejected</option></select><input name='evidence_quality' type='number' min='0' max='1' step='0.01' value='0.7'><textarea name='rationale' placeholder='Unabhängige Review-Begründung' required></textarea><button>Review speichern</button></form></div>
<div class='card'><h3>In Kernel binden</h3><form method='post' action='/build239/kernel-bind'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='vault_item_id' placeholder='Vault Item-ID' required><input name='title' placeholder='Evidence-Titel' required><textarea name='statement' placeholder='Welche Aussage trägt dieser Beleg?' required></textarea><input name='confidence' type='number' min='0' max='1' step='0.01' value='0.7'><button>Reviewten Beleg binden</button></form></div>
<div class='card'><h3>Integrität prüfen</h3><form method='post' action='/build239/integrity'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='vault_item_id' placeholder='Vault Item-ID' required><button>SHA-256 prüfen</button></form></div>
<div class='card'><h3>Vault-Snapshot</h3><form method='post' action='/build239/snapshot'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><button>Manifest-Snapshot erzeugen</button></form></div>
<div class='card'><h3>KI-Training fortführen</h3><form method='post' action='/build239/training-stage'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input name='limit' type='number' min='1' max='200' value='50'><button>Reviewte Evidenzentscheidungen für Build 228 vorbereiten</button></form><p class='muted'>Nur pending Human Review; keine automatische Modellaktivierung.</p></div>
</div></section>"""

    def item(self, vault_item_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_vault_items_239 WHERE vault_item_id=?", (_text(vault_item_id, 200),))
        if not row:
            raise KeyError(vault_item_id)
        out = self._item_payload(row)
        review = self.db.one("SELECT * FROM evidence_reviews_239 WHERE vault_item_id=?", (vault_item_id,))
        out["review"] = review
        deriv = self.db.one("SELECT * FROM evidence_derivations_239 WHERE child_vault_item_id=?", (vault_item_id,))
        out["derivation"] = deriv
        return out

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _item_payload(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {"vault_item_id": row["vault_item_id"], "case_id": row["case_id"], "content_sha256": row["content_sha256"],
                "media_type": row["media_type"], "byte_size": int(row["byte_size"]), "storage_relpath": row["storage_relpath"],
                "original_filename": row["original_filename"], "source_key": row["source_key"], "source_url": row["source_url"],
                "captured_at": row["captured_at"], "acquisition_method": row["acquisition_method"],
                "capture_metadata": _loads(row["capture_metadata_json"], {}), "created_by": row["created_by"], "created_at": row["created_at"]}

    def _blob_relpath(self, digest: str) -> str:
        return str(Path("evidence_vault_239") / "sha256" / digest[:2] / digest[2:4] / f"{digest}.blob")

    def _write_blob(self, rel: str, raw: bytes, digest: str) -> None:
        target = self.base_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise RuntimeError("content-addressed blob collision/integrity failure")
            return
        fd, tmpname = tempfile.mkstemp(prefix=".evidence239-", dir=str(target.parent))
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(raw); fh.flush(); os.fsync(fh.fileno())
            tmp = Path(tmpname)
            if hashlib.sha256(tmp.read_bytes()).hexdigest() != digest:
                raise RuntimeError("write verification failed")
            os.replace(tmp, target)
        finally:
            try:
                Path(tmpname).unlink(missing_ok=True)
            except Exception:
                pass

    def _origin_key(self, row: Mapping[str, Any]) -> str:
        if row.get("source_url"):
            return "url:" + row["source_url"]
        if row.get("source_key"):
            return "source:" + row["source_key"]
        return ""

    def _detect_change_for_new_item(self, vault_item_id: str, *, actor: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM evidence_vault_items_239 WHERE vault_item_id=?", (vault_item_id,))
        origin = self._origin_key(row)
        if not origin:
            return {"origin_key": "", "change_kind": "not_applicable"}
        if row["source_url"]:
            previous = self.db.one("SELECT * FROM evidence_vault_items_239 WHERE case_id=? AND source_url=? AND vault_item_id<>? ORDER BY captured_at DESC,created_at DESC LIMIT 1", (row["case_id"], row["source_url"], vault_item_id))
        else:
            previous = self.db.one("SELECT * FROM evidence_vault_items_239 WHERE case_id=? AND source_key=? AND source_url='' AND vault_item_id<>? ORDER BY captured_at DESC,created_at DESC LIMIT 1", (row["case_id"], row["source_key"], vault_item_id))
        if not previous:
            return {"origin_key": origin, "change_kind": "first_capture"}
        kind = "unchanged" if previous["content_sha256"] == row["content_sha256"] else "content_changed"
        cid, now = new_id("change239"), now_ts()
        payload = {"change_id": cid, "case_id": row["case_id"], "origin_key": origin, "previous_vault_item_id": previous["vault_item_id"],
                   "current_vault_item_id": vault_item_id, "previous_sha256": previous["content_sha256"], "current_sha256": row["content_sha256"],
                   "change_kind": kind, "detected_by": actor, "detected_at": now}
        self.db.execute("INSERT INTO evidence_change_events_239 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (cid, row["case_id"], origin, previous["vault_item_id"], vault_item_id, previous["content_sha256"], row["content_sha256"], kind, actor, now, _hash(payload)))
        self._event(row["case_id"], "evidence_change_detected", "vault_item", vault_item_id, {"change_kind": kind, "previous": previous["vault_item_id"]}, actor)
        return payload

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> None:
        prev = self.db.one("SELECT event_hash FROM build239_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "GENESIS"
        eid, now = new_id("evt239"), now_ts()
        material = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id,
                    "actor": actor, "payload": dict(payload), "previous_hash": previous, "created_at": now}
        h = _hash(material)
        self.db.execute("INSERT INTO build239_events VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (eid, case_id, event_type, object_type, object_id, actor, dumps(dict(payload)), previous, h, now))
        try:
            self.audit.log(f"build239_{event_type}", object_type, object_id, case_id, dict(payload))
        except Exception:
            pass
