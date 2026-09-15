from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import PurePath
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts

_SECRET = re.compile(r"(?i)(authorization|cookie|token|secret|password|api[_-]?key|session|private[_-]?key)")
_ENTITY_TYPES = {"person", "digital_identity", "account", "organisation", "location", "event", "document", "source", "claim", "hypothesis", "observation"}
_RELATION_TYPES = {"associated_with", "owns", "member_of", "located_at", "mentioned_in", "published", "works_for", "related_to", "supports", "contradicts", "observed_as"}
_MENTION_TYPES = {"person", "organisation", "location", "email", "account", "date", "other"}
_REVIEW_STATES = {"candidate", "review_required", "accepted", "rejected", "disputed"}
_THREATS = {"low", "elevated", "high", "critical"}
_ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm", ".pdf", ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".eml", ".msg", ".epub", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".zip"}
_ALLOWED_MEDIA_PREFIXES = ("text/", "image/")
_ALLOWED_MEDIA_TYPES = {
    "application/pdf", "application/json", "application/xml", "application/zip", "application/rtf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.oasis.opendocument.text", "application/vnd.oasis.opendocument.spreadsheet",
    "application/msword", "application/vnd.ms-excel", "application/vnd.ms-powerpoint",
    "message/rfc822", "application/epub+zip", "application/octet-stream",
}


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


def _text(value: Any, limit: int = 1000000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): ("[REDACTED]" if _SECRET.search(str(k)) else _redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"(?i)(authorization|cookie|token|secret|password|api[_-]?key|session)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", value[:100000])
    return value


def _safe_filename(name: str, content_hash: str) -> tuple[str, str]:
    cleaned = PurePath(_text(name, 300).strip()).name
    extension = PurePath(cleaned).suffix.casefold()
    if extension not in _ALLOWED_EXTENSIONS:
        raise ValueError("unsupported document extension")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", PurePath(cleaned).stem).strip("._")[:80] or "document"
    return f"{content_hash[:12]}_{stem}{extension}", extension


