from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts

_TOKEN_RE = re.compile(r"[\w@.+:/-]{2,}", re.UNICODE)
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 ()/.-]{5,24}$")
_USERNAME_RE = re.compile(r"^@?[A-Za-z0-9][A-Za-z0-9_.-]{1,63}$")
_INJECTION_RE = re.compile(r"(?i)(ignore (?:all|previous) instructions|system prompt|developer message|execute .*tool|do not cite|ignoriere .*anweisung|führe .*befehl aus)")
_RISK = {"low": 0, "elevated": 1, "high": 2, "critical": 3}
_COST = {"local": 1.0, "local-import": .95, "public-browser": .72, "free_public": .9, "provider-dependent": .45, "unknown": .5}


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _loads(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except Exception:
        return default


def _text(value: Any, limit: int = 40_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _clamp(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


def _tokens(value: Any) -> set[str]:
    return {x.casefold() for x in _TOKEN_RE.findall(_text(value, 100_000))}


def _ascii(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


class Build226SourceIntelligenceAlgorithmService:
    """Explainable, human-governed source selection for PersonOSINT.

    Build 226 ranks sources by information need, target compatibility, observed
    reliability, provenance, independence, language/country fit, cost, latency,
    identity-error risk and case OPSEC. It prepares recommendations only; it does
    not execute a source or confirm an identity.
    """

    BUILD = "226.0"
    ALGORITHM = "source_intelligence_explainable_v1"
    WEIGHTS = {
        "relevance": .22, "information_gain": .18, "precision": .10, "recall": .07,
        "provenance": .10, "freshness": .05, "independence": .07, "locale": .05,
        "stability": .05, "latency": .03, "cost": .03, "opsec": .05,
    }

    SOURCE_HINTS: dict[str, dict[str, Any]] = {
        "local_case_evidence": dict(group="case_internal", countries=["global"], languages=["mul"], precision=.92, recall=.72, provenance=.98, identity_risk=.12, cost="local"),
        "local_entity_resolution": dict(group="case_internal", countries=["global"], languages=["mul"], precision=.80, recall=.72, provenance=.92, identity_risk=.30, cost="local"),
        "local_document_analysis": dict(group="case_documents", countries=["global"], languages=["mul"], precision=.82, recall=.78, provenance=.94, identity_risk=.22, cost="local"),
        "firefox_public_web": dict(group="open_web", countries=["global"], languages=["mul"], precision=.48, recall=.85, provenance=.58, identity_risk=.58, cost="public-browser"),
        "digital_identity_pack_218": dict(group="username_discovery", countries=["global"], languages=["mul"], precision=.66, recall=.82, provenance=.62, identity_risk=.62, cost="free_public"),
        "github_public": dict(group="username_discovery", countries=["global"], languages=["mul"], precision=.78, recall=.55, provenance=.82, identity_risk=.35, cost="free_public"),
        "gravatar_public": dict(group="email_profile_discovery", countries=["global"], languages=["mul"], precision=.72, recall=.32, provenance=.72, identity_risk=.42, cost="free_public"),
        "wikidata_public": dict(group="wikimedia", countries=["global"], languages=["mul"], precision=.76, recall=.58, provenance=.84, identity_risk=.36, cost="free_public"),
        "sherlock_local": dict(group="username_discovery", countries=["global"], languages=["mul"], precision=.62, recall=.78, provenance=.55, identity_risk=.70, cost="local"),
        "whatsmyname_local": dict(group="username_discovery", countries=["global"], languages=["mul"], precision=.64, recall=.74, provenance=.58, identity_risk=.68, cost="local"),
        "wayback_pack_220": dict(group="internet_archive", countries=["global"], languages=["mul"], precision=.90, recall=.55, provenance=.92, identity_risk=.20, cost="free_public"),
        "wayback_public": dict(group="internet_archive", countries=["global"], languages=["mul"], precision=.90, recall=.55, provenance=.92, identity_risk=.20, cost="free_public"),
        "gleif_pack_220": dict(group="official_registry", countries=["global"], languages=["mul"], precision=.90, recall=.60, provenance=.96, identity_risk=.30, cost="free_public"),
        "gleif_public": dict(group="official_registry", countries=["global"], languages=["mul"], precision=.90, recall=.60, provenance=.96, identity_risk=.30, cost="free_public"),
        "exiftool_pack_220": dict(group="local_metadata", countries=["global"], languages=["mul"], precision=.76, recall=.66, provenance=.88, identity_risk=.38, cost="local"),
        "exiftool_local": dict(group="local_metadata", countries=["global"], languages=["mul"], precision=.76, recall=.66, provenance=.88, identity_risk=.38, cost="local"),
        "archivebox_pack_220": dict(group="case_archives", countries=["global"], languages=["mul"], precision=.90, recall=.58, provenance=.98, identity_risk=.18, cost="local-import"),
        "archivebox_import": dict(group="case_archives", countries=["global"], languages=["mul"], precision=.90, recall=.58, provenance=.98, identity_risk=.18, cost="local-import"),
    }

    def __init__(self, db: Any, audit: Any, *, consolidation: Any, planner: Any, reliability: Any,
                 source_pack1: Any, source_pack2: Any, retrieval: Any, conversation: Any,
                 identity_ai: Any, workspace: Any, actor: str = "local-analyst") -> None:
        self.db, self.audit = db, audit
        self.consolidation, self.planner, self.reliability = consolidation, planner, reliability
        self.source_pack1, self.source_pack2, self.retrieval = source_pack1, source_pack2, retrieval
        self.conversation, self.identity_ai, self.workspace = conversation, identity_ai, workspace
        self.actor = actor
        self.seed_profiles()
        self.consolidation._source_intelligence_v1 = self
        self.planner._source_intelligence_v1 = self

    # ---------- catalog ----------
    def seed_profiles(self) -> dict[str, Any]:
        now = now_ts(); sources: dict[str, dict[str, Any]] = {}
        for row in self.planner.catalog(active_only=False):
            sources[row["source_key"]] = {
                "source_key": row["source_key"], "title": row["title"], "route_class": row["route_class"],
                "adapter_family": row["adapter_type"], "target_types": row["input_types"],
                "expected_outputs": row["expected_outputs"], "network_capable": bool(row["network_capable"]),
                "requires_auth": bool(row["requires_auth"]), "active": bool(row["active"]),
                "health_state": row["health_status"], "opsec_risk": row["opsec_risk"],
                "notes": row["notes"], "cost_class": row["estimated_cost"],
            }
        for row in self.db.all("SELECT * FROM digital_source_adapters_218 ORDER BY adapter_key"):
            sources[row["adapter_key"]] = {
                "source_key": row["adapter_key"], "title": row["title"], "route_class": "social_username" if "username" in _loads(row["target_types_json"], []) else "public_web",
                "adapter_family": "build218", "target_types": _loads(row["target_types_json"], []),
                "expected_outputs": ["digital_identity_candidate", "evidence"], "network_capable": bool(row["network_capable"]),
                "requires_auth": row["auth_mode"] not in {"none", "none_legacy_public_json", "optional_env:GITHUB_TOKEN"},
                "active": bool(row["active"]), "health_state": row["health_status"], "opsec_risk": row["opsec_risk"],
                "notes": row["notes"], "cost_class": "local" if row["adapter_kind"] == "local_cli" else "free_public",
            }
        for row in self.db.all("SELECT * FROM source_adapters_220 ORDER BY adapter_key"):
            sources[row["adapter_key"]] = {
                "source_key": row["adapter_key"], "title": row["title"], "route_class": row["source_class"],
                "adapter_family": "build220", "target_types": _loads(row["target_types_json"], []),
                "expected_outputs": [row["source_class"] + "_candidate", "evidence"], "network_capable": bool(row["network_capable"]),
                "requires_auth": False, "active": bool(row["active"]), "health_state": row["health_state"],
                "opsec_risk": row["opsec_risk"], "notes": row["notes"],
                "cost_class": "local" if not row["network_capable"] else "free_public",
            }
        for key, src in sources.items():
            hint = self.SOURCE_HINTS.get(key, {})
            payload = {**src, "countries": hint.get("countries", ["global"]), "languages": hint.get("languages", ["mul"]),
                       "provenance_prior": hint.get("provenance", .6), "precision_prior": hint.get("precision", .55),
                       "recall_prior": hint.get("recall", .55), "identity_risk": hint.get("identity_risk", .5),
                       "source_group": hint.get("group", src["adapter_family"]), "created_at": now, "updated_at": now}
            existing = self.db.one("SELECT created_at FROM source_intelligence_profiles_226 WHERE source_key=?", (key,))
            created = (existing or {}).get("created_at", now)
            self.db.execute(
                """INSERT INTO source_intelligence_profiles_226 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(source_key) DO UPDATE SET title=excluded.title,route_class=excluded.route_class,adapter_family=excluded.adapter_family,
                   target_types_json=excluded.target_types_json,expected_outputs_json=excluded.expected_outputs_json,countries_json=excluded.countries_json,
                   languages_json=excluded.languages_json,network_capable=excluded.network_capable,requires_auth=excluded.requires_auth,active=excluded.active,
                   health_state=excluded.health_state,opsec_risk=excluded.opsec_risk,cost_class=excluded.cost_class,notes=excluded.notes,updated_at=excluded.updated_at,payload_sha256=excluded.payload_sha256""",
                (key, src["title"], src["route_class"], src["adapter_family"], dumps(src["target_types"]), dumps(src["expected_outputs"]),
                 dumps(payload["countries"]), dumps(payload["languages"]), int(src["network_capable"]), int(src["requires_auth"]), int(src["active"]),
                 src["health_state"], src["opsec_risk"], src["cost_class"], payload["provenance_prior"], payload["precision_prior"], payload["recall_prior"],
                 payload["identity_risk"], payload["source_group"], src["notes"], created, now, _hash(payload)),
            )
        return {"build": self.BUILD, "profiles": len(sources)}

    def catalog(self) -> list[dict[str, Any]]:
        self.seed_profiles()
        rows = self.db.all("SELECT * FROM source_intelligence_profiles_226 ORDER BY route_class,title")
        for row in rows:
            for field in ("target_types_json", "expected_outputs_json", "countries_json", "languages_json"):
                row[field.removesuffix("_json")] = _loads(row[field], [])
        fabric = getattr(self, "_source_fabric_236", None)
        if fabric is not None:
            try:
                rows = fabric.catalog_entries_for_ranker(rows)
            except Exception:
                # The Build-236 fabric is an enrichment/governance layer. A fabric
                # defect must never make the established Build-226 catalog unavailable.
                pass
        return rows

    # ---------- query intelligence ----------
    def rank_sources(self, *, case_id: str, objective: str, target_type: str = "unknown", target_value: str = "",
                     language: str = "und", countries: Sequence[str] = (), budget_class: str = "standard",
                     max_sources: int = 5, require_independence: bool = True, session_id: str = "", plan_id: str = "",
                     actor: str = "local-analyst", confirmation: str) -> dict[str, Any]:
        self._case(case_id)
        if confirmation != f"SOURCE INTELLIGENCE 226 {case_id} BERECHNEN":
            raise PermissionError("explicit approval required")
        if budget_class not in {"minimal", "standard", "broad"}:
            raise ValueError("invalid budget class")
        clean_objective = _INJECTION_RE.sub("[UNTRUSTED_INSTRUCTION_REMOVED]", _text(objective, 20_000)).strip()
        if len(clean_objective) < 5:
            raise ValueError("substantive objective required")
        inferred = self._infer_target_type(target_type, target_value or clean_objective)
        language = self._infer_language(language, target_value or clean_objective)
        countries = [self._norm_country(x) for x in countries if self._norm_country(x)][:8]
        threat = self.identity_ai._opsec(case_id)
        if threat.get("safety_lock"):
            raise PermissionError("case safety lock active")
        qid, now = new_id("sourceintel226"), now_ts()
        redacted_target = self._redact_target(inferred, target_value)
        stored_objective = clean_objective
        if inferred in {"email", "phone"} and target_value:
            stored_objective = stored_objective.replace(target_value, "[SENSITIVE_TARGET_REDACTED]")
        expansions = self._expand_query(clean_objective, inferred, target_value, language, countries)
        candidates = [self._score_source(case_id, source, clean_objective, inferred, language, countries, threat["threat_level"], budget_class)
                      for source in self.catalog()]
        candidates.sort(key=lambda x: (-x["final_score"], x["source_key"]))
        selected: list[dict[str, Any]] = []; groups: set[str] = set()
        for item in candidates:
            if not item["eligible"] or len(selected) >= max(1, min(int(max_sources), 12)):
                continue
            if require_independence and item["source_group"] in groups and any(x["source_group"] != item["source_group"] for x in candidates if x["eligible"] and x not in selected):
                continue
            item["selected"] = True; selected.append(item); groups.add(item["source_group"])
        if not selected:
            fallback = next((x for x in candidates if x["source_key"] == "local_case_evidence" and x["eligible"]), None)
            if fallback:
                fallback["selected"] = True; selected = [fallback]
        for pos, item in enumerate(candidates, 1):
            item["rank_position"] = pos
        stops = ["stop when the information gap is answered", "stop on OPSEC block or source quarantine", "stop when budget/max-source limit is reached"]
        if require_independence:
            stops.append("prefer two independent source groups before treating a claim as corroborated")
        payload = {"query_id": qid, "case_id": case_id, "session_id": session_id, "plan_id": plan_id, "objective": stored_objective,
                   "target_type": inferred, "target_value_redacted": redacted_target, "language": language, "countries": countries,
                   "budget_class": budget_class, "max_sources": max(1, min(int(max_sources), 12)), "require_independence": bool(require_independence),
                   "threat_level": threat["threat_level"], "status": "ranked", "selected_sources": [x["source_key"] for x in selected],
                   "stop_conditions": stops, "created_by": actor, "created_at": now}
        self.db.execute("INSERT INTO source_intelligence_queries_226 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (qid, case_id, session_id, plan_id, clean_objective, inferred, redacted_target, language, dumps(countries), budget_class,
                         payload["max_sources"], int(require_independence), threat["threat_level"], "ranked", dumps(payload["selected_sources"]), dumps(stops), actor, now, _hash(payload)))
        for exp in expansions:
            persisted_text = exp["text"]
            if inferred in {"email", "phone"}:
                persisted_text = "sha256:" + _hash(persisted_text)
            elif inferred == "url":
                persisted_text = self._redact_target("url", persisted_text)
            eid = new_id("expand226"); ep = {"expansion_id": eid, "query_id": qid, "case_id": case_id, **exp, "text": persisted_text, "created_at": now}
            self.db.execute("INSERT OR IGNORE INTO query_expansions_226 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (eid, qid, case_id, persisted_text, exp["type"], exp["language"], exp["country"], exp["confidence"], 1, now, _hash(ep)))
        for item in candidates:
            rid = new_id("ranking226"); explanation = item.pop("explanation")
            vals = (rid, qid, case_id, item["source_key"], item["rank_position"], int(item["eligible"]), int(item.get("selected", False)), dumps(item["exclusion_reasons"]),
                    item["relevance"], item["information_gain"], item["precision"], item["recall"], item["provenance"], item["freshness"], item["independence"],
                    item["locale"], item["stability"], item["latency"], item["cost"], item["opsec"], item["identity_risk_penalty"], item["final_score"], dumps(explanation), now,
                    _hash({**item, "explanation": explanation, "query_id": qid}))
            self.db.execute("INSERT INTO source_rankings_226 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vals)
            item["explanation"] = explanation
        self._event(case_id, "source_intelligence_ranked", "source_intelligence_query", qid,
                    {"target_type": inferred, "selected_sources": payload["selected_sources"], "threat_level": threat["threat_level"]}, actor)
        return {**payload, "algorithm": self.ALGORITHM, "query_expansions": expansions, "rankings": candidates,
                "selected": selected, "automatic_execution": False, "human_review_required": True, "identity_confirmed": False}

    def optimize_plan(self, *, plan_id: str, actor: str = "system") -> dict[str, Any]:
        plan = self.db.one("SELECT * FROM investigation_plans_217 WHERE plan_id=?", (plan_id,))
        if not plan:
            raise KeyError(plan_id)
        routes = self.db.all("SELECT * FROM source_routes_217 WHERE plan_id=? ORDER BY priority,route_id", (plan_id,))
        outputs = []
        for route in routes:
            result = self.rank_sources(case_id=plan["case_id"], session_id=plan["session_id"], plan_id=plan_id,
                objective=f"{plan['objective']}\n{route['purpose']}", target_type=route["target_type"], target_value=route["target_value"],
                language=plan["question_language"], budget_class="standard", max_sources=3, require_independence=True,
                actor=actor, confirmation=f"SOURCE INTELLIGENCE 226 {plan['case_id']} BERECHNEN")
            outputs.append({"route_id": route["route_id"], "query_id": result["query_id"], "selected_sources": result["selected_sources"]})
        return {"plan_id": plan_id, "optimized_routes": outputs, "automatic_execution": False}

    def review_ranking(self, *, query_id: str, decision: str, source_decisions: Mapping[str, Mapping[str, Any]],
                       rationale: str, reviewer: str, confirmation: str) -> dict[str, Any]:
        query = self._query(query_id)
        if confirmation != f"SOURCE INTELLIGENCE REVIEW 226 {query_id} ABSCHLIESSEN":
            raise PermissionError("explicit approval required")
        if reviewer == query["created_by"]:
            raise PermissionError("independent reviewer required")
        if decision not in {"approved", "changes_requested", "rejected"}:
            raise ValueError("invalid review decision")
        if len(_text(rationale, 5000).strip()) < 12:
            raise ValueError("substantive rationale required")
        valid = {x["source_key"] for x in self.db.all("SELECT source_key FROM source_rankings_226 WHERE query_id=?", (query_id,))}
        clean: dict[str, dict[str, str]] = {}; preferred: list[str] = []; rejected: list[str] = []
        for key, raw in source_decisions.items():
            if key not in valid:
                raise ValueError("unknown source in review")
            verdict = _text((raw or {}).get("decision"), 30)
            if verdict not in {"approved", "preferred", "rejected", "deferred"}:
                raise ValueError("invalid source decision")
            reason = _text((raw or {}).get("reason") or rationale, 3000)
            clean[key] = {"decision": verdict, "reason": reason}
            if verdict == "preferred": preferred.append(key)
            if verdict == "rejected": rejected.append(key)
        training = self.conversation.create_training_example(
            case_id=query["case_id"], task_type="source_routing", language=query["language"], difficulty="source_intelligence_preference",
            input_payload={"objective": query["objective"], "target_type": query["target_type"], "rankings": self.list_rankings(query_id)},
            expected_output={"decision": decision, "source_decisions": clean, "rationale": rationale}, evidence_refs=[],
            negative_constraints=["do not route to quarantined sources", "do not equate username match with identity", "respect OPSEC and source independence"],
            label="source_routing_preference", rationale=rationale, created_by=reviewer,
            confirmation=f"TRAINING EXAMPLE 216 {query['case_id']} ANLEGEN")
        rid, now = new_id("review226"), now_ts(); payload = {"review_id": rid, "query_id": query_id, "case_id": query["case_id"],
            "decision": decision, "source_decisions": clean, "rationale": rationale, "training_example_id": training["example_id"], "reviewer": reviewer, "reviewed_at": now}
        self.db.execute("INSERT INTO source_routing_reviews_226 VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (rid, query_id, query["case_id"], decision, dumps(clean), _text(rationale, 5000), training["example_id"], reviewer, now, _hash(payload)))
        top = (self.list_rankings(query_id) or [{}])[0].get("source_key", "")
        for pref in preferred:
            pid = new_id("pref226"); rejected_key = next((x for x in rejected if x != pref), top if top != pref else "")
            context = {"objective": query["objective"], "target_type": query["target_type"], "language": query["language"], "threat_level": query["threat_level"]}
            pp = {"preference_id": pid, "case_id": query["case_id"], "query_id": query_id, "preferred_source_key": pref, "rejected_source_key": rejected_key,
                  "context": context, "rationale": rationale, "reviewer": reviewer, "created_at": now}
            self.db.execute("INSERT INTO source_routing_preferences_226 VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (pid, query["case_id"], query_id, pref, rejected_key, dumps(context), _text(rationale, 5000), reviewer, now, _hash(pp)))
        self._event(query["case_id"], "source_intelligence_reviewed", "source_intelligence_query", query_id,
                    {"decision": decision, "preferred": preferred, "training_example_id": training["example_id"]}, reviewer)
        return {**payload, "preferred_sources": preferred, "training_example_id": training["example_id"], "automatic_model_update": False}

    def list_rankings(self, query_id: str) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT r.*,p.title,p.route_class,p.source_group FROM source_rankings_226 r JOIN source_intelligence_profiles_226 p ON p.source_key=r.source_key WHERE r.query_id=? ORDER BY r.rank_position", (query_id,))
        for row in rows:
            row["exclusion_reasons"] = _loads(row["exclusion_reasons_json"], [])
            row["explanation"] = _loads(row["explanation_json"], {})
        return rows

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        return {"build": self.BUILD, "case_id": case_id, "profiles": self.catalog(),
                "queries": self.db.all("SELECT * FROM source_intelligence_queries_226 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,)),
                "reviews": self.db.all("SELECT * FROM source_routing_reviews_226 WHERE case_id=? ORDER BY reviewed_at DESC LIMIT 20", (case_id,)),
                "preferences": self.db.all("SELECT * FROM source_routing_preferences_226 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,))}

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        data = self.dashboard(case_id=case_id); esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
        rows = "".join(f"<tr><td><code>{esc(x['query_id'])}</code></td><td>{esc(x['target_type'])}</td><td>{esc(x['language'])}</td><td>{esc(', '.join(_loads(x['selected_sources_json'], [])))}</td><td>{esc(x['threat_level'])}</td></tr>" for x in data["queries"]) or "<tr><td colspan='5'>Noch keine Source-Intelligence-Abfrage.</td></tr>"
        panel = f"""
<section class='card' id='build226_source_intelligence'><h2>Source Intelligence Algorithm · Build 226</h2>
<p>Erklärbare Quellenwahl nach Ermittlungsziel, Identifier, Sprache, Land, Reliability, Provenance, Unabhängigkeit, Kosten und OPSEC. Keine Quelle wird automatisch ausgeführt.</p>
<div class='grid two'><div><h3>Quellenstrategie berechnen</h3><form method='post' action='/build226/rank'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='session_id' placeholder='Chat-Session-ID optional'><select name='target_type'><option>unknown</option><option>name</option><option>alias</option><option>username</option><option>email</option><option>phone</option><option>organization</option><option>location</option><option>url</option><option>document</option><option>image</option></select><input name='target_value' placeholder='Zielwert'><input name='language' value='de'><input name='countries' placeholder='DE, IL, US'><select name='budget_class'><option>minimal</option><option selected>standard</option><option>broad</option></select><input name='max_sources' type='number' min='1' max='12' value='5'><textarea name='objective' rows='5' placeholder='Konkrete Ermittlungsfrage' required></textarea><button>Quellenranking berechnen</button></form></div>
<div><h3>Ranking unabhängig prüfen</h3><form method='post' action='/build226/review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='query_id' placeholder='Query-ID' required><select name='decision'><option>approved</option><option>changes_requested</option><option>rejected</option></select><textarea name='source_decisions_json' rows='5' placeholder='{{"github_public":{{"decision":"preferred","reason":"..."}}}}' required></textarea><textarea name='rationale' rows='4' placeholder='Begründung' required></textarea><button>Review und Trainingssignal speichern</button></form></div></div>
<div class='table-wrap'><table><thead><tr><th>Query</th><th>Zieltyp</th><th>Sprache</th><th>Ausgewählt</th><th>OPSEC</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>"""
        return panel

    # ---------- scoring ----------
    def _score_source(self, case_id: str, source: Mapping[str, Any], objective: str, target_type: str, language: str,
                      countries: Sequence[str], threat_level: str, budget_class: str) -> dict[str, Any]:
        target_types = source["target_types"]; exclusions: list[str] = []
        if target_type not in target_types and "unknown" not in target_types:
            exclusions.append("unsupported_target_type")
        if not bool(source["active"]): exclusions.append("inactive")
        if source["health_state"] in {"quarantined", "unavailable", "contract_failed"}: exclusions.append("source_unhealthy")
        max_risk = {"low": 2, "elevated": 1, "high": 0, "critical": 0}.get(threat_level, 0)
        if _RISK.get(source["opsec_risk"], 3) > max_risk: exclusions.append("opsec_risk_above_case_limit")
        if budget_class == "minimal" and source["cost_class"] in {"provider-dependent", "unknown"}: exclusions.append("budget_exceeded")
        fabric_info: dict[str, Any] = {"managed": False, "eligible": True, "reason": "build236_not_initialized"}
        fabric = getattr(self, "_source_fabric_236", None)
        if fabric is not None:
            try:
                fabric_info = fabric.ranking_constraint(source_key=source["source_key"])
                exclusions.extend(x for x in fabric_info.get("reasons", []) if x not in exclusions)
            except Exception as exc:
                fabric_info = {"managed": False, "eligible": True, "reason": "source_fabric_error", "error_type": type(exc).__name__}
        reliability = self._dynamic_reliability(source["source_key"], source)
        if reliability["state"] == "quarantined": exclusions.append("quarantined")
        relevance = 1.0 if target_type in target_types else .55 if "unknown" in target_types else .15
        capability_tokens = _tokens(" ".join(source["expected_outputs"]) + " " + source["route_class"] + " " + source["title"])
        objective_tokens = _tokens(objective)
        relevance = _clamp(relevance * .8 + (len(capability_tokens & objective_tokens) / max(1, len(objective_tokens))) * .6)
        prior_runs, successes, results = self._case_usage(case_id, source["source_key"])
        novelty = 1.0 if prior_runs == 0 else max(.25, 1.0 - min(prior_runs, 8) * .08)
        information_gain = _clamp((source["recall_prior"] * .55 + novelty * .45) * (1.0 if results == 0 else .88))
        locale = self._locale_score(source, language, countries)
        independence = 1.0
        precision = _clamp(reliability.get("precision", source["precision_prior"]), source["precision_prior"])
        recall = _clamp(reliability.get("recall", source["recall_prior"]), source["recall_prior"])
        provenance = _clamp(reliability.get("provenance", source["provenance_prior"]), source["provenance_prior"])
        freshness = _clamp(reliability.get("freshness", .6), .6)
        stability = _clamp(reliability.get("stability", .55), .55)
        latency = _clamp(reliability.get("latency", .65), .65)
        cost = _COST.get(source["cost_class"], .5)
        opsec = {"low": 1.0, "elevated": .78, "high": .48, "critical": .18}.get(source["opsec_risk"], .4)
        identity_penalty = _clamp(source["identity_risk"])
        components = {"relevance": relevance, "information_gain": information_gain, "precision": precision, "recall": recall,
                      "provenance": provenance, "freshness": freshness, "independence": independence, "locale": locale,
                      "stability": stability, "latency": latency, "cost": cost, "opsec": opsec}
        adaptive_info: dict[str, Any] = {"active": False, "reason": "build231_not_initialized"}
        adaptive = getattr(self, "_adaptive_learning_v1", None)
        if adaptive is not None:
            try:
                adaptive_info = adaptive.ranking_adjustment(
                    source_key=source["source_key"], target_type=target_type, language=language,
                    countries=countries, threat_level=threat_level,
                )
            except Exception as exc:
                # Build 231 is an optional bounded feedback layer. A malformed policy
                # must never make the canonical Build-226 ranker unavailable.
                adaptive_info = {"active": False, "reason": "adaptive_policy_error", "error_type": type(exc).__name__}
        if adaptive_info.get("active"):
            components["opsec"] = _clamp(components["opsec"] - float(adaptive_info.get("opsec_penalty") or 0.0), components["opsec"])
            if adaptive_info.get("hard_block"):
                exclusions.append("adaptive_opsec_policy_block")
        final = sum(components[k] * self.WEIGHTS[k] for k in self.WEIGHTS) - identity_penalty * .07
        final += float(adaptive_info.get("score_delta") or 0.0) if adaptive_info.get("active") else 0.0
        if exclusions: final = min(final, .12)
        explanation = {"positive": [k for k, v in components.items() if v >= .8], "weaknesses": [k for k, v in components.items() if v < .5],
                       "exclusions": exclusions, "prior_runs": prior_runs, "successful_runs": successes, "prior_results": results,
                       "candidate_only": True, "identity_limit": "source result never confirms identity automatically",
                       "adaptive_source_learning_231": adaptive_info, "source_fabric_236": fabric_info}
        return {"source_key": source["source_key"], "title": source["title"], "route_class": source["route_class"], "source_group": source["source_group"],
                "eligible": not exclusions, "selected": False, "exclusion_reasons": exclusions, **components,
                "identity_risk_penalty": identity_penalty, "final_score": round(max(0.0, final), 6), "explanation": explanation}

    def _dynamic_reliability(self, key: str, source: Mapping[str, Any]) -> dict[str, Any]:
        if self._table_exists("source_reliability_profiles_219"):
            row = self.db.one("SELECT * FROM source_reliability_profiles_219 WHERE adapter_key=?", (key,))
            if row:
                q = _loads(row.get("quality_json"), {})
                return {"state": row["state"], "precision": q.get("precision_score"), "recall": q.get("recall_score"), "provenance": q.get("provenance_quality"),
                        "freshness": q.get("freshness"), "stability": q.get("parser_stability"), "latency": q.get("latency_score")}
        if self._table_exists("source_adapters_220"):
            row = self.db.one("SELECT * FROM source_adapters_220 WHERE adapter_key=?", (key,))
            if row:
                checks = self.db.all("SELECT * FROM source_health_checks_220 WHERE adapter_key=? ORDER BY checked_at DESC LIMIT 20", (key,))
                healthy = sum(x["status"] in {"healthy", "degraded"} for x in checks)
                stability = healthy / len(checks) if checks else .55
                latencies = [int(x["latency_ms"]) for x in checks if int(x["latency_ms"]) > 0]
                med = sorted(latencies)[len(latencies)//2] if latencies else 0
                return {"state": row["health_state"], "stability": stability, "latency": 1.0 if not med or med < 1000 else .8 if med < 5000 else .5}
        return {"state": source["health_state"]}

    def _case_usage(self, case_id: str, key: str) -> tuple[int, int, int]:
        runs = successes = results = 0
        if self._table_exists("digital_source_runs_218"):
            row = self.db.one("SELECT COUNT(*) n,SUM(CASE WHEN status IN ('completed','not_found') THEN 1 ELSE 0 END) ok,SUM(result_count) results FROM digital_source_runs_218 WHERE case_id=? AND adapter_key=?", (case_id, key)) or {}
            runs += int(row.get("n") or 0); successes += int(row.get("ok") or 0); results += int(row.get("results") or 0)
        if self._table_exists("source_runs_220"):
            row = self.db.one("SELECT COUNT(*) n,SUM(CASE WHEN status IN ('completed','not_found') THEN 1 ELSE 0 END) ok,SUM(result_count) results FROM source_runs_220 WHERE case_id=? AND adapter_key=?", (case_id, key)) or {}
            runs += int(row.get("n") or 0); successes += int(row.get("ok") or 0); results += int(row.get("results") or 0)
        return runs, successes, results

    def _locale_score(self, source: Mapping[str, Any], language: str, countries: Sequence[str]) -> float:
        langs = set(source["languages"]); cn = set(source["countries"])
        lang_score = 1.0 if "mul" in langs or language in langs or language == "und" else .45
        country_score = 1.0 if not countries or "global" in cn or cn.intersection(countries) else .45
        return (lang_score + country_score) / 2

    def _expand_query(self, objective: str, target_type: str, target: str, language: str, countries: Sequence[str]) -> list[dict[str, Any]]:
        raw = _text(target or objective, 2000).strip(); variants: list[tuple[str, str, float]] = [(raw, "original", 1.0)]
        normalized = " ".join(unicodedata.normalize("NFKC", raw).split())
        if normalized != raw: variants.append((normalized, "unicode_normalized", .96))
        ascii_v = _ascii(normalized)
        if ascii_v and ascii_v.casefold() != normalized.casefold(): variants.append((ascii_v, "diacritic_variant", .72))
        if target_type in {"name", "alias", "organization"}:
            parts = [x for x in re.split(r"\s+", normalized) if x]
            if 2 <= len(parts) <= 4:
                variants.append((f"{parts[-1]}, {' '.join(parts[:-1])}", "surname_first", .72))
                variants.append((" ".join([parts[0]] + [p[0] + "." for p in parts[1:] if p]), "initials", .55))
                variants.append((f'"{normalized}"', "exact_phrase", .90))
        elif target_type in {"username", "alias"}:
            value = normalized.lstrip("@"); variants += [(value.casefold(), "username_lower", .95), ("@" + value, "username_at", .92)]
        elif target_type == "email" and _EMAIL_RE.match(normalized):
            local, domain = normalized.casefold().split("@", 1); variants += [(local, "email_localpart", .55), (domain, "email_domain", .48)]
        elif target_type == "phone":
            digits = re.sub(r"\D", "", normalized); variants += [(digits, "digits_only", .86), ("+" + digits, "international_candidate", .62)]
        elif target_type == "url":
            try:
                p = urlsplit(normalized); variants += [(p.hostname or "", "hostname", .82), ((p.hostname or "") + (p.path or ""), "host_path", .76)]
            except Exception: pass
        seen: set[str] = set(); out = []
        for value, kind, conf in variants:
            value = value.strip()
            if not value or value.casefold() in seen: continue
            seen.add(value.casefold()); out.append({"text": value, "type": kind, "language": language, "country": countries[0] if countries else "", "confidence": conf})
        return out[:20]

    def _infer_target_type(self, given: str, value: str) -> str:
        if given and given != "unknown": return given
        raw = value.strip()
        if _EMAIL_RE.match(raw): return "email"
        if raw.startswith(("http://", "https://")): return "url"
        if _PHONE_RE.match(raw): return "phone"
        if _USERNAME_RE.match(raw) and " " not in raw: return "username"
        return "name" if 1 < len(raw.split()) <= 5 else "unknown"

    def _infer_language(self, given: str, value: str) -> str:
        if given and given != "und": return given.casefold()[:12]
        if re.search(r"[\u0590-\u05ff]", value): return "he"
        if re.search(r"[\u0600-\u06ff]", value): return "ar"
        if re.search(r"[\u0400-\u04ff]", value): return "ru"
        return "de"

    def _norm_country(self, value: str) -> str:
        text = re.sub(r"[^A-Za-z]", "", _text(value, 20)).upper()
        return text[:3] if len(text) in {2,3} else ""

    def _redact_target(self, target_type: str, value: str) -> str:
        raw = _text(value, 2000)
        if target_type in {"email", "phone"}: return "sha256:" + _hash(raw)
        if target_type == "url":
            try:
                p = urlsplit(raw)
                host = p.hostname or ""
                if not host: return "invalid-url"
                try:
                    ip = ipaddress.ip_address(host)
                    if ip.is_private or ip.is_loopback: return "blocked-private-url"
                except ValueError: pass
                return f"{p.scheme}://{host}{p.path}"
            except Exception: return "invalid-url"
        return raw

    def _query(self, query_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM source_intelligence_queries_226 WHERE query_id=?", (query_id,))
        if not row: raise KeyError(query_id)
        return row

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)): raise KeyError(case_id)

    def _table_exists(self, name: str) -> bool:
        return bool(self.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)))

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> str:
        prev = self.db.one("SELECT event_hash FROM build226_events WHERE case_id=? ORDER BY created_at DESC,event_id DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "0" * 64
        eid, now = new_id("evt226"), now_ts(); safe = {k: v for k, v in dict(payload).items() if k not in {"prompt", "response", "content", "messages"}}
        body = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": safe, "previous_hash": previous, "created_at": now}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build226_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, actor, dumps(safe), previous, event_hash, now))
        if self.audit is not None and hasattr(self.audit, "log"): self.audit.log(event_type, object_type, object_id, case_id, safe)
        return eid
