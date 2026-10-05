from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse
import hashlib
import json
import secrets

BUILD = "439.0"
POLICY_ID = "phase19.ai-investigation-loop.v439"
CONFIRM = "AUTHORIZE INVESTIGATION LOOP"
VALID_STATES = {"awaiting_human_authorization", "active", "review_required", "completed", "hold"}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value):
    return hashlib.sha256(_canon(value).encode()).hexdigest()


def _clean(value, limit=2000):
    return " ".join(str(value or "").split())[:limit]


class AIInvestigationLoop439:
    """Human-authorized Phase-19 investigation control loop.

    Build 439 coordinates the existing planner, bounded research-wave, multi-agent,
    hypothesis/counterevidence, crawler-task, entity-resolution, fusion and synthesis
    layers.  It never performs network retrieval itself, never grants itself GO,
    never expands case/source scope, and never promotes an analytical hypothesis to
    truth.  External retrieval remains a separately governed adapter concern.
    """

    def __init__(
        self,
        db,
        audit,
        *,
        planner413,
        waves414,
        multi415,
        continuity416,
        hypothesis417,
        matrix418,
        synthesis419,
        registry421,
        crawler425,
        priority426,
        events422,
        content423,
        resolution437,
        fusion438,
        governance,
        actor="local-analyst",
    ):
        self.db = db
        self.audit = audit
        self.planner413 = planner413
        self.waves414 = waves414
        self.multi415 = multi415
        self.continuity416 = continuity416
        self.hypothesis417 = hypothesis417
        self.matrix418 = matrix418
        self.synthesis419 = synthesis419
        self.registry421 = registry421
        self.crawler425 = crawler425
        self.priority426 = priority426
        self.events422 = events422
        self.content423 = content423
        self.resolution437 = resolution437
        self.fusion438 = fusion438
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self):
        self.db.conn.executescript(
            """CREATE TABLE IF NOT EXISTS phase19_ai_loop_439(
            loop_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            objective TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            wave_run_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            state TEXT NOT NULL,
            max_cycles INTEGER NOT NULL,
            current_cycle INTEGER NOT NULL,
            scope_json TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ai_loop_439_case ON phase19_ai_loop_439(case_id,created_at);
            CREATE TABLE IF NOT EXISTS phase19_ai_loop_step_439(
            step_id TEXT PRIMARY KEY,
            loop_id TEXT NOT NULL,
            case_id TEXT NOT NULL,
            cycle_number INTEGER NOT NULL,
            decision TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            next_actions_json TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            record_hash TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ai_loop_step_439_loop ON phase19_ai_loop_step_439(loop_id,cycle_number);
            """
        )
        self.db.conn.commit()

    def _rh(self, row):
        return _hash({k: row[k] for k in row if k != "record_hash"})

    def _identity(self, identity):
        if not isinstance(identity, dict) or not identity.get("username") or not identity.get("user_id"):
            raise PermissionError("canonical active identity required")
        try:
            user = self.governance.identity.public_user(str(identity["username"]))
        except (KeyError, ValueError):
            raise PermissionError("canonical active identity required")
        if not user.get("active") or str(user.get("user_id")) != str(identity.get("user_id")):
            raise PermissionError("canonical active identity required")
        return {**user, "session_id": str(identity.get("session_id") or "ai-loop439")}

    def _authorize(self, identity, case_id, capability="research.run", object_id=""):
        ident = self._identity(identity)
        self.governance.authorize(
            ident,
            case_id=str(case_id),
            capability=capability,
            object_type="ai_investigation_loop_439",
            object_id=str(object_id or case_id),
        )
        return ident

    def _preflight(self, case_id):
        checks = {
            "planner413": self.planner413.verify_integrity()["valid"],
            "waves414": self.waves414.verify_integrity()["valid"],
            "multi415": self.multi415.verify_integrity()["valid"],
            "continuity416": self.continuity416.verify_integrity()["valid"],
            "hypothesis417": self.hypothesis417.verify_integrity()["valid"],
            "matrix418": self.matrix418.verify_integrity()["valid"],
            "synthesis419": self.synthesis419.verify_integrity()["valid"],
            "source_registry421": self.registry421.verify_integrity()["valid"],
            "crawler425": self.crawler425.verify_integrity()["valid"],
            "priority426": self.priority426.verify_integrity()["valid"],
            "events422": self.events422.verify_integrity()["valid"],
            "content423": self.content423.verify_integrity()["valid"],
            "entity_resolution437": self.resolution437.verify_integrity()["valid"],
            "fusion438": self.fusion438.verify_integrity()["valid"],
        }
        if not all(checks.values()):
            raise RuntimeError(
                "Build-439 investigation-loop preflight failed: "
                + ",".join(k for k, v in checks.items() if not v)
            )
        return checks

    def _decode_loop(self, row):
        d = dict(row)
        d["scope"] = json.loads(d.pop("scope_json"))
        return d

    def loop(self, loop_id):
        row = self.db.one("SELECT * FROM phase19_ai_loop_439 WHERE loop_id=?", (str(loop_id),))
        if not row:
            raise KeyError("AI investigation loop not found")
        return self._decode_loop(row)

    def loops(self, case_id):
        return [
            self._decode_loop(r)
            for r in self.db.all(
                "SELECT * FROM phase19_ai_loop_439 WHERE case_id=? ORDER BY created_at,loop_id",
                (str(case_id),),
            )
        ]

    def steps(self, loop_id):
        out = []
        for row in self.db.all(
            "SELECT * FROM phase19_ai_loop_step_439 WHERE loop_id=? ORDER BY cycle_number,created_at,step_id",
            (str(loop_id),),
        ):
            d = dict(row)
            d["snapshot"] = json.loads(d.pop("snapshot_json"))
            d["next_actions"] = json.loads(d.pop("next_actions_json"))
            out.append(d)
        return out

    def _update_loop(self, loop_id, *, state=None, current_cycle=None):
        row = dict(self.db.one("SELECT * FROM phase19_ai_loop_439 WHERE loop_id=?", (loop_id,)))
        if state is not None:
            if state not in VALID_STATES:
                raise ValueError("invalid loop state")
            row["state"] = state
        if current_cycle is not None:
            row["current_cycle"] = int(current_cycle)
        row["updated_at"] = _now()
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "UPDATE phase19_ai_loop_439 SET state=?,current_cycle=?,updated_at=?,record_hash=? WHERE loop_id=?",
            (row["state"], row["current_cycle"], row["updated_at"], row["record_hash"], loop_id),
        )
        return self.loop(loop_id)

    def _available_sources(self, *, include_fixtures=False):
        out = []
        for source in self.registry421.list_sources(enabled_only=True):
            if not include_fixtures and bool((source.get("coverage") or {}).get("fixture_only")):
                continue
            out.append(source)
        return out

    def create_loop(
        self,
        *,
        identity,
        case_id,
        objective,
        subquestions,
        allowed_source_ids=None,
        include_fixtures=False,
        max_cycles=4,
        max_collection_tasks_per_cycle=4,
    ):
        ident = self._authorize(identity, case_id)
        case_id = str(case_id or "").strip()
        objective = _clean(objective, 3000)
        if not case_id or not objective:
            raise ValueError("case_id and objective required")
        questions = [_clean(x, 1500) for x in (subquestions or []) if _clean(x, 1500)]
        if not questions:
            raise ValueError("at least one subquestion required")
        if not 1 <= int(max_cycles) <= 12:
            raise ValueError("max_cycles must be between 1 and 12")
        if not 1 <= int(max_collection_tasks_per_cycle) <= 12:
            raise ValueError("max_collection_tasks_per_cycle must be between 1 and 12")
        preflight = self._preflight(case_id)

        available = self._available_sources(include_fixtures=bool(include_fixtures))
        available_ids = {x["source_id"] for x in available}
        if allowed_source_ids is None:
            allowed = sorted(available_ids)
        else:
            requested = sorted({str(x) for x in allowed_source_ids if str(x)})
            unknown = [x for x in requested if x not in available_ids]
            if unknown:
                raise ValueError("allowed source is unavailable or outside fixture policy: " + ",".join(unknown))
            allowed = requested

        plan = self.planner413.create_plan(
            case_id=case_id,
            objective=objective,
            subquestions=questions,
            identity=ident,
            risk_constraints=[
                "case_scope_only",
                "phase19_registered_sources_only",
                "public_or_explicitly_governed_sources_only",
                "provenance_required",
                "no_access_control_bypass",
                "no_automatic_evidence_promotion",
                "no_truth_determination",
                "no_autonomous_scope_expansion",
                "network_execution_requires_separate_governed_adapter",
            ],
            stop_conditions=[
                "objective_answered_with_reviewable_provenance",
                "material_subquestions_exhausted_or_explicitly_deferred",
                "counterevidence_gap_requires_human_review",
                "new_source_or_scope_requires_human_review",
                "cycle_budget_exhausted",
            ],
        )
        wave = self.waves414.create_run(
            plan_id=plan["plan_id"],
            identity=ident,
            max_waves=int(max_cycles),
            max_searches_per_wave=int(max_collection_tasks_per_cycle),
        )
        session = self.multi415.create_session(
            plan_id=plan["plan_id"],
            wave_run_id=wave["run_id"],
            identity=ident,
        )
        loop_id = "ail439_" + secrets.token_hex(10)
        scope = {
            "allowed_source_ids": allowed,
            "include_fixtures": bool(include_fixtures),
            "max_collection_tasks_per_cycle": int(max_collection_tasks_per_cycle),
            "scope_expansion": False,
            "direct_network_authority": False,
            "remote_retrieval_requires_separate_governed_execution": True,
            "tor_requires_isolated_worker_and_separate_approval": True,
        }
        now = _now()
        row = {
            "loop_id": loop_id,
            "case_id": case_id,
            "objective": objective,
            "plan_id": plan["plan_id"],
            "wave_run_id": wave["run_id"],
            "session_id": session["session_id"],
            "state": "awaiting_human_authorization",
            "max_cycles": int(max_cycles),
            "current_cycle": 0,
            "scope_json": _canon(scope),
            "created_by": str(ident["username"]),
            "created_at": now,
            "updated_at": now,
        }
        row["record_hash"] = self._rh(row)
        self.db.execute(
            "INSERT INTO phase19_ai_loop_439 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(row.values()),
        )

        hypothesis_ids = []
        for index, question in enumerate(questions, 1):
            h = self.hypothesis417.create(
                session_id=session["session_id"],
                statement="Working hypothesis candidate for question: " + question,
                identity=ident,
            )
            self.hypothesis417.add_item(
                hypothesis_id=h["hypothesis_id"],
                item_type="open_question",
                reference=f"build439:{loop_id}:question:{index}",
                note="Question-derived AI working hypothesis. Requires support, counterevidence and human review; it is not a finding.",
                identity=ident,
            )
            hypothesis_ids.append(h["hypothesis_id"])

        self.audit.log(
            "ai_investigation_loop_created_439",
            "phase19_ai_loop_439",
            loop_id,
            case_id,
            {
                "plan_id": plan["plan_id"],
                "wave_run_id": wave["run_id"],
                "session_id": session["session_id"],
                "hypotheses": len(hypothesis_ids),
                "allowed_sources": len(allowed),
                "automatic_go": False,
                "network_execution": False,
            },
        )
        return {
            **self.loop(loop_id),
            "hypothesis_ids": hypothesis_ids,
            "preflight": preflight,
            "human_authorization_required": True,
            "confirmation_phrase": CONFIRM,
        }

    def authorize_loop(self, *, identity, loop_id, confirmation):
        loop = self.loop(loop_id)
        ident = self._authorize(identity, loop["case_id"], object_id=loop_id)
        if str(confirmation or "").strip().upper() != CONFIRM:
            raise PermissionError(f"explicit confirmation {CONFIRM} required")
        if loop["state"] != "awaiting_human_authorization":
            raise ValueError("loop is not awaiting human authorization")
        self.waves414.authorize(
            run_id=loop["wave_run_id"],
            identity=ident,
            confirmation="AUTHORIZE RESEARCH WAVES",
        )
        updated = self._update_loop(loop_id, state="active")
        self.audit.log(
            "ai_investigation_loop_authorized_439",
            "phase19_ai_loop_439",
            loop_id,
            loop["case_id"],
            {
                "bounded_autonomy": True,
                "allowed_source_ids": updated["scope"]["allowed_source_ids"],
                "direct_network_authority": False,
                "automatic_scope_expansion": False,
            },
        )
        return updated

    def _selected_sources(self, loop):
        allowed = set(loop["scope"].get("allowed_source_ids") or [])
        maxn = int(loop["scope"].get("max_collection_tasks_per_cycle") or 4)
        sources = [x for x in self._available_sources(include_fixtures=bool(loop["scope"].get("include_fixtures"))) if x["source_id"] in allowed]
        sources.sort(key=lambda x: (x.get("source_type", ""), x.get("name", ""), x["source_id"]))
        return sources[:maxn]

    def _plan_collection_tasks(self, *, identity, loop, subquestion):
        planned = []
        specialized = []
        for source in self._selected_sources(loop):
            sid = source["source_id"]
            if source.get("source_type") == "tor_onion" or source.get("access_mode") == "tor_public":
                specialized.append(
                    {
                        "source_id": sid,
                        "source_type": source.get("source_type"),
                        "action": "isolated_tor_worker_review_required",
                        "automatic_execution": False,
                    }
                )
                continue
            target = str(source.get("base_url") or "").strip()
            if not target:
                specialized.append(
                    {
                        "source_id": sid,
                        "source_type": source.get("source_type"),
                        "action": "adapter_or_local_dataset_target_required",
                        "automatic_execution": False,
                    }
                )
                continue
            parsed = urlparse(target)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                continue
            existing = self.db.one(
                "SELECT task_id FROM crawl_task_425 WHERE case_id=? AND source_id=? AND target=? ORDER BY created_at DESC LIMIT 1",
                (loop["case_id"], sid, target),
            )
            if existing:
                task = self.crawler425.get(existing["task_id"])
                created = False
            else:
                task = self.crawler425.create_task(
                    identity=identity,
                    case_id=loop["case_id"],
                    source_id=sid,
                    target=target,
                    objective=f"{loop['objective']} | {subquestion}",
                    scope={
                        "allowed_hosts": [parsed.hostname],
                        "build439_loop_id": loop["loop_id"],
                        "case_scope_only": True,
                    },
                    budget={"max_pages": 1, "max_bytes": 1000000},
                )
                self.priority426.prioritize(
                    identity=identity,
                    task_id=task["task_id"],
                    relevance=0.75,
                    urgency=0.5,
                    budget={"max_pages": 1, "max_bytes": 1000000},
                )
                created = True
            planned.append(
                {
                    "task_id": task["task_id"],
                    "source_id": sid,
                    "target": task["target"],
                    "state": task["state"],
                    "created_this_cycle": created,
                    "network_execution": False,
                }
            )
        return planned, specialized

    def _case_counts(self, case_id):
        tables = {
            "acquisition_events": ("acquisition_event_422", "case_id"),
            "content_observations": ("content_observation_423", "case_id"),
            "crawl_tasks": ("crawl_task_425", "case_id"),
            "resolution_bindings": ("phase19_entity_binding_437", "case_id"),
            "fusion_runs": ("phase19_fusion_run_438", "case_id"),
        }
        out = {}
        for key, (table, field) in tables.items():
            out[key] = int(self.db.one(f"SELECT COUNT(*) n FROM {table} WHERE {field}=?", (str(case_id),))["n"])
        return out

    def _next_actions(self, *, planned_tasks, specialized, matrix, timeline, graph, wave, decision):
        actions = []
        if planned_tasks:
            actions.append(
                {
                    "action": "governed_external_retrieval_handoff",
                    "task_ids": [x["task_id"] for x in planned_tasks],
                    "note": "Build 439 planned bounded crawl tasks; a separate governed retrieval adapter must perform network I/O.",
                    "network_execution_by_build439": False,
                }
            )
        actions.extend(specialized)
        gaps = matrix.get("gaps") or []
        if gaps:
            actions.append(
                {
                    "action": "hypothesis_gap_and_counterevidence_review",
                    "gap_count": len(gaps),
                    "gaps": gaps,
                    "automatic_hypothesis_acceptance": False,
                }
            )
        if timeline.get("temporal_disagreements"):
            actions.append(
                {
                    "action": "temporal_disagreement_review",
                    "count": len(timeline["temporal_disagreements"]),
                    "automatic_resolution": False,
                }
            )
        unresolved = graph.get("unresolved_relationship_candidates") or []
        if unresolved:
            actions.append(
                {
                    "action": "relationship_endpoint_review",
                    "count": len(unresolved),
                    "automatic_relationship_inference": False,
                }
            )
        if not planned_tasks and not specialized:
            actions.append(
                {
                    "action": "source_coverage_review",
                    "reason": "no Phase-19 source in the approved loop scope produced a collection task",
                    "automatic_scope_expansion": False,
                }
            )
        if decision == "review":
            actions.append(
                {
                    "action": "human_synthesis_review",
                    "reason": "cycle or research-wave budget reached",
                    "automatic_truth_determination": False,
                }
            )
        return actions

    def advance_loop(self, *, identity, loop_id):
        loop = self.loop(loop_id)
        ident = self._authorize(identity, loop["case_id"], object_id=loop_id)
        if loop["state"] != "active":
            raise PermissionError("AI investigation loop is not active")
        if loop["current_cycle"] >= loop["max_cycles"]:
            self._update_loop(loop_id, state="review_required")
            raise PermissionError("AI investigation loop cycle budget exhausted")
        preflight = self._preflight(loop["case_id"])
        continuity = self.continuity416.validate(session_id=loop["session_id"], identity=ident)
        wave_step = self.waves414.advance(run_id=loop["wave_run_id"], identity=ident)
        multi = self.continuity416.run_round(session_id=loop["session_id"], identity=ident)

        resolution = self.resolution437.sync_case(
            identity=ident,
            case_id=loop["case_id"],
            include_fixtures=bool(loop["scope"].get("include_fixtures")),
        )
        fusion = self.fusion438.fuse_case(
            identity=ident,
            case_id=loop["case_id"],
            include_fixtures=bool(loop["scope"].get("include_fixtures")),
        )
        timeline = self.fusion438.timeline(
            loop["case_id"], include_fixtures=bool(loop["scope"].get("include_fixtures"))
        )
        graph = self.fusion438.relationship_graph(
            loop["case_id"], include_fixtures=bool(loop["scope"].get("include_fixtures"))
        )
        matrix = self.matrix418.matrix(session_id=loop["session_id"], identity=ident)
        synthesis = self.synthesis419.synthesize(
            session_id=loop["session_id"],
            title=f"Build 439 investigation synthesis cycle {loop['current_cycle'] + 1}",
            identity=ident,
        )

        subquestion = _clean((wave_step.get("work") or {}).get("subquestion"), 1500)
        planned_tasks, specialized = self._plan_collection_tasks(
            identity=ident,
            loop=loop,
            subquestion=subquestion or loop["objective"],
        )
        cycle = loop["current_cycle"] + 1
        wave_run = self.waves414.run(loop["wave_run_id"])
        decision = "review" if cycle >= loop["max_cycles"] or wave_run["state"] == "completed" else "continue"
        snapshot = {
            "build": BUILD,
            "case_id": loop["case_id"],
            "loop_id": loop_id,
            "cycle": cycle,
            "objective": loop["objective"],
            "subquestion": subquestion,
            "preflight": preflight,
            "continuity": continuity,
            "wave_step": wave_step,
            "multi_agent_round": {
                "contribution_ids": [x["contribution_id"] for x in multi.get("contributions", [])],
                "synthesis_contribution_id": (multi.get("synthesis") or {}).get("contribution_id", ""),
            },
            "case_counts": self._case_counts(loop["case_id"]),
            "resolution_run_id": resolution["run_id"],
            "fusion_run_id": fusion["run_id"],
            "fusion_summary": fusion["result"],
            "hypothesis_count": len(matrix.get("hypotheses") or []),
            "hypothesis_gap_count": len(matrix.get("gaps") or []),
            "hypothesis_conflict_count": len(matrix.get("conflicts") or []),
            "synthesis_id": synthesis["synthesis_id"],
            "collection_tasks": planned_tasks,
            "specialized_source_actions": specialized,
            "network_execution": False,
            "automatic_go": False,
            "automatic_scope_expansion": False,
            "automatic_evidence_promotion": False,
            "truth_determined": False,
        }
        next_actions = self._next_actions(
            planned_tasks=planned_tasks,
            specialized=specialized,
            matrix=matrix,
            timeline=timeline,
            graph=graph,
            wave=wave_step,
            decision=decision,
        )
        step = {
            "step_id": "ailstep439_" + secrets.token_hex(10),
            "loop_id": loop_id,
            "case_id": loop["case_id"],
            "cycle_number": cycle,
            "decision": decision,
            "snapshot_json": _canon(snapshot),
            "next_actions_json": _canon(next_actions),
            "created_by": str(ident["username"]),
            "created_at": _now(),
        }
        step["record_hash"] = self._rh(step)
        self.db.execute(
            "INSERT INTO phase19_ai_loop_step_439 VALUES(?,?,?,?,?,?,?,?,?,?)",
            tuple(step.values()),
        )
        new_state = "review_required" if decision == "review" else "active"
        self._update_loop(loop_id, state=new_state, current_cycle=cycle)
        self.audit.log(
            "ai_investigation_loop_cycle_439",
            "phase19_ai_loop_step_439",
            step["step_id"],
            loop["case_id"],
            {
                "loop_id": loop_id,
                "cycle": cycle,
                "decision": decision,
                "collection_tasks": len(planned_tasks),
                "network_execution": False,
                "truth_determined": False,
            },
        )
        return {
            **step,
            "snapshot": snapshot,
            "next_actions": next_actions,
            "loop": self.loop(loop_id),
        }

    def report(self, loop_id, *, identity):
        loop = self.loop(loop_id)
        self._authorize(identity, loop["case_id"], capability="case.read", object_id=loop_id)
        matrix = self.matrix418.matrix(session_id=loop["session_id"], identity=identity)
        latest_synthesis = self.db.one(
            "SELECT synthesis_id FROM investigation_synthesis_419 WHERE session_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
            (loop["session_id"],),
        )
        return {
            "build": BUILD,
            "loop": loop,
            "steps": self.steps(loop_id),
            "plan": self.planner413.get_plan(loop["plan_id"]),
            "wave": self.waves414.run(loop["wave_run_id"]),
            "session": self.multi415.session(loop["session_id"]),
            "matrix": matrix,
            "latest_synthesis": self.synthesis419.get(latest_synthesis["synthesis_id"], identity=identity) if latest_synthesis else None,
            "fusion": self.fusion438.case_report(
                loop["case_id"], include_fixtures=bool(loop["scope"].get("include_fixtures"))
            ),
            "network_execution": False,
            "human_review_required": True,
            "truth_determined": False,
        }

    def run_case_selftest(self, *, identity, case_id):
        ident = self._authorize(identity, case_id)
        base = self.fusion438.run_case_selftest(identity=ident, case_id=str(case_id))
        fixture_sources = [
            x["source_id"]
            for x in self.registry421.list_sources(enabled_only=True)
            if bool((x.get("coverage") or {}).get("fixture_only"))
            and x.get("source_type") != "tor_onion"
        ]
        loop = self.create_loop(
            identity=ident,
            case_id=str(case_id),
            objective="Build 439 synthetic end-to-end investigation-loop qualification",
            subquestions=[
                "Which provenance-bound records describe the synthetic entities?",
                "What counterevidence would distinguish alternative identity interpretations?",
            ],
            allowed_source_ids=fixture_sources[:4],
            include_fixtures=True,
            max_cycles=2,
            max_collection_tasks_per_cycle=4,
        )
        blocked_before_go = False
        try:
            self.advance_loop(identity=ident, loop_id=loop["loop_id"])
        except PermissionError:
            blocked_before_go = True
        self.authorize_loop(identity=ident, loop_id=loop["loop_id"], confirmation=CONFIRM)
        step = self.advance_loop(identity=ident, loop_id=loop["loop_id"])
        matrix = self.matrix418.matrix(session_id=loop["session_id"], identity=ident)
        checks = {
            "build438_fixture_passed": base["result"] == "PASS",
            "human_go_required": blocked_before_go,
            "plan_wave_session_bound": bool(loop["plan_id"] and loop["wave_run_id"] and loop["session_id"]),
            "question_derived_working_hypotheses": len(matrix.get("hypotheses") or []) >= 2,
            "counterevidence_gap_visible": any(x.get("reason") in {"no_evidence_links", "no_counterevidence_link"} for x in matrix.get("gaps") or []),
            "bounded_collection_tasks_planned": len(step["snapshot"]["collection_tasks"]) >= 1,
            "entity_resolution_integrated": bool(step["snapshot"]["resolution_run_id"]),
            "temporal_relationship_fusion_integrated": bool(step["snapshot"]["fusion_run_id"]),
            "synthesis_created": bool(step["snapshot"]["synthesis_id"]),
            "no_direct_network_execution": step["snapshot"]["network_execution"] is False,
            "no_automatic_go": step["snapshot"]["automatic_go"] is False,
            "no_scope_expansion": step["snapshot"]["automatic_scope_expansion"] is False,
            "truth_not_determined": step["snapshot"]["truth_determined"] is False,
            "integrity_valid": self.verify_integrity()["valid"],
        }
        return {
            "build": BUILD,
            "case_id": str(case_id),
            "result": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "loop_id": loop["loop_id"],
            "step": step,
            "note": "Build 439 coordinates a bounded AI investigation loop after explicit human GO; retrieval remains a separately governed execution concern.",
        }

    def verify_integrity(self):
        bad = []
        for row in self.db.all("SELECT * FROM phase19_ai_loop_439"):
            d = dict(row)
            if self._rh(d) != d.get("record_hash"):
                bad.append({"loop_id": d.get("loop_id"), "reason": "loop_hash_mismatch"})
                continue
            if d["state"] not in VALID_STATES:
                bad.append({"loop_id": d["loop_id"], "reason": "invalid_state"})
            try:
                plan = self.planner413.get_plan(d["plan_id"])
                wave = self.waves414.run(d["wave_run_id"])
                session = self.multi415.session(d["session_id"])
                if plan["case_id"] != d["case_id"] or wave["case_id"] != d["case_id"] or session["case_id"] != d["case_id"]:
                    bad.append({"loop_id": d["loop_id"], "reason": "case_binding_mismatch"})
                if wave["plan_id"] != d["plan_id"] or session["plan_id"] != d["plan_id"]:
                    bad.append({"loop_id": d["loop_id"], "reason": "plan_binding_mismatch"})
            except KeyError:
                bad.append({"loop_id": d["loop_id"], "reason": "orphaned_dependency"})
        for row in self.db.all("SELECT * FROM phase19_ai_loop_step_439"):
            d = dict(row)
            if self._rh(d) != d.get("record_hash"):
                bad.append({"step_id": d.get("step_id"), "reason": "step_hash_mismatch"})
            parent = self.db.one("SELECT case_id,max_cycles FROM phase19_ai_loop_439 WHERE loop_id=?", (d["loop_id"],))
            if not parent:
                bad.append({"step_id": d["step_id"], "reason": "orphaned_loop"})
            elif parent["case_id"] != d["case_id"] or int(d["cycle_number"]) > int(parent["max_cycles"]):
                bad.append({"step_id": d["step_id"], "reason": "loop_step_binding_mismatch"})
        return {"build": BUILD, "valid": not bad, "violations": bad}

    def status(self):
        loops = int(self.db.one("SELECT COUNT(*) n FROM phase19_ai_loop_439")["n"])
        steps = int(self.db.one("SELECT COUNT(*) n FROM phase19_ai_loop_step_439")["n"])
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "loops": loops,
            "steps": steps,
            "integrity_valid": self.verify_integrity()["valid"],
            "ai_investigation_loop": True,
            "plan_to_synthesis_orchestration": True,
            "phase19_source_selection": True,
            "bounded_collection_task_planning": True,
            "evidence_intake_observed": True,
            "entity_resolution_integrated": True,
            "temporal_relationship_fusion_integrated": True,
            "hypothesis_counterevidence_gap_analysis": True,
            "new_research_waves_integrated": True,
            "investigation_synthesis_integrated": True,
            "explicit_human_go_required": True,
            "direct_network_authority": False,
            "external_retrieval_adapter_required": True,
            "automatic_go": False,
            "automatic_scope_expansion": False,
            "automatic_evidence_promotion": False,
            "automatic_identity_confirmation": False,
            "truth_determined": False,
            "case_scoped": True,
            "production_release_ready": False,
        }
