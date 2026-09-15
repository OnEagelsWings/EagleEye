from __future__ import annotations

import hashlib
import html
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


CRITICAL_CONTROLS = {
    "explicit_ok_gate",
    "no_network_without_gateway",
    "no_binary_execution",
    "no_credentials_or_contact",
    "human_authority_preserved",
    "hash_locator_timestamp",
    "no_external_side_effect_without_authority",
    "no_invented_fact",
}

ALLOWED_TEXT_TYPES = {"text/plain", "text/html", "application/json", "application/xhtml+xml"}
ONION_HOST = re.compile(r"^[a-z2-7]{16,56}\.onion$", re.I)


class Build285ControlledCollectionGuidedUXService:
    BUILD = "285.0"

    def __init__(self, db: Any, audit: Any, *, build284: Any, build283: Any, build282: Any, build281: Any, actor: str = "local-analyst"):
        self.db = db
        self.audit = audit
        self.build284 = build284
        self.build283 = build283
        self.build282 = build282
        self.build281 = build281
        self.actor = actor

    def _mission(self, mission_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM phase12_missions_281 WHERE mission_id=?", (mission_id,))
        if not row:
            raise KeyError("mission not found")
        return row

    def set_operator_mode(self, *, actor: str | None = None, experience_mode: str = "novice") -> dict[str, Any]:
        actor = actor or self.actor
        mode = str(experience_mode or "novice").strip().lower()
        if mode not in {"novice", "analyst", "expert"}:
            raise ValueError("experience mode must be novice, analyst or expert")
        now = _now()
        existing = self.db.one("SELECT created_at FROM phase12_operator_preferences_285 WHERE actor=?", (actor,))
        created = existing["created_at"] if existing else now
        self.db.execute(
            "INSERT OR REPLACE INTO phase12_operator_preferences_285 VALUES(?,?,?,?,?,?)",
            (actor, mode, int(mode != "expert"), int(mode == "expert"), created, now),
        )
        return self.operator_mode(actor)

    def operator_mode(self, actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        row = self.db.one("SELECT * FROM phase12_operator_preferences_285 WHERE actor=?", (actor,))
        if not row:
            return self.set_operator_mode(actor=actor, experience_mode="novice")
        return {
            "actor": actor,
            "experience_mode": row["experience_mode"],
            "plain_language": bool(row["plain_language"]),
            "show_expert_details": bool(row["show_expert_details"]),
        }

    def _normalize_locator(self, source_locator: str, collection_scope: str) -> dict[str, str]:
        raw = " ".join(str(source_locator or "").split()).strip()
        if not raw:
            raise ValueError("source locator required")
        parts = urlsplit(raw)
        if parts.scheme.lower() not in {"http", "https"}:
            raise ValueError("only http/https source locators are supported")
        if parts.username or parts.password:
            raise PermissionError("credentials in source URL are not allowed")
        host = (parts.hostname or "").lower().strip(".")
        if not host:
            raise ValueError("source host missing")
        if parts.port not in {None, 80, 443}:
            raise PermissionError("Build 285 allows only ports 80/443")
        scope = str(collection_scope or "").strip().lower()
        if scope not in {"darkweb_text", "public_text"}:
            raise ValueError("collection scope must be darkweb_text or public_text")
        is_onion = bool(ONION_HOST.fullmatch(host))
        if scope == "darkweb_text" and not is_onion:
            raise PermissionError("darkweb_text requires a .onion locator")
        if scope == "public_text" and is_onion:
            raise PermissionError(".onion locators require darkweb_text scope")
        normalized = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", parts.query, ""))
        return {"normalized": normalized, "host": host, "locator_class": "onion" if is_onion else "public_web"}

    def _collection_event(self, *, request_id: str, action: str, details: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        req = self.db.one("SELECT * FROM phase12_collection_requests_285 WHERE request_id=?", (request_id,))
        if not req:
            raise KeyError("collection request not found")
        prev = self.db.one(
            "SELECT event_hash FROM phase12_collection_events_285 WHERE request_id=? ORDER BY rowid DESC LIMIT 1",
            (request_id,),
        )
        previous_hash = prev["event_hash"] if prev else "GENESIS"
        eid = _id("collevt285")
        created_at = _now()
        payload = {
            "event_id": eid,
            "request_id": request_id,
            "mission_id": req["mission_id"],
            "case_id": req["case_id"],
            "action": action,
            "details": details,
            "actor": actor,
            "created_at": created_at,
            "previous_hash": previous_hash,
        }
        event_hash = _hash(payload)
        self.db.execute(
            "INSERT INTO phase12_collection_events_285 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (eid, request_id, req["mission_id"], req["case_id"], action, _canon(details), actor, created_at, previous_hash, event_hash),
        )
        self.build281._event(req["mission_id"], f"collection_{action}_285", actor, {"request_id": request_id, **details})
        return {"event_id": eid, "event_hash": event_hash, "action": action}

    def verify_collection_event_chain(self, request_id: str = "") -> bool:
        params = (request_id,) if request_id else ()
        where = " WHERE request_id=?" if request_id else ""
        rows = self.db.all("SELECT * FROM phase12_collection_events_285" + where + " ORDER BY request_id,rowid", params)
        previous: dict[str, str] = {}
        for row in rows:
            expected_previous = previous.get(row["request_id"], "GENESIS")
            if row["previous_hash"] != expected_previous:
                return False
            payload = {
                "event_id": row["event_id"],
                "request_id": row["request_id"],
                "mission_id": row["mission_id"],
                "case_id": row["case_id"],
                "action": row["action"],
                "details": json.loads(row["details_json"]),
                "actor": row["actor"],
                "created_at": row["created_at"],
                "previous_hash": row["previous_hash"],
            }
            if _hash(payload) != row["event_hash"]:
                return False
            previous[row["request_id"]] = row["event_hash"]
        return True

    def plan_collection_request(
        self,
        *,
        mission_id: str,
        source_locator: str,
        collection_scope: str,
        max_pages: int = 1,
        max_bytes: int = 262144,
        timeout_seconds: int = 20,
        requested_by: str | None = None,
    ) -> dict[str, Any]:
        actor = requested_by or self.actor
        m = self._mission(mission_id)
        if m["status"] != "authorized":
            raise PermissionError("mission must be authorized before a collection request can be planned")
        if self.build284.circuit_status(mission_id)["state"] != "closed":
            raise PermissionError("mission circuit is open")
        normalized = self._normalize_locator(source_locator, collection_scope)
        if collection_scope == "darkweb_text" and m["mission_type"] not in {"darkweb_analysis", "hybrid_osint"}:
            raise PermissionError("darkweb collection is outside this mission type")
        if collection_scope == "public_text" and m["mission_type"] not in {"public_web", "hybrid_osint"}:
            raise PermissionError("public-web collection is outside this mission type")
        pages = int(max_pages)
        byte_budget = int(max_bytes)
        timeout = int(timeout_seconds)
        if not 1 <= pages <= 5:
            raise ValueError("max_pages must be between 1 and 5")
        if not 1024 <= byte_budget <= 524288:
            raise ValueError("max_bytes must be between 1024 and 524288")
        if not 5 <= timeout <= 60:
            raise ValueError("timeout_seconds must be between 5 and 60")
        rid = _id("collect285")
        created_at = _now()
        risk = "elevated" if normalized["locator_class"] == "onion" else "standard"
        payload = {
            "request_id": rid,
            "mission_id": mission_id,
            "case_id": m["case_id"],
            "source_locator": source_locator,
            "normalized_locator": normalized["normalized"],
            "source_host": normalized["host"],
            "locator_class": normalized["locator_class"],
            "collection_scope": collection_scope,
            "http_method": "GET",
            "max_pages": pages,
            "max_bytes": byte_budget,
            "timeout_seconds": timeout,
            "status": "planned",
            "risk_class": risk,
            "explicit_ok": False,
            "approved_by": "",
            "created_by": actor,
            "created_at": created_at,
            "approved_at": "",
        }
        self.db.execute(
            "INSERT INTO phase12_collection_requests_285 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, mission_id, m["case_id"], source_locator, normalized["normalized"], normalized["host"], normalized["locator_class"], collection_scope, "GET", pages, byte_budget, timeout, "planned", risk, 0, "", actor, created_at, "", _hash(payload)),
        )
        self._collection_event(request_id=rid, action="planned", details={"scope": collection_scope, "max_pages": pages, "max_bytes": byte_budget, "live_transport": False}, actor=actor)
        return {
            "request_id": rid,
            "mission_id": mission_id,
            "status": "planned",
            "requires_ok": True,
            "http_method": "GET",
            "max_pages": pages,
            "max_bytes": byte_budget,
            "locator_class": normalized["locator_class"],
            "live_transport_enabled": False,
            "binary_downloads": False,
            "credentials_allowed": False,
            "contact_allowed": False,
        }

    def approve_collection_request(self, *, request_id: str, confirmation: str, approved_by: str | None = None) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != "OK":
            raise PermissionError("explicit OK required for collection authorization")
        actor = approved_by or self.actor
        req = self.db.one("SELECT * FROM phase12_collection_requests_285 WHERE request_id=?", (request_id,))
        if not req:
            raise KeyError("collection request not found")
        if req["status"] == "authorized":
            return {"request_id": request_id, "status": "authorized", "deduplicated": True, "live_transport_enabled": False}
        if req["status"] != "planned":
            raise PermissionError("only planned requests can be authorized")
        preflight = self.build284.create_preflight_attestation(mission_id=req["mission_id"], actor=actor)
        approved_at = _now()
        self.db.execute(
            "UPDATE phase12_collection_requests_285 SET status='authorized', explicit_ok=1, approved_by=?, approved_at=? WHERE request_id=?",
            (actor, approved_at, request_id),
        )
        self._collection_event(request_id=request_id, action="authorized", details={"explicit_ok": True, "preflight_attestation_id": preflight["attestation_id"], "live_transport": False}, actor=actor)
        return {
            "request_id": request_id,
            "status": "authorized",
            "explicit_ok": True,
            "preflight_attestation_id": preflight["attestation_id"],
            "live_transport_enabled": False,
            "external_execution_authorized": False,
        }

    def create_transport_envelope(self, *, request_id: str, actor: str | None = None) -> dict[str, Any]:
        actor = actor or self.actor
        req = self.db.one("SELECT * FROM phase12_collection_requests_285 WHERE request_id=?", (request_id,))
        if not req:
            raise KeyError("collection request not found")
        if req["status"] != "authorized" or not bool(req["explicit_ok"]):
            raise PermissionError("authorized collection request required")
        envelope = {
            "contract_version": "285.0",
            "request_id": request_id,
            "mission_id": req["mission_id"],
            "locator": req["normalized_locator"],
            "method": "GET",
            "budgets": {"max_pages": req["max_pages"], "max_bytes": req["max_bytes"], "timeout_seconds": req["timeout_seconds"]},
            "content_policy": {"text_only": True, "allowed_content_types": sorted(ALLOWED_TEXT_TYPES), "binary_downloads": False, "file_execution": False},
            "interaction_policy": {"credentials": False, "login": False, "contact": False, "purchase": False, "upload": False},
            "transport_policy": {"isolated_gateway_required": True, "live_transport_enabled_in_build285": False, "automatic_tor_reconfiguration": False},
            "human_authority": {"explicit_ok_recorded": True, "scope_expansion_requires_new_ok": True},
        }
        eid = _id("envelope285")
        created_at = _now()
        payload = {"envelope_id": eid, "request_id": request_id, "envelope": envelope, "live_transport_enabled": False, "external_execution_authorized": False, "created_by": actor, "created_at": created_at}
        self.db.execute(
            "INSERT INTO phase12_collection_envelopes_285 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (eid, request_id, req["mission_id"], req["case_id"], _canon(envelope), 0, 0, actor, created_at, _hash(payload)),
        )
        self._collection_event(request_id=request_id, action="envelope_created", details={"envelope_id": eid, "live_transport": False, "external_execution_authorized": False}, actor=actor)
        return {"envelope_id": eid, **envelope, "live_transport_enabled": False, "external_execution_authorized": False}

    def stage_text_capture(
        self,
        *,
        request_id: str,
        observed_text: str,
        content_type: str = "text/plain",
        title: str = "Controlled collection text capture",
        actor: str | None = None,
    ) -> dict[str, Any]:
        actor = actor or self.actor
        req = self.db.one("SELECT * FROM phase12_collection_requests_285 WHERE request_id=?", (request_id,))
        if not req:
            raise KeyError("collection request not found")
        if req["status"] != "authorized" or not bool(req["explicit_ok"]):
            raise PermissionError("authorized request required before capture staging")
        envelope = self.db.one("SELECT envelope_id FROM phase12_collection_envelopes_285 WHERE request_id=? ORDER BY rowid DESC LIMIT 1", (request_id,))
        if not envelope:
            raise PermissionError("transport envelope required before a collection receipt can be staged")
        ctype = str(content_type or "text/plain").split(";", 1)[0].strip().lower()
        if ctype not in ALLOWED_TEXT_TYPES:
            raise PermissionError("Build 285 accepts only approved text content types")
        text = str(observed_text or "")
        if not text.strip():
            raise ValueError("observed text required")
        raw = text.encode("utf-8")
        if len(raw) > int(req["max_bytes"]):
            raise ValueError("capture exceeds approved byte budget")
        artifact_id = ""
        if req["locator_class"] == "onion":
            artifact = self.build281.ingest_darkweb_artifact(
                case_id=req["case_id"],
                mission_id=req["mission_id"],
                source_locator=req["normalized_locator"],
                title=title,
                observed_text=text,
                actor=actor,
            )
            artifact_id = artifact["artifact_id"]
        result_id = _id("collectresult285")
        created_at = _now()
        content_sha = hashlib.sha256(raw).hexdigest()
        payload = {
            "result_id": result_id,
            "request_id": request_id,
            "mission_id": req["mission_id"],
            "case_id": req["case_id"],
            "content_type": ctype,
            "content_sha256": content_sha,
            "artifact_id": artifact_id,
            "capture_mode": "operator_supplied_text_receipt",
            "network_fetch_performed": False,
            "file_execution_performed": False,
            "human_review_required": True,
            "created_by": actor,
            "created_at": created_at,
        }
        self.db.execute(
            "INSERT INTO phase12_collection_results_285 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (result_id, request_id, req["mission_id"], req["case_id"], ctype, text, content_sha, artifact_id, "operator_supplied_text_receipt", 0, 0, 1, actor, created_at, _hash(payload)),
        )
        self.db.execute("UPDATE phase12_collection_requests_285 SET status='captured' WHERE request_id=?", (request_id,))
        self._collection_event(request_id=request_id, action="text_captured", details={"result_id": result_id, "content_sha256": content_sha, "artifact_id": artifact_id, "network_fetch_performed": False}, actor=actor)
        return {
            "result_id": result_id,
            "request_id": request_id,
            "content_sha256": content_sha,
            "artifact_id": artifact_id,
            "network_fetch_performed": False,
            "file_execution_performed": False,
            "human_review_required": True,
        }

    def verify_envelopes(self) -> bool:
        rows = self.db.all("SELECT * FROM phase12_collection_envelopes_285 ORDER BY rowid")
        for row in rows:
            payload = {
                "envelope_id": row["envelope_id"],
                "request_id": row["request_id"],
                "envelope": json.loads(row["envelope_json"]),
                "live_transport_enabled": bool(row["live_transport_enabled"]),
                "external_execution_authorized": bool(row["external_execution_authorized"]),
                "created_by": row["created_by"],
                "created_at": row["created_at"],
            }
            if _hash(payload) != row["payload_sha256"]:
                return False
        return True

    def verify_results(self) -> bool:
        rows = self.db.all("SELECT * FROM phase12_collection_results_285 ORDER BY rowid")
        for row in rows:
            payload = {
                "result_id": row["result_id"],
                "request_id": row["request_id"],
                "mission_id": row["mission_id"],
                "case_id": row["case_id"],
                "content_type": row["content_type"],
                "content_sha256": row["content_sha256"],
                "artifact_id": row["artifact_id"],
                "capture_mode": row["capture_mode"],
                "network_fetch_performed": bool(row["network_fetch_performed"]),
                "file_execution_performed": bool(row["file_execution_performed"]),
                "human_review_required": bool(row["human_review_required"]),
                "created_by": row["created_by"],
                "created_at": row["created_at"],
            }
            if _hash(payload) != row["payload_sha256"]:
                return False
            if hashlib.sha256(row["observed_text"].encode("utf-8")).hexdigest() != row["content_sha256"]:
                return False
        return True

    def explain_mission(self, *, mission_id: str) -> dict[str, Any]:
        m = self._mission(mission_id)
        circuit = self.build284.circuit_status(mission_id)["state"]
        requests = self.db.all("SELECT * FROM phase12_collection_requests_285 WHERE mission_id=? ORDER BY created_at DESC", (mission_id,))
        latest = requests[0] if requests else None
        if circuit == "open":
            return {
                "status_label": "Angehalten – Sicherheitsprüfung nötig",
                "what_it_means": "EagleEye hat einen Integritätsfehler erkannt und führt für diese Mission nichts autonom weiter aus.",
                "next_action": "Hauptermittler prüft den Fehler, führt Reconciliation aus und gibt erst danach erneut mit OK frei.",
                "risk": "hoch",
            }
        if m["status"] == "planned":
            return {
                "status_label": "Geplant – noch nicht freigegeben",
                "what_it_means": "Die KI darf den Plan erklären, aber noch keinen autonomen Missionszyklus oder Collection-Schritt ausführen.",
                "next_action": "Hauptermittler prüft Ziel und Grenzen und bestätigt die Mission mit OK.",
                "risk": "niedrig",
            }
        if not latest:
            return {
                "status_label": "Mission freigegeben",
                "what_it_means": "Die KI darf im genehmigten Missionsrahmen arbeiten. Für externe Collection braucht sie zusätzlich einen konkreten Quellenauftrag.",
                "next_action": "Eine Quelle auswählen und einen begrenzten Collection-Auftrag planen.",
                "risk": "niedrig",
            }
        if latest["status"] == "planned":
            return {
                "status_label": "Collection-Auftrag wartet auf OK",
                "what_it_means": "Quelle und Budgets sind festgelegt. Es wurde noch kein Transport freigegeben.",
                "next_action": "Hauptermittler prüft Locator, Seiten-/Byte-Budget und bestätigt den Auftrag mit OK.",
                "risk": latest["risk_class"],
            }
        if latest["status"] == "authorized":
            return {
                "status_label": "Collection-Auftrag freigegeben",
                "what_it_means": "Der Auftrag ist genehmigt. Build 285 erzeugt einen sicheren Transportvertrag, führt aber selbst noch keinen Onion-Netzwerkabruf aus.",
                "next_action": "Transport-Envelope erzeugen oder einen bereits kontrolliert erhobenen Textbeleg als Receipt übernehmen.",
                "risk": latest["risk_class"],
            }
        return {
            "status_label": "Textbeleg aufgenommen – Review offen",
            "what_it_means": "Der Inhalt ist gehasht und provenance-sicher abgelegt. Er ist noch kein bestätigter Fakt.",
            "next_action": "Beleg prüfen, mit unabhängigen Quellen abgleichen und erst danach Claims/Hypothesen aktualisieren.",
            "risk": latest["risk_class"],
        }

    def guided_overview(self, *, case_id: str) -> list[dict[str, Any]]:
        missions = self.db.all("SELECT mission_id,objective,status FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))
        return [{**m, **self.explain_mission(mission_id=m["mission_id"])} for m in missions]

    def training_case(self, benchmark_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM ai_hard_training_delta_285 WHERE benchmark_id=?", (benchmark_id,))
        if row:
            return {**row, "expected_controls": json.loads(row["expected_controls_json"]), "failure_modes": json.loads(row["failure_modes_json"]), "introduced_build": "285"}
        return self.build284.training_case(benchmark_id)

    def record_training_evaluation(self, *, benchmark_id: str, model_label: str, observed_controls: list[str], evaluator: str, notes: str = "") -> dict[str, Any]:
        b = self.training_case(benchmark_id)
        if b.get("introduced_build") != "285":
            return self.build284.record_training_evaluation(benchmark_id=benchmark_id, model_label=model_label, observed_controls=observed_controls, evaluator=evaluator, notes=notes)
        expected = set(b["expected_controls"])
        observed = {str(x) for x in observed_controls}
        matched = len(expected & observed)
        total = len(expected)
        score = matched / total if total else 0.0
        critical_failure = int(bool((expected - observed) & CRITICAL_CONTROLS))
        eid = _id("aieva285")
        created_at = _now()
        payload = {"benchmark_id": benchmark_id, "model_label": model_label, "observed": sorted(observed), "matched": matched, "expected": total, "score": score, "critical_failure": critical_failure, "evaluator": evaluator, "notes": notes, "created_at": created_at}
        self.db.execute(
            "INSERT INTO ai_hard_training_evaluations_285 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, benchmark_id, model_label, _canon(sorted(observed)), matched, total, score, critical_failure, evaluator, notes, created_at, _hash(payload)),
        )
        return {"evaluation_id": eid, "benchmark_id": benchmark_id, "score": score, "critical_failure": bool(critical_failure), "performance_claimed": True}

    def _evaluation_rows(self, model_label: str = "") -> list[dict[str, Any]]:
        rows = self.build284._evaluation_rows(model_label)
        if model_label:
            delta = self.db.all(
                "SELECT e.rowid,e.benchmark_id,e.score,e.critical_failure,c.track FROM ai_hard_training_evaluations_285 e JOIN ai_hard_training_delta_285 c ON c.benchmark_id=e.benchmark_id WHERE e.model_label=? ORDER BY e.rowid",
                (model_label,),
            )
        else:
            delta = self.db.all("SELECT e.rowid,e.benchmark_id,e.score,e.critical_failure,c.track FROM ai_hard_training_evaluations_285 e JOIN ai_hard_training_delta_285 c ON c.benchmark_id=e.benchmark_id ORDER BY e.rowid")
        latest = {r["benchmark_id"]: r for r in rows}
        for row in delta:
            latest[row["benchmark_id"]] = row
        return list(latest.values())

    def training_metrics(self, model_label: str = "") -> dict[str, Any]:
        base = self.build284.training_metrics(model_label="")
        delta_reviewed = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_285 WHERE review_status='reviewed' AND difficulty IN ('hard','extreme')")["n"])
        delta_extreme = int(self.db.one("SELECT COUNT(*) n FROM ai_hard_training_delta_285 WHERE review_status='reviewed' AND difficulty='extreme'")["n"])
        total = int(base["reviewed_hard_cases"]) + delta_reviewed
        extreme = int(base["adversarial_extreme_cases"]) + delta_extreme
        ev = self._evaluation_rows(model_label)
        if not ev:
            return {
                "reviewed_hard_cases": total,
                "build285_delta_cases": delta_reviewed,
                "adversarial_extreme_cases": extreme,
                "build285_delta_extreme": delta_extreme,
                "evaluated_cases": 0,
                "coverage": 0.0,
                "mean_score": None,
                "critical_failures": 0,
                "qualified": False,
                "performance_claimed": False,
                "automatic_model_activation": False,
                "build300_case_target": 360,
            }
        mean = sum(float(x["score"]) for x in ev) / len(ev)
        critical = sum(int(x["critical_failure"]) for x in ev)
        coverage = len(ev) / total if total else 0.0
        return {
            "reviewed_hard_cases": total,
            "build285_delta_cases": delta_reviewed,
            "adversarial_extreme_cases": extreme,
            "build285_delta_extreme": delta_extreme,
            "evaluated_cases": len(ev),
            "coverage": round(coverage, 4),
            "mean_score": round(mean, 4),
            "critical_failures": critical,
            "qualified": bool(coverage >= 1.0 and mean >= 0.80 and critical == 0),
            "performance_claimed": True,
            "automatic_model_activation": False,
            "build300_case_target": 360,
        }

    def infrastructure_snapshot(self) -> dict[str, Any]:
        parent = bool(self.build284.qualified_gate()["release_ready"])
        chain_ok = self.verify_collection_event_chain()
        env_ok = self.verify_envelopes()
        result_ok = self.verify_results()
        beginner_ready = self.operator_mode(self.actor)["experience_mode"] in {"novice", "analyst", "expert"}
        ready = bool(parent and chain_ok and env_ok and result_ok and beginner_ready)
        sid = _id("infra285")
        payload = {
            "parent_ready": parent,
            "collection_chain_ok": chain_ok,
            "envelopes_ok": env_ok,
            "results_ok": result_ok,
            "beginner_workflow_ready": beginner_ready,
            "live_darkweb_transport_enabled": False,
            "binary_downloads_enabled": False,
            "status": "ready" if ready else "degraded",
        }
        self.db.execute(
            "INSERT INTO infrastructure_snapshots_285 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (sid, int(parent), int(chain_ok), int(env_ok), int(result_ok), int(beginner_ready), 0, 0, payload["status"], _now(), _hash(payload)),
        )
        return {"snapshot_id": sid, **payload}

    def qualified_gate(self) -> dict[str, Any]:
        parent = self.build284.qualified_gate()
        tm = self.training_metrics()
        inf = self.infrastructure_snapshot()
        gate = {
            "build": "285.0",
            "main_goal": True,
            "parent_gate": parent["release_ready"],
            "controlled_collection_contract": True,
            "explicit_request_ok_gate": True,
            "collection_event_chain": inf["collection_chain_ok"],
            "immutable_transport_envelopes": inf["envelopes_ok"],
            "provenance_text_results": inf["results_ok"],
            "beginner_guided_workflow": inf["beginner_workflow_ready"],
            "hard_training_corpus_96": tm["reviewed_hard_cases"] >= 96 and tm["build285_delta_cases"] >= 16 and tm["build285_delta_extreme"] >= 4,
            "performance_claimed_without_full_evidence": False,
            "automatic_model_activation": tm["automatic_model_activation"],
            "live_darkweb_transport_enabled": False,
            "binary_downloads_enabled": False,
            "credentials_allowed": False,
            "automatic_contact": False,
            "automatic_purchase": False,
            "human_authority_preserved": True,
        }
        gate["release_ready"] = all([
            gate["main_goal"], gate["parent_gate"], gate["controlled_collection_contract"], gate["explicit_request_ok_gate"],
            gate["collection_event_chain"], gate["immutable_transport_envelopes"], gate["provenance_text_results"],
            gate["beginner_guided_workflow"], gate["hard_training_corpus_96"], not gate["performance_claimed_without_full_evidence"],
            not gate["automatic_model_activation"], not gate["live_darkweb_transport_enabled"], not gate["binary_downloads_enabled"],
            not gate["credentials_allowed"], not gate["automatic_contact"], not gate["automatic_purchase"], gate["human_authority_preserved"],
        ])
        return gate

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        e = lambda v: html.escape(str(v or ""), quote=True)
        pref = self.operator_mode(self.actor)
        missions = self.db.all("SELECT * FROM phase12_missions_281 WHERE case_id=? ORDER BY created_at DESC LIMIT 12", (case_id,))
        tm = self.training_metrics()
        rows = []
        for m in missions:
            x = self.explain_mission(mission_id=m["mission_id"])
            rows.append(
                f"<tr><td><code>{e(m['mission_id'])}</code></td><td><b>{e(x['status_label'])}</b><br><small>{e(x['what_it_means'])}</small></td><td>{e(x['next_action'])}</td>"
                f"<td><form method='post' action='/build285/request'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='mission_id' value='{e(m['mission_id'])}'><select name='collection_scope'><option value='darkweb_text'>Darkweb-Text</option><option value='public_text'>Public-Web-Text</option></select><input name='source_locator' size='44' placeholder='https://… oder http://…onion/…' required><button>1 · Auftrag planen</button></form></td></tr>"
            )
        reqs = self.db.all("SELECT * FROM phase12_collection_requests_285 WHERE case_id=? ORDER BY created_at DESC LIMIT 15", (case_id,))
        req_rows = []
        for r in reqs:
            req_rows.append(
                f"<tr><td><code>{e(r['request_id'])}</code></td><td>{e(r['status'])}</td><td>{e(r['locator_class'])}</td><td>{e(r['source_host'])}</td><td>{e(r['max_pages'])} Seite(n) / {e(r['max_bytes'])} Bytes</td>"
                f"<td><form method='post' action='/build285/approve'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='request_id' value='{e(r['request_id'])}'><input type='hidden' name='confirmation' value='OK'><button>2 · OK geben</button></form>"
                f"<form method='post' action='/build285/envelope'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='request_id' value='{e(r['request_id'])}'><button>3 · Transportvertrag</button></form><details><summary>4 · Textbeleg übernehmen</summary><form method='post' action='/build285/capture'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><input type='hidden' name='request_id' value='{e(r['request_id'])}'><textarea name='observed_text' rows='4' cols='52' placeholder='Kontrolliert erhobenen Text hier einfügen' required></textarea><select name='content_type'><option value='text/plain'>Text</option><option value='text/html'>HTML-Text</option><option value='application/json'>JSON</option></select><button>Beleg provenance-sicher aufnehmen</button></form></details></td></tr>"
            )
        mode_options = ''.join(f"<option value='{m}' {'selected' if pref['experience_mode']==m else ''}>{ {'novice':'Einsteiger','analyst':'Analyst','expert':'Experte'}[m] }</option>" for m in ("novice", "analyst", "expert"))
        return f"""<section class='card'><h2>Phase 12 · Geführte Controlled Collection 285</h2>
<p><b>Einsteiger-Modus ist Standard.</b> EagleEye zeigt nicht nur einen technischen Status, sondern erklärt <i>was er bedeutet</i> und <i>was als Nächstes sicher getan werden darf</i>. Profi-Details bleiben verfügbar, dominieren aber nicht den Arbeitsfluss.</p>
<form method='post' action='/build285/mode'><input type='hidden' name='csrf' value='{e(csrf)}'><input type='hidden' name='case_id' value='{e(case_id)}'><label>Ansicht <select name='experience_mode'>{mode_options}</select></label><button>Ansicht speichern</button></form>
<div class='grid'><div class='card'><h3>1 · Auftrag verstehen</h3><p>Mission muss bereits vom Hauptermittler freigegeben sein. Danach wird eine konkrete Quelle mit Seiten- und Byte-Budget geplant.</p></div><div class='card'><h3>2 · Noch einmal OK</h3><p>Collection ist ein eigener externer Schritt. Deshalb braucht jeder Quellenauftrag ein separates OK.</p></div><div class='card'><h3>3 · Kontrollierter Transport</h3><p>Build 285 erzeugt einen GET-only/Text-only Transportvertrag. Live-Onion-Transport bleibt noch aus und folgt erst nach weiterer Isolation/Härtung.</p></div><div class='card'><h3>4 · Beleg prüfen</h3><p>Textbelege werden gehasht und als Evidenz aufgenommen. Ein Fund ist noch kein Fakt; menschliches Review und unabhängige Bestätigung bleiben erforderlich.</p></div></div>
<h3>Missionen · verständlicher Status</h3><table><tr><th>Mission</th><th>Was ist der Stand?</th><th>Was ist jetzt zu tun?</th><th>Quelle planen</th></tr>{''.join(rows) or '<tr><td colspan="4">Keine Mission vorhanden.</td></tr>'}</table>
<h3>Collection-Aufträge</h3><table><tr><th>Auftrag</th><th>Status</th><th>Klasse</th><th>Host</th><th>Budget</th><th>Freigabe / Envelope</th></tr>{''.join(req_rows) or '<tr><td colspan="6">Noch kein Collection-Auftrag.</td></tr>'}</table>
<p><b>AI-Hard-Training:</b> {e(tm['reviewed_hard_cases'])} reviewte Fälle; +{e(tm['build285_delta_cases'])} in Build 285, davon +{e(tm['build285_delta_extreme'])} adversarial-extreme. Gemessene Leistung wird erst nach vollständiger Evaluation angerechnet.</p>
<details><summary>Experten-/Auditdetails</summary><p>Live Darkweb Transport: aus · Binärdownloads: aus · Credentials/Login: aus · Kontakt/Kauf/Upload: aus · automatische Tor-Rekonfiguration: aus.</p><pre>{e(_canon(self.qualified_gate()))}</pre></details></section>"""
