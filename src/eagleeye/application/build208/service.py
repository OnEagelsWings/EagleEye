from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    raw = value if isinstance(value, bytes) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if key not in {"tokens_used", "token_count", "max_tokens", "used_tokens"} and re.search(r"token|secret|password|authorization|cookie|session|api[_-]?key|private[_-]?key", key, re.I)
                else _redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _script(value: str) -> str:
    for char in value:
        name = unicodedata.name(char, "")
        for script in ("HEBREW", "ARABIC", "CYRILLIC", "HIRAGANA", "KATAKANA", "CJK"):
            if script in name:
                return script.lower()
    return "latin"


def _latin(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    if normalized:
        return re.sub(r"\s+", " ", normalized).strip()
    maps = {
        "ש": "sh", "ח": "h", "כ": "k", "ק": "q", "מ": "m", "נ": "n", "ר": "r", "א": "a", "ב": "b",
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "и": "i", "к": "k", "л": "l",
        "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "й": "y", "я": "ya",
    }
    return "".join(maps.get(char, char if char.isascii() else " ") for char in value.casefold()).strip()


class Build208EntityResolutionAgentRuntimeService:
    BUILD = "208.0"

    def __init__(self, db: Any, audit: Any, *, agents: Any, retrieval: Any, social: Any, runtime: Any, workspace: Any, actor: str = "system"):
        self.db = db
        self.audit = audit
        self.agents = agents
        self.retrieval = retrieval
        self.social = social
        self.runtime = runtime
        self.workspace = workspace
        self.actor = actor

    def _event(self, case_id: str, event_type: str, payload: Mapping[str, Any], run_id: str | None = None) -> str:
        previous = self.db.one(
            "SELECT event_hash FROM agent_runtime_events_208 WHERE case_id=? ORDER BY created_at DESC LIMIT 1",
            (case_id,),
        )
        previous_hash = previous["event_hash"] if previous else None
        created_at = now_ts()
        event_id = new_id("artevt208")
        body = {
            "event_id": event_id,
            "case_id": case_id,
            "run_id": run_id,
            "event_type": event_type,
            "actor": self.actor,
            "payload": _redact(dict(payload)),
            "prev_hash": previous_hash,
            "created_at": created_at,
        }
        event_hash = _hash(body)
        self.db.execute(
            "INSERT INTO agent_runtime_events_208 VALUES(?,?,?,?,?,?,?,?,?)",
            (event_id, case_id, run_id, event_type, self.actor, dumps(body["payload"]), previous_hash, event_hash, created_at),
        )
        return event_hash

    def seed_runtime(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != "AGENT RUNTIME 208 ANLEGEN":
            raise PermissionError("explicit approval required")
        created_at = now_ts()
        workers = [
            ("planner-worker", ["planning"], 2),
            ("source-worker", ["source_selection", "query_prepare"], 5),
            ("extract-worker", ["extraction"], 4),
            ("verify-worker", ["verification", "entity_resolution"], 3),
            ("hypothesis-worker", ["hypothesis"], 3),
            ("synthesis-worker", ["synthesis", "chat"], 2),
        ]
        policy = {"persistent": True, "resume": True, "least_privilege": True, "external_uploads": False}
        for worker_id, capabilities, max_parallel in workers:
            self.db.execute(
                "INSERT OR REPLACE INTO agent_workers_208 VALUES(?,?,?,?,?,?,?,?)",
                (worker_id, worker_id, dumps(capabilities), max_parallel, "idle", created_at, created_at, dumps(policy)),
            )
        routes = [
            ("de", "extraction", "local-multilingual-extractor", 32768, "balanced"),
            ("en", "extraction", "local-multilingual-extractor", 32768, "balanced"),
            ("he", "entity_resolution", "local-hebrew-name-router", 16384, "precision"),
            ("ar", "entity_resolution", "local-arabic-name-router", 16384, "precision"),
            ("ru", "entity_resolution", "local-cyrillic-name-router", 16384, "precision"),
            ("zh", "entity_resolution", "local-cjk-name-router", 16384, "precision"),
            ("*", "synthesis", "local-case-synthesis", 32768, "precision"),
        ]
        for language, task_type, model_ref, max_context, quality_tier in routes:
            self.db.execute(
                "INSERT OR REPLACE INTO model_routes_208 VALUES(?,?,?,?,?,?,?,?,?)",
                (f"{language}:{task_type}", language, task_type, model_ref, 1, max_context, quality_tier, "active", created_at),
            )
        return {"workers": len(workers), "routes": len(routes), "persistent": True, "parallel": True, "automatic_external_action": False}

    def create_budget(self, *, case_id: str, max_tokens: int, max_cost: float, currency: str = "EUR", confirmation: str) -> dict[str, Any]:
        if confirmation != f"AGENT BUDGET 208 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        if max_tokens < 1000 or max_cost < 0:
            raise ValueError("invalid budget")
        budget_id = new_id("budget208")
        created_at = now_ts()
        self.db.execute(
            "INSERT INTO agent_budgets_208 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (budget_id, case_id, max_tokens, 0, max_cost, 0.0, currency, "active", created_at, created_at),
        )
        return {"budget_id": budget_id, "case_id": case_id, "max_tokens": max_tokens, "max_cost": max_cost, "currency": currency}

    def route_model(self, *, language: str, task_type: str) -> dict[str, Any]:
        row = self.db.one(
            'SELECT * FROM model_routes_208 WHERE language=? AND task_type=? AND status="active"',
            (language, task_type),
        ) or self.db.one(
            'SELECT * FROM model_routes_208 WHERE language="*" AND task_type=? AND status="active"',
            (task_type,),
        )
        if not row:
            return {"model_ref": "rules-only-fallback", "local_only": True, "quality_tier": "safe", "route_status": "fallback"}
        return {
            "route_id": row["route_id"],
            "model_ref": row["model_ref"],
            "local_only": bool(row["local_only"]),
            "max_context": row["max_context"],
            "quality_tier": row["quality_tier"],
            "route_status": "matched",
        }

    def enqueue_jobs(self, *, run_id: str, case_id: str, jobs: Sequence[Mapping[str, Any]], budget_id: str | None, confirmation: str) -> dict[str, Any]:
        if confirmation != f"AGENT JOBS 208 {run_id} EINREIHEN":
            raise PermissionError("explicit approval required")
        output = []
        created_at = now_ts()
        for item in jobs:
            task_type = str(item.get("task_type", "extraction"))
            route = self.route_model(language=str(item.get("language", "de")), task_type=task_type)
            job_id = new_id("agentjob208")
            safe_input = _redact(dict(item))
            payload = {"job_id": job_id, "run_id": run_id, "case_id": case_id, "task_type": task_type, "input": safe_input, "model_route": route, "budget_id": budget_id}
            self.db.execute(
                "INSERT INTO agent_jobs_208 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (job_id, run_id, case_id, task_type, dumps(safe_input), "queued", int(item.get("priority", 50)), 0, int(item.get("max_attempts", 3)), None, dumps({}), dumps(route), budget_id, None, None, created_at, created_at, _hash(payload)),
            )
            output.append({"job_id": job_id, "task_type": task_type, "model_route": route})
        self._event(case_id, "jobs_enqueued", {"count": len(output), "jobs": output}, run_id)
        return {"jobs": output, "queued": len(output), "parallel_execution": True}

    def claim_jobs(self, *, worker_id: str, limit: int | None = None) -> list[dict[str, Any]]:
        worker = self.db.one("SELECT * FROM agent_workers_208 WHERE worker_id=?", (worker_id,))
        if not worker:
            raise KeyError(worker_id)
        maximum = min(int(limit or worker["max_parallel"]), int(worker["max_parallel"]))
        capabilities = set(json.loads(worker["capabilities_json"]))
        selected = []
        for row in self.db.all("SELECT * FROM agent_jobs_208 WHERE status IN ('queued','interrupted','retry') ORDER BY priority DESC,created_at LIMIT 100"):
            if row["task_type"] not in capabilities:
                continue
            self.db.execute(
                'UPDATE agent_jobs_208 SET status="running",worker_id=?,attempt=attempt+1,updated_at=? WHERE job_id=?',
                (worker_id, now_ts(), row["job_id"]),
            )
            selected.append(dict(row) | {"status": "running", "worker_id": worker_id, "attempt": int(row["attempt"]) + 1})
            if len(selected) >= maximum:
                break
        self.db.execute(
            "UPDATE agent_workers_208 SET status=?,last_heartbeat=? WHERE worker_id=?",
            ("busy" if selected else "idle", now_ts(), worker_id),
        )
        return selected

    def heartbeat(self, worker_id: str) -> dict[str, Any]:
        timestamp = now_ts()
        self.db.execute(
            'UPDATE agent_workers_208 SET last_heartbeat=?,status=CASE WHEN status="offline" THEN "idle" ELSE status END WHERE worker_id=?',
            (timestamp, worker_id),
        )
        return {"worker_id": worker_id, "heartbeat": timestamp}

    def checkpoint(self, *, job_id: str, checkpoint: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if confirmation != f"AGENT CHECKPOINT 208 {job_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        safe = _redact(dict(checkpoint))
        self.db.execute("UPDATE agent_jobs_208 SET checkpoint_json=?,updated_at=? WHERE job_id=?", (dumps(safe), now_ts(), job_id))
        return {"job_id": job_id, "checkpoint": safe}

    def interrupt_running(self, *, reason: str) -> dict[str, Any]:
        rows = self.db.all('SELECT job_id FROM agent_jobs_208 WHERE status="running"')
        self.db.execute(
            'UPDATE agent_jobs_208 SET status="interrupted",error_text=?,worker_id=NULL,updated_at=? WHERE status="running"',
            (reason[:500], now_ts()),
        )
        return {"interrupted": len(rows), "resumable": True}

    def execute_parallel(self, *, worker_id: str, handler: Callable[[dict[str, Any]], Mapping[str, Any]], limit: int | None = None) -> dict[str, Any]:
        jobs = self.claim_jobs(worker_id=worker_id, limit=limit)
        completed: list[str] = []
        failed: list[str] = []
        if not jobs:
            return {"completed": completed, "failed": failed, "parallelism": 0}

        def execute(job: dict[str, Any]):
            return job, handler(job)

        with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
            futures = [executor.submit(execute, job) for job in jobs]
            for future in as_completed(futures):
                job: dict[str, Any] | None = None
                try:
                    job, result = future.result()
                    safe_result = _redact(dict(result))
                    token_use = int(safe_result.get("tokens_used", 0))
                    cost = float(safe_result.get("cost", 0.0))
                    budget_id = job.get("budget_id")
                    if budget_id:
                        budget = self.db.one("SELECT * FROM agent_budgets_208 WHERE budget_id=?", (budget_id,))
                        if not budget or budget["status"] != "active" or budget["used_tokens"] + token_use > budget["max_tokens"] or budget["used_cost"] + cost > budget["max_cost"]:
                            raise RuntimeError("budget_exceeded")
                        self.db.execute(
                            "UPDATE agent_budgets_208 SET used_tokens=used_tokens+?,used_cost=used_cost+?,updated_at=? WHERE budget_id=?",
                            (token_use, cost, now_ts(), budget_id),
                        )
                    self.db.execute(
                        'UPDATE agent_jobs_208 SET status="completed",output_json=?,error_text=NULL,updated_at=? WHERE job_id=?',
                        (dumps(safe_result), now_ts(), job["job_id"]),
                    )
                    completed.append(job["job_id"])
                except Exception as exc:
                    if job:
                        status = "retry" if int(job["attempt"]) < int(job["max_attempts"]) else "failed"
                        self.db.execute(
                            "UPDATE agent_jobs_208 SET status=?,error_text=?,worker_id=NULL,updated_at=? WHERE job_id=?",
                            (status, str(exc)[:500], now_ts(), job["job_id"]),
                        )
                        failed.append(job["job_id"])
        self.db.execute('UPDATE agent_workers_208 SET status="idle",last_heartbeat=? WHERE worker_id=?', (now_ts(), worker_id))
        return {"completed": completed, "failed": failed, "parallelism": len(jobs)}

    def create_profile(self, *, case_id: str, display_name: str, names: Sequence[str], identifiers: Mapping[str, Any] | None = None, attributes: Mapping[str, Any] | None = None, confirmation: str) -> dict[str, Any]:
        if confirmation != f"ENTITY PROFILE 208 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        all_names = sorted({display_name.strip(), *(str(name).strip() for name in names if str(name).strip())})
        scripts = sorted({_script(name) for name in all_names})
        profile_id = new_id("entity208")
        created_at = now_ts()
        payload = {
            "profile_id": profile_id,
            "case_id": case_id,
            "display_name": display_name.strip(),
            "names": all_names,
            "scripts": scripts,
            "identifiers": _redact(dict(identifiers or {})),
            "attributes": _redact(dict(attributes or {})),
            "status": "candidate",
            "created_at": created_at,
        }
        self.db.execute(
            "INSERT INTO entity_resolution_profiles_208 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (profile_id, case_id, payload["display_name"], dumps(all_names), dumps(scripts), dumps(payload["identifiers"]), dumps(payload["attributes"]), "candidate", created_at, created_at, _hash(payload)),
        )
        return payload

    def resolve(self, *, case_id: str, left_profile_id: str, right_profile_id: str, citations: Sequence[Mapping[str, Any]], confirmation: str) -> dict[str, Any]:
        if confirmation != f"ENTITY RESOLUTION 208 {case_id} PRUEFEN":
            raise PermissionError("explicit approval required")
        left = self.db.one("SELECT * FROM entity_resolution_profiles_208 WHERE profile_id=? AND case_id=?", (left_profile_id, case_id))
        right = self.db.one("SELECT * FROM entity_resolution_profiles_208 WHERE profile_id=? AND case_id=?", (right_profile_id, case_id))
        if not left or not right:
            raise KeyError("profile")
        left_names = json.loads(left["names_json"])
        right_names = json.loads(right["names_json"])
        exact = {name.casefold() for name in left_names} & {name.casefold() for name in right_names}
        transliterated = {_latin(name) for name in left_names} & {_latin(name) for name in right_names}
        signals = []
        conflicts = []
        if exact:
            signals.append({"type": "exact_name", "weight": 0.45, "values": sorted(exact)})
        if transliterated:
            signals.append({"type": "cross_script_transliteration", "weight": 0.30, "values": sorted(transliterated)})
        left_ids = json.loads(left["identifiers_json"])
        right_ids = json.loads(right["identifiers_json"])
        shared = {key: value for key, value in left_ids.items() if key in right_ids and right_ids[key] == value and value}
        if shared:
            signals.append({"type": "shared_identifier", "weight": 0.55, "values": shared})
        for key in set(left_ids) & set(right_ids):
            if left_ids[key] and right_ids[key] and left_ids[key] != right_ids[key]:
                conflicts.append({"type": "identifier_conflict", "field": key, "left": left_ids[key], "right": right_ids[key]})
        independent_sources = len({str(item.get("source_ref") or item.get("source_id")) for item in citations if item.get("independent", True)})
        score = min(0.99, sum(float(signal["weight"]) for signal in signals) + (0.1 if independent_sources >= 2 else 0.0) - (0.35 if conflicts else 0.0))
        status = "conflicted_candidate" if conflicts else ("corroborated_candidate" if score >= 0.65 and independent_sources >= 2 else "candidate")
        candidate_id = new_id("ercand208")
        payload = {
            "candidate_id": candidate_id,
            "case_id": case_id,
            "left_profile_id": left_profile_id,
            "right_profile_id": right_profile_id,
            "signals": signals,
            "conflicts": conflicts,
            "score": round(max(0.0, score), 3),
            "status": status,
            "citations": [_redact(dict(item)) for item in citations],
            "created_at": now_ts(),
            "same_person_confirmed": False,
        }
        self.db.execute(
            "INSERT INTO entity_resolution_candidates_208 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (candidate_id, case_id, left_profile_id, right_profile_id, dumps(signals), dumps(conflicts), payload["score"], status, dumps(payload["citations"]), payload["created_at"], _hash(payload)),
        )
        return payload

    def benchmark(self, *, name: str, agent_id: str, language: str, task_type: str, metrics: Mapping[str, float], thresholds: Mapping[str, float], confirmation: str) -> dict[str, Any]:
        if confirmation != f"AGENT BENCHMARK 208 {name} PRUEFEN":
            raise PermissionError("explicit approval required")
        passed = True
        for key, threshold in thresholds.items():
            if key.endswith("_max"):
                passed = passed and float(metrics.get(key[:-4], float("inf"))) <= float(threshold)
            else:
                passed = passed and float(metrics.get(key, float("-inf"))) >= float(threshold)
        benchmark_id = new_id("bench208")
        status = "passed" if passed else "failed"
        payload = {"benchmark_id": benchmark_id, "name": name, "agent_id": agent_id, "language": language, "task_type": task_type, "metrics": dict(metrics), "thresholds": dict(thresholds), "status": status, "created_at": now_ts()}
        self.db.execute(
            "INSERT INTO agent_benchmarks_208 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (benchmark_id, name, agent_id, language, task_type, dumps(dict(metrics)), dumps(dict(thresholds)), status, payload["created_at"], _hash(payload)),
        )
        return payload

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        return {
            "build": self.BUILD,
            "case_id": case_id,
            "workers": [dict(row) for row in self.db.all("SELECT * FROM agent_workers_208 ORDER BY worker_id")],
            "jobs": [dict(row) for row in self.db.all("SELECT * FROM agent_jobs_208 WHERE case_id=? ORDER BY created_at DESC LIMIT 100", (case_id,))],
            "budgets": [dict(row) for row in self.db.all("SELECT * FROM agent_budgets_208 WHERE case_id=?", (case_id,))],
            "entity_candidates": [dict(row) for row in self.db.all("SELECT * FROM entity_resolution_candidates_208 WHERE case_id=? ORDER BY created_at DESC", (case_id,))],
            "parallel_agents": True,
            "resume_supported": True,
            "human_review_required": True,
        }

    def render_dashboard(self, *, case_id: str) -> str:
        dashboard = self.dashboard(case_id=case_id)
        worker_rows = "".join(
            f"<tr><td>{html.escape(row['name'])}</td><td>{html.escape(row['status'])}</td><td>{row['max_parallel']}</td><td>{html.escape(row['last_heartbeat'])}</td></tr>"
            for row in dashboard["workers"]
        )
        job_rows = "".join(
            f"<tr><td>{html.escape(row['task_type'])}</td><td>{html.escape(row['status'])}</td><td>{row['attempt']}/{row['max_attempts']}</td><td>{html.escape(row.get('worker_id') or '—')}</td></tr>"
            for row in dashboard["jobs"]
        )
        return f'''<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EagleEye Agenten 208</title><style>body{{font-family:system-ui;background:#10151d;color:#edf2f7;margin:0}}main{{max-width:1200px;margin:auto;padding:28px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}}.card{{background:#18212d;border:1px solid #314156;border-radius:12px;padding:18px;margin:14px 0}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:9px;border-bottom:1px solid #314156}}.pill{{display:inline-block;padding:5px 9px;border-radius:99px;background:#26364b}}a{{color:#9cd5ff}}</style></head><body><main><h1>AI-Agenten & Entity Resolution · Build 208</h1><p>Fall: <b>{html.escape(case_id)}</b> · Parallel, wiederaufnehmbar, budgetiert und review-first.</p><div class="grid"><div class="card"><h2>Worker</h2><span class="pill">{len(dashboard['workers'])} persistent</span></div><div class="card"><h2>Jobs</h2><span class="pill">{len(dashboard['jobs'])} sichtbar</span></div><div class="card"><h2>Entity-Kandidaten</h2><span class="pill">{len(dashboard['entity_candidates'])}</span></div></div><div class="card"><h2>Dauerhafte Agenten-Worker</h2><table><tr><th>Worker</th><th>Status</th><th>Parallelität</th><th>Heartbeat</th></tr>{worker_rows}</table></div><div class="card"><h2>Agenten-Jobs</h2><table><tr><th>Aufgabe</th><th>Status</th><th>Versuch</th><th>Worker</th></tr>{job_rows}</table></div><p>Keine automatische Identitätsbestätigung oder Falländerung. <a href="/">Zurück zum Workspace</a></p></main></body></html>'''
