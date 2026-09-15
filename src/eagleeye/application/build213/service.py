from __future__ import annotations

import hashlib
import html
import importlib
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urlsplit, urlunsplit

from eagleeye_pro.core.database import dumps, new_id, now_ts

_SECRET = re.compile(r"(?i)(authorization|cookie|token|secret|password|api[_-]?key|session|private[_-]?key)")
_USERNAME = re.compile(r"^[\w.\-]{1,80}$", re.UNICODE)
_STATES = {"found", "possible", "not_found", "blocked", "error"}
_REVIEWS = {"relevant", "not_relevant", "uncertain"}
_IDENTITY_RELATIONS = {"unknown", "possible_same_person", "not_same_person", "requires_entity_review"}
_THREATS = {"low", "elevated", "high", "critical"}


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


def _text(value: Any, limit: int = 100000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): ("[REDACTED]" if _SECRET.search(str(k)) else _redact(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"(?i)(authorization|cookie|token|secret|password|api[_-]?key|session)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", value[:100000])
    return value


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").casefold()
    except Exception:
        return ""


def _canonical_url(url: str) -> str:
    parsed = urlsplit(_text(url, 5000).strip())
    scheme = parsed.scheme.casefold()
    host = (parsed.hostname or "").casefold()
    if scheme not in {"http", "https"} or not host:
        raise ValueError("public http(s) URL required")
    netloc = host
    if parsed.port and not ((scheme == "http" and parsed.port == 80) or (scheme == "https" and parsed.port == 443)):
        netloc += f":{parsed.port}"
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))


