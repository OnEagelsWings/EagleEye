from __future__ import annotations

import hashlib
import html
import importlib
import importlib.util
import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts

_SECRET = re.compile(r"(?i)(authorization|cookie|token|secret|password|api[_-]?key|session|private[_-]?key)")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_REVIEW = {"match", "no_match", "uncertain"}
_THREAT = {"low", "elevated", "high", "critical"}
_BASE_WEIGHTS = {
    "name": 2.1, "alias": 1.3, "email": 5.0, "phone": 5.0, "username": 2.4,
    "birth_date": 3.4, "location": 1.1, "organisation": 1.2, "timeline": 1.4,
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


def _text(value: Any, limit: int = 20000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _fold(value: Any) -> str:
    s = unicodedata.normalize("NFKC", _text(value, 2000)).casefold().strip()
    s = " ".join(s.split())
    return re.sub(r"[^\w@+.-]+", " ", s, flags=re.UNICODE).strip()


def _ascii_fold(value: Any) -> str:
    s = unicodedata.normalize("NFKD", _fold(value))
    return " ".join(s.encode("ascii", "ignore").decode("ascii").split())


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = re.split(r"[,;\n]", value)
    if not isinstance(value, (list, tuple, set)):
        value = [value]
    out: list[str] = []
    for item in value:
        item = _text(item, 500).strip()
        if item and item not in out:
            out.append(item)
    return out


def _jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    a, b = set(left), set(right)
    return len(a & b) / max(1, len(a | b)) if a or b else 0.0


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): ("[REDACTED]" if _SECRET.search(str(k)) else _redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"(?i)(authorization|cookie|token|secret|password|api[_-]?key|session)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", value[:20000])
    return value


class Build212EntityResolutionCaseAIService:
    """Explainable, reversible person-resolution with translation-aware case AI.

    The service never confirms identity autonomously. It creates candidates,
    exposes feature contributions, requires independent human review for merges,
    preserves original-language evidence and applies a case-scoped OPSEC gate.
    """

    BUILD = "212.0"
    SOURCES = (
        ("splink", "Splink", "entity_resolution", "https://github.com/moj-analytical-services/splink", "MIT", "optional_python_adapter", ["probabilistic_linkage", "match_weights", "clustering"], False),
        ("dedupe", "dedupe", "entity_resolution", "https://github.com/dedupeio/dedupe", "MIT", "optional_python_adapter", ["active_learning", "human_labels", "blocking"], False),
        ("argos_translate", "Argos Translate", "translation", "https://github.com/argosopentech/argos-translate", "MIT", "optional_offline_python_adapter", ["offline_translation", "local_models", "language_pivot"], False),
        ("maigret", "Maigret", "social_discovery", "https://github.com/soxoj/maigret", "MIT", "external_candidate_collector", ["username_discovery", "site_registry"], True),
        ("sherlock", "Sherlock", "social_discovery", "https://github.com/sherlock-project/sherlock", "MIT", "external_candidate_collector", ["username_discovery", "site_checks"], True),
        ("whatsmyname", "WhatsMyName", "source_registry", "https://github.com/Arcade-Project/WhatsMyName", "MIT", "definition_import_reference", ["positive_rules", "negative_rules", "false_positive_tests"], True),
    )

    def __init__(self, db: Any, audit: Any, *, evidence: Any, agents: Any, agent_runtime: Any, social: Any, runtime: Any, base_dir: Any, actor: str = "system") -> None:
        self.db, self.audit = db, audit
        self.evidence, self.agents, self.agent_runtime = evidence, agents, agent_runtime
        self.social, self.runtime = social, runtime
        self.base_dir, self.actor = base_dir, actor

    # ---------------- foundation / sources ----------------
    def seed(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "BUILD 212 FOUNDATION ANLEGEN":
            raise PermissionError("explicit approval required")
        now = now_ts()
        policy = {
            "specialisation": "person_osint", "investigator_leads": True, "ai_supports": True,
            "automatic_identity_confirmation": False, "automatic_merge": False,
            "facts_inferences_hypotheses_separated": True, "translations_are_interpretations": True,
            "case_isolation": True, "external_uploads": False, "active_engagement": False,
            "existing_firefox_new_tabs": True, "social_candidates_only": True,
        }
        self.db.execute("INSERT OR REPLACE INTO build212_policies VALUES(?,?,?,?,?)", ("default", dumps(policy), now, now, _hash(policy)))
        for sid, title, ptype, home, lic, mode, caps, net in self.SOURCES:
            payload = {"source_id": sid, "title": title, "project_type": ptype, "homepage": home, "license": lic, "mode": mode, "capabilities": caps, "network_capable": net}
            self.db.execute(
                """INSERT OR REPLACE INTO source_extensions_212 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sid, title, ptype, home, lic, mode, dumps(caps), int(net), 0, 0, 0, 0, 0, "candidate-only; no bundled third-party code", now, now, _hash(payload)),
            )
        # Keep existing AI/source foundations aligned without starting research.
        try:
            self.agents.seed_agents(confirmation="AI AGENTS 207 ANLEGEN")
        except Exception:
            pass
        try:
            self.agent_runtime.seed_runtime(confirmation="AGENT RUNTIME 208 ANLEGEN")
        except Exception:
            pass
        try:
            self.social.seed(confirmation="SOCIAL SOURCES 204 ANLEGEN")
        except Exception:
            pass
        return {"build": self.BUILD, "sources": len(self.SOURCES), "policy": policy, "automatic_external_action": False}

    def detect_optional_components(self) -> dict[str, Any]:
        mapping = {"splink": "splink", "dedupe": "dedupe", "argos_translate": "argostranslate"}
        rows = []
        for source_id, module in mapping.items():
            available = importlib.util.find_spec(module) is not None
            rows.append({"source_id": source_id, "module": module, "available": available, "executed": False})
        return {"components": rows, "passive_detection": True, "network_access": False}

    def validate_source(self, *, source_id: str, fixture_ok: bool, parser_ok: bool, live_ok: bool, terms_reviewed: bool, reviewer: str, reason: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOURCE 212 {source_id} VALIDIEREN":
            raise PermissionError("explicit approval required")
        row = self.db.one("SELECT * FROM source_extensions_212 WHERE source_id=?", (source_id,))
        if not row:
            raise KeyError(source_id)
        if len(reason.strip()) < 10:
            raise ValueError("reason too short")
        active = bool(fixture_ok and parser_ok and terms_reviewed and (live_ok or not row["network_capable"]))
        payload = {"source_id": source_id, "fixture_ok": fixture_ok, "parser_ok": parser_ok, "live_ok": live_ok, "terms_reviewed": terms_reviewed, "active": active, "reviewer": reviewer, "reason": reason}
        self.db.execute("UPDATE source_extensions_212 SET active=?,fixture_ok=?,parser_ok=?,live_ok=?,terms_reviewed=?,notes=?,updated_at=?,payload_sha256=? WHERE source_id=?", (int(active), int(fixture_ok), int(parser_ok), int(live_ok), int(terms_reviewed), _text(reason, 2000), now_ts(), _hash(payload), source_id))
        return {**payload, "automatic_activation": False}

    # ---------------- identity records / comparison ----------------
    def add_identity_record(self, *, case_id: str, source_ref: str, record_ref: str, fields: Mapping[str, Any], provenance_refs: Sequence[str], source_reliability: float, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"IDENTITY RECORD 212 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        if not source_ref.strip() or not record_ref.strip():
            raise ValueError("source_ref and record_ref required")
        if not 0 <= float(source_reliability) <= 1:
            raise ValueError("source_reliability must be between 0 and 1")
        clean = _redact(dict(fields))
        normal = self._normalize_fields(clean)
        rid, created = new_id("idrec212"), now_ts()
        payload = {"record_id": rid, "case_id": case_id, "source_ref": source_ref, "record_ref": record_ref, "fields": clean, "normalized": normal, "provenance_refs": list(provenance_refs), "source_reliability": round(float(source_reliability), 4), "status": "candidate", "created_by": created_by, "created_at": created}
        self.db.execute("INSERT INTO identity_records_212 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (rid, case_id, source_ref, record_ref, dumps(clean), dumps(normal), dumps(list(provenance_refs)), payload["source_reliability"], "candidate", created_by, created, _hash(payload)))
        self._event(case_id, "identity_record_added", "identity_record", rid, payload, created_by)
        return {**payload, "identity_confirmed": False}

    def candidate_pairs(self, *, case_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT * FROM identity_records_212 WHERE case_id=? ORDER BY created_at", (case_id,))
        pairs: list[dict[str, Any]] = []
        for i, left in enumerate(rows):
            ln = _loads(left["normalized_json"], {})
            for right in rows[i + 1:]:
                rn = _loads(right["normalized_json"], {})
                blocking = []
                if set(ln.get("emails", [])) & set(rn.get("emails", [])): blocking.append("email")
                if set(ln.get("phones", [])) & set(rn.get("phones", [])): blocking.append("phone")
                if set(ln.get("usernames", [])) & set(rn.get("usernames", [])): blocking.append("username")
                if ln.get("name") and rn.get("name") and SequenceMatcher(None, ln["name"], rn["name"]).ratio() >= .72: blocking.append("name")
                if blocking:
                    pairs.append({"left_record_id": left["record_id"], "right_record_id": right["record_id"], "blocking": blocking})
                if len(pairs) >= max(1, min(limit, 1000)):
                    return pairs
        return pairs

    def compare_records(self, *, case_id: str, left_record_id: str, right_record_id: str, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"IDENTITY COMPARE 212 {case_id} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        left, right = self._record(left_record_id, case_id), self._record(right_record_id, case_id)
        if left_record_id == right_record_id:
            raise ValueError("records must differ")
        if left_record_id > right_record_id:
            left, right = right, left
            left_record_id, right_record_id = right_record_id, left_record_id
        weights, snapshot_id = self._weights()
        features, conflicts = self._features(_loads(left["normalized_json"], {}), _loads(right["normalized_json"], {}))
        contributions = {key: round(features[key] * weights[key], 6) for key in weights}
        raw = sum(contributions.values()) - 3.0
        if conflicts:
            raw -= sum(float(item.get("penalty", 0)) for item in conflicts)
        probability = 1 / (1 + math.exp(-max(-12.0, min(12.0, raw))))
        state = "strong_match_candidate" if probability >= .88 else "probable_match_candidate" if probability >= .65 else "uncertain" if probability >= .35 else "distinct_candidate"
        cid, created = new_id("idcmp212"), now_ts()
        payload = {"comparison_id": cid, "case_id": case_id, "left_record_id": left_record_id, "right_record_id": right_record_id, "engine": "eagleeye_explainable_fallback", "model_snapshot_id": snapshot_id, "features": features, "contributions": contributions, "hard_conflicts": conflicts, "score": round(raw, 6), "probability": round(probability, 6), "candidate_state": state, "automatic_merge": False, "created_by": created_by, "created_at": created}
        self.db.execute("INSERT INTO identity_comparisons_212 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid, case_id, left_record_id, right_record_id, payload["engine"], snapshot_id, dumps(features), dumps(contributions), dumps(conflicts), payload["score"], payload["probability"], state, 0, created_by, created, _hash(payload)))
        self._event(case_id, "identity_comparison_created", "identity_comparison", cid, payload, created_by)
        return {**payload, "identity_confirmed": False, "human_review_required": True}

    def review_comparison(self, *, comparison_id: str, reviewer: str, reviewer_role: str, decision: str, reason: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"IDENTITY REVIEW 212 {comparison_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if decision not in _REVIEW:
            raise ValueError("invalid decision")
        if reviewer_role not in {"analyst", "supervisor"}:
            raise ValueError("reviewer_role must be analyst or supervisor")
        if len(reason.strip()) < 15:
            raise ValueError("reason too short")
        comp = self._comparison(comparison_id)
        existing = self.db.one("SELECT review_id FROM identity_reviews_212 WHERE comparison_id=? AND reviewer=?", (comparison_id, reviewer))
        if existing:
            raise ValueError("reviewer already submitted a decision")
        rid, created = new_id("idreview212"), now_ts()
        payload = {"review_id": rid, "comparison_id": comparison_id, "case_id": comp["case_id"], "reviewer": reviewer, "reviewer_role": reviewer_role, "decision": decision, "reason": reason.strip(), "created_at": created}
        self.db.execute("INSERT INTO identity_reviews_212 VALUES(?,?,?,?,?,?,?,?,?)", (rid, comparison_id, comp["case_id"], reviewer, reviewer_role, decision, reason.strip(), created, _hash(payload)))
        self._event(comp["case_id"], "identity_comparison_reviewed", "identity_review", rid, payload, reviewer)
        return {**payload, "automatic_merge": False}

    def merge_records(self, *, comparison_id: str, label: str, actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"IDENTITY MERGE 212 {comparison_id} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        comp = self._comparison(comparison_id)
        reviews = self.db.all("SELECT * FROM identity_reviews_212 WHERE comparison_id=? ORDER BY created_at", (comparison_id,))
        match = [r for r in reviews if r["decision"] == "match"]
        if len({r["reviewer"] for r in match}) < 2 or {r["reviewer_role"] for r in match} != {"analyst", "supervisor"}:
            raise PermissionError("independent analyst and supervisor match reviews required")
        if _loads(comp["hard_conflicts_json"], []):
            raise RuntimeError("hard conflicts block merge")
        if float(comp["probability"]) < .65:
            raise RuntimeError("comparison probability below merge threshold")
        gid, created = new_id("identity212"), now_ts()
        gp = {"group_id": gid, "case_id": comp["case_id"], "label": label.strip() or "Identity candidate", "status": "human_confirmed_group", "created_by": actor, "created_at": created}
        self.db.execute("INSERT INTO identity_groups_212 VALUES(?,?,?,?,?,?,?)", (gid, comp["case_id"], gp["label"], gp["status"], actor, created, _hash(gp)))
        for record_id in (comp["left_record_id"], comp["right_record_id"]):
            self._membership(comp["case_id"], gid, record_id, "attach", comparison_id, actor, "independent human reviews and explainable comparison")
        self._event(comp["case_id"], "identity_group_created", "identity_group", gid, gp, actor)
        return {**gp, "record_ids": [comp["left_record_id"], comp["right_record_id"]], "reversible": True, "ai_confirmed": False}

    def unmerge_record(self, *, group_id: str, record_id: str, actor: str, reason: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"IDENTITY UNMERGE 212 {group_id} {record_id}":
            raise PermissionError("explicit approval required")
        group = self.db.one("SELECT * FROM identity_groups_212 WHERE group_id=?", (group_id,))
        if not group:
            raise KeyError(group_id)
        if len(reason.strip()) < 15:
            raise ValueError("reason too short")
        event = self._membership(group["case_id"], group_id, record_id, "detach", "", actor, reason)
        return {"group_id": group_id, "record_id": record_id, "event_id": event, "active": False, "history_preserved": True}

    def golden_record_candidate(self, *, group_id: str) -> dict[str, Any]:
        group = self.db.one("SELECT * FROM identity_groups_212 WHERE group_id=?", (group_id,))
        if not group:
            raise KeyError(group_id)
        record_ids = self._active_members(group_id)
        records = [self._record(rid, group["case_id"]) for rid in record_ids]
        values: dict[str, list[dict[str, Any]]] = {}
        for row in records:
            fields = _loads(row["fields_json"], {})
            for key, value in fields.items():
                if value in (None, "", []): continue
                values.setdefault(key, []).append({"value": value, "record_id": row["record_id"], "source_ref": row["source_ref"], "source_reliability": row["source_reliability"]})
        candidate = {}
        for key, options in values.items():
            candidate[key] = sorted(options, key=lambda x: (-float(x["source_reliability"]), x["record_id"]))[0]
        return {"group_id": group_id, "candidate_values": candidate, "member_records": record_ids, "automatic_overwrite": False, "provenance_preserved": True}

    # ---------------- human-labelled training ----------------
    def add_training_example(self, *, comparison_id: str, label: str, analyst: str, reason: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"ER TRAINING 212 {comparison_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if label not in {"match", "no_match"}:
            raise ValueError("label must be match or no_match")
        comp = self._comparison(comparison_id)
        human = self.db.one("SELECT * FROM identity_reviews_212 WHERE comparison_id=? AND decision=? ORDER BY created_at DESC LIMIT 1", (comparison_id, label))
        if not human:
            raise PermissionError("matching human review required before training")
        eid, created = new_id("erexample212"), now_ts()
        payload = {"example_id": eid, "case_id": comp["case_id"], "comparison_id": comparison_id, "label": label, "source": "human_reviewed_case_example", "analyst": analyst, "reason": reason.strip(), "created_at": created}
        self.db.execute("INSERT INTO er_training_examples_212 VALUES(?,?,?,?,?,?,?,?,?)", (eid, comp["case_id"], comparison_id, label, payload["source"], analyst, reason.strip(), created, _hash(payload)))
        return {**payload, "production_weights_changed": False}

    def build_calibration_snapshot(self, *, name: str, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != "ER CALIBRATION 212 ERSTELLEN":
            raise PermissionError("explicit approval required")
        examples = self.db.all("SELECT e.*,c.feature_scores_json FROM er_training_examples_212 e JOIN identity_comparisons_212 c ON c.comparison_id=e.comparison_id ORDER BY e.created_at")
        match = [e for e in examples if e["label"] == "match"]
        no_match = [e for e in examples if e["label"] == "no_match"]
        if len(match) < 2 or len(no_match) < 2:
            raise ValueError("at least two match and two no_match examples required")
        weights = dict(_BASE_WEIGHTS)
        separation = {}
        for feature in weights:
            m = sum(_loads(e["feature_scores_json"], {}).get(feature, 0.0) for e in match) / len(match)
            n = sum(_loads(e["feature_scores_json"], {}).get(feature, 0.0) for e in no_match) / len(no_match)
            delta = max(-.6, min(.6, m - n))
            weights[feature] = round(max(.25, min(7.0, weights[feature] * (1 + delta))), 5)
            separation[feature] = round(delta, 5)
        sid, created = new_id("ercal212"), now_ts()
        metrics = {"feature_separation": separation, "training_only": True, "independent_test_required": True}
        payload = {"snapshot_id": sid, "name": name.strip() or "Build 212 calibration", "example_count": len(examples), "match_count": len(match), "no_match_count": len(no_match), "weights": weights, "metrics": metrics, "status": "review_required", "created_by": created_by, "created_at": created}
        self.db.execute("INSERT INTO er_calibration_snapshots_212 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (sid, payload["name"], len(examples), len(match), len(no_match), dumps(weights), dumps(metrics), "review_required", created_by, "", created, "", _hash(payload)))
        return {**payload, "deployed": False}

    def approve_calibration_snapshot(self, *, snapshot_id: str, supervisor: str, reason: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"ER CALIBRATION 212 {snapshot_id} FREIGEBEN":
            raise PermissionError("explicit approval required")
        row = self.db.one("SELECT * FROM er_calibration_snapshots_212 WHERE snapshot_id=?", (snapshot_id,))
        if not row: raise KeyError(snapshot_id)
        if len(reason.strip()) < 15: raise ValueError("reason too short")
        approved = now_ts()
        self.db.execute("UPDATE er_calibration_snapshots_212 SET status='approved',approved_by=?,approved_at=? WHERE snapshot_id=?", (supervisor, approved, snapshot_id))
        return {"snapshot_id": snapshot_id, "status": "approved", "approved_by": supervisor, "approved_at": approved, "reason": reason, "automatic_deployment": False}

    # ---------------- translation-aware case chat ----------------
    def translate_case_text(self, *, case_id: str, original_text: str, original_language: str, target_language: str, engine: str, created_by: str, source_id: str = "", translated_text: str = "", glossary: Mapping[str, str] | None = None, uncertainties: Sequence[str] = (), confirmation: str) -> dict[str, Any]:
        if confirmation != f"CASE TRANSLATION 212 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        original_text = _text(original_text, 100000).strip()
        if not original_text: raise ValueError("original_text required")
        version = "human"
        if engine == "manual":
            result = _text(translated_text, 100000).strip()
            if not result: raise ValueError("translated_text required for manual translation")
        elif engine == "argos_offline":
            try:
                module = importlib.import_module("argostranslate.translate")
                package = importlib.import_module("argostranslate")
                result = _text(module.translate(original_text, original_language, target_language), 100000).strip()
                version = _text(getattr(package, "__version__", "installed"), 100)
            except Exception as exc:
                raise RuntimeError(f"offline Argos translation unavailable: {_redact(str(exc))}") from exc
        else:
            raise ValueError("engine must be manual or argos_offline")
        tid, created = new_id("translation212"), now_ts()
        limitations = list(uncertainties) or ["translation_requires_human_review"]
        payload = {"translation_id": tid, "case_id": case_id, "source_id": source_id, "original_language": original_language, "target_language": target_language, "original_text": original_text, "translated_text": result, "engine": engine, "engine_version": version, "glossary": dict(glossary or {}), "uncertainties": limitations, "status": "candidate_translation", "created_by": created_by, "created_at": created}
        self.db.execute("INSERT INTO case_translations_212 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tid, case_id, source_id, original_language, target_language, original_text, result, engine, version, dumps(dict(glossary or {})), dumps(limitations), "candidate_translation", created_by, created, _hash(payload)))
        self._event(case_id, "case_translation_created", "translation", tid, {**payload, "original_text": f"sha256:{_hash(original_text)}", "translated_text": f"sha256:{_hash(result)}"}, created_by)
        return {**payload, "fact_status": "interpretation", "external_upload": False, "model_download": False}

    def prepare_chat_turn(self, *, case_id: str, question: str, question_language: str, working_language: str, created_by: str, translation_id: str = "", confirmation: str) -> dict[str, Any]:
        if confirmation != f"CASE CHAT 212 {case_id} VORBEREITEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        q = _text(question, 12000).strip()
        if not q: raise ValueError("question required")
        translated_q = q
        if translation_id:
            tr = self.db.one("SELECT * FROM case_translations_212 WHERE translation_id=? AND case_id=?", (translation_id, case_id))
            if not tr: raise KeyError(translation_id)
            translated_q = tr["translated_text"]
        context = self._case_context(case_id)
        run = self.agents.create_run(case_id=case_id, question=translated_q, created_by=created_by, confirmation=f"AI RUN 207 {case_id} ANLEGEN")
        plan = self.agents.plan(run_id=run["run_id"], countries=(), source_ids=[x.get("source_id", "") for x in context["evidence"] if x.get("source_id")], confirmation=f"AI PLAN 207 {run['run_id']} ERSTELLEN")
        turn_id, created = new_id("chat212"), now_ts()
        payload = {"turn_id": turn_id, "case_id": case_id, "ai_run_id": run["run_id"], "question_original": q, "question_language": question_language, "working_language": working_language, "translated_question": translated_q, "context": context, "response": {}, "citations": [], "status": "planned_human_controlled", "created_by": created_by, "created_at": created, "updated_at": created}
        self.db.execute("INSERT INTO investigator_chat_turns_212 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (turn_id, case_id, run["run_id"], q, question_language, working_language, translated_q, dumps(context), "{}", "[]", payload["status"], created_by, created, created, _hash(payload)))
        return {**payload, "agent_plan": plan, "external_uploads": False, "automatic_execution": False, "translations_are_interpretations": True}

    def complete_chat_turn(self, *, turn_id: str, response: Mapping[str, Any], citations: Sequence[str], actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"CASE CHAT 212 {turn_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        turn = self.db.one("SELECT * FROM investigator_chat_turns_212 WHERE turn_id=?", (turn_id,))
        if not turn: raise KeyError(turn_id)
        clean = _redact(dict(response))
        if not citations:
            raise ValueError("citations required")
        if not all(key in clean for key in ("observations", "inferences", "hypotheses", "open_questions")):
            raise ValueError("response must separate observations, inferences, hypotheses and open_questions")
        payload = {"turn_id": turn_id, "response": clean, "citations": list(citations), "status": "review_required", "updated_at": now_ts(), "actor": actor}
        self.db.execute("UPDATE investigator_chat_turns_212 SET response_json=?,citations_json=?,status='review_required',updated_at=?,payload_sha256=? WHERE turn_id=?", (dumps(clean), dumps(list(citations)), payload["updated_at"], _hash(payload), turn_id))
        self._event(turn["case_id"], "case_chat_completed", "chat_turn", turn_id, payload, actor)
        return {**payload, "automatic_case_update": False, "human_review_required": True}

    def record_ai_feedback(self, *, case_id: str, item_type: str, item_id: str, verdict: str, dimensions: Mapping[str, float], reason: str, analyst: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"AI FEEDBACK 212 {case_id} SPEICHERN": raise PermissionError("explicit approval required")
        if verdict not in {"confirmed", "rejected", "partially_correct", "needs_more_evidence"}: raise ValueError("invalid verdict")
        clean_dims = {str(k): max(0.0, min(1.0, float(v))) for k, v in dimensions.items()}
        fid, created = new_id("aifeedback212"), now_ts()
        payload = {"feedback_id": fid, "case_id": case_id, "item_type": item_type, "item_id": item_id, "verdict": verdict, "dimensions": clean_dims, "reason": reason, "analyst": analyst, "created_at": created}
        self.db.execute("INSERT INTO ai_feedback_212 VALUES(?,?,?,?,?,?,?,?,?,?)", (fid, case_id, item_type, item_id, verdict, dumps(clean_dims), reason, analyst, created, _hash(payload)))
        return {**payload, "used_for_benchmarking": True, "automatic_model_update": False}

    # ---------------- OPSEC ----------------
    def create_opsec_profile(self, *, case_id: str, threat_level: str, environment: str, reason: str, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"OPSEC PROFILE 212 {case_id} ANLEGEN": raise PermissionError("explicit approval required")
        self._case(case_id)
        if threat_level not in _THREAT: raise ValueError("invalid threat_level")
        if len(reason.strip()) < 20: raise ValueError("reason too short")
        controls = self._controls(threat_level)
        pid, created = new_id("opsec212"), now_ts()
        payload = {"profile_id": pid, "case_id": case_id, "threat_level": threat_level, "environment": environment, "controls": controls, "safety_lock": False, "reason": reason, "created_by": created_by, "created_at": created}
        self.db.execute("INSERT INTO opsec_profiles_212 VALUES(?,?,?,?,?,?,?,?,?,?)", (pid, case_id, threat_level, environment, dumps(controls), 0, reason, created_by, created, _hash(payload)))
        self._event(case_id, "opsec_profile_created", "opsec_profile", pid, payload, created_by)
        return payload

    def set_safety_lock(self, *, case_id: str, enabled: bool, actor: str, reason: str, confirmation: str) -> dict[str, Any]:
        expected = f"OPSEC LOCK 212 {case_id} {'AKTIVIEREN' if enabled else 'LOESEN'}"
        if confirmation != expected: raise PermissionError("explicit approval required")
        profile = self._opsec(case_id)
        pid, created = new_id("opsec212"), now_ts()
        controls = _loads(profile["controls_json"], {})
        payload = {"profile_id": pid, "case_id": case_id, "threat_level": profile["threat_level"], "environment": profile["environment"], "controls": controls, "safety_lock": enabled, "reason": reason, "created_by": actor, "created_at": created}
        self.db.execute("INSERT INTO opsec_profiles_212 VALUES(?,?,?,?,?,?,?,?,?,?)", (pid, case_id, profile["threat_level"], profile["environment"], dumps(controls), int(enabled), reason, actor, created, _hash(payload)))
        return payload

    def opsec_preflight(self, *, case_id: str, action_type: str, requested: Mapping[str, Any], created_by: str, source_id: str = "", confirmation: str) -> dict[str, Any]:
        if confirmation != f"OPSEC PREFLIGHT 212 {case_id} PRUEFEN": raise PermissionError("explicit approval required")
        profile = self._opsec(case_id)
        req = {str(k): bool(v) if isinstance(v, bool) else v for k, v in _redact(dict(requested)).items()}
        controls = _loads(profile["controls_json"], {})
        risks: list[str] = []
        if profile["safety_lock"]: risks.append("case_safety_lock_active")
        if req.get("direct_contact"): risks.append("direct_contact_prohibited")
        if req.get("credential_login") and controls.get("no_login"): risks.append("credential_login_blocked")
        if req.get("upload_local_file") and controls.get("no_local_file_upload"): risks.append("local_file_upload_blocked")
        if req.get("download") and controls.get("no_downloads"): risks.append("downloads_blocked")
        if req.get("active_engagement"): risks.append("active_engagement_prohibited")
        if req.get("new_browser_window"): risks.append("existing_firefox_new_tabs_required")
        if profile["threat_level"] in {"high", "critical"} and req.get("network_execution_from_core"): risks.append("core_network_execution_blocked")
        decision = "blocked" if risks else "approved_with_controls"
        pfid, created = new_id("preflight212"), now_ts()
        payload = {"preflight_id": pfid, "case_id": case_id, "action_type": action_type, "source_id": source_id, "requested": req, "effective_controls": controls, "risks": risks, "decision": decision, "created_by": created_by, "created_at": created}
        self.db.execute("INSERT INTO opsec_preflights_212 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (pfid, case_id, action_type, source_id, dumps(req), dumps(controls), dumps(risks), decision, created_by, created, _hash(payload)))
        self._event(case_id, "opsec_preflight", "opsec_preflight", pfid, payload, created_by)
        return payload

    # ---------------- dashboard ----------------
    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        if not self.db.one("SELECT policy_id FROM build212_policies WHERE policy_id='default'"):
            self.seed(confirmation="BUILD 212 FOUNDATION ANLEGEN")
        count = lambda sql: int((self.db.one(sql, (case_id,)) or {}).get("n", 0))
        return {
            "build": self.BUILD, "case_id": case_id,
            "counts": {
                "records": count("SELECT COUNT(*) AS n FROM identity_records_212 WHERE case_id=?"),
                "comparisons": count("SELECT COUNT(*) AS n FROM identity_comparisons_212 WHERE case_id=?"),
                "reviews": count("SELECT COUNT(*) AS n FROM identity_reviews_212 WHERE case_id=?"),
                "translations": count("SELECT COUNT(*) AS n FROM case_translations_212 WHERE case_id=?"),
                "chat_turns": count("SELECT COUNT(*) AS n FROM investigator_chat_turns_212 WHERE case_id=?"),
                "preflights": count("SELECT COUNT(*) AS n FROM opsec_preflights_212 WHERE case_id=?"),
            },
            "records": self.db.all("SELECT * FROM identity_records_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,)),
            "comparisons": self.db.all("SELECT * FROM identity_comparisons_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,)),
            "reviews": self.db.all("SELECT * FROM identity_reviews_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,)),
            "groups": self.db.all("SELECT * FROM identity_groups_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,)),
            "translations": self.db.all("SELECT * FROM case_translations_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,)),
            "chats": self.db.all("SELECT * FROM investigator_chat_turns_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,)),
            "feedback": self.db.all("SELECT * FROM ai_feedback_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,)),
            "opsec": self.db.all("SELECT * FROM opsec_profiles_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 5", (case_id,)),
            "preflights": self.db.all("SELECT * FROM opsec_preflights_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,)),
            "sources": self.db.all("SELECT * FROM source_extensions_212 ORDER BY project_type,title"),
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        d, esc = self.dashboard(case_id=case_id), lambda x: html.escape(str(x or ""), quote=True)
        c = d["counts"]
        comparisons = "".join(
            f"<tr><td><code>{esc(r['comparison_id'])}</code></td><td>{float(r['probability'])*100:.1f}%</td>"
            f"<td>{esc(r['candidate_state'])}</td><td>{'ja' if _loads(r['hard_conflicts_json'],[]) else 'nein'}</td></tr>"
            for r in d["comparisons"]
        ) or "<tr><td colspan='4'>Noch keine Vergleiche.</td></tr>"
        reviews = "".join(
            f"<tr><td><code>{esc(r['comparison_id'])}</code></td><td>{esc(r['reviewer_role'])}</td><td>{esc(r['decision'])}</td><td>{esc(r['reviewer'])}</td></tr>"
            for r in d["reviews"]
        ) or "<tr><td colspan='4'>Noch keine unabhängigen Reviews.</td></tr>"
        groups = "".join(
            f"<tr><td><code>{esc(r['group_id'])}</code></td><td>{esc(r['label'])}</td><td>{esc(r['status'])}</td></tr>"
            for r in d["groups"]
        ) or "<tr><td colspan='3'>Noch keine menschlich bestätigten Gruppen.</td></tr>"
        translations = "".join(
            f"<tr><td>{esc(r['original_language'])} → {esc(r['target_language'])}</td><td>{esc(r['engine'])}</td><td>{esc(r['status'])}</td><td><code>{esc(r['translation_id'])}</code></td></tr>"
            for r in d["translations"]
        ) or "<tr><td colspan='4'>Noch keine fallbezogene Übersetzung.</td></tr>"
        preflights = "".join(
            f"<tr><td>{esc(r['action_type'])}</td><td>{esc(r['source_id'])}</td><td>{esc(r['decision'])}</td><td><code>{esc(r['preflight_id'])}</code></td></tr>"
            for r in d["preflights"]
        ) or "<tr><td colspan='4'>Noch kein OPSEC-Preflight.</td></tr>"
        sources = "".join(
            f"<tr><td><code>{esc(r['source_id'])}</code></td><td>{esc(r['title'])}</td><td>{esc(r['project_type'])}</td><td>{'aktiv' if r['active'] else 'gesperrt'}</td><td>{'ja' if r['network_capable'] else 'nein'}</td></tr>"
            for r in d["sources"]
        ) or "<tr><td colspan='5'>Keine Erweiterungsquellen registriert.</td></tr>"
        return f"""
        <div class='notice'><b>Entity Resolution, Case AI &amp; OPSEC 212</b><br>Erklärbare und reversible Identitätskorrelation. Der Ermittler führt; AI, Übersetzung und offene Werkzeuge liefern nur quellengebundene Kandidaten.</div>
        <div class='metrics'><div class='metric'><div class='label'>Identitätsdatensätze</div><div class='value'>{c['records']}</div></div><div class='metric'><div class='label'>Vergleiche</div><div class='value'>{c['comparisons']}</div></div><div class='metric'><div class='label'>Reviews</div><div class='value'>{c['reviews']}</div></div><div class='metric'><div class='label'>Übersetzungen</div><div class='value'>{c['translations']}</div></div><div class='metric'><div class='label'>Chat-Turns</div><div class='value'>{c['chat_turns']}</div></div><div class='metric'><div class='label'>OPSEC-Preflights</div><div class='value'>{c['preflights']}</div></div></div>
        <div class='panel'><h2>Quellen- und Open-Source-Erweiterungen</h2><div class='notice'>Neue Komponenten bleiben standardmäßig gesperrt. Aktivierung erfordert Fixture-, Parser-, Lizenz-/Terms- und bei Netzwerkquellen einen kontrollierten Live-Test.</div><form method='post' action='/build212/source-validate'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='source_id' placeholder='Source-ID, z. B. argos_translate' required><div class='form-grid'><label><input type='checkbox' name='fixture_ok' value='true'> Fixture bestanden</label><label><input type='checkbox' name='parser_ok' value='true'> Parser bestanden</label><label><input type='checkbox' name='live_ok' value='true'> kontrollierter Live-Test</label><label><input type='checkbox' name='terms_reviewed' value='true'> Lizenz/Terms geprüft</label></div><textarea name='reason' rows='3' placeholder='Prüfbegründung' required></textarea><button>Quellenstatus prüfen und dokumentieren</button></form><div class='table-wrap'><table><thead><tr><th>ID</th><th>Projekt</th><th>Typ</th><th>Status</th><th>Netzwerkfähig</th></tr></thead><tbody>{sources}</tbody></table></div></div>
        <div class='two-col'>
          <div class='panel'><h2>Identitätsdatensatz erfassen</h2><form method='post' action='/build212/identity-record'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='source_ref' placeholder='Quellenreferenz' required><input name='record_ref' placeholder='Record-/Account-/Dokumentreferenz' required><textarea name='fields_json' rows='8' placeholder='{{"name":"...","emails":["..."],"usernames":["..."]}}' required></textarea><input name='provenance_refs' placeholder='Beleg-IDs, kommagetrennt'><input name='source_reliability' type='number' step='.01' min='0' max='1' value='.6'><button>Kandidatenrecord anlegen</button></form></div>
          <div class='panel'><h2>Erklärbarer Vergleich</h2><form method='post' action='/build212/compare'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='left_record_id' placeholder='Linke Record-ID' required><input name='right_record_id' placeholder='Rechte Record-ID' required><button>Vergleich berechnen</button></form><div class='table-wrap'><table><thead><tr><th>ID</th><th>Wahrscheinlichkeit</th><th>Kandidatstatus</th><th>Harte Konflikte</th></tr></thead><tbody>{comparisons}</tbody></table></div></div>
        </div>
        <div class='two-col'>
          <div class='panel'><h2>Unabhängiges Identitätsreview</h2><form method='post' action='/build212/review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='comparison_id' placeholder='Comparison-ID' required><select name='reviewer_role'><option value='analyst'>analyst</option><option value='supervisor'>supervisor</option></select><select name='decision'><option value='match'>match</option><option value='no_match'>no_match</option><option value='uncertain'>uncertain</option></select><textarea name='reason' rows='4' placeholder='Begründung anhand der Belege' required></textarea><button>Review append-only speichern</button></form><div class='table-wrap'><table><thead><tr><th>Vergleich</th><th>Rolle</th><th>Entscheidung</th><th>Reviewer</th></tr></thead><tbody>{reviews}</tbody></table></div></div>
          <div class='panel'><h2>Reversibles Merge / Unmerge</h2><form method='post' action='/build212/merge'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='comparison_id' placeholder='Comparison-ID mit Analyst- und Supervisor-Review' required><input name='label' placeholder='Bezeichnung des Golden-Record-Kandidaten' required><button>Menschlich bestätigte Gruppe erzeugen</button></form><hr><form method='post' action='/build212/unmerge'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='group_id' placeholder='Group-ID' required><input name='record_id' placeholder='Record-ID' required><textarea name='reason' rows='3' placeholder='Neue Evidenz / Korrekturgrund' required></textarea><button>Record reversibel lösen</button></form><div class='table-wrap'><table><thead><tr><th>Gruppe</th><th>Label</th><th>Status</th></tr></thead><tbody>{groups}</tbody></table></div></div>
        </div>
        <div class='panel'><h2>Fallbezogene Übersetzung</h2><div class='notice warn'>Originaltext bleibt unverändert. Übersetzungen sind Interpretationen, keine neuen Tatsachen. Argos wird ausschließlich mit bereits lokal installierten Modellen offline verwendet.</div><form method='post' action='/build212/translate'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><div class='form-grid'><div class='field'><label>Originalsprache</label><input name='original_language' value='he'></div><div class='field'><label>Zielsprache</label><input name='target_language' value='de'></div><div class='field'><label>Engine</label><select name='engine'><option value='manual'>Manuell / geprüft</option><option value='argos_offline'>Argos offline</option></select></div><div class='field'><label>Source-ID optional</label><input name='source_id'></div></div><textarea name='original_text' rows='6' placeholder='Originaltext' required></textarea><textarea name='translated_text' rows='6' placeholder='Manuelle Übersetzung; bei Argos leer lassen'></textarea><input name='uncertainties' placeholder='Unsicherheiten, kommagetrennt'><button>Übersetzung als Kandidat sichern</button></form><div class='table-wrap'><table><thead><tr><th>Sprachen</th><th>Engine</th><th>Status</th><th>ID</th></tr></thead><tbody>{translations}</tbody></table></div></div>
        <div class='two-col'><div class='panel'><h2>Chat-Ermittler vorbereiten</h2><form method='post' action='/build212/chat'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><textarea name='question' rows='5' placeholder='Fallbezogene Ermittlungsfrage' required></textarea><div class='form-grid'><input name='question_language' value='de'><input name='working_language' value='de'></div><input name='translation_id' placeholder='Optionale Translation-ID'><button>Kontrollierten Agentenplan anlegen</button></form><hr><h3>Geprüfte AI-Antwort sichern</h3><form method='post' action='/build212/chat-complete'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='turn_id' placeholder='Chat-Turn-ID' required><textarea name='response_json' rows='8' placeholder='{{"observations":[],"inferences":[],"hypotheses":[],"open_questions":[]}}' required></textarea><input name='citations' placeholder='Evidence-/Translation-IDs, kommagetrennt' required><button>Antwort als review-pflichtig speichern</button></form></div><div class='panel'><h2>AI-Training durch Ermittlerfeedback</h2><form method='post' action='/build212/ai-feedback'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='item_type' value='chat_turn'><input name='item_id' placeholder='Turn-/Claim-/Comparison-ID' required><select name='verdict'><option value='confirmed'>confirmed</option><option value='rejected'>rejected</option><option value='partially_correct'>partially_correct</option><option value='needs_more_evidence'>needs_more_evidence</option></select><textarea name='dimensions_json' rows='4' placeholder='{{"source_grounding":0.8,"identity_caution":1.0}}' required></textarea><textarea name='reason' rows='4' placeholder='Was war richtig, falsch oder unzureichend belegt?' required></textarea><button>Feedback für Benchmarking speichern</button></form><div class='notice'>Kein automatisches Nachtrainieren und keine unkontrollierte Modelländerung.</div></div></div>
        <div class='two-col'><div class='panel'><h2>OPSEC-Profil</h2><form method='post' action='/build212/opsec-profile'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='threat_level'><option>low</option><option>elevated</option><option>high</option><option>critical</option></select><input name='environment' value='existing_firefox_case_workspace'><textarea name='reason' rows='4' placeholder='Gefährdungslage und Schutzbegründung' required></textarea><button>Fallbezogenes Schutzprofil anlegen</button></form><hr><form method='post' action='/build212/safety-lock'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='enabled'><option value='true'>Safety Lock aktivieren</option><option value='false'>Safety Lock lösen</option></select><textarea name='reason' rows='3' placeholder='Begründung' required></textarea><button>Safety Lock ändern</button></form></div><div class='panel'><h2>OPSEC-Preflight</h2><form method='post' action='/build212/preflight'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='action_type' value='source_research'><input name='source_id' placeholder='Source-ID optional'><textarea name='requested_json' rows='7' placeholder='{{"credential_login":false,"download":false,"network_execution_from_core":false,"new_browser_window":false}}' required></textarea><button>Aktion vor Ausführung prüfen</button></form><div class='table-wrap'><table><thead><tr><th>Aktion</th><th>Quelle</th><th>Entscheidung</th><th>ID</th></tr></thead><tbody>{preflights}</tbody></table></div></div></div>
        """

    # ---------------- internals ----------------
    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)): raise KeyError(case_id)

    def _record(self, record_id: str, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM identity_records_212 WHERE record_id=? AND case_id=?", (record_id, case_id))
        if not row: raise KeyError(record_id)
        return row

    def _comparison(self, comparison_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM identity_comparisons_212 WHERE comparison_id=?", (comparison_id,))
        if not row: raise KeyError(comparison_id)
        return row

    def _normalize_fields(self, fields: Mapping[str, Any]) -> dict[str, Any]:
        names = _list(fields.get("aliases"))
        name = _ascii_fold(fields.get("name") or "") or _fold(fields.get("name") or "")
        aliases = sorted({_ascii_fold(x) or _fold(x) for x in names if x})
        emails = sorted({_fold(x) for x in _list(fields.get("emails") or fields.get("email")) if _EMAIL.match(_fold(x))})
        phones = sorted({re.sub(r"\D", "", x) for x in _list(fields.get("phones") or fields.get("phone")) if len(re.sub(r"\D", "", x)) >= 6})
        usernames = sorted({_fold(x).lstrip("@") for x in _list(fields.get("usernames") or fields.get("username")) if _fold(x).lstrip("@")})
        locations = sorted({_ascii_fold(x) or _fold(x) for x in _list(fields.get("locations") or fields.get("location")) if x})
        organisations = sorted({_ascii_fold(x) or _fold(x) for x in _list(fields.get("organisations") or fields.get("organizations") or fields.get("organisation")) if x})
        return {"name": name, "aliases": aliases, "emails": emails, "phones": phones, "usernames": usernames, "birth_date": _fold(fields.get("birth_date") or fields.get("date_of_birth") or ""), "locations": locations, "organisations": organisations, "valid_from": _fold(fields.get("valid_from") or ""), "valid_to": _fold(fields.get("valid_to") or "")}

    def _features(self, left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[dict[str, float], list[dict[str, Any]]]:
        conflicts: list[dict[str, Any]] = []
        name = SequenceMatcher(None, left.get("name", ""), right.get("name", "")).ratio() if left.get("name") and right.get("name") else 0.0
        alias = max([SequenceMatcher(None, a, b).ratio() for a in [left.get("name", ""), *left.get("aliases", [])] for b in [right.get("name", ""), *right.get("aliases", [])] if a and b] or [0.0])
        email = 1.0 if set(left.get("emails", [])) & set(right.get("emails", [])) else 0.0
        phone = 1.0 if set(left.get("phones", [])) & set(right.get("phones", [])) else 0.0
        username = 1.0 if set(left.get("usernames", [])) & set(right.get("usernames", [])) else 0.0
        birth = 1.0 if left.get("birth_date") and left.get("birth_date") == right.get("birth_date") else 0.0
        if left.get("birth_date") and right.get("birth_date") and left.get("birth_date") != right.get("birth_date"):
            conflicts.append({"feature": "birth_date", "left": left.get("birth_date"), "right": right.get("birth_date"), "penalty": 4.5})
        if set(left.get("emails", [])) and set(right.get("emails", [])) and not email:
            conflicts.append({"feature": "email", "penalty": 1.0, "type": "different_nonempty_values"})
        return ({"name": round(name, 6), "alias": round(alias, 6), "email": email, "phone": phone, "username": username, "birth_date": birth, "location": round(_jaccard(left.get("locations", []), right.get("locations", [])), 6), "organisation": round(_jaccard(left.get("organisations", []), right.get("organisations", [])), 6), "timeline": 0.0}, conflicts)

    def _weights(self) -> tuple[dict[str, float], str]:
        row = self.db.one("SELECT * FROM er_calibration_snapshots_212 WHERE status='approved' ORDER BY approved_at DESC LIMIT 1")
        return (_loads(row["weights_json"], dict(_BASE_WEIGHTS)), row["snapshot_id"]) if row else (dict(_BASE_WEIGHTS), "")

    def _membership(self, case_id: str, group_id: str, record_id: str, action: str, comparison_id: str, actor: str, reason: str) -> str:
        eid, created = new_id("idmember212"), now_ts()
        payload = {"event_id": eid, "case_id": case_id, "group_id": group_id, "record_id": record_id, "action": action, "comparison_id": comparison_id, "actor": actor, "reason": reason, "created_at": created}
        self.db.execute("INSERT INTO identity_membership_events_212 VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, group_id, record_id, action, comparison_id, actor, reason, created, _hash(payload)))
        return eid

    def _active_members(self, group_id: str) -> list[str]:
        rows = self.db.all("SELECT * FROM identity_membership_events_212 WHERE group_id=? ORDER BY created_at,event_id", (group_id,))
        state: dict[str, bool] = {}
        for row in rows: state[row["record_id"]] = row["action"] == "attach"
        return sorted(rid for rid, active in state.items() if active)

    def _case_context(self, case_id: str) -> dict[str, Any]:
        evidence = self.db.all("SELECT source_id,collector_id,source_kind,canonical_url,observed_at FROM evidence_sources_211 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        statements = self.db.all("SELECT statement_id,source_id,entity_ref,predicate,value_json,statement_kind,confidence,review_status FROM evidence_statements_211 WHERE case_id=? ORDER BY created_at DESC LIMIT 40", (case_id,))
        comparisons = self.db.all("SELECT comparison_id,left_record_id,right_record_id,probability,candidate_state,hard_conflicts_json FROM identity_comparisons_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        translations = self.db.all("SELECT translation_id,source_id,original_language,target_language,translated_text,status FROM case_translations_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        return _redact({"evidence": evidence, "statements": statements, "identity_comparisons": comparisons, "translations": translations, "rules": ["cite_every_factual_claim", "separate_observation_inference_hypothesis", "do_not_confirm_identity", "no_external_action"]})

    def _controls(self, threat: str) -> dict[str, Any]:
        base = {"existing_firefox_new_tabs": True, "case_scoped_workspace": True, "no_direct_contact": True, "no_active_engagement": True, "no_secret_logging": True, "camera_microphone_geolocation_disabled": True, "external_uploads": False, "human_approval": True}
        if threat in {"elevated", "high", "critical"}: base.update({"dedicated_browser_profile": True, "no_login": True, "no_local_file_upload": True, "no_downloads": True, "cross_case_clipboard_prohibited": True})
        if threat in {"high", "critical"}: base.update({"network_execution_from_core": False, "offline_capture_import_preferred": True, "separate_os_account_recommended": True, "windows_appcontainer_target": True})
        if threat == "critical": base.update({"offline_only_default": True, "supervisor_review_each_network_step": True, "safety_lock_recommended": True})
        return base

    def _opsec(self, case_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM opsec_profiles_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 1", (case_id,))
        if row: return row
        # Safe implicit baseline is not persisted and never relaxes controls.
        return {"case_id": case_id, "threat_level": "elevated", "environment": "existing_firefox_case_workspace", "controls_json": dumps(self._controls("elevated")), "safety_lock": 0}

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> str:
        prev = self.db.one("SELECT event_hash FROM build212_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "0" * 64
        eid, created = new_id("evt212"), now_ts()
        clean = _redact(dict(payload))
        body = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": clean, "previous_hash": previous, "created_at": created}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build212_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, actor, dumps(clean), previous, event_hash, created))
        if self.audit is not None and hasattr(self.audit, "log"):
            self.audit.log(event_type, object_type, object_id, case_id, clean)
        return eid
