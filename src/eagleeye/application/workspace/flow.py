from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlsplit


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _split(value: str | Iterable[str]) -> list[str]:
    if isinstance(value, str):
        parts = value.replace(";", ",").replace("\n", ",").split(",")
    else:
        parts = list(value)
    return [str(item).strip() for item in parts if str(item).strip()]


class InvestigationFlow1222Service:
    """Connect the canonical browser workspace to the proven investigation services.

    This service deliberately orchestrates existing components instead of replacing them:
    case/target -> resolution entity -> research workflow/tasks -> controlled intake ->
    evidence review and local/controlled AI assistance.
    """

    DEFAULT_ENGINES = ("Google", "Bing", "DuckDuckGo", "Brave", "Startpage")

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        cases: Any,
        targets: Any,
        entities: Any,
        workflows: Any,
        search_workbench: Any,
        intake_console: Any,
        local_ai: Any,
        ai_search: Any,
        scale: Any | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.cases = cases
        self.targets = targets
        self.entities = entities
        self.workflows = workflows
        self.search_workbench = search_workbench
        self.intake_console = intake_console
        self.local_ai = local_ai
        self.ai_search = ai_search
        self.scale = scale
        self.ensure_schema()
        self._ensure_local_provider("manual_public_intake", "Manual public intake")
        self._ensure_local_provider("ai_analyst_107", "Controlled AI search candidates")

    def ensure_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS investigation_subject_links_1222(
                link_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                target_id TEXT NOT NULL UNIQUE,
                resolution_entity_id TEXT NOT NULL UNIQUE,
                workflow_id TEXT NOT NULL UNIQUE,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_subject_links1222_case
                ON investigation_subject_links_1222(case_id,created_at);
            CREATE TABLE IF NOT EXISTS intake_bridges_1222(
                bridge_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                source_id TEXT NOT NULL,
                intake_id TEXT NOT NULL UNIQUE,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(case_id,source_kind,source_id),
                FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
                FOREIGN KEY(intake_id) REFERENCES provider_intake_120(intake_id) ON DELETE CASCADE
            );
            """
        )
        self.db.conn.commit()

    def _case(self, case_id: str) -> dict[str, Any]:
        return self.cases.get_case(case_id)

    def _target(self, case_id: str, target_id: str) -> dict[str, Any]:
        target = self.targets.get_target(target_id)
        if target.get("case_id") != case_id:
            raise ValueError("Fall-/Zielbindung verletzt")
        return target

    def _ensure_local_provider(self, key: str, label: str) -> None:
        now = _now()
        self.db.execute(
            """INSERT INTO provider_catalog_120(
                provider_key,label,provider_type,public_only,supports_live,supports_replay,
                allowed_hosts_json,rate_limit_per_minute,min_interval_seconds,timeout_seconds,
                max_attempts,backoff_base_seconds,circuit_failure_threshold,circuit_cooldown_seconds,
                max_response_bytes,terms_profile,enabled,metadata_json,registered_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(provider_key) DO UPDATE SET label=excluded.label,enabled=1,updated_at=excluded.updated_at""",
            (
                key, label, "local_bridge", 1, 0, 0, "[]", 0, 0.0, 0.0,
                1, 0.0, 1, 0.0, 200000, "manual_public_only", 1,
                _json({"build": "123.0", "network_execution": False}), now, now,
            ),
        )

    def create_subject(
        self,
        *,
        case_id: str,
        name: str,
        actor: str,
        aliases: str = "",
        emails: str = "",
        usernames: str = "",
        locations: str = "",
        companies: str = "",
        domains: str = "",
        notes: str = "",
        objective: str = "",
        create_research_tasks: bool = True,
        subject_type: str = "person",
    ) -> dict[str, Any]:
        self._case(case_id)
        name = name.strip()
        if len(name) < 2:
            raise ValueError("Name oder belastbarer Personenanker ist erforderlich")
        if not actor.strip():
            raise ValueError("Bearbeiter ist erforderlich")

        subject_type = (subject_type or "person").strip().lower()
        if subject_type not in {"person", "organization"}:
            raise ValueError("Zieltyp muss person oder organization sein")
        if subject_type == "organization":
            company_values = _split(companies)
            if name not in company_values:
                companies = ", ".join([name, *company_values])
        target = self.targets.create_target(
            case_id, name, aliases=aliases, emails=emails, usernames=usernames,
            locations=locations, companies=companies, domains=domains, notes=notes,
        )
        anchors: list[dict[str, Any]] = []
        for typ, values, reliability in (
            ("email", _split(emails), .85), ("username", _split(usernames), .65),
            ("location", _split(locations), .55), ("organisation", _split(companies), .60),
            ("domain", _split(domains), .70),
        ):
            anchors.extend({"type": typ, "value": value, "reliability": reliability, "source_ref": target["target_id"]} for value in values)

        entity_id = self.entities.register_entity(
            case_id, ("person" if subject_type == "person" else "organisation"), name, actor, source_entity_id=target["target_id"],
            attributes={"target_id": target["target_id"], "notes": notes, "status": "candidate_only", "subject_type": subject_type},
            aliases=_split(aliases), anchors=anchors,
        )
        workflow_id = self.workflows.create_workflow(
            case_id, f"{'Personen' if subject_type == 'person' else 'Firmen'}recherche: {name}", objective.strip() or f"Öffentliche, fallgebundene Recherche zu {name}",
            actor, target_id=target["target_id"],
            approved_scope={
                "public_sources_only": True,
                "identity_confirmation": "human_review",
                "autonomous_scope_expansion": False,
                "target_id": target["target_id"],
                "subject_type": subject_type,
            },
            constraints=["Keine Zugangsumgehung", "Keine automatische Identitätsbestätigung", "Treffer bleiben candidate_only"],
        )
        self.workflows.set_gate(workflow_id, "scope", True, actor, "Fall, Zielperson und öffentliche Recherchegrenzen wurden dokumentiert.")
        self.workflows.transition(workflow_id, "planned", actor, "Rechercheprofil wurde angelegt.")
        self.workflows.transition(workflow_id, "approved", actor, "Dokumentierter Scope ist freigegeben.")
        self.workflows.transition(workflow_id, "running", actor, "Rechercheworkflow wird im Browser-Workspace gestartet.")
        self.db.execute(
            "INSERT INTO investigation_subject_links_1222 VALUES(?,?,?,?,?,?,?)",
            (_id("slink1222"), case_id, target["target_id"], entity_id, workflow_id, actor, _now()),
        )
        research = None
        if create_research_tasks:
            research = self.create_research_package(case_id=case_id, target_id=target["target_id"], engines=self.DEFAULT_ENGINES, actor=actor)
        self.audit.log("create", "investigation_subject_1222", entity_id, case_id, {
            "target_id": target["target_id"], "workflow_id": workflow_id, "research_tasks_created": bool(research), "subject_type": subject_type,
        })
        return {"target": target, "resolution_entity_id": entity_id, "workflow_id": workflow_id, "research": research, "subject_type": subject_type}

    def create_research_package(self, *, case_id: str, target_id: str, engines: Iterable[str], actor: str) -> dict[str, Any]:
        self._target(case_id, target_id)
        selected = [engine for engine in engines if engine in self.DEFAULT_ENGINES]
        if not selected:
            selected = list(self.DEFAULT_ENGINES)
        if self.scale is not None:
            result = self.scale.create_adaptive_research(case_id=case_id, target_id=target_id, engines=selected, actor=actor, limit=80)
        else:
            result = self.search_workbench.create_packages_from_target(case_id, target_id, engines=selected)
        self.audit.log("create", "research_package_1222", target_id, case_id, {"engines": selected, "result": result, "adaptive": self.scale is not None})
        return result

    def _synthetic_run(
        self, *, case_id: str, target_id: str, provider_key: str, query: str,
        purpose: str, actor: str, result_count: int,
    ) -> str:
        run_id, now = _id("prun1222"), _now()
        self.db.execute(
            """INSERT INTO provider_runs_120(
                run_id,case_id,target_id,provider_key,search_intent_id,search_query_id,query_text,purpose,
                approved_by,mode,status,correlation_id,request_count,attempt_count,result_count,duplicate_count,
                information_gain,error_class,error_text,started_at,completed_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (run_id, case_id, target_id or None, provider_key, None, None, query[:5000], purpose[:2000], actor,
             "local_bridge", "completed", _id("corr1222"), 0, 0, int(result_count), 0, 0.0, "", "", now, now),
        )
        return run_id

    def _insert_intake(
        self, *, case_id: str, target_id: str, run_id: str, provider_key: str,
        title: str, url: str, snippet: str, source_type: str, published_at: str,
        raw_payload: dict[str, Any], source_kind: str, source_id: str, actor: str,
    ) -> tuple[str, bool]:
        existing = self.db.one(
            "SELECT intake_id FROM intake_bridges_1222 WHERE case_id=? AND source_kind=? AND source_id=?",
            (case_id, source_kind, source_id),
        )
        if existing:
            return str(existing["intake_id"]), True
        canonical = (url or "").strip()
        host = (urlsplit(canonical).hostname or "").casefold()
        fingerprint = hashlib.sha256(_json([title.casefold(), canonical, snippet, raw_payload]).encode("utf-8")).hexdigest()
        intake_id = _id("pint1222")
        now = _now()
        try:
            with self.db.transaction(immediate=True):
                self.db.execute(
                    """INSERT INTO provider_intake_120(
                        intake_id,case_id,target_id,run_id,provider_key,title,url,canonical_url,source_host,
                        snippet,source_type,published_at,content_fingerprint,raw_payload_json,review_status,
                        candidate_only,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (intake_id, case_id, target_id or None, run_id, provider_key, title[:1000], canonical[:4000],
                     canonical[:4000], host[:253], snippet[:10000], source_type[:100], published_at[:100],
                     fingerprint, _json(raw_payload), "new", 1, now, now),
                )
                self.db.execute(
                    "INSERT INTO intake_bridges_1222 VALUES(?,?,?,?,?,?,?)",
                    (_id("ibr1222"), case_id, source_kind, source_id, intake_id, actor, now),
                )
            return intake_id, False
        except sqlite3.IntegrityError:
            row = self.db.one(
                "SELECT intake_id FROM provider_intake_120 WHERE case_id=? AND provider_key=? AND canonical_url=? AND content_fingerprint=?",
                (case_id, provider_key, canonical, fingerprint),
            )
            if not row:
                raise
            return str(row["intake_id"]), True

    def include_manual_candidate(
        self, *, case_id: str, target_id: str, title: str, url: str, text: str,
        html_snapshot: str, source_label: str, actor: str,
    ) -> dict[str, Any]:
        self._case(case_id)
        if target_id:
            self._target(case_id, target_id)
        result = self.intake_console.include(
            case_id=case_id, url=url, text=text, html_snapshot=html_snapshot, title=title,
            source_label=source_label or "browser_workspace_1222", run_security=True, run_ai_triage=True,
        )
        finding = result.get("finding") or {}
        source_id = str(finding.get("paste_id") or result.get("event_id") or _id("manual1222"))
        run_id = self._synthetic_run(
            case_id=case_id, target_id=target_id, provider_key="manual_public_intake",
            query="manual public intake", purpose="Analyst-controlled public URL/text intake", actor=actor, result_count=1,
        )
        intake_id, duplicate = self._insert_intake(
            case_id=case_id, target_id=target_id, run_id=run_id, provider_key="manual_public_intake",
            title=title.strip() or finding.get("title") or "Manueller Recherchefund",
            url=finding.get("canonical_url") or url, snippet=(text or finding.get("content_excerpt") or "")[:10000],
            source_type="manual_public_capture", published_at="",
            raw_payload={"source": "intake_console_101", "finding": finding, "local_ai": result.get("local_ai"), "security": result.get("security")},
            source_kind="manual_intake", source_id=source_id, actor=actor,
        )
        self.audit.log("bridge", "provider_intake_120", intake_id, case_id, {"source": "manual", "duplicate": duplicate, "target_id": target_id})
        return {"intake_id": intake_id, "duplicate": duplicate, "legacy_intake": result}

    def bridge_ai_run(self, *, case_id: str, run_id: str, actor: str) -> dict[str, Any]:
        run = self.db.one("SELECT * FROM ai_search_runs_107 WHERE run_id=? AND case_id=?", (run_id, case_id))
        if not run:
            raise ValueError("AI-Suchlauf gehört nicht zu diesem Fall")
        target_id = str(run.get("target_id") or "")
        if target_id:
            self._target(case_id, target_id)
        results = self.db.all("SELECT * FROM ai_search_results_107 WHERE run_id=? AND case_id=? ORDER BY relevance DESC", (run_id, case_id))
        provider_run = self._synthetic_run(
            case_id=case_id, target_id=target_id, provider_key="ai_analyst_107",
            query=f"AI search run {run_id}", purpose="Controlled AI-assisted public web search", actor=actor, result_count=len(results),
        )
        intake_ids, duplicates = [], 0
        for item in results:
            intake_id, duplicate = self._insert_intake(
                case_id=case_id, target_id=target_id, run_id=provider_run, provider_key="ai_analyst_107",
                title=item.get("title") or "AI-Suchkandidat", url=item.get("url") or "", snippet=item.get("snippet") or "",
                source_type=item.get("source_engine") or item.get("provider") or "ai_web_search",
                published_at=item.get("published_at") or "", raw_payload={"ai_result": item, "candidate_only": True},
                source_kind="ai_result_107", source_id=str(item.get("result_id") or ""), actor=actor,
            )
            intake_ids.append(intake_id)
            duplicates += int(duplicate)
        self.audit.log("bridge", "ai_search_run_107", run_id, case_id, {"intake_count": len(intake_ids), "duplicates": duplicates})
        return {"run_id": run_id, "intake_ids": intake_ids, "intake_count": len(intake_ids), "duplicates": duplicates}

    def local_assist(self, *, case_id: str, prompt: str, actor: str) -> dict[str, Any]:
        self._case(case_id)
        result = self.local_ai.suggest_next_steps(case_id, prompt)
        self.audit.log("assist", "investigation_flow_1222", result.get("run_id", ""), case_id, {"prompt": prompt[:500], "actor": actor})
        return result

    def case_flow(self, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        targets = self.targets.list_targets(case_id)
        links = self.db.all(
            "SELECT * FROM investigation_subject_links_1222 WHERE case_id=? ORDER BY created_at DESC",
            (case_id,),
        )
        tasks = self.search_workbench.list_tasks(case_id)
        intake = self.db.one("SELECT COUNT(*) n FROM provider_intake_120 WHERE case_id=?", (case_id,))["n"]
        evidence = self.db.one("SELECT COUNT(*) n FROM evidence_packages_121 WHERE case_id=?", (case_id,))["n"]
        ai_runs = self.db.one("SELECT COUNT(*) n FROM local_ai_agent_101_runs WHERE case_id=?", (case_id,))["n"]
        web_runs = self.db.one("SELECT COUNT(*) n FROM ai_search_runs_107 WHERE case_id=?", (case_id,))["n"]
        return {
            "targets": targets, "links": links, "search_task_count": len(tasks), "intake_count": int(intake),
            "evidence_count": int(evidence), "local_ai_runs": int(ai_runs), "web_ai_runs": int(web_runs),
            "next_step": "person" if not targets else "research" if not tasks else "intake" if not intake else "assistant" if not ai_runs else "review",
        }
