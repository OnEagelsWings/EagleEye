from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[\w@.+-]+", (text or "").casefold()) if len(t) > 1}


class SearchIntelligence114Service:
    """Purpose-bound search planning and measurable query quality.

    Build 114 does not execute searches by itself. It creates and ranks approved
    search assignments, records outcomes, detects redundancy and learns only from
    case-local performance data. Human approval and provider policy remain outside
    and above this service.
    """

    INTENT_TYPES = {
        "identity", "employment", "organisation", "publication", "social_profile",
        "username", "image_context", "location_context", "business_role",
        "public_finance", "timeline", "contradiction", "source_confirmation", "other",
    }
    STATES = {"draft", "approved", "running", "completed", "cancelled", "blocked"}
    SENSITIVITY = {"normal", "elevated", "high"}
    BLOCKED_TERMS = {
        "password", "passwort", "credential", "credentials", "bank account", "bankkonto",
        "private address", "privatadresse", "home address", "wohnadresse", "doxx", "doxxing",
        "captcha bypass", "paywall bypass", "protected account", "geschütztes konto",
    }

    def __init__(self, db: Any, audit: Any = None, workflow: Any = None, kernel: Any = None) -> None:
        self.db = db
        self.audit = audit
        self.workflow = workflow
        self.kernel = kernel
        self.ensure_schema()

    def ensure_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS search_intents_114(
                intent_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                workflow_id TEXT,
                step_id TEXT,
                target_id TEXT,
                intent_type TEXT NOT NULL,
                question TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expected_information TEXT NOT NULL,
                success_criteria_json TEXT NOT NULL,
                exclusions_json TEXT NOT NULL,
                sensitivity TEXT NOT NULL,
                state TEXT NOT NULL,
                created_by TEXT NOT NULL,
                approved_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_search_intents114_case_state
                ON search_intents_114(case_id,state,created_at);
            CREATE TABLE IF NOT EXISTS search_queries_114(
                query_id TEXT PRIMARY KEY,
                intent_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                query_text TEXT NOT NULL,
                normalized_query TEXT NOT NULL,
                query_fingerprint TEXT NOT NULL,
                locale TEXT NOT NULL,
                rationale TEXT NOT NULL,
                estimated_gain REAL NOT NULL,
                estimated_cost REAL NOT NULL,
                estimated_risk REAL NOT NULL,
                novelty_score REAL NOT NULL,
                priority_score REAL NOT NULL,
                state TEXT NOT NULL,
                created_by TEXT NOT NULL,
                approved_by TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(intent_id,provider,query_fingerprint)
            );
            CREATE INDEX IF NOT EXISTS idx_search_queries114_priority
                ON search_queries_114(intent_id,state,priority_score DESC);
            CREATE TABLE IF NOT EXISTS search_runs_114(
                run_id TEXT PRIMARY KEY,
                query_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                started_by TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                request_cost REAL NOT NULL DEFAULT 0,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                error_class TEXT,
                notes TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS search_results_114(
                result_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                url_fingerprint TEXT NOT NULL,
                title TEXT NOT NULL,
                snippet TEXT NOT NULL,
                source_host TEXT NOT NULL,
                published_at TEXT,
                content_fingerprint TEXT,
                relevance REAL NOT NULL,
                novelty REAL NOT NULL,
                source_quality REAL NOT NULL,
                is_duplicate INTEGER NOT NULL DEFAULT 0,
                duplicate_of TEXT,
                candidate_only INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_search_results114_run
                ON search_results_114(run_id,relevance DESC,novelty DESC);
            CREATE INDEX IF NOT EXISTS idx_search_results114_urlfp
                ON search_results_114(url_fingerprint);
            CREATE TABLE IF NOT EXISTS search_outcomes_114(
                outcome_id TEXT PRIMARY KEY,
                run_id TEXT UNIQUE NOT NULL,
                total_results INTEGER NOT NULL,
                unique_results INTEGER NOT NULL,
                relevant_results INTEGER NOT NULL,
                new_entities INTEGER NOT NULL,
                new_relations INTEGER NOT NULL,
                confirmed_gaps INTEGER NOT NULL,
                independent_sources INTEGER NOT NULL,
                information_gain REAL NOT NULL,
                redundancy_rate REAL NOT NULL,
                precision_estimate REAL NOT NULL,
                analyst_rating REAL,
                analyst_notes TEXT NOT NULL,
                recorded_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS search_strategy_stats_114(
                strategy_key TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                intent_type TEXT NOT NULL,
                locale TEXT NOT NULL,
                runs INTEGER NOT NULL,
                mean_gain REAL NOT NULL,
                mean_precision REAL NOT NULL,
                mean_redundancy REAL NOT NULL,
                mean_cost REAL NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS search_events_114(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                case_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                event_type TEXT NOT NULL,
                object_type TEXT NOT NULL,
                object_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                event_hash TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.db.conn.commit()

    @staticmethod
    def normalize_query(query: str) -> str:
        text = re.sub(r"\s+", " ", (query or "").strip())
        return text.casefold()

    @staticmethod
    def canonicalize_url(url: str) -> str:
        parts = urlsplit((url or "").strip())
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("result URL must be public HTTP(S)")
        if parts.username or parts.password:
            raise ValueError("credentials in result URL are prohibited")
        host = parts.hostname.casefold().strip(".")
        if host in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("loopback result URL is prohibited")
        port = f":{parts.port}" if parts.port and not ((parts.scheme == "http" and parts.port == 80) or (parts.scheme == "https" and parts.port == 443)) else ""
        path = re.sub(r"/{2,}", "/", parts.path or "/")
        tracking = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}
        query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.casefold() not in tracking))
        return urlunsplit((parts.scheme.casefold(), host + port, path, query, ""))

    def _event(self, case_id: str, actor: str, event_type: str, object_type: str, object_id: str, payload: dict[str, Any]) -> None:
        event_id, ts = _id("sevt"), _now()
        row = self.db.one("SELECT event_hash FROM search_events_114 WHERE case_id=? ORDER BY sequence DESC LIMIT 1", (case_id,))
        previous = row["event_hash"] if row else "GENESIS"
        material = _json([event_id, case_id, actor, event_type, object_type, object_id, payload, previous, ts])
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        self.db.execute(
            "INSERT INTO search_events_114(event_id,case_id,actor,event_type,object_type,object_id,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (event_id, case_id, actor, event_type, object_type, object_id, _json(payload), previous, digest, ts),
        )
        if self.kernel:
            self.kernel.event(case_id, actor, event_type, object_type, object_id, payload)

    def create_intent(self, case_id: str, question: str, purpose: str, expected_information: str,
                      created_by: str, intent_type: str = "other", workflow_id: str | None = None,
                      step_id: str | None = None, target_id: str | None = None,
                      success_criteria: Iterable[str] | None = None,
                      exclusions: Iterable[str] | None = None, sensitivity: str = "normal") -> str:
        if intent_type not in self.INTENT_TYPES or sensitivity not in self.SENSITIVITY:
            raise ValueError("invalid intent type or sensitivity")
        combined = " ".join([question, purpose, expected_information, *list(exclusions or [])]).casefold()
        if any(term in combined for term in self.BLOCKED_TERMS):
            raise ValueError("search intent contains prohibited private or bypass scope")
        if not question.strip() or not purpose.strip() or not expected_information.strip():
            raise ValueError("question, purpose and expected information are required")
        intent_id, ts = _id("sint"), _now()
        self.db.execute(
            "INSERT INTO search_intents_114(intent_id,case_id,workflow_id,step_id,target_id,intent_type,question,purpose,expected_information,success_criteria_json,exclusions_json,sensitivity,state,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (intent_id, case_id, workflow_id, step_id, target_id, intent_type, question[:2000], purpose[:3000], expected_information[:3000], _json(list(success_criteria or [])), _json(list(exclusions or [])), sensitivity, "draft", created_by, ts, ts),
        )
        self._event(case_id, created_by, "SearchIntentCreated", "search_intent", intent_id, {"intent_type": intent_type})
        return intent_id

    def approve_intent(self, intent_id: str, approved_by: str) -> None:
        row = self.db.one("SELECT * FROM search_intents_114 WHERE intent_id=?", (intent_id,))
        if not row or row["state"] != "draft":
            raise ValueError("only draft intents can be approved")
        self.db.execute("UPDATE search_intents_114 SET state='approved',approved_by=?,updated_at=? WHERE intent_id=?", (approved_by, _now(), intent_id))
        self._event(row["case_id"], approved_by, "SearchIntentApproved", "search_intent", intent_id, {})

    def propose_query(self, intent_id: str, provider: str, query_text: str, rationale: str, created_by: str,
                      locale: str = "de-DE", estimated_gain: float = 0.5,
                      estimated_cost: float = 0.1, estimated_risk: float = 0.1) -> str:
        intent = self.db.one("SELECT * FROM search_intents_114 WHERE intent_id=?", (intent_id,))
        if not intent or intent["state"] not in {"draft", "approved", "running"}:
            raise ValueError("search intent is unavailable")
        normalized = self.normalize_query(query_text)
        if len(normalized) < 3 or len(normalized) > 500:
            raise ValueError("query length outside safe bounds")
        if any(term in normalized for term in self.BLOCKED_TERMS):
            raise ValueError("query contains prohibited private or bypass scope")
        fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        previous = self.db.all("SELECT normalized_query FROM search_queries_114 q JOIN search_intents_114 i ON i.intent_id=q.intent_id WHERE i.case_id=?", (intent["case_id"],))
        qt = _tokens(normalized)
        similarity = max((len(qt & _tokens(p["normalized_query"])) / max(1, len(qt | _tokens(p["normalized_query"]))) for p in previous), default=0.0)
        novelty = max(0.0, 1.0 - similarity)
        strategy = self.db.one("SELECT * FROM search_strategy_stats_114 WHERE strategy_key=?", (self._strategy_key(provider, intent["intent_type"], locale),))
        learned_gain = float(strategy["mean_gain"]) if strategy else 0.5
        gain = self._bound(0.65 * estimated_gain + 0.35 * learned_gain)
        cost, risk = self._bound(estimated_cost), self._bound(estimated_risk)
        priority = self._bound((0.50 * gain) + (0.30 * novelty) + (0.20 * (1 - cost)) - (0.25 * risk))
        query_id = _id("qry")
        self.db.execute(
            "INSERT INTO search_queries_114(query_id,intent_id,provider,query_text,normalized_query,query_fingerprint,locale,rationale,estimated_gain,estimated_cost,estimated_risk,novelty_score,priority_score,state,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (query_id, intent_id, provider[:100], query_text[:500], normalized, fingerprint, locale[:20], rationale[:3000], gain, cost, risk, novelty, priority, "draft", created_by, _now()),
        )
        self._event(intent["case_id"], created_by, "SearchQueryProposed", "search_query", query_id, {"priority": priority, "novelty": novelty})
        return query_id

    def approve_query(self, query_id: str, approved_by: str) -> None:
        row = self.db.one("SELECT q.*,i.case_id,i.state intent_state FROM search_queries_114 q JOIN search_intents_114 i ON i.intent_id=q.intent_id WHERE q.query_id=?", (query_id,))
        if not row or row["state"] != "draft" or row["intent_state"] != "approved":
            raise ValueError("query and intent must be approved in order")
        self.db.execute("UPDATE search_queries_114 SET state='approved',approved_by=? WHERE query_id=?", (approved_by, query_id))
        self._event(row["case_id"], approved_by, "SearchQueryApproved", "search_query", query_id, {})

    def start_run(self, query_id: str, actor: str) -> str:
        row = self.db.one("SELECT q.*,i.case_id FROM search_queries_114 q JOIN search_intents_114 i ON i.intent_id=q.intent_id WHERE q.query_id=?", (query_id,))
        if not row or row["state"] != "approved":
            raise ValueError("query requires approval")
        run_id = _id("srun")
        with self.db.conn:
            self.db.conn.execute("UPDATE search_queries_114 SET state='running' WHERE query_id=? AND state='approved'", (query_id,))
            self.db.conn.execute("INSERT INTO search_runs_114(run_id,query_id,provider,started_by,started_at,status) VALUES(?,?,?,?,?,'running')", (run_id, query_id, row["provider"], actor, _now()))
        self._event(row["case_id"], actor, "SearchRunStarted", "search_run", run_id, {"query_id": query_id})
        return run_id

    def record_results(self, run_id: str, results: Iterable[dict[str, Any]], actor: str) -> list[str]:
        run = self.db.one("SELECT r.*,i.case_id FROM search_runs_114 r JOIN search_queries_114 q ON q.query_id=r.query_id JOIN search_intents_114 i ON i.intent_id=q.intent_id WHERE r.run_id=?", (run_id,))
        if not run or run["status"] != "running":
            raise ValueError("run is not active")
        ids: list[str] = []
        for item in list(results)[:500]:
            canonical = self.canonicalize_url(str(item.get("url", "")))
            urlfp = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            contentfp = str(item.get("content_fingerprint") or "")[:128] or None
            dup = self.db.one("SELECT result_id FROM search_results_114 WHERE url_fingerprint=? OR (? IS NOT NULL AND content_fingerprint=?) ORDER BY created_at LIMIT 1", (urlfp, contentfp, contentfp))
            result_id = _id("sres")
            self.db.execute(
                "INSERT INTO search_results_114(result_id,run_id,canonical_url,url_fingerprint,title,snippet,source_host,published_at,content_fingerprint,relevance,novelty,source_quality,is_duplicate,duplicate_of,candidate_only,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
                (result_id, run_id, canonical, urlfp, str(item.get("title", ""))[:1000], str(item.get("snippet", ""))[:5000], urlsplit(canonical).hostname or "", item.get("published_at"), contentfp, self._bound(float(item.get("relevance", 0.5))), 0.0 if dup else self._bound(float(item.get("novelty", 0.7))), self._bound(float(item.get("source_quality", 0.5))), 1 if dup else 0, dup["result_id"] if dup else None, _now()),
            )
            ids.append(result_id)
        self._event(run["case_id"], actor, "SearchResultsRecorded", "search_run", run_id, {"count": len(ids)})
        return ids

    def complete_run(self, run_id: str, actor: str, duration_ms: int = 0, request_cost: float = 0.0,
                     new_entities: int = 0, new_relations: int = 0, confirmed_gaps: int = 0,
                     independent_sources: int = 0, analyst_rating: float | None = None,
                     analyst_notes: str = "") -> dict[str, float]:
        run = self.db.one("SELECT r.*,q.query_id,q.locale,i.case_id,i.intent_type FROM search_runs_114 r JOIN search_queries_114 q ON q.query_id=r.query_id JOIN search_intents_114 i ON i.intent_id=q.intent_id WHERE r.run_id=?", (run_id,))
        if not run or run["status"] != "running":
            raise ValueError("run is not active")
        stats = self.db.one("SELECT COUNT(*) total,SUM(CASE WHEN is_duplicate=0 THEN 1 ELSE 0 END) unique_n,SUM(CASE WHEN relevance>=0.6 THEN 1 ELSE 0 END) relevant_n FROM search_results_114 WHERE run_id=?", (run_id,))
        total = int(stats["total"] or 0); unique_n = int(stats["unique_n"] or 0); relevant = int(stats["relevant_n"] or 0)
        redundancy = 0.0 if total == 0 else 1 - (unique_n / total)
        precision = 0.0 if total == 0 else relevant / total
        structural_gain = min(1.0, (new_entities * 0.12) + (new_relations * 0.10) + (confirmed_gaps * 0.08) + (independent_sources * 0.10))
        information_gain = self._bound((0.40 * precision) + (0.25 * (1 - redundancy)) + (0.35 * structural_gain))
        outcome_id = _id("sout")
        with self.db.conn:
            self.db.conn.execute("UPDATE search_runs_114 SET status='completed',completed_at=?,request_cost=?,duration_ms=?,notes=? WHERE run_id=?", (_now(), max(0.0, request_cost), max(0, duration_ms), analyst_notes[:5000], run_id))
            self.db.conn.execute("UPDATE search_queries_114 SET state='completed' WHERE query_id=?", (run["query_id"],))
            self.db.conn.execute("INSERT INTO search_outcomes_114(outcome_id,run_id,total_results,unique_results,relevant_results,new_entities,new_relations,confirmed_gaps,independent_sources,information_gain,redundancy_rate,precision_estimate,analyst_rating,analyst_notes,recorded_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (outcome_id, run_id, total, unique_n, relevant, max(0,new_entities), max(0,new_relations), max(0,confirmed_gaps), max(0,independent_sources), information_gain, redundancy, precision, analyst_rating, analyst_notes[:5000], actor, _now()))
        self._update_strategy(run["provider"], run["intent_type"], run["locale"], information_gain, precision, redundancy, max(0.0, request_cost))
        self._event(run["case_id"], actor, "SearchRunCompleted", "search_run", run_id, {"information_gain": information_gain, "redundancy": redundancy})
        return {"information_gain": information_gain, "redundancy_rate": redundancy, "precision_estimate": precision}

    def ranked_queries(self, intent_id: str, include_drafts: bool = True) -> list[dict[str, Any]]:
        states = "('draft','approved')" if include_drafts else "('approved')"
        return self.db.all(f"SELECT * FROM search_queries_114 WHERE intent_id=? AND state IN {states} ORDER BY priority_score DESC,novelty_score DESC", (intent_id,))

    def intent_dashboard(self, intent_id: str) -> dict[str, Any]:
        intent = self.db.one("SELECT * FROM search_intents_114 WHERE intent_id=?", (intent_id,))
        if not intent:
            raise ValueError("intent not found")
        queries = self.db.all("SELECT * FROM search_queries_114 WHERE intent_id=? ORDER BY priority_score DESC", (intent_id,))
        outcomes = self.db.all("SELECT o.*,r.query_id FROM search_outcomes_114 o JOIN search_runs_114 r ON r.run_id=o.run_id JOIN search_queries_114 q ON q.query_id=r.query_id WHERE q.intent_id=? ORDER BY o.created_at", (intent_id,))
        return {
            "intent": intent,
            "queries": queries,
            "outcomes": outcomes,
            "recommendation": self._recommend(queries, outcomes),
            "human_control": {"execution": "explicit approval required", "scope_expansion": "not automatic", "results": "candidate only"},
        }

    def verify_event_chain(self, case_id: str) -> dict[str, Any]:
        rows = self.db.all("SELECT * FROM search_events_114 WHERE case_id=? ORDER BY sequence", (case_id,))
        previous = "GENESIS"
        for row in rows:
            payload = json.loads(row["payload_json"])
            material = _json([row["event_id"], row["case_id"], row["actor"], row["event_type"], row["object_type"], row["object_id"], payload, previous, row["created_at"]])
            digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if row["previous_hash"] != previous or row["event_hash"] != digest:
                return {"valid": False, "sequence": row["sequence"]}
            previous = row["event_hash"]
        return {"valid": True, "events": len(rows), "head": previous}

    def _update_strategy(self, provider: str, intent_type: str, locale: str, gain: float, precision: float, redundancy: float, cost: float) -> None:
        key = self._strategy_key(provider, intent_type, locale)
        old = self.db.one("SELECT * FROM search_strategy_stats_114 WHERE strategy_key=?", (key,))
        if old:
            n = int(old["runs"]); nn = n + 1
            vals = [(float(old[k]) * n + v) / nn for k, v in (("mean_gain",gain),("mean_precision",precision),("mean_redundancy",redundancy),("mean_cost",cost))]
            self.db.execute("UPDATE search_strategy_stats_114 SET runs=?,mean_gain=?,mean_precision=?,mean_redundancy=?,mean_cost=?,updated_at=? WHERE strategy_key=?", (nn,*vals,_now(),key))
        else:
            self.db.execute("INSERT INTO search_strategy_stats_114(strategy_key,provider,intent_type,locale,runs,mean_gain,mean_precision,mean_redundancy,mean_cost,updated_at) VALUES(?,?,?,?,1,?,?,?,?,?)", (key,provider,intent_type,locale,gain,precision,redundancy,cost,_now()))

    @staticmethod
    def _strategy_key(provider: str, intent_type: str, locale: str) -> str:
        return hashlib.sha256(f"{provider.casefold()}|{intent_type}|{locale.casefold()}".encode()).hexdigest()

    @staticmethod
    def _bound(value: float) -> float:
        if math.isnan(value) or math.isinf(value):
            raise ValueError("score must be finite")
        return max(0.0, min(1.0, value))

    @staticmethod
    def _recommend(queries: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> dict[str, Any]:
        completed = {o["query_id"] for o in outcomes}
        candidates = [q for q in queries if q["query_id"] not in completed and q["state"] in {"draft", "approved"}]
        if not candidates:
            return {"action": "review_or_close", "reason": "no unexecuted query remains"}
        best = max(candidates, key=lambda q: (q["priority_score"], q["novelty_score"]))
        return {"action": "consider_query", "query_id": best["query_id"], "priority_score": best["priority_score"], "reason": "highest expected gain after novelty, cost and risk adjustment"}