class Build213SocialSourceFabricService:
    """Governed social source fabric for focused person OSINT.

    Build 213 does not execute third-party collectors from the application core.
    It imports reviewed site definitions, prepares public-browser tasks for the
    existing Firefox session, ingests candidate results with provenance, keeps
    translation and AI outputs reviewable, and enforces platform-specific OPSEC.
    """

    BUILD = "213.0"
    PROJECTS = (
        ("maigret", "Maigret", "https://github.com/soxoj/maigret", "MIT", "external_candidate_collector", True),
        ("sherlock", "Sherlock", "https://github.com/sherlock-project/sherlock", "MIT", "external_candidate_collector", True),
        ("whatsmyname", "WhatsMyName", "https://github.com/Arcade-Project/WhatsMyName", "MIT", "definition_import_reference", True),
        ("spiderfoot", "SpiderFoot", "https://github.com/smicallef/spiderfoot", "MIT", "isolated_collector_reference", True),
        ("argos_translate", "Argos Translate", "https://github.com/argosopentech/argos-translate", "MIT", "optional_offline_translation", False),
    )
    LANES = (
        ("sources", "Quellen & Adapter", "Quellenregister, Fixture-Tests, Parserqualität und False-Positive-Benchmarks"),
        ("ai_chat", "AI & Chat-Ermittler", "Fallbezogene Rechercheplanung, Quellenkritik und überprüfbare Antworten"),
        ("translation", "Fallübersetzung", "Originaltreue Übersetzung von Profil- und Inhaltsfragmenten mit Unsicherheiten"),
        ("opsec", "OPSEC & Ermittlerschutz", "Plattformbezogene Preflights, Falltrennung und sichere Browserübergaben"),
    )

    def __init__(self, db: Any, audit: Any, *, build212: Any, evidence: Any, social: Any, agents: Any, runtime: Any, base_dir: Any, actor: str = "system") -> None:
        self.db, self.audit = db, audit
        self.build212, self.evidence, self.social = build212, evidence, social
        self.agents, self.runtime = agents, runtime
        self.base_dir, self.actor = base_dir, actor

    # ---------------- foundation and parallel lanes ----------------
    def seed(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "BUILD 213 SOCIAL FABRIC ANLEGEN":
            raise PermissionError("explicit approval required")
        now = now_ts()
        policy = {
            "specialisation": "focused_person_osint",
            "investigator_leads": True,
            "ai_supports": True,
            "candidate_only": True,
            "automatic_identity_confirmation": False,
            "automatic_external_action": False,
            "third_party_code_bundled": False,
            "network_execution_from_core": False,
            "existing_firefox_new_tabs": True,
            "login_bypass": False,
            "anti_bot_bypass": False,
            "facts_inferences_hypotheses_separated": True,
            "original_language_preserved": True,
            "parallel_work_lanes": [x[0] for x in self.LANES],
        }
        self.db.execute("INSERT OR REPLACE INTO build213_policies VALUES(?,?,?,?,?)", ("default", dumps(policy), now, now, _hash(policy)))
        for pid, title, home, lic, mode, network in self.PROJECTS:
            payload = {"project_id": pid, "title": title, "homepage": home, "license": lic, "integration_mode": mode, "network_capable": network}
            self.db.execute(
                """INSERT OR IGNORE INTO social_projects_213 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, title, home, lic, mode, int(network), 0, 0, 0, 0, 0, 0, 0, "candidate-only; no bundled upstream code", now, now, _hash(payload)),
            )
        try:
            self.build212.seed(confirmation="BUILD 212 FOUNDATION ANLEGEN")
        except Exception:
            pass
        return {"build": self.BUILD, "projects": len(self.PROJECTS), "lanes": [x[0] for x in self.LANES], "policy": policy}

    def ensure_parallel_workspaces(self, *, case_id: str, owner: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"PARALLEL WORKSPACES 213 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        created = []
        for lane, title, objective in self.LANES:
            existing = self.db.one("SELECT * FROM parallel_workspaces_213 WHERE case_id=? AND lane_key=?", (case_id, lane))
            if existing:
                created.append(existing)
                continue
            wid, now = new_id("lane213"), now_ts()
            payload = {"workspace_id": wid, "case_id": case_id, "lane_key": lane, "title": title, "objective": objective, "status": "active", "owner": owner, "created_at": now}
            self.db.execute("INSERT INTO parallel_workspaces_213 VALUES(?,?,?,?,?,?,?,?,?,?)", (wid, case_id, lane, title, objective, "active", owner, now, now, _hash(payload)))
            self._event(case_id, "parallel_lane_created", "parallel_workspace", wid, payload, owner)
            created.append(payload)
        return {"case_id": case_id, "workspaces": created, "parallel": True, "automatic_execution": False}

    # ---------------- source definitions and benchmarks ----------------
    def import_definitions(self, *, project_id: str, dataset_version: str, source_hash: str, definitions: Sequence[Mapping[str, Any]], reviewer: str, notes: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL DEFINITIONS 213 {project_id} IMPORTIEREN":
            raise PermissionError("explicit approval required")
        project = self._project(project_id)
        if not dataset_version.strip() or len(source_hash.strip()) < 16:
            raise ValueError("dataset_version and source hash required")
        if not definitions or len(definitions) > 5000:
            raise ValueError("1 to 5000 definitions required")
        import_id, now = new_id("socialimport213"), now_ts()
        rows = []
        seen: set[str] = set()
        for raw in definitions:
            site_key = _text(raw.get("site_key") or raw.get("name"), 160).strip().casefold().replace(" ", "_")
            title = _text(raw.get("title") or raw.get("name"), 300).strip()
            template = _text(raw.get("profile_url_template") or raw.get("url"), 3000).strip()
            if not site_key or site_key in seen or not title or "{username}" not in template:
                raise ValueError("each definition needs unique site_key, title and {username} URL template")
            sample = template.replace("{username}", "fixture-user")
            canonical = _canonical_url(sample)
            host = _host(canonical)
            if not host:
                raise ValueError("definition host missing")
            positive = dict(raw.get("positive_rule") or {"type": "status_or_content", "expected": "fixture_defined"})
            negative = dict(raw.get("negative_rule") or {"type": "status_or_content", "expected": "fixture_defined"})
            blocked = dict(raw.get("blocked_rule") or {"type": "captcha_or_rate_limit"})
            requires_auth = bool(raw.get("requires_auth", False))
            disabled = bool(raw.get("disabled", False))
            network_risk = _text(raw.get("network_risk") or ("high" if requires_auth else "elevated"), 30)
            if network_risk not in _THREATS:
                raise ValueError("invalid network risk")
            payload = {
                "site_key": site_key, "title": title, "category": _text(raw.get("category") or "social", 100),
                "profile_url_template": template, "host": host, "positive_rule": positive, "negative_rule": negative,
                "blocked_rule": blocked, "requires_auth": requires_auth, "disabled": disabled, "network_risk": network_risk,
                "countries": list(raw.get("countries") or []), "tags": list(raw.get("tags") or []),
            }
            did = new_id("sitedef213")
            rows.append((did, import_id, project_id, site_key, title, payload["category"], template, host, dumps(positive), dumps(negative), dumps(blocked), int(requires_auth), int(disabled), network_risk, dumps(payload["countries"]), dumps(payload["tags"]), now, _hash(payload)))
            seen.add(site_key)
        import_payload = {"import_id": import_id, "project_id": project_id, "dataset_version": dataset_version.strip(), "source_hash": source_hash.strip(), "definition_count": len(rows), "status": "fixture_review_required", "reviewer": reviewer, "notes": notes, "created_at": now}
        with self.db.transaction(immediate=True):
            self.db.execute("INSERT INTO social_definition_imports_213 VALUES(?,?,?,?,?,?,?,?,?,?)", (import_id, project_id, dataset_version.strip(), source_hash.strip(), len(rows), "fixture_review_required", reviewer, _text(notes, 2000), now, _hash(import_payload)))
            for row in rows:
                self.db.execute("INSERT INTO social_site_definitions_213 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", row)
        return {**import_payload, "definitions_imported": len(rows), "network_executed": False, "upstream_code_bundled": False, "project": project["title"]}

    def run_fixture_benchmark(self, *, project_id: str, import_id: str, fixtures: Sequence[Mapping[str, Any]], reviewer: str, notes: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL BENCHMARK 213 {project_id} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        self._project(project_id)
        imp = self.db.one("SELECT * FROM social_definition_imports_213 WHERE import_id=? AND project_id=?", (import_id, project_id))
        if not imp:
            raise KeyError(import_id)
        if len(fixtures) < 4:
            raise ValueError("at least four offline fixtures required")
        tp = fp = tn = fn = 0
        parser_ok = True
        valid_states = {"found", "not_found", "blocked", "error"}
        for fixture in fixtures:
            expected = _text(fixture.get("expected"), 30)
            observed = _text(fixture.get("observed"), 30)
            if expected not in {"found", "not_found"} or observed not in valid_states:
                parser_ok = False
                continue
            if expected == "found" and observed == "found": tp += 1
            elif expected == "found": fn += 1
            elif observed == "found": fp += 1
            else: tn += 1
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        fpr = fp / max(1, fp + tn)
        status = "passed" if parser_ok and precision >= .90 and recall >= .80 and fpr <= .05 else "failed"
        cid, now = new_id("health213"), now_ts()
        payload = {"check_id": cid, "project_id": project_id, "import_id": import_id, "fixture_count": len(fixtures), "true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn, "precision": round(precision, 6), "recall": round(recall, 6), "false_positive_rate": round(fpr, 6), "parser_ok": parser_ok, "status": status, "reviewer": reviewer, "notes": notes, "created_at": now}
        self.db.execute("INSERT INTO social_health_checks_213 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid, project_id, import_id, len(fixtures), tp, fp, tn, fn, payload["precision"], payload["recall"], payload["false_positive_rate"], int(parser_ok), status, reviewer, _text(notes, 2000), now, _hash(payload)))
        self.db.execute("UPDATE social_projects_213 SET fixture_ok=?,parser_ok=?,benchmark_ok=?,updated_at=? WHERE project_id=?", (int(parser_ok), int(parser_ok), int(status == "passed"), now, project_id))
        return {**payload, "live_network_test": False, "automatic_activation": False}

    def approve_project(self, *, project_id: str, live_ok: bool, terms_reviewed: bool, reviewer: str, reason: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL PROJECT 213 {project_id} FREIGEBEN":
            raise PermissionError("explicit approval required")
        row = self._project(project_id)
        if len(reason.strip()) < 15:
            raise ValueError("reason too short")
        active = bool(row["fixture_ok"] and row["parser_ok"] and row["benchmark_ok"] and terms_reviewed and (live_ok or not row["network_capable"]))
        now = now_ts()
        payload = {"project_id": project_id, "live_ok": bool(live_ok), "terms_reviewed": bool(terms_reviewed), "active": active, "reviewer": reviewer, "reason": reason, "updated_at": now}
        self.db.execute("UPDATE social_projects_213 SET live_ok=?,terms_reviewed=?,active=?,notes=?,updated_at=?,payload_sha256=? WHERE project_id=?", (int(live_ok), int(terms_reviewed), int(active), _text(reason, 2000), now, _hash(payload), project_id))
        return {**payload, "automatic_execution": False, "core_network_access": False}

    # ---------------- focused research planning and candidate ingestion ----------------
    def create_username_plan(self, *, case_id: str, username: str, question: str, definition_ids: Sequence[str], created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL PLAN 213 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        username = _text(username, 100).strip().lstrip("@")
        if not _USERNAME.match(username):
            raise ValueError("username contains unsupported characters")
        lanes = self.ensure_parallel_workspaces(case_id=case_id, owner=created_by, confirmation=f"PARALLEL WORKSPACES 213 {case_id} ANLEGEN")
        source_lane = next(x for x in lanes["workspaces"] if x["lane_key"] == "sources")
        ids = list(dict.fromkeys(_text(x, 100) for x in definition_ids if x))[:25]
        if not ids:
            raise ValueError("at least one reviewed site definition required")
        placeholders = ",".join("?" for _ in ids)
        rows = self.db.all(f"SELECT d.*,p.active,p.terms_reviewed,p.fixture_ok,p.parser_ok,p.benchmark_ok,p.live_ok FROM social_site_definitions_213 d JOIN social_projects_213 p ON p.project_id=d.project_id WHERE d.definition_id IN ({placeholders}) ORDER BY d.title", ids)
        if len(rows) != len(ids):
            raise KeyError("unknown site definition")
        plan_id, now = new_id("socialplan213"), now_ts()
        task_ids, tabs = [], []
        for row in rows:
            if not (row["fixture_ok"] and row["parser_ok"] and row["benchmark_ok"] and row["terms_reviewed"]):
                raise PermissionError(f"site definition {row['site_key']} has not passed source governance")
            if row["disabled"] or row["requires_auth"]:
                continue
            public_url = _canonical_url(row["profile_url_template"].replace("{username}", quote(username, safe="")))
            if _host(public_url) != row["host"]:
                raise RuntimeError("site definition host mismatch")
            tid = new_id("socialtask213")
            payload = {"task_id": tid, "case_id": case_id, "workspace_id": source_lane["workspace_id"], "plan_id": plan_id, "definition_id": row["definition_id"], "target_type": "username", "target_value": username, "public_url": public_url, "mode": "guided_public_browser", "status": "planned", "candidate_only": True, "network_execution": False, "created_by": created_by, "created_at": now}
            self.db.execute("INSERT INTO social_tasks_213 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tid, case_id, source_lane["workspace_id"], plan_id, row["definition_id"], "username", username, public_url, "guided_public_browser", "planned", 1, 0, created_by, now, _hash(payload)))
            task_ids.append(tid)
            if len(tabs) < 5:
                tabs.append({"task_id": tid, "site_key": row["site_key"], "title": row["title"], "url": public_url, "command": ["firefox.exe", "-new-tab", public_url], "existing_firefox_session": True, "automatic_open": False})
        if not task_ids:
            raise RuntimeError("no public, no-login definitions available")
        plan = {"plan_id": plan_id, "case_id": case_id, "username": username, "question": _text(question, 3000), "definition_ids": ids, "tab_orders": tabs, "task_ids": task_ids, "status": "review_required", "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO social_research_plans_213 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (plan_id, case_id, username, plan["question"], dumps(ids), dumps(tabs), dumps(task_ids), "review_required", created_by, now, _hash(plan)))
        self._event(case_id, "social_plan_created", "social_research_plan", plan_id, plan, created_by)
        return {**plan, "parallel_tabs": len(tabs), "existing_firefox_only": True, "automatic_external_action": False}

    def ingest_candidate(self, *, case_id: str, task_id: str, existence_state: str, profile_url: str, display_name: str, bio_original: str, content_language: str, extracted: Mapping[str, Any], evidence_refs: Sequence[str], collector_version: str, observed_at: str, created_by: str, limitations: Sequence[str], confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL CANDIDATE 213 {case_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if existence_state not in _STATES:
            raise ValueError("invalid existence state")
        task = self.db.one("SELECT t.*,d.site_key,d.project_id,d.host,d.title FROM social_tasks_213 t JOIN social_site_definitions_213 d ON d.definition_id=t.definition_id WHERE t.task_id=? AND t.case_id=?", (task_id, case_id))
        if not task:
            raise KeyError(task_id)
        url = _canonical_url(profile_url or task["public_url"])
        if _host(url) != task["host"]:
            raise ValueError("candidate URL does not match reviewed definition host")
        evidence = [str(x) for x in evidence_refs if str(x).strip()]
        if existence_state in {"found", "possible"} and not evidence:
            raise ValueError("candidate result requires evidence reference")
        confidence = {"found": .72, "possible": .45, "not_found": .35, "blocked": .10, "error": .05}[existence_state]
        if existence_state == "found" and display_name.strip():
            confidence += .05
        if existence_state == "found" and bio_original.strip():
            confidence += .03
        confidence = min(.80, confidence)
        cid, now = new_id("socialcandidate213"), now_ts()
        limits = list(limitations) or ["username reuse possible", "account ownership not verified", "identity relation requires separate review"]
        payload = {
            "candidate_id": cid, "case_id": case_id, "task_id": task_id, "definition_id": task["definition_id"], "project_id": task["project_id"],
            "site_key": task["site_key"], "target_value": task["target_value"], "profile_url": url, "existence_state": existence_state,
            "display_name": _text(display_name, 1000), "bio_original": _text(bio_original, 30000), "content_language": _text(content_language, 30) or "und",
            "extracted": _redact(dict(extracted)), "evidence_refs": evidence, "collector_version": _text(collector_version, 200),
            "confidence": round(confidence, 4), "limitations": limits, "observed_at": observed_at or now, "status": "candidate", "created_by": created_by, "created_at": now,
        }
        self.db.execute("INSERT INTO social_candidates_213 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid, case_id, task_id, task["definition_id"], task["project_id"], task["site_key"], task["target_value"], url, existence_state, payload["display_name"], payload["bio_original"], payload["content_language"], dumps(payload["extracted"]), dumps(evidence), payload["collector_version"], payload["confidence"], dumps(limits), payload["observed_at"], "candidate", created_by, now, _hash(payload)))
        self._event(case_id, "social_candidate_ingested", "social_candidate", cid, payload, created_by)
        return {**payload, "same_person_confirmed": False, "human_review_required": True}

    def review_candidate(self, *, candidate_id: str, reviewer: str, decision: str, identity_relation: str, reason: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL REVIEW 213 {candidate_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if decision not in _REVIEWS or identity_relation not in _IDENTITY_RELATIONS:
            raise ValueError("invalid review decision")
        candidate = self._candidate(candidate_id)
        if len(reason.strip()) < 15:
            raise ValueError("reason too short")
        rid, now = new_id("socialreview213"), now_ts()
        payload = {"review_id": rid, "case_id": candidate["case_id"], "candidate_id": candidate_id, "reviewer": reviewer, "decision": decision, "identity_relation": identity_relation, "reason": reason.strip(), "created_at": now}
        self.db.execute("INSERT INTO social_candidate_reviews_213 VALUES(?,?,?,?,?,?,?,?,?)", (rid, candidate["case_id"], candidate_id, reviewer, decision, identity_relation, reason.strip(), now, _hash(payload)))
        self._event(candidate["case_id"], "social_candidate_reviewed", "social_candidate_review", rid, payload, reviewer)
        return {**payload, "identity_confirmation": False, "entity_resolution_required": identity_relation == "requires_entity_review"}

    # ---------------- translation and AI chat ----------------
    def translate_candidate_content(self, *, case_id: str, candidate_id: str, field_name: str, target_language: str, engine: str, translated_text: str, created_by: str, glossary: Mapping[str, str] | None, uncertainties: Sequence[str], confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL TRANSLATION 213 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        candidate = self._candidate(candidate_id, case_id)
        if field_name not in {"bio_original", "display_name"}:
            raise ValueError("unsupported field")
        original = _text(candidate[field_name], 30000).strip()
        if not original:
            raise ValueError("candidate field is empty")
        version = "human"
        if engine == "manual":
            result = _text(translated_text, 30000).strip()
            if not result:
                raise ValueError("manual translated_text required")
        elif engine == "argos_offline":
            try:
                module = importlib.import_module("argostranslate.translate")
                package = importlib.import_module("argostranslate")
                result = _text(module.translate(original, candidate["content_language"], target_language), 30000).strip()
                version = _text(getattr(package, "__version__", "installed"), 100)
            except Exception as exc:
                raise RuntimeError(f"offline translation unavailable: {_redact(str(exc))}") from exc
        else:
            raise ValueError("engine must be manual or argos_offline")
        tid, now = new_id("socialtranslation213"), now_ts()
        limits = list(uncertainties) or ["translation requires human review", "names and slang may be ambiguous"]
        payload = {"translation_id": tid, "case_id": case_id, "candidate_id": candidate_id, "field_name": field_name, "original_language": candidate["content_language"], "target_language": target_language, "original_text": original, "translated_text": result, "engine": engine, "engine_version": version, "glossary": dict(glossary or {}), "uncertainties": limits, "status": "candidate_translation", "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO social_content_translations_213 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (tid, case_id, candidate_id, field_name, candidate["content_language"], target_language, original, result, engine, version, dumps(payload["glossary"]), dumps(limits), "candidate_translation", created_by, now, _hash(payload)))
        self._event(case_id, "social_content_translated", "social_translation", tid, payload, created_by)
        return {**payload, "external_upload": False, "original_preserved": True, "fact_status": "interpretation"}

    def prepare_chat_turn(self, *, case_id: str, question: str, question_language: str, working_language: str, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL CHAT 213 {case_id} VORBEREITEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        question = _text(question, 10000).strip()
        if not question:
            raise ValueError("question required")
        tid, now = new_id("socialchat213"), now_ts()
        context = self._case_context(case_id)
        payload = {"turn_id": tid, "case_id": case_id, "question_original": question, "question_language": question_language, "working_language": working_language, "context": context, "status": "prepared", "created_by": created_by, "created_at": now, "updated_at": now}
        self.db.execute("INSERT INTO social_chat_turns_213 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (tid, case_id, question, question_language, working_language, dumps(context), "{}", "[]", "prepared", created_by, now, now, _hash(payload)))
        return {**payload, "co_investigator": True, "automatic_execution": False, "external_uploads": False}

    def complete_chat_turn(self, *, turn_id: str, response: Mapping[str, Any], citations: Sequence[str], actor: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL CHAT 213 {turn_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        row = self.db.one("SELECT * FROM social_chat_turns_213 WHERE turn_id=?", (turn_id,))
        if not row:
            raise KeyError(turn_id)
        required = {"observations", "inferences", "hypotheses", "open_questions", "recommended_next_steps"}
        if not required.issubset(response.keys()):
            raise ValueError("structured response sections required")
        clean = {key: list(response.get(key) or []) for key in required}
        refs = list(dict.fromkeys(str(x) for x in citations if str(x).strip()))
        if clean["observations"] and not refs:
            raise ValueError("observations require citations")
        valid = self._valid_citations(row["case_id"], refs)
        if set(refs) != set(valid):
            raise ValueError("unknown or cross-case citation")
        now = now_ts()
        payload = {"turn_id": turn_id, "case_id": row["case_id"], "response": _redact(clean), "citations": refs, "status": "review_required", "actor": actor, "updated_at": now}
        self.db.execute("UPDATE social_chat_turns_213 SET response_json=?,citations_json=?,status='review_required',updated_at=?,payload_sha256=? WHERE turn_id=?", (dumps(payload["response"]), dumps(refs), now, _hash(payload), turn_id))
        self._event(row["case_id"], "social_chat_completed", "social_chat_turn", turn_id, payload, actor)
        return {**payload, "automatic_case_update": False, "human_review_required": True, "identity_confirmation": False}

    def record_ai_feedback(self, *, case_id: str, item_type: str, item_id: str, verdict: str, dimensions: Mapping[str, Any], reason: str, analyst: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL AI FEEDBACK 213 {case_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        if verdict not in {"helpful", "partly_helpful", "incorrect", "unsafe", "needs_more_evidence"}:
            raise ValueError("invalid verdict")
        if len(reason.strip()) < 15:
            raise ValueError("reason too short")
        eligible = verdict in {"helpful", "incorrect", "unsafe"} and bool(dimensions)
        fid, now = new_id("socialfeedback213"), now_ts()
        payload = {"feedback_id": fid, "case_id": case_id, "item_type": item_type, "item_id": item_id, "verdict": verdict, "dimensions": _redact(dict(dimensions)), "reason": reason, "analyst": analyst, "training_eligible": eligible, "created_at": now}
        self.db.execute("INSERT INTO social_ai_feedback_213 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (fid, case_id, item_type, item_id, verdict, dumps(payload["dimensions"]), reason.strip(), analyst, int(eligible), now, _hash(payload)))
        return {**payload, "production_model_changed": False, "supervised_dataset_only": True}

    # ---------------- platform-specific OPSEC ----------------
    def create_platform_opsec(self, *, case_id: str, site_key: str, threat_level: str, reason: str, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL OPSEC 213 {case_id} {site_key} ANLEGEN":
            raise PermissionError("explicit approval required")
        self._case(case_id)
        if threat_level not in _THREATS:
            raise ValueError("invalid threat level")
        if len(reason.strip()) < 20:
            raise ValueError("reason too short")
        controls = self._controls(threat_level)
        pid, now = new_id("socialopsec213"), now_ts()
        payload = {"profile_id": pid, "case_id": case_id, "site_key": site_key, "threat_level": threat_level, "controls": controls, "reason": reason, "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO social_platform_opsec_213 VALUES(?,?,?,?,?,?,?,?,?)", (pid, case_id, site_key, threat_level, dumps(controls), reason.strip(), created_by, now, _hash(payload)))
        self._event(case_id, "social_opsec_profile_created", "social_platform_opsec", pid, payload, created_by)
        return {**payload, "defensive_only": True, "anti_bot_bypass": False}

    def preflight(self, *, case_id: str, task_id: str, requested: Mapping[str, Any], created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"SOCIAL PREFLIGHT 213 {case_id} PRUEFEN":
            raise PermissionError("explicit approval required")
        task = self.db.one("SELECT t.*,d.site_key,d.requires_auth,d.network_risk FROM social_tasks_213 t JOIN social_site_definitions_213 d ON d.definition_id=t.definition_id WHERE t.task_id=? AND t.case_id=?", (task_id, case_id))
        if not task:
            raise KeyError(task_id)
        profile = self.db.one("SELECT * FROM social_platform_opsec_213 WHERE case_id=? AND site_key=? ORDER BY created_at DESC LIMIT 1", (case_id, task["site_key"]))
        threat = profile["threat_level"] if profile else task["network_risk"]
        controls = _loads(profile["controls_json"], {}) if profile else self._controls(threat)
        req = _redact(dict(requested))
        risks: list[str] = []
        for key, risk in (
            ("direct_contact", "direct_contact_prohibited"), ("credential_login", "credential_login_prohibited"),
            ("upload_local_file", "local_upload_prohibited"), ("download", "download_prohibited"),
            ("anti_bot_bypass", "anti_bot_bypass_prohibited"), ("network_execution_from_core", "core_network_execution_prohibited"),
            ("new_browser_window", "new_browser_window_prohibited"), ("cross_case_clipboard", "cross_case_clipboard_prohibited"),
        ):
            if req.get(key):
                risks.append(risk)
        if task["requires_auth"]:
            risks.append("definition_requires_auth")
        if controls.get("offline_only_default") and req.get("open_public_tab"):
            risks.append("offline_only_default")
        decision = "blocked" if risks else "review_required"
        pid, now = new_id("socialpreflight213"), now_ts()
        payload = {"preflight_id": pid, "case_id": case_id, "task_id": task_id, "site_key": task["site_key"], "requested": req, "controls": controls, "risks": sorted(set(risks)), "decision": decision, "created_by": created_by, "created_at": now}
        self.db.execute("INSERT INTO social_preflights_213 VALUES(?,?,?,?,?,?,?,?,?,?,?)", (pid, case_id, task_id, task["site_key"], dumps(req), dumps(controls), dumps(payload["risks"]), decision, created_by, now, _hash(payload)))
        self._event(case_id, "social_preflight_completed", "social_preflight", pid, payload, created_by)
        return {**payload, "automatic_open": False, "existing_firefox_only": True}

    # ---------------- dashboard ----------------
    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        try:
            self.seed(confirmation="BUILD 213 SOCIAL FABRIC ANLEGEN")
        except Exception:
            pass
        lanes = self.ensure_parallel_workspaces(case_id=case_id, owner=self.actor, confirmation=f"PARALLEL WORKSPACES 213 {case_id} ANLEGEN")["workspaces"]
        return {
            "build": self.BUILD,
            "policy": _loads((self.db.one("SELECT policy_json FROM build213_policies WHERE policy_id='default'") or {}).get("policy_json", "{}"), {}),
            "projects": self.db.all("SELECT * FROM social_projects_213 ORDER BY title"),
            "imports": self.db.all("SELECT * FROM social_definition_imports_213 ORDER BY created_at DESC LIMIT 20"),
            "definitions": self.db.all("SELECT * FROM social_site_definitions_213 ORDER BY created_at DESC LIMIT 100"),
            "health_checks": self.db.all("SELECT * FROM social_health_checks_213 ORDER BY created_at DESC LIMIT 30"),
            "lanes": lanes,
            "plans": self.db.all("SELECT * FROM social_research_plans_213 WHERE case_id=? ORDER BY created_at DESC LIMIT 20", (case_id,)),
            "tasks": self.db.all("SELECT * FROM social_tasks_213 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "candidates": self.db.all("SELECT * FROM social_candidates_213 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "reviews": self.db.all("SELECT * FROM social_candidate_reviews_213 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,)),
            "translations": self.db.all("SELECT * FROM social_content_translations_213 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "chat": self.db.all("SELECT * FROM social_chat_turns_213 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "preflights": self.db.all("SELECT * FROM social_preflights_213 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "automatic_identity_confirmation": False,
            "automatic_external_action": False,
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        d = self.dashboard(case_id=case_id)
        esc = lambda x: html.escape(str(x or ""), quote=True)
        lanes = "".join(f"<div class='card'><b>{esc(x['title'])}</b><br><small>{esc(x['objective'])}</small><br>Status: {esc(x['status'])}</div>" for x in d["lanes"])
        defs = "".join(f"<tr><td>{esc(x['definition_id'])}</td><td>{esc(x['title'])}</td><td>{esc(x['project_id'])}</td><td>{esc(x['network_risk'])}</td></tr>" for x in d["definitions"][:50]) or "<tr><td colspan='4'>Noch keine geprüften Seitendefinitionen importiert.</td></tr>"
        projects = "".join(f"<tr><td>{esc(x['project_id'])}</td><td>{esc(x['title'])}</td><td>{'aktiv' if x['active'] else 'gesperrt'}</td><td>{'ja' if x['benchmark_ok'] else 'nein'}</td></tr>" for x in d["projects"]) or "<tr><td colspan='4'>Keine Projekte registriert.</td></tr>"
        health = "".join(f"<tr><td>{esc(x['project_id'])}</td><td>{esc(x['status'])}</td><td>{float(x['precision'])*100:.0f}%</td><td>{float(x['false_positive_rate'])*100:.1f}%</td></tr>" for x in d["health_checks"][:20]) or "<tr><td colspan='4'>Noch kein Offline-Benchmark.</td></tr>"
        tasks = "".join(f"<tr><td>{esc(x['task_id'])}</td><td>{esc(x['target_value'])}</td><td>{esc(x['status'])}</td><td><a href='{esc(x['public_url'])}' target='_blank' rel='noopener noreferrer'>öffnen</a></td></tr>" for x in d["tasks"][:30]) or "<tr><td colspan='4'>Keine Social-Rechercheaufgaben.</td></tr>"
        candidates = "".join(f"<tr><td>{esc(x['candidate_id'])}</td><td>{esc(x['site_key'])}</td><td>{esc(x['existence_state'])}</td><td>{float(x['confidence'])*100:.0f}%</td></tr>" for x in d["candidates"][:30]) or "<tr><td colspan='4'>Keine Kandidaten.</td></tr>"
        preflights = "".join(f"<tr><td>{esc(x['task_id'])}</td><td>{esc(x['site_key'])}</td><td>{esc(x['decision'])}</td></tr>" for x in d["preflights"][:30]) or "<tr><td colspan='3'>Keine Preflights.</td></tr>"
        return f"""
        <div class='notice'><b>Social Source Fabric 213</b><br>Vier parallele Arbeitsbereiche für fokussierte Personenrecherche. Externe Werkzeuge und Plattformdefinitionen liefern ausschließlich Kandidaten; Ermittler und unabhängige Reviews entscheiden.</div>
        <div class='grid'>{lanes}</div>
        <div class='grid'><div class='panel'><h2>Quellen &amp; Adapter</h2>
        <form method='post' action='/build213/import-definitions'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='project_id'>{''.join(f"<option value='{esc(p['project_id'])}'>{esc(p['title'])}</option>" for p in d['projects'])}</select><input name='dataset_version' placeholder='Dataset-Version' required><input name='source_hash' placeholder='SHA-256/Quellhash' required><textarea name='definitions_json' rows='10' placeholder='[{{"site_key":"example","title":"Example","profile_url_template":"https://example.org/{{username}}"}}]' required></textarea><textarea name='notes' rows='3' placeholder='Prüfnotiz'></textarea><button>Definitionen kontrolliert importieren</button></form>
        <hr><form method='post' action='/build213/benchmark'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='project_id' placeholder='Projekt-ID' required><input name='import_id' placeholder='Import-ID' required><textarea name='fixtures_json' rows='6' placeholder='[{{"expected":"found","observed":"found"}},{{"expected":"not_found","observed":"not_found"}}]' required></textarea><textarea name='notes' rows='2' placeholder='Benchmarknotiz'></textarea><button>Offline-Fixtures benchmarken</button></form>
        <hr><form method='post' action='/build213/project-approve'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='project_id' placeholder='Projekt-ID' required><label><input type='checkbox' name='terms_reviewed' value='1'> Lizenz/Terms geprüft</label><label><input type='checkbox' name='live_ok' value='1'> kontrollierter Live-Test bestanden</label><textarea name='reason' rows='3' placeholder='Freigabebegründung' required></textarea><button>Projektstatus kontrolliert freigeben</button></form>
        <div class='table-wrap'><table><thead><tr><th>Projekt</th><th>Titel</th><th>Status</th><th>Benchmark</th></tr></thead><tbody>{projects}</tbody></table></div><div class='table-wrap'><table><thead><tr><th>Projekt</th><th>Benchmark</th><th>Precision</th><th>FPR</th></tr></thead><tbody>{health}</tbody></table></div><div class='table-wrap'><table><thead><tr><th>ID</th><th>Plattform</th><th>Projekt</th><th>Risiko</th></tr></thead><tbody>{defs}</tbody></table></div></div>
        <div class='panel'><h2>Fokussierter Rechercheplan</h2><form method='post' action='/build213/plan'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='username' placeholder='Benutzername' required><textarea name='question' rows='3' placeholder='Konkrete Ermittlungsfrage' required></textarea><textarea name='definition_ids' rows='5' placeholder='Definition-IDs, komma- oder zeilengetrennt' required></textarea><button>Plan mit höchstens fünf Firefox-Tabs vorbereiten</button></form><div class='table-wrap'><table><thead><tr><th>Task</th><th>Ziel</th><th>Status</th><th>Firefox</th></tr></thead><tbody>{tasks}</tbody></table></div></div></div>
        <div class='grid'><div class='panel'><h2>Kandidaten &amp; Review</h2><form method='post' action='/build213/candidate'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='task_id' placeholder='Task-ID' required><select name='existence_state'><option>found</option><option>possible</option><option>not_found</option><option>blocked</option><option>error</option></select><input name='profile_url' placeholder='Öffentliche Profil-URL'><input name='display_name' placeholder='Anzeigename'><input name='content_language' value='und'><textarea name='bio_original' rows='4' placeholder='Original-Bio'></textarea><textarea name='extracted_json' rows='4' placeholder='{{}}'></textarea><input name='evidence_refs' placeholder='Evidence-Refs'><input name='collector_version' placeholder='Collector/Browser-Version'><textarea name='limitations' rows='3' placeholder='Einschränkungen'></textarea><button>Kandidatenbeobachtung speichern</button></form><hr><form method='post' action='/build213/review'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='candidate_id' placeholder='Candidate-ID' required><select name='decision'><option>relevant</option><option>not_relevant</option><option>uncertain</option></select><select name='identity_relation'><option>unknown</option><option>possible_same_person</option><option>not_same_person</option><option>requires_entity_review</option></select><textarea name='reason' rows='3' placeholder='Begründung' required></textarea><button>Review speichern</button></form><div class='table-wrap'><table><thead><tr><th>ID</th><th>Site</th><th>Status</th><th>Konfidenz</th></tr></thead><tbody>{candidates}</tbody></table></div></div>
        <div class='panel'><h2>Fallübersetzung</h2><form method='post' action='/build213/translate'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='candidate_id' placeholder='Candidate-ID' required><select name='field_name'><option>bio_original</option><option>display_name</option></select><input name='target_language' value='de'><select name='engine'><option>manual</option><option>argos_offline</option></select><textarea name='translated_text' rows='5' placeholder='Manuelle Übersetzung'></textarea><input name='uncertainties' placeholder='Unsicherheiten, komma-getrennt'><button>Übersetzung quellengebunden speichern</button></form></div></div>
        <div class='grid'><div class='panel'><h2>AI &amp; Chat-Ermittler</h2><form method='post' action='/build213/chat'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><textarea name='question' rows='4' placeholder='Fallbezogene Frage' required></textarea><input name='question_language' value='de'><input name='working_language' value='de'><button>Quellengebundenen Chat-Turn vorbereiten</button></form><hr><form method='post' action='/build213/chat-complete'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='turn_id' placeholder='Turn-ID' required><textarea name='response_json' rows='10' placeholder='{{"observations":[],"inferences":[],"hypotheses":[],"open_questions":[],"recommended_next_steps":[]}}' required></textarea><input name='citations' placeholder='Candidate-/Translation-/Evidence-IDs'><button>Reviewpflichtige AI-Antwort speichern</button></form><hr><form method='post' action='/build213/ai-feedback'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><select name='item_type'><option>social_chat_turn</option><option>social_translation</option><option>social_candidate</option></select><input name='item_id' placeholder='Item-ID' required><select name='verdict'><option>helpful</option><option>partly_helpful</option><option>incorrect</option><option>unsafe</option><option>needs_more_evidence</option></select><textarea name='dimensions_json' rows='4' placeholder='{{"source_grounding":5,"identity_caution":5,"translation_quality":4}}' required></textarea><textarea name='reason' rows='3' placeholder='Begründetes Ermittlerfeedback' required></textarea><button>Supervidiertes AI-Feedback speichern</button></form></div>
        <div class='panel'><h2>Plattform-OPSEC</h2><form method='post' action='/build213/opsec'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='site_key' placeholder='Site-Key' required><select name='threat_level'><option>elevated</option><option>high</option><option>critical</option><option>low</option></select><textarea name='reason' rows='4' placeholder='Gefährdungslage und Schutzbegründung' required></textarea><button>Plattformbezogenes OPSEC-Profil anlegen</button></form><hr><form method='post' action='/build213/preflight'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='task_id' placeholder='Task-ID' required><textarea name='requested_json' rows='7' placeholder='{{"open_public_tab":true,"credential_login":false,"direct_contact":false}}' required></textarea><button>Preflight prüfen</button></form><div class='table-wrap'><table><thead><tr><th>Task</th><th>Site</th><th>Entscheidung</th></tr></thead><tbody>{preflights}</tbody></table></div></div></div>
        """

    # ---------------- internals ----------------
    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _project(self, project_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM social_projects_213 WHERE project_id=?", (project_id,))
        if not row:
            raise KeyError(project_id)
        return row

    def _candidate(self, candidate_id: str, case_id: str = "") -> dict[str, Any]:
        row = self.db.one("SELECT * FROM social_candidates_213 WHERE candidate_id=?" + (" AND case_id=?" if case_id else ""), (candidate_id, case_id) if case_id else (candidate_id,))
        if not row:
            raise KeyError(candidate_id)
        return row

    def _case_context(self, case_id: str) -> dict[str, Any]:
        candidates = self.db.all("SELECT candidate_id,site_key,target_value,profile_url,existence_state,display_name,bio_original,content_language,evidence_refs_json,confidence,limitations_json,observed_at,status FROM social_candidates_213 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,))
        reviews = self.db.all("SELECT candidate_id,decision,identity_relation,reason,reviewer,created_at FROM social_candidate_reviews_213 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,))
        translations = self.db.all("SELECT translation_id,candidate_id,field_name,original_language,target_language,translated_text,uncertainties_json,status FROM social_content_translations_213 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,))
        identity = self.db.all("SELECT comparison_id,probability,candidate_state,hard_conflicts_json FROM identity_comparisons_212 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,))
        evidence = self.db.all("SELECT source_id,canonical_url,observed_at FROM evidence_sources_211 WHERE case_id=? ORDER BY created_at DESC LIMIT 30", (case_id,))
        return _redact({"social_candidates": candidates, "human_reviews": reviews, "translations": translations, "identity_comparisons": identity, "evidence_sources": evidence, "rules": ["cite every factual observation", "separate observation inference hypothesis", "do not confirm identity", "no external action", "preserve original language"]})

    def _valid_citations(self, case_id: str, refs: Sequence[str]) -> list[str]:
        valid = []
        for ref in refs:
            found = (
                self.db.one("SELECT candidate_id AS id FROM social_candidates_213 WHERE case_id=? AND candidate_id=?", (case_id, ref))
                or self.db.one("SELECT translation_id AS id FROM social_content_translations_213 WHERE case_id=? AND translation_id=?", (case_id, ref))
                or self.db.one("SELECT source_id AS id FROM evidence_sources_211 WHERE case_id=? AND source_id=?", (case_id, ref))
                or self.db.one("SELECT statement_id AS id FROM evidence_statements_211 WHERE case_id=? AND statement_id=?", (case_id, ref))
            )
            if found:
                valid.append(ref)
        return valid

    def _controls(self, threat: str) -> dict[str, Any]:
        controls = {
            "existing_firefox_new_tabs": True, "case_scoped_workspace": True, "automatic_open": False,
            "no_direct_contact": True, "no_active_engagement": True, "no_login_bypass": True,
            "no_anti_bot_bypass": True, "no_secret_logging": True, "external_uploads": False,
            "network_execution_from_core": False, "candidate_only": True, "human_preflight": True,
            "camera_microphone_geolocation_disabled": True, "cross_case_clipboard_prohibited": True,
        }
        if threat in {"elevated", "high", "critical"}:
            controls.update({"no_login": True, "no_local_file_upload": True, "no_downloads": True, "offline_capture_import_preferred": True})
        if threat in {"high", "critical"}:
            controls.update({"dedicated_browser_profile": True, "separate_os_account_recommended": True, "supervisor_review_each_network_step": True})
        if threat == "critical":
            controls.update({"offline_only_default": True, "safety_lock_recommended": True, "public_tab_open_blocked_until_supervisor": True})
        return controls

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> str:
        prev = self.db.one("SELECT event_hash FROM build213_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "0" * 64
        eid, now = new_id("evt213"), now_ts()
        clean = _redact(dict(payload))
        body = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": clean, "previous_hash": previous, "created_at": now}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build213_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, actor, dumps(clean), previous, event_hash, now))
        if self.audit is not None and hasattr(self.audit, "log"):
            self.audit.log(event_type, object_type, object_id, case_id, clean)
        return eid
