from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import datetime, timezone
from collections import defaultdict
from typing import Any, Iterable
from urllib.parse import quote_plus

from eagleeye_pro.core.database import dumps, loads, new_id, now_ts
from eagleeye_pro.providers.dork_engine import ENGINES
from eagleeye_pro.security.policy import PolicyGate


ANCHOR_TYPES = {
    "alias", "username", "email", "location", "organisation", "role", "domain",
    "birth_year", "date", "public_url", "identifier", "keyword",
}


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _quote(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return ""
    if text.startswith('"') and text.endswith('"'):
        return text
    return f'"{text}"'


def _table_exists(db: Any, table: str) -> bool:
    return bool(db.one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)))


class ScalePerformance123Service:
    """Build 123 adaptive research, controlled jobs, provider diagnostics and graph projection.

    The service is deliberately synchronous at the execution boundary. Jobs are persisted
    before execution and can be recovered, while no hidden worker thread is started by the
    browser process. This keeps the local application deterministic and prepares a later
    worker process without creating an unreviewed background network channel.
    """

    DEFAULT_ENGINES = ("Google", "Bing", "DuckDuckGo", "Brave", "Startpage")

    def __init__(self, db: Any, audit: Any, *, cases: Any, targets: Any, ai_search: Any) -> None:
        self.db = db
        self.audit = audit
        self.cases = cases
        self.targets = targets
        self.ai_search = ai_search
        self.ensure_schema()

    def ensure_schema(self) -> None:
        from eagleeye.infrastructure.scale.schema import ensure_scale_schema_123
        ensure_scale_schema_123(self.db)

    def _target(self, case_id: str, target_id: str) -> dict[str, Any]:
        self.cases.get_case(case_id)
        target = self.targets.get_target(target_id)
        if target.get("case_id") != case_id:
            raise ValueError("Fall-/Zielbindung verletzt")
        return target

    @staticmethod
    def _append(bucket: list[dict[str, Any]], typ: str, value: Any, reliability: float, source_kind: str, source_id: str = "") -> None:
        text = " ".join(str(value or "").strip().split())
        if len(text) < 2:
            return
        key = (typ, _norm(text))
        if any((item["type"], item["normalized"]) == key for item in bucket):
            return
        bucket.append({
            "type": typ, "value": text, "normalized": key[1],
            "reliability": max(0.0, min(1.0, float(reliability))),
            "source_kind": source_kind, "source_id": source_id,
        })

    def build_profile(self, case_id: str, target_id: str, *, persist: bool = True) -> dict[str, Any]:
        target = self._target(case_id, target_id)
        anchors: list[dict[str, Any]] = []
        self._append(anchors, "name", target.get("name"), 0.75, "target", target_id)
        mapping = {
            "aliases_json": ("alias", 0.70), "usernames_json": ("username", 0.78),
            "emails_json": ("email", 0.92), "locations_json": ("location", 0.62),
            "companies_json": ("organisation", 0.68), "domains_json": ("domain", 0.82),
        }
        for field, (typ, reliability) in mapping.items():
            for value in target.get(field, []) or []:
                self._append(anchors, typ, value, reliability, "target", target_id)

        if _table_exists(self.db, "resolution_entities_115"):
            entity = self.db.one(
                "SELECT resolution_entity_id FROM resolution_entities_115 WHERE case_id=? AND source_entity_id=?",
                (case_id, target_id),
            )
            if entity:
                eid = entity["resolution_entity_id"]
                for row in self.db.all("SELECT alias,alias_kind,alias_id FROM resolution_aliases_115 WHERE resolution_entity_id=?", (eid,)):
                    self._append(anchors, "alias", row.get("alias"), 0.72, "resolution_alias", row.get("alias_id", ""))
                for row in self.db.all("SELECT anchor_type,anchor_value,reliability,anchor_id FROM resolution_anchors_115 WHERE resolution_entity_id=?", (eid,)):
                    typ = str(row.get("anchor_type") or "identifier")
                    if typ not in ANCHOR_TYPES:
                        typ = "identifier"
                    self._append(anchors, typ, row.get("anchor_value"), float(row.get("reliability") or 0.5), "resolution_anchor", row.get("anchor_id", ""))

        for row in self.db.all(
            "SELECT * FROM research_anchors_123 WHERE case_id=? AND target_id=? AND review_status='reviewed' ORDER BY reliability DESC,created_at",
            (case_id, target_id),
        ):
            self._append(anchors, row["anchor_type"], row["anchor_value"], float(row["reliability"]), "analyst_reviewed", row["anchor_id"])

        if _table_exists(self.db, "search_chain_nodes_54"):
            rows = self.db.all(
                "SELECT * FROM search_chain_nodes_54 WHERE case_id=? AND status='active' AND confidence_label IN ('reviewed','confirmed') ORDER BY relevance_score DESC LIMIT 100",
                (case_id,),
            )
            for row in rows:
                meta = loads(row.get("metadata_json"), {}) or {}
                typ = str(meta.get("fact_type") or "keyword")
                if typ not in ANCHOR_TYPES:
                    typ = "keyword"
                self._append(anchors, typ, row.get("value"), min(0.95, max(0.5, float(row.get("relevance_score") or 50) / 100)), "reviewed_chain_fact", row.get("node_id", ""))

        type_counts: dict[str, int] = defaultdict(int)
        for item in anchors:
            type_counts[item["type"]] += 1
        strong_types = {"name", "alias", "username", "email", "location", "organisation", "domain", "role", "birth_year", "identifier"}
        covered = len(set(type_counts) & strong_types)
        reliability_points = sum(item["reliability"] for item in anchors if item["type"] != "name")
        completeness = min(100, int(18 + covered * 9 + min(35, reliability_points * 4)))
        serial = {
            "target_id": target_id, "name": target.get("name"), "anchors": anchors,
            "type_counts": dict(type_counts), "completeness": completeness,
        }
        digest = hashlib.sha256(dumps(serial).encode("utf-8")).hexdigest()
        serial["profile_digest"] = digest
        serial["anchor_count"] = len(anchors)
        serial["type_count"] = len(type_counts)
        if persist:
            self.db.execute(
                "INSERT OR IGNORE INTO research_profiles_123(profile_id,case_id,target_id,profile_digest,completeness,anchor_count,type_count,profile_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (new_id("rprof123"), case_id, target_id, digest, completeness, len(anchors), len(type_counts), dumps(serial), now_ts()),
            )
        return serial

    def add_anchor(self, *, case_id: str, target_id: str, anchor_type: str, value: str, reliability: float, actor: str) -> dict[str, Any]:
        self._target(case_id, target_id)
        typ = (anchor_type or "").strip().casefold()
        if typ not in ANCHOR_TYPES:
            raise ValueError("Nicht unterstützter Ankertyp")
        text = " ".join((value or "").strip().split())
        if len(text) < 2:
            raise ValueError("Der Rechercheanker ist zu kurz")
        rel = max(0.1, min(1.0, float(reliability)))
        now = now_ts()
        anchor_id = new_id("ranchor123")
        self.db.execute(
            """INSERT INTO research_anchors_123(anchor_id,case_id,target_id,anchor_type,anchor_value,normalized_value,reliability,source_kind,source_id,review_status,created_by,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,'reviewed',?,?,?)
               ON CONFLICT(case_id,target_id,anchor_type,normalized_value) DO UPDATE SET
                 anchor_value=excluded.anchor_value,reliability=excluded.reliability,review_status='reviewed',updated_at=excluded.updated_at""",
            (anchor_id, case_id, target_id, typ, text, _norm(text), rel, "analyst_input", "", actor, now, now),
        )
        row = self.db.one(
            "SELECT * FROM research_anchors_123 WHERE case_id=? AND target_id=? AND anchor_type=? AND normalized_value=?",
            (case_id, target_id, typ, _norm(text)),
        )
        self.audit.log("review", "research_anchor_123", row["anchor_id"], case_id, {"target_id": target_id, "type": typ, "reliability": rel})
        return row

    @staticmethod
    def _group(profile: dict[str, Any]) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for item in profile.get("anchors", []):
            value = str(item.get("value") or "").strip()
            if value and value not in grouped[item["type"]]:
                grouped[item["type"]].append(value)
        return grouped

    def generate_query_plan(self, case_id: str, target_id: str, *, limit: int = 80) -> dict[str, Any]:
        profile = self.build_profile(case_id, target_id)
        grouped = self._group(profile)
        names = grouped.get("name", [])
        if not names:
            raise ValueError("Kein belastbarer Namensanker vorhanden")
        name = names[0]
        base = _quote(name)
        candidates: list[dict[str, Any]] = []

        def add(category: str, query: str, score: int, used: Iterable[tuple[str, str]], rationale: str) -> None:
            query = " ".join((query or "").split())
            if not query or not PolicyGate.evaluate_query(query).get("ok"):
                return
            key = query.casefold()
            if any(item["query"].casefold() == key for item in candidates):
                return
            anchors = [{"type": typ, "value": value} for typ, value in used if value]
            candidates.append({
                "category": category, "query": query[:400], "precision_score": max(1, min(100, score)),
                "anchor_count": len(anchors), "anchors": anchors, "rationale": rationale[:500],
            })

        add("Identitätsanker", base, 42, [("name", name)], "Exakter Namensanker als Ausgangspunkt")
        add("Dokumente", f"{base} filetype:pdf", 48, [("name", name)], "Öffentliche Dokumente zur Zielperson")
        add("Presse", f"{base} (Presse OR Interview OR Profil OR Vortrag)", 48, [("name", name)], "Öffentliche Medien- und Profilspuren")
        add("Gegenbelege/Namensdoppler", f"{base} (Namensdoppler OR Verwechslung)", 45, [("name", name)], "Aktive Suche nach Alternativpersonen und Gegenbelegen")

        singles = [
            ("alias", "Alias", 62), ("username", "Username + Name", 78), ("email", "E-Mail", 92),
            ("location", "Ortskontext", 68), ("organisation", "Beruf/Firma", 72),
            ("role", "Rollenbezug", 72), ("domain", "Domain", 84),
            ("birth_year", "Zeitliche Disambiguierung", 76), ("identifier", "Identifikator", 86),
            ("keyword", "Kontextanker", 60),
        ]
        for typ, category, score in singles:
            for value in grouped.get(typ, [])[:5]:
                if typ == "email":
                    query = _quote(value)
                elif typ == "domain":
                    query = f"site:{value} {base}"
                elif typ == "username":
                    query = f"{_quote(value)} {base}"
                else:
                    query = f"{base} {_quote(value)}"
                add(category, query, score, [("name", name), (typ, value)], f"Name mit geprüftem {typ}-Anker zur Disambiguierung")

        aliases = grouped.get("alias", [])[:3]
        locations = grouped.get("location", [])[:4]
        orgs = grouped.get("organisation", [])[:4]
        roles = grouped.get("role", [])[:3]
        usernames = grouped.get("username", [])[:4]
        domains = grouped.get("domain", [])[:3]

        for location in locations:
            for org in orgs:
                add("Hochpräzise Kombination", f"{base} {_quote(org)} {_quote(location)}", 88,
                    [("name", name), ("organisation", org), ("location", location)],
                    "Drei bestätigte Anker reduzieren Namensdoppler")
        for alias in aliases:
            for location in locations[:2]:
                add("Alias-Disambiguierung", f"{_quote(alias)} {base} {_quote(location)}", 84,
                    [("alias", alias), ("name", name), ("location", location)], "Alias, Hauptname und Ort kombiniert")
        for username in usernames:
            for domain in domains[:2]:
                add("Digitale Korrelation", f"{_quote(username)} site:{domain}", 92,
                    [("username", username), ("domain", domain)], "Geprüfter Username auf fallbekannter Domain")
        for role in roles:
            for org in orgs[:2]:
                add("Berufsrolle", f"{base} {_quote(role)} {_quote(org)}", 88,
                    [("name", name), ("role", role), ("organisation", org)], "Name, Rolle und Organisation kombiniert")

        source_sites = [
            ("linkedin.com/in", "Öffentliches Berufsprofil"), ("xing.com/profile", "Öffentliches Berufsprofil"),
            ("github.com", "Technisches Profil"), ("orcid.org", "Fachprofil"),
            ("researchgate.net", "Fachprofil"), ("bundesanzeiger.de", "Register"),
        ]
        context = " ".join(_quote(x) for x in (orgs[:1] + locations[:1]))
        for site, category in source_sites:
            add(category, f"site:{site} {base} {context}".strip(), 66 + (8 if context else 0),
                [("name", name)] + ([('organisation', orgs[0])] if orgs else []) + ([('location', locations[0])] if locations else []),
                f"Quellenspezifische Suche auf {site}")

        candidates.sort(key=lambda item: (-item["precision_score"], -item["anchor_count"], item["category"], item["query"]))
        return {"profile": profile, "queries": candidates[:max(1, min(int(limit), 150))]}

    def _create_package(self, case_id: str, target_id: str, profile: dict[str, Any]) -> str:
        package_id = new_id("pkg123")
        now = now_ts()
        self.db.execute(
            "INSERT INTO search_packages(package_id,case_id,target_id,package_key,name,objective,status,created_at,updated_at,notes) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (package_id, case_id, target_id, "adaptive_person_123", "Adaptive Personenrecherche",
             "Personenspezifische Queries aus geprüften Rechercheankern", "active", now, now,
             f"Build 123 · Profilvollständigkeit {profile['completeness']}% · Digest {profile['profile_digest'][:12]}"),
        )
        return package_id

    def queue_query_plan(self, *, case_id: str, target_id: str, queries: list[dict[str, Any]], engines: Iterable[str], actor: str, source_kind: str = "adaptive_profile") -> dict[str, Any]:
        profile = self.build_profile(case_id, target_id)
        selected = [engine for engine in engines if engine in ENGINES]
        if not selected:
            selected = list(self.DEFAULT_ENGINES)
        package_id = self._create_package(case_id, target_id, profile)
        created = duplicates = 0
        now = now_ts()
        for item in queries:
            query = " ".join(str(item.get("query") or "").split())[:400]
            if not query or not PolicyGate.evaluate_query(query).get("ok"):
                continue
            category = str(item.get("category") or "AI-Query-Plan")[:100]
            score = max(1, min(100, int(item.get("precision_score") or 60)))
            anchor_count = max(1, int(item.get("anchor_count") or 1))
            rationale = str(item.get("rationale") or item.get("objective") or "Personenspezifischer Query-Plan")[:500]
            for engine in selected:
                novelty = hashlib.sha256(f"{target_id}|{engine}|{query.casefold()}".encode("utf-8")).hexdigest()
                existing = self.db.one("SELECT task_id FROM adaptive_search_tasks_123 WHERE case_id=? AND target_id=? AND novelty_key=?", (case_id, target_id, novelty))
                if existing:
                    duplicates += 1
                    continue
                task_id = new_id("task")
                self.db.execute(
                    "INSERT INTO search_tasks(task_id,case_id,target_id,category,query,engine,url,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (task_id, case_id, target_id, category, query, engine, ENGINES[engine].format(q=quote_plus(query)), "planned", now),
                )
                self.db.execute("INSERT INTO search_package_tasks(package_id,task_id,created_at) VALUES(?,?,?)", (package_id, task_id, now))
                self.db.execute(
                    "INSERT INTO adaptive_search_tasks_123(adaptive_id,task_id,case_id,target_id,profile_digest,precision_score,anchor_count,rationale,novelty_key,source_kind,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (new_id("adapt123"), task_id, case_id, target_id, profile["profile_digest"], score, anchor_count, rationale, novelty, source_kind, now),
                )
                created += 1
        if created == 0:
            self.db.execute("DELETE FROM search_packages WHERE package_id=?", (package_id,))
            package_id = ""
        self.audit.log("queue", "adaptive_research_123", package_id or target_id, case_id, {
            "target_id": target_id, "created": created, "duplicates": duplicates, "engines": selected,
            "profile_digest": profile["profile_digest"], "source_kind": source_kind,
        })
        return {"package_id": package_id, "tasks": created, "duplicates": duplicates, "engines": selected, "profile": profile}

    def create_adaptive_research(self, *, case_id: str, target_id: str, engines: Iterable[str], actor: str, limit: int = 80) -> dict[str, Any]:
        plan = self.generate_query_plan(case_id, target_id, limit=limit)
        return self.queue_query_plan(case_id=case_id, target_id=target_id, queries=plan["queries"], engines=engines, actor=actor)

    def create_job(self, *, case_id: str, target_id: str, job_type: str, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        self.cases.get_case(case_id)
        if target_id:
            self._target(case_id, target_id)
        if job_type not in {"adaptive_research", "ai_browser_queue", "provider_diagnostic"}:
            raise ValueError("Nicht unterstützter Hintergrundjob")
        job_id = new_id("job123")
        now = now_ts()
        self.db.execute(
            "INSERT INTO background_jobs_123(job_id,case_id,target_id,job_type,payload_json,status,created_by,created_at,updated_at) VALUES(?,?,?,?,?,'queued',?,?,?)",
            (job_id, case_id, target_id, job_type, dumps(payload), actor, now, now),
        )
        return self.db.one("SELECT * FROM background_jobs_123 WHERE job_id=?", (job_id,))

    def run_job(self, job_id: str) -> dict[str, Any]:
        job = self.db.one("SELECT * FROM background_jobs_123 WHERE job_id=?", (job_id,))
        if not job:
            raise KeyError("Job nicht gefunden")
        if job["status"] not in {"queued", "retry"}:
            return job
        payload = loads(job.get("payload_json"), {}) or {}
        with self.db.transaction(immediate=True):
            cursor = self.db.execute(
                "UPDATE background_jobs_123 SET status='running',attempts=attempts+1,started_at=?,updated_at=? WHERE job_id=? AND status IN ('queued','retry')",
                (now_ts(), now_ts(), job_id),
            )
            if getattr(cursor, "rowcount", 0) != 1:
                raise ValueError("Job wurde parallel übernommen")
        try:
            if job["job_type"] == "adaptive_research":
                result = self.create_adaptive_research(
                    case_id=job["case_id"], target_id=job["target_id"],
                    engines=payload.get("engines") or self.DEFAULT_ENGINES,
                    actor=job["created_by"], limit=int(payload.get("limit") or 80),
                )
            elif job["job_type"] == "ai_browser_queue":
                requested = list(payload.get("queries") or [])
                adaptive = self.generate_query_plan(job["case_id"], job["target_id"], limit=max(8, len(requested) * 2))["queries"]
                ai_items = [
                    {"category": "AI-Query-Plan", "query": item.get("query", ""),
                     "precision_score": 65, "anchor_count": 1,
                     "rationale": item.get("objective") or "Lokal erzeugter AI-Queryvorschlag"}
                    for item in requested
                ]
                result = self.queue_query_plan(
                    case_id=job["case_id"], target_id=job["target_id"],
                    queries=(adaptive + ai_items)[:max(12, len(requested) * 3)], engines=payload.get("engines") or self.DEFAULT_ENGINES,
                    actor=job["created_by"], source_kind="ai_browser_queue",
                )
            else:
                result = self.check_provider(case_id=job["case_id"], provider=str(payload.get("provider") or "browser_queue"))
            self.db.execute(
                "UPDATE background_jobs_123 SET status='completed',result_json=?,error_text='',completed_at=?,updated_at=? WHERE job_id=?",
                (dumps(result), now_ts(), now_ts(), job_id),
            )
        except Exception as exc:
            current = self.db.one("SELECT attempts,max_attempts FROM background_jobs_123 WHERE job_id=?", (job_id,)) or {}
            status = "retry" if int(current.get("attempts") or 1) < int(current.get("max_attempts") or 2) else "failed"
            self.db.execute(
                "UPDATE background_jobs_123 SET status=?,error_text=?,completed_at=?,updated_at=? WHERE job_id=?",
                (status, str(exc)[:2000], now_ts(), now_ts(), job_id),
            )
            self.audit.log("fail", "background_job_123", job_id, job["case_id"], {"error": str(exc), "status": status})
            raise
        result_row = self.db.one("SELECT * FROM background_jobs_123 WHERE job_id=?", (job_id,))
        self.audit.log("complete", "background_job_123", job_id, job["case_id"], {"job_type": job["job_type"]})
        return result_row

    def recover_stale_jobs(self, *, case_id: str, stale_seconds: int = 300) -> dict[str, Any]:
        self.cases.get_case(case_id)
        now_epoch = time.time()
        recovered = failed = 0
        rows = self.db.all("SELECT * FROM background_jobs_123 WHERE case_id=? AND status='running'", (case_id,))
        for row in rows:
            stamp = row.get("started_at") or row.get("updated_at") or row.get("created_at") or ""
            try:
                parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                age = now_epoch - parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).timestamp()
            except Exception:
                age = stale_seconds + 1
            if age < max(30, int(stale_seconds)):
                continue
            new_status = "retry" if int(row.get("attempts") or 0) < int(row.get("max_attempts") or 2) else "failed"
            self.db.execute(
                "UPDATE background_jobs_123 SET status=?,error_text=?,updated_at=? WHERE job_id=? AND status='running'",
                (new_status, "Recovered after stale running state", now_ts(), row["job_id"]),
            )
            if new_status == "retry":
                recovered += 1
            else:
                failed += 1
            self.audit.log("recover", "background_job_123", row["job_id"], case_id, {"new_status": new_status, "stale_seconds": stale_seconds})
        return {"recovered": recovered, "failed": failed, "checked": len(rows)}

    def performance_snapshot(self, case_id: str, *, target_id: str = "") -> dict[str, Any]:
        self.cases.get_case(case_id)
        targets = self.targets.list_targets(case_id)
        selected = target_id or (targets[0]["target_id"] if targets else "")
        budgets = {"task_page": 150.0, "graph_projection": 750.0, "profile_build": 250.0}
        samples: list[dict[str, Any]] = []

        def measure(operation: str, item_count: int, function: Any) -> Any:
            started = time.perf_counter()
            value = function()
            elapsed = (time.perf_counter() - started) * 1000.0
            budget = budgets[operation]
            sample = {"operation": operation, "elapsed_ms": round(elapsed, 3), "budget_ms": budget, "within_budget": elapsed <= budget, "item_count": int(item_count)}
            samples.append(sample)
            self.db.execute(
                "INSERT INTO performance_samples_123(sample_id,case_id,operation,elapsed_ms,budget_ms,within_budget,item_count,details_json,measured_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (new_id("perf123"), case_id, operation, elapsed, budget, int(elapsed <= budget), int(item_count), dumps({}), now_ts()),
            )
            return value

        task_count = int((self.db.one("SELECT COUNT(*) n FROM search_tasks WHERE case_id=?", (case_id,)) or {"n": 0})["n"])
        graph_counts = int((self.db.one("SELECT COUNT(*) n FROM provider_intake_120 WHERE case_id=?", (case_id,)) or {"n": 0})["n"])
        measure("task_page", task_count, lambda: self.list_tasks(case_id, target_id=selected, page=1, page_size=50) if selected else self.list_tasks(case_id, page=1, page_size=50))
        measure("graph_projection", graph_counts, lambda: self.graph_payload(case_id, limit_nodes=600, limit_edges=1200))
        if selected:
            measure("profile_build", len(targets), lambda: self.build_profile(case_id, selected, persist=False))
        return {"case_id": case_id, "samples": samples, "all_within_budget": all(item["within_budget"] for item in samples), "budgets_ms": budgets}


    def check_provider(self, *, case_id: str | None, provider: str) -> dict[str, Any]:
        status = self.ai_search.provider_status(provider)
        self.db.execute(
            "INSERT INTO provider_diagnostics_123(diagnostic_id,case_id,provider,ready,detail,checked_at) VALUES(?,?,?,?,?,?)",
            (new_id("pdiag123"), case_id, status["provider"], int(bool(status.get("ready"))), str(status.get("detail") or ""), now_ts()),
        )
        return status

    def list_jobs(self, case_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM background_jobs_123 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, max(1, min(int(limit), 200))))

    def list_tasks(self, case_id: str, *, target_id: str = "", page: int = 1, page_size: int = 50, min_precision: int = 0, status: str = "all") -> dict[str, Any]:
        page = max(1, int(page)); page_size = max(10, min(int(page_size), 200)); offset = (page - 1) * page_size
        where = ["st.case_id=?"]; params: list[Any] = [case_id]
        if target_id:
            self._target(case_id, target_id); where.append("st.target_id=?"); params.append(target_id)
        if status != "all":
            where.append("st.status=?"); params.append(status)
        where.append("COALESCE(ast.precision_score,0)>=?"); params.append(max(0, min(100, int(min_precision))))
        sql_where = " AND ".join(where)
        total = int((self.db.one(f"SELECT COUNT(*) n FROM search_tasks st LEFT JOIN adaptive_search_tasks_123 ast ON ast.task_id=st.task_id WHERE {sql_where}", params) or {"n": 0})["n"])
        rows = self.db.all(
            f"""SELECT st.*,COALESCE(sp.name,'Legacy') package_name,COALESCE(sp.package_key,'legacy') package_key,
                       COALESCE(ast.precision_score,0) precision_score,COALESCE(ast.anchor_count,0) anchor_count,
                       COALESCE(ast.rationale,'Legacy/standard query') rationale,COALESCE(ast.source_kind,'legacy') source_kind
                FROM search_tasks st
                LEFT JOIN search_package_tasks spt ON spt.task_id=st.task_id
                LEFT JOIN search_packages sp ON sp.package_id=spt.package_id
                LEFT JOIN adaptive_search_tasks_123 ast ON ast.task_id=st.task_id
                WHERE {sql_where}
                ORDER BY COALESCE(ast.precision_score,0) DESC,st.created_at DESC
                LIMIT ? OFFSET ?""",
            [*params, page_size, offset],
        )
        return {"rows": rows, "total": total, "page": page, "page_size": page_size, "pages": max(1, math.ceil(total / page_size))}

    def graph_payload(self, case_id: str, *, limit_nodes: int = 600, limit_edges: int = 1200, query: str = "") -> dict[str, Any]:
        self.cases.get_case(case_id)
        limit_nodes = max(50, min(int(limit_nodes), 5000)); limit_edges = max(100, min(int(limit_edges), 20000))
        nodes: dict[str, dict[str, Any]] = {}
        edges: dict[str, dict[str, Any]] = {}

        def node(node_id: str, label: Any, typ: str, *, value: Any = "", confidence: int = 50, candidate: bool = True, source: str = "") -> None:
            if not node_id or len(nodes) >= limit_nodes:
                return
            text = str(label or value or node_id)
            if query and query.casefold() not in f"{text} {value} {typ}".casefold():
                return
            nodes.setdefault(node_id, {"id": node_id, "label": text[:160], "type": typ, "value": str(value or "")[:500], "confidence": int(confidence), "candidate": bool(candidate), "source": source})

        def edge(edge_id: str, source: str, target: str, label: Any, typ: str = "relation", confidence: int = 50, candidate: bool = True) -> None:
            if not source or not target or len(edges) >= limit_edges:
                return
            edges.setdefault(edge_id, {"id": edge_id, "source": source, "target": target, "label": str(label or typ)[:120], "type": typ, "confidence": int(confidence), "candidate": bool(candidate)})

        for target in self.targets.list_targets(case_id):
            tid = f"target:{target['target_id']}"
            node(tid, target.get("name"), "person", confidence=75, candidate=True, source="target")
            mapping = {"aliases_json": "alias", "emails_json": "email", "usernames_json": "username", "locations_json": "location", "companies_json": "organization", "domains_json": "domain"}
            for field, typ in mapping.items():
                for value in target.get(field, []) or []:
                    aid = f"anchor:{hashlib.sha256((target['target_id']+'|'+typ+'|'+_norm(value)).encode()).hexdigest()[:20]}"
                    node(aid, value, typ, confidence=70, source="target_anchor")
                    edge(f"edge:{aid}", tid, aid, typ, "profile_anchor", 70, True)

        if _table_exists(self.db, "resolution_entities_115"):
            for row in self.db.all("SELECT * FROM resolution_entities_115 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, limit_nodes)):
                node(row["resolution_entity_id"], row["display_name"], row["entity_type"], confidence=65, candidate=bool(row.get("candidate_only", 1)), source="resolution_115")
                if row.get("source_entity_id"):
                    edge(f"res-target:{row['resolution_entity_id']}", f"target:{row['source_entity_id']}", row["resolution_entity_id"], "resolution profile", "same_as_candidate", 60, True)

        if _table_exists(self.db, "investigation_graph_nodes_68"):
            for row in self.db.all("SELECT * FROM investigation_graph_nodes_68 WHERE case_id=? ORDER BY updated_at DESC LIMIT ?", (case_id, limit_nodes)):
                node(row["node_id"], row["label"], row["node_type"], value=row.get("value"), confidence=int(row.get("confidence") or 50), candidate=True, source="graph_68")
            for row in self.db.all("SELECT * FROM investigation_graph_edges_68 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, limit_edges)):
                edge(row["edge_id"], row["source_node_id"], row["target_node_id"], row["edge_type"], row["edge_type"], int(row.get("confidence") or 50), row.get("review_status") != "reviewed")

        if _table_exists(self.db, "graph_relations_116"):
            for row in self.db.all("SELECT * FROM graph_relations_116 WHERE case_id=? ORDER BY created_at DESC LIMIT ?", (case_id, limit_edges)):
                edge(row["relation_id"], row["subject_entity_id"], row["object_entity_id"], row["predicate"], "canonical_relation", 60, bool(row.get("candidate_only", 1)))

        for row in self.db.all("SELECT * FROM provider_intake_120 WHERE case_id=? ORDER BY created_at DESC LIMIT 250", (case_id,)):
            iid = f"intake:{row['intake_id']}"
            node(iid, row.get("title") or row.get("source_host") or "Intake", "source", value=row.get("canonical_url"), confidence=45, candidate=True, source="intake_120")
            if row.get("target_id"):
                edge(f"intake-target:{row['intake_id']}", f"target:{row['target_id']}", iid, "candidate source", "mentions", 45, True)

        for row in self.db.all("SELECT * FROM evidence_packages_121 WHERE case_id=? ORDER BY captured_at DESC LIMIT 250", (case_id,)):
            eid = f"evidence:{row['package_id']}"
            node(eid, row.get("title") or "Evidence", "evidence", value=row.get("source_url"), confidence=70, candidate=bool(row.get("candidate_only", 1)), source="evidence_121")
            source_ref = str(row.get("source_ref") or "")
            if source_ref:
                edge(f"evidence-source:{row['package_id']}", f"intake:{source_ref}", eid, "preserved as", "evidence", 75, bool(row.get("candidate_only", 1)))

        # Keep only edges whose endpoints are visible. If a filtered endpoint was omitted, omit its edge.
        visible_edges = [item for item in edges.values() if item["source"] in nodes and item["target"] in nodes]
        type_counts: dict[str, int] = defaultdict(int)
        for item in nodes.values():
            type_counts[item["type"]] += 1
        return {
            "nodes": list(nodes.values()), "edges": visible_edges[:limit_edges],
            "meta": {"node_count": len(nodes), "edge_count": len(visible_edges[:limit_edges]), "type_counts": dict(type_counts), "truncated": len(nodes) >= limit_nodes or len(edges) >= limit_edges},
        }