class Build214InvestigationOntologyDocumentsService:
    """Consolidated, case-centred ontology and document workspace.

    The service preserves Build 211 evidence, Build 212 identity/AI and Build 213
    social-source data. It adds statement-oriented temporal entities, safe local
    document registration, reviewed mentions, case translation, grounded chat and
    document-specific OPSEC without executing network-capable parsers from the core.
    """

    BUILD = "214.0"
    LANES = (
        ("sources_documents", "Quellen, Dokumente & Ontologie", "Beweise, Dokumente, Entitäten, Beziehungen und Zeitbezug zusammenführen"),
        ("ai_chat", "AI & Chat-Ermittler", "Fallfragen quellengebunden analysieren und Beobachtung, Schlussfolgerung und Hypothese trennen"),
        ("translation", "Fallbezogene Übersetzung", "Originaltexte erhalten, Übersetzungen und Unsicherheiten dokumentieren"),
        ("opsec", "OPSEC & Ermittlerschutz", "Dokumentrisiken, aktive Inhalte, Metadaten und Außenwirkung vor jedem Schritt prüfen"),
    )

    def __init__(self, db: Any, audit: Any, *, evidence: Any, identity_ai: Any, social_fabric: Any, agents: Any, runtime: Any, base_dir: Any, actor: str = "system") -> None:
        self.db, self.audit = db, audit
        self.evidence, self.identity_ai, self.social_fabric = evidence, identity_ai, social_fabric
        self.agents, self.runtime = agents, runtime
        self.base_dir, self.actor = base_dir, actor

    # --------------------------- foundation ---------------------------
    def seed(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "BUILD 214 ONTOLOGY DOCUMENTS ANLEGEN":
            raise PermissionError("explicit approval required")
        now = now_ts()
        policy = {
            "specialisation": "focused_person_osint",
            "product_position": "hidden_champion",
            "investigator_leads_ai_supports": True,
            "consolidated_case_workspace": True,
            "legacy_functions_preserved": True,
            "parallel_lanes": [x[0] for x in self.LANES],
            "statement_level_provenance": True,
            "temporal_relations": True,
            "original_documents_preserved": True,
            "automatic_identity_confirmation": False,
            "automatic_accusation": False,
            "automatic_external_action": False,
            "network_parsing_from_core": False,
            "cloud_document_upload_default": False,
            "active_content_execution": False,
            "human_review_required": True,
        }
        self.db.execute("INSERT OR REPLACE INTO build214_policies VALUES(?,?,?,?,?)", ("default", dumps(policy), now, now, _hash(policy)))
        for svc, confirmation_value in (
            (self.evidence, "EVIDENCE FOUNDATION 211 ANLEGEN"),
            (self.identity_ai, "BUILD 212 FOUNDATION ANLEGEN"),
            (self.social_fabric, "BUILD 213 SOCIAL FABRIC ANLEGEN"),
        ):
            try:
                method = getattr(svc, "seed_foundation", None) or getattr(svc, "seed", None)
                if method:
                    method(confirmation=confirmation_value)
            except Exception:
                pass
        return {"build": self.BUILD, "policy": policy, "lanes": [x[0] for x in self.LANES]}

    def ensure_workspaces(self, *, case_id: str, owner: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"CONSOLIDATED WORKSPACES 214 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        rows = []
        for lane, title, objective in self.LANES:
            existing = self.db.one("SELECT * FROM consolidated_workspaces_214 WHERE case_id=? AND lane_key=?", (case_id, lane))
            if existing:
                rows.append(existing)
                continue
            wid, now = new_id("workspace214"), now_ts()
            payload = {"workspace_id": wid, "case_id": case_id, "lane_key": lane, "title": title, "objective": objective, "status": "active", "owner": owner, "created_at": now}
            self.db.execute("INSERT INTO consolidated_workspaces_214 VALUES(?,?,?,?,?,?,?,?,?,?)", (wid, case_id, lane, title, objective, "active", owner, now, now, _hash(payload)))
            self._event(case_id, "workspace_lane_created", "workspace", wid, payload, owner)
            rows.append(payload)
        return {"case_id": case_id, "workspaces": rows, "parallel": True, "single_ui": True}

    # --------------------------- ontology ---------------------------
    def create_entity(self, *, case_id: str, entity_type: str, label: str, properties: Mapping[str, Any], source_refs: Sequence[str], language: str, confidence: float, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"ONTOLOGY ENTITY 214 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        entity_type = _text(entity_type, 40).casefold()
        if entity_type not in _ENTITY_TYPES:
            raise ValueError("invalid entity type")
        label = _text(label, 500).strip()
        if not label:
            raise ValueError("entity label required")
        refs = self._valid_refs(case_id, source_refs)
        if not refs and entity_type not in {"hypothesis"}:
            raise ValueError("at least one valid case source reference required")
        confidence = max(0.0, min(float(confidence), 1.0))
        eid, now = new_id("entity214"), now_ts()
        payload = {"entity_id": eid, "case_id": case_id, "entity_type": entity_type, "label": label, "properties": _redact(dict(properties)), "source_refs": refs, "language": _text(language or "und", 12), "confidence": confidence, "review_status": "candidate", "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO ontology_entities_214 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (eid, case_id, entity_type, label, dumps(payload["properties"]), dumps(refs), payload["language"], confidence, "candidate", created_by, now, _hash(payload)))
        self._event(case_id, "ontology_entity_created", "ontology_entity", eid, payload, created_by)
        return {**payload, "automatic_identity_confirmation": False}

    def create_relation(self, *, case_id: str, source_entity_id: str, target_entity_id: str, relation_type: str, valid_from: str, valid_to: str, observed_at: str, source_refs: Sequence[str], confidence: float, contradiction_status: str, notes: str, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"ONTOLOGY RELATION 214 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        source = self._entity(source_entity_id, case_id)
        target = self._entity(target_entity_id, case_id)
        relation_type = _text(relation_type, 80).casefold()
        if relation_type not in _RELATION_TYPES:
            raise ValueError("invalid relation type")
        refs = self._valid_refs(case_id, source_refs)
        if not refs:
            raise ValueError("valid case source reference required")
        contradiction_status = _text(contradiction_status or "none", 30)
        if contradiction_status not in {"none", "possible", "confirmed", "resolved"}:
            raise ValueError("invalid contradiction status")
        confidence = max(0.0, min(float(confidence), 1.0))
        rid, now = new_id("relation214"), now_ts()
        payload = {
            "relation_id": rid, "case_id": case_id, "source_entity_id": source["entity_id"], "target_entity_id": target["entity_id"],
            "relation_type": relation_type, "valid_from": _text(valid_from, 40), "valid_to": _text(valid_to, 40),
            "observed_at": _text(observed_at or now, 40), "source_refs": refs, "confidence": confidence,
            "review_status": "review_required", "contradiction_status": contradiction_status, "notes": _text(notes, 5000),
            "created_by": created_by, "created_at": now,
        }
        self.db.execute("INSERT INTO ontology_relations_214 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (rid, case_id, source["entity_id"], target["entity_id"], relation_type, payload["valid_from"], payload["valid_to"], payload["observed_at"], dumps(refs), confidence, "review_required", contradiction_status, payload["notes"], created_by, now, _hash(payload)))
        self._event(case_id, "ontology_relation_created", "ontology_relation", rid, payload, created_by)
        return {**payload, "temporal": True, "human_review_required": True}

    # --------------------------- documents ---------------------------
    def register_document(self, *, case_id: str, evidence_ref: str, original_name: str, media_type: str, size_bytes: int, content_sha256: str, language: str, source_kind: str, active_content_state: str, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"DOCUMENT 214 {case_id} REGISTRIEREN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        refs = self._valid_refs(case_id, [evidence_ref])
        if not refs:
            raise ValueError("document must reference existing case evidence")
        size = int(size_bytes)
        if size < 0 or size > 100 * 1024 * 1024:
            raise ValueError("document size outside 100 MB limit")
        content_hash = _text(content_sha256, 64).casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", content_hash):
            raise ValueError("valid SHA-256 required")
        media = _text(media_type, 180).casefold().split(";", 1)[0].strip()
        if not (media in _ALLOWED_MEDIA_TYPES or any(media.startswith(x) for x in _ALLOWED_MEDIA_PREFIXES)):
            raise ValueError("unsupported media type")
        safe_name, extension = _safe_filename(original_name, content_hash)
        active = _text(active_content_state or "unknown", 30)
        if active not in {"none", "unknown", "detected", "removed"}:
            raise ValueError("invalid active content state")
        parser_mode = "isolated_offline_only"
        did, now = new_id("document214"), now_ts()
        payload = {"document_id": did, "case_id": case_id, "evidence_ref": refs[0], "original_name": _text(original_name, 300), "safe_name": safe_name, "extension": extension, "media_type": media, "size_bytes": size, "content_sha256": content_hash, "language": _text(language or "und", 12), "source_kind": _text(source_kind or "evidence_import", 80), "parser_mode": parser_mode, "active_content_state": active, "status": "registered_review_required", "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO document_records_214 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (did, case_id, refs[0], payload["original_name"], safe_name, extension, media, size, content_hash, payload["language"], payload["source_kind"], parser_mode, active, payload["status"], created_by, now, _hash(payload)))
        self._event(case_id, "document_registered", "document", did, payload, created_by)
        return {**payload, "file_executed": False, "network_used": False, "original_preserved": True}

    def record_extraction(self, *, case_id: str, document_id: str, extractor: str, extractor_version: str, text_original: str, metadata: Mapping[str, Any], warnings: Sequence[str], language: str, page_count: int, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"DOCUMENT EXTRACTION 214 {document_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        doc = self._document(document_id, case_id)
        extractor = _text(extractor, 80).casefold()
        if extractor not in {"manual", "tika_isolated", "tesseract_isolated", "datashare_import", "native_text"}:
            raise ValueError("unapproved extractor")
        text = _text(text_original, 2_000_000)
        if not text.strip():
            raise ValueError("extracted text required")
        eid, now = new_id("extract214"), now_ts()
        clean_meta = _redact(dict(metadata))
        clean_warnings = [_text(x, 1000) for x in warnings][:100]
        payload = {"extraction_id": eid, "case_id": case_id, "document_id": doc["document_id"], "extractor": extractor, "extractor_version": _text(extractor_version, 120), "text_sha256": _hash(text.encode("utf-8")), "metadata": clean_meta, "warnings": clean_warnings, "language": _text(language or doc["language"], 12), "page_count": max(0, min(int(page_count), 100000)), "status": "candidate_extraction", "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO document_extractions_214 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (eid, case_id, doc["document_id"], extractor, payload["extractor_version"], text, payload["text_sha256"], dumps(clean_meta), dumps(clean_warnings), payload["language"], payload["page_count"], payload["status"], created_by, now, _hash(payload)))
        self._event(case_id, "document_extraction_recorded", "document_extraction", eid, {**payload, "text_length": len(text)}, created_by)
        return {**payload, "text_original_preserved": True, "automatic_factual_status": False}

    def record_mentions(self, *, case_id: str, extraction_id: str, mentions: Sequence[Mapping[str, Any]], created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"DOCUMENT MENTIONS 214 {extraction_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        extraction = self._extraction(extraction_id, case_id)
        if not mentions or len(mentions) > 1000:
            raise ValueError("1 to 1000 mentions required")
        created = []
        for raw in mentions:
            entity_type = _text(raw.get("entity_type") or "other", 30).casefold()
            if entity_type not in _MENTION_TYPES:
                raise ValueError("invalid mention entity type")
            original = _text(raw.get("text_original"), 1000).strip()
            if not original:
                raise ValueError("mention text required")
            start = max(0, int(raw.get("start_offset", 0)))
            end = max(start, int(raw.get("end_offset", start + len(original))))
            linked = _text(raw.get("linked_entity_id"), 80)
            if linked:
                self._entity(linked, case_id)
            confidence = max(0.0, min(float(raw.get("confidence", 0.5)), 1.0))
            mid, now = new_id("mention214"), now_ts()
            payload = {"mention_id": mid, "case_id": case_id, "document_id": extraction["document_id"], "extraction_id": extraction_id, "entity_type": entity_type, "text_original": original, "normalized_text": _text(raw.get("normalized_text") or original, 1000), "start_offset": start, "end_offset": end, "context_text": _text(raw.get("context_text"), 4000), "confidence": confidence, "review_status": "review_required", "linked_entity_id": linked, "created_by": created_by, "created_at": now}
            self.db.execute("INSERT INTO document_mentions_214 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (mid, case_id, extraction["document_id"], extraction_id, entity_type, original, payload["normalized_text"], start, end, payload["context_text"], confidence, "review_required", linked, created_by, now, _hash(payload)))
            self._event(case_id, "document_mention_recorded", "document_mention", mid, payload, created_by)
            created.append(payload)
        return {"extraction_id": extraction_id, "mentions": created, "identity_confirmation": False, "human_review_required": True}

    # --------------------------- translation and AI ---------------------------
    def translate_excerpt(self, *, case_id: str, extraction_id: str, original_text: str, original_language: str, target_language: str, translated_text: str, engine: str, engine_version: str, glossary: Mapping[str, str], uncertainties: Sequence[str], created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"DOCUMENT TRANSLATION 214 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        extraction = self._extraction(extraction_id, case_id)
        original = _text(original_text, 200000).strip()
        translated = _text(translated_text, 200000).strip()
        if not original or not translated:
            raise ValueError("original and translated text required")
        engine = _text(engine, 60).casefold()
        if engine not in {"manual", "argos_offline", "reviewed_external_import", "ollama_local"}:
            raise ValueError("only manual or approved offline/import translation allowed")
        tid, now = new_id("translation214"), now_ts()
        payload = {"translation_id": tid, "case_id": case_id, "document_id": extraction["document_id"], "extraction_id": extraction_id, "original_language": _text(original_language or extraction["language"], 12), "target_language": _text(target_language, 12), "original_text": original, "translated_text": translated, "engine": engine, "engine_version": _text(engine_version, 100), "glossary": dict(glossary), "uncertainties": [_text(x, 1000) for x in uncertainties][:100], "status": "candidate_translation", "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO document_translations_214 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tid, case_id, extraction["document_id"], extraction_id, payload["original_language"], payload["target_language"], original, translated, engine, payload["engine_version"], dumps(payload["glossary"]), dumps(payload["uncertainties"]), payload["status"], created_by, now, _hash(payload)))
        self._event(case_id, "document_translation_recorded", "document_translation", tid, {**payload, "original_text": "[preserved]", "translated_text": "[preserved]"}, created_by)
        return {**payload, "original_preserved": True, "external_upload": False, "human_review_required": True}

    def prepare_chat_turn(self, *, case_id: str, question: str, question_language: str, working_language: str, focus: str, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"INVESTIGATION CHAT 214 {case_id} VORBEREITEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        question = _text(question, 10000).strip()
        if not question:
            raise ValueError("question required")
        context = self._case_context(case_id)
        tid, now = new_id("chat214"), now_ts()
        payload = {"turn_id": tid, "case_id": case_id, "question_original": question, "question_language": _text(question_language or "de", 12), "working_language": _text(working_language or "de", 12), "focus": _text(focus or "case_synthesis", 80), "context": context, "status": "prepared_no_execution", "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO investigation_chat_turns_214 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tid, case_id, question, payload["question_language"], payload["working_language"], payload["focus"], dumps(context), "{}", "[]", payload["status"], created_by, now, now, _hash(payload)))
        self._event(case_id, "investigation_chat_prepared", "chat_turn", tid, {**payload, "context": {"counts": context["counts"], "rules": context["rules"]}}, created_by)
        return {"turn_id": tid, "context": context, "automatic_execution": False, "human_review_required": True}

    def complete_chat_turn(self, *, turn_id: str, response: Mapping[str, Any], citations: Sequence[str], actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"INVESTIGATION CHAT 214 {turn_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        row = self.db.one("SELECT * FROM investigation_chat_turns_214 WHERE turn_id=?", (turn_id,))
        if not row:
            raise KeyError(turn_id)
        required = {"observations", "inferences", "hypotheses", "open_questions", "recommended_next_steps", "translation_notes"}
        if set(response.keys()) != required:
            raise ValueError("response must contain the exact structured sections")
        clean_response = {key: [_text(x, 5000) for x in (response.get(key) or [])][:100] for key in required}
        refs = self._valid_refs(row["case_id"], citations)
        if clean_response["observations"] and not refs:
            raise ValueError("factual observations require valid case citations")
        payload = {"response": clean_response, "citations": refs, "status": "review_required", "updated_at": now_ts(), "automatic_case_update": False, "automatic_external_action": False}
        self.db.execute("UPDATE investigation_chat_turns_214 SET response_json=?,citations_json=?,status='review_required',updated_at=?,payload_sha256=? WHERE turn_id=?", (dumps(clean_response), dumps(refs), payload["updated_at"], _hash({"turn_id": turn_id, **payload}), turn_id))
        self._event(row["case_id"], "investigation_chat_completed", "chat_turn", turn_id, payload, actor)
        return {"turn_id": turn_id, **payload, "human_review_required": True}

    def record_ai_feedback(self, *, case_id: str, item_type: str, item_id: str, verdict: str, dimensions: Mapping[str, Any], reason: str, analyst: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"INVESTIGATION AI FEEDBACK 214 {case_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        verdict = _text(verdict, 40)
        if verdict not in {"helpful", "partly_helpful", "incorrect", "unsafe", "needs_more_evidence"}:
            raise ValueError("invalid verdict")
        reason = _text(reason, 5000).strip()
        if len(reason) < 20:
            raise ValueError("reason too short")
        eligible = verdict in {"helpful", "partly_helpful", "incorrect", "needs_more_evidence"}
        fid, now = new_id("feedback214"), now_ts()
        payload = {"feedback_id": fid, "case_id": case_id, "item_type": _text(item_type, 80), "item_id": _text(item_id, 100), "verdict": verdict, "dimensions": _redact(dict(dimensions)), "reason": reason, "analyst": analyst, "training_eligible": eligible, "created_at": now}
        self.db.execute("INSERT INTO investigation_ai_feedback_214 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (fid, case_id, payload["item_type"], payload["item_id"], verdict, dumps(payload["dimensions"]), reason, analyst, int(eligible), now, _hash(payload)))
        self._event(case_id, "investigation_ai_feedback", "ai_feedback", fid, payload, analyst)
        return {**payload, "production_model_changed": False, "supervised_training_only": True}

    # --------------------------- OPSEC ---------------------------
    def create_document_opsec(self, *, case_id: str, threat_level: str, document_class: str, reason: str, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"DOCUMENT OPSEC 214 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        threat = _text(threat_level, 30).casefold()
        if threat not in _THREATS:
            raise ValueError("invalid threat level")
        reason = _text(reason, 5000).strip()
        if len(reason) < 30:
            raise ValueError("document threat rationale too short")
        controls = self._controls(threat)
        pid, now = new_id("docopsec214"), now_ts()
        payload = {"profile_id": pid, "case_id": case_id, "threat_level": threat, "document_class": _text(document_class or "unknown", 80), "controls": controls, "reason": reason, "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO document_opsec_profiles_214 VALUES(?,?,?,?,?,?,?,?,?)", (pid, case_id, threat, payload["document_class"], dumps(controls), reason, created_by, now, _hash(payload)))
        self._event(case_id, "document_opsec_profile_created", "document_opsec", pid, payload, created_by)
        return payload

    def preflight_document(self, *, case_id: str, document_id: str, requested: Mapping[str, Any], created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"DOCUMENT PREFLIGHT 214 {case_id} PRUEFEN":
            raise PermissionError("explicit approval required")
        doc = self._document(document_id, case_id)
        profile = self.db.one("SELECT * FROM document_opsec_profiles_214 WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        threat = profile["threat_level"] if profile else "elevated"
        controls = _loads(profile["controls_json"], {}) if profile else self._controls(threat)
        req = _redact(dict(requested))
        risks = []
        if requested.get("execute_active_content") or doc["active_content_state"] == "detected":
            risks.append("active_content_execution_prohibited")
        if requested.get("cloud_upload"):
            risks.append("cloud_upload_prohibited")
        if requested.get("external_link_fetch"):
            risks.append("external_link_fetch_prohibited")
        if requested.get("network_ocr") or requested.get("network_parser"):
            risks.append("network_document_processing_prohibited")
        if requested.get("preserve_original_filename_externally"):
            risks.append("original_filename_disclosure_prohibited")
        if requested.get("open_in_default_application") and threat in {"high", "critical"}:
            risks.append("unisolated_application_open_prohibited")
        if requested.get("enable_macros"):
            risks.append("macro_execution_prohibited")
        if requested.get("extract_embedded_files") and threat == "critical":
            risks.append("embedded_extraction_requires_supervisor")
        decision = "blocked" if risks else ("supervisor_review" if threat in {"high", "critical"} else "allowed_offline")
        pid, now = new_id("docpreflight214"), now_ts()
        payload = {"preflight_id": pid, "case_id": case_id, "document_id": document_id, "requested": req, "controls": controls, "risks": risks, "decision": decision, "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO document_preflights_214 VALUES(?,?,?,?,?,?,?,?,?,?)", (pid, case_id, document_id, dumps(req), dumps(controls), dumps(risks), decision, created_by, now, _hash(payload)))
        self._event(case_id, "document_preflight", "document_preflight", pid, payload, created_by)
        return payload

    # --------------------------- consolidated workspace ---------------------------
    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        try:
            self.seed(confirmation="BUILD 214 ONTOLOGY DOCUMENTS ANLEGEN")
        except Exception:
            pass
        lanes = self.ensure_workspaces(case_id=case_id, owner=self.actor, confirmation=f"CONSOLIDATED WORKSPACES 214 {case_id} ANLEGEN")["workspaces"]
        return {
            "build": self.BUILD,
            "policy": _loads((self.db.one("SELECT policy_json FROM build214_policies WHERE policy_id='default'") or {}).get("policy_json", "{}"), {}),
            "lanes": lanes,
            "documents": self.db.all("SELECT * FROM document_records_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "extractions": self.db.all("SELECT * FROM document_extractions_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "mentions": self.db.all("SELECT * FROM document_mentions_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "entities": self.db.all("SELECT * FROM ontology_entities_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "relations": self.db.all("SELECT * FROM ontology_relations_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "translations": self.db.all("SELECT * FROM document_translations_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "chat": self.db.all("SELECT * FROM investigation_chat_turns_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "preflights": self.db.all("SELECT * FROM document_preflights_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "legacy_counts": self._legacy_counts(case_id),
            "automatic_identity_confirmation": False,
            "automatic_external_action": False,
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        d = self.dashboard(case_id=case_id)
        esc = lambda x: html.escape(str(x or ""), quote=True)
        lane_cards = "".join(f"<a class='action-card' href='#{esc(x['lane_key'])}'><b>{esc(x['title'])}</b><br><small>{esc(x['objective'])}</small></a>" for x in d["lanes"])
        counts = d["legacy_counts"]
        docs = "".join(f"<tr><td>{esc(x['document_id'])}</td><td>{esc(x['safe_name'])}</td><td>{esc(x['language'])}</td><td>{esc(x['status'])}</td></tr>" for x in d["documents"][:30]) or "<tr><td colspan='4'>Noch keine Dokumente registriert.</td></tr>"
        entities = "".join(f"<tr><td>{esc(x['entity_id'])}</td><td>{esc(x['entity_type'])}</td><td>{esc(x['label'])}</td><td>{float(x['confidence'])*100:.0f}%</td></tr>" for x in d["entities"][:30]) or "<tr><td colspan='4'>Noch keine Ontologie-Entitäten.</td></tr>"
        relations = "".join(f"<tr><td>{esc(x['relation_type'])}</td><td>{esc(x['source_entity_id'])}</td><td>{esc(x['target_entity_id'])}</td><td>{esc(x['observed_at'])}</td></tr>" for x in d["relations"][:30]) or "<tr><td colspan='4'>Noch keine zeitlichen Beziehungen.</td></tr>"
        mentions = "".join(f"<tr><td>{esc(x['entity_type'])}</td><td>{esc(x['text_original'])}</td><td>{float(x['confidence'])*100:.0f}%</td><td>{esc(x['review_status'])}</td></tr>" for x in d["mentions"][:30]) or "<tr><td colspan='4'>Noch keine Dokumenterwähnungen.</td></tr>"
        preflights = "".join(f"<tr><td>{esc(x['document_id'])}</td><td>{esc(x['decision'])}</td><td>{esc(', '.join(_loads(x['risks_json'], [])))}</td></tr>" for x in d["preflights"][:20]) or "<tr><td colspan='3'>Noch keine Dokument-Preflights.</td></tr>"
        return f"""
        <div class='notice'><b>Fallarbeitsraum 214 · konsolidierte PersonOSINT</b><br>Die vier parallelen Arbeitsbereiche bleiben getrennt prüfbar, werden aber in einer Oberfläche geführt. Bestehende Evidence-, Entity-Resolution- und Social-Daten bleiben erhalten.</div>
        <div class='metrics'>
          <div class='metric'><div class='label'>Beweisquellen 211</div><div class='value'>{counts['evidence']}</div></div>
          <div class='metric'><div class='label'>Identitätsvergleiche 212</div><div class='value'>{counts['identity']}</div></div>
          <div class='metric'><div class='label'>Social-Kandidaten 213</div><div class='value'>{counts['social']}</div></div>
          <div class='metric'><div class='label'>Dokumente 214</div><div class='value'>{len(d['documents'])}</div></div>
        </div>
        <div class='actions workspace-jump'>{lane_cards}</div>

        <section id='sources_documents'>
        <div class='panel'><h2>1. Quellen, Dokumente &amp; Ontologie</h2><p>Dokumente werden nur als bereits gesicherte Evidence-Objekte registriert. Parser laufen isoliert und offline; Dateien werden nicht automatisch geöffnet.</p>
        <div class='grid'><form method='post' action='/build214/document-register'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>Dokument registrieren</h3><input name='evidence_ref' placeholder='Evidence-/Source-ID aus Build 211' required><input name='original_name' placeholder='Originaldateiname.pdf' required><input name='media_type' value='application/pdf' required><input name='size_bytes' type='number' min='0' max='104857600' placeholder='Dateigröße in Bytes' required><input name='content_sha256' placeholder='SHA-256' required><input name='language' value='und'><input name='source_kind' value='evidence_import'><select name='active_content_state'><option>unknown</option><option>none</option><option>detected</option><option>removed</option></select><button>Dokument sicher registrieren</button></form>
        <form method='post' action='/build214/extraction'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>Extraktion dokumentieren</h3><input name='document_id' placeholder='Document-ID' required><select name='extractor'><option>manual</option><option>native_text</option><option>tika_isolated</option><option>tesseract_isolated</option><option>datashare_import</option></select><input name='extractor_version' placeholder='Extractor-Version'><input name='language' value='und'><input name='page_count' type='number' min='0' value='1'><textarea name='text_original' rows='8' placeholder='Unveränderter extrahierter Text' required></textarea><textarea name='metadata_json' rows='4' placeholder='{{}}'></textarea><textarea name='warnings' rows='3' placeholder='Warnungen, zeilengetrennt'></textarea><button>Extraktionssnapshot speichern</button></form></div>
        <div class='grid'><form method='post' action='/build214/mentions'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>NER-/Mention-Kandidaten</h3><input name='extraction_id' placeholder='Extraction-ID' required><textarea name='mentions_json' rows='9' placeholder='[{{"entity_type":"person","text_original":"Name","normalized_text":"Name","start_offset":0,"end_offset":4,"confidence":0.7}}]' required></textarea><button>Reviewpflichtige Mentions speichern</button></form>
        <form method='post' action='/build214/entity'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>Ontologie-Entität</h3><select name='entity_type'>{''.join(f"<option>{x}</option>" for x in sorted(_ENTITY_TYPES))}</select><input name='label' placeholder='Bezeichnung' required><input name='language' value='und'><input name='confidence' type='number' min='0' max='1' step='.01' value='.5'><textarea name='properties_json' rows='4' placeholder='{{}}'></textarea><textarea name='source_refs' rows='3' placeholder='Quellen-IDs, komma- oder zeilengetrennt' required></textarea><button>Quellengebundene Entität anlegen</button></form>
        <form method='post' action='/build214/relation'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><h3>Zeitliche Beziehung</h3><input name='source_entity_id' placeholder='Quell-Entity-ID' required><input name='target_entity_id' placeholder='Ziel-Entity-ID' required><select name='relation_type'>{''.join(f"<option>{x}</option>" for x in sorted(_RELATION_TYPES))}</select><input name='valid_from' placeholder='Gültig ab / unbekannt'><input name='valid_to' placeholder='Gültig bis / offen'><input name='observed_at' placeholder='Beobachtet am (UTC)'><input name='confidence' type='number' min='0' max='1' step='.01' value='.5'><select name='contradiction_status'><option>none</option><option>possible</option><option>confirmed</option><option>resolved</option></select><textarea name='source_refs' rows='3' placeholder='Quellen-IDs' required></textarea><textarea name='notes' rows='3' placeholder='Einordnung'></textarea><button>Reviewpflichtige Beziehung anlegen</button></form></div>
        <div class='table-wrap'><table><thead><tr><th>Dokument</th><th>Sicherer Name</th><th>Sprache</th><th>Status</th></tr></thead><tbody>{docs}</tbody></table></div>
        <div class='grid'><div class='table-wrap'><table><thead><tr><th>Entity</th><th>Typ</th><th>Label</th><th>Konfidenz</th></tr></thead><tbody>{entities}</tbody></table></div><div class='table-wrap'><table><thead><tr><th>Relation</th><th>Von</th><th>Nach</th><th>Beobachtet</th></tr></thead><tbody>{relations}</tbody></table></div></div>
        <div class='table-wrap'><table><thead><tr><th>Mention-Typ</th><th>Originaltext</th><th>Konfidenz</th><th>Status</th></tr></thead><tbody>{mentions}</tbody></table></div></div></section>

        <section id='translation'><div class='panel'><h2>2. Fallbezogene Übersetzung</h2><form method='post' action='/build214/translate'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><div class='form-grid'><input name='extraction_id' placeholder='Extraction-ID' required><input name='original_language' value='und'><input name='target_language' value='de'><select name='engine'><option>manual</option><option>argos_offline</option><option>reviewed_external_import</option><option>ollama_local</option></select><input name='engine_version' placeholder='Engine-Version'><input name='uncertainties' placeholder='Unsicherheiten, komma-getrennt'></div><textarea name='original_text' rows='6' placeholder='Originalauszug' required></textarea><textarea name='translated_text' rows='6' placeholder='Übersetzung' required></textarea><textarea name='glossary_json' rows='3' placeholder='{{}}'></textarea><button>Originaltreue Übersetzung speichern</button></form></div></section>

        <section id='ai_chat'><div class='panel'><h2>3. AI &amp; Chat-Ermittler</h2><div class='grid'><form method='post' action='/build214/chat'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><textarea name='question' rows='5' placeholder='Konkrete fallbezogene Ermittlungsfrage' required></textarea><input name='question_language' value='de'><input name='working_language' value='de'><select name='focus'><option>case_synthesis</option><option>document_analysis</option><option>identity_review</option><option>social_review</option><option>contradiction_search</option><option>timeline</option></select><button>Fallkontext vorbereiten</button></form>
        <form method='post' action='/build214/chat-complete'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='turn_id' placeholder='Turn-ID' required><textarea name='response_json' rows='11' placeholder='{{"observations":[],"inferences":[],"hypotheses":[],"open_questions":[],"recommended_next_steps":[],"translation_notes":[]}}' required></textarea><textarea name='citations' rows='3' placeholder='Fallinterne Quellen-/Dokument-/Entity-IDs'></textarea><button>Reviewpflichtige AI-Antwort speichern</button></form>
        <form method='post' action='/build214/ai-feedback'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='item_type' value='investigation_chat_turn'><input name='item_id' placeholder='Item-ID' required><select name='verdict'><option>helpful</option><option>partly_helpful</option><option>needs_more_evidence</option><option>incorrect</option><option>unsafe</option></select><textarea name='dimensions_json' rows='4' placeholder='{{"source_grounding":5,"identity_caution":5,"translation_quality":5,"opsec":5}}'></textarea><textarea name='reason' rows='4' placeholder='Begründetes Ermittlerfeedback' required></textarea><button>Supervidiertes AI-Feedback speichern</button></form></div></div></section>

        <section id='opsec'><div class='panel'><h2>4. OPSEC &amp; Ermittlerschutz</h2><div class='grid'><form method='post' action='/build214/opsec'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='threat_level'><option>elevated</option><option>high</option><option>critical</option><option>low</option></select><input name='document_class' value='untrusted_public_document'><textarea name='reason' rows='5' placeholder='Gefährdungslage, mögliches Milieu, Gegenaufklärung und Schutzbedarf' required></textarea><button>Dokument-OPSEC-Profil anlegen</button></form>
        <form method='post' action='/build214/preflight'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='document_id' placeholder='Document-ID' required><textarea name='requested_json' rows='9' placeholder='{{"open_in_default_application":false,"execute_active_content":false,"cloud_upload":false,"external_link_fetch":false,"network_ocr":false}}' required></textarea><button>Dokument-Preflight prüfen</button></form></div><div class='table-wrap'><table><thead><tr><th>Dokument</th><th>Entscheidung</th><th>Risiken</th></tr></thead><tbody>{preflights}</tbody></table></div></div></section>
        """

    # --------------------------- internals ---------------------------
    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _entity(self, entity_id: str, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM ontology_entities_214 WHERE entity_id=? AND case_id=?", (entity_id, case_id))
        if not row:
            raise KeyError(entity_id)
        return row

    def _document(self, document_id: str, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM document_records_214 WHERE document_id=? AND case_id=?", (document_id, case_id))
        if not row:
            raise KeyError(document_id)
        return row

    def _extraction(self, extraction_id: str, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM document_extractions_214 WHERE extraction_id=? AND case_id=?", (extraction_id, case_id))
        if not row:
            raise KeyError(extraction_id)
        return row

    def _valid_refs(self, case_id: str, refs: Sequence[str]) -> list[str]:
        valid: list[str] = []
        seen: set[str] = set()
        for raw in refs:
            ref = _text(raw, 150).strip()
            if not ref or ref in seen:
                continue
            found = (
                self.db.one("SELECT source_id AS id FROM evidence_sources_211 WHERE case_id=? AND source_id=?", (case_id, ref))
                or self.db.one("SELECT statement_id AS id FROM evidence_statements_211 WHERE case_id=? AND statement_id=?", (case_id, ref))
                or self.db.one("SELECT candidate_id AS id FROM social_candidates_213 WHERE case_id=? AND candidate_id=?", (case_id, ref))
                or self.db.one("SELECT translation_id AS id FROM social_content_translations_213 WHERE case_id=? AND translation_id=?", (case_id, ref))
                or self.db.one("SELECT comparison_id AS id FROM identity_comparisons_212 WHERE case_id=? AND comparison_id=?", (case_id, ref))
                or self.db.one("SELECT document_id AS id FROM document_records_214 WHERE case_id=? AND document_id=?", (case_id, ref))
                or self.db.one("SELECT extraction_id AS id FROM document_extractions_214 WHERE case_id=? AND extraction_id=?", (case_id, ref))
                or self.db.one("SELECT mention_id AS id FROM document_mentions_214 WHERE case_id=? AND mention_id=?", (case_id, ref))
                or self.db.one("SELECT entity_id AS id FROM ontology_entities_214 WHERE case_id=? AND entity_id=?", (case_id, ref))
                or self.db.one("SELECT relation_id AS id FROM ontology_relations_214 WHERE case_id=? AND relation_id=?", (case_id, ref))
                or self.db.one("SELECT result_id AS id FROM digital_source_results_218 WHERE case_id=? AND result_id=?", (case_id, ref))
                or self.db.one("SELECT result_id AS id FROM source_results_220 WHERE case_id=? AND result_id=?", (case_id, ref))
                or self.db.one("SELECT v.vault_item_id AS id FROM evidence_vault_items_239 v JOIN evidence_reviews_239 r ON r.vault_item_id=v.vault_item_id AND r.decision='accepted' WHERE v.case_id=? AND v.vault_item_id=?", (case_id, ref))
                or self.db.one("SELECT l.link_id AS id FROM canonical_links_235 l JOIN canonical_link_reviews_235 r ON r.link_id=l.link_id AND r.decision='accepted' WHERE l.case_id=? AND l.link_id=?", (case_id, ref))
                or self.db.one("SELECT verified_claim_id AS id FROM verified_claims_229 WHERE case_id=? AND verified_claim_id=? AND status='verified'", (case_id, ref))
            )
            if found:
                valid.append(ref); seen.add(ref)
        return valid

    def _legacy_counts(self, case_id: str) -> dict[str, int]:
        def count(table: str) -> int:
            row = self.db.one(f"SELECT COUNT(*) AS n FROM {table} WHERE case_id=?", (case_id,))
            return int((row or {}).get("n", 0))
        return {"evidence": count("evidence_sources_211"), "identity": count("identity_comparisons_212"), "social": count("social_candidates_213")}

    def _case_context(self, case_id: str) -> dict[str, Any]:
        context = {
            "evidence_sources": self.db.all("SELECT source_id,canonical_url,observed_at,collector_id,collector_version FROM evidence_sources_211 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "evidence_statements": self.db.all("SELECT statement_id,statement_kind,entity_ref,predicate,original_value,value_json,value_language,confidence,review_status FROM evidence_statements_211 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "identity_comparisons": self.db.all("SELECT comparison_id,probability,candidate_state,hard_conflicts_json FROM identity_comparisons_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "social_candidates": self.db.all("SELECT candidate_id,site_key,target_value,profile_url,existence_state,display_name,content_language,confidence,limitations_json FROM social_candidates_213 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "documents": self.db.all("SELECT document_id,evidence_ref,safe_name,media_type,language,status FROM document_records_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "mentions": self.db.all("SELECT mention_id,document_id,entity_type,text_original,confidence,review_status,linked_entity_id FROM document_mentions_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "entities": self.db.all("SELECT entity_id,entity_type,label,source_refs_json,language,confidence,review_status FROM ontology_entities_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "relations": self.db.all("SELECT relation_id,source_entity_id,target_entity_id,relation_type,valid_from,valid_to,observed_at,source_refs_json,confidence,review_status,contradiction_status FROM ontology_relations_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "translations": self.db.all("SELECT translation_id,document_id,original_language,target_language,translated_text,uncertainties_json,status FROM document_translations_214 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "digital_source_results": self.db.all("SELECT result_id,adapter_key,platform,profile_url,display_name,username,description,location,organization,confidence,evidence_ref,review_status FROM digital_source_results_218 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "source_pack2_results": self.db.all("SELECT result_id,adapter_key,result_type,title,canonical_url,display_value,language,confidence,evidence_ref,review_status FROM source_results_220 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "rules": [
                "cite every factual observation", "separate observations, inferences and hypotheses",
                "do not confirm identity autonomously", "preserve original language and translation uncertainty",
                "no external action or contact", "treat document mentions as candidates until human review",
                "prefer the least risky next step", "surface contradictions and missing evidence",
            ],
        }
        context["counts"] = {key: len(value) for key, value in context.items() if isinstance(value, list)}
        return _redact(context)

    def _controls(self, threat: str) -> dict[str, Any]:
        controls = {
            "isolated_offline_parser": True, "no_active_content_execution": True, "no_macro_execution": True,
            "no_cloud_upload": True, "no_external_link_fetch": True, "no_network_ocr": True,
            "generated_safe_filename": True, "content_hash_required": True, "size_limit_mb": 100,
            "extension_allowlist": True, "media_type_validation": True, "original_preserved": True,
            "secrets_redacted": True, "human_preflight": True, "case_scoped_storage": True,
        }
        if threat in {"elevated", "high", "critical"}:
            controls.update({"quarantine_before_parse": True, "embedded_files_review_required": True, "metadata_review_required": True})
        if threat in {"high", "critical"}:
            controls.update({"dedicated_os_account_recommended": True, "supervisor_review_before_open": True, "default_application_open_blocked": True})
        if threat == "critical":
            controls.update({"offline_only": True, "separate_analysis_machine_recommended": True, "safety_lock": True, "embedded_extraction_blocked_by_default": True})
        return controls

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> str:
        prev = self.db.one("SELECT event_hash FROM build214_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "0" * 64
        eid, now = new_id("evt214"), now_ts()
        clean = _redact(dict(payload))
        body = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": clean, "previous_hash": previous, "created_at": now}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build214_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, actor, dumps(clean), previous, event_hash, now))
        if self.audit is not None and hasattr(self.audit, "log"):
            self.audit.log(event_type, object_type, object_id, case_id, clean)
        return eid
